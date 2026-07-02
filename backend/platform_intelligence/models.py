"""Append-only historical intelligence records for Layer 18A.

These rows record what the platform observed or believed at a point in time.
They are intentionally not canonical truth records and do not carry update
metadata. Corrections should be represented by later rows.
"""

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
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.db import Base


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"
    __table_args__ = (
        Index("ix_market_snapshots_region_date", "region_id", "snapshot_date"),
        Index("ix_market_snapshots_type", "snapshot_type"),
        Index("ix_market_snapshots_created_at", "created_at"),
    )

    market_snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    region_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("regions.region_id"),
        nullable=False,
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    snapshot_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="observed",
    )
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_level_access_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    internship_density_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_opportunity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    product_opportunity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    company_presence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    hidden_opportunity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    coverage_tier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    freshness_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    provenance_summary: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    @property
    def id(self) -> str:
        return self.market_snapshot_id


class CompanyRegionSnapshot(Base):
    __tablename__ = "company_region_snapshots"
    __table_args__ = (
        Index(
            "ix_company_region_snapshots_company_region_date",
            "company_id",
            "region_id",
            "snapshot_date",
        ),
        Index("ix_company_region_snapshots_region", "region_id"),
        Index("ix_company_region_snapshots_type", "snapshot_type"),
        Index("ix_company_region_snapshots_created_at", "created_at"),
    )

    company_region_snapshot_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )
    company_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("companies.company_id"),
        nullable=False,
    )
    region_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("regions.region_id"),
        nullable=False,
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    snapshot_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="observed",
    )
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_level_access_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    internship_density_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_opportunity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    product_opportunity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    company_presence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    hiring_activity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    hidden_opportunity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    presence_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    currently_hiring_flag: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    active_posting_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    posting_count_30d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    posting_count_90d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    internship_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    coverage_tier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    freshness_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    provenance_summary: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    @property
    def id(self) -> str:
        return self.company_region_snapshot_id


class SectorRegionSnapshot(Base):
    __tablename__ = "sector_region_snapshots"
    __table_args__ = (
        Index(
            "ix_sector_region_snapshots_sector_region_date",
            "sector_id",
            "region_id",
            "snapshot_date",
        ),
        Index("ix_sector_region_snapshots_region", "region_id"),
        Index("ix_sector_region_snapshots_type", "snapshot_type"),
        Index("ix_sector_region_snapshots_created_at", "created_at"),
    )

    sector_region_snapshot_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )
    sector_id: Mapped[str] = mapped_column(String(64), nullable=False)
    region_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("regions.region_id"),
        nullable=False,
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    snapshot_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="observed",
    )
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_level_access_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    internship_density_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_opportunity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    product_opportunity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    company_presence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    hiring_activity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    hidden_opportunity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    sector_company_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_company_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    coverage_tier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    freshness_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    provenance_summary: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    @property
    def id(self) -> str:
        return self.sector_region_snapshot_id


class MarketScoreHistory(Base):
    __tablename__ = "market_score_history"
    __table_args__ = (
        Index("ix_market_score_history_region_date", "region_id", "snapshot_date"),
        Index("ix_market_score_history_snapshot", "market_snapshot_id"),
        Index("ix_market_score_history_score_name", "score_name"),
        Index("ix_market_score_history_created_at", "created_at"),
    )

    market_score_history_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    region_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("regions.region_id"),
        nullable=False,
    )
    market_snapshot_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("market_snapshots.market_snapshot_id"),
        nullable=True,
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    score_name: Mapped[str] = mapped_column(String(64), nullable=False)
    score_value: Mapped[float] = mapped_column(Float, nullable=False)
    score_ruleset_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ranking_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    coverage_tier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    freshness_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    provenance_summary: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    @property
    def id(self) -> str:
        return self.market_score_history_id


class HistoricalObservation(Base):
    __tablename__ = "historical_observations"
    __table_args__ = (
        CheckConstraint(
            "observation_type IN ("
            "'company_presence_increased', "
            "'company_presence_decreased', "
            "'hiring_activity_increased', "
            "'hiring_activity_decreased', "
            "'entry_level_access_improved', "
            "'entry_level_access_declined', "
            "'regional_score_increased', "
            "'regional_score_decreased', "
            "'sector_growth_detected', "
            "'sector_decline_detected', "
            "'internship_density_changed'"
            ")",
            name="ck_historical_observations_type",
        ),
        CheckConstraint(
            "target_type IN ('region', 'company_region', 'sector_region')",
            name="ck_historical_observations_target_type",
        ),
        CheckConstraint(
            "delta_direction IN ('increased', 'decreased', 'changed')",
            name="ck_historical_observations_direction",
        ),
        CheckConstraint(
            "severity IN ('low', 'medium', 'high')",
            name="ck_historical_observations_severity",
        ),
        Index("ix_historical_observations_region", "region_id"),
        Index("ix_historical_observations_target", "target_type", "target_id"),
        Index("ix_historical_observations_type", "observation_type"),
        Index("ix_historical_observations_current", "current_snapshot_id"),
        Index("ix_historical_observations_created_at", "created_at"),
    )

    historical_observation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    observation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    region_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("regions.region_id"),
        nullable=True,
    )
    previous_snapshot_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_snapshot_id: Mapped[str] = mapped_column(String(64), nullable=False)
    delta_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta_direction: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_summary: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    @property
    def id(self) -> str:
        return self.historical_observation_id


