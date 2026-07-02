from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.admin.roles import AdminRole
from backend.companies.models import Company
from backend.geography.models import Region
from backend.opportunities.models import Opportunity, OpportunitySubmission
from backend.opportunities.repository import OpportunityRepository
from backend.opportunities.schemas import (
    OpportunityLocationMode,
    OpportunityProgramType,
    OpportunityRegionBindingCreate,
    OpportunityReviewStatus,
    OpportunityRoleFamilyBindingCreate,
    OpportunitySeniorityLevel,
    OpportunitySourceType,
    OpportunitySubmissionRequest,
    OpportunityTrustLabel,
)
from backend.opportunities.submissions import OpportunitySubmissionService
from backend.users.models import User

NOW = datetime(2026, 6, 24, 12, tzinfo=UTC)


def _seed_region_company(session: Session) -> None:
    session.add_all(
        [
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
                region_type="metro",
            ),
            Company(
                company_id="comp_a",
                company_name="Company A",
                normalized_company_name="company a",
                sector_primary="software",
            ),
        ]
    )
    session.flush()


def _submission_request(**overrides) -> OpportunitySubmissionRequest:
    payload = {
        "submission_id": "sub_default",
        "opportunity_id": "opp_submission_default",
        "employer_id": "comp_a",
        "employer_name": "Company A",
        "program_name": "Employer Submitted Internship",
        "program_type": OpportunityProgramType.INTERNSHIP,
        "location_mode": OpportunityLocationMode.HYBRID,
        "seniority_level": OpportunitySeniorityLevel.INTERNSHIP,
        "eligibility_summary": "Open to students graduating in 2027 or 2028.",
        "application_url": "https://example.com/apply/internship",
        "source_url": "https://example.com/careers/internship",
        "source_type": OpportunitySourceType.PARTNER_SUBMITTED,
        "application_open_date": date(2026, 8, 1),
        "application_deadline": date(2026, 10, 1),
        "submitter_contact": "talent@example.com",
        "submitted_by": "talent_partner",
        "submission_source": "employer_portal",
        "partner_organization_id": "partner_1",
        "partner_organization_name": "Partner Org",
        "role_family_bindings": (
            OpportunityRoleFamilyBindingCreate(role_family="software_engineering"),
        ),
        "region_bindings": (
            OpportunityRegionBindingCreate(
                region_id="greater_boston",
                region_label="Greater Boston",
            ),
        ),
        "submitted_at": NOW,
    }
    payload.update(overrides)
    return OpportunitySubmissionRequest(**payload)


def _service(session: Session) -> OpportunitySubmissionService:
    return OpportunitySubmissionService(OpportunityRepository(session))


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


def _assign_role(
    api_client: TestClient,
    session: Session,
    role: AdminRole | None,
    *,
    subject: str,
) -> dict[str, str]:
    headers = _auth_headers(subject)
    response = api_client.get("/me", headers=headers)
    assert response.status_code == 200
    user_id = response.json()["data"]["user"]["user_id"]
    user = session.get(User, user_id)
    assert user is not None
    user.admin_role = role.value if role is not None else None
    session.flush()
    return headers


def test_employer_submission_defaults_to_safe_pending_partner_state(
    session: Session,
) -> None:
    _seed_region_company(session)
    payload = _service(session).submit_opportunity(_submission_request())

    assert payload.submission_id == "sub_default"
    assert payload.status == "pending_review"
    assert payload.opportunity.trust_label == OpportunityTrustLabel.PARTNER_SUBMITTED
    assert payload.opportunity.review_status == OpportunityReviewStatus.PENDING_REVIEW
    assert payload.opportunity.partner_submitted is True
    assert payload.opportunity.paid_partner is False
    assert payload.opportunity.ranking_influence_allowed is False

    row = session.get(Opportunity, "opp_submission_default")
    assert row is not None
    assert row.trust_label == "partner_submitted"
    assert row.review_status == "pending_review"
    assert session.get(OpportunitySubmission, "sub_default") is not None
    assert _service(session).list_submissions().submissions[0].submission_id == "sub_default"
    assert _service(session)._opportunity_service.list_active_verified_opportunities(
        now=NOW
    ).opportunities == ()


def test_submission_rejects_self_verification_and_ranking_influence_attempts() -> None:
    base = _submission_request().model_dump(mode="python")

    for forbidden in (
        {"trust_label": "verified"},
        {"review_status": "approved"},
        {"ranking_influence_allowed": True},
        {"source_checked": True},
        {"verified": True},
    ):
        with pytest.raises(ValidationError):
            OpportunitySubmissionRequest(**(base | forbidden))

    with pytest.raises(ValidationError):
        _submission_request(application_url="file:///private/apply")
    with pytest.raises(ValidationError):
        _submission_request(employer_name="   ")
    with pytest.raises(ValidationError):
        _submission_request(program_name="   ")
    with pytest.raises(ValidationError):
        _submission_request(application_url=None, source_url=None)
    with pytest.raises(ValidationError):
        _submission_request(paid_partner=True, paid_partner_label=None)


def test_paid_partner_submission_metadata_is_visible_but_not_verified(
    session: Session,
) -> None:
    _seed_region_company(session)
    payload = _service(session).submit_opportunity(
        _submission_request(
            opportunity_id="opp_paid_partner",
            submission_id="sub_paid_partner",
            paid_partner=True,
            paid_partner_label="paid_partner_relationship",
        )
    )

    assert payload.paid_partner is True
    assert payload.paid_partner_label == "paid_partner_relationship"
    assert payload.opportunity.paid_partner is True
    assert payload.opportunity.trust_label == "partner_submitted"
    assert payload.opportunity.review_status == "pending_review"
    assert payload.opportunity.ranking_influence_allowed is False
    assert _service(session)._opportunity_service.list_active_verified_opportunities(
        now=NOW
    ).opportunities == ()


def test_submission_api_create_validation_and_public_boundary(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_region_company(session)
    request = _submission_request(
        submission_id="sub_api",
        opportunity_id="opp_api_submission",
    ).model_dump(mode="json")
    submitter_headers = _auth_headers("auth0|opportunity_submitter")
    reviewer_headers = _assign_role(
        api_client,
        session,
        AdminRole.DATA_REVIEWER,
        subject="auth0|opportunity_submission_reviewer",
    )

    unauthenticated = api_client.post("/opportunities/submissions", json=request)
    assert unauthenticated.status_code == 401

    response = api_client.post(
        "/opportunities/submissions",
        headers=submitter_headers,
        json=request,
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["submission_id"] == "sub_api"
    assert body["status"] == "pending_review"
    assert body["opportunity"]["trust_label"] == "partner_submitted"
    assert body["opportunity"]["review_status"] == "pending_review"
    assert body["opportunity"]["partner_submitted"] is True
    assert body["opportunity"]["ranking_influence_allowed"] is False

    listed_without_role = api_client.get("/opportunities/submissions", headers=submitter_headers)
    assert listed_without_role.status_code == 403

    listed = api_client.get("/opportunities/submissions", headers=reviewer_headers)
    assert listed.status_code == 200
    assert listed.json()["data"]["submissions"][0]["submission_id"] == "sub_api"

    invalid = dict(request)
    invalid["trust_label"] = "verified"
    assert api_client.post(
        "/opportunities/submissions",
        headers=submitter_headers,
        json=invalid,
    ).status_code == 422
    invalid = dict(request)
    invalid["ranking_influence_allowed"] = True
    assert api_client.post(
        "/opportunities/submissions",
        headers=submitter_headers,
        json=invalid,
    ).status_code == 422
