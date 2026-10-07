"""SQLAlchemy models for Layer 38A current opportunities."""

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
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.current_opportunities.schemas import (
    AcquisitionMethod,
    AcquisitionRecordStatus,
    AcquisitionRunStatus,
    AllowedUseClassification,
    CompensationInterval,
    ConfidenceLevel,
    CoverageStatus,
    EmploymentType,
    FreshnessState,
    LicenseTermsClassification,
    LocationResolutionStatus,
    NormalizationStatus,
    OpportunityKind,
    OpportunitySourceType,
    OpportunityStatus,
    RetryClassification,
    SourceOperationalStatus,
    SourceTrustClassification,
    WorkArrangement,
)
from backend.shared.db import Base


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _sql_values(values: frozenset[str]) -> str:
    return "(" + ", ".join(f"'{value}'" for value in sorted(values)) + ")"


class TimestampMixin:
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


class OpportunityDataSource(Base, TimestampMixin):
    """Governed source registry for production-current opportunity data."""

    __tablename__ = "opportunity_data_sources"
    __table_args__ = (
        CheckConstraint(
            f"source_type IN {_sql_values(OpportunitySourceType.values())}",
            name="ck_opportunity_data_sources_type",
        ),
        CheckConstraint(
            f"acquisition_method IN {_sql_values(AcquisitionMethod.values())}",
            name="ck_opportunity_data_sources_acquisition_method",
        ),
        CheckConstraint(
            f"allowed_use IN {_sql_values(AllowedUseClassification.values())}",
            name="ck_opportunity_data_sources_allowed_use",
        ),
        CheckConstraint(
            f"license_terms IN {_sql_values(LicenseTermsClassification.values())}",
            name="ck_opportunity_data_sources_license_terms",
        ),
        CheckConstraint(
            f"trust_classification IN {_sql_values(SourceTrustClassification.values())}",
            name="ck_opportunity_data_sources_trust",
        ),
        CheckConstraint(
            f"operational_status IN {_sql_values(SourceOperationalStatus.values())}",
            name="ck_opportunity_data_sources_operational_status",
        ),
        CheckConstraint("freshness_sla_hours > 0", name="ck_opportunity_sources_sla_positive"),
        Index("ix_opportunity_data_sources_provider", "provider"),
        Index("ix_opportunity_data_sources_enabled", "enabled"),
        Index("ix_opportunity_data_sources_operational_status", "operational_status"),
        Index("ix_opportunity_data_sources_ranking", "ranking_use_allowed"),
    )

    source_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    acquisition_method: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allowed_use: Mapped[str] = mapped_column(String(64), nullable=False)
    license_terms: Mapped[str] = mapped_column(String(64), nullable=False)
    trust_classification: Mapped[str] = mapped_column(String(32), nullable=False)
    freshness_sla_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    supported_domains: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    supported_markets: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    supported_opportunity_types: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    retention_classification: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ranking_use_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_use_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    refresh_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    provenance_requirements: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    operational_status: Mapped[str] = mapped_column(String(32), nullable=False)


