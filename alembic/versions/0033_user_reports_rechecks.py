"""Add Layer 30D user reports and automated recheck jobs.

Revision ID: 0033_user_reports_rechecks
Revises: 0032_risk_routing_decisions
Create Date: 2026-07-08
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0033_user_reports_rechecks"
down_revision = "0032_risk_routing_decisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_reports",
        sa.Column("user_report_id", sa.String(length=128), nullable=False),
        sa.Column("subject_type", sa.String(length=64), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("report_type", sa.String(length=64), nullable=False),
        sa.Column("report_reason", sa.Text(), nullable=True),
        sa.Column("reporter_user_id", sa.String(length=128), nullable=True),
        sa.Column("reporter_session_id", sa.String(length=128), nullable=True),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("source_surface", sa.String(length=128), nullable=True),
        sa.Column("related_trust_assessment_id", sa.String(length=128), nullable=True),
        sa.Column(
            "related_risk_routing_decision_id",
            sa.String(length=128),
            nullable=True,
        ),
        sa.Column("created_recheck_job_id", sa.String(length=128), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_report_id"),
    )
    op.create_index(
        "ix_user_reports_subject",
        "user_reports",
        ["subject_type", "subject_id"],
    )
    op.create_index("ix_user_reports_type", "user_reports", ["report_type"])
    op.create_index("ix_user_reports_severity", "user_reports", ["severity"])
    op.create_index("ix_user_reports_status", "user_reports", ["status"])
    op.create_index("ix_user_reports_created_at", "user_reports", ["created_at"])

    op.create_table(
        "automated_recheck_jobs",
        sa.Column(
            "automated_recheck_job_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column("subject_type", sa.String(length=64), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("trigger_type", sa.String(length=64), nullable=False),
        sa.Column("trigger_source", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("priority", sa.String(length=32), nullable=False),
        sa.Column("reason_codes_json", sa.JSON(), nullable=False),
        sa.Column("related_user_report_id", sa.String(length=128), nullable=True),
        sa.Column("related_trust_assessment_id", sa.String(length=128), nullable=True),
        sa.Column(
            "related_risk_routing_decision_id",
            sa.String(length=128),
            nullable=True,
        ),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.String(length=64), nullable=True),
        sa.Column("outcome_reason", sa.String(length=512), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("automated_recheck_job_id"),
    )
    op.create_index(
        "ix_automated_recheck_jobs_subject",
        "automated_recheck_jobs",
        ["subject_type", "subject_id"],
    )
    op.create_index(
        "ix_automated_recheck_jobs_trigger",
        "automated_recheck_jobs",
        ["trigger_type"],
    )
    op.create_index(
        "ix_automated_recheck_jobs_status",
        "automated_recheck_jobs",
        ["status"],
    )
    op.create_index(
        "ix_automated_recheck_jobs_priority",
        "automated_recheck_jobs",
        ["priority"],
    )
    op.create_index(
        "ix_automated_recheck_jobs_scheduled_for",
        "automated_recheck_jobs",
        ["scheduled_for"],
    )
    op.create_index(
        "ix_automated_recheck_jobs_created_at",
        "automated_recheck_jobs",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_automated_recheck_jobs_created_at",
        table_name="automated_recheck_jobs",
    )
    op.drop_index(
        "ix_automated_recheck_jobs_scheduled_for",
        table_name="automated_recheck_jobs",
    )
    op.drop_index(
        "ix_automated_recheck_jobs_priority",
        table_name="automated_recheck_jobs",
    )
    op.drop_index(
        "ix_automated_recheck_jobs_status",
        table_name="automated_recheck_jobs",
    )
    op.drop_index(
        "ix_automated_recheck_jobs_trigger",
        table_name="automated_recheck_jobs",
    )
    op.drop_index(
        "ix_automated_recheck_jobs_subject",
        table_name="automated_recheck_jobs",
    )
    op.drop_table("automated_recheck_jobs")
    op.drop_index("ix_user_reports_created_at", table_name="user_reports")
    op.drop_index("ix_user_reports_status", table_name="user_reports")
    op.drop_index("ix_user_reports_severity", table_name="user_reports")
    op.drop_index("ix_user_reports_type", table_name="user_reports")
    op.drop_index("ix_user_reports_subject", table_name="user_reports")
    op.drop_table("user_reports")
