from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.api.errors import safe_error_response_for_request_id
from backend.api.protection import apply_security_headers
from backend.api.request_context import (
    REQUEST_ID_HEADER,
    reset_request_id,
    resolve_request_id,
    set_request_id,
)


class RequestObservabilityMiddleware:
    """Attach safe request IDs and emit one structured log per HTTP request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.logger = logging.getLogger("backend.api.requests")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = resolve_request_id(Headers(scope=scope).get(REQUEST_ID_HEADER))
        scope.setdefault("state", {})["request_id"] = request_id
        request_id_token = set_request_id(request_id)

        method = str(scope.get("method", ""))
        path = str(scope.get("path", ""))
        status_code = 500
        start = time.perf_counter()

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers = MutableHeaders(scope=message)
                headers[REQUEST_ID_HEADER] = request_id
                settings = getattr(getattr(scope.get("app"), "state", None), "settings", None)
                if settings is not None and settings.security_headers_enabled:
                    apply_security_headers(headers)
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
            state = scope.get("state", {})
            self._log_request(
                level=logging.INFO,
                request_id=request_id,
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=_duration_ms(start),
                error_type=state.get("error_type"),
            )
        except Exception as exc:
            error_type = (
                "database_error" if isinstance(exc, SQLAlchemyError) else "internal_error"
            )
            message = (
                "Database unavailable"
                if isinstance(exc, SQLAlchemyError)
                else "Internal server error"
            )
            status_code = 503 if isinstance(exc, SQLAlchemyError) else 500
            self._log_request(
                level=logging.ERROR,
                request_id=request_id,
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=_duration_ms(start),
                error_type=type(exc).__name__,
            )
            response = safe_error_response_for_request_id(
                request_id,
                status_code=status_code,
                error_type=error_type,
                message=message,
            )
            await response(scope, receive, send_with_request_id)
            return
        finally:
            reset_request_id(request_id_token)

    def _log_request(
        self,
        *,
        level: int,
        request_id: str,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        error_type: str | None,
    ) -> None:
        fields: dict[str, Any] = {
            "request_id": request_id,
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "error_type": error_type,
        }
        try:
            self.logger.log(level, "request_completed", extra={"extra_fields": fields})
        except Exception:
            pass


def _duration_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 3)
