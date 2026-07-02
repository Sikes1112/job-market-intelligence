from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.models import Region
from backend.platform_intelligence.history_repository import HistoryRepository
from backend.platform_intelligence.models import (
    CompanyRegionSnapshot,
    HistoricalObservation,
    MarketScoreHistory,
    MarketSnapshot,
    SectorRegionSnapshot,
)
from backend.platform_intelligence.schemas import (
    CompanyRegionSnapshotCreate,
    MarketSnapshotCreate,
    SectorRegionSnapshotCreate,
)
from backend.platform_intelligence.snapshots import HistoricalSnapshotService
from backend.scoring.models import RegionMarketScore

JAN_1 = date(2026, 1, 1)
FEB_1 = date(2026, 2, 1)
MAR_1 = date(2026, 3, 1)


def _service(session: Session) -> HistoricalSnapshotService:
    return HistoricalSnapshotService(HistoryRepository(session))


def _seed_region(session: Session, region_id: str = "greater_boston") -> None:
    session.add(
        Region(
            region_id=region_id,
            region_name=region_id,
            display_name=region_id.replace("_", " ").title(),
            region_type="greater_region",
        )
    )
    session.flush()


def _seed_company(session: Session, company_id: str = "comp_a") -> None:
    session.add(
        Company(
            company_id=company_id,
            company_name=company_id,
            normalized_company_name=company_id,
            eligibility_status="eligible",
        )
    )
    session.flush()


def _seed_market_score(session: Session, region_id: str = "greater_boston") -> None:
    session.add(
        RegionMarketScore(
            region_score_id=f"score_{region_id}",
            region_id=region_id,
            objective_opportunity_score=0.71,
            early_career_accessibility_score=0.63,
            score_ruleset_version="marketscore_v1",
        )
    )
    session.flush()


def test_region_company_and_sector_snapshot_creation_works(session: Session) -> None:
    _seed_region(session)
    _seed_company(session)
    service = _service(session)

    region_result = service.record_market_snapshot(
        MarketSnapshotCreate(
            market_snapshot_id="market_snap_1",
            region_id="greater_boston",
            snapshot_date=JAN_1,
            overall_score=0.72,
            entry_level_access_score=0.64,
            coverage_tier="tier_2",
            freshness_state="fresh",
            confidence_score=0.8,
            warnings=({"warning_code": "partial_coverage"},),
            provenance_summary={"safe_summary": "reviewed source bundle"},
        )
    )
    company_result = service.record_company_region_snapshot(
        CompanyRegionSnapshotCreate(
            company_region_snapshot_id="company_region_snap_1",
            company_id="comp_a",
            region_id="greater_boston",
            snapshot_date=JAN_1,
            company_presence_score=0.51,
            hiring_activity_score=0.42,
            active_posting_count=4,
            presence_status="present",
        )
    )
    sector_result = service.record_sector_region_snapshot(
        SectorRegionSnapshotCreate(
            sector_region_snapshot_id="sector_region_snap_1",
            sector_id="ai",
            region_id="greater_boston",
            snapshot_date=JAN_1,
            overall_score=0.58,
            sector_company_count=11,
        )
    )

    assert region_result.snapshot.market_snapshot_id == "market_snap_1"
    assert company_result.snapshot.company_region_snapshot_id == "company_region_snap_1"
    assert sector_result.snapshot.sector_region_snapshot_id == "sector_region_snap_1"
    assert region_result.observations == ()
    assert company_result.observations == ()
    assert sector_result.observations == ()
    assert session.get(MarketSnapshot, "market_snap_1").coverage_tier == "tier_2"
    assert session.get(CompanyRegionSnapshot, "company_region_snap_1").company_id == "comp_a"
    assert session.get(SectorRegionSnapshot, "sector_region_snap_1").sector_id == "ai"


