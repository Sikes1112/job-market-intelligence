"""Public-safe contracts for Layer 21A predictive intelligence.

These DTOs are neutral inputs and outputs. They do not own raw source records,
canonical market authority, recommendation authority, geography authority, or
public report authority.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.shared.confidence import Confidence

ForecastDataBasis = Literal[
    "producer_owned_export",
    "public_safe_payload",
    "neutral_contract",
    "test_fixture",
    "mixed",
    "unknown",
]
ForecastUncertaintyLevel = Literal["low", "medium", "high"]
ForecastConfidenceFactorSeverity = Literal["info", "low", "medium", "high"]

_FORBIDDEN_USER_TEXT = (
    "raw_source",
    "raw scrape",
    "source_id",
    "source ids",
    "admin metadata",
    "private metadata",
    "internal-only",
    "guaranteed",
    "guarantee",
)


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class PredictiveEntityType(_Vocabulary):
    REGION = "region"
    COMPANY_REGION = "company_region"
    SECTOR_REGION = "sector_region"


class PredictiveMetric(_Vocabulary):
    COMPANY_EXPANSION = "company_expansion"
    HIRING_ACTIVITY = "hiring_activity"
    INTERNSHIP_DENSITY = "internship_density"
    REGIONAL_SCORE = "regional_score"
    ENTRY_LEVEL_ACCESS = "entry_level_access"
    SECTOR_GROWTH = "sector_growth"
    AI_OPPORTUNITY = "ai_opportunity"
    CLOUD_OPPORTUNITY = "cloud_opportunity"
    CYBERSECURITY_OPPORTUNITY = "cybersecurity_opportunity"
    PRODUCT_OPPORTUNITY = "product_opportunity"
    HIDDEN_OPPORTUNITY = "hidden_opportunity"


class TrendType(_Vocabulary):
    COMPANY_EXPANSION = "company_expansion"
    HIRING_GROWTH = "hiring_growth"
    HIRING_CONTRACTION = "hiring_contraction"
    INTERNSHIP_SEASONALITY = "internship_seasonality"
    REGIONAL_SCORE_MOVEMENT = "regional_score_movement"
    SECTOR_SPECIFIC_GROWTH = "sector_specific_growth"


class TrendDirection(_Vocabulary):
    RISING = "rising"
    STABLE = "stable"
    WEAKENING = "weakening"
    NOISY = "noisy"
    SEASONAL = "seasonal"
    INSUFFICIENT_DATA = "insufficient_data"


class EmergingMarketType(_Vocabulary):
    RISING_AI_MARKET = "rising_ai_market"
    NEW_CLOUD_HUB = "new_cloud_hub"
    CYBERSECURITY_GROWTH_REGION = "cybersecurity_growth_region"
    PRODUCT_ROLE_EXPANSION_REGION = "product_role_expansion_region"
    UNDERPRICED_OPPORTUNITY_MARKET = "underpriced_opportunity_market"


class EmergingMarketClassification(_Vocabulary):
    RISING = "rising"
    STABLE = "stable"
    WEAKENING = "weakening"
    NOISY = "noisy"
    INSUFFICIENT_DATA = "insufficient_data"


class EarlyWarningType(_Vocabulary):
    COMPANY_HIRING_SLOWDOWN = "company_hiring_slowdown"
    REGIONAL_MARKET_WEAKENING = "regional_market_weakening"
    INTERNSHIP_PIPELINE_CONTRACTION = "internship_pipeline_contraction"
    SECTOR_COOLING = "sector_cooling"
    OVERHEATED_MARKET = "overheated_market"


class EarlyWarningStatus(_Vocabulary):
    CONFIRMED_WEAKENING = "confirmed_weakening"
    POSSIBLE_WEAKENING = "possible_weakening"
    OVERHEATING = "overheating"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class WarningSeverity(_Vocabulary):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class HistoricalMetricObservation(BaseModel):
    """Neutral historical point consumed by Layer 21A.

    Producers may build this from append-only history exports, API-safe
    snapshots, public-safe payloads, or tests. It intentionally carries source
    categories and counts only, never source identifiers or raw records.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_type: PredictiveEntityType
    entity_id: str = Field(min_length=1, max_length=128)
    metric: PredictiveMetric
    observed_at: date
    value: float
    region_id: str | None = Field(default=None, min_length=1, max_length=64)
    company_id: str | None = Field(default=None, min_length=1, max_length=64)
    sector_id: str | None = Field(default=None, min_length=1, max_length=64)
    source_categories: tuple[str, ...] = Field(
        default=("historical_snapshot",),
        min_length=1,
        max_length=8,
    )
    source_count: int = Field(default=1, ge=1)
    data_basis: ForecastDataBasis = "neutral_contract"
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    freshness_state: str | None = Field(default=None, min_length=1, max_length=64)
    coverage_tier: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("entity_id", "region_id", "company_id", "sector_id")
    @classmethod
    def _strings_not_blank(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)

    @field_validator("source_categories")
    @classmethod
    def _source_categories_not_blank(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        cleaned = tuple(_clean_text(item) for item in value if item.strip())
        if not cleaned:
            raise ValueError("source_categories must not be empty")
        return cleaned


class ForecastTimeWindow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    start: date
    end: date
    window_days: int = Field(ge=0)

    @model_validator(mode="after")
    def _end_not_before_start(self) -> ForecastTimeWindow:
        if self.end < self.start:
            raise ValueError("time window end must not be before start")
        return self


class HistoricalDepth(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_count: int = Field(ge=0)
    period_count: int = Field(ge=0)
    window_start: date | None = None
    window_end: date | None = None
    window_days: int = Field(default=0, ge=0)
    latest_observed_at: date | None = None

    @model_validator(mode="after")
    def _window_is_ordered(self) -> HistoricalDepth:
        if (
            self.window_start is not None
            and self.window_end is not None
            and self.window_end < self.window_start
        ):
            raise ValueError("historical depth window is not ordered")
        return self


class ForecastSourceBasis(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    data_basis: ForecastDataBasis = "unknown"
    source_categories: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    source_count: int = Field(default=0, ge=0)
    observed_metrics: tuple[PredictiveMetric, ...] = Field(default_factory=tuple)
    coverage_tiers: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    freshness_states: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    notes: tuple[str, ...] = Field(default_factory=tuple, max_length=12)

    @field_validator("source_categories", "coverage_tiers", "freshness_states", "notes")
    @classmethod
    def _tuple_strings_are_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_user_text(item) for item in value if item.strip())


class ForecastConfidenceFactor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1, max_length=96)
    severity: ForecastConfidenceFactorSeverity
    explanation: str = Field(min_length=1, max_length=512)

    @field_validator("code")
    @classmethod
    def _code_not_blank(cls, value: str) -> str:
        return _clean_text(value)

    @field_validator("explanation")
    @classmethod
    def _explanation_safe(cls, value: str) -> str:
        return _safe_user_text(value)


class ForecastConfidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    level: Confidence = Confidence.UNKNOWN
    score: float = Field(ge=0.0, le=1.0)
    factors: tuple[ForecastConfidenceFactor, ...] = Field(default_factory=tuple)


class ForecastUncertainty(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    level: ForecastUncertaintyLevel
    known_uncertainties: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    limitations: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    bounded: bool = True

    @field_validator("known_uncertainties", "limitations")
    @classmethod
    def _uncertainty_text_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_user_text(item) for item in value if item.strip())


class ReasoningStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1, max_length=96)
    summary: str = Field(min_length=1, max_length=512)

    @field_validator("code")
    @classmethod
    def _reasoning_code_not_blank(cls, value: str) -> str:
        return _clean_text(value)

    @field_validator("summary")
    @classmethod
    def _reasoning_summary_safe(cls, value: str) -> str:
        return _safe_user_text(value)


