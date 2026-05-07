"""Scoped invalidation tests for Slice 15."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.orchestration.events.exceptions import (
    EventValidationError,
    UnsupportedEventType,
)
from backend.orchestration.events.payloads import Event
from backend.orchestration.events.types import EventType
from backend.orchestration.invalidation.rules import (
    canonical_comparison_id,
    derive_invalidation_directives,
)
from backend.orchestration.invalidation.service import InvalidationService
from backend.orchestration.invalidation.types import (
    InvalidationDirective,
    InvalidationTarget,
)

_T0 = datetime(2026, 5, 6, 16, 0, tzinfo=UTC)


def _event(event_type: EventType, scope: dict) -> Event:
    return Event(
        event_id=f"evt_{event_type.value.lower()}",
        event_type=event_type,
        emitted_at=_T0,
        source="scheduler",
        scope=scope,
    )


def test_invalidation_target_vocabulary_is_fixed() -> None:
    assert InvalidationTarget.values() == {
        "region_score",
        "region_output",
        "company_output",
        "comparison_output",
        "hiring_refresh",
        "entry_level_refresh",
        "presence_mapping",
        "company_classification",
    }


def test_region_definition_changed_scopes_to_region() -> None:
    directives = derive_invalidation_directives(
        _event(EventType.REGION_DEFINITION_CHANGED, {"region_id": "greater_boston"})
    )
    targets = [d.target for d in directives]
    assert InvalidationTarget.REGION_SCORE in targets
    assert InvalidationTarget.REGION_OUTPUT in targets
    assert InvalidationTarget.COMPARISON_OUTPUT in targets
    for d in directives:
        if d.target in {
            InvalidationTarget.REGION_SCORE,
            InvalidationTarget.REGION_OUTPUT,
        }:
            assert d.scope == {"region_id": "greater_boston"}


def test_new_company_candidate_invalidates_only_classification() -> None:
    directives = derive_invalidation_directives(
        _event(EventType.NEW_COMPANY_CANDIDATE_ADDED, {"company_id": "comp_101"})
    )
    assert [d.target for d in directives] == [
        InvalidationTarget.COMPANY_CLASSIFICATION,
    ]
    assert directives[0].scope == {"company_id": "comp_101"}


def test_company_presence_updated_per_pair() -> None:
    directives = derive_invalidation_directives(
        _event(
            EventType.COMPANY_PRESENCE_UPDATED,
            {
                "company_region_pairs": [
                    {"company_id": "c2", "region_id": "greater_boston"},
                    {"company_id": "c1", "region_id": "greater_sf"},
                ]
            },
        )
    )
    pair_directives = [
        d for d in directives if d.target is InvalidationTarget.HIRING_REFRESH
    ]
    # Sorted deterministically.
    assert [d.scope for d in pair_directives] == [
        {"company_id": "c1", "region_id": "greater_sf"},
        {"company_id": "c2", "region_id": "greater_boston"},
    ]


def test_hiring_data_updated_does_not_invalidate_company_classification() -> None:
    directives = derive_invalidation_directives(
        _event(
            EventType.HIRING_DATA_UPDATED,
            {
                "company_region_pairs": [
                    {"company_id": "c1", "region_id": "greater_boston"}
                ]
            },
        )
    )
    targets = {d.target for d in directives}
    assert InvalidationTarget.COMPANY_CLASSIFICATION not in targets
    assert InvalidationTarget.PRESENCE_MAPPING not in targets


def test_entry_level_signal_does_not_invalidate_hiring() -> None:
    directives = derive_invalidation_directives(
        _event(
            EventType.ENTRY_LEVEL_SIGNAL_UPDATED,
            {
                "company_region_pairs": [
                    {"company_id": "c1", "region_id": "greater_boston"}
                ]
            },
        )
    )
    targets = {d.target for d in directives}
    assert InvalidationTarget.HIRING_REFRESH not in targets


def test_normalization_inputs_updated_per_region() -> None:
    directives = derive_invalidation_directives(
        _event(
            EventType.NORMALIZATION_INPUTS_UPDATED,
            {"region_ids": ["greater_boston", "greater_sf"]},
        )
    )
    score_dirs = [
        d for d in directives if d.target is InvalidationTarget.REGION_SCORE
    ]
    assert [d.scope["region_id"] for d in score_dirs] == [
        "greater_boston",
        "greater_sf",
    ]


def test_comparison_requested_uses_canonical_subject_id() -> None:
    forward = derive_invalidation_directives(
        _event(
            EventType.COMPARISON_REQUESTED,
            {"region_a": "greater_sf", "region_b": "greater_boston"},
        )
    )
    reverse = derive_invalidation_directives(
        _event(
            EventType.COMPARISON_REQUESTED,
            {"region_a": "greater_boston", "region_b": "greater_sf"},
        )
    )
    assert len(forward) == 1
    assert forward[0].target is InvalidationTarget.COMPARISON_OUTPUT
    assert (
        forward[0].scope["comparison_id"]
        == canonical_comparison_id("greater_sf", "greater_boston")
        == "greater_boston__greater_sf"
    )
    assert forward[0].scope == reverse[0].scope


def test_comparison_requested_rejects_identical() -> None:
    with pytest.raises(EventValidationError):
        derive_invalidation_directives(
            _event(
                EventType.COMPARISON_REQUESTED,
                {"region_a": "greater_boston", "region_b": "greater_boston"},
            )
        )


def test_unsupported_event_type_raises() -> None:
    # Forge an Event with a value not in our rule table by monkey-patching
    # the dictionary; cleaner: pretend by constructing a known type then
    # replacing event_type before the call. Since EventType is a closed enum
    # we exercise the explicit guard another way: invoke through a fresh
    # InvalidationService and patch the rule table.
    from backend.orchestration.invalidation import rules as rules_mod

    original = rules_mod._RULES
    try:
        rules_mod._RULES = {}
        with pytest.raises(UnsupportedEventType):
            InvalidationService().directives_for(
                _event(EventType.REGION_ADDED, {"region_id": "x"})
            )
    finally:
        rules_mod._RULES = original


def test_directives_are_pydantic_frozen() -> None:
    from pydantic import ValidationError

    directive = InvalidationDirective(
        target=InvalidationTarget.REGION_SCORE,
        scope={"region_id": "x"},
        reason="t",
    )
    with pytest.raises(ValidationError):
        directive.reason = "y"  # type: ignore[misc]