class PredictiveSignal(Base):
    __tablename__ = "predictive_signals"
    __table_args__ = (
        CheckConstraint(
            "signal_type IN ("
            "'emerging_market', "
            "'declining_market', "
            "'seasonal_hiring_window', "
            "'company_expansion_signal', "
            "'entry_level_access_trend'"
            ")",
            name="ck_predictive_signals_type",
        ),
        CheckConstraint(
            "target_type IN ('region', 'company_region', 'sector_region')",
            name="ck_predictive_signals_target_type",
        ),
        CheckConstraint(
            "signal_strength IN ('weak', 'moderate', 'strong')",
            name="ck_predictive_signals_strength",
        ),
        CheckConstraint(
            "confidence_level IN ('low', 'medium', 'high', 'unknown')",
            name="ck_predictive_signals_confidence_level",
        ),
        CheckConstraint(
            "status IN ('candidate', 'active', 'expired', 'rejected', 'superseded')",
            name="ck_predictive_signals_status",
        ),
        Index("ix_predictive_signals_region", "region_id"),
        Index("ix_predictive_signals_target", "target_type", "target_id"),
        Index("ix_predictive_signals_type", "signal_type"),
        Index("ix_predictive_signals_status", "status"),
        Index("ix_predictive_signals_created_at", "created_at"),
    )

    predictive_signal_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    signal_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    region_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("regions.region_id"),
        nullable=True,
    )
    signal_strength: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence_level: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_window_start: Mapped[date] = mapped_column(Date, nullable=False)
    evidence_window_end: Mapped[date] = mapped_column(Date, nullable=False)
    snapshot_count: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_snapshot_count_met: Mapped[bool] = mapped_column(Boolean, nullable=False)
    summary: Mapped[str] = mapped_column(String(1024), nullable=False)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    @property
    def id(self) -> str:
        return self.predictive_signal_id


class SignalInput(Base):
    __tablename__ = "signal_inputs"
    __table_args__ = (
        Index("ix_signal_inputs_signal", "predictive_signal_id"),
        Index("ix_signal_inputs_observation", "historical_observation_id"),
        Index("ix_signal_inputs_snapshot", "source_snapshot_id"),
        Index("ix_signal_inputs_type", "input_type"),
        Index("ix_signal_inputs_created_at", "created_at"),
    )

    signal_input_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    predictive_signal_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("predictive_signals.predictive_signal_id"),
        nullable=False,
    )
    source_snapshot_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    historical_observation_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("historical_observations.historical_observation_id"),
        nullable=True,
    )
    input_type: Mapped[str] = mapped_column(String(64), nullable=False)
    input_weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    contribution_strength: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    @property
    def id(self) -> str:
        return self.signal_input_id


class MarketIndex(Base):
    __tablename__ = "market_indices"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive', 'retired')",
            name="ck_market_indices_status",
        ),
        UniqueConstraint("key", name="uq_market_indices_key"),
        Index("ix_market_indices_key", "key"),
        Index("ix_market_indices_status", "status"),
        Index("ix_market_indices_created_at", "created_at"),
    )

    market_index_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    @property
    def id(self) -> str:
        return self.market_index_id


class MarketIndexVersion(Base):
    __tablename__ = "market_index_versions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'active', 'retired')",
            name="ck_market_index_versions_status",
        ),
        UniqueConstraint("index_id", "version", name="uq_market_index_versions_index"),
        Index("ix_market_index_versions_index", "index_id"),
        Index("ix_market_index_versions_status", "status"),
        Index("ix_market_index_versions_effective_date", "effective_date"),
        Index("ix_market_index_versions_created_at", "created_at"),
    )

    market_index_version_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    index_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("market_indices.market_index_id"),
        nullable=False,
    )
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    formula_description: Mapped[str] = mapped_column(String(2048), nullable=False)
    input_schema: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    internal_weight_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    @property
    def id(self) -> str:
        return self.market_index_version_id


