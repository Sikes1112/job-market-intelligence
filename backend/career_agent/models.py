"""User-scoped career-agent memory persistence."""

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
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.db import Base

CAREER_MEMORY_CATEGORY_SQL = (
    "'saved_companies', "
    "'target_regions', "
    "'applied_roles', "
    "'preferred_industries', "
    "'rejected_markets', "
    "'career_constraints', "
    "'preferred_role_types'"
)

CAREER_AGENT_TOOL_TYPE_SQL = (
    "'reminder', "
    "'career_report_export', "
    "'watchlist_update_suggestion', "
    "'notification_preference', "
    "'outreach_message_draft', "
    "'application_prep_checklist', "
    "'job_application_submission'"
)

CAREER_AGENT_TOOL_STATUS_SQL = (
    "'suggested', "
    "'drafted', "
    "'preview_ready', "
    "'awaiting_user_approval', "
    "'approved', "
    "'executed', "
    "'rejected', "
    "'expired', "
    "'blocked'"
)

CAREER_AGENT_ACTION_BOUNDARY_SQL = (
    "'read_only_preview', "
    "'user_state_change', "
    "'reminder_creation', "
    "'user_data_export', "
    "'watchlist_mutation', "
    "'notification_change', "
    "'external_contact', "
    "'application_submission'"
)

CAREER_AGENT_TOOL_PRIVACY_SQL = (
    "'public_safe', "
    "'user_private', "
    "'external_contact', "
    "'blocked'"
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class CareerMemoryPermissionRecord(Base):
    """Per-user opt-in switch for one career memory category."""

    __tablename__ = "career_memory_permissions"
    __table_args__ = (
        CheckConstraint(
            f"category IN ({CAREER_MEMORY_CATEGORY_SQL})",
            name="ck_career_memory_permissions_category",
        ),
        CheckConstraint(
            "visibility = 'private'",
            name="ck_career_memory_permissions_private",
        ),
        UniqueConstraint(
            "user_id",
            "category",
            name="uq_career_memory_permissions_user_category",
        ),
        Index("ix_career_memory_permissions_user_id", "user_id"),
        Index("ix_career_memory_permissions_category", "category"),
    )

    career_memory_permission_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.user_id"),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    personalize_allowed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="private")
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


class CareerMemoryEntryRecord(Base):
    """User-provided career context that never counts as market evidence."""

    __tablename__ = "career_memory_entries"
    __table_args__ = (
        CheckConstraint(
            f"category IN ({CAREER_MEMORY_CATEGORY_SQL})",
            name="ck_career_memory_entries_category",
        ),
        CheckConstraint(
            "visibility = 'private'",
            name="ck_career_memory_entries_private",
        ),
        CheckConstraint(
            "source = 'user_provided'",
            name="ck_career_memory_entries_user_provided",
        ),
        UniqueConstraint(
            "user_id",
            "category",
            "value",
            name="uq_career_memory_entries_user_category_value",
        ),
        Index("ix_career_memory_entries_user_id", "user_id"),
        Index("ix_career_memory_entries_category", "category"),
        Index("ix_career_memory_entries_user_category", "user_id", "category"),
    )

    career_memory_entry_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.user_id"),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="private")
    source: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="user_provided",
    )
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


class CareerAgentToolRecord(Base):
    """Protected career-agent tool preview and approval state."""

    __tablename__ = "career_agent_tool_records"
    __table_args__ = (
        CheckConstraint(
            f"tool_type IN ({CAREER_AGENT_TOOL_TYPE_SQL})",
            name="ck_career_agent_tool_records_type",
        ),
        CheckConstraint(
            f"status IN ({CAREER_AGENT_TOOL_STATUS_SQL})",
            name="ck_career_agent_tool_records_status",
        ),
        CheckConstraint(
            f"action_boundary IN ({CAREER_AGENT_ACTION_BOUNDARY_SQL})",
            name="ck_career_agent_tool_records_boundary",
        ),
        CheckConstraint(
            f"privacy_classification IN ({CAREER_AGENT_TOOL_PRIVACY_SQL})",
            name="ck_career_agent_tool_records_privacy",
        ),
        CheckConstraint(
            "runtime_execution_performed = false",
            name="ck_career_agent_tool_records_no_runtime_execution",
        ),
        Index("ix_career_agent_tool_records_user_id", "user_id"),
        Index("ix_career_agent_tool_records_status", "status"),
        Index("ix_career_agent_tool_records_tool_type", "tool_type"),
        Index("ix_career_agent_tool_records_created_at", "created_at"),
    )

    career_agent_tool_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.user_id"),
        nullable=False,
    )
    tool_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    action_boundary: Mapped[str] = mapped_column(String(64), nullable=False)
    privacy_classification: Mapped[str] = mapped_column(String(64), nullable=False)
    approval_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    explicit_user_approval_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    approval_reason: Mapped[str] = mapped_column(String(1024), nullable=False)
    proposed_action_summary: Mapped[str] = mapped_column(String(2048), nullable=False)
    preview_payload: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    freshness: Mapped[dict] = mapped_column(JSON, nullable=False)
    uncertainty: Mapped[dict] = mapped_column(JSON, nullable=False)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_answer_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    source_plan_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    runtime_execution_performed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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


class CareerAgentToolAuditEventRecord(Base):
    """Append-style audit event for career-agent tool approval transitions."""

    __tablename__ = "career_agent_tool_audit_events"
    __table_args__ = (
        Index("ix_career_agent_tool_audit_tool", "career_agent_tool_id"),
        Index("ix_career_agent_tool_audit_user", "user_id"),
        Index("ix_career_agent_tool_audit_created_at", "created_at"),
    )

    career_agent_tool_audit_event_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )
    career_agent_tool_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("career_agent_tool_records.career_agent_tool_id"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.user_id"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
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
