"""Add Layer 26C career-agent tool approval records.

Revision ID: 0028_career_agent_tool_approvals
Revises: 0027_career_agent_memory
Create Date: 2026-06-30
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0028_career_agent_tool_approvals"
down_revision = "0027_career_agent_memory"
branch_labels = None
depends_on = None

CAREER_AGENT_TOOL_TYPE_SQL = (
    "'reminder', "
    "'career_report_export', "
    "'watchlist_update_suggestion', "
    "'notification_preference', "
    "'outreach_message_draft', "
    "'application_prep_checklist', "
    "'job_application_submission'"
)

CAREER_AGENT_TOOL_STATUS_SQL = (
    "'suggested', "
    "'drafted', "
    "'preview_ready', "
    "'awaiting_user_approval', "
    "'approved', "
    "'executed', "
    "'rejected', "
    "'expired', "
    "'blocked'"
)

CAREER_AGENT_ACTION_BOUNDARY_SQL = (
    "'read_only_preview', "
    "'user_state_change', "
    "'reminder_creation', "
    "'user_data_export', "
    "'watchlist_mutation', "
    "'notification_change', "
    "'external_contact', "
    "'application_submission'"
)

CAREER_AGENT_TOOL_PRIVACY_SQL = (
    "'public_safe', "
    "'user_private', "
    "'external_contact', "
    "'blocked'"
)


def upgrade() -> None:
    op.create_table(
        "career_agent_tool_records",
        sa.Column("career_agent_tool_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("tool_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("action_boundary", sa.String(length=64), nullable=False),
        sa.Column("privacy_classification", sa.String(length=64), nullable=False),
        sa.Column("approval_required", sa.Boolean(), nullable=False),
        sa.Column("explicit_user_approval_required", sa.Boolean(), nullable=False),
        sa.Column("approval_reason", sa.String(length=1024), nullable=False),
        sa.Column("proposed_action_summary", sa.String(length=2048), nullable=False),
        sa.Column("preview_payload", sa.JSON(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("freshness", sa.JSON(), nullable=False),
        sa.Column("uncertainty", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("source_answer_id", sa.String(length=160), nullable=True),
        sa.Column("source_plan_id", sa.String(length=160), nullable=True),
        sa.Column("runtime_execution_performed", sa.Boolean(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"tool_type IN ({CAREER_AGENT_TOOL_TYPE_SQL})",
            name="ck_career_agent_tool_records_type",
        ),
        sa.CheckConstraint(
            f"status IN ({CAREER_AGENT_TOOL_STATUS_SQL})",
            name="ck_career_agent_tool_records_status",
        ),
        sa.CheckConstraint(
            f"action_boundary IN ({CAREER_AGENT_ACTION_BOUNDARY_SQL})",
            name="ck_career_agent_tool_records_boundary",
        ),
        sa.CheckConstraint(
            f"privacy_classification IN ({CAREER_AGENT_TOOL_PRIVACY_SQL})",
            name="ck_career_agent_tool_records_privacy",
        ),
        sa.CheckConstraint(
            "runtime_execution_performed = false",
            name="ck_career_agent_tool_records_no_runtime_execution",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("career_agent_tool_id"),
    )
    op.create_index(
        "ix_career_agent_tool_records_created_at",
        "career_agent_tool_records",
        ["created_at"],
    )
    op.create_index(
        "ix_career_agent_tool_records_status",
        "career_agent_tool_records",
        ["status"],
    )
    op.create_index(
        "ix_career_agent_tool_records_tool_type",
        "career_agent_tool_records",
        ["tool_type"],
    )
    op.create_index(
        "ix_career_agent_tool_records_user_id",
        "career_agent_tool_records",
        ["user_id"],
    )

    op.create_table(
        "career_agent_tool_audit_events",
        sa.Column("career_agent_tool_audit_event_id", sa.String(length=64), nullable=False),
        sa.Column("career_agent_tool_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["career_agent_tool_id"],
            ["career_agent_tool_records.career_agent_tool_id"],
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("career_agent_tool_audit_event_id"),
    )
    op.create_index(
        "ix_career_agent_tool_audit_created_at",
        "career_agent_tool_audit_events",
        ["created_at"],
    )
    op.create_index(
        "ix_career_agent_tool_audit_tool",
        "career_agent_tool_audit_events",
        ["career_agent_tool_id"],
    )
    op.create_index(
        "ix_career_agent_tool_audit_user",
        "career_agent_tool_audit_events",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_career_agent_tool_audit_user",
        table_name="career_agent_tool_audit_events",
    )
    op.drop_index(
        "ix_career_agent_tool_audit_tool",
        table_name="career_agent_tool_audit_events",
    )
    op.drop_index(
        "ix_career_agent_tool_audit_created_at",
        table_name="career_agent_tool_audit_events",
    )
    op.drop_table("career_agent_tool_audit_events")

    op.drop_index(
        "ix_career_agent_tool_records_user_id",
        table_name="career_agent_tool_records",
    )
    op.drop_index(
        "ix_career_agent_tool_records_tool_type",
        table_name="career_agent_tool_records",
    )
    op.drop_index(
        "ix_career_agent_tool_records_status",
        table_name="career_agent_tool_records",
    )
    op.drop_index(
        "ix_career_agent_tool_records_created_at",
        table_name="career_agent_tool_records",
    )
    op.drop_table("career_agent_tool_records")
