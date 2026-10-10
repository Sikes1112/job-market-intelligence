"""Authenticated Layer 43 My Search workspace routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.api.dependencies import CurrentUser, get_current_user, get_session, require_beta_access
from backend.api.envelope import (
    NOT_FOUND,
    VALIDATION_ERROR,
    error_envelope,
    lightweight_success_envelope,
)
from backend.my_search.schemas import TrackOpportunityInput
from backend.my_search.service import (
    MySearchService,
    SearchWorkspaceNotFound,
    SearchWorkspaceValidationError,
)
from backend.users.exceptions import UserNotFound

router = APIRouter(
    prefix="/me/search-workspace",
    tags=["my-search"],
    dependencies=[Depends(require_beta_access)],
)


@router.get("")
def get_search_workspace(
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        workspace = MySearchService(session).workspace(current.user.user_id)
    except UserNotFound:
        return _not_found("User not found.")
    return lightweight_success_envelope(data=workspace.model_dump(mode="json"))


@router.post("/applications/track", status_code=status.HTTP_201_CREATED, response_model=None)
def track_current_opportunity(
    request: TrackOpportunityInput,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    try:
        result = MySearchService(session).track_opportunity(current.user.user_id, request)
    except (SearchWorkspaceNotFound, UserNotFound):
        return _not_found("Pursuit or current opportunity not found.")
    except SearchWorkspaceValidationError as exc:
        return JSONResponse(
            status_code=422,
            content=error_envelope(code=VALIDATION_ERROR, message=str(exc)),
        )
    response = lightweight_success_envelope(data=result.model_dump(mode="json"))
    if not result.created:
        response["metadata"]["state"] = "unchanged"
    return response


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=error_envelope(code=NOT_FOUND, message=message),
    )
