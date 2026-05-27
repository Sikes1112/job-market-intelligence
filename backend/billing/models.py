"""SQLAlchemy models for provider reference billing state."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.db import Base


def _utc_now() -> datetime:
    return datetime.now(UTC)


class BillingTimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        onupdate=_utc_now,
    )


class BillingCustomerRef(Base, BillingTimestampMixin):
    """External customer reference isolated from product entitlement logic."""

    __tablename__ = "billing_customer_refs"
    __table_args__ = (
        CheckConstraint("provider IN ('stripe')", name="ck_billing_customer_refs_provider"),
        UniqueConstraint(
            "provider",
            "provider_customer_id",
            name="uq_billing_customer_refs_provider_customer",
        ),
        UniqueConstraint(
            "provider",
            "monetization_account_id",
            name="uq_billing_customer_refs_provider_account",
        ),
        Index("ix_billing_customer_refs_account", "monetization_account_id"),
    )

    billing_customer_ref_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    monetization_account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("monetization_accounts.monetization_account_id"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_customer_id: Mapped[str] = mapped_column(String(256), nullable=False)
    safe_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class BillingSubscriptionRef(Base, BillingTimestampMixin):
    """External subscription reference mapped to an internal plan assignment."""

    __tablename__ = "billing_subscription_refs"
    __table_args__ = (
        CheckConstraint(
            "provider IN ('stripe')",
            name="ck_billing_subscription_refs_provider",
        ),
        UniqueConstraint(
            "provider",
            "provider_subscription_id",
            name="uq_billing_subscription_refs_provider_subscription",
        ),
        Index("ix_billing_subscription_refs_account", "monetization_account_id"),
        Index("ix_billing_subscription_refs_customer", "provider", "provider_customer_id"),
        Index("ix_billing_subscription_refs_plan_status", "plan_key", "provider_status"),
    )

    billing_subscription_ref_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    monetization_account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("monetization_accounts.monetization_account_id"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_subscription_id: Mapped[str] = mapped_column(String(256), nullable=False)
    provider_customer_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    provider_price_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    plan_key: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_status: Mapped[str] = mapped_column(String(64), nullable=False)
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    canceled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    active_plan_assignment_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("monetization_plan_assignments.plan_assignment_id"),
        nullable=True,
    )
    safe_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class BillingWebhookEvent(Base):
    """Idempotency and audit record for received provider webhooks."""

    __tablename__ = "billing_webhook_events"
    __table_args__ = (
        CheckConstraint("provider IN ('stripe')", name="ck_billing_webhook_events_provider"),
        CheckConstraint(
            "processing_status IN ('pending', 'processed', 'ignored', 'failed')",
            name="ck_billing_webhook_events_processing_status",
        ),
        UniqueConstraint(
            "provider",
            "provider_event_id",
            name="uq_billing_webhook_events_provider_event",
        ),
        Index("ix_billing_webhook_events_type", "event_type"),
        Index("ix_billing_webhook_events_status", "processing_status"),
    )

    billing_webhook_event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(256), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    safe_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
