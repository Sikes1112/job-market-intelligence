from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.api.dependencies import get_session
from backend.api.errors import SafeHTTPException
from backend.public_guest.service import (
    PUBLIC_GUEST_COOKIE_NAME,
    GuestDatabaseCapacityExceeded,
    GuestSessionCapacityExceeded,
    PublicGuestSessionService,
)

router = APIRouter(tags=["public-guest"])


@router.post("/guest/session", response_model=None)
def bootstrap_guest_session(
    request: Request,
    session: Session = Depends(get_session),
) -> JSONResponse:
    settings = request.app.state.settings
    if not settings.is_public_guest_demo:
        raise SafeHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            error_type="not_found",
            message="Not Found",
        )

    presented_token = request.cookies.get(PUBLIC_GUEST_COOKIE_NAME)
    try:
        bootstrap = PublicGuestSessionService(session, settings).bootstrap(presented_token)
    except (GuestSessionCapacityExceeded, GuestDatabaseCapacityExceeded) as exc:
        raise SafeHTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_type="guest_capacity_reached",
            message="Guest demo capacity reached",
        ) from exc

    response = JSONResponse(
        status_code=status.HTTP_201_CREATED if bootstrap.created else status.HTTP_200_OK,
        headers={"Cache-Control": "no-store, private"},
        content={
            "data": {
                "status": "active",
                "csrf_token": bootstrap.csrf_token,
                "expires_at": bootstrap.principal.expires_at.isoformat(),
                "created": bootstrap.created,
                "replaced": bootstrap.created and presented_token is not None,
            }
        },
    )
    response.set_cookie(
        key=PUBLIC_GUEST_COOKIE_NAME,
        value=bootstrap.session_token,
        max_age=settings.guest_session_ttl_seconds,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )
    return response
