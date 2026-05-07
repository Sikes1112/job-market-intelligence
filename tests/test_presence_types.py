from backend.presence.types import (
    PresenceBasis,
    PresenceConfidence,
    PresenceStatus,
)


def test_presence_status_values_match_data_model() -> None:
    assert PresenceStatus.values() == {"present", "not_present", "uncertain"}


def test_presence_basis_values_match_data_model() -> None:
    assert PresenceBasis.values() == {
        "office_plus_operations",
        "office_plus_hiring",
        "satellite_office_only",
        "insufficient_evidence",
    }


def test_presence_confidence_values() -> None:
    assert PresenceConfidence.values() == {
        "high_confidence",
        "moderate_confidence",
        "low_confidence",
        "unknown",
    }
