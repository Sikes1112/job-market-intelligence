import pytest

from backend.scoring.normalization import (
    general_density_score,
    raw_total_score,
    saturate,
    tech_market_density_score,
)


def test_saturate_zero() -> None:
    assert saturate(0, 10) == 0.0


def test_saturate_negative_clamps_to_zero() -> None:
    assert saturate(-5, 10) == 0.0


def test_saturate_at_cap() -> None:
    assert saturate(10, 10) == 1.0


def test_saturate_above_cap() -> None:
    assert saturate(99, 10) == 1.0


def test_saturate_below_cap() -> None:
    assert saturate(3, 10) == pytest.approx(0.3)


def test_saturate_rejects_non_positive_cap() -> None:
    with pytest.raises(ValueError):
        saturate(5, 0)


def test_general_density_balances_count_and_postings() -> None:
    score = general_density_score(
        eligible_count=50,
        total_active_postings=500,
        cap_eligible=100,
        cap_postings=1000,
    )
    assert score == pytest.approx(0.5)  # 0.5 each, equally weighted


def test_general_density_zero_when_empty() -> None:
    score = general_density_score(
        eligible_count=0,
        total_active_postings=0,
        cap_eligible=100,
        cap_postings=1000,
    )
    assert score == 0.0


def test_tech_density_distinct_from_general() -> None:
    g = general_density_score(
        eligible_count=10,
        total_active_postings=100,
        cap_eligible=100,
        cap_postings=1000,
    )
    t = tech_market_density_score(
        major_tech_company_count=5,
        major_tech_active_postings=50,
        cap_major_companies=30,
        cap_major_postings=300,
    )
    # Different inputs and caps; just confirm they're independently computable.
    assert 0 <= g <= 1
    assert 0 <= t <= 1


def test_raw_total_combines_three_aggregates() -> None:
    total = raw_total_score(
        structural_ecosystem=0.5,
        live_market=0.5,
        objective_opportunity=0.5,
        w_structural=0.30,
        w_live=0.30,
        w_objective=0.40,
    )
    assert total == pytest.approx(0.5)


def test_raw_total_is_bounded() -> None:
    total = raw_total_score(
        structural_ecosystem=1.0,
        live_market=1.0,
        objective_opportunity=1.0,
        w_structural=0.30,
        w_live=0.30,
        w_objective=0.40,
    )
    assert total == pytest.approx(1.0)
    total = raw_total_score(
        structural_ecosystem=0.0,
        live_market=0.0,
        objective_opportunity=0.0,
        w_structural=0.30,
        w_live=0.30,
        w_objective=0.40,
    )
    assert total == 0.0
