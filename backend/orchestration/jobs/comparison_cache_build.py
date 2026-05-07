"""Comparison Cache Build job handler — synchronous skeleton.

Body of the ``comparison_cache_build`` job (``JOB_CONTRACT_SPEC.md`` Job 10).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from backend.orchestration.jobs.envelopes import JobRequest, JobResponse
from backend.orchestration.jobs.errors import ErrorCode
from backend.orchestration.jobs.types import JobStatus, JobType
from backend.outputs.exceptions import (
    InvalidComparisonInput,
    InvalidOutputInput,
    MissingRegionForOutput,
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


def handle_comparison_cache_build(
    request: JobRequest,
    service: OutputAssemblyService,
    *,
    now: Callable[[], datetime] = _now,
) -> JobResponse:
    started_at = now()

    if request.job_type is not JobType.COMPARISON_CACHE_BUILD:
        return _failure(
            request,
            started_at=started_at,
            completed_at=now(),
            code=ErrorCode.INPUT_VALIDATION_ERROR,
            message=(
                f"unexpected job_type {request.job_type.value!r} "
                "for comparison_cache_build handler"
            ),
        )

    pairs = request.scope.get("comparison_pairs")
    if not isinstance(pairs, list):
        return _failure(
            request,
            started_at=started_at,
            completed_at=now(),
            code=ErrorCode.INPUT_VALIDATION_ERROR,
            message="scope.comparison_pairs must be a list",
        )
    for pair in pairs:
        if not isinstance(pair, list) or len(pair) != 2:
            return _failure(
                request,
                started_at=started_at,
                completed_at=now(),
                code=ErrorCode.INPUT_VALIDATION_ERROR,
                message=(
                    "each comparison pair must be a list of exactly two "
                    "region IDs"
                ),
            )
        if not all(isinstance(rid, str) and rid for rid in pair):
            return _failure(
                request,
                started_at=started_at,
                completed_at=now(),
                code=ErrorCode.INPUT_VALIDATION_ERROR,
                message=(
                    "each comparison pair must contain two non-empty "
                    "string region IDs"
                ),
            )
        if pair[0] == pair[1]:
            return _failure(
                request,
                started_at=started_at,
                completed_at=now(),
                code=ErrorCode.INPUT_VALIDATION_ERROR,
                message=(
                    "each comparison pair must contain two distinct "
                    f"region IDs; got {pair[0]!r} twice"
                ),
            )

    created: list[str] = []
    updated: list[str] = []
    unchanged: list[str] = []
    comparison_results: list[dict] = []

    for pair in pairs:
        a, b = pair
        try:
            result = service.build_comparison(a, b, now=now)
        except InvalidComparisonInput as e:
            return _failure(
                request,
                started_at=started_at,
                completed_at=now(),
                code=ErrorCode.INPUT_VALIDATION_ERROR,
                message=str(e),
            )
        except (MissingRegionForOutput, InvalidOutputInput) as e:
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

        subject_id = result.metadata.subject_id
        if result.action == "created":
            created.append(subject_id)
        elif result.action == "updated":
            updated.append(subject_id)
        else:
            unchanged.append(subject_id)

        comparison_results.append(
            {
                "comparison_id": subject_id,
                "output_id": result.metadata.output_id,
                "output_type": result.metadata.output_type,
                "state": result.metadata.state,
                "version": result.metadata.version,
                "artifact_hash": result.metadata.artifact_hash,
            }
        )

    metrics = {
        "comparisons_built": len(comparison_results),
        "comparisons_changed": len(created) + len(updated),
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
            "comparison_outputs": comparison_results,
            "comparisons_created": created,
            "comparisons_updated": updated,
            "comparisons_unchanged": unchanged,
        },
        metrics=metrics,
    )
