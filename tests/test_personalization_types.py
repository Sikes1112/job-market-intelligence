from backend.personalization.types import CareerStage, PreferenceLevel


def test_career_stage_values_match_mvp_scope() -> None:
    # MVP V1 is early-career-weighted; only entry_level is in scope.
    assert CareerStage.values() == {"entry_level"}


def test_preference_level_values() -> None:
    assert PreferenceLevel.values() == {"low", "medium", "high"}
