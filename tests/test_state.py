import pytest

from backend.shared.state import (
    ALLOWED_TRANSITIONS,
    InvalidStateTransition,
    ObjectState,
    can_transition,
    coerce_state,
    validate_transition,
)

REQUIRED_MVP_STATES = {
    "new",
    "building",
    "fresh",
    "stale",
    "partial",
    "failed",
    "blocked",
    "rebuilding",
}

DEFERRED_STATES = {"low_confidence", "verified", "deprecated"}


def test_all_required_mvp_states_present() -> None:
    assert ObjectState.values() == REQUIRED_MVP_STATES


def test_deferred_states_not_implemented() -> None:
    overlap = ObjectState.values() & DEFERRED_STATES
    assert overlap == set(), overlap


def test_coerce_state_accepts_string_or_enum() -> None:
    assert coerce_state("new") is ObjectState.NEW
    assert coerce_state(ObjectState.FRESH) is ObjectState.FRESH


def test_coerce_state_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        coerce_state("verified")  # deferred, not yet allowed


def test_can_transition_allows_documented_paths() -> None:
    # Spot checks pulled from OBJECT_STATE_MODEL.md §17.
    assert can_transition("new", "building")
    assert can_transition("building", "fresh")
    assert can_transition("fresh", "stale")
    assert can_transition("stale", "rebuilding")
    assert can_transition("rebuilding", "fresh")
    assert can_transition("blocked", "rebuilding")
    assert can_transition("failed", "building")
    assert can_transition("partial", "rebuilding")


@pytest.mark.parametrize(
    "current,target",
    [
        # Same-state moves are not transitions.
        ("fresh", "fresh"),
        # Skipping a build is not allowed.
        ("new", "fresh"),
        # Time-decay only moves forward.
        ("stale", "fresh"),
        # You cannot leap from a hard failure straight to fresh.
        ("failed", "fresh"),
        # blocked must go through building or rebuilding.
        ("blocked", "fresh"),
        # building cannot go directly to stale.
        ("building", "stale"),
    ],
)
def test_can_transition_rejects_invalid_paths(current: str, target: str) -> None:
    assert can_transition(current, target) is False


def test_validate_transition_returns_target_when_valid() -> None:
    assert validate_transition("new", "building") is ObjectState.BUILDING


def test_validate_transition_raises_on_invalid() -> None:
    with pytest.raises(InvalidStateTransition):
        validate_transition("new", "fresh")


def test_validate_transition_raises_on_unknown_value() -> None:
    with pytest.raises(ValueError):
        validate_transition("new", "verified")


def test_allowed_transitions_only_reference_mvp_states() -> None:
    for current, target in ALLOWED_TRANSITIONS:
        assert isinstance(current, ObjectState)
        assert isinstance(target, ObjectState)


def test_no_self_loops_in_allowed_transitions() -> None:
    self_loops = {(c, t) for c, t in ALLOWED_TRANSITIONS if c is t}
    assert self_loops == set()
