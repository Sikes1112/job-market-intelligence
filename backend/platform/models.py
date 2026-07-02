"""Persistence models for Layer 20 Platform API access control."""

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


class PlatformApiTimestampMixin:
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


class PlatformApiKey(Base, PlatformApiTimestampMixin):
    """Hashed key for the versioned public Platform API.

    Raw key material is returned only by the creation service and is never
    represented on this persistence model.
    """

    __tablename__ = "platform_api_keys"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'revoked')",
            name="ck_platform_api_keys_status",
        ),
        CheckConstraint(
            "environment IN ('test', 'live')",
            name="ck_platform_api_keys_environment",
        ),
        CheckConstraint(
            "tier IN ('trial', 'starter', 'growth', 'enterprise')",
            name="ck_platform_api_keys_tier",
        ),
        UniqueConstraint("key_hash", name="uq_platform_api_keys_hash"),
        Index("ix_platform_api_keys_prefix", "key_prefix"),
        Index("ix_platform_api_keys_status", "status"),
        Index("ix_platform_api_keys_environment", "environment"),
        Index("ix_platform_api_keys_tier", "tier"),
        Index("ix_platform_api_keys_created_at", "created_at"),
    )

    platform_api_key_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    key_prefix: Mapped[str] = mapped_column(String(24), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    display_key: Mapped[str] = mapped_column(String(96), nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    environment: Mapped[str] = mapped_column(String(16), nullable=False, default="test")
    tier: Mapped[str] = mapped_column(String(32), nullable=False)
    product_scopes_json: Mapped[list] = mapped_column(JSON, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class PlatformApiUsageEvent(Base):
    """Append-style usage event for external Platform API requests."""

    __tablename__ = "platform_api_usage_events"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('allowed', 'denied')",
            name="ck_platform_api_usage_events_outcome",
        ),
        Index("ix_platform_api_usage_events_key", "platform_api_key_id"),
        Index("ix_platform_api_usage_events_product", "product_id"),
        Index("ix_platform_api_usage_events_occurred_at", "occurred_at"),
        Index("ix_platform_api_usage_events_outcome", "outcome"),
    )

    platform_api_usage_event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    platform_api_key_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("platform_api_keys.platform_api_key_id"),
        nullable=True,
    )
    key_prefix: Mapped[str | None] = mapped_column(String(24), nullable=True)
    product_id: Mapped[str] = mapped_column(String(96), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    request_units: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    decision_reason: Mapped[str] = mapped_column(String(96), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )


class PlatformApiAuditLog(Base):
    """Audit log for external Platform API access decisions."""

    __tablename__ = "platform_api_audit_logs"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('allowed', 'denied')",
            name="ck_platform_api_audit_logs_decision",
        ),
        CheckConstraint(
            "event_type IN ("
            "'allowed_request', "
            "'denied_request', "
            "'rate_limited', "
            "'usage_limit_exceeded', "
            "'missing_key', "
            "'invalid_key', "
            "'revoked_key', "
            "'entitlement_denied'"
            ")",
            name="ck_platform_api_audit_logs_event_type",
        ),
        Index("ix_platform_api_audit_logs_key", "platform_api_key_id"),
        Index("ix_platform_api_audit_logs_product", "product_id"),
        Index("ix_platform_api_audit_logs_occurred_at", "occurred_at"),
        Index("ix_platform_api_audit_logs_event_type", "event_type"),
        Index("ix_platform_api_audit_logs_decision", "decision"),
    )

    platform_api_audit_log_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    platform_api_key_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("platform_api_keys.platform_api_key_id"),
        nullable=True,
    )
    key_prefix: Mapped[str | None] = mapped_column(String(24), nullable=True)
    product_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    event_metadata: Mapped[dict | list | None] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )
