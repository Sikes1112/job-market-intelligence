"""Layer 18A historical snapshot service.

The service writes only append-only historical tables and derives observations
from adjacent snapshots. It does not recompute current scores or update
canonical market records.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import NamedTuple
from uuid import uuid4

from backend.platform_intelligence.delta_detection import (
    detect_company_region_snapshot_deltas,
    detect_market_snapshot_deltas,
    detect_sector_region_snapshot_deltas,
)
from backend.platform_intelligence.history_repository import HistoryRepository
from backend.platform_intelligence.models import (
    CompanyRegionSnapshot,
    HistoricalObservation,
    MarketScoreHistory,
    MarketSnapshot,
    SectorRegionSnapshot,
)
from backend.platform_intelligence.observations import make_historical_observation
from backend.platform_intelligence.schemas import (
    CompanyHistorySummary,
    CompanyRegionSnapshotCreate,
    CompanyRegionSnapshotSummary,
    HistoricalObservationSummary,
    MarketSnapshotCreate,
    MarketSnapshotSummary,
    RegionHistorySummary,
    SectorRegionSnapshotCreate,
    SectorRegionSnapshotSummary,
)


class SnapshotRecordResult(NamedTuple):
    snapshot: MarketSnapshot | CompanyRegionSnapshot | SectorRegionSnapshot
    observations: tuple[HistoricalObservation, ...]


class HistoricalSnapshotService:
    def __init__(self, repository: HistoryRepository) -> None:
        self._repo = repository

    def record_market_snapshot(
        self,
        request: MarketSnapshotCreate,
    ) -> SnapshotRecordResult:
        previous = self._repo.latest_market_snapshot(request.region_id)
        created_at = request.created_at or datetime.now(UTC)
        row = MarketSnapshot(
            market_snapshot_id=request.market_snapshot_id or _new_id("market_snapshot"),
            region_id=request.region_id,
            snapshot_date=request.snapshot_date,
            snapshot_type=request.snapshot_type.value,
            overall_score=request.overall_score,
            entry_level_access_score=request.entry_level_access_score,
            internship_density_score=request.internship_density_score,
            ai_opportunity_score=request.ai_opportunity_score,
            product_opportunity_score=request.product_opportunity_score,
            company_presence_score=request.company_presence_score,
            hidden_opportunity_score=request.hidden_opportunity_score,
            coverage_tier=request.coverage_tier,
            freshness_state=request.freshness_state,
            confidence_score=request.confidence_score,
            warnings=list(request.warnings),
            provenance_summary=request.provenance_summary,
            created_at=created_at,
        )
        self._repo.add_market_snapshot(row)
        self._repo.flush()

        for score_row in _score_history_rows(request, row, created_at=created_at):
            self._repo.add_market_score_history(score_row)

        observations = tuple(
            make_historical_observation(draft, created_at=created_at)
            for draft in detect_market_snapshot_deltas(previous, row)
        )
        for observation in observations:
            self._repo.add_historical_observation(observation)
        self._repo.flush()
        return SnapshotRecordResult(snapshot=row, observations=observations)

    def record_company_region_snapshot(
        self,
        request: CompanyRegionSnapshotCreate,
    ) -> SnapshotRecordResult:
        previous = self._repo.latest_company_region_snapshot(
            company_id=request.company_id,
            region_id=request.region_id,
        )
        created_at = request.created_at or datetime.now(UTC)
        row = CompanyRegionSnapshot(
            company_region_snapshot_id=(
                request.company_region_snapshot_id
                or _new_id("company_region_snapshot")
            ),
            company_id=request.company_id,
            region_id=request.region_id,
            snapshot_date=request.snapshot_date,
            snapshot_type=request.snapshot_type.value,
            overall_score=request.overall_score,
            entry_level_access_score=request.entry_level_access_score,
            internship_density_score=request.internship_density_score,
            ai_opportunity_score=request.ai_opportunity_score,
            product_opportunity_score=request.product_opportunity_score,
            company_presence_score=request.company_presence_score,
            hiring_activity_score=request.hiring_activity_score,
            hidden_opportunity_score=request.hidden_opportunity_score,
            presence_status=request.presence_status,
            currently_hiring_flag=request.currently_hiring_flag,
            active_posting_count=request.active_posting_count,
            posting_count_30d=request.posting_count_30d,
            posting_count_90d=request.posting_count_90d,
            internship_count=request.internship_count,
            coverage_tier=request.coverage_tier,
            freshness_state=request.freshness_state,
            confidence_score=request.confidence_score,
            warnings=list(request.warnings),
            provenance_summary=request.provenance_summary,
            created_at=created_at,
        )
        self._repo.add_company_region_snapshot(row)
        self._repo.flush()

        observations = tuple(
            make_historical_observation(draft, created_at=created_at)
            for draft in detect_company_region_snapshot_deltas(previous, row)
        )
        for observation in observations:
            self._repo.add_historical_observation(observation)
        self._repo.flush()
        return SnapshotRecordResult(snapshot=row, observations=observations)

    def record_sector_region_snapshot(
        self,
        request: SectorRegionSnapshotCreate,
    ) -> SnapshotRecordResult:
        previous = self._repo.latest_sector_region_snapshot(
            sector_id=request.sector_id,
            region_id=request.region_id,
        )
        created_at = request.created_at or datetime.now(UTC)
        row = SectorRegionSnapshot(
            sector_region_snapshot_id=(
                request.sector_region_snapshot_id or _new_id("sector_region_snapshot")
            ),
            sector_id=request.sector_id,
            region_id=request.region_id,
            snapshot_date=request.snapshot_date,
            snapshot_type=request.snapshot_type.value,
            overall_score=request.overall_score,
            entry_level_access_score=request.entry_level_access_score,
            internship_density_score=request.internship_density_score,
            ai_opportunity_score=request.ai_opportunity_score,
            product_opportunity_score=request.product_opportunity_score,
            company_presence_score=request.company_presence_score,
            hiring_activity_score=request.hiring_activity_score,
            hidden_opportunity_score=request.hidden_opportunity_score,
            sector_company_count=request.sector_company_count,
            active_company_count=request.active_company_count,
            coverage_tier=request.coverage_tier,
            freshness_state=request.freshness_state,
            confidence_score=request.confidence_score,
            warnings=list(request.warnings),
            provenance_summary=request.provenance_summary,
            created_at=created_at,
        )
        self._repo.add_sector_region_snapshot(row)
        self._repo.flush()

        observations = tuple(
            make_historical_observation(draft, created_at=created_at)
            for draft in detect_sector_region_snapshot_deltas(previous, row)
        )
        for observation in observations:
            self._repo.add_historical_observation(observation)
        self._repo.flush()
        return SnapshotRecordResult(snapshot=row, observations=observations)

    def region_history(self, region_id: str, *, limit: int = 100) -> RegionHistorySummary:
        market_snapshots = tuple(
            _market_summary(row)
            for row in self._repo.list_market_snapshots(region_id, limit=limit)
        )
        sector_snapshots = tuple(
            _sector_summary(row)
            for row in self._repo.list_sector_region_snapshots(region_id, limit=limit)
        )
        observations = tuple(
            _observation_summary(row)
            for row in self._repo.list_region_observations(region_id, limit=limit)
        )
        latest = market_snapshots[-1] if market_snapshots else None
        coverage_context = (
            {
                "coverage_tier": latest.coverage_tier,
                "freshness_state": latest.freshness_state,
                "confidence_score": latest.confidence_score,
            }
            if latest is not None
            else {}
        )
        return RegionHistorySummary(
            region_id=region_id,
            market_snapshots=market_snapshots,
            sector_snapshots=sector_snapshots,
            observations=observations,
            coverage_context=coverage_context,
        )

    def company_history(self, company_id: str, *, limit: int = 100) -> CompanyHistorySummary:
        snapshots = tuple(
            _company_region_summary(row)
            for row in self._repo.list_company_region_snapshots(company_id, limit=limit)
        )
        observations = tuple(
            _observation_summary(row)
            for row in self._repo.list_company_observations(company_id, limit=limit)
        )
        return CompanyHistorySummary(
            company_id=company_id,
            region_snapshots=snapshots,
            observations=observations,
        )


def _score_history_rows(
    request: MarketSnapshotCreate,
    snapshot: MarketSnapshot,
    *,
    created_at: datetime,
) -> tuple[MarketScoreHistory, ...]:
    rows: list[MarketScoreHistory] = []
    for score_name in (
        "overall_score",
        "entry_level_access_score",
        "internship_density_score",
        "ai_opportunity_score",
        "product_opportunity_score",
        "company_presence_score",
        "hidden_opportunity_score",
    ):
        score_value = getattr(request, score_name)
        if score_value is None:
            continue
        rows.append(
            MarketScoreHistory(
                market_score_history_id=_new_id("market_score_history"),
                region_id=request.region_id,
                market_snapshot_id=snapshot.market_snapshot_id,
                snapshot_date=request.snapshot_date,
                score_name=score_name,
                score_value=score_value,
                score_ruleset_version=request.score_ruleset_version,
                ranking_position=request.ranking_position,
                coverage_tier=request.coverage_tier,
                freshness_state=request.freshness_state,
                confidence_score=request.confidence_score,
                warnings=list(request.warnings),
                provenance_summary=request.provenance_summary,
                created_at=created_at,
            )
        )
    return tuple(rows)


def _market_summary(row: MarketSnapshot) -> MarketSnapshotSummary:
    return MarketSnapshotSummary(
        snapshot_id=row.market_snapshot_id,
        region_id=row.region_id,
        snapshot_date=row.snapshot_date,
        snapshot_type=row.snapshot_type,
        overall_score=row.overall_score,
        entry_level_access_score=row.entry_level_access_score,
        internship_density_score=row.internship_density_score,
        ai_opportunity_score=row.ai_opportunity_score,
        product_opportunity_score=row.product_opportunity_score,
        company_presence_score=row.company_presence_score,
        hidden_opportunity_score=row.hidden_opportunity_score,
        coverage_tier=row.coverage_tier,
        freshness_state=row.freshness_state,
        confidence_score=row.confidence_score,
        warnings=tuple(row.warnings or ()),
        created_at=row.created_at,
    )


def _company_region_summary(row: CompanyRegionSnapshot) -> CompanyRegionSnapshotSummary:
    return CompanyRegionSnapshotSummary(
        snapshot_id=row.company_region_snapshot_id,
        company_id=row.company_id,
        region_id=row.region_id,
        snapshot_date=row.snapshot_date,
        snapshot_type=row.snapshot_type,
        overall_score=row.overall_score,
        entry_level_access_score=row.entry_level_access_score,
        internship_density_score=row.internship_density_score,
        ai_opportunity_score=row.ai_opportunity_score,
        product_opportunity_score=row.product_opportunity_score,
        company_presence_score=row.company_presence_score,
        hiring_activity_score=row.hiring_activity_score,
        hidden_opportunity_score=row.hidden_opportunity_score,
        presence_status=row.presence_status,
        currently_hiring_flag=row.currently_hiring_flag,
        active_posting_count=row.active_posting_count,
        posting_count_30d=row.posting_count_30d,
        posting_count_90d=row.posting_count_90d,
        internship_count=row.internship_count,
        coverage_tier=row.coverage_tier,
        freshness_state=row.freshness_state,
        confidence_score=row.confidence_score,
        warnings=tuple(row.warnings or ()),
        created_at=row.created_at,
    )


def _sector_summary(row: SectorRegionSnapshot) -> SectorRegionSnapshotSummary:
    return SectorRegionSnapshotSummary(
        snapshot_id=row.sector_region_snapshot_id,
        sector_id=row.sector_id,
        region_id=row.region_id,
        snapshot_date=row.snapshot_date,
        snapshot_type=row.snapshot_type,
        overall_score=row.overall_score,
        entry_level_access_score=row.entry_level_access_score,
        internship_density_score=row.internship_density_score,
        ai_opportunity_score=row.ai_opportunity_score,
        product_opportunity_score=row.product_opportunity_score,
        company_presence_score=row.company_presence_score,
        hiring_activity_score=row.hiring_activity_score,
        hidden_opportunity_score=row.hidden_opportunity_score,
        sector_company_count=row.sector_company_count,
        active_company_count=row.active_company_count,
        coverage_tier=row.coverage_tier,
        freshness_state=row.freshness_state,
        confidence_score=row.confidence_score,
        warnings=tuple(row.warnings or ()),
        created_at=row.created_at,
    )


def _observation_summary(row: HistoricalObservation) -> HistoricalObservationSummary:
    return HistoricalObservationSummary(
        observation_id=row.historical_observation_id,
        observation_type=row.observation_type,
        target_type=row.target_type,
        target_id=row.target_id,
        region_id=row.region_id,
        previous_snapshot_id=row.previous_snapshot_id,
        current_snapshot_id=row.current_snapshot_id,
        delta_value=row.delta_value,
        delta_direction=row.delta_direction,
        severity=row.severity,
        confidence_score=row.confidence_score,
        evidence_summary=row.evidence_summary,
        created_at=row.created_at,
    )


def _new_id(prefix: str) -> str:
    suffix_length = max(8, 63 - len(prefix))
    return f"{prefix}_{uuid4().hex[:suffix_length]}"
