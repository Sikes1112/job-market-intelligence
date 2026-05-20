from __future__ import annotations

import math
import time
from dataclasses import dataclass

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.api.errors import safe_error_response_for_request_id
from backend.api.request_context import request_id_from_scope
from backend.config.settings import Settings


class RequestBodyTooLarge(Exception):
    pass


@dataclass
class RateLimitBucket:
    count: int
    reset_at: float


class APIProtectionMiddleware:
    def __init__(self, app: ASGIApp, *, settings: Settings) -> None:
        self.app = app
        self.settings = settings
        self._rate_limits: dict[str, RateLimitBucket] = {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = request_id_from_scope(scope)

        retry_after = self._rate_limit_retry_after(scope)
        if retry_after is not None:
            scope.setdefault("state", {})["error_type"] = "rate_limited"
            response = safe_error_response_for_request_id(
                request_id,
                status_code=429,
                error_type="rate_limited",
                message="Too many requests",
                headers={"Retry-After": str(retry_after)},
            )
            await response(scope, receive, send)
            return

        if self._content_length_too_large(scope):
            scope.setdefault("state", {})["error_type"] = "request_too_large"
            response = safe_error_response_for_request_id(
                request_id,
                status_code=413,
                error_type="request_too_large",
                message="Request body too large",
            )
            await response(scope, receive, send)
            return

        try:
            await self.app(scope, self._limited_receive(receive), send)
        except RequestBodyTooLarge:
            scope.setdefault("state", {})["error_type"] = "request_too_large"
            response = safe_error_response_for_request_id(
                request_id,
                status_code=413,
                error_type="request_too_large",
                message="Request body too large",
            )
            await response(scope, receive, send)

    def _rate_limit_retry_after(self, scope: Scope) -> int | None:
        if not self.settings.rate_limit_enabled:
            return None

        now = time.monotonic()
        self._prune_expired_rate_limits(now)
        key = _client_key(scope)
        bucket = self._rate_limits.get(key)
        if bucket is None or bucket.reset_at <= now:
            self._rate_limits[key] = RateLimitBucket(
                count=1,
                reset_at=now + self.settings.rate_limit_window_seconds,
            )
            return None

        if bucket.count >= self.settings.rate_limit_requests:
            return max(1, math.ceil(bucket.reset_at - now))

        bucket.count += 1
        return None

    def _prune_expired_rate_limits(self, now: float) -> None:
        expired_keys = [
            key for key, bucket in self._rate_limits.items() if bucket.reset_at <= now
        ]
        for key in expired_keys:
            del self._rate_limits[key]

    def _content_length_too_large(self, scope: Scope) -> bool:
        content_length = Headers(scope=scope).get("content-length")
        if content_length is None:
            return False
        try:
            return int(content_length) > self.settings.max_request_body_bytes
        except ValueError:
            return False

    def _limited_receive(self, receive: Receive) -> Receive:
        received = 0
        limit = self.settings.max_request_body_bytes

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise RequestBodyTooLarge
            return message

        return limited_receive


def apply_security_headers(headers: MutableHeaders) -> None:
    if "X-Content-Type-Options" not in headers:
        headers["X-Content-Type-Options"] = "nosniff"
    if "X-Frame-Options" not in headers:
        headers["X-Frame-Options"] = "DENY"
    if "Referrer-Policy" not in headers:
        headers["Referrer-Policy"] = "no-referrer"
    if "Permissions-Policy" not in headers:
        headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"


def _client_key(scope: Scope) -> str:
    client = scope.get("client")
    if client and client[0]:
        return str(client[0])
    return "unknown"
