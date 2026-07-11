"""Layer 31A curated-file import contract.

This module defines the deterministic file and field contract for curated
market-data imports. It deliberately does not write canonical records.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.shared.provenance import ObservationStatus

REGIONS_FILE = "regions.json"
COMPANIES_FILE = "companies.csv"
PRESENCE_FILE = "presence.csv"
HIRING_FILE = "hiring.csv"
ENTRY_LEVEL_FILE = "entry_level.csv"
SOURCE_REFS_FILE = "source_refs.csv"

REQUIRED_DATASET_FILES: tuple[str, ...] = (
    REGIONS_FILE,
    COMPANIES_FILE,
    PRESENCE_FILE,
    HIRING_FILE,
    ENTRY_LEVEL_FILE,
    SOURCE_REFS_FILE,
)

REGION_REQUIRED_FIELDS: tuple[str, ...] = (
    "region_id",
    "region_name",
    "region_type",
    "country",
    "state_codes",
    "primary_city",
    "source_ref",
)

CSV_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    COMPANIES_FILE: (
        "company_id",
        "company_name",
        "sector",
        "public_or_private",
        "website_domain",
        "source_ref",
    ),
    PRESENCE_FILE: (
        "company_id",
        "region_id",
        "presence_status",
        "presence_basis",
        "office_location_summary",
        "source_ref",
    ),
    HIRING_FILE: (
        "company_id",
        "region_id",
        "role_family",
        "active_posting_count",
        "active_posting_count_status",
        "annualized_trend_signal",
        "seasonal_student_hiring_signal",
        "source_ref",
    ),
    ENTRY_LEVEL_FILE: (
        "company_id",
        "region_id",
        "internship_count",
        "internship_count_status",
        "coop_count",
        "coop_count_status",
        "entry_level_full_time_count",
        "entry_level_full_time_count_status",
        "formal_early_career_program_flag",
        "student_season_recurrence_signal",
        "source_ref",
    ),
    SOURCE_REFS_FILE: (
        "source_ref",
        "source_name",
        "source_type",
        "source_url_or_reference",
        "collected_at",
        "observed_at",
        "confidence",
        "license_or_terms_category",
        "freshness_status",
    ),
}

COUNT_FIELDS_BY_FILE: dict[str, tuple[tuple[str, str], ...]] = {
    HIRING_FILE: (("active_posting_count", "active_posting_count_status"),),
    ENTRY_LEVEL_FILE: (
        ("internship_count", "internship_count_status"),
        ("coop_count", "coop_count_status"),
        ("entry_level_full_time_count", "entry_level_full_time_count_status"),
    ),
}

OBSERVED_COUNT_STATUSES: frozenset[ObservationStatus] = frozenset(
    {
        ObservationStatus.ZERO_OBSERVED,
        ObservationStatus.POSITIVE_OBSERVED,
    }
)

UNOBSERVED_COUNT_STATUSES: frozenset[ObservationStatus] = frozenset(
    {
        ObservationStatus.UNKNOWN,
        ObservationStatus.NOT_COLLECTED,
        ObservationStatus.NOT_APPLICABLE,
    }
)

IMPORT_COUNT_STATUSES: frozenset[ObservationStatus] = (
    OBSERVED_COUNT_STATUSES | UNOBSERVED_COUNT_STATUSES
)

AMBIGUOUS_UNKNOWN_COUNT_VALUES: frozenset[str] = frozenset(
    {
        "unknown",
        "unk",
        "n/a",
        "na",
        "none",
        "null",
        "not_collected",
        "not collected",
        "not_applicable",
        "not applicable",
    }
)


@dataclass(frozen=True, slots=True)
class ImportDatasetSummary:
    region_count: int = 0
    company_count: int = 0
    presence_fact_count: int = 0
    hiring_fact_count: int = 0
    entry_level_fact_count: int = 0
    source_ref_count: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "region_count": self.region_count,
            "company_count": self.company_count,
            "presence_fact_count": self.presence_fact_count,
            "hiring_fact_count": self.hiring_fact_count,
            "entry_level_fact_count": self.entry_level_fact_count,
            "source_ref_count": self.source_ref_count,
        }
