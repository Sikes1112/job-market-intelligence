"""Predictive report builder for Layer 21B."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime

from backend.predictive.contracts import (
    AffectedEntity,
    EarlyWarningSignal,
    EarlyWarningStatus,
    EarlyWarningType,
    EmergingMarketClassification,
    EmergingMarketSignal,
    EmergingMarketType,
    HistoricalMetricObservation,
    HistoricalTrendSignal,
    PredictiveEntityType,
    PredictiveForecastType,
    PredictiveMetric,
    PredictiveReportForecast,
    PredictiveReportPayload,
    PredictiveReportSection,
    PredictiveSignalKind,
    PredictiveSupportingSignal,
    TrendDirection,
    TrendType,
)
from backend.predictive.service import PredictiveIntelligenceService

DEFAULT_TIME_HORIZON = "next_12_months"


class PredictiveReportBuilder:
    """Build public-safe predictive report payloads from Layer 21A outputs."""

    def __init__(self, service: PredictiveIntelligenceService | None = None) -> None:
        self._service = service or PredictiveIntelligenceService()

    def build_report(
        self,
        observations: Iterable[HistoricalMetricObservation],
        *,
        generated_at: datetime | None = None,
        now: date | None = None,
        time_horizon: str = DEFAULT_TIME_HORIZON,
    ) -> PredictiveReportPayload:
        generated_at = generated_at or datetime.now(UTC)
        now = now or generated_at.date()
        rows = tuple(observations)
        trends = self._service.model_historical_trends(rows, now=now)
        emerging = self._service.detect_emerging_markets(rows, now=now)
        warnings = self._service.detect_early_warnings(
            rows,
            now=now,
            include_insufficient=True,
        )
        sections = (
            _ai_growth_section(emerging, time_horizon),
            _entry_access_section(trends, time_horizon),
            _company_expansion_section(trends, time_horizon),
            _sector_conditions_section(warnings, time_horizon),
            _underpriced_section(emerging, time_horizon),
        )
        return PredictiveReportPayload(
            report_id=f"predictive_report:{time_horizon}",
            title="Predictive labor-market intelligence",
            generated_at=generated_at,
            time_horizon=time_horizon,
            forecast_disclaimer=(
                "Forecasts are bounded directional signals from historical evidence, "
                "not certain outcomes."
            ),
            methodology_summary=(
                "This report reuses Layer 21A deterministic trend, emerging-market, "
                "warning, confidence, uncertainty, source-basis, historical-depth, "
                "and reasoning contracts."
            ),
            sections=sections,
            limitations=(
                "Weak or limited evidence is shown as low-confidence or "
                "insufficient-data messaging.",
                "Forecasts depend on the historical producer exports supplied to this report.",
                "No live scraping, nondeterministic model calls, or raw source records are used.",
            ),
        )


def _ai_growth_section(
    emerging: tuple[EmergingMarketSignal, ...],
    time_horizon: str,
) -> PredictiveReportSection:
    relevant = tuple(
        signal
        for signal in emerging
        if signal.emerging_type is EmergingMarketType.RISING_AI_MARKET
    )
    return PredictiveReportSection(
        section_key="ai_role_market_growth",
        title="AI role market growth forecasts",
        summary=(
            "Markets appear here when AI opportunity observations support a rising, "
            "stable, noisy, weakening, or insufficient-data classification."
        ),
        why_this_section_exists=(
            "This section exists to show whether historical AI opportunity movement "
            "supports a bounded growth forecast."
        ),
        forecasts=tuple(
            _forecast_from_emerging(
                signal,
                forecast_type=PredictiveForecastType.AI_ROLE_MARKET_GROWTH_12M,
                time_horizon=time_horizon,
            )
            for signal in sorted(relevant, key=lambda item: item.region_id)
        ),
    )


def _entry_access_section(
    trends: tuple[HistoricalTrendSignal, ...],
    time_horizon: str,
) -> PredictiveReportSection:
    relevant = tuple(
        trend
        for trend in trends
        if trend.metric is PredictiveMetric.ENTRY_LEVEL_ACCESS
        and trend.direction
        in {
            TrendDirection.WEAKENING,
            TrendDirection.INSUFFICIENT_DATA,
        }
    )
    return PredictiveReportSection(
        section_key="entry_level_access_weakening",
        title="Entry-level tech access weakening forecasts",
        summary=(
            "Regions appear here when historical entry-level access movement weakens "
            "or does not yet have enough evidence for a stronger statement."
        ),
        why_this_section_exists=(
            "This section exists to make entry-level access softening visible without "
            "treating sparse evidence as a firm forecast."
        ),
        forecasts=tuple(
            _forecast_from_trend(
                trend,
                forecast_type=PredictiveForecastType.ENTRY_LEVEL_ACCESS_WEAKENING,
                time_horizon=time_horizon,
            )
            for trend in sorted(relevant, key=lambda item: item.entity.entity_id)
        ),
    )


def _company_expansion_section(
    trends: tuple[HistoricalTrendSignal, ...],
    time_horizon: str,
) -> PredictiveReportSection:
    relevant = tuple(
        trend
        for trend in trends
        if trend.trend_type
        in {
            TrendType.COMPANY_EXPANSION,
            TrendType.HIRING_GROWTH,
        }
        and trend.direction
        in {
            TrendDirection.RISING,
            TrendDirection.INSUFFICIENT_DATA,
        }
    )
    return PredictiveReportSection(
        section_key="early_career_hiring_expansion",
        title="Company early-career hiring expansion forecasts",
        summary=(
            "Companies appear here when company-region expansion or hiring activity "
            "observations support a bounded expansion signal."
        ),
        why_this_section_exists=(
            "This section exists to surface company-region expansion signals without "
            "making Layer 21 the employer authority."
        ),
        forecasts=tuple(
            _forecast_from_trend(
                trend,
                forecast_type=PredictiveForecastType.EARLY_CAREER_HIRING_EXPANSION,
                time_horizon=time_horizon,
            )
            for trend in sorted(relevant, key=lambda item: item.entity.entity_id)
        ),
    )


def _sector_conditions_section(
    warnings: tuple[EarlyWarningSignal, ...],
    time_horizon: str,
) -> PredictiveReportSection:
    relevant = tuple(
        warning
        for warning in warnings
        if warning.warning_type
        in {
            EarlyWarningType.SECTOR_COOLING,
            EarlyWarningType.OVERHEATED_MARKET,
        }
    )
    return PredictiveReportSection(
        section_key="sector_cooling_overheating",
        title="Sector cooling and overheated condition forecasts",
        summary=(
            "Signals appear here when historical sector or regional movement supports "
            "a cooling, overheating, or insufficient-evidence warning."
        ),
        why_this_section_exists=(
            "This section exists to separate confirmed weakening, possible weakening, "
            "overheating, and insufficient evidence in non-alarmist language."
        ),
        forecasts=tuple(
            _forecast_from_warning(
                warning,
                forecast_type=PredictiveForecastType.SECTOR_CONDITION_CHANGE,
                time_horizon=time_horizon,
            )
            for warning in sorted(
                relevant,
                key=lambda item: (
                    item.warning_type.value,
                    item.affected_entity.entity_id,
                ),
            )
        ),
    )


def _underpriced_section(
    emerging: tuple[EmergingMarketSignal, ...],
    time_horizon: str,
) -> PredictiveReportSection:
    relevant = tuple(
        signal
        for signal in emerging
        if signal.emerging_type is EmergingMarketType.UNDERPRICED_OPPORTUNITY_MARKET
    )
    return PredictiveReportSection(
        section_key="underpriced_opportunity_markets",
        title="Underpriced opportunity market forecasts",
        summary=(
            "Markets appear here when hidden opportunity observations support an "
            "opportunity signal with capped confidence."
        ),
        why_this_section_exists=(
            "This section exists to frame underpriced markets as opportunity signals, "
            "not certain outcomes."
        ),
        forecasts=tuple(
            _forecast_from_emerging(
                signal,
                forecast_type=PredictiveForecastType.UNDERPRICED_OPPORTUNITY_MARKET,
                time_horizon=time_horizon,
            )
            for signal in sorted(relevant, key=lambda item: item.region_id)
        ),
    )


def _forecast_from_trend(
    trend: HistoricalTrendSignal,
    *,
    forecast_type: PredictiveForecastType,
    time_horizon: str,
) -> PredictiveReportForecast:
    label = _forecast_label_for_trend(trend)
    return PredictiveReportForecast(
        forecast_id=f"forecast:{forecast_type.value}:{trend.signal_key}",
        forecast_title=f"{label} forecast for {_entity_label(trend.entity.entity_id)}",
        forecast_label=label,
        forecast_type=forecast_type,
        affected_entity=trend.entity,
        time_horizon=time_horizon,
        confidence=trend.confidence,
        source_basis=trend.source_basis,
        historical_depth=trend.historical_depth,
        uncertainty=trend.uncertainty,
        reasoning_trail=trend.reasoning_trail,
        supporting_signals=(_supporting_trend(trend),),
        safe_display_summary=_trend_display_summary(trend),
        why_this_forecast_exists=(
            "The forecast exists because the supporting trend was derived from "
            "historical observations and carries bounded confidence."
        ),
    )


def _forecast_from_emerging(
    signal: EmergingMarketSignal,
    *,
    forecast_type: PredictiveForecastType,
    time_horizon: str,
) -> PredictiveReportForecast:
    label = _forecast_label_for_emerging(signal)
    return PredictiveReportForecast(
        forecast_id=f"forecast:{forecast_type.value}:{signal.signal_key}",
        forecast_title=f"{label} forecast for {_entity_label(signal.region_id)}",
        forecast_label=label,
        forecast_type=forecast_type,
        affected_entity=_region_entity(signal.region_id),
        time_horizon=time_horizon,
        confidence=signal.confidence,
        source_basis=signal.source_basis,
        historical_depth=signal.historical_depth,
        uncertainty=signal.uncertainty,
        reasoning_trail=signal.reasoning_trail,
        supporting_signals=(_supporting_emerging(signal),),
        safe_display_summary=_emerging_display_summary(signal),
        why_this_forecast_exists=(
            "The forecast exists because an emerging-market signal was classified "
            "from observable historical movement."
        ),
    )


def _forecast_from_warning(
    warning: EarlyWarningSignal,
    *,
    forecast_type: PredictiveForecastType,
    time_horizon: str,
) -> PredictiveReportForecast:
    label = _forecast_label_for_warning(warning)
    return PredictiveReportForecast(
        forecast_id=f"forecast:{forecast_type.value}:{warning.signal_key}",
        forecast_title=f"{label} forecast for {_entity_label(warning.affected_entity.entity_id)}",
        forecast_label=label,
        forecast_type=forecast_type,
        affected_entity=warning.affected_entity,
        time_horizon=time_horizon,
        confidence=warning.confidence,
        source_basis=warning.source_basis,
        historical_depth=warning.historical_depth,
        uncertainty=warning.uncertainty,
        reasoning_trail=warning.reasoning_trail,
        supporting_signals=(_supporting_warning(warning),),
        safe_display_summary=_warning_display_summary(warning),
        why_this_forecast_exists=(
            "The forecast exists because the supporting warning signal was produced "
            "from historical movement with explicit evidence bounds."
        ),
    )


def _supporting_trend(trend: HistoricalTrendSignal) -> PredictiveSupportingSignal:
    return PredictiveSupportingSignal(
        signal_key=trend.signal_key,
        signal_kind=PredictiveSignalKind.TREND,
        signal_type=trend.trend_type.value,
        signal_status=trend.direction.value,
        summary=trend.summary,
    )


def _supporting_emerging(signal: EmergingMarketSignal) -> PredictiveSupportingSignal:
    return PredictiveSupportingSignal(
        signal_key=signal.signal_key,
        signal_kind=PredictiveSignalKind.EMERGING_MARKET,
        signal_type=signal.emerging_type.value,
        signal_status=signal.classification.value,
        summary=signal.opportunity_framing,
    )


def _supporting_warning(warning: EarlyWarningSignal) -> PredictiveSupportingSignal:
    return PredictiveSupportingSignal(
        signal_key=warning.signal_key,
        signal_kind=PredictiveSignalKind.EARLY_WARNING,
        signal_type=warning.warning_type.value,
        signal_status=warning.status.value,
        summary=warning.summary,
    )


def _forecast_label_for_trend(trend: HistoricalTrendSignal) -> str:
    if trend.direction is TrendDirection.INSUFFICIENT_DATA:
        return "Insufficient-data forecast"
    if trend.direction is TrendDirection.WEAKENING:
        return "Weakening forecast"
    if trend.direction is TrendDirection.RISING:
        return "Growth signal forecast"
    if trend.direction is TrendDirection.SEASONAL:
        return "Seasonal movement forecast"
    return "Directional forecast"


def _forecast_label_for_emerging(signal: EmergingMarketSignal) -> str:
    if signal.classification is EmergingMarketClassification.INSUFFICIENT_DATA:
        return "Insufficient-data opportunity forecast"
    if signal.classification is EmergingMarketClassification.RISING:
        return signal.emerging_label or "Emerging opportunity forecast"
    if signal.classification is EmergingMarketClassification.WEAKENING:
        return "Weakening opportunity forecast"
    if signal.classification is EmergingMarketClassification.NOISY:
        return "Noisy opportunity forecast"
    return "Stable opportunity forecast"


def _forecast_label_for_warning(warning: EarlyWarningSignal) -> str:
    if warning.status is EarlyWarningStatus.INSUFFICIENT_EVIDENCE:
        return "Insufficient-evidence warning forecast"
    if warning.status is EarlyWarningStatus.OVERHEATING:
        return "Overheated market condition forecast"
    if warning.status is EarlyWarningStatus.CONFIRMED_WEAKENING:
        return "Confirmed weakening forecast"
    return "Possible weakening forecast"


def _trend_display_summary(trend: HistoricalTrendSignal) -> str:
    if trend.direction is TrendDirection.INSUFFICIENT_DATA:
        return (
            "Historical observations are too limited for a stronger directional "
            "forecast."
        )
    return (
        f"Historical {trend.metric.value} movement is classified as "
        f"{trend.direction.value} with {trend.confidence.level.value} confidence."
    )


def _emerging_display_summary(signal: EmergingMarketSignal) -> str:
    if signal.classification is EmergingMarketClassification.INSUFFICIENT_DATA:
        return "Historical observations are insufficient for an emerging-market label."
    if signal.classification is EmergingMarketClassification.RISING:
        return (
            f"{signal.emerging_type.value} is supported by observed movement with "
            f"{signal.confidence.level.value} confidence."
        )
    return (
        f"The emerging-market signal is classified as {signal.classification.value} "
        "from historical movement."
    )


def _warning_display_summary(warning: EarlyWarningSignal) -> str:
    if warning.status is EarlyWarningStatus.INSUFFICIENT_EVIDENCE:
        return "Evidence is too limited for a stronger warning forecast."
    return (
        f"{warning.warning_type.value} is classified as {warning.status.value} "
        f"with {warning.confidence.level.value} confidence."
    )


def _region_entity(region_id: str) -> AffectedEntity:
    return AffectedEntity(
        entity_type=PredictiveEntityType.REGION,
        entity_id=region_id,
        region_id=region_id,
    )


def _entity_label(entity_id: str) -> str:
    return entity_id.replace("_", " ").replace(":", " / ").title()
