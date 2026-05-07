from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.companies.repository import CompanyRepository


def _make(company_id: str = "comp_1", **overrides) -> Company:
    base = dict(
        company_id=company_id,
        company_name="X",
        normalized_company_name=company_id,
    )
    base.update(overrides)
    return Company(**base)


def test_repository_get_returns_none_for_missing(session: Session) -> None:
    repo = CompanyRepository(session)
    assert repo.get("ghost") is None
    assert repo.exists("ghost") is False


def test_repository_add_and_get(session: Session) -> None:
    repo = CompanyRepository(session)
    repo.add(_make("comp_101", company_name="Example AI"))
    repo.flush()
    fetched = repo.get("comp_101")
    assert fetched is not None
    assert fetched.company_name == "Example AI"


def test_repository_list_returns_sorted(session: Session) -> None:
    repo = CompanyRepository(session)
    repo.add(_make("comp_b"))
    repo.add(_make("comp_a"))
    repo.flush()
    rows = repo.list()
    assert [c.company_id for c in rows] == ["comp_a", "comp_b"]
