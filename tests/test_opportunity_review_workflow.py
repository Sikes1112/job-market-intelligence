from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.admin.roles import AdminRole
from backend.companies.models import Company
from backend.geography.models import Region
from backend.opportunities.models import Opportunity, OpportunityReviewActionRecord
from backend.opportunities.repository import OpportunityRepository
from backend.opportunities.schemas import (
    OpportunityLocationMode,
    OpportunityProgramType,
    OpportunityRegionBindingCreate,
    OpportunityReviewAction,
    OpportunityReviewRequest,
    OpportunityRoleFamilyBindingCreate,
    OpportunitySeniorityLevel,
    OpportunitySubmissionRequest,
)
from backend.opportunities.service import OpportunityService
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


def _submission_request(
    *,
    submission_id: str,
    opportunity_id: str,
    deadline: date = date(2099, 1, 1),
) -> OpportunitySubmissionRequest:
    return OpportunitySubmissionRequest(
        submission_id=submission_id,
        opportunity_id=opportunity_id,
        employer_id="comp_a",
        employer_name="Company A",
        program_name=f"Program {submission_id}",
        program_type=OpportunityProgramType.INTERNSHIP,
        location_mode=OpportunityLocationMode.HYBRID,
        seniority_level=OpportunitySeniorityLevel.INTERNSHIP,
        eligibility_summary="Open to early-career candidates.",
        application_url=f"https://example.com/apply/{submission_id}",
        source_url=f"https://example.com/careers/{submission_id}",
        application_deadline=deadline,
        submitter_contact="talent@example.com",
        role_family_bindings=(
            OpportunityRoleFamilyBindingCreate(role_family="software_engineering"),
        ),
        region_bindings=(
            OpportunityRegionBindingCreate(
                region_id="greater_boston",
                region_label="Greater Boston",
            ),
        ),
        submitted_at=NOW,
    )


def _review_request(action: OpportunityReviewAction, **overrides) -> OpportunityReviewRequest:
    payload = {
        "review_action": action,
        "reviewer_id": "reviewer_1",
        "reviewer_name": "Internal Reviewer",
        "review_note": "Internal review note must not leak.",
        "reviewed_at": NOW,
    }
    if action is OpportunityReviewAction.APPROVE_AS_VERIFIED:
        payload["official_employer_url"] = "https://example.com/careers"
    if action is OpportunityReviewAction.APPROVE_AS_SOURCE_CHECKED:
        payload["source_url_checked"] = "https://example.com/careers/source"
    if action is OpportunityReviewAction.REQUEST_CORRECTION:
        payload["correction_reason"] = "Need clearer eligibility language."
    payload.update(overrides)
    return OpportunityReviewRequest(**payload)


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


def test_review_actions_change_effective_trust_without_mutating_snapshot(
    session: Session,
) -> None:
    _seed_region_company(session)
    service = _service(session)
    submission = service.submit_opportunity(
        _submission_request(
            submission_id="sub_verified",
            opportunity_id="opp_verified",
        )
    )

    reviewed = service.review_submission(
        submission.submission_id,
        _review_request(OpportunityReviewAction.APPROVE_AS_VERIFIED),
    )

    assert reviewed.status == "reviewed"
    assert reviewed.latest_review is not None
    assert reviewed.latest_review.review_action == "approve_as_verified"
    assert reviewed.opportunity.trust_label == "verified"
    assert reviewed.opportunity.review_status == "approved"
    assert reviewed.opportunity.ranking_influence_allowed is False

    immutable_snapshot = session.get(Opportunity, "opp_verified")
    assert immutable_snapshot is not None
    assert immutable_snapshot.trust_label == "partner_submitted"
    assert immutable_snapshot.review_status == "pending_review"
    review_row = session.execute(select(OpportunityReviewActionRecord)).scalar_one()
    assert review_row.ranking_influence_allowed is False
    assert review_row.review_note == "Internal review note must not leak."
    assert "reviewer_1" not in reviewed.model_dump_json()
    assert "Internal review note" not in reviewed.opportunity.model_dump_json()