class OpportunityAcquisitionRun(Base, TimestampMixin):
    """Auditable acquisition/refresh receipt scoped to one governed source."""

    __tablename__ = "opportunity_acquisition_runs"
    __table_args__ = (
        CheckConstraint(
            f"status IN {_sql_values(AcquisitionRunStatus.values())}",
            name="ck_opportunity_acquisition_runs_status",
        ),
        CheckConstraint(
            f"retry_classification IN {_sql_values(RetryClassification.values())}",
            name="ck_opportunity_acquisition_runs_retry",
        ),
        UniqueConstraint("idempotency_key", name="uq_opportunity_runs_idempotency_key"),
        Index("ix_opportunity_runs_source", "source_id"),
        Index("ix_opportunity_runs_status", "status"),
        Index("ix_opportunity_runs_started", "started_at"),
    )

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("opportunity_data_sources.source_id"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    requested_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cursor: Mapped[str | None] = mapped_column(String(512), nullable=True)
    checkpoint: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    retry_classification: Mapped[str] = mapped_column(String(32), nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acquired_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    normalized_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    promoted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class OpportunitySourceObservation(Base, TimestampMixin):
    """Raw source observation. This row is never canonical truth."""

    __tablename__ = "opportunity_source_observations"
    __table_args__ = (
        CheckConstraint(
            f"record_status IN {_sql_values(AcquisitionRecordStatus.values())}",
            name="ck_opportunity_source_observations_record_status",
        ),
        CheckConstraint(
            f"normalization_status IN {_sql_values(NormalizationStatus.values())}",
            name="ck_opportunity_source_observations_norm_status",
        ),
        UniqueConstraint(
            "source_id",
            "run_id",
            "provider_record_id",
            name="uq_opportunity_observation_run_record",
        ),
        Index("ix_opportunity_observations_source_record", "source_id", "provider_record_id"),
        Index("ix_opportunity_observations_run", "run_id"),
        Index("ix_opportunity_observations_hash", "payload_hash"),
        Index("ix_opportunity_observations_observed", "observed_at"),
    )

    source_observation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("opportunity_data_sources.source_id"), nullable=False
    )
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("opportunity_acquisition_runs.run_id"), nullable=False
    )
    provider_record_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_record_key: Mapped[str] = mapped_column(String(255), nullable=False)
    cursor: Mapped[str | None] = mapped_column(String(512), nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_values: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    normalized_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    record_status: Mapped[str] = mapped_column(String(32), nullable=False)
    normalization_status: Mapped[str] = mapped_column(String(32), nullable=False)
    validation_errors: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CurrentOpportunity(Base, TimestampMixin):
    """Normalized, deduplicated, product-usable current opportunity."""

    __tablename__ = "current_opportunities"
    __table_args__ = (
        CheckConstraint(
            f"work_arrangement IN {_sql_values(WorkArrangement.values())}",
            name="ck_current_opportunities_work_arrangement",
        ),
        CheckConstraint(
            f"employment_type IN {_sql_values(EmploymentType.values())}",
            name="ck_current_opportunities_employment_type",
        ),
        CheckConstraint(
            f"opportunity_type IN {_sql_values(OpportunityKind.values())}",
            name="ck_current_opportunities_kind",
        ),
        CheckConstraint(
            f"compensation_interval IN {_sql_values(CompensationInterval.values())}",
            name="ck_current_opportunities_comp_interval",
        ),
        CheckConstraint(
            f"canonical_status IN {_sql_values(OpportunityStatus.values())}",
            name="ck_current_opportunities_status",
        ),
        CheckConstraint(
            f"freshness_state IN {_sql_values(FreshnessState.values())}",
            name="ck_current_opportunities_freshness",
        ),
        CheckConstraint(
            f"normalization_confidence IN {_sql_values(ConfidenceLevel.values())}",
            name="ck_current_opportunities_norm_conf",
        ),
        CheckConstraint(
            f"identity_confidence IN {_sql_values(ConfidenceLevel.values())}",
            name="ck_current_opportunities_identity_conf",
        ),
        CheckConstraint(
            f"location_resolution_status IN {_sql_values(LocationResolutionStatus.values())}",
            name="ck_current_opportunities_location_resolution",
        ),
        UniqueConstraint("canonical_identity_key", name="uq_current_opportunities_identity_key"),
        Index("ix_current_opportunities_company", "company_id"),
        Index("ix_current_opportunities_company_name", "company_name"),
        Index("ix_current_opportunities_role_family", "role_family"),
        Index("ix_current_opportunities_market", "market_id"),
        Index(
            "ix_current_opportunities_location_resolution",
            "location_resolution_status",
        ),
        Index("ix_current_opportunities_status", "canonical_status"),
        Index("ix_current_opportunities_freshness", "freshness_state"),
        Index("ix_current_opportunities_ranking", "ranking_eligible"),
        Index("ix_current_opportunities_duplicate_group", "duplicate_group_key"),
        Index("ix_current_opportunities_last_observed", "last_observed_at"),
    )

    current_opportunity_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    canonical_identity_key: Mapped[str] = mapped_column(String(255), nullable=False)
    duplicate_group_key: Mapped[str] = mapped_column(String(255), nullable=False)
    company_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("companies.company_id"), nullable=True
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_title: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(255), nullable=False)
    role_family: Mapped[str] = mapped_column(String(64), nullable=False)
    seniority_level: Mapped[str] = mapped_column(String(64), nullable=False)
    market_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("regions.region_id"), nullable=True
    )
    market_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    location_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location_resolution_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=LocationResolutionStatus.UNRESOLVED.value
    )
    location_resolution_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    work_arrangement: Mapped[str] = mapped_column(String(32), nullable=False)
    compensation_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    compensation_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    compensation_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    compensation_interval: Mapped[str] = mapped_column(String(32), nullable=False)
    employment_type: Mapped[str] = mapped_column(String(32), nullable=False)
    opportunity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    posting_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    closing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    application_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    application_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    description_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    skills: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    requirements: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_values: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    normalization_confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    identity_confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    canonical_status: Mapped[str] = mapped_column(String(32), nullable=False)
    first_observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_collected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    canonical_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    freshness_state: Mapped[str] = mapped_column(String(32), nullable=False)
    ranking_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ranking_ineligible_reasons: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class CurrentOpportunitySourceLink(Base, TimestampMixin):
    """Relationship between a source/provider record and canonical opportunity."""

    __tablename__ = "current_opportunity_source_links"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "provider_record_id",
            name="uq_current_opportunity_source_record",
        ),
        Index("ix_current_opportunity_links_opportunity", "current_opportunity_id"),
        Index("ix_current_opportunity_links_source", "source_id"),
        Index("ix_current_opportunity_links_observation", "latest_observation_id"),
        Index("ix_current_opportunity_links_active", "active"),
    )

    current_opportunity_source_link_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    current_opportunity_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("current_opportunities.current_opportunity_id"), nullable=False
    )
    source_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("opportunity_data_sources.source_id"), nullable=False
    )
    provider_record_id: Mapped[str] = mapped_column(String(255), nullable=False)
    latest_observation_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("opportunity_source_observations.source_observation_id"),
        nullable=False,
    )
    source_identity_key: Mapped[str] = mapped_column(String(255), nullable=False)
    first_observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_collected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    application_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    identity_confidence: Mapped[str] = mapped_column(String(32), nullable=False)


