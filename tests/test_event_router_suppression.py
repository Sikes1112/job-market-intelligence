"""Suppression behavior for events flagged ``no_meaningful_change``."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.orchestration.events.payloads import Event
from backend.orchestration.events.router import route_event
from backend.orchestration.events.types import EventType

_T0 = datetime(2026, 5, 6, 16, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "event_type, scope",
    [
        (EventType.REGION_ADDED, {"region_id": "greater_boston"}),
        (
            EventType.HIRING_DATA_UPDATED,
            {
                "company_region_pairs": [
                    {"company_id": "c1", "region_id": "greater_boston"}
                ]
            },
        ),
        (
            EventType.ENTRY_LEVEL_SIGNAL_UPDATED,
            {
                "company_region_pairs": [
                    {"company_id": "c1", "region_id": "greater_boston"}
                ]
            },
        ),
        (
            EventType.NORMALIZATION_INPUTS_UPDATED,
            {"region_ids": ["greater_boston"]},
        ),
        (
            EventType.COMPARISON_REQUESTED,
            {"region_a": "greater_boston", "region_b": "greater_sf"},
        ),
    ],
)
def test_no_meaningful_change_suppresses_visibly(event_type, scope) -> None:
    event = Event(
        event_id="evt_x",
        event_type=event_type,
        emitted_at=_T0,
        source="scheduler",
        scope=scope,
        no_meaningful_change=True,
    )
    result = route_event(event)
    assert result.suppressed is True
    assert result.suppression_reason is not None
    assert "no_meaningful_change" in result.suppression_reason
    assert result.recommendations == ()
    assert result.invalidations == ()


def test_meaningful_change_still_routes() -> None:
    event = Event(
        event_id="evt_x",
        event_type=EventType.HIRING_DATA_UPDATED,
        emitted_at=_T0,
        source="scheduler",
        scope={
            "company_region_pairs": [
                {"company_id": "c1", "region_id": "greater_boston"}
            ]
        },
        no_meaningful_change=False,
    )
    result = route_event(event)
    assert result.suppressed is False
    assert result.suppression_reason is None
    assert result.recommendations  # non-empty
    assert result.invalidations  # non-empty
