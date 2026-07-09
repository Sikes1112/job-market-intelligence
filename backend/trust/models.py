"""Persistence models for Layer 30 trust/risk/report/recheck snapshots."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.db import Base


def _utc_now() -> datetime:
    return datetime.now(UTC)


class TrustAssessment(Base):
    """Additive trust assessment snapshot.

    Creating these rows is optional. The assessment service itself remains
    read-only and callers must explicitly persist an assessment through the
    repository when an audit snapshot is needed.
    """

    __tablename__ = "trust_assessments"
    __table_args__ = (
        UniqueConstraint(
            "subject_type",
            "subject_id",
            "assessment_version",
            "assessed_at",
            name="uq_trust_assessments_subject_version_time",
        ),
        Index("ix_trust_assessments_subject", "subject_type", "subject_id"),
        Index("ix_trust_assessments_tier", "trust_tier"),
        Index("ix_trust_assessments_assessed_at", "assessed_at"),
        Index("ix_trust_assessments_next_assessment", "next_assessment_at"),
        Index("ix_trust_assessments_created_at", "created_at"),
    )

    trust_assessment_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(128), nullable=False)
    trust_tier: Mapped[str] = mapped_column(String(64), nullable=False)
    assessment_source: Mapped[str] = mapped_column(String(128), nullable=False)
    assessment_version: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_requirements_met_json: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    evidence_requirements_missing_json: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    evidence_requirements_failed_json: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    evidence_requirements_not_applicable_json: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    warnings_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    reasons_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    ranking_influence_allowed: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_assessment_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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

    @property
    def id(self) -> str:
        return self.trust_assessment_id


class RiskRoutingDecision(Base):
    """Additive Layer 30B risk and ranking decision snapshot."""

    __tablename__ = "risk_routing_decisions"
    __table_args__ = (
        UniqueConstraint(
            "subject_type",
            "subject_id",
            "decision_version",
            "decided_at",
            name="uq_risk_routing_decisions_subject_version_time",
        ),
        Index("ix_risk_routing_decisions_subject", "subject_type", "subject_id"),
        Index("ix_risk_routing_decisions_risk", "risk_level"),
        Index("ix_risk_routing_decisions_outcome", "routing_outcome"),
        Index(
            "ix_risk_routing_decisions_ranking_allowed",
            "ranking_influence_allowed",
        ),
        Index("ix_risk_routing_decisions_decided_at", "decided_at"),
        Index("ix_risk_routing_decisions_created_at", "created_at"),
    )

    risk_routing_decision_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )
    subject_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(128), nullable=False)
    trust_assessment_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    trust_tier: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)
    routing_outcome: Mapped[str] = mapped_column(String(64), nullable=False)
    routing_reasons_json: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    ranking_influence_decision: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    ranking_influence_allowed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    ranking_influence_reason: Mapped[str] = mapped_column(String(512), nullable=False)
    ranking_influence_reason_codes_json: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    evidence_requirements_met_json: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    evidence_requirements_missing_json: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    evidence_requirements_failed_json: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    warnings_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    decision_source: Mapped[str] = mapped_column(String(128), nullable=False)
    decision_version: Mapped[str] = mapped_column(String(64), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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

    @property
    def id(self) -> str:
        return self.risk_routing_decision_id


class UserReport(Base):
    """Append-only user report signal.

    Reports are product feedback inputs. They do not edit canonical truth,
    ranking flags, trust tiers, risk levels, or source records.
    """

    __tablename__ = "user_reports"
    __table_args__ = (
        Index("ix_user_reports_subject", "subject_type", "subject_id"),
        Index("ix_user_reports_type", "report_type"),
        Index("ix_user_reports_severity", "severity"),
        Index("ix_user_reports_status", "status"),
        Index("ix_user_reports_created_at", "created_at"),
    )

    user_report_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(128), nullable=False)
    report_type: Mapped[str] = mapped_column(String(64), nullable=False)
    report_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reporter_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reporter_session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    source_surface: Mapped[str | None] = mapped_column(String(128), nullable=True)
    related_trust_assessment_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    related_risk_routing_decision_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    created_recheck_job_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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

    @property
    def id(self) -> str:
        return self.user_report_id


class AutomatedRecheckJob(Base):
    """Deterministic recheck job signal for trust/risk recomputation."""

    __tablename__ = "automated_recheck_jobs"
    __table_args__ = (
        Index("ix_automated_recheck_jobs_subject", "subject_type", "subject_id"),
        Index("ix_automated_recheck_jobs_trigger", "trigger_type"),
        Index("ix_automated_recheck_jobs_status", "status"),
        Index("ix_automated_recheck_jobs_priority", "priority"),
        Index("ix_automated_recheck_jobs_scheduled_for", "scheduled_for"),
        Index("ix_automated_recheck_jobs_created_at", "created_at"),
    )

    automated_recheck_job_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )
    subject_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(128), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(64), nullable=False)
    trigger_source: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    priority: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_codes_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    related_user_report_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    related_trust_assessment_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    related_risk_routing_decision_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    scheduled_for: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    outcome: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outcome_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    @property
    def id(self) -> str:
        return self.automated_recheck_job_id


class ExceptionCase(Base):
    """Rare unresolved trust/risk exception case.

    Exception cases are not normal approval records. They are created only for
    serious unresolved signals that automated trust, risk, and recheck flows
    cannot safely resolve.
    """

    __tablename__ = "exception_cases"
    __table_args__ = (
        Index("ix_exception_cases_subject", "subject_type", "subject_id"),
        Index("ix_exception_cases_type", "exception_type"),
        Index("ix_exception_cases_status", "status"),
        Index("ix_exception_cases_severity", "severity"),
        Index("ix_exception_cases_public_status", "public_safe_status"),
        Index("ix_exception_cases_created_at", "created_at"),
    )

    exception_case_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(128), nullable=False)
    exception_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    reason_codes_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    summary: Mapped[str] = mapped_column(String(512), nullable=False)
    related_user_report_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    related_recheck_job_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    related_trust_assessment_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    related_risk_routing_decision_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    public_safe_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolution_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
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

    @property
    def id(self) -> str:
        return self.exception_case_id
