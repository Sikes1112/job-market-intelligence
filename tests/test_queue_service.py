from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.geography.models import Region
from backend.orchestration.jobs.envelopes import JobRequest
from backend.orchestration.jobs.models import Job
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
from backend.shared.db import create_all, make_engine, make_session_factory


def _service(session: Session) -> QueueService:
    return QueueService(QueueRepository(session))


class _RaceyQueueRepository(QueueRepository):
    """Simulate a second writer winning between app dedupe check and flush."""

    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self._find_calls = 0

    def find_active_by_dedupe_key(self, dedupe_key: str) -> Job | None:
        self._find_calls += 1
        if self._find_calls == 1:
            return None
        return super().find_active_by_dedupe_key(dedupe_key)


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


def _raw_job(*, job_id: str, status: JobStatus, dedupe_key: str) -> Job:
    return Job(
        job_id=job_id,
        job_type=JobType.GEOGRAPHY_BUILD.value,
        queue_name=QueueName.FOUNDATIONAL.value,
        status=status.value,
        priority=Priority.NORMAL.value,
        trigger_type=TriggerType.MANUAL.value,
        requested_by="test",
        scope={},
        scope_hash="hash",
        dedupe_key=dedupe_key,
        inputs={},
        options={},
        dependency_refs=[],
    )


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


def test_database_rejects_duplicate_active_dedupe_keys(session: Session) -> None:
    session.add(
        _raw_job(job_id="job_active_1", status=JobStatus.QUEUED, dedupe_key="same")
    )
    session.flush()
    session.add(
        _raw_job(job_id="job_active_2", status=JobStatus.RUNNING, dedupe_key="same")
    )

    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_enqueue_integrity_conflict_preserves_outer_session_work(
    session: Session,
) -> None:
    first = _service(session).enqueue(_request(), dedupe_key="race")
    region = Region(
        region_id="outer_tx_region",
        region_name="outer_tx_region",
        display_name="Outer Tx Region",
        region_type="greater_region",
    )
    session.add(region)
    session.flush()

    racey = QueueService(_RaceyQueueRepository(session))
    duplicate = racey.enqueue(
        _request(job_id="job_geo_002"),
        dedupe_key="race",
    )

    assert duplicate.outcome == "suppressed"
    assert duplicate.job.job_id == first.job.job_id
    assert session.get(Region, "outer_tx_region") is region
    assert session.get(Job, "job_geo_002") is None


def test_enqueue_dedupes_same_active_key_across_independent_sessions(
    tmp_path,
) -> None:
    """Portable two-session coverage.

    The committed-session path proves independent callers converge on one
    active job. The simulated conflict test above covers the race window where
    the DB unique constraint fires after the app-level check.
    """
    db_path = tmp_path / "queue_dedupe.db"
    engine = make_engine(f"sqlite:///{db_path}")
    create_all(engine)
    factory = make_session_factory(engine)
    session_a = factory()
    session_b = factory()
    verify_session = factory()
    try:
        first = QueueService(QueueRepository(session_a)).enqueue(
            _request(job_id="job_geo_001"), dedupe_key="shared"
        )
        assert first.outcome == "enqueued"
        session_a.commit()

        region = Region(
            region_id="independent_session_region",
            region_name="independent_session_region",
            display_name="Independent Session Region",
            region_type="greater_region",
        )
        session_b.add(region)
        session_b.flush()

        second = QueueService(QueueRepository(session_b)).enqueue(
            _request(job_id="job_geo_002"), dedupe_key="shared"
        )

        assert second.outcome == "suppressed"
        assert second.job.job_id == first.job.job_id
        assert session_b.get(Region, "independent_session_region") is region
        session_b.commit()

        stmt = select(Job).where(
            Job.dedupe_key == "shared",
            Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
        )
        active_jobs = list(verify_session.execute(stmt).scalars())
        assert [job.job_id for job in active_jobs] == ["job_geo_001"]
    finally:
        session_a.close()
        session_b.close()
        verify_session.close()
        engine.dispose()


def test_database_allows_reenqueue_after_terminal_dedupe_key(
    session: Session,
) -> None:
    session.add(
        _raw_job(job_id="job_done", status=JobStatus.SUCCEEDED, dedupe_key="same")
    )
    session.flush()
    session.add(
        _raw_job(job_id="job_new", status=JobStatus.QUEUED, dedupe_key="same")
    )
    session.flush()

    assert session.get(Job, "job_new") is not None
