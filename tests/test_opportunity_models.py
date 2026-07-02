from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.models import Region
from backend.opportunities.models import (
    EmployerInfluenceMetadata,
    EmployerProgram,
    Opportunity,
    OpportunityRegionBinding,
    OpportunityRoleFamilyBinding,
    OpportunitySource,
)
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
    session.add(
        Region(
            region_id="greater_boston",
            region_name="greater_boston",
            display_name="Greater Boston",
            region_type="metro",
        )
    )
    session.add(
        Company(
            company_id="comp_a",
            company_name="Company A",
            normalized_company_name="company a",
            sector_primary="software",
        )
    )
    session.flush()


def _request(**overrides) -> OpportunityCreate:
    payload = {
        "opportunity_id": "opp_model",
        "employer_id": "comp_a",
        "employer_name": "Company A",
        "program_name": "Early Talent Internship",
        "program_type": OpportunityProgramType.INTERNSHIP,
        "location_mode": OpportunityLocationMode.HYBRID,
        "seniority_level": OpportunitySeniorityLevel.INTERNSHIP,
        "eligibility_summary": "Students graduating in 2027 or 2028.",
        "application_url": "https://example.com/apply/internship",
        "source_url": "https://example.com/careers/internship",
        "source_type": OpportunitySourceType.EMPLOYER_OFFICIAL,
        "application_open_date": date(2026, 8, 1),
        "application_deadline": date(2026, 10, 1),
        "compensation_min": 30.0,
        "compensation_max": 40.0,
        "compensation_disclosed": True,
        "trust_label": OpportunityTrustLabel.VERIFIED,
        "review_status": OpportunityReviewStatus.APPROVED,
        "region_bindings": (
            OpportunityRegionBindingCreate(
                region_id="greater_boston",
                region_label="Greater Boston",
                metro_area="Boston-Cambridge-Newton",
            ),
        ),
        "role_family_bindings": (
            OpportunityRoleFamilyBindingCreate(
                role_family="software_engineering",
                role_family_label="Software Engineering",
            ),
        ),
        "employer_influence": EmployerInfluenceMetadataCreate(
            partner_submitted=True,
            paid_partner=True,
            paid_partner_label="paid_partner",
            internal_review_notes="Internal reviewer note.",
        ),
        "created_at": NOW,
    }
    payload.update(overrides)
    return OpportunityCreate(**payload)


def test_opportunity_vocabularies_include_layer_23a_required_values() -> None:
    assert OpportunityTrustLabel.values() == {
        "verified",
        "source_checked",
        "partner_submitted",
        "unverified",
        "expired",
        "rejected",
    }
    assert OpportunityReviewStatus.values() == {
        "pending_review",
        "approved",
        "source_checked",
        "rejected",
        "expired",
        "needs_correction",
    }
    assert {"onsite", "hybrid", "remote", "mixed", "unknown"}.issubset(
        OpportunityLocationMode.values()
    )
    assert {"internship", "co-op", "apprentice", "new-grad", "early-career"}.issubset(
        OpportunitySeniorityLevel.values()
    )


def test_opportunity_contract_validation_rejects_unsafe_or_corrupting_inputs() -> None:
    with pytest.raises(ValidationError):
        _request(application_url="file:///private/apply")
    with pytest.raises(ValidationError):
        _request(source_url="https://example.com/careers?token=secret")
    with pytest.raises(ValidationError):
        _request(compensation_disclosed=False, compensation_min=20.0)
    with pytest.raises(ValidationError):
        _request(
            employer_influence=EmployerInfluenceMetadataCreate(
                ranking_influence_allowed=True
            )
        )


def test_opportunities_can_be_stored_with_sources_bindings_and_metadata(
    session: Session,
) -> None:
    _seed_region_company(session)
    payload = OpportunityService(OpportunityRepository(session)).create_opportunity(
        _request()
    )

    assert payload.id == "opp_model"
    assert payload.trust_label == OpportunityTrustLabel.VERIFIED
    assert payload.review_status == OpportunityReviewStatus.APPROVED
    assert payload.role_families == ("software_engineering",)
    assert payload.regions == ("greater_boston",)
    assert payload.partner_submitted is True
    assert payload.paid_partner is True
    assert payload.ranking_influence_allowed is False

    assert session.get(Opportunity, "opp_model") is not None
    assert session.execute(select(EmployerProgram)).scalars().all()
    assert session.execute(select(OpportunitySource)).scalars().all()
    assert session.execute(select(OpportunityRegionBinding)).scalars().all()
    assert session.execute(select(OpportunityRoleFamilyBinding)).scalars().all()
    assert session.execute(select(EmployerInfluenceMetadata)).scalars().all()


def test_opportunity_rows_are_additive_only(session: Session) -> None:
    _seed_region_company(session)
    OpportunityService(OpportunityRepository(session)).create_opportunity(_request())
    row = session.get(Opportunity, "opp_model")
    assert row is not None

    with pytest.raises(ValueError, match="additive-only"):
        row.trust_label = OpportunityTrustLabel.REJECTED.value
        session.flush()
    session.rollback()
