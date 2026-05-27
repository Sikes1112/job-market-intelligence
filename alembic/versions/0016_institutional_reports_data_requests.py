"""Add institutional reports and data request records.

Revision ID: 0016_institutional_reports_data_requests
Revises: 0015_institutional_foundation
Create Date: 2026-05-27
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0016_institutional_reports_data_requests"
down_revision = "0015_institutional_foundation"
branch_labels = None
depends_on = None

AUDIT_ACTION_CHECK = (
    "action IN ("
    "'organization_viewed', "
    "'organization_members_viewed', "
    "'organization_member_added', "
    "'organization_member_updated', "
    "'institution_dashboard_viewed', "
    "'advisor_compare_regions_used', "
    "'advisor_compare_industries_used', "
    "'advisor_compare_companies_used', "
    "'advisor_compare_career_stages_used', "
    "'advisor_application_timing_used', "
    "'institutional_report_generated', "
    "'institutional_report_viewed', "
    "'institutional_reports_listed', "
    "'institutional_data_request_created', "
    "'institutional_data_requests_listed'"
    ")"
)

AUDIT_ACTION_CHECK_DOWNGRADE = (
    "action IN ("
    "'organization_viewed', "
    "'organization_members_viewed', "
    "'organization_member_added', "
    "'organization_member_updated', "
    "'institution_dashboard_viewed', "
    "'advisor_compare_regions_used', "
    "'advisor_compare_industries_used', "
    "'advisor_compare_companies_used', "
    "'advisor_compare_career_stages_used', "
    "'advisor_application_timing_used'"
    ")"
)


def upgrade() -> None:
    with op.batch_alter_table("institutional_audit_logs") as batch_op:
        batch_op.drop_constraint("ck_institutional_audit_logs_action", type_="check")
        batch_op.create_check_constraint(
            "ck_institutional_audit_logs_action",
            AUDIT_ACTION_CHECK,
        )

    op.create_table(
        "institutional_reports",
        sa.Column("institutional_report_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("report_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("generated_by_user_id", sa.String(length=64), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("minimum_group_size", sa.Integer(), nullable=False),
        sa.Column("privacy_summary", sa.JSON(), nullable=True),
        sa.Column("coverage_summary", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "report_type IN ("
            "'career_services', "
            "'program_director', "
            "'workforce_planner', "
            "'economic_development_partner'"
            ")",
            name="ck_institutional_reports_type",
        ),
        sa.CheckConstraint(
            "status IN ('generated', 'archived')",
            name="ck_institutional_reports_status",
        ),
        sa.ForeignKeyConstraint(["generated_by_user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.organization_id"]),
        sa.PrimaryKeyConstraint("institutional_report_id"),
    )
    op.create_index(
        "ix_institutional_reports_generated_at",
        "institutional_reports",
        ["generated_at"],
    )
    op.create_index(
        "ix_institutional_reports_generated_by",
        "institutional_reports",
        ["generated_by_user_id"],
    )
    op.create_index(
        "ix_institutional_reports_org",
        "institutional_reports",
        ["organization_id"],
    )
    op.create_index(
        "ix_institutional_reports_type",
        "institutional_reports",
        ["report_type"],
    )

    op.create_table(
        "institutional_data_requests",
        sa.Column("institutional_data_request_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("requester_user_id", sa.String(length=64), nullable=False),
        sa.Column("request_type", sa.String(length=64), nullable=False),
        sa.Column("subject_type", sa.String(length=32), nullable=False),
        sa.Column("subject_user_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=1024), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "request_type IN ("
            "'organization_export', "
            "'organization_deletion', "
            "'student_export', "
            "'student_deletion'"
            ")",
            name="ck_institutional_data_requests_type",
        ),
        sa.CheckConstraint(
            "subject_type IN ('organization', 'student')",
            name="ck_institutional_data_requests_subject_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'completed', 'canceled')",
            name="ck_institutional_data_requests_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.organization_id"]),
        sa.ForeignKeyConstraint(["requester_user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["subject_user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("institutional_data_request_id"),
    )
    op.create_index(
        "ix_institutional_data_requests_created_at",
        "institutional_data_requests",
        ["created_at"],
    )
    op.create_index(
        "ix_institutional_data_requests_org",
        "institutional_data_requests",
        ["organization_id"],
    )
    op.create_index(
        "ix_institutional_data_requests_requester",
        "institutional_data_requests",
        ["requester_user_id"],
    )
    op.create_index(
        "ix_institutional_data_requests_status",
        "institutional_data_requests",
        ["status"],
    )
    op.create_index(
        "ix_institutional_data_requests_subject_user",
        "institutional_data_requests",
        ["subject_user_id"],
    )
    op.create_index(
        "ix_institutional_data_requests_type",
        "institutional_data_requests",
        ["request_type"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_institutional_data_requests_type",
        table_name="institutional_data_requests",
    )
    op.drop_index(
        "ix_institutional_data_requests_subject_user",
        table_name="institutional_data_requests",
    )
    op.drop_index(
        "ix_institutional_data_requests_status",
        table_name="institutional_data_requests",
    )
    op.drop_index(
        "ix_institutional_data_requests_requester",
        table_name="institutional_data_requests",
    )
    op.drop_index(
        "ix_institutional_data_requests_org",
        table_name="institutional_data_requests",
    )
    op.drop_index(
        "ix_institutional_data_requests_created_at",
        table_name="institutional_data_requests",
    )
    op.drop_table("institutional_data_requests")

    op.drop_index(
        "ix_institutional_reports_type",
        table_name="institutional_reports",
    )
    op.drop_index(
        "ix_institutional_reports_org",
        table_name="institutional_reports",
    )
    op.drop_index(
        "ix_institutional_reports_generated_by",
        table_name="institutional_reports",
    )
    op.drop_index(
        "ix_institutional_reports_generated_at",
        table_name="institutional_reports",
    )
    op.drop_table("institutional_reports")

    with op.batch_alter_table("institutional_audit_logs") as batch_op:
        batch_op.drop_constraint("ck_institutional_audit_logs_action", type_="check")
        batch_op.create_check_constraint(
            "ck_institutional_audit_logs_action",
            AUDIT_ACTION_CHECK_DOWNGRADE,
        )
