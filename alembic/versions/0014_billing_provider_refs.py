"""Add billing provider reference tables.

Revision ID: 0014_billing_provider_refs
Revises: 0013_monetization_account_state
Create Date: 2026-05-26
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0014_billing_provider_refs"
down_revision = "0013_monetization_account_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_customer_refs",
        sa.Column("billing_customer_ref_id", sa.String(length=64), nullable=False),
        sa.Column("monetization_account_id", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_customer_id", sa.String(length=256), nullable=False),
        sa.Column("safe_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "provider IN ('stripe')",
            name="ck_billing_customer_refs_provider",
        ),
        sa.ForeignKeyConstraint(
            ["monetization_account_id"],
            ["monetization_accounts.monetization_account_id"],
        ),
        sa.PrimaryKeyConstraint("billing_customer_ref_id"),
        sa.UniqueConstraint(
            "provider",
            "provider_customer_id",
            name="uq_billing_customer_refs_provider_customer",
        ),
        sa.UniqueConstraint(
            "provider",
            "monetization_account_id",
            name="uq_billing_customer_refs_provider_account",
        ),
    )
    op.create_index(
        "ix_billing_customer_refs_account",
        "billing_customer_refs",
        ["monetization_account_id"],
    )

    op.create_table(
        "billing_subscription_refs",
        sa.Column("billing_subscription_ref_id", sa.String(length=64), nullable=False),
        sa.Column("monetization_account_id", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_subscription_id", sa.String(length=256), nullable=False),
        sa.Column("provider_customer_id", sa.String(length=256), nullable=True),
        sa.Column("provider_price_id", sa.String(length=256), nullable=True),
        sa.Column("plan_key", sa.String(length=64), nullable=False),
        sa.Column("provider_status", sa.String(length=64), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_plan_assignment_id", sa.String(length=64), nullable=True),
        sa.Column("safe_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "provider IN ('stripe')",
            name="ck_billing_subscription_refs_provider",
        ),
        sa.ForeignKeyConstraint(
            ["active_plan_assignment_id"],
            ["monetization_plan_assignments.plan_assignment_id"],
        ),
        sa.ForeignKeyConstraint(
            ["monetization_account_id"],
            ["monetization_accounts.monetization_account_id"],
        ),
        sa.PrimaryKeyConstraint("billing_subscription_ref_id"),
        sa.UniqueConstraint(
            "provider",
            "provider_subscription_id",
            name="uq_billing_subscription_refs_provider_subscription",
        ),
    )
    op.create_index(
        "ix_billing_subscription_refs_account",
        "billing_subscription_refs",
        ["monetization_account_id"],
    )
    op.create_index(
        "ix_billing_subscription_refs_customer",
        "billing_subscription_refs",
        ["provider", "provider_customer_id"],
    )
    op.create_index(
        "ix_billing_subscription_refs_plan_status",
        "billing_subscription_refs",
        ["plan_key", "provider_status"],
    )

    op.create_table(
        "billing_webhook_events",
        sa.Column("billing_webhook_event_id", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_event_id", sa.String(length=256), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("processing_status", sa.String(length=32), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("safe_metadata", sa.JSON(), nullable=True),
        sa.CheckConstraint(
            "provider IN ('stripe')",
            name="ck_billing_webhook_events_provider",
        ),
        sa.CheckConstraint(
            "processing_status IN ('pending', 'processed', 'ignored', 'failed')",
            name="ck_billing_webhook_events_processing_status",
        ),
        sa.PrimaryKeyConstraint("billing_webhook_event_id"),
        sa.UniqueConstraint(
            "provider",
            "provider_event_id",
            name="uq_billing_webhook_events_provider_event",
        ),
    )
    op.create_index(
        "ix_billing_webhook_events_status",
        "billing_webhook_events",
        ["processing_status"],
    )
    op.create_index(
        "ix_billing_webhook_events_type",
        "billing_webhook_events",
        ["event_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_billing_webhook_events_type", table_name="billing_webhook_events")
    op.drop_index("ix_billing_webhook_events_status", table_name="billing_webhook_events")
    op.drop_table("billing_webhook_events")

    op.drop_index(
        "ix_billing_subscription_refs_plan_status",
        table_name="billing_subscription_refs",
    )
    op.drop_index(
        "ix_billing_subscription_refs_customer",
        table_name="billing_subscription_refs",
    )
    op.drop_index(
        "ix_billing_subscription_refs_account",
        table_name="billing_subscription_refs",
    )
    op.drop_table("billing_subscription_refs")

    op.drop_index("ix_billing_customer_refs_account", table_name="billing_customer_refs")
    op.drop_table("billing_customer_refs")
