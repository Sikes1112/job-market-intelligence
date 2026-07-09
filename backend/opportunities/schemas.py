"""API-safe contracts for Layer 23A opportunity records."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from ipaddress import ip_address
from typing import Self
from urllib.parse import parse_qsl, urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.trust.schemas import (
    EvidenceRequirementResult,
    ExceptionSubjectStatus,
    RankingInfluenceDecision,
    RankingInfluenceReasonCode,
    ReportRecheckStatus,
    RiskLevel,
    RiskRoutingReasonCode,
    RoutingOutcome,
    TrustExplanation,
    TrustTier,
    TrustWarning,
)


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class OpportunityProgramType(_Vocabulary):
    INTERNSHIP = "internship"
    CO_OP = "co-op"
    ROTATIONAL_PROGRAM = "rotational_program"
    NEW_GRAD_ROLE = "new_grad_role"
    APPRENTICESHIP = "apprenticeship"
    EMPLOYER_PROGRAM = "employer_program"
    FELLOWSHIP = "fellowship"
    UNKNOWN = "unknown"


class OpportunityLocationMode(_Vocabulary):
    ONSITE = "onsite"
    HYBRID = "hybrid"
    REMOTE = "remote"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class OpportunitySeniorityLevel(_Vocabulary):
    INTERNSHIP = "internship"
    CO_OP = "co-op"
    APPRENTICE = "apprentice"
    NEW_GRAD = "new-grad"
    EARLY_CAREER = "early-career"
    UNKNOWN = "unknown"


class OpportunitySourceType(_Vocabulary):
    EMPLOYER_OFFICIAL = "employer_official"
    CAREER_CENTER = "career_center"
    PARTNER_SUBMITTED = "partner_submitted"
    PUBLIC_DATASET = "public_dataset"
    MANUAL_RESEARCH = "manual_research"
    INTERNAL_REVIEW = "internal_review"
    UNKNOWN = "unknown"


class OpportunityTrustLabel(_Vocabulary):
    VERIFIED = "verified"
    SOURCE_CHECKED = "source_checked"
    PARTNER_SUBMITTED = "partner_submitted"
    UNVERIFIED = "unverified"
    EXPIRED = "expired"
    REJECTED = "rejected"


class OpportunityReviewStatus(_Vocabulary):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    SOURCE_CHECKED = "source_checked"
    REJECTED = "rejected"
    EXPIRED = "expired"
    NEEDS_CORRECTION = "needs_correction"


class OpportunityExpirationState(_Vocabulary):
    ACTIVE = "active"
    EXPIRED = "expired"


class OpportunityBindingConfidence(_Vocabulary):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class OpportunitySubmissionStatus(_Vocabulary):
    PENDING_REVIEW = "pending_review"
    REVIEWED = "reviewed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    NEEDS_CORRECTION = "needs_correction"


class OpportunityReviewAction(_Vocabulary):
    APPROVE_AS_VERIFIED = "approve_as_verified"
    APPROVE_AS_SOURCE_CHECKED = "approve_as_source_checked"
    MARK_UNVERIFIED = "mark_unverified"
    MARK_EXPIRED = "mark_expired"
    REJECT = "reject"
    REQUEST_CORRECTION = "request_correction"


class EmployerProgramCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    employer_program_id: str | None = Field(default=None, min_length=1, max_length=64)
    employer_id: str | None = Field(default=None, min_length=1, max_length=64)
    employer_name: str = Field(min_length=1, max_length=255)
    program_name: str = Field(min_length=1, max_length=255)
    program_type: OpportunityProgramType
    program_url: str | None = Field(default=None, min_length=1, max_length=2048)
    created_at: datetime | None = None

    @field_validator("employer_program_id", "employer_id")
    @classmethod
    def _optional_strings_not_blank(cls, value: str | None) -> str | None:
        return _clean_optional_string(value)

    @field_validator("employer_name", "program_name")
    @classmethod
    def _required_strings_not_blank(cls, value: str) -> str:
        return _clean_required_string(value)

    @field_validator("program_url")
    @classmethod
    def _program_url_must_be_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_public_url(value, field_name="program_url")

    @field_validator("created_at")
    @classmethod
    def _created_at_must_be_aware(cls, value: datetime | None) -> datetime | None:
        return _aware_datetime(value, field_name="created_at")


class OpportunitySourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    opportunity_source_id: str | None = Field(default=None, min_length=1, max_length=64)
    source_type: OpportunitySourceType
    source_url: str = Field(min_length=1, max_length=2048)
    source_name: str | None = Field(default=None, min_length=1, max_length=255)
    collected_at: datetime | None = None
    verification_note: str | None = Field(default=None, min_length=1, max_length=2048)

    @field_validator("opportunity_source_id", "source_name", "verification_note")
    @classmethod
    def _source_strings_not_blank(cls, value: str | None) -> str | None:
        return _clean_optional_string(value)

    @field_validator("source_url")
    @classmethod
    def _source_url_must_be_safe(cls, value: str) -> str:
        return _safe_public_url(value, field_name="source_url")

    @field_validator("collected_at")
    @classmethod
    def _collected_at_must_be_aware(cls, value: datetime | None) -> datetime | None:
        return _aware_datetime(value, field_name="collected_at")


class OpportunityRegionBindingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    opportunity_region_binding_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
    )
    region_id: str | None = Field(default=None, min_length=1, max_length=64)
    region_label: str = Field(min_length=1, max_length=128)
    metro_area: str | None = Field(default=None, min_length=1, max_length=128)
    binding_confidence: OpportunityBindingConfidence = OpportunityBindingConfidence.UNKNOWN

    @field_validator("opportunity_region_binding_id", "region_id", "metro_area")
    @classmethod
    def _optional_strings_not_blank(cls, value: str | None) -> str | None:
        return _clean_optional_string(value)

    @field_validator("region_label")
    @classmethod
    def _region_label_not_blank(cls, value: str) -> str:
        return _clean_required_string(value)


class OpportunityRoleFamilyBindingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    opportunity_role_family_binding_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
    )
    role_family: str = Field(min_length=1, max_length=64)
    role_family_label: str | None = Field(default=None, min_length=1, max_length=128)
    binding_confidence: OpportunityBindingConfidence = OpportunityBindingConfidence.UNKNOWN

    @field_validator("opportunity_role_family_binding_id", "role_family_label")
    @classmethod
    def _optional_strings_not_blank(cls, value: str | None) -> str | None:
        return _clean_optional_string(value)

    @field_validator("role_family")
    @classmethod
    def _role_family_not_blank(cls, value: str) -> str:
        return _clean_required_string(value)


class EmployerInfluenceMetadataCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    employer_influence_metadata_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
    )
    partner_submitted: bool = False
    paid_partner: bool = False
    ranking_influence_allowed: bool = False
    submitted_by_partner_id: str | None = Field(default=None, min_length=1, max_length=64)
    paid_partner_label: str | None = Field(default=None, min_length=1, max_length=128)
    internal_review_notes: str | None = Field(default=None, min_length=1, max_length=4096)

    @field_validator(
        "employer_influence_metadata_id",
        "submitted_by_partner_id",
        "paid_partner_label",
        "internal_review_notes",
    )
    @classmethod
    def _metadata_strings_not_blank(cls, value: str | None) -> str | None:
        return _clean_optional_string(value)

    @model_validator(mode="after")
    def _ranking_influence_must_stay_disabled(self) -> Self:
        if self.ranking_influence_allowed:
            raise ValueError(
                "ranking_influence_allowed is reserved for a future governed layer"
            )
        return self


class OpportunityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    opportunity_id: str | None = Field(default=None, min_length=1, max_length=64)
    employer_program_id: str | None = Field(default=None, min_length=1, max_length=64)
    employer_id: str | None = Field(default=None, min_length=1, max_length=64)
    employer_name: str = Field(min_length=1, max_length=255)
    program_name: str = Field(min_length=1, max_length=255)
    program_type: OpportunityProgramType
    location_mode: OpportunityLocationMode = OpportunityLocationMode.UNKNOWN
    seniority_level: OpportunitySeniorityLevel = OpportunitySeniorityLevel.UNKNOWN
    eligibility_summary: str | None = Field(default=None, min_length=1, max_length=2048)
    application_url: str = Field(min_length=1, max_length=2048)
    source_url: str = Field(min_length=1, max_length=2048)
    source_type: OpportunitySourceType
    application_open_date: date | None = None
    application_deadline: date | None = None
    expires_at: datetime | None = None
    compensation_min: float | None = Field(default=None, ge=0.0)
    compensation_max: float | None = Field(default=None, ge=0.0)
    compensation_disclosed: bool = False
    trust_label: OpportunityTrustLabel = OpportunityTrustLabel.UNVERIFIED
    review_status: OpportunityReviewStatus = OpportunityReviewStatus.PENDING_REVIEW
    employer_influence: EmployerInfluenceMetadataCreate = Field(
        default_factory=EmployerInfluenceMetadataCreate,
    )
    sources: tuple[OpportunitySourceCreate, ...] = Field(default_factory=tuple)
    region_bindings: tuple[OpportunityRegionBindingCreate, ...] = Field(
        default_factory=tuple,
    )
    role_family_bindings: tuple[OpportunityRoleFamilyBindingCreate, ...] = Field(
        default_factory=tuple,
    )
    created_at: datetime | None = None

    @field_validator("opportunity_id", "employer_program_id", "employer_id")
    @classmethod
    def _optional_strings_not_blank(cls, value: str | None) -> str | None:
        return _clean_optional_string(value)

    @field_validator("employer_name", "program_name")
    @classmethod
    def _required_strings_not_blank(cls, value: str) -> str:
        return _clean_required_string(value)

    @field_validator("eligibility_summary")
    @classmethod
    def _eligibility_summary_not_blank(cls, value: str | None) -> str | None:
        return _clean_optional_string(value)

    @field_validator("application_url")
    @classmethod
    def _application_url_must_be_safe(cls, value: str) -> str:
        return _safe_public_url(value, field_name="application_url")

    @field_validator("source_url")
    @classmethod
    def _source_url_must_be_safe(cls, value: str) -> str:
        return _safe_public_url(value, field_name="source_url")

    @field_validator("expires_at", "created_at")
    @classmethod
    def _datetimes_must_be_aware(cls, value: datetime | None) -> datetime | None:
        return _aware_datetime(value, field_name="datetime")

    @model_validator(mode="after")
    def _opportunity_dates_and_compensation_are_consistent(self) -> Self:
        if (
            self.application_open_date is not None
            and self.application_deadline is not None
            and self.application_deadline < self.application_open_date
        ):
            raise ValueError("application_deadline must not precede application_open_date")
        if (
            self.compensation_min is not None
            and self.compensation_max is not None
            and self.compensation_max < self.compensation_min
        ):
            raise ValueError("compensation_max must be greater than or equal to min")
        if (
            not self.compensation_disclosed
            and (self.compensation_min is not None or self.compensation_max is not None)
        ):
            raise ValueError("compensation_disclosed must be true when compensation exists")
        return self


class OpportunitySubmissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    submission_id: str | None = Field(default=None, min_length=1, max_length=64)
    opportunity_id: str | None = Field(default=None, min_length=1, max_length=64)
    employer_id: str | None = Field(default=None, min_length=1, max_length=64)
    employer_name: str = Field(min_length=1, max_length=255)
    program_name: str = Field(min_length=1, max_length=255)
    program_type: OpportunityProgramType
    location_mode: OpportunityLocationMode
    seniority_level: OpportunitySeniorityLevel
    eligibility_summary: str = Field(min_length=1, max_length=2048)
    application_url: str | None = Field(default=None, min_length=1, max_length=2048)
    source_url: str | None = Field(default=None, min_length=1, max_length=2048)
    source_type: OpportunitySourceType = OpportunitySourceType.PARTNER_SUBMITTED
    application_open_date: date | None = None
    application_deadline: date | None = None
    expires_at: datetime | None = None
    compensation_min: float | None = Field(default=None, ge=0.0)
    compensation_max: float | None = Field(default=None, ge=0.0)
    compensation_disclosed: bool = False
    submitter_contact: str = Field(min_length=1, max_length=255)
    submitted_by: str | None = Field(default=None, min_length=1, max_length=128)
    submission_source: str | None = Field(default=None, min_length=1, max_length=128)
    partner_organization_id: str | None = Field(default=None, min_length=1, max_length=64)
    partner_organization_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    paid_partner: bool = False
    paid_partner_label: str | None = Field(default=None, min_length=1, max_length=128)
    role_family_bindings: tuple[OpportunityRoleFamilyBindingCreate, ...] = Field(
        min_length=1,
    )
    region_bindings: tuple[OpportunityRegionBindingCreate, ...] = Field(min_length=1)
    submitted_at: datetime | None = None

    @field_validator(
        "submission_id",
        "opportunity_id",
        "employer_id",
        "submitted_by",
        "submission_source",
        "partner_organization_id",
        "partner_organization_name",
        "paid_partner_label",
    )
    @classmethod
    def _submission_optional_strings_not_blank(
        cls,
        value: str | None,
    ) -> str | None:
        return _clean_optional_string(value)

    @field_validator("employer_name", "program_name", "eligibility_summary")
    @classmethod
    def _submission_required_strings_not_blank(cls, value: str) -> str:
        return _clean_required_string(value)

    @field_validator("application_url")
    @classmethod
    def _application_url_must_be_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_public_url(value, field_name="application_url")

    @field_validator("source_url")
    @classmethod
    def _source_url_must_be_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_public_url(value, field_name="source_url")

    @field_validator("expires_at", "submitted_at")
    @classmethod
    def _submission_datetimes_must_be_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        return _aware_datetime(value, field_name="datetime")

    @model_validator(mode="after")
    def _submission_is_safe_and_complete(self) -> Self:
        if self.application_url is None and self.source_url is None:
            raise ValueError("application_url or source_url is required")
        if (
            self.application_open_date is not None
            and self.application_deadline is not None
            and self.application_deadline < self.application_open_date
        ):
            raise ValueError("application_deadline must not precede application_open_date")
        if (
            self.compensation_min is not None
            and self.compensation_max is not None
            and self.compensation_max < self.compensation_min
        ):
            raise ValueError("compensation_max must be greater than or equal to min")
        if (
            not self.compensation_disclosed
            and (self.compensation_min is not None or self.compensation_max is not None)
        ):
            raise ValueError("compensation_disclosed must be true when compensation exists")
        if self.paid_partner and self.paid_partner_label is None:
            raise ValueError("paid partner submissions require visible paid metadata")
        return self


class OpportunityReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    review_action: OpportunityReviewAction
    reviewer_id: str = Field(min_length=1, max_length=128)
    reviewer_name: str | None = Field(default=None, min_length=1, max_length=255)
    review_note: str | None = Field(default=None, min_length=1, max_length=4096)
    correction_reason: str | None = Field(default=None, min_length=1, max_length=2048)
    source_url_checked: str | None = Field(default=None, min_length=1, max_length=2048)
    official_employer_url: str | None = Field(default=None, min_length=1, max_length=2048)
    reviewed_at: datetime | None = None

    @field_validator(
        "reviewer_id",
        "reviewer_name",
        "review_note",
        "correction_reason",
    )
    @classmethod
    def _review_strings_not_blank(cls, value: str | None) -> str | None:
        return _clean_optional_string(value)

    @field_validator("source_url_checked")
    @classmethod
    def _source_url_checked_must_be_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_public_url(value, field_name="source_url_checked")

    @field_validator("official_employer_url")
    @classmethod
    def _official_employer_url_must_be_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_public_url(value, field_name="official_employer_url")

    @field_validator("reviewed_at")
    @classmethod
    def _reviewed_at_must_be_aware(cls, value: datetime | None) -> datetime | None:
        return _aware_datetime(value, field_name="reviewed_at")

    @model_validator(mode="after")
    def _review_action_has_required_evidence(self) -> Self:
        if (
            self.review_action is OpportunityReviewAction.APPROVE_AS_VERIFIED
            and self.official_employer_url is None
        ):
            raise ValueError("approve_as_verified requires official_employer_url")
        if (
            self.review_action is OpportunityReviewAction.APPROVE_AS_SOURCE_CHECKED
            and self.source_url_checked is None
        ):
            raise ValueError("approve_as_source_checked requires source_url_checked")
        if (
            self.review_action is OpportunityReviewAction.REQUEST_CORRECTION
            and self.correction_reason is None
        ):
            raise ValueError("request_correction requires correction_reason")
        return self


class EmployerProgramPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    employer_program_id: str
    employer_id: str | None = None
    employer_name: str
    program_name: str
    program_type: OpportunityProgramType
    program_url: str | None = None
    created_at: datetime
    updated_at: datetime


class OpportunitySourcePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    opportunity_source_id: str
    source_type: OpportunitySourceType
    source_url: str
    source_name: str | None = None
    collected_at: datetime | None = None
    verification_note: str | None = None
    created_at: datetime


class OpportunityRegionBindingPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    opportunity_region_binding_id: str
    region_id: str | None = None
    region_label: str
    metro_area: str | None = None
    binding_confidence: OpportunityBindingConfidence
    created_at: datetime


class OpportunityRoleFamilyBindingPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    opportunity_role_family_binding_id: str
    role_family: str
    role_family_label: str | None = None
    binding_confidence: OpportunityBindingConfidence
    created_at: datetime


class EmployerInfluenceMetadataPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    employer_influence_metadata_id: str
    partner_submitted: bool
    paid_partner: bool
    ranking_influence_allowed: bool
    submitted_by_partner_id: str | None = None
    paid_partner_label: str | None = None
    created_at: datetime
    updated_at: datetime


class OpportunityPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    employer_program: EmployerProgramPayload | None = None
    employer_id: str | None = None
    employer_name: str
    program_name: str
    program_type: OpportunityProgramType
    role_families: tuple[str, ...] = Field(default_factory=tuple)
    regions: tuple[str, ...] = Field(default_factory=tuple)
    location_mode: OpportunityLocationMode
    seniority_level: OpportunitySeniorityLevel
    eligibility_summary: str | None = None
    application_url: str
    source_url: str
    source_type: OpportunitySourceType
    application_open_date: date | None = None
    application_deadline: date | None = None
    expires_at: datetime | None = None
    expiration_state: OpportunityExpirationState
    compensation_min: float | None = None
    compensation_max: float | None = None
    compensation_disclosed: bool
    trust_label: OpportunityTrustLabel
    review_status: OpportunityReviewStatus
    partner_submitted: bool
    paid_partner: bool
    ranking_influence_allowed: bool
    created_at: datetime
    updated_at: datetime
    sources: tuple[OpportunitySourcePayload, ...] = Field(default_factory=tuple)
    region_bindings: tuple[OpportunityRegionBindingPayload, ...] = Field(
        default_factory=tuple,
    )
    role_family_bindings: tuple[OpportunityRoleFamilyBindingPayload, ...] = Field(
        default_factory=tuple,
    )
    employer_influence: EmployerInfluenceMetadataPayload | None = None
    trust_tier: TrustTier = TrustTier.NOT_ASSESSED
    evidence_requirements_met: tuple[EvidenceRequirementResult, ...] = Field(
        default_factory=tuple,
    )
    evidence_requirements_missing: tuple[EvidenceRequirementResult, ...] = Field(
        default_factory=tuple,
    )
    evidence_requirements_failed: tuple[EvidenceRequirementResult, ...] = Field(
        default_factory=tuple,
    )
    trust_warnings: tuple[TrustWarning, ...] = Field(default_factory=tuple)
    risk_level: RiskLevel | None = None
    routing_outcome: RoutingOutcome | None = None
    routing_reasons: tuple[RiskRoutingReasonCode, ...] = Field(default_factory=tuple)
    ranking_influence_decision: RankingInfluenceDecision = (
        RankingInfluenceDecision.DENIED
    )
    ranking_influence_reason: str | None = None
    ranking_influence_reason_codes: tuple[RankingInfluenceReasonCode, ...] = Field(
        default_factory=tuple,
    )
    trust_explanation: TrustExplanation | None = None
    report_recheck_status: ReportRecheckStatus | None = None
    exception_status: ExceptionSubjectStatus | None = None


class OpportunityListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    opportunities: tuple[OpportunityPayload, ...] = Field(default_factory=tuple)


class OpportunitySubmissionReviewSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    review_action: OpportunityReviewAction
    resulting_trust_label: OpportunityTrustLabel
    resulting_review_status: OpportunityReviewStatus
    reviewed_at: datetime
    correction_reason: str | None = None
    source_url_checked: str | None = None
    official_employer_url: str | None = None


class OpportunitySubmissionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    submission_id: str
    opportunity_id: str
    status: OpportunitySubmissionStatus
    submitted_at: datetime
    submitter_contact: str
    submitted_by: str | None = None
    submission_source: str | None = None
    partner_organization_id: str | None = None
    partner_organization_name: str | None = None
    paid_partner: bool
    paid_partner_label: str | None = None
    opportunity: OpportunityPayload
    latest_review: OpportunitySubmissionReviewSummary | None = None


class OpportunitySubmissionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    submissions: tuple[OpportunitySubmissionPayload, ...] = Field(default_factory=tuple)


def _clean_optional_string(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


def _clean_required_string(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


def _aware_datetime(value: datetime | None, *, field_name: str) -> datetime | None:
    if value is not None and value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


def _safe_public_url(value: str, *, field_name: str) -> str:
    stripped = value.strip()
    parsed = urlparse(stripped)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field_name} must be an http(s) URL")
    if parsed.username or parsed.password:
        raise ValueError(f"{field_name} must not contain credentials")
    hostname = (parsed.hostname or "").lower()
    if _hostname_is_private_or_local(hostname):
        raise ValueError(f"{field_name} must not point to private or local hosts")
    sensitive_keys = {"token", "key", "secret", "password", "credential"}
    for key, _value in parse_qsl(parsed.query, keep_blank_values=True):
        if any(fragment in key.lower() for fragment in sensitive_keys):
            raise ValueError(f"{field_name} must not include credential query fields")
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
