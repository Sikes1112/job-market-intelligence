"""Add in-app alerts and region expansion workflows.

Revision ID: 0012_change_expansion_engine
Revises: 0011_retention_foundation
Create Date: 2026-05-25
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0012_change_expansion_engine"
down_revision = "0011_retention_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_events",
        sa.Column("alert_event_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("company_id", sa.String(length=64), nullable=True),
        sa.Column("region_id", sa.String(length=64), nullable=True),
        sa.Column("role_family", sa.String(length=64), nullable=True),
        sa.Column("previous_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column("change_summary", sa.JSON(), nullable=True),
        sa.Column("freshness_status", sa.String(length=32), nullable=True),
        sa.Column("freshness_observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("freshness_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_refs", sa.JSON(), nullable=True),
        sa.Column("change_basis_refs", sa.JSON(), nullable=True),
        sa.Column("detection_basis", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_type IN ("
            "'new_hiring_activity', "
            "'entry_level_signal_changed', "
            "'company_expanded_in_region', "
            "'region_score_changed', "
            "'internship_window_opened'"
            ")",
            name="ck_alert_events_event_type",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.company_id"]),
        sa.ForeignKeyConstraint(["region_id"], ["regions.region_id"]),
        sa.PrimaryKeyConstraint("alert_event_id"),
    )
    op.create_index("ix_alert_events_company_id", "alert_events", ["company_id"])
    op.create_index("ix_alert_events_created_at", "alert_events", ["created_at"])
    op.create_index("ix_alert_events_event_type", "alert_events", ["event_type"])
    op.create_index("ix_alert_events_region_id", "alert_events", ["region_id"])

    op.create_table(
        "region_expansion_workflows",
        sa.Column("workflow_id", sa.String(length=64), nullable=False),
        sa.Column("region_key", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("canonical_region_id", sa.String(length=64), nullable=True),
        sa.Column("workflow_state", sa.String(length=32), nullable=False),
        sa.Column("region_data_mode", sa.String(length=32), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False),
        sa.Column("refresh_enabled", sa.Boolean(), nullable=False),
        sa.Column("ingestion_contract_ref", sa.String(length=128), nullable=True),
        sa.Column("provenance_contract_ref", sa.String(length=128), nullable=True),
        sa.Column("admin_review_ref", sa.String(length=128), nullable=True),
        sa.Column("output_refresh_contract_ref", sa.String(length=128), nullable=True),
        sa.Column("checklist_notes", sa.JSON(), nullable=True),
        sa.Column("region_identity_check", sa.Boolean(), nullable=False),
        sa.Column("source_coverage_check", sa.Boolean(), nullable=False),
        sa.Column("company_region_presence_check", sa.Boolean(), nullable=False),
        sa.Column("hiring_signal_support_check", sa.Boolean(), nullable=False),
        sa.Column("entry_level_signal_support_check", sa.Boolean(), nullable=False),
        sa.Column("scoring_readiness_check", sa.Boolean(), nullable=False),
        sa.Column("freshness_readiness_check", sa.Boolean(), nullable=False),
        sa.Column("provenance_attached_check", sa.Boolean(), nullable=False),
        sa.Column("admin_approval_check", sa.Boolean(), nullable=False),
        sa.Column("output_refresh_readiness_check", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "workflow_state IN ("
            "'candidate', "
            "'intake_started', "
            "'normalized', "
            "'provenance_attached', "
            "'review_ready', "
            "'approved', "
            "'published', "
            "'refresh_enabled'"
            ")",
            name="ck_region_expansion_workflows_state",
        ),
        sa.CheckConstraint(
            "region_data_mode IN ('seed_demo', 'candidate', 'real_refreshable')",
            name="ck_region_expansion_workflows_data_mode",
        ),
        sa.PrimaryKeyConstraint("workflow_id"),
        sa.UniqueConstraint(
            "region_key",
            name="uq_region_expansion_workflows_region_key",
        ),
    )
    op.create_index(
        "ix_region_expansion_workflows_data_mode",
        "region_expansion_workflows",
        ["region_data_mode"],
    )
    op.create_index(
        "ix_region_expansion_workflows_state",
        "region_expansion_workflows",
        ["workflow_state"],
    )

    op.create_table(
        "user_alerts",
        sa.Column("user_alert_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("alert_event_id", sa.String(length=64), nullable=False),
        sa.Column("relevance_reason", sa.String(length=64), nullable=False),
        sa.Column("relevance_artifact_id", sa.String(length=64), nullable=True),
        sa.Column("relevance_artifact_type", sa.String(length=32), nullable=True),
        sa.Column("relevance_artifact_ref", sa.String(length=255), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("dismissed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "relevance_reason IN ("
            "'saved_company', "
            "'saved_region', "
            "'saved_comparison', "
            "'saved_role_family', "
            "'preferred_region', "
            "'role_interest'"
            ")",
            name="ck_user_alerts_relevance_reason",
        ),
        sa.ForeignKeyConstraint(["alert_event_id"], ["alert_events.alert_event_id"]),
        sa.ForeignKeyConstraint(
            ["relevance_artifact_id"],
            ["saved_market_artifacts.saved_artifact_id"],
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("user_alert_id"),
        sa.UniqueConstraint(
            "user_id",
            "alert_event_id",
            name="uq_user_alerts_user_event",
        ),
    )
    op.create_index("ix_user_alerts_dismissed", "user_alerts", ["dismissed"])
    op.create_index("ix_user_alerts_user_created", "user_alerts", ["user_id", "created_at"])
    op.create_index("ix_user_alerts_user_read", "user_alerts", ["user_id", "is_read"])


def downgrade() -> None:
    op.drop_index("ix_user_alerts_user_read", table_name="user_alerts")
    op.drop_index("ix_user_alerts_user_created", table_name="user_alerts")
    op.drop_index("ix_user_alerts_dismissed", table_name="user_alerts")
    op.drop_table("user_alerts")

    op.drop_index(
        "ix_region_expansion_workflows_state",
        table_name="region_expansion_workflows",
    )
    op.drop_index(
        "ix_region_expansion_workflows_data_mode",
        table_name="region_expansion_workflows",
    )
    op.drop_table("region_expansion_workflows")

    op.drop_index("ix_alert_events_region_id", table_name="alert_events")
    op.drop_index("ix_alert_events_event_type", table_name="alert_events")
    op.drop_index("ix_alert_events_created_at", table_name="alert_events")
    op.drop_index("ix_alert_events_company_id", table_name="alert_events")
    op.drop_table("alert_events")

