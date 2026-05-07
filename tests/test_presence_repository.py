from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.models import Region
from backend.presence.models import CompanyRegionPresence
from backend.presence.repository import PresenceRepository


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


def _make(presence_id: str = "p1") -> CompanyRegionPresence:
    return CompanyRegionPresence(
        presence_id=presence_id,
        company_id="comp_101",
        region_id="greater_boston",
        presence_status="present",
        presence_basis="office_plus_hiring",
        office_evidence_flag=True,
        hiring_evidence_flag=True,
    )


def test_repository_get_returns_none_for_missing(session: Session) -> None:
    repo = PresenceRepository(session)
    assert repo.get("ghost") is None
    assert repo.get_by_pair("a", "b") is None
    assert repo.exists("ghost") is False


def test_repository_round_trip(session: Session) -> None:
    _seed(session)
    repo = PresenceRepository(session)
    repo.add(_make())
    repo.flush()
    fetched = repo.get("p1")
    assert fetched is not None
    assert fetched.presence_status == "present"


def test_repository_get_by_pair(session: Session) -> None:
    _seed(session)
    repo = PresenceRepository(session)
    repo.add(_make())
    repo.flush()
    fetched = repo.get_by_pair("comp_101", "greater_boston")
    assert fetched is not None
    assert fetched.presence_id == "p1"
