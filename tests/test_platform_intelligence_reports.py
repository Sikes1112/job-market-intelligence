from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
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
    REQUIRED_INDEX_DEFINITIONS,
    MarketIndexService,
)
from backend.platform_intelligence.models import (
    BenchmarkReportEvidence,
    BenchmarkReportRanking,
    BenchmarkReportSection,
    MarketIndexScore,
    PredictiveSignal,
)
from backend.platform_intelligence.predictive_signals import PredictiveSignalService
from backend.platform_intelligence.reports import (
    REPORT_DEFINITIONS,
    BenchmarkReportLifecycleError,
    BenchmarkReportService,
)
from backend.platform_intelligence.schemas import (
    BenchmarkReportCreate,
    BenchmarkReportEvidenceCreate,
    BenchmarkReportKey,
    BenchmarkReportRankingCreate,
    BenchmarkReportSectionCreate,
    BenchmarkReportStatus,
    MarketSnapshotCreate,
    SectorRegionSnapshotCreate,
)
from backend.platform_intelligence.snapshots import HistoricalSnapshotService
from backend.scoring.models import RegionMarketScore

NOW = datetime(2026, 6, 17, 12, tzinfo=UTC)


def _repo(session: Session) -> HistoryRepository:
    return HistoryRepository(session)


def _snapshots(session: Session) -> HistoricalSnapshotService:
    return HistoricalSnapshotService(_repo(session))


def _indices(session: Session) -> MarketIndexService:
    return MarketIndexService(_repo(session))


def _signals(session: Session) -> PredictiveSignalService:
    return PredictiveSignalService(_repo(session))


def _reports(session: Session) -> BenchmarkReportService:
    return BenchmarkReportService(_repo(session))


def _seed_region(session: Session, region_id: str) -> None:
    session.add(
        Region(
            region_id=region_id,
            region_name=region_id,
            display_name=region_id.replace("_", " ").title(),
            region_type="greater_region",
        )
    )
    session.flush()


def _seed_company(session: Session, company_id: str) -> None:
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


def _seed_canonical_authority(session: Session, region_id: str) -> None:
    session.add(
        RegionMarketScore(
            region_score_id=f"score_{region_id}",
            region_id=region_id,
            objective_opportunity_score=0.61,
            early_career_accessibility_score=0.57,
            score_ruleset_version="canonical_v1",
        )
    )
    session.add(
        OutputMetadata(
            output_id=f"output_{region_id}",
            output_type="region_output",
            subject_id=region_id,
            artifact_hash="stable-output",
        )
    )
    session.flush()


def _seed_history(session: Session, region_id: str, *, base: float) -> None:
    service = _snapshots(session)
    for idx in range(3):
        service.record_market_snapshot(
            MarketSnapshotCreate(
                market_snapshot_id=f"market_{region_id}_{idx}",
                region_id=region_id,
                snapshot_date=date(2026, idx + 1, 1),
                overall_score=base + (idx * 0.07),
                entry_level_access_score=base + 0.05 + (idx * 0.06),
                internship_density_score=base + 0.03 + (idx * 0.06),
                ai_opportunity_score=base + 0.08 + (idx * 0.07),
                product_opportunity_score=base + 0.04 + (idx * 0.06),
                company_presence_score=base + 0.02 + (idx * 0.06),
                hidden_opportunity_score=base + (idx * 0.07),
                coverage_tier="tier_2" if region_id == "greater_boston" else "tier_4",
                freshness_state="fresh",
                confidence_score=0.80 if region_id == "greater_boston" else 0.55,
                warnings=(
                    ()
                    if region_id == "greater_boston"
                    else ("source_coverage_limited",)
                ),
                created_at=datetime(2026, idx + 1, 1, 12, tzinfo=UTC),
            )
        )
    service.record_sector_region_snapshot(
        SectorRegionSnapshotCreate(
            sector_region_snapshot_id=f"sector_ai_{region_id}_1",
            sector_id="ai",
            region_id=region_id,
            snapshot_date=date(2026, 1, 3),
            overall_score=base + 0.10,
            created_at=datetime(2026, 1, 3, 12, tzinfo=UTC),
        )
    )
    service.record_sector_region_snapshot(
        SectorRegionSnapshotCreate(
            sector_region_snapshot_id=f"sector_ai_{region_id}_2",
            sector_id="ai",
            region_id=region_id,
            snapshot_date=date(2026, 2, 3),
            overall_score=base + 0.25,
            created_at=datetime(2026, 2, 3, 12, tzinfo=UTC),
        )
    )


