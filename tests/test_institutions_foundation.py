from __future__ import annotations

import json

from sqlalchemy.orm import Session

from backend.institutions.models import (
    InstitutionalAuditLog,
    Organization,
    OrganizationMembership,
)
from backend.institutions.permissions import (
    can_access_audit_logs,
    can_access_student_private_data,
    can_administer_organization,
    can_view_organization_surfaces,
    is_active_member,
)
from backend.institutions.repository import InstitutionRepository
from backend.institutions.roles import OrganizationRole


def _auth_headers(subject: str) -> dict[str, str]:
    suffix = subject.split("|")[-1]
    claims = {
        "iss": "https://jmi.us.auth0.com/",
        "sub": subject,
        "email": f"{suffix}@example.com",
        "email_verified": True,
        "name": f"User {suffix}",
    }
    return {"X-Verified-OIDC-Claims": json.dumps(claims)}


def _current_user_id(api_client, subject: str) -> tuple[dict[str, str], str]:
    headers = _auth_headers(subject)
    response = api_client.get("/me", headers=headers)
    assert response.status_code == 200
    return headers, response.json()["data"]["user"]["user_id"]


def _seed_org(session: Session, organization_id: str, *, name: str | None = None) -> None:
    session.add(
        Organization(
            organization_id=organization_id,
            name=name or organization_id.replace("_", " ").title(),
            organization_type="school",
            status="active",
        )
    )
    session.flush()


def _seed_membership(
    session: Session,
    *,
    organization_id: str,
    user_id: str,
    role: OrganizationRole,
    status: str = "active",
) -> str:
    membership_id = f"mem_{organization_id}_{user_id}_{role.value}".replace("|", "_")
    session.add(
        OrganizationMembership(
            organization_membership_id=membership_id[:64],
            organization_id=organization_id,
            user_id=user_id,
            role=role.value,
            status=status,
        )
    )
    session.flush()
    return membership_id[:64]


def test_permission_helpers_enforce_role_and_status_stance(
    session: Session,
    api_client,
) -> None:
    _admin_headers, admin_id = _current_user_id(api_client, "auth0|inst_admin")
    _advisor_headers, advisor_id = _current_user_id(api_client, "auth0|inst_advisor")
    _student_headers, student_id = _current_user_id(api_client, "auth0|inst_student")
    _report_headers, report_id = _current_user_id(api_client, "auth0|inst_report")
    _inactive_headers, inactive_id = _current_user_id(api_client, "auth0|inst_inactive")
    _seed_org(session, "org_permissions")
    _seed_membership(
        session,
        organization_id="org_permissions",
        user_id=admin_id,
        role=OrganizationRole.ORG_ADMIN,
    )
    _seed_membership(
        session,
        organization_id="org_permissions",
        user_id=advisor_id,
        role=OrganizationRole.ADVISOR,
    )
    _seed_membership(
        session,
        organization_id="org_permissions",
        user_id=student_id,
        role=OrganizationRole.STUDENT,
    )
    _seed_membership(
        session,
        organization_id="org_permissions",
        user_id=report_id,
        role=OrganizationRole.REPORT_VIEWER,
    )
    _seed_membership(
        session,
        organization_id="org_permissions",
        user_id=inactive_id,
        role=OrganizationRole.ORG_ADMIN,
        status="inactive",
    )
    repo = InstitutionRepository(session)

    assert is_active_member(repo, user_id=admin_id, organization_id="org_permissions")
    assert can_administer_organization(
        repo,
        user_id=admin_id,
        organization_id="org_permissions",
    )
    assert can_view_organization_surfaces(
        repo,
        user_id=advisor_id,
        organization_id="org_permissions",
    )
    assert can_view_organization_surfaces(
        repo,
        user_id=report_id,
        organization_id="org_permissions",
    )
    assert not can_view_organization_surfaces(
        repo,
        user_id=student_id,
        organization_id="org_permissions",
    )
    assert can_access_audit_logs(
        repo,
        user_id=admin_id,
        organization_id="org_permissions",
    )
    assert not can_access_audit_logs(
        repo,
        user_id=advisor_id,
        organization_id="org_permissions",
    )
    assert not is_active_member(
        repo,
        user_id=inactive_id,
        organization_id="org_permissions",
    )
    assert not can_access_student_private_data(
        repo,
        user_id=admin_id,
        organization_id="org_permissions",
        student_user_id=student_id,
    )


