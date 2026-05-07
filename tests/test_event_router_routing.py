"""Event-to-job routing tests for Slice 15."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.orchestration.events.exceptions import EventValidationError
from backend.orchestration.events.payloads import Event
from backend.orchestration.events.router import (
    EventRouter,
    RouteResult,
    route_event,
)
from backend.orchestration.events.types import EventType
from backend.orchestration.jobs.types import JobType, Priority

_T0 = datetime(2026, 5, 6, 16, 0, tzinfo=UTC)


def _event(event_type: EventType, scope: dict, **overrides) -> Event:
    payload = dict(
        event_id=f"evt_{event_type.value.lower()}",
        event_type=event_type,
        emitted_at=_T0,
        source="scheduler",
        scope=scope,
    )
    payload.update(overrides)
    return Event(**payload)


def _job_types(result: RouteResult) -> list[JobType]:
    return [r.job_type for r in result.recommendations]


# ---------------------------------------------------------------------------
# REGION_ADDED
# ---------------------------------------------------------------------------


def test_region_added_only_recommends_region_output_build() -> None:
    event = _event(EventType.REGION_ADDED, {"region_id": "greater_boston"})
    result = route_event(event)
    assert _job_types(result) == [JobType.REGION_OUTPUT_BUILD]
    assert all(
        rec.scope == {"region_ids": ["greater_boston"]}
        for rec in result.recommendations
    )


def test_region_added_does_not_propose_geography_or_intake() -> None:
    event = _event(EventType.REGION_ADDED, {"region_id": "greater_boston"})
    result = route_event(event)
    job_types = {r.job_type for r in result.recommendations}
    assert JobType.GEOGRAPHY_BUILD not in job_types
    assert JobType.COMPANY_UNIVERSE_INTAKE not in job_types
    assert JobType.HIRING_REFRESH not in job_types


def test_region_added_requires_region_id() -> None:
    event = _event(EventType.REGION_ADDED, {})
    with pytest.raises(EventValidationError):
        route_event(event)


# ---------------------------------------------------------------------------
# REGION_DEFINITION_CHANGED
# ---------------------------------------------------------------------------


def test_region_definition_changed_scopes_to_region() -> None:
    event = _event(
        EventType.REGION_DEFINITION_CHANGED,
        {"region_id": "greater_boston"},
    )
    result = route_event(event)
    assert _job_types(result) == [
        JobType.REGION_SCORE_RECOMPUTE,
        JobType.REGION_OUTPUT_BUILD,
    ]
    for rec in result.recommendations:
        assert rec.scope == {"region_ids": ["greater_boston"]}


def test_region_definition_changed_does_not_trigger_classification() -> None:
    event = _event(
        EventType.REGION_DEFINITION_CHANGED,
        {"region_id": "greater_boston"},
    )
    result = route_event(event)
    job_types = {r.job_type for r in result.recommendations}
    assert JobType.ELIGIBILITY_CLASSIFICATION not in job_types


# ---------------------------------------------------------------------------
# NEW_COMPANY_CANDIDATE_ADDED
# ---------------------------------------------------------------------------


def test_new_company_candidate_added_recommends_classification_only() -> None:
    event = _event(
        EventType.NEW_COMPANY_CANDIDATE_ADDED,
        {"company_id": "comp_101"},
    )
    result = route_event(event)
    assert _job_types(result) == [JobType.ELIGIBILITY_CLASSIFICATION]
    rec = result.recommendations[0]
    assert rec.scope == {"company_ids": ["comp_101"]}


def test_new_company_candidate_does_not_trigger_presence_or_hiring() -> None:
    event = _event(
        EventType.NEW_COMPANY_CANDIDATE_ADDED,
        {"company_id": "comp_101"},
    )
    result = route_event(event)
    job_types = {r.job_type for r in result.recommendations}
    assert JobType.PRESENCE_MAPPING not in job_types
    assert JobType.HIRING_REFRESH not in job_types
    assert JobType.ENTRY_LEVEL_REFRESH not in job_types
    assert JobType.REGION_SCORE_RECOMPUTE not in job_types


# ---------------------------------------------------------------------------
# COMPANY_CLASSIFICATION_CORRECTED
# ---------------------------------------------------------------------------


def test_company_classification_corrected_with_regions() -> None:
    event = _event(
        EventType.COMPANY_CLASSIFICATION_CORRECTED,
        {"company_id": "comp_101", "region_ids": ["greater_boston"]},
    )
    result = route_event(event)
    assert _job_types(result) == [
        JobType.PRESENCE_MAPPING,
        JobType.COMPANY_OUTPUT_BUILD,
        JobType.REGION_SCORE_RECOMPUTE,
        JobType.REGION_OUTPUT_BUILD,
    ]


def test_company_classification_corrected_without_regions_skips_region_jobs() -> None:
    event = _event(
        EventType.COMPANY_CLASSIFICATION_CORRECTED,
        {"company_id": "comp_101"},
    )
    result = route_event(event)
    assert _job_types(result) == [
        JobType.PRESENCE_MAPPING,
        JobType.COMPANY_OUTPUT_BUILD,
    ]


# ---------------------------------------------------------------------------
# COMPANY_PRESENCE_UPDATED
# ---------------------------------------------------------------------------


def test_company_presence_updated_recommends_full_chain() -> None:
    event = _event(
        EventType.COMPANY_PRESENCE_UPDATED,
        {
            "company_region_pairs": [
                {"company_id": "comp_101", "region_id": "greater_boston"},
            ]
        },
    )
    result = route_event(event)
    assert _job_types(result) == [
        JobType.HIRING_REFRESH,
        JobType.ENTRY_LEVEL_REFRESH,
        JobType.REGION_SCORE_RECOMPUTE,
        JobType.REGION_OUTPUT_BUILD,
        JobType.COMPANY_OUTPUT_BUILD,
    ]


def test_company_presence_updated_does_not_touch_geography_or_classification() -> None:
    event = _event(
        EventType.COMPANY_PRESENCE_UPDATED,
        {
            "company_region_pairs": [
                {"company_id": "comp_1", "region_id": "greater_boston"}
            ]
        },
    )
    result = route_event(event)
    job_types = {r.job_type for r in result.recommendations}
    assert JobType.GEOGRAPHY_BUILD not in job_types
    assert JobType.COMPANY_UNIVERSE_INTAKE not in job_types
    assert JobType.ELIGIBILITY_CLASSIFICATION not in job_types


# ---------------------------------------------------------------------------
# HIRING_DATA_UPDATED
# ---------------------------------------------------------------------------


def test_hiring_data_updated_recommends_entry_level_score_outputs() -> None:
    event = _event(
        EventType.HIRING_DATA_UPDATED,
        {
            "company_region_pairs": [
                {"company_id": "comp_1", "region_id": "greater_boston"},
            ]
        },
    )
    result = route_event(event)
    assert _job_types(result) == [
        JobType.ENTRY_LEVEL_REFRESH,
        JobType.REGION_SCORE_RECOMPUTE,
        JobType.REGION_OUTPUT_BUILD,
        JobType.COMPANY_OUTPUT_BUILD,
    ]


def test_hiring_data_updated_does_not_trigger_geography_or_classification() -> None:
    event = _event(
        EventType.HIRING_DATA_UPDATED,
        {
            "company_region_pairs": [
                {"company_id": "comp_1", "region_id": "greater_boston"},
            ]
        },
    )
    result = route_event(event)
    job_types = {r.job_type for r in result.recommendations}
    assert JobType.GEOGRAPHY_BUILD not in job_types
    assert JobType.COMPANY_UNIVERSE_INTAKE not in job_types
    assert JobType.ELIGIBILITY_CLASSIFICATION not in job_types


def test_hiring_data_updated_collapses_duplicate_pairs() -> None:
    event = _event(
        EventType.HIRING_DATA_UPDATED,
        {
            "company_region_pairs": [
                {"company_id": "comp_1", "region_id": "greater_boston"},
                {"company_id": "comp_1", "region_id": "greater_boston"},
            ]
        },
    )
    result = route_event(event)
    pair_recs = [
        rec for rec in result.recommendations
        if rec.job_type is JobType.ENTRY_LEVEL_REFRESH
    ]
    assert len(pair_recs) == 1
    assert pair_recs[0].scope["company_region_pairs"] == [
        {"company_id": "comp_1", "region_id": "greater_boston"}
    ]


# ---------------------------------------------------------------------------
# ENTRY_LEVEL_SIGNAL_UPDATED
# ---------------------------------------------------------------------------


def test_entry_level_signal_updated_does_not_reissue_hiring_refresh() -> None:
    event = _event(
        EventType.ENTRY_LEVEL_SIGNAL_UPDATED,
        {
            "company_region_pairs": [
                {"company_id": "comp_1", "region_id": "greater_boston"}
            ]
        },
    )
    result = route_event(event)
    job_types = [r.job_type for r in result.recommendations]
    assert JobType.HIRING_REFRESH not in job_types
    assert job_types == [
        JobType.REGION_SCORE_RECOMPUTE,
        JobType.REGION_OUTPUT_BUILD,
        JobType.COMPANY_OUTPUT_BUILD,
    ]


# ---------------------------------------------------------------------------
# NORMALIZATION_INPUTS_UPDATED
# ---------------------------------------------------------------------------


def test_normalization_inputs_updated_scopes_to_regions() -> None:
    event = _event(
        EventType.NORMALIZATION_INPUTS_UPDATED,
        {"region_ids": ["greater_sf", "greater_boston"]},
    )
    result = route_event(event)
    assert _job_types(result) == [
        JobType.REGION_SCORE_RECOMPUTE,
        JobType.REGION_OUTPUT_BUILD,
    ]
    for rec in result.recommendations:
        # Sorted deterministically.
        assert rec.scope == {"region_ids": ["greater_boston", "greater_sf"]}


def test_normalization_inputs_updated_rejects_blank_entry() -> None:
    event = _event(
        EventType.NORMALIZATION_INPUTS_UPDATED,
        {"region_ids": [""]},
    )
    with pytest.raises(EventValidationError):
        route_event(event)


# ---------------------------------------------------------------------------
# COMPARISON_REQUESTED
# ---------------------------------------------------------------------------


def test_comparison_requested_canonicalizes_pair() -> None:
    forward = _event(
        EventType.COMPARISON_REQUESTED,
        {"region_a": "greater_sf", "region_b": "greater_boston"},
    )
    reverse = _event(
        EventType.COMPARISON_REQUESTED,
        {"region_a": "greater_boston", "region_b": "greater_sf"},
    )
    forward_result = route_event(forward)
    reverse_result = route_event(reverse)

    forward_rec = forward_result.recommendations[0]
    reverse_rec = reverse_result.recommendations[0]
    assert forward_rec.scope == reverse_rec.scope
    assert forward_rec.scope == {
        "comparison_pairs": [["greater_boston", "greater_sf"]]
    }
    assert (
        "canonical_comparison_id=greater_boston__greater_sf"
        in forward_result.notes
    )


def test_comparison_requested_priority_is_high() -> None:
    event = _event(
        EventType.COMPARISON_REQUESTED,
        {"region_a": "greater_boston", "region_b": "greater_sf"},
    )
    result = route_event(event)
    assert result.recommendations[0].priority is Priority.HIGH


def test_comparison_requested_rejects_identical_regions() -> None:
    event = _event(
        EventType.COMPARISON_REQUESTED,
        {"region_a": "greater_boston", "region_b": "greater_boston"},
    )
    with pytest.raises(EventValidationError):
        route_event(event)


def test_comparison_requested_rejects_blank() -> None:
    event = _event(
        EventType.COMPARISON_REQUESTED,
        {"region_a": "", "region_b": "greater_sf"},
    )
    with pytest.raises(EventValidationError):
        route_event(event)


# ---------------------------------------------------------------------------
# Determinism + foundational-job guarantees.
# ---------------------------------------------------------------------------


def test_route_is_deterministic_across_calls() -> None:
    event = _event(
        EventType.HIRING_DATA_UPDATED,
        {
            "company_region_pairs": [
                {"company_id": "c2", "region_id": "greater_boston"},
                {"company_id": "c1", "region_id": "greater_sf"},
            ]
        },
    )
    a = route_event(event)
    b = route_event(event)
    assert a.recommendations == b.recommendations
    assert a.invalidations == b.invalidations


def test_dynamic_events_never_recommend_foundational_jobs() -> None:
    dynamic_events = [
        _event(
            EventType.HIRING_DATA_UPDATED,
            {
                "company_region_pairs": [
                    {"company_id": "c1", "region_id": "greater_boston"}
                ]
            },
        ),
        _event(
            EventType.ENTRY_LEVEL_SIGNAL_UPDATED,
            {
                "company_region_pairs": [
                    {"company_id": "c1", "region_id": "greater_boston"}
                ]
            },
        ),
        _event(
            EventType.NORMALIZATION_INPUTS_UPDATED,
            {"region_ids": ["greater_boston"]},
        ),
        _event(
            EventType.COMPARISON_REQUESTED,
            {"region_a": "greater_boston", "region_b": "greater_sf"},
        ),
    ]
    forbidden = {JobType.GEOGRAPHY_BUILD, JobType.COMPANY_UNIVERSE_INTAKE}
    for event in dynamic_events:
        result = route_event(event)
        produced = {rec.job_type for rec in result.recommendations}
        assert not (produced & forbidden), (event.event_type.value, produced)


def test_router_class_matches_function() -> None:
    event = _event(EventType.REGION_ADDED, {"region_id": "greater_boston"})
    assert EventRouter().route(event).recommendations == route_event(event).recommendations
