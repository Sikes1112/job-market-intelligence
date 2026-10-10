"""Layer 40A product measurement API/service contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class ProductEventType(_Vocabulary):
    AUTHENTICATED_VISIT = "authenticated_visit"
    EXPLORE_CONTEXT_EVALUATED = "explore_context_evaluated"
    EXPLORE_FIT_GENERATED = "explore_fit_generated"
    EXPLORE_FIT_ABSTAINED = "explore_fit_abstained"
    EXPLORE_CONTEXT_UNSUPPORTED = "explore_context_unsupported"
    MARKET_INSPECTED = "market_inspected"
    COMPARISON_SELECTION_READY = "comparison_selection_ready"
    MY_SEARCH_VIEWED = "my_search_viewed"
    COMPARISON_GENERATED = "comparison_generated"
    COMPARISON_SAVED = "comparison_saved"
    PRIORITIZE_INITIATED = "prioritize_initiated"
    PRIORITIZE_COMPLETED = "prioritize_completed"
    COMPARISON_RECOMMENDATION_OVERRIDDEN = "comparison_recommendation_overridden"
    COMPARISON_RECOMMENDATION_VIEWED = "comparison_recommendation_viewed"
    COMPARISON_ABSTAINED_VIEWED = "comparison_abstained_viewed"
    RECOMMENDATION_GENERATED = "recommendation_generated"
    DECISION_CONSIDERED = "decision_considered"
    DECISION_SAVED = "decision_saved"
    RECOMMENDATION_CHANGED_DECISION = "recommendation_changed_decision"
    USER_ACTED = "user_acted"
    ACTION_SUCCEEDED = "action_succeeded"
    OUTCOME_RECORDED = "outcome_recorded"
    REFLECTION_RECORDED = "reflection_recorded"
    STRATEGY_CHANGED = "strategy_changed"
    ONBOARDING_STARTED = "onboarding_started"
    ONBOARDING_COMPLETED = "onboarding_completed"
    CAREER_IDENTITY_SUFFICIENT = "career_identity_sufficient"
    DECISION_CREATED = "decision_created"
    RECOMMENDATION_VIEWED = "recommendation_viewed"
    RECOMMENDATION_FEEDBACK_SUBMITTED = "recommendation_feedback_submitted"
    ACTION_CREATED = "action_created"
    APPLICATION_RECORDED = "application_recorded"
    OUTCOME_UPDATED = "outcome_updated"
    USER_RETURNED = "user_returned"
    COVERAGE_LIMITATION_VIEWED = "coverage_limitation_viewed"
    TRUST_EXPLANATION_VIEWED = "trust_explanation_viewed"
    COMMERCIAL_OFFER_EXPOSED = "commercial_offer_exposed"
    COMMERCIAL_OFFER_INTEREST_RECORDED = "commercial_offer_interest_recorded"
    COMMERCIAL_CONVERSION_RECORDED = "commercial_conversion_recorded"
    SUPPORT_CASE_CREATED = "support_case_created"
    SUPPORT_CASE_STATUS_CHANGED = "support_case_status_changed"


class ProductEventSource(_Vocabulary):
    BACKEND = "backend"
    FRONTEND = "frontend"
    ADMIN = "admin"
    SYSTEM = "system"


class CohortStatus(_Vocabulary):
    PLANNED = "planned"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class CohortMembershipStatus(_Vocabulary):
    INVITED = "invited"
    ACTIVE = "active"
    PAUSED = "paused"
    REMOVED = "removed"
    COMPLETED = "completed"


class FeatureAccessMode(_Vocabulary):
    CLOSED = "closed"
    OPEN = "open"
    BETA_ONLY = "beta_only"
    ENTITLEMENT_REQUIRED = "entitlement_required"


class ExperimentAssignmentStatus(_Vocabulary):
    ASSIGNED = "assigned"
    REMOVED = "removed"
    EXPIRED = "expired"


class ConfidenceCalibrationFeedback(_Vocabulary):
    TOO_HIGH = "too_high"
    TOO_LOW = "too_low"
    ABOUT_RIGHT = "about_right"
    UNSURE = "unsure"


class SameDecisionFeedback(_Vocabulary):
    YES = "yes"
    NO = "no"
    UNSURE = "unsure"
    NOT_APPLICABLE = "not_applicable"


class RegretLevel(_Vocabulary):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNSURE = "unsure"


class StrategyChangeType(_Vocabulary):
    TARGET_ROLE = "target_role"
    GEOGRAPHY = "geography"
    COMPANY_STRATEGY = "company_strategy"
    OPPORTUNITY_TYPE = "opportunity_type"
    APPLICATION_STRATEGY = "application_strategy"
    OTHER = "other"


class SupportCaseType(_Vocabulary):
    PRODUCT_ISSUE = "product_issue"
    BAD_DATA = "bad_data"
    RECOMMENDATION_ISSUE = "recommendation_issue"
    PRIVACY_ISSUE = "privacy_issue"
    ACCOUNT_ACCESS_ISSUE = "account_access_issue"
    BILLING_ISSUE = "billing_issue"
    OTHER = "other"


class SupportCaseStatus(_Vocabulary):
    OPEN = "open"
    INVESTIGATING = "investigating"
    AWAITING_USER = "awaiting_user"
    RESOLVED = "resolved"
    CLOSED = "closed"


class ProductEntitlementSource(_Vocabulary):
    BETA_ACCESS = "beta_access"
    FREE_ACCESS = "free_access"
    PROMOTIONAL_ACCESS = "promotional_access"
    PAID_PLAN = "paid_plan"
    INSTITUTIONAL_ACCESS = "institutional_access"
    ADVISOR_UNIVERSITY_ACCESS = "advisor_university_access"
    ADMINISTRATIVE_GRANT = "administrative_grant"


class CommercialOfferKey(_Vocabulary):
    ONE_TIME_DECISION_REPORT = "one_time_decision_report"
    ACTIVE_SEARCH_SUBSCRIPTION = "active_search_subscription"
    PREMIUM_SCENARIOS = "premium_scenarios"
    UNIVERSITY_ADVISOR_ACCESS = "university_advisor_access"


class CommercialSignalType(_Vocabulary):
    EXPOSED = "exposed"
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    LEARN_MORE = "learn_more"
    CONVERTED = "converted"
    ACTIVATED = "activated"
    CANCELED = "canceled"


SENSITIVE_EVENT_PAYLOAD_KEYS = frozenset(
    {
        "resume",
        "resume_text",
        "profile_text",
        "journal",
        "journal_text",
        "recommendation_text",
        "recommendation_narrative",
        "support_message",
        "application_materials",
        "cover_letter",
        "reflection_text",
        "private_note",
    }
)

EVENT_REQUIRED_REFS: dict[ProductEventType, frozenset[str]] = {
    ProductEventType.RECOMMENDATION_GENERATED: frozenset({"decision_id", "recommendation_id"}),
    ProductEventType.DECISION_CONSIDERED: frozenset({"decision_id"}),
    ProductEventType.DECISION_SAVED: frozenset({"decision_id"}),
    ProductEventType.RECOMMENDATION_CHANGED_DECISION: frozenset(
        {"decision_id", "recommendation_id"}
    ),
    ProductEventType.USER_ACTED: frozenset(),
    ProductEventType.ACTION_SUCCEEDED: frozenset({"action_id"}),
    ProductEventType.OUTCOME_RECORDED: frozenset({"outcome_id"}),
    ProductEventType.REFLECTION_RECORDED: frozenset({"decision_id"}),
    ProductEventType.STRATEGY_CHANGED: frozenset(),
    ProductEventType.CAREER_IDENTITY_SUFFICIENT: frozenset({"career_identity_id"}),
    ProductEventType.DECISION_CREATED: frozenset({"decision_id"}),
    ProductEventType.RECOMMENDATION_VIEWED: frozenset({"decision_id", "recommendation_id"}),
    ProductEventType.RECOMMENDATION_FEEDBACK_SUBMITTED: frozenset(
        {"decision_id", "recommendation_id"}
    ),
    ProductEventType.ACTION_CREATED: frozenset({"action_id"}),
    ProductEventType.APPLICATION_RECORDED: frozenset({"application_id"}),
    ProductEventType.OUTCOME_UPDATED: frozenset(),
    ProductEventType.COVERAGE_LIMITATION_VIEWED: frozenset({"coverage_status"}),
    ProductEventType.TRUST_EXPLANATION_VIEWED: frozenset(),
    ProductEventType.COMMERCIAL_OFFER_EXPOSED: frozenset({"experiment_key", "variant_key"}),
    ProductEventType.COMMERCIAL_OFFER_INTEREST_RECORDED: frozenset(
        {"experiment_key", "variant_key"}
    ),
    ProductEventType.COMMERCIAL_CONVERSION_RECORDED: frozenset({"experiment_key", "variant_key"}),
    ProductEventType.SUPPORT_CASE_CREATED: frozenset(),
    ProductEventType.SUPPORT_CASE_STATUS_CHANGED: frozenset(),
}


class ProductEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: ProductEventType
    event_source: ProductEventSource = ProductEventSource.BACKEND
    schema_version: int = Field(default=1, ge=1, le=10)
    occurred_at: datetime | None = None
    anonymous_session_id: str | None = Field(default=None, min_length=1, max_length=128)
    product_surface: str | None = Field(default=None, min_length=1, max_length=128)
    decision_id: str | None = Field(default=None, min_length=1, max_length=64)
    recommendation_id: str | None = Field(default=None, min_length=1, max_length=64)
    current_opportunity_id: str | None = Field(default=None, min_length=1, max_length=64)
    action_id: str | None = Field(default=None, min_length=1, max_length=64)
    application_id: str | None = Field(default=None, min_length=1, max_length=64)
    outcome_id: str | None = Field(default=None, min_length=1, max_length=64)
    career_identity_id: str | None = Field(default=None, min_length=1, max_length=64)
    career_identity_version: int | None = Field(default=None, ge=1)
    cohort_key: str | None = Field(default=None, min_length=1, max_length=64)
    experiment_key: str | None = Field(default=None, min_length=1, max_length=128)
    variant_key: str | None = Field(default=None, min_length=1, max_length=128)
    confidence_bucket: str | None = Field(default=None, min_length=1, max_length=32)
    coverage_status: str | None = Field(default=None, min_length=1, max_length=64)
    recommendation_state: str | None = Field(default=None, min_length=1, max_length=64)
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "anonymous_session_id",
        "product_surface",
        "decision_id",
        "recommendation_id",
        "current_opportunity_id",
        "action_id",
        "application_id",
        "outcome_id",
        "career_identity_id",
        "cohort_key",
        "experiment_key",
        "variant_key",
        "confidence_bucket",
        "coverage_status",
        "recommendation_state",
    )
    @classmethod
    def _clean_text(cls, value: str | None) -> str | None:
        return _clean_optional(value)

    @model_validator(mode="after")
    def _payload_is_canonical(self) -> Self:
        missing = [
            key
            for key in EVENT_REQUIRED_REFS.get(self.event_type, frozenset())
            if getattr(self, key) is None
        ]
        if missing:
            raise ValueError(f"{self.event_type.value} requires {', '.join(sorted(missing))}")
        if (
            self.event_type is ProductEventType.USER_ACTED
            and self.action_id is None
            and self.application_id is None
        ):
            raise ValueError("user_acted requires action_id or application_id")
        if (
            self.event_type is ProductEventType.OUTCOME_UPDATED
            and self.outcome_id is None
            and self.application_id is None
        ):
            raise ValueError("outcome_updated requires outcome_id or application_id")
        bad_keys = sorted(SENSITIVE_EVENT_PAYLOAD_KEYS & set(self.payload))
        if bad_keys:
            raise ValueError(f"analytics payload contains sensitive free-text keys: {bad_keys}")
        return self


class ProductEventView(ProductEventCreate):
    event_id: str
    user_id: str | None
    occurred_at: datetime
    created_at: datetime


class RecommendationFeedbackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str = Field(min_length=1, max_length=64)
    recommendation_id: str = Field(min_length=1, max_length=64)
    useful: bool
    surprising: bool
    changed_decision: bool
    missing_alternative: bool = False
    missing_alternative_category: str | None = Field(default=None, max_length=128)
    confidence_calibration: ConfidenceCalibrationFeedback
    feedback_comment: str | None = Field(default=None, max_length=2048)
    cohort_key: str | None = Field(default=None, max_length=64)
    experiment_key: str | None = Field(default=None, max_length=128)
    variant_key: str | None = Field(default=None, max_length=128)

    @field_validator(
        "decision_id",
        "recommendation_id",
        "missing_alternative_category",
        "feedback_comment",
        "cohort_key",
        "experiment_key",
        "variant_key",
    )
    @classmethod
    def _clean_text(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class RecommendationFeedbackView(RecommendationFeedbackCreate):
    feedback_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime


class DecisionReflectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str = Field(min_length=1, max_length=64)
    recommendation_id: str | None = Field(default=None, max_length=64)
    outcome_id: str | None = Field(default=None, max_length=64)
    would_make_same_decision: SameDecisionFeedback
    view_changed: bool = False
    satisfaction_rating: int | None = Field(default=None, ge=1, le=5)
    regret_level: RegretLevel | None = None
    reflection_comment: str | None = Field(default=None, max_length=2048)

    @field_validator("decision_id", "recommendation_id", "outcome_id", "reflection_comment")
    @classmethod
    def _clean_text(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class DecisionReflectionView(DecisionReflectionCreate):
    reflection_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime


class StrategyChangeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str | None = Field(default=None, max_length=64)
    recommendation_id: str | None = Field(default=None, max_length=64)
    change_type: StrategyChangeType
    previous_state: dict[str, Any] | None = None
    new_state: dict[str, Any] = Field(default_factory=dict)
    reason_category: str | None = Field(default=None, max_length=128)
    occurred_at: datetime | None = None
    note: str | None = Field(default=None, max_length=2048)

    @field_validator("decision_id", "recommendation_id", "reason_category", "note")
    @classmethod
    def _clean_text(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class StrategyChangeView(StrategyChangeCreate):
    strategy_change_id: str
    user_id: str
    occurred_at: datetime
    created_at: datetime
    updated_at: datetime


class CohortCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cohort_key: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    status: CohortStatus = CohortStatus.PLANNED
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    feature_flags: dict[str, Any] = Field(default_factory=dict)
    configuration: dict[str, Any] = Field(default_factory=dict)

    @field_validator("cohort_key", "name")
    @classmethod
    def _clean_text(cls, value: str) -> str:
        return _clean_required(value)


class CohortView(CohortCreate):
    cohort_id: str
    created_at: datetime
    updated_at: datetime


class CohortMembershipCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str = Field(min_length=1, max_length=64)
    cohort_key: str = Field(min_length=1, max_length=64)
    status: CohortMembershipStatus = CohortMembershipStatus.ACTIVE
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    configuration: dict[str, Any] = Field(default_factory=dict)

    @field_validator("user_id", "cohort_key")
    @classmethod
    def _clean_text(cls, value: str) -> str:
        return _clean_required(value)


class CohortMembershipView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    membership_id: str
    user_id: str
    cohort_id: str
    cohort_key: str
    status: CohortMembershipStatus
    assigned_by: str | None
    starts_at: datetime | None
    ends_at: datetime | None
    configuration: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class FeatureGateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    feature_key: str = Field(min_length=1, max_length=128)
    enabled: bool = False
    access_mode: FeatureAccessMode = FeatureAccessMode.CLOSED
    cohort_keys: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    entitlement_feature_key: str | None = Field(default=None, max_length=128)
    configuration: dict[str, Any] = Field(default_factory=dict)

    @field_validator("feature_key", "entitlement_feature_key")
    @classmethod
    def _clean_text(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class FeatureGateView(FeatureGateCreate):
    feature_gate_id: str
    created_at: datetime
    updated_at: datetime


class ExperimentAssignmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str = Field(min_length=1, max_length=64)
    experiment_key: str = Field(min_length=1, max_length=128)
    variant_key: str = Field(min_length=1, max_length=128)
    cohort_key: str | None = Field(default=None, max_length=64)
    assignment_basis: str = Field(default="manual", min_length=1, max_length=128)
    expires_at: datetime | None = None

    @field_validator("user_id", "experiment_key", "variant_key", "cohort_key", "assignment_basis")
    @classmethod
    def _clean_text(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class ExperimentAssignmentView(ExperimentAssignmentCreate):
    assignment_id: str
    status: ExperimentAssignmentStatus
    assigned_at: datetime
    created_at: datetime
    updated_at: datetime


class SupportCaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_type: SupportCaseType
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4096)
    subject_type: str | None = Field(default=None, max_length=64)
    subject_id: str | None = Field(default=None, max_length=128)
    decision_id: str | None = Field(default=None, max_length=64)
    recommendation_id: str | None = Field(default=None, max_length=64)
    current_opportunity_id: str | None = Field(default=None, max_length=64)
    privacy_request_type: str | None = Field(default=None, max_length=64)
    priority: str = Field(default="normal", min_length=1, max_length=32)

    @field_validator(
        "title",
        "description",
        "subject_type",
        "subject_id",
        "decision_id",
        "recommendation_id",
        "current_opportunity_id",
        "privacy_request_type",
        "priority",
    )
    @classmethod
    def _clean_text(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class SupportCaseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: SupportCaseStatus
    resolution: str | None = Field(default=None, max_length=4096)
    assigned_operator_id: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=2048)

    @field_validator("resolution", "assigned_operator_id", "note")
    @classmethod
    def _clean_text(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class SupportCaseView(SupportCaseCreate):
    support_case_id: str
    user_id: str
    status: SupportCaseStatus
    assigned_operator_id: str | None
    resolution: str | None
    resolved_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class EntitlementGrantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str = Field(min_length=1, max_length=64)
    feature_key: str = Field(min_length=1, max_length=128)
    source_type: ProductEntitlementSource
    source_ref_id: str | None = Field(default=None, max_length=128)
    effective_at: datetime | None = None
    expires_at: datetime | None = None
    reason: str = Field(min_length=1, max_length=512)

    @field_validator("user_id", "feature_key", "source_ref_id", "reason")
    @classmethod
    def _clean_text(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class EntitlementGrantView(EntitlementGrantCreate):
    entitlement_grant_id: str
    status: str
    created_at: datetime
    updated_at: datetime


class CommercialExperimentSignalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    experiment_key: str = Field(min_length=1, max_length=128)
    variant_key: str = Field(min_length=1, max_length=128)
    offer_key: CommercialOfferKey
    signal_type: CommercialSignalType
    product_surface: str | None = Field(default=None, max_length=128)
    conversion_ref: str | None = Field(default=None, max_length=128)
    qualitative_feedback: str | None = Field(default=None, max_length=2048)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "experiment_key",
        "variant_key",
        "product_surface",
        "conversion_ref",
        "qualitative_feedback",
    )
    @classmethod
    def _clean_text(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class CommercialExperimentSignalView(CommercialExperimentSignalCreate):
    signal_id: str
    user_id: str | None
    created_at: datetime
    updated_at: datetime


class FeatureAccessDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    feature_key: str
    allowed: bool
    reason: str
    cohort_keys: tuple[str, ...] = ()
    access_mode: FeatureAccessMode | None = None
    entitlement_source: str | None = None
    configuration: dict[str, Any] = Field(default_factory=dict)


class FunnelStageCount(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    stage: str
    user_count: int = Field(ge=0)
    event_count: int = Field(ge=0)
    conversion_from_previous: float | None = Field(default=None, ge=0.0, le=1.0)


class BetaAnalyticsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    generated_at: datetime
    cohort_key: str | None
    funnel: tuple[FunnelStageCount, ...]
    recommendation_feedback: dict[str, int]
    support_cases: dict[str, int]
    commercial_signals: dict[str, int]
    trust_exposures: dict[str, int]
    causal_limitation: str


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = " ".join(value.strip().split())
    return stripped or None


def _clean_required(value: str) -> str:
    cleaned = _clean_optional(value)
    if cleaned is None:
        raise ValueError("string fields must not be blank")
    return cleaned
