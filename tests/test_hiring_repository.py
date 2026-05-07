from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.hiring.repository import HiringRepository


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
    repo = HiringRepository(session)
    assert repo.get("ghost") is None
    assert repo.get_by_pair("a", "b") is None


def test_repository_round_trip(session: Session) -> None:
    _seed(session)
    repo = HiringRepository(session)
    repo.add(
        CompanyRegionHiring(
            hiring_id="h1",
            company_id="comp_101",
            region_id="greater_boston",
        )
    )
    repo.flush()
    fetched = repo.get_by_pair("comp_101", "greater_boston")
    assert fetched is not None
    assert fetched.hiring_id == "h1"
