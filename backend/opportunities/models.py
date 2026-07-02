"""SQLAlchemy models for Layer 23A opportunity infrastructure."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.opportunities.schemas import (
    OpportunityBindingConfidence,
    OpportunityLocationMode,
    OpportunityProgramType,
    OpportunityReviewAction,
    OpportunityReviewStatus,
    OpportunitySeniorityLevel,
    OpportunitySourceType,
    OpportunitySubmissionStatus,
    OpportunityTrustLabel,
)
from backend.shared.db import Base


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _sql_values(values: frozenset[str]) -> str:
    return "(" + ", ".join(f"'{value}'" for value in sorted(values)) + ")"


class OpportunityTimestampMixin:
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


class EmployerProgram(Base, OpportunityTimestampMixin):
    """Stable employer program identity separate from an individual opportunity."""

    __tablename__ = "employer_programs"
    __table_args__ = (
        CheckConstraint(
            f"program_type IN {_sql_values(OpportunityProgramType.values())}",
            name="ck_employer_programs_type",
        ),
        Index("ix_employer_programs_employer", "employer_id"),
        Index("ix_employer_programs_employer_name", "employer_name"),
        Index("ix_employer_programs_type", "program_type"),
        Index("ix_employer_programs_created_at", "created_at"),
    )

    employer_program_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    employer_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("companies.company_id"),
        nullable=True,
    )
    employer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    program_name: Mapped[str] = mapped_column(String(255), nullable=False)
    program_type: Mapped[str] = mapped_column(String(64), nullable=False)
    program_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    @property
    def id(self) -> str:
        return self.employer_program_id


class Opportunity(Base, OpportunityTimestampMixin):
    """Structured early-career opportunity record.

    Opportunities are independent marketplace records. They attach evidence and
    trust metadata but do not own or update objective market intelligence.
    """

    __tablename__ = "opportunities"
    __table_args__ = (
        CheckConstraint(
            f"program_type IN {_sql_values(OpportunityProgramType.values())}",
            name="ck_opportunities_program_type",
        ),
        CheckConstraint(
            f"location_mode IN {_sql_values(OpportunityLocationMode.values())}",
            name="ck_opportunities_location_mode",
        ),
        CheckConstraint(
            f"seniority_level IN {_sql_values(OpportunitySeniorityLevel.values())}",
            name="ck_opportunities_seniority_level",
        ),
        CheckConstraint(
            f"source_type IN {_sql_values(OpportunitySourceType.values())}",
            name="ck_opportunities_source_type",
        ),
        CheckConstraint(
            f"trust_label IN {_sql_values(OpportunityTrustLabel.values())}",
            name="ck_opportunities_trust_label",
        ),
        CheckConstraint(
            f"review_status IN {_sql_values(OpportunityReviewStatus.values())}",
            name="ck_opportunities_review_status",
        ),
        CheckConstraint(
            "compensation_min IS NULL OR compensation_min >= 0.0",
            name="ck_opportunities_compensation_min_nonnegative",
        ),
        CheckConstraint(
            "compensation_max IS NULL OR compensation_max >= 0.0",
            name="ck_opportunities_compensation_max_nonnegative",
        ),
        CheckConstraint(
            "compensation_min IS NULL OR compensation_max IS NULL "
            "OR compensation_max >= compensation_min",
            name="ck_opportunities_compensation_bounds",
        ),
        Index("ix_opportunities_program", "employer_program_id"),
        Index("ix_opportunities_employer", "employer_id"),
        Index("ix_opportunities_employer_name", "employer_name"),
        Index("ix_opportunities_program_type", "program_type"),
        Index("ix_opportunities_location_mode", "location_mode"),
        Index("ix_opportunities_seniority_level", "seniority_level"),
        Index("ix_opportunities_trust_label", "trust_label"),
        Index("ix_opportunities_review_status", "review_status"),
        Index("ix_opportunities_application_deadline", "application_deadline"),
        Index("ix_opportunities_expires_at", "expires_at"),
        Index("ix_opportunities_created_at", "created_at"),
    )

    opportunity_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    employer_program_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("employer_programs.employer_program_id"),
        nullable=False,
    )
    employer_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("companies.company_id"),
        nullable=True,
    )
    employer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    program_name: Mapped[str] = mapped_column(String(255), nullable=False)
    program_type: Mapped[str] = mapped_column(String(64), nullable=False)
    location_mode: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=OpportunityLocationMode.UNKNOWN.value,
    )
    seniority_level: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=OpportunitySeniorityLevel.UNKNOWN.value,
    )
    eligibility_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    application_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    application_open_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    application_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    compensation_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    compensation_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    compensation_disclosed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    trust_label: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=OpportunityTrustLabel.UNVERIFIED.value,
    )
    review_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=OpportunityReviewStatus.PENDING_REVIEW.value,
    )

    @property
    def id(self) -> str:
        return self.opportunity_id


class OpportunitySource(Base):
    """Source evidence attached to an opportunity record."""

    __tablename__ = "opportunity_sources"
    __table_args__ = (
        CheckConstraint(
            f"source_type IN {_sql_values(OpportunitySourceType.values())}",
            name="ck_opportunity_sources_type",
        ),
        Index("ix_opportunity_sources_opportunity", "opportunity_id"),
        Index("ix_opportunity_sources_type", "source_type"),
        Index("ix_opportunity_sources_created_at", "created_at"),
    )

    opportunity_source_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    opportunity_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("opportunities.opportunity_id"),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    collected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    verification_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )

    @property
    def id(self) -> str:
        return self.opportunity_source_id


class OpportunityRegionBinding(Base):
    """Region or metro binding for an opportunity."""

    __tablename__ = "opportunity_region_bindings"
    __table_args__ = (
        CheckConstraint(
            f"binding_confidence IN {_sql_values(OpportunityBindingConfidence.values())}",
            name="ck_opportunity_region_bindings_confidence",
        ),
        Index("ix_opportunity_region_bindings_opportunity", "opportunity_id"),
        Index("ix_opportunity_region_bindings_region", "region_id"),
        Index("ix_opportunity_region_bindings_label", "region_label"),
        Index("ix_opportunity_region_bindings_created_at", "created_at"),
    )

    opportunity_region_binding_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )
    opportunity_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("opportunities.opportunity_id"),
        nullable=False,
    )
    region_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("regions.region_id"),
        nullable=True,
    )
    region_label: Mapped[str] = mapped_column(String(128), nullable=False)
    metro_area: Mapped[str | None] = mapped_column(String(128), nullable=True)
    binding_confidence: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=OpportunityBindingConfidence.UNKNOWN.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )

    @property
    def id(self) -> str:
        return self.opportunity_region_binding_id


class OpportunityRoleFamilyBinding(Base):
    """Role-family binding for an opportunity."""

    __tablename__ = "opportunity_role_family_bindings"
    __table_args__ = (
        CheckConstraint(
            f"binding_confidence IN {_sql_values(OpportunityBindingConfidence.values())}",
            name="ck_opportunity_role_family_bindings_confidence",
        ),
        Index("ix_opportunity_role_family_bindings_opportunity", "opportunity_id"),
        Index("ix_opportunity_role_family_bindings_role", "role_family"),
        Index("ix_opportunity_role_family_bindings_created_at", "created_at"),
    )

    opportunity_role_family_binding_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )
    opportunity_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("opportunities.opportunity_id"),
        nullable=False,
    )
    role_family: Mapped[str] = mapped_column(String(64), nullable=False)
    role_family_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    binding_confidence: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=OpportunityBindingConfidence.UNKNOWN.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )

    @property
    def id(self) -> str:
        return self.opportunity_role_family_binding_id


class EmployerInfluenceMetadata(Base, OpportunityTimestampMixin):
    """Employer/partner influence metadata isolated from scoring authority."""

    __tablename__ = "employer_influence_metadata"
    __table_args__ = (
        CheckConstraint(
            "ranking_influence_allowed = false",
            name="ck_employer_influence_metadata_no_ranking_influence",
        ),
        UniqueConstraint(
            "opportunity_id",
            name="uq_employer_influence_metadata_opportunity",
        ),
        Index("ix_employer_influence_metadata_opportunity", "opportunity_id"),
        Index("ix_employer_influence_metadata_partner", "partner_submitted"),
        Index("ix_employer_influence_metadata_paid", "paid_partner"),
        Index("ix_employer_influence_metadata_created_at", "created_at"),
    )

    employer_influence_metadata_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )
    opportunity_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("opportunities.opportunity_id"),
        nullable=False,
    )
    partner_submitted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    paid_partner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ranking_influence_allowed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    submitted_by_partner_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    paid_partner_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    internal_review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def id(self) -> str:
        return self.employer_influence_metadata_id


class OpportunitySubmission(Base):
    """Employer or partner submitted opportunity intake record."""

    __tablename__ = "opportunity_submissions"
    __table_args__ = (
        CheckConstraint(
            f"status IN {_sql_values(OpportunitySubmissionStatus.values())}",
            name="ck_opportunity_submissions_status",
        ),
        UniqueConstraint("opportunity_id", name="uq_opportunity_submissions_opportunity"),
        Index("ix_opportunity_submissions_opportunity", "opportunity_id"),
        Index("ix_opportunity_submissions_status", "status"),
        Index("ix_opportunity_submissions_partner", "partner_organization_id"),
        Index("ix_opportunity_submissions_submitted_at", "submitted_at"),
        Index("ix_opportunity_submissions_created_at", "created_at"),
    )

    opportunity_submission_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )
    opportunity_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("opportunities.opportunity_id"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=OpportunitySubmissionStatus.PENDING_REVIEW.value,
    )
    submitter_contact: Mapped[str] = mapped_column(String(255), nullable=False)
    submitted_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    submission_source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    partner_organization_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    partner_organization_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    paid_partner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    paid_partner_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raw_submission_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )

    @property
    def id(self) -> str:
        return self.opportunity_submission_id


class OpportunityReviewActionRecord(Base):
    """Append-only internal review action for a submitted opportunity."""

    __tablename__ = "opportunity_review_actions"
    __table_args__ = (
        CheckConstraint(
            f"review_action IN {_sql_values(OpportunityReviewAction.values())}",
            name="ck_opportunity_review_actions_action",
        ),
        CheckConstraint(
            f"resulting_trust_label IN {_sql_values(OpportunityTrustLabel.values())}",
            name="ck_opportunity_review_actions_trust_label",
        ),
        CheckConstraint(
            f"resulting_review_status IN {_sql_values(OpportunityReviewStatus.values())}",
            name="ck_opportunity_review_actions_review_status",
        ),
        CheckConstraint(
            "ranking_influence_allowed = false",
            name="ck_opportunity_review_actions_no_ranking_influence",
        ),
        Index("ix_opportunity_review_actions_submission", "submission_id"),
        Index("ix_opportunity_review_actions_opportunity", "opportunity_id"),
        Index("ix_opportunity_review_actions_action", "review_action"),
        Index("ix_opportunity_review_actions_reviewed_at", "reviewed_at"),
        Index("ix_opportunity_review_actions_created_at", "created_at"),
    )

    opportunity_review_action_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )
    submission_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("opportunity_submissions.opportunity_submission_id"),
        nullable=False,
    )
    opportunity_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("opportunities.opportunity_id"),
        nullable=False,
    )
    review_action: Mapped[str] = mapped_column(String(64), nullable=False)
    resulting_trust_label: Mapped[str] = mapped_column(String(32), nullable=False)
    resulting_review_status: Mapped[str] = mapped_column(String(32), nullable=False)
    ranking_influence_allowed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    reviewer_id: Mapped[str] = mapped_column(String(128), nullable=False)
    reviewer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    correction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url_checked: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    official_employer_url: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
    )
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )

    @property
    def id(self) -> str:
        return self.opportunity_review_action_id


def _prevent_opportunity_update(_mapper, _connection, target) -> None:  # noqa: ANN001
    raise ValueError(f"{target.__class__.__name__} rows are additive-only")


def _install_additive_only_guards() -> None:
    for model in (
        EmployerProgram,
        Opportunity,
        OpportunitySource,
        OpportunityRegionBinding,
        OpportunityRoleFamilyBinding,
        EmployerInfluenceMetadata,
        OpportunitySubmission,
        OpportunityReviewActionRecord,
    ):
        event.listen(model, "before_update", _prevent_opportunity_update, propagate=True)
        event.listen(model, "before_delete", _prevent_opportunity_update, propagate=True)


_install_additive_only_guards()
