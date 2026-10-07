"""Layer 37 deep decision intelligence schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class FactorCategory(_Vocabulary):
    BENEFIT = "benefit"
    COST = "cost"
    RISK = "risk"
    TIME = "time"
    CONFIDENCE = "confidence"
    UNCERTAINTY = "uncertainty"
    USER_IMPORTANCE = "user_importance"
    EVIDENCE_STRENGTH = "evidence_strength"
    REVERSIBILITY = "reversibility"


class FactorDirection(_Vocabulary):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class FactorEvidenceKind(_Vocabulary):
    DIRECT = "direct"
    DERIVED = "derived"
    INFERRED = "inferred"
    PROXY = "proxy"
    UNAVAILABLE = "unavailable"
    CONFLICTING = "conflicting"


class FactorConfidence(_Vocabulary):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class FactorFreshness(_Vocabulary):
    FRESH = "fresh"
    STALE = "stale"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class AdvisorySeverity(_Vocabulary):
    INFO = "info"
    WATCH = "watch"
    WARNING = "warning"
    BLOCKING = "blocking"


class AdvisorySupportStatus(_Vocabulary):
    SUPPORTED = "supported"
    WEAKLY_SUPPORTED = "weakly_supported"
    UNRESOLVED = "unresolved"


class RecommendationEvolutionChangeType(_Vocabulary):
    NONE = "none"
    USER_CHANGED = "user_changed"
    GOAL_CHANGED = "goal_changed"
    CAREER_IDENTITY_CHANGED = "career_identity_changed"
    MARKET_CHANGED = "market_changed"
    EVIDENCE_CHANGED = "evidence_changed"
    OUTCOME_CHANGED = "outcome_changed"
    CONFIDENCE_CHANGED = "confidence_changed"
    STALE_PRIOR = "stale_prior"
    SUPERSEDED = "superseded"


class DeepDecisionAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    include_domains: tuple[str, ...] = Field(default_factory=tuple, max_length=25)
    window_start: datetime | None = None
    window_end: datetime | None = None

    @field_validator("include_domains")
    @classmethod
    def _clean_domains(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(dict.fromkeys(_clean_optional(item) for item in value))
        return tuple(item for item in cleaned if item)


class DecisionFactorView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    factor_id: str
    decision_id: str
    option_id: str | None
    recommendation_id: str | None
    context_snapshot_id: str | None
    domain: str
    category: FactorCategory
    factor_key: str
    label: str
    normalized_value: dict[str, Any] | None
    raw_value: dict[str, Any] | None
    direction: FactorDirection
    importance: int | None
    confidence: FactorConfidence
    uncertainty: str
    evidence_strength: str
    evidence_kind: FactorEvidenceKind
    source_type: str | None
    source_id: str | None
    provenance: dict[str, Any]
    explanation: str
    caveats: tuple[str, ...]
    freshness_status: FactorFreshness
    freshness_expires_at: datetime | None
    generated_at: datetime


class LongitudinalContextView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    longitudinal_context_id: str
    decision_id: str | None
    window_start: datetime | None
    window_end: datetime
    record_count: int
    context: dict[str, Any]
    evidence: dict[str, Any]
    generated_at: datetime


class RecommendationEvolutionView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evolution_id: str
    decision_id: str
    previous_recommendation_id: str | None
    current_recommendation_id: str | None
    change_type: RecommendationEvolutionChangeType
    meaningful_changes: tuple[dict[str, Any], ...]
    confidence_before: FactorConfidence | None
    confidence_after: FactorConfidence | None
    evidence_basis: dict[str, Any]
    uncertainty: str
    explanation: str
    generated_at: datetime


class AdvisoryFindingView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    advisory_finding_id: str
    decision_id: str | None
    finding_type: str
    severity: AdvisorySeverity
    support_status: AdvisorySupportStatus
    confidence: FactorConfidence
    uncertainty: str
    window_start: datetime | None
    window_end: datetime
    affected_goal: str | None
    supporting_evidence: tuple[dict[str, Any], ...]
    counter_evidence: tuple[dict[str, Any], ...]
    explanation: str
    suggested_action: str | None
    acknowledged_at: datetime | None
    dismissed_at: datetime | None
    generated_at: datetime


class StrategicCareerReviewView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    strategic_review_id: str
    decision_id: str | None
    longitudinal_context_id: str
    status: str
    window_start: datetime | None
    window_end: datetime
    goals: dict[str, Any]
    strategy_performance: dict[str, Any]
    application_summary: dict[str, Any]
    outcome_summary: dict[str, Any]
    identity_changes: tuple[dict[str, Any], ...]
    market_changes: tuple[dict[str, Any], ...]
    recommendation_changes: tuple[dict[str, Any], ...]
    active_risks: tuple[dict[str, Any], ...]
    blind_spots: tuple[dict[str, Any], ...]
    suggested_next_actions: tuple[dict[str, Any], ...]
    confidence: FactorConfidence
    uncertainty: str
    generated_at: datetime


class DeepDecisionAnalysisView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str
    factors: tuple[DecisionFactorView, ...]
    longitudinal_context: LongitudinalContextView
    recommendation_evolution: RecommendationEvolutionView | None
    advisory_findings: tuple[AdvisoryFindingView, ...]
    strategic_review: StrategicCareerReviewView


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    return cleaned or None