def test_current_organizations_returns_only_current_active_memberships(
    api_client,
    session: Session,
) -> None:
    headers, user_id = _current_user_id(api_client, "auth0|current_member")
    _other_headers, other_id = _current_user_id(api_client, "auth0|other_member")
    _seed_org(session, "org_current_active")
    _seed_org(session, "org_current_inactive")
    _seed_org(session, "org_other")
    _seed_membership(
        session,
        organization_id="org_current_active",
        user_id=user_id,
        role=OrganizationRole.STUDENT,
    )
    _seed_membership(
        session,
        organization_id="org_current_inactive",
        user_id=user_id,
        role=OrganizationRole.ORG_ADMIN,
        status="inactive",
    )
    _seed_membership(
        session,
        organization_id="org_other",
        user_id=other_id,
        role=OrganizationRole.ORG_ADMIN,
    )

    response = api_client.get("/api/institutions/organizations/current", headers=headers)

    assert response.status_code == 200
    organizations = response.json()["data"]["organizations"]
    assert [row["organization"]["organization_id"] for row in organizations] == [
        "org_current_active"
    ]
    assert organizations[0]["membership"]["role"] == OrganizationRole.STUDENT.value


def test_user_in_one_organization_cannot_access_another_organization_endpoint(
    api_client,
    session: Session,
) -> None:
    headers, user_id = _current_user_id(api_client, "auth0|org_a_user")
    _other_headers, other_id = _current_user_id(api_client, "auth0|org_b_user")
    _seed_org(session, "org_a")
    _seed_org(session, "org_b")
    _seed_membership(
        session,
        organization_id="org_a",
        user_id=user_id,
        role=OrganizationRole.ADVISOR,
    )
    _seed_membership(
        session,
        organization_id="org_b",
        user_id=other_id,
        role=OrganizationRole.ORG_ADMIN,
    )

    response = api_client.get("/api/institutions/organizations/org_b", headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_advisor_cannot_access_other_organization_members(
    api_client,
    session: Session,
) -> None:
    headers, advisor_id = _current_user_id(api_client, "auth0|advisor_a")
    _admin_headers, admin_id = _current_user_id(api_client, "auth0|admin_b")
    _seed_org(session, "advisor_org_a")
    _seed_org(session, "advisor_org_b")
    _seed_membership(
        session,
        organization_id="advisor_org_a",
        user_id=advisor_id,
        role=OrganizationRole.ADVISOR,
    )
    _seed_membership(
        session,
        organization_id="advisor_org_b",
        user_id=admin_id,
        role=OrganizationRole.ORG_ADMIN,
    )

    response = api_client.get(
        "/api/institutions/organizations/advisor_org_b/members",
        headers=headers,
    )

    assert response.status_code == 403


def test_student_cannot_access_institution_wide_surfaces(
    api_client,
    session: Session,
) -> None:
    headers, student_id = _current_user_id(api_client, "auth0|student_member")
    _seed_org(session, "student_org")
    _seed_membership(
        session,
        organization_id="student_org",
        user_id=student_id,
        role=OrganizationRole.STUDENT,
    )

    organization = api_client.get(
        "/api/institutions/organizations/student_org",
        headers=headers,
    )
    members = api_client.get(
        "/api/institutions/organizations/student_org/members",
        headers=headers,
    )

    assert organization.status_code == 403
    assert members.status_code == 403


def test_inactive_membership_does_not_authorize_institutional_access(
    api_client,
    session: Session,
) -> None:
    headers, user_id = _current_user_id(api_client, "auth0|inactive_admin")
    _seed_org(session, "inactive_org")
    _seed_membership(
        session,
        organization_id="inactive_org",
        user_id=user_id,
        role=OrganizationRole.ORG_ADMIN,
        status="inactive",
    )

    response = api_client.get(
        "/api/institutions/organizations/inactive_org/members",
        headers=headers,
    )

    assert response.status_code == 403


def test_report_viewer_cannot_manage_members_even_if_payload_claims_admin(
    api_client,
    session: Session,
) -> None:
    headers, report_viewer_id = _current_user_id(api_client, "auth0|report_viewer")
    _target_headers, target_user_id = _current_user_id(api_client, "auth0|target_user")
    _seed_org(session, "report_view_org")
    _seed_membership(
        session,
        organization_id="report_view_org",
        user_id=report_viewer_id,
        role=OrganizationRole.REPORT_VIEWER,
    )

    response = api_client.post(
        "/api/institutions/organizations/report_view_org/members",
        headers=headers,
        json={
            "user_id": target_user_id,
            "role": OrganizationRole.ORG_ADMIN.value,
            "status": "active",
        },
    )

    assert response.status_code == 403
    assert (
        session.query(OrganizationMembership)
        .filter_by(organization_id="report_view_org", user_id=target_user_id)
        .count()
        == 0
    )


def test_org_admin_can_list_own_members_and_audit_access(
    api_client,
    session: Session,
) -> None:
    headers, admin_id = _current_user_id(api_client, "auth0|own_org_admin")
    _student_headers, student_id = _current_user_id(api_client, "auth0|own_org_student")
    _seed_org(session, "own_org")
    _seed_membership(
        session,
        organization_id="own_org",
        user_id=admin_id,
        role=OrganizationRole.ORG_ADMIN,
    )
    _seed_membership(
        session,
        organization_id="own_org",
        user_id=student_id,
        role=OrganizationRole.STUDENT,
    )

    response = api_client.get(
        "/api/institutions/organizations/own_org/members",
        headers=headers,
    )

    assert response.status_code == 200
    members = response.json()["data"]["members"]
    assert {row["user_id"] for row in members} == {admin_id, student_id}
    assert "email" not in json.dumps(members).casefold()
    audit = session.query(InstitutionalAuditLog).one()
    assert audit.organization_id == "own_org"
    assert audit.actor_user_id == admin_id
    assert audit.actor_role == OrganizationRole.ORG_ADMIN.value
    assert audit.action == "organization_members_viewed"


def test_org_admin_cannot_access_another_organization_member_list(
    api_client,
    session: Session,
) -> None:
    headers, admin_a_id = _current_user_id(api_client, "auth0|admin_a")
    _admin_b_headers, admin_b_id = _current_user_id(api_client, "auth0|admin_b2")
    _seed_org(session, "admin_org_a")
    _seed_org(session, "admin_org_b")
    _seed_membership(
        session,
        organization_id="admin_org_a",
        user_id=admin_a_id,
        role=OrganizationRole.ORG_ADMIN,
    )
    _seed_membership(
        session,
        organization_id="admin_org_b",
        user_id=admin_b_id,
        role=OrganizationRole.ORG_ADMIN,
    )

    response = api_client.get(
        "/api/institutions/organizations/admin_org_b/members",
        headers=headers,
    )

    assert response.status_code == 403


def test_org_admin_can_add_and_update_members_with_audit_records(
    api_client,
    session: Session,
) -> None:
    headers, admin_id = _current_user_id(api_client, "auth0|manage_admin")
    _target_headers, target_user_id = _current_user_id(api_client, "auth0|manage_target")
    _seed_org(session, "manage_org")
    _seed_membership(
        session,
        organization_id="manage_org",
        user_id=admin_id,
        role=OrganizationRole.ORG_ADMIN,
    )

    created = api_client.post(
        "/api/institutions/organizations/manage_org/members",
        headers=headers,
        json={
            "user_id": target_user_id,
            "role": OrganizationRole.ADVISOR.value,
            "status": "active",
        },
    )
    assert created.status_code == 201
    membership_id = created.json()["data"]["membership"]["organization_membership_id"]

    updated = api_client.patch(
        f"/api/institutions/organizations/manage_org/members/{membership_id}",
        headers=headers,
        json={"role": OrganizationRole.REPORT_VIEWER.value, "status": "inactive"},
    )

    assert updated.status_code == 200
    membership = updated.json()["data"]["membership"]
    assert membership["role"] == OrganizationRole.REPORT_VIEWER.value
    assert membership["status"] == "inactive"
    actions = [
        row.action
        for row in session.query(InstitutionalAuditLog).order_by(
            InstitutionalAuditLog.created_at,
            InstitutionalAuditLog.institutional_audit_log_id,
        )
    ]
    assert actions == ["organization_member_added", "organization_member_updated"]