class MarketIndexScore(Base):
    __tablename__ = "market_index_scores"
    __table_args__ = (
        Index("ix_market_index_scores_index_region", "index_id", "region_id"),
        Index("ix_market_index_scores_version", "index_version_id"),
        Index("ix_market_index_scores_region", "region_id"),
        Index("ix_market_index_scores_calculated_at", "calculated_at"),
        Index("ix_market_index_scores_created_at", "created_at"),
    )

    market_index_score_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    index_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("market_indices.market_index_id"),
        nullable=False,
    )
    index_version_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("market_index_versions.market_index_version_id"),
        nullable=False,
    )
    region_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("regions.region_id"),
        nullable=False,
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    freshness_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    evidence_summary: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    @property
    def id(self) -> str:
        return self.market_index_score_id


class MarketIndexInput(Base):
    __tablename__ = "market_index_inputs"
    __table_args__ = (
        Index("ix_market_index_inputs_score", "index_score_id"),
        Index("ix_market_index_inputs_name", "input_name"),
        Index("ix_market_index_inputs_source", "source_type", "source_id"),
        Index("ix_market_index_inputs_created_at", "created_at"),
    )

    market_index_input_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    index_score_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("market_index_scores.market_index_score_id"),
        nullable=False,
    )
    input_name: Mapped[str] = mapped_column(String(64), nullable=False)
    input_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    input_weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    @property
    def id(self) -> str:
        return self.market_index_input_id


class BenchmarkReport(Base):
    __tablename__ = "benchmark_reports"
    __table_args__ = (
        CheckConstraint(
            "report_key IN ("
            "'best_cities_early_career_ai_roles', "
            "'top_emerging_tech_markets', "
            "'best_markets_product_careers', "
            "'best_regions_internship_access'"
            ")",
            name="ck_benchmark_reports_key",
        ),
        CheckConstraint(
            "report_type IN ("
            "'early_career_ai_roles', "
            "'emerging_tech_markets', "
            "'product_careers', "
            "'internship_access'"
            ")",
            name="ck_benchmark_reports_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'review_ready', 'published', 'archived', 'superseded')",
            name="ck_benchmark_reports_status",
        ),
        Index("ix_benchmark_reports_key_status", "report_key", "status"),
        Index("ix_benchmark_reports_period", "report_period"),
        Index("ix_benchmark_reports_published_at", "published_at"),
        Index("ix_benchmark_reports_created_at", "created_at"),
    )

    benchmark_report_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    report_key: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    report_period: Mapped[str] = mapped_column(String(64), nullable=False)
    report_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str] = mapped_column(String(2048), nullable=False)
    methodology_summary: Mapped[str] = mapped_column(String(2048), nullable=False)
    data_window_start: Mapped[date] = mapped_column(Date, nullable=False)
    data_window_end: Mapped[date] = mapped_column(Date, nullable=False)
    freshness_notes: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    confidence_notes: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    coverage_notes: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    limitations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    @property
    def id(self) -> str:
        return self.benchmark_report_id


class BenchmarkReportSection(Base):
    __tablename__ = "benchmark_report_sections"
    __table_args__ = (
        UniqueConstraint("report_id", "section_key", name="uq_report_sections_key"),
        Index("ix_report_sections_report_order", "report_id", "display_order"),
        Index("ix_report_sections_created_at", "created_at"),
    )

    benchmark_report_section_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    report_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("benchmark_reports.benchmark_report_id"),
        nullable=False,
    )
    section_key: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(String(4096), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    @property
    def id(self) -> str:
        return self.benchmark_report_section_id


class BenchmarkReportRanking(Base):
    __tablename__ = "benchmark_report_rankings"
    __table_args__ = (
        UniqueConstraint("report_id", "rank", name="uq_report_rankings_rank"),
        Index("ix_report_rankings_report_rank", "report_id", "rank"),
        Index("ix_report_rankings_region", "region_id"),
        Index("ix_report_rankings_index_score", "index_score_id"),
        Index("ix_report_rankings_created_at", "created_at"),
    )

    benchmark_report_ranking_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    report_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("benchmark_reports.benchmark_report_id"),
        nullable=False,
    )
    region_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("regions.region_id"),
        nullable=False,
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    index_score_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("market_index_scores.market_index_score_id"),
        nullable=True,
    )
    explanation: Mapped[str] = mapped_column(String(2048), nullable=False)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    freshness_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    @property
    def id(self) -> str:
        return self.benchmark_report_ranking_id


class BenchmarkReportEvidence(Base):
    __tablename__ = "benchmark_report_evidence"
    __table_args__ = (
        Index("ix_report_evidence_report", "report_id"),
        Index("ix_report_evidence_target", "target_type", "target_id"),
        Index("ix_report_evidence_source", "source_type", "source_id"),
        Index("ix_report_evidence_created_at", "created_at"),
    )

    benchmark_report_evidence_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    report_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("benchmark_reports.benchmark_report_id"),
        nullable=False,
    )
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    evidence_summary: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    @property
    def id(self) -> str:
        return self.benchmark_report_evidence_id