def test_market_snapshots_write_score_history_without_mutating_canonical_scores(
    session: Session,
) -> None:
    _seed_region(session)
    _seed_market_score(session)
    canonical_before = session.get(RegionMarketScore, "score_greater_boston")
    assert canonical_before is not None
    before_values = (
        canonical_before.objective_opportunity_score,
        canonical_before.early_career_accessibility_score,
        canonical_before.score_ruleset_version,
    )

    _service(session).record_market_snapshot(
        MarketSnapshotCreate(
            market_snapshot_id="market_snap_score_history",
            region_id="greater_boston",
            snapshot_date=JAN_1,
            overall_score=0.88,
            entry_level_access_score=0.77,
            score_ruleset_version="historical_copy_v1",
            ranking_position=4,
        )
    )

    score_history = session.execute(select(MarketScoreHistory)).scalars().all()
    assert {row.score_name for row in score_history} == {
        "overall_score",
        "entry_level_access_score",
    }
    assert {row.market_snapshot_id for row in score_history} == {
        "market_snap_score_history"
    }
    canonical_after = session.get(RegionMarketScore, "score_greater_boston")
    assert canonical_after is not None
    assert (
        canonical_after.objective_opportunity_score,
        canonical_after.early_career_accessibility_score,
        canonical_after.score_ruleset_version,
    ) == before_values


def test_snapshots_are_append_only_and_prior_rows_are_not_mutated(
    session: Session,
) -> None:
    _seed_region(session)
    service = _service(session)
    service.record_market_snapshot(
        MarketSnapshotCreate(
            market_snapshot_id="market_snap_old",
            region_id="greater_boston",
            snapshot_date=JAN_1,
            overall_score=0.50,
        )
    )
    service.record_market_snapshot(
        MarketSnapshotCreate(
            market_snapshot_id="market_snap_new",
            region_id="greater_boston",
            snapshot_date=FEB_1,
            overall_score=0.61,
        )
    )

    snapshots = session.execute(
        select(MarketSnapshot).order_by(MarketSnapshot.snapshot_date)
    ).scalars().all()
    assert [row.market_snapshot_id for row in snapshots] == [
        "market_snap_old",
        "market_snap_new",
    ]
    assert snapshots[0].overall_score == 0.50
    assert snapshots[1].overall_score == 0.61

    session.commit()
    snapshots[0].overall_score = 0.90
    with pytest.raises(ValueError, match="append-only"):
        session.flush()
    session.rollback()
    assert session.get(MarketSnapshot, "market_snap_old").overall_score == 0.50


def test_market_delta_detection_records_score_increases_decreases_and_entry_access(
    session: Session,
) -> None:
    _seed_region(session)
    service = _service(session)
    service.record_market_snapshot(
        MarketSnapshotCreate(
            market_snapshot_id="market_snap_jan",
            region_id="greater_boston",
            snapshot_date=JAN_1,
            overall_score=0.70,
            entry_level_access_score=0.50,
            confidence_score=0.9,
        )
    )
    service.record_market_snapshot(
        MarketSnapshotCreate(
            market_snapshot_id="market_snap_feb",
            region_id="greater_boston",
            snapshot_date=FEB_1,
            overall_score=0.62,
            entry_level_access_score=0.61,
            confidence_score=0.8,
        )
    )
    service.record_market_snapshot(
        MarketSnapshotCreate(
            market_snapshot_id="market_snap_mar",
            region_id="greater_boston",
            snapshot_date=MAR_1,
            overall_score=0.74,
            entry_level_access_score=0.52,
            confidence_score=0.7,
        )
    )

    observations = session.execute(
        select(HistoricalObservation).order_by(HistoricalObservation.created_at)
    ).scalars().all()
    observation_types = {row.observation_type for row in observations}
    assert "regional_score_decreased" in observation_types
    assert "regional_score_increased" in observation_types
    assert "entry_level_access_improved" in observation_types
    assert "entry_level_access_declined" in observation_types
    assert {
        (row.previous_snapshot_id, row.current_snapshot_id)
        for row in observations
        if row.observation_type == "regional_score_increased"
    } == {("market_snap_feb", "market_snap_mar")}
    assert all(row.target_type == "region" for row in observations)


