from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.institutions.models import (
    InstitutionalAuditLog,
    Organization,
    OrganizationMembership,
)
from backend.institutions.permissions import can_use_advisor_tools
from backend.institutions.repository import InstitutionRepository
from backend.institutions.roles import InstitutionalAuditAction, OrganizationRole
from backend.presence.models import CompanyRegionPresence
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
                region_id="greater_sf",
                region_name="Greater San Francisco",
                display_name="Greater San Francisco",
                region_type="metro",
            ),
            Company(
                company_id="comp_alpha",
                company_name="Alpha Systems",
                normalized_company_name="alpha systems",
                sector_primary="software",
                sector_secondary="ai",
            ),
            Company(
                company_id="comp_beta",
                company_name="Beta Cloud",
                normalized_company_name="beta cloud",
                sector_primary="cloud",
                sector_secondary="software",
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            CompanyRegionPresence(
                presence_id="presence_alpha_boston",
                company_id="comp_alpha",
                region_id="greater_boston",
                presence_status="present",
            ),
            CompanyRegionPresence(
                presence_id="presence_beta_sf",
                company_id="comp_beta",
                region_id="greater_sf",
                presence_status="present",
            ),
            CompanyRegionHiring(
                hiring_id="hire_alpha_boston",
                company_id="comp_alpha",
                region_id="greater_boston",
                currently_hiring_flag=True,
                active_posting_count_now=12,
                posting_count_90d=30,
                annualized_trend_signal="increasing",
                seasonal_student_hiring_signal="fall",
                hiring_confidence="medium",
                role_family_summary={"software_engineering": 5},
            ),
            CompanyRegionHiring(
                hiring_id="hire_beta_sf",
                company_id="comp_beta",
                region_id="greater_sf",
                currently_hiring_flag=False,
                active_posting_count_now=3,
                posting_count_90d=8,
                annualized_trend_signal="flat",
                seasonal_student_hiring_signal="spring",
                hiring_confidence="low",
                role_family_summary={"cloud": 2},
            ),
            CompanyRegionEntryLevel(
                entry_level_id="entry_alpha_boston",
                company_id="comp_alpha",
                region_id="greater_boston",
                internship_count=5,
                coop_count=2,
                entry_level_full_time_count=4,
                formal_early_career_program_flag=True,
                student_season_recurrence_signal="fall",
                entry_level_access_score=0.72,
            ),
            CompanyRegionEntryLevel(
                entry_level_id="entry_beta_sf",
                company_id="comp_beta",
                region_id="greater_sf",
                internship_count=1,
                coop_count=0,
                entry_level_full_time_count=1,
                formal_early_career_program_flag=False,
                student_season_recurrence_signal="unknown",
                entry_level_access_score=0.4,
            ),
        ]
    )
    session.flush()


def _seed_principals(
    api_client,
    session: Session,
    organization_id: str,
) -> dict[str, tuple[dict[str, str], str]]:
    principals = {
        name: _current_user_id(api_client, f"auth0|{organization_id}_{name}")
        for name in ("admin", "advisor", "report", "student", "inactive")
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
        user_id=principals["student"][1],
        role=OrganizationRole.STUDENT,
    )
    _seed_membership(
        session,
        organization_id=organization_id,
        user_id=principals["inactive"][1],
        role=OrganizationRole.ORG_ADMIN,
        status="inactive",
    )
    _seed_private_student_records(session, user_id=principals["student"][1])
    return principals


def _seed_private_student_records(session: Session, *, user_id: str) -> None:
    user_suffix = user_id[-12:]
    session.add(
        UserPreferenceProfile(
            user_id=user_id,
            role_interests=["secret_student_role"],
            industry_interests=["secret_industry"],
            preferred_regions=["secret_market"],
        )
    )
    session.flush()
    session.add(
        SavedMarketArtifact(
            saved_artifact_id=f"saved_secret_student_company_{user_suffix}",
            user_id=user_id,
            artifact_type="company",
            artifact_ref="secret_company",
            label="Secret Student Company",
            snapshot={"private": True},
        )
    )
    session.flush()
    session.add(
        PersonalizedRecommendationSnapshot(
            recommendation_snapshot_id=f"rec_secret_student_snapshot_{user_suffix}",
            user_id=user_id,
            preference_profile_id=user_id,
            personalized_output={"private_recommendation": "secret"},
            recommendation_version="test",
            source_version_bundle={},
            objective_output_refs=[],
            recommendation_inputs_hash=f"hash_secret_{user_suffix}",
            generated_at=datetime.now(UTC),
        )
    )
    session.flush()


def _advisor_url(organization_id: str, endpoint: str) -> str:
    return f"/api/institutions/organizations/{organization_id}/advisor/{endpoint}"


def test_org_admin_can_compare_regions_and_audit_is_recorded(
    api_client,
    session: Session,
) -> None:
    principals = _seed_principals(api_client, session, "advisor_admin_org")
    _seed_market_context(session)

    response = api_client.post(
        _advisor_url("advisor_admin_org", "compare-regions"),
        headers=principals["admin"][0],
        json={
            "regions": ["greater_boston", "greater_sf"],
            "career_stage": "entry_level",
            "industry_context": "software",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["comparison_type"] == "regions"
    assert [item["item_id"] for item in data["compared_items"]] == [
        "greater_boston",
        "greater_sf",
    ]
    assert data["tradeoffs"]
    assert data["limitations"]
    assert data["coverage_warnings"]
    payload_text = json.dumps(data)
    assert principals["student"][1] not in payload_text
    assert "secret_student_role" not in payload_text
    assert "Secret Student Company" not in payload_text
    assert "recommendation_snapshot_id" not in payload_text
    assert "saved_artifact_id" not in payload_text

    audit_rows = session.execute(
        select(InstitutionalAuditLog).where(
            InstitutionalAuditLog.organization_id == "advisor_admin_org",
            InstitutionalAuditLog.action
            == InstitutionalAuditAction.ADVISOR_COMPARE_REGIONS_USED.value,
        )
    ).scalars().all()
    assert len(audit_rows) == 1
    assert audit_rows[0].actor_user_id == principals["admin"][1]
    assert audit_rows[0].event_metadata["student_specific"] is False


def test_advisor_can_use_company_industry_stage_and_timing_tools(
    api_client,
    session: Session,
) -> None:
    principals = _seed_principals(api_client, session, "advisor_tools_org")
    _seed_market_context(session)

    company_response = api_client.post(
        _advisor_url("advisor_tools_org", "compare-companies"),
        headers=principals["advisor"][0],
        json={"companies": ["comp_alpha", "comp_beta"], "career_stage": "entry_level"},
    )
    industry_response = api_client.post(
        _advisor_url("advisor_tools_org", "compare-industries"),
        headers=principals["advisor"][0],
        json={"industries": ["software", "cloud"], "region_context": ["greater_boston"]},
    )
    stage_response = api_client.post(
        _advisor_url("advisor_tools_org", "compare-career-stages"),
        headers=principals["advisor"][0],
        json={"career_stages": ["entry_level", "internship", "career_changer"]},
    )
    timing_response = api_client.post(
        _advisor_url("advisor_tools_org", "application-timing"),
        headers=principals["advisor"][0],
        json={
            "target_regions": ["greater_boston"],
            "target_industries": ["software"],
            "career_stage": "internship",
            "application_window": "fall recruiting",
        },
    )

    assert company_response.status_code == 200
    assert industry_response.status_code == 200
    assert stage_response.status_code == 200
    assert timing_response.status_code == 200
    assert company_response.json()["data"]["comparison_type"] == "companies"
    assert industry_response.json()["data"]["comparison_type"] == "industries"
    assert stage_response.json()["data"]["comparison_type"] == "career_stages"
    assert timing_response.json()["data"]["comparison_type"] == "application_timing"
    assert timing_response.json()["data"]["guidance"]


def test_report_viewer_student_and_inactive_membership_cannot_use_advisor_tools(
    api_client,
    session: Session,
) -> None:
    principals = _seed_principals(api_client, session, "advisor_denied_org")
    _seed_market_context(session)
    body = {"regions": ["greater_boston", "greater_sf"]}

    report_response = api_client.post(
        _advisor_url("advisor_denied_org", "compare-regions"),
        headers=principals["report"][0],
        json=body,
    )
    student_response = api_client.post(
        _advisor_url("advisor_denied_org", "compare-regions"),
        headers=principals["student"][0],
        json=body,
    )
    inactive_response = api_client.post(
        _advisor_url("advisor_denied_org", "compare-regions"),
        headers=principals["inactive"][0],
        json=body,
    )

    assert report_response.status_code == 403
    assert student_response.status_code == 403
    assert inactive_response.status_code == 403

    repo = InstitutionRepository(session)
    assert can_use_advisor_tools(
        repo,
        user_id=principals["advisor"][1],
        organization_id="advisor_denied_org",
    )
    assert not can_use_advisor_tools(
        repo,
        user_id=principals["report"][1],
        organization_id="advisor_denied_org",
    )


def test_cross_org_advisor_access_is_denied(
    api_client,
    session: Session,
) -> None:
    org_a = _seed_principals(api_client, session, "advisor_org_a")
    org_b = _seed_principals(api_client, session, "advisor_org_b")
    _seed_market_context(session)

    response = api_client.post(
        _advisor_url("advisor_org_b", "compare-regions"),
        headers=org_a["advisor"][0],
        json={"regions": ["greater_boston", "greater_sf"]},
    )
    own_response = api_client.post(
        _advisor_url("advisor_org_b", "compare-regions"),
        headers=org_b["advisor"][0],
        json={"regions": ["greater_boston", "greater_sf"]},
    )

    assert response.status_code == 403
    assert own_response.status_code == 200


def test_advisor_payloads_remain_guidance_not_student_surveillance(
    api_client,
    session: Session,
) -> None:
    principals = _seed_principals(api_client, session, "advisor_privacy_org")
    _seed_market_context(session)

    response = api_client.post(
        _advisor_url("advisor_privacy_org", "compare-industries"),
        headers=principals["advisor"][0],
        json={"industries": ["software", "secret_industry"]},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    text = json.dumps(data)
    assert data["privacy_notes"]
    assert data["limitations"]
    assert principals["student"][1] not in text
    assert "secret_student_role" not in text
    assert "Secret Student Company" not in text
    assert "rec_secret_student_snapshot" not in text
    assert "saved_secret_student_company" not in text
    assert "personalized_output" not in text
    assert "raw_per_student" not in text.casefold()
    assert "per_student" not in text.casefold()
