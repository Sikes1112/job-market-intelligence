from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.app import create_app
from backend.api.dependencies import get_session
from backend.companies.models import Company
from backend.config.settings import Settings
from backend.geography.models import Region
from backend.outputs.models import OutputMetadata
from backend.platform_intelligence.history_repository import HistoryRepository
from backend.platform_intelligence.indices import (
    DEFAULT_INDEX_VERSION,
    REQUIRED_INDEX_DEFINITIONS,
    MarketIndexService,
)
from backend.platform_intelligence.models import (
    MarketIndexInput,
    MarketIndexScore,
    MarketIndexVersion,
    SignalInput,
)
from backend.platform_intelligence.predictive_signals import PredictiveSignalService
from backend.platform_intelligence.schemas import (
    CompanyRegionSnapshotCreate,
    MarketIndexVersionCreate,
    MarketSnapshotCreate,
    PredictiveSignalCreate,
    PredictiveSignalStatus,
    PredictiveSignalType,
    SectorRegionSnapshotCreate,
)
from backend.platform_intelligence.snapshots import HistoricalSnapshotService
from backend.scoring.models import RegionMarketScore

NOW = datetime(2026, 6, 17, 12, tzinfo=UTC)


def _history_repo(session: Session) -> HistoryRepository:
    return HistoryRepository(session)


def _snapshot_service(session: Session) -> HistoricalSnapshotService:
    return HistoricalSnapshotService(_history_repo(session))


def _signal_service(session: Session) -> PredictiveSignalService:
    return PredictiveSignalService(_history_repo(session))


def _index_service(session: Session) -> MarketIndexService:
    return MarketIndexService(_history_repo(session))


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
            sector_primary="ai",
        )
    )
    session.flush()


def _seed_canonical_score(session: Session, region_id: str = "greater_boston") -> None:
    session.add(
        RegionMarketScore(
            region_score_id=f"score_{region_id}",
            region_id=region_id,
            objective_opportunity_score=0.71,
            early_career_accessibility_score=0.62,
            score_ruleset_version="canonical_v1",
        )
    )
    session.add(
        OutputMetadata(
            output_id=f"out_{region_id}",
            output_type="region_output",
            subject_id=region_id,
            artifact_hash="canonical-output-hash",
        )
    )
    session.flush()


def _seed_market_series(
    session: Session,
    *,
    region_id: str = "greater_boston",
    count: int,
    start_score: float = 0.40,
    step: float = 0.06,
) -> None:
    service = _snapshot_service(session)
    for idx in range(count):
        service.record_market_snapshot(
            MarketSnapshotCreate(
                market_snapshot_id=f"market_{region_id}_{idx}",
                region_id=region_id,
                snapshot_date=date(2026, idx + 1, 1),
                overall_score=start_score + (idx * step),
                entry_level_access_score=0.30 + (idx * step),
                internship_density_score=0.20 + (idx * step),
                ai_opportunity_score=0.25 + (idx * step),
                company_presence_score=0.35 + (idx * step),
                hidden_opportunity_score=0.15 + (idx * step),
                coverage_tier="tier_2",
                freshness_state="fresh",
                confidence_score=0.80,
                warnings=(),
                created_at=datetime(2026, idx + 1, 1, 12, tzinfo=UTC),
            )
        )


