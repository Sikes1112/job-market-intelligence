"""EventType enum coverage tests."""

from __future__ import annotations

from backend.orchestration.events.types import EventType

REQUIRED_EVENT_TYPES = {
    "REGION_ADDED",
    "REGION_DEFINITION_CHANGED",
    "NEW_COMPANY_CANDIDATE_ADDED",
    "COMPANY_CLASSIFICATION_CORRECTED",
    "COMPANY_PRESENCE_UPDATED",
    "HIRING_DATA_UPDATED",
    "ENTRY_LEVEL_SIGNAL_UPDATED",
    "NORMALIZATION_INPUTS_UPDATED",
    "COMPARISON_REQUESTED",
}


def test_every_required_event_type_exists() -> None:
    assert REQUIRED_EVENT_TYPES.issubset(EventType.values())


def test_event_type_values_are_strings() -> None:
    for member in EventType:
        assert isinstance(member.value, str)
        assert member.value == member.value.upper()


def test_no_unexpected_event_types() -> None:
    """Slice 15 is fixed-vocabulary. Adding a member needs an explicit slice."""
    assert EventType.values() == REQUIRED_EVENT_TYPES
