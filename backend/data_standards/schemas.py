"""Layer 27 standards definitions and partner submission schemas."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.shared.confidence import Confidence


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class StandardDefinitionStatus(_Vocabulary):
    ACTIVE = "active"
    DRAFT = "draft"
    DEPRECATED = "deprecated"


class PartnerRecordType(_Vocabulary):
    COMPANY = "company"
    REGION = "region"
    EARLY_CAREER_PROGRAM = "early_career_program"
    HIRING_SIGNAL = "hiring_signal"
    COMPANY_REGION_PRESENCE = "company_region_presence"


class PartnerSubmitterType(_Vocabulary):
    EMPLOYER = "employer"
    EDUCATION_INSTITUTION = "education_institution"
    WORKFORCE_BOARD = "workforce_board"
    DATA_VENDOR = "data_vendor"
    NONPROFIT_PARTNER = "nonprofit_partner"
    GOVERNMENT_AGENCY = "government_agency"


class PartnerValidationStatus(_Vocabulary):
    RECEIVED = "received"
    VALIDATED = "validated"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"
    CERTIFIED = "certified"
    ARCHIVED = "archived"


class SubmissionReviewLifecycleState(_Vocabulary):
    SUBMITTED = "submitted"
    VALIDATION_FAILED = "validation_failed"
    VALIDATION_PASSED = "validation_passed"
    UNDER_REVIEW = "under_review"
    NEEDS_CHANGES = "needs_changes"
    ACCEPTED_AS_CANDIDATE = "accepted_as_candidate"
    REJECTED = "rejected"
    MERGED = "merged"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"


class CandidateFactState(_Vocabulary):
    PENDING_REVIEW = "pending_review"
    APPROVED_FOR_MERGE = "approved_for_merge"
    REJECTED = "rejected"
    NEEDS_CORRECTION = "needs_correction"
    CONFLICT = "conflict"
    DUPLICATE = "duplicate"
    LOW_CONFIDENCE = "low_confidence"
    ESCALATED = "escalated"
    MERGED = "merged"


class CandidateReviewDecision(_Vocabulary):
    APPROVE_CANDIDATE = "approve_candidate"
    REJECT_CANDIDATE = "reject_candidate"
    REQUEST_CHANGES = "request_changes"
    MARK_DUPLICATE = "mark_duplicate"
    MARK_LOW_CONFIDENCE = "mark_low_confidence"
    ESCALATE = "escalate"
    MERGE_TO_CANONICAL = "merge_to_canonical"
    RESOLVE_CONFLICTS = "resolve_conflicts"
    APPROVE_FOR_MERGE = "approve_for_merge"
    REJECT = "reject"
    REQUEST_CORRECTION = "request_correction"
    MARK_CONFLICT = "mark_conflict"


class CandidateCanonicalTargetType(_Vocabulary):
    COMPANY = "company"
    REGION = "region"
    COMPANY_REGION_PRESENCE = "company_region_presence"
    COMPANY_REGION_HIRING = "company_region_hiring"
    UNSUPPORTED = "unsupported"


class CanonicalMergeAction(_Vocabulary):
    CREATE = "create"
    NOOP = "noop"


class CanonicalMergeStatus(_Vocabulary):
    PREVIEW_READY = "preview_ready"
    BLOCKED = "blocked"
    MERGED = "merged"


class PartnerFreshnessStatus(_Vocabulary):
    FRESH = "fresh"
    STALE = "stale"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class PartnerType(_Vocabulary):
    UNIVERSITY = "university"
    WORKFORCE_BOARD = "workforce_board"
    BOOTCAMP = "bootcamp"
    REGIONAL_ECONOMIC_GROUP = "regional_economic_group"
    CAREER_PLATFORM = "career_platform"
    EMPLOYER = "employer"
    RESEARCH_GROUP = "research_group"
    PUBLIC_AGENCY = "public_agency"


class PartnerVerificationStatus(_Vocabulary):
    UNVERIFIED = "unverified"
    PENDING_REVIEW = "pending_review"
    VERIFIED = "verified"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class PartnerTrustTier(_Vocabulary):
    TIER_1_VERIFIED_INSTITUTIONAL = "tier_1_verified_institutional"
    TIER_2_VERIFIED_REGIONAL = "tier_2_verified_regional"
    TIER_3_VERIFIED_PLATFORM = "tier_3_verified_platform"
    TIER_4_LIMITED_PARTNER = "tier_4_limited_partner"
    UNTRUSTED = "untrusted"


class DataQualityLabelValue(_Vocabulary):
    VERIFIED_PARTNER_DATA = "verified_partner_data"
    AUDITED_SOURCE_DATA = "audited_source_data"
    SELF_REPORTED_EMPLOYER_DATA = "self_reported_employer_data"
    PUBLIC_SOURCE_VERIFIED = "public_source_verified"
    LOW_CONFIDENCE_SIGNAL = "low_confidence_signal"


class GovernanceArea(_Vocabulary):
    DATA_ETHICS = "data_ethics"
    LABOR_MARKET_FAIRNESS = "labor_market_fairness"
    SOURCE_STANDARDS = "source_standards"
    INSTITUTIONAL_USE = "institutional_use"
    BIAS_REVIEW = "bias_review"


class GovernanceStatus(_Vocabulary):
    FRAMEWORK_DEFINED = "framework_defined"


class StandardDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    term: str = Field(min_length=1, max_length=128)
    canonical_name: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=2048)
    inclusion_criteria: tuple[str, ...] = Field(min_length=1, max_length=20)
    exclusion_criteria: tuple[str, ...] = Field(min_length=1, max_length=20)
    examples: tuple[str, ...] = Field(min_length=1, max_length=20)
    related_terms: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    version: str = Field(min_length=1, max_length=64)
    status: StandardDefinitionStatus = StandardDefinitionStatus.ACTIVE

    @field_validator(
        "term",
        "canonical_name",
        "description",
        "version",
    )
    @classmethod
    def _text_safe(cls, value: str) -> str:
        return _safe_text(value, label="standard definition")

    @field_validator(
        "inclusion_criteria",
        "exclusion_criteria",
        "examples",
        "related_terms",
    )
    @classmethod
    def _tuple_text_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_text(item, label="standard definition list") for item in value)


class StandardDefinitionList(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str
    definitions: tuple[StandardDefinition, ...]


class PartnerPublicContactMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    website_url: str | None = Field(default=None, min_length=1, max_length=2048)
    contact_page_url: str | None = Field(default=None, min_length=1, max_length=2048)
    public_contact_label: str | None = Field(default=None, min_length=1, max_length=255)
    public_notes: str | None = Field(default=None, min_length=1, max_length=512)

    @field_validator("website_url", "contact_page_url")
    @classmethod
    def _url_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_url(value, label="partner public contact url")

    @field_validator("public_contact_label", "public_notes")
    @classmethod
    def _text_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_text(value, label="partner public contact metadata")


class PartnerRegistryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    partner_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    partner_type: PartnerType
    region_scope: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    verification_status: PartnerVerificationStatus
    allowed_submission_types: tuple[PartnerRecordType, ...] = Field(
        default_factory=tuple,
        max_length=20,
    )
    trust_tier: PartnerTrustTier
    public_contact_metadata: PartnerPublicContactMetadata
    created_at: datetime
    updated_at: datetime

    @field_validator("partner_id", "name")
    @classmethod
    def _text_safe(cls, value: str) -> str:
        return _safe_text(value, label="partner registry record")

    @field_validator("region_scope")
    @classmethod
    def _region_scope_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_text(item, label="partner region scope") for item in value)


class PartnerRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str
    supported_partner_types: tuple[str, ...]
    verification_statuses: tuple[str, ...]
    trust_tiers: tuple[str, ...]
    partners: tuple[PartnerRegistryRecord, ...]


class PartnerSourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_ref_id: str = Field(min_length=1, max_length=128)
    source_type: str = Field(min_length=1, max_length=64)
    url: str | None = Field(default=None, min_length=1, max_length=2048)
    citation: str | None = Field(default=None, min_length=1, max_length=1024)
    collected_at: datetime | date | None = None
    license_or_terms_category: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
    )
    notes: str | None = Field(default=None, min_length=1, max_length=1024)

    @field_validator(
        "source_ref_id",
        "source_type",
        "citation",
        "license_or_terms_category",
        "notes",
    )
    @classmethod
    def _text_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_text(value, label="source ref")

    @field_validator("url")
    @classmethod
    def _url_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = _safe_text(value, label="source ref url")
        if not cleaned.startswith(("https://", "http://")):
            raise ValueError("source ref url must be http(s)")
        lowered = cleaned.casefold()
        if any(token in lowered for token in ("localhost", "127.0.0.1", "169.254.")):
            raise ValueError("source ref url must not point at local/internal hosts")
        return cleaned

    @model_validator(mode="after")
    def _url_or_citation_required(self) -> Self:
        if self.url is None and self.citation is None:
            raise ValueError("source ref requires url or citation")
        return self


class PartnerFreshness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    freshness_status: PartnerFreshnessStatus
    observed_at: datetime | date | None = None
    freshness_expires_at: datetime | date | None = None
    declared_at: datetime | date | None = None
    notes: str | None = Field(default=None, min_length=1, max_length=1024)

    @field_validator("notes")
    @classmethod
    def _notes_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_text(value, label="freshness notes")


class PartnerConfidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    confidence_label: Confidence
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    rationale: str | None = Field(default=None, min_length=1, max_length=1024)

    @field_validator("rationale")
    @classmethod
    def _rationale_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_text(value, label="confidence rationale")


class PartnerSubmissionWarning(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=512)
    record_id: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("code", "message", "record_id")
    @classmethod
    def _text_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_text(value, label="submission warning")


class PartnerSubmissionValidationError(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1, max_length=64)
    field: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1, max_length=512)
    record_id: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("code", "field", "message", "record_id")
    @classmethod
    def _text_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_text(value, label="validation error")


class PartnerSubmissionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    record_id: str = Field(min_length=1, max_length=128)
    record_type: PartnerRecordType
    payload: dict[str, Any] = Field(default_factory=dict)
    source_ref_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=20)

    @field_validator("record_id", "source_ref_ids")
    @classmethod
    def _text_safe(cls, value: str | tuple[str, ...]) -> str | tuple[str, ...]:
        if isinstance(value, tuple):
            return tuple(_safe_text(item, label="record source ref") for item in value)
        return _safe_text(value, label="submission record")

    @field_validator("payload")
    @classmethod
    def _payload_safe(cls, value: dict[str, Any]) -> dict[str, Any]:
        _assert_no_private_keys(value)
        return value


class PartnerSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    submission_id: str = Field(min_length=1, max_length=128)
    partner_id: str = Field(min_length=1, max_length=128)
    submitted_at: datetime
    schema_version: str = Field(min_length=1, max_length=64)
    submitter_type: PartnerSubmitterType
    records: tuple[PartnerSubmissionRecord, ...] = Field(min_length=1, max_length=500)
    source_refs: tuple[PartnerSourceRef, ...] = Field(min_length=1, max_length=500)
    freshness: PartnerFreshness
    confidence: PartnerConfidence
    warnings: tuple[PartnerSubmissionWarning, ...] = Field(default_factory=tuple, max_length=50)
    validation_status: PartnerValidationStatus = PartnerValidationStatus.RECEIVED

    @field_validator("submission_id", "partner_id", "schema_version")
    @classmethod
    def _text_safe(cls, value: str) -> str:
        return _safe_text(value, label="partner submission")


class PartnerSubmissionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    supported_submitter_types: tuple[str, ...]
    supported_record_types: tuple[str, ...]
    validation_statuses: tuple[str, ...]
    review_lifecycle_states: tuple[str, ...]
    required_submission_fields: tuple[str, ...]
    required_fields_by_record_type: dict[str, tuple[str, ...]]
    source_refs_required_for_record_types: tuple[str, ...]
    freshness_required: bool = True
    confidence_required: bool = True


class PartnerSubmissionValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    validation_status: PartnerValidationStatus
    schema_version: str | None = None
    errors: tuple[PartnerSubmissionValidationError, ...] = Field(default_factory=tuple)
    warnings: tuple[PartnerSubmissionWarning, ...] = Field(default_factory=tuple)
    normalized_submission: PartnerSubmission | None = None


class PartnerIdentityContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    partner_id: str = Field(min_length=1, max_length=128)
    partner_name: str | None = Field(default=None, min_length=1, max_length=255)
    partner_type: PartnerType | None = None
    verification_status: PartnerVerificationStatus
    trust_tier: PartnerTrustTier
    region_scope: tuple[str, ...] = Field(default_factory=tuple, max_length=50)

    @field_validator("partner_id", "partner_name", "region_scope")
    @classmethod
    def _text_safe(
        cls,
        value: str | tuple[str, ...] | None,
    ) -> str | tuple[str, ...] | None:
        if value is None:
            return None
        if isinstance(value, tuple):
            return tuple(_safe_text(item, label="partner identity context") for item in value)
        return _safe_text(value, label="partner identity context")


class CandidateProvenanceSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    partner: PartnerIdentityContext
    submitter_type: PartnerSubmitterType
    submitted_at: datetime
    source_refs: tuple[PartnerSourceRef, ...] = Field(default_factory=tuple, max_length=50)
    freshness: PartnerFreshness
    confidence: PartnerConfidence
    provenance_complete: bool
    provenance_warnings: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    ranking_influence_allowed: Literal[False] = False

    @field_validator("provenance_warnings")
    @classmethod
    def _warnings_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_text(item, label="candidate provenance warning") for item in value)


class CandidateFactPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_fact_id: str
    partner_submission_id: str
    record_id: str
    record_type: PartnerRecordType
    candidate_state: CandidateFactState
    canonical_target_type: CandidateCanonicalTargetType
    canonical_target_id: str
    canonical_target_key: dict[str, Any]
    fact_payload: dict[str, Any]
    raw_record: dict[str, Any]
    provenance: CandidateProvenanceSnapshot
    created_at: datetime
    updated_at: datetime


class CandidateFactListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidates: tuple[CandidateFactPayload, ...] = Field(default_factory=tuple)


class CandidateReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: CandidateReviewDecision
    reviewer_id: str = Field(min_length=1, max_length=128)
    reviewer_name: str | None = Field(default=None, min_length=1, max_length=255)
    reason: str = Field(min_length=1, max_length=2048)
    decision_notes: str = Field(min_length=1, max_length=4096)
    source_basis: dict[str, Any] = Field(default_factory=dict)
    before_after_diff: dict[str, Any] = Field(default_factory=dict)
    reviewed_at: datetime | None = None

    @field_validator("reviewer_id", "reviewer_name", "reason", "decision_notes")
    @classmethod
    def _review_text_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_text(value, label="candidate review")

    @field_validator("reviewed_at")
    @classmethod
    def _reviewed_at_must_be_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("reviewed_at must be timezone-aware")
        return value

    @field_validator("source_basis", "before_after_diff")
    @classmethod
    def _review_dict_safe(cls, value: dict[str, Any]) -> dict[str, Any]:
        _assert_no_private_keys(value)
        return value

    @model_validator(mode="after")
    def _decision_has_required_context(self) -> Self:
        if not self.source_basis:
            raise ValueError("candidate review requires source_basis")
        if self.decision in {
            CandidateReviewDecision.REQUEST_CHANGES,
            CandidateReviewDecision.REQUEST_CORRECTION,
            CandidateReviewDecision.REJECT,
            CandidateReviewDecision.REJECT_CANDIDATE,
            CandidateReviewDecision.MARK_DUPLICATE,
            CandidateReviewDecision.MARK_LOW_CONFIDENCE,
            CandidateReviewDecision.ESCALATE,
            CandidateReviewDecision.MARK_CONFLICT,
            CandidateReviewDecision.RESOLVE_CONFLICTS,
            CandidateReviewDecision.MERGE_TO_CANONICAL,
        } and not self.before_after_diff:
            raise ValueError(f"{self.decision.value} requires before_after_diff")
        return self


class CandidateReviewPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_review_id: str
    candidate_fact_id: str
    partner_submission_id: str
    decision: CandidateReviewDecision
    resulting_candidate_state: CandidateFactState
    reviewed_at: datetime
    reviewer_name: str | None = None
    reason: str
    source_basis: dict[str, Any]
    before_after_diff: dict[str, Any]
    audit_event_id: str
    resolved_conflict_codes: tuple[str, ...] = Field(default_factory=tuple)
    provenance_complete: bool
    ranking_influence_allowed: Literal[False] = False


class MergeConflict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1, max_length=64)
    field: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=512)
    canonical_value: Any = None
    candidate_value: Any = None

    @field_validator("code", "field", "message")
    @classmethod
    def _conflict_text_safe(cls, value: str) -> str:
        return _safe_text(value, label="merge conflict")


class CanonicalMergePreview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_fact_id: str
    canonical_target_type: CandidateCanonicalTargetType
    canonical_target_id: str
    status: CanonicalMergeStatus
    action: CanonicalMergeAction | None = None
    can_merge: bool
    blockers: tuple[str, ...] = Field(default_factory=tuple)
    conflicts: tuple[MergeConflict, ...] = Field(default_factory=tuple)
    canonical_before: dict[str, Any] | None = None
    canonical_after: dict[str, Any] | None = None
    provenance_complete: bool
    latest_review: CandidateReviewPayload | None = None
    ranking_influence_allowed: Literal[False] = False


class CanonicalMergeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    merged_by: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=2048)
    merged_at: datetime | None = None

    @field_validator("merged_by", "reason")
    @classmethod
    def _merge_text_safe(cls, value: str) -> str:
        return _safe_text(value, label="canonical merge request")

    @field_validator("merged_at")
    @classmethod
    def _merged_at_must_be_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("merged_at must be timezone-aware")
        return value


class CanonicalMergeResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    merge_record_id: str
    candidate_fact_id: str
    canonical_target_type: CandidateCanonicalTargetType
    canonical_target_id: str
    status: CanonicalMergeStatus
    action: CanonicalMergeAction
    audit_event_id: str
    provenance_link_ids: tuple[str, ...] = Field(default_factory=tuple)
    invalidation_directives: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    stale_output_ids: tuple[str, ...] = Field(default_factory=tuple)
    merged_at: datetime
    ranking_influence_allowed: Literal[False] = False


class DataQualityLabel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: DataQualityLabelValue
    display_name: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=2048)
    allowed_sources: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    minimum_confidence: Confidence
    requires_source_refs: bool
    requires_partner_verification: bool
    ranking_influence_allowed: Literal[False] = False
    public_display_allowed: bool
    warning_copy: str = Field(min_length=1, max_length=1024)

    @field_validator("display_name", "description", "warning_copy")
    @classmethod
    def _text_safe(cls, value: str) -> str:
        return _safe_text(value, label="data quality label")

    @field_validator("allowed_sources")
    @classmethod
    def _allowed_sources_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_text(item, label="quality label source") for item in value)


class DataQualityLabelList(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str
    labels: tuple[DataQualityLabel, ...]


class DataQualityCertificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: DataQualityLabelValue
    partner_id: str | None = Field(default=None, min_length=1, max_length=128)
    submitter_type: PartnerSubmitterType | None = None
    record: PartnerSubmissionRecord | None = None
    source_refs: tuple[PartnerSourceRef, ...] = Field(default_factory=tuple, max_length=50)
    freshness: PartnerFreshness | None = None
    confidence: PartnerConfidence | None = None
    audit_marker: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("partner_id", "audit_marker")
    @classmethod
    def _text_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_text(value, label="quality label evaluation")


class DataQualityCertificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: DataQualityLabel
    eligible: bool
    certification_status: Literal["eligible", "not_eligible"]
    reasons: tuple[str, ...] = Field(default_factory=tuple)
    warnings: tuple[str, ...] = Field(default_factory=tuple)
    partner_id: str | None = None
    partner_verification_status: PartnerVerificationStatus | None = None
    partner_trust_tier: PartnerTrustTier | None = None
    source_ref_count: int = Field(ge=0)
    freshness: PartnerFreshness | None = None
    confidence: PartnerConfidence | None = None
    ranking_influence_allowed: Literal[False] = False
    public_display_allowed: bool


class GovernanceFrameworkRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    area: GovernanceArea
    display_name: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=2048)
    review_questions: tuple[str, ...] = Field(min_length=1, max_length=20)
    risk_flags: tuple[str, ...] = Field(min_length=1, max_length=20)
    recommended_controls: tuple[str, ...] = Field(min_length=1, max_length=20)
    status: GovernanceStatus = GovernanceStatus.FRAMEWORK_DEFINED
    version: str = Field(min_length=1, max_length=64)
    public_summary: str = Field(min_length=1, max_length=1024)

    @field_validator("display_name", "description", "version", "public_summary")
    @classmethod
    def _text_safe(cls, value: str) -> str:
        return _safe_text(value, label="governance framework")

    @field_validator("review_questions", "risk_flags", "recommended_controls")
    @classmethod
    def _list_text_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_text(item, label="governance framework list") for item in value)


class GovernanceFramework(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str
    status: GovernanceStatus = GovernanceStatus.FRAMEWORK_DEFINED
    governance_records: tuple[GovernanceFrameworkRecord, ...]


def _safe_text(value: str, *, label: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{label} must not be blank")
    lowered = cleaned.casefold()
    if any(
        token in lowered
        for token in (
            "internal_review_notes",
            "private_metadata",
            "admin_metadata",
            "raw_scrape",
        )
    ):
        raise ValueError(f"{label} contains private/internal metadata")
    return cleaned


def _safe_url(value: str, *, label: str) -> str:
    cleaned = _safe_text(value, label=label)
    if not cleaned.startswith(("https://", "http://")):
        raise ValueError(f"{label} must be http(s)")
    lowered = cleaned.casefold()
    if any(token in lowered for token in ("localhost", "127.0.0.1", "169.254.")):
        raise ValueError(f"{label} must not point at local/internal hosts")
    return cleaned


def _assert_no_private_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).casefold() in {
                "internal_review_notes",
                "private_metadata",
                "admin_metadata",
            }:
                raise ValueError("partner payload contains private/internal metadata")
            _assert_no_private_keys(item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_private_keys(item)
