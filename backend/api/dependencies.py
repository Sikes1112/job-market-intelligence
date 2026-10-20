"""FastAPI dependencies for the read layer and protected user boundary.

* :func:`get_session` yields a SQLAlchemy session bound to the app's engine.
  Tests override this dependency to share their seeded session.
* :func:`get_output_service` constructs an :class:`OutputAssemblyService`
  with all required repositories + the session.

The dependencies wire only repositories and the output service. **No upstream
domain service** (companies/geography/presence/hiring/entry_level/scoring)
is constructed in the API layer — the layer-isolation test pins this.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.admin.roles import (
    ADMIN_MUTATION_ROLES,
    ADMIN_READ_ROLES,
    DATA_REVIEW_ROLES,
    AdminRole,
    parse_admin_role,
)
from backend.api.errors import SafeHTTPException
from backend.auth.boundary import (
    AuthBoundaryError,
    principal_from_verified_oidc_claims,
)
from backend.companies.repository import CompanyRepository
from backend.config.settings import AppEnv
from backend.entry_level.repository import EntryLevelRepository
from backend.geography.repository import RegionRepository
from backend.hiring.repository import HiringRepository
from backend.outputs.repository import OutputMetadataRepository
from backend.outputs.service import OutputAssemblyService
from backend.presence.repository import PresenceRepository
from backend.public_guest.service import VerifiedGuestPrincipal
from backend.scoring.repository import RegionScoreRepository
from backend.users.exceptions import (
    DeactivatedUserAuthenticationBlocked,
    ExternalIdentityNotFound,
    MissingProfileForExternalIdentity,
    MissingUserForExternalIdentity,
)
from backend.users.models import ExternalAuthIdentity, User, UserProfile
from backend.users.repository import UserRepository
from backend.users.service import UserIdentityService

VERIFIED_OIDC_CLAIMS_HEADER = "x-verified-oidc-claims"


@dataclass(frozen=True, slots=True)
class CurrentUser:
    user: User
    identity: ExternalAuthIdentity
    profile: UserProfile


@dataclass(frozen=True, slots=True)
class CurrentAdmin:
    current: CurrentUser
    role: AdminRole


def get_session(request: Request) -> Iterator[Session]:
    factory = request.app.state.session_factory
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_output_service(
    session: Session = Depends(get_session),
) -> OutputAssemblyService:
    return OutputAssemblyService(
        OutputMetadataRepository(session),
        session=session,
        region_repo=RegionRepository(session),
        company_repo=CompanyRepository(session),
        presence_repo=PresenceRepository(session),
        hiring_repo=HiringRepository(session),
        entry_level_repo=EntryLevelRepository(session),
        score_repo=RegionScoreRepository(session),
    )


def get_region_repository(
    session: Session = Depends(get_session),
) -> RegionRepository:
    return RegionRepository(session)


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
) -> CurrentUser:
    """Resolve the current internal user from already-verified OIDC claims.

    Production Auth0 JWT/JWKS verification happens in middleware, which attaches
    the verified claim mapping to ``request.state.verified_oidc_claims``. For
    local/test API-route coverage only, ``X-Verified-OIDC-Claims`` may carry
    that already-verified claim mapping as JSON.
    """

    settings = request.app.state.settings
    verified_guest: VerifiedGuestPrincipal | None = None
    if settings.app_env == AppEnv.PUBLIC_GUEST_DEMO:
        verified_guest = getattr(request.state, "verified_guest_principal", None)
        if not isinstance(verified_guest, VerifiedGuestPrincipal):
            error_type = (
                "guest_session_expired"
                if getattr(request.state, "guest_session_invalid", False)
                else "guest_session_required"
            )
            raise SafeHTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                error_type=error_type,
                message="Guest session is missing or expired",
            )
        principal = verified_guest.as_external_principal()
    else:
        claims = _verified_oidc_claims_from_request(request)
        try:
            principal = principal_from_verified_oidc_claims(claims)
        except AuthBoundaryError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid verified auth claims",
            ) from exc

    identity_service = UserIdentityService(UserRepository(session))
    try:
        if verified_guest is not None:
            resolved = identity_service.resolve_existing_external_principal_read_only(
                principal
            )
        else:
            resolved = identity_service.resolve_external_principal(principal)
    except DeactivatedUserAuthenticationBlocked as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        ) from exc
    except (
        ExternalIdentityNotFound,
        MissingProfileForExternalIdentity,
        MissingUserForExternalIdentity,
    ) as exc:
        if verified_guest is None:
            raise
        raise SafeHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_type="guest_session_invalid",
            message="Guest session is invalid",
        ) from exc
    if settings.app_env == AppEnv.PUBLIC_GUEST_DEMO:
        if resolved.user.user_id != verified_guest.user_id:
            raise SafeHTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                error_type="guest_session_invalid",
                message="Guest session is invalid",
            )
        if resolved.user.admin_role is not None:
            raise SafeHTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                error_type="guest_privilege_denied",
                message="Guest privileges are invalid",
            )
    return CurrentUser(
        user=resolved.user,
        identity=resolved.identity,
        profile=resolved.profile,
    )


def require_beta_access(
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CurrentUser:
    """Gate beta product routes with the existing Layer 40 cohort authority."""

    if not request.app.state.settings.beta_access_required:
        return current
    from backend.product_measurement.service import ProductMeasurementService

    if ProductMeasurementService(session).has_active_beta_access(current.user.user_id):
        return current
    raise SafeHTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        error_type="beta_access_required",
        message="Active beta access is required",
    )


def require_admin_read_access(
    current: CurrentUser = Depends(get_current_user),
) -> CurrentAdmin:
    return _require_admin_role(current, ADMIN_READ_ROLES)


def require_data_review_access(
    current: CurrentUser = Depends(get_current_user),
) -> CurrentAdmin:
    return _require_admin_role(current, DATA_REVIEW_ROLES)


def require_admin_mutation_access(
    current: CurrentUser = Depends(get_current_user),
) -> CurrentAdmin:
    return _require_admin_role(current, ADMIN_MUTATION_ROLES)


def _require_admin_role(
    current: CurrentUser,
    allowed_roles: frozenset[AdminRole],
) -> CurrentAdmin:
    role = parse_admin_role(current.user.admin_role)
    if role is None or role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return CurrentAdmin(current=current, role=role)


def _verified_oidc_claims_from_request(request: Request) -> dict[str, Any]:
    state_claims = getattr(request.state, "verified_oidc_claims", None)
    if isinstance(state_claims, dict):
        return dict(state_claims)

    raw_header = request.headers.get(VERIFIED_OIDC_CLAIMS_HEADER)
    if raw_header is not None:
        settings = request.app.state.settings
        if settings.app_env not in {AppEnv.LOCAL, AppEnv.TEST}:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Verified auth middleware is required",
            )
        try:
            claims = json.loads(raw_header)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid verified auth claims",
            ) from exc
        if isinstance(claims, dict):
            return claims
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid verified auth claims",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )
