"""ASGI middleware that attaches verified Auth0/OIDC claims to request state."""

from __future__ import annotations

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from backend.api.errors import safe_error_response_for_request_id
from backend.api.request_context import request_id_from_scope
from backend.auth.jwks import Auth0JWTError, Auth0JWTVerifier, auth0_config_from_settings
from backend.config.settings import Settings


class Auth0JWTMiddleware:
    """Verify Bearer JWTs and expose only verified claims to route dependencies."""

    def __init__(self, app: ASGIApp, *, settings: Settings) -> None:
        self.app = app
        self.verifier = Auth0JWTVerifier(auth0_config_from_settings(settings))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        authorization = Headers(scope=scope).get("authorization")
        if authorization:
            try:
                claims = self._verify_authorization_header(authorization)
            except Auth0JWTError:
                scope.setdefault("state", {})["error_type"] = "auth_error"
                response = safe_error_response_for_request_id(
                    request_id_from_scope(scope),
                    status_code=401,
                    error_type="auth_error",
                    message="Unauthorized",
                    headers={"WWW-Authenticate": "Bearer"},
                )
                await response(scope, receive, send)
                return
            scope.setdefault("state", {})["verified_oidc_claims"] = claims

        await self.app(scope, receive, send)

    def _verify_authorization_header(self, authorization: str) -> dict:
        scheme, separator, token = authorization.partition(" ")
        if separator != " " or scheme.lower() != "bearer" or not token.strip():
            raise Auth0JWTError("Authorization header must use Bearer token syntax")
        return self.verifier.verify(token.strip())
