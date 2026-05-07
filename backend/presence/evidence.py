"""Presence evidence input shape and the rule that turns evidence into a decision.

The rule is a pure function over structured evidence flags. It does not fetch,
scrape, or query anything — that's deferred (Slice 14+ and external ingestion
work).

Source rules:

* ``DATA_MODEL.md`` §5: a company is regionally present iff
  *(real office + real operations)* **or** *(real office + actual hiring tied
  to that region)*. Hiring evidence is preferred when available. A real
  satellite office may still suffice when hiring evidence is unavailable.
* ``JOB_CONTRACT_SPEC.md`` Job 4 ``options``:
  ``prefer_hiring_evidence``, ``allow_satellite_office_presence``.

The rule honors "never silently treat unknown as a confident value": when
evidence is partial or absent, the decision returns honest uncertainty rather
than fabricated presence.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from backend.presence.types import (
    PresenceBasis,
    PresenceConfidence,
    PresenceStatus,
)


class PresenceEvidence(BaseModel):
    """Structured evidence flags + opaque ``source_refs``.

    The boolean flags are explicit yes/no inputs. ``source_refs`` is opaque
    JSON-shaped data that round-trips through the model without
    interpretation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    office_evidence_flag: bool
    operations_evidence_flag: bool
    hiring_evidence_flag: bool
    source_refs: list[dict] | dict | None = None


@dataclass(frozen=True, slots=True)
class PresenceDecision:
    status: PresenceStatus
    basis: PresenceBasis
    confidence: PresenceConfidence


def evaluate_presence(
    evidence: PresenceEvidence,
    *,
    prefer_hiring_evidence: bool = True,
    allow_satellite_office_presence: bool = True,
) -> PresenceDecision:
    office = evidence.office_evidence_flag
    operations = evidence.operations_evidence_flag
    hiring = evidence.hiring_evidence_flag

    # Strongest signal: office + both ops AND hiring. Basis chooses between
    # the two qualifying paths according to ``prefer_hiring_evidence``.
    if office and operations and hiring:
        basis = (
            PresenceBasis.OFFICE_PLUS_HIRING
            if prefer_hiring_evidence
            else PresenceBasis.OFFICE_PLUS_OPERATIONS
        )
        return PresenceDecision(
            status=PresenceStatus.PRESENT,
            basis=basis,
            confidence=PresenceConfidence.HIGH_CONFIDENCE,
        )

    if office and hiring:
        return PresenceDecision(
            status=PresenceStatus.PRESENT,
            basis=PresenceBasis.OFFICE_PLUS_HIRING,
            confidence=PresenceConfidence.HIGH_CONFIDENCE,
        )

    if office and operations:
        return PresenceDecision(
            status=PresenceStatus.PRESENT,
            basis=PresenceBasis.OFFICE_PLUS_OPERATIONS,
            confidence=PresenceConfidence.HIGH_CONFIDENCE,
        )

    if office and not operations and not hiring:
        # Satellite-only: documented as acceptable when hiring evidence is
        # unavailable and the option is enabled.
        if allow_satellite_office_presence:
            return PresenceDecision(
                status=PresenceStatus.PRESENT,
                basis=PresenceBasis.SATELLITE_OFFICE_ONLY,
                confidence=PresenceConfidence.MODERATE_CONFIDENCE,
            )
        return PresenceDecision(
            status=PresenceStatus.UNCERTAIN,
            basis=PresenceBasis.SATELLITE_OFFICE_ONLY,
            confidence=PresenceConfidence.LOW_CONFIDENCE,
        )

    if operations or hiring:
        # No office but we have *something*: not enough to qualify per the
        # documented rule, but not nothing.
        return PresenceDecision(
            status=PresenceStatus.UNCERTAIN,
            basis=PresenceBasis.INSUFFICIENT_EVIDENCE,
            confidence=PresenceConfidence.LOW_CONFIDENCE,
        )

    # Zero positive evidence.
    return PresenceDecision(
        status=PresenceStatus.NOT_PRESENT,
        basis=PresenceBasis.INSUFFICIENT_EVIDENCE,
        confidence=PresenceConfidence.UNKNOWN,
    )
