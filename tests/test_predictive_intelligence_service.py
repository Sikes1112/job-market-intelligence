from __future__ import annotations

import json
from datetime import date, timedelta

from backend.predictive.contracts import (
    EarlyWarningStatus,
    EarlyWarningType,
    EmergingMarketClassification,
    EmergingMarketType,
    HistoricalMetricObservation,
    PredictiveEntityType,
    PredictiveMetric,
    TrendDirection,
    TrendType,
)
from backend.predictive.service import PredictiveIntelligenceService
from backend.shared.confidence import Confidence

NOW = date(2026, 6, 20)


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
    step_days: int = 30,
    source_categories: tuple[str, ...] = (
        "historical_snapshot",
        "historical_observation",
    ),
    confidence_score: float = 0.86,
) -> tuple[HistoricalMetricObservation, ...]:
    return tuple(
        HistoricalMetricObservation(
            entity_type=entity_type,
            entity_id=entity_id,
            metric=metric,
            observed_at=start + timedelta(days=idx * step_days),
            value=value,
            region_id=region_id,
            company_id=company_id,
            sector_id=sector_id,
            source_categories=source_categories,
            source_count=len(source_categories),
            data_basis="test_fixture",
            confidence_score=confidence_score,
            freshness_state="fresh",
            coverage_tier="tier_2",
        )
        for idx, value in enumerate(values)
    )


def test_historical_trend_modeling_from_sufficient_evidence() -> None:
    observations = (
        *_series(
            PredictiveMetric.COMPANY_EXPANSION,
            (0.20, 0.31, 0.43, 0.55),
            entity_type=PredictiveEntityType.COMPANY_REGION,
            entity_id="comp_a:greater_boston",
            company_id="comp_a",
        ),
        *_series(
            PredictiveMetric.HIRING_ACTIVITY,
            (0.25, 0.35, 0.47, 0.58),
            entity_type=PredictiveEntityType.COMPANY_REGION,
            entity_id="comp_b:greater_boston",
            company_id="comp_b",
        ),
        *_series(
            PredictiveMetric.HIRING_ACTIVITY,
            (0.76, 0.68, 0.56, 0.48),
            entity_type=PredictiveEntityType.COMPANY_REGION,
            entity_id="comp_c:greater_boston",
            company_id="comp_c",
        ),
        *_series(
            PredictiveMetric.INTERNSHIP_DENSITY,
            (0.20, 0.34, 0.48, 0.35, 0.22, 0.31, 0.46, 0.33),
            entity_id="internship_region",
            region_id="internship_region",
        ),
        *_series(
            PredictiveMetric.REGIONAL_SCORE,
            (0.50, 0.57, 0.63, 0.69),
            entity_id="regional_growth",
            region_id="regional_growth",
        ),
        *_series(
            PredictiveMetric.SECTOR_GROWTH,
            (0.30, 0.39, 0.48, 0.60),
            entity_type=PredictiveEntityType.SECTOR_REGION,
            entity_id="ai:greater_boston",
            sector_id="ai",
        ),
    )

    trends = PredictiveIntelligenceService().model_historical_trends(
        observations,
        now=NOW,
    )

    by_type = {trend.trend_type: trend for trend in trends}
    assert by_type[TrendType.COMPANY_EXPANSION].direction is TrendDirection.RISING
    assert by_type[TrendType.HIRING_GROWTH].direction is TrendDirection.RISING
    assert by_type[TrendType.HIRING_CONTRACTION].direction is TrendDirection.WEAKENING
    assert by_type[TrendType.INTERNSHIP_SEASONALITY].direction is TrendDirection.SEASONAL
    assert by_type[TrendType.REGIONAL_SCORE_MOVEMENT].magnitude > 0
    assert by_type[TrendType.SECTOR_SPECIFIC_GROWTH].direction is TrendDirection.RISING
    for trend in trends:
        _assert_predictive_payload_common(trend)
        assert trend.supporting_evidence
        assert trend.time_window.start < trend.time_window.end


def test_no_trend_or_low_confidence_trend_from_insufficient_evidence() -> None:
    service = PredictiveIntelligenceService()

    assert service.model_historical_trends(
        _series(PredictiveMetric.REGIONAL_SCORE, (0.40,), entity_id="one_point"),
        now=NOW,
    ) == ()

    [trend] = service.model_historical_trends(
        _series(PredictiveMetric.REGIONAL_SCORE, (0.40, 0.48), entity_id="two_points"),
        now=NOW,
    )
    assert trend.direction is TrendDirection.INSUFFICIENT_DATA
    assert trend.confidence.level in {Confidence.LOW, Confidence.UNKNOWN}
    assert "thin_historical_evidence" in {
        factor.code for factor in trend.confidence.factors
    }


