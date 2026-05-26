"""API-facing DTOs for Layer 14 recommendation outputs.

The DTO layer keeps recommendation API responses structured and serializable
without turning explanations or strategy guidance into prose-only summaries.
It wraps Layer 14A-D contracts and exposes goal-mode profile metadata in an
API-safe shape.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from backend.recommendations.goal_modes import (
    GoalModePenaltyComponent,
    GoalModeWeightedComponent,
    GoalModeWeightProfile,
    RecommendationScoreComponent,
    goal_mode_weight_profile,
    goal_mode_weight_profiles,
)
from backend.recommendations.models import (
    RecommendationEvidenceBasis,
    RecommendationGoalMode,
)
from backend.recommendations.ranking import (
    RecommendationRankingItem,
    RecommendationRankingResult,
)
from backend.recommendations.strategy import MarketStrategyPlan


class RecommendationGoalModeComponentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    component: RecommendationScoreComponent
    weight: float = Field(ge=0.0, le=1.0)
    evidence_basis: tuple[RecommendationEvidenceBasis, ...] = Field(min_length=1)
    is_proxy: bool = False
    requires_heuristic_inference: bool = False
    unavailable_behavior: str = Field(min_length=1, max_length=512)
    warning: str | None = Field(default=None, min_length=1, max_length=512)
    penalty_explanation: str | None = Field(default=None, min_length=1, max_length=512)


class RecommendationGoalModeProfilePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    goal_mode: RecommendationGoalMode
    label: str = Field(min_length=1, max_length=96)
    description: str = Field(min_length=1, max_length=256)
    prioritization_summary: str = Field(min_length=1, max_length=512)
    weighted_components: tuple[RecommendationGoalModeComponentPayload, ...] = Field(
        min_length=1
    )
    penalty_components: tuple[RecommendationGoalModeComponentPayload, ...] = Field(
        default_factory=tuple
    )
    missing_data_behavior: str = Field(min_length=1, max_length=512)
    warnings: tuple[str, ...] = Field(default_factory=tuple, max_length=12)


class RecommendationGoalModesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    goal_modes: tuple[RecommendationGoalModeProfilePayload, ...] = Field(min_length=1)


class RecommendationStrategyRequest(BaseModel):
    """Request contract for deterministic recommendation strategy generation."""

    model_config = ConfigDict(extra="forbid")

    goal_mode: RecommendationGoalMode
    include_company_recommendations: bool = True
    region_limit: int = Field(default=25, ge=1, le=100)
    company_limit: int = Field(default=25, ge=0, le=100)
    max_primary_regions: int = Field(default=3, ge=1, le=10)
    max_secondary_regions: int = Field(default=3, ge=0, le=10)
    max_fallback_regions: int = Field(default=3, ge=0, le=10)
    max_watchlist_items: int = Field(default=6, ge=0, le=25)
    max_company_targets: int = Field(default=5, ge=0, le=25)


class RecommendationStrategyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    available_goal_modes: tuple[RecommendationGoalModeProfilePayload, ...] = Field(
        min_length=1
    )
    selected_goal_mode: RecommendationGoalModeProfilePayload
    ranking_profile_version: str = Field(min_length=1, max_length=128)
    ranking_tie_breaker: str = Field(min_length=1, max_length=256)
    ranked_region_recommendations: tuple[RecommendationRankingItem, ...]
    ranked_company_recommendations: tuple[RecommendationRankingItem, ...] = Field(
        default_factory=tuple
    )
    market_strategy_plan: MarketStrategyPlan
    warnings: tuple[str, ...] = Field(default_factory=tuple, max_length=50)


def recommendation_goal_modes_payload() -> RecommendationGoalModesPayload:
    return RecommendationGoalModesPayload(
        goal_modes=tuple(
            _profile_payload(profile) for profile in goal_mode_weight_profiles()
        )
    )


def recommendation_strategy_payload(
    *,
    region_rankings: RecommendationRankingResult,
    strategy_plan: MarketStrategyPlan,
    company_rankings: RecommendationRankingResult | None = None,
    warnings: tuple[str, ...] = (),
) -> RecommendationStrategyPayload:
    selected_profile = goal_mode_weight_profile(region_rankings.goal_mode)
    return RecommendationStrategyPayload(
        available_goal_modes=recommendation_goal_modes_payload().goal_modes,
        selected_goal_mode=_profile_payload(selected_profile),
        ranking_profile_version=region_rankings.profile_version,
        ranking_tie_breaker=region_rankings.tie_breaker,
        ranked_region_recommendations=region_rankings.ranked_recommendations,
        ranked_company_recommendations=(
            company_rankings.ranked_recommendations if company_rankings else ()
        ),
        market_strategy_plan=strategy_plan,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _profile_payload(profile: GoalModeWeightProfile) -> RecommendationGoalModeProfilePayload:
    return RecommendationGoalModeProfilePayload(
        goal_mode=profile.goal_mode,
        label=profile.label,
        description=profile.description,
        prioritization_summary=profile.prioritization_summary,
        weighted_components=tuple(
            _weighted_component_payload(component)
            for component in profile.weighted_components
        ),
        penalty_components=tuple(
            _penalty_component_payload(component)
            for component in profile.penalty_components
        ),
        missing_data_behavior=profile.missing_data_behavior,
        warnings=profile.warnings,
    )


def _weighted_component_payload(
    component: GoalModeWeightedComponent,
) -> RecommendationGoalModeComponentPayload:
    return RecommendationGoalModeComponentPayload(
        component=component.component,
        weight=component.weight,
        evidence_basis=component.evidence_basis,
        is_proxy=component.is_proxy,
        requires_heuristic_inference=component.requires_heuristic_inference,
        unavailable_behavior=component.unavailable_behavior,
        warning=component.warning,
    )


def _penalty_component_payload(
    component: GoalModePenaltyComponent,
) -> RecommendationGoalModeComponentPayload:
    return RecommendationGoalModeComponentPayload(
        component=component.component,
        weight=component.weight,
        evidence_basis=component.evidence_basis,
        is_proxy=component.is_proxy,
        requires_heuristic_inference=component.requires_heuristic_inference,
        unavailable_behavior=component.unavailable_behavior,
        penalty_explanation=component.explanation,
    )
