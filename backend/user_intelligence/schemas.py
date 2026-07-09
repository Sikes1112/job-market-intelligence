"""API contracts for the Layer 30.1 user intelligence dashboard."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.trust.schemas import (
    ExceptionSubjectStatus,
    ReportRecheckStatus,
    TrustExplanation,
)

WarningSeverity = Literal["info", "warning", "critical"]
NextActionPriority = Literal["low", "medium", "high"]


class _DashboardModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DashboardSummary(_DashboardModel):
    headline: str
    description: str
    warning_count: int = Field(ge=0)
    recommendation_count: int = Field(ge=0)


class RecommendedRegion(_DashboardModel):
    region_id: str
    region_name: str
    score: float | None = None
    confidence: str | None = None
    freshness: str | None = None
    warnings: tuple[str, ...] = Field(default_factory=tuple)
    why_recommended: str
    ranking_influence_allowed: bool | None = None
    trust_tier: str | None = None
    risk_level: str | None = None
    routing_outcome: str | None = None
    ranking_influence_decision: str | None = None
    ranking_influence_reason: str | None = None
    ranking_influence_reason_codes: tuple[str, ...] = Field(default_factory=tuple)
    trust_explanation: TrustExplanation | None = None
    report_recheck_status: ReportRecheckStatus | None = None
    exception_status: ExceptionSubjectStatus | None = None


class RecommendedCompany(_DashboardModel):
    company_id: str
    company_name: str
    score: float | None = None
    confidence: str | None = None
    freshness: str | None = None
    warnings: tuple[str, ...] = Field(default_factory=tuple)
    why_recommended: str
    ranking_influence_allowed: bool | None = None
    trust_tier: str | None = None
    risk_level: str | None = None
    routing_outcome: str | None = None
    ranking_influence_decision: str | None = None
    ranking_influence_reason: str | None = None
    ranking_influence_reason_codes: tuple[str, ...] = Field(default_factory=tuple)
    trust_explanation: TrustExplanation | None = None
    report_recheck_status: ReportRecheckStatus | None = None
    exception_status: ExceptionSubjectStatus | None = None


class RecommendedOpportunity(_DashboardModel):
    opportunity_id: str
    title: str
    company_name: str
    region_name: str | None = None
    trust_label: str | None = None
    review_status: str | None = None
    partner_submitted: bool = False
    ranking_influence_allowed: bool = False
    expiration_state: str | None = None
    source_type: str | None = None
    warnings: tuple[str, ...] = Field(default_factory=tuple)
    why_recommended: str
    trust_tier: str | None = None
    evidence_summary: dict[str, int | str] | None = None
    risk_level: str | None = None
    routing_outcome: str | None = None
    ranking_influence_decision: str | None = None
    ranking_influence_reason: str | None = None
    ranking_influence_reason_codes: tuple[str, ...] = Field(default_factory=tuple)
    trust_explanation: TrustExplanation | None = None
    report_recheck_status: ReportRecheckStatus | None = None
    exception_status: ExceptionSubjectStatus | None = None


class MarketWarning(_DashboardModel):
    warning_code: str
    severity: WarningSeverity
    title: str
    message: str
    subject_type: str
    subject_id: str
    source: str


class ForecastChange(_DashboardModel):
    subject_type: str
    subject_id: str
    title: str
    summary: str
    confidence: str | None = None
    freshness: str | None = None
    warnings: tuple[str, ...] = Field(default_factory=tuple)


class SavedDashboardItem(_DashboardModel):
    item_id: str
    item_type: str
    label: str
    target_route: str | None = None
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class RecommendedNextAction(_DashboardModel):
    action_code: str
    label: str
    description: str
    priority: NextActionPriority
    target_route: str | None = None


class DashboardTrustContext(_DashboardModel):
    uses_existing_metadata_only: bool = True
    layer_30_full_trust_engine_available: bool = False
    message: str


class UserIntelligenceDashboardResponse(_DashboardModel):
    generated_at: datetime
    dashboard_version: Literal["30.1"] = "30.1"
    summary: DashboardSummary
    recommended_regions: tuple[RecommendedRegion, ...] = Field(default_factory=tuple)
    recommended_companies: tuple[RecommendedCompany, ...] = Field(default_factory=tuple)
    recommended_opportunities: tuple[RecommendedOpportunity, ...] = Field(
        default_factory=tuple,
    )
    market_warnings: tuple[MarketWarning, ...] = Field(default_factory=tuple)
    forecast_changes: tuple[ForecastChange, ...] = Field(default_factory=tuple)
    saved_items: tuple[SavedDashboardItem, ...] = Field(default_factory=tuple)
    recommended_next_actions: tuple[RecommendedNextAction, ...] = Field(
        default_factory=tuple,
    )
    trust_context: DashboardTrustContext

    @field_validator("generated_at")
    @classmethod
    def _generated_at_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        return value
