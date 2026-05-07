"""Pure-builder tests for the contextual challenge."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.geography.models import Region
from backend.outputs.contextual_challenge import (
    ChallengeStatus,
    build_contextual_challenge,
)
from backend.outputs.exceptions import InvalidComparisonInput
from backend.outputs.types import BuildOutcome
from backend.scoring.models import RegionMarketScore


def _region(region_id: str) -> Region:
    return Region(
        region_id=region_id,
        region_name=region_id,
        display_name=region_id.replace("_", " ").title(),
        region_type="greater_region",
    )


def _score(
    *,
    region_id: str,
    objective: float | None = None,
    structural: float | None = None,
    live: float | None = None,
    early_career: float | None = None,
    raw_total: float | None = None,
    general_density: float | None = None,
    tech_density: float | None = None,
) -> RegionMarketScore:
    return RegionMarketScore(
        region_score_id=f"rms_{region_id}",
        region_id=region_id,
        structural_ecosystem_score=structural,
        live_market_score=live,
        objective_opportunity_score=objective,
        raw_total_score=raw_total,
        general_density_score=general_density,
        tech_market_density_score=tech_density,
        early_career_accessibility_score=early_career,
        score_ruleset_version="marketscore_v1",
    )


_NOW = datetime(2026, 5, 7, tzinfo=UTC)


def test_reinforced_when_all_contextual_categories_back_primary_winner() -> None:
    a = _region("greater_boston")
    b = _region("greater_sf")
    score_a = _score(
        region_id="greater_boston",
        objective=0.80,
        structural=0.80,
        live=0.80,
        early_career=0.80,
        raw_total=0.80,
        general_density=0.80,
        tech_density=0.80,
    )
    score_b = _score(
        region_id="greater_sf",
        objective=0.40,
        structural=0.40,
        live=0.40,
        early_career=0.40,
        raw_total=0.40,
        general_density=0.40,
        tech_density=0.40,
    )

    result = build_contextual_challenge(
        region_a=a, region_b=b, score_a=score_a, score_b=score_b, now=_NOW
    )

    body = result.payload.contextual_challenge
    assert body.challenge_status is ChallengeStatus.REINFORCED
    assert body.primary_winner_region_id == "greater_boston"
    assert body.reinforced_count == 6
    assert body.challenged_count == 0
    assert all(f.favors_primary is True for f in body.findings)
    assert {f.category for f in body.findings} == {
        "early_career_accessibility_score",
        "live_market_score",
        "structural_ecosystem_score",
        "tech_market_density_score",
        "general_density_score",
        "raw_total_score",
    }


def test_challenged_when_contextual_signals_oppose_primary_winner() -> None:
    a = _region("greater_boston")
    b = _region("greater_sf")
    # Boston wins primary objective_opportunity_score but loses everywhere else.
    score_a = _score(
        region_id="greater_boston",
        objective=0.90,
        structural=0.10,
        live=0.10,
        early_career=0.10,
        raw_total=0.10,
        general_density=0.10,
        tech_density=0.10,
    )
    score_b = _score(
        region_id="greater_sf",
        objective=0.50,
        structural=0.80,
        live=0.80,
        early_career=0.80,
        raw_total=0.80,
        general_density=0.80,
        tech_density=0.80,
    )

    result = build_contextual_challenge(
        region_a=a, region_b=b, score_a=score_a, score_b=score_b, now=_NOW
    )
    body = result.payload.contextual_challenge
    assert body.challenge_status is ChallengeStatus.CHALLENGED
    assert body.primary_winner_region_id == "greater_boston"
    assert body.challenged_count == 6
    assert body.reinforced_count == 0
    assert all(
        f.reason_code.startswith("primary_winner_challenged_by_")
        for f in body.findings
    )


def test_unchanged_when_contextual_signals_split_evenly() -> None:
    a = _region("greater_boston")
    b = _region("greater_sf")
    # Boston wins primary; three contextual categories favor Boston, three SF.
    score_a = _score(
        region_id="greater_boston",
        objective=0.80,
        structural=0.90,
        live=0.90,
        early_career=0.90,
        raw_total=0.10,
        general_density=0.10,
        tech_density=0.10,
    )
    score_b = _score(
        region_id="greater_sf",
        objective=0.40,
        structural=0.10,
        live=0.10,
        early_career=0.10,
        raw_total=0.90,
        general_density=0.90,
        tech_density=0.90,
    )
    result = build_contextual_challenge(
        region_a=a, region_b=b, score_a=score_a, score_b=score_b, now=_NOW
    )
    body = result.payload.contextual_challenge
    assert body.challenge_status is ChallengeStatus.UNCHANGED
    assert body.reinforced_count == 3
    assert body.challenged_count == 3
    assert "no_clear_contextual_difference" in body.explanation_codes


def test_unchanged_when_no_comparable_contextual_categories() -> None:
    a = _region("greater_boston")
    b = _region("greater_sf")
    # Primary present on both; but no contextual category has both sides.
    score_a = _score(
        region_id="greater_boston",
        objective=0.80,
        structural=0.5,  # but b's structural is None -> skipped
    )
    score_b = _score(region_id="greater_sf", objective=0.40)
    result = build_contextual_challenge(
        region_a=a, region_b=b, score_a=score_a, score_b=score_b, now=_NOW
    )
    body = result.payload.contextual_challenge
    assert body.challenge_status is ChallengeStatus.UNCHANGED
    assert body.findings == []
    assert body.reinforced_count == 0
    assert body.challenged_count == 0
    assert "no_clear_contextual_difference" in body.explanation_codes


def test_insufficient_data_when_one_side_score_missing() -> None:
    a = _region("greater_boston")
    b = _region("greater_sf")
    score_a = _score(region_id="greater_boston", objective=0.80, live=0.7)
    result = build_contextual_challenge(
        region_a=a, region_b=b, score_a=score_a, score_b=None, now=_NOW
    )
    body = result.payload.contextual_challenge
    assert body.challenge_status is ChallengeStatus.INSUFFICIENT_DATA
    assert body.primary_winner_region_id is None
    assert body.findings == []
    assert "insufficient_score_data" in body.explanation_codes
    assert result.outcome is BuildOutcome.PARTIAL


def test_insufficient_data_when_primary_score_missing_on_one_side() -> None:
    a = _region("greater_boston")
    b = _region("greater_sf")
    score_a = _score(region_id="greater_boston", objective=0.80, live=0.7)
    score_b = _score(region_id="greater_sf", objective=None, live=0.5)
    result = build_contextual_challenge(
        region_a=a, region_b=b, score_a=score_a, score_b=score_b, now=_NOW
    )
    body = result.payload.contextual_challenge
    assert body.challenge_status is ChallengeStatus.INSUFFICIENT_DATA
    assert body.primary_winner_region_id is None
    assert result.outcome is BuildOutcome.PARTIAL


def test_primary_tie_forces_unchanged_with_no_clear_primary_winner() -> None:
    a = _region("greater_boston")
    b = _region("greater_sf")
    score_a = _score(
        region_id="greater_boston", objective=0.5, structural=0.9, live=0.9
    )
    score_b = _score(region_id="greater_sf", objective=0.5, structural=0.1, live=0.1)
    result = build_contextual_challenge(
        region_a=a, region_b=b, score_a=score_a, score_b=score_b, now=_NOW
    )
    body = result.payload.contextual_challenge
    assert body.challenge_status is ChallengeStatus.UNCHANGED
    assert body.primary_winner_region_id is None
    assert body.explanation_codes == ["no_clear_primary_winner"]


def test_subject_id_is_canonical_pair_regardless_of_call_order() -> None:
    a = _region("greater_boston")
    b = _region("greater_sf")
    sa = _score(region_id="greater_boston", objective=0.8)
    sb = _score(region_id="greater_sf", objective=0.6)

    forward = build_contextual_challenge(
        region_a=a, region_b=b, score_a=sa, score_b=sb, now=_NOW
    )
    reverse = build_contextual_challenge(
        region_a=b, region_b=a, score_a=sb, score_b=sa, now=_NOW
    )
    assert (
        forward.payload.contextual_challenge.comparison_id
        == reverse.payload.contextual_challenge.comparison_id
        == "greater_boston__greater_sf"
    )
    # The canonical-side fields also match.
    assert (
        forward.payload.contextual_challenge.region_a_id
        == reverse.payload.contextual_challenge.region_a_id
        == "greater_boston"
    )


def test_rejects_identical_regions() -> None:
    a = _region("greater_boston")
    b = _region("greater_boston")
    sa = _score(region_id="greater_boston", objective=0.5)
    with pytest.raises(InvalidComparisonInput):
        build_contextual_challenge(
            region_a=a, region_b=b, score_a=sa, score_b=sa, now=_NOW
        )


def test_findings_carry_both_sides_values() -> None:
    a = _region("greater_boston")
    b = _region("greater_sf")
    score_a = _score(region_id="greater_boston", objective=0.8, live=0.7)
    score_b = _score(region_id="greater_sf", objective=0.4, live=0.3)
    result = build_contextual_challenge(
        region_a=a, region_b=b, score_a=score_a, score_b=score_b, now=_NOW
    )
    [finding] = result.payload.contextual_challenge.findings
    assert finding.category == "live_market_score"
    assert finding.region_a_value == 0.7
    assert finding.region_b_value == 0.3
    assert finding.winner_region_id == "greater_boston"


def test_outcome_is_fresh_for_normal_paths() -> None:
    a = _region("greater_boston")
    b = _region("greater_sf")
    sa = _score(region_id="greater_boston", objective=0.8, live=0.7)
    sb = _score(region_id="greater_sf", objective=0.4, live=0.3)
    result = build_contextual_challenge(
        region_a=a, region_b=b, score_a=sa, score_b=sb, now=_NOW
    )
    assert result.outcome is BuildOutcome.FRESH
    assert result.payload.metadata.state == "fresh"
