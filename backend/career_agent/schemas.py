"""Layer 26A grounded career-agent contracts.

The career agent is a representation layer over structured platform data. It
may rank, summarize, and personalize using request-scoped preferences, but it
must not treat preferences as external evidence or invent opportunity records.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.shared.confidence import Confidence

PRIVATE_OR_UNSAFE_TOKENS = (
    "internal_review_notes",
    "internal review",
    "review_notes",
    "admin_metadata",
    "private_metadata",
    "raw_source",
    "raw scrape",
    "raw_source_refs",
    "raw_scrape_records",
    "source_refs",
    "fact_source_link_id",
    "internal_formula_weights",
)

CERTAINTY_TOKENS = (
    "guaranteed",
    "guarantee",
    "will happen",
)

CAREER_PLAN_FABRICATION_TOKENS = (
    "application deadline:",
    "application_deadline",
    "hiring probability",
    "recruiter contact",
    "recruiter_contacts",
    "guaranteed outcome",
)

TOOL_ACTION_UNSAFE_TOKENS = (
    "resume submitted",
    "application submitted",
    "applied on your behalf",
    "contacted employer",
    "outreach sent",
    "profile shared",
    "scheduled reminder",
    "notification enabled",
    "watchlist updated",
)


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class CareerAgentQuestionType(_Vocabulary):
    WHERE_SHOULD_I_APPLY = "where_should_i_apply"
    CITY_FIT = "city_fit"
    COMPANIES_TO_WATCH = "companies_to_watch"
    STRONGEST_MARKET_STRATEGY = "strongest_market_strategy"
    WHAT_SHOULD_I_DO_THIS_MONTH = "what_should_i_do_this_month"


class CareerAgentEvidenceType(_Vocabulary):
    REGION = "region"
    REGION_SCORE = "region_score"
    COMPANY = "company"
    PRESENCE = "presence"
    HIRING = "hiring"
    ENTRY_LEVEL = "entry_level"
    OPPORTUNITY = "opportunity"
    FORECAST = "forecast"
    MARKET = "market"


class CareerAgentFreshnessStatus(_Vocabulary):
    FRESH = "fresh"
    STALE = "stale"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    SEEDED_DEMO = "seeded_demo"


class CareerAgentTargetType(_Vocabulary):
    REGION = "region"
    COMPANY = "company"
    OPPORTUNITY = "opportunity"
    MARKET_STRATEGY = "market_strategy"
    MONTHLY_ACTION = "monthly_action"


class CareerAgentPreferenceSnapshot(BaseModel):
    """Request-scoped preferences used only for personalization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    preferred_region_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=25)
    preferred_company_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=25)
    preferred_role_families: tuple[str, ...] = Field(default_factory=tuple, max_length=25)
    preferred_location_modes: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    preferred_program_types: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    constraints: tuple[str, ...] = Field(default_factory=tuple, max_length=25)
    preference_context: str | None = Field(default=None, min_length=1, max_length=1024)
    counts_as_evidence: Literal[False] = False

    @field_validator(
        "preferred_region_ids",
        "preferred_company_ids",
        "preferred_role_families",
        "preferred_location_modes",
        "preferred_program_types",
        "constraints",
        mode="before",
    )
    @classmethod
    def _string_tuple_values_not_blank(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, str):
            values = (value,)
        else:
            values = value
        if not isinstance(values, tuple | list):
            return values
        return tuple(_clean_text(str(item), label="preference") for item in values)

    @field_validator("preference_context")
    @classmethod
    def _preference_context_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_public_text(value, label="preference_context")


class CareerAgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    question_type: CareerAgentQuestionType
    user_goal: str | None = Field(default=None, min_length=1, max_length=2048)
    target_region_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=25)
    target_company_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=25)
    target_role_families: tuple[str, ...] = Field(default_factory=tuple, max_length=25)
    preferred_program_types: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    preferred_location_modes: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    skills: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    background_tags: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    include_forecasts: bool = True
    limit: int = Field(default=5, ge=1, le=10)
    preference_snapshot: CareerAgentPreferenceSnapshot | None = None

    @field_validator("user_goal")
    @classmethod
    def _goal_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_public_text(value, label="user_goal")

    @field_validator(
        "target_region_ids",
        "target_company_ids",
        "target_role_families",
        "preferred_program_types",
        "preferred_location_modes",
        "skills",
        "background_tags",
        mode="before",
    )
    @classmethod
    def _tuple_values_not_blank(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, str):
            values = (value,)
        else:
            values = value
        if not isinstance(values, tuple | list):
            return values
        return tuple(_clean_text(str(item), label="request value") for item in values)


