from backend.companies.types import (
    EXCLUDED_SECTORS,
    IN_SCOPE_SECTORS,
    ClassificationConfidence,
    EligibilityStatus,
    PublicOrPrivate,
)


def test_eligibility_status_values() -> None:
    assert EligibilityStatus.values() == {"eligible", "ineligible", "override_included"}


def test_classification_confidence_values_match_data_model() -> None:
    assert ClassificationConfidence.values() == {
        "high_confidence",
        "moderate_confidence",
        "override_edge_case",
        "unknown",
    }


def test_public_or_private_values_match_data_model() -> None:
    assert PublicOrPrivate.values() == {"public", "private", "subsidiary", "unknown"}


def test_in_scope_sectors_documented() -> None:
    assert IN_SCOPE_SECTORS == {
        "software",
        "internet",
        "ai",
        "cloud",
        "data",
        "hardware",
        "cybersecurity",
    }


def test_excluded_sectors_are_disjoint_from_in_scope() -> None:
    assert IN_SCOPE_SECTORS.isdisjoint(EXCLUDED_SECTORS)
