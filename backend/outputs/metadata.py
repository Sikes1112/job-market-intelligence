"""source_version_bundle + freshness aggregation helpers.

Pure functions over the canonical model rows the builders read. Nothing in
this module touches the database directly or imports any service.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore


def _ensure_aware(value: datetime) -> datetime:
    """Attach UTC if the datetime is naive.

    SQLite (the MVP default backend) round-trips
    ``DateTime(timezone=True)`` columns as naive datetimes. Treating those
    as UTC keeps freshness comparisons well-defined and matches the values
    originally written.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def aggregate_freshness_expires_at(
    *windows: datetime | None,
) -> datetime | None:
    """Return the minimum non-null timestamp across ``windows`` (or ``None``).

    Naive datetimes in the input are normalized to UTC.
    """
    non_null = [_ensure_aware(w) for w in windows if w is not None]
    if not non_null:
        return None
    return min(non_null)


def aggregate_freshness_from_iterables(
    *iterables: Iterable[datetime | None],
) -> datetime | None:
    """Convenience: flatten and aggregate."""
    flat: list[datetime | None] = []
    for it in iterables:
        flat.extend(it)
    return aggregate_freshness_expires_at(*flat)


# ---------------------------------------------------------------------------
# source_version_bundle builders
# ---------------------------------------------------------------------------


def _versions_by_id(rows: Iterable[Any], id_attr: str) -> dict[str, int]:
    """Return ``{<row id>: version}`` sorted by id (deterministic JSON)."""
    out = {getattr(r, id_attr): r.version for r in rows}
    return dict(sorted(out.items()))


def region_source_version_bundle(
    *,
    region: Region,
    region_market_score: RegionMarketScore | None,
    present_companies: Iterable[Company],
    presence_rows: Iterable[CompanyRegionPresence],
    hiring_rows: Iterable[CompanyRegionHiring],
    entry_level_rows: Iterable[CompanyRegionEntryLevel],
) -> dict[str, Any]:
    bundle: dict[str, Any] = {
        "region_version": region.version,
        "region_market_score_version": (
            region_market_score.version if region_market_score is not None else None
        ),
        "score_ruleset_version": (
            region_market_score.score_ruleset_version
            if region_market_score is not None
            else None
        ),
        "company_versions": _versions_by_id(present_companies, "company_id"),
        "presence_versions": _versions_by_id(presence_rows, "presence_id"),
        "hiring_versions": _versions_by_id(hiring_rows, "hiring_id"),
        "entry_level_versions": _versions_by_id(entry_level_rows, "entry_level_id"),
    }
    return bundle


def company_source_version_bundle(
    *,
    company: Company,
    regions: Iterable[Region],
    presence_rows: Iterable[CompanyRegionPresence],
    hiring_rows: Iterable[CompanyRegionHiring],
    entry_level_rows: Iterable[CompanyRegionEntryLevel],
) -> dict[str, Any]:
    bundle: dict[str, Any] = {
        "company_version": company.version,
        "region_versions": _versions_by_id(regions, "region_id"),
        "presence_versions": _versions_by_id(presence_rows, "presence_id"),
        "hiring_versions": _versions_by_id(hiring_rows, "hiring_id"),
        "entry_level_versions": _versions_by_id(entry_level_rows, "entry_level_id"),
    }
    return bundle


def comparison_source_version_bundle(
    *,
    comparison_subject_id: str,
    region_a: Region,
    region_b: Region,
    score_a: RegionMarketScore | None,
    score_b: RegionMarketScore | None,
) -> dict[str, Any]:
    return {
        "comparison_subject_id": comparison_subject_id,
        "region_a": {
            "region_id": region_a.region_id,
            "region_version": region_a.version,
            "region_market_score_version": score_a.version if score_a else None,
            "score_ruleset_version": (
                score_a.score_ruleset_version if score_a else None
            ),
        },
        "region_b": {
            "region_id": region_b.region_id,
            "region_version": region_b.version,
            "region_market_score_version": score_b.version if score_b else None,
            "score_ruleset_version": (
                score_b.score_ruleset_version if score_b else None
            ),
        },
    }