class CareerAgentFreshness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    freshness_status: CareerAgentFreshnessStatus = CareerAgentFreshnessStatus.UNKNOWN
    data_basis: str = Field(default="unknown", min_length=1, max_length=128)
    last_updated_at: datetime | None = None
    freshness_expires_at: datetime | date | None = None
    source_count: int = Field(default=0, ge=0)
    warnings: tuple[str, ...] = Field(default_factory=tuple, max_length=25)

    @field_validator("data_basis")
    @classmethod
    def _data_basis_not_blank(cls, value: str) -> str:
        return _clean_text(value, label="data_basis")

    @field_validator("warnings")
    @classmethod
    def _warnings_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_public_text(item, label="freshness warning") for item in value)


class CareerAgentUncertainty(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    confidence_level: Confidence = Confidence.UNKNOWN
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    uncertainty_level: Literal["low", "medium", "high"] = "high"
    reasons: tuple[str, ...] = Field(default_factory=tuple, max_length=25)
    limitations: tuple[str, ...] = Field(default_factory=tuple, max_length=25)
    forecast_based: bool = False
    bounded: bool = True

    @field_validator("reasons", "limitations")
    @classmethod
    def _uncertainty_text_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_public_text(item, label="uncertainty text") for item in value)


class CareerAgentEvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ref_id: str = Field(min_length=1, max_length=160)
    evidence_type: CareerAgentEvidenceType
    entity_type: str = Field(min_length=1, max_length=64)
    entity_id: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=255)
    summary: str = Field(min_length=1, max_length=1024)
    data_basis: str = Field(min_length=1, max_length=128)
    freshness_status: CareerAgentFreshnessStatus = CareerAgentFreshnessStatus.UNKNOWN
    confidence_label: str | None = Field(default=None, min_length=1, max_length=64)
    source_count: int = Field(default=0, ge=0)
    observed_at: datetime | date | None = None
    public_url: str | None = Field(default=None, min_length=1, max_length=2048)

    @field_validator(
        "ref_id",
        "entity_type",
        "entity_id",
        "label",
        "summary",
        "data_basis",
        "confidence_label",
        "public_url",
    )
    @classmethod
    def _strings_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_public_text(value, label="evidence")

    @model_validator(mode="after")
    def _preferences_are_not_evidence(self) -> Self:
        if "preference" in self.data_basis.casefold():
            raise ValueError("user preferences cannot be evidence refs")
        return self


class CareerAgentRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    recommendation_id: str = Field(min_length=1, max_length=160)
    recommendation_type: str = Field(min_length=1, max_length=64)
    rank: int = Field(ge=1)
    target_type: CareerAgentTargetType
    target_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(min_length=1, max_length=2048)
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    action: str | None = Field(default=None, min_length=1, max_length=1024)
    evidence_refs: tuple[CareerAgentEvidenceRef, ...] = Field(min_length=1, max_length=20)
    freshness: CareerAgentFreshness
    uncertainty: CareerAgentUncertainty
    preference_alignment: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    matched_opportunity_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    warnings: tuple[str, ...] = Field(default_factory=tuple, max_length=25)
    limitations: tuple[str, ...] = Field(default_factory=tuple, max_length=25)

    @field_validator(
        "recommendation_id",
        "recommendation_type",
        "target_id",
        "title",
        "summary",
        "action",
    )
    @classmethod
    def _recommendation_strings_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_public_text(value, label="recommendation")

    @field_validator("preference_alignment", "matched_opportunity_ids", "warnings", "limitations")
    @classmethod
    def _tuple_strings_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_public_text(item, label="recommendation tuple") for item in value)


class CareerAgentGuardrailStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    passed: bool
    evidence_requirement_met: bool
    fabricated_openings_blocked: bool = True
    preferences_excluded_from_evidence: bool = True
    forecast_claims_bounded: bool = True
    private_fields_redacted: bool = True
    blocked_reasons: tuple[str, ...] = Field(default_factory=tuple, max_length=25)
    warnings: tuple[str, ...] = Field(default_factory=tuple, max_length=25)

    @field_validator("blocked_reasons", "warnings")
    @classmethod
    def _guardrail_text_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_public_text(item, label="guardrail text") for item in value)


class CareerAgentAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    answer_id: str = Field(min_length=1, max_length=160)
    question_type: CareerAgentQuestionType
    generated_at: datetime
    summary: str = Field(min_length=1, max_length=2048)
    recommendations: tuple[CareerAgentRecommendation, ...] = Field(
        default_factory=tuple,
        max_length=10,
    )
    freshness: CareerAgentFreshness
    source_freshness: tuple[CareerAgentFreshness, ...] = Field(min_length=1, max_length=50)
    uncertainty: CareerAgentUncertainty
    preference_snapshot: CareerAgentPreferenceSnapshot | None = None
    guardrails: CareerAgentGuardrailStatus
    limitations: tuple[str, ...] = Field(default_factory=tuple, max_length=25)

    @field_validator("summary")
    @classmethod
    def _summary_safe(cls, value: str) -> str:
        return _safe_public_text(value, label="answer summary")

    @field_validator("limitations")
    @classmethod
    def _limitations_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_public_text(item, label="answer limitation") for item in value)


class CareerAgentGuardrailViolation(ValueError):
    """Raised when an answer violates the Layer 26A evidence contract."""


def validate_career_agent_answer(answer: CareerAgentAnswer) -> None:
    """Reject unsupported recommendations and unsafe payloads."""

    problems: list[str] = []
    dumped = answer.model_dump(mode="json")
    serialized = json.dumps(dumped, sort_keys=True).casefold()

    for token in PRIVATE_OR_UNSAFE_TOKENS:
        if token in serialized:
            problems.append(f"unsafe private/internal token leaked: {token}")
    for token in CERTAINTY_TOKENS:
        if token in serialized:
            problems.append(f"certainty language is not allowed: {token}")

    for recommendation in answer.recommendations:
        if not recommendation.evidence_refs:
            problems.append(
                f"recommendation {recommendation.recommendation_id} has no evidence refs"
            )
            continue

        opportunity_evidence_ids = {
            ref.entity_id
            for ref in recommendation.evidence_refs
            if ref.evidence_type is CareerAgentEvidenceType.OPPORTUNITY
        }
        if recommendation.target_type is CareerAgentTargetType.OPPORTUNITY:
            if recommendation.target_id not in opportunity_evidence_ids:
                problems.append(
                    f"opportunity recommendation {recommendation.recommendation_id} "
                    "is missing matching opportunity evidence"
                )
        for opportunity_id in recommendation.matched_opportunity_ids:
            if opportunity_id not in opportunity_evidence_ids:
                problems.append(
                    f"matched opportunity {opportunity_id} lacks opportunity evidence"
                )

        has_forecast_evidence = any(
            ref.evidence_type is CareerAgentEvidenceType.FORECAST
            for ref in recommendation.evidence_refs
        )
        if has_forecast_evidence or recommendation.uncertainty.forecast_based:
            if not recommendation.uncertainty.bounded:
                problems.append(
                    f"forecast recommendation {recommendation.recommendation_id} "
                    "must be bounded"
                )
            warning_text = " ".join(
                (*recommendation.warnings, *recommendation.limitations)
            ).casefold()
            if "forecast" not in warning_text or not (
                "not a certain outcome" in warning_text
                or "bounded directional signal" in warning_text
            ):
                problems.append(
                    f"forecast recommendation {recommendation.recommendation_id} "
                    "must warn that forecasts are bounded and uncertain"
                )

    evidence_refs = [
        ref
        for recommendation in answer.recommendations
        for ref in recommendation.evidence_refs
    ]
    if any("preference" in ref.data_basis.casefold() for ref in evidence_refs):
        problems.append("user preferences were treated as source evidence")

    if problems:
        raise CareerAgentGuardrailViolation("; ".join(problems))