def test_emerging_market_detection_for_rising_signals() -> None:
    observations = (
        *_series(
            PredictiveMetric.AI_OPPORTUNITY,
            (0.30, 0.39, 0.50, 0.62),
            entity_id="ai_city",
            region_id="ai_city",
        ),
        *_series(
            PredictiveMetric.CLOUD_OPPORTUNITY,
            (0.28, 0.38, 0.47, 0.59),
            entity_id="cloud_city",
            region_id="cloud_city",
        ),
        *_series(
            PredictiveMetric.CYBERSECURITY_OPPORTUNITY,
            (0.35, 0.43, 0.55, 0.66),
            entity_id="cyber_city",
            region_id="cyber_city",
        ),
        *_series(
            PredictiveMetric.PRODUCT_OPPORTUNITY,
            (0.32, 0.41, 0.52, 0.61),
            entity_id="product_city",
            region_id="product_city",
        ),
    )

    signals = PredictiveIntelligenceService().detect_emerging_markets(
        observations,
        now=NOW,
    )

    by_type = {signal.emerging_type: signal for signal in signals}
    assert by_type[EmergingMarketType.RISING_AI_MARKET].classification is (
        EmergingMarketClassification.RISING
    )
    assert by_type[EmergingMarketType.NEW_CLOUD_HUB].emerging_label
    assert by_type[EmergingMarketType.CYBERSECURITY_GROWTH_REGION].emerging_label
    assert by_type[EmergingMarketType.PRODUCT_ROLE_EXPANSION_REGION].emerging_label
    for signal in signals:
        _assert_predictive_payload_common(signal)
        assert signal.signal_basis


def test_emerging_market_detection_for_stable_weakening_noisy_and_insufficient() -> None:
    observations = (
        *_series(
            PredictiveMetric.AI_OPPORTUNITY,
            (0.45, 0.46, 0.45, 0.47),
            entity_id="stable_city",
            region_id="stable_city",
        ),
        *_series(
            PredictiveMetric.AI_OPPORTUNITY,
            (0.62, 0.56, 0.49, 0.42),
            entity_id="weakening_city",
            region_id="weakening_city",
        ),
        *_series(
            PredictiveMetric.AI_OPPORTUNITY,
            (0.45, 0.60, 0.44, 0.46),
            entity_id="noisy_city",
            region_id="noisy_city",
        ),
        *_series(
            PredictiveMetric.AI_OPPORTUNITY,
            (0.40, 0.52),
            entity_id="thin_city",
            region_id="thin_city",
        ),
    )

    signals = PredictiveIntelligenceService().detect_emerging_markets(
        observations,
        now=NOW,
    )

    by_region = {signal.region_id: signal for signal in signals}
    assert by_region["stable_city"].classification is EmergingMarketClassification.STABLE
    assert by_region["stable_city"].emerging_label is None
    assert by_region["weakening_city"].classification is (
        EmergingMarketClassification.WEAKENING
    )
    assert by_region["weakening_city"].emerging_label is None
    assert by_region["noisy_city"].classification is EmergingMarketClassification.NOISY
    assert by_region["noisy_city"].emerging_label is None
    assert by_region["thin_city"].classification is (
        EmergingMarketClassification.INSUFFICIENT_DATA
    )
    assert by_region["thin_city"].confidence.level in {Confidence.LOW, Confidence.UNKNOWN}


def test_underpriced_opportunity_detection_uses_bounded_confidence() -> None:
    [signal] = PredictiveIntelligenceService().detect_emerging_markets(
        _series(
            PredictiveMetric.HIDDEN_OPPORTUNITY,
            (0.30, 0.41, 0.54, 0.66),
            entity_id="hidden_city",
            region_id="hidden_city",
        ),
        now=NOW,
    )

    assert signal.emerging_type is EmergingMarketType.UNDERPRICED_OPPORTUNITY_MARKET
    assert signal.classification is EmergingMarketClassification.RISING
    assert signal.emerging_label == "Underpriced opportunity signal"
    assert signal.confidence.level is Confidence.MEDIUM
    assert signal.confidence.score <= 0.72
    assert "not a certain market outcome" in signal.opportunity_framing
    assert "bounded_interpretation" in {factor.code for factor in signal.confidence.factors}


