from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.api.app import create_app
from backend.api.dependencies import get_session
from backend.companies.models import Company
from backend.config.settings import Settings
from backend.geography.models import Region
from backend.platform_intelligence.history_repository import HistoryRepository
from backend.platform_intelligence.predictive_exports import (
    export_predictive_observations,
)
from backend.platform_intelligence.schemas import (
    CompanyRegionSnapshotCreate,
    MarketSnapshotCreate,
    SectorRegionSnapshotCreate,
)
from backend.platform_intelligence.snapshots import HistoricalSnapshotService
from backend.predictive.contracts import (
    HistoricalMetricObservation,
    PredictiveEntityType,
    PredictiveForecastType,
    PredictiveMetric,
    PredictiveSignalKind,
)
from backend.predictive.reports import PredictiveReportBuilder

NOW = date(2026, 6, 20)
GENERATED_AT = datetime(2026, 6, 20, 12, tzinfo=UTC)

INTERNAL_ONLY_FIELDS = {
    "source_id",
    "source_ids",
    "raw_source_refs",
    "raw_scrape_records",
    "admin_metadata",
    "private_metadata",
    "internal_formula_weights",
    "formula_weights",
    "review_notes",
}


def _series(
    metric: PredictiveMetric,
    values: tuple[float, ...],
    *,
    entity_type: PredictiveEntityType = PredictiveEntityType.REGION,
    entity_id: str = "greater_boston",
    region_id: str | None = "greater_boston",
    company_id: str | None = None,
    sector_id: str | None = None,
    start: date = date(2026, 1, 1),
    source_categories: tuple[str, ...] = (
        "historical_snapshot",
        "historical_observation",
    ),
) -> tuple[HistoricalMetricObservation, ...]:
    return tuple(
        HistoricalMetricObservation(
            entity_type=entity_type,
            entity_id=entity_id,
            metric=metric,
            observed_at=start + timedelta(days=idx * 30),
            value=value,
            region_id=region_id,
            company_id=company_id,
            sector_id=sector_id,
            source_categories=source_categories,
            source_count=len(source_categories),
            data_basis="test_fixture",
            confidence_score=0.86,
            freshness_state="fresh",
            coverage_tier="tier_2",
        )
        for idx, value in enumerate(values)
    )


def _fixture_observations() -> tuple[HistoricalMetricObservation, ...]:
    return (
        *_series(PredictiveMetric.AI_OPPORTUNITY, (0.32, 0.42, 0.53, 0.64)),
        *_series(
            PredictiveMetric.ENTRY_LEVEL_ACCESS,
            (0.66, 0.58, 0.50, 0.43),
            entity_id="weak_entry_region",
            region_id="weak_entry_region",
        ),
        *_series(
            PredictiveMetric.COMPANY_EXPANSION,
            (0.25, 0.36, 0.48, 0.60),
            entity_type=PredictiveEntityType.COMPANY_REGION,
            entity_id="comp_a:greater_atlanta",
            region_id="greater_atlanta",
            company_id="comp_a",
        ),
        *_series(
            PredictiveMetric.SECTOR_GROWTH,
            (0.70, 0.62, 0.52, 0.44),
            entity_type=PredictiveEntityType.SECTOR_REGION,
            entity_id="cybersecurity:weak_region",
            region_id="weak_region",
            sector_id="cybersecurity",
        ),
        *_series(
            PredictiveMetric.REGIONAL_SCORE,
            (0.70, 0.78, 0.86, 0.93),
            entity_id="hot_region",
            region_id="hot_region",
        ),
        *_series(
            PredictiveMetric.HIDDEN_OPPORTUNITY,
            (0.30, 0.41, 0.53, 0.66),
            entity_id="hidden_region",
            region_id="hidden_region",
        ),
        *_series(
            PredictiveMetric.AI_OPPORTUNITY,
            (0.42, 0.54),
            entity_id="thin_ai_region",
            region_id="thin_ai_region",
        ),
    )