def _clean_text(value: str, *, label: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{label} must not be blank")
    return stripped


def _safe_public_text(value: str, *, label: str) -> str:
    stripped = _clean_text(value, label=label)
    lowered = stripped.casefold()
    for token in PRIVATE_OR_UNSAFE_TOKENS:
        if token in lowered:
            raise ValueError(f"{label} contains unsafe private/internal metadata")
    for token in CERTAINTY_TOKENS:
        if token in lowered:
            raise ValueError(f"{label} contains unsupported certainty language")
    return stripped


class CareerPlanType(_Vocabulary):
    WEEKLY_JOB_SEARCH_PLAN = "weekly_job_search_plan"
    REGIONAL_TARGETING_PLAN = "regional_targeting_plan"
    COMPANY_RESEARCH_PLAN = "company_research_plan"
    INTERNSHIP_APPLICATION_CALENDAR = "internship_application_calendar"
    NETWORKING_PLAN = "networking_plan"


class CareerPlanUserActionRequirement(_Vocabulary):
    USER_ACTION_REQUIRED = "user_action_required"
    SYSTEM_SUGGESTED = "system_suggested"


class CareerPlanTimeWindow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str = Field(min_length=1, max_length=128)
    start_date: date
    end_date: date

    @field_validator("label")
    @classmethod
    def _label_safe(cls, value: str) -> str:
        return _safe_career_plan_text(value, label="plan time window")

    @model_validator(mode="after")
    def _end_after_start(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("plan end_date must be on or after start_date")
        return self


class CareerPlanMilestone(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    milestone_id: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=512)
    outcome: str = Field(min_length=1, max_length=512)
    target_date: date | None = None

    @field_validator("milestone_id", "summary", "outcome")
    @classmethod
    def _strings_safe(cls, value: str) -> str:
        return _safe_career_plan_text(value, label="plan milestone")


class CareerPlanRisk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    risk_id: str = Field(min_length=1, max_length=160)
    severity: Literal["low", "medium", "high"] = "medium"
    summary: str = Field(min_length=1, max_length=512)
    mitigation: str = Field(min_length=1, max_length=512)
    evidence_refs: tuple[CareerAgentEvidenceRef, ...] = Field(
        default_factory=tuple,
        max_length=10,
    )

    @field_validator("risk_id", "summary", "mitigation")
    @classmethod
    def _strings_safe(cls, value: str) -> str:
        return _safe_career_plan_text(value, label="plan risk")


class CareerPlanEvidenceBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    binding_id: str = Field(min_length=1, max_length=160)
    step_id: str = Field(min_length=1, max_length=160)
    binding_type: Literal["strategic_basis", "verification_basis"] = "strategic_basis"
    evidence_refs: tuple[CareerAgentEvidenceRef, ...] = Field(min_length=1, max_length=20)
    note: str = Field(min_length=1, max_length=512)

    @field_validator("binding_id", "step_id", "note")
    @classmethod
    def _strings_safe(cls, value: str) -> str:
        return _safe_career_plan_text(value, label="plan evidence binding")


class CareerPlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    step_id: str = Field(min_length=1, max_length=160)
    rank: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=2048)
    action_owner: CareerPlanUserActionRequirement
    strategic: bool = True
    milestone: CareerPlanMilestone
    evidence_refs: tuple[CareerAgentEvidenceRef, ...] = Field(
        default_factory=tuple,
        max_length=20,
    )
    evidence_bindings: tuple[CareerPlanEvidenceBinding, ...] = Field(
        default_factory=tuple,
        max_length=10,
    )
    freshness: CareerAgentFreshness
    uncertainty: CareerAgentUncertainty
    risks: tuple[CareerPlanRisk, ...] = Field(default_factory=tuple, max_length=10)
    matched_opportunity_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    warnings: tuple[str, ...] = Field(default_factory=tuple, max_length=25)

    @field_validator("step_id", "title", "description")
    @classmethod
    def _strings_safe(cls, value: str) -> str:
        return _safe_career_plan_text(value, label="plan step")

    @field_validator("matched_opportunity_ids", "warnings")
    @classmethod
    def _tuple_strings_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_career_plan_text(item, label="plan step tuple") for item in value)


class CareerActionPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plan_type: CareerPlanType
    career_agent_request: CareerAgentRequest
    career_goal: str | None = Field(default=None, min_length=1, max_length=2048)
    time_window: CareerPlanTimeWindow | None = None
    include_memory: bool = False
    limit: int = Field(default=5, ge=1, le=10)

    @field_validator("career_goal")
    @classmethod
    def _career_goal_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_career_plan_text(value, label="career_goal")


class CareerActionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plan_id: str = Field(min_length=1, max_length=160)
    plan_type: CareerPlanType
    generated_at: datetime
    source_answer_id: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=2048)
    career_goal: str | None = Field(default=None, min_length=1, max_length=2048)
    time_window: CareerPlanTimeWindow
    steps: tuple[CareerPlanStep, ...] = Field(min_length=1, max_length=20)
    evidence_refs: tuple[CareerAgentEvidenceRef, ...] = Field(min_length=1, max_length=50)
    freshness: CareerAgentFreshness
    source_freshness: tuple[CareerAgentFreshness, ...] = Field(min_length=1, max_length=50)
    uncertainty: CareerAgentUncertainty
    risks: tuple[CareerPlanRisk, ...] = Field(default_factory=tuple, max_length=25)
    warnings: tuple[str, ...] = Field(default_factory=tuple, max_length=25)
    limitations: tuple[str, ...] = Field(default_factory=tuple, max_length=25)
    memory_personalization: tuple[str, ...] = Field(default_factory=tuple, max_length=25)
    guardrails: CareerAgentGuardrailStatus

    @field_validator("plan_id", "source_answer_id", "summary", "career_goal")
    @classmethod
    def _strings_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_career_plan_text(value, label="action plan")

    @field_validator("warnings", "limitations", "memory_personalization")
    @classmethod
    def _tuple_strings_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_career_plan_text(item, label="action plan tuple") for item in value)


