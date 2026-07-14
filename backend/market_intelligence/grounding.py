"""Public-safe evidence grounding for Layer 34C intelligence outputs."""

from __future__ import annotations

from collections.abc import Mapping

from backend.market_intelligence.goals import (
    career_goal_definition,
    classify_goal_evidence,
    public_evidence_label,
)
from backend.market_intelligence.schemas import (
    CareerGoal,
    EvidenceGrounding,
    EvidenceSufficiency,
    ExplainableRankingItem,
    IntelligenceConfidence,
    IntelligenceFreshness,
    RankingDriver,
    RankingStabilityStatus,
    RobustnessScenarioResult,
)


def build_profile_grounding(
    *,
    supporting_metrics: Mapping[str, object],
    confidence: IntelligenceConfidence,
    freshness: IntelligenceFreshness,
    coverage_summary: str,
    limitations: tuple[str, ...],
) -> EvidenceGrounding:
    """Ground a market profile without exposing source/provenance internals."""

    evidence_used = _profile_evidence_used(supporting_metrics)
    evidence_missing = _profile_evidence_missing(supporting_metrics)
    return EvidenceGrounding(
        evidence_areas_used=evidence_used,
        evidence_areas_missing=evidence_missing,
        direct_evidence_summary=_profile_direct_summary(supporting_metrics),
        proxy_evidence_summary=_profile_proxy_summary(supporting_metrics),
        freshness=freshness,
        coverage=coverage_summary or _coverage_summary(supporting_metrics),
        excluded_fact_summary=_excluded_fact_summary(supporting_metrics),
        confidence_constraints=_confidence_constraints(
            confidence=confidence,
            freshness=freshness,
            sufficiency=None,
            supporting_metrics=supporting_metrics,
            limitations=limitations,
        ),
        score_margin=None,
        stability_status=RankingStabilityStatus.INDETERMINATE,
    )


def build_ranking_grounding(
    *,
    goal: CareerGoal,
    ranking_drivers: tuple[RankingDriver, ...],
    supporting_metrics: Mapping[str, object],
    confidence: IntelligenceConfidence,
    freshness: IntelligenceFreshness,
    evidence_sufficiency: EvidenceSufficiency,
    limitations: tuple[str, ...],
    score_margin: float | None,
    stability_status: RankingStabilityStatus = RankingStabilityStatus.INDETERMINATE,
    stability_scenarios: tuple[RobustnessScenarioResult, ...] = (),
) -> EvidenceGrounding:
    """Ground a market-goal ranking item using only public-safe summaries."""

    classification = classify_goal_evidence(
        goal,
        (driver.code for driver in ranking_drivers),
    )
    direct_summary = _direct_evidence_summary(
        goal=goal,
        ranking_drivers=ranking_drivers,
        classification_direct=frozenset(classification.direct_evidence_categories),
    )
    proxy_summary = _proxy_evidence_summary(
        goal=goal,
        ranking_drivers=ranking_drivers,
        classification_proxy=frozenset(classification.proxy_evidence_categories),
        evidence_basis=classification.evidence_basis.value,
        direct_count=classification.direct_evidence_count,
        proxy_count=classification.proxy_evidence_count,
    )
    missing = tuple(
        public_evidence_label(goal, category)
        for category in classification.missing_direct_evidence_categories
    )
    return EvidenceGrounding(
        evidence_areas_used=tuple(
            sorted(
                {
                    *(
                        public_evidence_label(goal, category)
                        for category in classification.direct_evidence_categories
                    ),
                    *(
                        public_evidence_label(goal, category)
                        for category in classification.proxy_evidence_categories
                    ),
                }
            )
        )
        or ("No qualifying goal evidence in positive ranking drivers.",),
        evidence_areas_missing=_with_metric_gaps(missing, supporting_metrics),
        direct_evidence_summary=direct_summary,
        proxy_evidence_summary=proxy_summary,
        freshness=freshness,
        coverage=_coverage_summary(supporting_metrics),
        excluded_fact_summary=_excluded_fact_summary(supporting_metrics),
        confidence_constraints=_confidence_constraints(
            confidence=confidence,
            freshness=freshness,
            sufficiency=evidence_sufficiency,
            supporting_metrics=supporting_metrics,
            limitations=limitations,
        ),
        score_margin=score_margin,
        stability_status=stability_status,
        stability_scenarios=stability_scenarios,
    )


