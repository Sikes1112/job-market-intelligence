"""Bridge between the Slice 4 :class:`JobRequest` / :class:`JobResponse`
contracts and the Slice 2 :class:`Job` ORM table.

This is the first slice allowed to translate between the wire envelope and
the persisted row. Both sides remain authoritative for their own concerns:

* The Pydantic envelopes own input validation and cross-field semantics.
* The ORM table owns persistent state, status, attempt counters, hashes,
  and timestamps.

The bridge does not modify upstream canonical truth. It only reads/writes
fields on the ``jobs`` table.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.orchestration.jobs.envelopes import JobRequest, JobResponse
from backend.orchestration.jobs.errors import ErrorCode
from backend.orchestration.jobs.models import Job
from backend.orchestration.jobs.types import (
    JobStatus,
    JobType,
    Priority,
    TriggerType,
)


def _ensure_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def request_to_job_kwargs(
    request: JobRequest,
    *,
    queue_name: str,
    dedupe_key: str,
    scope_hash_value: str,
    initial_status: str = JobStatus.QUEUED.value,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Project a :class:`JobRequest` into kwargs suitable for ``Job(**kwargs)``."""
    return {
        "job_id": request.job_id,
        "job_type": request.job_type.value,
        "queue_name": queue_name,
        "status": initial_status,
        "priority": request.priority.value,
        "trigger_type": request.trigger_type.value,
        "requested_by": request.requested_by,
        "scope": dict(request.scope),
        "scope_hash": scope_hash_value,
        "dedupe_key": dedupe_key,
        "inputs": dict(request.inputs),
        "options": dict(request.options),
        "dependency_refs": list(request.dependency_refs),
        "retry_count": 0,
        "max_retries": max_retries,
    }


def job_to_request(job: Job) -> JobRequest:
    """Re-hydrate a :class:`JobRequest` from a persisted ``Job`` row."""
    return JobRequest(
        job_id=job.job_id,
        job_type=JobType(job.job_type),
        trigger_type=(
            TriggerType(job.trigger_type)
            if job.trigger_type
            else TriggerType.SCHEDULED
        ),
        requested_by=job.requested_by or "system",
        priority=Priority(job.priority),
        request_time=_ensure_aware(job.created_at) or datetime.now(UTC),
        scope=dict(job.scope or {}),
        inputs=dict(job.inputs or {}),
        options=dict(job.options or {}),
        dependency_refs=list(job.dependency_refs or []),
    )


def apply_response_to_job(job: Job, response: JobResponse) -> None:
    """Write ``response`` outcome fields back to the ``Job`` row.

    This is the only mutation the runtime makes to the jobs table per
    response. Downstream-trigger recommendations are intentionally **not**
    persisted here — they remain runtime data and will be consumed by
    Slice 15 (event router).
    """
    job.status = response.status.value
    job.started_at = _ensure_aware(response.started_at)
    job.completed_at = _ensure_aware(response.completed_at)
    job.input_hash = response.input_hash
    job.output_hash = response.output_hash
    if response.error_code is not None:
        job.error_code = response.error_code.value
        job.error_message = response.error_message
    else:
        job.error_code = None
        job.error_message = None
    if response.warnings:
        job.warnings = [w.model_dump(mode="json") for w in response.warnings]
    else:
        job.warnings = None


def make_failure_response(
    request: JobRequest,
    *,
    code: ErrorCode,
    message: str,
    started_at: datetime,
    completed_at: datetime,
) -> JobResponse:
    """Helper for runtime-side failures (dependency missing, no handler, etc.)."""
    return JobResponse(
        job_id=request.job_id,
        job_type=request.job_type,
        status=JobStatus.FAILED,
        error_code=code,
        error_message=message,
        started_at=_ensure_aware(started_at),
        completed_at=_ensure_aware(completed_at),
        scope=dict(request.scope),
    )
