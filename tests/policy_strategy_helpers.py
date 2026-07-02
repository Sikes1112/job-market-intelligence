from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.institutions.models import Organization
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
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore

NOW = datetime(2026, 6, 27, 12, tzinfo=UTC)
FRESH_UNTIL = datetime(2099, 1, 1, 12, tzinfo=UTC)


def seed_region(
    session: Session,
    region_id: str,
    *,
    display_name: str | None = None,
    score: bool = True,
    opportunity_score: float = 0.68,
    live_market_score: float = 0.70,
    early_career_score: float = 0.58,
) -> None:
    if session.get(Region, region_id) is None:
        session.add(
            Region(
                region_id=region_id,
                region_name=region_id,
                display_name=display_name or region_id.replace("_", " ").title(),
                region_type="greater_region",
            )
        )
    if score and session.get(RegionMarketScore, f"score_{region_id}") is None:
        session.add(
            RegionMarketScore(
                region_score_id=f"score_{region_id}",
                region_id=region_id,
                objective_opportunity_score=opportunity_score,
                live_market_score=live_market_score,
                early_career_accessibility_score=early_career_score,
                score_ruleset_version="marketscore_v1",
            )
        )
    session.flush()


def seed_company(
    session: Session,
    company_id: str,
    *,
    company_name: str | None = None,
    sector: str = "software",
    is_major_tech: bool = False,
) -> None:
    if session.get(Company, company_id) is not None:
        return
    name = company_name or company_id.replace("_", " ").title()
    session.add(
        Company(
            company_id=company_id,
            company_name=name,
            normalized_company_name=name.casefold(),
            sector_primary=sector,
            eligibility_status="eligible",
            classification_confidence="high",
            is_major_tech=is_major_tech,
        )
    )
    session.flush()


def seed_company_region_signal(
    session: Session,
    *,
    region_id: str,
    company_id: str,
    sector: str = "software",
    company_name: str | None = None,
    active_postings: int = 10,
    internship_count: int | None = 1,
    coop_count: int | None = 0,
    entry_level_full_time_count: int | None = 1,
    formal_program: bool = True,
    present: bool = True,
    is_major_tech: bool = False,
) -> None:
    seed_company(
        session,
        company_id,
        company_name=company_name,
        sector=sector,
        is_major_tech=is_major_tech,
    )
    suffix = f"{region_id}_{company_id}"
    session.add(
        CompanyRegionPresence(
            presence_id=f"presence_{suffix}",
            company_id=company_id,
            region_id=region_id,
            presence_status="present" if present else "not_present",
            presence_basis="office_plus_hiring" if present else "not_observed",
            office_evidence_flag=present,
            hiring_evidence_flag=active_postings > 0,
            presence_confidence="high",
            source_refs=[{"fact_source_link_id": f"presence_src_{suffix}"}],
        )
    )
    session.add(
        CompanyRegionHiring(
            hiring_id=f"hiring_{suffix}",
            company_id=company_id,
            region_id=region_id,
            currently_hiring_flag=active_postings > 0,
            active_posting_count_now=active_postings,
            posting_count_30d=active_postings * 2,
            posting_count_90d=active_postings * 3,
            hiring_confidence="high",
            freshness_expires_at=FRESH_UNTIL,
            source_refs=[{"fact_source_link_id": f"hiring_src_{suffix}"}],
        )
    )
    access_score = _entry_access_score(
        internship_count=internship_count,
        coop_count=coop_count,
        entry_level_full_time_count=entry_level_full_time_count,
        formal_program=formal_program,
    )
    session.add(
        CompanyRegionEntryLevel(
            entry_level_id=f"entry_{suffix}",
            company_id=company_id,
            region_id=region_id,
            internship_count=internship_count,
            coop_count=coop_count,
            entry_level_full_time_count=entry_level_full_time_count,
            formal_early_career_program_flag=formal_program,
            entry_level_access_score=access_score,
            entry_level_confidence="high",
            freshness_expires_at=FRESH_UNTIL,
            source_refs=[{"fact_source_link_id": f"entry_src_{suffix}"}],
        )
    )
    session.flush()


def seed_active_institution(
    session: Session,
    *,
    organization_id: str = "policy_state_university",
    name: str = "Policy State University",
    organization_type: str = "school",
) -> None:
    session.add(
        Organization(
            organization_id=organization_id,
            name=name,
            organization_type=organization_type,
            status="active",
        )
    )
    session.flush()


def seed_private_submission(
    session: Session,
    *,
    region_id: str,
    employer_id: str,
) -> None:
    employer = session.get(Company, employer_id)
    employer_name = employer.company_name if employer is not None else "Private Employer"
    service = OpportunitySubmissionService(OpportunityRepository(session))
    payload = service.submit_opportunity(
        OpportunitySubmissionRequest(
            submission_id=f"sub_{region_id}_private",
            opportunity_id=f"opp_{region_id}_private",
            employer_id=employer_id,
            employer_name=employer_name,
            program_name="Private Partner Internship",
            program_type=OpportunityProgramType.INTERNSHIP,
            location_mode=OpportunityLocationMode.HYBRID,
            seniority_level=OpportunitySeniorityLevel.INTERNSHIP,
            eligibility_summary="Open to students and recent graduates.",
            application_url="https://example.com/apply/private-partner",
            source_url="https://example.com/careers/private-partner",
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
                    region_id=region_id,
                    region_label=region_id.replace("_", " ").title(),
                ),
            ),
            submitted_at=NOW,
        )
    )
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


def _entry_access_score(
    *,
    internship_count: int | None,
    coop_count: int | None,
    entry_level_full_time_count: int | None,
    formal_program: bool,
) -> float:
    if any(
        value is not None and value > 0
        for value in (internship_count, coop_count, entry_level_full_time_count)
    ) or formal_program:
        return 0.70
    return 0.0
