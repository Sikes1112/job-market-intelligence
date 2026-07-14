"""Internal calibration report composition for Layer 34C."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import date, datetime

from backend.market_intelligence.contradictions import (
    contradiction_limitation,
    evaluate_ranking_item_contradictions,
)
from backend.market_intelligence.goals import (
    classify_goal_evidence,
    public_evidence_label,
)
from backend.market_intelligence.grounding import build_ranking_grounding
from backend.market_intelligence.schemas import (
    CalibrationTieStatus,
    CareerGoal,
    CareerGoalDefinition,
    ExplainableRankingItem,
    ExplainableRankingReport,
    GoalEvidenceClassification,
    MarketCalibrationReport,
    MarketGoalCalibrationResult,
    MarketGoalStabilityAnalysis,
    RankingStabilityStatus,
)

NEAR_TIE_THRESHOLD = 0.01


def build_calibration_report(
    *,
    rankings: Mapping[CareerGoal, ExplainableRankingReport],
    stability_by_goal_market: Mapping[
        CareerGoal, Mapping[str, MarketGoalStabilityAnalysis]
    ]
    | None = None,
    as_of: date | datetime | None = None,
) -> MarketCalibrationReport:
    """Build a deterministic, public-safe matrix over precomputed rankings."""

    goals = tuple(goal for goal in CareerGoal if goal in rankings)
    markets = tuple(
        sorted(
            {
                item.market_key
                for goal in goals
                for item in rankings[goal].ranked_markets
            }
        )
    )
    matrix: dict[str, dict[str, MarketGoalCalibrationResult]] = {}
    report_limitations: set[str] = set()
    tie_breakers: set[str] = set()

    for goal in goals:
        ranking = rankings[goal]
        tie_breakers.add(ranking.tie_breaker)
        report_limitations.update(ranking.limitations)
        stability_lookup = (
            stability_by_goal_market.get(goal, {}) if stability_by_goal_market else {}
        )
        by_market: dict[str, MarketGoalCalibrationResult] = {}
        for item in sorted(ranking.ranked_markets, key=lambda ranked: ranked.market_key):
            result = _calibration_result(
                item,
                ranking_items=ranking.ranked_markets,
                top_market_key=ranking.top_market_key,
                tie_breaker=ranking.tie_breaker,
                explanation=ranking.explanation,
                goal_definition=ranking.goal_definition,
                goal_limitations=ranking.goal_definition.limitations,
                stability=stability_lookup.get(item.market_key),
            )
            by_market[item.market_key] = result
            report_limitations.update(result.limitations)
        matrix[goal.value] = by_market

    return MarketCalibrationReport(
        as_of=_as_of_label(as_of),
        markets=markets,
        goals=goals,
        market_goal_matrix=matrix,
        result_count=sum(len(by_market) for by_market in matrix.values()),
        near_tie_threshold=NEAR_TIE_THRESHOLD,
        tie_breaker=_tie_breaker_summary(tie_breakers),
        limitations=tuple(sorted(report_limitations)),
    )


def _calibration_result(
    item: ExplainableRankingItem,
    *,
    ranking_items: tuple[ExplainableRankingItem, ...],
    top_market_key: str | None,
    tie_breaker: str,
    explanation: str,
    goal_definition: CareerGoalDefinition,
    goal_limitations: tuple[str, ...],
    stability: MarketGoalStabilityAnalysis | None,
) -> MarketGoalCalibrationResult:
    tied = _tied_market_keys(item, ranking_items)
    near_ties = _near_tie_market_keys(item, ranking_items)
    stability_status = (
        stability.status if stability else RankingStabilityStatus.INDETERMINATE
    )
    contradiction_analysis = evaluate_ranking_item_contradictions(
        item,
        ranking_items=ranking_items,
        top_market_key=top_market_key,
        tie_breaker=tie_breaker,
        explanation=explanation,
    )
    contradiction_note = contradiction_limitation(contradiction_analysis)
    limitations = tuple(
        sorted(
            {
                *item.limitations,
                *goal_limitations,
                *_stability_limitations(
                    stability_status,
                    evaluated=stability is not None,
                ),
                *((contradiction_note,) if contradiction_note else ()),
            }
        )
    )
    classification = classify_goal_evidence(
        item.goal,
        (driver.code for driver in item.ranking_drivers),
    )
    score_margin = _score_margin(item, ranking_items)
    direct_evidence_summary = _direct_evidence_summary(
        item,
        goal_definition=goal_definition,
        classification=classification,
    )
    proxy_evidence_summary = _proxy_evidence_summary(
        item,
        classification=classification,
    )
    grounding = replace(
        item.grounding
        or build_ranking_grounding(
            goal=item.goal,
            ranking_drivers=item.ranking_drivers,
            supporting_metrics=item.supporting_metrics,
            confidence=item.confidence,
            freshness=item.freshness,
            evidence_sufficiency=item.evidence_sufficiency,
            limitations=limitations,
            score_margin=score_margin,
        ),
        direct_evidence_summary=direct_evidence_summary,
        proxy_evidence_summary=proxy_evidence_summary,
        score_margin=score_margin,
        stability_status=stability_status,
        stability_scenarios=stability.scenarios if stability else (),
    )
    return MarketGoalCalibrationResult(
        market_key=item.market_key,
        market_name=item.market_name,
        goal=item.goal,
        score=item.score,
        rank=item.rank,
        score_margin=score_margin,
        confidence=item.confidence,
        freshness=item.freshness,
        evidence_sufficiency=item.evidence_sufficiency,
        direct_evidence_summary=direct_evidence_summary,
        proxy_evidence_summary=proxy_evidence_summary,
        top_drivers=item.ranking_drivers[:4],
        limitations=limitations,
        tie_status=_tie_status(tied, near_ties),
        tied_market_keys=tied,
        near_tie_market_keys=near_ties,
        stability_status=stability_status,
        stability_scenarios=stability.scenarios if stability else (),
        contradiction_status=contradiction_analysis.status,
        contradictions=contradiction_analysis.findings,
        grounding=grounding,
    )


def _score_margin(
    item: ExplainableRankingItem,
    ranking_items: tuple[ExplainableRankingItem, ...],
) -> float:
    deltas = [
        _score_delta(item, other)
        for other in ranking_items
        if other.market_key != item.market_key
    ]
    return round(min(deltas), 4) if deltas else 0.0


def _tied_market_keys(
    item: ExplainableRankingItem,
    ranking_items: tuple[ExplainableRankingItem, ...],
) -> tuple[str, ...]:
    return tuple(
        sorted(
            other.market_key
            for other in ranking_items
            if other.market_key != item.market_key and _score_delta(item, other) == 0.0
        )
    )


def _near_tie_market_keys(
    item: ExplainableRankingItem,
    ranking_items: tuple[ExplainableRankingItem, ...],
) -> tuple[str, ...]:
    return tuple(
        sorted(
            other.market_key
            for other in ranking_items
            if other.market_key != item.market_key
            and 0.0 < _score_delta(item, other) <= NEAR_TIE_THRESHOLD
        )
    )


def _tie_status(
    tied_market_keys: tuple[str, ...],
    near_tie_market_keys: tuple[str, ...],
) -> CalibrationTieStatus:
    if tied_market_keys:
        return CalibrationTieStatus.TIE
    if near_tie_market_keys:
        return CalibrationTieStatus.NEAR_TIE
    return CalibrationTieStatus.CLEAR


def _score_delta(left: ExplainableRankingItem, right: ExplainableRankingItem) -> float:
    return round(abs(left.score - right.score), 4)


def _direct_evidence_summary(
    item: ExplainableRankingItem,
    *,
    goal_definition: CareerGoalDefinition,
    classification: GoalEvidenceClassification,
) -> tuple[str, ...]:
    direct_codes = frozenset(classification.direct_evidence_categories)
    direct_drivers = tuple(
        driver for driver in item.ranking_drivers if driver.code in direct_codes
    )
    if not direct_drivers:
        missing = ", ".join(
            public_evidence_label(item.goal, category)
            for category in classification.missing_direct_evidence_categories[:3]
        )
        if missing:
            return (
                f"No direct {goal_definition.label} evidence is available in "
                f"positive ranking drivers; missing {missing}.",
            )
        return (
            f"No direct {goal_definition.label} evidence is available in "
            "positive ranking drivers.",
        )
    if not item.ranking_drivers:
        return ("No positive ranking driver is available from current canonical facts.",)
    return tuple(
        f"{public_evidence_label(item.goal, driver.code)}: {driver.evidence}"
        for driver in direct_drivers[:4]
    )


def _proxy_evidence_summary(
    item: ExplainableRankingItem,
    *,
    classification: GoalEvidenceClassification,
) -> tuple[str, ...]:
    metrics = item.supporting_metrics
    proxy_codes = frozenset(classification.proxy_evidence_categories)
    proxy_drivers = tuple(
        driver for driver in item.ranking_drivers if driver.code in proxy_codes
    )
    proxy_summary = tuple(
        f"{public_evidence_label(item.goal, driver.code)}: {driver.evidence}"
        for driver in proxy_drivers[:4]
    ) or ("No proxy evidence appears among positive ranking drivers.",)
    return (
        *proxy_summary,
        (
            f"Evidence basis is {classification.evidence_basis.value}; "
            f"{classification.direct_evidence_count} direct categor"
            f"{'y' if classification.direct_evidence_count == 1 else 'ies'} and "
            f"{classification.proxy_evidence_count} proxy categor"
            f"{'y' if classification.proxy_evidence_count == 1 else 'ies'}."
        ),
        f"Confidence is {item.confidence.value}; freshness is {item.freshness.value}.",
        (
            "Ranking facts: "
            f"{_metric(metrics, 'ranking_eligible_fact_count')} eligible; "
            f"{_metric(metrics, 'ranking_excluded_fact_count')} excluded."
        ),
        (
            "Count semantics: "
            f"{_metric(metrics, 'unknown_fact_count')} unknown count fact(s); "
            f"{_metric(metrics, 'observed_zero_fact_count')} observed zero count fact(s)."
        ),
    )


def _metric(
    metrics: Mapping[str, int | float | str | None],
    key: str,
) -> int:
    value = metrics.get(key)
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


def _as_of_label(value: date | datetime | None) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return None


def _tie_breaker_summary(tie_breakers: set[str]) -> str:
    if not tie_breakers:
        return "No ranked markets are available."
    if len(tie_breakers) == 1:
        return next(iter(tie_breakers))
    return " | ".join(sorted(tie_breakers))


def _stability_limitations(
    status: RankingStabilityStatus,
    *,
    evaluated: bool,
) -> tuple[str, ...]:
    if not evaluated:
        return ("Sensitivity analysis has not been evaluated for this result.",)
    if status is RankingStabilityStatus.UNSTABLE:
        return (
            "Sensitivity analysis found unstable ranking behavior; use scenario "
            "details before treating this rank as durable.",
        )
    if status is RankingStabilityStatus.SENSITIVE:
        return (
            "Sensitivity analysis found ranking-sensitive behavior; treat this "
            "position as provisional.",
        )
    if status is RankingStabilityStatus.INDETERMINATE:
        return (
            "Sensitivity analysis could not determine stability for every required scenario.",
        )
    return ()
