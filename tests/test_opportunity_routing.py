from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.models import Region
from backend.opportunities.repository import OpportunityRepository
from backend.opportunities.route_schemas import OpportunityRouteRequest
from backend.opportunities.routing import OpportunityRouteService
from backend.opportunities.schemas import (
    EmployerInfluenceMetadataCreate,
    OpportunityCreate,
    OpportunityLocationMode,
    OpportunityProgramType,
    OpportunityRegionBindingCreate,
    OpportunityReviewStatus,
    OpportunityRoleFamilyBindingCreate,
    OpportunitySeniorityLevel,
    OpportunitySourceCreate,
    OpportunitySourceType,
    OpportunityTrustLabel,
)
from backend.opportunities.service import OpportunityService
from backend.scoring.models import RegionMarketScore

NOW = datetime(2026, 6, 24, 12, tzinfo=UTC)


def _seed_market(session: Session) -> None:
    session.add_all(
        [
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
                region_type="metro",
            ),
            Region(
                region_id="greater_atlanta",
                region_name="greater_atlanta",
                display_name="Greater Atlanta",
                region_type="metro",
            ),
            Company(
                company_id="comp_a",
                company_name="Company A",
                normalized_company_name="company a",
                sector_primary="software",
            ),
            Company(
                company_id="comp_b",
                company_name="Company B",
                normalized_company_name="company b",
                sector_primary="data",
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            RegionMarketScore(
                region_score_id="score_boston",
                region_id="greater_boston",
                objective_opportunity_score=0.72,
                early_career_accessibility_score=0.68,
                score_ruleset_version="canonical_v1",
            ),
            RegionMarketScore(
                region_score_id="score_atlanta",
                region_id="greater_atlanta",
                objective_opportunity_score=0.58,
                early_career_accessibility_score=0.61,
                score_ruleset_version="canonical_v1",
            ),
        ]
    )
    session.flush()


def _route_request(*, include_unverified: bool = False) -> OpportunityRouteRequest:
    return OpportunityRouteRequest(
        user_intent_summary="New grad software engineer seeking practical AI platform work.",
        target_regions=("greater_boston", "greater_atlanta"),
        target_role_families=("software_engineering",),
        preferred_program_types=(
            OpportunityProgramType.INTERNSHIP,
            OpportunityProgramType.NEW_GRAD_ROLE,
        ),
        preferred_location_modes=(OpportunityLocationMode.HYBRID, OpportunityLocationMode.REMOTE),
        experience_level=OpportunitySeniorityLevel.INTERNSHIP,
        skills=("python", "platform", "data"),
        background_tags=("computer_science",),
        constraints=("needs hybrid or remote option",),
        include_unverified=include_unverified,
        limit=5,
    )


def _create(
    session: Session,
    *,
    opportunity_id: str,
    employer_id: str = "comp_a",
    employer_name: str = "Company A",
    region_id: str = "greater_boston",
    region_label: str = "Greater Boston",
    metro: str | None = "Boston-Cambridge",
    trust_label: OpportunityTrustLabel = OpportunityTrustLabel.VERIFIED,
    review_status: OpportunityReviewStatus = OpportunityReviewStatus.APPROVED,
    deadline: date = date(2099, 1, 1),
    partner_submitted: bool = False,
    paid_partner: bool = False,
) -> None:
    OpportunityService(OpportunityRepository(session)).create_opportunity(
        OpportunityCreate(
            opportunity_id=opportunity_id,
            employer_id=employer_id,
            employer_name=employer_name,
            program_name=f"Route Program {opportunity_id}",
            program_type=OpportunityProgramType.INTERNSHIP,
            location_mode=OpportunityLocationMode.HYBRID,
            seniority_level=OpportunitySeniorityLevel.INTERNSHIP,
            eligibility_summary="Python, platform, and data experience preferred.",
            application_url=f"https://example.com/apply/{opportunity_id}",
            source_url=f"https://example.com/source/{opportunity_id}",
            source_type=OpportunitySourceType.EMPLOYER_OFFICIAL,
            application_deadline=deadline,
            trust_label=trust_label,
            review_status=review_status,
            employer_influence=EmployerInfluenceMetadataCreate(
                partner_submitted=partner_submitted,
                paid_partner=paid_partner,
                paid_partner_label="paid_partner" if paid_partner else None,
                internal_review_notes="Internal routing note must not leak.",
            ),
            sources=(
                OpportunitySourceCreate(
                    source_type=OpportunitySourceType.CAREER_CENTER,
                    source_url=f"https://example.edu/source/{opportunity_id}",
                    source_name="Career Center",
                    collected_at=NOW,
                    verification_note="Public source checked.",
                ),
            ),
            region_bindings=(
                OpportunityRegionBindingCreate(
                    region_id=region_id,
                    region_label=region_label,
                    metro_area=metro,
                ),
            ),
            role_family_bindings=(
                OpportunityRoleFamilyBindingCreate(role_family="software_engineering"),
            ),
            created_at=NOW,
        )
    )


