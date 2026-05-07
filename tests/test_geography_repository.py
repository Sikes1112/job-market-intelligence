from sqlalchemy.orm import Session

from backend.geography.models import Region
from backend.geography.repository import RegionRepository


def _make_region(region_id: str = "r1", **overrides) -> Region:
    base = dict(
        region_id=region_id,
        region_name=region_id,
        display_name=region_id.title(),
        region_type="greater_region",
    )
    base.update(overrides)
    return Region(**base)


def test_repository_get_returns_none_for_missing(session: Session) -> None:
    repo = RegionRepository(session)
    assert repo.get("missing") is None
    assert repo.exists("missing") is False


def test_repository_add_and_get(session: Session) -> None:
    repo = RegionRepository(session)
    region = _make_region("greater_boston", display_name="Greater Boston")
    repo.add(region)
    repo.flush()

    fetched = repo.get("greater_boston")
    assert fetched is not None
    assert fetched.display_name == "Greater Boston"
    assert repo.exists("greater_boston") is True


def test_repository_list_returns_sorted(session: Session) -> None:
    repo = RegionRepository(session)
    repo.add(_make_region("r2"))
    repo.add(_make_region("r1"))
    repo.flush()
    rows = repo.list()
    assert [r.region_id for r in rows] == ["r1", "r2"]
