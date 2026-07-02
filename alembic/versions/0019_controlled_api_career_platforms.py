"""Add Layer 17 controlled API access and career platform records.

Revision ID: 0019_controlled_api_career_platforms
Revises: 0018_partner_import_governance
Create Date: 2026-06-16
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0019_controlled_api_career_platforms"
down_revision = "0018_partner_import_governance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_clients",
        sa.Column("api_client_id", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("scopes_json", sa.JSON(), nullable=False),
        sa.Column("allowed_origins_json", sa.JSON(), nullable=False),
        sa.Column("rate_limit_count", sa.Integer(), nullable=False),
        sa.Column("rate_limit_window_seconds", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'revoked')",
            name="ck_api_clients_status",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.organization_id"]),
        sa.PrimaryKeyConstraint("api_client_id"),
    )
    op.create_index("ix_api_clients_created_by", "api_clients", ["created_by_user_id"])
    op.create_index("ix_api_clients_org", "api_clients", ["organization_id"])
    op.create_index("ix_api_clients_status", "api_clients", ["status"])

    op.create_table(
        "api_keys",
        sa.Column("api_key_id", sa.String(length=64), nullable=False),
        sa.Column("api_client_id", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=64), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=128), nullable=False),
        sa.Column("display_key", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'revoked')",
            name="ck_api_keys_status",
        ),
        sa.ForeignKeyConstraint(["api_client_id"], ["api_clients.api_client_id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("api_key_id"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index("ix_api_keys_client", "api_keys", ["api_client_id"])
    op.create_index("ix_api_keys_hash", "api_keys", ["key_hash"])
    op.create_index("ix_api_keys_prefix", "api_keys", ["key_prefix"])
    op.create_index("ix_api_keys_status", "api_keys", ["status"])

    op.create_table(
        "api_usage_records",
        sa.Column("api_usage_record_id", sa.String(length=64), nullable=False),
        sa.Column("api_client_id", sa.String(length=64), nullable=True),
        sa.Column("api_key_id", sa.String(length=64), nullable=True),
        sa.Column("route", sa.String(length=255), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("scope", sa.String(length=96), nullable=True),
        sa.Column("decision", sa.String(length=64), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("rate_limit_limit", sa.Integer(), nullable=True),
        sa.Column("rate_limit_remaining", sa.Integer(), nullable=True),
        sa.Column("rate_limit_reset_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ("
            "'allowed', "
            "'missing_scope', "
            "'invalid_key', "
            "'revoked_key', "
            "'rate_limited'"
            ")",
            name="ck_api_usage_records_decision",
        ),
        sa.ForeignKeyConstraint(["api_client_id"], ["api_clients.api_client_id"]),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.api_key_id"]),
        sa.PrimaryKeyConstraint("api_usage_record_id"),
    )
    op.create_index("ix_api_usage_records_client", "api_usage_records", ["api_client_id"])
    op.create_index("ix_api_usage_records_key", "api_usage_records", ["api_key_id"])
    op.create_index(
        "ix_api_usage_records_occurred_at",
        "api_usage_records",
        ["occurred_at"],
    )
    op.create_index("ix_api_usage_records_scope", "api_usage_records", ["scope"])

    op.create_table(
        "api_access_audit_events",
        sa.Column("api_access_audit_event_id", sa.String(length=64), nullable=False),
        sa.Column("api_client_id", sa.String(length=64), nullable=True),
        sa.Column("api_key_id", sa.String(length=64), nullable=True),
        sa.Column("route", sa.String(length=255), nullable=False),
        sa.Column("scope", sa.String(length=96), nullable=True),
        sa.Column("decision", sa.String(length=64), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["api_client_id"], ["api_clients.api_client_id"]),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.api_key_id"]),
        sa.PrimaryKeyConstraint("api_access_audit_event_id"),
    )
    op.create_index(
        "ix_api_access_audit_events_client",
        "api_access_audit_events",
        ["api_client_id"],
    )
    op.create_index(
        "ix_api_access_audit_events_decision",
        "api_access_audit_events",
        ["decision"],
    )
    op.create_index(
        "ix_api_access_audit_events_occurred_at",
        "api_access_audit_events",
        ["occurred_at"],
    )

    op.create_table(
        "career_platform_references",
        sa.Column("career_platform_reference_id", sa.String(length=64), nullable=False),
        sa.Column("platform", sa.String(length=64), nullable=False),
        sa.Column("risk_posture", sa.String(length=64), nullable=False),
        sa.Column("subject_type", sa.String(length=64), nullable=False),
        sa.Column("subject_id", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=True),
        sa.Column("submitted_by_user_id", sa.String(length=64), nullable=False),
        sa.Column("manual_only", sa.Boolean(), nullable=False),
        sa.Column("automation_performed", sa.Boolean(), nullable=False),
        sa.Column("ats_state_created", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        _career_platform_check("ck_career_platform_references_platform", "platform"),
        _career_platform_risk_check(
            "ck_career_platform_references_risk_posture",
            "risk_posture",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.organization_id"]),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("career_platform_reference_id"),
    )
    op.create_index(
        "ix_career_platform_references_org",
        "career_platform_references",
        ["organization_id"],
    )
    op.create_index(
        "ix_career_platform_references_platform",
        "career_platform_references",
        ["platform"],
    )
    op.create_index(
        "ix_career_platform_references_subject",
        "career_platform_references",
        ["subject_type", "subject_id"],
    )
    op.create_index(
        "ix_career_platform_references_user",
        "career_platform_references",
        ["submitted_by_user_id"],
    )

    op.create_table(
        "career_platform_exports",
        sa.Column("career_platform_export_id", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=True),
        sa.Column("platform", sa.String(length=64), nullable=False),
        sa.Column("risk_posture", sa.String(length=64), nullable=False),
        sa.Column("export_mode", sa.String(length=64), nullable=False),
        sa.Column("rows_json", sa.JSON(), nullable=False),
        sa.Column("receipt_json", sa.JSON(), nullable=False),
        sa.Column("manual_only", sa.Boolean(), nullable=False),
        sa.Column("automation_performed", sa.Boolean(), nullable=False),
        sa.Column("ats_state_created", sa.Boolean(), nullable=False),
        sa.Column("application_status_created", sa.Boolean(), nullable=False),
        sa.Column("recruiter_outreach_created", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        _career_platform_check("ck_career_platform_exports_platform", "platform"),
        _career_platform_risk_check(
            "ck_career_platform_exports_risk_posture",
            "risk_posture",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.organization_id"]),
        sa.PrimaryKeyConstraint("career_platform_export_id"),
    )
    op.create_index(
        "ix_career_platform_exports_org",
        "career_platform_exports",
        ["organization_id"],
    )
    op.create_index(
        "ix_career_platform_exports_platform",
        "career_platform_exports",
        ["platform"],
    )
    op.create_index(
        "ix_career_platform_exports_user",
        "career_platform_exports",
        ["created_by_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_career_platform_exports_user", table_name="career_platform_exports")
    op.drop_index("ix_career_platform_exports_platform", table_name="career_platform_exports")
    op.drop_index("ix_career_platform_exports_org", table_name="career_platform_exports")
    op.drop_table("career_platform_exports")

    op.drop_index("ix_career_platform_references_user", table_name="career_platform_references")
    op.drop_index("ix_career_platform_references_subject", table_name="career_platform_references")
    op.drop_index("ix_career_platform_references_platform", table_name="career_platform_references")
    op.drop_index("ix_career_platform_references_org", table_name="career_platform_references")
    op.drop_table("career_platform_references")

    op.drop_index("ix_api_access_audit_events_occurred_at", table_name="api_access_audit_events")
    op.drop_index("ix_api_access_audit_events_decision", table_name="api_access_audit_events")
    op.drop_index("ix_api_access_audit_events_client", table_name="api_access_audit_events")
    op.drop_table("api_access_audit_events")

    op.drop_index("ix_api_usage_records_scope", table_name="api_usage_records")
    op.drop_index("ix_api_usage_records_occurred_at", table_name="api_usage_records")
    op.drop_index("ix_api_usage_records_key", table_name="api_usage_records")
    op.drop_index("ix_api_usage_records_client", table_name="api_usage_records")
    op.drop_table("api_usage_records")

    op.drop_index("ix_api_keys_status", table_name="api_keys")
    op.drop_index("ix_api_keys_prefix", table_name="api_keys")
    op.drop_index("ix_api_keys_hash", table_name="api_keys")
    op.drop_index("ix_api_keys_client", table_name="api_keys")
    op.drop_table("api_keys")

    op.drop_index("ix_api_clients_status", table_name="api_clients")
    op.drop_index("ix_api_clients_org", table_name="api_clients")
    op.drop_index("ix_api_clients_created_by", table_name="api_clients")
    op.drop_table("api_clients")


def _career_platform_check(name: str, column_name: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(
        f"{column_name} IN ("
        "'linkedin', "
        "'handshake', "
        "'university_job_board', "
        "'company_career_page', "
        "'other_public_career_site'"
        ")",
        name=name,
    )


def _career_platform_risk_check(name: str, column_name: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(
        f"{column_name} IN ("
        "'safe_manual', "
        "'export_only', "
        "'deep_link_only', "
        "'official_api_only', "
        "'requires_review', "
        "'blocked_hostile_tos', "
        "'deferred'"
        ")",
        name=name,
    )
