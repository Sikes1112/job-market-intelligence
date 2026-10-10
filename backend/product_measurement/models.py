"""Layer 40A measurable beta operations persistence models."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.db import Base


def _utc_now() -> datetime:
    return datetime.now(UTC)


EVENT_TYPE_SQL = (
    "'authenticated_visit', 'explore_context_evaluated', 'explore_fit_generated', "
    "'explore_fit_abstained', 'explore_context_unsupported', "
    "'market_inspected', 'comparison_selection_ready', 'my_search_viewed', "
    "'comparison_generated', 'comparison_saved', 'prioritize_initiated', "
    "'prioritize_completed', 'comparison_recommendation_overridden', "
    "'comparison_recommendation_viewed', 'comparison_abstained_viewed', "
    "'recommendation_generated', 'decision_considered', 'decision_saved', "
    "'recommendation_changed_decision', 'user_acted', 'action_succeeded', "
    "'outcome_recorded', 'reflection_recorded', 'strategy_changed', "
    "'onboarding_started', 'onboarding_completed', 'career_identity_sufficient', "
    "'decision_created', 'recommendation_viewed', 'recommendation_feedback_submitted', "
    "'action_created', 'application_recorded', 'outcome_updated', 'user_returned', "
    "'coverage_limitation_viewed', 'trust_explanation_viewed', "
    "'commercial_offer_exposed', 'commercial_offer_interest_recorded', "
    "'commercial_conversion_recorded', 'support_case_created', "
    "'support_case_status_changed'"
)
EVENT_SOURCE_SQL = "'backend', 'frontend', 'admin', 'system'"
COHORT_STATUS_SQL = "'planned', 'active', 'paused', 'completed', 'archived'"
MEMBERSHIP_STATUS_SQL = "'invited', 'active', 'paused', 'removed', 'completed'"
FEATURE_ACCESS_MODE_SQL = "'closed', 'open', 'beta_only', 'entitlement_required'"
ASSIGNMENT_STATUS_SQL = "'assigned', 'removed', 'expired'"
FEEDBACK_CALIBRATION_SQL = "'too_high', 'too_low', 'about_right', 'unsure'"
REFLECTION_DECISION_SQL = "'yes', 'no', 'unsure', 'not_applicable'"
REGRET_LEVEL_SQL = "'none', 'low', 'medium', 'high', 'unsure'"
STRATEGY_CHANGE_TYPE_SQL = (
    "'target_role', 'geography', 'company_strategy', 'opportunity_type', "
    "'application_strategy', 'other'"
)
CASE_TYPE_SQL = (
    "'product_issue', 'bad_data', 'recommendation_issue', 'privacy_issue', "
    "'account_access_issue', 'billing_issue', 'other'"
)
CASE_STATUS_SQL = "'open', 'investigating', 'awaiting_user', 'resolved', 'closed'"
ENTITLEMENT_SOURCE_SQL = (
    "'beta_access', 'free_access', 'promotional_access', 'paid_plan', "
    "'institutional_access', 'advisor_university_access', 'administrative_grant'"
)
ENTITLEMENT_STATUS_SQL = "'active', 'expired', 'revoked'"
COMMERCIAL_OFFER_SQL = (
    "'one_time_decision_report', 'active_search_subscription', "
    "'premium_scenarios', 'university_advisor_access'"
)
COMMERCIAL_SIGNAL_SQL = (
    "'exposed', 'interested', 'not_interested', 'learn_more', 'converted', 'activated', 'canceled'"
)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )


class ProductAnalyticsEvent(Base):
    """Append-only canonical product and decision-quality event."""

    __tablename__ = "product_analytics_events"
    __table_args__ = (
        CheckConstraint(f"event_type IN ({EVENT_TYPE_SQL})", name="ck_product_events_type"),
        CheckConstraint(f"event_source IN ({EVENT_SOURCE_SQL})", name="ck_product_events_source"),
        CheckConstraint("schema_version >= 1", name="ck_product_events_schema_version"),
        Index("ix_product_events_user_time", "user_id", "occurred_at"),
        Index("ix_product_events_type_time", "event_type", "occurred_at"),
        Index("ix_product_events_decision", "decision_id", "occurred_at"),
        Index("ix_product_events_recommendation", "recommendation_id"),
        Index("ix_product_events_cohort_type", "cohort_key", "event_type"),
        Index("ix_product_events_experiment", "experiment_key", "variant_key"),
    )

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.user_id"))
    anonymous_session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    event_source: Mapped[str] = mapped_column(String(32), nullable=False)
    product_surface: Mapped[str | None] = mapped_column(String(128), nullable=True)
    decision_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("career_decisions.decision_id"), nullable=True
    )
    recommendation_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("decision_recommendations.recommendation_id"), nullable=True
    )
    current_opportunity_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("current_opportunities.current_opportunity_id"), nullable=True
    )
    action_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("career_actions.action_id"), nullable=True
    )
    application_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("career_applications.application_id"), nullable=True
    )
    outcome_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("career_outcomes.outcome_id"), nullable=True
    )
    career_identity_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("career_identities.career_identity_id"), nullable=True
    )
    career_identity_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cohort_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    experiment_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    variant_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confidence_bucket: Mapped[str | None] = mapped_column(String(32), nullable=True)
    coverage_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recommendation_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )


class ProductUserVisit(Base, TimestampMixin):
    """Server-side authenticated visit boundary for return measurement."""

    __tablename__ = "product_user_visits"
    __table_args__ = (
        Index("ix_product_user_visits_user_started", "user_id", "visit_started_at"),
        Index("ix_product_user_visits_user_last_seen", "user_id", "last_seen_at"),
        Index("ix_product_user_visits_return_event", "returned_event_id"),
        Index("ix_product_user_visits_cohort", "cohort_key"),
    )

    visit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    visit_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    product_surface: Mapped[str] = mapped_column(String(128), nullable=False)
    cohort_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    experiment_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    variant_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    returned_event_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("product_analytics_events.event_id"), nullable=True
    )


class BetaCohort(Base, TimestampMixin):
    """Controlled beta or rollout cohort."""

    __tablename__ = "beta_cohorts"
    __table_args__ = (
        CheckConstraint(f"status IN ({COHORT_STATUS_SQL})", name="ck_beta_cohorts_status"),
        UniqueConstraint("cohort_key", name="uq_beta_cohorts_key"),
        Index("ix_beta_cohorts_status", "status"),
    )

    cohort_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cohort_key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="planned")
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    feature_flags: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    configuration: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class BetaCohortMembership(Base, TimestampMixin):
    """User assignment to a beta cohort, never hard-coded in app logic."""

    __tablename__ = "beta_cohort_memberships"
    __table_args__ = (
        CheckConstraint(f"status IN ({MEMBERSHIP_STATUS_SQL})", name="ck_beta_memberships_status"),
        UniqueConstraint("user_id", "cohort_id", name="uq_beta_memberships_user_cohort"),
        Index("ix_beta_memberships_user_status", "user_id", "status"),
        Index("ix_beta_memberships_cohort_status", "cohort_id", "status"),
    )

    membership_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    cohort_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("beta_cohorts.cohort_id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    assigned_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    configuration: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class ProductFeatureGate(Base, TimestampMixin):
    """Server-authoritative feature access configuration."""

    __tablename__ = "product_feature_gates"
    __table_args__ = (
        CheckConstraint(
            f"access_mode IN ({FEATURE_ACCESS_MODE_SQL})", name="ck_feature_gates_mode"
        ),
        UniqueConstraint("feature_key", name="uq_feature_gates_key"),
        Index("ix_feature_gates_mode", "access_mode"),
        Index("ix_feature_gates_enabled", "enabled"),
    )

    feature_gate_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    feature_key: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    access_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="closed")
    cohort_keys: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    entitlement_feature_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    configuration: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class ExperimentAssignment(Base, TimestampMixin):
    """Stable user assignment to a beta or commercial experiment variant."""

    __tablename__ = "experiment_assignments"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({ASSIGNMENT_STATUS_SQL})", name="ck_experiment_assignments_status"
        ),
        UniqueConstraint("user_id", "experiment_key", name="uq_experiment_user_key"),
        Index("ix_experiment_assignments_user", "user_id"),
        Index("ix_experiment_assignments_experiment", "experiment_key", "variant_key"),
    )

    assignment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    cohort_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("beta_cohorts.cohort_id"), nullable=True
    )
    experiment_key: Mapped[str] = mapped_column(String(128), nullable=False)
    variant_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="assigned")
    assignment_basis: Mapped[str] = mapped_column(String(128), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RecommendationFeedback(Base, TimestampMixin):
    """User feedback tied to the exact recommendation/version shown."""

    __tablename__ = "recommendation_feedback"
    __table_args__ = (
        CheckConstraint(
            f"confidence_calibration IN ({FEEDBACK_CALIBRATION_SQL})",
            name="ck_recommendation_feedback_calibration",
        ),
        Index("ix_recommendation_feedback_user_created", "user_id", "created_at"),
        Index("ix_recommendation_feedback_decision", "decision_id"),
        Index("ix_recommendation_feedback_recommendation", "recommendation_id"),
        Index("ix_recommendation_feedback_cohort", "cohort_key"),
    )

    feedback_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    decision_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("career_decisions.decision_id"), nullable=False
    )
    recommendation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("decision_recommendations.recommendation_id"), nullable=False
    )
    useful: Mapped[bool] = mapped_column(Boolean, nullable=False)
    surprising: Mapped[bool] = mapped_column(Boolean, nullable=False)
    changed_decision: Mapped[bool] = mapped_column(Boolean, nullable=False)
    missing_alternative: Mapped[bool] = mapped_column(Boolean, nullable=False)
    missing_alternative_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confidence_calibration: Mapped[str] = mapped_column(String(32), nullable=False)
    feedback_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    cohort_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    experiment_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    variant_key: Mapped[str | None] = mapped_column(String(128), nullable=True)


class DecisionReflection(Base, TimestampMixin):
    """Bounded later reflection on a user decision and outcome."""

    __tablename__ = "decision_reflections"
    __table_args__ = (
        CheckConstraint(
            f"would_make_same_decision IN ({REFLECTION_DECISION_SQL})",
            name="ck_decision_reflections_same_decision",
        ),
        CheckConstraint(
            f"regret_level IS NULL OR regret_level IN ({REGRET_LEVEL_SQL})",
            name="ck_decision_reflections_regret",
        ),
        CheckConstraint(
            "satisfaction_rating IS NULL OR satisfaction_rating BETWEEN 1 AND 5",
            name="ck_decision_reflections_satisfaction",
        ),
        Index("ix_decision_reflections_user_created", "user_id", "created_at"),
        Index("ix_decision_reflections_decision", "decision_id"),
        Index("ix_decision_reflections_recommendation", "recommendation_id"),
    )

    reflection_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    decision_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("career_decisions.decision_id"), nullable=False
    )
    recommendation_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("decision_recommendations.recommendation_id"), nullable=True
    )
    outcome_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("career_outcomes.outcome_id"), nullable=True
    )
    would_make_same_decision: Mapped[str] = mapped_column(String(32), nullable=False)
    view_changed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    satisfaction_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    regret_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reflection_comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class StrategyChange(Base, TimestampMixin):
    """Explicit durable strategy-change record."""

    __tablename__ = "strategy_changes"
    __table_args__ = (
        CheckConstraint(
            f"change_type IN ({STRATEGY_CHANGE_TYPE_SQL})", name="ck_strategy_changes_type"
        ),
        Index("ix_strategy_changes_user_occurred", "user_id", "occurred_at"),
        Index("ix_strategy_changes_decision", "decision_id"),
        Index("ix_strategy_changes_recommendation", "recommendation_id"),
    )

    strategy_change_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    decision_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("career_decisions.decision_id"), nullable=True
    )
    recommendation_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("decision_recommendations.recommendation_id"), nullable=True
    )
    change_type: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_state: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    reason_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class SupportCase(Base, TimestampMixin):
    """Durable beta support, correction, dispute, privacy, and incident case."""

    __tablename__ = "support_cases"
    __table_args__ = (
        CheckConstraint(f"case_type IN ({CASE_TYPE_SQL})", name="ck_support_cases_type"),
        CheckConstraint(f"status IN ({CASE_STATUS_SQL})", name="ck_support_cases_status"),
        Index("ix_support_cases_user_status", "user_id", "status"),
        Index("ix_support_cases_type_status", "case_type", "status"),
        Index("ix_support_cases_subject", "subject_type", "subject_id"),
        Index("ix_support_cases_decision", "decision_id"),
        Index("ix_support_cases_recommendation", "recommendation_id"),
    )

    support_case_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    case_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subject_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    decision_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("career_decisions.decision_id"), nullable=True
    )
    recommendation_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("decision_recommendations.recommendation_id"), nullable=True
    )
    current_opportunity_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("current_opportunities.current_opportunity_id"), nullable=True
    )
    privacy_request_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="normal")
    assigned_operator_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SupportCaseEvent(Base):
    """Append-only support case lifecycle event."""

    __tablename__ = "support_case_events"
    __table_args__ = (
        Index("ix_support_case_events_case", "support_case_id", "created_at"),
        Index("ix_support_case_events_actor", "actor_user_id"),
    )

    support_case_event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    support_case_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("support_cases.support_case_id"), nullable=False
    )
    actor_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    before_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )


class ProductEntitlementGrant(Base, TimestampMixin):
    """Canonical product entitlement grant independent of ranking intelligence."""

    __tablename__ = "product_entitlement_grants"
    __table_args__ = (
        CheckConstraint(
            f"source_type IN ({ENTITLEMENT_SOURCE_SQL})", name="ck_product_entitlements_source"
        ),
        CheckConstraint(
            f"status IN ({ENTITLEMENT_STATUS_SQL})", name="ck_product_entitlements_status"
        ),
        Index("ix_product_entitlements_user_feature", "user_id", "feature_key"),
        Index("ix_product_entitlements_source", "source_type", "source_ref_id"),
        Index("ix_product_entitlements_status", "status"),
    )

    entitlement_grant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False)
    feature_key: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_ref_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    effective_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str] = mapped_column(String(512), nullable=False)


class CommercialExperimentSignal(Base, TimestampMixin):
    """Observed commercial offer exposure/interest/conversion signal."""

    __tablename__ = "commercial_experiment_signals"
    __table_args__ = (
        CheckConstraint(
            f"offer_key IN ({COMMERCIAL_OFFER_SQL})", name="ck_commercial_signals_offer"
        ),
        CheckConstraint(
            f"signal_type IN ({COMMERCIAL_SIGNAL_SQL})", name="ck_commercial_signals_type"
        ),
        Index("ix_commercial_signals_user_created", "user_id", "created_at"),
        Index("ix_commercial_signals_experiment", "experiment_key", "variant_key"),
        Index("ix_commercial_signals_offer", "offer_key", "signal_type"),
    )

    signal_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.user_id"))
    experiment_key: Mapped[str] = mapped_column(String(128), nullable=False)
    variant_key: Mapped[str] = mapped_column(String(128), nullable=False)
    offer_key: Mapped[str] = mapped_column(String(64), nullable=False)
    signal_type: Mapped[str] = mapped_column(String(64), nullable=False)
    product_surface: Mapped[str | None] = mapped_column(String(128), nullable=True)
    conversion_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    qualitative_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


@event.listens_for(ProductAnalyticsEvent, "before_update", propagate=True)
@event.listens_for(ProductAnalyticsEvent, "before_delete", propagate=True)
def _reject_product_event_mutation(_mapper, _connection, _target) -> None:  # noqa: ANN001
    raise ValueError("product analytics events are append-only")


@event.listens_for(SupportCaseEvent, "before_update", propagate=True)
@event.listens_for(SupportCaseEvent, "before_delete", propagate=True)
def _reject_support_case_event_mutation(_mapper, _connection, _target) -> None:  # noqa: ANN001
    raise ValueError("support case events are append-only")
