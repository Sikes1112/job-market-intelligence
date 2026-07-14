"""Deterministic sensitivity scenarios for Layer 34C calibration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace

from backend.market_intelligence.goals import career_goal_definition
from backend.market_intelligence.schemas import (
    CareerGoal,
    EvidenceSufficiency,
    ExplainableRankingItem,
    ExplainableRankingReport,
    IntelligenceConfidence,
    IntelligenceFreshness,
    MarketGoalStabilityAnalysis,
    MarketIntelligenceProfile,
    RankingStabilityStatus,
    RobustnessScenarioCode,
    RobustnessScenarioRankingResult,
    RobustnessScenarioResult,
)
from backend.market_intelligence.scoring import MarketMetrics, rank_profiles
from backend.market_intelligence.sufficiency import sufficiency_allows_recommendation

_CONFIDENCE_ORDER = {
    IntelligenceConfidence.LIMITED: 1,
    IntelligenceConfidence.LOW: 2,
    IntelligenceConfidence.MODERATE: 3,
    IntelligenceConfidence.HIGH: 4,
}


@dataclass(frozen=True, slots=True)
class _Scenario:
    code: RobustnessScenarioCode
    label: str
    apply: Callable[[MarketMetrics, CareerGoal], tuple[MarketMetrics, bool, str]]
    missing_data: bool = False


SCENARIOS: tuple[_Scenario, ...] = (
    _Scenario(
        RobustnessScenarioCode.UNKNOWN_TO_OBSERVED_ZERO,
        "Unknown count becomes observed zero",
        lambda metrics, goal: _unknown_to_zero(metrics),
    ),
    _Scenario(
        RobustnessScenarioCode.OBSERVED_ZERO_TO_UNKNOWN,
        "Observed zero becomes unknown",
        lambda metrics, goal: _zero_to_unknown(metrics),
        missing_data=True,
    ),
    _Scenario(
        RobustnessScenarioCode.STALE_SOURCE,
        "Primary source becomes stale",
        lambda metrics, goal: _stale_source(metrics),
        missing_data=True,
    ),
    _Scenario(
        RobustnessScenarioCode.EXPIRED_SOURCE,
        "Primary source becomes expired",
        lambda metrics, goal: _expired_source(metrics),
        missing_data=True,
    ),
    _Scenario(
        RobustnessScenarioCode.LOW_CONFIDENCE_EXCLUSION,
        "Low-confidence fact is excluded",
        lambda metrics, goal: _exclude_fact(
            metrics,
            confidence_penalty=0.08,
            limitation="A low-confidence fact is excluded from ranking influence.",
        ),
        missing_data=True,
    ),
    _Scenario(
        RobustnessScenarioCode.RANKING_EXCLUSION,
        "Ranking-eligible fact is excluded",
        lambda metrics, goal: _exclude_fact(
            metrics,
            confidence_penalty=0.10,
            limitation="A ranking-eligible fact is excluded in sensitivity analysis.",
        ),
        missing_data=True,
    ),
    _Scenario(
        RobustnessScenarioCode.MISSING_INTERNSHIP,
        "Internship evidence is missing",
        lambda metrics, goal: _missing_internship(metrics),
        missing_data=True,
    ),
    _Scenario(
        RobustnessScenarioCode.MISSING_COOP,
        "Co-op evidence is missing",
        lambda metrics, goal: _missing_coop(metrics),
        missing_data=True,
    ),
    _Scenario(
        RobustnessScenarioCode.DOMINANT_EMPLOYER,
        "Employer evidence is concentrated",
        lambda metrics, goal: _dominant_employer(metrics),
    ),
    _Scenario(
        RobustnessScenarioCode.SOURCE_CONCENTRATION,
        "Source evidence is concentrated",
        lambda metrics, goal: _source_concentration(metrics),
    ),
    _Scenario(
        RobustnessScenarioCode.SPARSE_COVERAGE,
        "Coverage becomes sparse",
        lambda metrics, goal: _sparse_coverage(metrics),
        missing_data=True,
    ),
    _Scenario(
        RobustnessScenarioCode.DIRECT_EVIDENCE_REMOVED,
        "Strongest direct evidence is removed",
        lambda metrics, goal: _direct_evidence_removed(metrics, goal),
        missing_data=True,
    ),
    _Scenario(
        RobustnessScenarioCode.PROXY_ONLY_EVIDENCE,
        "Only proxy evidence remains",
        lambda metrics, goal: _proxy_only_evidence(metrics, goal),
        missing_data=True,
    ),
    _Scenario(
        RobustnessScenarioCode.CONTRADICTORY_INPUTS,
        "Contradictory inputs are present",
        lambda metrics, goal: _contradictory_inputs(metrics),
    ),
)


def evaluate_ranking_robustness(
    *,
    rankings: Mapping[CareerGoal, ExplainableRankingReport],
    profiles: tuple[MarketIntelligenceProfile, ...],
    metrics_by_market: Mapping[str, MarketMetrics],
) -> dict[CareerGoal, dict[str, MarketGoalStabilityAnalysis]]:
    """Run the required Layer 34C scenarios without mutating canonical state."""

    profiles_by_market = {profile.market_key: profile for profile in profiles}
    profile_tuple = tuple(sorted(profiles, key=lambda item: item.market_key))
    result: dict[CareerGoal, dict[str, MarketGoalStabilityAnalysis]] = {}

    for goal, ranking in sorted(rankings.items(), key=lambda item: item[0].value):
        goal_result: dict[str, MarketGoalStabilityAnalysis] = {}
        for item in ranking.ranked_markets:
            scenario_results = [
                _run_metric_scenario(
                    scenario,
                    goal=goal,
                    target=item.market_key,
                    baseline_ranking=ranking,
                    profiles=profile_tuple,
                    profiles_by_market=profiles_by_market,
                    metrics_by_market=metrics_by_market,
                )
                for scenario in SCENARIOS
            ]
            scenario_results.append(
                _run_small_score_perturbation_scenario(
                    goal=goal,
                    target=item.market_key,
                    baseline_ranking=ranking,
                )
            )
            scenario_results.append(
                _run_equal_evidence_tie_scenario(
                    goal=goal,
                    target=item.market_key,
                    baseline_ranking=ranking,
                )
            )
            goal_result[item.market_key] = MarketGoalStabilityAnalysis(
                status=_aggregate_status(tuple(scenario_results)),
                scenarios=tuple(scenario_results),
            )
        result[goal] = goal_result
    return result


def _run_metric_scenario(
    scenario: _Scenario,
    *,
    goal: CareerGoal,
    target: str,
    baseline_ranking: ExplainableRankingReport,
    profiles: tuple[MarketIntelligenceProfile, ...],
    profiles_by_market: Mapping[str, MarketIntelligenceProfile],
    metrics_by_market: Mapping[str, MarketMetrics],
) -> RobustnessScenarioResult:
    baseline_item = _ranking_item(baseline_ranking.ranked_markets, target)
    baseline_point = _point(baseline_item, baseline_ranking.top_market_key)
    scenario_metrics, applied, reason = scenario.apply(metrics_by_market[target], goal)
    if not applied:
        return _scenario_result(
            scenario_code=scenario.code,
            label=scenario.label,
            baseline=baseline_point,
            scenario=baseline_point,
            applied=False,
            missing_data=scenario.missing_data,
            reason=reason,
        )

    perturbed_metrics = dict(metrics_by_market)
    perturbed_metrics[target] = scenario_metrics
    perturbed_profiles = tuple(
        _profile_for_metrics(profile, scenario_metrics)
        if profile.market_key == target
        else profile
        for profile in profiles
    )
    scenario_ranking = rank_profiles(
        perturbed_profiles,
        perturbed_metrics,
        goal=goal,
        goal_definition=career_goal_definition(goal),
    )
    scenario_item = _ranking_item(scenario_ranking.ranked_markets, target)
    return _scenario_result(
        scenario_code=scenario.code,
        label=scenario.label,
        baseline=baseline_point,
        scenario=_point(scenario_item, scenario_ranking.top_market_key),
        applied=True,
        missing_data=scenario.missing_data,
        reason=reason,
    )


def _run_equal_evidence_tie_scenario(
    *,
    goal: CareerGoal,
    target: str,
    baseline_ranking: ExplainableRankingReport,
) -> RobustnessScenarioResult:
    baseline_item = _ranking_item(baseline_ranking.ranked_markets, target)
    baseline_point = _point(baseline_item, baseline_ranking.top_market_key)
    peers = tuple(
        item for item in baseline_ranking.ranked_markets if item.market_key != target
    )
    if not peers:
        return _scenario_result(
            scenario_code=RobustnessScenarioCode.EQUAL_EVIDENCE_TIE,
            label="Evidence becomes an exact tie",
            baseline=baseline_point,
            scenario=baseline_point,
            applied=False,
            missing_data=False,
            reason="no peer market is available for an equal-evidence tie.",
        )

    peer = sorted(
        peers,
        key=lambda item: (abs(item.score - baseline_item.score), item.market_key),
    )[0]
    tied_items = tuple(
        replace(item, score=peer.score, raw_score=peer.raw_score)
        if item.market_key == target
        else item
        for item in baseline_ranking.ranked_markets
    )
    reranked = _rerank_items(tied_items)
    scenario_item = _ranking_item(reranked, target)
    return _scenario_result(
        scenario_code=RobustnessScenarioCode.EQUAL_EVIDENCE_TIE,
        label="Evidence becomes an exact tie",
        baseline=baseline_point,
        scenario=_point(scenario_item, _top_market_key(reranked)),
        applied=True,
        missing_data=False,
        reason=(
            f"{baseline_item.market_name} is set equal to nearest peer "
            f"{peer.market_name}; market-key ordering is diagnostic only."
        ),
    )


def _run_small_score_perturbation_scenario(
    *,
    goal: CareerGoal,
    target: str,
    baseline_ranking: ExplainableRankingReport,
) -> RobustnessScenarioResult:
    baseline_item = _ranking_item(baseline_ranking.ranked_markets, target)
    baseline_point = _point(baseline_item, baseline_ranking.top_market_key)
    peers = tuple(
        item for item in baseline_ranking.ranked_markets if item.market_key != target
    )
    if not peers:
        return _scenario_result(
            scenario_code=RobustnessScenarioCode.SMALL_SCORE_PERTURBATION,
            label="Small score perturbation",
            baseline=baseline_point,
            scenario=baseline_point,
            applied=False,
            missing_data=False,
            reason="no peer market is available for a small score perturbation.",
        )

    peer = sorted(
        peers,
        key=lambda item: (abs(item.score - baseline_item.score), item.market_key),
    )[0]
    perturbed_score, reason = _small_perturbed_score(baseline_item, peer)
    perturbed_items = tuple(
        replace(item, score=perturbed_score, raw_score=perturbed_score)
        if item.market_key == target
        else item
        for item in baseline_ranking.ranked_markets
    )
    reranked = _rerank_items(perturbed_items)
    scenario_item = _ranking_item(reranked, target)
    return _scenario_result(
        scenario_code=RobustnessScenarioCode.SMALL_SCORE_PERTURBATION,
        label="Small score perturbation",
        baseline=baseline_point,
        scenario=_point(scenario_item, _top_market_key(reranked)),
        applied=True,
        missing_data=False,
        reason=reason,
    )


def _scenario_result(
    *,
    scenario_code: RobustnessScenarioCode,
    label: str,
    baseline: RobustnessScenarioRankingResult,
    scenario: RobustnessScenarioRankingResult,
    applied: bool,
    missing_data: bool,
    reason: str,
) -> RobustnessScenarioResult:
    rank_change = scenario.rank - baseline.rank
    score_delta = round(scenario.score - baseline.score, 4)
    confidence_delta = (
        _CONFIDENCE_ORDER[scenario.confidence]
        - _CONFIDENCE_ORDER[baseline.confidence]
    )
    sufficiency_delta = (
        "unchanged"
        if scenario.evidence_sufficiency is baseline.evidence_sufficiency
        else f"{baseline.evidence_sufficiency.value}->{scenario.evidence_sufficiency.value}"
    )
    winner_change = scenario.top_market_key != baseline.top_market_key
    status = _scenario_status(
        applied=applied,
        rank_change=rank_change,
        score_delta=score_delta,
        winner_change=winner_change,
        baseline_sufficiency=baseline.evidence_sufficiency,
        scenario_sufficiency=scenario.evidence_sufficiency,
        confidence_delta=confidence_delta,
        missing_data=missing_data,
    )
    return RobustnessScenarioResult(
        scenario=scenario_code,
        label=label,
        status=status,
        baseline_result=baseline,
        scenario_result=scenario,
        rank_change=rank_change,
        winner_change=winner_change,
        score_delta=score_delta,
        confidence_delta=confidence_delta,
        sufficiency_delta=sufficiency_delta,
        explanation=_public_explanation(
            label=label,
            status=status,
            baseline=baseline,
            scenario=scenario,
            rank_change=rank_change,
            score_delta=score_delta,
            confidence_delta=confidence_delta,
            sufficiency_delta=sufficiency_delta,
            winner_change=winner_change,
            applied=applied,
            reason=reason,
        ),
    )


def _scenario_status(
    *,
    applied: bool,
    rank_change: int,
    score_delta: float,
    winner_change: bool,
    baseline_sufficiency: EvidenceSufficiency,
    scenario_sufficiency: EvidenceSufficiency,
    confidence_delta: int,
    missing_data: bool,
) -> RankingStabilityStatus:
    if not applied:
        return RankingStabilityStatus.INDETERMINATE
    if missing_data and (
        confidence_delta > 0
        or score_delta > 0
        or rank_change < 0
        or winner_change
    ):
        return RankingStabilityStatus.UNSTABLE
    if winner_change or abs(rank_change) >= 2:
        return RankingStabilityStatus.UNSTABLE
    baseline_allows = sufficiency_allows_recommendation(baseline_sufficiency)
    scenario_allows = sufficiency_allows_recommendation(scenario_sufficiency)
    if baseline_allows != scenario_allows:
        return RankingStabilityStatus.UNSTABLE
    if (
        rank_change
        or abs(score_delta) >= 0.05
        or confidence_delta
        or baseline_sufficiency is not scenario_sufficiency
    ):
        return RankingStabilityStatus.SENSITIVE
    return RankingStabilityStatus.STABLE


def _aggregate_status(
    results: tuple[RobustnessScenarioResult, ...],
) -> RankingStabilityStatus:
    statuses = {result.status for result in results}
    if RankingStabilityStatus.UNSTABLE in statuses:
        return RankingStabilityStatus.UNSTABLE
    if RankingStabilityStatus.SENSITIVE in statuses:
        return RankingStabilityStatus.SENSITIVE
    if RankingStabilityStatus.STABLE in statuses:
        return RankingStabilityStatus.STABLE
    return RankingStabilityStatus.INDETERMINATE


def _unknown_to_zero(metrics: MarketMetrics) -> tuple[MarketMetrics, bool, str]:
    if metrics.unknown_fact_count <= 0:
        return metrics, False, "no unknown count fact is available to convert."
    updated = replace(
        metrics,
        unknown_fact_count=max(0, metrics.unknown_fact_count - 1),
        observed_zero_fact_count=metrics.observed_zero_fact_count + 1,
        active_posting_unknown_rows=max(0, metrics.active_posting_unknown_rows - 1),
        active_posting_zero_rows=metrics.active_posting_zero_rows + 1,
    )
    if updated.unknown_fact_count == 0:
        updated = replace(
            updated,
            limitations=_remove_limitation(
                updated.limitations,
                "Some count facts are unknown",
            ),
        )
    updated = _with_confidence_score(updated, updated.confidence_score + 0.03)
    return (
        updated,
        True,
        "one unknown count is treated as an observed zero; zero remains distinct "
        "from missing data.",
    )


def _zero_to_unknown(metrics: MarketMetrics) -> tuple[MarketMetrics, bool, str]:
    if metrics.observed_zero_fact_count <= 0:
        return metrics, False, "no observed zero count fact is available to remove."
    updated = replace(
        metrics,
        observed_zero_fact_count=max(0, metrics.observed_zero_fact_count - 1),
        unknown_fact_count=metrics.unknown_fact_count + 1,
        active_posting_zero_rows=max(0, metrics.active_posting_zero_rows - 1),
        active_posting_unknown_rows=metrics.active_posting_unknown_rows + 1,
    )
    updated = _with_confidence_score(updated, updated.confidence_score - 0.08)
    return (
        _with_limitation(
            updated,
            "A previously observed zero count becomes unknown; missing data is not "
            "treated as zero.",
        ),
        True,
        "one observed zero count becomes unknown, reducing confidence instead of increasing it.",
    )


def _stale_source(metrics: MarketMetrics) -> tuple[MarketMetrics, bool, str]:
    if metrics.freshness is IntelligenceFreshness.STALE:
        return metrics, False, "the baseline source freshness is already stale."
    updated = replace(
        metrics,
        freshness=IntelligenceFreshness.STALE,
        stale_source_count=metrics.stale_source_count + 1,
    )
    updated = _with_confidence_score(updated, updated.confidence_score - 0.25)
    return (
        _with_limitation(updated, "One or more source references are stale."),
        True,
        "source freshness is degraded to stale and confidence is capped by sufficiency.",
    )


def _expired_source(metrics: MarketMetrics) -> tuple[MarketMetrics, bool, str]:
    if metrics.expired_source_count > 0:
        return metrics, False, "the baseline source set already includes expired evidence."
    updated = replace(
        metrics,
        freshness=IntelligenceFreshness.STALE,
        expired_source_count=metrics.expired_source_count + 1,
    )
    updated = _with_confidence_score(updated, updated.confidence_score - 0.30)
    return (
        _with_limitation(updated, "One or more source references are expired."),
        True,
        "source freshness is degraded to expired evidence and confidence is reduced.",
    )


def _exclude_fact(
    metrics: MarketMetrics,
    *,
    confidence_penalty: float,
    limitation: str,
) -> tuple[MarketMetrics, bool, str]:
    if metrics.ranking_eligible_fact_count <= 0:
        return metrics, False, "no ranking-eligible fact is available to exclude."
    updated = replace(
        metrics,
        ranking_eligible_fact_count=max(0, metrics.ranking_eligible_fact_count - 1),
        ranking_excluded_fact_count=metrics.ranking_excluded_fact_count + 1,
    )
    updated = _with_confidence_score(updated, updated.confidence_score - confidence_penalty)
    return (
        _with_limitation(updated, limitation),
        True,
        "one qualifying fact is removed from ranking influence.",
    )


def _missing_internship(metrics: MarketMetrics) -> tuple[MarketMetrics, bool, str]:
    if metrics.internship_total is None and metrics.internship_observed_rows <= 0:
        return metrics, False, "no observed internship evidence is available to remove."
    updated = replace(
        metrics,
        internship_total=None,
        internship_unknown_rows=(
            metrics.internship_unknown_rows + metrics.internship_observed_rows
        ),
        internship_observed_rows=0,
    )
    updated = _with_confidence_score(updated, updated.confidence_score - 0.08)
    return (
        _with_limitation(updated, "Internship evidence is missing in sensitivity analysis."),
        True,
        "observed internship evidence is removed and treated as missing.",
    )


def _missing_coop(metrics: MarketMetrics) -> tuple[MarketMetrics, bool, str]:
    if metrics.coop_total is None and metrics.coop_observed_rows <= 0:
        return metrics, False, "no observed co-op evidence is available to remove."
    updated = replace(
        metrics,
        coop_total=None,
        coop_unknown_rows=metrics.coop_unknown_rows + metrics.coop_observed_rows,
        coop_observed_rows=0,
    )
    updated = _with_confidence_score(updated, updated.confidence_score - 0.05)
    return (
        _with_limitation(updated, "Co-op coverage is limited or unavailable."),
        True,
        "observed co-op evidence is removed and represented as missing coverage.",
    )


def _dominant_employer(metrics: MarketMetrics) -> tuple[MarketMetrics, bool, str]:
    if metrics.employer_count <= 1:
        return metrics, False, "the baseline market is already single-employer coverage."
    updated = replace(
        metrics,
        employer_count=1,
        sector_count=min(metrics.sector_count, 1),
        major_tech_count=min(metrics.major_tech_count, 1),
        mag7_count=min(metrics.mag7_count, 1),
        ai_cloud_employer_count=min(metrics.ai_cloud_employer_count, 1),
        cybersecurity_employer_count=min(metrics.cybersecurity_employer_count, 1),
    )
    updated = _with_confidence_score(updated, updated.confidence_score - 0.05)
    return (
        _with_limitation(
            updated,
            "Employer evidence is concentrated in one dominant employer.",
        ),
        True,
        "employer breadth is collapsed to one dominant employer to test concentration risk.",
    )


def _source_concentration(metrics: MarketMetrics) -> tuple[MarketMetrics, bool, str]:
    if metrics.source_count <= 1:
        return metrics, False, "the baseline evidence is already single-source coverage."
    updated = replace(
        metrics,
        source_count=1,
        medium_gap_count=metrics.medium_gap_count + 1,
    )
    updated = _with_confidence_score(updated, updated.confidence_score - 0.10)
    return (
        _with_limitation(updated, "Source evidence is concentrated in one source."),
        True,
        "source coverage is collapsed to one public source to test concentration risk.",
    )


def _sparse_coverage(metrics: MarketMetrics) -> tuple[MarketMetrics, bool, str]:
    if metrics.total_fact_count <= 0:
        return metrics, False, "no fact coverage exists to sparsify."
    eligible = max(1, metrics.ranking_eligible_fact_count // 2)
    unknown = max(metrics.unknown_fact_count + 2, metrics.total_fact_count - eligible)
    updated = replace(
        metrics,
        total_fact_count=max(metrics.total_fact_count, unknown),
        ranking_eligible_fact_count=eligible,
        ranking_excluded_fact_count=(
            metrics.ranking_excluded_fact_count
            + max(0, metrics.ranking_eligible_fact_count - eligible)
        ),
        unknown_fact_count=unknown,
        high_gap_count=metrics.high_gap_count + 1,
    )
    updated = _with_confidence_score(updated, updated.confidence_score - 0.18)
    return (
        _with_limitation(updated, "Sparse coverage limits ranking stability."),
        True,
        "coverage is reduced and unknown facts increase to test sparse-market behavior.",
    )


def _direct_evidence_removed(
    metrics: MarketMetrics,
    goal: CareerGoal,
) -> tuple[MarketMetrics, bool, str]:
    categories = tuple(
        category
        for category in career_goal_definition(goal).direct_evidence_categories
        if _category_has_evidence(metrics, category)
    )
    if not categories:
        return metrics, False, "no direct goal evidence is available to remove."
    updated = _remove_categories(metrics, categories[:1])
    updated = _with_confidence_score(updated, updated.confidence_score - 0.12)
    return (
        _with_limitation(updated, "Direct goal evidence is removed in sensitivity analysis."),
        True,
        f"direct evidence category {categories[0]} is removed.",
    )


def _proxy_only_evidence(
    metrics: MarketMetrics,
    goal: CareerGoal,
) -> tuple[MarketMetrics, bool, str]:
    categories = tuple(
        category
        for category in career_goal_definition(goal).direct_evidence_categories
        if _category_has_evidence(metrics, category)
    )
    if not categories:
        return metrics, False, "no direct goal evidence is available to remove."
    updated = _remove_categories(metrics, categories)
    updated = _with_confidence_score(updated, updated.confidence_score - 0.18)
    return (
        _with_limitation(updated, "Only proxy evidence remains in sensitivity analysis."),
        True,
        "all available direct goal evidence is removed, leaving proxy evidence only.",
    )


def _contradictory_inputs(metrics: MarketMetrics) -> tuple[MarketMetrics, bool, str]:
    if metrics.total_fact_count <= 0:
        return metrics, False, "no fact coverage exists to test contradictory inputs."
    updated = replace(
        metrics,
        high_gap_count=metrics.high_gap_count + 1,
        ranking_excluded_fact_count=metrics.ranking_excluded_fact_count + 1,
    )
    updated = _with_confidence_score(updated, updated.confidence_score - 0.22)
    return (
        _with_limitation(
            updated,
            "Contradictory inputs require manual review before firm recommendation.",
        ),
        True,
        "a contradictory-input diagnostic reduces confidence and excludes one fact.",
    )


def _remove_categories(
    metrics: MarketMetrics,
    categories: tuple[str, ...],
) -> MarketMetrics:
    updates: dict[str, object] = {}
    role_active = dict(metrics.role_active_postings)
    role_observed = dict(metrics.role_observed_rows)
    role_unknown = dict(metrics.role_unknown_rows)

    for category in categories:
        if category == "hiring_activity":
            updates["active_posting_total"] = None
            updates["active_posting_unknown_rows"] = (
                metrics.active_posting_unknown_rows + metrics.active_posting_observed_rows
            )
            updates["active_posting_observed_rows"] = 0
            updates["active_posting_zero_rows"] = 0
            role_active.clear()
            role_observed.clear()
            role_unknown["unknown"] = role_unknown.get("unknown", 0) + 1
        elif category == "tech_signal":
            updates["tech_density_score"] = 0.0
            updates["major_tech_count"] = 0
            updates["ai_cloud_employer_count"] = 0
            updates["cybersecurity_employer_count"] = 0
        elif category == "early_career":
            updates["early_career_score"] = 0.0
            updates["entry_level_full_time_total"] = None
            updates["formal_program_count"] = 0
            updates["positive_entry_level_score_count"] = 0
        elif category == "formal_programs":
            updates["formal_program_count"] = 0
        elif category == "internship":
            updates["internship_total"] = None
            updates["internship_unknown_rows"] = (
                metrics.internship_unknown_rows + metrics.internship_observed_rows
            )
            updates["internship_observed_rows"] = 0
        elif category == "product_activity":
            _remove_role(role_active, role_observed, role_unknown, "product")
        elif category == "ai_cloud_activity":
            _remove_role(role_active, role_observed, role_unknown, "ai_cloud_adjacent")
        elif category == "ai_cloud_employers":
            updates["ai_cloud_employer_count"] = 0
        elif category == "cybersecurity_activity":
            _remove_role(role_active, role_observed, role_unknown, "cybersecurity")
        elif category == "cybersecurity_employers":
            updates["cybersecurity_employer_count"] = 0

    updates["role_active_postings"] = dict(sorted(role_active.items()))
    updates["role_observed_rows"] = dict(sorted(role_observed.items()))
    updates["role_unknown_rows"] = dict(sorted(role_unknown.items()))
    return replace(metrics, **updates)


def _remove_role(
    role_active: dict[str, int],
    role_observed: dict[str, int],
    role_unknown: dict[str, int],
    role: str,
) -> None:
    observed_rows = role_observed.get(role, 0)
    role_active.pop(role, None)
    role_observed.pop(role, None)
    if observed_rows:
        role_unknown[role] = role_unknown.get(role, 0) + observed_rows


def _category_has_evidence(metrics: MarketMetrics, category: str) -> bool:
    return _category_value(metrics, category) > 0


def _category_value(metrics: MarketMetrics, category: str) -> float:
    values: dict[str, float] = {
        "employer_presence": float(metrics.employer_count),
        "hiring_activity": float(metrics.active_posting_total or 0),
        "tech_signal": float(
            (metrics.tech_density_score or 0)
            + metrics.ai_cloud_employer_count
            + metrics.cybersecurity_employer_count
            + metrics.major_tech_count
        ),
        "early_career": float(
            (metrics.early_career_score or 0)
            + (metrics.entry_level_full_time_total or 0)
            + metrics.formal_program_count
        ),
        "formal_programs": float(metrics.formal_program_count),
        "internship": float(metrics.internship_total or 0),
        "product_activity": float(metrics.product_activity or 0),
        "ai_cloud_activity": float(metrics.ai_cloud_activity or 0),
        "ai_cloud_employers": float(metrics.ai_cloud_employer_count),
        "cybersecurity_activity": float(metrics.cybersecurity_activity or 0),
        "cybersecurity_employers": float(metrics.cybersecurity_employer_count),
    }
    return values.get(category, 0.0)


def _profile_for_metrics(
    profile: MarketIntelligenceProfile,
    metrics: MarketMetrics,
) -> MarketIntelligenceProfile:
    return replace(
        profile,
        confidence=metrics.confidence,
        confidence_score=metrics.confidence_score,
        freshness=metrics.freshness,
        limitations=metrics.limitations,
        supporting_metrics=metrics.supporting_metrics(),
    )


def _with_limitation(metrics: MarketMetrics, limitation: str) -> MarketMetrics:
    return replace(metrics, limitations=tuple(dict.fromkeys((*metrics.limitations, limitation))))


def _remove_limitation(
    limitations: tuple[str, ...],
    prefix: str,
) -> tuple[str, ...]:
    return tuple(item for item in limitations if not item.startswith(prefix))


def _with_confidence_score(metrics: MarketMetrics, score: float) -> MarketMetrics:
    confidence_score = round(max(0.0, min(1.0, score)), 4)
    return replace(
        metrics,
        confidence_score=confidence_score,
        confidence=_confidence_label(confidence_score),
    )


def _confidence_label(score: float) -> IntelligenceConfidence:
    if score >= 0.80:
        return IntelligenceConfidence.HIGH
    if score >= 0.60:
        return IntelligenceConfidence.MODERATE
    if score >= 0.40:
        return IntelligenceConfidence.LOW
    return IntelligenceConfidence.LIMITED


def _rerank_items(
    items: tuple[ExplainableRankingItem, ...],
) -> tuple[ExplainableRankingItem, ...]:
    return tuple(
        replace(item, rank=index)
        for index, item in enumerate(
            sorted(items, key=lambda ranked: (-ranked.score, ranked.market_key)),
            start=1,
        )
    )


def _top_market_key(items: tuple[ExplainableRankingItem, ...]) -> str | None:
    if not items:
        return None
    top = items[0]
    return (
        top.market_key
        if sufficiency_allows_recommendation(top.evidence_sufficiency)
        else None
    )


def _small_perturbed_score(
    baseline_item: ExplainableRankingItem,
    peer: ExplainableRankingItem,
) -> tuple[float, str]:
    max_delta = 0.01
    crossing_delta = abs(baseline_item.score - peer.score) + 0.0001
    if baseline_item.score >= peer.score:
        if crossing_delta <= max_delta:
            return (
                round(max(0.0, peer.score - 0.0001), 4),
                (
                    f"a small perturbation moves {baseline_item.market_name} just "
                    f"below nearest peer {peer.market_name}."
                ),
            )
        return (
            round(max(0.0, baseline_item.score - max_delta), 4),
            (
                f"a small perturbation moves {baseline_item.market_name} toward "
                f"nearest peer {peer.market_name} without crossing the peer."
            ),
        )
    if crossing_delta <= max_delta:
        return (
            round(min(1.0, peer.score + 0.0001), 4),
            (
                f"a small perturbation moves {baseline_item.market_name} just "
                f"above nearest peer {peer.market_name}."
            ),
        )
    return (
        round(min(1.0, baseline_item.score + max_delta), 4),
        (
            f"a small perturbation moves {baseline_item.market_name} toward "
            f"nearest peer {peer.market_name} without crossing the peer."
        ),
    )


def _ranking_item(
    items: tuple[ExplainableRankingItem, ...],
    market_key: str,
) -> ExplainableRankingItem:
    return next(item for item in items if item.market_key == market_key)


def _point(
    item: ExplainableRankingItem,
    top_market_key: str | None,
) -> RobustnessScenarioRankingResult:
    return RobustnessScenarioRankingResult(
        market_key=item.market_key,
        rank=item.rank,
        score=item.score,
        confidence=item.confidence,
        freshness=item.freshness,
        evidence_sufficiency=item.evidence_sufficiency,
        top_market_key=top_market_key,
    )


def _public_explanation(
    *,
    label: str,
    status: RankingStabilityStatus,
    baseline: RobustnessScenarioRankingResult,
    scenario: RobustnessScenarioRankingResult,
    rank_change: int,
    score_delta: float,
    confidence_delta: int,
    sufficiency_delta: str,
    winner_change: bool,
    applied: bool,
    reason: str,
) -> str:
    if not applied:
        return f"{label} is indeterminate for {baseline.market_key}: {reason}"
    winner_text = "winner changed" if winner_change else "winner unchanged"
    return (
        f"{label} is {status.value} for {baseline.market_key}: rank "
        f"{baseline.rank}->{scenario.rank} (change {rank_change}), score delta "
        f"{score_delta:+.4f}, confidence delta {confidence_delta:+d}, sufficiency "
        f"{sufficiency_delta}, {winner_text}. {reason}"
    )
