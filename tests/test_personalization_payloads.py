import pytest
from pydantic import ValidationError

from backend.personalization.payloads import UserPreferences
from backend.personalization.types import CareerStage, PreferenceLevel


def _prefs(**overrides) -> UserPreferences:
    base = dict(region_ids=["greater_boston"])
    base.update(overrides)
    return UserPreferences(**base)


def test_preferences_minimal_payload_validates() -> None:
    p = _prefs()
    assert p.region_ids == ["greater_boston"]
    assert p.role_targets == []
    assert p.industry_preferences == []
    assert p.career_stage is None
    assert p.prestige_preference is None
    assert p.brand_preference is None
    assert p.limit == 25


def test_preferences_full_payload_validates() -> None:
    p = _prefs(
        role_targets=["product"],
        industry_preferences=["ai", "cloud"],
        career_stage=CareerStage.ENTRY_LEVEL,
        prestige_preference=PreferenceLevel.MEDIUM,
        brand_preference=PreferenceLevel.HIGH,
        limit=10,
    )
    assert p.role_targets == ["product"]
    assert p.career_stage is CareerStage.ENTRY_LEVEL
    assert p.brand_preference is PreferenceLevel.HIGH
    assert p.limit == 10


def test_preferences_requires_region_ids() -> None:
    with pytest.raises(ValidationError):
        UserPreferences(region_ids=[])


def test_preferences_rejects_blank_region_id() -> None:
    with pytest.raises(ValidationError):
        UserPreferences(region_ids=["greater_boston", "  "])


def test_preferences_rejects_blank_role_target() -> None:
    with pytest.raises(ValidationError):
        _prefs(role_targets=["product", ""])


def test_preferences_rejects_blank_industry() -> None:
    with pytest.raises(ValidationError):
        _prefs(industry_preferences=["ai", ""])


def test_preferences_rejects_unknown_career_stage() -> None:
    with pytest.raises(ValidationError):
        UserPreferences.model_validate(
            {"region_ids": ["greater_boston"], "career_stage": "senior"}
        )


def test_preferences_rejects_unknown_preference_level() -> None:
    with pytest.raises(ValidationError):
        UserPreferences.model_validate(
            {
                "region_ids": ["greater_boston"],
                "prestige_preference": "extreme",
            }
        )


def test_preferences_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        UserPreferences.model_validate(
            {"region_ids": ["greater_boston"], "extra_field": True}
        )


def test_preferences_limit_bounds() -> None:
    with pytest.raises(ValidationError):
        _prefs(limit=0)
    with pytest.raises(ValidationError):
        _prefs(limit=1000)
    assert _prefs(limit=1).limit == 1
    assert _prefs(limit=100).limit == 100
