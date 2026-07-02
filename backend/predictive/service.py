"""Core deterministic service for Layer 21A predictive intelligence."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime

from backend.predictive.contracts import (
    EarlyWarningSignal,
    EarlyWarningStatus,
    EarlyWarningType,
    EmergingMarketClassification,
    EmergingMarketSignal,
    EmergingMarketType,
    HistoricalMetricObservation,
    HistoricalTrendSignal,
    PredictiveEntityType,
    PredictiveIntelligenceResult,
    PredictiveMetric,
    TrendDirection,
    TrendType,
    WarningSeverity,
)
from backend.predictive.signals import (
    MIN_EMERGING_OBSERVATIONS,
    MIN_TREND_OBSERVATIONS,
    MIN_WARNING_OBSERVATIONS,
    MetricSeriesAnalysis,
    analyze_metric_series,
    group_observations,
    stable_signal_key,
)
from backend.shared.confidence import Confidence

TREND_METRICS = {
    PredictiveMetric.COMPANY_EXPANSION,
    PredictiveMetric.HIRING_ACTIVITY,
    PredictiveMetric.INTERNSHIP_DENSITY,
    PredictiveMetric.REGIONAL_SCORE,
    PredictiveMetric.ENTRY_LEVEL_ACCESS,
    PredictiveMetric.SECTOR_GROWTH,
}

EMERGING_METRICS = {
    PredictiveMetric.AI_OPPORTUNITY: EmergingMarketType.RISING_AI_MARKET,
    PredictiveMetric.CLOUD_OPPORTUNITY: EmergingMarketType.NEW_CLOUD_HUB,
    PredictiveMetric.CYBERSECURITY_OPPORTUNITY: (
        EmergingMarketType.CYBERSECURITY_GROWTH_REGION
    ),
    PredictiveMetric.PRODUCT_OPPORTUNITY: (
        EmergingMarketType.PRODUCT_ROLE_EXPANSION_REGION
    ),
    PredictiveMetric.HIDDEN_OPPORTUNITY: (
        EmergingMarketType.UNDERPRICED_OPPORTUNITY_MARKET
    ),
}


class PredictiveIntelligenceService:
    """Pure service over neutral historical observations."""

    def model_historical_trends(
        self,
        observations: Iterable[HistoricalMetricObservation],
        *,
        now: date | None = None,
    ) -> tuple[HistoricalTrendSignal, ...]:
        now = now or datetime.now(UTC).date()
        trends: list[HistoricalTrendSignal] = []
        for series in group_observations(observations):
            if series.metric not in TREND_METRICS or len(series.observations) < 2:
                continue
            analysis = analyze_metric_series(
                series,
                now=now,
                min_observations=MIN_TREND_OBSERVATIONS,
            )
            trends.append(_trend_signal(analysis))
        return tuple(trends)

    def detect_emerging_markets(
        self,
        observations: Iterable[HistoricalMetricObservation],
        *,
        now: date | None = None,
    ) -> tuple[EmergingMarketSignal, ...]:
        now = now or datetime.now(UTC).date()
        signals: list[EmergingMarketSignal] = []
        for series in group_observations(observations):
            emerging_type = EMERGING_METRICS.get(series.metric)
            if emerging_type is None:
                continue
            if series.entity_type is not PredictiveEntityType.REGION or not series.region_id:
                continue
            is_underpriced = (
                emerging_type is EmergingMarketType.UNDERPRICED_OPPORTUNITY_MARKET
            )
            max_score = 0.72 if is_underpriced else None
            max_level = Confidence.MEDIUM if is_underpriced else None
            analysis = analyze_metric_series(
                series,
                now=now,
                min_observations=MIN_EMERGING_OBSERVATIONS,
                max_confidence_score=max_score,
                max_confidence_level=max_level,
            )
            signals.append(_emerging_signal(analysis, emerging_type))
        return tuple(signals)

    def detect_early_warnings(
        self,
        observations: Iterable[HistoricalMetricObservation],
        *,
        now: date | None = None,
        include_insufficient: bool = False,
    ) -> tuple[EarlyWarningSignal, ...]:
        now = now or datetime.now(UTC).date()
        warnings: list[EarlyWarningSignal] = []
        for series in group_observations(observations):
            if series.metric not in {
                PredictiveMetric.HIRING_ACTIVITY,
                PredictiveMetric.REGIONAL_SCORE,
                PredictiveMetric.ENTRY_LEVEL_ACCESS,
                PredictiveMetric.INTERNSHIP_DENSITY,
                PredictiveMetric.SECTOR_GROWTH,
            }:
                continue
            analysis = analyze_metric_series(
                series,
                now=now,
                min_observations=MIN_WARNING_OBSERVATIONS,
            )
            warning = _warning_signal(analysis)
            if warning is None:
                continue
            if (
                warning.status is EarlyWarningStatus.INSUFFICIENT_EVIDENCE
                and not include_insufficient
            ):
                continue
            warnings.append(warning)
        return tuple(warnings)

    def generate(
        self,
        observations: Iterable[HistoricalMetricObservation],
        *,
        now: date | None = None,
    ) -> PredictiveIntelligenceResult:
        rows = tuple(observations)
        now = now or datetime.now(UTC).date()
        return PredictiveIntelligenceResult(
            trends=self.model_historical_trends(rows, now=now),
            emerging_markets=self.detect_emerging_markets(rows, now=now),
            warnings=self.detect_early_warnings(rows, now=now),
        )


def _trend_signal(analysis: MetricSeriesAnalysis) -> HistoricalTrendSignal:
    trend_type = _trend_type(analysis)
    return HistoricalTrendSignal(
        signal_key=stable_signal_key("trend", analysis, trend_type.value),
        trend_type=trend_type,
        entity=analysis.entity,
        metric=analysis.series.metric,
        direction=analysis.direction,
        magnitude=analysis.magnitude,
        time_window=analysis.time_window,
        historical_depth=analysis.historical_depth,
        supporting_evidence=(analysis.evidence,),
        confidence=analysis.confidence,
        source_basis=analysis.source_basis,
        uncertainty=analysis.uncertainty,
        reasoning_trail=analysis.reasoning_trail,
        summary=_trend_summary(analysis, trend_type),
    )


def _trend_type(analysis: MetricSeriesAnalysis) -> TrendType:
    metric = analysis.series.metric
    if metric is PredictiveMetric.COMPANY_EXPANSION:
        return TrendType.COMPANY_EXPANSION
    if metric is PredictiveMetric.HIRING_ACTIVITY:
        if analysis.direction is TrendDirection.WEAKENING:
            return TrendType.HIRING_CONTRACTION
        return TrendType.HIRING_GROWTH
    if metric is PredictiveMetric.INTERNSHIP_DENSITY:
        return TrendType.INTERNSHIP_SEASONALITY
    if metric is PredictiveMetric.SECTOR_GROWTH:
        return TrendType.SECTOR_SPECIFIC_GROWTH
    return TrendType.REGIONAL_SCORE_MOVEMENT


def _trend_summary(analysis: MetricSeriesAnalysis, trend_type: TrendType) -> str:
    return (
        f"{trend_type.value} is {analysis.direction.value} across "
        f"{analysis.historical_depth.observation_count} historical observations."
    )


def _emerging_signal(
    analysis: MetricSeriesAnalysis,
    emerging_type: EmergingMarketType,
) -> EmergingMarketSignal:
    classification = _emerging_classification(analysis.direction)
    label = _emerging_label(emerging_type, classification)
    return EmergingMarketSignal(
        signal_key=stable_signal_key("emerging", analysis, emerging_type.value),
        emerging_type=emerging_type,
        region_id=analysis.series.region_id or analysis.series.entity_id,
        classification=classification,
        emerging_label=label,
        signal_basis=(analysis.evidence,),
        confidence=analysis.confidence,
        source_basis=analysis.source_basis,
        historical_depth=analysis.historical_depth,
        uncertainty=analysis.uncertainty,
        reasoning_trail=analysis.reasoning_trail,
        opportunity_framing=_opportunity_framing(emerging_type, classification),
    )


def _emerging_classification(direction: TrendDirection) -> EmergingMarketClassification:
    if direction is TrendDirection.RISING:
        return EmergingMarketClassification.RISING
    if direction is TrendDirection.WEAKENING:
        return EmergingMarketClassification.WEAKENING
    if direction is TrendDirection.NOISY or direction is TrendDirection.SEASONAL:
        return EmergingMarketClassification.NOISY
    if direction is TrendDirection.INSUFFICIENT_DATA:
        return EmergingMarketClassification.INSUFFICIENT_DATA
    return EmergingMarketClassification.STABLE


def _emerging_label(
    emerging_type: EmergingMarketType,
    classification: EmergingMarketClassification,
) -> str | None:
    if classification is not EmergingMarketClassification.RISING:
        return None
    labels = {
        EmergingMarketType.RISING_AI_MARKET: "Rising AI market signal",
        EmergingMarketType.NEW_CLOUD_HUB: "New cloud hub signal",
        EmergingMarketType.CYBERSECURITY_GROWTH_REGION: (
            "Cybersecurity growth region signal"
        ),
        EmergingMarketType.PRODUCT_ROLE_EXPANSION_REGION: (
            "Product role expansion region signal"
        ),
        EmergingMarketType.UNDERPRICED_OPPORTUNITY_MARKET: (
            "Underpriced opportunity signal"
        ),
    }
    return labels[emerging_type]


def _opportunity_framing(
    emerging_type: EmergingMarketType,
    classification: EmergingMarketClassification,
) -> str:
    if emerging_type is EmergingMarketType.UNDERPRICED_OPPORTUNITY_MARKET:
        return (
            "This is an opportunity signal from observed movement, not a certain "
            "market outcome."
        )
    if classification is EmergingMarketClassification.RISING:
        return "The label is based on observed historical movement and bounded confidence."
    return "No emerging label is applied unless the historical movement supports one."


def _warning_signal(analysis: MetricSeriesAnalysis) -> EarlyWarningSignal | None:
    if analysis.direction is TrendDirection.INSUFFICIENT_DATA:
        return _build_warning(
            analysis,
            warning_type=_warning_type_for_analysis(analysis),
            status=EarlyWarningStatus.INSUFFICIENT_EVIDENCE,
            severity=WarningSeverity.INFO,
            summary="Evidence is too limited to issue a weakening warning.",
        )

    overheating = _overheating_signal(analysis)
    if overheating is not None:
        return overheating

    if analysis.direction is not TrendDirection.WEAKENING:
        return None

    confirmed = _confirmed_weakening(analysis)
    possible = _possible_weakening(analysis)
    if not confirmed and not possible:
        return None
    status = (
        EarlyWarningStatus.CONFIRMED_WEAKENING
        if confirmed
        else EarlyWarningStatus.POSSIBLE_WEAKENING
    )
    severity = _weakening_severity(analysis, confirmed=confirmed)
    summary = (
        "Historical observations show sustained weakening in this signal."
        if confirmed
        else "Historical observations show possible weakening in this signal."
    )
    return _build_warning(
        analysis,
        warning_type=_warning_type_for_analysis(analysis),
        status=status,
        severity=severity,
        summary=summary,
    )


def _overheating_signal(analysis: MetricSeriesAnalysis) -> EarlyWarningSignal | None:
    if analysis.series.metric is not PredictiveMetric.REGIONAL_SCORE:
        return None
    if analysis.direction is not TrendDirection.RISING:
        return None
    if analysis.latest_value < 0.85 or analysis.net_change < 0.15:
        return None
    severity = WarningSeverity.HIGH if analysis.latest_value >= 0.92 else WarningSeverity.MEDIUM
    return _build_warning(
        analysis,
        warning_type=EarlyWarningType.OVERHEATED_MARKET,
        status=EarlyWarningStatus.OVERHEATING,
        severity=severity,
        summary="Historical observations show a fast-rising, high-intensity market signal.",
    )


def _confirmed_weakening(analysis: MetricSeriesAnalysis) -> bool:
    return analysis.net_change <= -0.12 and analysis.negative_intervals >= 2


def _possible_weakening(analysis: MetricSeriesAnalysis) -> bool:
    return analysis.net_change <= -0.06 or analysis.negative_intervals >= 2


def _weakening_severity(
    analysis: MetricSeriesAnalysis,
    *,
    confirmed: bool,
) -> WarningSeverity:
    if confirmed and abs(analysis.net_change) >= 0.20:
        return WarningSeverity.HIGH
    if confirmed:
        return WarningSeverity.MEDIUM
    return WarningSeverity.LOW


def _warning_type_for_analysis(analysis: MetricSeriesAnalysis) -> EarlyWarningType:
    metric = analysis.series.metric
    if metric is PredictiveMetric.HIRING_ACTIVITY:
        return EarlyWarningType.COMPANY_HIRING_SLOWDOWN
    if metric is PredictiveMetric.INTERNSHIP_DENSITY:
        return EarlyWarningType.INTERNSHIP_PIPELINE_CONTRACTION
    if metric is PredictiveMetric.SECTOR_GROWTH:
        return EarlyWarningType.SECTOR_COOLING
    return EarlyWarningType.REGIONAL_MARKET_WEAKENING


def _build_warning(
    analysis: MetricSeriesAnalysis,
    *,
    warning_type: EarlyWarningType,
    status: EarlyWarningStatus,
    severity: WarningSeverity,
    summary: str,
) -> EarlyWarningSignal:
    return EarlyWarningSignal(
        signal_key=stable_signal_key("warning", analysis, warning_type.value),
        warning_type=warning_type,
        status=status,
        severity=severity,
        affected_entity=analysis.entity,
        evidence_basis=(analysis.evidence,),
        confidence=analysis.confidence,
        source_basis=analysis.source_basis,
        historical_depth=analysis.historical_depth,
        uncertainty=analysis.uncertainty,
        reasoning_trail=analysis.reasoning_trail,
        summary=summary,
    )
