"""Conservative derived dataset registry for Layer 20 data licensing."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.platform.entitlements import PlatformApiTier


class LicensedDatasetId(StrEnum):
    REGIONAL_MARKET_INTELLIGENCE = "regional_market_intelligence_v1"
    EARLY_CAREER_ACCESS_SCORES = "early_career_access_scores_v1"
    COMPANY_REGION_PRESENCE = "company_region_presence_v1"
    HISTORICAL_HIRING_SIGNAL_SNAPSHOTS = "historical_hiring_signal_snapshots_v1"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class LicensedDatasetEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_id: LicensedDatasetId
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=700)
    sample_fields: tuple[str, ...] = Field(min_length=1, max_length=24)
    excluded_fields: tuple[str, ...] = Field(min_length=1, max_length=32)
    refresh_cadence: str = Field(min_length=1, max_length=160)
    allowed_formats: tuple[str, ...] = Field(min_length=1, max_length=8)
    minimum_tier: PlatformApiTier
    restrictions: tuple[str, ...] = Field(min_length=1, max_length=16)
    attribution_rules: tuple[str, ...] = Field(min_length=1, max_length=12)
    source_safety_notes: tuple[str, ...] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def _raw_fields_excluded(self) -> LicensedDatasetEntry:
        forbidden_fragments = (
            "raw_scrape",
            "raw_job",
            "source_id",
            "source_ref",
            "formula",
            "billing",
            "user_id",
            "ingestion",
        )
        sample = " ".join(self.sample_fields).casefold()
        if any(fragment in sample for fragment in forbidden_fragments):
            raise ValueError("licensed dataset sample fields must be derived and source-safe")
        excluded = " ".join(self.excluded_fields).casefold()
        missing = [fragment for fragment in forbidden_fragments if fragment not in excluded]
        if missing:
            raise ValueError(f"licensed dataset exclusions must include {missing!r}")
        return self


LICENSED_DATASETS: tuple[LicensedDatasetEntry, ...] = (
    LicensedDatasetEntry(
        dataset_id=LicensedDatasetId.REGIONAL_MARKET_INTELLIGENCE,
        title="Regional market intelligence",
        description=(
            "Derived regional opportunity, coverage, early-career, and hiring "
            "summary fields for market analysis use cases."
        ),
        sample_fields=(
            "region_id",
            "region_name",
            "coverage_tier",
            "opportunity_score",
            "live_market_score",
            "early_career_access_score",
            "currently_hiring_company_count",
        ),
        excluded_fields=(
            "raw_scrape_records",
            "raw_job_records",
            "source_ids",
            "source_refs",
            "scoring_formulas",
            "billing_records",
            "user_id",
            "ingestion_metadata",
        ),
        refresh_cadence="Monthly or contract-defined refresh windows.",
        allowed_formats=("csv", "json", "parquet"),
        minimum_tier=PlatformApiTier.ENTERPRISE,
        restrictions=(
            "No resale as raw job listings.",
            "No use as the sole basis for employment or credit decisions.",
            "No attempt to reverse-engineer source providers or scoring internals.",
        ),
        attribution_rules=(
            "Display Job Market Intelligence attribution in derived reports.",
            "Preserve freshness and confidence labels.",
        ),
        source_safety_notes=(
            "Source ids and raw records are excluded.",
            "Outputs are derived market summaries only.",
        ),
    ),
    LicensedDatasetEntry(
        dataset_id=LicensedDatasetId.EARLY_CAREER_ACCESS_SCORES,
        title="Early-career access scores",
        description="Derived internship, co-op, entry-level, and early-career access indicators.",
        sample_fields=(
            "region_id",
            "region_name",
            "early_career_access_score",
            "internship_count",
            "coop_count",
            "entry_level_full_time_count",
            "confidence_label",
        ),
        excluded_fields=(
            "raw_scrape_records",
            "raw_job_records",
            "source_ids",
            "source_refs",
            "scoring_formulas",
            "billing_records",
            "user_id",
            "ingestion_metadata",
        ),
        refresh_cadence="Monthly with explicit freshness metadata.",
        allowed_formats=("csv", "json"),
        minimum_tier=PlatformApiTier.GROWTH,
        restrictions=(
            "No applicant profiling or automated decisioning.",
            "No claim of comprehensive job-market coverage.",
        ),
        attribution_rules=(
            "Show source-safety and freshness notes near exported analysis.",
            "Use the dataset title and version in citations.",
        ),
        source_safety_notes=(
            "Counts are derived summaries, not raw postings.",
            "Small or missing evidence remains labeled as unknown or partial.",
        ),
    ),
    LicensedDatasetEntry(
        dataset_id=LicensedDatasetId.COMPANY_REGION_PRESENCE,
        title="Company-region presence",
        description="Derived employer presence and public-safe regional activity summaries.",
        sample_fields=(
            "company_id",
            "company_name",
            "sector",
            "region_id",
            "region_name",
            "presence_status",
            "current_hiring",
            "coverage_tier",
        ),
        excluded_fields=(
            "raw_scrape_records",
            "raw_job_records",
            "source_ids",
            "source_refs",
            "scoring_formulas",
            "billing_records",
            "user_id",
            "ingestion_metadata",
        ),
        refresh_cadence="Monthly or contract-defined refresh windows.",
        allowed_formats=("csv", "json", "parquet"),
        minimum_tier=PlatformApiTier.ENTERPRISE,
        restrictions=(
            "No employer CRM enrichment with raw source provenance.",
            "No redistribution as a source feed.",
        ),
        attribution_rules=(
            "Retain Job Market Intelligence attribution.",
            "Retain coverage tier and confidence labels.",
        ),
        source_safety_notes=(
            "Presence basis is summarized without source refs.",
            "Private user or institution data is excluded.",
        ),
    ),
    LicensedDatasetEntry(
        dataset_id=LicensedDatasetId.HISTORICAL_HIRING_SIGNAL_SNAPSHOTS,
        title="Historical hiring signal snapshots",
        description=(
            "Derived time-window snapshots of hiring concentration and market "
            "signal changes."
        ),
        sample_fields=(
            "snapshot_month",
            "region_id",
            "region_name",
            "active_posting_count",
            "posting_count_30d",
            "posting_count_90d",
            "concentration_share",
            "freshness_status",
        ),
        excluded_fields=(
            "raw_scrape_records",
            "raw_job_records",
            "source_ids",
            "source_refs",
            "scoring_formulas",
            "billing_records",
            "user_id",
            "ingestion_metadata",
        ),
        refresh_cadence="Monthly snapshot delivery when historical coverage is available.",
        allowed_formats=("csv", "json", "parquet"),
        minimum_tier=PlatformApiTier.ENTERPRISE,
        restrictions=(
            "No reconstruction of raw posting feeds.",
            "No use as real-time labor-market truth.",
            "Historical gaps must remain visible in downstream products.",
        ),
        attribution_rules=(
            "Cite dataset id and snapshot month.",
            "Preserve freshness and source-safety notes.",
        ),
        source_safety_notes=(
            "Snapshots are aggregated and derived.",
            "Raw jobs, source ids, and ingestion metadata are excluded.",
        ),
    ),
)


def list_licensed_datasets() -> tuple[LicensedDatasetEntry, ...]:
    return LICENSED_DATASETS


def get_licensed_dataset(dataset_id: LicensedDatasetId | str) -> LicensedDatasetEntry | None:
    normalized = LicensedDatasetId(dataset_id)
    for entry in LICENSED_DATASETS:
        if entry.dataset_id is normalized:
            return entry
    return None
