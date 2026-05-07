from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.geography.models import Region


def _make_region(**overrides) -> Region:
    defaults = dict(
        region_id="greater_boston",
        region_name="greater_boston",
        display_name="Greater Boston",
        region_type="greater_region",
    )
    defaults.update(overrides)
    return Region(**defaults)


def test_region_created_with_required_fields(session: Session) -> None:
    region = _make_region()
    session.add(region)
    session.flush()

    fetched = session.get(Region, "greater_boston")
    assert fetched is not None
    assert fetched.display_name == "Greater Boston"


def test_region_canonical_metadata_defaults_set(session: Session) -> None:
    region = _make_region()
    session.add(region)
    session.flush()

    assert region.state == "new"
    assert region.version == 1
    assert isinstance(region.created_at, datetime)
    assert region.created_at.tzinfo is not None
    assert region.created_at <= datetime.now(UTC)


def test_region_parent_relationship_resolves(session: Session) -> None:
    parent = _make_region(
        region_id="massachusetts",
        region_name="massachusetts",
        display_name="Massachusetts",
        region_type="state",
    )
    child = _make_region(parent_region_id="massachusetts")
    session.add_all([parent, child])
    session.flush()

    fetched = session.get(Region, "greater_boston")
    assert fetched is not None
    assert fetched.parent_region is not None
    assert fetched.parent_region.region_id == "massachusetts"
    assert fetched.parent_region.child_regions[0].region_id == "greater_boston"


def test_region_missing_required_field_raises(session: Session) -> None:
    region = Region(
        region_id="seattle",
        region_name="seattle",
        # display_name omitted
        region_type="greater_region",
    )
    session.add(region)
    with pytest.raises(IntegrityError):
        session.flush()


def test_region_id_is_primary_key(session: Session) -> None:
    session.add(_make_region())
    session.flush()
    duplicate = _make_region()
    session.add(duplicate)
    with pytest.raises(IntegrityError):
        session.flush()


def test_regions_query_returns_inserted_rows(session: Session) -> None:
    session.add_all(
        [
            _make_region(region_id="r1", region_name="r1", display_name="R1"),
            _make_region(region_id="r2", region_name="r2", display_name="R2"),
        ]
    )
    session.flush()
    rows = session.execute(select(Region).order_by(Region.region_id)).scalars().all()
    assert [r.region_id for r in rows] == ["r1", "r2"]
