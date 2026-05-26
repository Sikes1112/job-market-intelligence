"""Inert goal-mode weight profiles for future recommendation ranking.

These profiles are inspectable configuration only. They define the component
vocabulary and relative priorities a later deterministic ranking batch can
consume; nothing here scores, ranks, or recommends targets.
"""

from __future__ import annotations

import math
from enum import StrEnum
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.recommendations.models import (
    RecommendationEvidenceBasis,
    RecommendationGoalMode,
    recommendation_goal_mode_definition,
)


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class RecommendationScoreComponent(_Vocabulary):
    ENTRY_LEVEL_ACCESS = "entry_level_access"
    INTERNSHIP_OR_COOP_ACCESS = "internship_or_coop_access"
    PRESTIGE_DENSITY = "prestige_density"
    AI_CLOUD_CONCENTRATION = "ai_cloud_concentration"
    COMPANY_DENSITY = "company_density"
    ROLE_DIVERSITY = "role_diversity"
    LOWER_COMPETITION_PROXY = "lower_competition_proxy"
    GEOGRAPHIC_FLEXIBILITY = "geographic_flexibility"
    MARKET_COVERAGE = "market_coverage"
    CONFIDENCE = "confidence"
    FRESHNESS = "freshness"


class RecommendationComponentAvailability(_Vocabulary):
    REGION_OUTPUT = "region_output"
    COMPANY_OUTPUT = "company_output"
    SEARCH_RESULT = "search_result"
    PERSONALIZATION_PREVIEW = "personalization_preview"
    COVERAGE_METADATA = "coverage_metadata"
    FUTURE_RANKING_INPUT = "future_ranking_input"
    HEURISTIC_PROXY_ONLY = "heuristic_proxy_only"


class GoalModeWeightedComponent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    component: RecommendationScoreComponent
    weight: float = Field(ge=0.0, le=1.0)
    evidence_basis: tuple[RecommendationEvidenceBasis, ...] = Field(min_length=1)
    available_from: tuple[RecommendationComponentAvailability, ...] = Field(
        min_length=1
    )
    is_proxy: bool = False
    requires_heuristic_inference: bool = False
    unavailable_behavior: str = Field(min_length=1, max_length=256)
    warning: str | None = Field(default=None, min_length=1, max_length=256)

    @field_validator("unavailable_behavior", "warning")
    @classmethod
    def _strings_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("goal-mode component strings must not be blank")
        return stripped

    @model_validator(mode="after")
    def _proxy_flags_must_match_basis(self) -> GoalModeWeightedComponent:
        if self.requires_heuristic_inference and (
            RecommendationEvidenceBasis.HEURISTIC_INFERENCE not in self.evidence_basis
        ):
            raise ValueError(
                "heuristic goal-mode components must declare heuristic_inference basis"
            )
        if (
            RecommendationEvidenceBasis.HEURISTIC_INFERENCE in self.evidence_basis
            and not self.is_proxy
        ):
            raise ValueError("heuristic goal-mode components must be marked proxy")
        if (
            RecommendationEvidenceBasis.HEURISTIC_INFERENCE in self.evidence_basis
            and not self.requires_heuristic_inference
        ):
            raise ValueError("heuristic goal-mode components must require inference")
        return self


