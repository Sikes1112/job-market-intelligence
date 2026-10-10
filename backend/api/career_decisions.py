"""Protected Layer 36A career decision lifecycle routes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.api.dependencies import CurrentUser, get_current_user, get_session, require_beta_access
from backend.api.envelope import (
    NOT_FOUND,
    VALIDATION_ERROR,
    error_envelope,
    lightweight_success_envelope,
)
from backend.career_decisions.exceptions import (
    CareerDecisionNotFound,
    CareerDecisionTransitionError,
    CareerDecisionValidationError,
)
from backend.career_decisions.repository import CareerDecisionRepository
from backend.career_decisions.schemas import (
    ActionPlanCreateInput,
    ApplicationCreateInput,
    ApplicationTransitionInput,
    CareerActionInput,
    CareerActionUpdateInput,
    DecisionCreateInput,
    DecisionOptionInput,
    DecisionUpdateInput,
    OptionSelectInput,
    OutcomeCreateInput,
)
from backend.career_decisions.service import CareerDecisionService
from backend.career_identity.repository import CareerIdentityRepository
from backend.companies.repository import CompanyRepository
from backend.geography.repository import RegionRepository
from backend.product_measurement.service import ProductMeasurementService
from backend.scoring.repository import RegionScoreRepository
from backend.users.exceptions import CrossUserAccessBlocked, UserNotFound
from backend.users.repository import UserRepository

router = APIRouter(
    prefix="/me", tags=["career-decisions"], dependencies=[Depends(require_beta_access)]
)


def _service(session: Session) -> CareerDecisionService:
    return CareerDecisionService(
        CareerDecisionRepository(session),
        CareerIdentityRepository(session),
        UserRepository(session),
        RegionRepository(session),
        CompanyRepository(session),
        RegionScoreRepository(session),
        ProductMeasurementService(session),
    )


@router.get("/decisions")
def list_decisions(
    limit: int = Query(default=100, ge=1, le=500),
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    views = _service(session).list_decisions(current.user.user_id, limit=limit)
    return lightweight_success_envelope(
        data={"decisions": [view.model_dump(mode="json") for view in views]}
    )


@router.post("/decisions", status_code=status.HTTP_201_CREATED, response_model=None)
def create_decision(
    request: DecisionCreateInput,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        view = _service(session).create_decision(current.user.user_id, request)
    except UserNotFound:
        return _not_found("User not found.")
    except CareerDecisionValidationError as exc:
        return _validation(str(exc), code=exc.code)
    return lightweight_success_envelope(data={"decision": view.model_dump(mode="json")})


@router.get("/decisions/{decision_id}", response_model=None)
def get_decision(
    decision_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        view = _service(session).decision_view(current.user.user_id, decision_id)
    except (CareerDecisionNotFound, CrossUserAccessBlocked):
        return _not_found("Decision not found.")
    return lightweight_success_envelope(data={"decision": view.model_dump(mode="json")})


@router.patch("/decisions/{decision_id}", response_model=None)
def update_decision(
    decision_id: str,
    request: DecisionUpdateInput,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        view = _service(session).update_decision(current.user.user_id, decision_id, request)
    except (CareerDecisionNotFound, CrossUserAccessBlocked):
        return _not_found("Decision not found.")
    except CareerDecisionValidationError as exc:
        return _validation(str(exc), code=exc.code)
    return lightweight_success_envelope(data={"decision": view.model_dump(mode="json")})


@router.post(
    "/decisions/{decision_id}/options", status_code=status.HTTP_201_CREATED, response_model=None
)
def add_decision_option(
    decision_id: str,
    request: DecisionOptionInput,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        view = _service(session).add_option(current.user.user_id, decision_id, request)
    except (CareerDecisionNotFound, CrossUserAccessBlocked):
        return _not_found("Decision not found.")
    return lightweight_success_envelope(data={"decision": view.model_dump(mode="json")})


@router.post("/decisions/{decision_id}/compare", response_model=None)
def compare_decision(
    decision_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        recommendation = _service(session).compare_decision(current.user.user_id, decision_id)
    except (CareerDecisionNotFound, CrossUserAccessBlocked):
        return _not_found("Decision not found.")
    except CareerDecisionValidationError as exc:
        return _validation(str(exc), code=exc.code)
    envelope = lightweight_success_envelope(
        data={"recommendation": recommendation.model_dump(mode="json")},
        state="partial" if recommendation.recommendation_status == "abstained" else "fresh",
    )
    envelope["metadata"]["warnings"] = list(recommendation.limitations)
    return envelope


@router.get("/decisions/{decision_id}/journal", response_model=None)
def get_decision_journal(
    decision_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        versions = _service(session).journal(current.user.user_id, decision_id)
    except (CareerDecisionNotFound, CrossUserAccessBlocked):
        return _not_found("Decision not found.")
    return lightweight_success_envelope(
        data={"journal": [version.model_dump(mode="json") for version in versions]}
    )


@router.post("/decisions/{decision_id}/select", response_model=None)
def select_decision_option(
    decision_id: str,
    request: OptionSelectInput,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        view = _service(session).select_option(current.user.user_id, decision_id, request)
    except (CareerDecisionNotFound, CrossUserAccessBlocked):
        return _not_found("Decision or option not found.")
    return lightweight_success_envelope(data={"decision": view.model_dump(mode="json")})


@router.post("/decisions/{decision_id}/reopen", response_model=None)
def reopen_decision(
    decision_id: str,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        view = _service(session).reopen_decision(current.user.user_id, decision_id)
    except (CareerDecisionNotFound, CrossUserAccessBlocked):
        return _not_found("Decision not found.")
    return lightweight_success_envelope(data={"decision": view.model_dump(mode="json")})


@router.post(
    "/decisions/{decision_id}/plan", status_code=status.HTTP_201_CREATED, response_model=None
)
def create_action_plan(
    decision_id: str,
    request: ActionPlanCreateInput,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        plan = _service(session).create_action_plan(current.user.user_id, decision_id, request)
    except (CareerDecisionNotFound, CrossUserAccessBlocked):
        return _not_found("Decision not found.")
    except CareerDecisionValidationError as exc:
        return _validation(str(exc), code=exc.code)
    return lightweight_success_envelope(data={"action_plan": plan.model_dump(mode="json")})


@router.get("/actions", response_model=None)
def list_actions(
    decision_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        actions = _service(session).list_actions(
            current.user.user_id, decision_id=decision_id, limit=limit
        )
    except (CareerDecisionNotFound, CrossUserAccessBlocked):
        return _not_found("Decision not found.")
    return lightweight_success_envelope(
        data={"actions": [action.model_dump(mode="json") for action in actions]}
    )


@router.post(
    "/decisions/{decision_id}/actions",
    status_code=status.HTTP_201_CREATED,
    response_model=None,
)
def create_action(
    decision_id: str,
    request: CareerActionInput,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        action = _service(session).create_action(current.user.user_id, decision_id, request)
    except (CareerDecisionNotFound, CrossUserAccessBlocked):
        return _not_found("Decision or option not found.")
    except CareerDecisionValidationError as exc:
        return _validation(str(exc), code=exc.code)
    return lightweight_success_envelope(data={"action": action.model_dump(mode="json")})


@router.patch("/actions/{action_id}", response_model=None)
def update_action(
    action_id: str,
    request: CareerActionUpdateInput,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        action = _service(session).update_action(current.user.user_id, action_id, request)
    except (CareerDecisionNotFound, CrossUserAccessBlocked):
        return _not_found("Action not found.")
    return lightweight_success_envelope(data={"action": action.model_dump(mode="json")})


@router.post("/applications", status_code=status.HTTP_201_CREATED, response_model=None)
def create_application(
    request: ApplicationCreateInput,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        application = _service(session).create_application(current.user.user_id, request)
    except (CareerDecisionNotFound, CrossUserAccessBlocked):
        return _not_found("Linked decision/action/application not found.")
    except CareerDecisionValidationError as exc:
        return _validation(str(exc), code=exc.code)
    return lightweight_success_envelope(data={"application": application.model_dump(mode="json")})


@router.patch("/applications/{application_id}/transition", response_model=None)
def transition_application(
    application_id: str,
    request: ApplicationTransitionInput,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        application = _service(session).transition_application(
            current.user.user_id, application_id, request
        )
    except (CareerDecisionNotFound, CrossUserAccessBlocked):
        return _not_found("Application not found.")
    except CareerDecisionTransitionError as exc:
        return _validation(str(exc), code=exc.code)
    return lightweight_success_envelope(data={"application": application.model_dump(mode="json")})


@router.post("/outcomes", status_code=status.HTTP_201_CREATED, response_model=None)
def create_outcome(
    request: OutcomeCreateInput,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        outcome = _service(session).create_outcome(current.user.user_id, request)
    except (CareerDecisionNotFound, CrossUserAccessBlocked):
        return _not_found("Linked decision/action/application not found.")
    except CareerDecisionValidationError as exc:
        return _validation(str(exc), code=exc.code)
    return lightweight_success_envelope(data={"outcome": outcome.model_dump(mode="json")})


@router.get("/reviews/weekly", response_model=None)
def weekly_review(
    window_start: datetime | None = Query(default=None),
    window_end: datetime | None = Query(default=None),
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    review = _service(session).weekly_review(
        current.user.user_id,
        window_start=window_start,
        window_end=window_end,
    )
    return lightweight_success_envelope(data={"review": review.model_dump(mode="json")})


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
