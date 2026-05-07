"""Company Output Build job handler — synchronous skeleton.

Body of the ``company_output_build`` job (``JOB_CONTRACT_SPEC.md`` Job 9).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from backend.orchestration.jobs.envelopes import JobRequest, JobResponse
from backend.orchestration.jobs.errors import ErrorCode
from backend.orchestration.jobs.types import JobStatus, JobType
from backend.outputs.exceptions import (
    InvalidOutputInput,
    MissingCompanyForOutput,
)
from backend.outputs.service import OutputAssemblyService


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


def handle_company_output_build(
    request: JobRequest,
    service: OutputAssemblyService,
    *,
    now: Callable[[], datetime] = _now,
) -> JobResponse:
    started_at = now()

    if request.job_type is not JobType.COMPANY_OUTPUT_BUILD:
        return _failure(
            request,
            started_at=started_at,
            completed_at=now(),
            code=ErrorCode.INPUT_VALIDATION_ERROR,
            message=(
                f"unexpected job_type {request.job_type.value!r} "
                "for company_output_build handler"
            ),
        )

    company_ids = request.scope.get("company_ids")
    if not isinstance(company_ids, list):
        return _failure(
            request,
            started_at=started_at,
            completed_at=now(),
            code=ErrorCode.INPUT_VALIDATION_ERROR,
            message="scope.company_ids must be a list",
        )
    if not all(isinstance(cid, str) and cid for cid in company_ids):
        return _failure(
            request,
            started_at=started_at,
            completed_at=now(),
            code=ErrorCode.INPUT_VALIDATION_ERROR,
            message="scope.company_ids must contain non-empty strings",
        )

    created: list[str] = []
    updated: list[str] = []
    unchanged: list[str] = []
    company_results: list[dict] = []

    for company_id in company_ids:
        try:
            result = service.build_company(company_id, now=now)
        except (MissingCompanyForOutput, InvalidOutputInput) as e:
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

        if result.action == "created":
            created.append(company_id)
        elif result.action == "updated":
            updated.append(company_id)
        else:
            unchanged.append(company_id)

        company_results.append(
            {
                "company_id": company_id,
                "output_id": result.metadata.output_id,
                "output_type": result.metadata.output_type,
                "subject_id": result.metadata.subject_id,
                "state": result.metadata.state,
                "version": result.metadata.version,
                "artifact_hash": result.metadata.artifact_hash,
            }
        )

    metrics = {
        "company_outputs_built": len(company_results),
        "companies_changed": len(created) + len(updated),
        "created_count": len(created),
        "updated_count": len(updated),
        "unchanged_count": len(unchanged),
    }

    return JobResponse(
        job_id=request.job_id,
        job_type=request.job_type,
        status=JobStatus.SUCCEEDED,
        started_at=started_at,
        completed_at=now(),
        scope=dict(request.scope),
        outputs={
            "company_outputs": company_results,
            "companies_created": created,
            "companies_updated": updated,
            "companies_unchanged": unchanged,
        },
        metrics=metrics,
    )
