"""Company-domain enums.

These mirror the documented vocabularies in ``DATA_MODEL.md`` §4. Only the
narrow, slow-changing enums are strict types here (``EligibilityStatus``,
``ClassificationConfidence``, ``PublicOrPrivate``). Sector remains a free-form
string at the input layer because the in-scope sector list may evolve; the
default classification rule consults a documented in-scope set without forcing
admins through enum updates.
"""

from __future__ import annotations

from enum import StrEnum


class EligibilityStatus(StrEnum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    OVERRIDE_INCLUDED = "override_included"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class ClassificationConfidence(StrEnum):
    HIGH_CONFIDENCE = "high_confidence"
    MODERATE_CONFIDENCE = "moderate_confidence"
    OVERRIDE_EDGE_CASE = "override_edge_case"
    UNKNOWN = "unknown"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class PublicOrPrivate(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"
    SUBSIDIARY = "subsidiary"
    UNKNOWN = "unknown"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


# Documented in-scope sectors for the default classification rule
# (``DATA_MODEL.md`` §4 / ``MVP_SCOPE.md`` "Included sector types").
IN_SCOPE_SECTORS: frozenset[str] = frozenset(
    {
        "software",
        "internet",
        "ai",
        "cloud",
        "data",
        "hardware",
        "cybersecurity",
    }
)

# Documented exclusions ("Excluded by default" in MVP_SCOPE.md / DATA_MODEL.md).
# Kept conservative on purpose; not a comprehensive blocklist.
EXCLUDED_SECTORS: frozenset[str] = frozenset({"biotech", "martech"})
