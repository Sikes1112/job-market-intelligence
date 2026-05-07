import pytest
from pydantic import ValidationError

from backend.presence.evidence import (
    PresenceDecision,
    PresenceEvidence,
    evaluate_presence,
)
from backend.presence.types import (
    PresenceBasis,
    PresenceConfidence,
    PresenceStatus,
)


def _ev(
    *,
    office: bool = False,
    operations: bool = False,
    hiring: bool = False,
    source_refs=None,
) -> PresenceEvidence:
    return PresenceEvidence(
        office_evidence_flag=office,
        operations_evidence_flag=operations,
        hiring_evidence_flag=hiring,
        source_refs=source_refs,
    )


# --- input validation -----------------------------------------------------


def test_evidence_rejects_missing_required_flags() -> None:
    with pytest.raises(ValidationError):
        PresenceEvidence(office_evidence_flag=True)  # type: ignore[call-arg]


def test_evidence_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        PresenceEvidence.model_validate(
            {
                "office_evidence_flag": True,
                "operations_evidence_flag": False,
                "hiring_evidence_flag": False,
                "rogue": True,
            }
        )


def test_evidence_source_refs_round_trip_unmodified() -> None:
    refs = [{"kind": "office_data", "ref": "office_data_v2"}]
    ev = _ev(office=True, source_refs=refs)
    assert ev.source_refs == refs


def test_evidence_is_frozen() -> None:
    ev = _ev(office=True)
    with pytest.raises(ValidationError):
        ev.office_evidence_flag = False  # type: ignore[misc]


# --- rule outcomes --------------------------------------------------------


def test_office_plus_operations_is_present_high() -> None:
    d = evaluate_presence(_ev(office=True, operations=True))
    assert d.status is PresenceStatus.PRESENT
    assert d.basis is PresenceBasis.OFFICE_PLUS_OPERATIONS
    assert d.confidence is PresenceConfidence.HIGH_CONFIDENCE


def test_office_plus_hiring_is_present_high() -> None:
    d = evaluate_presence(_ev(office=True, hiring=True))
    assert d.status is PresenceStatus.PRESENT
    assert d.basis is PresenceBasis.OFFICE_PLUS_HIRING
    assert d.confidence is PresenceConfidence.HIGH_CONFIDENCE


def test_office_plus_both_prefers_hiring_by_default() -> None:
    d = evaluate_presence(_ev(office=True, operations=True, hiring=True))
    assert d.status is PresenceStatus.PRESENT
    assert d.basis is PresenceBasis.OFFICE_PLUS_HIRING


def test_office_plus_both_when_hiring_not_preferred_uses_operations() -> None:
    d = evaluate_presence(
        _ev(office=True, operations=True, hiring=True),
        prefer_hiring_evidence=False,
    )
    assert d.basis is PresenceBasis.OFFICE_PLUS_OPERATIONS


def test_satellite_office_only_when_allowed_is_present_moderate() -> None:
    d = evaluate_presence(_ev(office=True))
    assert d.status is PresenceStatus.PRESENT
    assert d.basis is PresenceBasis.SATELLITE_OFFICE_ONLY
    assert d.confidence is PresenceConfidence.MODERATE_CONFIDENCE


def test_satellite_office_only_when_disallowed_is_uncertain() -> None:
    d = evaluate_presence(_ev(office=True), allow_satellite_office_presence=False)
    assert d.status is PresenceStatus.UNCERTAIN
    assert d.basis is PresenceBasis.SATELLITE_OFFICE_ONLY
    assert d.confidence is PresenceConfidence.LOW_CONFIDENCE


@pytest.mark.parametrize(
    "operations,hiring",
    [
        (True, False),
        (False, True),
        (True, True),
    ],
)
def test_no_office_with_partial_evidence_is_uncertain(
    operations: bool, hiring: bool
) -> None:
    d = evaluate_presence(_ev(operations=operations, hiring=hiring))
    assert d.status is PresenceStatus.UNCERTAIN
    assert d.basis is PresenceBasis.INSUFFICIENT_EVIDENCE
    assert d.confidence is PresenceConfidence.LOW_CONFIDENCE


def test_no_evidence_is_not_present_with_unknown_confidence() -> None:
    d = evaluate_presence(_ev())
    assert d.status is PresenceStatus.NOT_PRESENT
    assert d.basis is PresenceBasis.INSUFFICIENT_EVIDENCE
    assert d.confidence is PresenceConfidence.UNKNOWN


def test_evaluate_presence_is_deterministic() -> None:
    e = _ev(office=True, hiring=True)
    a = evaluate_presence(e)
    b = evaluate_presence(e)
    assert a == b
    assert isinstance(a, PresenceDecision)