class GoalModePenaltyComponent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    component: RecommendationScoreComponent
    weight: float = Field(ge=0.0, le=1.0)
    evidence_basis: tuple[RecommendationEvidenceBasis, ...] = Field(min_length=1)
    is_proxy: bool = False
    requires_heuristic_inference: bool = False
    explanation: str = Field(min_length=1, max_length=256)
    unavailable_behavior: str = Field(min_length=1, max_length=256)

    @field_validator("explanation", "unavailable_behavior")
    @classmethod
    def _strings_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("goal-mode penalty strings must not be blank")
        return stripped

    @model_validator(mode="after")
    def _proxy_flags_must_match_basis(self) -> GoalModePenaltyComponent:
        if self.requires_heuristic_inference and (
            RecommendationEvidenceBasis.HEURISTIC_INFERENCE not in self.evidence_basis
        ):
            raise ValueError(
                "heuristic goal-mode penalties must declare heuristic_inference basis"
            )
        if (
            RecommendationEvidenceBasis.HEURISTIC_INFERENCE in self.evidence_basis
            and not self.is_proxy
        ):
            raise ValueError("heuristic goal-mode penalties must be marked proxy")
        if (
            RecommendationEvidenceBasis.HEURISTIC_INFERENCE in self.evidence_basis
            and not self.requires_heuristic_inference
        ):
            raise ValueError("heuristic goal-mode penalties must require inference")
        return self


class GoalModeWeightProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    goal_mode: RecommendationGoalMode
    label: str = Field(min_length=1, max_length=96)
    description: str = Field(min_length=1, max_length=256)
    prioritization_summary: str = Field(min_length=1, max_length=512)
    weighted_components: tuple[GoalModeWeightedComponent, ...] = Field(min_length=1)
    penalty_components: tuple[GoalModePenaltyComponent, ...] = Field(
        default_factory=tuple
    )
    missing_data_behavior: str = Field(min_length=1, max_length=512)
    warnings: tuple[str, ...] = Field(default_factory=tuple, max_length=12)

    @field_validator(
        "label",
        "description",
        "prioritization_summary",
        "missing_data_behavior",
    )
    @classmethod
    def _strings_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("goal-mode profile strings must not be blank")
        return stripped

    @field_validator("warnings")
    @classmethod
    def _warnings_not_blank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        cleaned: list[str] = []
        for item in value:
            stripped = item.strip()
            if not stripped:
                raise ValueError("goal-mode profile warnings must not be blank")
            cleaned.append(stripped)
        return tuple(cleaned)

    @model_validator(mode="after")
    def _profile_must_be_coherent(self) -> GoalModeWeightProfile:
        definition = recommendation_goal_mode_definition(self.goal_mode)
        if self.label != definition.label or self.description != definition.description:
            raise ValueError("goal-mode profile metadata must match canonical goal mode")
        weight_total = sum(component.weight for component in self.weighted_components)
        if not math.isclose(weight_total, 1.0, abs_tol=1e-9):
            raise ValueError(f"goal-mode profile weights must sum to 1.0, got {weight_total}")
        components = [component.component for component in self.weighted_components]
        if len(components) != len(set(components)):
            raise ValueError("goal-mode profile weighted components must be unique")
        penalty_components = [component.component for component in self.penalty_components]
        if len(penalty_components) != len(set(penalty_components)):
            raise ValueError("goal-mode profile penalty components must be unique")
        return self


def _component(
    component: RecommendationScoreComponent,
    weight: float,
    *,
    basis: tuple[RecommendationEvidenceBasis, ...],
    available_from: tuple[RecommendationComponentAvailability, ...],
    is_proxy: bool = False,
    requires_heuristic_inference: bool = False,
    unavailable_behavior: str = (
        "Treat as unavailable and surface a missing-data weakness; do not impute."
    ),
    warning: str | None = None,
) -> GoalModeWeightedComponent:
    return GoalModeWeightedComponent(
        component=component,
        weight=weight,
        evidence_basis=basis,
        available_from=available_from,
        is_proxy=is_proxy,
        requires_heuristic_inference=requires_heuristic_inference,
        unavailable_behavior=unavailable_behavior,
        warning=warning,
    )


def _penalty(
    component: RecommendationScoreComponent,
    weight: float,
    *,
    basis: tuple[RecommendationEvidenceBasis, ...],
    explanation: str,
    unavailable_behavior: str = "Do not apply this penalty when the component is missing.",
    is_proxy: bool = False,
    requires_heuristic_inference: bool = False,
) -> GoalModePenaltyComponent:
    return GoalModePenaltyComponent(
        component=component,
        weight=weight,
        evidence_basis=basis,
        explanation=explanation,
        unavailable_behavior=unavailable_behavior,
        is_proxy=is_proxy,
        requires_heuristic_inference=requires_heuristic_inference,
    )