class AffectedEntity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_type: PredictiveEntityType
    entity_id: str = Field(min_length=1, max_length=128)
    region_id: str | None = Field(default=None, min_length=1, max_length=64)
    company_id: str | None = Field(default=None, min_length=1, max_length=64)
    sector_id: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("entity_id", "region_id", "company_id", "sector_id")
    @classmethod
    def _entity_strings_not_blank(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)


class SupportingEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    metric: PredictiveMetric
    observation_count: int = Field(ge=0)
    first_observed_at: date | None = None
    latest_observed_at: date | None = None
    first_value: float | None = None
    latest_value: float | None = None
    net_change: float | None = None
    magnitude: float = Field(ge=0.0)
    positive_intervals: int = Field(ge=0)
    negative_intervals: int = Field(ge=0)
    flat_intervals: int = Field(ge=0)
    peak_value: float | None = None
    trough_value: float | None = None
    evidence_summary: str = Field(min_length=1, max_length=512)

    @field_validator("evidence_summary")
    @classmethod
    def _evidence_summary_safe(cls, value: str) -> str:
        return _safe_user_text(value)


class _PredictivePayloadBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    confidence: ForecastConfidence
    source_basis: ForecastSourceBasis
    historical_depth: HistoricalDepth
    uncertainty: ForecastUncertainty
    reasoning_trail: tuple[ReasoningStep, ...] = Field(min_length=1, max_length=12)


