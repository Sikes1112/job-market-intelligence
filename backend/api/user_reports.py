"""Layer 30D user report signal API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.api.dependencies import get_session
from backend.api.envelope import NOT_FOUND, error_envelope, lightweight_success_envelope
from backend.trust.models import UserReport
from backend.trust.report_schemas import UserReportCreate, UserReportSubmissionResult
from backend.trust.reports import (
    AutomatedRecheckRepository,
    UserReportNotFound,
    UserReportRepository,
    UserReportService,
    automated_recheck_job_payload,
    latest_report_recheck_status,
    user_report_payload,
)
from backend.trust.schemas import TrustAssessmentSubjectType

router = APIRouter(tags=["user-reports"])


@router.post("/user-reports", response_model=None)
def create_user_report(
    request: UserReportCreate,
    session: Session = Depends(get_session),
) -> dict:
    result = UserReportService(session).submit_report(request)
    return lightweight_success_envelope(data=_safe_submission_result(result))


@router.get("/user-reports", response_model=None)
def list_user_reports_for_subject(
    subject_type: TrustAssessmentSubjectType = Query(...),
    subject_id: str = Query(..., min_length=1, max_length=128),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
) -> dict:
    rows = UserReportRepository(session).list_reports_for_subject(
        subject_type=subject_type,
        subject_id=subject_id,
        limit=limit,
    )
    status = latest_report_recheck_status(
        session,
        subject_type=subject_type,
        subject_id=subject_id,
    )
    return lightweight_success_envelope(
        data={
            "reports": [_safe_user_report(row) for row in rows],
            "status": status.model_dump(mode="json") if status is not None else None,
        }
    )


@router.get("/user-reports/status/{report_id}", response_model=None)
def get_user_report_status(
    report_id: str,
    session: Session = Depends(get_session),
) -> dict | JSONResponse:
    try:
        result = UserReportService(session).report_status(report_id)
    except UserReportNotFound:
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code=NOT_FOUND,
                message=f"User report not found: {report_id!r}",
            ),
        )
    return lightweight_success_envelope(data=_safe_submission_result(result))


@router.get("/automated-rechecks/status/{job_id}", response_model=None)
def get_automated_recheck_status(
    job_id: str,
    session: Session = Depends(get_session),
) -> dict | JSONResponse:
    row = AutomatedRecheckRepository(session).get_job(job_id)
    if row is None:
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code=NOT_FOUND,
                message=f"Automated recheck job not found: {job_id!r}",
            ),
        )
    return lightweight_success_envelope(
        data={"recheck_job": automated_recheck_job_payload(row).model_dump(mode="json")}
    )


def _safe_submission_result(result: UserReportSubmissionResult) -> dict:
    data = result.model_dump(mode="json")
    data["report"] = _redact_report_payload(data["report"])
    return data


def _safe_user_report(row: UserReport) -> dict:
    return _redact_report_payload(user_report_payload(row).model_dump(mode="json"))


def _redact_report_payload(payload: dict) -> dict:
    redacted = dict(payload)
    redacted.pop("report_reason", None)
    redacted.pop("reporter_user_id", None)
    redacted.pop("reporter_session_id", None)
    return redacted
