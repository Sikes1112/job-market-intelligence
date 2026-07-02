"""Repository for Layer 18A append-only historical intelligence tables."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.platform_intelligence.models import (
    BenchmarkReport,
    BenchmarkReportEvidence,
    BenchmarkReportRanking,
    BenchmarkReportSection,
    CompanyRegionSnapshot,
    ContributionEvidence,
    ContributionReview,
    DataContribution,
    HistoricalObservation,
    MarketIndex,
    MarketIndexInput,
    MarketIndexScore,
    MarketIndexVersion,
    MarketScoreHistory,
    MarketSnapshot,
    PredictiveSignal,
    SectorRegionSnapshot,
    SignalInput,
)


class HistoryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @property
    def session(self) -> Session:
        return self._session

    def add_market_snapshot(self, row: MarketSnapshot) -> None:
        self._session.add(row)

    def latest_market_snapshot(self, region_id: str) -> MarketSnapshot | None:
        return self._session.execute(
            select(MarketSnapshot)
            .where(MarketSnapshot.region_id == region_id)
            .order_by(
                MarketSnapshot.snapshot_date.desc(),
                MarketSnapshot.created_at.desc(),
                MarketSnapshot.market_snapshot_id.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()

    def list_market_snapshots(
        self,
        region_id: str,
        *,
        limit: int = 100,
    ) -> list[MarketSnapshot]:
        rows = self._session.execute(
            select(MarketSnapshot)
            .where(MarketSnapshot.region_id == region_id)
            .order_by(
                MarketSnapshot.snapshot_date.asc(),
                MarketSnapshot.created_at.asc(),
                MarketSnapshot.market_snapshot_id.asc(),
            )
            .limit(limit)
        ).scalars()
        return list(rows)

    def add_company_region_snapshot(self, row: CompanyRegionSnapshot) -> None:
        self._session.add(row)

    def latest_company_region_snapshot(
        self,
        *,
        company_id: str,
        region_id: str,
    ) -> CompanyRegionSnapshot | None:
        return self._session.execute(
            select(CompanyRegionSnapshot)
            .where(
                CompanyRegionSnapshot.company_id == company_id,
                CompanyRegionSnapshot.region_id == region_id,
            )
            .order_by(
                CompanyRegionSnapshot.snapshot_date.desc(),
                CompanyRegionSnapshot.created_at.desc(),
                CompanyRegionSnapshot.company_region_snapshot_id.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()

    def list_company_region_snapshots(
        self,
        company_id: str,
        *,
        limit: int = 100,
    ) -> list[CompanyRegionSnapshot]:
        rows = self._session.execute(
            select(CompanyRegionSnapshot)
            .where(CompanyRegionSnapshot.company_id == company_id)
            .order_by(
                CompanyRegionSnapshot.region_id.asc(),
                CompanyRegionSnapshot.snapshot_date.asc(),
                CompanyRegionSnapshot.created_at.asc(),
                CompanyRegionSnapshot.company_region_snapshot_id.asc(),
            )
            .limit(limit)
        ).scalars()
        return list(rows)

    def list_company_region_snapshots_for_region(
        self,
        region_id: str,
        *,
        limit: int = 500,
    ) -> list[CompanyRegionSnapshot]:
        rows = self._session.execute(
            select(CompanyRegionSnapshot)
            .where(CompanyRegionSnapshot.region_id == region_id)
            .order_by(
                CompanyRegionSnapshot.company_id.asc(),
                CompanyRegionSnapshot.snapshot_date.asc(),
                CompanyRegionSnapshot.created_at.asc(),
                CompanyRegionSnapshot.company_region_snapshot_id.asc(),
            )
            .limit(limit)
        ).scalars()
        return list(rows)

    def add_sector_region_snapshot(self, row: SectorRegionSnapshot) -> None:
        self._session.add(row)

    def latest_sector_region_snapshot(
        self,
        *,
        sector_id: str,
        region_id: str,
    ) -> SectorRegionSnapshot | None:
        return self._session.execute(
            select(SectorRegionSnapshot)
            .where(
                SectorRegionSnapshot.sector_id == sector_id,
                SectorRegionSnapshot.region_id == region_id,
            )
            .order_by(
                SectorRegionSnapshot.snapshot_date.desc(),
                SectorRegionSnapshot.created_at.desc(),
                SectorRegionSnapshot.sector_region_snapshot_id.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()

    def list_sector_region_snapshots(
        self,
        region_id: str,
        *,
        limit: int = 100,
    ) -> list[SectorRegionSnapshot]:
        rows = self._session.execute(
            select(SectorRegionSnapshot)
            .where(SectorRegionSnapshot.region_id == region_id)
            .order_by(
                SectorRegionSnapshot.sector_id.asc(),
                SectorRegionSnapshot.snapshot_date.asc(),
                SectorRegionSnapshot.created_at.asc(),
                SectorRegionSnapshot.sector_region_snapshot_id.asc(),
            )
            .limit(limit)
        ).scalars()
        return list(rows)

    def add_market_score_history(self, row: MarketScoreHistory) -> None:
        self._session.add(row)

    def list_market_score_history(
        self,
        region_id: str,
        *,
        limit: int = 500,
    ) -> list[MarketScoreHistory]:
        rows = self._session.execute(
            select(MarketScoreHistory)
            .where(MarketScoreHistory.region_id == region_id)
            .order_by(
                MarketScoreHistory.snapshot_date.asc(),
                MarketScoreHistory.score_name.asc(),
                MarketScoreHistory.created_at.asc(),
                MarketScoreHistory.market_score_history_id.asc(),
            )
            .limit(limit)
        ).scalars()
        return list(rows)

    def add_historical_observation(self, row: HistoricalObservation) -> None:
        self._session.add(row)

    def list_region_observations(
        self,
        region_id: str,
        *,
        limit: int = 100,
    ) -> list[HistoricalObservation]:
        rows = self._session.execute(
            select(HistoricalObservation)
            .where(HistoricalObservation.region_id == region_id)
            .order_by(
                HistoricalObservation.created_at.asc(),
                HistoricalObservation.historical_observation_id.asc(),
            )
            .limit(limit)
        ).scalars()
        return list(rows)

    def list_company_observations(
        self,
        company_id: str,
        *,
        limit: int = 100,
    ) -> list[HistoricalObservation]:
        rows = self._session.execute(
            select(HistoricalObservation)
            .where(
                HistoricalObservation.target_type == "company_region",
                HistoricalObservation.target_id.like(f"{company_id}:%"),
            )
            .order_by(
                HistoricalObservation.created_at.asc(),
                HistoricalObservation.historical_observation_id.asc(),
            )
            .limit(limit)
        ).scalars()
        return list(rows)

    def add_predictive_signal(self, row: PredictiveSignal) -> None:
        self._session.add(row)

    def add_signal_input(self, row: SignalInput) -> None:
        self._session.add(row)

    def list_active_region_signals(
        self,
        region_id: str,
        *,
        now,
        limit: int = 100,
    ) -> list[PredictiveSignal]:  # noqa: ANN001
        rows = self._session.execute(
            select(PredictiveSignal)
            .where(
                PredictiveSignal.region_id == region_id,
                PredictiveSignal.status == "active",
                (
                    (PredictiveSignal.expires_at.is_(None))
                    | (PredictiveSignal.expires_at > now)
                ),
            )
            .order_by(
                PredictiveSignal.created_at.desc(),
                PredictiveSignal.predictive_signal_id.desc(),
            )
            .limit(limit)
        ).scalars()
        return list(rows)

    def list_signal_inputs(self, predictive_signal_id: str) -> list[SignalInput]:
        rows = self._session.execute(
            select(SignalInput)
            .where(SignalInput.predictive_signal_id == predictive_signal_id)
            .order_by(SignalInput.created_at.asc(), SignalInput.signal_input_id.asc())
        ).scalars()
        return list(rows)

    def add_market_index(self, row: MarketIndex) -> None:
        self._session.add(row)

    def get_market_index_by_key(self, key: str) -> MarketIndex | None:
        return self._session.execute(
            select(MarketIndex).where(MarketIndex.key == key)
        ).scalar_one_or_none()

    def list_market_indices(self) -> list[MarketIndex]:
        rows = self._session.execute(
            select(MarketIndex).order_by(MarketIndex.key.asc())
        ).scalars()
        return list(rows)

    def add_market_index_version(self, row: MarketIndexVersion) -> None:
        self._session.add(row)

    def get_market_index_version(
        self,
        *,
        index_id: str,
        version: str,
    ) -> MarketIndexVersion | None:
        return self._session.execute(
            select(MarketIndexVersion).where(
                MarketIndexVersion.index_id == index_id,
                MarketIndexVersion.version == version,
            )
        ).scalar_one_or_none()

    def latest_active_index_version(self, index_id: str) -> MarketIndexVersion | None:
        return self._session.execute(
            select(MarketIndexVersion)
            .where(
                MarketIndexVersion.index_id == index_id,
                MarketIndexVersion.status == "active",
            )
            .order_by(
                MarketIndexVersion.effective_date.desc(),
                MarketIndexVersion.created_at.desc(),
                MarketIndexVersion.market_index_version_id.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()

    def list_index_versions(self, index_id: str) -> list[MarketIndexVersion]:
        rows = self._session.execute(
            select(MarketIndexVersion)
            .where(MarketIndexVersion.index_id == index_id)
            .order_by(
                MarketIndexVersion.effective_date.asc(),
                MarketIndexVersion.version.asc(),
                MarketIndexVersion.created_at.asc(),
            )
        ).scalars()
        return list(rows)

    def add_market_index_score(self, row: MarketIndexScore) -> None:
        self._session.add(row)

    def add_market_index_input(self, row: MarketIndexInput) -> None:
        self._session.add(row)

    def list_index_scores(
        self,
        index_id: str,
        *,
        limit: int = 100,
    ) -> list[MarketIndexScore]:
        rows = self._session.execute(
            select(MarketIndexScore)
            .where(MarketIndexScore.index_id == index_id)
            .order_by(
                MarketIndexScore.calculated_at.desc(),
                MarketIndexScore.rank.asc(),
                MarketIndexScore.region_id.asc(),
                MarketIndexScore.market_index_score_id.desc(),
            )
            .limit(limit)
        ).scalars()
        return list(rows)

    def list_index_inputs(self, index_score_id: str) -> list[MarketIndexInput]:
        rows = self._session.execute(
            select(MarketIndexInput)
            .where(MarketIndexInput.index_score_id == index_score_id)
            .order_by(
                MarketIndexInput.created_at.asc(),
                MarketIndexInput.market_index_input_id.asc(),
            )
        ).scalars()
        return list(rows)

    def add_benchmark_report(self, row: BenchmarkReport) -> None:
        self._session.add(row)

    def get_benchmark_report(self, report_id: str) -> BenchmarkReport | None:
        return self._session.get(BenchmarkReport, report_id)

    def list_benchmark_reports_by_key(
        self,
        report_key: str,
        *,
        status: str | None = None,
    ) -> list[BenchmarkReport]:
        stmt = select(BenchmarkReport).where(BenchmarkReport.report_key == report_key)
        if status is not None:
            stmt = stmt.where(BenchmarkReport.status == status)
        rows = self._session.execute(
            stmt.order_by(
                BenchmarkReport.created_at.desc(),
                BenchmarkReport.benchmark_report_id.desc(),
            )
        ).scalars()
        return list(rows)

    def list_published_benchmark_reports(
        self,
        *,
        limit: int = 100,
    ) -> list[BenchmarkReport]:
        rows = self._session.execute(
            select(BenchmarkReport)
            .where(BenchmarkReport.status == "published")
            .order_by(
                BenchmarkReport.published_at.desc(),
                BenchmarkReport.created_at.desc(),
                BenchmarkReport.benchmark_report_id.desc(),
            )
            .limit(limit)
        ).scalars()
        return list(rows)

    def latest_published_benchmark_report(
        self,
        report_key: str,
    ) -> BenchmarkReport | None:
        return self._session.execute(
            select(BenchmarkReport)
            .where(
                BenchmarkReport.report_key == report_key,
                BenchmarkReport.status == "published",
            )
            .order_by(
                BenchmarkReport.published_at.desc(),
                BenchmarkReport.created_at.desc(),
                BenchmarkReport.benchmark_report_id.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()

    def add_benchmark_report_section(self, row: BenchmarkReportSection) -> None:
        self._session.add(row)

    def list_report_sections(self, report_id: str) -> list[BenchmarkReportSection]:
        rows = self._session.execute(
            select(BenchmarkReportSection)
            .where(BenchmarkReportSection.report_id == report_id)
            .order_by(
                BenchmarkReportSection.display_order.asc(),
                BenchmarkReportSection.created_at.asc(),
                BenchmarkReportSection.benchmark_report_section_id.asc(),
            )
        ).scalars()
        return list(rows)

    def add_benchmark_report_ranking(self, row: BenchmarkReportRanking) -> None:
        self._session.add(row)

    def list_report_rankings(self, report_id: str) -> list[BenchmarkReportRanking]:
        rows = self._session.execute(
            select(BenchmarkReportRanking)
            .where(BenchmarkReportRanking.report_id == report_id)
            .order_by(
                BenchmarkReportRanking.rank.asc(),
                BenchmarkReportRanking.created_at.asc(),
                BenchmarkReportRanking.benchmark_report_ranking_id.asc(),
            )
        ).scalars()
        return list(rows)

    def add_benchmark_report_evidence(self, row: BenchmarkReportEvidence) -> None:
        self._session.add(row)

    def list_report_evidence(self, report_id: str) -> list[BenchmarkReportEvidence]:
        rows = self._session.execute(
            select(BenchmarkReportEvidence)
            .where(BenchmarkReportEvidence.report_id == report_id)
            .order_by(
                BenchmarkReportEvidence.created_at.asc(),
                BenchmarkReportEvidence.benchmark_report_evidence_id.asc(),
            )
        ).scalars()
        return list(rows)

    def add_data_contribution(self, row: DataContribution) -> None:
        self._session.add(row)

    def get_data_contribution(self, contribution_id: str) -> DataContribution | None:
        return self._session.get(DataContribution, contribution_id)

    def list_data_contributions_for_review(
        self,
        *,
        statuses: tuple[str, ...] = ("submitted", "needs_review"),
        limit: int = 100,
    ) -> list[DataContribution]:
        stmt = select(DataContribution)
        if statuses:
            stmt = stmt.where(DataContribution.status.in_(statuses))
        rows = self._session.execute(
            stmt.order_by(
                DataContribution.created_at.asc(),
                DataContribution.data_contribution_id.asc(),
            ).limit(limit)
        ).scalars()
        return list(rows)

    def add_contribution_evidence(self, row: ContributionEvidence) -> None:
        self._session.add(row)

    def list_contribution_evidence(
        self,
        contribution_id: str,
    ) -> list[ContributionEvidence]:
        rows = self._session.execute(
            select(ContributionEvidence)
            .where(ContributionEvidence.contribution_id == contribution_id)
            .order_by(
                ContributionEvidence.created_at.asc(),
                ContributionEvidence.contribution_evidence_id.asc(),
            )
        ).scalars()
        return list(rows)

    def add_contribution_review(self, row: ContributionReview) -> None:
        self._session.add(row)

    def list_contribution_reviews(
        self,
        contribution_id: str,
    ) -> list[ContributionReview]:
        rows = self._session.execute(
            select(ContributionReview)
            .where(ContributionReview.contribution_id == contribution_id)
            .order_by(
                ContributionReview.created_at.asc(),
                ContributionReview.contribution_review_id.asc(),
            )
        ).scalars()
        return list(rows)

    def flush(self) -> None:
        self._session.flush()