class DataContribution(Base):
    __tablename__ = "data_contributions"
    __table_args__ = (
        CheckConstraint(
            "contributor_type IN ('user', 'institution', 'partner', 'admin')",
            name="ck_data_contributions_contributor_type",
        ),
        CheckConstraint(
            "target_type IN ("
            "'region', "
            "'company', "
            "'company_region', "
            "'sector_region', "
            "'source', "
            "'market', "
            "'role_family'"
            ")",
            name="ck_data_contributions_target_type",
        ),
        CheckConstraint(
            "contribution_type IN ("
            "'verified_correction', "
            "'company_presence_update', "
            "'regional_employer_list', "
            "'career_center_intelligence', "
            "'internship_program_information', "
            "'role_access_feedback', "
            "'source_suggestion', "
            "'market_quality_feedback', "
            "'outdated_data_report'"
            ")",
            name="ck_data_contributions_type",
        ),
        CheckConstraint(
            "status IN ("
            "'submitted', "
            "'needs_review', "
            "'verified', "
            "'rejected', "
            "'merged', "
            "'superseded'"
            ")",
            name="ck_data_contributions_status",
        ),
        CheckConstraint(
            "claimed_confidence IS NULL OR "
            "(claimed_confidence >= 0.0 AND claimed_confidence <= 1.0)",
            name="ck_data_contributions_claimed_confidence",
        ),
        Index("ix_data_contributions_type", "contribution_type"),
        Index("ix_data_contributions_status", "status"),
        Index("ix_data_contributions_target", "target_type", "target_id"),
        Index("ix_data_contributions_region", "region_id"),
        Index("ix_data_contributions_institution", "institution_id"),
        Index("ix_data_contributions_contributor", "contributor_type", "contributor_id"),
        Index("ix_data_contributions_created_at", "created_at"),
    )

    data_contribution_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    contributor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    contributor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    institution_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("organizations.organization_id"),
        nullable=True,
    )
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    region_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("regions.region_id"),
        nullable=True,
    )
    contribution_type: Mapped[str] = mapped_column(String(64), nullable=False)
    structured_payload: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    summary: Mapped[str] = mapped_column(String(1024), nullable=False)
    claimed_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    @property
    def id(self) -> str:
        return self.data_contribution_id


class ContributionEvidence(Base):
    __tablename__ = "contribution_evidence"
    __table_args__ = (
        CheckConstraint(
            "evidence_type IN ('url', 'reference', 'description', 'uploaded_reference')",
            name="ck_contribution_evidence_type",
        ),
        Index("ix_contribution_evidence_contribution", "contribution_id"),
        Index("ix_contribution_evidence_type", "evidence_type"),
        Index("ix_contribution_evidence_created_at", "created_at"),
    )

    contribution_evidence_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    contribution_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("data_contributions.data_contribution_id"),
        nullable=False,
    )
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    uploaded_reference_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    @property
    def id(self) -> str:
        return self.contribution_evidence_id


class ContributionReview(Base):
    __tablename__ = "contribution_reviews"
    __table_args__ = (
        CheckConstraint(
            "review_decision IN ('needs_review', 'verified', 'rejected', 'merged', 'superseded')",
            name="ck_contribution_reviews_decision",
        ),
        Index("ix_contribution_reviews_contribution", "contribution_id"),
        Index("ix_contribution_reviews_reviewer", "reviewer_id"),
        Index("ix_contribution_reviews_decision", "review_decision"),
        Index("ix_contribution_reviews_created_at", "created_at"),
    )

    contribution_review_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    contribution_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("data_contributions.data_contribution_id"),
        nullable=False,
    )
    reviewer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    review_decision: Mapped[str] = mapped_column(String(32), nullable=False)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    canonical_update_candidate_created: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    canonical_update_candidate_ref: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    refresh_task_created: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    refresh_task_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    @property
    def id(self) -> str:
        return self.contribution_review_id


def _prevent_append_only_update(_mapper, _connection, target) -> None:  # noqa: ANN001
    raise ValueError(f"{target.__class__.__name__} rows are append-only")


def _install_append_only_guards() -> None:
    for model in (
        MarketSnapshot,
        CompanyRegionSnapshot,
        SectorRegionSnapshot,
        MarketScoreHistory,
        HistoricalObservation,
        PredictiveSignal,
        SignalInput,
        MarketIndex,
        MarketIndexVersion,
        MarketIndexScore,
        MarketIndexInput,
        BenchmarkReportSection,
        BenchmarkReportRanking,
        BenchmarkReportEvidence,
        ContributionEvidence,
        ContributionReview,
    ):
        event.listen(model, "before_update", _prevent_append_only_update)
        event.listen(model, "before_delete", _prevent_append_only_update)
    event.listen(DataContribution, "before_delete", _prevent_append_only_update)


_install_append_only_guards()
