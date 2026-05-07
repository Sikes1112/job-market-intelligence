import pytest

from backend.outputs.comparison_output import canonical_comparison_id
from backend.outputs.exceptions import InvalidComparisonInput


def test_canonical_id_is_order_independent() -> None:
    assert canonical_comparison_id("greater_boston", "greater_sf") == canonical_comparison_id(
        "greater_sf", "greater_boston"
    )


def test_canonical_id_format() -> None:
    assert (
        canonical_comparison_id("greater_boston", "greater_sf")
        == "greater_boston__greater_sf"
    )


def test_canonical_id_uses_min_first() -> None:
    # "a" < "b" lexicographically
    assert canonical_comparison_id("b", "a") == "a__b"


@pytest.mark.parametrize("a,b", [("", "x"), ("x", ""), ("   ", "x"), ("x", "   ")])
def test_canonical_id_rejects_blank(a: str, b: str) -> None:
    with pytest.raises(InvalidComparisonInput):
        canonical_comparison_id(a, b)


def test_canonical_id_rejects_identical() -> None:
    with pytest.raises(InvalidComparisonInput):
        canonical_comparison_id("greater_boston", "greater_boston")


def test_canonical_id_rejects_non_string() -> None:
    with pytest.raises(InvalidComparisonInput):
        canonical_comparison_id(123, "greater_sf")  # type: ignore[arg-type]
