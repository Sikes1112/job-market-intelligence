from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass
from http.cookies import CookieError, SimpleCookie
from urllib.parse import urlsplit, urlunsplit

from starlette.concurrency import run_in_threadpool
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.api.errors import safe_error_response_for_request_id
from backend.api.request_context import request_id_from_scope
from backend.config.settings import Settings
from backend.public_guest.policy import public_guest_scope_allowed
from backend.public_guest.service import (
    PUBLIC_GUEST_COOKIE_NAME,
    PUBLIC_GUEST_CSRF_HEADER,
    GuestDatabaseCapacityExceeded,
    GuestMutationQuotaExceeded,
    PublicGuestSessionService,
    VerifiedGuestPrincipal,
)

_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_BOOTSTRAP_ROUTE = ("POST", "/guest/session")


@dataclass
class _RateBucket:
    count: int
    reset_at: float


class PublicGuestSessionMiddleware:
    """Verify guest cookies and stop unsafe requests before route execution."""

    def __init__(self, app: ASGIApp, *, settings: Settings) -> None:
        self.app = app
        self.settings = settings
        self._issuance_limits: dict[str, _RateBucket] = {}
        self._issuance_lock = asyncio.Lock()
        self._mutation_locks: dict[str, asyncio.Lock] = {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.settings.is_public_guest_demo:
            await self.app(scope, receive, send)
            return

        method = str(scope.get("method", "")).upper()
        path = _normalized_path(scope)
        if method == "OPTIONS":
            await self.app(scope, receive, send)
            return
        if method == "GET" and path.startswith(("/assets/", "/data/")):
            await self.app(scope, receive, send)
            return

        if (method, path) == _BOOTSTRAP_ROUTE:
            if not _trusted_request_origin(scope, self.settings.public_origin):
                await self._deny(scope, receive, send, 403, "guest_origin_denied", "Forbidden")
                return
            retry_after = self._issuance_retry_after(scope)
            if retry_after is not None:
                await self._deny(
                    scope,
                    receive,
                    send,
                    429,
                    "guest_session_rate_limited",
                    "Too many guest session requests",
                    headers={"Retry-After": str(retry_after)},
                )
                return
            async with self._issuance_lock:
                await self.app(scope, receive, _no_store_send(send))
            return

        token = _cookie_value(scope, PUBLIC_GUEST_COOKIE_NAME)
        principal = await run_in_threadpool(self._resolve_principal, scope, token)
        if principal is not None:
            state = scope.setdefault("state", {})
            state["verified_guest_principal"] = principal
            state["verified_guest_session_id"] = principal.session_id
        elif token is not None:
            scope.setdefault("state", {})["guest_session_invalid"] = True

        is_allowed = public_guest_scope_allowed(scope)
        if method in _UNSAFE_METHODS and is_allowed:
            if principal is None:
                await self._deny(
                    scope,
                    receive,
                    send,
                    401,
                    "guest_session_expired",
                    "Guest session is missing or expired",
                )
                return
            if not _trusted_request_origin(scope, self.settings.public_origin):
                await self._deny(scope, receive, send, 403, "guest_origin_denied", "Forbidden")
                return
            csrf_token = Headers(scope=scope).get(PUBLIC_GUEST_CSRF_HEADER)
            if not await run_in_threadpool(
                self._csrf_valid, scope, principal, csrf_token
            ):
                await self._deny(scope, receive, send, 403, "guest_csrf_invalid", "Forbidden")
                return

            lock = self._mutation_locks.setdefault(principal.session_id, asyncio.Lock())
            async with lock:
                quota_error = await run_in_threadpool(
                    self._consume_mutation,
                    scope,
                    principal,
                    method,
                    path,
                )
                if quota_error is not None:
                    await self._deny(
                        scope,
                        receive,
                        send,
                        429,
                        "guest_quota_exceeded",
                        quota_error,
                    )
                    return
                await self.app(scope, receive, _no_store_send(send))
            return

        response_send = _no_store_send(send) if principal is not None or token else send
        await self.app(scope, receive, response_send)

    def _resolve_principal(
        self, scope: Scope, token: str | None
    ) -> VerifiedGuestPrincipal | None:
        factory = scope["app"].state.session_factory
        with factory() as session:
            # Guest sessions use a fixed lifetime. Resolving every authenticated
            # read must remain read-only: otherwise a normal page that loads
            # several resources concurrently turns each request into a SQLite
            # writer and can exhaust the browser connection pool behind lock
            # retries. Bootstrap already records the meaningful last-seen event.
            return PublicGuestSessionService(session, self.settings).resolve(
                token,
                touch=False,
            )

    def _csrf_valid(
        self,
        scope: Scope,
        principal: VerifiedGuestPrincipal,
        csrf_token: str | None,
    ) -> bool:
        factory = scope["app"].state.session_factory
        with factory() as session:
            return PublicGuestSessionService(session, self.settings).csrf_valid(
                principal.session_id, csrf_token
            )

    def _consume_mutation(
        self,
        scope: Scope,
        principal: VerifiedGuestPrincipal,
        method: str,
        path: str,
    ) -> str | None:
        factory = scope["app"].state.session_factory
        with factory() as session:
            service = PublicGuestSessionService(session, self.settings)
            try:
                service.consume_mutation(principal.session_id)
                session.commit()
            except (GuestMutationQuotaExceeded, GuestDatabaseCapacityExceeded):
                session.rollback()
                return "Guest demo storage limit reached"
        return None

    def _issuance_retry_after(self, scope: Scope) -> int | None:
        now = time.monotonic()
        expired = [key for key, bucket in self._issuance_limits.items() if bucket.reset_at <= now]
        for key in expired:
            del self._issuance_limits[key]
        client = scope.get("client")
        client_host = client[0] if client and client[0] else "unknown"
        bucket = self._issuance_limits.get(client_host)
        if bucket is None:
            self._issuance_limits[client_host] = _RateBucket(
                count=1,
                reset_at=now + self.settings.guest_session_issue_window_seconds,
            )
            return None
        if bucket.count >= self.settings.guest_session_issue_requests:
            return max(1, math.ceil(bucket.reset_at - now))
        bucket.count += 1
        return None

    async def _deny(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        status_code: int,
        error_type: str,
        message: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        scope.setdefault("state", {})["error_type"] = error_type
        response = safe_error_response_for_request_id(
            request_id_from_scope(scope),
            status_code=status_code,
            error_type=error_type,
            message=message,
            headers=headers,
        )
        await response(scope, receive, _no_store_send(send))


def _trusted_request_origin(scope: Scope, expected_origin: str) -> bool:
    headers = Headers(scope=scope)
    origin = headers.get("origin")
    if origin is not None:
        return _normalized_origin(origin, allow_path=False) == expected_origin

    referer = headers.get("referer")
    fetch_site = headers.get("sec-fetch-site")
    return (
        referer is not None
        and _normalized_origin(referer, allow_path=True) == expected_origin
        and fetch_site is not None
        and fetch_site.lower() == "same-origin"
    )


def _normalized_origin(value: str, *, allow_path: bool) -> str | None:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    if parsed.username or parsed.password:
        return None
    if not allow_path and (parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        return None
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), "", "", ""))


def _cookie_value(scope: Scope, name: str) -> str | None:
    raw_cookie = Headers(scope=scope).get("cookie")
    if not raw_cookie:
        return None
    cookie = SimpleCookie()
    try:
        cookie.load(raw_cookie)
    except CookieError:
        return None
    morsel = cookie.get(name)
    return morsel.value if morsel is not None else None


def _normalized_path(scope: Scope) -> str:
    path = str(scope.get("path") or "/")
    return path if path == "/" else path.rstrip("/")


def _no_store_send(send: Send) -> Send:
    async def wrapped(message: Message) -> None:
        if message["type"] == "http.response.start":
            headers = MutableHeaders(scope=message)
            headers["Cache-Control"] = "no-store, private"
            headers.append("Vary", "Cookie")
            headers.append("Vary", "Origin")
        await send(message)

    return wrapped
