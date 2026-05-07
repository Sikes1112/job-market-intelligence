import pytest
from pydantic import ValidationError

from backend.companies.overrides import Override


def test_override_round_trip() -> None:
    o = Override(reason="credible edge case", decided_by="admin")
    assert o.reason == "credible edge case"
    assert o.decided_by == "admin"


def test_override_decided_by_is_optional() -> None:
    o = Override(reason="ok")
    assert o.decided_by is None


@pytest.mark.parametrize("bad", ["", "   "])
def test_override_rejects_blank_reason(bad: str) -> None:
    with pytest.raises(ValidationError):
        Override(reason=bad)


def test_override_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        Override.model_validate({"reason": "x", "rogue": True})


def test_override_is_frozen() -> None:
    o = Override(reason="x")
    with pytest.raises(ValidationError):
        o.reason = "y"  # type: ignore[misc]
