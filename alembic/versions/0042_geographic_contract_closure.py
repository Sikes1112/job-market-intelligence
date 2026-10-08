"""Close canonical geography compatibility and ownership contracts.

Revision ID: 0042_geographic_contract_closure
Revises: 0041_canonical_geographic_foundation
Create Date: 2026-10-07
"""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision = "0042_geographic_contract_closure"
down_revision = "0041_canonical_geographic_foundation"
branch_labels = None
depends_on = None

_SF_CANONICAL_ID = "sf_bay_area"
_SF_LEGACY_ID = "greater_sf"
_SF_SLUG = "san-francisco-bay-area"
_SF_ALIASES = (
    ("san_francisco_bay_area", "import_key"),
    ("greater_sf", "legacy_id"),
    ("Bay Area", "alternate_name"),
    ("SF Bay Area", "abbreviation"),
    ("San Francisco", "city_alias"),
)


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    return re.sub(r"[\s_\-/,\.]+", " ", normalized).strip()


def _preflight(connection) -> None:  # noqa: ANN001
    regions = connection.execute(
        sa.text("SELECT region_id, public_slug FROM regions ORDER BY region_id")
    ).all()
    region_ids = {row.region_id for row in regions}
    owners: dict[str, str] = {}

    def effective(region_id: str) -> str:
        return _SF_CANONICAL_ID if region_id == _SF_LEGACY_ID else region_id

    def claim(value: str, region_id: str) -> None:
        token = _normalize(value)
        owner = effective(region_id)
        prior = owners.get(token)
        if prior is not None and prior != owner:
            raise RuntimeError(
                "0042 geographic identity conflict for normalized token "
                f"{token!r}: {prior!r} vs {owner!r}"
            )
        owners[token] = owner

    for row in regions:
        claim(row.region_id, row.region_id)
        if row.public_slug:
            claim(row.public_slug, row.region_id)
    for row in connection.execute(
        sa.text("SELECT region_id, alias FROM region_aliases ORDER BY region_alias_id")
    ):
        claim(row.alias, row.region_id)

    if _SF_LEGACY_ID in region_ids or _SF_CANONICAL_ID in region_ids:
        claim(_SF_CANONICAL_ID, _SF_CANONICAL_ID)
        claim(_SF_SLUG, _SF_CANONICAL_ID)
        for alias, _alias_type in _SF_ALIASES:
            claim(alias, _SF_CANONICAL_ID)

    invalid_expansion_ref = connection.execute(
        sa.text(
            "SELECT canonical_region_id FROM region_expansion_workflows "
            "WHERE canonical_region_id IS NOT NULL "
            "AND canonical_region_id NOT IN (SELECT region_id FROM regions) LIMIT 1"
        )
    ).scalar_one_or_none()
    if invalid_expansion_ref is not None:
        raise RuntimeError(
            "0042 cannot enforce canonical Region Expansion references; unknown Region "
            f"{invalid_expansion_ref!r}"
        )


