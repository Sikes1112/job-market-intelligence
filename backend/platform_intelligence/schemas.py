"""Schemas and API-safe DTOs for Layer 18A historical intelligence."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from ipaddress import ip_address
from typing import Any
from urllib.parse import parse_qsl, urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class SnapshotType(_Vocabulary):
    OBSERVED = "observed"
    BACKFILL = "backfill"
    CORRECTION = "correction"


class HistoricalObservationType(_Vocabulary):
    COMPANY_PRESENCE_INCREASED = "company_presence_increased"
    COMPANY_PRESENCE_DECREASED = "company_presence_decreased"
    HIRING_ACTIVITY_INCREASED = "hiring_activity_increased"
    HIRING_ACTIVITY_DECREASED = "hiring_activity_decreased"
    ENTRY_LEVEL_ACCESS_IMPROVED = "entry_level_access_improved"
    ENTRY_LEVEL_ACCESS_DECLINED = "entry_level_access_declined"
    REGIONAL_SCORE_INCREASED = "regional_score_increased"
    REGIONAL_SCORE_DECREASED = "regional_score_decreased"
    SECTOR_GROWTH_DETECTED = "sector_growth_detected"
    SECTOR_DECLINE_DETECTED = "sector_decline_detected"
    INTERNSHIP_DENSITY_CHANGED = "internship_density_changed"


class HistoricalTargetType(_Vocabulary):
    REGION = "region"
    COMPANY_REGION = "company_region"
    SECTOR_REGION = "sector_region"


class DeltaDirection(_Vocabulary):
    INCREASED = "increased"
    DECREASED = "decreased"
    CHANGED = "changed"


class ObservationSeverity(_Vocabulary):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PredictiveSignalType(_Vocabulary):
    EMERGING_MARKET = "emerging_market"
    DECLINING_MARKET = "declining_market"
    SEASONAL_HIRING_WINDOW = "seasonal_hiring_window"
    COMPANY_EXPANSION_SIGNAL = "company_expansion_signal"
    ENTRY_LEVEL_ACCESS_TREND = "entry_level_access_trend"


class PredictiveSignalStatus(_Vocabulary):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    EXPIRED = "expired"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class SignalStrength(_Vocabulary):
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"


class ConfidenceLevel(_Vocabulary):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class MarketIndexStatus(_Vocabulary):
    ACTIVE = "active"
    INACTIVE = "inactive"
    RETIRED = "retired"


class MarketIndexVersionStatus(_Vocabulary):
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class _SnapshotCreateBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_date: date
    snapshot_type: SnapshotType = SnapshotType.OBSERVED
    overall_score: float | None = None
    entry_level_access_score: float | None = None
    internship_density_score: float | None = None
    ai_opportunity_score: float | None = None
    product_opportunity_score: float | None = None
    company_presence_score: float | None = None
    hidden_opportunity_score: float | None = None
    coverage_tier: str | None = Field(default=None, min_length=1, max_length=32)
    freshness_state: str | None = Field(default=None, min_length=1, max_length=32)
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    warnings: tuple[Any, ...] = Field(default_factory=tuple)
    provenance_summary: dict[str, Any] | list[Any] | None = None
    created_at: datetime | None = None

    @field_validator("coverage_tier", "freshness_state")
    @classmethod
    def _optional_string_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("created_at")
    @classmethod
    def _created_at_must_be_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return value


class MarketSnapshotCreate(_SnapshotCreateBase):
    market_snapshot_id: str | None = Field(default=None, min_length=1, max_length=64)
    region_id: str = Field(min_length=1, max_length=64)
    score_ruleset_version: str | None = Field(default=None, min_length=1, max_length=64)
    ranking_position: int | None = Field(default=None, ge=1)

    @field_validator("market_snapshot_id", "region_id", "score_ruleset_version")
    @classmethod
    def _market_strings_not_blank(cls, value: str | None) -> str | None:
        return _clean_optional_string(value)


class CompanyRegionSnapshotCreate(_SnapshotCreateBase):
    company_region_snapshot_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
    )
    company_id: str = Field(min_length=1, max_length=64)
    region_id: str = Field(min_length=1, max_length=64)
    hiring_activity_score: float | None = None
    presence_status: str | None = Field(default=None, min_length=1, max_length=32)
    currently_hiring_flag: bool | None = None
    active_posting_count: int | None = Field(default=None, ge=0)
    posting_count_30d: int | None = Field(default=None, ge=0)
    posting_count_90d: int | None = Field(default=None, ge=0)
    internship_count: int | None = Field(default=None, ge=0)

    @field_validator(
        "company_region_snapshot_id",
        "company_id",
        "region_id",
        "presence_status",
    )
    @classmethod
    def _company_strings_not_blank(cls, value: str | None) -> str | None:
        return _clean_optional_string(value)


class SectorRegionSnapshotCreate(_SnapshotCreateBase):
    sector_region_snapshot_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
    )
    sector_id: str = Field(min_length=1, max_length=64)
    region_id: str = Field(min_length=1, max_length=64)
    hiring_activity_score: float | None = None
    sector_company_count: int | None = Field(default=None, ge=0)
    active_company_count: int | None = Field(default=None, ge=0)

    @field_validator("sector_region_snapshot_id", "sector_id", "region_id")
    @classmethod
    def _sector_strings_not_blank(cls, value: str | None) -> str | None:
        return _clean_optional_string(value)


class HistoricalObservationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str
    observation_type: HistoricalObservationType
    target_type: HistoricalTargetType
    target_id: str
    region_id: str | None = None
    previous_snapshot_id: str | None = None
    current_snapshot_id: str
    delta_value: float | None = None
    delta_direction: DeltaDirection
    severity: ObservationSeverity
    confidence_score: float | None = None
    evidence_summary: dict[str, Any] | list[Any] | None = None
    created_at: datetime


class MarketSnapshotSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_id: str
    region_id: str
    snapshot_date: date
    snapshot_type: SnapshotType
    overall_score: float | None = None
    entry_level_access_score: float | None = None
    internship_density_score: float | None = None
    ai_opportunity_score: float | None = None
    product_opportunity_score: float | None = None
    company_presence_score: float | None = None
    hidden_opportunity_score: float | None = None
    coverage_tier: str | None = None
    freshness_state: str | None = None
    confidence_score: float | None = None
    warnings: tuple[Any, ...] = Field(default_factory=tuple)
    created_at: datetime


class CompanyRegionSnapshotSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_id: str
    company_id: str
    region_id: str
    snapshot_date: date
    snapshot_type: SnapshotType
    overall_score: float | None = None
    entry_level_access_score: float | None = None
    internship_density_score: float | None = None
    ai_opportunity_score: float | None = None
    product_opportunity_score: float | None = None
    company_presence_score: float | None = None
    hiring_activity_score: float | None = None
    hidden_opportunity_score: float | None = None
    presence_status: str | None = None
    currently_hiring_flag: bool | None = None
    active_posting_count: int | None = None
    posting_count_30d: int | None = None
    posting_count_90d: int | None = None
    internship_count: int | None = None
    coverage_tier: str | None = None
    freshness_state: str | None = None
    confidence_score: float | None = None
    warnings: tuple[Any, ...] = Field(default_factory=tuple)
    created_at: datetime


class SectorRegionSnapshotSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_id: str
    sector_id: str
    region_id: str
    snapshot_date: date
    snapshot_type: SnapshotType
    overall_score: float | None = None
    entry_level_access_score: float | None = None
    internship_density_score: float | None = None
    ai_opportunity_score: float | None = None
    product_opportunity_score: float | None = None
    company_presence_score: float | None = None
    hiring_activity_score: float | None = None
    hidden_opportunity_score: float | None = None
    sector_company_count: int | None = None
    active_company_count: int | None = None
    coverage_tier: str | None = None
    freshness_state: str | None = None
    confidence_score: float | None = None
    warnings: tuple[Any, ...] = Field(default_factory=tuple)
    created_at: datetime


class RegionHistorySummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str
    market_snapshots: tuple[MarketSnapshotSummary, ...] = Field(default_factory=tuple)
    sector_snapshots: tuple[SectorRegionSnapshotSummary, ...] = Field(default_factory=tuple)
    observations: tuple[HistoricalObservationSummary, ...] = Field(default_factory=tuple)
    coverage_context: dict[str, Any] = Field(default_factory=dict)


class CompanyHistorySummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    company_id: str
    region_snapshots: tuple[CompanyRegionSnapshotSummary, ...] = Field(
        default_factory=tuple,
    )
    observations: tuple[HistoricalObservationSummary, ...] = Field(default_factory=tuple)


class SignalInputCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_snapshot_id: str | None = Field(default=None, min_length=1, max_length=64)
    historical_observation_id: str | None = Field(default=None, min_length=1, max_length=64)
    input_type: str = Field(min_length=1, max_length=64)
    input_weight: float | None = None
    contribution_strength: float | None = None

    @field_validator("source_snapshot_id", "historical_observation_id", "input_type")
    @classmethod
    def _strings_not_blank(cls, value: str | None) -> str | None:
        return _clean_optional_string(value)


class PredictiveSignalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    predictive_signal_id: str | None = Field(default=None, min_length=1, max_length=64)
    signal_type: PredictiveSignalType
    target_type: HistoricalTargetType
    target_id: str = Field(min_length=1, max_length=128)
    region_id: str | None = Field(default=None, min_length=1, max_length=64)
    signal_strength: SignalStrength
    confidence_level: ConfidenceLevel
    evidence_window_start: date
    evidence_window_end: date
    snapshot_count: int = Field(ge=0)
    minimum_snapshot_count_met: bool
    summary: str = Field(min_length=1, max_length=1024)
    warnings: tuple[Any, ...] = Field(default_factory=tuple)
    status: PredictiveSignalStatus
    created_at: datetime | None = None
    expires_at: datetime | None = None
    inputs: tuple[SignalInputCreate, ...] = Field(default_factory=tuple)

    @field_validator("predictive_signal_id", "target_id", "region_id", "summary")
    @classmethod
    def _signal_strings_not_blank(cls, value: str | None) -> str | None:
        return _clean_optional_string(value)

    @field_validator("created_at", "expires_at")
    @classmethod
    def _signal_timestamps_must_be_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("signal timestamps must be timezone-aware")
        return value


class PredictiveSignalSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    signal_id: str
    signal_type: PredictiveSignalType
    target_type: HistoricalTargetType
    target_id: str
    region_id: str | None = None
    signal_strength: SignalStrength
    confidence_level: ConfidenceLevel
    evidence_window_start: date
    evidence_window_end: date
    snapshot_count: int
    minimum_snapshot_count_met: bool
    summary: str
    warnings: tuple[Any, ...] = Field(default_factory=tuple)
    status: PredictiveSignalStatus
    created_at: datetime
    expires_at: datetime | None = None


class RegionSignalsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str
    signals: tuple[PredictiveSignalSummary, ...] = Field(default_factory=tuple)


class MarketIndexCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    market_index_id: str | None = Field(default=None, min_length=1, max_length=64)
    key: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=1024)
    status: MarketIndexStatus = MarketIndexStatus.ACTIVE
    created_at: datetime | None = None

    @field_validator("market_index_id", "key", "name", "description")
    @classmethod
    def _index_strings_not_blank(cls, value: str | None) -> str | None:
        return _clean_optional_string(value)


class MarketIndexVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    market_index_version_id: str | None = Field(default=None, min_length=1, max_length=64)
    index_id: str = Field(min_length=1, max_length=64)
    version: str = Field(min_length=1, max_length=32)
    formula_description: str = Field(min_length=1, max_length=2048)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    internal_weight_config: dict[str, float] = Field(default_factory=dict)
    status: MarketIndexVersionStatus = MarketIndexVersionStatus.ACTIVE
    effective_date: date
    created_at: datetime | None = None

    @field_validator(
        "market_index_version_id",
        "index_id",
        "version",
        "formula_description",
    )
    @classmethod
    def _version_strings_not_blank(cls, value: str | None) -> str | None:
        return _clean_optional_string(value)


class MarketIndexInputCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input_name: str = Field(min_length=1, max_length=64)
    input_value: float | None = None
    input_weight: float | None = None
    source_type: str = Field(min_length=1, max_length=64)
    source_id: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("input_name", "source_type", "source_id")
    @classmethod
    def _input_strings_not_blank(cls, value: str | None) -> str | None:
        return _clean_optional_string(value)


class MarketIndexScoreCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    market_index_score_id: str | None = Field(default=None, min_length=1, max_length=64)
    index_id: str = Field(min_length=1, max_length=64)
    index_version_id: str = Field(min_length=1, max_length=64)
    region_id: str = Field(min_length=1, max_length=64)
    score: float = Field(ge=0.0, le=1.0)
    rank: int | None = Field(default=None, ge=1)
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    freshness_state: str | None = Field(default=None, min_length=1, max_length=32)
    evidence_summary: dict[str, Any] | list[Any] | None = None
    calculated_at: datetime
    created_at: datetime | None = None
    inputs: tuple[MarketIndexInputCreate, ...] = Field(default_factory=tuple)

    @field_validator(
        "market_index_score_id",
        "index_id",
        "index_version_id",
        "region_id",
        "freshness_state",
    )
    @classmethod
    def _score_strings_not_blank(cls, value: str | None) -> str | None:
        return _clean_optional_string(value)

    @field_validator("calculated_at", "created_at")
    @classmethod
    def _score_timestamps_must_be_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("index score timestamps must be timezone-aware")
        return value


class MarketIndexSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    index_id: str
    key: str
    name: str
    description: str
    status: MarketIndexStatus
    latest_version: str | None = None
    methodology_summary: str | None = None
    created_at: datetime


class MarketIndexScoreSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    score_id: str
    index_key: str
    index_version_id: str
    index_version: str
    region_id: str
    score: float
    rank: int | None = None
    confidence_score: float | None = None
    freshness_state: str | None = None
    evidence_summary: dict[str, Any] | list[Any] | None = None
    methodology_summary: str
    calculated_at: datetime
    created_at: datetime


class MarketIndexScoresResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    index_key: str
    scores: tuple[MarketIndexScoreSummary, ...] = Field(default_factory=tuple)


class BenchmarkReportKey(_Vocabulary):
    BEST_CITIES_EARLY_CAREER_AI_ROLES = "best_cities_early_career_ai_roles"
    TOP_EMERGING_TECH_MARKETS = "top_emerging_tech_markets"
    BEST_MARKETS_PRODUCT_CAREERS = "best_markets_product_careers"
    BEST_REGIONS_INTERNSHIP_ACCESS = "best_regions_internship_access"


class BenchmarkReportType(_Vocabulary):
    EARLY_CAREER_AI_ROLES = "early_career_ai_roles"
    EMERGING_TECH_MARKETS = "emerging_tech_markets"
    PRODUCT_CAREERS = "product_careers"
    INTERNSHIP_ACCESS = "internship_access"


class BenchmarkReportStatus(_Vocabulary):
    DRAFT = "draft"
    REVIEW_READY = "review_ready"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    SUPERSEDED = "superseded"


class ContributorType(_Vocabulary):
    USER = "user"
    INSTITUTION = "institution"
    PARTNER = "partner"
    ADMIN = "admin"


class ContributionTargetType(_Vocabulary):
    REGION = "region"
    COMPANY = "company"
    COMPANY_REGION = "company_region"
    SECTOR_REGION = "sector_region"
    SOURCE = "source"
    MARKET = "market"
    ROLE_FAMILY = "role_family"


class ContributionType(_Vocabulary):
    VERIFIED_CORRECTION = "verified_correction"
    COMPANY_PRESENCE_UPDATE = "company_presence_update"
    REGIONAL_EMPLOYER_LIST = "regional_employer_list"
    CAREER_CENTER_INTELLIGENCE = "career_center_intelligence"
    INTERNSHIP_PROGRAM_INFORMATION = "internship_program_information"
    ROLE_ACCESS_FEEDBACK = "role_access_feedback"
    SOURCE_SUGGESTION = "source_suggestion"
    MARKET_QUALITY_FEEDBACK = "market_quality_feedback"
    OUTDATED_DATA_REPORT = "outdated_data_report"


class ContributionStatus(_Vocabulary):
    SUBMITTED = "submitted"
    NEEDS_REVIEW = "needs_review"
    VERIFIED = "verified"
    REJECTED = "rejected"
    MERGED = "merged"
    SUPERSEDED = "superseded"


class ContributionEvidenceType(_Vocabulary):
    URL = "url"
    REFERENCE = "reference"
    DESCRIPTION = "description"
    UPLOADED_REFERENCE = "uploaded_reference"


class ContributionReviewDecision(_Vocabulary):
    NEEDS_REVIEW = "needs_review"
    VERIFIED = "verified"
    REJECTED = "rejected"
    MERGED = "merged"
    SUPERSEDED = "superseded"


class BenchmarkReportSectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    section_key: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=4096)
    display_order: int = Field(ge=0)

    @field_validator("section_key", "title", "body")
    @classmethod
    def _section_strings_not_blank(cls, value: str | None) -> str | None:
        return _clean_optional_string(value)


class BenchmarkReportRankingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str = Field(min_length=1, max_length=64)
    rank: int = Field(ge=1)
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    index_score_id: str | None = Field(default=None, min_length=1, max_length=64)
    explanation: str = Field(min_length=1, max_length=2048)
    warnings: tuple[Any, ...] = Field(default_factory=tuple)
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    freshness_state: str | None = Field(default=None, min_length=1, max_length=32)

    @field_validator("region_id", "index_score_id", "explanation", "freshness_state")
    @classmethod
    def _ranking_strings_not_blank(cls, value: str | None) -> str | None:
        return _clean_optional_string(value)


class BenchmarkReportEvidenceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    target_type: str = Field(min_length=1, max_length=64)
    target_id: str = Field(min_length=1, max_length=128)
    source_type: str = Field(min_length=1, max_length=64)
    source_id: str | None = Field(default=None, min_length=1, max_length=128)
    evidence_summary: dict[str, Any] | list[Any] | None = None

    @field_validator("target_type", "target_id", "source_type", "source_id")
    @classmethod
    def _evidence_strings_not_blank(cls, value: str | None) -> str | None:
        return _clean_optional_string(value)


class BenchmarkReportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    benchmark_report_id: str | None = Field(default=None, min_length=1, max_length=64)
    report_key: BenchmarkReportKey
    title: str = Field(min_length=1, max_length=255)
    report_period: str = Field(min_length=1, max_length=64)
    report_type: BenchmarkReportType
    status: BenchmarkReportStatus = BenchmarkReportStatus.DRAFT
    summary: str = Field(min_length=1, max_length=2048)
    methodology_summary: str = Field(min_length=1, max_length=2048)
    data_window_start: date
    data_window_end: date
    freshness_notes: str | None = Field(default=None, min_length=1, max_length=2048)
    confidence_notes: str | None = Field(default=None, min_length=1, max_length=2048)
    coverage_notes: str | None = Field(default=None, min_length=1, max_length=2048)
    limitations: tuple[Any, ...] = Field(default_factory=tuple)
    created_at: datetime | None = None
    sections: tuple[BenchmarkReportSectionCreate, ...] = Field(default_factory=tuple)
    rankings: tuple[BenchmarkReportRankingCreate, ...] = Field(default_factory=tuple)
    evidence: tuple[BenchmarkReportEvidenceCreate, ...] = Field(default_factory=tuple)

    @field_validator(
        "benchmark_report_id",
        "title",
        "report_period",
        "summary",
        "methodology_summary",
        "freshness_notes",
        "confidence_notes",
        "coverage_notes",
    )
    @classmethod
    def _report_strings_not_blank(cls, value: str | None) -> str | None:
        return _clean_optional_string(value)

    @field_validator("created_at")
    @classmethod
    def _created_at_must_be_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return value


class BenchmarkReportSectionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    section_key: str
    title: str
    body: str
    display_order: int


class BenchmarkReportRankingSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    region_id: str
    rank: int
    score: float | None = None
    explanation: str
    warnings: tuple[Any, ...] = Field(default_factory=tuple)
    confidence_score: float | None = None
    freshness_state: str | None = None


class BenchmarkReportEvidenceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    target_type: str
    target_id: str
    source_type: str
    evidence_summary: dict[str, Any] | list[Any] | None = None


class BenchmarkReportSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    report_id: str
    report_key: BenchmarkReportKey
    title: str
    report_period: str
    report_type: BenchmarkReportType
    status: BenchmarkReportStatus
    summary: str
    data_window_start: date
    data_window_end: date
    published_at: datetime | None = None


class BenchmarkReportDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    report_id: str
    report_key: BenchmarkReportKey
    title: str
    report_period: str
    report_type: BenchmarkReportType
    status: BenchmarkReportStatus
    summary: str
    methodology_summary: str
    data_window_start: date
    data_window_end: date
    freshness_notes: str | None = None
    confidence_notes: str | None = None
    coverage_notes: str | None = None
    limitations: tuple[Any, ...] = Field(default_factory=tuple)
    ranked_regions: tuple[BenchmarkReportRankingSummary, ...] = Field(
        default_factory=tuple,
    )
    sections: tuple[BenchmarkReportSectionSummary, ...] = Field(default_factory=tuple)
    evidence: tuple[BenchmarkReportEvidenceSummary, ...] = Field(default_factory=tuple)
    warnings: tuple[Any, ...] = Field(default_factory=tuple)
    published_at: datetime | None = None


class BenchmarkReportListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reports: tuple[BenchmarkReportSummary, ...] = Field(default_factory=tuple)


class ContributionEvidenceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_type: ContributionEvidenceType
    url: str | None = Field(default=None, min_length=1, max_length=2048)
    reference: str | None = Field(default=None, min_length=1, max_length=512)
    description: str | None = Field(default=None, min_length=1, max_length=2048)
    uploaded_reference_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
    )

    @field_validator("url")
    @classmethod
    def _url_must_be_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        parsed = urlparse(stripped)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("evidence URLs must be http(s) URLs")
        if parsed.username or parsed.password:
            raise ValueError("evidence URLs must not contain credentials")
        hostname = (parsed.hostname or "").lower()
        if _hostname_is_private_or_local(hostname):
            raise ValueError("evidence URLs must not point to private hosts")
        sensitive_keys = {"token", "key", "secret", "password", "credential"}
        for key, _value in parse_qsl(parsed.query, keep_blank_values=True):
            if any(fragment in key.lower() for fragment in sensitive_keys):
                raise ValueError("evidence URLs must not include credential query fields")
        return stripped

    @field_validator("reference", "uploaded_reference_id")
    @classmethod
    def _reference_must_be_safe(cls, value: str | None) -> str | None:
        cleaned = _clean_optional_string(value)
        if cleaned is None:
            return None
        if cleaned.startswith(("/", "~")) or "\\" in cleaned or ".." in cleaned:
            raise ValueError("evidence references must not be filesystem paths")
        return cleaned

    @field_validator("description")
    @classmethod
    def _description_not_blank(cls, value: str | None) -> str | None:
        return _clean_optional_string(value)


class ContributionSubmissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contribution_id: str | None = Field(default=None, min_length=1, max_length=64)
    institution_id: str | None = Field(default=None, min_length=1, max_length=64)
    target_type: ContributionTargetType
    target_id: str = Field(min_length=1, max_length=128)
    region_id: str | None = Field(default=None, min_length=1, max_length=64)
    contribution_type: ContributionType
    structured_payload: dict[str, Any] | list[Any] = Field(default_factory=dict)
    summary: str = Field(min_length=1, max_length=1024)
    claimed_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence: tuple[ContributionEvidenceCreate, ...] = Field(default_factory=tuple)
    created_at: datetime | None = None

    @field_validator("contribution_id", "institution_id", "target_id", "region_id", "summary")
    @classmethod
    def _submission_strings_not_blank(cls, value: str | None) -> str | None:
        return _clean_optional_string(value)

    @field_validator("created_at")
    @classmethod
    def _created_at_must_be_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return value


class ContributionEvidenceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_type: ContributionEvidenceType
    url: str | None = None
    reference: str | None = None
    description: str | None = None
    uploaded_reference_id: str | None = None
    created_at: datetime


class ContributionSubmissionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contribution_id: str
    status: ContributionStatus
    contribution_type: ContributionType
    summary: str
    created_at: datetime
    next_step_message: str


class ContributionReviewQueueItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contribution_id: str
    contributor_type: ContributorType
    contributor_id: str | None = None
    institution_id: str | None = None
    target_type: ContributionTargetType
    target_id: str
    region_id: str | None = None
    contribution_type: ContributionType
    structured_payload: dict[str, Any] | list[Any]
    summary: str
    claimed_confidence: float | None = None
    status: ContributionStatus
    evidence: tuple[ContributionEvidenceSummary, ...] = Field(default_factory=tuple)
    created_at: datetime
    reviewed_at: datetime | None = None


class ContributionReviewQueueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contributions: tuple[ContributionReviewQueueItem, ...] = Field(default_factory=tuple)


class ContributionReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    review_decision: ContributionReviewDecision
    review_notes: str | None = Field(default=None, min_length=1, max_length=4096)
    canonical_update_candidate_created: bool = False
    canonical_update_candidate_ref: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
    )
    refresh_task_created: bool = False
    refresh_task_ref: str | None = Field(default=None, min_length=1, max_length=128)
    created_at: datetime | None = None

    @field_validator(
        "review_notes",
        "canonical_update_candidate_ref",
        "refresh_task_ref",
    )
    @classmethod
    def _review_strings_not_blank(cls, value: str | None) -> str | None:
        return _clean_optional_string(value)

    @field_validator("created_at")
    @classmethod
    def _review_created_at_must_be_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return value


class ContributionReviewSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contribution_id: str
    review_decision: ContributionReviewDecision
    resulting_status: ContributionStatus
    canonical_update_candidate_created: bool
    refresh_task_created: bool
    created_at: datetime


def _clean_optional_string(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


def _hostname_is_private_or_local(hostname: str) -> bool:
    if hostname in {"localhost"} or hostname.endswith(".localhost"):
        return True
    if hostname.endswith(".local"):
        return True
    try:
        parsed = ip_address(hostname)
    except ValueError:
        return False
    return any(
        (
            parsed.is_private,
            parsed.is_loopback,
            parsed.is_link_local,
            parsed.is_reserved,
            parsed.is_multicast,
            parsed.is_unspecified,
        )
    )
