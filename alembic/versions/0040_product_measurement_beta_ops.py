"""Add Layer 40A product measurement and beta operations.

Revision ID: 0040_product_measurement_beta_ops
Revises: 0039_current_opportunity_backend
Create Date: 2026-09-02
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0040_product_measurement_beta_ops"
down_revision = "0039_current_opportunity_backend"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_analytics_events",
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column("anonymous_session_id", sa.String(length=128), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_source", sa.String(length=32), nullable=False),
        sa.Column("product_surface", sa.String(length=128), nullable=True),
        sa.Column("decision_id", sa.String(length=64), nullable=True),
        sa.Column("recommendation_id", sa.String(length=64), nullable=True),
        sa.Column("current_opportunity_id", sa.String(length=64), nullable=True),
        sa.Column("action_id", sa.String(length=64), nullable=True),
        sa.Column("application_id", sa.String(length=64), nullable=True),
        sa.Column("outcome_id", sa.String(length=64), nullable=True),
        sa.Column("career_identity_id", sa.String(length=64), nullable=True),
        sa.Column("career_identity_version", sa.Integer(), nullable=True),
        sa.Column("cohort_key", sa.String(length=64), nullable=True),
        sa.Column("experiment_key", sa.String(length=128), nullable=True),
        sa.Column("variant_key", sa.String(length=128), nullable=True),
        sa.Column("confidence_bucket", sa.String(length=32), nullable=True),
        sa.Column("coverage_status", sa.String(length=64), nullable=True),
        sa.Column("recommendation_state", sa.String(length=64), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_source IN ('backend', 'frontend', 'admin', 'system')",
            name="ck_product_events_source",
        ),
        sa.CheckConstraint(
            "event_type IN ("
            "'recommendation_generated', 'decision_considered', 'decision_saved', "
            "'recommendation_changed_decision', 'user_acted', 'action_succeeded', "
            "'outcome_recorded', 'reflection_recorded', 'strategy_changed', "
            "'onboarding_started', 'onboarding_completed', 'career_identity_sufficient', "
            "'decision_created', 'recommendation_viewed', "
            "'recommendation_feedback_submitted', 'action_created', "
            "'application_recorded', 'outcome_updated', 'user_returned', "
            "'coverage_limitation_viewed', 'trust_explanation_viewed', "
            "'commercial_offer_exposed', 'commercial_offer_interest_recorded', "
            "'commercial_conversion_recorded', 'support_case_created', "
            "'support_case_status_changed')",
            name="ck_product_events_type",
        ),
        sa.CheckConstraint("schema_version >= 1", name="ck_product_events_schema_version"),
        sa.ForeignKeyConstraint(["action_id"], ["career_actions.action_id"]),
        sa.ForeignKeyConstraint(["application_id"], ["career_applications.application_id"]),
        sa.ForeignKeyConstraint(["career_identity_id"], ["career_identities.career_identity_id"]),
        sa.ForeignKeyConstraint(
            ["current_opportunity_id"], ["current_opportunities.current_opportunity_id"]
        ),
        sa.ForeignKeyConstraint(["decision_id"], ["career_decisions.decision_id"]),
        sa.ForeignKeyConstraint(["outcome_id"], ["career_outcomes.outcome_id"]),
        sa.ForeignKeyConstraint(
            ["recommendation_id"], ["decision_recommendations.recommendation_id"]
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_product_events_cohort_type", "product_analytics_events", ["cohort_key", "event_type"]
    )
    op.create_index(
        "ix_product_events_decision", "product_analytics_events", ["decision_id", "occurred_at"]
    )
    op.create_index(
        "ix_product_events_experiment",
        "product_analytics_events",
        ["experiment_key", "variant_key"],
    )
    op.create_index(
        "ix_product_events_recommendation", "product_analytics_events", ["recommendation_id"]
    )
    op.create_index(
        "ix_product_events_type_time", "product_analytics_events", ["event_type", "occurred_at"]
    )
    op.create_index(
        "ix_product_events_user_time", "product_analytics_events", ["user_id", "occurred_at"]
    )

    op.create_table(
        "product_user_visits",
        sa.Column("visit_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("visit_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("product_surface", sa.String(length=128), nullable=False),
        sa.Column("cohort_key", sa.String(length=64), nullable=True),
        sa.Column("experiment_key", sa.String(length=128), nullable=True),
        sa.Column("variant_key", sa.String(length=128), nullable=True),
        sa.Column("returned_event_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["returned_event_id"], ["product_analytics_events.event_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("visit_id"),
    )
    op.create_index("ix_product_user_visits_cohort", "product_user_visits", ["cohort_key"])
    op.create_index(
        "ix_product_user_visits_return_event", "product_user_visits", ["returned_event_id"]
    )
    op.create_index(
        "ix_product_user_visits_user_last_seen", "product_user_visits", ["user_id", "last_seen_at"]
    )
    op.create_index(
        "ix_product_user_visits_user_started",
        "product_user_visits",
        ["user_id", "visit_started_at"],
    )

    op.create_table(
        "beta_cohorts",
        sa.Column("cohort_id", sa.String(length=64), nullable=False),
        sa.Column("cohort_key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("feature_flags", sa.JSON(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('planned', 'active', 'paused', 'completed', 'archived')",
            name="ck_beta_cohorts_status",
        ),
        sa.PrimaryKeyConstraint("cohort_id"),
        sa.UniqueConstraint("cohort_key", name="uq_beta_cohorts_key"),
    )
    op.create_index("ix_beta_cohorts_status", "beta_cohorts", ["status"])

    op.create_table(
        "product_feature_gates",
        sa.Column("feature_gate_id", sa.String(length=64), nullable=False),
        sa.Column("feature_key", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("access_mode", sa.String(length=32), nullable=False),
        sa.Column("cohort_keys", sa.JSON(), nullable=False),
        sa.Column("entitlement_feature_key", sa.String(length=128), nullable=True),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "access_mode IN ('closed', 'open', 'beta_only', 'entitlement_required')",
            name="ck_feature_gates_mode",
        ),
        sa.PrimaryKeyConstraint("feature_gate_id"),
        sa.UniqueConstraint("feature_key", name="uq_feature_gates_key"),
    )
    op.create_index("ix_feature_gates_enabled", "product_feature_gates", ["enabled"])
    op.create_index("ix_feature_gates_mode", "product_feature_gates", ["access_mode"])

    op.create_table(
        "beta_cohort_memberships",
        sa.Column("membership_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("cohort_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("assigned_by", sa.String(length=64), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('invited', 'active', 'paused', 'removed', 'completed')",
            name="ck_beta_memberships_status",
        ),
        sa.ForeignKeyConstraint(["cohort_id"], ["beta_cohorts.cohort_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("membership_id"),
        sa.UniqueConstraint("user_id", "cohort_id", name="uq_beta_memberships_user_cohort"),
    )
    op.create_index(
        "ix_beta_memberships_cohort_status", "beta_cohort_memberships", ["cohort_id", "status"]
    )
    op.create_index(
        "ix_beta_memberships_user_status", "beta_cohort_memberships", ["user_id", "status"]
    )

    op.create_table(
        "experiment_assignments",
        sa.Column("assignment_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("cohort_id", sa.String(length=64), nullable=True),
        sa.Column("experiment_key", sa.String(length=128), nullable=False),
        sa.Column("variant_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("assignment_basis", sa.String(length=128), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('assigned', 'removed', 'expired')",
            name="ck_experiment_assignments_status",
        ),
        sa.ForeignKeyConstraint(["cohort_id"], ["beta_cohorts.cohort_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("assignment_id"),
        sa.UniqueConstraint("user_id", "experiment_key", name="uq_experiment_user_key"),
    )
    op.create_index(
        "ix_experiment_assignments_experiment",
        "experiment_assignments",
        ["experiment_key", "variant_key"],
    )
    op.create_index("ix_experiment_assignments_user", "experiment_assignments", ["user_id"])

    op.create_table(
        "recommendation_feedback",
        sa.Column("feedback_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("decision_id", sa.String(length=64), nullable=False),
        sa.Column("recommendation_id", sa.String(length=64), nullable=False),
        sa.Column("useful", sa.Boolean(), nullable=False),
        sa.Column("surprising", sa.Boolean(), nullable=False),
        sa.Column("changed_decision", sa.Boolean(), nullable=False),
        sa.Column("missing_alternative", sa.Boolean(), nullable=False),
        sa.Column("missing_alternative_category", sa.String(length=128), nullable=True),
        sa.Column("confidence_calibration", sa.String(length=32), nullable=False),
        sa.Column("feedback_comment", sa.Text(), nullable=True),
        sa.Column("cohort_key", sa.String(length=64), nullable=True),
        sa.Column("experiment_key", sa.String(length=128), nullable=True),
        sa.Column("variant_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "confidence_calibration IN ('too_high', 'too_low', 'about_right', 'unsure')",
            name="ck_recommendation_feedback_calibration",
        ),
        sa.ForeignKeyConstraint(["decision_id"], ["career_decisions.decision_id"]),
        sa.ForeignKeyConstraint(
            ["recommendation_id"], ["decision_recommendations.recommendation_id"]
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("feedback_id"),
    )
    op.create_index("ix_recommendation_feedback_cohort", "recommendation_feedback", ["cohort_key"])
    op.create_index(
        "ix_recommendation_feedback_decision", "recommendation_feedback", ["decision_id"]
    )
    op.create_index(
        "ix_recommendation_feedback_recommendation",
        "recommendation_feedback",
        ["recommendation_id"],
    )
    op.create_index(
        "ix_recommendation_feedback_user_created",
        "recommendation_feedback",
        ["user_id", "created_at"],
    )

    op.create_table(
        "decision_reflections",
        sa.Column("reflection_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("decision_id", sa.String(length=64), nullable=False),
        sa.Column("recommendation_id", sa.String(length=64), nullable=True),
        sa.Column("outcome_id", sa.String(length=64), nullable=True),
        sa.Column("would_make_same_decision", sa.String(length=32), nullable=False),
        sa.Column("view_changed", sa.Boolean(), nullable=False),
        sa.Column("satisfaction_rating", sa.Integer(), nullable=True),
        sa.Column("regret_level", sa.String(length=32), nullable=True),
        sa.Column("reflection_comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "would_make_same_decision IN ('yes', 'no', 'unsure', 'not_applicable')",
            name="ck_decision_reflections_same_decision",
        ),
        sa.CheckConstraint(
            "regret_level IS NULL OR regret_level IN ('none', 'low', 'medium', 'high', 'unsure')",
            name="ck_decision_reflections_regret",
        ),
        sa.CheckConstraint(
            "satisfaction_rating IS NULL OR satisfaction_rating BETWEEN 1 AND 5",
            name="ck_decision_reflections_satisfaction",
        ),
        sa.ForeignKeyConstraint(["decision_id"], ["career_decisions.decision_id"]),
        sa.ForeignKeyConstraint(["outcome_id"], ["career_outcomes.outcome_id"]),
        sa.ForeignKeyConstraint(
            ["recommendation_id"], ["decision_recommendations.recommendation_id"]
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("reflection_id"),
    )
    op.create_index("ix_decision_reflections_decision", "decision_reflections", ["decision_id"])
    op.create_index(
        "ix_decision_reflections_recommendation", "decision_reflections", ["recommendation_id"]
    )
    op.create_index(
        "ix_decision_reflections_user_created", "decision_reflections", ["user_id", "created_at"]
    )

    op.create_table(
        "strategy_changes",
        sa.Column("strategy_change_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("decision_id", sa.String(length=64), nullable=True),
        sa.Column("recommendation_id", sa.String(length=64), nullable=True),
        sa.Column("change_type", sa.String(length=64), nullable=False),
        sa.Column("previous_state", sa.JSON(), nullable=True),
        sa.Column("new_state", sa.JSON(), nullable=False),
        sa.Column("reason_category", sa.String(length=128), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "change_type IN ('target_role', 'geography', 'company_strategy', "
            "'opportunity_type', 'application_strategy', 'other')",
            name="ck_strategy_changes_type",
        ),
        sa.ForeignKeyConstraint(["decision_id"], ["career_decisions.decision_id"]),
        sa.ForeignKeyConstraint(
            ["recommendation_id"], ["decision_recommendations.recommendation_id"]
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("strategy_change_id"),
    )
    op.create_index("ix_strategy_changes_decision", "strategy_changes", ["decision_id"])
    op.create_index("ix_strategy_changes_recommendation", "strategy_changes", ["recommendation_id"])
    op.create_index(
        "ix_strategy_changes_user_occurred", "strategy_changes", ["user_id", "occurred_at"]
    )

    op.create_table(
        "support_cases",
        sa.Column("support_case_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("case_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("subject_type", sa.String(length=64), nullable=True),
        sa.Column("subject_id", sa.String(length=128), nullable=True),
        sa.Column("decision_id", sa.String(length=64), nullable=True),
        sa.Column("recommendation_id", sa.String(length=64), nullable=True),
        sa.Column("current_opportunity_id", sa.String(length=64), nullable=True),
        sa.Column("privacy_request_type", sa.String(length=64), nullable=True),
        sa.Column("priority", sa.String(length=32), nullable=False),
        sa.Column("assigned_operator_id", sa.String(length=64), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "case_type IN ('product_issue', 'bad_data', 'recommendation_issue', "
            "'privacy_issue', 'account_access_issue', 'billing_issue', 'other')",
            name="ck_support_cases_type",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'investigating', 'awaiting_user', 'resolved', 'closed')",
            name="ck_support_cases_status",
        ),
        sa.ForeignKeyConstraint(
            ["current_opportunity_id"], ["current_opportunities.current_opportunity_id"]
        ),
        sa.ForeignKeyConstraint(["decision_id"], ["career_decisions.decision_id"]),
        sa.ForeignKeyConstraint(
            ["recommendation_id"], ["decision_recommendations.recommendation_id"]
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("support_case_id"),
    )
    op.create_index("ix_support_cases_decision", "support_cases", ["decision_id"])
    op.create_index("ix_support_cases_recommendation", "support_cases", ["recommendation_id"])
    op.create_index("ix_support_cases_subject", "support_cases", ["subject_type", "subject_id"])
    op.create_index("ix_support_cases_type_status", "support_cases", ["case_type", "status"])
    op.create_index("ix_support_cases_user_status", "support_cases", ["user_id", "status"])

    op.create_table(
        "support_case_events",
        sa.Column("support_case_event_id", sa.String(length=64), nullable=False),
        sa.Column("support_case_id", sa.String(length=64), nullable=False),
        sa.Column("actor_user_id", sa.String(length=64), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("before_state", sa.JSON(), nullable=True),
        sa.Column("after_state", sa.JSON(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["support_case_id"], ["support_cases.support_case_id"]),
        sa.PrimaryKeyConstraint("support_case_event_id"),
    )
    op.create_index("ix_support_case_events_actor", "support_case_events", ["actor_user_id"])
    op.create_index(
        "ix_support_case_events_case", "support_case_events", ["support_case_id", "created_at"]
    )

    op.create_table(
        "product_entitlement_grants",
        sa.Column("entitlement_grant_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("feature_key", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_ref_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_type IN ('beta_access', 'free_access', 'promotional_access', "
            "'paid_plan', 'institutional_access', 'advisor_university_access', "
            "'administrative_grant')",
            name="ck_product_entitlements_source",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'expired', 'revoked')",
            name="ck_product_entitlements_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("entitlement_grant_id"),
    )
    op.create_index(
        "ix_product_entitlements_source",
        "product_entitlement_grants",
        ["source_type", "source_ref_id"],
    )
    op.create_index("ix_product_entitlements_status", "product_entitlement_grants", ["status"])
    op.create_index(
        "ix_product_entitlements_user_feature",
        "product_entitlement_grants",
        ["user_id", "feature_key"],
    )

    op.create_table(
        "commercial_experiment_signals",
        sa.Column("signal_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column("experiment_key", sa.String(length=128), nullable=False),
        sa.Column("variant_key", sa.String(length=128), nullable=False),
        sa.Column("offer_key", sa.String(length=64), nullable=False),
        sa.Column("signal_type", sa.String(length=64), nullable=False),
        sa.Column("product_surface", sa.String(length=128), nullable=True),
        sa.Column("conversion_ref", sa.String(length=128), nullable=True),
        sa.Column("qualitative_feedback", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "offer_key IN ('one_time_decision_report', 'active_search_subscription', "
            "'premium_scenarios', 'university_advisor_access')",
            name="ck_commercial_signals_offer",
        ),
        sa.CheckConstraint(
            "signal_type IN ('exposed', 'interested', 'not_interested', 'learn_more', "
            "'converted', 'activated', 'canceled')",
            name="ck_commercial_signals_type",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("signal_id"),
    )
    op.create_index(
        "ix_commercial_signals_experiment",
        "commercial_experiment_signals",
        ["experiment_key", "variant_key"],
    )
    op.create_index(
        "ix_commercial_signals_offer", "commercial_experiment_signals", ["offer_key", "signal_type"]
    )
    op.create_index(
        "ix_commercial_signals_user_created",
        "commercial_experiment_signals",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_commercial_signals_user_created", table_name="commercial_experiment_signals")
    op.drop_index("ix_commercial_signals_offer", table_name="commercial_experiment_signals")
    op.drop_index("ix_commercial_signals_experiment", table_name="commercial_experiment_signals")
    op.drop_table("commercial_experiment_signals")
    op.drop_index("ix_product_entitlements_user_feature", table_name="product_entitlement_grants")
    op.drop_index("ix_product_entitlements_status", table_name="product_entitlement_grants")
    op.drop_index("ix_product_entitlements_source", table_name="product_entitlement_grants")
    op.drop_table("product_entitlement_grants")
    op.drop_index("ix_support_case_events_case", table_name="support_case_events")
    op.drop_index("ix_support_case_events_actor", table_name="support_case_events")
    op.drop_table("support_case_events")
    op.drop_index("ix_support_cases_user_status", table_name="support_cases")
    op.drop_index("ix_support_cases_type_status", table_name="support_cases")
    op.drop_index("ix_support_cases_subject", table_name="support_cases")
    op.drop_index("ix_support_cases_recommendation", table_name="support_cases")
    op.drop_index("ix_support_cases_decision", table_name="support_cases")
    op.drop_table("support_cases")
    op.drop_index("ix_strategy_changes_user_occurred", table_name="strategy_changes")
    op.drop_index("ix_strategy_changes_recommendation", table_name="strategy_changes")
    op.drop_index("ix_strategy_changes_decision", table_name="strategy_changes")
    op.drop_table("strategy_changes")
    op.drop_index("ix_decision_reflections_user_created", table_name="decision_reflections")
    op.drop_index("ix_decision_reflections_recommendation", table_name="decision_reflections")
    op.drop_index("ix_decision_reflections_decision", table_name="decision_reflections")
    op.drop_table("decision_reflections")
    op.drop_index("ix_recommendation_feedback_user_created", table_name="recommendation_feedback")
    op.drop_index("ix_recommendation_feedback_recommendation", table_name="recommendation_feedback")
    op.drop_index("ix_recommendation_feedback_decision", table_name="recommendation_feedback")
    op.drop_index("ix_recommendation_feedback_cohort", table_name="recommendation_feedback")
    op.drop_table("recommendation_feedback")
    op.drop_index("ix_experiment_assignments_user", table_name="experiment_assignments")
    op.drop_index("ix_experiment_assignments_experiment", table_name="experiment_assignments")
    op.drop_table("experiment_assignments")
    op.drop_index("ix_beta_memberships_user_status", table_name="beta_cohort_memberships")
    op.drop_index("ix_beta_memberships_cohort_status", table_name="beta_cohort_memberships")
    op.drop_table("beta_cohort_memberships")
    op.drop_index("ix_feature_gates_mode", table_name="product_feature_gates")
    op.drop_index("ix_feature_gates_enabled", table_name="product_feature_gates")
    op.drop_table("product_feature_gates")
    op.drop_index("ix_beta_cohorts_status", table_name="beta_cohorts")
    op.drop_table("beta_cohorts")
    op.drop_index("ix_product_user_visits_user_started", table_name="product_user_visits")
    op.drop_index("ix_product_user_visits_user_last_seen", table_name="product_user_visits")
    op.drop_index("ix_product_user_visits_return_event", table_name="product_user_visits")
    op.drop_index("ix_product_user_visits_cohort", table_name="product_user_visits")
    op.drop_table("product_user_visits")
    op.drop_index("ix_product_events_user_time", table_name="product_analytics_events")
    op.drop_index("ix_product_events_type_time", table_name="product_analytics_events")
    op.drop_index("ix_product_events_recommendation", table_name="product_analytics_events")
    op.drop_index("ix_product_events_experiment", table_name="product_analytics_events")
    op.drop_index("ix_product_events_decision", table_name="product_analytics_events")
    op.drop_index("ix_product_events_cohort_type", table_name="product_analytics_events")
    op.drop_table("product_analytics_events")
