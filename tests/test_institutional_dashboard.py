from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.institutions.models import (
    InstitutionalAuditLog,
    Organization,
    OrganizationMembership,
)
from backend.institutions.roles import (
    InstitutionalAuditAction,
    OrganizationRole,
)
from backend.users.models import SavedMarketArtifact, UserPreferenceProfile


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
            organization_type="career_center",
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
) -> None:
    session.add(
        OrganizationMembership(
            organization_membership_id=(
                f"mem_{organization_id}_{user_id}_{role.value}".replace("|", "_")[:64]
            ),
            organization_id=organization_id,
            user_id=user_id,
            role=role.value,
            status=status,
        )
    )
    session.flush()


def _seed_market_context(session: Session) -> None:
    session.add_all(
        [
            Region(
                region_id="greater_boston",
                region_name="Greater Boston",
                display_name="Greater Boston",
                region_type="metro",
            ),
            Region(
                region_id="stealth_market",
                region_name="Stealth Market",
                display_name="Stealth Market",
                region_type="metro",
            ),
            Company(
                company_id="comp_alpha",
                company_name="Alpha Systems",
                normalized_company_name="alpha systems",
            ),
            Company(
                company_id="comp_hidden",
                company_name="Hidden Company",
                normalized_company_name="hidden company",
            ),
            CompanyRegionHiring(
                hiring_id="hire_alpha_boston",
                company_id="comp_alpha",
                region_id="greater_boston",
                currently_hiring_flag=True,
                active_posting_count_now=12,
                annualized_trend_signal="increasing",
                hiring_confidence="medium",
            ),
        ]
    )
    session.flush()


def _seed_student_inputs(
    session: Session,
    *,
    user_id: str,
    regions: list[str],
    roles: list[str],
    companies: list[str],
) -> None:
    session.add(
        UserPreferenceProfile(
            user_id=user_id,
            role_interests=roles,
            industry_interests=["software"],
            preferred_regions=regions,
        )
    )
    for company_id in companies:
        session.add(
            SavedMarketArtifact(
                saved_artifact_id=f"saved_{user_id}_{company_id}".replace("|", "_")[:64],
                user_id=user_id,
                artifact_type="company",
                artifact_ref=company_id,
                label=None,
                snapshot={"source": "test"},
            )
        )
    session.flush()


def _seed_dashboard_org(
    api_client,
    session: Session,
    organization_id: str,
) -> dict[str, tuple[dict[str, str], str]]:
    principals = {
        name: _current_user_id(api_client, f"auth0|{organization_id}_{name}")
        for name in (
            "admin",
            "advisor",
            "report",
            "student1",
            "student2",
            "student3",
            "student4",
            "student5",
        )
    }
    _seed_org(session, organization_id, name="Institution Demo")
    _seed_membership(
        session,
        organization_id=organization_id,
        user_id=principals["admin"][1],
        role=OrganizationRole.ORG_ADMIN,
    )
    _seed_membership(
        session,
        organization_id=organization_id,
        user_id=principals["advisor"][1],
        role=OrganizationRole.ADVISOR,
    )
    _seed_membership(
        session,
        organization_id=organization_id,
        user_id=principals["report"][1],
        role=OrganizationRole.REPORT_VIEWER,
    )
    for student_name in ("student1", "student2", "student3", "student4", "student5"):
        _seed_membership(
            session,
            organization_id=organization_id,
            user_id=principals[student_name][1],
            role=OrganizationRole.STUDENT,
        )
    _seed_student_inputs(
        session,
        user_id=principals["student1"][1],
        regions=["greater_boston", "stealth_market"],
        roles=["product", "secret_role"],
        companies=["comp_alpha", "comp_hidden"],
    )
    _seed_student_inputs(
        session,
        user_id=principals["student2"][1],
        regions=["greater_boston"],
        roles=["product"],
        companies=["comp_alpha"],
    )
    _seed_student_inputs(
        session,
        user_id=principals["student3"][1],
        regions=["greater_boston"],
        roles=["product"],
        companies=["comp_alpha"],
    )
    _seed_student_inputs(
        session,
        user_id=principals["student4"][1],
        regions=["greater_boston"],
        roles=["product"],
        companies=["comp_alpha"],
    )
    _seed_student_inputs(
        session,
        user_id=principals["student5"][1],
        regions=["greater_boston"],
        roles=["product"],
        companies=["comp_alpha"],
    )
    return principals


def _dashboard_url(organization_id: str, *, minimum_group_size: int = 5) -> str:
    return (
        f"/api/institutions/organizations/{organization_id}/dashboard"
        f"?minimum_group_size={minimum_group_size}"
    )


