from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.entry_level.repository import EntryLevelRepository
from backend.geography.models import Region


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
                company_id="comp_101",
                company_name="Example",
                normalized_company_name="example",
            ),
        ]
    )
    session.flush()


def test_repository_get_returns_none_for_missing(session: Session) -> None:
    repo = EntryLevelRepository(session)
    assert repo.get("ghost") is None
    assert repo.get_by_pair("a", "b") is None


def test_repository_round_trip(session: Session) -> None:
    _seed(session)
    repo = EntryLevelRepository(session)
    repo.add(
        CompanyRegionEntryLevel(
            entry_level_id="e1",
            company_id="comp_101",
            region_id="greater_boston",
        )
    )
    repo.flush()
    fetched = repo.get_by_pair("comp_101", "greater_boston")
    assert fetched is not None
    assert fetched.entry_level_id == "e1"