def test_company_presence_and_hiring_delta_detection_records_both_directions(
    session: Session,
) -> None:
    _seed_region(session)
    _seed_company(session)
    service = _service(session)
    service.record_company_region_snapshot(
        CompanyRegionSnapshotCreate(
            company_region_snapshot_id="company_snap_jan",
            company_id="comp_a",
            region_id="greater_boston",
            snapshot_date=JAN_1,
            company_presence_score=0.40,
            hiring_activity_score=0.20,
        )
    )
    service.record_company_region_snapshot(
        CompanyRegionSnapshotCreate(
            company_region_snapshot_id="company_snap_feb",
            company_id="comp_a",
            region_id="greater_boston",
            snapshot_date=FEB_1,
            company_presence_score=0.55,
            hiring_activity_score=0.35,
        )
    )
    service.record_company_region_snapshot(
        CompanyRegionSnapshotCreate(
            company_region_snapshot_id="company_snap_mar",
            company_id="comp_a",
            region_id="greater_boston",
            snapshot_date=MAR_1,
            company_presence_score=0.45,
            hiring_activity_score=0.20,
        )
    )

    observation_types = {
        row.observation_type
        for row in session.execute(select(HistoricalObservation)).scalars()
    }
    assert "company_presence_increased" in observation_types
    assert "company_presence_decreased" in observation_types
    assert "hiring_activity_increased" in observation_types
    assert "hiring_activity_decreased" in observation_types


def test_sector_delta_detection_records_growth_and_decline(session: Session) -> None:
    _seed_region(session)
    service = _service(session)
    service.record_sector_region_snapshot(
        SectorRegionSnapshotCreate(
            sector_region_snapshot_id="sector_snap_jan",
            sector_id="ai",
            region_id="greater_boston",
            snapshot_date=JAN_1,
            overall_score=0.40,
        )
    )
    service.record_sector_region_snapshot(
        SectorRegionSnapshotCreate(
            sector_region_snapshot_id="sector_snap_feb",
            sector_id="ai",
            region_id="greater_boston",
            snapshot_date=FEB_1,
            overall_score=0.55,
        )
    )
    service.record_sector_region_snapshot(
        SectorRegionSnapshotCreate(
            sector_region_snapshot_id="sector_snap_mar",
            sector_id="ai",
            region_id="greater_boston",
            snapshot_date=MAR_1,
            overall_score=0.45,
        )
    )

    observation_types = {
        row.observation_type
        for row in session.execute(select(HistoricalObservation)).scalars()
    }
    assert "sector_growth_detected" in observation_types
    assert "sector_decline_detected" in observation_types


def test_tiny_noisy_changes_do_not_create_observations(session: Session) -> None:
    _seed_region(session)
    _seed_company(session)
    service = _service(session)
    service.record_market_snapshot(
        MarketSnapshotCreate(
            market_snapshot_id="market_snap_noise_1",
            region_id="greater_boston",
            snapshot_date=JAN_1,
            overall_score=0.500,
            entry_level_access_score=0.600,
        )
    )
    result = service.record_market_snapshot(
        MarketSnapshotCreate(
            market_snapshot_id="market_snap_noise_2",
            region_id="greater_boston",
            snapshot_date=FEB_1,
            overall_score=0.520,
            entry_level_access_score=0.630,
        )
    )
    company_result = service.record_company_region_snapshot(
        CompanyRegionSnapshotCreate(
            company_region_snapshot_id="company_snap_noise_1",
            company_id="comp_a",
            region_id="greater_boston",
            snapshot_date=JAN_1,
            active_posting_count=10,
        )
    )
    company_result_2 = service.record_company_region_snapshot(
        CompanyRegionSnapshotCreate(
            company_region_snapshot_id="company_snap_noise_2",
            company_id="comp_a",
            region_id="greater_boston",
            snapshot_date=FEB_1,
            active_posting_count=11,
        )
    )

    assert result.observations == ()
    assert company_result.observations == ()
    assert company_result_2.observations == ()
    assert session.execute(select(HistoricalObservation)).scalars().all() == []


