"""Enqueue-adapter tests — Slice 15 routes through the Slice 14 QueueService."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.orchestration.events.payloads import Event
from backend.orchestration.events.types import EventType
from backend.orchestration.invalidation.types import InvalidationTarget
from backend.orchestration.queues.repository import QueueRepository
from backend.orchestration.queues.service import QueueService
from backend.orchestration.scheduler.enqueue import EventEnqueueService

_T0 = datetime(2026, 5, 6, 16, 0, tzinfo=UTC)


def _service(session: Session) -> EventEnqueueService:
    return EventEnqueueService(QueueService(QueueRepository(session)))


def test_dispatch_enqueues_each_recommendation(session: Session) -> None:
    svc = _service(session)
    event = Event(
        event_id="evt_1",
        event_type=EventType.HIRING_DATA_UPDATED,
        emitted_at=_T0,
        source="scheduler",
        scope={
            "company_region_pairs": [
                {"company_id": "comp_1", "region_id": "greater_boston"}
            ]
        },
    )
    result = svc.dispatch(event)

    assert result.suppressed is False
    job_types = [item.job_type for item in result.enqueued]
    assert job_types == [
        "entry_level_refresh",
        "region_score_recompute",
        "region_output_build",
        "company_output_build",
    ]
    for item in result.enqueued:
        assert item.enqueue_result.outcome == "enqueued"
        assert item.enqueue_result.job.status == "queued"


def test_dispatch_dedupes_via_queue_service(session: Session) -> None:
    svc = _service(session)
    event = Event(
        event_id="evt_1",
        event_type=EventType.NORMALIZATION_INPUTS_UPDATED,
        emitted_at=_T0,
        source="scheduler",
        scope={"region_ids": ["greater_boston"]},
    )
    first = svc.dispatch(event)
    second = svc.dispatch(event)

    assert all(item.enqueue_result.outcome == "enqueued" for item in first.enqueued)
    assert all(item.enqueue_result.outcome == "suppressed" for item in second.enqueued)
    # Same job IDs reused — dedupe lined up across dispatches.
    first_ids = {item.enqueue_result.job.job_id for item in first.enqueued}
    second_ids = {item.enqueue_result.job.job_id for item in second.enqueued}
    assert first_ids == second_ids


def test_no_meaningful_change_skips_enqueue(session: Session) -> None:
    svc = _service(session)
    event = Event(
        event_id="evt_1",
        event_type=EventType.HIRING_DATA_UPDATED,
        emitted_at=_T0,
        source="scheduler",
        scope={
            "company_region_pairs": [
                {"company_id": "comp_1", "region_id": "greater_boston"}
            ]
        },
        no_meaningful_change=True,
    )
    result = svc.dispatch(event)
    assert result.suppressed is True
    assert result.enqueued == ()
    assert result.invalidations == ()


def test_dispatch_returns_invalidation_directives(session: Session) -> None:
    svc = _service(session)
    event = Event(
        event_id="evt_1",
        event_type=EventType.REGION_DEFINITION_CHANGED,
        emitted_at=_T0,
        source="scheduler",
        scope={"region_id": "greater_boston"},
    )
    result = svc.dispatch(event)
    assert any(
        d.target is InvalidationTarget.REGION_SCORE for d in result.invalidations
    )


def test_dispatch_uses_event_driven_trigger_type(session: Session) -> None:
    svc = _service(session)
    event = Event(
        event_id="evt_1",
        event_type=EventType.REGION_ADDED,
        emitted_at=_T0,
        source="admin",
        scope={"region_id": "greater_boston"},
    )
    result = svc.dispatch(event)
    enqueued = result.enqueued[0].enqueue_result.job
    assert enqueued.trigger_type == "event_driven"
    assert enqueued.requested_by == "admin"


def test_dispatch_does_not_run_workers(session: Session) -> None:
    """The adapter only enqueues — every job is left in 'queued' status."""
    svc = _service(session)
    event = Event(
        event_id="evt_1",
        event_type=EventType.COMPARISON_REQUESTED,
        emitted_at=_T0,
        source="scheduler",
        scope={"region_a": "greater_boston", "region_b": "greater_sf"},
    )
    result = svc.dispatch(event)
    for item in result.enqueued:
        assert item.enqueue_result.job.status == "queued"
        assert item.enqueue_result.job.started_at is None
        assert item.enqueue_result.job.completed_at is None
