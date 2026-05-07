"""Entry-Level Refresh job handler — synchronous skeleton.

Body of the ``entry_level_refresh`` job (``JOB_CONTRACT_SPEC.md`` Job 6).
Pure function shaped ``(request, service) -> response``. No queue, no
retry, no event emission — Slice 14 owns dispatch.

Inputs schema (under ``request.inputs``):

* ``entry_level_records`` — required, ``list[dict]``. Each entry parses to
  :class:`EntryLevelDefinition`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from pydantic import ValidationError

from backend.entry_level.exceptions import (
    DuplicateEntryLevel,
    InvalidEntryLevelInput,
    MissingHiringForEntryLevel,
)
from backend.entry_level.service import EntryLevelDefinition, EntryLevelService
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


def handle_entry_level_refresh(
    request: JobRequest,
    service: EntryLevelService,
    *,
    now: Callable[[], datetime] = _now,
) -> JobResponse:
    started_at = now()

    if request.job_type is not JobType.ENTRY_LEVEL_REFRESH:
        return _failure(
            request,
            started_at=started_at,
            completed_at=now(),
            code=ErrorCode.INPUT_VALIDATION_ERROR,
            message=(
                f"unexpected job_type {request.job_type.value!r} "
                "for entry_level_refresh handler"
            ),
        )

    raw_records = request.inputs.get("entry_level_records", [])
    if not isinstance(raw_records, list):
        return _failure(
            request,
            started_at=started_at,
            completed_at=now(),
            code=ErrorCode.INPUT_VALIDATION_ERROR,
            message="inputs.entry_level_records must be a list",
        )

    try:
        definitions = [EntryLevelDefinition.model_validate(d) for d in raw_records]
    except ValidationError as e:
        return _failure(
            request,
            started_at=started_at,
            completed_at=now(),
            code=ErrorCode.INPUT_VALIDATION_ERROR,
            message=f"invalid entry-level definitions: {e.error_count()} error(s)",
        )

    created: list[str] = []
    updated: list[str] = []
    unchanged: list[str] = []
    entry_level_results: list[dict] = []

    for definition in definitions:
        try:
            row, action = service.upsert_for_refresh(definition)
        except (
            MissingHiringForEntryLevel,
            InvalidEntryLevelInput,
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
        except DuplicateEntryLevel as e:  # defensive
            return _failure(
                request,
                started_at=started_at,
                completed_at=now(),
                code=ErrorCode.INTEGRITY_CHECK_FAILED,
                message=f"duplicate entry-level: {e!s}",
            )

        if action == "created":
            created.append(row.entry_level_id)
        elif action == "updated":
            updated.append(row.entry_level_id)
        else:
            unchanged.append(row.entry_level_id)

        entry_level_results.append(
            {
                "entry_level_id": row.entry_level_id,
                "company_id": row.company_id,
                "region_id": row.region_id,
                "internship_count": row.internship_count,
                "coop_count": row.coop_count,
                "entry_level_full_time_count": row.entry_level_full_time_count,
                "formal_early_career_program_flag": row.formal_early_career_program_flag,
                "student_season_recurrence_signal": row.student_season_recurrence_signal,
                "entry_level_access_score": row.entry_level_access_score,
                "entry_level_confidence": row.entry_level_confidence,
            }
        )

    metrics = {
        "created_count": len(created),
        "updated_count": len(updated),
        "unchanged_count": len(unchanged),
        "pairs_evaluated": len(entry_level_results),
        "pairs_with_entry_level_access": sum(
            1
            for r in entry_level_results
            if r["entry_level_access_score"] is not None
            and r["entry_level_access_score"] > 0
        ),
    }

    return JobResponse(
        job_id=request.job_id,
        job_type=request.job_type,
        status=JobStatus.SUCCEEDED,
        started_at=started_at,
        completed_at=now(),
        scope=dict(request.scope),
        outputs={
            "entry_level_results": entry_level_results,
            "entry_level_records_created": created,
            "entry_level_records_updated": updated,
            "entry_level_records_unchanged": unchanged,
        },
        metrics=metrics,
    )
