"""Layer 37 deep decision intelligence persistence models."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.db import Base


def _utc_now() -> datetime:
    return datetime.now(UTC)


FACTOR_CATEGORY_SQL = (
    "'benefit', 'cost', 'risk', 'time', 'confidence', 'uncertainty', "
    "'user_importance', 'evidence_strength', 'reversibility'"
)
FACTOR_DIRECTION_SQL = "'positive', 'negative', 'neutral', 'mixed', 'unknown'"
FACTOR_EVIDENCE_KIND_SQL = "'direct', 'derived', 'inferred', 'proxy', 'unavailable', 'conflicting'"
FACTOR_CONFIDENCE_SQL = "'high', 'medium', 'low', 'unknown'"
FACTOR_FRESHNESS_SQL = "'fresh', 'stale', 'partial', 'unknown'"
ADVISORY_SEVERITY_SQL = "'info', 'watch', 'warning', 'blocking'"
ADVISORY_SUPPORT_SQL = "'supported', 'weakly_supported', 'unresolved'"
EVOLUTION_CHANGE_SQL = (
    "'none', 'user_changed', 'goal_changed', 'career_identity_changed', "
    "'market_changed', 'evidence_changed', 'outcome_changed', "
    "'confidence_changed', 'stale_prior', 'superseded'"
)
STRATEGIC_REVIEW_STATUS_SQL = "'generated', 'archived'"


class DecisionFactor(Base):
    """Shared factor record attached to a Layer 36 decision scenario."""

    __tablename__ = "decision_factors"
    __table_args__ = (
        CheckConstraint(
            f"category IN ({FACTOR_CATEGORY_SQL})", name="ck_decision_factors_category"
        ),
        CheckConstraint(
            f"direction IN ({FACTOR_DIRECTION_SQL})", name="ck_decision_factors_direction"
        ),
        CheckConstraint(
            f"evidence_kind IN ({FACTOR_EVIDENCE_KIND_SQL})",
            name="ck_decision_factors_evidence_kind",
        ),
        CheckConstraint(
            f"confidence IN ({FACTOR_CONFIDENCE_SQL})", name="ck_decision_factors_confidence"
        ),
        CheckConstraint(
            f"freshness_status IN ({FACTOR_FRESHNESS_SQL})",
            name="ck_decision_factors_freshness",
        ),
        CheckConstraint(
            "importance IS NULL OR importance BETWEEN 1 AND 5",
            name="ck_decision_factors_importance",
        ),
        Index("ix_decision_factors_decision_domain", "decision_id", "domain"),
        Index("ix_decision_factors_option", "option_id"),
        Index("ix_decision_factors_user_generated", "user_id", "generated_at"),
        Index("ix_decision_factors_recommendation", "recommendation_id"),
    )

    factor_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    decision_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("career_decisions.decision_id"), nullable=False
    )
    option_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("decision_options.option_id"), nullable=True
    )
    recommendation_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("decision_recommendations.recommendation_id"), nullable=True
    )
    context_snapshot_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("decision_context_snapshots.context_snapshot_id"), nullable=True
    )
    domain: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    factor_key: Mapped[str] = mapped_column(String(128), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    raw_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    direction: Mapped[str] = mapped_column(String(32), nullable=False)
    importance: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    uncertainty: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_strength: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provenance: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    caveats: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    freshness_status: Mapped[str] = mapped_column(String(32), nullable=False)
    freshness_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )


class LongitudinalContextSnapshot(Base):
    """Bounded historical decision context used for Layer 37 review/advice."""

    __tablename__ = "longitudinal_context_snapshots"
    __table_args__ = (
        CheckConstraint("record_count >= 0", name="ck_longitudinal_context_record_count"),
        Index("ix_longitudinal_context_user_generated", "user_id", "generated_at"),
        Index("ix_longitudinal_context_decision", "decision_id"),
    )

    longitudinal_context_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    decision_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("career_decisions.decision_id"), nullable=True
    )
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    context_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    evidence_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )


class RecommendationEvolution(Base):
    """Comparison of prior and current Layer 36 recommendation snapshots."""

    __tablename__ = "decision_recommendation_evolutions"
    __table_args__ = (
        CheckConstraint(
            f"change_type IN ({EVOLUTION_CHANGE_SQL})", name="ck_recommendation_evolutions_change"
        ),
        CheckConstraint(
            f"confidence_before IS NULL OR confidence_before IN ({FACTOR_CONFIDENCE_SQL})",
            name="ck_recommendation_evolutions_conf_before",
        ),
        CheckConstraint(
            f"confidence_after IS NULL OR confidence_after IN ({FACTOR_CONFIDENCE_SQL})",
            name="ck_recommendation_evolutions_conf_after",
        ),
        Index("ix_recommendation_evolutions_decision", "decision_id", "generated_at"),
        Index("ix_recommendation_evolutions_user", "user_id", "generated_at"),
    )

    evolution_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    decision_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("career_decisions.decision_id"), nullable=False
    )
    previous_recommendation_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("decision_recommendations.recommendation_id"), nullable=True
    )
    current_recommendation_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("decision_recommendations.recommendation_id"), nullable=True
    )
    change_type: Mapped[str] = mapped_column(String(64), nullable=False)
    meaningful_changes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    confidence_before: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence_after: Mapped[str | None] = mapped_column(String(32), nullable=True)
    evidence_basis: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    uncertainty: Mapped[str] = mapped_column(String(64), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )


class AdvisoryFinding(Base):
    """Typed, evidence-backed proactive advisor finding."""

    __tablename__ = "decision_advisory_findings"
    __table_args__ = (
        CheckConstraint(
            f"severity IN ({ADVISORY_SEVERITY_SQL})", name="ck_advisory_findings_severity"
        ),
        CheckConstraint(
            f"support_status IN ({ADVISORY_SUPPORT_SQL})", name="ck_advisory_findings_support"
        ),
        CheckConstraint(
            f"confidence IN ({FACTOR_CONFIDENCE_SQL})", name="ck_advisory_findings_confidence"
        ),
        Index("ix_advisory_findings_decision", "decision_id", "generated_at"),
        Index("ix_advisory_findings_user_status", "user_id", "support_status"),
        Index("ix_advisory_findings_type", "finding_type"),
    )

    advisory_finding_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    decision_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("career_decisions.decision_id"), nullable=True
    )
    finding_type: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    support_status: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    uncertainty: Mapped[str] = mapped_column(String(64), nullable=False)
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    affected_goal: Mapped[str | None] = mapped_column(String(255), nullable=True)
    supporting_evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    counter_evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )


class StrategicCareerReview(Base):
    """Persisted strategic career review generated from bounded Layer 37 context."""

    __tablename__ = "strategic_career_reviews"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({STRATEGIC_REVIEW_STATUS_SQL})", name="ck_strategic_reviews_status"
        ),
        CheckConstraint(
            f"confidence IN ({FACTOR_CONFIDENCE_SQL})", name="ck_strategic_reviews_confidence"
        ),
        Index("ix_strategic_reviews_user_generated", "user_id", "generated_at"),
        Index("ix_strategic_reviews_decision", "decision_id", "generated_at"),
        Index("ix_strategic_reviews_context", "longitudinal_context_id"),
    )

    strategic_review_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    decision_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("career_decisions.decision_id"), nullable=True
    )
    longitudinal_context_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("longitudinal_context_snapshots.longitudinal_context_id"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="generated")
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    goals: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    strategy_performance: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    application_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    outcome_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    identity_changes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    market_changes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    recommendation_changes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    active_risks: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    blind_spots: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    suggested_next_actions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    uncertainty: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )
