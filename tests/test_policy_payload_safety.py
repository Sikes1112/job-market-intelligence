from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.opportunities.models import (
    Opportunity,
    OpportunityReviewActionRecord,
    OpportunitySubmission,
)
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
from backend.opportunities.submissions import OpportunitySubmissionService
from backend.platform.public_api_payloads import find_forbidden_public_api_fields
from backend.policy.service import PolicyIntelligenceService
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore

NOW = datetime(2026, 6, 27, 12, tzinfo=UTC)
FRESH_UNTIL = datetime(2099, 1, 1, 12, tzinfo=UTC)


def _seed_market(session: Session) -> None:
    session.add(
        Region(
            region_id="safety_region",
            region_name="safety_region",
            display_name="Safety Region",
            region_type="greater_region",
        )
    )
    session.add(
        RegionMarketScore(
            region_score_id="score_safety_region",
            region_id="safety_region",
            objective_opportunity_score=0.65,
            early_career_accessibility_score=0.58,
            score_ruleset_version="marketscore_v1",
        )
    )
    for index in range(5):
        company_id = f"safe_comp_{index}"
        session.add(
            Company(
                company_id=company_id,
                company_name=f"Safe Company {index}",
                normalized_company_name=f"safe company {index}",
                sector_primary="software" if index < 3 else "ai",
                eligibility_status="eligible",
            )
        )
        session.flush()
        session.add(
            CompanyRegionPresence(
                presence_id=f"presence_safe_{index}",
                company_id=company_id,
                region_id="safety_region",
                presence_status="present",
                presence_basis="office_plus_hiring",
                office_evidence_flag=True,
                hiring_evidence_flag=True,
                presence_confidence="high",
                source_refs=[{"fact_source_link_id": f"presence_safe_src_{index}"}],
            )
        )
        session.add(
            CompanyRegionHiring(
                hiring_id=f"hiring_safe_{index}",
                company_id=company_id,
                region_id="safety_region",
                currently_hiring_flag=True,
                active_posting_count_now=10,
                hiring_confidence="high",
                freshness_expires_at=FRESH_UNTIL,
                source_refs=[{"fact_source_link_id": f"hiring_safe_src_{index}"}],
            )
        )
        session.add(
            CompanyRegionEntryLevel(
                entry_level_id=f"entry_safe_{index}",
                company_id=company_id,
                region_id="safety_region",
                internship_count=1,
                coop_count=0,
                entry_level_full_time_count=1,
                formal_early_career_program_flag=True,
                entry_level_access_score=0.55,
                entry_level_confidence="high",
                freshness_expires_at=FRESH_UNTIL,
                source_refs=[{"fact_source_link_id": f"entry_safe_src_{index}"}],
            )
        )
    session.flush()


def _submission_request() -> OpportunitySubmissionRequest:
    return OpportunitySubmissionRequest(
        submission_id="sub_policy_private",
        opportunity_id="opp_policy_private",
        employer_id="safe_comp_0",
        employer_name="Safe Company 0",
        program_name="Private Review Program",
        program_type=OpportunityProgramType.INTERNSHIP,
        location_mode=OpportunityLocationMode.HYBRID,
        seniority_level=OpportunitySeniorityLevel.INTERNSHIP,
        eligibility_summary="Open to students and recent graduates.",
        application_url="https://example.com/apply/private-review",
        source_url="https://example.com/careers/private-review",
        application_deadline=date(2099, 1, 1),
        submitter_contact="private_submitter@example.com",
        submitted_by="Private Submitter",
        submission_source="private_partner_portal",
        partner_organization_id="private_partner",
        partner_organization_name="Private Partner Org",
        paid_partner=True,
        paid_partner_label="paid_partner_relationship",
        role_family_bindings=(
            OpportunityRoleFamilyBindingCreate(role_family="software_engineering"),
        ),
        region_bindings=(
            OpportunityRegionBindingCreate(
                region_id="safety_region",
                region_label="Safety Region",
            ),
        ),
        submitted_at=NOW,
    )


def _seed_private_submission(session: Session) -> None:
    service = OpportunitySubmissionService(OpportunityRepository(session))
    payload = service.submit_opportunity(_submission_request())
    service.review_submission(
        payload.submission_id,
        OpportunityReviewRequest(
            review_action=OpportunityReviewAction.APPROVE_AS_VERIFIED,
            reviewer_id="private_reviewer_id",
            reviewer_name="Private Reviewer",
            review_note="Internal private review note.",
            official_employer_url="https://example.com/careers",
            reviewed_at=NOW,
        ),
    )
    session.flush()


def test_policy_payload_does_not_leak_private_layer23_fields(
    api_client,
    session: Session,
) -> None:
    _seed_market(session)
    _seed_private_submission(session)

    response = api_client.get("/policy/regions/safety_region/workforce-dashboard")

    assert response.status_code == 200
    serialized = str(response.json()).casefold()
    for token in (
        "private_reviewer_id",
        "private reviewer",
        "internal private review note",
        "private_submitter@example.com",
        "private submitter",
        "raw_submission_json",
        "submitter_contact",
        "reviewer_id",
        "review_note",
    ):
        assert token not in serialized


def test_policy_public_payload_does_not_expose_internal_only_field_names(
    session: Session,
) -> None:
    _seed_market(session)

    payload = PolicyIntelligenceService(session).build_workforce_dashboard(
        "safety_region",
        now=NOW,
    )
    dumped = payload.model_dump(mode="python")

    assert find_forbidden_public_api_fields(dumped) == ()
    assert payload.public_safe is True
    assert payload.public_safety.student_level_data_exposed is False
    assert payload.public_safety.partner_submission_internals_exposed is False
    assert payload.public_safety.private_review_fields_exposed is False


def test_layer24a_does_not_mutate_opportunities_or_submissions(
    session: Session,
) -> None:
    _seed_market(session)
    _seed_private_submission(session)
    opportunity_before = session.get(Opportunity, "opp_policy_private")
    submission_before = session.get(OpportunitySubmission, "sub_policy_private")
    review_count_before = session.query(OpportunityReviewActionRecord).count()
    assert opportunity_before is not None
    assert submission_before is not None
    before_values = {
        "opportunity_updated_at": opportunity_before.updated_at,
        "opportunity_review_status": opportunity_before.review_status,
        "submission_status": submission_before.status,
        "raw_submission_json": dict(submission_before.raw_submission_json),
    }

    PolicyIntelligenceService(session).build_regional_policy_profile(
        "safety_region",
        now=NOW,
    )
    session.flush()

    opportunity_after = session.get(Opportunity, "opp_policy_private")
    submission_after = session.get(OpportunitySubmission, "sub_policy_private")
    assert opportunity_after is not None
    assert submission_after is not None
    assert opportunity_after.updated_at == before_values["opportunity_updated_at"]
    assert opportunity_after.review_status == before_values["opportunity_review_status"]
    assert submission_after.status == before_values["submission_status"]
    assert submission_after.raw_submission_json == before_values["raw_submission_json"]
    assert session.query(OpportunityReviewActionRecord).count() == review_count_before
