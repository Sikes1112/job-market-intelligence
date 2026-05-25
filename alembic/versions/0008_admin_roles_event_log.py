"""Add admin roles and admin event log.

Revision ID: 0008_admin_roles_event_log
Revises: 0007_output_cache
Create Date: 2026-05-25
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0008_admin_roles_event_log"
down_revision = "0007_output_cache"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "admin_role",
            sa.String(length=32),
            sa.CheckConstraint(
                "admin_role IS NULL OR "
                "admin_role IN ('admin', 'data_reviewer', 'read_only_operator')",
                name="ck_users_admin_role",
            ),
            nullable=True,
        ),
    )
    op.create_index("ix_users_admin_role", "users", ["admin_role"])

    op.create_table(
        "admin_event_logs",
        sa.Column("admin_event_id", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("actor_role", sa.String(length=32), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("object_type", sa.String(length=64), nullable=False),
        sa.Column("object_id", sa.String(length=128), nullable=False),
        sa.Column("before_state", sa.JSON(), nullable=True),
        sa.Column("after_state", sa.JSON(), nullable=True),
        sa.Column("reason", sa.String(length=2048), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("admin_event_id"),
    )
    op.create_index("ix_admin_event_logs_actor", "admin_event_logs", ["actor"])
    op.create_index("ix_admin_event_logs_action", "admin_event_logs", ["action"])
    op.create_index(
        "ix_admin_event_logs_object",
        "admin_event_logs",
        ["object_type", "object_id"],
    )
    op.create_index(
        "ix_admin_event_logs_request_id",
        "admin_event_logs",
        ["request_id"],
    )
    op.create_index("ix_admin_event_logs_timestamp", "admin_event_logs", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_admin_event_logs_timestamp", table_name="admin_event_logs")
    op.drop_index("ix_admin_event_logs_request_id", table_name="admin_event_logs")
    op.drop_index("ix_admin_event_logs_object", table_name="admin_event_logs")
    op.drop_index("ix_admin_event_logs_action", table_name="admin_event_logs")
    op.drop_index("ix_admin_event_logs_actor", table_name="admin_event_logs")
    op.drop_table("admin_event_logs")
    op.drop_index("ix_users_admin_role", table_name="users")
    op.drop_column("users", "admin_role")
