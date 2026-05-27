"""Add monetization account state and usage counters.

Revision ID: 0013_monetization_account_state
Revises: 0012_change_expansion_engine
Create Date: 2026-05-26
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0013_monetization_account_state"
down_revision = "0012_change_expansion_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "monetization_accounts",
        sa.Column("monetization_account_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column("account_type", sa.String(length=32), nullable=False),
        sa.Column("assigned_seats_count", sa.Integer(), nullable=True),
        sa.Column("safe_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "account_type IN "
            "('individual', 'student', 'institutional', 'public_demo', 'internal_test')",
            name="ck_monetization_accounts_account_type",
        ),
        sa.CheckConstraint(
            "assigned_seats_count IS NULL OR assigned_seats_count >= 0",
            name="ck_monetization_accounts_assigned_seats_nonnegative",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("monetization_account_id"),
        sa.UniqueConstraint("user_id", name="uq_monetization_accounts_user_id"),
    )
    op.create_index(
        "ix_monetization_accounts_account_type",
        "monetization_accounts",
        ["account_type"],
    )
    op.create_index(
        "ix_monetization_accounts_user_id",
        "monetization_accounts",
        ["user_id"],
    )

    op.create_table(
        "monetization_plan_assignments",
        sa.Column("plan_assignment_id", sa.String(length=64), nullable=False),
        sa.Column("monetization_account_id", sa.String(length=64), nullable=False),
        sa.Column("plan_key", sa.String(length=64), nullable=False),
        sa.Column("plan_status", sa.String(length=32), nullable=False),
        sa.Column("assignment_source", sa.String(length=32), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("seat_limit", sa.Integer(), nullable=True),
        sa.Column("safe_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "plan_key IN ("
            "'free', "
            "'individual_monthly', "
            "'individual_annual', "
            "'student_annual', "
            "'career_center_license', "
            "'bootcamp_license', "
            "'university_license', "
            "'workforce_board_license'"
            ")",
            name="ck_monetization_plan_assignments_plan_key",
        ),
        sa.CheckConstraint(
            "plan_status IN "
            "('active', 'trialing', 'paused', 'expired', 'canceled', 'test', 'manual')",
            name="ck_monetization_plan_assignments_status",
        ),
        sa.CheckConstraint(
            "assignment_source IN "
            "('manual', 'admin_seed', 'test_fixture', 'future_billing_provider')",
            name="ck_monetization_plan_assignments_source",
        ),
        sa.CheckConstraint(
            "seat_limit IS NULL OR seat_limit >= 0",
            name="ck_monetization_plan_assignments_seat_limit_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["monetization_account_id"],
            ["monetization_accounts.monetization_account_id"],
        ),
        sa.PrimaryKeyConstraint("plan_assignment_id"),
    )
    op.create_index(
        "ix_monetization_plan_assignments_account",
        "monetization_plan_assignments",
        ["monetization_account_id", "effective_at"],
    )
    op.create_index(
        "ix_monetization_plan_assignments_plan_key",
        "monetization_plan_assignments",
        ["plan_key"],
    )
    op.create_index(
        "ix_monetization_plan_assignments_status",
        "monetization_plan_assignments",
        ["plan_status"],
    )

    op.create_table(
        "monetization_usage_counters",
        sa.Column("usage_counter_id", sa.String(length=64), nullable=False),
        sa.Column("monetization_account_id", sa.String(length=64), nullable=False),
        sa.Column("feature_key", sa.String(length=64), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_count", sa.Integer(), nullable=False),
        sa.Column("limit_count", sa.Integer(), nullable=False),
        sa.Column("reset_policy", sa.String(length=32), nullable=False),
        sa.Column("last_incremented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "reset_policy IN ('monthly', 'static')",
            name="ck_monetization_usage_counters_reset_policy",
        ),
        sa.CheckConstraint(
            "used_count >= 0",
            name="ck_monetization_usage_counters_used_nonnegative",
        ),
        sa.CheckConstraint(
            "limit_count >= 0",
            name="ck_monetization_usage_counters_limit_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["monetization_account_id"],
            ["monetization_accounts.monetization_account_id"],
        ),
        sa.PrimaryKeyConstraint("usage_counter_id"),
        sa.UniqueConstraint(
            "monetization_account_id",
            "feature_key",
            "period_start",
            "period_end",
            name="uq_monetization_usage_account_feature_period",
        ),
    )
    op.create_index(
        "ix_monetization_usage_account_feature",
        "monetization_usage_counters",
        ["monetization_account_id", "feature_key"],
    )
    op.create_index(
        "ix_monetization_usage_period",
        "monetization_usage_counters",
        ["period_start", "period_end"],
    )


def downgrade() -> None:
    op.drop_index("ix_monetization_usage_period", table_name="monetization_usage_counters")
    op.drop_index(
        "ix_monetization_usage_account_feature",
        table_name="monetization_usage_counters",
    )
    op.drop_table("monetization_usage_counters")

    op.drop_index(
        "ix_monetization_plan_assignments_status",
        table_name="monetization_plan_assignments",
    )
    op.drop_index(
        "ix_monetization_plan_assignments_plan_key",
        table_name="monetization_plan_assignments",
    )
    op.drop_index(
        "ix_monetization_plan_assignments_account",
        table_name="monetization_plan_assignments",
    )
    op.drop_table("monetization_plan_assignments")

    op.drop_index("ix_monetization_accounts_user_id", table_name="monetization_accounts")
    op.drop_index(
        "ix_monetization_accounts_account_type",
        table_name="monetization_accounts",
    )
    op.drop_table("monetization_accounts")