@pytest.mark.parametrize(
    ("action", "expected_trust", "expected_review", "expected_status"),
    [
        (
            OpportunityReviewAction.APPROVE_AS_SOURCE_CHECKED,
            "source_checked",
            "source_checked",
            "reviewed",
        ),
        (
            OpportunityReviewAction.MARK_UNVERIFIED,
            "unverified",
            "pending_review",
            "reviewed",
        ),
        (OpportunityReviewAction.MARK_EXPIRED, "expired", "expired", "expired"),
        (OpportunityReviewAction.REJECT, "rejected", "rejected", "rejected"),
        (
            OpportunityReviewAction.REQUEST_CORRECTION,
            "unverified",
            "needs_correction",
            "needs_correction",
        ),
    ],
)
def test_review_workflow_supports_required_actions(
    session: Session,
    action: OpportunityReviewAction,
    expected_trust: str,
    expected_review: str,
    expected_status: str,
) -> None:
    _seed_region_company(session)
    service = _service(session)
    submission = service.submit_opportunity(
        _submission_request(
            submission_id=f"sub_{action.value}",
            opportunity_id=f"opp_{action.value}",
        )
    )

    reviewed = service.review_submission(
        submission.submission_id,
        _review_request(action),
    )

    assert reviewed.status == expected_status
    assert reviewed.opportunity.trust_label == expected_trust
    assert reviewed.opportunity.review_status == expected_review
    assert reviewed.opportunity.ranking_influence_allowed is False
    [review_row] = session.execute(select(OpportunityReviewActionRecord)).scalars().all()
    assert review_row.ranking_influence_allowed is False


def test_only_reviewed_verified_or_source_checked_submissions_are_active_verified(
    session: Session,
) -> None:
    _seed_region_company(session)
    service = _service(session)
    verified = service.submit_opportunity(
        _submission_request(submission_id="sub_verified", opportunity_id="opp_verified")
    )
    source_checked = service.submit_opportunity(
        _submission_request(
            submission_id="sub_source_checked",
            opportunity_id="opp_source_checked",
        )
    )
    rejected = service.submit_opportunity(
        _submission_request(submission_id="sub_rejected", opportunity_id="opp_rejected")
    )
    expired = service.submit_opportunity(
        _submission_request(submission_id="sub_expired", opportunity_id="opp_expired")
    )

    service.review_submission(
        verified.submission_id,
        _review_request(OpportunityReviewAction.APPROVE_AS_VERIFIED),
    )
    service.review_submission(
        source_checked.submission_id,
        _review_request(OpportunityReviewAction.APPROVE_AS_SOURCE_CHECKED),
    )
    service.review_submission(
        rejected.submission_id,
        _review_request(OpportunityReviewAction.REJECT),
    )
    service.review_submission(
        expired.submission_id,
        _review_request(OpportunityReviewAction.MARK_EXPIRED),
    )

    active_verified = OpportunityService(
        OpportunityRepository(session)
    ).list_active_verified_opportunities(now=NOW)
    assert {item.id for item in active_verified.opportunities} == {
        "opp_verified",
        "opp_source_checked",
    }


