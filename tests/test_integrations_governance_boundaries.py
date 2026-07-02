from __future__ import annotations

import json

from sqlalchemy.orm import Session

from backend.geography.models import Region
from backend.institutions.models import Organization, OrganizationMembership
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


def _seed_region(session: Session) -> None:
    session.add(
        Region(
            region_id="greater_boston",
            region_name="greater_boston",
            display_name="Greater Boston",
            region_type="greater_region",
        )
    )
    session.flush()


def _seed_org_membership(
    session: Session,
    *,
    organization_id: str,
    user_id: str,
    role: OrganizationRole,
) -> None:
    if session.get(Organization, organization_id) is None:
        session.add(
            Organization(
                organization_id=organization_id,
                name=organization_id.replace("_", " ").title(),
                organization_type="career_center",
                status="active",
            )
        )
        session.flush()
    session.add(
        OrganizationMembership(
            organization_membership_id=(
                f"mem_{organization_id}_{user_id}_{role.value}".replace("|", "_")[:64]
            ),
            organization_id=organization_id,
            user_id=user_id,
            role=role.value,
            status="active",
        )
    )
    session.flush()


def test_user_owned_exports_cannot_be_retrieved_by_another_user(
    api_client,
    session: Session,
) -> None:
    _seed_region(session)
    owner_headers, _ = _current_user_id(api_client, "auth0|export_owner")
    other_headers, _ = _current_user_id(api_client, "auth0|export_other")

    created = api_client.post(
        "/api/integrations/exports",
        headers=owner_headers,
        json={
            "product_object_type": "region",
            "product_object_id": "greater_boston",
            "export_format": "csv",
        },
    )
    export_id = created.json()["data"]["export"]["export_id"]

    response = api_client.get(
        f"/api/integrations/exports/{export_id}",
        headers=other_headers,
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_institution_exports_require_scoped_membership(api_client, session: Session) -> None:
    admin_headers, admin_user_id = _current_user_id(api_client, "auth0|org_admin")
    student_headers, student_user_id = _current_user_id(api_client, "auth0|org_student")
    other_headers, other_user_id = _current_user_id(api_client, "auth0|org_other")
    _seed_org_membership(
        session,
        organization_id="org_a",
        user_id=admin_user_id,
        role=OrganizationRole.ORG_ADMIN,
    )
    _seed_org_membership(
        session,
        organization_id="org_a",
        user_id=student_user_id,
        role=OrganizationRole.STUDENT,
    )
    _seed_org_membership(
        session,
        organization_id="org_b",
        user_id=other_user_id,
        role=OrganizationRole.ORG_ADMIN,
    )

    allowed = api_client.post(
        "/api/integrations/exports",
        headers=admin_headers,
        json={
            "product_object_type": "institutional_dashboard",
            "product_object_id": "org_a",
            "organization_id": "org_a",
            "export_format": "prepared_google_sheets",
        },
    )
    student = api_client.post(
        "/api/integrations/exports",
        headers=student_headers,
        json={
            "product_object_type": "institutional_dashboard",
            "product_object_id": "org_a",
            "organization_id": "org_a",
            "export_format": "csv",
        },
    )
    cross_org = api_client.post(
        "/api/integrations/exports",
        headers=admin_headers,
        json={
            "product_object_type": "institutional_dashboard",
            "product_object_id": "org_b",
            "organization_id": "org_b",
            "export_format": "csv",
        },
    )

    assert allowed.status_code == 201
    assert allowed.json()["data"]["export"]["receipt"]["permission_decision"]["boundary"] == (
        "organization_membership"
    )
    assert student.status_code == 403
    assert cross_org.status_code == 403


def test_external_destinations_do_not_define_product_semantics(
    api_client,
    session: Session,
) -> None:
    _seed_region(session)
    headers, _ = _current_user_id(api_client, "auth0|semantics_user")

    created = api_client.post(
        "/api/integrations/exports",
        headers=headers,
        json={
            "product_object_type": "region",
            "product_object_id": "greater_boston",
            "export_format": "prepared_airtable",
        },
    )

    payload = created.json()["data"]["export"]["payload"]
    receipt = created.json()["data"]["export"]["receipt"]
    assert payload["destination_defines_product_semantics"] is False
    assert payload["product_authority_retained"] is True
    assert receipt["product_authority_retained"] is True
    assert receipt["external_write_performed"] is False
