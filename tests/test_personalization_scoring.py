"""Direct tests of the personalization formula functions."""

import pytest

from backend.personalization.scoring import (
    W_BRAND,
    W_INDUSTRY,
    W_PRESTIGE,
    W_ROLE,
    brand_fit_component,
    industry_fit_component,
    personal_company_score,
    personal_market_score,
    prestige_fit_component,
    role_fit_component,
    weights_snapshot,
)
from backend.personalization.types import PreferenceLevel

# --- weight invariants ----------------------------------------------------


def test_weights_sum_to_one() -> None:
    assert pytest.approx(1.0) == W_ROLE + W_INDUSTRY + W_PRESTIGE + W_BRAND


def test_role_and_industry_outweigh_prestige_and_brand() -> None:
    assert (W_ROLE + W_INDUSTRY) > (W_PRESTIGE + W_BRAND)


def test_role_leads_industry_leads_prestige_leads_brand() -> None:
    """Role fit must lead, industry second, prestige third, brand last."""
    assert W_ROLE > W_INDUSTRY > W_PRESTIGE > W_BRAND


def test_weights_snapshot_returns_dict() -> None:
    snap = weights_snapshot()
    assert snap["role"] == W_ROLE
    assert snap["industry"] == W_INDUSTRY


# --- role fit -------------------------------------------------------------


def test_role_fit_neutral_when_no_targets() -> None:
    score, notes = role_fit_component(role_targets=[], role_family_summary={"product": 5})
    assert score == 0.5
    assert notes == []


def test_role_fit_zero_when_summary_missing() -> None:
    score, notes = role_fit_component(
        role_targets=["product"], role_family_summary=None
    )
    assert score == 0.0
    assert notes == []


def test_role_fit_full_match() -> None:
    score, notes = role_fit_component(
        role_targets=["product"], role_family_summary={"product": 10}
    )
    assert score == 1.0
    assert "role:product" in notes


def test_role_fit_partial_match() -> None:
    score, notes = role_fit_component(
        role_targets=["product"],
        role_family_summary={"product": 3, "ai_cloud_adjacent": 7},
    )
    assert score == pytest.approx(0.3)


def test_role_fit_normalizes_case() -> None:
    score, _ = role_fit_component(
        role_targets=["PRODUCT"], role_family_summary={"product": 5}
    )
    assert score == 1.0


# --- industry fit --------------------------------------------------------


def test_industry_fit_neutral_when_no_preferences() -> None:
    score, _ = industry_fit_component(
        industry_preferences=[],
        sector_primary="ai",
        sector_secondary=None,
    )
    assert score == 0.5


def test_industry_fit_primary_match() -> None:
    score, notes = industry_fit_component(
        industry_preferences=["ai", "cloud"],
        sector_primary="ai",
        sector_secondary=None,
    )
    assert score == 1.0
    assert any("industry_primary:ai" in n for n in notes)


def test_industry_fit_secondary_match_only() -> None:
    score, notes = industry_fit_component(
        industry_preferences=["cloud"],
        sector_primary="hardware",
        sector_secondary="cloud",
    )
    assert score == 0.5
    assert any("industry_secondary:cloud" in n for n in notes)


def test_industry_fit_no_match() -> None:
    score, notes = industry_fit_component(
        industry_preferences=["cybersecurity"],
        sector_primary="ai",
        sector_secondary="cloud",
    )
    assert score == 0.0
    assert notes == []


def test_industry_fit_handles_missing_sectors() -> None:
    score, _ = industry_fit_component(
        industry_preferences=["ai"],
        sector_primary=None,
        sector_secondary=None,
    )
    assert score == 0.0


# --- prestige fit --------------------------------------------------------


def test_prestige_neutral_when_no_preference() -> None:
    score, _ = prestige_fit_component(
        preference=None,
        prestige_score=0.8,
        is_major_tech=True,
        is_mag7=False,
    )
    assert score == 0.5


def test_prestige_high_preference_rewards_high_signal() -> None:
    high = prestige_fit_component(
        preference=PreferenceLevel.HIGH,
        prestige_score=None,
        is_major_tech=False,
        is_mag7=True,
    )[0]
    low = prestige_fit_component(
        preference=PreferenceLevel.HIGH,
        prestige_score=0.0,
        is_major_tech=False,
        is_mag7=False,
    )[0]
    assert high == 1.0
    assert low == 0.0


