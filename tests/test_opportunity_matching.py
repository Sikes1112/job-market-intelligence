from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.models import Region
from backend.opportunities.matching import (
    is_route_eligible_opportunity,
    match_opportunity_to_route,
)
from backend.opportunities.repository import OpportunityRepository
from backend.opportunities.route_schemas import OpportunityRouteRequest
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


def _seed(session: Session) -> None:
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


def _route_request(*, include_unverified: bool = False) -> OpportunityRouteRequest:
    return OpportunityRouteRequest(
        user_intent_summary="Early-career software engineer seeking internship routes.",
        target_regions=("greater_boston",),
        target_role_families=("software_engineering",),
        preferred_program_types=(OpportunityProgramType.INTERNSHIP,),
        preferred_location_modes=(OpportunityLocationMode.HYBRID,),
        experience_level=OpportunitySeniorityLevel.INTERNSHIP,
        skills=("python", "cloud"),
        include_unverified=include_unverified,
    )


def _create_opportunity(
    session: Session,
    *,
    opportunity_id: str,
    trust_label: OpportunityTrustLabel = OpportunityTrustLabel.VERIFIED,
    review_status: OpportunityReviewStatus = OpportunityReviewStatus.APPROVED,
    paid_partner: bool = False,
    partner_submitted: bool = False,
) -> None:
    OpportunityService(OpportunityRepository(session)).create_opportunity(
        OpportunityCreate(
            opportunity_id=opportunity_id,
            employer_id="comp_a",
            employer_name="Company A",
            program_name=f"Software Internship {opportunity_id}",
            program_type=OpportunityProgramType.INTERNSHIP,
            location_mode=OpportunityLocationMode.HYBRID,
            seniority_level=OpportunitySeniorityLevel.INTERNSHIP,
            eligibility_summary="Python and cloud background preferred.",
            application_url=f"https://example.com/apply/{opportunity_id}",
            source_url=f"https://example.com/source/{opportunity_id}",
            source_type=OpportunitySourceType.EMPLOYER_OFFICIAL,
            application_deadline=date(2099, 1, 1),
            trust_label=trust_label,
            review_status=review_status,
            employer_influence=EmployerInfluenceMetadataCreate(
                partner_submitted=partner_submitted,
                paid_partner=paid_partner,
                paid_partner_label="paid_partner" if paid_partner else None,
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


def test_matcher_excludes_unverified_by_default(session: Session) -> None:
    _seed(session)
    _create_opportunity(
        session,
        opportunity_id="opp_unverified",
        trust_label=OpportunityTrustLabel.UNVERIFIED,
        review_status=OpportunityReviewStatus.PENDING_REVIEW,
    )

    opportunity = OpportunityService(OpportunityRepository(session)).get_opportunity(
        "opp_unverified",
        now=NOW,
    )

    assert not is_route_eligible_opportunity(
        opportunity,
        include_unverified=False,
    )
    assert match_opportunity_to_route(
        opportunity,
        _route_request(),
        target_region="greater_boston",
        target_role_family="software_engineering",
    ) is None


def test_include_unverified_allows_labeled_unverified_match(session: Session) -> None:
    _seed(session)
    _create_opportunity(
        session,
        opportunity_id="opp_unverified",
        trust_label=OpportunityTrustLabel.UNVERIFIED,
        review_status=OpportunityReviewStatus.PENDING_REVIEW,
    )

    opportunity = OpportunityService(OpportunityRepository(session)).get_opportunity(
        "opp_unverified",
        now=NOW,
    )
    match = match_opportunity_to_route(
        opportunity,
        _route_request(include_unverified=True),
        target_region="greater_boston",
        target_role_family="software_engineering",
    )

    assert match is not None
    assert match.fit_score > 0
    assert any("Unverified opportunity" in warning for warning in match.warnings)


def test_paid_partner_status_does_not_boost_opportunity_fit_score(
    session: Session,
) -> None:
    _seed(session)
    _create_opportunity(
        session,
        opportunity_id="opp_unpaid_partner",
        partner_submitted=True,
        paid_partner=False,
    )
    _create_opportunity(
        session,
        opportunity_id="opp_paid_partner",
        partner_submitted=True,
        paid_partner=True,
    )
    service = OpportunityService(OpportunityRepository(session))
    request = _route_request()

    unpaid = match_opportunity_to_route(
        service.get_opportunity("opp_unpaid_partner", now=NOW),
        request,
        target_region="greater_boston",
        target_role_family="software_engineering",
    )
    paid = match_opportunity_to_route(
        service.get_opportunity("opp_paid_partner", now=NOW),
        request,
        target_region="greater_boston",
        target_role_family="software_engineering",
    )

    assert unpaid is not None
    assert paid is not None
    assert paid.fit_score == unpaid.fit_score
    assert any("Paid partner relationship disclosed" in warning for warning in paid.warnings)