def test_predictive_report_is_generated_from_layer21a_outputs() -> None:
    report = PredictiveReportBuilder().build_report(
        _fixture_observations(),
        generated_at=GENERATED_AT,
        now=NOW,
    )

    forecasts = [forecast for section in report.sections for forecast in section.forecasts]
    forecast_types = {forecast.forecast_type for forecast in forecasts}

    assert report.report_type == "labor_market_forecast"
    assert PredictiveForecastType.AI_ROLE_MARKET_GROWTH_12M in forecast_types
    assert PredictiveForecastType.ENTRY_LEVEL_ACCESS_WEAKENING in forecast_types
    assert PredictiveForecastType.EARLY_CAREER_HIRING_EXPANSION in forecast_types
    assert PredictiveForecastType.SECTOR_CONDITION_CHANGE in forecast_types
    assert PredictiveForecastType.UNDERPRICED_OPPORTUNITY_MARKET in forecast_types
    assert any(
        signal.signal_kind is PredictiveSignalKind.EMERGING_MARKET
        for forecast in forecasts
        for signal in forecast.supporting_signals
    )
    assert any(
        signal.signal_kind is PredictiveSignalKind.EARLY_WARNING
        for forecast in forecasts
        for signal in forecast.supporting_signals
    )
    assert all(section.why_this_section_exists for section in report.sections)


def test_predictive_reports_preserve_forecast_metadata_and_safe_copy() -> None:
    report = PredictiveReportBuilder().build_report(
        _fixture_observations(),
        generated_at=GENERATED_AT,
        now=NOW,
    )

    forecasts = [forecast for section in report.sections for forecast in section.forecasts]
    assert forecasts
    for forecast in forecasts:
        assert forecast.confidence.level.value in {"high", "medium", "low", "unknown"}
        assert 0.0 <= forecast.confidence.score <= 1.0
        assert forecast.source_basis.source_count > 0
        assert forecast.source_basis.observed_metrics
        assert forecast.historical_depth.observation_count >= 2
        assert forecast.uncertainty.known_uncertainties
        assert forecast.uncertainty.bounded is True
        assert forecast.reasoning_trail
        assert forecast.supporting_signals
        assert forecast.safe_display_summary
        assert forecast.why_this_forecast_exists

    serialized = json.dumps(report.model_dump(mode="json"))
    assert "guaranteed" not in serialized.casefold()
    assert "guarantee" not in serialized.casefold()
    assert "certain outcome" in serialized.casefold()
    found = _find_forbidden_fields(report.model_dump(mode="json"))
    assert not found, found


def test_insufficient_historical_data_renders_low_confidence_forecast() -> None:
    report = PredictiveReportBuilder().build_report(
        _series(
            PredictiveMetric.AI_OPPORTUNITY,
            (0.40, 0.55),
            entity_id="thin_region",
            region_id="thin_region",
        ),
        generated_at=GENERATED_AT,
        now=NOW,
    )

    forecasts = [forecast for section in report.sections for forecast in section.forecasts]
    assert len(forecasts) == 1
    [forecast] = forecasts
    assert forecast.forecast_label == "Insufficient-data opportunity forecast"
    assert forecast.confidence.level.value in {"low", "unknown"}
    assert "insufficient" in forecast.safe_display_summary.casefold()


def test_predictive_export_adapter_maps_historical_snapshots(session: Session) -> None:
    _seed_region(session, "greater_boston")
    _seed_company(session, "comp_a")
    snapshot_service = HistoricalSnapshotService(HistoryRepository(session))
    for idx, value in enumerate((0.40, 0.50, 0.61, 0.72), start=1):
        snapshot_service.record_market_snapshot(
            MarketSnapshotCreate(
                market_snapshot_id=f"market_{idx}",
                region_id="greater_boston",
                snapshot_date=date(2026, idx, 1),
                overall_score=value,
                entry_level_access_score=0.70 - (idx * 0.06),
                ai_opportunity_score=value,
                hidden_opportunity_score=0.25 + (idx * 0.08),
                confidence_score=0.84,
                coverage_tier="tier_2",
                freshness_state="fresh",
            )
        )
        snapshot_service.record_company_region_snapshot(
            CompanyRegionSnapshotCreate(
                company_region_snapshot_id=f"company_{idx}",
                company_id="comp_a",
                region_id="greater_boston",
                snapshot_date=date(2026, idx, 2),
                company_presence_score=0.20 + (idx * 0.10),
                hiring_activity_score=0.25 + (idx * 0.08),
                confidence_score=0.80,
                coverage_tier="tier_2",
                freshness_state="fresh",
            )
        )
        snapshot_service.record_sector_region_snapshot(
            SectorRegionSnapshotCreate(
                sector_region_snapshot_id=f"sector_{idx}",
                sector_id="cybersecurity",
                region_id="greater_boston",
                snapshot_date=date(2026, idx, 3),
                overall_score=0.70 - (idx * 0.06),
                confidence_score=0.78,
                coverage_tier="tier_2",
                freshness_state="fresh",
            )
        )

    observations = export_predictive_observations(
        HistoryRepository(session),
        region_ids=("greater_boston",),
    )
    metrics = {observation.metric for observation in observations}

    assert PredictiveMetric.AI_OPPORTUNITY in metrics
    assert PredictiveMetric.ENTRY_LEVEL_ACCESS in metrics
    assert PredictiveMetric.COMPANY_EXPANSION in metrics
    assert PredictiveMetric.CYBERSECURITY_OPPORTUNITY in metrics
    assert all(observation.data_basis == "producer_owned_export" for observation in observations)


