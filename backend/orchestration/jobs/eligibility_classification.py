"""Eligibility & Classification job handler — synchronous skeleton.

Body of the ``eligibility_classification`` job (``JOB_CONTRACT_SPEC.md`` Job
3). Like Slice 5's geography handler, this is a pure function shaped
``(request, service) -> response``. No queue, no retry, no event emission —
Slice 14 owns dispatch.

Inputs schema (under ``request.inputs``):

* ``company_records`` — required, ``list[dict]``. Each entry parses to
  :class:`CompanyDefinition`.

External candidate-source ingestion is **deferred** (Deferred A). Callers
are expected to supply pre-shaped definitions.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from pydantic import ValidationError

from backend.companies.exceptions import (
    DuplicateCompany,
    InvalidClassification,
    InvalidOverride,
)
from backend.companies.service import CompanyDefinition, CompanyService
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


def handle_eligibility_classification(
    request: JobRequest,
    service: CompanyService,
    *,
    now: Callable[[], datetime] = _now,
) -> JobResponse:
    started_at = now()

    if request.job_type is not JobType.ELIGIBILITY_CLASSIFICATION:
        return _failure(
            request,
            started_at=started_at,
            completed_at=now(),
            code=ErrorCode.INPUT_VALIDATION_ERROR,
            message=(
                f"unexpected job_type {request.job_type.value!r} "
                "for eligibility_classification handler"
            ),
        )

    raw_records = request.inputs.get("company_records", [])
    if not isinstance(raw_records, list):
        return _failure(
            request,
            started_at=started_at,
            completed_at=now(),
            code=ErrorCode.INPUT_VALIDATION_ERROR,
            message="inputs.company_records must be a list",
        )

    try:
        definitions = [CompanyDefinition.model_validate(d) for d in raw_records]
    except ValidationError as e:
        return _failure(
            request,
            started_at=started_at,
            completed_at=now(),
            code=ErrorCode.INPUT_VALIDATION_ERROR,
            message=f"invalid company definitions: {e.error_count()} error(s)",
        )

    created: list[str] = []
    updated: list[str] = []
    unchanged: list[str] = []
    company_results: list[dict] = []

    for definition in definitions:
        try:
            company, action = service.upsert_for_classify(definition)
        except (InvalidClassification, InvalidOverride) as e:
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
        except DuplicateCompany as e:  # defensive — upsert avoids this
            return _failure(
                request,
                started_at=started_at,
                completed_at=now(),
                code=ErrorCode.INTEGRITY_CHECK_FAILED,
                message=f"duplicate company: {e!s}",
            )

        if action == "created":
            created.append(company.company_id)
        elif action == "updated":
            updated.append(company.company_id)
        else:
            unchanged.append(company.company_id)

        company_results.append(
            {
                "company_id": company.company_id,
                "company_name": company.company_name,
                "eligibility_status": company.eligibility_status,
                "eligibility_score": company.eligibility_score,
                "eligibility_override_flag": company.eligibility_override_flag,
                "classification_confidence": company.classification_confidence,
                "is_major_tech": company.is_major_tech,
                "major_tech_score": company.major_tech_score,
                "is_mag7": company.is_mag7,
            }
        )

    metrics = {
        "created_count": len(created),
        "updated_count": len(updated),
        "unchanged_count": len(unchanged),
        "eligible_count": sum(
            1 for r in company_results if r["eligibility_status"] == "eligible"
        ),
        "ineligible_count": sum(
            1 for r in company_results if r["eligibility_status"] == "ineligible"
        ),
        "override_included_count": sum(
            1
            for r in company_results
            if r["eligibility_status"] == "override_included"
        ),
        "major_tech_count": sum(1 for r in company_results if r["is_major_tech"]),
    }

    return JobResponse(
        job_id=request.job_id,
        job_type=request.job_type,
        status=JobStatus.SUCCEEDED,
        started_at=started_at,
        completed_at=now(),
        scope=dict(request.scope),
        outputs={
            "company_results": company_results,
            "company_records_created": created,
            "company_records_updated": updated,
            "company_records_unchanged": unchanged,
        },
        metrics=metrics,
    )
