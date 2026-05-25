"""Durable in-app alert metadata.

Alert events are system-detected change records built from structured market
facts or approved derived metadata. User alerts are relevance overlays for a
specific app user. Neither table owns canonical market truth.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.db import Base


class AlertEvent(Base):
    __tablename__ = "alert_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ("
            "'new_hiring_activity', "
            "'entry_level_signal_changed', "
            "'company_expanded_in_region', "
            "'region_score_changed', "
            "'internship_window_opened'"
            ")",
            name="ck_alert_events_event_type",
        ),
        Index("ix_alert_events_event_type", "event_type"),
        Index("ix_alert_events_company_id", "company_id"),
        Index("ix_alert_events_region_id", "region_id"),
        Index("ix_alert_events_created_at", "created_at"),
    )

    alert_event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    company_id: Mapped[str | None] = mapped_column(
        ForeignKey("companies.company_id"),
        nullable=True,
    )
    region_id: Mapped[str | None] = mapped_column(
        ForeignKey("regions.region_id"),
        nullable=True,
    )
    role_family: Mapped[str | None] = mapped_column(String(64), nullable=True)
    previous_value: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    new_value: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    change_summary: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    freshness_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    freshness_observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    freshness_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    source_refs: Mapped[list | None] = mapped_column(JSON, nullable=True)
    change_basis_refs: Mapped[list | None] = mapped_column(JSON, nullable=True)
    detection_basis: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class UserAlert(Base):
    __tablename__ = "user_alerts"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "alert_event_id",
            name="uq_user_alerts_user_event",
        ),
        CheckConstraint(
            "relevance_reason IN ("
            "'saved_company', "
            "'saved_region', "
            "'saved_comparison', "
            "'saved_role_family', "
            "'preferred_region', "
            "'role_interest'"
            ")",
            name="ck_user_alerts_relevance_reason",
        ),
        Index("ix_user_alerts_user_created", "user_id", "created_at"),
        Index("ix_user_alerts_user_read", "user_id", "is_read"),
        Index("ix_user_alerts_dismissed", "dismissed"),
    )

    user_alert_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id"),
        nullable=False,
    )
    alert_event_id: Mapped[str] = mapped_column(
        ForeignKey("alert_events.alert_event_id"),
        nullable=False,
    )
    relevance_reason: Mapped[str] = mapped_column(String(64), nullable=False)
    relevance_artifact_id: Mapped[str | None] = mapped_column(
        ForeignKey("saved_market_artifacts.saved_artifact_id"),
        nullable=True,
    )
    relevance_artifact_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    relevance_artifact_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

