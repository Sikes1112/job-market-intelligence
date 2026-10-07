"""Protected Layer 37 deep decision intelligence routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.api.dependencies import CurrentUser, get_current_user, get_session
from backend.api.envelope import (
    NOT_FOUND,
    VALIDATION_ERROR,
    error_envelope,
    lightweight_success_envelope,
)
from backend.career_decisions.repository import CareerDecisionRepository
from backend.deep_decisions.repository import DeepDecisionRepository
from backend.deep_decisions.schemas import DeepDecisionAnalysisRequest
from backend.deep_decisions.service import (
    DeepDecisionNotFound,
    DeepDecisionService,
    DeepDecisionValidationError,
)
from backend.users.exceptions import CrossUserAccessBlocked, UserNotFound
from backend.users.repository import UserRepository

router = APIRouter(prefix="/me", tags=["deep-decisions"])


def _service(session: Session) -> DeepDecisionService:
    return DeepDecisionService(
        session,
        DeepDecisionRepository(session),
        CareerDecisionRepository(session),
        UserRepository(session),
    )


@router.post(
    "/decisions/{decision_id}/deep-analysis",
    status_code=status.HTTP_201_CREATED,
    response_model=None,
)
def generate_deep_decision_analysis(
    decision_id: str,
    request: DeepDecisionAnalysisRequest,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        view = _service(session).generate_analysis(current.user.user_id, decision_id, request)
    except (DeepDecisionNotFound, CrossUserAccessBlocked):
        return _not_found("Decision not found.")
    except UserNotFound:
        return _not_found("User not found.")
    except DeepDecisionValidationError as exc:
        return _validation(str(exc), code=exc.code)
    return lightweight_success_envelope(data={"analysis": view.model_dump(mode="json")})


@router.get("/decisions/{decision_id}/deep-analysis", response_model=None)
def get_latest_deep_decision_analysis(
    decision_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        view = _service(session).latest_analysis(current.user.user_id, decision_id)
    except (DeepDecisionNotFound, CrossUserAccessBlocked):
        return _not_found("Deep decision analysis not found.")
    return lightweight_success_envelope(data={"analysis": view.model_dump(mode="json")})


@router.get("/strategic-reviews", response_model=None)
def list_strategic_reviews(
    decision_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        views = _service(session).list_strategic_reviews(
            current.user.user_id, decision_id=decision_id, limit=limit
        )
    except (DeepDecisionNotFound, CrossUserAccessBlocked):
        return _not_found("Decision not found.")
    return lightweight_success_envelope(
        data={"strategic_reviews": [view.model_dump(mode="json") for view in views]}
    )


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=error_envelope(code=NOT_FOUND, message=message),
    )


def _validation(message: str, *, code: str = VALIDATION_ERROR) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_envelope(code=code, message=message),
    )
