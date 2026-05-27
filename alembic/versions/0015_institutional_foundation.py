"""Add institutional organization and audit foundation.

Revision ID: 0015_institutional_foundation
Revises: 0014_billing_provider_refs
Create Date: 2026-05-27
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0015_institutional_foundation"
down_revision = "0014_billing_provider_refs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("organization_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "organization_type IN ("
            "'school', "
            "'career_center', "
            "'bootcamp', "
            "'workforce_org', "
            "'economic_development_partner', "
            "'internal_demo'"
            ")",
            name="ck_organizations_type",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_organizations_status",
        ),
        sa.PrimaryKeyConstraint("organization_id"),
    )
    op.create_index("ix_organizations_status", "organizations", ["status"])
    op.create_index("ix_organizations_type", "organizations", ["organization_type"])

    op.create_table(
        "organization_memberships",
        sa.Column("organization_membership_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('ORG_ADMIN', 'ADVISOR', 'STUDENT', 'REPORT_VIEWER')",
            name="ck_organization_memberships_role",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_organization_memberships_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.organization_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("organization_membership_id"),
        sa.UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_organization_memberships_org_user",
        ),
    )
    op.create_index(
        "ix_organization_memberships_org",
        "organization_memberships",
        ["organization_id"],
    )
    op.create_index(
        "ix_organization_memberships_role",
        "organization_memberships",
        ["role"],
    )
    op.create_index(
        "ix_organization_memberships_status",
        "organization_memberships",
        ["status"],
    )
    op.create_index(
        "ix_organization_memberships_user",
        "organization_memberships",
        ["user_id"],
    )

    op.create_table(
        "institutional_audit_logs",
        sa.Column("institutional_audit_log_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("actor_user_id", sa.String(length=64), nullable=False),
        sa.Column("actor_role", sa.String(length=32), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("purpose", sa.String(length=512), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "actor_role IS NULL OR actor_role IN "
            "('ORG_ADMIN', 'ADVISOR', 'STUDENT', 'REPORT_VIEWER')",
            name="ck_institutional_audit_logs_actor_role",
        ),
        sa.CheckConstraint(
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
            ")",
            name="ck_institutional_audit_logs_action",
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.user_id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.organization_id"]),
        sa.PrimaryKeyConstraint("institutional_audit_log_id"),
    )
    op.create_index(
        "ix_institutional_audit_logs_action",
        "institutional_audit_logs",
        ["action"],
    )
    op.create_index(
        "ix_institutional_audit_logs_actor",
        "institutional_audit_logs",
        ["actor_user_id"],
    )
    op.create_index(
        "ix_institutional_audit_logs_created_at",
        "institutional_audit_logs",
        ["created_at"],
    )
    op.create_index(
        "ix_institutional_audit_logs_org",
        "institutional_audit_logs",
        ["organization_id"],
    )
    op.create_index(
        "ix_institutional_audit_logs_target",
        "institutional_audit_logs",
        ["target_type", "target_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_institutional_audit_logs_target",
        table_name="institutional_audit_logs",
    )
    op.drop_index(
        "ix_institutional_audit_logs_org",
        table_name="institutional_audit_logs",
    )
    op.drop_index(
        "ix_institutional_audit_logs_created_at",
        table_name="institutional_audit_logs",
    )
    op.drop_index(
        "ix_institutional_audit_logs_actor",
        table_name="institutional_audit_logs",
    )
    op.drop_index(
        "ix_institutional_audit_logs_action",
        table_name="institutional_audit_logs",
    )
    op.drop_table("institutional_audit_logs")

    op.drop_index(
        "ix_organization_memberships_user",
        table_name="organization_memberships",
    )
    op.drop_index(
        "ix_organization_memberships_status",
        table_name="organization_memberships",
    )
    op.drop_index(
        "ix_organization_memberships_role",
        table_name="organization_memberships",
    )
    op.drop_index(
        "ix_organization_memberships_org",
        table_name="organization_memberships",
    )
    op.drop_table("organization_memberships")

    op.drop_index("ix_organizations_type", table_name="organizations")
    op.drop_index("ix_organizations_status", table_name="organizations")
    op.drop_table("organizations")
