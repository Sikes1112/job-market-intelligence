"""Add revocable public guest browser sessions.

Revision ID: 0047_public_guest_sessions
Revises: 0046_beta_production_hardening
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0047_public_guest_sessions"
down_revision = "0046_beta_production_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "public_guest_sessions",
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("csrf_token_digest", sa.String(length=64), nullable=False),
        sa.Column("mutation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("session_id"),
        sa.UniqueConstraint("subject"),
        sa.UniqueConstraint("token_digest"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(
        "ix_public_guest_sessions_user",
        "public_guest_sessions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_public_guest_sessions_expires",
        "public_guest_sessions",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_public_guest_sessions_active",
        "public_guest_sessions",
        ["revoked_at", "expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_public_guest_sessions_active", table_name="public_guest_sessions")
    op.drop_index("ix_public_guest_sessions_expires", table_name="public_guest_sessions")
    op.drop_index("ix_public_guest_sessions_user", table_name="public_guest_sessions")
    op.drop_table("public_guest_sessions")
