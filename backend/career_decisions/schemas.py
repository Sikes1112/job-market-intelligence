"""Layer 36A API and service contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class DecisionType(_Vocabulary):
    ROLE_CHOICE = "role_choice"
    COMPANY_CHOICE = "company_choice"
    LOCATION_CHOICE = "location_choice"
    CAREER_STRATEGY = "career_strategy"
    JOB_SEARCH_STRATEGY = "job_search_strategy"
    EDUCATION_SKILL_INVESTMENT = "education_skill_investment"
    OFFER_COMPARISON = "offer_comparison"
    CAREER_PATH = "career_path"


class DecisionStatus(_Vocabulary):
    DRAFT = "draft"
    EVALUATING = "evaluating"
    DECIDED = "decided"
    RECONSIDERING = "reconsidering"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class DecisionOptionStatus(_Vocabulary):
    ACTIVE = "active"
    SELECTED = "selected"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class DecisionRecommendationStatus(_Vocabulary):
    READY = "ready"
    ABSTAINED = "abstained"


class EvidenceSufficiency(_Vocabulary):
    COMPARISON_READY = "comparison_ready"
    LIMITED_EVIDENCE = "limited_evidence"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_SUPPORTED = "not_supported"


class EvidenceKind(_Vocabulary):
    DIRECT = "direct"
    PROXY = "proxy"
    CONTRARY = "contrary"
    UNAVAILABLE = "unavailable"
    WEAK = "weak"
    CONFLICTING = "conflicting"


class ConfidenceLevel(_Vocabulary):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class FitAssessment(_Vocabulary):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    MISALIGNED = "misaligned"
    UNKNOWN = "unknown"
    ABSTAIN = "abstain"


class ChallengeCode(_Vocabulary):
    HARD_CONSTRAINT_VIOLATION = "hard_constraint_violation"
    PREFERENCE_CONSTRAINT_CONFLICT = "preference_constraint_conflict"
    WEAK_COMPANY_EVIDENCE = "weak_company_evidence"
    INFERRED_IDENTITY_DEPENDENCY = "inferred_identity_dependency"
    PRIORITY_CONFLICT = "priority_conflict"
    INCOMPLETE_IDENTITY = "incomplete_identity"
    COMPENSATION_MINIMUM_VIOLATION = "compensation_minimum_violation"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class ActionPlanStatus(_Vocabulary):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class CareerActionType(_Vocabulary):
    RESEARCH = "research"
    APPLICATION = "application"
    SKILL_WORK = "skill_work"
    COMPANY_TARGETING = "company_targeting"
    NETWORKING_FOLLOW_UP = "networking_follow_up"
    PREPARATION = "preparation"
    TIMING_CHECKPOINT = "timing_checkpoint"
    REVIEW_TASK = "review_task"
    OTHER = "other"


class CareerActionStatus(_Vocabulary):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class ApplicationStatus(_Vocabulary):
    CONSIDERING = "considering"
    PREPARING = "preparing"
    APPLIED = "applied"
    RESPONSE = "response"
    INTERVIEW = "interview"
    FINAL_ROUND = "final_round"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    OFFER = "offer"
    ACCEPTED = "accepted"
    DECLINED = "declined"


class OutcomeType(_Vocabulary):
    APPLICATION_PROGRESS = "application_progress"
    OFFER = "offer"
    REJECTION = "rejection"
    WITHDRAWAL = "withdrawal"
    SKILL_DEVELOPMENT = "skill_development"
    RESEARCH_COMPLETED = "research_completed"
    NETWORKING = "networking"
    STRATEGY_CHANGE = "strategy_change"
    EDUCATION = "education"
    DECISION_COMPLETED = "decision_completed"
    OTHER = "other"


class OutcomeStatus(_Vocabulary):
    OBSERVED = "observed"
    REFLECTED = "reflected"
    SUPERSEDED = "superseded"


class DecisionPriorityInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(min_length=1, max_length=64)
    label: str | None = Field(default=None, min_length=1, max_length=255)
    weight: int | None = Field(default=None, ge=1, le=5)
    hard: bool = False

    @field_validator("key", "label")
    @classmethod
    def _clean_strings(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class DecisionConstraintInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(min_length=1, max_length=64)
    field: str = Field(min_length=1, max_length=64)
    operator: str = Field(default="equals", min_length=1, max_length=32)
    value: Any
    hard: bool = True
    label: str | None = Field(default=None, min_length=1, max_length=255)

    @field_validator("key", "field", "operator", "label")
    @classmethod
    def _clean_strings(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class DecisionOptionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=4096)
    scenario: dict[str, Any] = Field(default_factory=dict)
    position: int = Field(default=0, ge=0)

    @field_validator("title", "description")
    @classmethod
    def _clean_strings(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class DecisionCreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_type: DecisionType
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=10000)
    target_date: datetime | None = None
    planned_review_at: datetime | None = None
    time_horizon: str | None = Field(default=None, min_length=1, max_length=128)
    priorities: tuple[DecisionPriorityInput, ...] = Field(default_factory=tuple, max_length=25)
    constraints: tuple[DecisionConstraintInput, ...] = Field(default_factory=tuple, max_length=50)
    options: tuple[DecisionOptionInput, ...] = Field(default_factory=tuple, max_length=25)

    @field_validator("title", "description", "time_horizon")
    @classmethod
    def _clean_strings(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class DecisionUpdateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: DecisionStatus | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=10000)
    target_date: datetime | None = None
    planned_review_at: datetime | None = None
    time_horizon: str | None = Field(default=None, min_length=1, max_length=128)
    priorities: tuple[DecisionPriorityInput, ...] | None = Field(default=None, max_length=25)
    constraints: tuple[DecisionConstraintInput, ...] | None = Field(default=None, max_length=50)
    user_note: str | None = Field(default=None, min_length=1, max_length=10000)

    @field_validator("title", "description", "time_horizon", "user_note")
    @classmethod
    def _clean_strings(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class OptionSelectInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    option_id: str = Field(min_length=1, max_length=64)
    user_note: str | None = Field(default=None, min_length=1, max_length=10000)

    @field_validator("option_id", "user_note")
    @classmethod
    def _clean_strings(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class CareerActionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action_type: CareerActionType
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=4096)
    option_id: str | None = Field(default=None, min_length=1, max_length=64)
    due_at: datetime | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    position: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title", "description", "option_id")
    @classmethod
    def _clean_strings(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class ActionPlanCreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str | None = Field(default=None, min_length=1, max_length=255)
    actions: tuple[CareerActionInput, ...] = Field(default_factory=tuple, max_length=50)

    @field_validator("title")
    @classmethod
    def _clean_title(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class CareerActionUpdateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: CareerActionStatus | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=4096)
    due_at: datetime | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    metadata: dict[str, Any] | None = None

    @field_validator("title", "description")
    @classmethod
    def _clean_strings(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class ApplicationCreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str | None = Field(default=None, min_length=1, max_length=64)
    action_id: str | None = Field(default=None, min_length=1, max_length=64)
    option_id: str | None = Field(default=None, min_length=1, max_length=64)
    company_id: str | None = Field(default=None, min_length=1, max_length=64)
    region_id: str | None = Field(default=None, min_length=1, max_length=64)
    role_title: str | None = Field(default=None, min_length=1, max_length=255)
    status: ApplicationStatus = ApplicationStatus.CONSIDERING
    applied_at: datetime | None = None
    follow_up_at: datetime | None = None
    source_url: str | None = Field(default=None, min_length=1, max_length=1024)
    notes: str | None = Field(default=None, min_length=1, max_length=10000)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "decision_id",
        "action_id",
        "option_id",
        "company_id",
        "region_id",
        "role_title",
        "source_url",
        "notes",
    )
    @classmethod
    def _clean_strings(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class ApplicationTransitionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    to_status: ApplicationStatus
    reason: str | None = Field(default=None, min_length=1, max_length=4096)
    transitioned_at: datetime | None = None
    follow_up_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("reason")
    @classmethod
    def _clean_reason(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class OutcomeCreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome_type: OutcomeType
    title: str = Field(min_length=1, max_length=255)
    status: OutcomeStatus = OutcomeStatus.OBSERVED
    decision_id: str | None = Field(default=None, min_length=1, max_length=64)
    action_id: str | None = Field(default=None, min_length=1, max_length=64)
    application_id: str | None = Field(default=None, min_length=1, max_length=64)
    option_id: str | None = Field(default=None, min_length=1, max_length=64)
    recommendation_id: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = Field(default=None, min_length=1, max_length=10000)
    occurred_at: datetime | None = None
    reflection: str | None = Field(default=None, min_length=1, max_length=10000)
    evidence: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "title",
        "decision_id",
        "action_id",
        "application_id",
        "option_id",
        "recommendation_id",
        "description",
        "reflection",
    )
    @classmethod
    def _clean_strings(cls, value: str | None) -> str | None:
        return _clean_optional(value)

    @model_validator(mode="after")
    def _has_lifecycle_link(self) -> Self:
        if not any((self.decision_id, self.action_id, self.application_id)):
            raise ValueError("outcome requires decision_id, action_id, or application_id")
        return self


class DecisionContextView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    context_snapshot_id: str
    career_identity_id: str
    career_identity_version: int
    completeness_state: str
    sufficiency_state: str
    privacy_scope: str
    context: dict[str, Any]
    fact_refs: tuple[dict[str, Any], ...]
    created_at: datetime


class DecisionOptionView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    option_id: str
    decision_id: str
    title: str
    description: str | None
    scenario: dict[str, Any]
    status: DecisionOptionStatus
    position: int
    created_at: datetime
    updated_at: datetime


class DecisionRecommendationView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    recommendation_id: str
    decision_id: str
    context_snapshot_id: str
    recommended_option_id: str | None
    recommendation_status: DecisionRecommendationStatus
    evidence_sufficiency: EvidenceSufficiency
    confidence: ConfidenceLevel
    summary: str | None
    fit: dict[str, Any]
    comparison: dict[str, Any]
    evidence: dict[str, Any]
    challenges: tuple[dict[str, Any], ...]
    limitations: tuple[str, ...]
    generated_at: datetime


class DecisionVersionView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_version_id: str
    version_number: int
    version_reason: str
    selected_option_id: str | None
    context_snapshot_id: str | None
    decision_snapshot: dict[str, Any]
    options_snapshot: tuple[dict[str, Any], ...]
    recommendation_snapshot: dict[str, Any] | None
    user_note: str | None
    created_at: datetime


class CareerActionView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action_id: str
    action_plan_id: str | None
    decision_id: str | None
    option_id: str | None
    action_type: CareerActionType
    status: CareerActionStatus
    title: str
    description: str | None
    due_at: datetime | None
    priority: int | None
    position: int
    completed_at: datetime | None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ActionPlanView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action_plan_id: str
    decision_id: str
    selected_option_id: str | None
    title: str
    status: ActionPlanStatus
    plan: dict[str, Any]
    actions: tuple[CareerActionView, ...]
    created_at: datetime
    updated_at: datetime


class ApplicationTransitionView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    transition_id: str
    application_id: str
    from_status: ApplicationStatus | None
    to_status: ApplicationStatus
    reason: str | None
    metadata: dict[str, Any]
    transitioned_at: datetime


class ApplicationView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    application_id: str
    decision_id: str | None
    action_id: str | None
    option_id: str | None
    company_id: str | None
    region_id: str | None
    role_title: str | None
    status: ApplicationStatus
    status_started_at: datetime
    applied_at: datetime | None
    follow_up_at: datetime | None
    source_url: str | None
    notes: str | None
    metadata: dict[str, Any]
    transitions: tuple[ApplicationTransitionView, ...] = ()
    created_at: datetime
    updated_at: datetime


class OutcomeView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome_id: str
    decision_id: str | None
    action_id: str | None
    application_id: str | None
    option_id: str | None
    recommendation_id: str | None
    outcome_type: OutcomeType
    status: OutcomeStatus
    title: str
    description: str | None
    occurred_at: datetime
    reflection: str | None
    evidence: dict[str, Any]
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class DecisionView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str
    decision_type: DecisionType
    status: DecisionStatus
    title: str
    description: str | None
    decision_date: datetime | None
    target_date: datetime | None
    planned_review_at: datetime | None
    time_horizon: str | None
    priorities: tuple[dict[str, Any], ...]
    constraints: tuple[dict[str, Any], ...]
    selected_option_id: str | None
    career_identity_id: str | None
    current_context_snapshot_id: str | None
    current_recommendation_id: str | None
    current_version: int
    context: DecisionContextView | None
    options: tuple[DecisionOptionView, ...]
    recommendation: DecisionRecommendationView | None
    action_plan: ActionPlanView | None = None
    applications: tuple[ApplicationView, ...] = ()
    outcomes: tuple[OutcomeView, ...] = ()
    created_at: datetime
    updated_at: datetime


class WeeklyReviewView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    window_start: datetime
    window_end: datetime
    happened: tuple[dict[str, Any], ...]
    changed: tuple[dict[str, Any], ...]
    worked: tuple[dict[str, Any], ...]
    did_not_work: tuple[dict[str, Any], ...]
    stalled: tuple[dict[str, Any], ...]
    invalidated_assumptions: tuple[dict[str, Any], ...]
    reconsider: tuple[dict[str, Any], ...]
    next_actions: tuple[dict[str, Any], ...]
    reminders: tuple[dict[str, Any], ...]


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        raise ValueError("string fields must not be blank")
    return cleaned
