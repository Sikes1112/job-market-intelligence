"""Add Layer 27 partner standards submissions.

Revision ID: 0029_data_standards_partner_submissions
Revises: 0028_career_agent_tool_approvals
Create Date: 2026-06-30
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0029_data_standards_partner_submissions"
down_revision = "0028_career_agent_tool_approvals"
branch_labels = None
depends_on = None

PARTNER_SUBMITTER_TYPE_SQL = (
    "'employer', "
    "'education_institution', "
    "'workforce_board', "
    "'data_vendor', "
    "'nonprofit_partner', "
    "'government_agency'"
)

PARTNER_VALIDATION_STATUS_SQL = (
    "'received', "
    "'validated', "
    "'rejected', "
    "'needs_review', "
    "'certified', "
    "'archived'"
)


def upgrade() -> None:
    op.create_table(
        "data_standard_partner_submissions",
        sa.Column("partner_submission_id", sa.String(length=128), nullable=False),
        sa.Column("partner_id", sa.String(length=128), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("submitter_type", sa.String(length=64), nullable=False),
        sa.Column("validation_status", sa.String(length=32), nullable=False),
        sa.Column("records_json", sa.JSON(), nullable=False),
        sa.Column("source_refs_json", sa.JSON(), nullable=False),
        sa.Column("freshness_json", sa.JSON(), nullable=False),
        sa.Column("confidence_json", sa.JSON(), nullable=False),
        sa.Column("warnings_json", sa.JSON(), nullable=False),
        sa.Column("validation_errors_json", sa.JSON(), nullable=False),
        sa.Column("raw_submission_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"submitter_type IN ({PARTNER_SUBMITTER_TYPE_SQL})",
            name="ck_data_standard_partner_submissions_submitter_type",
        ),
        sa.CheckConstraint(
            f"validation_status IN ({PARTNER_VALIDATION_STATUS_SQL})",
            name="ck_data_standard_partner_submissions_validation_status",
        ),
        sa.CheckConstraint(
            "schema_version = 'partner_submission_v1'",
            name="ck_data_standard_partner_submissions_schema_version",
        ),
        sa.PrimaryKeyConstraint("partner_submission_id"),
    )
    op.create_index(
        "ix_data_standard_partner_submissions_created_at",
        "data_standard_partner_submissions",
        ["created_at"],
    )
    op.create_index(
        "ix_data_standard_partner_submissions_partner",
        "data_standard_partner_submissions",
        ["partner_id"],
    )
    op.create_index(
        "ix_data_standard_partner_submissions_status",
        "data_standard_partner_submissions",
        ["validation_status"],
    )
    op.create_index(
        "ix_data_standard_partner_submissions_submitted_at",
        "data_standard_partner_submissions",
        ["submitted_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_data_standard_partner_submissions_submitted_at",
        table_name="data_standard_partner_submissions",
    )
    op.drop_index(
        "ix_data_standard_partner_submissions_status",
        table_name="data_standard_partner_submissions",
    )
    op.drop_index(
        "ix_data_standard_partner_submissions_partner",
        table_name="data_standard_partner_submissions",
    )
    op.drop_index(
        "ix_data_standard_partner_submissions_created_at",
        table_name="data_standard_partner_submissions",
    )
    op.drop_table("data_standard_partner_submissions")
