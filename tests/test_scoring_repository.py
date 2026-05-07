from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.presence.models import CompanyRegionPresence
from backend.scoring.repository import RegionScoreRepository


def _seed(session: Session) -> None:
    session.add_all(
        [
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
                region_type="greater_region",
            ),
            Company(
                company_id="comp_a",
                company_name="A",
                normalized_company_name="a",
                eligibility_status="eligible",
            ),
            Company(
                company_id="comp_b",
                company_name="B",
                normalized_company_name="b",
                eligibility_status="ineligible",
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            CompanyRegionPresence(
                presence_id="p_a",
                company_id="comp_a",
                region_id="greater_boston",
                presence_status="present",
                presence_basis="office_plus_hiring",
                office_evidence_flag=True,
                hiring_evidence_flag=True,
            ),
            CompanyRegionPresence(
                presence_id="p_b",
                company_id="comp_b",
                region_id="greater_boston",
                presence_status="uncertain",
                presence_basis="insufficient_evidence",
            ),
            CompanyRegionHiring(
                hiring_id="h_a",
                company_id="comp_a",
                region_id="greater_boston",
                currently_hiring_flag=True,
                active_posting_count_now=5,
            ),
            CompanyRegionEntryLevel(
                entry_level_id="e_a",
                company_id="comp_a",
                region_id="greater_boston",
                entry_level_access_score=0.7,
            ),
        ]
    )
    session.flush()


def test_list_present_companies_filters_to_present_only(session: Session) -> None:
    _seed(session)
    repo = RegionScoreRepository(session)
    companies = repo.list_present_companies_for_region("greater_boston")
    assert {c.company_id for c in companies} == {"comp_a"}  # comp_b is uncertain


def test_list_hiring_for_region(session: Session) -> None:
    _seed(session)
    repo = RegionScoreRepository(session)
    rows = repo.list_hiring_for_region("greater_boston")
    assert len(rows) == 1
    assert rows[0].company_id == "comp_a"


def test_list_entry_level_for_region(session: Session) -> None:
    _seed(session)
    repo = RegionScoreRepository(session)
    rows = repo.list_entry_level_for_region("greater_boston")
    assert len(rows) == 1
    assert rows[0].entry_level_access_score == 0.7


def test_get_score_returns_none_for_missing(session: Session) -> None:
    repo = RegionScoreRepository(session)
    assert repo.get_score("ghost") is None
    assert repo.get_score_by_region("ghost") is None