def test_prestige_medium_never_below_half() -> None:
    score = prestige_fit_component(
        preference=PreferenceLevel.MEDIUM,
        prestige_score=0.0,
        is_major_tech=False,
        is_mag7=False,
    )[0]
    assert score >= 0.5


def test_prestige_low_inverts_the_signal() -> None:
    low_with_high_signal = prestige_fit_component(
        preference=PreferenceLevel.LOW,
        prestige_score=None,
        is_major_tech=False,
        is_mag7=True,
    )[0]
    low_with_no_signal = prestige_fit_component(
        preference=PreferenceLevel.LOW,
        prestige_score=0.0,
        is_major_tech=False,
        is_mag7=False,
    )[0]
    assert low_with_high_signal < low_with_no_signal


# --- brand fit ----------------------------------------------------------


def test_brand_neutral_when_no_preference() -> None:
    score, _ = brand_fit_component(
        preference=None, is_major_tech=True, is_mag7=True
    )
    assert score == 0.5


def test_brand_high_pref_rewards_mag7() -> None:
    score, notes = brand_fit_component(
        preference=PreferenceLevel.HIGH, is_major_tech=False, is_mag7=True
    )
    assert score == 1.0
    assert any("brand:mag7" in n for n in notes)


def test_brand_high_pref_rewards_major_tech_partially() -> None:
    score, _ = brand_fit_component(
        preference=PreferenceLevel.HIGH, is_major_tech=True, is_mag7=False
    )
    assert score == 0.5


def test_brand_uses_only_user_input_no_inference() -> None:
    """Brand component must not derive preference from any inferred signal —
    it relies solely on the user's explicit preference + binary brand
    recognition flags."""
    # No preference + no flags → neutral 0.5 (not "low").
    score, _ = brand_fit_component(
        preference=None, is_major_tech=False, is_mag7=False
    )
    assert score == 0.5


# --- composite -----------------------------------------------------------


def test_personal_company_score_is_bounded() -> None:
    assert (
        personal_company_score(role_fit=0, industry_fit=0, prestige_fit=0, brand_fit=0)
        == 0.0
    )
    # Float summation of the four weights can land at 0.9999...; the
    # helper clamps to [0, 1] so we use ``approx`` here.
    assert pytest.approx(1.0) == personal_company_score(
        role_fit=1, industry_fit=1, prestige_fit=1, brand_fit=1
    )


def test_personal_company_score_reflects_weight_ordering() -> None:
    """Maxing role beats maxing prestige + brand combined."""
    role_only = personal_company_score(
        role_fit=1.0, industry_fit=0.0, prestige_fit=0.0, brand_fit=0.0
    )
    prestige_and_brand = personal_company_score(
        role_fit=0.0, industry_fit=0.0, prestige_fit=1.0, brand_fit=1.0
    )
    assert role_only == W_ROLE
    assert prestige_and_brand == W_PRESTIGE + W_BRAND


def test_personal_company_score_role_industry_combo_dominates_prestige_brand() -> None:
    role_industry = personal_company_score(
        role_fit=1.0, industry_fit=1.0, prestige_fit=0.0, brand_fit=0.0
    )
    prestige_brand = personal_company_score(
        role_fit=0.0, industry_fit=0.0, prestige_fit=1.0, brand_fit=1.0
    )
    assert role_industry > prestige_brand


def test_personal_company_score_is_deterministic() -> None:
    a = personal_company_score(
        role_fit=0.5, industry_fit=0.5, prestige_fit=0.5, brand_fit=0.5
    )
    b = personal_company_score(
        role_fit=0.5, industry_fit=0.5, prestige_fit=0.5, brand_fit=0.5
    )
    assert a == b


def test_personal_market_score_empty() -> None:
    assert personal_market_score(company_scores=[]) == 0.0


def test_personal_market_score_average() -> None:
    assert personal_market_score(company_scores=[0.4, 0.6]) == pytest.approx(0.5)


def test_personal_market_score_clips_to_unit_range() -> None:
    assert (
        personal_market_score(company_scores=[1.5, 2.0, -1.0])
        == pytest.approx(2 / 3)  # clipped to [0, 1] before averaging
    )