def test_org_admin_can_view_own_aggregate_dashboard_and_audit_is_recorded(
    api_client,
    session: Session,
) -> None:
    _seed_market_context(session)
    principals = _seed_dashboard_org(api_client, session, "dash_admin_org")

    response = api_client.get(
        _dashboard_url("dash_admin_org"),
        headers=principals["admin"][0],
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["organization_id"] == "dash_admin_org"
    assert data["minimum_group_size"] == 5
    assert data["cohort_size"] == 5
    assert data["popular_target_markets"][0]["label"] == "Greater Boston"
    assert data["popular_target_markets"][0]["count"] == 5
    assert data["role_interest_summary"][0]["label"] == "Product"
    assert data["saved_company_summary"][0]["label"] == "Alpha Systems"
    assert data["market_demand_trends"][0]["metadata"]["trend_signal"] == "increasing"
    assert data["coverage_warnings"]

    audit_rows = session.execute(
        select(InstitutionalAuditLog).where(
            InstitutionalAuditLog.organization_id == "dash_admin_org",
            InstitutionalAuditLog.action
            == InstitutionalAuditAction.INSTITUTION_DASHBOARD_VIEWED.value,
        )
    ).scalars().all()
    assert len(audit_rows) == 1
    assert audit_rows[0].actor_user_id == principals["admin"][1]


def test_advisor_and_report_viewer_can_view_own_aggregate_dashboard(
    api_client,
    session: Session,
) -> None:
    _seed_market_context(session)
    principals = _seed_dashboard_org(api_client, session, "dash_surface_org")

    advisor_response = api_client.get(
        _dashboard_url("dash_surface_org"),
        headers=principals["advisor"][0],
    )
    report_response = api_client.get(
        _dashboard_url("dash_surface_org"),
        headers=principals["report"][0],
    )

    assert advisor_response.status_code == 200
    assert report_response.status_code == 200
    assert advisor_response.json()["data"]["saved_company_summary"][0]["label"] == (
        "Alpha Systems"
    )
    assert report_response.json()["data"]["popular_target_markets"][0]["label"] == (
        "Greater Boston"
    )


def test_student_and_inactive_membership_cannot_view_institution_dashboard(
    api_client,
    session: Session,
) -> None:
    _seed_market_context(session)
    principals = _seed_dashboard_org(api_client, session, "dash_denied_org")
    inactive_headers, inactive_id = _current_user_id(api_client, "auth0|dash_inactive")
    _seed_membership(
        session,
        organization_id="dash_denied_org",
        user_id=inactive_id,
        role=OrganizationRole.ORG_ADMIN,
        status="inactive",
    )

    student_response = api_client.get(
        _dashboard_url("dash_denied_org") + "&role=ORG_ADMIN",
        headers=principals["student1"][0],
    )
    inactive_response = api_client.get(
        _dashboard_url("dash_denied_org"),
        headers=inactive_headers,
    )

    assert student_response.status_code == 403
    assert inactive_response.status_code == 403


def test_cross_org_dashboard_access_is_denied(
    api_client,
    session: Session,
) -> None:
    _seed_market_context(session)
    org_a = _seed_dashboard_org(api_client, session, "dash_org_a")
    org_b = _seed_dashboard_org(api_client, session, "dash_org_b")

    advisor_response = api_client.get(
        _dashboard_url("dash_org_b"),
        headers=org_a["advisor"][0],
    )
    admin_response = api_client.get(
        _dashboard_url("dash_org_b"),
        headers=org_a["admin"][0],
    )
    own_response = api_client.get(
        _dashboard_url("dash_org_b"),
        headers=org_b["admin"][0],
    )

    assert advisor_response.status_code == 403
    assert admin_response.status_code == 403
    assert own_response.status_code == 200


def test_low_sample_categories_are_suppressed_without_hidden_labels_or_counts(
    api_client,
    session: Session,
) -> None:
    _seed_market_context(session)
    principals = _seed_dashboard_org(api_client, session, "dash_privacy_org")

    response = api_client.get(
        _dashboard_url("dash_privacy_org"),
        headers=principals["admin"][0],
    )

    assert response.status_code == 200
    data = response.json()["data"]
    payload_text = json.dumps(data)
    assert "Stealth Market" not in payload_text
    assert "Hidden Company" not in payload_text
    assert "secret_role" not in payload_text
    assert principals["student1"][1] not in payload_text
    assert principals["student2"][1] not in payload_text
    assert "saved_artifact_id" not in payload_text
    assert "recommendation_snapshot_id" not in payload_text

    suppressed_items = [
        item for item in data["popular_target_markets"] if item["suppressed"]
    ]
    assert suppressed_items == [
        {
            "label": "Other / insufficient sample size",
            "count": None,
            "percentage": None,
            "category": "target_market",
            "suppressed": True,
            "suppression_reason": "minimum_group_size_not_met",
            "source_count": 1,
            "coverage": None,
            "confidence": "suppressed",
            "metadata": {"minimum_group_size": 5},
        }
    ]
    assert {
        "section": "popular_target_markets",
        "suppressed_count": 1,
        "suppression_reason": "minimum_group_size_not_met",
        "minimum_group_size": 5,
    } in data["suppressed_categories"]


def test_minimum_group_threshold_suppresses_otherwise_visible_categories(
    api_client,
    session: Session,
) -> None:
    _seed_market_context(session)
    principals = _seed_dashboard_org(api_client, session, "dash_threshold_org")

    response = api_client.get(
        _dashboard_url("dash_threshold_org", minimum_group_size=6),
        headers=principals["admin"][0],
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["minimum_group_size"] == 6
    assert "Greater Boston" not in json.dumps(data["popular_target_markets"])
    assert data["popular_target_markets"][0]["suppressed"] is True
    assert data["market_demand_trends"] == []
    assert data["coverage_gaps"] == []
    assert any(
        row["section"] == "popular_target_markets"
        and row["minimum_group_size"] == 6
        for row in data["suppressed_categories"]
    )


def test_dashboard_rejects_unsafe_low_minimum_group_override(
    api_client,
    session: Session,
) -> None:
    _seed_market_context(session)
    principals = _seed_dashboard_org(api_client, session, "dash_low_threshold_org")

    response = api_client.get(
        _dashboard_url("dash_low_threshold_org", minimum_group_size=4),
        headers=principals["admin"][0],
    )

    assert response.status_code == 422
