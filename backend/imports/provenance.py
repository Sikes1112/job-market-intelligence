"""Layer 31A provenance policy for curated import files."""

from __future__ import annotations

from datetime import date, datetime

from backend.shared.freshness import FreshnessStatus
from backend.shared.provenance import LicenseTermsCategory, SourceType

IMPORT_STALENESS_DAYS = 365

ALLOWED_SOURCE_TYPES: frozenset[SourceType] = frozenset(
    {
        SourceType.COMPANY_OFFICIAL,
        SourceType.ATS_JOB_BOARD,
        SourceType.GOVERNMENT_PUBLIC_DATA,
        SourceType.REGIONAL_ECONOMIC_DATASET,
        SourceType.REPUTABLE_THIRD_PARTY_AGGREGATOR,
        SourceType.MANUAL_RESEARCH,
    }
)

ALLOWED_LICENSE_OR_TERMS_CATEGORIES: frozenset[LicenseTermsCategory] = frozenset(
    {
        LicenseTermsCategory.PUBLIC,
        LicenseTermsCategory.PERMISSIVE,
        LicenseTermsCategory.RESTRICTED,
    }
)

ALLOWED_FRESHNESS_STATUSES: frozenset[str] = frozenset(
    status.value for status in FreshnessStatus
)


def coerce_import_as_of(value: date | datetime | None) -> date:
    if value is None:
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    return value


def parse_import_date(value: str) -> date:
    """Parse the Layer 31A ISO date contract.

    The curated import files use date-only ISO-8601 values (``YYYY-MM-DD``)
    so validation remains deterministic and timezone-free.
    """

    return date.fromisoformat(value)


def is_stale_observed_at(
    observed_at: date,
    *,
    as_of: date,
    stale_after_days: int = IMPORT_STALENESS_DAYS,
) -> bool:
    return (as_of - observed_at).days > stale_after_days
