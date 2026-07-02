"""Read-only API routes for Layer 23A opportunities."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.api.dependencies import get_session
from backend.api.envelope import (
    NOT_FOUND,
    VALIDATION_ERROR,
    error_envelope,
    lightweight_success_envelope,
)
from backend.opportunities.repository import OpportunityRepository
from backend.opportunities.route_schemas import OpportunityRouteRequest
from backend.opportunities.routing import OpportunityRouteService
from backend.opportunities.schemas import (
    OpportunityProgramType,
    OpportunityReviewRequest,
    OpportunitySubmissionRequest,
    OpportunitySubmissionStatus,
    OpportunityTrustLabel,
)
from backend.opportunities.service import (
    OpportunityNotFound,
    OpportunityService,
    OpportunityValidationError,
)
from backend.opportunities.submissions import (
    OpportunityReviewWorkflowError,
    OpportunitySubmissionNotFound,
    OpportunitySubmissionService,
)

router = APIRouter(tags=["opportunities"])


@router.get("/opportunities")
def list_opportunities(
    trust_label: OpportunityTrustLabel | None = Query(default=None),
    region: str | None = Query(default=None, min_length=1),
    role_family: str | None = Query(default=None, min_length=1),
    program_type: OpportunityProgramType | None = Query(default=None),
    active: bool | None = Query(default=None),
    expired: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    service = OpportunityService(OpportunityRepository(session))
    try:
        payload = service.list_opportunities(
            trust_label=trust_label,
            region=region,
            role_family=role_family,
            program_type=program_type.value if program_type is not None else None,
            active=active,
            expired=expired,
            limit=limit,
        )
    except OpportunityValidationError as exc:
        return JSONResponse(
            status_code=400,
            content=error_envelope(code=VALIDATION_ERROR, message=str(exc)),
        )
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


@router.post("/opportunities/submissions")
def create_opportunity_submission(
    request: OpportunitySubmissionRequest,
    session: Session = Depends(get_session),
):
    service = OpportunitySubmissionService(OpportunityRepository(session))
    payload = service.submit_opportunity(request)
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


@router.get("/opportunities/submissions")
def list_opportunity_submissions(
    status: OpportunitySubmissionStatus | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    service = OpportunitySubmissionService(OpportunityRepository(session))
    payload = service.list_submissions(status=status, limit=limit)
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


@router.get("/opportunities/submissions/{submission_id}")
def get_opportunity_submission(
    submission_id: str,
    session: Session = Depends(get_session),
):
    service = OpportunitySubmissionService(OpportunityRepository(session))
    try:
        payload = service.get_submission(submission_id)
    except OpportunitySubmissionNotFound:
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code=NOT_FOUND,
                message=f"Opportunity submission not found: {submission_id!r}",
            ),
        )
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


@router.post("/opportunities/submissions/{submission_id}/review")
def review_opportunity_submission(
    submission_id: str,
    request: OpportunityReviewRequest,
    session: Session = Depends(get_session),
):
    service = OpportunitySubmissionService(OpportunityRepository(session))
    try:
        payload = service.review_submission(submission_id, request)
    except OpportunitySubmissionNotFound:
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code=NOT_FOUND,
                message=f"Opportunity submission not found: {submission_id!r}",
            ),
        )
    except OpportunityReviewWorkflowError as exc:
        return JSONResponse(
            status_code=400,
            content=error_envelope(code=VALIDATION_ERROR, message=str(exc)),
        )
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


@router.post("/opportunities/routes")
def generate_opportunity_routes(
    request: OpportunityRouteRequest,
    session: Session = Depends(get_session),
):
    service = OpportunityRouteService(OpportunityRepository(session))
    payload = service.generate_routes(request)
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))


@router.get("/opportunities/{opportunity_id}")
def get_opportunity(
    opportunity_id: str,
    session: Session = Depends(get_session),
):
    service = OpportunityService(OpportunityRepository(session))
    try:
        payload = service.get_opportunity(opportunity_id)
    except OpportunityNotFound:
        return JSONResponse(
            status_code=404,
            content=error_envelope(
                code=NOT_FOUND,
                message=f"Opportunity not found: {opportunity_id!r}",
            ),
        )
    return lightweight_success_envelope(data=payload.model_dump(mode="json"))
