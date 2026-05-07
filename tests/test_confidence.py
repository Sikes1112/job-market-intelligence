import pytest

from backend.shared.confidence import (
    Confidence,
    coerce_confidence,
    validate_confidence,
)


def test_confidence_enum_has_documented_generic_values() -> None:
    assert Confidence.values() == {"high", "medium", "low", "unknown"}


def test_coerce_treats_none_as_unknown() -> None:
    assert coerce_confidence(None) is Confidence.UNKNOWN


def test_coerce_passes_through_enum_member() -> None:
    assert coerce_confidence(Confidence.HIGH) is Confidence.HIGH


def test_coerce_resolves_string() -> None:
    assert coerce_confidence("medium") is Confidence.MEDIUM


@pytest.mark.parametrize(
    "bad",
    [
        "high_confidence",  # domain-specific (companies.classification_confidence)
        "moderate_confidence",
        "override_edge_case",
        "verified",
        "",
        "HIGH",  # case-sensitive
    ],
)
def test_coerce_rejects_non_generic_or_unknown_values(bad: str) -> None:
    with pytest.raises(ValueError):
        coerce_confidence(bad)


def test_validate_confidence_is_alias_for_coerce() -> None:
    assert validate_confidence("low") is Confidence.LOW
    assert validate_confidence(None) is Confidence.UNKNOWN
