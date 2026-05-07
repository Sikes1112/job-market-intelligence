"""Geography Build job handler — synchronous skeleton.

This is the body of the ``geography_build`` job (``JOB_CONTRACT_SPEC.md`` Job
1). It takes a :class:`JobRequest`, performs the build via
:class:`GeographyService`, and returns a populated :class:`JobResponse`.

What this is **not**:

* a worker — there is no event loop, no queue subscription, no retry runner;
* a dispatcher — nothing here decides *whether* to run the job. Slice 14 owns
  dispatch.

The handler is pure-function shaped: ``(request, service) -> response``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from pydantic import ValidationError

from backend.geography.exceptions import (
    DuplicateRegion,
    InvalidRegionHierarchy,
)
from backend.geography.service import GeographyService, RegionDefinition
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


def handle_geography_build(
    request: JobRequest,
    service: GeographyService,
    *,
    now: Callable[[], datetime] = _now,
) -> JobResponse:
    started_at = now()

    if request.job_type is not JobType.GEOGRAPHY_BUILD:
        return _failure(
            request,
            started_at=started_at,
            completed_at=now(),
            code=ErrorCode.INPUT_VALIDATION_ERROR,
            message=(
                f"unexpected job_type {request.job_type.value!r} "
                "for geography_build handler"
            ),
        )

    raw_defs = request.inputs.get("region_definitions", [])
    if not isinstance(raw_defs, list):
        return _failure(
            request,
            started_at=started_at,
            completed_at=now(),
            code=ErrorCode.INPUT_VALIDATION_ERROR,
            message="inputs.region_definitions must be a list",
        )

    try:
        definitions = [RegionDefinition.model_validate(d) for d in raw_defs]
    except ValidationError as e:
        return _failure(
            request,
            started_at=started_at,
            completed_at=now(),
            code=ErrorCode.INPUT_VALIDATION_ERROR,
            message=f"invalid region definitions: {e.error_count()} error(s)",
        )

    created: list[str] = []
    updated: list[str] = []
    unchanged: list[str] = []

    for definition in definitions:
        try:
            region, action = service.upsert_for_build(definition)
        except InvalidRegionHierarchy as e:
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
        except DuplicateRegion as e:  # defensive — upsert_for_build avoids this
            return _failure(
                request,
                started_at=started_at,
                completed_at=now(),
                code=ErrorCode.INTEGRITY_CHECK_FAILED,
                message=f"duplicate region {e!s}",
            )
        if action == "created":
            created.append(region.region_id)
        elif action == "updated":
            updated.append(region.region_id)
        else:
            unchanged.append(region.region_id)

    return JobResponse(
        job_id=request.job_id,
        job_type=request.job_type,
        status=JobStatus.SUCCEEDED,
        started_at=started_at,
        completed_at=now(),
        scope=dict(request.scope),
        outputs={
            "geography_objects_created": created,
            "geography_objects_updated": updated,
            "geography_objects_unchanged": unchanged,
        },
        metrics={
            "created_count": len(created),
            "updated_count": len(updated),
            "unchanged_count": len(unchanged),
        },
    )
