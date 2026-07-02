"""Add Layer 26B career-agent memory tables.

Revision ID: 0027_career_agent_memory
Revises: 0026_opportunity_submission_review
Create Date: 2026-06-30
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0027_career_agent_memory"
down_revision = "0026_opportunity_submission_review"
branch_labels = None
depends_on = None

CAREER_MEMORY_CATEGORY_SQL = (
    "'saved_companies', "
    "'target_regions', "
    "'applied_roles', "
    "'preferred_industries', "
    "'rejected_markets', "
    "'career_constraints', "
    "'preferred_role_types'"
)


def upgrade() -> None:
    op.create_table(
        "career_memory_permissions",
        sa.Column("career_memory_permission_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("personalize_allowed", sa.Boolean(), nullable=False),
        sa.Column("visibility", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"category IN ({CAREER_MEMORY_CATEGORY_SQL})",
            name="ck_career_memory_permissions_category",
        ),
        sa.CheckConstraint(
            "visibility = 'private'",
            name="ck_career_memory_permissions_private",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("career_memory_permission_id"),
        sa.UniqueConstraint(
            "user_id",
            "category",
            name="uq_career_memory_permissions_user_category",
        ),
    )
    op.create_index(
        "ix_career_memory_permissions_category",
        "career_memory_permissions",
        ["category"],
    )
    op.create_index(
        "ix_career_memory_permissions_user_id",
        "career_memory_permissions",
        ["user_id"],
    )

    op.create_table(
        "career_memory_entries",
        sa.Column("career_memory_entry_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.String(length=2048), nullable=True),
        sa.Column("visibility", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"category IN ({CAREER_MEMORY_CATEGORY_SQL})",
            name="ck_career_memory_entries_category",
        ),
        sa.CheckConstraint(
            "visibility = 'private'",
            name="ck_career_memory_entries_private",
        ),
        sa.CheckConstraint(
            "source = 'user_provided'",
            name="ck_career_memory_entries_user_provided",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("career_memory_entry_id"),
        sa.UniqueConstraint(
            "user_id",
            "category",
            "value",
            name="uq_career_memory_entries_user_category_value",
        ),
    )
    op.create_index(
        "ix_career_memory_entries_category",
        "career_memory_entries",
        ["category"],
    )
    op.create_index(
        "ix_career_memory_entries_user_category",
        "career_memory_entries",
        ["user_id", "category"],
    )
    op.create_index(
        "ix_career_memory_entries_user_id",
        "career_memory_entries",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_career_memory_entries_user_id", table_name="career_memory_entries")
    op.drop_index(
        "ix_career_memory_entries_user_category",
        table_name="career_memory_entries",
    )
    op.drop_index("ix_career_memory_entries_category", table_name="career_memory_entries")
    op.drop_table("career_memory_entries")

    op.drop_index(
        "ix_career_memory_permissions_user_id",
        table_name="career_memory_permissions",
    )
    op.drop_index(
        "ix_career_memory_permissions_category",
        table_name="career_memory_permissions",
    )
    op.drop_table("career_memory_permissions")
