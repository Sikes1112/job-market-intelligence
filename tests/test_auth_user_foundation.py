from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.auth.boundary import (
    AuthBoundaryError,
    ExternalAuthPrincipal,
    principal_from_verified_oidc_claims,
)
from backend.companies.models import Company
from backend.geography.models import Region
from backend.users.models import ExternalAuthIdentity, User, UserProfile
from backend.users.repository import UserRepository
from backend.users.service import UserIdentityService


def _service(session: Session) -> UserIdentityService:
    return UserIdentityService(UserRepository(session))


def _principal(**overrides) -> ExternalAuthPrincipal:
    defaults = dict(
        provider="auth0",
        issuer="https://jmi.us.auth0.com/",
        subject="auth0|abc123",
        email="person@example.com",
        email_verified=True,
        display_name="Example Person",
        avatar_url="https://cdn.example.com/avatar.png",
    )
    defaults.update(overrides)
    return ExternalAuthPrincipal(**defaults)


def test_principal_requires_stable_provider_identity() -> None:
    with pytest.raises(AuthBoundaryError):
        ExternalAuthPrincipal(provider="auth0", issuer="", subject="auth0|abc123")
    with pytest.raises(AuthBoundaryError):
        ExternalAuthPrincipal(provider="auth0", issuer="https://issuer/", subject=" ")


def test_principal_can_be_built_from_verified_oidc_claims() -> None:
    principal = principal_from_verified_oidc_claims(
        {
            "iss": "https://jmi.us.auth0.com/",
            "sub": "auth0|abc123",
            "email": "person@example.com",
            "email_verified": True,
            "name": "Example Person",
            "picture": "https://cdn.example.com/avatar.png",
        }
    )

    assert principal.identity_key == (
        "auth0",
        "https://jmi.us.auth0.com/",
        "auth0|abc123",
    )
    assert principal.email_verified is True


def test_principal_from_claims_rejects_missing_subject() -> None:
    with pytest.raises(AuthBoundaryError):
        principal_from_verified_oidc_claims({"iss": "https://jmi.us.auth0.com/"})


def test_user_model_maps_external_identity_to_internal_user(session: Session) -> None:
    result = _service(session).resolve_external_principal(_principal())

    assert result.created_user is True
    assert result.created_identity is True
    assert result.user.user_id.startswith("user_")
    assert result.user.status == "active"
    assert result.user.admin_role is None
    assert result.identity.user_id == result.user.user_id
    assert result.identity.provider == "auth0"
    assert result.identity.issuer == "https://jmi.us.auth0.com/"
    assert result.identity.subject == "auth0|abc123"
    assert result.profile.user_id == result.user.user_id
    assert result.profile.email == "person@example.com"
    assert result.profile.display_name == "Example Person"


def test_same_external_identity_reuses_internal_user(session: Session) -> None:
    svc = _service(session)
    first = svc.resolve_external_principal(_principal())
    second = svc.resolve_external_principal(
        _principal(email="renamed@example.com", display_name="Renamed")
    )

    assert second.created_user is False
    assert second.created_identity is False
    assert second.user.user_id == first.user.user_id
    assert second.identity.external_identity_id == first.identity.external_identity_id
    assert second.identity.email == "renamed@example.com"
    assert second.profile.display_name == "Renamed"


def test_same_subject_from_different_issuer_creates_distinct_user(
    session: Session,
) -> None:
    svc = _service(session)
    first = svc.resolve_external_principal(_principal())
    second = svc.resolve_external_principal(
        _principal(issuer="https://other-tenant.auth0.com/")
    )

    assert second.user.user_id != first.user.user_id
    assert session.query(User).count() == 2
    assert session.query(ExternalAuthIdentity).count() == 2


def test_email_is_not_used_as_identity_key(session: Session) -> None:
    svc = _service(session)
    first = svc.resolve_external_principal(_principal(subject="auth0|first"))
    second = svc.resolve_external_principal(_principal(subject="auth0|second"))

    assert first.profile.email == second.profile.email
    assert first.user.user_id != second.user.user_id


def test_external_identity_unique_boundary_is_enforced(session: Session) -> None:
    user = User(user_id="user_manual")
    session.add(user)
    session.flush()
    session.add_all(
        [
            ExternalAuthIdentity(
                external_identity_id="identity_1",
                user_id=user.user_id,
                provider="auth0",
                issuer="https://jmi.us.auth0.com/",
                subject="auth0|abc123",
            ),
            ExternalAuthIdentity(
                external_identity_id="identity_2",
                user_id=user.user_id,
                provider="auth0",
                issuer="https://jmi.us.auth0.com/",
                subject="auth0|abc123",
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        session.flush()


def test_user_profile_has_no_saved_preference_fields(session: Session) -> None:
    columns = set(UserProfile.__table__.columns.keys())

    assert {"user_id", "display_name", "email", "avatar_url"}.issubset(columns)
    assert "role_targets" not in columns
    assert "saved_markets" not in columns
    assert "recommendation_snapshot" not in columns


def test_identity_mapping_does_not_touch_market_truth(session: Session) -> None:
    session.add_all(
        [
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
                region_type="greater_region",
            ),
            Company(
                company_id="comp_a",
                company_name="A",
                normalized_company_name="a",
                eligibility_status="eligible",
            ),
        ]
    )
    session.flush()
    region = session.get(Region, "greater_boston")
    company = session.get(Company, "comp_a")
    region_version = region.version
    company_version = company.version

    _service(session).resolve_external_principal(_principal())

    session.refresh(region)
    session.refresh(company)
    assert region.version == region_version
    assert company.version == company_version
