"""Verify that the @validates hook on CanonicalMixin enforces ObjectState.

Slice 3 wires :class:`backend.shared.state.ObjectState` into every model that
uses :class:`backend.shared.db.CanonicalMixin`. Job intentionally does not use
the mixin (its lifecycle is the orchestration ``status`` enum, owned by Slice 4).
"""

import pytest
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.outputs.models import OutputMetadata
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore
from backend.shared.state import ObjectState


def _make_region(state: ObjectState | str | None = None) -> Region:
    kwargs = dict(
        region_id="r1",
        region_name="r1",
        display_name="R1",
        region_type="greater_region",
    )
    if state is not None:
        kwargs["state"] = state
    return Region(**kwargs)


def test_default_state_is_new(session: Session) -> None:
    region = _make_region()
    session.add(region)
    session.flush()
    assert region.state == ObjectState.NEW.value


def test_assigning_enum_member_stores_string_value(session: Session) -> None:
    region = _make_region(state=ObjectState.BUILDING)
    session.add(region)
    session.flush()
    assert region.state == "building"


def test_assigning_valid_state_string_succeeds(session: Session) -> None:
    region = _make_region(state="rebuilding")
    session.add(region)
    session.flush()
    assert region.state == "rebuilding"


@pytest.mark.parametrize(
    "bad",
    [
        "verified",  # deferred per Slice 3 scope
        "low_confidence",
        "deprecated",
        "ready",
        "",
        "FRESH",  # case-sensitive
    ],
)
def test_invalid_state_strings_are_rejected_at_assignment(bad: str) -> None:
    with pytest.raises(ValueError):
        _make_region(state=bad)


def test_state_cannot_be_set_to_none() -> None:
    with pytest.raises(ValueError):
        Region(
            region_id="r1",
            region_name="r1",
            display_name="R1",
            region_type="greater_region",
            state=None,
        )


def test_state_validation_applies_across_canonical_models(session: Session) -> None:
    """Every model inheriting CanonicalMixin should reject invalid state."""
    samples: list[object] = [
        Company(
            company_id="c1",
            company_name="X",
            normalized_company_name="x",
        ),
        CompanyRegionPresence(
            presence_id="p1",
            company_id="c1",
            region_id="r1",
            presence_status="present",
        ),
        CompanyRegionHiring(
            hiring_id="h1",
            company_id="c1",
            region_id="r1",
        ),
        CompanyRegionEntryLevel(
            entry_level_id="e1",
            company_id="c1",
            region_id="r1",
        ),
        RegionMarketScore(
            region_score_id="rms1",
            region_id="r1",
        ),
        OutputMetadata(
            output_id="o1",
            output_type="region_output",
            subject_id="r1",
        ),
    ]
    for obj in samples:
        with pytest.raises(ValueError):
            obj.state = "verified"