def score_margin_for_item(
    item: ExplainableRankingItem,
    ranking_items: tuple[ExplainableRankingItem, ...],
) -> float:
    peers = tuple(peer for peer in ranking_items if peer.market_key != item.market_key)
    if not peers:
        return 0.0
    return round(min(abs(item.score - peer.score) for peer in peers), 4)


def grounding_for_ranking_report(
    ranked_markets: tuple[ExplainableRankingItem, ...],
) -> EvidenceGrounding | None:
    if not ranked_markets:
        return None
    return ranked_markets[0].grounding


def grounding_for_comparison_side(
    item: ExplainableRankingItem,
) -> EvidenceGrounding:
    if item.grounding is not None:
        return item.grounding
    return build_ranking_grounding(
        goal=item.goal,
        ranking_drivers=item.ranking_drivers,
        supporting_metrics=item.supporting_metrics,
        confidence=item.confidence,
        freshness=item.freshness,
        evidence_sufficiency=item.evidence_sufficiency,
        limitations=item.limitations,
        score_margin=None,
    )


def build_comparison_grounding(
    *,
    left: ExplainableRankingItem,
    right: ExplainableRankingItem,
    confidence: IntelligenceConfidence,
    evidence_sufficiency: EvidenceSufficiency,
    limitations: tuple[str, ...],
    score_delta: float,
) -> EvidenceGrounding:
    left_grounding = grounding_for_comparison_side(left)
    right_grounding = grounding_for_comparison_side(right)
    return EvidenceGrounding(
        evidence_areas_used=_sorted_unique(
            (*left_grounding.evidence_areas_used, *right_grounding.evidence_areas_used)
        ),
        evidence_areas_missing=_sorted_unique(
            (
                *left_grounding.evidence_areas_missing,
                *right_grounding.evidence_areas_missing,
            )
        ),
        direct_evidence_summary=_prefixed_summary(left, left_grounding.direct_evidence_summary)
        + _prefixed_summary(right, right_grounding.direct_evidence_summary),
        proxy_evidence_summary=_prefixed_summary(left, left_grounding.proxy_evidence_summary)
        + _prefixed_summary(right, right_grounding.proxy_evidence_summary),
        freshness=_least_fresh(left_grounding.freshness, right_grounding.freshness),
        coverage=(
            f"{left.market_name}: {left_grounding.coverage} "
            f"{right.market_name}: {right_grounding.coverage}"
        ),
        excluded_fact_summary=(
            f"{left.market_name}: {left_grounding.excluded_fact_summary} "
            f"{right.market_name}: {right_grounding.excluded_fact_summary}"
        ),
        confidence_constraints=_sorted_unique(
            (
                f"Comparison confidence is {confidence.value}; sufficiency is "
                f"{evidence_sufficiency.value}.",
                *left_grounding.confidence_constraints,
                *right_grounding.confidence_constraints,
                *limitations[:2],
            )
        ),
        score_margin=score_delta,
        stability_status=_least_stable(
            left_grounding.stability_status,
            right_grounding.stability_status,
        ),
        stability_scenarios=_combined_stability_scenarios(
            left_grounding,
            right_grounding,
        ),
    )


def _profile_evidence_used(metrics: Mapping[str, object]) -> tuple[str, ...]:
    areas: list[str] = []
    if _metric(metrics, "employer_count") > 0:
        areas.append("Curated employer presence")
    if _known(metrics, "active_posting_total"):
        areas.append("Observed hiring activity")
    if _known(metrics, "internship_total"):
        areas.append("Observed internship evidence")
    if _known(metrics, "coop_total"):
        areas.append("Observed co-op evidence")
    if _metric(metrics, "formal_program_count") > 0:
        areas.append("Formal early-career programs")
    if _metric(metrics, "source_count") > 0:
        areas.append("Source freshness evidence")
    return tuple(areas) or ("No observed profile evidence is available.",)


def _profile_evidence_missing(metrics: Mapping[str, object]) -> tuple[str, ...]:
    missing: list[str] = []
    if not _known(metrics, "active_posting_total"):
        missing.append("Observed hiring activity")
    if not _known(metrics, "internship_total"):
        missing.append("Observed internship evidence")
    if not _known(metrics, "coop_total"):
        missing.append("Observed co-op evidence")
    return _with_metric_gaps(tuple(missing), metrics)