class CareerMemoryCategory(_Vocabulary):
    SAVED_COMPANIES = "saved_companies"
    TARGET_REGIONS = "target_regions"
    APPLIED_ROLES = "applied_roles"
    PREFERRED_INDUSTRIES = "preferred_industries"
    REJECTED_MARKETS = "rejected_markets"
    CAREER_CONSTRAINTS = "career_constraints"
    PREFERRED_ROLE_TYPES = "preferred_role_types"


class CareerMemoryVisibility(_Vocabulary):
    PRIVATE = "private"


class CareerMemoryPermission(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    category: CareerMemoryCategory
    enabled: bool = False
    personalize_allowed: bool = False
    visibility: CareerMemoryVisibility = CareerMemoryVisibility.PRIVATE

    @model_validator(mode="after")
    def _personalization_requires_enabled(self) -> Self:
        if self.personalize_allowed and not self.enabled:
            raise ValueError("memory personalization requires enabled memory permission")
        return self


class CareerMemoryEntryInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    category: CareerMemoryCategory
    value: str = Field(min_length=1, max_length=255)
    label: str | None = Field(default=None, min_length=1, max_length=255)
    notes: str | None = Field(default=None, min_length=1, max_length=2048)

    @field_validator("value", "label", "notes")
    @classmethod
    def _strings_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_public_text(value, label="career memory")


class CareerMemoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    memory_entry_id: str = Field(min_length=1, max_length=160)
    category: CareerMemoryCategory
    value: str = Field(min_length=1, max_length=255)
    label: str | None = Field(default=None, min_length=1, max_length=255)
    notes: str | None = Field(default=None, min_length=1, max_length=2048)
    visibility: CareerMemoryVisibility = CareerMemoryVisibility.PRIVATE
    source: Literal["user_provided"] = "user_provided"
    counts_as_evidence: Literal[False] = False
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("memory_entry_id", "value", "label", "notes")
    @classmethod
    def _strings_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_public_text(value, label="career memory")


class CareerMemoryAuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: Literal[
        "permission_updated",
        "entry_saved",
        "entry_deleted",
        "memory_cleared",
    ]
    category: CareerMemoryCategory | None = None
    memory_entry_id: str | None = Field(default=None, min_length=1, max_length=160)
    occurred_at: datetime
    summary: str = Field(min_length=1, max_length=512)

    @field_validator("memory_entry_id", "summary")
    @classmethod
    def _strings_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_public_text(value, label="career memory audit")


class CareerMemoryProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str = Field(min_length=1, max_length=64)
    memory_enabled: bool = False
    permissions: tuple[CareerMemoryPermission, ...]
    entries: tuple[CareerMemoryEntry, ...] = Field(default_factory=tuple, max_length=500)
    entries_by_category: dict[str, tuple[CareerMemoryEntry, ...]] = Field(
        default_factory=dict
    )
    audit_events: tuple[CareerMemoryAuditEvent, ...] = Field(default_factory=tuple)

    @field_validator("user_id")
    @classmethod
    def _user_id_safe(cls, value: str) -> str:
        return _safe_public_text(value, label="career memory profile")


class CareerMemoryUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    explicit_user_permission: bool = False
    permissions: tuple[CareerMemoryPermission, ...] = Field(default_factory=tuple)
    entries: tuple[CareerMemoryEntryInput, ...] = Field(default_factory=tuple)
    replace_categories: tuple[CareerMemoryCategory, ...] = Field(default_factory=tuple)


class CareerMemoryDeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    clear_all: bool = False
    categories: tuple[CareerMemoryCategory, ...] = Field(default_factory=tuple)
    memory_entry_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=100)
    disable_permissions: bool = True

    @field_validator("memory_entry_ids")
    @classmethod
    def _ids_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_public_text(item, label="career memory delete") for item in value)


class CareerAgentToolType(_Vocabulary):
    REMINDER = "reminder"
    CAREER_REPORT_EXPORT = "career_report_export"
    WATCHLIST_UPDATE_SUGGESTION = "watchlist_update_suggestion"
    NOTIFICATION_PREFERENCE = "notification_preference"
    OUTREACH_DRAFT = "outreach_message_draft"
    APPLICATION_PREP_CHECKLIST = "application_prep_checklist"
    JOB_APPLICATION_SUBMISSION = "job_application_submission"


class CareerAgentToolStatus(_Vocabulary):
    SUGGESTED = "suggested"
    DRAFTED = "drafted"
    PREVIEW_READY = "preview_ready"
    AWAITING_USER_APPROVAL = "awaiting_user_approval"
    APPROVED = "approved"
    EXECUTED = "executed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    BLOCKED = "blocked"


class CareerAgentActionBoundary(_Vocabulary):
    READ_ONLY_PREVIEW = "read_only_preview"
    USER_STATE_CHANGE = "user_state_change"
    REMINDER_CREATION = "reminder_creation"
    USER_DATA_EXPORT = "user_data_export"
    WATCHLIST_MUTATION = "watchlist_mutation"
    NOTIFICATION_CHANGE = "notification_change"
    EXTERNAL_CONTACT = "external_contact"
    APPLICATION_SUBMISSION = "application_submission"


class CareerAgentToolPrivacy(_Vocabulary):
    PUBLIC_SAFE = "public_safe"
    USER_PRIVATE = "user_private"
    EXTERNAL_CONTACT = "external_contact"
    BLOCKED = "blocked"


class CareerAgentRequestedToolAction(_Vocabulary):
    PREVIEW = "preview"
    DRAFT = "draft"
    APPROVAL_ONLY = "approval_only"
    SEND = "send"
    SUBMIT_APPLICATION = "submit_application"


class CareerAgentApprovalRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    approval_required: bool
    explicit_user_approval_required: bool
    reason: str = Field(min_length=1, max_length=1024)
    boundary: CareerAgentActionBoundary
    approval_button_label: str | None = Field(default=None, min_length=1, max_length=128)
    runtime_execution_available: bool = False

    @field_validator("reason", "approval_button_label")
    @classmethod
    def _strings_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_tool_text(value, label="tool approval requirement")

    @model_validator(mode="after")
    def _runtime_requires_approval(self) -> Self:
        if self.runtime_execution_available and not self.approval_required:
            raise ValueError("runtime tool execution must require approval")
        return self


class CareerAgentToolAuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: Literal[
        "preview_created",
        "approval_recorded",
        "rejection_recorded",
        "blocked",
    ]
    occurred_at: datetime
    summary: str = Field(min_length=1, max_length=512)

    @field_validator("summary")
    @classmethod
    def _summary_safe(cls, value: str) -> str:
        return _safe_tool_text(value, label="tool audit event")


class CareerAgentToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_type: CareerAgentToolType
    career_agent_request: CareerAgentRequest | None = None
    action_plan_request: CareerActionPlanRequest | None = None
    requested_action: CareerAgentRequestedToolAction = CareerAgentRequestedToolAction.PREVIEW
    include_memory: bool = False
    include_private_memory_in_export: bool = False
    target_opportunity_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    user_context_claims: tuple[str, ...] = Field(default_factory=tuple, max_length=20)
    draft_recipient_role: str | None = Field(default=None, min_length=1, max_length=128)
    limit: int = Field(default=5, ge=1, le=10)

    @field_validator("target_opportunity_ids", "user_context_claims")
    @classmethod
    def _tuple_strings_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_tool_text(item, label="tool request") for item in value)

    @field_validator("draft_recipient_role")
    @classmethod
    def _draft_recipient_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_tool_text(value, label="draft_recipient_role")

    @model_validator(mode="after")
    def _grounding_required(self) -> Self:
        if self.career_agent_request is None and self.action_plan_request is None:
            raise ValueError("tool requests require a career_agent_request or action_plan_request")
        return self


