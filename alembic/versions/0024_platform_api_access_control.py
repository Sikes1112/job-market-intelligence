"""Add Layer 20 Platform API access control.

Revision ID: 0024_platform_api_access_control
Revises: 0023_contribution_governance
Create Date: 2026-06-19
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0024_platform_api_access_control"
down_revision = "0023_contribution_governance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_api_keys",
        sa.Column("platform_api_key_id", sa.String(length=64), nullable=False),
        sa.Column("key_prefix", sa.String(length=24), nullable=False),
        sa.Column("key_hash", sa.String(length=128), nullable=False),
        sa.Column("display_key", sa.String(length=96), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("environment", sa.String(length=16), nullable=False),
        sa.Column("tier", sa.String(length=32), nullable=False),
        sa.Column("product_scopes_json", sa.JSON(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'revoked')",
            name="ck_platform_api_keys_status",
        ),
        sa.CheckConstraint(
            "environment IN ('test', 'live')",
            name="ck_platform_api_keys_environment",
        ),
        sa.CheckConstraint(
            "tier IN ('trial', 'starter', 'growth', 'enterprise')",
            name="ck_platform_api_keys_tier",
        ),
        sa.PrimaryKeyConstraint("platform_api_key_id"),
        sa.UniqueConstraint("key_hash", name="uq_platform_api_keys_hash"),
    )
    op.create_index(
        "ix_platform_api_keys_created_at",
        "platform_api_keys",
        ["created_at"],
    )
    op.create_index(
        "ix_platform_api_keys_environment",
        "platform_api_keys",
        ["environment"],
    )
    op.create_index(
        "ix_platform_api_keys_prefix",
        "platform_api_keys",
        ["key_prefix"],
    )
    op.create_index(
        "ix_platform_api_keys_status",
        "platform_api_keys",
        ["status"],
    )
    op.create_index(
        "ix_platform_api_keys_tier",
        "platform_api_keys",
        ["tier"],
    )

    op.create_table(
        "platform_api_usage_events",
        sa.Column("platform_api_usage_event_id", sa.String(length=64), nullable=False),
        sa.Column("platform_api_key_id", sa.String(length=64), nullable=True),
        sa.Column("key_prefix", sa.String(length=24), nullable=True),
        sa.Column("product_id", sa.String(length=96), nullable=False),
        sa.Column("endpoint", sa.String(length=255), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("request_units", sa.Integer(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("decision_reason", sa.String(length=96), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('allowed', 'denied')",
            name="ck_platform_api_usage_events_outcome",
        ),
        sa.ForeignKeyConstraint(
            ["platform_api_key_id"],
            ["platform_api_keys.platform_api_key_id"],
        ),
        sa.PrimaryKeyConstraint("platform_api_usage_event_id"),
    )
    op.create_index(
        "ix_platform_api_usage_events_key",
        "platform_api_usage_events",
        ["platform_api_key_id"],
    )
    op.create_index(
        "ix_platform_api_usage_events_occurred_at",
        "platform_api_usage_events",
        ["occurred_at"],
    )
    op.create_index(
        "ix_platform_api_usage_events_outcome",
        "platform_api_usage_events",
        ["outcome"],
    )
    op.create_index(
        "ix_platform_api_usage_events_product",
        "platform_api_usage_events",
        ["product_id"],
    )

    op.create_table(
        "platform_api_audit_logs",
        sa.Column("platform_api_audit_log_id", sa.String(length=64), nullable=False),
        sa.Column("platform_api_key_id", sa.String(length=64), nullable=True),
        sa.Column("key_prefix", sa.String(length=24), nullable=True),
        sa.Column("product_id", sa.String(length=96), nullable=True),
        sa.Column("endpoint", sa.String(length=255), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ('allowed', 'denied')",
            name="ck_platform_api_audit_logs_decision",
        ),
        sa.CheckConstraint(
            "event_type IN ("
            "'allowed_request', "
            "'denied_request', "
            "'rate_limited', "
            "'usage_limit_exceeded', "
            "'missing_key', "
            "'invalid_key', "
            "'revoked_key', "
            "'entitlement_denied'"
            ")",
            name="ck_platform_api_audit_logs_event_type",
        ),
        sa.ForeignKeyConstraint(
            ["platform_api_key_id"],
            ["platform_api_keys.platform_api_key_id"],
        ),
        sa.PrimaryKeyConstraint("platform_api_audit_log_id"),
    )
    op.create_index(
        "ix_platform_api_audit_logs_decision",
        "platform_api_audit_logs",
        ["decision"],
    )
    op.create_index(
        "ix_platform_api_audit_logs_event_type",
        "platform_api_audit_logs",
        ["event_type"],
    )
    op.create_index(
        "ix_platform_api_audit_logs_key",
        "platform_api_audit_logs",
        ["platform_api_key_id"],
    )
    op.create_index(
        "ix_platform_api_audit_logs_occurred_at",
        "platform_api_audit_logs",
        ["occurred_at"],
    )
    op.create_index(
        "ix_platform_api_audit_logs_product",
        "platform_api_audit_logs",
        ["product_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_platform_api_audit_logs_product", table_name="platform_api_audit_logs")
    op.drop_index(
        "ix_platform_api_audit_logs_occurred_at",
        table_name="platform_api_audit_logs",
    )
    op.drop_index("ix_platform_api_audit_logs_key", table_name="platform_api_audit_logs")
    op.drop_index(
        "ix_platform_api_audit_logs_event_type",
        table_name="platform_api_audit_logs",
    )
    op.drop_index(
        "ix_platform_api_audit_logs_decision",
        table_name="platform_api_audit_logs",
    )
    op.drop_table("platform_api_audit_logs")

    op.drop_index(
        "ix_platform_api_usage_events_product",
        table_name="platform_api_usage_events",
    )
    op.drop_index(
        "ix_platform_api_usage_events_outcome",
        table_name="platform_api_usage_events",
    )
    op.drop_index(
        "ix_platform_api_usage_events_occurred_at",
        table_name="platform_api_usage_events",
    )
    op.drop_index(
        "ix_platform_api_usage_events_key",
        table_name="platform_api_usage_events",
    )
    op.drop_table("platform_api_usage_events")

    op.drop_index("ix_platform_api_keys_tier", table_name="platform_api_keys")
    op.drop_index("ix_platform_api_keys_status", table_name="platform_api_keys")
    op.drop_index("ix_platform_api_keys_prefix", table_name="platform_api_keys")
    op.drop_index("ix_platform_api_keys_environment", table_name="platform_api_keys")
    op.drop_index("ix_platform_api_keys_created_at", table_name="platform_api_keys")
    op.drop_table("platform_api_keys")
