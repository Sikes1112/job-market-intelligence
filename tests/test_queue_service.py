from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from backend.orchestration.jobs.envelopes import JobRequest
from backend.orchestration.jobs.types import (
    JobStatus,
    JobType,
    Priority,
    TriggerType,
)
from backend.orchestration.queues.exceptions import InvalidQueueName
from backend.orchestration.queues.repository import QueueRepository
from backend.orchestration.queues.service import QueueService
from backend.orchestration.queues.types import QueueName


def _service(session: Session) -> QueueService:
    return QueueService(QueueRepository(session))


def _request(**overrides) -> JobRequest:
    payload = dict(
        job_id="job_geo_001",
        job_type=JobType.GEOGRAPHY_BUILD,
        trigger_type=TriggerType.MANUAL,
        requested_by="admin",
        priority=Priority.HIGH,
        request_time=datetime(2026, 5, 6, 16, 0, tzinfo=UTC),
        scope={"region_ids": ["greater_boston"]},
        inputs={},
        options={},
        dependency_refs=[],
    )
    payload.update(overrides)
    return JobRequest(**payload)


def test_enqueue_persists_job_with_default_queue(session: Session) -> None:
    svc = _service(session)
    result = svc.enqueue(_request())
    assert result.outcome == "enqueued"
    assert result.job.queue_name == "foundational"
    assert result.job.status == JobStatus.QUEUED.value
    assert result.job.dedupe_key is not None
    assert result.job.scope_hash is not None


def test_enqueue_respects_explicit_queue_name(session: Session) -> None:
    svc = _service(session)
    result = svc.enqueue(
        _request(),
        queue_name=QueueName.REFRESH,
    )
    assert result.job.queue_name == "refresh"


def test_enqueue_accepts_string_queue_name(session: Session) -> None:
    svc = _service(session)
    result = svc.enqueue(_request(), queue_name="output")
    assert result.job.queue_name == "output"


def test_enqueue_rejects_invalid_queue_name(session: Session) -> None:
    svc = _service(session)
    with pytest.raises(InvalidQueueName):
        svc.enqueue(_request(), queue_name="not_a_queue")


def test_enqueue_routes_per_job_type(session: Session) -> None:
    svc = _service(session)
    refresh = svc.enqueue(
        _request(
            job_id="hir_001",
            job_type=JobType.HIRING_REFRESH,
            trigger_type=TriggerType.SCHEDULED,
            requested_by="system",
            priority=Priority.NORMAL,
            scope={"region_ids": ["greater_sf"]},
        )
    )
    assert refresh.job.queue_name == "refresh"

    output = svc.enqueue(
        _request(
            job_id="out_001",
            job_type=JobType.REGION_OUTPUT_BUILD,
            trigger_type=TriggerType.EVENT_DRIVEN,
            requested_by="system",
            priority=Priority.NORMAL,
            scope={"region_ids": ["greater_boston"]},
        )
    )
    assert output.job.queue_name == "output"


def test_enqueue_dedupes_active_jobs(session: Session) -> None:
    svc = _service(session)
    first = svc.enqueue(_request())
    duplicate = svc.enqueue(_request(job_id="different_id"))
    assert duplicate.outcome == "suppressed"
    assert duplicate.job.job_id == first.job.job_id


def test_enqueue_does_not_dedupe_against_terminal_jobs(session: Session) -> None:
    """A succeeded/failed/cancelled job should NOT block a new enqueue with
    the same dedupe key — the queue is only "active" when status is queued
    or running."""
    svc = _service(session)
    first = svc.enqueue(_request())
    # Mark the existing job as succeeded (terminal).
    first.job.status = JobStatus.SUCCEEDED.value
    session.flush()

    # New enqueue with same scope should NOT be suppressed.
    second = svc.enqueue(_request(job_id="job_geo_002"))
    assert second.outcome == "enqueued"
    assert second.job.job_id == "job_geo_002"


def test_enqueue_with_explicit_dedupe_key(session: Session) -> None:
    svc = _service(session)
    a = svc.enqueue(_request(), dedupe_key="custom_key_a")
    b = svc.enqueue(
        _request(job_id="job_geo_002", scope={"region_ids": ["different"]}),
        dedupe_key="custom_key_a",
    )
    # Same dedupe key → suppressed even though scope differs.
    assert b.outcome == "suppressed"
    assert b.job.job_id == a.job.job_id


def test_enqueue_preserves_dependency_refs(session: Session) -> None:
    svc = _service(session)
    result = svc.enqueue(
        _request(dependency_refs=["company_universe_v45", "presence_v33"])
    )
    assert result.job.dependency_refs == [
        "company_universe_v45",
        "presence_v33",
    ]


def test_get_returns_persisted_job(session: Session) -> None:
    svc = _service(session)
    enqueued = svc.enqueue(_request())
    assert svc.get(enqueued.job.job_id) is enqueued.job
    assert svc.get("ghost") is None