class HistoricalTrendSignal(_PredictivePayloadBase):
    signal_key: str = Field(min_length=1, max_length=256)
    trend_type: TrendType
    entity: AffectedEntity
    metric: PredictiveMetric
    direction: TrendDirection
    magnitude: float = Field(ge=0.0)
    time_window: ForecastTimeWindow
    supporting_evidence: tuple[SupportingEvidence, ...] = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=512)

    @field_validator("signal_key")
    @classmethod
    def _trend_signal_key_not_blank(cls, value: str) -> str:
        return _clean_text(value)

    @field_validator("summary")
    @classmethod
    def _trend_summary_safe(cls, value: str) -> str:
        return _safe_user_text(value)


class EmergingMarketSignal(_PredictivePayloadBase):
    signal_key: str = Field(min_length=1, max_length=256)
    emerging_type: EmergingMarketType
    region_id: str = Field(min_length=1, max_length=64)
    classification: EmergingMarketClassification
    emerging_label: str | None = Field(default=None, min_length=1, max_length=128)
    signal_basis: tuple[SupportingEvidence, ...] = Field(min_length=1)
    opportunity_framing: str = Field(min_length=1, max_length=512)

    @field_validator("signal_key", "region_id", "emerging_label")
    @classmethod
    def _emerging_strings_not_blank(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)

    @field_validator("emerging_label", "opportunity_framing")
    @classmethod
    def _emerging_text_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _safe_user_text(value)


class EarlyWarningSignal(_PredictivePayloadBase):
    signal_key: str = Field(min_length=1, max_length=256)
    warning_type: EarlyWarningType
    status: EarlyWarningStatus
    severity: WarningSeverity
    affected_entity: AffectedEntity
    evidence_basis: tuple[SupportingEvidence, ...] = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=512)

    @field_validator("signal_key")
    @classmethod
    def _warning_signal_key_not_blank(cls, value: str) -> str:
        return _clean_text(value)

    @field_validator("summary")
    @classmethod
    def _warning_summary_safe(cls, value: str) -> str:
        return _safe_user_text(value)


class PredictiveIntelligenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trends: tuple[HistoricalTrendSignal, ...] = Field(default_factory=tuple)
    emerging_markets: tuple[EmergingMarketSignal, ...] = Field(default_factory=tuple)
    warnings: tuple[EarlyWarningSignal, ...] = Field(default_factory=tuple)


class PredictiveReportType(_Vocabulary):
    LABOR_MARKET_FORECAST = "labor_market_forecast"


class PredictiveForecastType(_Vocabulary):
    AI_ROLE_MARKET_GROWTH_12M = "ai_role_market_growth_12m"
    ENTRY_LEVEL_ACCESS_WEAKENING = "entry_level_access_weakening"
    EARLY_CAREER_HIRING_EXPANSION = "early_career_hiring_expansion"
    SECTOR_CONDITION_CHANGE = "sector_condition_change"
    UNDERPRICED_OPPORTUNITY_MARKET = "underpriced_opportunity_market"


class PredictiveSignalKind(_Vocabulary):
    TREND = "trend"
    EMERGING_MARKET = "emerging_market"
    EARLY_WARNING = "early_warning"