def _seed_company_and_sector_history(session: Session, region_id: str = "greater_boston") -> None:
    _seed_company(session)
    service = _snapshot_service(session)
    for idx in range(3):
        service.record_company_region_snapshot(
            CompanyRegionSnapshotCreate(
                company_region_snapshot_id=f"company_region_{idx}",
                company_id="comp_a",
                region_id=region_id,
                snapshot_date=date(2026, idx + 1, 2),
                company_presence_score=0.30 + (idx * 0.08),
                hiring_activity_score=0.20 + (idx * 0.08),
                entry_level_access_score=0.35 + (idx * 0.07),
                internship_density_score=0.25 + (idx * 0.06),
                internship_count=idx + 1,
                active_posting_count=idx + 4,
                created_at=datetime(2026, idx + 1, 2, 12, tzinfo=UTC),
            )
        )
    service.record_sector_region_snapshot(
        SectorRegionSnapshotCreate(
            sector_region_snapshot_id="sector_ai_1",
            sector_id="ai",
            region_id=region_id,
            snapshot_date=date(2026, 1, 3),
            overall_score=0.45,
            created_at=datetime(2026, 1, 3, 12, tzinfo=UTC),
        )
    )
    service.record_sector_region_snapshot(
        SectorRegionSnapshotCreate(
            sector_region_snapshot_id="sector_ai_2",
            sector_id="ai",
            region_id=region_id,
            snapshot_date=date(2026, 2, 3),
            overall_score=0.58,
            created_at=datetime(2026, 2, 3, 12, tzinfo=UTC),
        )
    )


def test_predictive_signals_require_minimum_snapshots_before_active(
    session: Session,
) -> None:
    _seed_region(session)
    _seed_market_series(session, count=2)

    signals = _signal_service(session).generate_region_signals(
        "greater_boston",
        created_at=NOW,
    )
    signal = next(row for row in signals if row.signal_type == "emerging_market")

    assert signal.status == "candidate"
    assert signal.minimum_snapshot_count_met is False
    assert signal.snapshot_count == 2
    assert "minimum_snapshot_count_not_met" in signal.warnings
    active = _signal_service(session).active_region_signals("greater_boston", now=NOW)
    assert active.signals == ()


def test_signal_strength_rules_and_evidence_windows(session: Session) -> None:
    for region_id, count, expected_strength in (
        ("weak_region", 3, "weak"),
        ("moderate_region", 6, "moderate"),
        ("strong_region", 12, "strong"),
    ):
        _seed_region(session, region_id)
        _seed_market_series(session, region_id=region_id, count=count)
        signals = _signal_service(session).generate_region_signals(
            region_id,
            created_at=NOW,
        )
        emerging = next(signal for signal in signals if signal.signal_type == "emerging_market")
        assert emerging.status == "active"
        assert emerging.signal_strength == expected_strength
        assert emerging.snapshot_count == count
        assert emerging.evidence_window_start == date(2026, 1, 1)
        assert emerging.evidence_window_end == date(2026, count, 1)
        if count == 3:
            assert "thin_historical_evidence_window" in emerging.warnings


def test_signal_inputs_reference_snapshots_and_observations(session: Session) -> None:
    _seed_region(session)
    _seed_market_series(session, count=3)

    _signal_service(session).generate_region_signals("greater_boston", created_at=NOW)

    inputs = session.execute(select(SignalInput)).scalars().all()
    assert inputs
    assert any(row.source_snapshot_id for row in inputs)
    assert any(row.historical_observation_id for row in inputs)


def test_expired_rejected_and_superseded_signals_are_not_active(
    session: Session,
) -> None:
    _seed_region(session)
    service = _signal_service(session)
    common = {
        "signal_type": PredictiveSignalType.EMERGING_MARKET,
        "target_type": "region",
        "target_id": "greater_boston",
        "region_id": "greater_boston",
        "signal_strength": "weak",
        "confidence_level": "low",
        "evidence_window_start": date(2026, 1, 1),
        "evidence_window_end": date(2026, 3, 1),
        "snapshot_count": 3,
        "minimum_snapshot_count_met": True,
        "summary": "Emerging signal watchlist item.",
        "created_at": NOW,
    }
    service.create_signal(
        PredictiveSignalCreate(
            **common,
            predictive_signal_id="signal_active",
            status=PredictiveSignalStatus.ACTIVE,
            expires_at=NOW + timedelta(days=30),
        )
    )
    for signal_id, status in (
        ("signal_expired_status", PredictiveSignalStatus.EXPIRED),
        ("signal_rejected", PredictiveSignalStatus.REJECTED),
        ("signal_superseded", PredictiveSignalStatus.SUPERSEDED),
    ):
        service.create_signal(
            PredictiveSignalCreate(
                **common,
                predictive_signal_id=signal_id,
                status=status,
                expires_at=NOW + timedelta(days=30),
            )
        )
    service.create_signal(
        PredictiveSignalCreate(
            **common,
            predictive_signal_id="signal_expired_time",
            status=PredictiveSignalStatus.ACTIVE,
            expires_at=NOW - timedelta(days=1),
        )
    )

    active = service.active_region_signals("greater_boston", now=NOW)

    assert [signal.signal_id for signal in active.signals] == ["signal_active"]


