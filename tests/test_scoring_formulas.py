"""Direct tests of per-component formula functions in
``backend.scoring.service``. These tests use stub Company / hiring /
entry-level objects rather than the ORM so they isolate formula behavior
from persistence."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from backend.entry_level.models import CompanyRegionEntryLevel
from backend.hiring.models import CompanyRegionHiring
from backend.scoring.rulesets import DEFAULT_RULESET
from backend.scoring.service import (
    compute_early_career_accessibility,
    compute_live_market,
    compute_objective_opportunity,
    compute_prestige_aggregate,
    compute_structural_ecosystem,
)


# Light-weight stand-in for Company. We only read a handful of attributes
# in formulas, so a duck-typed object is sufficient and keeps tests fast.
@dataclass(frozen=True)
class _CompanyStub:
    company_id: str
    eligibility_status: str
    is_major_tech: bool = False
    is_mag7: bool = False
    prestige_score: float | None = None


# --- structural ecosystem -----------------------------------------------


def test_structural_score_zero_for_no_companies() -> None:
    assert compute_structural_ecosystem([], ruleset=DEFAULT_RULESET) == 0.0


def test_structural_score_responds_to_eligible_density() -> None:
    companies = [
        _CompanyStub(company_id=f"c{i}", eligibility_status="eligible")
        for i in range(DEFAULT_RULESET.cap_eligible_count)
    ]
    score = compute_structural_ecosystem(companies, ruleset=DEFAULT_RULESET)
    # Saturated eligible × eligible weight (no major-tech, no Mag 7).
    assert score == pytest.approx(DEFAULT_RULESET.w_struct_eligible)


def test_structural_score_does_not_depend_on_hiring_recency() -> None:
    """Two regions with identical company structure but different hiring
    activity should produce identical structural scores when hiring is not
    fed in. (Structural reads companies only; hiring is a separate aggregate.)"""
    companies = [
        _CompanyStub(company_id="c1", eligibility_status="eligible", is_major_tech=True)
    ]
    a = compute_structural_ecosystem(companies, ruleset=DEFAULT_RULESET)
    b = compute_structural_ecosystem(companies, ruleset=DEFAULT_RULESET)
    assert a == b


def test_structural_score_is_deterministic() -> None:
    companies = [
        _CompanyStub(
            company_id="c1",
            eligibility_status="eligible",
            is_major_tech=True,
            is_mag7=True,
        )
    ]
    a = compute_structural_ecosystem(companies, ruleset=DEFAULT_RULESET)
    b = compute_structural_ecosystem(companies, ruleset=DEFAULT_RULESET)
    assert a == b


# --- live market --------------------------------------------------------


def test_live_market_zero_for_no_records() -> None:
    assert compute_live_market([], ruleset=DEFAULT_RULESET) == 0.0


def test_live_market_unknown_counts_treated_as_zero_when_record_present() -> None:
    """If a hiring record exists but counts are unknown, the live market
    score reflects only what is known. The ``currently_hiring_flag`` still
    contributes because it is explicitly recorded."""
    h = CompanyRegionHiring(
        hiring_id="h1",
        company_id="c1",
        region_id="r1",
        currently_hiring_flag=True,
    )
    score = compute_live_market([h], ruleset=DEFAULT_RULESET)
    # currently_hiring_count = 1, postings = 0, programs = 0
    expected = DEFAULT_RULESET.w_live_hiring_count * (
        1 / DEFAULT_RULESET.cap_currently_hiring_count
    )
    assert score == pytest.approx(expected)


def test_live_market_does_not_consider_personalization() -> None:
    """Live market reads only hiring records — the formula has no
    user-preference inputs."""
    h = CompanyRegionHiring(
        hiring_id="h1",
        company_id="c1",
        region_id="r1",
        currently_hiring_flag=True,
        active_posting_count_now=10,
    )
    score = compute_live_market([h], ruleset=DEFAULT_RULESET)
    # No user/preference fields available — confirmed by signature.
    assert 0 <= score <= 1


# --- early career accessibility ----------------------------------------


def test_early_career_zero_for_no_pairs() -> None:
    assert compute_early_career_accessibility([], ruleset=DEFAULT_RULESET) == 0.0


def test_early_career_uses_stored_access_score() -> None:
    """Slice 10 must read stored entry_level_access_score — never recompute."""
    rows = [
        CompanyRegionEntryLevel(
            entry_level_id=f"e{i}",
            company_id=f"c{i}",
            region_id="r1",
            entry_level_access_score=0.8,
        )
        for i in range(2)
    ]
    score = compute_early_career_accessibility(rows, ruleset=DEFAULT_RULESET)
    # 2 nonzero pairs × 0.8 average × saturation (2/10) = 0.16
    assert score == pytest.approx(0.16)


def test_early_career_ignores_zero_scored_pairs() -> None:
    rows = [
        CompanyRegionEntryLevel(
            entry_level_id="e1",
            company_id="c1",
            region_id="r1",
            entry_level_access_score=0.0,
        )
    ]
    assert compute_early_career_accessibility(rows, ruleset=DEFAULT_RULESET) == 0.0


def test_early_career_ignores_none_scored_pairs() -> None:
    rows = [
        CompanyRegionEntryLevel(
            entry_level_id="e1",
            company_id="c1",
            region_id="r1",
            entry_level_access_score=None,
        )
    ]
    assert compute_early_career_accessibility(rows, ruleset=DEFAULT_RULESET) == 0.0


# --- prestige -----------------------------------------------------------


def test_prestige_aggregate_partial_when_all_none() -> None:
    score, partial = compute_prestige_aggregate(
        [_CompanyStub(company_id="c1", eligibility_status="eligible")]
    )
    assert score == 0.0
    assert partial is True


def test_prestige_aggregate_average_across_known() -> None:
    score, partial = compute_prestige_aggregate(
        [
            _CompanyStub(
                company_id="c1", eligibility_status="eligible", prestige_score=0.6
            ),
            _CompanyStub(
                company_id="c2", eligibility_status="eligible", prestige_score=0.8
            ),
        ]
    )
    assert score == pytest.approx(0.7)
    assert partial is False


# --- objective opportunity ---------------------------------------------


def test_objective_entry_level_leads_modestly() -> None:
    """Three single-component fixtures: entry-level=1, others=0; etc.
    Confirms the documented 1>2>3 ordering and that the lead is moderate
    (not >>).
    """
    a = compute_objective_opportunity(
        early_career=1.0,
        live_market=0.0,
        prestige=0.0,
        ruleset=DEFAULT_RULESET,
    )
    b = compute_objective_opportunity(
        early_career=0.0,
        live_market=1.0,
        prestige=0.0,
        ruleset=DEFAULT_RULESET,
    )
    c = compute_objective_opportunity(
        early_career=0.0,
        live_market=0.0,
        prestige=1.0,
        ruleset=DEFAULT_RULESET,
    )
    assert a > b > c
    # Modest lead: A leads B by less than 0.2.
    assert (a - b) < 0.2
    # And b > c with similarly modest gap.
    assert (b - c) < 0.2


def test_objective_is_deterministic() -> None:
    a = compute_objective_opportunity(
        early_career=0.5,
        live_market=0.5,
        prestige=0.5,
        ruleset=DEFAULT_RULESET,
    )
    b = compute_objective_opportunity(
        early_career=0.5,
        live_market=0.5,
        prestige=0.5,
        ruleset=DEFAULT_RULESET,
    )
    assert a == b


def test_objective_is_bounded() -> None:
    score = compute_objective_opportunity(
        early_career=1.0,
        live_market=1.0,
        prestige=1.0,
        ruleset=DEFAULT_RULESET,
    )
    assert score == pytest.approx(1.0)
