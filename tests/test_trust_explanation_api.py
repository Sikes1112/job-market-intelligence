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

NOW = datetime(2026, 7, 4, 12, tzinfo=UTC)


def test_trust_explanation_endpoint_returns_stable_supported_payload(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_partner_opportunity(session)

    response = api_client.get(
        "/trust/explanation",
        params={
            "subject_type": "opportunity",
            "subject_id": "opp_trust_explanation",
        },
    )

    assert response.status_code == 200
    explanation = response.json()["data"]
    assert explanation["subject_type"] == "opportunity"
    assert explanation["subject_id"] == "opp_trust_explanation"
    assert explanation["trust_tier"] == "partner_submitted"
    assert explanation["trust_label"] == "Partner-submitted"
    assert explanation["risk_label"] == "Use with caution"
    assert explanation["routing_label"] == "Visible with warning"
    assert explanation["ranking_influence_allowed"] is False
    assert explanation["ranking_influence_label"] == "Excluded from rankings"
    assert "visible for awareness" in explanation["ranking_influence_reason"]
    assert explanation["explanation_version"] == "30C"
    serialized = response.text
    assert "Internal trust explanation note" not in serialized
    assert "internal_review_notes" not in serialized
    assert "reviewer_identity" not in serialized


def test_trust_explanation_endpoint_returns_safe_missing_explanation(
    api_client: TestClient,
) -> None:
    response = api_client.get(
        "/trust/explanation",
        params={"subject_type": "opportunity", "subject_id": "missing"},
    )

    assert response.status_code == 200
    explanation = response.json()["data"]
    assert explanation["trust_tier"] == "not_assessed"
    assert explanation["risk_level"] == "unknown"
    assert explanation["routing_outcome"] == "not_routed"
    assert explanation["ranking_influence_allowed"] is False
    assert explanation["user_facing_warnings"][0]["warning_code"] == "NOT_ASSESSED"


def test_opportunity_payload_embeds_public_safe_trust_explanation(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_partner_opportunity(session)

    response = api_client.get("/opportunities/opp_trust_explanation")

    assert response.status_code == 200
    payload = response.json()["data"]
    explanation = payload["trust_explanation"]
    assert explanation["trust_label"] == "Partner-submitted"
    assert explanation["ranking_influence_allowed"] is False
    assert explanation["ranking_influence_label"] == "Excluded from rankings"
    assert explanation["evidence_requirements_met"]
    assert explanation["user_facing_warnings"]
    assert "Internal trust explanation note" not in response.text


def _seed_partner_opportunity(session: Session) -> None:
    session.add_all(
        [
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
                region_type="metro",
            ),
            Company(
                company_id="comp_trust",
                company_name="Trust Example Co",
                normalized_company_name="trust example co",
                sector_primary="software",
            ),
        ]
    )
    session.flush()
    OpportunityService(OpportunityRepository(session)).create_opportunity(
        OpportunityCreate(
            opportunity_id="opp_trust_explanation",
            employer_id="comp_trust",
            employer_name="Trust Example Co",
            program_name="Trust Explanation Internship",
            program_type=OpportunityProgramType.INTERNSHIP,
            location_mode=OpportunityLocationMode.HYBRID,
            seniority_level=OpportunitySeniorityLevel.INTERNSHIP,
            eligibility_summary="Students and recent graduates.",
            application_url="https://example.com/apply/trust",
            source_url="https://example.com/source/trust",
            source_type=OpportunitySourceType.PARTNER_SUBMITTED,
            application_deadline=date(2099, 1, 1),
            trust_label=OpportunityTrustLabel.PARTNER_SUBMITTED,
            review_status=OpportunityReviewStatus.PENDING_REVIEW,
            employer_influence=EmployerInfluenceMetadataCreate(
                partner_submitted=True,
                paid_partner=False,
                internal_review_notes="Internal trust explanation note",
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
    session.flush()
