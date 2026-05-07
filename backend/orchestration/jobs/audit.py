"""Audit job handler — synchronous skeleton.

Body of the ``audit`` job (``JOB_CONTRACT_SPEC.md`` Job 13). Returns the
audit report in ``JobResponse.outputs.audit_report``. The handler maps
findings into ``JobWarning`` entries so the standard envelope captures
severities; the full structured report is in ``outputs``.

The handler is **not** registered with Slice 14's ``default_registry()``
— per the slice prompt's conservative-default guidance, audit remains
caller-driven for MVP. A future slice can register it once event-driven
audits are needed.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from pydantic import ValidationError

from backend.audit.payloads import AuditScope
from backend.audit.service import AuditService
from backend.audit.types import AuditOverallStatus, AuditSeverity
from backend.orchestration.jobs.envelopes import JobRequest, JobResponse
from backend.orchestration.jobs.errors import (
    ErrorCode,
    JobWarning,
    WarningSeverity,
)
from backend.orchestration.jobs.types import JobStatus, JobType

_AUDIT_TO_WARNING_SEVERITY: dict[AuditSeverity, WarningSeverity] = {
    AuditSeverity.LOW: WarningSeverity.LOW,
    AuditSeverity.MEDIUM: WarningSeverity.MEDIUM,
    AuditSeverity.HIGH: WarningSeverity.HIGH,
    # WarningSeverity has no "critical"; map to HIGH and surface the audit
    # severity faithfully via the structured report payload.
    AuditSeverity.CRITICAL: WarningSeverity.HIGH,
}


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _failure(
    request: JobRequest,
    *,
    started_at: datetime,
    completed_at: datetime,
    code: ErrorCode,
    message: str,
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
    )


def handle_audit(
    request: JobRequest,
    service: AuditService,
    *,
    now: Callable[[], datetime] = _utc_now,
) -> JobResponse:
    started_at = now()

    if request.job_type is not JobType.AUDIT:
        return _failure(
            request,
            started_at=started_at,
            completed_at=now(),
            code=ErrorCode.INPUT_VALIDATION_ERROR,
            message=(
                f"unexpected job_type {request.job_type.value!r} "
                "for audit handler"
            ),
        )

    # Parse optional scope. Empty/missing → full audit.
    raw_scope = dict(request.scope or {})
    audit_keys = {"region_ids", "company_ids", "audit_mode"}
    scope_payload = {k: v for k, v in raw_scope.items() if k in audit_keys}
    try:
        audit_scope = AuditScope.model_validate(scope_payload)
    except ValidationError as e:
        return _failure(
            request,
            started_at=started_at,
            completed_at=now(),
            code=ErrorCode.INPUT_VALIDATION_ERROR,
            message=f"invalid audit scope: {e.error_count()} error(s)",
        )

    report = service.run_audit(audit_scope)

    warnings = [
        JobWarning(
            warning_code=f.category.value,
            severity=_AUDIT_TO_WARNING_SEVERITY[f.severity],
            message=f.message,
            scope_type=f.scope_type,
            scope_ref=f.scope_ref,
        )
        for f in report.findings
    ]

    if report.overall_status is AuditOverallStatus.PASSED:
        status = JobStatus.SUCCEEDED
    else:
        # All non-passed outcomes carry findings; SUCCEEDED_WITH_WARNINGS
        # requires at least one warning, which we always have here.
        status = JobStatus.SUCCEEDED_WITH_WARNINGS

    return JobResponse(
        job_id=request.job_id,
        job_type=request.job_type,
        status=status,
        started_at=started_at,
        completed_at=now(),
        scope=dict(request.scope),
        outputs={
            "audit_report": report.model_dump(mode="json"),
            "overall_status": report.overall_status.value,
        },
        warnings=warnings,
        metrics={
            "total_findings": len(report.findings),
            "by_severity": dict(report.summary_by_severity),
            "by_category": dict(report.summary_by_category),
        },
    )
