from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from backend.provenance.freshness import (
    evaluate_fact_link_freshness,
    evaluate_observation_freshness,
    freshness_fact_type_for_binding,
)
from backend.shared.freshness import FreshnessStatus
from backend.shared.provenance import FactBindingType, ProvenanceFactType

_NOW = datetime(2026, 5, 20, 12, tzinfo=UTC)


def _record(days_old: int, *, fact_type: FactBindingType, fact_field: str | None = None):
    return SimpleNamespace(
        observed_at=_NOW - timedelta(days=days_old),
        fact_type=fact_type.value,
        fact_field=fact_field,
    )


def test_company_presence_uses_slow_changing_window() -> None:
    fresh = _record(100, fact_type=FactBindingType.COMPANY_REGION_PRESENCE)
    stale = _record(181, fact_type=FactBindingType.COMPANY_REGION_PRESENCE)

    assert evaluate_fact_link_freshness(fresh, now=_NOW) is FreshnessStatus.FRESH
    assert evaluate_fact_link_freshness(stale, now=_NOW) is FreshnessStatus.STALE


def test_hiring_counts_use_fast_changing_window() -> None:
    fresh = _record(10, fact_type=FactBindingType.COMPANY_REGION_HIRING)
    stale = _record(15, fact_type=FactBindingType.COMPANY_REGION_HIRING)

    assert evaluate_fact_link_freshness(fresh, now=_NOW) is FreshnessStatus.FRESH
    assert evaluate_fact_link_freshness(stale, now=_NOW) is FreshnessStatus.STALE


def test_internships_and_coops_use_seasonal_window() -> None:
    fresh = _record(
        100,
        fact_type=FactBindingType.COMPANY_REGION_ENTRY_LEVEL,
        fact_field="internship_count",
    )
    stale = _record(
        121,
        fact_type=FactBindingType.COMPANY_REGION_ENTRY_LEVEL,
        fact_field="coop_count",
    )

    assert evaluate_fact_link_freshness(fresh, now=_NOW) is FreshnessStatus.FRESH
    assert evaluate_fact_link_freshness(stale, now=_NOW) is FreshnessStatus.STALE


def test_early_career_programs_use_medium_changing_window() -> None:
    fresh = _record(
        80,
        fact_type=FactBindingType.COMPANY_REGION_ENTRY_LEVEL,
        fact_field="formal_early_career_program_flag",
    )
    stale = _record(
        91,
        fact_type=FactBindingType.COMPANY_REGION_ENTRY_LEVEL,
        fact_field="entry_level_access_score",
    )

    assert evaluate_fact_link_freshness(fresh, now=_NOW) is FreshnessStatus.FRESH
    assert evaluate_fact_link_freshness(stale, now=_NOW) is FreshnessStatus.STALE


def test_region_metadata_uses_slow_changing_window() -> None:
    fresh = _record(300, fact_type=FactBindingType.REGION)
    stale = _record(366, fact_type=FactBindingType.REGION)

    assert evaluate_fact_link_freshness(fresh, now=_NOW) is FreshnessStatus.FRESH
    assert evaluate_fact_link_freshness(stale, now=_NOW) is FreshnessStatus.STALE


def test_score_input_requires_declared_source_fact_category() -> None:
    link = _record(10, fact_type=FactBindingType.SCORE_INPUT)
    with pytest.raises(ValueError):
        evaluate_fact_link_freshness(link, now=_NOW)

    assert (
        evaluate_fact_link_freshness(
            link,
            score_source_fact_type=ProvenanceFactType.HIRING_COUNTS,
            now=_NOW,
        )
        is FreshnessStatus.FRESH
    )


def test_source_observation_freshness_uses_declared_fact_type() -> None:
    observation = SimpleNamespace(observed_at=_NOW - timedelta(days=15))
    assert (
        evaluate_observation_freshness(
            observation,
            fact_type=ProvenanceFactType.HIRING_COUNTS,
            now=_NOW,
        )
        is FreshnessStatus.STALE
    )


def test_entry_level_binding_field_maps_to_expected_fact_type() -> None:
    assert (
        freshness_fact_type_for_binding(
            FactBindingType.COMPANY_REGION_ENTRY_LEVEL,
            fact_field="internship_count",
        )
        is ProvenanceFactType.INTERNSHIPS_COOPS
    )
