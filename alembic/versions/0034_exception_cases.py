"""Add Layer 30E exception cases.

Revision ID: 0034_exception_cases
Revises: 0033_user_reports_rechecks
Create Date: 2026-07-08
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0034_exception_cases"
down_revision = "0033_user_reports_rechecks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exception_cases",
        sa.Column("exception_case_id", sa.String(length=128), nullable=False),
        sa.Column("subject_type", sa.String(length=64), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("exception_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("reason_codes_json", sa.JSON(), nullable=False),
        sa.Column("summary", sa.String(length=512), nullable=False),
        sa.Column("related_user_report_id", sa.String(length=128), nullable=True),
        sa.Column("related_recheck_job_id", sa.String(length=128), nullable=True),
        sa.Column("related_trust_assessment_id", sa.String(length=128), nullable=True),
        sa.Column(
            "related_risk_routing_decision_id",
            sa.String(length=128),
            nullable=True,
        ),
        sa.Column("public_safe_status", sa.String(length=64), nullable=True),
        sa.Column("internal_notes", sa.Text(), nullable=True),
        sa.Column("assigned_owner", sa.String(length=128), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("exception_case_id"),
    )
    op.create_index(
        "ix_exception_cases_subject",
        "exception_cases",
        ["subject_type", "subject_id"],
    )
    op.create_index(
        "ix_exception_cases_type",
        "exception_cases",
        ["exception_type"],
    )
    op.create_index(
        "ix_exception_cases_status",
        "exception_cases",
        ["status"],
    )
    op.create_index(
        "ix_exception_cases_severity",
        "exception_cases",
        ["severity"],
    )
    op.create_index(
        "ix_exception_cases_public_status",
        "exception_cases",
        ["public_safe_status"],
    )
    op.create_index(
        "ix_exception_cases_created_at",
        "exception_cases",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_exception_cases_created_at", table_name="exception_cases")
    op.drop_index("ix_exception_cases_public_status", table_name="exception_cases")
    op.drop_index("ix_exception_cases_severity", table_name="exception_cases")
    op.drop_index("ix_exception_cases_status", table_name="exception_cases")
    op.drop_index("ix_exception_cases_type", table_name="exception_cases")
    op.drop_index("ix_exception_cases_subject", table_name="exception_cases")
    op.drop_table("exception_cases")