def _profile_direct_summary(metrics: Mapping[str, object]) -> tuple[str, ...]:
    return (
        f"Employer evidence: {_metric(metrics, 'employer_count')} curated employer(s).",
        (
            "Hiring evidence: "
            f"{_known_count(metrics, 'active_posting_total')} observed active posting(s)."
        ),
        (
            "Internship evidence: "
            f"{_known_count(metrics, 'internship_total')} observed internship count(s)."
        ),
        (
            "Early-career evidence: "
            f"{_metric(metrics, 'formal_program_count')} formal program signal(s)."
        ),
    )


def _profile_proxy_summary(metrics: Mapping[str, object]) -> tuple[str, ...]:
    return (
        (
            "Coverage proxy: "
            f"{_metric(metrics, 'ranking_eligible_fact_count')} ranking-eligible fact(s), "
            f"{_metric(metrics, 'high_gap_count')} high coverage gap(s), and "
            f"{_metric(metrics, 'medium_gap_count')} medium coverage gap(s)."
        ),
        (
            "Count semantics: "
            f"{_metric(metrics, 'unknown_fact_count')} unknown count fact(s); "
            f"{_metric(metrics, 'observed_zero_fact_count')} observed zero count fact(s)."
        ),
    )


def _direct_evidence_summary(
    *,
    goal: CareerGoal,
    ranking_drivers: tuple[RankingDriver, ...],
    classification_direct: frozenset[str],
) -> tuple[str, ...]:
    drivers = tuple(
        driver for driver in ranking_drivers if driver.code in classification_direct
    )
    if not drivers:
        label = career_goal_definition(goal).label
        return (
            f"No direct {label} evidence appears among positive ranking drivers.",
        )
    return tuple(
        f"{public_evidence_label(goal, driver.code)}: {driver.evidence}"
        for driver in drivers[:4]
    )


def _proxy_evidence_summary(
    *,
    goal: CareerGoal,
    ranking_drivers: tuple[RankingDriver, ...],
    classification_proxy: frozenset[str],
    evidence_basis: str,
    direct_count: int,
    proxy_count: int,
) -> tuple[str, ...]:
    drivers = tuple(
        driver for driver in ranking_drivers if driver.code in classification_proxy
    )
    summary = tuple(
        f"{public_evidence_label(goal, driver.code)}: {driver.evidence}"
        for driver in drivers[:4]
    ) or ("No proxy evidence appears among positive ranking drivers.",)
    return (
        *summary,
        (
            f"Evidence basis is {evidence_basis}; {direct_count} direct "
            f"categor{'y' if direct_count == 1 else 'ies'} and {proxy_count} "
            f"proxy categor{'y' if proxy_count == 1 else 'ies'}."
        ),
    )


def _confidence_constraints(
    *,
    confidence: IntelligenceConfidence,
    freshness: IntelligenceFreshness,
    sufficiency: EvidenceSufficiency | None,
    supporting_metrics: Mapping[str, object],
    limitations: tuple[str, ...],
) -> tuple[str, ...]:
    constraints: list[str] = [f"Confidence is {confidence.value}."]
    if sufficiency is None:
        constraints.append("No goal-specific sufficiency gate applies to the profile.")
    elif sufficiency is EvidenceSufficiency.COMPARISON_READY:
        constraints.append("No sufficiency confidence cap is applied.")
    elif sufficiency is EvidenceSufficiency.LIMITED_EVIDENCE:
        constraints.append("Confidence is constrained because evidence is limited.")
    elif sufficiency is EvidenceSufficiency.INSUFFICIENT_EVIDENCE:
        constraints.append("A firm recommendation is blocked by insufficient evidence.")
    else:
        constraints.append("A firm recommendation is blocked because the goal is not supported.")

    proxy_cap = supporting_metrics.get("proxy_only_confidence_cap")
    if isinstance(proxy_cap, str) and proxy_cap:
        constraints.append(f"Proxy-only confidence cap is {proxy_cap}.")
    if freshness is not IntelligenceFreshness.CURRENT:
        constraints.append(f"Freshness is {freshness.value}, which constrains confidence.")
    if _metric(supporting_metrics, "unknown_fact_count") > 0:
        constraints.append(
            "Unknown count facts constrain confidence and remain distinct from zero."
        )
    if _metric(supporting_metrics, "ranking_excluded_fact_count") > 0:
        constraints.append("Ranking-excluded facts are omitted from score influence.")
    if _metric(supporting_metrics, "high_gap_count") > 0:
        constraints.append("High coverage gaps constrain confidence.")
    constraints.extend(limitations[:2])
    return tuple(dict.fromkeys(constraints))


