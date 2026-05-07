"""Tests for the JobRequest ↔ Job ORM ↔ JobResponse bridge."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from backend.orchestration.jobs.envelopes import JobRequest, JobResponse
from backend.orchestration.jobs.errors import (
    ErrorCode,
    JobWarning,
    WarningSeverity,
)
from backend.orchestration.jobs.models import Job
from backend.orchestration.jobs.storage import (
    apply_response_to_job,
    job_to_request,
    make_failure_response,
    request_to_job_kwargs,
)
from backend.orchestration.jobs.types import (
    JobStatus,
    JobType,
    Priority,
    TriggerType,
)


def _request(**overrides) -> JobRequest:
    payload = dict(
        job_id="job_geo_001",
        job_type=JobType.GEOGRAPHY_BUILD,
        trigger_type=TriggerType.MANUAL,
        requested_by="admin",
        priority=Priority.HIGH,
        request_time=datetime(2026, 5, 6, 16, 0, tzinfo=UTC),
        scope={"region_ids": ["greater_boston"]},
        inputs={"region_definitions": []},
        options={"validate_hierarchy": True},
        dependency_refs=["geo_v1"],
    )
    payload.update(overrides)
    return JobRequest(**payload)


def test_request_to_job_kwargs_round_trips_to_orm(session: Session) -> None:
    request = _request()
    kwargs = request_to_job_kwargs(
        request,
        queue_name="foundational",
        dedupe_key="dedupe-1",
        scope_hash_value="hash-1",
    )
    job = Job(**kwargs)
    session.add(job)
    session.flush()

    fetched = session.get(Job, "job_geo_001")
    assert fetched is not None
    assert fetched.job_type == "geography_build"
    assert fetched.queue_name == "foundational"
    assert fetched.status == "queued"
    assert fetched.priority == "high"
    assert fetched.scope == {"region_ids": ["greater_boston"]}
    assert fetched.dependency_refs == ["geo_v1"]
    assert fetched.dedupe_key == "dedupe-1"
    assert fetched.retry_count == 0
    assert fetched.max_retries == 3


def test_job_to_request_rehydrates_envelope(session: Session) -> None:
    request = _request()
    kwargs = request_to_job_kwargs(
        request,
        queue_name="foundational",
        dedupe_key="dedupe-1",
        scope_hash_value="hash-1",
    )
    job = Job(**kwargs)
    session.add(job)
    session.flush()
    session.refresh(job)

    rehydrated = job_to_request(job)
    assert rehydrated.job_id == request.job_id
    assert rehydrated.job_type is JobType.GEOGRAPHY_BUILD
    assert rehydrated.trigger_type is TriggerType.MANUAL
    assert rehydrated.priority is Priority.HIGH
    assert rehydrated.scope == request.scope
    assert rehydrated.inputs == request.inputs
    assert rehydrated.dependency_refs == request.dependency_refs


def test_apply_success_response_clears_error_fields(session: Session) -> None:
    request = _request()
    kwargs = request_to_job_kwargs(
        request,
        queue_name="foundational",
        dedupe_key="dedupe-1",
        scope_hash_value="h",
    )
    job = Job(**kwargs)
    session.add(job)
    session.flush()
    job.error_code = "TIMEOUT"  # simulate a prior failed attempt
    job.error_message = "old message"

    response = JobResponse(
        job_id=request.job_id,
        job_type=request.job_type,
        status=JobStatus.SUCCEEDED,
        started_at=datetime(2026, 5, 6, 16, 0, tzinfo=UTC),
        completed_at=datetime(2026, 5, 6, 16, 0, 30, tzinfo=UTC),
        outputs={"created": 1},
    )
    apply_response_to_job(job, response)

    assert job.status == "succeeded"
    assert job.error_code is None
    assert job.error_message is None


def test_apply_failed_response_writes_error_fields(session: Session) -> None:
    request = _request()
    kwargs = request_to_job_kwargs(
        request,
        queue_name="foundational",
        dedupe_key="dedupe-1",
        scope_hash_value="h",
    )
    job = Job(**kwargs)
    session.add(job)
    session.flush()

    response = JobResponse(
        job_id=request.job_id,
        job_type=request.job_type,
        status=JobStatus.FAILED,
        error_code=ErrorCode.SOURCE_UNAVAILABLE,
        error_message="hiring source 503",
        started_at=datetime(2026, 5, 6, 16, 0, tzinfo=UTC),
        completed_at=datetime(2026, 5, 6, 16, 0, 30, tzinfo=UTC),
    )
    apply_response_to_job(job, response)
    assert job.status == "failed"
    assert job.error_code == "SOURCE_UNAVAILABLE"
    assert job.error_message == "hiring source 503"


def test_apply_warnings_serializes_deterministically(session: Session) -> None:
    request = _request()
    kwargs = request_to_job_kwargs(
        request, queue_name="foundational", dedupe_key="d", scope_hash_value="h"
    )
    job = Job(**kwargs)
    session.add(job)
    session.flush()

    warning = JobWarning(
        warning_code="LOW_CONFIDENCE",
        severity=WarningSeverity.LOW,
        scope_type="region",
        scope_ref="greater_boston",
        message="thin data",
    )
    response = JobResponse(
        job_id=request.job_id,
        job_type=request.job_type,
        status=JobStatus.SUCCEEDED_WITH_WARNINGS,
        warnings=[warning],
        started_at=datetime(2026, 5, 6, 16, 0, tzinfo=UTC),
        completed_at=datetime(2026, 5, 6, 16, 0, 5, tzinfo=UTC),
    )
    apply_response_to_job(job, response)

    assert isinstance(job.warnings, list)
    assert job.warnings[0]["warning_code"] == "LOW_CONFIDENCE"
    assert job.warnings[0]["severity"] == "low"
    assert job.warnings[0]["scope_ref"] == "greater_boston"


def test_make_failure_response_returns_valid_envelope() -> None:
    request = _request()
    started = datetime(2026, 5, 6, 16, 0, tzinfo=UTC)
    completed = started + timedelta(seconds=1)
    response = make_failure_response(
        request,
        code=ErrorCode.DEPENDENCY_MISSING,
        message="presence_v33 not found",
        started_at=started,
        completed_at=completed,
    )
    assert response.status is JobStatus.FAILED
    assert response.error_code is ErrorCode.DEPENDENCY_MISSING
    assert response.error_message == "presence_v33 not found"
