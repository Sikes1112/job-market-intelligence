"""Add Layer 17 ecosystem integration export and reminder records.

Revision ID: 0017_ecosystem_integrations_foundation
Revises: 0016_institutional_reports_data_requests
Create Date: 2026-06-16
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0017_ecosystem_integrations_foundation"
down_revision = "0016_institutional_reports_data_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_exports",
        sa.Column("integration_export_id", sa.String(length=64), nullable=False),
        sa.Column("owner_user_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=True),
        sa.Column("product_object_type", sa.String(length=64), nullable=False),
        sa.Column("product_object_id", sa.String(length=255), nullable=False),
        sa.Column("destination", sa.String(length=64), nullable=False),
        sa.Column("capability", sa.String(length=64), nullable=False),
        sa.Column("risk_posture", sa.String(length=64), nullable=False),
        sa.Column("export_format", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("file_text", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("receipt_json", sa.JSON(), nullable=False),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "destination IN ('csv', 'pdf', 'google_sheets', 'notion', 'airtable')",
            name="ck_integration_exports_destination",
        ),
        sa.CheckConstraint(
            "capability IN ('export_file', 'prepared_payload')",
            name="ck_integration_exports_capability",
        ),
        sa.CheckConstraint(
            "risk_posture IN ("
            "'local_download_only', "
            "'prepared_no_sync', "
            "'unsupported_deferred'"
            ")",
            name="ck_integration_exports_risk_posture",
        ),
        sa.CheckConstraint(
            "export_format IN ("
            "'csv', "
            "'pdf', "
            "'prepared_google_sheets', "
            "'prepared_notion', "
            "'prepared_airtable'"
            ")",
            name="ck_integration_exports_format",
        ),
        sa.CheckConstraint(
            "product_object_type IN ("
            "'region', "
            "'company', "
            "'comparison', "
            "'recommendation_strategy', "
            "'institutional_dashboard', "
            "'institutional_report'"
            ")",
            name="ck_integration_exports_product_object_type",
        ),
        sa.CheckConstraint(
            "status IN ('created', 'blocked', 'deferred')",
            name="ck_integration_exports_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.organization_id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("integration_export_id"),
    )
    op.create_index(
        "ix_integration_exports_created_at",
        "integration_exports",
        ["created_at"],
    )
    op.create_index(
        "ix_integration_exports_object",
        "integration_exports",
        ["product_object_type", "product_object_id"],
    )
    op.create_index(
        "ix_integration_exports_org",
        "integration_exports",
        ["organization_id"],
    )
    op.create_index(
        "ix_integration_exports_owner",
        "integration_exports",
        ["owner_user_id"],
    )

    op.create_table(
        "integration_reminders",
        sa.Column("integration_reminder_id", sa.String(length=64), nullable=False),
        sa.Column("owner_user_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=True),
        sa.Column("product_object_type", sa.String(length=64), nullable=False),
        sa.Column("product_object_id", sa.String(length=255), nullable=False),
        sa.Column("reminder_type", sa.String(length=64), nullable=False),
        sa.Column("destination", sa.String(length=64), nullable=False),
        sa.Column("capability", sa.String(length=64), nullable=False),
        sa.Column("risk_posture", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("ics_content", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("receipt_json", sa.JSON(), nullable=False),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "destination IN ('ics_calendar')",
            name="ck_integration_reminders_destination",
        ),
        sa.CheckConstraint(
            "capability IN ('calendar_file')",
            name="ck_integration_reminders_capability",
        ),
        sa.CheckConstraint(
            "risk_posture IN ('calendar_file_no_sync', 'unsupported_deferred')",
            name="ck_integration_reminders_risk_posture",
        ),
        sa.CheckConstraint(
            "reminder_type IN ("
            "'application_window', "
            "'internship_deadline', "
            "'follow_up', "
            "'market_refresh_alert', "
            "'institutional_report_review', "
            "'data_request_due'"
            ")",
            name="ck_integration_reminders_type",
        ),
        sa.CheckConstraint(
            "product_object_type IN ("
            "'region', "
            "'company', "
            "'comparison', "
            "'recommendation_strategy', "
            "'institutional_dashboard', "
            "'institutional_report'"
            ")",
            name="ck_integration_reminders_product_object_type",
        ),
        sa.CheckConstraint(
            "status IN ('created', 'blocked', 'deferred')",
            name="ck_integration_reminders_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.organization_id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("integration_reminder_id"),
    )
    op.create_index(
        "ix_integration_reminders_due_at",
        "integration_reminders",
        ["due_at"],
    )
    op.create_index(
        "ix_integration_reminders_object",
        "integration_reminders",
        ["product_object_type", "product_object_id"],
    )
    op.create_index(
        "ix_integration_reminders_org",
        "integration_reminders",
        ["organization_id"],
    )
    op.create_index(
        "ix_integration_reminders_owner",
        "integration_reminders",
        ["owner_user_id"],
    )
    op.create_index(
        "ix_integration_reminders_type",
        "integration_reminders",
        ["reminder_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_integration_reminders_type", table_name="integration_reminders")
    op.drop_index("ix_integration_reminders_owner", table_name="integration_reminders")
    op.drop_index("ix_integration_reminders_org", table_name="integration_reminders")
    op.drop_index("ix_integration_reminders_object", table_name="integration_reminders")
    op.drop_index("ix_integration_reminders_due_at", table_name="integration_reminders")
    op.drop_table("integration_reminders")

    op.drop_index("ix_integration_exports_owner", table_name="integration_exports")
    op.drop_index("ix_integration_exports_org", table_name="integration_exports")
    op.drop_index("ix_integration_exports_object", table_name="integration_exports")
    op.drop_index("ix_integration_exports_created_at", table_name="integration_exports")
    op.drop_table("integration_exports")