def test_snapshot_and_delta_detection_do_not_change_canonical_current_scores(
    session: Session,
) -> None:
    _seed_region(session)
    _seed_market_score(session)
    service = _service(session)

    service.record_market_snapshot(
        MarketSnapshotCreate(
            market_snapshot_id="market_snap_current_1",
            region_id="greater_boston",
            snapshot_date=JAN_1,
            overall_score=0.40,
        )
    )
    service.record_market_snapshot(
        MarketSnapshotCreate(
            market_snapshot_id="market_snap_current_2",
            region_id="greater_boston",
            snapshot_date=FEB_1,
            overall_score=0.80,
        )
    )

    canonical = session.get(RegionMarketScore, "score_greater_boston")
    assert canonical is not None
    assert canonical.objective_opportunity_score == 0.71
    assert canonical.early_career_accessibility_score == 0.63
    assert canonical.score_ruleset_version == "marketscore_v1"


def test_history_apis_return_safe_region_and_company_summaries(
    api_client,
    session: Session,
) -> None:
    _seed_region(session)
    _seed_company(session)
    service = _service(session)
    service.record_market_snapshot(
        MarketSnapshotCreate(
            market_snapshot_id="api_market_snap_1",
            region_id="greater_boston",
            snapshot_date=JAN_1,
            overall_score=0.50,
            coverage_tier="tier_2",
            freshness_state="fresh",
            confidence_score=0.8,
            provenance_summary={"source_refs": ["internal_source_a"]},
            created_at=datetime(2026, 1, 1, 12, tzinfo=UTC),
        )
    )
    service.record_market_snapshot(
        MarketSnapshotCreate(
            market_snapshot_id="api_market_snap_2",
            region_id="greater_boston",
            snapshot_date=FEB_1,
            overall_score=0.62,
            coverage_tier="tier_2",
            freshness_state="fresh",
            confidence_score=0.7,
            provenance_summary={"source_refs": ["internal_source_b"]},
            created_at=datetime(2026, 2, 1, 12, tzinfo=UTC),
        )
    )
    service.record_company_region_snapshot(
        CompanyRegionSnapshotCreate(
            company_region_snapshot_id="api_company_snap_1",
            company_id="comp_a",
            region_id="greater_boston",
            snapshot_date=JAN_1,
            company_presence_score=0.40,
            hiring_activity_score=0.20,
            provenance_summary={"source_refs": ["internal_company_source_a"]},
        )
    )
    service.record_company_region_snapshot(
        CompanyRegionSnapshotCreate(
            company_region_snapshot_id="api_company_snap_2",
            company_id="comp_a",
            region_id="greater_boston",
            snapshot_date=FEB_1,
            company_presence_score=0.52,
            hiring_activity_score=0.32,
            provenance_summary={"source_refs": ["internal_company_source_b"]},
        )
    )

    region_response = api_client.get("/platform/history/regions/greater_boston")
    company_response = api_client.get("/platform/history/companies/comp_a")

    assert region_response.status_code == 200
    region_body = region_response.json()
    assert region_body["status"] == "success"
    assert region_body["data"]["region_id"] == "greater_boston"
    assert len(region_body["data"]["market_snapshots"]) == 2
    assert region_body["data"]["coverage_context"] == {
        "coverage_tier": "tier_2",
        "freshness_state": "fresh",
        "confidence_score": 0.7,
    }
    assert any(
        row["observation_type"] == "regional_score_increased"
        for row in region_body["data"]["observations"]
    )

    assert company_response.status_code == 200
    company_body = company_response.json()
    assert company_body["data"]["company_id"] == "comp_a"
    assert len(company_body["data"]["region_snapshots"]) == 2
    assert {
        row["observation_type"] for row in company_body["data"]["observations"]
    } >= {"company_presence_increased", "hiring_activity_increased"}

    serialized = json.dumps({"region": region_body, "company": company_body})
    for internal_field in (
        "provenance_summary",
        "source_refs",
        "source_version_bundle",
        "admin_metadata",
    ):
        assert internal_field not in serialized