def _prepare_intelligence(session: Session) -> tuple[str, str]:
    region_ids = ("greater_boston", "greater_atlanta")
    for region_id in region_ids:
        _seed_region(session, region_id)
        _seed_canonical_authority(session, region_id)
    _seed_company(session, "comp_a")
    _seed_history(session, "greater_boston", base=0.45)
    _seed_history(session, "greater_atlanta", base=0.35)

    index_service = _indices(session)
    index_service.ensure_required_indices(effective_date=date(2026, 6, 1), created_at=NOW)
    for definition in REQUIRED_INDEX_DEFINITIONS:
        index_service.calculate_scores(
            index_key=definition.key,
            region_ids=region_ids,
            calculated_at=NOW,
        )
    for region_id in region_ids:
        _signals(session).generate_region_signals(region_id, created_at=NOW)
    return region_ids


def test_report_records_sections_rankings_and_evidence_can_be_created(
    session: Session,
) -> None:
    _seed_region(session, "greater_boston")
    report = _reports(session).create_report(
        BenchmarkReportCreate(
            report_key=BenchmarkReportKey.TOP_EMERGING_TECH_MARKETS,
            title="Top Emerging Tech Markets",
            report_period="2026-Q2",
            report_type="emerging_tech_markets",
            status=BenchmarkReportStatus.DRAFT,
            summary="Draft benchmark summary.",
            methodology_summary="Uses safe historical and index summaries.",
            data_window_start=date(2026, 1, 1),
            data_window_end=date(2026, 3, 1),
            freshness_notes="Freshness disclosed.",
            confidence_notes="Confidence disclosed.",
            coverage_notes="Coverage disclosed.",
            limitations=("No unverified contribution data.",),
            created_at=NOW,
            sections=(
                BenchmarkReportSectionCreate(
                    section_key="methodology",
                    title="Methodology",
                    body="Methodology body.",
                    display_order=1,
                ),
            ),
            rankings=(
                BenchmarkReportRankingCreate(
                    region_id="greater_boston",
                    rank=1,
                    score=0.72,
                    explanation="Public-safe explanation.",
                    warnings=("partial_input",),
                    confidence_score=0.8,
                    freshness_state="fresh",
                ),
            ),
            evidence=(
                BenchmarkReportEvidenceCreate(
                    target_type="region",
                    target_id="greater_boston",
                    source_type="historical_observation",
                    source_id="obs_1",
                    evidence_summary={"observation_type": "regional_score_increased"},
                ),
            ),
        )
    )

    assert report.status == "draft"
    assert session.execute(select(BenchmarkReportSection)).scalars().all()
    assert session.execute(select(BenchmarkReportRanking)).scalars().all()
    assert session.execute(select(BenchmarkReportEvidence)).scalars().all()
    assert BenchmarkReportStatus.values() == {
        "draft",
        "review_ready",
        "published",
        "archived",
        "superseded",
    }
    assert {definition.report_key.value for definition in REPORT_DEFINITIONS} == {
        "best_cities_early_career_ai_roles",
        "top_emerging_tech_markets",
        "best_markets_product_careers",
        "best_regions_internship_access",
    }
    with pytest.raises(ValidationError):
        BenchmarkReportCreate(
            report_key="not_supported",
            title="Bad",
            report_period="2026-Q2",
            report_type="emerging_tech_markets",
            summary="Bad",
            methodology_summary="Bad",
            data_window_start=date(2026, 1, 1),
            data_window_end=date(2026, 3, 1),
        )
    with pytest.raises(BenchmarkReportLifecycleError):
        _reports(session).create_report(
            BenchmarkReportCreate(
                report_key=BenchmarkReportKey.TOP_EMERGING_TECH_MARKETS,
                title="Top Emerging Tech Markets",
                report_period="2026-Q2",
                report_type="emerging_tech_markets",
                status=BenchmarkReportStatus.PUBLISHED,
                summary="Should not publish directly.",
                methodology_summary="Should not publish directly.",
                data_window_start=date(2026, 1, 1),
                data_window_end=date(2026, 3, 1),
            )
        )


