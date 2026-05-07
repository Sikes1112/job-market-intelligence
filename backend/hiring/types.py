"""Hiring-domain enums.

Source: ``DATA_MODEL.md`` §6 and ``STAGE_BY_STAGE_EXECUTION_PROTOCOL.md`` §9.
"""

from __future__ import annotations

from enum import StrEnum


class AnnualizedTrendSignal(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    UNKNOWN = "unknown"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class SeasonalStudentHiringSignal(StrEnum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NONE = "none"
    UNKNOWN = "unknown"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class HiringConfidence(StrEnum):
    """Mirrors the ``classification_confidence`` / ``presence_confidence`` pattern."""

    HIGH_CONFIDENCE = "high_confidence"
    MODERATE_CONFIDENCE = "moderate_confidence"
    LOW_CONFIDENCE = "low_confidence"
    UNKNOWN = "unknown"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)
