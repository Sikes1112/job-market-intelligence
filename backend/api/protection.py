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


PUBLIC_DEMO_READ_ONLY_ERROR_TYPE = "public_demo_read_only"
PUBLIC_DEMO_EXACT_ALLOWLIST = frozenset(
    {
        ("GET", "/health"),
        ("GET", "/ready"),
        ("GET", "/regions"),
        ("GET", "/regions/search"),
        ("GET", "/companies/search"),
        ("GET", "/compare"),
        ("POST", "/discover/personalized"),
        ("GET", "/recommendations/goal-modes"),
        ("POST", "/recommendations/strategy"),
        ("GET", "/trust/explanation"),
        ("GET", "/exceptions/subject-status"),
        ("GET", "/user-intelligence/dashboard"),
        ("POST", "/career-agent/answers"),
        ("POST", "/career-agent/action-plans"),
        ("GET", "/data-standards/definitions"),
        ("GET", "/data-standards/partner-schema"),
        ("GET", "/data-standards/partners"),
        ("GET", "/data-standards/quality-labels"),
        ("GET", "/data-standards/governance-framework"),
        ("GET", "/public/benchmarks"),
        ("GET", "/public/reports"),
        ("GET", "/monetization/plans"),
        ("GET", "/monetization/features"),
        ("GET", "/monetization/reports"),
        ("GET", "/monetization/access-preview"),
        ("GET", "/billing/status"),
    }
)


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

        if self._public_demo_request_denied(scope):
            scope.setdefault("state", {})["error_type"] = PUBLIC_DEMO_READ_ONLY_ERROR_TYPE
            response = safe_error_response_for_request_id(
                request_id,
                status_code=403,
                error_type=PUBLIC_DEMO_READ_ONLY_ERROR_TYPE,
                message="Public demo mode exposes only approved read-only routes",
            )
            await response(scope, receive, send)
            return

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
        if _rate_limit_exempt(scope):
            return None

        now = time.monotonic()
        self._prune_expired_rate_limits(now)
        key = _client_key(scope)
        bucket = self._rate_limits.get(key)
        limit = int(self.settings.rate_limit_requests or 1)
        window_seconds = int(self.settings.rate_limit_window_seconds or 60)
        if bucket is None or bucket.reset_at <= now:
            self._rate_limits[key] = RateLimitBucket(
                count=1,
                reset_at=now + window_seconds,
            )
            return None

        if bucket.count >= limit:
            return max(1, math.ceil(bucket.reset_at - now))

        bucket.count += 1
        return None

    def _public_demo_request_denied(self, scope: Scope) -> bool:
        if not self.settings.is_public_demo_read_only:
            return False

        method = str(scope.get("method", "")).upper()
        if method == "OPTIONS":
            return False

        path = _normalized_path(scope)
        return not _public_demo_route_allowed(method, path)

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
        limit = int(self.settings.max_request_body_bytes or 1)

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


def _rate_limit_exempt(scope: Scope) -> bool:
    method = str(scope.get("method", "")).upper()
    if method == "OPTIONS":
        return True
    return _normalized_path(scope) in {"/health", "/ready"}


def _normalized_path(scope: Scope) -> str:
    raw_path = str(scope.get("path") or "/")
    if raw_path == "/":
        return raw_path
    return raw_path.rstrip("/")


def _public_demo_route_allowed(method: str, path: str) -> bool:
    if (method, path) in PUBLIC_DEMO_EXACT_ALLOWLIST:
        return True
    if method != "GET":
        return False

    parts = path.strip("/").split("/")
    if len(parts) == 2 and parts[0] in {"regions", "companies"} and parts[1]:
        return parts[1] != "search"
    if (
        len(parts) == 3
        and parts[0] == "data-standards"
        and parts[1] == "partners"
        and parts[2]
    ):
        return True
    if (
        len(parts) == 3
        and parts[0] == "public"
        and parts[1] in {"benchmarks", "reports"}
        and parts[2]
    ):
        return True
    if (
        len(parts) == 3
        and parts[0] == "regions"
        and parts[1]
        and parts[2] == "sources"
    ):
        return True
    if (
        len(parts) == 4
        and parts[0] == "platform"
        and parts[1] == "history"
        and parts[2] in {"regions", "companies"}
        and parts[3]
    ):
        return True
    if (
        len(parts) == 4
        and parts[0] == "platform"
        and parts[1] == "signals"
        and parts[2] == "regions"
        and parts[3]
    ):
        return True
    if len(parts) == 2 and parts[0] == "platform" and parts[1] == "indices":
        return True
    if (
        len(parts) == 4
        and parts[0] == "platform"
        and parts[1] == "indices"
        and parts[2]
        and parts[3] == "scores"
    ):
        return True
    if len(parts) == 2 and parts[0] == "platform" and parts[1] == "reports":
        return True
    if (
        len(parts) == 3
        and parts[0] == "platform"
        and parts[1] == "predictive"
        and parts[2] == "reports"
    ):
        return True
    if (
        len(parts) == 3
        and parts[0] == "platform"
        and parts[1] == "reports"
        and parts[2]
    ):
        return True
    if (
        len(parts) == 6
        and parts[0] == "api"
        and parts[1] == "v1"
        and parts[2] == "platform"
        and parts[3] == "regions"
        and parts[4]
        and parts[5] in {"scores", "early-career-access"}
    ):
        return True
    if (
        len(parts) == 6
        and parts[0] == "api"
        and parts[1] == "v1"
        and parts[2] == "platform"
        and parts[3] == "companies"
        and parts[4]
        and parts[5] == "geography"
    ):
        return True
    if (
        len(parts) == 5
        and parts[0] == "api"
        and parts[1] == "v1"
        and parts[2] == "platform"
        and parts[3] == "docs"
        and parts[4] in {"openapi.json", "postman.json"}
    ):
        return True
    if (
        len(parts) == 5
        and parts[0] == "api"
        and parts[1] == "v1"
        and parts[2] == "platform"
        and parts[3] == "embeds"
        and parts[4] in {"region-comparison", "market-score-card"}
    ):
        return True
    if (
        len(parts) == 5
        and parts[0] == "api"
        and parts[1] == "v1"
        and parts[2] == "platform"
        and parts[3] == "markets"
        and parts[4] in {"hiring-concentration", "compare"}
    ):
        return True
    return (
        len(parts) == 3
        and parts[0] == "companies"
        and parts[1]
        and parts[2] in {"regions", "sources"}
    )