def _definition_kwargs(goal_mode: RecommendationGoalMode) -> dict[str, object]:
    definition = recommendation_goal_mode_definition(goal_mode)
    return {
        "goal_mode": definition.goal_mode,
        "label": definition.label,
        "description": definition.description,
    }


_STRUCTURED_SCORE = (RecommendationEvidenceBasis.STRUCTURED_SCORE,)
_COVERAGE = (RecommendationEvidenceBasis.MARKET_COVERAGE,)
_COMPANY_METADATA = (RecommendationEvidenceBasis.COMPANY_METADATA,)
_REGION_METADATA = (RecommendationEvidenceBasis.REGION_METADATA,)
_CONFIDENCE = (RecommendationEvidenceBasis.CONFIDENCE,)
_FRESHNESS = (RecommendationEvidenceBasis.FRESHNESS,)
_HEURISTIC = (RecommendationEvidenceBasis.HEURISTIC_INFERENCE,)

_REGION_AND_COVERAGE = (
    RecommendationComponentAvailability.REGION_OUTPUT,
    RecommendationComponentAvailability.COVERAGE_METADATA,
)
_COMPANY_AND_SEARCH = (
    RecommendationComponentAvailability.COMPANY_OUTPUT,
    RecommendationComponentAvailability.SEARCH_RESULT,
)
_FUTURE_PROXY = (
    RecommendationComponentAvailability.FUTURE_RANKING_INPUT,
    RecommendationComponentAvailability.HEURISTIC_PROXY_ONLY,
)


