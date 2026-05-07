"""Presence Mapping job handler — synchronous skeleton.

Body of the ``presence_mapping`` job (``JOB_CONTRACT_SPEC.md`` Job 4). Pure
function shaped ``(request, service) -> response``. No queue, no retry, no
event emission — Slice 14 owns dispatch.

Inputs schema (under ``request.inputs``):

* ``presence_records`` — required, ``list[dict]``. Each entry parses to
  :class:`PresenceDefinition`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from pydantic import ValidationError

from backend.orchestration.jobs.envelopes import JobRequest, JobResponse
from backend.orchestration.jobs.errors import ErrorCode
from backend.orchestration.jobs.types import JobStatus, JobType
from backend.presence.exceptions import (
    DuplicatePresence,
    InvalidPresenceEvidence,
    MissingCompanyForPresence,
    MissingRegionForPresence,
)
from backend.presence.service import PresenceDefinition, PresenceService


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


def handle_presence_mapping(
    request: JobRequest,
    service: PresenceService,
    *,
    now: Callable[[], datetime] = _now,
) -> JobResponse:
    started_at = now()

    if request.job_type is not JobType.PRESENCE_MAPPING:
        return _failure(
            request,
            started_at=started_at,
            completed_at=now(),
            code=ErrorCode.INPUT_VALIDATION_ERROR,
            message=(
                f"unexpected job_type {request.job_type.value!r} "
                "for presence_mapping handler"
            ),
        )

    raw_records = request.inputs.get("presence_records", [])
    if not isinstance(raw_records, list):
        return _failure(
            request,
            started_at=started_at,
            completed_at=now(),
            code=ErrorCode.INPUT_VALIDATION_ERROR,
            message="inputs.presence_records must be a list",
        )

    try:
        definitions = [PresenceDefinition.model_validate(d) for d in raw_records]
    except ValidationError as e:
        return _failure(
            request,
            started_at=started_at,
            completed_at=now(),
            code=ErrorCode.INPUT_VALIDATION_ERROR,
            message=f"invalid presence definitions: {e.error_count()} error(s)",
        )

    created: list[str] = []
    updated: list[str] = []
    unchanged: list[str] = []
    presence_results: list[dict] = []

    for definition in definitions:
        try:
            presence, action = service.upsert_for_mapping(definition)
        except (
            MissingCompanyForPresence,
            MissingRegionForPresence,
            InvalidPresenceEvidence,
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
        except DuplicatePresence as e:  # defensive
            return _failure(
                request,
                started_at=started_at,
                completed_at=now(),
                code=ErrorCode.INTEGRITY_CHECK_FAILED,
                message=f"duplicate presence: {e!s}",
            )

        if action == "created":
            created.append(presence.presence_id)
        elif action == "updated":
            updated.append(presence.presence_id)
        else:
            unchanged.append(presence.presence_id)

        presence_results.append(
            {
                "presence_id": presence.presence_id,
                "company_id": presence.company_id,
                "region_id": presence.region_id,
                "presence_status": presence.presence_status,
                "presence_basis": presence.presence_basis,
                "office_evidence_flag": presence.office_evidence_flag,
                "operations_evidence_flag": presence.operations_evidence_flag,
                "hiring_evidence_flag": presence.hiring_evidence_flag,
                "presence_confidence": presence.presence_confidence,
            }
        )

    metrics = {
        "created_count": len(created),
        "updated_count": len(updated),
        "unchanged_count": len(unchanged),
        "pairs_evaluated": len(presence_results),
        "present_count": sum(
            1 for r in presence_results if r["presence_status"] == "present"
        ),
        "not_present_count": sum(
            1 for r in presence_results if r["presence_status"] == "not_present"
        ),
        "uncertain_count": sum(
            1 for r in presence_results if r["presence_status"] == "uncertain"
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
            "presence_results": presence_results,
            "presence_records_created": created,
            "presence_records_updated": updated,
            "presence_records_unchanged": unchanged,
        },
        metrics=metrics,
    )
