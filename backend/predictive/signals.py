"""Deterministic signal analysis helpers for Layer 21A."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from backend.predictive.confidence import (
    ForecastConfidenceInput,
    build_forecast_confidence,
    uncertainty_from_confidence,
)
from backend.predictive.contracts import (
    AffectedEntity,
    ForecastConfidence,
    ForecastSourceBasis,
    ForecastTimeWindow,
    ForecastUncertainty,
    HistoricalDepth,
    HistoricalMetricObservation,
    PredictiveEntityType,
    PredictiveMetric,
    ReasoningStep,
    SupportingEvidence,
    TrendDirection,
)
from backend.shared.confidence import Confidence

MIN_TREND_OBSERVATIONS = 4
MIN_WARNING_OBSERVATIONS = 4
MIN_EMERGING_OBSERVATIONS = 4
SCORE_DELTA_THRESHOLD = 0.03
SCORE_STABILITY_THRESHOLD = 0.05


@dataclass(frozen=True, slots=True)
class MetricSeries:
    entity_type: PredictiveEntityType
    entity_id: str
    metric: PredictiveMetric
    region_id: str | None
    company_id: str | None
    sector_id: str | None
    observations: tuple[HistoricalMetricObservation, ...]


@dataclass(frozen=True, slots=True)
class MetricSeriesAnalysis:
    series: MetricSeries
    direction: TrendDirection
    net_change: float
    magnitude: float
    amplitude: float
    positive_intervals: int
    negative_intervals: int
    flat_intervals: int
    time_window: ForecastTimeWindow
    historical_depth: HistoricalDepth
    source_basis: ForecastSourceBasis
    evidence: SupportingEvidence
    confidence: ForecastConfidence
    uncertainty: ForecastUncertainty
    reasoning_trail: tuple[ReasoningStep, ...]

    @property
    def latest_value(self) -> float:
        return self.series.observations[-1].value

    @property
    def latest_observed_at(self) -> date:
        return self.series.observations[-1].observed_at

    @property
    def entity(self) -> AffectedEntity:
        return AffectedEntity(
            entity_type=self.series.entity_type,
            entity_id=self.series.entity_id,
            region_id=self.series.region_id,
            company_id=self.series.company_id,
            sector_id=self.series.sector_id,
        )


def group_observations(
    observations: Iterable[HistoricalMetricObservation],
) -> tuple[MetricSeries, ...]:
    grouped: dict[
        tuple[
            PredictiveEntityType,
            str,
            PredictiveMetric,
            str | None,
            str | None,
            str | None,
        ],
        list[HistoricalMetricObservation],
    ] = defaultdict(list)
    for observation in observations:
        key = (
            observation.entity_type,
            observation.entity_id,
            observation.metric,
            observation.region_id,
            observation.company_id,
            observation.sector_id,
        )
        grouped[key].append(observation)

    series: list[MetricSeries] = []
    for (
        entity_type,
        entity_id,
        metric,
        region_id,
        company_id,
        sector_id,
    ), rows in grouped.items():
        ordered = tuple(
            sorted(
                rows,
                key=lambda row: (
                    row.observed_at,
                    row.value,
                    row.entity_id,
                    row.metric.value,
                ),
            )
        )
        series.append(
            MetricSeries(
                entity_type=entity_type,
                entity_id=entity_id,
                metric=metric,
                region_id=region_id,
                company_id=company_id,
                sector_id=sector_id,
                observations=ordered,
            )
        )
    return tuple(
        sorted(
            series,
            key=lambda item: (
                item.entity_type.value,
                item.entity_id,
                item.metric.value,
                item.region_id or "",
                item.company_id or "",
                item.sector_id or "",
            ),
        )
    )


def analyze_metric_series(
    series: MetricSeries,
    *,
    now: date,
    min_observations: int = MIN_TREND_OBSERVATIONS,
    max_confidence_score: float | None = None,
    max_confidence_level: Confidence | None = None,
) -> MetricSeriesAnalysis:
    observations = series.observations
    if not observations:
        raise ValueError("metric series requires at least one observation")

    values = [row.value for row in observations]
    threshold = _meaningful_delta_threshold(values)
    intervals = [values[idx] - values[idx - 1] for idx in range(1, len(values))]
    positive_intervals = sum(1 for delta in intervals if delta >= threshold)
    negative_intervals = sum(1 for delta in intervals if delta <= -threshold)
    flat_intervals = max(0, len(intervals) - positive_intervals - negative_intervals)
    net_change = values[-1] - values[0] if len(values) >= 2 else 0.0
    amplitude = max(values) - min(values)
    direction = _direction(
        series.metric,
        values=values,
        net_change=net_change,
        amplitude=amplitude,
        positive_intervals=positive_intervals,
        negative_intervals=negative_intervals,
        threshold=threshold,
        min_observations=min_observations,
    )
    magnitude = amplitude if direction is TrendDirection.SEASONAL else abs(net_change)
    first_date = observations[0].observed_at
    latest_date = observations[-1].observed_at
    window_days = max(0, (latest_date - first_date).days)
    time_window = ForecastTimeWindow(
        start=first_date,
        end=latest_date,
        window_days=window_days,
    )
    depth = HistoricalDepth(
        observation_count=len(observations),
        period_count=len({row.observed_at for row in observations}),
        window_start=first_date,
        window_end=latest_date,
        window_days=window_days,
        latest_observed_at=latest_date,
    )
    source_basis = source_basis_for_observations(observations)
    confidence = build_forecast_confidence(
        ForecastConfidenceInput(
            observation_count=depth.observation_count,
            period_count=depth.period_count,
            window_days=depth.window_days,
            latest_observed_at=depth.latest_observed_at,
            now=now,
            positive_intervals=positive_intervals,
            negative_intervals=negative_intervals,
            source_basis=source_basis,
            average_input_confidence=_average_input_confidence(observations),
            concentration_ratio=_concentration_ratio(observations),
            min_observations=min_observations,
            max_score=max_confidence_score,
            max_level=max_confidence_level,
        )
    )
    uncertainty = uncertainty_from_confidence(confidence)
    evidence = SupportingEvidence(
        metric=series.metric,
        observation_count=len(observations),
        first_observed_at=first_date,
        latest_observed_at=latest_date,
        first_value=values[0],
        latest_value=values[-1],
        net_change=net_change,
        magnitude=magnitude,
        positive_intervals=positive_intervals,
        negative_intervals=negative_intervals,
        flat_intervals=flat_intervals,
        peak_value=max(values),
        trough_value=min(values),
        evidence_summary=_evidence_summary(
            metric=series.metric,
            observation_count=len(observations),
            net_change=net_change,
            magnitude=magnitude,
        ),
    )
    reasoning = _reasoning_trail(
        direction=direction,
        observation_count=len(observations),
        first_date=first_date,
        latest_date=latest_date,
        net_change=net_change,
        confidence=confidence,
    )
    return MetricSeriesAnalysis(
        series=series,
        direction=direction,
        net_change=net_change,
        magnitude=magnitude,
        amplitude=amplitude,
        positive_intervals=positive_intervals,
        negative_intervals=negative_intervals,
        flat_intervals=flat_intervals,
        time_window=time_window,
        historical_depth=depth,
        source_basis=source_basis,
        evidence=evidence,
        confidence=confidence,
        uncertainty=uncertainty,
        reasoning_trail=reasoning,
    )


def source_basis_for_observations(
    observations: tuple[HistoricalMetricObservation, ...],
) -> ForecastSourceBasis:
    data_bases = {row.data_basis for row in observations}
    data_basis = next(iter(data_bases)) if len(data_bases) == 1 else "mixed"
    categories = sorted({category for row in observations for category in row.source_categories})
    coverage_tiers = sorted({row.coverage_tier for row in observations if row.coverage_tier})
    freshness_states = sorted(
        {row.freshness_state for row in observations if row.freshness_state}
    )
    metrics = tuple(sorted({row.metric for row in observations}, key=lambda metric: metric.value))
    source_count = sum(row.source_count for row in observations)
    return ForecastSourceBasis(
        data_basis=data_basis,  # type: ignore[arg-type]
        source_categories=tuple(categories),
        source_count=source_count,
        observed_metrics=metrics,
        coverage_tiers=tuple(coverage_tiers),
        freshness_states=tuple(freshness_states),
        notes=("Derived from historical observations only.",),
    )


def stable_signal_key(prefix: str, analysis: MetricSeriesAnalysis, suffix: str) -> str:
    window = analysis.time_window
    series = analysis.series
    return (
        f"{prefix}:{suffix}:{series.entity_type.value}:{series.entity_id}:"
        f"{series.metric.value}:{window.start.isoformat()}:{window.end.isoformat()}"
    )


def _direction(
    metric: PredictiveMetric,
    *,
    values: list[float],
    net_change: float,
    amplitude: float,
    positive_intervals: int,
    negative_intervals: int,
    threshold: float,
    min_observations: int,
) -> TrendDirection:
    if len(values) < min_observations:
        return TrendDirection.INSUFFICIENT_DATA
    if _is_internship_seasonality(
        metric,
        values=values,
        net_change=net_change,
        amplitude=amplitude,
        positive_intervals=positive_intervals,
        negative_intervals=negative_intervals,
        threshold=threshold,
    ):
        return TrendDirection.SEASONAL
    meaningful = positive_intervals + negative_intervals
    if meaningful:
        contradiction_ratio = min(positive_intervals, negative_intervals) / meaningful
        if contradiction_ratio >= 0.34 and abs(net_change) <= max(
            SCORE_STABILITY_THRESHOLD,
            threshold * 3,
        ):
            return TrendDirection.NOISY
    if abs(net_change) < max(SCORE_STABILITY_THRESHOLD, threshold * 1.5):
        return TrendDirection.STABLE
    return TrendDirection.RISING if net_change > 0 else TrendDirection.WEAKENING


def _is_internship_seasonality(
    metric: PredictiveMetric,
    *,
    values: list[float],
    net_change: float,
    amplitude: float,
    positive_intervals: int,
    negative_intervals: int,
    threshold: float,
) -> bool:
    return (
        metric is PredictiveMetric.INTERNSHIP_DENSITY
        and len(values) >= 6
        and positive_intervals >= 2
        and negative_intervals >= 2
        and amplitude >= max(0.12, threshold * 4)
        and abs(net_change) <= amplitude * 0.50
    )


def _meaningful_delta_threshold(values: list[float]) -> float:
    if any(abs(value) > 1.5 for value in values):
        return 2.0
    return SCORE_DELTA_THRESHOLD


def _average_input_confidence(
    observations: tuple[HistoricalMetricObservation, ...],
) -> float | None:
    values = [row.confidence_score for row in observations if row.confidence_score is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _concentration_ratio(
    observations: tuple[HistoricalMetricObservation, ...],
) -> float:
    total = sum(row.source_count for row in observations)
    if total <= 0:
        return 1.0
    counts: Counter[str] = Counter()
    for row in observations:
        category_weight = row.source_count / len(row.source_categories)
        for category in row.source_categories:
            counts[category] += category_weight
    return max(counts.values()) / total if counts else 1.0


def _evidence_summary(
    *,
    metric: PredictiveMetric,
    observation_count: int,
    net_change: float,
    magnitude: float,
) -> str:
    signed = f"{net_change:+.3f}"
    return (
        f"{metric.value} used {observation_count} observations with net movement "
        f"{signed} and magnitude {magnitude:.3f}."
    )


def _reasoning_trail(
    *,
    direction: TrendDirection,
    observation_count: int,
    first_date: date,
    latest_date: date,
    net_change: float,
    confidence: ForecastConfidence,
) -> tuple[ReasoningStep, ...]:
    return (
        ReasoningStep(
            code="historical_window",
            summary=(
                f"Compared {observation_count} historical observations from "
                f"{first_date.isoformat()} through {latest_date.isoformat()}."
            ),
        ),
        ReasoningStep(
            code="directional_movement",
            summary=(
                f"Classified movement as {direction.value} from a net change of "
                f"{net_change:+.3f}."
            ),
        ),
        ReasoningStep(
            code="confidence_bounds",
            summary=(
                f"Assigned {confidence.level.value} confidence after evidence-quality "
                "checks."
            ),
        ),
    )
