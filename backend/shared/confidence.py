"""Generic confidence enum and validator.

This is the *generic* confidence vocabulary from ``DATA_MODEL.md`` §2:
``high | medium | low | unknown``. Domain-specific vocabularies (for example
``classification_confidence`` on ``companies``: ``high_confidence``,
``moderate_confidence``, ``override_edge_case``, ``unknown``) are intentionally
not normalized here — they remain plain strings on their respective models so
this module stays free of domain logic.
"""

from __future__ import annotations

from enum import StrEnum


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


def coerce_confidence(value: Confidence | str | None) -> Confidence:
    """Coerce ``value`` to :class:`Confidence`.

    ``None`` is treated as :attr:`Confidence.UNKNOWN`. Any other value outside
    the enum raises ``ValueError``.
    """
    if value is None:
        return Confidence.UNKNOWN
    if isinstance(value, Confidence):
        return value
    return Confidence(value)


def validate_confidence(value: Confidence | str | None) -> Confidence:
    """Alias for :func:`coerce_confidence` that signals validation intent."""
    return coerce_confidence(value)
