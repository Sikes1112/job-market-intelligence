import pytest
from pydantic import ValidationError

from backend.orchestration.dependencies.refs import DependencyRef


def test_dependency_ref_accepts_minimal_form() -> None:
    ref = DependencyRef(ref="presence_v33")
    assert ref.ref == "presence_v33"
    assert ref.kind is None
    assert ref.required is True


def test_dependency_ref_round_trip_with_kind() -> None:
    ref = DependencyRef(ref="hiring_v71", kind="hiring_map", required=False)
    dumped = ref.model_dump()
    assert dumped == {"ref": "hiring_v71", "kind": "hiring_map", "required": False}
    again = DependencyRef.model_validate(dumped)
    assert again == ref


def test_dependency_ref_to_string_returns_ref_only() -> None:
    ref = DependencyRef(ref="company_universe_v45", kind="classified_universe")
    assert ref.to_string() == "company_universe_v45"


def test_dependency_ref_from_string_helper() -> None:
    ref = DependencyRef.from_string("entry_v29", kind="entry_level_map")
    assert ref.ref == "entry_v29"
    assert ref.kind == "entry_level_map"


@pytest.mark.parametrize("bad", ["", "   "])
def test_dependency_ref_rejects_blank(bad: str) -> None:
    with pytest.raises(ValidationError):
        DependencyRef(ref=bad)


def test_dependency_ref_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        DependencyRef.model_validate({"ref": "x", "rogue": True})


def test_dependency_ref_does_not_resolve_anything() -> None:
    """Slice 4 contract: structural only. The ref is opaque to this layer."""
    ref = DependencyRef(ref="totally_made_up_v99")
    assert ref.ref == "totally_made_up_v99"
    # No exception, no DB lookup, no version check. Resolution lives in Slices 14+.