class CareerAgentToolPreview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_request_id: str = Field(min_length=1, max_length=160)
    tool_type: CareerAgentToolType
    proposed_action_summary: str = Field(min_length=1, max_length=2048)
    user_visible_preview: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: tuple[CareerAgentEvidenceRef, ...] = Field(
        default_factory=tuple,
        max_length=50,
    )
    freshness: CareerAgentFreshness
    uncertainty: CareerAgentUncertainty
    warnings: tuple[str, ...] = Field(default_factory=tuple, max_length=25)
    approval_requirement: CareerAgentApprovalRequirement
    action_boundary: CareerAgentActionBoundary
    status: CareerAgentToolStatus
    privacy_classification: CareerAgentToolPrivacy
    source_answer_id: str | None = Field(default=None, min_length=1, max_length=160)
    source_plan_id: str | None = Field(default=None, min_length=1, max_length=160)
    user_id: str | None = Field(default=None, min_length=1, max_length=64)
    runtime_execution_performed: bool = False
    created_at: datetime
    updated_at: datetime
    audit_events: tuple[CareerAgentToolAuditEvent, ...] = Field(default_factory=tuple)

    @field_validator(
        "tool_request_id",
        "proposed_action_summary",
        "source_answer_id",
        "source_plan_id",
        "user_id",
    )
    @classmethod
    def _strings_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_tool_text(value, label="tool preview")

    @field_validator("warnings")
    @classmethod
    def _warnings_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_tool_text(item, label="tool warning") for item in value)

    @model_validator(mode="after")
    def _approval_boundary_matches_action_boundary(self) -> Self:
        if self.approval_requirement.boundary is not self.action_boundary:
            raise ValueError("tool approval boundary must match action boundary")
        return self


class CareerAgentToolApproval(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_request_id: str = Field(min_length=1, max_length=160)
    explicit_user_approval: bool = False
    approval_note: str | None = Field(default=None, min_length=1, max_length=512)

    @field_validator("tool_request_id", "approval_note")
    @classmethod
    def _strings_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_tool_text(value, label="tool approval")


class CareerAgentToolExecution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_request_id: str = Field(min_length=1, max_length=160)
    status: CareerAgentToolStatus
    runtime_execution_performed: bool = False
    executed_at: datetime | None = None
    summary: str = Field(min_length=1, max_length=1024)
    warnings: tuple[str, ...] = Field(default_factory=tuple, max_length=25)
    tool_preview: CareerAgentToolPreview

    @field_validator("tool_request_id", "summary")
    @classmethod
    def _strings_safe(cls, value: str) -> str:
        return _safe_tool_text(value, label="tool execution")

    @field_validator("warnings")
    @classmethod
    def _warnings_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_tool_text(item, label="tool execution warning") for item in value)


def validate_career_agent_tool_preview(preview: CareerAgentToolPreview) -> None:
    problems: list[str] = []
    dumped = preview.model_dump(mode="json")
    serialized = json.dumps(dumped, sort_keys=True).casefold()

    for token in PRIVATE_OR_UNSAFE_TOKENS:
        if token in serialized:
            problems.append(f"unsafe private/internal token leaked: {token}")
    for token in CERTAINTY_TOKENS:
        if token in serialized:
            problems.append(f"certainty language is not allowed: {token}")
    for token in TOOL_ACTION_UNSAFE_TOKENS:
        if token in serialized and preview.runtime_execution_performed is False:
            problems.append(f"tool preview falsely claims execution: {token}")

    approval_required_boundaries = {
        CareerAgentActionBoundary.USER_STATE_CHANGE,
        CareerAgentActionBoundary.REMINDER_CREATION,
        CareerAgentActionBoundary.USER_DATA_EXPORT,
        CareerAgentActionBoundary.WATCHLIST_MUTATION,
        CareerAgentActionBoundary.NOTIFICATION_CHANGE,
        CareerAgentActionBoundary.EXTERNAL_CONTACT,
        CareerAgentActionBoundary.APPLICATION_SUBMISSION,
    }
    if preview.action_boundary in approval_required_boundaries:
        if not preview.approval_requirement.approval_required:
            problems.append("high-impact tool action does not require approval")
        if not preview.approval_requirement.explicit_user_approval_required:
            problems.append("high-impact tool action does not require explicit approval")
    if preview.action_boundary is CareerAgentActionBoundary.APPLICATION_SUBMISSION:
        if preview.status is not CareerAgentToolStatus.BLOCKED:
            problems.append("job application submission must remain blocked")
    if preview.tool_type is CareerAgentToolType.JOB_APPLICATION_SUBMISSION:
        if preview.status is not CareerAgentToolStatus.BLOCKED:
            problems.append("autonomous job application tool must be blocked")
    if preview.status is CareerAgentToolStatus.EXECUTED and not preview.runtime_execution_performed:
        problems.append("executed status requires backend runtime execution")
    if preview.runtime_execution_performed:
        problems.append("career-agent tool runtime execution is not wired")
    if preview.evidence_refs:
        if any("memory" in ref.data_basis.casefold() for ref in preview.evidence_refs):
            problems.append("career memory was treated as tool evidence")
        if any("preference" in ref.data_basis.casefold() for ref in preview.evidence_refs):
            problems.append("user preferences were treated as tool evidence")
    if (
        preview.tool_type
        in {
            CareerAgentToolType.REMINDER,
            CareerAgentToolType.CAREER_REPORT_EXPORT,
            CareerAgentToolType.WATCHLIST_UPDATE_SUGGESTION,
            CareerAgentToolType.NOTIFICATION_PREFERENCE,
            CareerAgentToolType.OUTREACH_DRAFT,
            CareerAgentToolType.APPLICATION_PREP_CHECKLIST,
        }
        and preview.status is not CareerAgentToolStatus.BLOCKED
        and not preview.evidence_refs
    ):
        problems.append("tool preview is missing grounding evidence refs")
    if preview.uncertainty.forecast_based and not preview.uncertainty.bounded:
        problems.append("forecast-backed tool preview must be bounded")

    if problems:
        raise CareerAgentGuardrailViolation("; ".join(problems))


