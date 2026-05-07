"""Event envelope validation tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.orchestration.events.payloads import Event
from backend.orchestration.events.types import EventType
from backend.orchestration.jobs.types import Priority


def _base(**overrides):
    payload = dict(
        event_id="evt_001",
        event_type=EventType.HIRING_DATA_UPDATED,
        emitted_at=datetime(2026, 5, 6, 16, 0, tzinfo=UTC),
        source="scheduler",
        scope={
            "company_region_pairs": [
                {"company_id": "comp_1", "region_id": "greater_boston"}
            ]
        },
        priority=Priority.HIGH,
    )
    payload.update(overrides)
    return payload


def test_event_constructs_with_required_fields() -> None:
    event = Event(**_base())
    assert event.event_type is EventType.HIRING_DATA_UPDATED
    assert event.emitted_at.tzinfo is not None
    assert event.no_meaningful_change is False
    assert event.priority is Priority.HIGH


def test_event_rejects_naive_emitted_at() -> None:
    with pytest.raises(ValidationError):
        Event(**_base(emitted_at=datetime(2026, 5, 6, 16, 0)))


def test_event_rejects_blank_event_id() -> None:
    with pytest.raises(ValidationError):
        Event(**_base(event_id=""))


def test_event_rejects_blank_source() -> None:
    with pytest.raises(ValidationError):
        Event(**_base(source=""))


def test_event_rejects_blank_correlation_id() -> None:
    with pytest.raises(ValidationError):
        Event(**_base(correlation_id="   "))


def test_event_accepts_no_meaningful_change_flag() -> None:
    event = Event(**_base(no_meaningful_change=True))
    assert event.no_meaningful_change is True


def test_event_extra_fields_rejected() -> None:
    with pytest.raises(ValidationError):
        Event(**_base(unexpected="x"))
