"""Canonicalize active mutable geography relationships.

Revision ID: 0043_active_geography_canonicalization
Revises: 0042_geographic_contract_closure
Create Date: 2026-10-07
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

from alembic import op

revision = "0043_active_geography_canonicalization"
down_revision = "0042_geographic_contract_closure"
branch_labels = None
depends_on = None


def _redirects(connection) -> dict[str, str]:  # noqa: ANN001
    direct = {
        row.legacy_region_id: row.canonical_region_id
        for row in connection.execute(
            sa.text(
                "SELECT legacy_region_id, canonical_region_id "
                "FROM region_canonical_redirects ORDER BY legacy_region_id"
            )
        )
    }
    resolved: dict[str, str] = {}
    for source in direct:
        current = source
        visited: set[str] = set()
        while current in direct:
            if current in visited:
                raise RuntimeError(
                    f"0043 cannot canonicalize cyclic Region redirect at {current!r}"
                )
            visited.add(current)
            current = direct[current]
        resolved[source] = current
    return resolved


def _canonical(value: str | None, redirects: dict[str, str]) -> str | None:
    return redirects.get(value, value) if value is not None else None


def _norm(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").replace("_", " ").split())


def _identity_keys(row: Any, canonical_market_id: str, provider_record_id: str) -> tuple[str, str]:
    identity_parts = str(row.canonical_identity_key).split("|")
    duplicate_parts = str(row.duplicate_group_key).split("|")
    if len(identity_parts) == 5 and len(duplicate_parts) == 4:
        identity_parts[2] = _norm(canonical_market_id)
        duplicate_parts[2] = _norm(canonical_market_id)
        return "|".join(identity_parts), "|".join(duplicate_parts)

    company = _norm(row.company_id or row.company_name or "unknown_company")
    title = _norm(row.normalized_title or "unknown_title")
    market = _norm(canonical_market_id)
    route = _norm(
        row.application_host
        or row.application_url
        or provider_record_id
        or row.current_opportunity_id
    )
    return (
        "|".join((company, title, market, row.employment_type, route)),
        "|".join((company, title, market, row.employment_type)),
    )


def _preflight_unique_pair_tables(connection, redirects: dict[str, str]) -> None:  # noqa: ANN001
    checks = (
        ("company_region_presence", "company_id", "region_id"),
        ("company_region_hiring", "company_id", "region_id"),
        ("company_region_entry_level", "company_id", "region_id"),
        ("region_market_scores", None, "region_id"),
    )
    for table, owner_column, region_column in checks:
        columns = f"{owner_column}, {region_column}" if owner_column else region_column
        seen: dict[tuple[str, ...], str] = {}
        for row in connection.execute(sa.text(f"SELECT {columns} FROM {table}")):
            region_id = getattr(row, region_column)
            canonical_region_id = _canonical(region_id, redirects)
            if canonical_region_id == region_id:
                continue
            key = (
                (str(getattr(row, owner_column)), str(canonical_region_id))
                if owner_column
                else (str(canonical_region_id),)
            )
            seen[key] = region_id
        if not seen:
            continue
        for key, legacy_region_id in seen.items():
            if owner_column:
                collision = connection.execute(
                    sa.text(
                        f"SELECT 1 FROM {table} WHERE {owner_column} = :owner "
                        f"AND {region_column} = :region LIMIT 1"
                    ),
                    {"owner": key[0], "region": key[1]},
                ).scalar_one_or_none()
            else:
                collision = connection.execute(
                    sa.text(
                        f"SELECT 1 FROM {table} WHERE {region_column} = :region LIMIT 1"
                    ),
                    {"region": key[0]},
                ).scalar_one_or_none()
            if collision is not None:
                raise RuntimeError(
                    "0043 active geography collision requires operator reconciliation: "
                    f"{table} {key!r} already exists while canonicalizing "
                    f"{legacy_region_id!r}"
                )


def _canonicalize_sources(connection, redirects: dict[str, str]) -> None:  # noqa: ANN001
    for row in connection.execute(
        sa.text("SELECT source_id, supported_markets FROM opportunity_data_sources")
    ):
        values = _json_list(row.supported_markets)
        canonical_values = list(
            dict.fromkeys(
                _canonical(value, redirects) if isinstance(value, str) else value
                for value in values
            )
        )
        if canonical_values != values:
            connection.execute(
                sa.text(
                    "UPDATE opportunity_data_sources SET supported_markets = :markets "
                    "WHERE source_id = :source_id"
                ).bindparams(sa.bindparam("markets", type_=sa.JSON())),
                {"markets": canonical_values, "source_id": row.source_id},
            )


def _canonicalize_coverage(connection, redirects: dict[str, str]) -> None:  # noqa: ANN001
    rows = connection.execute(
        sa.text(
            "SELECT coverage_id, market_key, market_id, role_family, opportunity_type "
            "FROM opportunity_coverage_contracts ORDER BY coverage_id"
        )
    ).all()
    projected: dict[tuple[str, str, str], str] = {}
    changes: list[tuple[Any, str, str | None]] = []
    for row in rows:
        market_key = _canonical(row.market_key, redirects) or row.market_key
        market_id = _canonical(row.market_id, redirects)
        key = (market_key, row.role_family, row.opportunity_type)
        prior = projected.get(key)
        if prior is not None and prior != row.coverage_id:
            raise RuntimeError(
                "0043 coverage scope collision after Region canonicalization: "
                f"{prior!r} and {row.coverage_id!r} -> {key!r}"
            )
        projected[key] = row.coverage_id
        if market_key != row.market_key or market_id != row.market_id:
            changes.append((row, market_key, market_id))

    for row, market_key, market_id in changes:
        label = None
        if market_id is not None:
            label = connection.execute(
                sa.text("SELECT display_name FROM regions WHERE region_id = :region_id"),
                {"region_id": market_id},
            ).scalar_one_or_none()
        connection.execute(
            sa.text(
                "UPDATE opportunity_coverage_contracts SET market_key = :market_key, "
                "market_id = :market_id, market_label = COALESCE(:label, market_label) "
                "WHERE coverage_id = :coverage_id"
            ),
            {
                "market_key": market_key,
                "market_id": market_id,
                "label": label,
                "coverage_id": row.coverage_id,
            },
        )


def _merge_json_lists(*values: Any) -> list[Any]:
    result: list[Any] = []
    for value in values:
        for item in _json_list(value):
            if item not in result:
                result.append(item)
    return result


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return []
        return decoded if isinstance(decoded, list) else []
    return []


def _canonicalize_current_opportunities(connection, redirects: dict[str, str]) -> None:  # noqa: ANN001
    rows = connection.execute(
        sa.text(
            "SELECT current_opportunity_id, canonical_identity_key, duplicate_group_key, "
            "company_id, company_name, normalized_title, employment_type, market_id, "
            "application_host, application_url, canonical_status, freshness_state, "
            "ranking_eligible, ranking_ineligible_reasons, warnings, source_count, "
            "first_observed_at, last_observed_at, last_collected_at, canonical_updated_at, "
            "created_at FROM current_opportunities ORDER BY created_at, current_opportunity_id"
        )
    ).all()
    existing_by_key = {row.canonical_identity_key: row for row in rows}
    projected: list[tuple[Any, str, str, str]] = []
    for row in rows:
        canonical_market_id = _canonical(row.market_id, redirects)
        if canonical_market_id == row.market_id or canonical_market_id is None:
            continue
        provider_record_id = connection.execute(
            sa.text(
                "SELECT provider_record_id FROM current_opportunity_source_links "
                "WHERE current_opportunity_id = :opportunity_id "
                "ORDER BY created_at, current_opportunity_source_link_id LIMIT 1"
            ),
            {"opportunity_id": row.current_opportunity_id},
        ).scalar_one_or_none()
        identity_key, duplicate_key = _identity_keys(
            row, canonical_market_id, provider_record_id or ""
        )
        projected.append((row, canonical_market_id, identity_key, duplicate_key))

    for row, canonical_market_id, identity_key, duplicate_key in projected:
        survivor = existing_by_key.get(identity_key)
        if survivor is not None and survivor.current_opportunity_id != row.current_opportunity_id:
            survivor_id = survivor.current_opportunity_id
            loser_id = row.current_opportunity_id
            for table in (
                "current_opportunity_source_links",
                "current_opportunity_identity_evidence",
                "product_analytics_events",
                "support_cases",
            ):
                connection.execute(
                    sa.text(
                        f"UPDATE {table} SET current_opportunity_id = :survivor "
                        "WHERE current_opportunity_id = :loser"
                    ),
                    {"survivor": survivor_id, "loser": loser_id},
                )
            warnings = _merge_json_lists(
                survivor.warnings,
                row.warnings,
                [f"merged_active_geography:{loser_id}:{row.market_id}:{canonical_market_id}"],
            )
            reasons = _merge_json_lists(
                survivor.ranking_ineligible_reasons,
                row.ranking_ineligible_reasons,
            )
            active_links = connection.execute(
                sa.text(
                    "SELECT COUNT(*) FROM current_opportunity_source_links "
                    "WHERE current_opportunity_id = :opportunity_id AND active = :active"
                ),
                {"opportunity_id": survivor_id, "active": True},
            ).scalar_one()
            connection.execute(
                sa.text(
                    "UPDATE current_opportunities SET warnings = :warnings, "
                    "ranking_ineligible_reasons = :reasons, source_count = :source_count, "
                    "first_observed_at = CASE WHEN first_observed_at IS NULL OR "
                    ":first_observed_at < first_observed_at THEN :first_observed_at "
                    "ELSE first_observed_at END, "
                    "last_observed_at = CASE WHEN last_observed_at IS NULL OR "
                    ":last_observed_at > last_observed_at THEN :last_observed_at "
                    "ELSE last_observed_at END, "
                    "last_collected_at = CASE WHEN last_collected_at IS NULL OR "
                    ":last_collected_at > last_collected_at THEN :last_collected_at "
                    "ELSE last_collected_at END, "
                    "ranking_eligible = CASE WHEN ranking_eligible = :active OR "
                    ":loser_ranking = :active THEN :active ELSE :inactive END "
                    "WHERE current_opportunity_id = :survivor"
                ).bindparams(
                    sa.bindparam("warnings", type_=sa.JSON()),
                    sa.bindparam("reasons", type_=sa.JSON()),
                ),
                {
                    "warnings": warnings,
                    "reasons": reasons,
                    "source_count": active_links,
                    "first_observed_at": row.first_observed_at,
                    "last_observed_at": row.last_observed_at,
                    "last_collected_at": row.last_collected_at,
                    "loser_ranking": row.ranking_eligible,
                    "active": True,
                    "inactive": False,
                    "survivor": survivor_id,
                },
            )
            connection.execute(
                sa.text(
                    "DELETE FROM current_opportunities "
                    "WHERE current_opportunity_id = :opportunity_id"
                ),
                {"opportunity_id": loser_id},
            )
            continue

        label = connection.execute(
            sa.text("SELECT display_name FROM regions WHERE region_id = :region_id"),
            {"region_id": canonical_market_id},
        ).scalar_one()
        connection.execute(
            sa.text(
                "UPDATE current_opportunities SET market_id = :market_id, "
                "market_label = :market_label, canonical_identity_key = :identity_key, "
                "duplicate_group_key = :duplicate_key, canonical_updated_at = :now "
                "WHERE current_opportunity_id = :opportunity_id"
            ),
            {
                "market_id": canonical_market_id,
                "market_label": label,
                "identity_key": identity_key,
                "duplicate_key": duplicate_key,
                "now": datetime.now(UTC),
                "opportunity_id": row.current_opportunity_id,
            },
        )
        existing_by_key.pop(row.canonical_identity_key, None)
        existing_by_key[identity_key] = row


def _canonicalize_active_region_columns(connection, redirects: dict[str, str]) -> None:  # noqa: ANN001
    for legacy_region_id, canonical_region_id in redirects.items():
        for table in (
            "company_region_presence",
            "company_region_hiring",
            "company_region_entry_level",
            "region_market_scores",
        ):
            connection.execute(
                sa.text(
                    f"UPDATE {table} SET region_id = :canonical "
                    "WHERE region_id = :legacy"
                ),
                {"canonical": canonical_region_id, "legacy": legacy_region_id},
            )

        duplicate_bindings = connection.execute(
            sa.text(
                "SELECT legacy.opportunity_region_binding_id "
                "FROM opportunity_region_bindings AS legacy "
                "JOIN opportunity_region_bindings AS canonical "
                "ON canonical.opportunity_id = legacy.opportunity_id "
                "AND canonical.region_id = :canonical "
                "WHERE legacy.region_id = :legacy"
            ),
            {"canonical": canonical_region_id, "legacy": legacy_region_id},
        ).scalars()
        for binding_id in duplicate_bindings:
            connection.execute(
                sa.text(
                    "DELETE FROM opportunity_region_bindings "
                    "WHERE opportunity_region_binding_id = :binding_id"
                ),
                {"binding_id": binding_id},
            )
        connection.execute(
            sa.text(
                "UPDATE opportunity_region_bindings SET region_id = :canonical "
                "WHERE region_id = :legacy"
            ),
            {"canonical": canonical_region_id, "legacy": legacy_region_id},
        )


def upgrade() -> None:
    connection = op.get_bind()
    redirects = _redirects(connection)
    if not redirects:
        return
    _preflight_unique_pair_tables(connection, redirects)
    _canonicalize_coverage(connection, redirects)
    _canonicalize_current_opportunities(connection, redirects)
    _canonicalize_sources(connection, redirects)
    _canonicalize_active_region_columns(connection, redirects)


def downgrade() -> None:
    # Active canonical relationships intentionally remain canonical. Restoring
    # redirect-source IDs would manufacture current state from historical IDs.
    pass
