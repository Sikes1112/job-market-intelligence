"""Append-only admin event log persistence model."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, Index, String, event
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.db import Base


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AdminEventLog(Base):
    """Governed admin action log.

    Rows are append-only at the ORM boundary: callers create new rows for new
    facts instead of updating or deleting historical records.
    """

    __tablename__ = "admin_event_logs"
    __table_args__ = (
        Index("ix_admin_event_logs_actor", "actor"),
        Index("ix_admin_event_logs_action", "action"),
        Index("ix_admin_event_logs_object", "object_type", "object_id"),
        Index("ix_admin_event_logs_request_id", "request_id"),
        Index("ix_admin_event_logs_timestamp", "timestamp"),
    )

    admin_event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False)
    object_id: Mapped[str] = mapped_column(String(128), nullable=False)
    before_state: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    after_state: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str] = mapped_column(String(2048), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )


@event.listens_for(AdminEventLog, "before_update", propagate=True)
def _reject_admin_event_log_update(_mapper, _connection, _target) -> None:  # noqa: ANN001
    raise ValueError("admin event log records are append-only")


@event.listens_for(AdminEventLog, "before_delete", propagate=True)
def _reject_admin_event_log_delete(_mapper, _connection, _target) -> None:  # noqa: ANN001
    raise ValueError("admin event log records are append-only")


class AdminOverride(Base):
    """Visible, auditable admin override record.

    Overrides are overlays: they never overwrite the canonical market/source
    row they reference. Downstream readers may choose to inspect active
    overrides explicitly.
    """

    __tablename__ = "admin_overrides"
    __table_args__ = (
        CheckConstraint(
            "target_type IN ('company', 'presence_fact', 'source_ref')",
            name="ck_admin_overrides_target_type",
        ),
        CheckConstraint(
            "override_type IN ("
            "'company_eligibility', "
            "'company_classification', "
            "'presence_status', "
            "'source_confidence'"
            ")",
            name="ck_admin_overrides_override_type",
        ),
        CheckConstraint(
            "status IN ('proposed', 'active', 'expired', 'revoked', 'superseded')",
            name="ck_admin_overrides_status",
        ),
        CheckConstraint(
            "expires_at IS NOT NULL OR review_at IS NOT NULL",
            name="ck_admin_overrides_expiration_or_review",
        ),
        Index("ix_admin_overrides_target", "target_type", "target_id"),
        Index("ix_admin_overrides_override_type", "override_type"),
        Index("ix_admin_overrides_status", "status"),
        Index("ix_admin_overrides_reviewer", "reviewer_actor"),
        Index("ix_admin_overrides_created_at", "created_at"),
    )

    override_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    override_type: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(
        JSON,
        nullable=True,
    )
    override_value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(
        JSON,
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(String(2048), nullable=False)
    reviewer_actor: Mapped[str] = mapped_column(String(128), nullable=False)
    reviewer_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_evidence: Mapped[dict | list | str] = mapped_column(JSON, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    review_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="proposed")
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
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    activated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    activated_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    revoked_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
    )


class AdminRepairAction(Base):
    """Visible workflow record for controlled admin repair actions."""

    __tablename__ = "admin_repair_actions"
    __table_args__ = (
        CheckConstraint(
            "action_type IN ("
            "'recompute_score', "
            "'rebuild_output', "
            "'mark_source_stale', "
            "'request_review', "
            "'deactivate_bad_fact'"
            ")",
            name="ck_admin_repair_actions_action_type",
        ),
        CheckConstraint(
            "target_type IN ("
            "'region', "
            "'output', "
            "'company', "
            "'presence_fact', "
            "'hiring_fact', "
            "'entry_level_fact', "
            "'source_ref', "
            "'audit_finding'"
            ")",
            name="ck_admin_repair_actions_target_type",
        ),
        CheckConstraint(
            "status IN ('requested', 'executed', 'failed', 'rejected')",
            name="ck_admin_repair_actions_status",
        ),
        Index("ix_admin_repair_actions_action_type", "action_type"),
        Index("ix_admin_repair_actions_target", "target_type", "target_id"),
        Index("ix_admin_repair_actions_status", "status"),
        Index("ix_admin_repair_actions_requested_by", "requested_by"),
        Index("ix_admin_repair_actions_audit_finding", "audit_finding_id"),
        Index("ix_admin_repair_actions_created_at", "created_at"),
    )

    repair_action_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="requested")
    reason: Mapped[str] = mapped_column(String(2048), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(128), nullable=False)
    requested_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )
    executed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    executed_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    audit_finding_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parameters: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    result: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
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


class AuditFindingReview(Base):
    """Persistent lifecycle state for deterministic audit findings."""

    __tablename__ = "audit_finding_reviews"
    __table_args__ = (
        CheckConstraint(
            "review_state IN ('open', 'acknowledged', 'resolved', 'dismissed', 'escalated')",
            name="ck_audit_finding_reviews_state",
        ),
        Index("ix_audit_finding_reviews_state", "review_state"),
        Index("ix_audit_finding_reviews_category", "category"),
        Index("ix_audit_finding_reviews_scope", "scope_type", "scope_ref"),
        Index("ix_audit_finding_reviews_updated_at", "updated_at"),
    )

    finding_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    review_state: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(32), nullable=True)
    scope_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scope_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    evidence_refs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    recommendation: Mapped[str | None] = mapped_column(String(2048), nullable=True)
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
    last_transitioned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )
    last_transition_actor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_transition_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_transition_reason: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
    )
