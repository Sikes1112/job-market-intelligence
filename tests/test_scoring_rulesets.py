from dataclasses import replace

import pytest

from backend.scoring.exceptions import InvalidRuleset
from backend.scoring.rulesets import DEFAULT_RULESET, ScoringRuleset, default_ruleset


def test_default_ruleset_objective_hierarchy() -> None:
    """Entry-level access leads, current hiring next, prestige last."""
    r = DEFAULT_RULESET
    assert r.w_obj_entry_level > r.w_obj_live_market > r.w_obj_prestige


def test_default_ruleset_entry_level_leads_modestly() -> None:
    """The lead must be measurable but not overwhelming."""
    r = DEFAULT_RULESET
    gap = r.w_obj_entry_level - r.w_obj_live_market
    assert 0 < gap <= 0.15  # 5pp gap in default; cap allows minor tuning


def test_default_ruleset_weights_sum_to_one() -> None:
    r = DEFAULT_RULESET
    assert pytest.approx(1.0) == r.w_obj_entry_level + r.w_obj_live_market + r.w_obj_prestige
    assert pytest.approx(1.0) == r.w_struct_eligible + r.w_struct_major_tech + r.w_struct_mag7
    assert pytest.approx(1.0) == r.w_live_hiring_count + r.w_live_postings + r.w_live_programs
    assert pytest.approx(1.0) == r.w_raw_structural + r.w_raw_live + r.w_raw_objective


def test_default_ruleset_factory_returns_default() -> None:
    assert default_ruleset() is DEFAULT_RULESET


def test_ruleset_rejects_objective_weights_not_summing_to_one() -> None:
    with pytest.raises(InvalidRuleset):
        replace(DEFAULT_RULESET, w_obj_entry_level=0.50)


def test_ruleset_rejects_inverted_objective_hierarchy() -> None:
    with pytest.raises(InvalidRuleset):
        replace(
            DEFAULT_RULESET,
            w_obj_entry_level=0.25,
            w_obj_live_market=0.35,
            w_obj_prestige=0.40,
        )


def test_ruleset_rejects_tied_objective_hierarchy() -> None:
    with pytest.raises(InvalidRuleset):
        replace(
            DEFAULT_RULESET,
            w_obj_entry_level=0.34,
            w_obj_live_market=0.33,
            w_obj_prestige=0.33,
        )


def test_ruleset_rejects_negative_weight() -> None:
    with pytest.raises(InvalidRuleset):
        replace(
            DEFAULT_RULESET,
            w_struct_eligible=-0.1,
            w_struct_major_tech=0.55,
            w_struct_mag7=0.55,
        )


def test_ruleset_rejects_non_positive_caps() -> None:
    with pytest.raises(InvalidRuleset):
        replace(DEFAULT_RULESET, cap_eligible_count=0)


def test_ruleset_is_frozen() -> None:
    # frozen=True dataclass → FrozenInstanceError on assignment
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        DEFAULT_RULESET.w_obj_entry_level = 0.99  # type: ignore[misc]


def test_ruleset_struct_hierarchy_is_documented_default() -> None:
    """Default structural weights: eligible > major_tech > mag7."""
    r = DEFAULT_RULESET
    assert r.w_struct_eligible > r.w_struct_major_tech > r.w_struct_mag7


def test_ruleset_can_be_overridden_with_custom_values() -> None:
    custom = replace(
        DEFAULT_RULESET,
        version="custom_v1",
        w_obj_entry_level=0.45,
        w_obj_live_market=0.35,
        w_obj_prestige=0.20,
    )
    assert isinstance(custom, ScoringRuleset)
    assert custom.version == "custom_v1"
