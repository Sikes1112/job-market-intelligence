"""SQLAlchemy models for institutional organization boundaries."""

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
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.db import Base


def _utc_now() -> datetime:
    return datetime.now(UTC)


class InstitutionTimestampMixin:
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


class Organization(Base, InstitutionTimestampMixin):
    """Institutional account boundary for schools and workforce organizations."""

    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint(
            "organization_type IN ("
            "'school', "
            "'career_center', "
            "'bootcamp', "
            "'workforce_org', "
            "'economic_development_partner', "
            "'internal_demo'"
            ")",
            name="ck_organizations_type",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_organizations_status",
        ),
        Index("ix_organizations_type", "organization_type"),
        Index("ix_organizations_status", "status"),
    )

    organization_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    organization_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")


class OrganizationMembership(Base, InstitutionTimestampMixin):
    """User membership in a scoped institutional organization."""

    __tablename__ = "organization_memberships"
    __table_args__ = (
        CheckConstraint(
            "role IN ('ORG_ADMIN', 'ADVISOR', 'STUDENT', 'REPORT_VIEWER')",
            name="ck_organization_memberships_role",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_organization_memberships_status",
        ),
        UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_organization_memberships_org_user",
        ),
        Index("ix_organization_memberships_org", "organization_id"),
        Index("ix_organization_memberships_user", "user_id"),
        Index("ix_organization_memberships_role", "role"),
        Index("ix_organization_memberships_status", "status"),
    )

    organization_membership_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )
    organization_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("organizations.organization_id"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.user_id"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")


class InstitutionalAuditLog(Base):
    """Append-only institutional access and member-management audit record."""

    __tablename__ = "institutional_audit_logs"
    __table_args__ = (
        CheckConstraint(
            "actor_role IS NULL OR actor_role IN "
            "('ORG_ADMIN', 'ADVISOR', 'STUDENT', 'REPORT_VIEWER')",
            name="ck_institutional_audit_logs_actor_role",
        ),
        CheckConstraint(
            "action IN ("
            "'organization_viewed', "
            "'organization_members_viewed', "
            "'organization_member_added', "
            "'organization_member_updated', "
            "'institution_dashboard_viewed', "
            "'advisor_compare_regions_used', "
            "'advisor_compare_industries_used', "
            "'advisor_compare_companies_used', "
            "'advisor_compare_career_stages_used', "
            "'advisor_application_timing_used', "
            "'institutional_report_generated', "
            "'institutional_report_viewed', "
            "'institutional_reports_listed', "
            "'institutional_data_request_created', "
            "'institutional_data_requests_listed'"
            ")",
            name="ck_institutional_audit_logs_action",
        ),
        Index("ix_institutional_audit_logs_org", "organization_id"),
        Index("ix_institutional_audit_logs_actor", "actor_user_id"),
        Index("ix_institutional_audit_logs_action", "action"),
        Index("ix_institutional_audit_logs_target", "target_type", "target_id"),
        Index("ix_institutional_audit_logs_created_at", "created_at"),
    )

    institutional_audit_log_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )
    organization_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("organizations.organization_id"),
        nullable=False,
    )
    actor_user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.user_id"),
        nullable=False,
    )
    actor_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    purpose: Mapped[str] = mapped_column(String(512), nullable=False)
    event_metadata: Mapped[dict | list | None] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )


@event.listens_for(InstitutionalAuditLog, "before_update", propagate=True)
def _reject_institutional_audit_log_update(
    _mapper,
    _connection,
    _target,
) -> None:
    raise ValueError("institutional audit log records are append-only")


@event.listens_for(InstitutionalAuditLog, "before_delete", propagate=True)
def _reject_institutional_audit_log_delete(
    _mapper,
    _connection,
    _target,
) -> None:
    raise ValueError("institutional audit log records are append-only")


class InstitutionalReport(Base, InstitutionTimestampMixin):
    """Persisted aggregate-first institutional report payload."""

    __tablename__ = "institutional_reports"
    __table_args__ = (
        CheckConstraint(
            "report_type IN ("
            "'career_services', "
            "'program_director', "
            "'workforce_planner', "
            "'economic_development_partner'"
            ")",
            name="ck_institutional_reports_type",
        ),
        CheckConstraint(
            "status IN ('generated', 'archived')",
            name="ck_institutional_reports_status",
        ),
        Index("ix_institutional_reports_org", "organization_id"),
        Index("ix_institutional_reports_type", "report_type"),
        Index("ix_institutional_reports_generated_at", "generated_at"),
        Index("ix_institutional_reports_generated_by", "generated_by_user_id"),
    )

    institutional_report_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("organizations.organization_id"),
        nullable=False,
    )
    report_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    generated_by_user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.user_id"),
        nullable=False,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )
    payload_json: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    minimum_group_size: Mapped[int] = mapped_column(nullable=False)
    privacy_summary: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    coverage_summary: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="generated")


class InstitutionalDataRequest(Base, InstitutionTimestampMixin):
    """Auditable institutional export/deletion request record.

    Rows represent requested workflows only. They do not execute destructive
    deletion or create export packages.
    """

    __tablename__ = "institutional_data_requests"
    __table_args__ = (
        CheckConstraint(
            "request_type IN ("
            "'organization_export', "
            "'organization_deletion', "
            "'student_export', "
            "'student_deletion'"
            ")",
            name="ck_institutional_data_requests_type",
        ),
        CheckConstraint(
            "subject_type IN ('organization', 'student')",
            name="ck_institutional_data_requests_subject_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'completed', 'canceled')",
            name="ck_institutional_data_requests_status",
        ),
        Index("ix_institutional_data_requests_org", "organization_id"),
        Index("ix_institutional_data_requests_requester", "requester_user_id"),
        Index("ix_institutional_data_requests_subject_user", "subject_user_id"),
        Index("ix_institutional_data_requests_type", "request_type"),
        Index("ix_institutional_data_requests_status", "status"),
        Index("ix_institutional_data_requests_created_at", "created_at"),
    )

    institutional_data_request_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )
    organization_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("organizations.organization_id"),
        nullable=False,
    )
    requester_user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.user_id"),
        nullable=False,
    )
    request_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_user_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("users.user_id"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    reason: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    request_metadata: Mapped[dict | list | None] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
    )
