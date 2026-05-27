from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.institutions.models import (
    InstitutionalAuditLog,
    InstitutionalDataRequest,
    InstitutionalReport,
    Organization,
    OrganizationMembership,
)
from backend.institutions.roles import InstitutionalAuditAction, OrganizationRole
from backend.users.models import (
    PersonalizedRecommendationSnapshot,
    SavedMarketArtifact,
    UserPreferenceProfile,
)


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


def _seed_org(session: Session, organization_id: str) -> None:
    session.add(
        Organization(
            organization_id=organization_id,
            name=organization_id.replace("_", " ").title(),
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
                region_id="hidden_market",
                region_name="Hidden Market",
                display_name="Hidden Market",
                region_type="metro",
            ),
            Company(
                company_id="comp_alpha",
                company_name="Alpha Systems",
                normalized_company_name="alpha systems",
                sector_primary="software",
            ),
            Company(
                company_id="comp_secret",
                company_name="Secret Student Company",
                normalized_company_name="secret student company",
                sector_primary="software",
            ),
        ]
    )
    session.flush()
    session.add(
        CompanyRegionHiring(
            hiring_id="hire_alpha_boston_reports",
            company_id="comp_alpha",
            region_id="greater_boston",
            currently_hiring_flag=True,
            active_posting_count_now=18,
            posting_count_90d=40,
            annualized_trend_signal="increasing",
            seasonal_student_hiring_signal="fall",
            hiring_confidence="medium",
        )
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
    session.flush()
    for company_id in companies:
        session.add(
            SavedMarketArtifact(
                saved_artifact_id=f"saved_report_{user_id}_{company_id}".replace("|", "_")[
                    :64
                ],
                user_id=user_id,
                artifact_type="company",
                artifact_ref=company_id,
                label=None,
                snapshot={"private": company_id == "comp_secret"},
            )
        )
    session.add(
        PersonalizedRecommendationSnapshot(
            recommendation_snapshot_id=f"rec_report_{user_id[-12:]}",
            user_id=user_id,
            preference_profile_id=user_id,
            personalized_output={"private_recommendation": "do not expose"},
            recommendation_version="test",
            source_version_bundle={},
            objective_output_refs=[],
            recommendation_inputs_hash=f"hash_report_{user_id[-12:]}",
            generated_at=datetime.now(UTC),
        )
    )
    session.flush()


def _seed_principals(
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
            "inactive",
        )
    }
    _seed_org(session, organization_id)
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
    _seed_membership(
        session,
        organization_id=organization_id,
        user_id=principals["inactive"][1],
        role=OrganizationRole.ORG_ADMIN,
        status="inactive",
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
        regions=["greater_boston", "hidden_market"],
        roles=["product", "secret_student_role"],
        companies=["comp_alpha", "comp_secret"],
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


def _report_url(organization_id: str, report_id: str | None = None) -> str:
    base = f"/api/institutions/organizations/{organization_id}/reports"
    return f"{base}/{report_id}" if report_id else base


def _data_request_url(organization_id: str) -> str:
    return f"/api/institutions/organizations/{organization_id}/data-requests"


def test_org_admin_can_generate_list_and_view_privacy_aware_report(
    api_client,
    session: Session,
) -> None:
    _seed_market_context(session)
    principals = _seed_principals(api_client, session, "reports_admin_org")

    generated = api_client.post(
        _report_url("reports_admin_org"),
        headers=principals["admin"][0],
        json={"report_type": "career_services", "minimum_group_size": 5},
    )

    assert generated.status_code == 201
    report = generated.json()["data"]["report"]
    assert report["report_type"] == "career_services"
    assert report["minimum_group_size"] == 5
    assert report["sections"]
    assert report["privacy_suppressions"]
    assert report["coverage_warnings"]
    assert report["limitations"]
    assert report["data_freshness"]
    assert report["export_options"] == {
        "pdf": "deferred",
        "csv": "deferred",
        "powerpoint": "deferred",
    }
    report_text = json.dumps(report)
    for student_name in ("student1", "student2", "student3"):
        assert principals[student_name][1] not in report_text
    assert "secret_student_role" not in report_text
    assert "Secret Student Company" not in report_text
    assert "private_recommendation" not in report_text
    assert "personalized_output" not in report_text

    listed = api_client.get(
        _report_url("reports_admin_org"),
        headers=principals["admin"][0],
    )
    viewed = api_client.get(
        _report_url("reports_admin_org", report["report_id"]),
        headers=principals["admin"][0],
    )

    assert listed.status_code == 200
    assert listed.json()["data"]["reports"][0]["report_id"] == report["report_id"]
    assert viewed.status_code == 200
    assert viewed.json()["data"]["report"]["report_id"] == report["report_id"]
    assert session.query(InstitutionalReport).count() == 1

    actions = {
        row.action
        for row in session.execute(
            select(InstitutionalAuditLog).where(
                InstitutionalAuditLog.organization_id == "reports_admin_org"
            )
        ).scalars()
    }
    assert InstitutionalAuditAction.INSTITUTIONAL_REPORT_GENERATED.value in actions
    assert InstitutionalAuditAction.INSTITUTIONAL_REPORTS_LISTED.value in actions
    assert InstitutionalAuditAction.INSTITUTIONAL_REPORT_VIEWED.value in actions


def test_report_permissions_deny_students_inactive_and_cross_org_access(
    api_client,
    session: Session,
) -> None:
    _seed_market_context(session)
    org_a = _seed_principals(api_client, session, "reports_org_a")
    org_b = _seed_principals(api_client, session, "reports_org_b")
    body = {"report_type": "program_director", "minimum_group_size": 5}

    advisor_response = api_client.post(
        _report_url("reports_org_a"),
        headers=org_a["advisor"][0],
        json=body,
    )
    report_viewer_response = api_client.post(
        _report_url("reports_org_a"),
        headers=org_a["report"][0],
        json={"report_type": "workforce_planner", "minimum_group_size": 5},
    )
    student_response = api_client.post(
        _report_url("reports_org_a"),
        headers=org_a["student1"][0],
        json=body,
    )
    inactive_response = api_client.post(
        _report_url("reports_org_a"),
        headers=org_a["inactive"][0],
        json=body,
    )
    cross_org_response = api_client.post(
        _report_url("reports_org_b"),
        headers=org_a["admin"][0],
        json=body,
    )

    assert advisor_response.status_code == 201
    assert report_viewer_response.status_code == 201
    assert student_response.status_code == 403
    assert inactive_response.status_code == 403
    assert cross_org_response.status_code == 403
    assert api_client.get(
        _report_url("reports_org_b"),
        headers=org_b["report"][0],
    ).status_code == 200


def test_report_generation_rejects_unsafe_low_minimum_group_override(
    api_client,
    session: Session,
) -> None:
    _seed_market_context(session)
    principals = _seed_principals(api_client, session, "reports_low_threshold_org")

    response = api_client.post(
        _report_url("reports_low_threshold_org"),
        headers=principals["admin"][0],
        json={"report_type": "career_services", "minimum_group_size": 4},
    )

    assert response.status_code == 422


def test_data_request_records_are_auditable_and_do_not_execute_export_or_deletion(
    api_client,
    session: Session,
) -> None:
    _seed_market_context(session)
    principals = _seed_principals(api_client, session, "data_request_org")

    created = api_client.post(
        _data_request_url("data_request_org"),
        headers=principals["admin"][0],
        json={
            "request_type": "organization_export",
            "reason": "annual audit packet",
        },
    )
    listed = api_client.get(
        _data_request_url("data_request_org"),
        headers=principals["admin"][0],
    )

    assert created.status_code == 201
    data_request = created.json()["data"]["data_request"]
    assert data_request["request_type"] == "organization_export"
    assert data_request["subject_type"] == "organization"
    assert data_request["status"] == "pending"
    assert "not executed" in data_request["execution_note"]
    assert listed.status_code == 200
    assert listed.json()["data"]["data_requests"][0]["data_request_id"] == (
        data_request["data_request_id"]
    )
    assert session.query(Organization).filter_by(organization_id="data_request_org").one()
    assert session.query(OrganizationMembership).filter_by(
        organization_id="data_request_org"
    ).count() == 9
    assert session.query(InstitutionalDataRequest).count() == 1

    actions = {
        row.action
        for row in session.execute(
            select(InstitutionalAuditLog).where(
                InstitutionalAuditLog.organization_id == "data_request_org"
            )
        ).scalars()
    }
    assert InstitutionalAuditAction.INSTITUTIONAL_DATA_REQUEST_CREATED.value in actions
    assert InstitutionalAuditAction.INSTITUTIONAL_DATA_REQUESTS_LISTED.value in actions


def test_student_can_create_only_own_student_data_request(
    api_client,
    session: Session,
) -> None:
    _seed_market_context(session)
    principals = _seed_principals(api_client, session, "student_request_org")

    own = api_client.post(
        _data_request_url("student_request_org"),
        headers=principals["student1"][0],
        json={
            "request_type": "student_deletion",
            "subject_user_id": principals["student1"][1],
            "reason": "student initiated request",
        },
    )
    other_student = api_client.post(
        _data_request_url("student_request_org"),
        headers=principals["student1"][0],
        json={
            "request_type": "student_export",
            "subject_user_id": principals["student2"][1],
        },
    )
    student_org_request = api_client.post(
        _data_request_url("student_request_org"),
        headers=principals["student1"][0],
        json={"request_type": "organization_export"},
    )
    listed = api_client.get(
        _data_request_url("student_request_org"),
        headers=principals["student1"][0],
    )
    admin_list = api_client.get(
        _data_request_url("student_request_org"),
        headers=principals["admin"][0],
    )

    assert own.status_code == 201
    assert own.json()["data"]["data_request"]["subject_user_id"] == principals["student1"][1]
    assert other_student.status_code == 403
    assert student_org_request.status_code == 403
    assert listed.status_code == 200
    assert len(listed.json()["data"]["data_requests"]) == 1
    assert admin_list.status_code == 200
    assert admin_list.json()["data"]["data_requests"] == []


def test_advisor_report_viewer_inactive_and_cross_org_data_requests_are_denied(
    api_client,
    session: Session,
) -> None:
    _seed_market_context(session)
    org_a = _seed_principals(api_client, session, "data_request_org_a")
    org_b = _seed_principals(api_client, session, "data_request_org_b")
    body = {
        "request_type": "student_export",
        "subject_user_id": org_a["student1"][1],
    }

    advisor_response = api_client.post(
        _data_request_url("data_request_org_a"),
        headers=org_a["advisor"][0],
        json=body,
    )
    report_viewer_response = api_client.post(
        _data_request_url("data_request_org_a"),
        headers=org_a["report"][0],
        json=body,
    )
    inactive_response = api_client.post(
        _data_request_url("data_request_org_a"),
        headers=org_a["inactive"][0],
        json={"request_type": "organization_deletion"},
    )
    cross_org_response = api_client.post(
        _data_request_url("data_request_org_b"),
        headers=org_a["admin"][0],
        json={"request_type": "organization_export"},
    )
    own_admin_response = api_client.post(
        _data_request_url("data_request_org_b"),
        headers=org_b["admin"][0],
        json={"request_type": "organization_deletion"},
    )

    assert advisor_response.status_code == 403
    assert report_viewer_response.status_code == 403
    assert inactive_response.status_code == 403
    assert cross_org_response.status_code == 403
    assert own_admin_response.status_code == 201
