"""Add admin override and repair workflow tables.

Revision ID: 0010_admin_overrides_repairs
Revises: 0009_audit_finding_lifecycle
Create Date: 2026-05-25
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0010_admin_overrides_repairs"
down_revision = "0009_audit_finding_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_overrides",
        sa.Column("override_id", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("override_type", sa.String(length=64), nullable=False),
        sa.Column("previous_value", sa.JSON(), nullable=True),
        sa.Column("override_value", sa.JSON(), nullable=False),
        sa.Column("reason", sa.String(length=2048), nullable=False),
        sa.Column("reviewer_actor", sa.String(length=128), nullable=False),
        sa.Column("reviewer_role", sa.String(length=32), nullable=True),
        sa.Column("source_evidence", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_by", sa.String(length=128), nullable=True),
        sa.Column("activated_role", sa.String(length=32), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.String(length=128), nullable=True),
        sa.Column("revoked_role", sa.String(length=32), nullable=True),
        sa.Column("revocation_reason", sa.String(length=2048), nullable=True),
        sa.CheckConstraint(
            "target_type IN ('company', 'presence_fact', 'source_ref')",
            name="ck_admin_overrides_target_type",
        ),
        sa.CheckConstraint(
            "override_type IN ("
            "'company_eligibility', "
            "'company_classification', "
            "'presence_status', "
            "'source_confidence'"
            ")",
            name="ck_admin_overrides_override_type",
        ),
        sa.CheckConstraint(
            "status IN ('proposed', 'active', 'expired', 'revoked', 'superseded')",
            name="ck_admin_overrides_status",
        ),
        sa.CheckConstraint(
            "expires_at IS NOT NULL OR review_at IS NOT NULL",
            name="ck_admin_overrides_expiration_or_review",
        ),
        sa.PrimaryKeyConstraint("override_id"),
    )
    op.create_index(
        "ix_admin_overrides_created_at",
        "admin_overrides",
        ["created_at"],
    )
    op.create_index(
        "ix_admin_overrides_override_type",
        "admin_overrides",
        ["override_type"],
    )
    op.create_index(
        "ix_admin_overrides_reviewer",
        "admin_overrides",
        ["reviewer_actor"],
    )
    op.create_index("ix_admin_overrides_status", "admin_overrides", ["status"])
    op.create_index(
        "ix_admin_overrides_target",
        "admin_overrides",
        ["target_type", "target_id"],
    )

    op.create_table(
        "admin_repair_actions",
        sa.Column("repair_action_id", sa.String(length=64), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=2048), nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        sa.Column("requested_role", sa.String(length=32), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executed_by", sa.String(length=128), nullable=True),
        sa.Column("executed_role", sa.String(length=32), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("audit_finding_id", sa.String(length=255), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "action_type IN ("
            "'recompute_score', "
            "'rebuild_output', "
            "'mark_source_stale', "
            "'request_review', "
            "'deactivate_bad_fact'"
            ")",
            name="ck_admin_repair_actions_action_type",
        ),
        sa.CheckConstraint(
            "target_type IN ("
            "'region', "
            "'output', "
            "'company', "
            "'presence_fact', "
            "'hiring_fact', "
            "'entry_level_fact', "
            "'source_ref', "
            "'audit_finding'"
            ")",
            name="ck_admin_repair_actions_target_type",
        ),
        sa.CheckConstraint(
            "status IN ('requested', 'executed', 'failed', 'rejected')",
            name="ck_admin_repair_actions_status",
        ),
        sa.PrimaryKeyConstraint("repair_action_id"),
    )
    op.create_index(
        "ix_admin_repair_actions_action_type",
        "admin_repair_actions",
        ["action_type"],
    )
    op.create_index(
        "ix_admin_repair_actions_audit_finding",
        "admin_repair_actions",
        ["audit_finding_id"],
    )
    op.create_index(
        "ix_admin_repair_actions_created_at",
        "admin_repair_actions",
        ["created_at"],
    )
    op.create_index(
        "ix_admin_repair_actions_requested_by",
        "admin_repair_actions",
        ["requested_by"],
    )
    op.create_index(
        "ix_admin_repair_actions_status",
        "admin_repair_actions",
        ["status"],
    )
    op.create_index(
        "ix_admin_repair_actions_target",
        "admin_repair_actions",
        ["target_type", "target_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_admin_repair_actions_target", table_name="admin_repair_actions")
    op.drop_index("ix_admin_repair_actions_status", table_name="admin_repair_actions")
    op.drop_index(
        "ix_admin_repair_actions_requested_by",
        table_name="admin_repair_actions",
    )
    op.drop_index(
        "ix_admin_repair_actions_created_at",
        table_name="admin_repair_actions",
    )
    op.drop_index(
        "ix_admin_repair_actions_audit_finding",
        table_name="admin_repair_actions",
    )
    op.drop_index(
        "ix_admin_repair_actions_action_type",
        table_name="admin_repair_actions",
    )
    op.drop_table("admin_repair_actions")

    op.drop_index("ix_admin_overrides_target", table_name="admin_overrides")
    op.drop_index("ix_admin_overrides_status", table_name="admin_overrides")
    op.drop_index("ix_admin_overrides_reviewer", table_name="admin_overrides")
    op.drop_index("ix_admin_overrides_override_type", table_name="admin_overrides")
    op.drop_index("ix_admin_overrides_created_at", table_name="admin_overrides")
    op.drop_table("admin_overrides")
