"""Add auth user foundation schema.

Revision ID: 0004_auth_user_foundation
Revises: 0003_ingestion_raw_intake
Create Date: 2026-05-21
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0004_auth_user_foundation"
down_revision = "0003_ingestion_raw_intake"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index("ix_users_status", "users", ["status"])

    op.create_table(
        "external_auth_identities",
        sa.Column("external_identity_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("issuer", sa.String(length=512), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("external_identity_id"),
        sa.UniqueConstraint(
            "provider",
            "issuer",
            "subject",
            name="uq_external_auth_identity_provider_subject",
        ),
    )
    op.create_index(
        "ix_external_auth_identities_provider",
        "external_auth_identities",
        ["provider"],
    )
    op.create_index(
        "ix_external_auth_identities_user_id",
        "external_auth_identities",
        ["user_id"],
    )

    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("avatar_url", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("user_profiles")
    op.drop_index(
        "ix_external_auth_identities_user_id",
        table_name="external_auth_identities",
    )
    op.drop_index(
        "ix_external_auth_identities_provider",
        table_name="external_auth_identities",
    )
    op.drop_table("external_auth_identities")
    op.drop_index("ix_users_status", table_name="users")
    op.drop_table("users")

