"""Personalization-domain enums.

Strict, narrow vocabularies. Free-form fields like sector names and role
family keys stay as plain strings on the input model so the service can match
against the canonical truth without forcing schema updates.
"""

from __future__ import annotations

from enum import StrEnum


class CareerStage(StrEnum):
    """MVP career-stage vocabulary.

    Per ``MVP_SCOPE.md``, MVP V1 is early-career weighted; ``entry_level`` is
    the only documented in-scope value. Future slices may add ``mid`` /
    ``senior`` etc. once the role-family taxonomy expands.
    """

    ENTRY_LEVEL = "entry_level"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class PreferenceLevel(StrEnum):
    """User-expressed preference intensity for prestige and brand."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)