def upgrade() -> None:
    connection = op.get_bind()
    # SQLite migration DDL is non-transactional. Detect every data collision
    # before creating or altering tables.
    _preflight(connection)
    now = datetime.now(UTC)

    legacy_exists = connection.execute(
        sa.text("SELECT 1 FROM regions WHERE region_id = :region_id"),
        {"region_id": _SF_LEGACY_ID},
    ).scalar_one_or_none()
    canonical_exists = connection.execute(
        sa.text("SELECT 1 FROM regions WHERE region_id = :region_id"),
        {"region_id": _SF_CANONICAL_ID},
    ).scalar_one_or_none()
    if legacy_exists and not canonical_exists:
        connection.execute(
            sa.text(
                "INSERT INTO regions ("
                "region_id, region_name, display_name, region_type, parent_region_id, "
                "labor_market_group, normalization_profile_id, public_slug, primary_city, "
                "centroid_latitude, centroid_longitude, focus_bounds, market_support_status, "
                "state, version, created_at, updated_at"
                ") SELECT :canonical_id, 'sf_bay_area', "
                "'San Francisco Bay Area', region_type, parent_region_id, labor_market_group, "
                "normalization_profile_id, :public_slug, 'San Francisco', centroid_latitude, "
                "centroid_longitude, focus_bounds, 'supported', state, version, created_at, :now "
                "FROM regions WHERE region_id = :legacy_id"
            ),
            {
                "canonical_id": _SF_CANONICAL_ID,
                "legacy_id": _SF_LEGACY_ID,
                "public_slug": _SF_SLUG,
                "now": now,
            },
        )
        canonical_exists = True

    op.create_table(
        "region_canonical_redirects",
        sa.Column("legacy_region_id", sa.String(length=64), nullable=False),
        sa.Column("canonical_region_id", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "legacy_region_id <> canonical_region_id",
            name="ck_region_canonical_redirects_distinct",
        ),
        sa.ForeignKeyConstraint(["canonical_region_id"], ["regions.region_id"]),
        sa.ForeignKeyConstraint(["legacy_region_id"], ["regions.region_id"]),
        sa.PrimaryKeyConstraint("legacy_region_id"),
    )
    op.create_index(
        "ix_region_canonical_redirects_canonical",
        "region_canonical_redirects",
        ["canonical_region_id"],
    )

    if legacy_exists and canonical_exists:
        connection.execute(
            sa.text(
                "INSERT INTO region_canonical_redirects "
                "(legacy_region_id, canonical_region_id, reason, created_at) "
                "VALUES (:legacy_id, :canonical_id, :reason, :now)"
            ),
            {
                "legacy_id": _SF_LEGACY_ID,
                "canonical_id": _SF_CANONICAL_ID,
                "reason": "Layer 41A legacy Bay Area convergence",
                "now": now,
            },
        )
        connection.execute(
            sa.text(
                "UPDATE region_aliases SET region_id = :canonical_id "
                "WHERE region_id = :legacy_id"
            ),
            {"canonical_id": _SF_CANONICAL_ID, "legacy_id": _SF_LEGACY_ID},
        )

    if canonical_exists:
        connection.execute(
            sa.text(
                "UPDATE regions SET public_slug = :public_slug, primary_city = 'San Francisco', "
                "market_support_status = 'supported' WHERE region_id = :canonical_id"
            ),
            {"public_slug": _SF_SLUG, "canonical_id": _SF_CANONICAL_ID},
        )
        existing_state = connection.execute(
            sa.text(
                "SELECT 1 FROM region_state_memberships "
                "WHERE region_id = :region_id AND state_code = 'CA'"
            ),
            {"region_id": _SF_CANONICAL_ID},
        ).scalar_one_or_none()
        if not existing_state:
            connection.execute(
                sa.text(
                    "INSERT INTO region_state_memberships "
                    "(region_id, state_code, membership_type, source, created_at, updated_at) "
                    "VALUES (:region_id, 'CA', 'market_coverage', :source, :now, :now)"
                ),
                {
                    "region_id": _SF_CANONICAL_ID,
                    "source": "0042 legacy Bay Area convergence",
                    "now": now,
                },
            )
        for index, (alias, alias_type) in enumerate(_SF_ALIASES, start=1):
            normalized = _normalize(alias)
            existing_alias = connection.execute(
                sa.text(
                    "SELECT region_id FROM region_aliases WHERE normalized_alias = :normalized"
                ),
                {"normalized": normalized},
            ).scalar_one_or_none()
            if existing_alias is None:
                connection.execute(
                    sa.text(
                        "INSERT INTO region_aliases "
                        "(region_alias_id, region_id, alias, normalized_alias, alias_type, "
                        "source, created_at, updated_at) VALUES "
                        "(:alias_id, :region_id, :alias, :normalized, :alias_type, "
                        ":source, :now, :now)"
                    ),
                    {
                        "alias_id": f"geo_alias_{_SF_CANONICAL_ID}_{index}",
                        "region_id": _SF_CANONICAL_ID,
                        "alias": alias,
                        "normalized": normalized,
                        "alias_type": alias_type,
                        "source": "0042 legacy Bay Area convergence",
                        "now": now,
                    },
                )

    op.create_table(
        "region_identity_claims",
        sa.Column("normalized_token", sa.String(length=255), nullable=False),
        sa.Column("region_id", sa.String(length=64), nullable=False),
        sa.Column("claim_type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "claim_type IN ('region_id', 'public_slug', 'alias', 'legacy', 'import_key')",
            name="ck_region_identity_claims_type",
        ),
        sa.ForeignKeyConstraint(["region_id"], ["regions.region_id"]),
        sa.PrimaryKeyConstraint("normalized_token"),
    )
    op.create_index(
        "ix_region_identity_claims_region_id", "region_identity_claims", ["region_id"]
    )
    op.create_index(
        "ix_region_identity_claims_claim_type", "region_identity_claims", ["claim_type"]
    )

    claims: dict[str, tuple[str, str, str]] = {}

    def add_claim(value: str, region_id: str, claim_type: str, source: str) -> None:
        owner = _SF_CANONICAL_ID if region_id == _SF_LEGACY_ID else region_id
        token = _normalize(value)
        claims.setdefault(token, (owner, claim_type, source))

    for row in connection.execute(
        sa.text("SELECT region_id, public_slug FROM regions ORDER BY region_id")
    ):
        add_claim(
            row.region_id,
            row.region_id,
            "legacy" if row.region_id == _SF_LEGACY_ID else "region_id",
            "0042 namespace backfill",
        )
        if row.public_slug and row.region_id != _SF_LEGACY_ID:
            add_claim(row.public_slug, row.region_id, "public_slug", "0042 namespace backfill")
    for row in connection.execute(
        sa.text(
            "SELECT region_id, alias, alias_type FROM region_aliases ORDER BY region_alias_id"
        )
    ):
        add_claim(
            row.alias,
            row.region_id,
            "import_key" if row.alias_type == "import_key" else "alias",
            "0042 alias backfill",
        )
    for token, (region_id, claim_type, source) in sorted(claims.items()):
        connection.execute(
            sa.text(
                "INSERT INTO region_identity_claims "
                "(normalized_token, region_id, claim_type, source, created_at) "
                "VALUES (:token, :region_id, :claim_type, :source, :now)"
            ),
            {
                "token": token,
                "region_id": region_id,
                "claim_type": claim_type,
                "source": source,
                "now": now,
            },
        )

    if legacy_exists and canonical_exists:
        connection.execute(
            sa.text(
                "UPDATE region_expansion_workflows SET canonical_region_id = :canonical_id "
                "WHERE canonical_region_id = :legacy_id"
            ),
            {"canonical_id": _SF_CANONICAL_ID, "legacy_id": _SF_LEGACY_ID},
        )
    with op.batch_alter_table("region_expansion_workflows") as batch_op:
        batch_op.create_foreign_key(
            "fk_region_expansion_canonical_region",
            "regions",
            ["canonical_region_id"],
            ["region_id"],
        )

    op.add_column(
        "current_opportunity_identity_evidence",
        sa.Column("geography_review_status", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "current_opportunity_identity_evidence",
        sa.Column("geography_previous_region_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "current_opportunity_identity_evidence",
        sa.Column("geography_candidate_region_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "current_opportunity_identity_evidence",
        sa.Column("geography_reviewed_by", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "current_opportunity_identity_evidence",
        sa.Column("geography_reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "current_opportunity_identity_evidence",
        sa.Column("geography_review_reason", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "current_opportunity_identity_evidence",
        sa.Column("geography_corrected_region_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_current_opportunity_identity_geography_review",
        "current_opportunity_identity_evidence",
        ["geography_review_status"],
    )
    if connection.dialect.name != "sqlite":
        op.create_check_constraint(
            "ck_current_opportunity_identity_geography_review",
            "current_opportunity_identity_evidence",
            "geography_review_status IS NULL OR geography_review_status IN ('pending', 'approved')",
        )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name != "sqlite":
        op.drop_constraint(
            "ck_current_opportunity_identity_geography_review",
            "current_opportunity_identity_evidence",
            type_="check",
        )
    op.drop_index(
        "ix_current_opportunity_identity_geography_review",
        table_name="current_opportunity_identity_evidence",
    )
    for column in (
        "geography_corrected_region_id",
        "geography_review_reason",
        "geography_reviewed_at",
        "geography_reviewed_by",
        "geography_candidate_region_id",
        "geography_previous_region_id",
        "geography_review_status",
    ):
        op.drop_column("current_opportunity_identity_evidence", column)
    with op.batch_alter_table("region_expansion_workflows") as batch_op:
        batch_op.drop_constraint(
            "fk_region_expansion_canonical_region",
            type_="foreignkey",
        )
    op.drop_index("ix_region_identity_claims_claim_type", table_name="region_identity_claims")
    op.drop_index("ix_region_identity_claims_region_id", table_name="region_identity_claims")
    op.drop_table("region_identity_claims")
    op.drop_index(
        "ix_region_canonical_redirects_canonical",
        table_name="region_canonical_redirects",
    )
    op.drop_table("region_canonical_redirects")
