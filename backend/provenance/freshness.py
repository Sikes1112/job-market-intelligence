"""Freshness evaluation for provenance observations and fact bindings."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from backend.shared.freshness import FreshnessStatus, evaluate_freshness
from backend.shared.provenance import (
    FRESHNESS_WINDOWS,
    FactBindingType,
    ProvenanceFactType,
)

_ENTRY_LEVEL_FIELD_FACT_TYPES: dict[str, ProvenanceFactType] = {
    "internship_count": ProvenanceFactType.INTERNSHIPS_COOPS,
    "coop_count": ProvenanceFactType.INTERNSHIPS_COOPS,
    "entry_level_full_time_count": ProvenanceFactType.EARLY_CAREER_PROGRAMS,
    "formal_early_career_program_flag": ProvenanceFactType.EARLY_CAREER_PROGRAMS,
    "student_season_recurrence_signal": ProvenanceFactType.EARLY_CAREER_PROGRAMS,
    "entry_level_access_score": ProvenanceFactType.EARLY_CAREER_PROGRAMS,
}


def freshness_fact_type_for_binding(
    fact_type: FactBindingType | str,
    *,
    fact_field: str | None = None,
    score_source_fact_type: ProvenanceFactType | str | None = None,
) -> ProvenanceFactType:
    binding_type = (
        fact_type if isinstance(fact_type, FactBindingType) else FactBindingType(fact_type)
    )

    if binding_type is FactBindingType.COMPANY:
        return ProvenanceFactType.COMPANY_UNIVERSE
    if binding_type is FactBindingType.REGION:
        return ProvenanceFactType.REGION_METADATA
    if binding_type is FactBindingType.COMPANY_REGION_PRESENCE:
        return ProvenanceFactType.COMPANY_PRESENCE
    if binding_type is FactBindingType.COMPANY_REGION_HIRING:
        return ProvenanceFactType.HIRING_COUNTS
    if binding_type is FactBindingType.COMPANY_REGION_ENTRY_LEVEL:
        if fact_field in _ENTRY_LEVEL_FIELD_FACT_TYPES:
            return _ENTRY_LEVEL_FIELD_FACT_TYPES[fact_field]
        return ProvenanceFactType.EARLY_CAREER_PROGRAMS
    if binding_type is FactBindingType.SCORE_INPUT:
        if score_source_fact_type is None:
            raise ValueError("score_input freshness requires score_source_fact_type")
        if isinstance(score_source_fact_type, ProvenanceFactType):
            return score_source_fact_type
        return ProvenanceFactType(score_source_fact_type)

    raise ValueError(f"unsupported fact binding type: {fact_type!r}")


def freshness_expires_at_for_observation(
    observed_at: datetime | None,
    *,
    fact_type: ProvenanceFactType,
) -> datetime | None:
    if observed_at is None:
        return None
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)
    return observed_at + timedelta(days=FRESHNESS_WINDOWS[fact_type].max_age_days)


def evaluate_observation_freshness(
    record: Any,
    *,
    fact_type: ProvenanceFactType,
    now: datetime | None = None,
) -> FreshnessStatus:
    expires_at = freshness_expires_at_for_observation(
        getattr(record, "observed_at", None),
        fact_type=fact_type,
    )
    return evaluate_freshness(expires_at, now=now)


def evaluate_fact_link_freshness(
    fact_link: Any,
    *,
    fact_field: str | None = None,
    score_source_fact_type: ProvenanceFactType | str | None = None,
    now: datetime | None = None,
) -> FreshnessStatus:
    fact_type = freshness_fact_type_for_binding(
        fact_link.fact_type,
        fact_field=(
            fact_field if fact_field is not None else getattr(fact_link, "fact_field", None)
        ),
        score_source_fact_type=score_source_fact_type,
    )
    return evaluate_observation_freshness(fact_link, fact_type=fact_type, now=now)
