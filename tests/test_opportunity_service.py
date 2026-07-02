from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.models import Region
from backend.opportunities.repository import OpportunityRepository
from backend.opportunities.schemas import (
    EmployerInfluenceMetadataCreate,
    OpportunityCreate,
    OpportunityExpirationState,
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
            Region(
                region_id="remote_us",
                region_name="remote_us",
                display_name="Remote US",
                region_type="custom_region",
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


def _service(session: Session) -> OpportunityService:
    return OpportunityService(OpportunityRepository(session))


def _request(**overrides) -> OpportunityCreate:
    payload = {
        "opportunity_id": "opp_service",
        "employer_id": "comp_a",
        "employer_name": "Company A",
        "program_name": "New Grad Launch",
        "program_type": OpportunityProgramType.NEW_GRAD_ROLE,
        "location_mode": OpportunityLocationMode.MIXED,
        "seniority_level": OpportunitySeniorityLevel.NEW_GRAD,
        "eligibility_summary": "Graduating seniors and recent alumni.",
        "application_url": "https://example.com/apply/new-grad",
        "source_url": "https://example.com/careers/new-grad",
        "source_type": OpportunitySourceType.EMPLOYER_OFFICIAL,
        "application_open_date": date(2026, 8, 1),
        "application_deadline": date(2026, 12, 1),
        "trust_label": OpportunityTrustLabel.SOURCE_CHECKED,
        "review_status": OpportunityReviewStatus.SOURCE_CHECKED,
        "sources": (
            OpportunitySourceCreate(
                source_type=OpportunitySourceType.CAREER_CENTER,
                source_url="https://example.edu/jobs/company-a-new-grad",
                source_name="Career center listing",
                collected_at=NOW,
            ),
        ),
        "region_bindings": (
            OpportunityRegionBindingCreate(
                region_id="greater_boston",
                region_label="Greater Boston",
            ),
            OpportunityRegionBindingCreate(
                region_id="remote_us",
                region_label="Remote US",
            ),
        ),
        "role_family_bindings": (
            OpportunityRoleFamilyBindingCreate(role_family="software_engineering"),
            OpportunityRoleFamilyBindingCreate(role_family="product_management"),
        ),
        "created_at": NOW,
    }
    payload.update(overrides)
    return OpportunityCreate(**payload)


def test_service_serializes_trust_review_sources_and_bindings(session: Session) -> None:
    _seed_region_company(session)
    payload = _service(session).create_opportunity(_request())

    dumped = payload.model_dump(mode="json")
    assert dumped["trust_label"] == "source_checked"
    assert dumped["review_status"] == "source_checked"
    assert dumped["expiration_state"] == "active"
    assert dumped["source_type"] == "employer_official"
    assert dumped["role_families"] == ["product_management", "software_engineering"]
    assert dumped["regions"] == ["greater_boston", "remote_us"]
    assert len(dumped["sources"]) == 2


def test_service_marks_deadline_and_timestamp_expiration(session: Session) -> None:
    _seed_region_company(session)
    service = _service(session)
    active = service.create_opportunity(_request(opportunity_id="opp_active"))
    past_deadline = service.create_opportunity(
        _request(
            opportunity_id="opp_deadline_expired",
            application_open_date=None,
            application_deadline=date(2026, 6, 1),
        )
    )
    timestamp_expired = service.create_opportunity(
        _request(
            opportunity_id="opp_timestamp_expired",
            expires_at=NOW - timedelta(minutes=1),
        )
    )

    assert active.expiration_state == OpportunityExpirationState.ACTIVE
    assert past_deadline.expiration_state == OpportunityExpirationState.EXPIRED
    assert timestamp_expired.expiration_state == OpportunityExpirationState.EXPIRED

    active_verified = service.list_active_verified_opportunities(now=NOW)
    assert [item.id for item in active_verified.opportunities] == ["opp_active"]
    expired = service.list_opportunities(expired=True, now=NOW)
    assert {item.id for item in expired.opportunities} == {
        "opp_deadline_expired",
        "opp_timestamp_expired",
    }


def test_service_filters_by_trust_region_role_program_and_active_state(
    session: Session,
) -> None:
    _seed_region_company(session)
    service = _service(session)
    service.create_opportunity(_request(opportunity_id="opp_matching"))
    service.create_opportunity(
        _request(
            opportunity_id="opp_other_program",
            program_type=OpportunityProgramType.INTERNSHIP,
            seniority_level=OpportunitySeniorityLevel.INTERNSHIP,
            trust_label=OpportunityTrustLabel.UNVERIFIED,
            review_status=OpportunityReviewStatus.PENDING_REVIEW,
        )
    )
    service.create_opportunity(
        _request(
            opportunity_id="opp_expired",
            application_open_date=None,
            application_deadline=date(2020, 1, 1),
        )
    )

    filtered = service.list_opportunities(
        trust_label=OpportunityTrustLabel.SOURCE_CHECKED,
        region="greater_boston",
        role_family="software_engineering",
        program_type=OpportunityProgramType.NEW_GRAD_ROLE.value,
        active=True,
        now=NOW,
    )

    assert [item.id for item in filtered.opportunities] == ["opp_matching"]


def test_partner_and_paid_metadata_is_preserved_but_cannot_rank(
    session: Session,
) -> None:
    _seed_region_company(session)
    payload = _service(session).create_opportunity(
        _request(
            employer_influence=EmployerInfluenceMetadataCreate(
                partner_submitted=True,
                paid_partner=True,
                submitted_by_partner_id="partner_1",
                paid_partner_label="sponsored_relationship",
                internal_review_notes="Visible only to internal review tools.",
            )
        )
    )

    assert payload.partner_submitted is True
    assert payload.paid_partner is True
    assert payload.ranking_influence_allowed is False
    assert payload.employer_influence is not None
    assert payload.employer_influence.submitted_by_partner_id == "partner_1"
    serialized = payload.model_dump(mode="json")
    assert "internal_review_notes" not in str(serialized)