def test_review_api_surfaces_effective_state_and_keeps_public_payload_clean(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_region_company(session)
    submitter_headers = _auth_headers("auth0|opp_review_submitter")
    ordinary_headers = _assign_role(
        api_client,
        session,
        None,
        subject="auth0|opp_review_ordinary",
    )
    reviewer_headers = _assign_role(
        api_client,
        session,
        AdminRole.DATA_REVIEWER,
        subject="auth0|opp_review_reviewer",
    )
    request = _submission_request(
        submission_id="sub_api_review",
        opportunity_id="opp_api_review",
    ).model_dump(mode="json")
    create_response = api_client.post(
        "/opportunities/submissions",
        headers=submitter_headers,
        json=request,
    )
    assert create_response.status_code == 200

    unauthenticated_review = api_client.post(
        "/opportunities/submissions/sub_api_review/review",
        json=_review_request(
            OpportunityReviewAction.APPROVE_AS_SOURCE_CHECKED
        ).model_dump(mode="json"),
    )
    assert unauthenticated_review.status_code == 401

    ordinary_review = api_client.post(
        "/opportunities/submissions/sub_api_review/review",
        headers=ordinary_headers,
        json=_review_request(
            OpportunityReviewAction.APPROVE_AS_SOURCE_CHECKED
        ).model_dump(mode="json"),
    )
    assert ordinary_review.status_code == 403

    review_response = api_client.post(
        "/opportunities/submissions/sub_api_review/review",
        headers=reviewer_headers,
        json=_review_request(
            OpportunityReviewAction.APPROVE_AS_SOURCE_CHECKED
        ).model_dump(mode="json"),
    )
    assert review_response.status_code == 200
    reviewed = review_response.json()["data"]
    assert reviewed["opportunity"]["trust_label"] == "source_checked"
    assert reviewed["opportunity"]["review_status"] == "source_checked"
    assert reviewed["opportunity"]["ranking_influence_allowed"] is False
    assert "reviewer_1" not in review_response.text
    assert "Internal review note" not in review_response.text

    public_detail = api_client.get("/opportunities/opp_api_review")
    assert public_detail.status_code == 200
    assert public_detail.json()["data"]["trust_label"] == "source_checked"
    assert "reviewer_1" not in public_detail.text
    assert "Internal review note" not in public_detail.text


def test_review_api_supports_required_actions_and_submission_filters(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_region_company(session)
    submitter_headers = _auth_headers("auth0|opp_review_scenarios_submitter")
    reviewer_headers = _assign_role(
        api_client,
        session,
        AdminRole.DATA_REVIEWER,
        subject="auth0|opp_review_scenarios_reviewer",
    )
    scenarios = {
        "verified": (
            OpportunityReviewAction.APPROVE_AS_VERIFIED,
            "verified",
            "approved",
            "reviewed",
        ),
        "rejected": (
            OpportunityReviewAction.REJECT,
            "rejected",
            "rejected",
            "rejected",
        ),
        "expired": (
            OpportunityReviewAction.MARK_EXPIRED,
            "expired",
            "expired",
            "expired",
        ),
        "correction": (
            OpportunityReviewAction.REQUEST_CORRECTION,
            "unverified",
            "needs_correction",
            "needs_correction",
        ),
    }
    for key, (action, trust_label, review_status, submission_status) in scenarios.items():
        create_response = api_client.post(
            "/opportunities/submissions",
            headers=submitter_headers,
            json=_submission_request(
                submission_id=f"sub_api_{key}",
                opportunity_id=f"opp_api_{key}",
            ).model_dump(mode="json"),
        )
        assert create_response.status_code == 200

        review_response = api_client.post(
            f"/opportunities/submissions/sub_api_{key}/review",
            headers=reviewer_headers,
            json=_review_request(action).model_dump(mode="json"),
        )
        assert review_response.status_code == 200
        reviewed = review_response.json()["data"]
        assert reviewed["status"] == submission_status
        assert reviewed["opportunity"]["trust_label"] == trust_label
        assert reviewed["opportunity"]["review_status"] == review_status
        assert reviewed["opportunity"]["ranking_influence_allowed"] is False

    reviewed_list = api_client.get(
        "/opportunities/submissions",
        headers=reviewer_headers,
        params={"status": "reviewed"},
    )
    assert reviewed_list.status_code == 200
    assert {row["submission_id"] for row in reviewed_list.json()["data"]["submissions"]} == {
        "sub_api_verified",
    }
