from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.recommendations.goal_modes import (
    GoalModeWeightedComponent,
    GoalModeWeightProfile,
    RecommendationComponentAvailability,
    RecommendationScoreComponent,
    goal_mode_weight_profile,
    goal_mode_weight_profiles,
)
from backend.recommendations.models import (
    RecommendationEvidenceBasis,
    RecommendationGoalMode,
    recommendation_goal_mode_definition,
)


def test_every_goal_mode_has_exactly_one_profile() -> None:
    profiles = goal_mode_weight_profiles()

    assert len(profiles) == len(RecommendationGoalMode)
    assert {profile.goal_mode for profile in profiles} == set(RecommendationGoalMode)
    assert len({profile.goal_mode for profile in profiles}) == len(profiles)


def test_profiles_use_canonical_metadata_and_known_components() -> None:
    known_components = set(RecommendationScoreComponent)

    for profile in goal_mode_weight_profiles():
        definition = recommendation_goal_mode_definition(profile.goal_mode)
        assert profile.label == definition.label
        assert profile.description == definition.description
        assert profile.prioritization_summary
        assert profile.missing_data_behavior
        assert {component.component for component in profile.weighted_components} <= (
            known_components
        )


def test_profile_weights_are_bounded_and_sum_to_one() -> None:
    for profile in goal_mode_weight_profiles():
        total = sum(component.weight for component in profile.weighted_components)
        assert total == pytest.approx(1.0)
        assert all(0 <= component.weight <= 1 for component in profile.weighted_components)
        assert all(0 <= component.weight <= 1 for component in profile.penalty_components)


def test_penalties_and_proxy_components_are_explicit() -> None:
    profiles = goal_mode_weight_profiles()

    assert any(profile.penalty_components for profile in profiles)
    for profile in profiles:
        for penalty in profile.penalty_components:
            assert penalty.explanation
            assert penalty.unavailable_behavior
        for component in profile.weighted_components:
            if RecommendationEvidenceBasis.HEURISTIC_INFERENCE in component.evidence_basis:
                assert component.is_proxy is True
                assert component.requires_heuristic_inference is True
                assert component.warning


def test_profiles_are_deterministic_and_importable_by_goal_mode() -> None:
    first = [profile.model_dump(mode="json") for profile in goal_mode_weight_profiles()]
    second = [profile.model_dump(mode="json") for profile in goal_mode_weight_profiles()]

    assert first == second
    assert (
        goal_mode_weight_profile("maximize_entry_level_access").goal_mode
        is RecommendationGoalMode.MAXIMIZE_ENTRY_LEVEL_ACCESS
    )


def test_profile_validation_rejects_bad_weights_unknown_goal_and_bad_proxy() -> None:
    definition = recommendation_goal_mode_definition(
        RecommendationGoalMode.MAXIMIZE_ENTRY_LEVEL_ACCESS
    )
    component = GoalModeWeightedComponent(
        component=RecommendationScoreComponent.ENTRY_LEVEL_ACCESS,
        weight=0.5,
        evidence_basis=(RecommendationEvidenceBasis.STRUCTURED_SCORE,),
        available_from=(RecommendationComponentAvailability.REGION_OUTPUT,),
        unavailable_behavior="Do not impute missing data.",
    )

    with pytest.raises(ValidationError):
        GoalModeWeightProfile(
            goal_mode=RecommendationGoalMode.MAXIMIZE_ENTRY_LEVEL_ACCESS,
            label=definition.label,
            description=definition.description,
            prioritization_summary="bad total",
            weighted_components=(component,),
            missing_data_behavior="missing data stays missing",
        )

    with pytest.raises(ValidationError):
        GoalModeWeightProfile(
            goal_mode="unknown_goal",
            label=definition.label,
            description=definition.description,
            prioritization_summary="bad goal",
            weighted_components=(
                component.model_copy(update={"weight": 1.0}),
            ),
            missing_data_behavior="missing data stays missing",
        )

    with pytest.raises(ValidationError):
        GoalModeWeightedComponent(
            component=RecommendationScoreComponent.LOWER_COMPETITION_PROXY,
            weight=1.0,
            evidence_basis=(RecommendationEvidenceBasis.HEURISTIC_INFERENCE,),
            available_from=(RecommendationComponentAvailability.HEURISTIC_PROXY_ONLY,),
            is_proxy=False,
            requires_heuristic_inference=True,
            unavailable_behavior="Do not impute missing data.",
        )
