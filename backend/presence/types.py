"""Company-region presence enums.

Source: ``DATA_MODEL.md`` §5 and ``STAGE_BY_STAGE_EXECUTION_PROTOCOL.md`` §8.
"""

from __future__ import annotations

from enum import StrEnum


class PresenceStatus(StrEnum):
    PRESENT = "present"
    NOT_PRESENT = "not_present"
    UNCERTAIN = "uncertain"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class PresenceBasis(StrEnum):
    OFFICE_PLUS_OPERATIONS = "office_plus_operations"
    OFFICE_PLUS_HIRING = "office_plus_hiring"
    SATELLITE_OFFICE_ONLY = "satellite_office_only"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class PresenceConfidence(StrEnum):
    """Domain-specific confidence vocabulary, mirroring the
    ``classification_confidence`` pattern from ``DATA_MODEL.md`` §4.
    """

    HIGH_CONFIDENCE = "high_confidence"
    MODERATE_CONFIDENCE = "moderate_confidence"
    LOW_CONFIDENCE = "low_confidence"
    UNKNOWN = "unknown"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)