def test_each_required_report_type_generates_review_ready_report(
    session: Session,
) -> None:
    region_ids = _prepare_intelligence(session)
    service = _reports(session)

    generated = [
        service.generate_report(
            definition.report_key,
            report_period="2026-Q2",
            region_ids=region_ids,
            status=BenchmarkReportStatus.REVIEW_READY,
            created_at=NOW,
        )
        for definition in REPORT_DEFINITIONS
    ]

    assert {report.report_key for report in generated} == {
        definition.report_key.value for definition in REPORT_DEFINITIONS
    }
    for report in generated:
        detail = service.report_detail(report.benchmark_report_id)
        assert detail.status == BenchmarkReportStatus.REVIEW_READY
        assert detail.ranked_regions
        assert detail.methodology_summary
        assert detail.data_window_start == date(2026, 1, 1)
        assert detail.data_window_end == date(2026, 3, 1)
        assert detail.freshness_notes
        assert detail.confidence_notes
        assert detail.coverage_notes
        assert detail.limitations
        assert detail.evidence
        assert all(row.score is not None for row in detail.ranked_regions)
        assert any(row.warnings for row in detail.ranked_regions)


def test_reports_include_index_observation_and_signal_evidence(
    session: Session,
) -> None:
    region_ids = _prepare_intelligence(session)
    report = _reports(session).generate_report(
        BenchmarkReportKey.TOP_EMERGING_TECH_MARKETS,
        report_period="2026-Q2",
        region_ids=region_ids,
        created_at=NOW,
    )

    evidence = _repo(session).list_report_evidence(report.benchmark_report_id)
    source_types = {row.source_type for row in evidence}

    assert "market_index_score" in source_types
    assert "historical_observation" in source_types
    assert "predictive_signal" in source_types
    assert "contribution" not in " ".join(source_types)


def test_report_lifecycle_public_visibility_and_supersede(session: Session) -> None:
    region_ids = _prepare_intelligence(session)
    service = _reports(session)
    draft = service.generate_report(
        BenchmarkReportKey.TOP_EMERGING_TECH_MARKETS,
        report_period="2026-Q2-draft",
        region_ids=region_ids,
        status=BenchmarkReportStatus.DRAFT,
        created_at=NOW,
    )
    review_ready = service.generate_report(
        BenchmarkReportKey.TOP_EMERGING_TECH_MARKETS,
        report_period="2026-Q2",
        region_ids=region_ids,
        status=BenchmarkReportStatus.REVIEW_READY,
        created_at=NOW,
    )

    assert service.list_public_reports().reports == ()
    assert service.public_report_detail("top_emerging_tech_markets") is None
    with pytest.raises(BenchmarkReportLifecycleError):
        service.publish_report(draft.benchmark_report_id, published_at=NOW)

    published = service.publish_report(review_ready.benchmark_report_id, published_at=NOW)
    assert published.status == "published"
    assert service.public_report_detail("top_emerging_tech_markets") is not None

    replacement = service.generate_report(
        BenchmarkReportKey.TOP_EMERGING_TECH_MARKETS,
        report_period="2026-Q3",
        region_ids=region_ids,
        status=BenchmarkReportStatus.REVIEW_READY,
        created_at=NOW,
    )
    service.publish_report(replacement.benchmark_report_id, published_at=NOW)
    assert session.get(type(published), published.benchmark_report_id).status == "superseded"
    current = service.public_report_detail("top_emerging_tech_markets")
    assert current.report_period == "2026-Q3"

    service.archive_report(replacement.benchmark_report_id, archived_at=NOW)
    assert service.public_report_detail("top_emerging_tech_markets") is None


