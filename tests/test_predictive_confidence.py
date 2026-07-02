from __future__ import annotations

from datetime import date

from backend.predictive.confidence import (
    ForecastConfidenceInput,
    build_forecast_confidence,
)
from backend.predictive.contracts import ForecastSourceBasis, PredictiveMetric
from backend.shared.confidence import Confidence

NOW = date(2026, 6, 20)


def _source_basis(
    *,
    categories: tuple[str, ...] = ("historical_snapshot", "historical_observation"),
    source_count: int = 8,
) -> ForecastSourceBasis:
    return ForecastSourceBasis(
        data_basis="test_fixture",
        source_categories=categories,
        source_count=source_count,
        observed_metrics=(PredictiveMetric.REGIONAL_SCORE,),
        notes=("Test evidence uses neutral historical observations.",),
    )


def _profile(**overrides) -> ForecastConfidenceInput:  # noqa: ANN003
    values = {
        "observation_count": 6,
        "period_count": 6,
        "window_days": 150,
        "latest_observed_at": date(2026, 6, 1),
        "now": NOW,
        "positive_intervals": 5,
        "negative_intervals": 0,
        "source_basis": _source_basis(),
        "average_input_confidence": 0.86,
        "concentration_ratio": 0.50,
    }
    values.update(overrides)
    return ForecastConfidenceInput(**values)


def test_confidence_is_high_for_deep_fresh_consistent_evidence() -> None:
    confidence = build_forecast_confidence(_profile())

    assert confidence.level is Confidence.HIGH
    assert confidence.score >= 0.78
    assert confidence.factors == ()


def test_confidence_degrades_for_thin_evidence() -> None:
    confidence = build_forecast_confidence(
        _profile(observation_count=2, period_count=2, window_days=30)
    )

    assert confidence.level in {Confidence.LOW, Confidence.UNKNOWN}
    assert {factor.code for factor in confidence.factors} >= {
        "thin_historical_evidence",
        "limited_period_coverage",
        "short_historical_window",
    }


def test_confidence_degrades_for_stale_evidence() -> None:
    confidence = build_forecast_confidence(
        _profile(latest_observed_at=date(2025, 12, 1))
    )

    assert confidence.level is Confidence.MEDIUM
    assert "stale_evidence" in {factor.code for factor in confidence.factors}


def test_confidence_degrades_for_contradictory_evidence() -> None:
    confidence = build_forecast_confidence(
        _profile(positive_intervals=3, negative_intervals=3)
    )

    assert confidence.level is Confidence.MEDIUM
    assert "contradictory_directional_evidence" in {
        factor.code for factor in confidence.factors
    }


def test_confidence_degrades_for_narrow_and_concentrated_evidence() -> None:
    confidence = build_forecast_confidence(
        _profile(
            source_basis=_source_basis(categories=("historical_snapshot",), source_count=6),
            concentration_ratio=1.0,
        )
    )

    assert confidence.level is Confidence.MEDIUM
    assert {factor.code for factor in confidence.factors} >= {
        "narrow_source_basis",
        "concentrated_evidence",
    }


def test_confidence_can_be_capped_for_interpretive_signals() -> None:
    confidence = build_forecast_confidence(
        _profile(max_score=0.72, max_level=Confidence.MEDIUM)
    )

    assert confidence.level is Confidence.MEDIUM
    assert confidence.score <= 0.72
    assert "bounded_interpretation" in {factor.code for factor in confidence.factors}
