"""Reusable privacy metadata for institutional aggregate payloads."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

InstitutionAggregationLevel = Literal[
    "cohort",
    "public_market",
    "mixed_aggregate",
]
InstitutionPrivacyMode = Literal[
    "aggregate_only",
    "suppressed_small_cohort",
]


class InstitutionPrivacyMetadata(BaseModel):
    """Server-side privacy controls attached to institutional outputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    aggregation_level: InstitutionAggregationLevel
    privacy_mode: InstitutionPrivacyMode
    minimum_cohort_size: int = Field(ge=1)
    cohort_size: int = Field(ge=0)
    suppression_applied: bool
    suppressed_fields: list[str] = Field(default_factory=list)
    privacy_notes: list[str] = Field(default_factory=list)
    student_level_data_exposed: Literal[False] = False


def build_privacy_metadata(
    *,
    cohort_size: int,
    minimum_cohort_size: int,
    aggregation_level: InstitutionAggregationLevel = "mixed_aggregate",
    suppressed_fields: list[str] | tuple[str, ...] = (),
    extra_notes: list[str] | tuple[str, ...] = (),
) -> InstitutionPrivacyMetadata:
    """Build a consistent aggregate-only privacy envelope."""

    suppressed = cohort_size < minimum_cohort_size or bool(suppressed_fields)
    notes = [
        (
            "Institutional outputs use aggregate, anonymized cohort-level or "
            "public market-level intelligence only."
        ),
        (
            "Raw student searches, saved jobs, applications, preferences, "
            "recommendations, identities, and private activity are not exposed."
        ),
        f"Small-group detail is suppressed below the minimum cohort size of {minimum_cohort_size}.",
    ]
    notes.extend(note for note in extra_notes if note.strip())
    return InstitutionPrivacyMetadata(
        aggregation_level=aggregation_level,
        privacy_mode="suppressed_small_cohort" if suppressed else "aggregate_only",
        minimum_cohort_size=minimum_cohort_size,
        cohort_size=cohort_size,
        suppression_applied=suppressed,
        suppressed_fields=list(dict.fromkeys(suppressed_fields)),
        privacy_notes=notes,
    )
