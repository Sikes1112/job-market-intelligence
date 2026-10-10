"""Layer 36A personalized career decision lifecycle models."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.db import Base


def _utc_now() -> datetime:
    return datetime.now(UTC)


DECISION_TYPE_SQL = (
    "'role_choice', "
    "'company_choice', "
    "'location_choice', "
    "'career_strategy', "
    "'job_search_strategy', "
    "'education_skill_investment', "
    "'offer_comparison', "
    "'career_path'"
)

DECISION_STATUS_SQL = "'draft', 'evaluating', 'decided', 'reconsidering', 'completed', 'abandoned'"

OPTION_STATUS_SQL = "'active', 'selected', 'rejected', 'archived'"
RECOMMENDATION_STATUS_SQL = "'ready', 'abstained'"
EVIDENCE_SUFFICIENCY_SQL = (
    "'comparison_ready', 'limited_evidence', 'insufficient_evidence', 'not_supported'"
)
ACTION_PLAN_STATUS_SQL = "'active', 'completed', 'archived'"
CAREER_ACTION_TYPE_SQL = (
    "'research', "
    "'application', "
    "'skill_work', "
    "'company_targeting', "
    "'networking_follow_up', "
    "'preparation', "
    "'timing_checkpoint', "
    "'review_task', "
    "'other'"
)
CAREER_ACTION_STATUS_SQL = "'open', 'in_progress', 'completed', 'skipped', 'blocked'"
APPLICATION_STATUS_SQL = (
    "'considering', "
    "'preparing', "
    "'applied', "
    "'response', "
    "'interview', "
    "'final_round', "
    "'rejected', "
    "'withdrawn', "
    "'offer', "
    "'accepted', "
    "'declined'"
)
OUTCOME_TYPE_SQL = (
    "'application_progress', "
    "'offer', "
    "'rejection', "
    "'withdrawal', "
    "'skill_development', "
    "'research_completed', "
    "'networking', "
    "'strategy_change', "
    "'education', "
    "'decision_completed', "
    "'other'"
)
OUTCOME_STATUS_SQL = "'observed', 'reflected', 'superseded'"


class CareerDecision(Base):
    """User-owned aggregate root for a personalized career decision."""

    __tablename__ = "career_decisions"
    __table_args__ = (
        CheckConstraint(f"decision_type IN ({DECISION_TYPE_SQL})", name="ck_career_decisions_type"),
        CheckConstraint(f"status IN ({DECISION_STATUS_SQL})", name="ck_career_decisions_status"),
        CheckConstraint("current_version >= 1", name="ck_career_decisions_current_version"),
        Index("ix_career_decisions_user_status", "user_id", "status"),
        Index("ix_career_decisions_user_updated", "user_id", "updated_at"),
        Index("ix_career_decisions_identity", "career_identity_id"),
        Index("ix_career_decisions_selected_option", "selected_option_id"),
    )

    decision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    career_identity_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("career_identities.career_identity_id"), nullable=True
    )
    current_context_snapshot_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("decision_context_snapshots.context_snapshot_id"), nullable=True
    )
    current_recommendation_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("decision_recommendations.recommendation_id"), nullable=True
    )
    selected_option_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    target_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    planned_review_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    time_horizon: Mapped[str | None] = mapped_column(String(128), nullable=True)
    priorities: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    constraints: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )


class DecisionContextSnapshot(Base):
    """Immutable decision-facing Career Identity context snapshot."""

    __tablename__ = "decision_context_snapshots"
    __table_args__ = (
        CheckConstraint(
            "career_identity_version >= 1", name="ck_decision_context_identity_version"
        ),
        Index("ix_decision_context_user_created", "user_id", "created_at"),
        Index(
            "ix_decision_context_identity_version", "career_identity_id", "career_identity_version"
        ),
    )

    context_snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    career_identity_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("career_identities.career_identity_id"), nullable=False
    )
    career_identity_version: Mapped[int] = mapped_column(Integer, nullable=False)
    completeness_state: Mapped[str] = mapped_column(String(32), nullable=False)
    sufficiency_state: Mapped[str] = mapped_column(String(32), nullable=False)
    privacy_scope: Mapped[str] = mapped_column(
        String(64), nullable=False, default="owner_decision_only"
    )
    context_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    fact_refs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )


class DecisionOption(Base):
    """A structured scenario option within a decision."""

    __tablename__ = "decision_options"
    __table_args__ = (
        CheckConstraint(f"status IN ({OPTION_STATUS_SQL})", name="ck_decision_options_status"),
        CheckConstraint("position >= 0", name="ck_decision_options_position"),
        Index("ix_decision_options_decision_position", "decision_id", "position"),
        Index("ix_decision_options_user", "user_id"),
    )

    option_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    decision_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("career_decisions.decision_id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scenario: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )


class DecisionRecommendation(Base):
    """Persisted fit/comparison/recommendation snapshot for reproducibility."""

    __tablename__ = "decision_recommendations"
    __table_args__ = (
        CheckConstraint(
            f"recommendation_status IN ({RECOMMENDATION_STATUS_SQL})",
            name="ck_decision_recommendations_status",
        ),
        CheckConstraint(
            f"evidence_sufficiency IN ({EVIDENCE_SUFFICIENCY_SQL})",
            name="ck_decision_recommendations_sufficiency",
        ),
        CheckConstraint(
            "confidence IN ('high', 'medium', 'low', 'unknown')",
            name="ck_decision_recommendations_confidence",
        ),
        Index("ix_decision_recommendations_decision", "decision_id", "generated_at"),
        Index("ix_decision_recommendations_context", "context_snapshot_id"),
        Index("ix_decision_recommendations_user", "user_id"),
    )

    recommendation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    decision_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("career_decisions.decision_id"), nullable=False
    )
    context_snapshot_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("decision_context_snapshots.context_snapshot_id"), nullable=False
    )
    recommended_option_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recommendation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_sufficiency: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    fit_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    comparison_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    evidence_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    challenge_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    limitations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )


class DecisionVersion(Base):
    """Append-only decision journal/version snapshot."""

    __tablename__ = "decision_versions"
    __table_args__ = (
        UniqueConstraint(
            "decision_id", "version_number", name="uq_decision_versions_decision_number"
        ),
        CheckConstraint("version_number >= 1", name="ck_decision_versions_number"),
        Index("ix_decision_versions_decision_created", "decision_id", "created_at"),
        Index("ix_decision_versions_user", "user_id"),
    )

    decision_version_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    decision_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("career_decisions.decision_id"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    version_reason: Mapped[str] = mapped_column(String(128), nullable=False)
    decision_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    options_snapshot: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    recommendation_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    selected_option_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    context_snapshot_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("decision_context_snapshots.context_snapshot_id"), nullable=True
    )
    user_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )


class CareerActionPlan(Base):
    """Structured execution plan created from a decision."""

    __tablename__ = "career_action_plans"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({ACTION_PLAN_STATUS_SQL})", name="ck_career_action_plans_status"
        ),
        Index("ix_career_action_plans_decision", "decision_id"),
        Index("ix_career_action_plans_user_status", "user_id", "status"),
        Index(
            "uq_career_action_plans_active_decision",
            "decision_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
        ),
    )

    action_plan_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    decision_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("career_decisions.decision_id"), nullable=False
    )
    selected_option_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    plan_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )


class CareerAction(Base):
    """Personal action state for executing a career decision."""

    __tablename__ = "career_actions"
    __table_args__ = (
        CheckConstraint(
            f"action_type IN ({CAREER_ACTION_TYPE_SQL})", name="ck_career_actions_type"
        ),
        CheckConstraint(f"status IN ({CAREER_ACTION_STATUS_SQL})", name="ck_career_actions_status"),
        CheckConstraint(
            "priority IS NULL OR priority BETWEEN 1 AND 5", name="ck_career_actions_priority"
        ),
        CheckConstraint("position >= 0", name="ck_career_actions_position"),
        Index("ix_career_actions_user_status", "user_id", "status"),
        Index("ix_career_actions_decision", "decision_id"),
        Index("ix_career_actions_plan_position", "action_plan_id", "position"),
        Index("ix_career_actions_due", "due_at"),
    )

    action_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    action_plan_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("career_action_plans.action_plan_id"), nullable=True
    )
    decision_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("career_decisions.decision_id"), nullable=True
    )
    option_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )


class CareerApplication(Base):
    """User personal application tracker, not employer ATS state."""

    __tablename__ = "career_applications"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({APPLICATION_STATUS_SQL})", name="ck_career_applications_status"
        ),
        Index("ix_career_applications_user_status", "user_id", "status"),
        Index("ix_career_applications_decision", "decision_id"),
        Index("ix_career_applications_company", "company_id"),
        Index("ix_career_applications_follow_up", "follow_up_at"),
        UniqueConstraint(
            "user_id",
            "decision_id",
            "current_opportunity_id",
            name="uq_career_applications_pursuit_opportunity",
        ),
    )

    application_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    decision_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("career_decisions.decision_id"), nullable=True
    )
    action_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("career_actions.action_id"), nullable=True
    )
    option_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    company_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("companies.company_id"), nullable=True
    )
    region_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("regions.region_id"), nullable=True
    )
    current_opportunity_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("current_opportunities.current_opportunity_id"), nullable=True
    )
    role_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="considering")
    status_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )


class CareerApplicationTransition(Base):
    """Append-only application status transition history."""

    __tablename__ = "career_application_transitions"
    __table_args__ = (
        CheckConstraint(
            f"to_status IN ({APPLICATION_STATUS_SQL})", name="ck_application_transitions_to_status"
        ),
        CheckConstraint(
            f"from_status IS NULL OR from_status IN ({APPLICATION_STATUS_SQL})",
            name="ck_application_transitions_from_status",
        ),
        Index("ix_application_transitions_application", "application_id", "transitioned_at"),
        Index("ix_application_transitions_user", "user_id"),
    )

    transition_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    application_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("career_applications.application_id"), nullable=False
    )
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    transitioned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )


class CareerOutcome(Base):
    """Observed outcome linked to any point in the decision lifecycle."""

    __tablename__ = "career_outcomes"
    __table_args__ = (
        CheckConstraint(f"outcome_type IN ({OUTCOME_TYPE_SQL})", name="ck_career_outcomes_type"),
        CheckConstraint(f"status IN ({OUTCOME_STATUS_SQL})", name="ck_career_outcomes_status"),
        Index("ix_career_outcomes_user_occurred", "user_id", "occurred_at"),
        Index("ix_career_outcomes_decision", "decision_id"),
        Index("ix_career_outcomes_application", "application_id"),
    )

    outcome_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    decision_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("career_decisions.decision_id"), nullable=True
    )
    action_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("career_actions.action_id"), nullable=True
    )
    application_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("career_applications.application_id"), nullable=True
    )
    option_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recommendation_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("decision_recommendations.recommendation_id"), nullable=True
    )
    outcome_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="observed")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    reflection: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )
