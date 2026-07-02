from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.models import Region
from backend.integrations.types import (
    ApiAccessPolicy,
    ApiScope,
    CareerPlatform,
    CareerPlatformExport,
    CareerPlatformRiskPosture,
    ExternalCareerLink,
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


def _seed_company(session: Session) -> None:
    session.add(
        Region(
            region_id="greater_boston",
            region_name="greater_boston",
            display_name="Greater Boston",
            region_type="greater_region",
        )
    )
    session.add(
        Company(
            company_id="comp_alpha",
            company_name="Alpha Systems",
            normalized_company_name="alpha systems",
            sector_primary="software",
            eligibility_status="eligible",
            classification_confidence="high",
            prestige_score=0.71,
        )
    )
    session.flush()


def test_linkedin_and_handshake_registry_are_manual_export_or_deep_link_only(
    api_client,
    session: Session,
) -> None:
    _seed_company(session)
    headers, _ = _current_user_id(api_client, "auth0|platform_registry")

    response = api_client.get("/api/integrations/career-platforms", headers=headers)

    assert response.status_code == 200
    platforms = {
        item["platform"]: item for item in response.json()["data"]["platforms"]
    }
    linkedin = platforms["linkedin"]
    handshake = platforms["handshake"]
    assert linkedin["risk_posture"] == "deep_link_only"
    assert linkedin["manual_only"] is True
    assert linkedin["automation_performed"] is False
    assert "scraping" in linkedin["blocked_capabilities"]
    assert "application_submission" in linkedin["blocked_capabilities"]
    assert handshake["risk_posture"] == "export_only"
    assert "automation" in handshake["blocked_capabilities"]
    assert "login_crawling" in handshake["blocked_capabilities"]

    links = api_client.get(
        "/api/integrations/career-platforms/companies/comp_alpha/links",
        headers=headers,
    )
    assert links.status_code == 200
    payload = links.json()["data"]
    assert payload["company_name"] == "Alpha Systems"
    assert all(link["manual_only"] is True for link in payload["links"])
    assert all(link["automation_performed"] is False for link in payload["links"])
    assert "automated_application_submission" in payload["blocked_workflows"]
    assert "ats_pipeline" in payload["blocked_workflows"]


def test_career_platform_export_does_not_create_ats_application_state(
    api_client,
    session: Session,
) -> None:
    _seed_company(session)
    headers, _ = _current_user_id(api_client, "auth0|platform_export")

    response = api_client.post(
        "/api/integrations/career-platform-exports",
        headers=headers,
        json={
            "platform": "linkedin",
            "company_ids": ["comp_alpha"],
            "employer_names": ["Beta Labs"],
        },
    )

    assert response.status_code == 201
    export = response.json()["data"]["export"]
    assert export["platform"] == "linkedin"
    assert export["risk_posture"] == "deep_link_only"
    assert export["manual_only"] is True
    assert export["automation_performed"] is False
    assert export["ats_state_created"] is False
    assert export["application_status_created"] is False
    assert export["recruiter_outreach_created"] is False
    assert len(export["rows"]) == 2
    assert export["rows"][0]["manual_action"] == "manual_company_search"
    serialized = json.dumps(export)
    assert "resume_submission_created" in serialized
    assert "applied" not in serialized
    assert "interviewing" not in serialized
    assert "offer" not in serialized
    assert "rejected" not in serialized


def test_public_career_page_reference_is_manual_and_user_owned(
    api_client,
    session: Session,
) -> None:
    _seed_company(session)
    headers, user_id = _current_user_id(api_client, "auth0|platform_reference")

    response = api_client.post(
        "/api/integrations/career-platform-references",
        headers=headers,
        json={
            "platform": "company_career_page",
            "subject_type": "company",
            "subject_id": "comp_alpha",
            "url": "https://example.com/careers",
            "label": "Alpha Systems public careers page",
        },
    )

    assert response.status_code == 201
    reference = response.json()["data"]["reference"]
    assert reference["risk_posture"] == "safe_manual"
    assert reference["manual_only"] is True
    assert reference["submitted_by_user_id"] == user_id

    listed = api_client.get(
        "/api/integrations/career-platform-references?subject_type=company&subject_id=comp_alpha",
        headers=headers,
    )
    assert listed.status_code == 200
    assert listed.json()["data"]["references"][0]["url"] == "https://example.com/careers"


def test_career_platform_reference_rejects_non_public_url(
    api_client,
    session: Session,
) -> None:
    _seed_company(session)
    headers, _ = _current_user_id(api_client, "auth0|platform_bad_reference")

    response = api_client.post(
        "/api/integrations/career-platform-references",
        headers=headers,
        json={
            "platform": "company_career_page",
            "subject_type": "company",
            "subject_id": "comp_alpha",
            "url": "javascript:alert(1)",
        },
    )

    assert response.status_code == 422


def test_career_platform_domain_models_reject_automation_and_forbidden_scopes() -> None:
    with pytest.raises(ValidationError):
        ExternalCareerLink(
            url="https://www.linkedin.com",
            label="Automated LinkedIn action",
            platform=CareerPlatform.LINKEDIN,
            risk_posture=CareerPlatformRiskPosture.DEEP_LINK_ONLY,
            automation_performed=True,
        )

    with pytest.raises(ValidationError):
        CareerPlatformExport(
            career_platform_export_id="cpe_bad",
            platform=CareerPlatform.HANDSHAKE,
            risk_posture=CareerPlatformRiskPosture.EXPORT_ONLY,
            export_mode="automated_lookup",
            rows=[],
            automation_performed=True,
            created_at=datetime.now(UTC),
        )

    allowed_scopes = {scope.value for scope in ApiScope}
    forbidden_fragments = {
        "job_application",
        "applicant",
        "candidate",
        "student_profile",
        "resume",
        "recruiter",
        "ats",
        "pipeline",
        "crm",
    }
    assert not any(
        fragment in scope for fragment in forbidden_fragments for scope in allowed_scopes
    )
    policy = ApiAccessPolicy(scopes=list(ApiScope))
    assert {scope.value for scope in policy.scopes} == allowed_scopes
