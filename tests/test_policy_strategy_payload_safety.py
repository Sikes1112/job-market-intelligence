from __future__ import annotations

from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.institutions.models import Organization
from backend.opportunities.models import (
    Opportunity,
    OpportunityReviewActionRecord,
    OpportunitySubmission,
)
from backend.platform.public_api_payloads import find_forbidden_public_api_fields
from backend.policy.service import PolicyIntelligenceService
from tests.policy_strategy_helpers import (
    NOW,
    seed_active_institution,
    seed_company_region_signal,
    seed_private_submission,
    seed_region,
)


def _seed_strategy_payload_market(session: Session) -> None:
    seed_region(session, "strategy_api_region", display_name="Strategy API Region")
    seed_region(session, "strategy_api_peer", display_name="Strategy API Peer")
    seed_active_institution(
        session,
        organization_id="strategy_api_university",
        name="Strategy API University",
    )

    for index, postings in enumerate([65, 9, 9, 9, 9]):
        seed_company_region_signal(
            session,
            region_id="strategy_api_region",
            company_id=f"strategy_api_target_{index}",
            company_name=f"Strategy API Target {index}",
            sector="software" if index < 4 else "ai",
            active_postings=postings,
            internship_count=0,
            coop_count=0,
            entry_level_full_time_count=2 if index == 0 else 0,
            formal_program=False,
        )

    for index, sector in enumerate(["software", "ai", "cloud", "cybersecurity", "data"]):
        seed_company_region_signal(
            session,
            region_id="strategy_api_peer",
            company_id=f"strategy_api_peer_{index}",
            company_name=f"Strategy API Peer {index}",
            sector=sector,
            active_postings=10 + index,
            internship_count=2,
            coop_count=1,
            entry_level_full_time_count=1,
            formal_program=True,
        )

    seed_private_submission(
        session,
        region_id="strategy_api_region",
        employer_id="strategy_api_target_0",
    )


def test_strategy_api_payloads_include_required_public_metadata(
    api_client,
    session: Session,
) -> None:
    _seed_strategy_payload_market(session)

    for path in (
        "/policy/regions/strategy_api_region/economic-development",
        "/policy/regions/strategy_api_region/peer-comparison",
        "/policy/regions/strategy_api_region/education-alignment",
    ):
        response = api_client.get(path)

        assert response.status_code == 200
        body = response.json()
        data = body["data"]
        assert data["confidence"]
        assert data["freshness"]
        assert data["warnings"]
        assert data["source_summary"]
        assert data["limitations"]
        assert data["public_safe"] is True
        assert data["public_safety"]["student_level_data_exposed"] is False
        assert body["metadata"]["confidence"] == data["confidence"]
        assert body["metadata"]["freshness"] == data["freshness"]
        assert body["metadata"]["warnings"] == data["warnings"]
        assert body["metadata"]["source_summary"] == data["source_summary"]
        assert body["metadata"]["limitations"] == data["limitations"]
        assert body["metadata"]["public_safe"] is True
        assert find_forbidden_public_api_fields(data) == ()


def test_strategy_payloads_do_not_leak_private_layer23_or_institution_internals(
    api_client,
    session: Session,
) -> None:
    _seed_strategy_payload_market(session)

    payloads = [
        api_client.get("/policy/regions/strategy_api_region/economic-development").json(),
        api_client.get("/policy/regions/strategy_api_region/education-alignment").json(),
    ]
    serialized = str(payloads).casefold()

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
        "organization_membership_id",
        "institutional_audit_log_id",
        "payload_json",
        "minimum_group_size",
    ):
        assert token not in serialized


def test_layer24b_strategy_reads_do_not_mutate_source_records(session: Session) -> None:
    _seed_strategy_payload_market(session)
    opportunity_before = session.get(Opportunity, "opp_strategy_api_region_private")
    submission_before = session.get(OpportunitySubmission, "sub_strategy_api_region_private")
    company_before = session.get(Company, "strategy_api_target_0")
    organization_before = session.get(Organization, "strategy_api_university")
    assert opportunity_before is not None
    assert submission_before is not None
    assert company_before is not None
    assert organization_before is not None
    review_count_before = session.query(OpportunityReviewActionRecord).count()
    before_values = {
        "opportunity_updated_at": opportunity_before.updated_at,
        "opportunity_review_status": opportunity_before.review_status,
        "submission_status": submission_before.status,
        "raw_submission_json": dict(submission_before.raw_submission_json),
        "company_sector": company_before.sector_primary,
        "organization_status": organization_before.status,
    }

    service = PolicyIntelligenceService(session)
    service.build_economic_development_profile("strategy_api_region", now=NOW)
    service.build_peer_comparison_profile("strategy_api_region", now=NOW)
    service.build_education_alignment_profile("strategy_api_region", now=NOW)
    session.flush()

    opportunity_after = session.get(Opportunity, "opp_strategy_api_region_private")
    submission_after = session.get(OpportunitySubmission, "sub_strategy_api_region_private")
    company_after = session.get(Company, "strategy_api_target_0")
    organization_after = session.get(Organization, "strategy_api_university")
    assert opportunity_after is not None
    assert submission_after is not None
    assert company_after is not None
    assert organization_after is not None
    assert opportunity_after.updated_at == before_values["opportunity_updated_at"]
    assert opportunity_after.review_status == before_values["opportunity_review_status"]
    assert submission_after.status == before_values["submission_status"]
    assert submission_after.raw_submission_json == before_values["raw_submission_json"]
    assert company_after.sector_primary == before_values["company_sector"]
    assert organization_after.status == before_values["organization_status"]
    assert session.query(OpportunityReviewActionRecord).count() == review_count_before
