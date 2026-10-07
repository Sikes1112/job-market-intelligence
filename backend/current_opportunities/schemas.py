"""Layer 38A current opportunity contracts."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any, Self
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class OpportunitySourceType(_Vocabulary):
    API = "api"
    FEED = "feed"
    LICENSED_SOURCE = "licensed_source"
    EMPLOYER_CONTRIBUTION = "employer_contribution"
    CURATED_INPUT = "curated_input"


class AcquisitionMethod(_Vocabulary):
    API_PULL = "api_pull"
    FEED_PULL = "feed_pull"
    LICENSED_PULL = "licensed_pull"
    EMPLOYER_SUBMISSION = "employer_submission"
    CURATED_IMPORT = "curated_import"


class AllowedUseClassification(_Vocabulary):
    ALLOWED = "allowed"
    ALLOWED_WITH_CAUTION = "allowed_with_caution"
    INTERNAL_ONLY = "internal_only"
    PROHIBITED = "prohibited"
    UNKNOWN = "unknown"


class LicenseTermsClassification(_Vocabulary):
    PUBLIC = "public"
    PERMISSIVE = "permissive"
    RESTRICTED = "restricted"
    PROHIBITED = "prohibited"
    UNKNOWN = "unknown"


class SourceTrustClassification(_Vocabulary):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNTRUSTED = "untrusted"
    UNKNOWN = "unknown"


class SourceOperationalStatus(_Vocabulary):
    ENABLED = "enabled"
    DISABLED = "disabled"
    UNHEALTHY = "unhealthy"
    PROHIBITED = "prohibited"


class AcquisitionRunStatus(_Vocabulary):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL_FAILURE = "partial_failure"
    FAILED = "failed"
    REJECTED = "rejected"


class AcquisitionRecordStatus(_Vocabulary):
    ACTIVE = "active"
    REMOVED = "removed"
    MALFORMED = "malformed"


class RetryClassification(_Vocabulary):
    NONE = "none"
    RETRYABLE = "retryable"
    TERMINAL = "terminal"


class NormalizationStatus(_Vocabulary):
    VALID = "valid"
    INVALID = "invalid"
    WARNING = "warning"


class IdentityResolutionStatus(_Vocabulary):
    NEW = "new"
    EXISTING_SOURCE_RECORD = "existing_source_record"
    CROSS_SOURCE_DUPLICATE = "cross_source_duplicate"
    POTENTIAL_DUPLICATE = "potential_duplicate"
    SOURCE_ID_REUSE_CONFLICT = "source_id_reuse_conflict"


class OpportunityStatus(_Vocabulary):
    ACTIVE = "active"
    STALE = "stale"
    CLOSED = "closed"
    SUPPRESSED = "suppressed"


class FreshnessState(_Vocabulary):
    FRESH = "fresh"
    AGING = "aging"
    STALE = "stale"
    UNKNOWN = "unknown"


class ConfidenceLevel(_Vocabulary):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class WorkArrangement(_Vocabulary):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class LocationResolutionStatus(_Vocabulary):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"


class EmploymentType(_Vocabulary):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    INTERNSHIP = "internship"
    CONTRACT = "contract"
    TEMPORARY = "temporary"
    UNKNOWN = "unknown"


class OpportunityKind(_Vocabulary):
    JOB = "job"
    INTERNSHIP = "internship"
    CO_OP = "co_op"
    APPRENTICESHIP = "apprenticeship"
    FELLOWSHIP = "fellowship"
    EARLY_CAREER_PROGRAM = "early_career_program"
    UNKNOWN = "unknown"


class CompensationInterval(_Vocabulary):
    ANNUAL = "annual"
    HOURLY = "hourly"
    MONTHLY = "monthly"
    STIPEND = "stipend"
    UNKNOWN = "unknown"


class CoverageStatus(_Vocabulary):
    PRODUCTION_READY = "production_ready"
    LIMITED = "limited"
    EXPERIMENTAL = "experimental"
    UNSUPPORTED = "unsupported"


class DiagnosticSeverity(_Vocabulary):
    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


class SourceRegistryInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(min_length=1, max_length=64)
    provider: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=255)
    source_type: OpportunitySourceType
    acquisition_method: AcquisitionMethod
    enabled: bool = True
    allowed_use: AllowedUseClassification = AllowedUseClassification.UNKNOWN
    license_terms: LicenseTermsClassification = LicenseTermsClassification.UNKNOWN
    trust: SourceTrustClassification = SourceTrustClassification.UNKNOWN
    freshness_sla_hours: int = Field(default=72, ge=1, le=8760)
    supported_domains: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    supported_markets: tuple[str, ...] = Field(default_factory=tuple, max_length=100)
    supported_opportunity_types: tuple[OpportunityKind, ...] = Field(
        default_factory=tuple,
        max_length=25,
    )
    retention_classification: str | None = Field(default=None, min_length=1, max_length=64)
    ranking_use_allowed: bool = False
    display_use_allowed: bool = False
    refresh_config: dict[str, Any] = Field(default_factory=dict)
    provenance_requirements: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    operational_status: SourceOperationalStatus = SourceOperationalStatus.ENABLED

    @field_validator(
        "source_id",
        "provider",
        "display_name",
        "retention_classification",
    )
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("text values must not be blank")
        return stripped

    @field_validator("supported_domains", "supported_markets", "provenance_requirements")
    @classmethod
    def _strip_tuple(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(item.strip() for item in value if item.strip())
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("tuple values must be unique")
        return cleaned

    @model_validator(mode="after")
    def _source_governance_fails_closed(self) -> Self:
        prohibited = {
            AllowedUseClassification.UNKNOWN,
            AllowedUseClassification.PROHIBITED,
            AllowedUseClassification.INTERNAL_ONLY,
        }
        if self.ranking_use_allowed and self.allowed_use in prohibited:
            raise ValueError("ranking requires explicit allowed use")
        if self.ranking_use_allowed and self.license_terms in {
            LicenseTermsClassification.UNKNOWN,
            LicenseTermsClassification.PROHIBITED,
        }:
            raise ValueError("ranking requires explicit non-prohibited license terms")
        if self.ranking_use_allowed and self.trust in {
            SourceTrustClassification.UNKNOWN,
            SourceTrustClassification.UNTRUSTED,
        }:
            raise ValueError("ranking requires a trusted source classification")
        if self.display_use_allowed and self.allowed_use in {
            AllowedUseClassification.UNKNOWN,
            AllowedUseClassification.PROHIBITED,
            AllowedUseClassification.INTERNAL_ONLY,
        }:
            raise ValueError("display requires explicit allowed use")
        if self.display_use_allowed and self.license_terms in {
            LicenseTermsClassification.UNKNOWN,
            LicenseTermsClassification.PROHIBITED,
        }:
            raise ValueError("display requires explicit non-prohibited license terms")
        if self.operational_status is SourceOperationalStatus.PROHIBITED and self.enabled:
            raise ValueError("prohibited sources must be disabled")
        return self


class AcquiredOpportunityRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_record_id: str = Field(min_length=1, max_length=255)
    observed_at: datetime | None = None
    collected_at: datetime
    cursor: str | None = Field(default=None, min_length=1, max_length=512)
    raw_payload: dict[str, Any]
    status: AcquisitionRecordStatus = AcquisitionRecordStatus.ACTIVE
    retry_classification: RetryClassification = RetryClassification.NONE
    terminal_failure: bool = False
    error_code: str | None = Field(default=None, min_length=1, max_length=128)
    error_message: str | None = Field(default=None, min_length=1, max_length=512)

    @field_validator("observed_at", "collected_at")
    @classmethod
    def _aware_datetimes(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        return value


class AcquisitionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    run_id: str
    collected_at: datetime
    records: tuple[AcquiredOpportunityRecord, ...] = Field(default_factory=tuple)
    cursor: str | None = None
    checkpoint: dict[str, Any] = Field(default_factory=dict)
    status: AcquisitionRunStatus = AcquisitionRunStatus.COMPLETED
    retry_classification: RetryClassification = RetryClassification.NONE
    failure_details: dict[str, Any] = Field(default_factory=dict)
    warnings: tuple[str, ...] = Field(default_factory=tuple)


class NormalizedOpportunity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_record_id: str
    company_name: str | None = Field(default=None, max_length=255)
    company_id: str | None = Field(default=None, max_length=64)
    original_title: str | None = Field(default=None, max_length=255)
    normalized_title: str | None = Field(default=None, max_length=255)
    role_family: str = Field(default="unknown", max_length=64)
    seniority_level: str = Field(default="unknown", max_length=64)
    market_id: str | None = Field(default=None, max_length=64)
    market_label: str | None = Field(default=None, max_length=128)
    location_text: str | None = Field(default=None, max_length=255)
    location_resolution_status: LocationResolutionStatus = (
        LocationResolutionStatus.UNRESOLVED
    )
    location_resolution_source: str | None = Field(default=None, max_length=64)
    work_arrangement: WorkArrangement = WorkArrangement.UNKNOWN
    compensation_min: float | None = Field(default=None, ge=0.0)
    compensation_max: float | None = Field(default=None, ge=0.0)
    compensation_currency: str | None = Field(default=None, min_length=3, max_length=3)
    compensation_interval: CompensationInterval = CompensationInterval.UNKNOWN
    employment_type: EmploymentType = EmploymentType.UNKNOWN
    opportunity_type: OpportunityKind = OpportunityKind.UNKNOWN
    posting_date: date | None = None
    closing_date: date | None = None
    application_url: str | None = Field(default=None, max_length=2048)
    application_host: str | None = Field(default=None, max_length=255)
    source_url: str | None = Field(default=None, max_length=2048)
    description_text: str | None = Field(default=None, max_length=8000)
    skills: tuple[str, ...] = Field(default_factory=tuple, max_length=100)
    requirements: tuple[str, ...] = Field(default_factory=tuple, max_length=100)
    source_values: dict[str, Any] = Field(default_factory=dict)
    normalization_confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    normalization_warnings: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("company_name", "company_id", "original_title", "normalized_title")
    @classmethod
    def _clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("compensation_currency")
    @classmethod
    def _currency_upper(cls, value: str | None) -> str | None:
        return value.upper() if value else None

    @field_validator("application_url", "source_url")
    @classmethod
    def _safe_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return safe_external_url(value)

    @model_validator(mode="after")
    def _compensation_range_valid(self) -> Self:
        if (
            self.compensation_min is not None
            and self.compensation_max is not None
            and self.compensation_max < self.compensation_min
        ):
            raise ValueError("compensation_max must be greater than or equal to min")
        return self


class OpportunityCoverageInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    coverage_id: str = Field(min_length=1, max_length=64)
    market_key: str = Field(default="*", min_length=1, max_length=128)
    market_id: str | None = Field(default=None, min_length=1, max_length=64)
    market_label: str | None = Field(default=None, min_length=1, max_length=128)
    role_family: str = Field(default="*", min_length=1, max_length=64)
    opportunity_type: OpportunityKind | str = "*"
    status: CoverageStatus
    rationale: str = Field(min_length=1, max_length=2048)
    source_basis: dict[str, Any] = Field(default_factory=dict)
    minimum_expected_sources: int = Field(default=0, ge=0)
    freshness_max_age_hours: int | None = Field(default=None, ge=1)
    last_evaluated_at: datetime | None = None
    operator_override_status: CoverageStatus | None = None

    @field_validator("last_evaluated_at")
    @classmethod
    def _coverage_datetime_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("last_evaluated_at must be timezone-aware")
        return value


class CurrentOpportunityPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    opportunity_id: str
    company_id: str | None
    company_name: str
    original_title: str
    normalized_title: str
    role_family: str
    seniority_level: str
    market_id: str | None
    market_label: str | None
    location_text: str | None
    location_resolution_status: LocationResolutionStatus
    location_resolution_source: str | None
    work_arrangement: WorkArrangement
    compensation_min: float | None
    compensation_max: float | None
    compensation_currency: str | None
    compensation_interval: CompensationInterval
    employment_type: EmploymentType
    opportunity_type: OpportunityKind
    posting_date: date | None
    closing_date: date | None
    application_url: str | None
    source_url: str | None
    description_text: str | None
    skills: tuple[str, ...]
    requirements: tuple[str, ...]
    status: OpportunityStatus
    freshness_state: FreshnessState
    freshness_age_hours: int | None
    first_observed_at: datetime | None
    last_observed_at: datetime | None
    last_collected_at: datetime | None
    canonical_updated_at: datetime
    normalization_confidence: ConfidenceLevel
    identity_confidence: ConfidenceLevel
    ranking_eligible: bool
    ranking_ineligible_reasons: tuple[str, ...]
    coverage_status: CoverageStatus
    coverage_limitations: tuple[str, ...]
    provenance: dict[str, Any]
    warnings: tuple[str, ...]


class OpportunityMatchPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    opportunity: CurrentOpportunityPayload
    match_score: float = Field(ge=0.0, le=1.0)
    strategic_relevance: str
    contributing_factors: tuple[str, ...]
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]
    ranking_eligible: bool


class CoveragePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    market_key: str
    role_family: str
    opportunity_type: str
    status: CoverageStatus
    effective_status: CoverageStatus
    rationale: str
    limitations: tuple[str, ...]
    source_basis: dict[str, Any]
    minimum_expected_sources: int
    freshness_max_age_hours: int | None
    last_evaluated_at: datetime | None


class DiagnosticPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    severity: DiagnosticSeverity
    message: str
    scope: dict[str, Any]
    evidence: dict[str, Any]


class RefreshRunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    source_id: str
    status: AcquisitionRunStatus
    acquired_count: int
    normalized_count: int
    promoted_count: int
    duplicate_count: int
    rejected_count: int
    warning_count: int
    failure_count: int
    started_at: datetime
    completed_at: datetime | None
    warnings: tuple[str, ...]
    failure_details: dict[str, Any]


def safe_external_url(value: str) -> str:
    stripped = value.strip()
    parsed = urlparse(stripped)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("external URLs must use http or https")
    if not parsed.netloc:
        raise ValueError("external URLs require a host")
    hostname = parsed.hostname
    if hostname in {None, "localhost"} or hostname.startswith("127."):
        raise ValueError("external URLs must not target localhost")
    return stripped
