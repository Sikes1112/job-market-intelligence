"""Boundary types for externally verified auth identities.

The app never verifies passwords or owns primary credentials. Upstream managed
auth middleware should validate provider tokens first, then pass the stable
issuer/subject claims through this module before the user service maps them to
an internal user id.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

MANAGED_AUTH_PROVIDER_ID = "auth0"


class AuthBoundaryError(ValueError):
    """Raised when a verified provider identity is missing stable claims."""


@dataclass(frozen=True, slots=True)
class ExternalAuthPrincipal:
    """Provider identity after external token/session verification.

    ``provider``, ``issuer``, and ``subject`` are the only stable identity key.
    Profile fields are optional metadata and must not be used to identify a
    user because email/name values can change at the provider.
    """

    provider: str
    issuer: str
    subject: str
    email: str | None = None
    email_verified: bool | None = None
    display_name: str | None = None
    avatar_url: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", _required("provider", self.provider))
        object.__setattr__(self, "issuer", _required("issuer", self.issuer))
        object.__setattr__(self, "subject", _required("subject", self.subject))
        object.__setattr__(self, "email", _optional("email", self.email))
        object.__setattr__(self, "display_name", _optional("display_name", self.display_name))
        object.__setattr__(self, "avatar_url", _optional("avatar_url", self.avatar_url))
        if self.email_verified is not None and not isinstance(self.email_verified, bool):
            raise AuthBoundaryError("email_verified must be a boolean when provided")

    @property
    def identity_key(self) -> tuple[str, str, str]:
        return self.provider, self.issuer, self.subject


def principal_from_verified_oidc_claims(
    claims: Mapping[str, Any],
    *,
    provider: str = MANAGED_AUTH_PROVIDER_ID,
) -> ExternalAuthPrincipal:
    """Build an auth principal from already-validated OIDC/JWT claims.

    This intentionally does not decode or validate tokens; that remains the
    managed-provider SDK/JWKS middleware boundary.
    """

    return ExternalAuthPrincipal(
        provider=provider,
        issuer=_claim(claims, "iss"),
        subject=_claim(claims, "sub"),
        email=_optional_claim(claims, "email"),
        email_verified=claims.get("email_verified")
        if isinstance(claims.get("email_verified"), bool)
        else None,
        display_name=_optional_claim(claims, "name"),
        avatar_url=_optional_claim(claims, "picture"),
    )


def _claim(claims: Mapping[str, Any], name: str) -> str:
    value = claims.get(name)
    if not isinstance(value, str):
        raise AuthBoundaryError(f"verified auth claims must include string {name!r}")
    return value


def _optional_claim(claims: Mapping[str, Any], name: str) -> str | None:
    value = claims.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise AuthBoundaryError(f"claim {name!r} must be a string when provided")
    return _optional(name, value)


def _required(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise AuthBoundaryError(f"{name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise AuthBoundaryError(f"{name} must not be blank")
    return normalized


def _optional(name: str, value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AuthBoundaryError(f"{name} must be a string when provided")
    normalized = value.strip()
    return normalized or None
