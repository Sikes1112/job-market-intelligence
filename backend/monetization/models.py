"""SQLAlchemy models for provider-agnostic monetization account state."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.db import Base


def _utc_now() -> datetime:
    return datetime.now(UTC)


class MonetizationTimestampMixin:
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


class MonetizationAccount(Base, MonetizationTimestampMixin):
    """Internal monetization account profile.

    This table intentionally contains no payment-provider identifiers and no
    private recommendation inputs. Future billing adapters may map provider
    state into plan assignments without becoming product authority.
    """

    __tablename__ = "monetization_accounts"
    __table_args__ = (
        CheckConstraint(
            "account_type IN "
            "('individual', 'student', 'institutional', 'public_demo', 'internal_test')",
            name="ck_monetization_accounts_account_type",
        ),
        CheckConstraint(
            "assigned_seats_count IS NULL OR assigned_seats_count >= 0",
            name="ck_monetization_accounts_assigned_seats_nonnegative",
        ),
        UniqueConstraint("user_id", name="uq_monetization_accounts_user_id"),
        Index("ix_monetization_accounts_user_id", "user_id"),
        Index("ix_monetization_accounts_account_type", "account_type"),
    )

    monetization_account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("users.user_id"),
        nullable=True,
    )
    account_type: Mapped[str] = mapped_column(String(32), nullable=False)
    assigned_seats_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    safe_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class MonetizationPlanAssignment(Base, MonetizationTimestampMixin):
    """Provider-agnostic plan assignment for a monetization account."""

    __tablename__ = "monetization_plan_assignments"
    __table_args__ = (
        CheckConstraint(
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
        CheckConstraint(
            "plan_status IN "
            "('active', 'trialing', 'paused', 'expired', 'canceled', 'test', 'manual')",
            name="ck_monetization_plan_assignments_status",
        ),
        CheckConstraint(
            "assignment_source IN "
            "('manual', 'admin_seed', 'test_fixture', 'future_billing_provider')",
            name="ck_monetization_plan_assignments_source",
        ),
        CheckConstraint(
            "seat_limit IS NULL OR seat_limit >= 0",
            name="ck_monetization_plan_assignments_seat_limit_nonnegative",
        ),
        Index(
            "ix_monetization_plan_assignments_account",
            "monetization_account_id",
            "effective_at",
        ),
        Index("ix_monetization_plan_assignments_status", "plan_status"),
        Index("ix_monetization_plan_assignments_plan_key", "plan_key"),
    )

    plan_assignment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    monetization_account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("monetization_accounts.monetization_account_id"),
        nullable=False,
    )
    plan_key: Mapped[str] = mapped_column(String(64), nullable=False)
    plan_status: Mapped[str] = mapped_column(String(32), nullable=False)
    assignment_source: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    seat_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    safe_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class MonetizationUsageCounter(Base, MonetizationTimestampMixin):
    """Usage counter for limited monetization features.

    Counters track product usage only. They are not billing-provider metering
    records and are not reported to any external system in this layer.
    """

    __tablename__ = "monetization_usage_counters"
    __table_args__ = (
        CheckConstraint(
            "reset_policy IN ('monthly', 'static')",
            name="ck_monetization_usage_counters_reset_policy",
        ),
        CheckConstraint(
            "used_count >= 0",
            name="ck_monetization_usage_counters_used_nonnegative",
        ),
        CheckConstraint(
            "limit_count >= 0",
            name="ck_monetization_usage_counters_limit_nonnegative",
        ),
        UniqueConstraint(
            "monetization_account_id",
            "feature_key",
            "period_start",
            "period_end",
            name="uq_monetization_usage_account_feature_period",
        ),
        Index(
            "ix_monetization_usage_account_feature",
            "monetization_account_id",
            "feature_key",
        ),
        Index("ix_monetization_usage_period", "period_start", "period_end"),
    )

    usage_counter_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    monetization_account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("monetization_accounts.monetization_account_id"),
        nullable=False,
    )
    feature_key: Mapped[str] = mapped_column(String(64), nullable=False)
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    limit_count: Mapped[int] = mapped_column(Integer, nullable=False)
    reset_policy: Mapped[str] = mapped_column(String(32), nullable=False)
    last_incremented_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