class PredictiveSupportingSignal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    signal_key: str = Field(min_length=1, max_length=256)
    signal_kind: PredictiveSignalKind
    signal_type: str = Field(min_length=1, max_length=128)
    signal_status: str = Field(min_length=1, max_length=128)
    summary: str = Field(min_length=1, max_length=512)

    @field_validator("signal_key", "signal_type", "signal_status")
    @classmethod
    def _supporting_signal_strings_not_blank(cls, value: str) -> str:
        return _clean_text(value)

    @field_validator("summary")
    @classmethod
    def _supporting_signal_summary_safe(cls, value: str) -> str:
        return _safe_user_text(value)


class PredictiveReportForecast(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    forecast_id: str = Field(min_length=1, max_length=512)
    forecast_title: str = Field(min_length=1, max_length=256)
    forecast_label: str = Field(min_length=1, max_length=128)
    forecast_type: PredictiveForecastType
    affected_entity: AffectedEntity
    time_horizon: str = Field(min_length=1, max_length=64)
    confidence: ForecastConfidence
    source_basis: ForecastSourceBasis
    historical_depth: HistoricalDepth
    uncertainty: ForecastUncertainty
    reasoning_trail: tuple[ReasoningStep, ...] = Field(min_length=1, max_length=12)
    supporting_signals: tuple[PredictiveSupportingSignal, ...] = Field(min_length=1)
    safe_display_summary: str = Field(min_length=1, max_length=768)
    why_this_forecast_exists: str = Field(min_length=1, max_length=768)

    @field_validator("forecast_id", "time_horizon")
    @classmethod
    def _forecast_identifiers_not_blank(cls, value: str) -> str:
        return _clean_text(value)

    @field_validator(
        "forecast_title",
        "forecast_label",
        "safe_display_summary",
        "why_this_forecast_exists",
    )
    @classmethod
    def _forecast_text_safe(cls, value: str) -> str:
        return _safe_user_text(value)


class PredictiveReportSection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    section_key: str = Field(min_length=1, max_length=96)
    title: str = Field(min_length=1, max_length=256)
    summary: str = Field(min_length=1, max_length=1024)
    why_this_section_exists: str = Field(min_length=1, max_length=1024)
    forecasts: tuple[PredictiveReportForecast, ...] = Field(default_factory=tuple)

    @field_validator("section_key")
    @classmethod
    def _section_key_not_blank(cls, value: str) -> str:
        return _clean_text(value)

    @field_validator("title", "summary", "why_this_section_exists")
    @classmethod
    def _section_text_safe(cls, value: str) -> str:
        return _safe_user_text(value)


class PredictiveReportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    report_id: str = Field(min_length=1, max_length=128)
    report_type: PredictiveReportType = PredictiveReportType.LABOR_MARKET_FORECAST
    title: str = Field(min_length=1, max_length=256)
    generated_at: datetime
    time_horizon: str = Field(min_length=1, max_length=64)
    forecast_disclaimer: str = Field(min_length=1, max_length=512)
    methodology_summary: str = Field(min_length=1, max_length=1024)
    sections: tuple[PredictiveReportSection, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = Field(default_factory=tuple, max_length=12)

    @field_validator("generated_at")
    @classmethod
    def _generated_at_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        return value

    @field_validator("report_id", "time_horizon")
    @classmethod
    def _report_identifiers_not_blank(cls, value: str) -> str:
        return _clean_text(value)

    @field_validator("title", "forecast_disclaimer", "methodology_summary")
    @classmethod
    def _report_text_safe(cls, value: str) -> str:
        return _safe_user_text(value)

    @field_validator("limitations")
    @classmethod
    def _limitations_safe(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_safe_user_text(item) for item in value if item.strip())


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    return _clean_text(value)


def _clean_text(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


def _safe_user_text(value: str) -> str:
    cleaned = _clean_text(value)
    folded = cleaned.casefold()
    for forbidden in _FORBIDDEN_USER_TEXT:
        if forbidden in folded:
            raise ValueError(f"user-facing predictive text includes unsafe term: {forbidden}")
    return cleaned
