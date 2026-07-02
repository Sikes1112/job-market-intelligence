"""Reusable forecast-confidence scoring for Layer 21A."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from backend.predictive.contracts import (
    ForecastConfidence,
    ForecastConfidenceFactor,
    ForecastSourceBasis,
    ForecastUncertainty,
)
from backend.shared.confidence import Confidence


@dataclass(frozen=True, slots=True)
class ForecastConfidenceInput:
    observation_count: int
    period_count: int
    window_days: int
    latest_observed_at: date | None
    now: date
    positive_intervals: int
    negative_intervals: int
    source_basis: ForecastSourceBasis
    average_input_confidence: float | None
    concentration_ratio: float
    min_observations: int = 4
    min_window_days: int = 60
    stale_after_days: int = 120
    max_score: float | None = None
    max_level: Confidence | None = None


def build_forecast_confidence(profile: ForecastConfidenceInput) -> ForecastConfidence:
    """Build deterministic confidence from evidence quality.

    The model is intentionally simple and inspectable. It degrades confidence
    for thin, shallow, stale, contradictory, narrow, concentrated, weak, or
    interpretation-bounded evidence.
    """

    score = 0.92
    factors: list[ForecastConfidenceFactor] = []

    if profile.observation_count < 2:
        score -= 0.55
        factors.append(
            _factor(
                "insufficient_observations",
                "high",
                "Fewer than two historical observations were available.",
            )
        )
    elif profile.observation_count < profile.min_observations:
        score -= 0.35
        factors.append(
            _factor(
                "thin_historical_evidence",
                "medium",
                "Historical evidence is below the preferred observation count.",
            )
        )

    if profile.period_count < profile.min_observations:
        score -= 0.12
        factors.append(
            _factor(
                "limited_period_coverage",
                "medium",
                "Observations cover fewer distinct historical periods than preferred.",
            )
        )

    if profile.window_days < profile.min_window_days:
        score -= 0.18
        factors.append(
            _factor(
                "short_historical_window",
                "medium",
                "The historical window is short for directional forecasting.",
            )
        )

    if profile.latest_observed_at is None:
        score -= 0.18
        factors.append(
            _factor(
                "unknown_recency",
                "medium",
                "The latest observation date is unavailable.",
            )
        )
    else:
        age_days = (profile.now - profile.latest_observed_at).days
        if age_days > profile.stale_after_days:
            score -= 0.25
            factors.append(
                _factor(
                    "stale_evidence",
                    "high",
                    "The latest historical observation is older than the freshness window.",
                )
            )

    meaningful = profile.positive_intervals + profile.negative_intervals
    if meaningful:
        contradiction_ratio = (
            min(profile.positive_intervals, profile.negative_intervals) / meaningful
        )
        if contradiction_ratio >= 0.34:
            score -= 0.25
            factors.append(
                _factor(
                    "contradictory_directional_evidence",
                    "high",
                    "Historical intervals contain material movement in both directions.",
                )
            )
        elif contradiction_ratio >= 0.20:
            score -= 0.12
            factors.append(
                _factor(
                    "mixed_directional_evidence",
                    "medium",
                    "Some historical intervals move against the net direction.",
                )
            )

    if profile.source_basis.source_count < 2 or len(profile.source_basis.source_categories) < 2:
        score -= 0.14
        factors.append(
            _factor(
                "narrow_source_basis",
                "medium",
                "The signal is supported by a narrow source basis.",
            )
        )

    if profile.concentration_ratio >= 0.75:
        score -= 0.18
        factors.append(
            _factor(
                "concentrated_evidence",
                "medium",
                "Evidence is concentrated in one source category or producer stream.",
            )
        )

    if profile.average_input_confidence is None:
        score -= 0.10
        factors.append(
            _factor(
                "missing_input_confidence",
                "low",
                "Input observations did not include their own confidence scores.",
            )
        )
    elif profile.average_input_confidence < 0.55:
        score -= 0.20
        factors.append(
            _factor(
                "low_input_confidence",
                "high",
                "Input observation confidence is low.",
            )
        )
    elif profile.average_input_confidence < 0.70:
        score -= 0.10
        factors.append(
            _factor(
                "moderate_input_confidence",
                "medium",
                "Input observation confidence is moderate.",
            )
        )

    if profile.source_basis.data_basis == "unknown":
        score -= 0.16
        factors.append(
            _factor(
                "unknown_data_basis",
                "high",
                "The evidence basis is unknown.",
            )
        )

    if profile.max_score is not None and score > profile.max_score:
        score = profile.max_score
        factors.append(
            _factor(
                "bounded_interpretation",
                "medium",
                "This signal type is intentionally capped because it is interpretive.",
            )
        )

    bounded_score = max(0.0, min(1.0, round(score, 4)))
    level = _level_for_score(bounded_score, profile.observation_count)
    if profile.max_level is not None:
        level = _cap_level(level, profile.max_level)

    return ForecastConfidence(
        level=level,
        score=bounded_score,
        factors=tuple(factors),
    )


def uncertainty_from_confidence(confidence: ForecastConfidence) -> ForecastUncertainty:
    high_factor_codes = {
        factor.code for factor in confidence.factors if factor.severity == "high"
    }
    medium_factor_codes = {
        factor.code for factor in confidence.factors if factor.severity == "medium"
    }
    if confidence.level in {Confidence.LOW, Confidence.UNKNOWN} or high_factor_codes:
        level = "high"
    elif confidence.level is Confidence.MEDIUM or medium_factor_codes:
        level = "medium"
    else:
        level = "low"

    uncertainties = tuple(
        factor.explanation
        for factor in confidence.factors
        if factor.severity in {"medium", "high"}
    )
    if not uncertainties:
        uncertainties = ("Forecasts are bounded directional signals, not certain outcomes.",)

    limitations = (
        "Forecasts should be read with the stated confidence and evidence window.",
        "Signals do not promise future hiring, compensation, or applicant outcomes.",
    )
    return ForecastUncertainty(
        level=level,
        known_uncertainties=uncertainties,
        limitations=limitations,
        bounded=True,
    )


def _level_for_score(score: float, observation_count: int) -> Confidence:
    if observation_count < 2 or score < 0.25:
        return Confidence.UNKNOWN
    if score >= 0.78:
        return Confidence.HIGH
    if score >= 0.52:
        return Confidence.MEDIUM
    return Confidence.LOW


def _cap_level(level: Confidence, max_level: Confidence) -> Confidence:
    order = {
        Confidence.UNKNOWN: 0,
        Confidence.LOW: 1,
        Confidence.MEDIUM: 2,
        Confidence.HIGH: 3,
    }
    if order[level] <= order[max_level]:
        return level
    return max_level


def _factor(
    code: str,
    severity: str,
    explanation: str,
) -> ForecastConfidenceFactor:
    return ForecastConfidenceFactor(
        code=code,
        severity=severity,  # type: ignore[arg-type]
        explanation=explanation,
    )