def test_predictive_signal_creation_does_not_mutate_canonical_authority(
    session: Session,
) -> None:
    _seed_region(session)
    _seed_canonical_score(session)
    _seed_market_series(session, count=3)
    before_score = session.get(RegionMarketScore, "score_greater_boston")
    before_output = session.get(OutputMetadata, "out_greater_boston")
    assert before_score is not None
    assert before_output is not None

    _signal_service(session).generate_region_signals("greater_boston", created_at=NOW)

    after_score = session.get(RegionMarketScore, "score_greater_boston")
    after_output = session.get(OutputMetadata, "out_greater_boston")
    assert after_score.objective_opportunity_score == 0.71
    assert after_score.early_career_accessibility_score == 0.62
    assert after_score.score_ruleset_version == "canonical_v1"
    assert after_output.artifact_hash == "canonical-output-hash"
    assert session.query(OutputMetadata).count() == 1


def test_required_indices_versions_scores_and_inputs(session: Session) -> None:
    _seed_region(session)
    _seed_market_series(session, count=3)
    _seed_company_and_sector_history(session)
    service = _index_service(session)

    indices = service.ensure_required_indices(effective_date=date(2026, 6, 1), created_at=NOW)
    scores = service.calculate_scores(
        index_key="early_career_tech_access",
        region_ids=("greater_boston",),
        calculated_at=NOW,
    )

    assert {index.key for index in indices} == {
        definition.key for definition in REQUIRED_INDEX_DEFINITIONS
    }
    versions = session.execute(select(MarketIndexVersion)).scalars().all()
    assert len(versions) == 5
    assert {version.version for version in versions} == {DEFAULT_INDEX_VERSION}
    assert len(scores) == 1
    [score] = scores
    assert score.index_version_id
    assert score.confidence_score == 0.80
    assert score.freshness_state == "fresh"
    assert session.execute(select(MarketIndexInput)).scalars().all()


def test_index_version_changes_create_new_versions_and_preserve_old_scores(
    session: Session,
) -> None:
    _seed_region(session)
    _seed_market_series(session, count=3)
    service = _index_service(session)
    service.ensure_required_indices(effective_date=date(2026, 6, 1), created_at=NOW)
    [old_score] = service.calculate_scores(
        index_key="early_career_tech_access",
        region_ids=("greater_boston",),
        calculated_at=NOW,
    )
    index = _history_repo(session).get_market_index_by_key("early_career_tech_access")
    assert index is not None
    new_version = service.create_index_version(
        MarketIndexVersionCreate(
            index_id=index.market_index_id,
            version="2026.07",
            formula_description="Updated public methodology summary.",
            input_schema={"entry_level_access_score": "optional 0-1 historical score"},
            internal_weight_config={"entry_level_access_score": 1.0},
            effective_date=date(2026, 7, 1),
            created_at=NOW + timedelta(days=1),
        )
    )

    [new_score] = service.calculate_scores(
        index_key="early_career_tech_access",
        region_ids=("greater_boston",),
        calculated_at=NOW + timedelta(days=1),
    )

    assert new_score.index_version_id == new_version.market_index_version_id
    assert old_score.index_version_id != new_score.index_version_id
    assert session.get(MarketIndexScore, old_score.market_index_score_id).score == (old_score.score)
    with pytest.raises(ValueError, match="append-only"):
        old_score.score = 0.0
        session.flush()
    session.rollback()


