"""Protected Layer 35A Career Identity routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.api.dependencies import CurrentUser, get_current_user, get_session
from backend.api.envelope import (
    NOT_FOUND,
    VALIDATION_ERROR,
    error_envelope,
    lightweight_success_envelope,
)
from backend.career_identity.exceptions import (
    CareerIdentityFactNotFound,
    CareerIdentityStateTransitionError,
    CareerIdentityValidationError,
    CareerIdentityVersionConflict,
)
from backend.career_identity.repository import CareerIdentityRepository
from backend.career_identity.schemas import (
    CareerIdentityFactInput,
    CareerIdentityFactUpdateInput,
    CareerIdentityIngestionRequest,
    CareerIdentityPrivacyInput,
)
from backend.career_identity.service import CareerIdentityService
from backend.product_measurement.schemas import (
    ProductEventCreate,
    ProductEventSource,
    ProductEventType,
)
from backend.product_measurement.service import ProductMeasurementService
from backend.users.exceptions import CrossUserAccessBlocked
from backend.users.repository import UserRepository

router = APIRouter(prefix="/me/career-identity", tags=["career-identity"])


class ConfirmFactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_version: int | None = Field(default=None, ge=1)


def _service(session: Session) -> CareerIdentityService:
    return CareerIdentityService(
        CareerIdentityRepository(session),
        UserRepository(session),
    )


@router.get("")
def get_career_identity(
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    view = _service(session).view_identity(current.user.user_id)
    return lightweight_success_envelope(data=view.model_dump(mode="json"))


@router.post("", status_code=status.HTTP_201_CREATED)
def initialize_career_identity(
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    view = _service(session).view_identity(current.user.user_id)
    _record_identity_event(
        session,
        current.user.user_id,
        ProductEventType.ONBOARDING_STARTED,
        view.career_identity_id,
        view.current_version,
        {"completeness_state": view.completeness_state},
    )
    return lightweight_success_envelope(data=view.model_dump(mode="json"))


@router.get("/privacy")
def get_career_identity_privacy(
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    view = _service(session).view_identity(current.user.user_id)
    return lightweight_success_envelope(
        data={
            "career_identity_id": view.career_identity_id,
            "identity_version": view.current_version,
            "privacy": view.privacy,
        }
    )


@router.put("/privacy")
def update_career_identity_privacy(
    request: CareerIdentityPrivacyInput,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    try:
        view = _service(session).update_privacy(current.user.user_id, request)
    except CareerIdentityVersionConflict as exc:
        return _conflict_response(exc)
    return lightweight_success_envelope(data=view.model_dump(mode="json"))


@router.post("/facts", status_code=status.HTTP_201_CREATED)
def upsert_career_identity_fact(
    request: CareerIdentityFactInput,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    try:
        result = _service(session).upsert_fact(current.user.user_id, request)
    except CareerIdentityVersionConflict as exc:
        return _conflict_response(exc)
    except CareerIdentityValidationError as exc:
        return _validation_response(str(exc), code=exc.code)
    identity_view = _service(session).view_identity(current.user.user_id)
    _record_sufficiency_events(session, current.user.user_id, identity_view)
    return lightweight_success_envelope(
        data={
            "career_identity_fact_id": result.fact.career_identity_fact_id,
            "outcome": result.outcome,
            "version_changed": result.version_changed,
            "identity": identity_view.model_dump(mode="json"),
        }
    )


@router.put("/facts/{fact_id}")
def update_career_identity_fact(
    fact_id: str,
    request: CareerIdentityFactUpdateInput,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    try:
        _service(session).update_fact(current.user.user_id, fact_id, request)
    except CareerIdentityFactNotFound:
        return _not_found_response("Career identity fact not found.")
    except CrossUserAccessBlocked:
        return _not_found_response("Career identity fact not found.")
    except CareerIdentityVersionConflict as exc:
        return _conflict_response(exc)
    except CareerIdentityValidationError as exc:
        return _validation_response(str(exc), code=exc.code)
    identity_view = _service(session).view_identity(current.user.user_id)
    _record_sufficiency_events(session, current.user.user_id, identity_view)
    return lightweight_success_envelope(data=identity_view.model_dump(mode="json"))


@router.post("/facts/{fact_id}/confirm")
def confirm_career_identity_fact(
    fact_id: str,
    request: ConfirmFactRequest | None = None,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    request = request or ConfirmFactRequest()
    try:
        _service(session).confirm_fact(
            current.user.user_id,
            fact_id,
            expected_version=request.expected_version,
        )
    except CareerIdentityFactNotFound:
        return _not_found_response("Career identity fact not found.")
    except CrossUserAccessBlocked:
        return _not_found_response("Career identity fact not found.")
    except CareerIdentityVersionConflict as exc:
        return _conflict_response(exc)
    except CareerIdentityStateTransitionError as exc:
        return _validation_response(str(exc), code=exc.code)
    identity_view = _service(session).view_identity(current.user.user_id)
    _record_sufficiency_events(session, current.user.user_id, identity_view)
    return lightweight_success_envelope(data=identity_view.model_dump(mode="json"))


@router.delete("/facts/{fact_id}")
def delete_career_identity_fact(
    fact_id: str,
    expected_version: int | None = Query(default=None, ge=1),
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    try:
        _service(session).delete_fact(
            current.user.user_id,
            fact_id,
            expected_version=expected_version,
        )
    except CareerIdentityFactNotFound:
        return _not_found_response("Career identity fact not found.")
    except CrossUserAccessBlocked:
        return _not_found_response("Career identity fact not found.")
    except CareerIdentityVersionConflict as exc:
        return _conflict_response(exc)
    return lightweight_success_envelope(data={"deleted_career_identity_facts": 1})


@router.get("/evaluation")
def get_career_identity_evaluation(
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    evaluation = _service(session).evaluate(current.user.user_id)
    return lightweight_success_envelope(data=evaluation)


@router.post("/ingest")
def ingest_career_identity_profile(
    request: CareerIdentityIngestionRequest,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    try:
        result = _service(session).ingest_profile(current.user.user_id, request)
    except CareerIdentityVersionConflict as exc:
        return _conflict_response(exc)
    except CareerIdentityValidationError as exc:
        return _validation_response(str(exc), code=exc.code)
    identity_view = _service(session).view_identity(current.user.user_id)
    _record_sufficiency_events(session, current.user.user_id, identity_view)
    return lightweight_success_envelope(data=result.model_dump(mode="json"))


def _record_sufficiency_events(session: Session, user_id: str, view) -> None:  # noqa: ANN001
    if view.sufficiency_state != "sufficient":
        return
    payload = {
        "completeness_state": view.completeness_state,
        "sufficiency_state": view.sufficiency_state,
    }
    _record_identity_event(
        session,
        user_id,
        ProductEventType.CAREER_IDENTITY_SUFFICIENT,
        view.career_identity_id,
        view.current_version,
        payload,
    )
    _record_identity_event(
        session,
        user_id,
        ProductEventType.ONBOARDING_COMPLETED,
        view.career_identity_id,
        view.current_version,
        payload,
    )


def _record_identity_event(
    session: Session,
    user_id: str,
    event_type: ProductEventType,
    career_identity_id: str,
    career_identity_version: int,
    payload: dict,
) -> None:
    ProductMeasurementService(session).best_effort_record_event(
        user_id,
        ProductEventCreate(
            event_type=event_type,
            event_source=ProductEventSource.BACKEND,
            career_identity_id=career_identity_id,
            career_identity_version=career_identity_version,
            product_surface="career_identity",
            payload=payload,
        ),
    )


def _not_found_response(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=error_envelope(code=NOT_FOUND, message=message),
    )


def _validation_response(
    message: str,
    *,
    code: str = VALIDATION_ERROR,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_envelope(code=code, message=_safe_validation_message(message)),
    )


def _conflict_response(exc: CareerIdentityVersionConflict) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content=error_envelope(
            code="VERSION_CONFLICT",
            message=(
                "Career identity version conflict: "
                f"expected {exc.expected_version}, current {exc.actual_version}."
            ),
        ),
    )


def _safe_validation_message(message: str) -> str:
    if "input_value=" in message or "input_type=" in message:
        return "Invalid Career Identity input."
    return message
