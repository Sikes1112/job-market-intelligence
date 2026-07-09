"""Shared Layer 30 trust, evidence, risk, and ranking contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

TRUST_ASSESSMENT_VERSION = "30A.1"
TRUST_ASSESSMENT_SOURCE = "deterministic_layer_30a"
RISK_ROUTING_DECISION_VERSION = "30B.1"
RISK_ROUTING_DECISION_SOURCE = "deterministic_layer_30b"
TRUST_EXPLANATION_VERSION = "30C"
AUTOMATED_RECHECK_DECISION_VERSION = "30D.1"
EXCEPTION_WORKFLOW_VERSION = "30E.1"


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class TrustTier(_Vocabulary):
    TRUSTED = "trusted"
    VERIFIED = "verified"
    PARTNER_SUBMITTED = "partner_submitted"
    UNVERIFIED_VISIBLE = "unverified_visible"
    LOW_CONFIDENCE = "low_confidence"
    CONFLICTING = "conflicting"
    STALE = "stale"
    QUARANTINED = "quarantined"
    RANKING_INELIGIBLE = "ranking_ineligible"
    BLOCKED = "blocked"
    NOT_ASSESSED = "not_assessed"


class EvidenceRequirementStatus(_Vocabulary):
    MET = "met"
    MISSING = "missing"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"


class EvidenceRequirementCode(_Vocabulary):
    VALID_FIELDS = "valid_fields"
    SOURCE_PRESENT = "source_present"
    SOURCE_ALLOWED = "source_allowed"
    SOURCE_FRESH = "source_fresh"
    OBSERVATION_DATE_VALID = "observation_date_valid"
    CONFIDENCE_SUFFICIENT = "confidence_sufficient"
    NO_DUPLICATE_DETECTED = "no_duplicate_detected"
    NO_CONFLICT_DETECTED = "no_conflict_detected"
    INDEPENDENT_VERIFICATION = "independent_verification"
    PARTNER_TRUST_SUFFICIENT = "partner_trust_sufficient"
    NOT_SELF_PROMOTIONAL = "not_self_promotional"
    CORROBORATION_PRESENT = "corroboration_present"
    CLAIM_TYPE_ALLOWED = "claim_type_allowed"
    RANKING_EVIDENCE_SUFFICIENT = "ranking_evidence_sufficient"


class TrustAssessmentSubjectType(_Vocabulary):
    OPPORTUNITY = "opportunity"
    DATA_STANDARD_FACT = "data_standard_fact"
    PARTNER_SUBMISSION = "partner_submission"
    COMPANY_FACT = "company_fact"
    REGION_FACT = "region_fact"
    RECOMMENDATION_INPUT = "recommendation_input"
    DASHBOARD_ITEM = "dashboard_item"


class RiskLevel(_Vocabulary):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class RoutingOutcome(_Vocabulary):
    AUTO_ACCEPT_NON_RANKING = "auto_accept_non_ranking"
    VISIBLE_WITH_WARNING = "visible_with_warning"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"
    AUTO_RECHECK = "auto_recheck"
    AUTO_REJECT = "auto_reject"
    QUARANTINE = "quarantine"
    BLOCKED = "blocked"
    ESCALATE_EXCEPTION = "escalate_exception"
    NOT_ROUTED = "not_routed"


class RankingInfluenceDecision(_Vocabulary):
    ALLOWED = "allowed"
    DENIED = "denied"
    NOT_APPLICABLE = "not_applicable"
    NOT_ASSESSED = "not_assessed"


class RankingInfluenceReasonCode(_Vocabulary):
    TRUSTED_FRESH_HIGH_CONFIDENCE = "trusted_fresh_high_confidence"
    VERIFIED_FRESH_NO_CONFLICT = "verified_fresh_no_conflict"
    PARTNER_SUBMITTED_NOT_VERIFIED = "partner_submitted_not_verified"
    STALE_SOURCE = "stale_source"
    LOW_CONFIDENCE = "low_confidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    DUPLICATE_RISK = "duplicate_risk"
    MISSING_SOURCE = "missing_source"
    SOURCE_NOT_ALLOWED = "source_not_allowed"
    SELF_PROMOTIONAL_SOURCE = "self_promotional_source"
    CORROBORATION_MISSING = "corroboration_missing"
    HIGH_IMPACT_UNCORROBORATED = "high_impact_uncorroborated"
    BLOCKED_OR_QUARANTINED = "blocked_or_quarantined"
    CLAIM_TYPE_NOT_ALLOWED = "claim_type_not_allowed"
    LEGACY_UNASSESSED = "legacy_unassessed"
    ASSESSMENT_MISSING = "assessment_missing"
    EVIDENCE_REQUIREMENTS_MISSING = "evidence_requirements_missing"
    PUBLIC_DEMO_RESTRICTED = "public_demo_restricted"
    RANKING_DEFAULT_DENIED = "ranking_default_denied"


class RiskRoutingReasonCode(_Vocabulary):
    LOW_RISK_VISIBLE_NON_RANKING = "low_risk_visible_non_ranking"
    MEDIUM_RISK_WARNING_REQUIRED = "medium_risk_warning_required"
    HIGH_RISK_MORE_EVIDENCE_REQUIRED = "high_risk_more_evidence_required"
    CRITICAL_RISK_BLOCKED = "critical_risk_blocked"
    STALE_RECHECK_REQUIRED = "stale_recheck_required"
    CONFLICT_REQUIRES_QUARANTINE = "conflict_requires_quarantine"
    PARTNER_SUBMISSION_NON_RANKING = "partner_submission_non_ranking"
    MISSING_EVIDENCE_NON_RANKING = "missing_evidence_non_ranking"
    BLOCKED_POLICY_SIGNAL = "blocked_policy_signal"


class UserReportType(_Vocabulary):
    OUTDATED = "outdated"
    INCORRECT = "incorrect"
    DUPLICATE = "duplicate"
    SPAM = "spam"
    MISLEADING = "misleading"
    EXPIRED_OPPORTUNITY = "expired_opportunity"
    WRONG_COMPANY = "wrong_company"
    WRONG_REGION = "wrong_region"
    SUSPICIOUS_RANKING = "suspicious_ranking"
    OTHER = "other"


class UserReportSeverity(_Vocabulary):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class UserReportStatus(_Vocabulary):
    RECEIVED = "received"
    QUEUED_FOR_RECHECK = "queued_for_recheck"
    RECHECK_PENDING = "recheck_pending"
    RESOLVED_BY_SYSTEM = "resolved_by_system"
    DISMISSED_LOW_SIGNAL = "dismissed_low_signal"
    ESCALATED_EXCEPTION = "escalated_exception"
    CLOSED = "closed"


class AutomatedRecheckTriggerType(_Vocabulary):
    STALE_SOURCE = "stale_source"
    LOW_CONFIDENCE = "low_confidence"
    MISSING_SECOND_SOURCE = "missing_second_source"
    CONFLICT_DETECTED = "conflict_detected"
    PARTNER_CORRECTION = "partner_correction"
    USER_REPORT = "user_report"
    NEW_SOURCE_AVAILABLE = "new_source_available"
    SCHEDULED_REFRESH = "scheduled_refresh"
    SUSPICIOUS_RANKING = "suspicious_ranking"
    EXPIRED_OPPORTUNITY = "expired_opportunity"


class AutomatedRecheckJobStatus(_Vocabulary):
    QUEUED = "queued"
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    SKIPPED = "skipped"
    ESCALATED_EXCEPTION = "escalated_exception"


class AutomatedRecheckPriority(_Vocabulary):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AutomatedRecheckOutcome(_Vocabulary):
    TRUST_UPGRADED = "trust_upgraded"
    TRUST_DOWNGRADED = "trust_downgraded"
    STILL_LOW_CONFIDENCE = "still_low_confidence"
    QUARANTINED = "quarantined"
    BLOCKED = "blocked"
    RANKING_INFLUENCE_ALLOWED = "ranking_influence_allowed"
    RANKING_INFLUENCE_DENIED = "ranking_influence_denied"
    NO_CHANGE = "no_change"
    NEEDS_EXCEPTION = "needs_exception"
    FAILED = "failed"


class ExceptionCaseType(_Vocabulary):
    FRAUD_SPAM = "fraud_spam"
    LEGAL_RISK = "legal_risk"
    ABUSE_REPORT = "abuse_report"
    UNRESOLVED_CONFLICT = "unresolved_conflict"
    PARTNER_TRUST_UPGRADE = "partner_trust_upgrade"
    RANKING_INFLUENCE_EXCEPTION = "ranking_influence_exception"
    SOURCE_POLICY_DISPUTE = "source_policy_dispute"
    HIGH_IMPACT_MARKET_CORRECTION = "high_impact_market_correction"
    REPEATED_FAILED_RECHECK = "repeated_failed_recheck"
    SUSPICIOUS_RANKING = "suspicious_ranking"
    BLOCKED_OR_QUARANTINED_CRITICAL = "blocked_or_quarantined_critical"
    OTHER = "other"


class ExceptionCaseStatus(_Vocabulary):
    OPEN = "open"
    AUTO_RECHECK_PENDING = "auto_recheck_pending"
    WAITING_FOR_PARTNER_EVIDENCE = "waiting_for_partner_evidence"
    QUARANTINED = "quarantined"
    BLOCKED = "blocked"
    RESOLVED_BY_SYSTEM = "resolved_by_system"
    REQUIRES_HUMAN_EXCEPTION = "requires_human_exception"
    CLOSED = "closed"


class ExceptionSeverity(_Vocabulary):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ExceptionResolutionCode(_Vocabulary):
    RESOLVED_BY_SYSTEM = "resolved_by_system"
    DUPLICATE_CLOSED = "duplicate_closed"
    NO_LONGER_APPLIES = "no_longer_applies"
    PARTNER_EVIDENCE_RECEIVED = "partner_evidence_received"
    CLOSED_NO_ACTION = "closed_no_action"


class PublicExceptionStatus(_Vocabulary):
    NO_EXCEPTION = "no_exception"
    AUTOMATED_RECHECK_PENDING = "automated_recheck_pending"
    QUARANTINED = "quarantined"
    BLOCKED = "blocked"
    RESOLVED_BY_SYSTEM = "resolved_by_system"
    REQUIRES_EXCEPTION_HANDLING = "requires_exception_handling"
    CLOSED = "closed"


TrustWarningSeverity = Literal["info", "warning", "critical"]


class _TrustModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvidenceRequirementResult(_TrustModel):
    code: EvidenceRequirementCode
    status: EvidenceRequirementStatus
    message: str
    source: str


class TrustWarning(_TrustModel):
    warning_code: str
    severity: TrustWarningSeverity
    message: str
    source: str
    evidence_requirement_code: EvidenceRequirementCode | None = None


class TrustSubjectMetadata(_TrustModel):
    subject_type: TrustAssessmentSubjectType
    subject_id: str
    valid_fields: bool | None = None
    source_count: int | None = Field(default=None, ge=0)
    source_present: bool | None = None
    source_allowed: bool | None = None
    freshness_status: str | None = None
    observation_date_valid: bool | None = None
    confidence_label: str | None = None
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    duplicate_detected: bool | None = None
    conflict_detected: bool | None = None
    independent_verification: bool | None = None
    partner_submitted: bool = False
    partner_origin: bool = False
    partner_verification_status: str | None = None
    partner_trust_tier: str | None = None
    self_promotional: bool | None = None
    corroboration_count: int | None = Field(default=None, ge=0)
    claim_type_allowed: bool | None = None
    ranking_influence_allowed: bool | None = None
    expired: bool | None = None
    blocked: bool = False
    quarantined: bool = False
    stale: bool | None = None
    verification_status: str | None = None
    quality_label: str | None = None
    trust_label: str | None = None
    review_status: str | None = None
    warnings: tuple[str, ...] = Field(default_factory=tuple)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class EvidenceEvaluationResult(_TrustModel):
    subject_type: TrustAssessmentSubjectType
    subject_id: str
    requirements: tuple[EvidenceRequirementResult, ...]
    warnings: tuple[TrustWarning, ...] = Field(default_factory=tuple)
    reasons: tuple[str, ...] = Field(default_factory=tuple)

    @property
    def met(self) -> tuple[EvidenceRequirementResult, ...]:
        return tuple(
            result
            for result in self.requirements
            if result.status is EvidenceRequirementStatus.MET
        )

    @property
    def missing(self) -> tuple[EvidenceRequirementResult, ...]:
        return tuple(
            result
            for result in self.requirements
            if result.status is EvidenceRequirementStatus.MISSING
        )

    @property
    def failed(self) -> tuple[EvidenceRequirementResult, ...]:
        return tuple(
            result
            for result in self.requirements
            if result.status is EvidenceRequirementStatus.FAILED
        )

    @property
    def not_applicable(self) -> tuple[EvidenceRequirementResult, ...]:
        return tuple(
            result
            for result in self.requirements
            if result.status is EvidenceRequirementStatus.NOT_APPLICABLE
        )


class TrustAssessmentResult(_TrustModel):
    subject_type: TrustAssessmentSubjectType
    subject_id: str
    trust_tier: TrustTier
    assessment_version: str = TRUST_ASSESSMENT_VERSION
    assessment_source: str = TRUST_ASSESSMENT_SOURCE
    evidence_requirements_met: tuple[EvidenceRequirementResult, ...] = Field(
        default_factory=tuple,
    )
    evidence_requirements_missing: tuple[EvidenceRequirementResult, ...] = Field(
        default_factory=tuple,
    )
    evidence_requirements_failed: tuple[EvidenceRequirementResult, ...] = Field(
        default_factory=tuple,
    )
    evidence_requirements_not_applicable: tuple[EvidenceRequirementResult, ...] = Field(
        default_factory=tuple,
    )
    warnings: tuple[TrustWarning, ...] = Field(default_factory=tuple)
    reasons: tuple[str, ...] = Field(default_factory=tuple)
    ranking_influence_allowed: bool | None = None
    assessed_at: datetime
    expires_at: datetime | None = None
    next_assessment_at: datetime | None = None

    @field_validator("assessed_at", "expires_at", "next_assessment_at")
    @classmethod
    def _datetimes_must_be_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("trust assessment datetimes must be timezone-aware")
        return value


class RankingInfluencePolicyResult(_TrustModel):
    decision: RankingInfluenceDecision
    ranking_influence_allowed: bool = False
    reason: str
    reason_codes: tuple[RankingInfluenceReasonCode, ...] = Field(default_factory=tuple)


class RiskClassificationResult(_TrustModel):
    subject_type: TrustAssessmentSubjectType
    subject_id: str
    trust_tier: TrustTier
    risk_level: RiskLevel
    reason_codes: tuple[RiskRoutingReasonCode, ...] = Field(default_factory=tuple)
    reasons: tuple[str, ...] = Field(default_factory=tuple)


class RiskRoutingDecisionResult(_TrustModel):
    subject_type: TrustAssessmentSubjectType
    subject_id: str
    trust_tier: TrustTier
    risk_level: RiskLevel
    routing_outcome: RoutingOutcome
    routing_reasons: tuple[RiskRoutingReasonCode, ...] = Field(default_factory=tuple)
    ranking_influence_decision: RankingInfluenceDecision
    ranking_influence_allowed: bool = False
    ranking_influence_reason: str
    ranking_influence_reason_codes: tuple[RankingInfluenceReasonCode, ...] = Field(
        default_factory=tuple,
    )
    evidence_requirements_met: tuple[EvidenceRequirementResult, ...] = Field(
        default_factory=tuple,
    )
    evidence_requirements_missing: tuple[EvidenceRequirementResult, ...] = Field(
        default_factory=tuple,
    )
    evidence_requirements_failed: tuple[EvidenceRequirementResult, ...] = Field(
        default_factory=tuple,
    )
    warnings: tuple[TrustWarning, ...] = Field(default_factory=tuple)
    decided_at: datetime
    decision_version: str = RISK_ROUTING_DECISION_VERSION
    decision_source: str = RISK_ROUTING_DECISION_SOURCE
    expires_at: datetime | None = None

    @field_validator("decided_at", "expires_at")
    @classmethod
    def _decision_datetimes_must_be_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("risk routing datetimes must be timezone-aware")
        return value


class UserFacingTrustWarning(_TrustModel):
    warning_code: str
    severity: TrustWarningSeverity
    title: str
    message: str


class ExceptionSubjectStatus(_TrustModel):
    subject_type: TrustAssessmentSubjectType
    subject_id: str
    has_open_exception: bool = False
    exception_case_id: str | None = None
    exception_type: ExceptionCaseType | None = None
    status: ExceptionCaseStatus | None = None
    severity: ExceptionSeverity | None = None
    public_safe_status: PublicExceptionStatus = PublicExceptionStatus.NO_EXCEPTION
    label: str = "No exception"
    message: str = "No rare exception case is open for this item."
    updated_at: datetime | None = None
    resolved_at: datetime | None = None

    @field_validator("updated_at", "resolved_at")
    @classmethod
    def _exception_status_datetime_must_be_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("exception status datetimes must be timezone-aware")
        return value


class ReportRecheckStatus(_TrustModel):
    subject_type: TrustAssessmentSubjectType
    subject_id: str
    latest_report_status: UserReportStatus | None = None
    latest_report_type: UserReportType | None = None
    latest_report_severity: UserReportSeverity | None = None
    latest_reported_at: datetime | None = None
    active_recheck_job_id: str | None = None
    recheck_status: AutomatedRecheckJobStatus | None = None
    recheck_priority: AutomatedRecheckPriority | None = None
    recheck_outcome: AutomatedRecheckOutcome | None = None
    recheck_status_label: str | None = None
    exception_status: ExceptionSubjectStatus | None = None
    message: str

    @field_validator("latest_reported_at")
    @classmethod
    def _report_datetime_must_be_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("report/recheck datetime must be timezone-aware")
        return value


class TrustExplanation(_TrustModel):
    subject_type: TrustAssessmentSubjectType
    subject_id: str
    trust_tier: TrustTier
    trust_label: str
    trust_summary: str
    risk_level: RiskLevel | None = None
    risk_label: str | None = None
    risk_summary: str | None = None
    routing_outcome: RoutingOutcome | None = None
    routing_label: str | None = None
    routing_summary: str | None = None
    ranking_influence_allowed: bool = False
    ranking_influence_decision: RankingInfluenceDecision = (
        RankingInfluenceDecision.NOT_ASSESSED
    )
    ranking_influence_label: str
    ranking_influence_reason: str
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
    user_facing_warnings: tuple[UserFacingTrustWarning, ...] = Field(
        default_factory=tuple,
    )
    last_checked_at: datetime | None = None
    decided_at: datetime | None = None
    next_recheck_at: datetime | None = None
    report_recheck_status: ReportRecheckStatus | None = None
    exception_status: ExceptionSubjectStatus | None = None
    explanation_version: Literal["30C"] = TRUST_EXPLANATION_VERSION

    @field_validator("last_checked_at", "decided_at", "next_recheck_at")
    @classmethod
    def _explanation_datetimes_must_be_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("trust explanation datetimes must be timezone-aware")
        return value


def safe_evidence_summary(result: TrustAssessmentResult) -> dict[str, int | str]:
    return {
        "trust_tier": result.trust_tier.value,
        "met_count": len(result.evidence_requirements_met),
        "missing_count": len(result.evidence_requirements_missing),
        "failed_count": len(result.evidence_requirements_failed),
        "warning_count": len(result.warnings),
    }