def _coverage_summary(metrics: Mapping[str, object]) -> str:
    return (
        f"{_metric(metrics, 'ranking_eligible_fact_count')} ranking-eligible fact(s); "
        f"{_metric(metrics, 'unknown_fact_count')} unknown count fact(s); "
        f"{_metric(metrics, 'observed_zero_fact_count')} observed zero count fact(s); "
        f"{_metric(metrics, 'high_gap_count')} high coverage gap(s); "
        f"{_metric(metrics, 'medium_gap_count')} medium coverage gap(s)."
    )


def _excluded_fact_summary(metrics: Mapping[str, object]) -> str:
    excluded = _metric(metrics, "ranking_excluded_fact_count")
    if excluded <= 0:
        return "No ranking-excluded facts are used in the score."
    return f"{excluded} ranking-excluded fact(s) are omitted from ranking influence."


def _with_metric_gaps(
    missing: tuple[str, ...],
    metrics: Mapping[str, object],
) -> tuple[str, ...]:
    result = list(missing)
    if _metric(metrics, "unknown_fact_count") > 0:
        result.append("Unknown count facts")
    if _metric(metrics, "ranking_excluded_fact_count") > 0:
        result.append("Ranking-excluded facts")
    if _metric(metrics, "high_gap_count") > 0:
        result.append("High-severity coverage gaps")
    return tuple(dict.fromkeys(result))


def _prefixed_summary(
    item: ExplainableRankingItem,
    values: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(f"{item.market_name}: {value}" for value in values)


def _least_fresh(
    left: IntelligenceFreshness,
    right: IntelligenceFreshness,
) -> IntelligenceFreshness:
    order = {
        IntelligenceFreshness.STALE: 4,
        IntelligenceFreshness.UNKNOWN: 3,
        IntelligenceFreshness.AGING: 2,
        IntelligenceFreshness.CURRENT: 1,
    }
    return left if order[left] >= order[right] else right


def _least_stable(
    left: RankingStabilityStatus,
    right: RankingStabilityStatus,
) -> RankingStabilityStatus:
    order = {
        RankingStabilityStatus.UNSTABLE: 4,
        RankingStabilityStatus.SENSITIVE: 3,
        RankingStabilityStatus.INDETERMINATE: 2,
        RankingStabilityStatus.STABLE: 1,
    }
    return left if order[left] >= order[right] else right


def _combined_stability_scenarios(
    left: EvidenceGrounding,
    right: EvidenceGrounding,
) -> tuple[RobustnessScenarioResult, ...]:
    scenarios = (*left.stability_scenarios, *right.stability_scenarios)
    by_key: dict[tuple[str, str, str], RobustnessScenarioResult] = {}
    for scenario in scenarios:
        key = (
            scenario.scenario.value,
            scenario.baseline_result.market_key,
            scenario.explanation,
        )
        by_key[key] = scenario
    order = {
        RankingStabilityStatus.UNSTABLE: 0,
        RankingStabilityStatus.SENSITIVE: 1,
        RankingStabilityStatus.INDETERMINATE: 2,
        RankingStabilityStatus.STABLE: 3,
    }
    return tuple(
        sorted(
            by_key.values(),
            key=lambda scenario: (
                order[scenario.status],
                scenario.scenario.value,
                scenario.baseline_result.market_key,
            ),
        )
    )


def _sorted_unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(dict.fromkeys(value for value in values if value)))


def _known(metrics: Mapping[str, object], key: str) -> bool:
    return metrics.get(key) is not None


def _known_count(metrics: Mapping[str, object], key: str) -> str:
    value = metrics.get(key)
    if value is None:
        return "unavailable"
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, int | float):
        return f"{value:g}"
    return str(value)


def _metric(metrics: Mapping[str, object], key: str) -> int:
    value = metrics.get(key)
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0