def test_predictive_export_filters_are_deterministic_for_repeated_inputs(
    session: Session,
) -> None:
    _seed_predictive_history(session)
    repository = HistoryRepository(session)

    single = export_predictive_observations(
        repository,
        region_ids=("greater_boston",),
        company_ids=("comp_a",),
    )
    repeated = export_predictive_observations(
        repository,
        region_ids=("greater_boston", "greater_boston"),
        company_ids=("comp_a", "comp_a"),
    )

    assert [row.model_dump(mode="json") for row in repeated] == [
        row.model_dump(mode="json") for row in single
    ]


def test_predictive_report_api_returns_public_safe_payload(api_client, session: Session) -> None:
    _seed_predictive_history(session)

    response = api_client.get(
        "/platform/predictive/reports?region_id=greater_boston&company_id=comp_a"
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["report_type"] == "labor_market_forecast"
    assert data["sections"]
    assert any(section["forecasts"] for section in data["sections"])
    forecast = next(
        forecast
        for section in data["sections"]
        for forecast in section["forecasts"]
    )
    for key in (
        "forecast_title",
        "forecast_type",
        "affected_entity",
        "time_horizon",
        "confidence",
        "source_basis",
        "historical_depth",
        "uncertainty",
        "reasoning_trail",
        "supporting_signals",
        "safe_display_summary",
    ):
        assert key in forecast
    found = _find_forbidden_fields(data)
    assert not found, found


def test_public_demo_allows_predictive_report_get(session: Session) -> None:
    app = create_app(
        engine=session.bind,
        settings=Settings(
            app_env="public_demo",
            database_url="sqlite:///public-demo-predictive.db",
            cors_allowed_origins="https://demo.example",
            _env_file=None,
        ),
    )

    def _override_get_session() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    client = TestClient(app)

    response = client.get("/platform/predictive/reports?region_id=greater_boston")

    assert response.status_code == 200


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
        )
    )
    session.flush()


def _seed_predictive_history(session: Session) -> None:
    _seed_region(session, "greater_boston")
    _seed_company(session, "comp_a")
    service = HistoricalSnapshotService(HistoryRepository(session))
    for idx, value in enumerate((0.35, 0.45, 0.55, 0.66), start=1):
        service.record_market_snapshot(
            MarketSnapshotCreate(
                market_snapshot_id=f"api_market_{idx}",
                region_id="greater_boston",
                snapshot_date=date(2026, idx, 1),
                overall_score=value,
                entry_level_access_score=0.74 - (idx * 0.06),
                ai_opportunity_score=value,
                hidden_opportunity_score=0.25 + (idx * 0.08),
                confidence_score=0.84,
                coverage_tier="tier_2",
                freshness_state="fresh",
            )
        )
        service.record_company_region_snapshot(
            CompanyRegionSnapshotCreate(
                company_region_snapshot_id=f"api_company_{idx}",
                company_id="comp_a",
                region_id="greater_boston",
                snapshot_date=date(2026, idx, 2),
                company_presence_score=0.20 + (idx * 0.10),
                hiring_activity_score=0.25 + (idx * 0.08),
                confidence_score=0.80,
                coverage_tier="tier_2",
                freshness_state="fresh",
            )
        )


def _find_forbidden_fields(value: object, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if key in INTERNAL_ONLY_FIELDS:
                found.append(child_path)
            found.extend(_find_forbidden_fields(child, child_path))
    elif isinstance(value, list | tuple):
        for index, child in enumerate(value):
            found.extend(_find_forbidden_fields(child, f"{path}[{index}]"))
    return found
