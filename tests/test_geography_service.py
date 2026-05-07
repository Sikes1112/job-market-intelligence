import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.geography.exceptions import (
    DuplicateRegion,
    InvalidRegionHierarchy,
    RegionNotFound,
)
from backend.geography.repository import RegionRepository
from backend.geography.service import GeographyService, RegionDefinition
from backend.geography.types import RegionType
from backend.shared.state import ObjectState


def _service(session: Session) -> GeographyService:
    return GeographyService(RegionRepository(session))


def _def(region_id: str = "greater_boston", **overrides) -> RegionDefinition:
    base = dict(
        region_id=region_id,
        region_name=region_id,
        display_name=region_id.replace("_", " ").title(),
        region_type=RegionType.GREATER_REGION,
    )
    base.update(overrides)
    return RegionDefinition(**base)


# --- definition validation ------------------------------------------------


def test_region_definition_rejects_blank_strings() -> None:
    with pytest.raises(ValidationError):
        RegionDefinition(
            region_id="",
            region_name="x",
            display_name="x",
            region_type=RegionType.CITY,
        )


def test_region_definition_rejects_unknown_type() -> None:
    with pytest.raises(ValidationError):
        RegionDefinition.model_validate(
            {
                "region_id": "r",
                "region_name": "r",
                "display_name": "r",
                "region_type": "neighborhood",
            }
        )


def test_region_definition_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        RegionDefinition.model_validate(
            {
                "region_id": "r",
                "region_name": "r",
                "display_name": "r",
                "region_type": "city",
                "extra": True,
            }
        )


# --- create ---------------------------------------------------------------


def test_create_region_persists_definition(session: Session) -> None:
    svc = _service(session)
    region = svc.create_region(_def("greater_boston"))
    assert region.region_id == "greater_boston"
    assert region.display_name == "Greater Boston"
    assert region.region_type == "greater_region"
    assert region.state == ObjectState.NEW.value
    assert region.version == 1


def test_create_region_rejects_duplicate(session: Session) -> None:
    svc = _service(session)
    svc.create_region(_def("greater_boston"))
    with pytest.raises(DuplicateRegion):
        svc.create_region(_def("greater_boston"))


def test_create_region_rejects_self_parent(session: Session) -> None:
    svc = _service(session)
    with pytest.raises(InvalidRegionHierarchy):
        svc.create_region(_def("greater_boston", parent_region_id="greater_boston"))


def test_create_region_rejects_missing_parent(session: Session) -> None:
    svc = _service(session)
    with pytest.raises(InvalidRegionHierarchy):
        svc.create_region(_def("greater_boston", parent_region_id="ghost"))


def test_create_region_with_valid_parent(session: Session) -> None:
    svc = _service(session)
    svc.create_region(_def("massachusetts", region_type=RegionType.STATE))
    region = svc.create_region(_def("greater_boston", parent_region_id="massachusetts"))
    assert region.parent_region_id == "massachusetts"


def test_create_region_preserves_labor_market_and_normalization(
    session: Session,
) -> None:
    svc = _service(session)
    region = svc.create_region(
        _def(
            "greater_boston",
            labor_market_group="boston_labor_market",
            normalization_profile_id="norm_v1",
        )
    )
    assert region.labor_market_group == "boston_labor_market"
    assert region.normalization_profile_id == "norm_v1"


# --- get / list -----------------------------------------------------------


def test_get_region_raises_when_missing(session: Session) -> None:
    svc = _service(session)
    with pytest.raises(RegionNotFound):
        svc.get_region("ghost")


def test_list_regions_returns_inserted(session: Session) -> None:
    svc = _service(session)
    svc.create_region(_def("greater_boston"))
    svc.create_region(_def("greater_sf"))
    rows = svc.list_regions()
    assert {r.region_id for r in rows} == {"greater_boston", "greater_sf"}


# --- update ---------------------------------------------------------------


def test_update_region_changes_fields_and_bumps_version(session: Session) -> None:
    svc = _service(session)
    svc.create_region(_def("greater_boston"))
    updated = svc.update_region(
        _def("greater_boston", display_name="Greater Boston Region")
    )
    assert updated.display_name == "Greater Boston Region"
    assert updated.version == 2


def test_update_region_raises_on_missing(session: Session) -> None:
    svc = _service(session)
    with pytest.raises(RegionNotFound):
        svc.update_region(_def("ghost"))


# --- upsert_for_build (state machine) -------------------------------------


def test_upsert_for_build_creates_and_marks_fresh(session: Session) -> None:
    svc = _service(session)
    region, action = svc.upsert_for_build(_def("greater_boston"))
    assert action == "created"
    assert region.state == ObjectState.FRESH.value
    assert region.version == 1


def test_upsert_for_build_unchanged_does_nothing(session: Session) -> None:
    svc = _service(session)
    svc.upsert_for_build(_def("greater_boston"))
    same, action = svc.upsert_for_build(_def("greater_boston"))
    assert action == "unchanged"
    assert same.version == 1
    assert same.state == ObjectState.FRESH.value


def test_upsert_for_build_changed_bumps_version_keeps_fresh(
    session: Session,
) -> None:
    """A fresh region updated in place stays fresh (no stale → rebuilding
    detour). The new content is the current build."""
    svc = _service(session)
    svc.upsert_for_build(_def("greater_boston"))
    region, action = svc.upsert_for_build(
        _def("greater_boston", display_name="Boston / Greater Region")
    )
    assert action == "updated"
    assert region.version == 2
    assert region.state == ObjectState.FRESH.value


def test_upsert_for_build_walks_never_built_region_to_fresh(
    session: Session,
) -> None:
    """If a region was created directly (state="new") and then an upsert
    arrives, the upsert should bring it to fresh."""
    svc = _service(session)
    svc.create_region(_def("greater_boston"))
    assert svc.get_region("greater_boston").state == ObjectState.NEW.value

    region, action = svc.upsert_for_build(
        _def("greater_boston", display_name="Boston / Greater")
    )
    assert action == "updated"
    assert region.state == ObjectState.FRESH.value


# --- cycle detection ------------------------------------------------------


def test_upsert_for_build_rejects_cycle(session: Session) -> None:
    svc = _service(session)
    # A->None, B->A
    svc.upsert_for_build(_def("region_a", region_type=RegionType.STATE))
    svc.upsert_for_build(
        _def("region_b", parent_region_id="region_a")
    )
    # Now try to set A.parent = B → cycle
    with pytest.raises(InvalidRegionHierarchy):
        svc.upsert_for_build(
            _def("region_a", region_type=RegionType.STATE, parent_region_id="region_b")
        )


def test_upsert_for_build_rejects_three_node_cycle(session: Session) -> None:
    svc = _service(session)
    svc.upsert_for_build(_def("a", region_type=RegionType.STATE))
    svc.upsert_for_build(_def("b", parent_region_id="a"))
    svc.upsert_for_build(_def("c", parent_region_id="b"))
    # Try to make a.parent=c → cycle a->c->b->a
    with pytest.raises(InvalidRegionHierarchy):
        svc.upsert_for_build(
            _def("a", region_type=RegionType.STATE, parent_region_id="c")
        )


def test_update_rejects_self_parent(session: Session) -> None:
    svc = _service(session)
    svc.create_region(_def("greater_boston"))
    with pytest.raises(InvalidRegionHierarchy):
        svc.update_region(_def("greater_boston", parent_region_id="greater_boston"))


def test_update_rejects_missing_parent(session: Session) -> None:
    svc = _service(session)
    svc.create_region(_def("greater_boston"))
    with pytest.raises(InvalidRegionHierarchy):
        svc.update_region(_def("greater_boston", parent_region_id="ghost"))
