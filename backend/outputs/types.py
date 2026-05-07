"""Output-domain enums.

The five-value ``OutputType`` matches ``DATA_MODEL.md`` §10. Slice 11 writers
emit only ``region_output``, ``company_output``, and ``comparison_output``;
``contextual_challenge_output`` (Slice 17) and ``personalized_output``
(Slice 13) are deferred but kept in the enum so all downstream code shares
one vocabulary.
"""

from __future__ import annotations

from enum import StrEnum


class OutputType(StrEnum):
    REGION_OUTPUT = "region_output"
    COMPANY_OUTPUT = "company_output"
    COMPARISON_OUTPUT = "comparison_output"
    CONTEXTUAL_CHALLENGE_OUTPUT = "contextual_challenge_output"
    PERSONALIZED_OUTPUT = "personalized_output"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


# Output types Slice 11 is allowed to write. Tests pin this set.
SLICE_11_WRITABLE_TYPES: frozenset[str] = frozenset(
    {
        OutputType.REGION_OUTPUT.value,
        OutputType.COMPANY_OUTPUT.value,
        OutputType.COMPARISON_OUTPUT.value,
    }
)


# Build-time outcome the assembly pipeline emits per row. Distinct from the
# ObjectState transitions: ``BuildOutcome`` describes "what kind of result
# did we just compute"; the service then decides which ObjectState the
# OutputMetadata row should walk to.
class BuildOutcome(StrEnum):
    FRESH = "fresh"
    PARTIAL = "partial"
    STALE = "stale"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)
