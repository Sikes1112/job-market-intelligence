"""Object lifecycle state primitives.

This module defines the MVP object lifecycle enum, the static set of allowed
transitions, and reusable helpers to check or validate a transition. There is
no business meaning here: nothing in this module decides *why* an object should
move between states — only whether a particular move is structurally allowed.

The optional later states ``low_confidence``, ``verified``, and ``deprecated``
are intentionally omitted: ``MVP_SCOPE.md`` and ``SLICE_PLAN.md`` Slice 3 list
them as deferred until the integrity layer matures.
"""

from __future__ import annotations

from enum import StrEnum


class ObjectState(StrEnum):
    NEW = "new"
    BUILDING = "building"
    FRESH = "fresh"
    STALE = "stale"
    PARTIAL = "partial"
    FAILED = "failed"
    BLOCKED = "blocked"
    REBUILDING = "rebuilding"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class InvalidStateTransition(ValueError):
    """Raised when a transition is not in :data:`ALLOWED_TRANSITIONS`."""


# Derived from OBJECT_STATE_MODEL.md §6, §7, and §17 with non-MVP states
# pruned. Any pair not in this set is rejected by ``validate_transition``.
ALLOWED_TRANSITIONS: frozenset[tuple[ObjectState, ObjectState]] = frozenset(
    {
        # First-time build
        (ObjectState.NEW, ObjectState.BUILDING),
        # Successful build
        (ObjectState.BUILDING, ObjectState.FRESH),
        (ObjectState.REBUILDING, ObjectState.FRESH),
        # Time decay
        (ObjectState.FRESH, ObjectState.STALE),
        # Rebuild a usable older version
        (ObjectState.STALE, ObjectState.REBUILDING),
        # Partial outcomes
        (ObjectState.BUILDING, ObjectState.PARTIAL),
        (ObjectState.REBUILDING, ObjectState.PARTIAL),
        (ObjectState.PARTIAL, ObjectState.REBUILDING),
        # Hard failure
        (ObjectState.BUILDING, ObjectState.FAILED),
        (ObjectState.REBUILDING, ObjectState.FAILED),
        # Dependency missing
        (ObjectState.NEW, ObjectState.BLOCKED),
        (ObjectState.STALE, ObjectState.BLOCKED),
        (ObjectState.REBUILDING, ObjectState.BLOCKED),
        # Dependency restored
        (ObjectState.BLOCKED, ObjectState.BUILDING),
        (ObjectState.BLOCKED, ObjectState.REBUILDING),
        # Repair after failure
        (ObjectState.FAILED, ObjectState.BUILDING),
        (ObjectState.FAILED, ObjectState.REBUILDING),
    }
)


def coerce_state(value: ObjectState | str) -> ObjectState:
    """Return ``value`` as an :class:`ObjectState`, raising ``ValueError`` on unknown values."""
    if isinstance(value, ObjectState):
        return value
    return ObjectState(value)


def can_transition(current: ObjectState | str, target: ObjectState | str) -> bool:
    """Return whether ``current → target`` is in :data:`ALLOWED_TRANSITIONS`."""
    return (coerce_state(current), coerce_state(target)) in ALLOWED_TRANSITIONS


def validate_transition(
    current: ObjectState | str, target: ObjectState | str
) -> ObjectState:
    """Validate a transition and return the coerced target state.

    Raises :class:`InvalidStateTransition` if the move is not allowed.
    """
    current_state = coerce_state(current)
    target_state = coerce_state(target)
    if (current_state, target_state) not in ALLOWED_TRANSITIONS:
        raise InvalidStateTransition(
            f"transition not allowed: {current_state.value} -> {target_state.value}"
        )
    return target_state