_GOAL_MODE_WEIGHT_PROFILES: dict[RecommendationGoalMode, GoalModeWeightProfile] = {
    RecommendationGoalMode.MAXIMIZE_ENTRY_LEVEL_ACCESS: GoalModeWeightProfile(
        **_definition_kwargs(RecommendationGoalMode.MAXIMIZE_ENTRY_LEVEL_ACCESS),
        prioritization_summary=(
            "Prioritizes app-owned early-career accessibility score fields, "
            "internship/co-op signals, and enough coverage/freshness to trust them."
        ),
        weighted_components=(
            _component(
                RecommendationScoreComponent.ENTRY_LEVEL_ACCESS,
                0.42,
                basis=_STRUCTURED_SCORE,
                available_from=_REGION_AND_COVERAGE + _COMPANY_AND_SEARCH,
            ),
            _component(
                RecommendationScoreComponent.INTERNSHIP_OR_COOP_ACCESS,
                0.22,
                basis=_STRUCTURED_SCORE,
                available_from=_REGION_AND_COVERAGE + _COMPANY_AND_SEARCH,
            ),
            _component(
                RecommendationScoreComponent.COMPANY_DENSITY,
                0.12,
                basis=_STRUCTURED_SCORE + _REGION_METADATA,
                available_from=_REGION_AND_COVERAGE,
            ),
            _component(
                RecommendationScoreComponent.MARKET_COVERAGE,
                0.12,
                basis=_COVERAGE,
                available_from=(RecommendationComponentAvailability.COVERAGE_METADATA,),
            ),
            _component(
                RecommendationScoreComponent.CONFIDENCE,
                0.06,
                basis=_CONFIDENCE + _COVERAGE,
                available_from=_REGION_AND_COVERAGE + _COMPANY_AND_SEARCH,
            ),
            _component(
                RecommendationScoreComponent.FRESHNESS,
                0.06,
                basis=_FRESHNESS,
                available_from=_REGION_AND_COVERAGE + _COMPANY_AND_SEARCH,
            ),
        ),
        penalty_components=(
            _penalty(
                RecommendationScoreComponent.PRESTIGE_DENSITY,
                0.08,
                basis=_COMPANY_METADATA,
                explanation="High prestige can indicate harder entry-level access.",
                is_proxy=True,
            ),
        ),
        missing_data_behavior=(
            "Missing entry-level or internship/co-op inputs must become weaknesses "
            "and manual verification items, not zero-valued facts."
        ),
    ),
    RecommendationGoalMode.MAXIMIZE_PRESTIGE: GoalModeWeightProfile(
        **_definition_kwargs(RecommendationGoalMode.MAXIMIZE_PRESTIGE),
        prioritization_summary=(
            "Prioritizes company prestige metadata, major-tech/Mag 7 density, "
            "and score fields already owned by the app."
        ),
        weighted_components=(
            _component(
                RecommendationScoreComponent.PRESTIGE_DENSITY,
                0.44,
                basis=_COMPANY_METADATA + _STRUCTURED_SCORE,
                available_from=_REGION_AND_COVERAGE + _COMPANY_AND_SEARCH,
            ),
            _component(
                RecommendationScoreComponent.COMPANY_DENSITY,
                0.18,
                basis=_STRUCTURED_SCORE + _REGION_METADATA,
                available_from=_REGION_AND_COVERAGE,
            ),
            _component(
                RecommendationScoreComponent.AI_CLOUD_CONCENTRATION,
                0.12,
                basis=_COMPANY_METADATA + _COVERAGE,
                available_from=_REGION_AND_COVERAGE + _COMPANY_AND_SEARCH,
                is_proxy=True,
                warning="Sector metadata is a concentration proxy until ranking has richer inputs.",
            ),
            _component(
                RecommendationScoreComponent.MARKET_COVERAGE,
                0.12,
                basis=_COVERAGE,
                available_from=(RecommendationComponentAvailability.COVERAGE_METADATA,),
            ),
            _component(
                RecommendationScoreComponent.CONFIDENCE,
                0.08,
                basis=_CONFIDENCE + _COVERAGE,
                available_from=_REGION_AND_COVERAGE + _COMPANY_AND_SEARCH,
            ),
            _component(
                RecommendationScoreComponent.FRESHNESS,
                0.06,
                basis=_FRESHNESS,
                available_from=_REGION_AND_COVERAGE + _COMPANY_AND_SEARCH,
            ),
        ),
        penalty_components=(
            _penalty(
                RecommendationScoreComponent.ENTRY_LEVEL_ACCESS,
                0.08,
                basis=_STRUCTURED_SCORE,
                explanation="Prestige-heavy targets may have weaker early-career access.",
                is_proxy=True,
            ),
        ),
        missing_data_behavior=(
            "Missing prestige metadata should be disclosed as missing company metadata "
            "instead of inferred from brand text."
        ),
    ),
    RecommendationGoalMode.MAXIMIZE_AI_CLOUD_CONCENTRATION: GoalModeWeightProfile(
        **_definition_kwargs(
            RecommendationGoalMode.MAXIMIZE_AI_CLOUD_CONCENTRATION
        ),
        prioritization_summary=(
            "Prioritizes AI/cloud sector metadata and sector coverage while keeping "
            "coverage, confidence, and freshness visible."
        ),
        weighted_components=(
            _component(
                RecommendationScoreComponent.AI_CLOUD_CONCENTRATION,
                0.46,
                basis=_COMPANY_METADATA + _COVERAGE,
                available_from=_REGION_AND_COVERAGE + _COMPANY_AND_SEARCH,
                is_proxy=True,
                warning="Current AI/cloud concentration is derived from sector metadata proxies.",
            ),
            _component(
                RecommendationScoreComponent.ROLE_DIVERSITY,
                0.14,
                basis=_STRUCTURED_SCORE,
                available_from=(
                    RecommendationComponentAvailability.SEARCH_RESULT,
                    RecommendationComponentAvailability.PERSONALIZATION_PREVIEW,
                ),
                is_proxy=True,
                warning="Role diversity is limited where role-family summaries are absent.",
            ),
            _component(
                RecommendationScoreComponent.COMPANY_DENSITY,
                0.12,
                basis=_REGION_METADATA + _STRUCTURED_SCORE,
                available_from=_REGION_AND_COVERAGE,
            ),
            _component(
                RecommendationScoreComponent.MARKET_COVERAGE,
                0.12,
                basis=_COVERAGE,
                available_from=(RecommendationComponentAvailability.COVERAGE_METADATA,),
            ),
            _component(
                RecommendationScoreComponent.CONFIDENCE,
                0.08,
                basis=_CONFIDENCE + _COVERAGE,
                available_from=_REGION_AND_COVERAGE + _COMPANY_AND_SEARCH,
            ),
            _component(
                RecommendationScoreComponent.FRESHNESS,
                0.08,
                basis=_FRESHNESS,
                available_from=_REGION_AND_COVERAGE + _COMPANY_AND_SEARCH,
            ),
        ),
        penalty_components=(
            _penalty(
                RecommendationScoreComponent.COMPANY_DENSITY,
                0.06,
                basis=_REGION_METADATA,
                explanation="Narrow company universes can make concentration less actionable.",
                is_proxy=True,
            ),
        ),
        missing_data_behavior=(
            "Missing sector or sector-coverage inputs must be surfaced as weak AI/cloud "
            "evidence, not converted into a concentration score."
        ),
        warnings=("AI/cloud concentration is currently a proxy component.",),
    ),
    RecommendationGoalMode.MAXIMIZE_UNDERRATED_MARKETS: GoalModeWeightProfile(
        **_definition_kwargs(RecommendationGoalMode.MAXIMIZE_UNDERRATED_MARKETS),
        prioritization_summary=(
            "Prioritizes useful coverage, company density, and lower-prestige / "
            "lower-competition proxies without treating them as objective truth."
        ),
        weighted_components=(
            _component(
                RecommendationScoreComponent.COMPANY_DENSITY,
                0.22,
                basis=_REGION_METADATA + _STRUCTURED_SCORE,
                available_from=_REGION_AND_COVERAGE,
            ),
            _component(
                RecommendationScoreComponent.LOWER_COMPETITION_PROXY,
                0.22,
                basis=_HEURISTIC,
                available_from=_FUTURE_PROXY,
                is_proxy=True,
                requires_heuristic_inference=True,
                warning="Lower competition is not directly observed in current app data.",
            ),
            _component(
                RecommendationScoreComponent.ENTRY_LEVEL_ACCESS,
                0.18,
                basis=_STRUCTURED_SCORE,
                available_from=_REGION_AND_COVERAGE + _COMPANY_AND_SEARCH,
            ),
            _component(
                RecommendationScoreComponent.MARKET_COVERAGE,
                0.16,
                basis=_COVERAGE,
                available_from=(RecommendationComponentAvailability.COVERAGE_METADATA,),
            ),
            _component(
                RecommendationScoreComponent.CONFIDENCE,
                0.12,
                basis=_CONFIDENCE + _COVERAGE,
                available_from=_REGION_AND_COVERAGE + _COMPANY_AND_SEARCH,
            ),
            _component(
                RecommendationScoreComponent.FRESHNESS,
                0.10,
                basis=_FRESHNESS,
                available_from=_REGION_AND_COVERAGE + _COMPANY_AND_SEARCH,
            ),
        ),
        penalty_components=(
            _penalty(
                RecommendationScoreComponent.PRESTIGE_DENSITY,
                0.12,
                basis=_COMPANY_METADATA + _HEURISTIC,
                explanation="Obvious prestige density can weaken an underrated-market thesis.",
                is_proxy=True,
                requires_heuristic_inference=True,
            ),
        ),
        missing_data_behavior=(
            "Underrated-market claims require explicit heuristic labeling and should "
            "fall back to manual verification when proxy inputs are unavailable."
        ),
        warnings=("Underrated-market scoring is proxy-heavy by design.",),
    ),
    RecommendationGoalMode.MAXIMIZE_INTERNSHIP_COOP_ACCESS: GoalModeWeightProfile(
        **_definition_kwargs(
            RecommendationGoalMode.MAXIMIZE_INTERNSHIP_COOP_ACCESS
        ),
        prioritization_summary=(
            "Prioritizes internship and co-op counts/signals, then entry-level access "
            "and enough freshness to trust seasonal signals."
        ),
        weighted_components=(
            _component(
                RecommendationScoreComponent.INTERNSHIP_OR_COOP_ACCESS,
                0.44,
                basis=_STRUCTURED_SCORE,
                available_from=_REGION_AND_COVERAGE + _COMPANY_AND_SEARCH,
            ),
            _component(
                RecommendationScoreComponent.ENTRY_LEVEL_ACCESS,
                0.22,
                basis=_STRUCTURED_SCORE,
                available_from=_REGION_AND_COVERAGE + _COMPANY_AND_SEARCH,
            ),
            _component(
                RecommendationScoreComponent.COMPANY_DENSITY,
                0.10,
                basis=_REGION_METADATA + _STRUCTURED_SCORE,
                available_from=_REGION_AND_COVERAGE,
            ),
            _component(
                RecommendationScoreComponent.FRESHNESS,
                0.10,
                basis=_FRESHNESS,
                available_from=_REGION_AND_COVERAGE + _COMPANY_AND_SEARCH,
            ),
            _component(
                RecommendationScoreComponent.MARKET_COVERAGE,
                0.08,
                basis=_COVERAGE,
                available_from=(RecommendationComponentAvailability.COVERAGE_METADATA,),
            ),
            _component(
                RecommendationScoreComponent.CONFIDENCE,
                0.06,
                basis=_CONFIDENCE + _COVERAGE,
                available_from=_REGION_AND_COVERAGE + _COMPANY_AND_SEARCH,
            ),
        ),
        penalty_components=(),
        missing_data_behavior=(
            "Missing internship/co-op counts must trigger manual verification because "
            "these signals can be seasonal and stale."
        ),
    ),
    RecommendationGoalMode.MAXIMIZE_LOWER_COMPETITION: GoalModeWeightProfile(
        **_definition_kwargs(RecommendationGoalMode.MAXIMIZE_LOWER_COMPETITION),
        prioritization_summary=(
            "Prioritizes explicit lower-competition proxies while preserving warnings "
            "that current app data does not directly measure applicant competition."
        ),
        weighted_components=(
            _component(
                RecommendationScoreComponent.LOWER_COMPETITION_PROXY,
                0.40,
                basis=_HEURISTIC,
                available_from=_FUTURE_PROXY,
                is_proxy=True,
                requires_heuristic_inference=True,
                warning="Competition is not directly measured; this component is heuristic.",
            ),
            _component(
                RecommendationScoreComponent.COMPANY_DENSITY,
                0.16,
                basis=_REGION_METADATA + _STRUCTURED_SCORE,
                available_from=_REGION_AND_COVERAGE,
            ),
            _component(
                RecommendationScoreComponent.ENTRY_LEVEL_ACCESS,
                0.14,
                basis=_STRUCTURED_SCORE,
                available_from=_REGION_AND_COVERAGE + _COMPANY_AND_SEARCH,
            ),
            _component(
                RecommendationScoreComponent.MARKET_COVERAGE,
                0.12,
                basis=_COVERAGE,
                available_from=(RecommendationComponentAvailability.COVERAGE_METADATA,),
            ),
            _component(
                RecommendationScoreComponent.CONFIDENCE,
                0.10,
                basis=_CONFIDENCE + _COVERAGE,
                available_from=_REGION_AND_COVERAGE + _COMPANY_AND_SEARCH,
            ),
            _component(
                RecommendationScoreComponent.FRESHNESS,
                0.08,
                basis=_FRESHNESS,
                available_from=_REGION_AND_COVERAGE + _COMPANY_AND_SEARCH,
            ),
        ),
        penalty_components=(
            _penalty(
                RecommendationScoreComponent.PRESTIGE_DENSITY,
                0.10,
                basis=_COMPANY_METADATA + _HEURISTIC,
                explanation="Prestige density can be a proxy for higher competition.",
                is_proxy=True,
                requires_heuristic_inference=True,
            ),
        ),
        missing_data_behavior=(
            "When lower-competition proxies are unavailable, the later ranking layer "
            "must emit an inferred/missing-data warning instead of a competition claim."
        ),
        warnings=("Lower competition is heuristic until direct competition data exists.",),
    ),
    RecommendationGoalMode.MAXIMIZE_GEOGRAPHIC_FLEXIBILITY: GoalModeWeightProfile(
        **_definition_kwargs(
            RecommendationGoalMode.MAXIMIZE_GEOGRAPHIC_FLEXIBILITY
        ),
        prioritization_summary=(
            "Prioritizes company-region breadth, region coverage, and freshness so "
            "later ranking can prefer targets with more location optionality."
        ),
        weighted_components=(
            _component(
                RecommendationScoreComponent.GEOGRAPHIC_FLEXIBILITY,
                0.34,
                basis=_REGION_METADATA + _COMPANY_METADATA,
                available_from=_COMPANY_AND_SEARCH,
                is_proxy=True,
                warning="Flexibility is currently inferred from region breadth, not policy.",
            ),
            _component(
                RecommendationScoreComponent.COMPANY_DENSITY,
                0.18,
                basis=_REGION_METADATA + _STRUCTURED_SCORE,
                available_from=_REGION_AND_COVERAGE,
            ),
            _component(
                RecommendationScoreComponent.MARKET_COVERAGE,
                0.18,
                basis=_COVERAGE,
                available_from=(RecommendationComponentAvailability.COVERAGE_METADATA,),
            ),
            _component(
                RecommendationScoreComponent.ROLE_DIVERSITY,
                0.10,
                basis=_STRUCTURED_SCORE,
                available_from=(
                    RecommendationComponentAvailability.SEARCH_RESULT,
                    RecommendationComponentAvailability.PERSONALIZATION_PREVIEW,
                ),
                is_proxy=True,
            ),
            _component(
                RecommendationScoreComponent.CONFIDENCE,
                0.10,
                basis=_CONFIDENCE + _COVERAGE,
                available_from=_REGION_AND_COVERAGE + _COMPANY_AND_SEARCH,
            ),
            _component(
                RecommendationScoreComponent.FRESHNESS,
                0.10,
                basis=_FRESHNESS,
                available_from=_REGION_AND_COVERAGE + _COMPANY_AND_SEARCH,
            ),
        ),
        penalty_components=(
            _penalty(
                RecommendationScoreComponent.GEOGRAPHIC_FLEXIBILITY,
                0.12,
                basis=_HEURISTIC,
                explanation="Location requirements are not directly represented.",
                unavailable_behavior=(
                    "Always add manual verification for location requirements."
                ),
                is_proxy=True,
                requires_heuristic_inference=True,
            ),
        ),
        missing_data_behavior=(
            "Missing region breadth or location policy data must become a manual "
            "verification item, not a flexibility score."
        ),
        warnings=("Geographic flexibility is a proxy until location-policy data exists.",),
    ),
}

GOAL_MODE_WEIGHT_PROFILES = MappingProxyType(_GOAL_MODE_WEIGHT_PROFILES)


def goal_mode_weight_profiles() -> tuple[GoalModeWeightProfile, ...]:
    return tuple(GOAL_MODE_WEIGHT_PROFILES[mode] for mode in RecommendationGoalMode)


def goal_mode_weight_profile(
    goal_mode: RecommendationGoalMode | str,
) -> GoalModeWeightProfile:
    return GOAL_MODE_WEIGHT_PROFILES[RecommendationGoalMode(goal_mode)]
