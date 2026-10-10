"""Add Layer 36A complete decision and outcome backend.

Revision ID: 0037_complete_decision_outcome_backend
Revises: 0036_career_identity_backend
Create Date: 2026-09-01
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0037_complete_decision_outcome_backend"
down_revision = "0036_career_identity_backend"
branch_labels = None
depends_on = None

DECISION_TYPE_SQL = (
    "'role_choice', 'company_choice', 'location_choice', 'career_strategy', "
    "'job_search_strategy', 'education_skill_investment', 'offer_comparison', "
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
    "'research', 'application', 'skill_work', 'company_targeting', "
    "'networking_follow_up', 'preparation', 'timing_checkpoint', 'review_task', "
    "'other'"
)
CAREER_ACTION_STATUS_SQL = "'open', 'in_progress', 'completed', 'skipped', 'blocked'"
APPLICATION_STATUS_SQL = (
    "'considering', 'preparing', 'applied', 'response', 'interview', "
    "'final_round', 'rejected', 'withdrawn', 'offer', 'accepted', 'declined'"
)
OUTCOME_TYPE_SQL = (
    "'application_progress', 'offer', 'rejection', 'withdrawal', "
    "'skill_development', 'research_completed', 'networking', 'strategy_change', "
    "'education', 'decision_completed', 'other'"
)
OUTCOME_STATUS_SQL = "'observed', 'reflected', 'superseded'"


def upgrade() -> None:
    op.create_table(
        "decision_context_snapshots",
        sa.Column("context_snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("career_identity_id", sa.String(length=64), nullable=False),
        sa.Column("career_identity_version", sa.Integer(), nullable=False),
        sa.Column("completeness_state", sa.String(length=32), nullable=False),
        sa.Column("sufficiency_state", sa.String(length=32), nullable=False),
        sa.Column("privacy_scope", sa.String(length=64), nullable=False),
        sa.Column("context_payload", sa.JSON(), nullable=False),
        sa.Column("fact_refs", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "career_identity_version >= 1",
            name="ck_decision_context_identity_version",
        ),
        sa.ForeignKeyConstraint(["career_identity_id"], ["career_identities.career_identity_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("context_snapshot_id"),
    )
    op.create_index(
        "ix_decision_context_identity_version",
        "decision_context_snapshots",
        ["career_identity_id", "career_identity_version"],
        unique=False,
    )
    op.create_index(
        "ix_decision_context_user_created",
        "decision_context_snapshots",
        ["user_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "career_decisions",
        sa.Column("decision_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("career_identity_id", sa.String(length=64), nullable=True),
        sa.Column("current_context_snapshot_id", sa.String(length=64), nullable=True),
        sa.Column("current_recommendation_id", sa.String(length=64), nullable=True),
        sa.Column("selected_option_id", sa.String(length=64), nullable=True),
        sa.Column("decision_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("decision_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("target_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("planned_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("time_horizon", sa.String(length=128), nullable=True),
        sa.Column("priorities", sa.JSON(), nullable=False),
        sa.Column("constraints", sa.JSON(), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"decision_type IN ({DECISION_TYPE_SQL})", name="ck_career_decisions_type"
        ),
        sa.CheckConstraint(f"status IN ({DECISION_STATUS_SQL})", name="ck_career_decisions_status"),
        sa.CheckConstraint("current_version >= 1", name="ck_career_decisions_current_version"),
        sa.ForeignKeyConstraint(["career_identity_id"], ["career_identities.career_identity_id"]),
        sa.ForeignKeyConstraint(
            ["current_context_snapshot_id"], ["decision_context_snapshots.context_snapshot_id"]
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("decision_id"),
    )
    op.create_index(
        "ix_career_decisions_identity", "career_decisions", ["career_identity_id"], unique=False
    )
    op.create_index(
        "ix_career_decisions_selected_option",
        "career_decisions",
        ["selected_option_id"],
        unique=False,
    )
    op.create_index(
        "ix_career_decisions_user_status", "career_decisions", ["user_id", "status"], unique=False
    )
    op.create_index(
        "ix_career_decisions_user_updated",
        "career_decisions",
        ["user_id", "updated_at"],
        unique=False,
    )

    op.create_table(
        "decision_options",
        sa.Column("option_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("decision_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scenario", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"status IN ({OPTION_STATUS_SQL})", name="ck_decision_options_status"),
        sa.CheckConstraint("position >= 0", name="ck_decision_options_position"),
        sa.ForeignKeyConstraint(["decision_id"], ["career_decisions.decision_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("option_id"),
    )
    op.create_index(
        "ix_decision_options_decision_position",
        "decision_options",
        ["decision_id", "position"],
        unique=False,
    )
    op.create_index("ix_decision_options_user", "decision_options", ["user_id"], unique=False)

    op.create_table(
        "decision_recommendations",
        sa.Column("recommendation_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("decision_id", sa.String(length=64), nullable=False),
        sa.Column("context_snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("recommended_option_id", sa.String(length=64), nullable=True),
        sa.Column("recommendation_status", sa.String(length=32), nullable=False),
        sa.Column("evidence_sufficiency", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("fit_payload", sa.JSON(), nullable=False),
        sa.Column("comparison_payload", sa.JSON(), nullable=False),
        sa.Column("evidence_payload", sa.JSON(), nullable=False),
        sa.Column("challenge_payload", sa.JSON(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"recommendation_status IN ({RECOMMENDATION_STATUS_SQL})",
            name="ck_decision_recommendations_status",
        ),
        sa.CheckConstraint(
            f"evidence_sufficiency IN ({EVIDENCE_SUFFICIENCY_SQL})",
            name="ck_decision_recommendations_sufficiency",
        ),
        sa.CheckConstraint(
            "confidence IN ('high', 'medium', 'low', 'unknown')",
            name="ck_decision_recommendations_confidence",
        ),
        sa.ForeignKeyConstraint(
            ["context_snapshot_id"], ["decision_context_snapshots.context_snapshot_id"]
        ),
        sa.ForeignKeyConstraint(["decision_id"], ["career_decisions.decision_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("recommendation_id"),
    )
    op.create_index(
        "ix_decision_recommendations_context",
        "decision_recommendations",
        ["context_snapshot_id"],
        unique=False,
    )
    op.create_index(
        "ix_decision_recommendations_decision",
        "decision_recommendations",
        ["decision_id", "generated_at"],
        unique=False,
    )
    op.create_index(
        "ix_decision_recommendations_user", "decision_recommendations", ["user_id"], unique=False
    )

    # ``career_decisions`` and ``decision_recommendations`` reference each
    # other. PostgreSQL requires the referenced table to exist when a foreign
    # key is created, so add this side of the cycle only after both tables are
    # present. SQLite's batch mode preserves the same final schema.
    with op.batch_alter_table("career_decisions") as batch_op:
        batch_op.create_foreign_key(
            "fk_career_decisions_current_recommendation",
            "decision_recommendations",
            ["current_recommendation_id"],
            ["recommendation_id"],
        )

    op.create_table(
        "decision_versions",
        sa.Column("decision_version_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("decision_id", sa.String(length=64), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("version_reason", sa.String(length=128), nullable=False),
        sa.Column("decision_snapshot", sa.JSON(), nullable=False),
        sa.Column("options_snapshot", sa.JSON(), nullable=False),
        sa.Column("recommendation_snapshot", sa.JSON(), nullable=True),
        sa.Column("selected_option_id", sa.String(length=64), nullable=True),
        sa.Column("context_snapshot_id", sa.String(length=64), nullable=True),
        sa.Column("user_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version_number >= 1", name="ck_decision_versions_number"),
        sa.ForeignKeyConstraint(
            ["context_snapshot_id"], ["decision_context_snapshots.context_snapshot_id"]
        ),
        sa.ForeignKeyConstraint(["decision_id"], ["career_decisions.decision_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("decision_version_id"),
        sa.UniqueConstraint(
            "decision_id", "version_number", name="uq_decision_versions_decision_number"
        ),
    )
    op.create_index(
        "ix_decision_versions_decision_created",
        "decision_versions",
        ["decision_id", "created_at"],
        unique=False,
    )
    op.create_index("ix_decision_versions_user", "decision_versions", ["user_id"], unique=False)

    op.create_table(
        "career_action_plans",
        sa.Column("action_plan_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("decision_id", sa.String(length=64), nullable=False),
        sa.Column("selected_option_id", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("plan_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"status IN ({ACTION_PLAN_STATUS_SQL})", name="ck_career_action_plans_status"
        ),
        sa.ForeignKeyConstraint(["decision_id"], ["career_decisions.decision_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("action_plan_id"),
    )
    op.create_index(
        "ix_career_action_plans_decision", "career_action_plans", ["decision_id"], unique=False
    )
    op.create_index(
        "ix_career_action_plans_user_status",
        "career_action_plans",
        ["user_id", "status"],
        unique=False,
    )

    op.create_table(
        "career_actions",
        sa.Column("action_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("action_plan_id", sa.String(length=64), nullable=True),
        sa.Column("decision_id", sa.String(length=64), nullable=True),
        sa.Column("option_id", sa.String(length=64), nullable=True),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"action_type IN ({CAREER_ACTION_TYPE_SQL})", name="ck_career_actions_type"
        ),
        sa.CheckConstraint(
            f"status IN ({CAREER_ACTION_STATUS_SQL})", name="ck_career_actions_status"
        ),
        sa.CheckConstraint(
            "priority IS NULL OR priority BETWEEN 1 AND 5", name="ck_career_actions_priority"
        ),
        sa.CheckConstraint("position >= 0", name="ck_career_actions_position"),
        sa.ForeignKeyConstraint(["action_plan_id"], ["career_action_plans.action_plan_id"]),
        sa.ForeignKeyConstraint(["decision_id"], ["career_decisions.decision_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("action_id"),
    )
    op.create_index("ix_career_actions_decision", "career_actions", ["decision_id"], unique=False)
    op.create_index("ix_career_actions_due", "career_actions", ["due_at"], unique=False)
    op.create_index(
        "ix_career_actions_plan_position",
        "career_actions",
        ["action_plan_id", "position"],
        unique=False,
    )
    op.create_index(
        "ix_career_actions_user_status", "career_actions", ["user_id", "status"], unique=False
    )

    op.create_table(
        "career_applications",
        sa.Column("application_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("decision_id", sa.String(length=64), nullable=True),
        sa.Column("action_id", sa.String(length=64), nullable=True),
        sa.Column("option_id", sa.String(length=64), nullable=True),
        sa.Column("company_id", sa.String(length=64), nullable=True),
        sa.Column("region_id", sa.String(length=64), nullable=True),
        sa.Column("role_title", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("status_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("follow_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"status IN ({APPLICATION_STATUS_SQL})", name="ck_career_applications_status"
        ),
        sa.ForeignKeyConstraint(["action_id"], ["career_actions.action_id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.company_id"]),
        sa.ForeignKeyConstraint(["decision_id"], ["career_decisions.decision_id"]),
        sa.ForeignKeyConstraint(["region_id"], ["regions.region_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("application_id"),
    )
    op.create_index(
        "ix_career_applications_company", "career_applications", ["company_id"], unique=False
    )
    op.create_index(
        "ix_career_applications_decision", "career_applications", ["decision_id"], unique=False
    )
    op.create_index(
        "ix_career_applications_follow_up", "career_applications", ["follow_up_at"], unique=False
    )
    op.create_index(
        "ix_career_applications_user_status",
        "career_applications",
        ["user_id", "status"],
        unique=False,
    )

    op.create_table(
        "career_application_transitions",
        sa.Column("transition_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("application_id", sa.String(length=64), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("transitioned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"to_status IN ({APPLICATION_STATUS_SQL})", name="ck_application_transitions_to_status"
        ),
        sa.CheckConstraint(
            f"from_status IS NULL OR from_status IN ({APPLICATION_STATUS_SQL})",
            name="ck_application_transitions_from_status",
        ),
        sa.ForeignKeyConstraint(["application_id"], ["career_applications.application_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("transition_id"),
    )
    op.create_index(
        "ix_application_transitions_application",
        "career_application_transitions",
        ["application_id", "transitioned_at"],
        unique=False,
    )
    op.create_index(
        "ix_application_transitions_user",
        "career_application_transitions",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "career_outcomes",
        sa.Column("outcome_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("decision_id", sa.String(length=64), nullable=True),
        sa.Column("action_id", sa.String(length=64), nullable=True),
        sa.Column("application_id", sa.String(length=64), nullable=True),
        sa.Column("option_id", sa.String(length=64), nullable=True),
        sa.Column("recommendation_id", sa.String(length=64), nullable=True),
        sa.Column("outcome_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reflection", sa.Text(), nullable=True),
        sa.Column("evidence_payload", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"outcome_type IN ({OUTCOME_TYPE_SQL})", name="ck_career_outcomes_type"),
        sa.CheckConstraint(f"status IN ({OUTCOME_STATUS_SQL})", name="ck_career_outcomes_status"),
        sa.ForeignKeyConstraint(["action_id"], ["career_actions.action_id"]),
        sa.ForeignKeyConstraint(["application_id"], ["career_applications.application_id"]),
        sa.ForeignKeyConstraint(["decision_id"], ["career_decisions.decision_id"]),
        sa.ForeignKeyConstraint(
            ["recommendation_id"], ["decision_recommendations.recommendation_id"]
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("outcome_id"),
    )
    op.create_index(
        "ix_career_outcomes_application", "career_outcomes", ["application_id"], unique=False
    )
    op.create_index("ix_career_outcomes_decision", "career_outcomes", ["decision_id"], unique=False)
    op.create_index(
        "ix_career_outcomes_user_occurred",
        "career_outcomes",
        ["user_id", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_career_outcomes_user_occurred", table_name="career_outcomes")
    op.drop_index("ix_career_outcomes_decision", table_name="career_outcomes")
    op.drop_index("ix_career_outcomes_application", table_name="career_outcomes")
    op.drop_table("career_outcomes")

    op.drop_index("ix_application_transitions_user", table_name="career_application_transitions")
    op.drop_index(
        "ix_application_transitions_application", table_name="career_application_transitions"
    )
    op.drop_table("career_application_transitions")

    op.drop_index("ix_career_applications_user_status", table_name="career_applications")
    op.drop_index("ix_career_applications_follow_up", table_name="career_applications")
    op.drop_index("ix_career_applications_decision", table_name="career_applications")
    op.drop_index("ix_career_applications_company", table_name="career_applications")
    op.drop_table("career_applications")

    op.drop_index("ix_career_actions_user_status", table_name="career_actions")
    op.drop_index("ix_career_actions_plan_position", table_name="career_actions")
    op.drop_index("ix_career_actions_due", table_name="career_actions")
    op.drop_index("ix_career_actions_decision", table_name="career_actions")
    op.drop_table("career_actions")

    op.drop_index("ix_career_action_plans_user_status", table_name="career_action_plans")
    op.drop_index("ix_career_action_plans_decision", table_name="career_action_plans")
    op.drop_table("career_action_plans")

    op.drop_index("ix_decision_versions_user", table_name="decision_versions")
    op.drop_index("ix_decision_versions_decision_created", table_name="decision_versions")
    op.drop_table("decision_versions")

    with op.batch_alter_table("career_decisions") as batch_op:
        batch_op.drop_constraint("fk_career_decisions_current_recommendation", type_="foreignkey")

    op.drop_index("ix_decision_recommendations_user", table_name="decision_recommendations")
    op.drop_index("ix_decision_recommendations_decision", table_name="decision_recommendations")
    op.drop_index("ix_decision_recommendations_context", table_name="decision_recommendations")
    op.drop_table("decision_recommendations")

    op.drop_index("ix_decision_options_user", table_name="decision_options")
    op.drop_index("ix_decision_options_decision_position", table_name="decision_options")
    op.drop_table("decision_options")

    op.drop_index("ix_career_decisions_user_updated", table_name="career_decisions")
    op.drop_index("ix_career_decisions_user_status", table_name="career_decisions")
    op.drop_index("ix_career_decisions_selected_option", table_name="career_decisions")
    op.drop_index("ix_career_decisions_identity", table_name="career_decisions")
    op.drop_table("career_decisions")

    op.drop_index("ix_decision_context_user_created", table_name="decision_context_snapshots")
    op.drop_index("ix_decision_context_identity_version", table_name="decision_context_snapshots")
    op.drop_table("decision_context_snapshots")
