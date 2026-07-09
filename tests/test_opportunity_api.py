from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.models import Region
from backend.opportunities.repository import OpportunityRepository
from backend.opportunities.schemas import (
    EmployerInfluenceMetadataCreate,
    OpportunityCreate,
    OpportunityLocationMode,
    OpportunityProgramType,
    OpportunityRegionBindingCreate,
    OpportunityReviewStatus,
    OpportunityRoleFamilyBindingCreate,
    OpportunitySeniorityLevel,
    OpportunitySourceType,
    OpportunityTrustLabel,
)
from backend.opportunities.service import OpportunityService

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


def _create(
    session: Session,
    *,
    opportunity_id: str,
    deadline: date,
    trust_label: OpportunityTrustLabel = OpportunityTrustLabel.VERIFIED,
    review_status: OpportunityReviewStatus = OpportunityReviewStatus.APPROVED,
) -> None:
    OpportunityService(OpportunityRepository(session)).create_opportunity(
        OpportunityCreate(
            opportunity_id=opportunity_id,
            employer_id="comp_a",
            employer_name="Company A",
            program_name="API Internship",
            program_type=OpportunityProgramType.INTERNSHIP,
            location_mode=OpportunityLocationMode.HYBRID,
            seniority_level=OpportunitySeniorityLevel.INTERNSHIP,
            eligibility_summary="Students and recent graduates.",
            application_url=f"https://example.com/apply/{opportunity_id}",
            source_url=f"https://example.com/careers/{opportunity_id}",
            source_type=OpportunitySourceType.EMPLOYER_OFFICIAL,
            application_deadline=deadline,
            trust_label=trust_label,
            review_status=review_status,
            employer_influence=EmployerInfluenceMetadataCreate(
                partner_submitted=True,
                paid_partner=True,
                internal_review_notes="Internal-only API test note.",
            ),
            region_bindings=(
                OpportunityRegionBindingCreate(
                    region_id="greater_boston",
                    region_label="Greater Boston",
                ),
            ),
            role_family_bindings=(
                OpportunityRoleFamilyBindingCreate(role_family="software_engineering"),
            ),
            created_at=NOW,
        )
    )


def test_opportunity_api_lists_gets_filters_and_hides_internal_fields(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_region_company(session)
    _create(session, opportunity_id="opp_api_active", deadline=date(2099, 1, 1))
    _create(session, opportunity_id="opp_api_expired", deadline=date(2000, 1, 1))
    _create(
        session,
        opportunity_id="opp_api_unverified",
        deadline=date(2099, 1, 1),
        trust_label=OpportunityTrustLabel.UNVERIFIED,
        review_status=OpportunityReviewStatus.PENDING_REVIEW,
    )

    list_response = api_client.get("/opportunities")
    assert list_response.status_code == 200
    opportunities = list_response.json()["data"]["opportunities"]
    ids = {item["id"] for item in opportunities}
    assert {"opp_api_active", "opp_api_expired", "opp_api_unverified"}.issubset(ids)
    assert "Internal-only API test note" not in list_response.text

    detail_response = api_client.get("/opportunities/opp_api_active")
    assert detail_response.status_code == 200
    detail = detail_response.json()["data"]
    assert detail["id"] == "opp_api_active"
    assert detail["trust_label"] == "verified"
    assert detail["review_status"] == "approved"
    assert detail["partner_submitted"] is True
    assert detail["paid_partner"] is True
    assert detail["ranking_influence_allowed"] is False
    assert detail["trust_tier"] == "partner_submitted"
    assert detail["risk_level"] == "medium"
    assert detail["routing_outcome"] == "visible_with_warning"
    assert detail["ranking_influence_decision"] == "denied"
    assert "partner_submitted_not_verified" in detail["ranking_influence_reason_codes"]
    assert detail["trust_explanation"]["trust_label"] == "Partner-submitted"
    assert detail["trust_explanation"]["risk_label"] == "Use with caution"
    assert detail["trust_explanation"]["routing_label"] == "Visible with warning"
    assert detail["trust_explanation"]["ranking_influence_label"] == (
        "Excluded from rankings"
    )
    assert detail["trust_explanation"]["ranking_influence_allowed"] is False
    assert detail["trust_explanation"]["explanation_version"] == "30C"
    assert detail["evidence_requirements_met"]
    assert detail["evidence_requirements_failed"]
    assert detail["expiration_state"] == "active"
    assert "internal_review_notes" not in detail_response.text

    verified_active = api_client.get(
        "/opportunities",
        params={"trust_label": "verified", "active": "true"},
    )
    assert verified_active.status_code == 200
    assert [item["id"] for item in verified_active.json()["data"]["opportunities"]] == [
        "opp_api_active"
    ]

    expired = api_client.get("/opportunities", params={"expired": "true"})
    assert expired.status_code == 200
    assert [item["id"] for item in expired.json()["data"]["opportunities"]] == [
        "opp_api_expired"
    ]

    by_bindings = api_client.get(
        "/opportunities",
        params={
            "region": "greater_boston",
            "role_family": "software_engineering",
            "program_type": "internship",
            "active": "true",
        },
    )
    assert by_bindings.status_code == 200
    assert {item["id"] for item in by_bindings.json()["data"]["opportunities"]} == {
        "opp_api_active",
        "opp_api_unverified",
    }


def test_opportunity_api_not_found_and_conflicting_filters(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_region_company(session)
    missing = api_client.get("/opportunities/missing")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"

    conflicting = api_client.get(
        "/opportunities",
        params={"active": "true", "expired": "true"},
    )
    assert conflicting.status_code == 400
    assert conflicting.json()["error"]["code"] == "VALIDATION_ERROR"
