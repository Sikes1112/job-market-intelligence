"""Contracts for the Layer 43 My Search workspace projection."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _View(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PursuitOptionView(_View):
    option_id: str
    title: str
    region_id: str | None = None
    public_slug: str | None = None


class PursuitActionView(_View):
    action_id: str
    action_type: str
    status: str
    title: str
    description: str | None = None
    due_at: datetime | None = None
    priority: int | None = None
    completed_at: datetime | None = None
    updated_at: datetime


class PursuitApplicationView(_View):
    application_id: str
    decision_id: str | None
    company_id: str | None
    company_name: str
    region_id: str | None
    market_name: str | None
    role_title: str
    status: str
    applied_at: datetime | None
    follow_up_at: datetime | None
    source_url: str | None
    current_opportunity_id: str | None
    needs_attention: bool
    attention_reason: str | None
    created_at: datetime
    updated_at: datetime


class SourceComparisonView(_View):
    comparison_id: str
    compared_markets: tuple[str, ...]
    system_recommendation: tuple[str, ...]
    original_user_choice: str
    original_choice_matches_recommendation: bool | None
    current_user_choice: str
    current_choice_matches_recommendation: bool | None
    recommendation_state: str
    recommendation_summary: str | None
    generated_at: datetime | None


class OpportunitySummaryView(_View):
    market_id: str | None
    coverage_status: str
    coverage_rationale: str
    coverage_limitations: tuple[str, ...] = ()
    observed_active_count: int = 0
    ranking_eligible_count: int = 0
    fresh_count: int = 0
    latest_observed_at: datetime | None = None
    top_opportunities: tuple[dict[str, Any], ...] = ()


class ActivePursuitView(_View):
    decision_id: str
    decision_type: str
    status: str
    title: str
    selected_priority: PursuitOptionView
    alternatives: tuple[PursuitOptionView, ...]
    target_context: str | None
    prioritized_at: datetime | None
    next_action: PursuitActionView | None
    open_action_count: int
    completed_action_count: int
    applications: tuple[PursuitApplicationView, ...]
    active_application_count: int
    applications_needing_attention: int
    source_comparison: SourceComparisonView | None
    current_opportunities: OpportunitySummaryView
    latest_meaningful_update_at: datetime


class SavedComparisonView(_View):
    comparison_id: str
    market_names: tuple[str, ...]
    context_summary: str
    recommendation_state: str
    recommendation_summary: str
    winner_region_ids: tuple[str, ...]
    generated_at: datetime
    saved_at: datetime


class SavedItemView(_View):
    saved_artifact_id: str
    artifact_type: str
    artifact_ref: str
    label: str | None
    notes: str | None
    region_id: str | None
    public_slug: str | None
    display_name: str | None
    created_at: datetime


class SearchHistoryItemView(_View):
    history_id: str
    kind: str
    title: str
    detail: str | None
    occurred_at: datetime
    decision_id: str | None = None
    application_id: str | None = None


class SearchWorkspaceView(_View):
    active_pursuits: tuple[ActivePursuitView, ...]
    applications: tuple[PursuitApplicationView, ...]
    saved_comparisons: tuple[SavedComparisonView, ...]
    saved_items: tuple[SavedItemView, ...]
    history: tuple[SearchHistoryItemView, ...]
    generated_at: datetime


class TrackOpportunityInitialStatus(StrEnum):
    CONSIDERING = "considering"
    PREPARING = "preparing"


class TrackOpportunityInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str = Field(min_length=1, max_length=64)
    opportunity_id: str = Field(min_length=1, max_length=64)
    initial_status: TrackOpportunityInitialStatus = TrackOpportunityInitialStatus.PREPARING

    @field_validator("decision_id", "opportunity_id")
    @classmethod
    def _clean(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("identifiers must not be blank")
        return cleaned


class TrackOpportunityResult(_View):
    application: PursuitApplicationView
    created: bool
    external_application_url: str | None
