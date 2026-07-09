"""Layer 30E rare exception workflow API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.api.dependencies import CurrentAdmin, get_session, require_data_review_access
from backend.api.envelope import NOT_FOUND, error_envelope, lightweight_success_envelope
from backend.trust.exception_schemas import ExceptionCaseStatusUpdate
from backend.trust.exceptions import (
    ExceptionCaseNotFound,
    ExceptionCaseRepository,
    ExceptionWorkflowService,
    exception_case_payload,
)
from backend.trust.schemas import ExceptionCaseStatus, TrustAssessmentSubjectType

router = APIRouter(tags=["exceptions"])


@router.get("/exceptions/subject-status", response_model=None)
def exception_subject_status(
    subject_type: TrustAssessmentSubjectType = Query(...),
    subject_id: str = Query(..., min_length=1, max_length=128),
    session: Session = Depends(get_session),
) -> dict:
    status = ExceptionWorkflowService(session).get_exception_status_for_subject(
        subject_type=subject_type,
        subject_id=subject_id,
    )
    return lightweight_success_envelope(data=status.model_dump(mode="json"))


@router.get("/exceptions", response_model=None)
def list_exception_cases(
    status: ExceptionCaseStatus | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
    _admin: CurrentAdmin = Depends(require_data_review_access),
) -> dict:
    rows = ExceptionCaseRepository(session).list_cases(status=status, limit=limit)
    return lightweight_success_envelope(
        data={
            "exception_cases": [
                exception_case_payload(row).model_dump(mode="json") for row in rows
            ]
        }
    )


@router.patch("/exceptions/{exception_case_id}/status", response_model=None)
def update_exception_status(
    exception_case_id: str,
    request: ExceptionCaseStatusUpdate,
    session: Session = Depends(get_session),
    _admin: CurrentAdmin = Depends(require_data_review_access),
) -> dict | JSONResponse:
    try:
        row = ExceptionWorkflowService(session).update_exception_status(
            exception_case_id,
            request,
        )
    except ExceptionCaseNotFound:
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code=NOT_FOUND,
                message=f"Exception case not found: {exception_case_id!r}",
            ),
        )
    return lightweight_success_envelope(
        data={"exception_case": exception_case_payload(row).model_dump(mode="json")}
    )