def test_index_scores_include_partial_data_warnings(session: Session) -> None:
    _seed_region(session)
    _snapshot_service(session).record_market_snapshot(
        MarketSnapshotCreate(
            market_snapshot_id="partial_market",
            region_id="greater_boston",
            snapshot_date=date(2026, 1, 1),
            entry_level_access_score=0.50,
            coverage_tier="tier_4",
            freshness_state="unknown",
            confidence_score=0.35,
            warnings=("source_coverage_limited",),
        )
    )
    service = _index_service(session)
    service.ensure_required_indices(effective_date=date(2026, 6, 1), created_at=NOW)
    [score] = service.calculate_scores(
        index_key="early_career_tech_access",
        region_ids=("greater_boston",),
        calculated_at=NOW,
    )

    warnings = score.evidence_summary["warnings"]
    assert "source_coverage_limited" in warnings
    assert "limited_coverage:tier_4" in warnings
    assert "missing_input:internship_density_score" in warnings


def test_index_score_generation_does_not_mutate_canonical_authority(
    session: Session,
) -> None:
    _seed_region(session)
    _seed_canonical_score(session)
    _seed_market_series(session, count=3)
    service = _index_service(session)
    service.ensure_required_indices(effective_date=date(2026, 6, 1), created_at=NOW)

    service.calculate_scores(
        index_key="early_career_tech_access",
        region_ids=("greater_boston",),
        calculated_at=NOW,
    )

    score = session.get(RegionMarketScore, "score_greater_boston")
    output = session.get(OutputMetadata, "out_greater_boston")
    assert score.objective_opportunity_score == 0.71
    assert score.early_career_accessibility_score == 0.62
    assert score.score_ruleset_version == "canonical_v1"
    assert output.artifact_hash == "canonical-output-hash"
    assert session.query(OutputMetadata).count() == 1


def test_platform_intelligence_apis_return_safe_summaries(api_client, session: Session) -> None:
    _seed_region(session)
    _seed_market_series(session, count=3)
    _seed_company_and_sector_history(session)
    _signal_service(session).generate_region_signals("greater_boston", created_at=NOW)
    index_service = _index_service(session)
    index_service.ensure_required_indices(effective_date=date(2026, 6, 1), created_at=NOW)
    index_service.calculate_scores(
        index_key="early_career_tech_access",
        region_ids=("greater_boston",),
        calculated_at=NOW,
    )

    signals = api_client.get("/platform/signals/regions/greater_boston")
    indices = api_client.get("/platform/indices")
    scores = api_client.get("/platform/indices/early_career_tech_access/scores")

    assert signals.status_code == 200
    assert indices.status_code == 200
    assert scores.status_code == 200
    assert signals.json()["data"]["signals"]
    assert indices.json()["data"]["indices"]
    assert scores.json()["data"]["scores"][0]["region_id"] == "greater_boston"

    serialized = json.dumps(
        {
            "signals": signals.json(),
            "indices": indices.json(),
            "scores": scores.json(),
        }
    )
    for internal_field in (
        "internal_weight_config",
        "input_weight",
        "market_index_inputs",
        "signal_inputs",
        "source_id",
        "provenance_summary",
        "admin_metadata",
    ):
        assert internal_field not in serialized


def test_public_demo_allows_only_safe_platform_intelligence_gets(
    session: Session,
) -> None:
    session.add(
        Region(
            region_id="greater_boston",
            region_name="greater_boston",
            display_name="Greater Boston",
            region_type="greater_region",
        )
    )
    session.flush()
    app = create_app(
        engine=session.bind,
        settings=Settings(
            app_env="public_demo",
            database_url="sqlite:///public-demo-layer-18b.db",
            cors_allowed_origins="https://demo.example",
            _env_file=None,
        ),
    )

    def _override_get_session():
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    client = TestClient(app)

    assert client.get("/platform/signals/regions/greater_boston").status_code == 200
    assert client.get("/platform/indices").status_code == 200
    assert client.get("/platform/indices/early_career_tech_access/scores").status_code == 200
    response = client.post(
        "/platform/signals/regions/greater_boston",
        json={"status": "active"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["type"] == "public_demo_read_only"
