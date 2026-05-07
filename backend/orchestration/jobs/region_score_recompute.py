"""Region Score Recompute job handler — synchronous skeleton.

Body of the ``region_score_recompute`` job (``JOB_CONTRACT_SPEC.md`` Job 7).
Pure function shaped ``(request, service) -> response``. No queue, no
retry, no event emission — Slice 14 owns dispatch.

Inputs schema (under ``request.scope``):

* ``region_ids`` — required, ``list[str]``. Each region is recomputed in
  order; the handler stops on the first integrity failure (matching the
  conservative pattern from prior slices).

The handler does not require explicit hiring/entry-level data in
``inputs`` — scoring reads stored canonical truth via the service.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from backend.orchestration.jobs.envelopes import JobRequest, JobResponse
from backend.orchestration.jobs.errors import ErrorCode
from backend.orchestration.jobs.types import JobStatus, JobType
from backend.scoring.exceptions import (
    InvalidScoringInput,
    MissingRegionForScoring,
)
from backend.scoring.service import RegionScoringService


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


def handle_region_score_recompute(
    request: JobRequest,
    service: RegionScoringService,
    *,
    now: Callable[[], datetime] = _now,
) -> JobResponse:
    started_at = now()

    if request.job_type is not JobType.REGION_SCORE_RECOMPUTE:
        return _failure(
            request,
            started_at=started_at,
            completed_at=now(),
            code=ErrorCode.INPUT_VALIDATION_ERROR,
            message=(
                f"unexpected job_type {request.job_type.value!r} "
                "for region_score_recompute handler"
            ),
        )

    region_ids = request.scope.get("region_ids")
    if not isinstance(region_ids, list):
        return _failure(
            request,
            started_at=started_at,
            completed_at=now(),
            code=ErrorCode.INPUT_VALIDATION_ERROR,
            message="scope.region_ids must be a list",
        )

    if not all(isinstance(rid, str) and rid for rid in region_ids):
        return _failure(
            request,
            started_at=started_at,
            completed_at=now(),
            code=ErrorCode.INPUT_VALIDATION_ERROR,
            message="scope.region_ids must contain non-empty strings",
        )

    created: list[str] = []
    updated: list[str] = []
    unchanged: list[str] = []
    region_results: list[dict] = []
    warnings_collected: list[dict] = []

    for region_id in region_ids:
        try:
            row, action = service.upsert_for_recompute(region_id)
        except (MissingRegionForScoring, InvalidScoringInput) as e:
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

        if action == "created":
            created.append(region_id)
        elif action == "updated":
            updated.append(region_id)
        else:
            unchanged.append(region_id)

        region_results.append(
            {
                "region_id": row.region_id,
                "region_score_id": row.region_score_id,
                "structural_ecosystem_score": row.structural_ecosystem_score,
                "live_market_score": row.live_market_score,
                "objective_opportunity_score": row.objective_opportunity_score,
                "raw_total_score": row.raw_total_score,
                "general_density_score": row.general_density_score,
                "tech_market_density_score": row.tech_market_density_score,
                "early_career_accessibility_score": row.early_career_accessibility_score,
                "score_ruleset_version": row.score_ruleset_version,
                "version": row.version,
                "state": row.state,
            }
        )

    metrics = {
        "regions_recomputed": len(region_results),
        "regions_changed": len(created) + len(updated),
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
            "region_scores": region_results,
            "regions_created": created,
            "regions_updated": updated,
            "regions_unchanged": unchanged,
            "warnings_by_region": warnings_collected,
        },
        metrics=metrics,
    )