def test_route_recommendations_are_grouped_strategic_routes(
    session: Session,
) -> None:
    _seed_market(session)
    _create(session, opportunity_id="opp_verified")
    _create(
        session,
        opportunity_id="opp_source_checked",
        trust_label=OpportunityTrustLabel.SOURCE_CHECKED,
        review_status=OpportunityReviewStatus.SOURCE_CHECKED,
    )

    payload = OpportunityRouteService(OpportunityRepository(session)).generate_routes(
        _route_request(),
        now=NOW,
    )
    dumped = payload.model_dump(mode="json")

    assert dumped["route_count"] == 2
    assert "routes" in dumped
    assert "opportunities" not in dumped
    assert "jobs" not in dumped
    first_route = dumped["routes"][0]
    assert first_route["route_title"]
    assert first_route["explanation"]
    assert first_route["next_steps"]
    assert first_route["market_fit_score"] == 0.72
    assert first_route["matched_opportunities"][0]["trust_label"] in {
        "verified",
        "source_checked",
    }


def test_unverified_expired_and_rejected_trust_behavior(session: Session) -> None:
    _seed_market(session)
    _create(session, opportunity_id="opp_verified")
    _create(
        session,
        opportunity_id="opp_unverified",
        trust_label=OpportunityTrustLabel.UNVERIFIED,
        review_status=OpportunityReviewStatus.PENDING_REVIEW,
    )
    _create(
        session,
        opportunity_id="opp_expired",
        deadline=date(2000, 1, 1),
    )
    _create(
        session,
        opportunity_id="opp_rejected",
        trust_label=OpportunityTrustLabel.REJECTED,
        review_status=OpportunityReviewStatus.REJECTED,
    )

    service = OpportunityRouteService(OpportunityRepository(session))
    default_payload = service.generate_routes(_route_request(), now=NOW)
    default_ids = {
        match.opportunity_id
        for route in default_payload.routes
        for match in route.matched_opportunities
    }
    assert "opp_verified" in default_ids
    assert "opp_unverified" not in default_ids
    assert "opp_expired" not in default_ids
    assert "opp_rejected" not in default_ids

    unverified_payload = service.generate_routes(
        _route_request(include_unverified=True),
        now=NOW,
    )
    unverified_matches = [
        match
        for route in unverified_payload.routes
        for match in route.matched_opportunities
        if match.opportunity_id == "opp_unverified"
    ]
    assert unverified_matches
    assert unverified_matches[0].trust_label == OpportunityTrustLabel.UNVERIFIED
    assert any("Unverified opportunity" in warning for warning in unverified_matches[0].warnings)


def test_partner_and_paid_metadata_is_preserved_and_disclosed(
    session: Session,
) -> None:
    _seed_market(session)
    _create(
        session,
        opportunity_id="opp_paid_partner",
        partner_submitted=True,
        paid_partner=True,
    )

    payload = OpportunityRouteService(OpportunityRepository(session)).generate_routes(
        _route_request(),
        now=NOW,
    )
    [route] = [route for route in payload.routes if route.matched_opportunities]
    [match] = route.matched_opportunities

    assert match.partner_submitted is True
    assert match.paid_partner is True
    assert route.sponsored_or_partner_disclosure is not None
    assert "paid status does not affect scoring" in route.sponsored_or_partner_disclosure
    assert any("Paid partner relationship disclosed" in warning for warning in match.warnings)


def test_route_guidance_exists_without_live_opportunities(session: Session) -> None:
    _seed_market(session)

    payload = OpportunityRouteService(OpportunityRepository(session)).generate_routes(
        _route_request(),
        now=NOW,
    )

    assert payload.routes
    assert all(not route.matched_opportunities for route in payload.routes)
    assert all(route.explanation for route in payload.routes)
    assert all(route.next_steps for route in payload.routes)
    assert any(
        "No active verified" in warning
        for route in payload.routes
        for warning in route.warnings
    )


def test_route_api_returns_routes_and_does_not_leak_internal_notes(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_market(session)
    _create(
        session,
        opportunity_id="opp_api_paid_partner",
        partner_submitted=True,
        paid_partner=True,
    )

    response = api_client.post(
        "/opportunities/routes",
        json=_route_request().model_dump(mode="json"),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert "routes" in data
    assert "opportunities" not in data
    assert "Internal routing note" not in response.text
    assert data["routes"][0]["sponsored_or_partner_disclosure"] is not None
    assert "paid status does not affect scoring" in response.text
    assert "one-click" not in response.text.lower()
