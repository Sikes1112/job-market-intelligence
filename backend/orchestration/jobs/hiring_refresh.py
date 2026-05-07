"""Hiring Refresh job handler — synchronous skeleton.

Body of the ``hiring_refresh`` job (``JOB_CONTRACT_SPEC.md`` Job 5). Pure
function shaped ``(request, service) -> response``. No queue, no retry, no
event emission — Slice 14 owns dispatch.

Inputs schema (under ``request.inputs``):

* ``hiring_records`` — required, ``list[dict]``. Each entry parses to
  :class:`HiringDefinition`.

External hiring source ingestion is **deferred** (Deferred A). Callers
supply pre-shaped snapshots.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from pydantic import ValidationError

from backend.hiring.exceptions import (
    DuplicateHiring,
    InvalidHiringInput,
    InvalidHiringPair,
    MissingPresenceForHiring,
)
from backend.hiring.service import HiringDefinition, HiringService
from backend.orchestration.jobs.envelopes import JobRequest, JobResponse
from backend.orchestration.jobs.errors import ErrorCode
from backend.orchestration.jobs.types import JobStatus, JobType


def _now() -> datetime:
    return datetime.now(UTC)


def _failure(
    request: JobRequest,
    *,
    started_at: datetime,
    completed_at: datetime,
    code: ErrorCode,
    message: str,
    metrics: dict | None = None,
) -> JobResponse:
    return JobResponse(
        job_id=request.job_id,
        job_type=request.job_type,
        status=JobStatus.FAILED,
        error_code=code,
        error_message=message,
        started_at=started_at,
        completed_at=completed_at,
        scope=dict(request.scope),
        metrics=metrics or {},
    )


def handle_hiring_refresh(
    request: JobRequest,
    service: HiringService,
    *,
    now: Callable[[], datetime] = _now,
) -> JobResponse:
    started_at = now()

    if request.job_type is not JobType.HIRING_REFRESH:
        return _failure(
            request,
            started_at=started_at,
            completed_at=now(),
            code=ErrorCode.INPUT_VALIDATION_ERROR,
            message=(
                f"unexpected job_type {request.job_type.value!r} "
                "for hiring_refresh handler"
            ),
        )

    raw_records = request.inputs.get("hiring_records", [])
    if not isinstance(raw_records, list):
        return _failure(
            request,
            started_at=started_at,
            completed_at=now(),
            code=ErrorCode.INPUT_VALIDATION_ERROR,
            message="inputs.hiring_records must be a list",
        )

    try:
        definitions = [HiringDefinition.model_validate(d) for d in raw_records]
    except ValidationError as e:
        return _failure(
            request,
            started_at=started_at,
            completed_at=now(),
            code=ErrorCode.INPUT_VALIDATION_ERROR,
            message=f"invalid hiring definitions: {e.error_count()} error(s)",
        )

    created: list[str] = []
    updated: list[str] = []
    unchanged: list[str] = []
    hiring_results: list[dict] = []

    for definition in definitions:
        try:
            row, action = service.upsert_for_refresh(definition)
        except (
            MissingPresenceForHiring,
            InvalidHiringPair,
            InvalidHiringInput,
        ) as e:
            return _failure(
                request,
                started_at=started_at,
                completed_at=now(),
                code=ErrorCode.INTEGRITY_CHECK_FAILED,
                message=str(e),
                metrics={
                    "created_count": len(created),
                    "updated_count": len(updated),
                    "unchanged_count": len(unchanged),
                },
            )
        except DuplicateHiring as e:  # defensive
            return _failure(
                request,
                started_at=started_at,
                completed_at=now(),
                code=ErrorCode.INTEGRITY_CHECK_FAILED,
                message=f"duplicate hiring: {e!s}",
            )

        if action == "created":
            created.append(row.hiring_id)
        elif action == "updated":
            updated.append(row.hiring_id)
        else:
            unchanged.append(row.hiring_id)

        hiring_results.append(
            {
                "hiring_id": row.hiring_id,
                "company_id": row.company_id,
                "region_id": row.region_id,
                "currently_hiring_flag": row.currently_hiring_flag,
                "active_posting_count_now": row.active_posting_count_now,
                "posting_count_30d": row.posting_count_30d,
                "posting_count_90d": row.posting_count_90d,
                "annualized_trend_signal": row.annualized_trend_signal,
                "seasonal_student_hiring_signal": row.seasonal_student_hiring_signal,
                "hiring_program_count": row.hiring_program_count,
                "hiring_confidence": row.hiring_confidence,
            }
        )

    metrics = {
        "created_count": len(created),
        "updated_count": len(updated),
        "unchanged_count": len(unchanged),
        "pairs_refreshed": len(hiring_results),
        "pairs_changed": len(created) + len(updated),
        "pairs_unchanged": len(unchanged),
    }

    return JobResponse(
        job_id=request.job_id,
        job_type=request.job_type,
        status=JobStatus.SUCCEEDED,
        started_at=started_at,
        completed_at=now(),
        scope=dict(request.scope),
        outputs={
            "hiring_results": hiring_results,
            "hiring_records_created": created,
            "hiring_records_updated": updated,
            "hiring_records_unchanged": unchanged,
        },
        metrics=metrics,
    )
