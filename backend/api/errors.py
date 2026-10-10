from __future__ import annotations

from http import HTTPStatus
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api.request_context import request_id_from_scope
from backend.operations.error_monitoring import capture_exception_fail_open


class SafeHTTPException(StarletteHTTPException):
    """HTTP failure whose stable type and message are safe for a client."""

    def __init__(self, status_code: int, *, error_type: str, message: str) -> None:
        super().__init__(status_code=status_code, detail=message)
        self.error_type = error_type
        self.safe_message = message


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(SQLAlchemyError, database_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)


async def validation_error_handler(request: Request, _exc: RequestValidationError) -> JSONResponse:
    request.state.error_type = "validation_error"
    return safe_error_response(
        request,
        status_code=422,
        error_type="validation_error",
        message="Invalid request",
    )


async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    error_type = getattr(
        exc,
        "error_type",
        "not_found" if exc.status_code == 404 else "http_error",
    )
    message = getattr(exc, "safe_message", _safe_status_message(exc.status_code))
    request.state.error_type = error_type
    return safe_error_response(
        request,
        status_code=exc.status_code,
        error_type=error_type,
        message=message,
    )


async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    request.state.error_type = "database_error"
    _capture(request, exc, status_code=503)
    return safe_error_response(
        request,
        status_code=503,
        error_type="database_error",
        message="Database unavailable",
    )


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    request.state.error_type = "internal_error"
    _capture(request, exc, status_code=500)
    return safe_error_response(
        request,
        status_code=500,
        error_type="internal_error",
        message="Internal server error",
    )


def safe_error_response(
    request: Request,
    *,
    status_code: int,
    error_type: str,
    message: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return safe_error_response_for_request_id(
        _request_id_from_request(request),
        status_code=status_code,
        error_type=error_type,
        message=message,
        headers=headers,
    )


def safe_error_response_for_request_id(
    request_id: str,
    *,
    status_code: int,
    error_type: str,
    message: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    response_headers = dict(headers or {})
    response_headers["X-Request-ID"] = request_id
    return JSONResponse(
        status_code=status_code,
        headers=response_headers,
        content={
            "error": {
                "type": error_type,
                "message": message,
                "request_id": request_id,
            }
        },
    )


def _request_id_from_request(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if isinstance(request_id, str) and request_id:
        return request_id
    return uuid4().hex


def _safe_status_message(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "HTTP error"


def _capture(request: Request, exc: BaseException, *, status_code: int) -> None:
    settings = getattr(request.app.state, "settings", None)
    capture_exception_fail_open(
        getattr(request.app.state, "error_monitor", None),
        exc,
        context={
            "request_id": request_id_from_scope(request.scope),
            "method": request.method,
            "route": getattr(request.scope.get("route"), "path", request.url.path),
            "status_code": status_code,
            "release_id": getattr(settings, "release_id", "unknown"),
        },
    )