def validate_career_action_plan(plan: CareerActionPlan) -> None:
    problems: list[str] = []
    dumped = plan.model_dump(mode="json")
    serialized = json.dumps(dumped, sort_keys=True).casefold()

    for token in PRIVATE_OR_UNSAFE_TOKENS:
        if token in serialized:
            problems.append(f"unsafe private/internal token leaked: {token}")
    for token in (*CERTAINTY_TOKENS, *CAREER_PLAN_FABRICATION_TOKENS):
        if token in serialized:
            problems.append(f"unsupported fabricated or certain plan claim: {token}")

    for step in plan.steps:
        if step.strategic and not step.evidence_refs:
            problems.append(f"strategic step {step.step_id} has no evidence refs")
        for binding in step.evidence_bindings:
            if binding.step_id != step.step_id:
                problems.append(f"evidence binding {binding.binding_id} points at a different step")
        opportunity_evidence_ids = {
            ref.entity_id
            for ref in step.evidence_refs
            if ref.evidence_type is CareerAgentEvidenceType.OPPORTUNITY
        }
        for opportunity_id in step.matched_opportunity_ids:
            if opportunity_id not in opportunity_evidence_ids:
                problems.append(
                    f"plan step {step.step_id} references unsupported opportunity {opportunity_id}"
                )
        has_forecast_evidence = any(
            ref.evidence_type is CareerAgentEvidenceType.FORECAST
            for ref in step.evidence_refs
        )
        if has_forecast_evidence or step.uncertainty.forecast_based:
            if not step.uncertainty.bounded:
                problems.append(f"forecast step {step.step_id} must be bounded")
            warning_text = " ".join(step.warnings).casefold()
            if "forecast" not in warning_text or not (
                "not a certain outcome" in warning_text
                or "bounded directional signal" in warning_text
            ):
                problems.append(
                    f"forecast step {step.step_id} must warn that forecasts are bounded"
                )
        if any("preference" in ref.data_basis.casefold() for ref in step.evidence_refs):
            problems.append(f"step {step.step_id} treats user preferences as evidence")
        if any("memory" in ref.data_basis.casefold() for ref in step.evidence_refs):
            problems.append(f"step {step.step_id} treats user memory as evidence")

    if any("preference" in ref.data_basis.casefold() for ref in plan.evidence_refs):
        problems.append("user preferences were treated as plan source evidence")
    if any("memory" in ref.data_basis.casefold() for ref in plan.evidence_refs):
        problems.append("career memory was treated as plan source evidence")

    if problems:
        raise CareerAgentGuardrailViolation("; ".join(problems))


def _safe_career_plan_text(value: str, *, label: str) -> str:
    stripped = _safe_public_text(value, label=label)
    lowered = stripped.casefold()
    for token in CAREER_PLAN_FABRICATION_TOKENS:
        if token in lowered:
            raise ValueError(f"{label} contains unsupported fabricated plan detail")
    return stripped


def _safe_tool_text(value: str, *, label: str) -> str:
    stripped = _safe_career_plan_text(value, label=label)
    lowered = stripped.casefold()
    for token in TOOL_ACTION_UNSAFE_TOKENS:
        if token in lowered:
            raise ValueError(f"{label} contains unsupported tool execution claim")
    return stripped