class CurrentOpportunityIdentityEvidence(Base, TimestampMixin):
    """Evidence used to resolve observations into canonical opportunities."""

    __tablename__ = "current_opportunity_identity_evidence"
    __table_args__ = (
        Index("ix_current_opportunity_identity_opportunity", "current_opportunity_id"),
        Index("ix_current_opportunity_identity_observation", "source_observation_id"),
        Index("ix_current_opportunity_identity_status", "resolution_status"),
    )

    identity_evidence_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    current_opportunity_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("current_opportunities.current_opportunity_id"), nullable=False
    )
    source_observation_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("opportunity_source_observations.source_observation_id"),
        nullable=False,
    )
    source_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("opportunity_data_sources.source_id"), nullable=False
    )
    provider_record_id: Mapped[str] = mapped_column(String(255), nullable=False)
    resolution_status: Mapped[str] = mapped_column(String(64), nullable=False)
    identity_key: Mapped[str] = mapped_column(String(255), nullable=False)
    duplicate_group_key: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class OpportunityPromotionReceipt(Base, TimestampMixin):
    """Safe promotion/diff receipt for one refresh run."""

    __tablename__ = "opportunity_promotion_receipts"
    __table_args__ = (
        UniqueConstraint("run_id", name="uq_opportunity_promotion_receipts_run"),
        Index("ix_opportunity_promotion_receipts_source", "source_id"),
        Index("ix_opportunity_promotion_receipts_status", "status"),
    )

    promotion_receipt_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("opportunity_acquisition_runs.run_id"), nullable=False
    )
    source_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("opportunity_data_sources.source_id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    diff_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    semantic_warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    promoted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    closed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class OpportunityCoverageContract(Base, TimestampMixin):
    """Explicit coverage contract by market, role family, and opportunity type."""

    __tablename__ = "opportunity_coverage_contracts"
    __table_args__ = (
        CheckConstraint(
            f"status IN {_sql_values(CoverageStatus.values())}",
            name="ck_opportunity_coverage_contracts_status",
        ),
        CheckConstraint(
            "operator_override_status IS NULL OR "
            f"operator_override_status IN {_sql_values(CoverageStatus.values())}",
            name="ck_opportunity_coverage_contracts_override",
        ),
        CheckConstraint(
            "minimum_expected_sources >= 0",
            name="ck_opportunity_coverage_min_sources",
        ),
        UniqueConstraint(
            "market_key",
            "role_family",
            "opportunity_type",
            name="uq_opportunity_coverage_scope",
        ),
        Index("ix_opportunity_coverage_market", "market_key"),
        Index("ix_opportunity_coverage_role", "role_family"),
        Index("ix_opportunity_coverage_type", "opportunity_type"),
        Index("ix_opportunity_coverage_status", "status"),
    )

    coverage_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market_key: Mapped[str] = mapped_column(String(128), nullable=False)
    market_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("regions.region_id"), nullable=True
    )
    market_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    role_family: Mapped[str] = mapped_column(String(64), nullable=False)
    opportunity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    source_basis: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    minimum_expected_sources: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    freshness_max_age_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_evaluated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    operator_override_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