def test_early_warning_signals_for_weakening_and_overheated_markets() -> None:
    observations = (
        *_series(
            PredictiveMetric.HIRING_ACTIVITY,
            (0.80, 0.72, 0.61, 0.52),
            entity_type=PredictiveEntityType.COMPANY_REGION,
            entity_id="comp_slowing:greater_boston",
            company_id="comp_slowing",
        ),
        *_series(
            PredictiveMetric.REGIONAL_SCORE,
            (0.70, 0.64, 0.57, 0.51),
            entity_id="weak_region",
            region_id="weak_region",
        ),
        *_series(
            PredictiveMetric.INTERNSHIP_DENSITY,
            (0.60, 0.54, 0.45, 0.38),
            entity_id="internship_contraction",
            region_id="internship_contraction",
        ),
        *_series(
            PredictiveMetric.SECTOR_GROWTH,
            (0.65, 0.58, 0.49, 0.42),
            entity_type=PredictiveEntityType.SECTOR_REGION,
            entity_id="cyber:weak_region",
            region_id="weak_region",
            sector_id="cyber",
        ),
        *_series(
            PredictiveMetric.REGIONAL_SCORE,
            (0.70, 0.78, 0.86, 0.93),
            entity_id="hot_region",
            region_id="hot_region",
        ),
    )

    warnings = PredictiveIntelligenceService().detect_early_warnings(
        observations,
        now=NOW,
    )

    by_type = {warning.warning_type: warning for warning in warnings}
    assert by_type[EarlyWarningType.COMPANY_HIRING_SLOWDOWN].status is (
        EarlyWarningStatus.CONFIRMED_WEAKENING
    )
    assert by_type[EarlyWarningType.REGIONAL_MARKET_WEAKENING].status is (
        EarlyWarningStatus.CONFIRMED_WEAKENING
    )
    assert by_type[EarlyWarningType.INTERNSHIP_PIPELINE_CONTRACTION].status is (
        EarlyWarningStatus.CONFIRMED_WEAKENING
    )
    assert by_type[EarlyWarningType.SECTOR_COOLING].status is (
        EarlyWarningStatus.CONFIRMED_WEAKENING
    )
    assert by_type[EarlyWarningType.OVERHEATED_MARKET].status is (
        EarlyWarningStatus.OVERHEATING
    )
    for warning in warnings:
        _assert_predictive_payload_common(warning)
        assert warning.evidence_basis
        assert "collapse" not in warning.summary.casefold()
        assert "crash" not in warning.summary.casefold()


def test_warning_signals_are_not_emitted_when_evidence_is_too_thin() -> None:
    observations = _series(
        PredictiveMetric.HIRING_ACTIVITY,
        (0.80, 0.52),
        entity_type=PredictiveEntityType.COMPANY_REGION,
        entity_id="thin_comp:greater_boston",
        company_id="thin_comp",
    )
    service = PredictiveIntelligenceService()

    assert service.detect_early_warnings(observations, now=NOW) == ()

    [insufficient] = service.detect_early_warnings(
        observations,
        now=NOW,
        include_insufficient=True,
    )
    assert insufficient.status is EarlyWarningStatus.INSUFFICIENT_EVIDENCE
    assert insufficient.severity.value == "info"


def test_generate_returns_payloads_with_required_forecast_metadata() -> None:
    result = PredictiveIntelligenceService().generate(
        (
            *_series(PredictiveMetric.REGIONAL_SCORE, (0.40, 0.50, 0.61, 0.70)),
            *_series(
                PredictiveMetric.AI_OPPORTUNITY,
                (0.35, 0.44, 0.55, 0.64),
                entity_id="ai_region",
                region_id="ai_region",
            ),
            *_series(
                PredictiveMetric.HIRING_ACTIVITY,
                (0.80, 0.72, 0.61, 0.52),
                entity_type=PredictiveEntityType.COMPANY_REGION,
                entity_id="warn_comp:greater_boston",
                company_id="warn_comp",
            ),
        ),
        now=NOW,
    )

    payloads = (*result.trends, *result.emerging_markets, *result.warnings)
    assert payloads
    for payload in payloads:
        _assert_predictive_payload_common(payload)


def _assert_predictive_payload_common(payload) -> None:  # noqa: ANN001
    assert payload.confidence.level.value in Confidence.values()
    assert payload.source_basis.source_count > 0
    assert payload.historical_depth.observation_count >= 2
    assert payload.uncertainty.known_uncertainties
    assert payload.reasoning_trail

    serialized = json.dumps(payload.model_dump(mode="json"))
    for forbidden in (
        "source_id",
        "source_ids",
        "raw_source",
        "raw_scrape",
        "admin_metadata",
        "private_metadata",
    ):
        assert forbidden not in serialized