def test_report_generation_does_not_mutate_authoritative_records(
    session: Session,
) -> None:
    region_ids = _prepare_intelligence(session)
    before_scores = {
        row.market_index_score_id: row.score
        for row in session.execute(select(MarketIndexScore)).scalars()
    }
    before_signals = {
        row.predictive_signal_id: row.status
        for row in session.execute(select(PredictiveSignal)).scalars()
    }

    _reports(session).generate_report(
        BenchmarkReportKey.BEST_REGIONS_INTERNSHIP_ACCESS,
        report_period="2026-Q2",
        region_ids=region_ids,
        created_at=NOW,
    )

    for region_id in region_ids:
        canonical = session.get(RegionMarketScore, f"score_{region_id}")
        output = session.get(OutputMetadata, f"output_{region_id}")
        assert canonical.objective_opportunity_score == 0.61
        assert canonical.early_career_accessibility_score == 0.57
        assert canonical.score_ruleset_version == "canonical_v1"
        assert output.artifact_hash == "stable-output"
    assert {
        row.market_index_score_id: row.score
        for row in session.execute(select(MarketIndexScore)).scalars()
    } == before_scores
    assert {
        row.predictive_signal_id: row.status
        for row in session.execute(select(PredictiveSignal)).scalars()
    } == before_signals


def test_public_report_apis_return_only_safe_published_payloads(
    api_client,
    session: Session,
) -> None:
    region_ids = _prepare_intelligence(session)
    service = _reports(session)
    service.generate_report(
        BenchmarkReportKey.BEST_REGIONS_INTERNSHIP_ACCESS,
        report_period="draft",
        region_ids=region_ids,
        status=BenchmarkReportStatus.DRAFT,
        created_at=NOW,
    )
    report = service.generate_report(
        BenchmarkReportKey.BEST_REGIONS_INTERNSHIP_ACCESS,
        report_period="2026-Q2",
        region_ids=region_ids,
        status=BenchmarkReportStatus.REVIEW_READY,
        created_at=NOW,
    )
    assert api_client.get("/platform/reports").json()["data"]["reports"] == []
    assert api_client.get("/platform/reports/best_regions_internship_access").status_code == 404

    service.publish_report(report.benchmark_report_id, published_at=NOW)
    list_response = api_client.get("/platform/reports")
    detail_response = api_client.get("/platform/reports/best_regions_internship_access")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert list_response.json()["data"]["reports"][0]["status"] == "published"
    detail = detail_response.json()["data"]
    assert detail["ranked_regions"]
    assert detail["methodology_summary"]
    serialized = json.dumps({"list": list_response.json(), "detail": detail_response.json()})
    for internal_field in (
        "internal_weight_config",
        "input_weight",
        "source_id",
        "admin_metadata",
        "review_notes",
        "market_index_inputs",
        "signal_inputs",
    ):
        assert internal_field not in serialized


def test_public_demo_allows_only_safe_report_gets(session: Session) -> None:
    app = create_app(
        engine=session.bind,
        settings=Settings(
            app_env="public_demo",
            database_url="sqlite:///public-demo-reports.db",
            cors_allowed_origins="https://demo.example",
            _env_file=None,
        ),
    )

    def _override_get_session():
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    client = TestClient(app)

    assert client.get("/platform/reports").status_code == 200
    assert client.get("/platform/reports/top_emerging_tech_markets").status_code == 404
    response = client.post(
        "/platform/reports",
        json={"report_key": "top_emerging_tech_markets"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["type"] == "public_demo_read_only"
