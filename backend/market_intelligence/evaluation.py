"""Product-quality evaluation report aggregation for Layer 34C."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import replace

from backend.market_intelligence.explanations import (
    build_ranking_report_explanation,
    explanation_language_rejections,
)
from backend.market_intelligence.schemas import (
    CareerGoal,
    ContradictionStatus,
    DifferentiationFinding,
    DifferentiationSeverity,
    EvidenceBasis,
    EvidenceSufficiency,
    ExplainableRankingItem,
    ExplainableRankingReport,
    ExplanationQualityStatus,
    MarketCalibrationReport,
    MarketDifferentiationAudit,
    MarketGoalCalibrationResult,
    ProductQualityAbstention,
    ProductQualityContradictionSummary,
    ProductQualityDominantMetricSummary,
    ProductQualityEvaluationReport,
    ProductQualityEvidenceSummary,
    ProductQualityExplanationCheck,
    ProductQualityExplanationQuality,
    ProductQualityMarketGoalResult,
    ProductQualityPlatformSummary,
    ProductQualityResultReference,
    ProductQualityScoreClusterSummary,
    ProductQualityStabilitySummary,
    ProductQualityUnsupportedGoalSummary,
    RankingStabilityStatus,
)
from backend.market_intelligence.sufficiency import (
    sufficiency_allows_recommendation,
    sufficiency_requires_abstention,
)

PRODUCT_QUALITY_EVALUATION_REPORT_ARTIFACT_PATH = (
    "docs/implementation/layer_34c/artifacts/product_quality_evaluation_report.json"
)

SCHEMA_VERSION = "34C.11"
REPORT_TYPE = "layer_34c_product_quality_evaluation"
NEAR_TIE_CLUSTER_THRESHOLD = 0.01
SCORE_CLUSTER_SPREAD_THRESHOLD = 0.05
DOMINANT_METRIC_SHARE_THRESHOLD = 0.75
PRODUCT_QUALITY_DIFFERENTIATION_THRESHOLD = 0.80

_EXPLANATION_SECTION_LABELS = (
    "Ranking position:",
    "Direct evidence:",
    "Proxy evidence:",
    "Strongest comparative advantage:",
    "Strongest comparative weakness:",
    "Missing evidence:",
    "Confidence limitation:",
    "Stability limitation:",
)


def build_product_quality_evaluation_report(
    *,
    calibration_report: MarketCalibrationReport,
    differentiation_audit: MarketDifferentiationAudit,
    rankings: Mapping[CareerGoal, ExplainableRankingReport],
    artifact_path: str = PRODUCT_QUALITY_EVALUATION_REPORT_ARTIFACT_PATH,
) -> ProductQualityEvaluationReport:
    """Compose the public-safe report used by the final Layer 34C audit."""

    ranking_lookup = _ranking_lookup(rankings)
    all_differentiation_findings = _differentiation_findings(differentiation_audit)
    results = tuple(
        _result_from_calibration(
            calibration,
            ranking=rankings.get(goal),
            ranking_item=ranking_lookup.get((goal, market_key)),
            differentiation_findings=_findings_for_result(
                all_differentiation_findings,
                goal=goal,
                market_key=market_key,
            ),
        )
        for goal, market_key, calibration in _ordered_calibration_results(
            calibration_report
        )
    )

    differentiation_passed = (
        differentiation_audit.differentiation_score
        >= PRODUCT_QUALITY_DIFFERENTIATION_THRESHOLD
        and not _has_unresolved_differentiation_failure(results)
    )
    return ProductQualityEvaluationReport(
        schema_version=SCHEMA_VERSION,
        report_type=REPORT_TYPE,
        artifact_path=artifact_path,
        as_of=calibration_report.as_of,
        markets=calibration_report.markets,
        goals=calibration_report.goals,
        expected_result_count=len(calibration_report.markets)
        * len(calibration_report.goals),
        result_count=len(results),
        results=results,
        platform_summary=_platform_summary(
            results,
            differentiation_audit=differentiation_audit,
        ),
        calibration_limitations=calibration_report.limitations,
        differentiation_score=differentiation_audit.differentiation_score,
        differentiation_threshold=PRODUCT_QUALITY_DIFFERENTIATION_THRESHOLD,
        differentiation_passed=differentiation_passed,
        differentiation_notes=differentiation_audit.true_similarity_notes,
    )


def _ordered_calibration_results(
    calibration_report: MarketCalibrationReport,
) -> tuple[tuple[CareerGoal, str, MarketGoalCalibrationResult], ...]:
    ordered: list[tuple[CareerGoal, str, MarketGoalCalibrationResult]] = []
    for goal_key in sorted(calibration_report.market_goal_matrix):
        goal = CareerGoal(goal_key)
        by_market = calibration_report.market_goal_matrix[goal_key]
        for market_key in sorted(by_market):
            ordered.append((goal, market_key, by_market[market_key]))
    return tuple(ordered)


def _ranking_lookup(
    rankings: Mapping[CareerGoal, ExplainableRankingReport],
) -> dict[tuple[CareerGoal, str], ExplainableRankingItem]:
    return {
        (goal, item.market_key): item
        for goal, ranking in sorted(rankings.items(), key=lambda entry: entry[0].value)
        for item in ranking.ranked_markets
    }


def _result_from_calibration(
    calibration: MarketGoalCalibrationResult,
    *,
    ranking: ExplainableRankingReport | None,
    ranking_item: ExplainableRankingItem | None,
    differentiation_findings: tuple[DifferentiationFinding, ...],
) -> ProductQualityMarketGoalResult:
    abstention = _abstention(calibration, ranking_item=ranking_item)
    reportable_differentiation = _reportable_differentiation_findings(
        differentiation_findings,
        abstention=abstention,
    )
    return ProductQualityMarketGoalResult(
        market_key=calibration.market_key,
        market_name=calibration.market_name,
        goal=calibration.goal,
        rank=calibration.rank,
        score=calibration.score,
        score_margin=calibration.score_margin,
        confidence=calibration.confidence,
        freshness=calibration.freshness,
        sufficiency=calibration.evidence_sufficiency,
        direct_proxy_evidence=_direct_proxy_evidence(
            calibration,
            ranking_item=ranking_item,
        ),
        top_drivers=calibration.top_drivers,
        limitations=calibration.limitations,
        stability=_stability(calibration),
        contradictions=calibration.contradictions,
        abstention=abstention,
        explanation_quality_status=_explanation_quality(
            calibration,
            ranking=ranking,
            ranking_item=ranking_item,
        ),
        differentiation_findings=reportable_differentiation,
    )


def _direct_proxy_evidence(
    calibration: MarketGoalCalibrationResult,
    *,
    ranking_item: ExplainableRankingItem | None,
) -> ProductQualityEvidenceSummary:
    metrics = ranking_item.supporting_metrics if ranking_item else {}
    return ProductQualityEvidenceSummary(
        evidence_basis=(
            ranking_item.evidence_basis
            if ranking_item
            else EvidenceBasis.NO_QUALIFYING_EVIDENCE
        ),
        direct_evidence_count=_metric(metrics, "direct_evidence_count"),
        proxy_evidence_count=_metric(metrics, "proxy_evidence_count"),
        direct_evidence_summary=calibration.direct_evidence_summary,
        proxy_evidence_summary=calibration.proxy_evidence_summary,
    )


def _stability(
    calibration: MarketGoalCalibrationResult,
) -> ProductQualityStabilitySummary:
    unstable = tuple(
        scenario.scenario
        for scenario in calibration.stability_scenarios
        if scenario.status is RankingStabilityStatus.UNSTABLE
    )
    sensitive = tuple(
        scenario.scenario
        for scenario in calibration.stability_scenarios
        if scenario.status is RankingStabilityStatus.SENSITIVE
    )
    return ProductQualityStabilitySummary(
        status=calibration.stability_status,
        scenario_count=len(calibration.stability_scenarios),
        unstable_scenarios=tuple(sorted(unstable, key=lambda item: item.value)),
        sensitive_scenarios=tuple(sorted(sensitive, key=lambda item: item.value)),
    )


def _abstention(
    calibration: MarketGoalCalibrationResult,
    *,
    ranking_item: ExplainableRankingItem | None,
) -> ProductQualityAbstention:
    abstains = sufficiency_requires_abstention(calibration.evidence_sufficiency)
    reason = ranking_item.abstention_reason if ranking_item else None
    if abstains and reason is None:
        reason = (
            "evidence sufficiency is "
            f"{calibration.evidence_sufficiency.value}; no firm recommendation is made"
        )
    return ProductQualityAbstention(
        abstains=abstains,
        is_provisional=bool(
            ranking_item and ranking_item.is_provisional
            or calibration.evidence_sufficiency is EvidenceSufficiency.LIMITED_EVIDENCE
        ),
        reason=reason,
    )


def _explanation_quality(
    calibration: MarketGoalCalibrationResult,
    *,
    ranking: ExplainableRankingReport | None,
    ranking_item: ExplainableRankingItem | None,
) -> ProductQualityExplanationQuality:
    if ranking is None or ranking_item is None:
        checks = (
            ProductQualityExplanationCheck(
                code="explanation_available",
                passed=False,
                message="No ranking explanation is available for this market-goal result.",
            ),
        )
        return ProductQualityExplanationQuality(
            status=ExplanationQualityStatus.NEEDS_IMPROVEMENT,
            rejection_codes=(),
            checks=checks,
        )

    stable_item = replace(
        ranking_item,
        limitations=calibration.limitations,
        grounding=calibration.grounding or ranking_item.grounding,
    )
    stable_ranked_markets = tuple(
        stable_item if item.market_key == stable_item.market_key else item
        for item in ranking.ranked_markets
    )
    explanation = build_ranking_report_explanation(
        stable_item,
        stable_ranked_markets,
        ranking.goal_definition,
    )
    rejection_codes = explanation_language_rejections(explanation)
    checks = [
        ProductQualityExplanationCheck(
            code=f"section_{_section_code(label)}",
            passed=label in explanation,
            message=f"Explanation includes {label.rstrip(':').casefold()} section.",
        )
        for label in _EXPLANATION_SECTION_LABELS
    ]
    checks.extend(
        (
            _top_driver_check(ranking_item, explanation),
            _confidence_alignment_check(ranking_item, explanation),
            _sufficiency_alignment_check(ranking_item, explanation),
            _stability_alignment_check(calibration.stability_status, explanation),
            ProductQualityExplanationCheck(
                code="freshness_available",
                passed=True,
                message=(
                    "Freshness is carried in the market-goal result for explanation "
                    "alignment."
                ),
            ),
            ProductQualityExplanationCheck(
                code="public_language",
                passed=not rejection_codes,
                message=(
                    "Explanation avoids unsupported generic or stereotype language."
                ),
            ),
        )
    )
    status = (
        ExplanationQualityStatus.PASSED
        if all(check.passed for check in checks)
        else ExplanationQualityStatus.NEEDS_IMPROVEMENT
    )
    return ProductQualityExplanationQuality(
        status=status,
        rejection_codes=tuple(rejection_codes),
        checks=tuple(checks),
    )


def _top_driver_check(
    ranking_item: ExplainableRankingItem,
    explanation: str,
) -> ProductQualityExplanationCheck:
    if not ranking_item.ranking_drivers:
        return ProductQualityExplanationCheck(
            code="top_driver_alignment",
            passed=True,
            message="No positive ranking driver is available to align.",
        )
    top_driver = ranking_item.ranking_drivers[0]
    return ProductQualityExplanationCheck(
        code="top_driver_alignment",
        passed=top_driver.label in explanation,
        message="Explanation names the top score driver for this result.",
    )


def _confidence_alignment_check(
    ranking_item: ExplainableRankingItem,
    explanation: str,
) -> ProductQualityExplanationCheck:
    expected = f"confidence is {ranking_item.confidence.value}"
    return ProductQualityExplanationCheck(
        code="confidence_alignment",
        passed=expected in explanation,
        message="Explanation states the backend confidence label.",
    )


def _sufficiency_alignment_check(
    ranking_item: ExplainableRankingItem,
    explanation: str,
) -> ProductQualityExplanationCheck:
    normalized = explanation.casefold()
    if sufficiency_requires_abstention(ranking_item.evidence_sufficiency):
        return ProductQualityExplanationCheck(
            code="sufficiency_alignment",
            passed="abstain" in normalized or "blocked" in normalized,
            message="Explanation makes abstention visible for abstention-level evidence.",
        )
    if ranking_item.evidence_sufficiency is EvidenceSufficiency.LIMITED_EVIDENCE:
        return ProductQualityExplanationCheck(
            code="sufficiency_alignment",
            passed="provisional" in normalized or "limited_evidence" in normalized,
            message="Explanation makes limited evidence visible.",
        )
    return ProductQualityExplanationCheck(
        code="sufficiency_alignment",
        passed=ranking_item.evidence_sufficiency.value in normalized
        or "no sufficiency cap" in normalized,
        message="Explanation aligns with comparison-ready sufficiency.",
    )


def _stability_alignment_check(
    stability_status: RankingStabilityStatus,
    explanation: str,
) -> ProductQualityExplanationCheck:
    normalized = explanation.casefold()
    expected = stability_status.value
    if stability_status in {
        RankingStabilityStatus.UNSTABLE,
        RankingStabilityStatus.SENSITIVE,
    }:
        passed = expected in normalized and "scenario" in normalized
    elif stability_status is RankingStabilityStatus.STABLE:
        passed = "stable" in normalized and "scenario" in normalized
    else:
        passed = "indeterminate" in normalized
    return ProductQualityExplanationCheck(
        code="stability_alignment",
        passed=passed,
        message="Explanation states the evaluated backend stability classification.",
    )


def _platform_summary(
    results: tuple[ProductQualityMarketGoalResult, ...],
    *,
    differentiation_audit: MarketDifferentiationAudit,
) -> ProductQualityPlatformSummary:
    return ProductQualityPlatformSummary(
        cross_goal_ranking_similarity=_substantive_cross_goal_correlations(
            differentiation_audit.cross_goal_rank_correlation_summary,
            results=results,
        ),
        score_clustering=_score_clustering(results),
        dominant_metrics=_dominant_metrics(results),
        unsupported_goals=_unsupported_goals(results),
        provisional_results=_result_references(
            results,
            predicate=lambda result: result.abstention.is_provisional,
        ),
        abstentions=_result_references(
            results,
            predicate=lambda result: result.abstention.abstains,
        ),
        unstable_results=_result_references(
            results,
            predicate=lambda result: result.stability.status
            is RankingStabilityStatus.UNSTABLE,
        ),
        contradictions=_contradiction_summaries(results),
    )


def _reportable_differentiation_findings(
    findings: tuple[DifferentiationFinding, ...],
    *,
    abstention: ProductQualityAbstention,
) -> tuple[DifferentiationFinding, ...]:
    if abstention.abstains:
        return ()
    return findings


def _has_unresolved_differentiation_failure(
    results: tuple[ProductQualityMarketGoalResult, ...],
) -> bool:
    return any(
        finding.severity is DifferentiationSeverity.NEEDS_IMPROVEMENT
        for result in results
        for finding in result.differentiation_findings
    )


def _substantive_cross_goal_correlations(
    correlations,
    *,
    results: tuple[ProductQualityMarketGoalResult, ...],
):
    substantive_goals = {
        result.goal
        for result in results
        if sufficiency_allows_recommendation(result.sufficiency)
        and not result.abstention.abstains
    }
    return tuple(
        correlation
        for correlation in correlations
        if correlation.goal_a in substantive_goals
        and correlation.goal_b in substantive_goals
    )


def _score_clustering(
    results: tuple[ProductQualityMarketGoalResult, ...],
) -> tuple[ProductQualityScoreClusterSummary, ...]:
    summaries: list[ProductQualityScoreClusterSummary] = []
    for goal in sorted({result.goal for result in results}, key=lambda item: item.value):
        goal_results = tuple(
            sorted(
                (result for result in results if result.goal is goal),
                key=lambda item: item.score,
            )
        )
        if not goal_results:
            continue
        scores = tuple(result.score for result in goal_results)
        adjacent_gaps = tuple(
            round(scores[index + 1] - scores[index], 4)
            for index in range(len(scores) - 1)
        )
        score_spread = round(max(scores) - min(scores), 4)
        near_tie_count = sum(
            1 for gap in adjacent_gaps if gap <= NEAR_TIE_CLUSTER_THRESHOLD
        )
        if len(goal_results) <= 1:
            status = "single_result"
        elif score_spread <= SCORE_CLUSTER_SPREAD_THRESHOLD:
            status = "clustered"
        else:
            status = "not_clustered"
        summaries.append(
            ProductQualityScoreClusterSummary(
                goal=goal,
                market_count=len(goal_results),
                min_score=round(min(scores), 4),
                max_score=round(max(scores), 4),
                score_spread=score_spread,
                minimum_pairwise_gap=min(adjacent_gaps) if adjacent_gaps else None,
                near_tie_pair_count=near_tie_count,
                status=status,
            )
        )
    return tuple(summaries)


def _dominant_metrics(
    results: tuple[ProductQualityMarketGoalResult, ...],
) -> tuple[ProductQualityDominantMetricSummary, ...]:
    summaries: list[ProductQualityDominantMetricSummary] = []
    for goal in sorted({result.goal for result in results}, key=lambda item: item.value):
        goal_results = tuple(result for result in results if result.goal is goal)
        appearances: Counter[str] = Counter()
        labels: dict[str, str] = {}
        for result in goal_results:
            driver_codes = {driver.code for driver in result.top_drivers}
            for driver in result.top_drivers:
                labels.setdefault(driver.code, driver.label)
            appearances.update(driver_codes)
        for code, count in sorted(
            appearances.items(),
            key=lambda item: (-item[1], item[0]),
        ):
            share = round(count / len(goal_results), 4) if goal_results else 0.0
            summaries.append(
                ProductQualityDominantMetricSummary(
                    goal=goal,
                    metric_code=code,
                    label=labels.get(code, code.replace("_", " ")),
                    market_count=count,
                    share=share,
                    dominant=share >= DOMINANT_METRIC_SHARE_THRESHOLD,
                )
            )
    return tuple(summaries)


def _unsupported_goals(
    results: tuple[ProductQualityMarketGoalResult, ...],
) -> tuple[ProductQualityUnsupportedGoalSummary, ...]:
    summaries: list[ProductQualityUnsupportedGoalSummary] = []
    for goal in sorted({result.goal for result in results}, key=lambda item: item.value):
        unsupported = tuple(
            result
            for result in results
            if result.goal is goal
            and result.sufficiency is EvidenceSufficiency.NOT_SUPPORTED
        )
        if unsupported:
            summaries.append(
                ProductQualityUnsupportedGoalSummary(
                    goal=goal,
                    result_count=len(unsupported),
                    reason="One or more results are not_supported by the current data model.",
                )
            )
    return tuple(summaries)


def _result_references(
    results: tuple[ProductQualityMarketGoalResult, ...],
    *,
    predicate,
) -> tuple[ProductQualityResultReference, ...]:
    return tuple(
        ProductQualityResultReference(
            goal=result.goal,
            market_key=result.market_key,
            rank=result.rank,
            status=_reference_status(result),
            reason=result.abstention.reason,
        )
        for result in sorted(results, key=lambda item: (item.goal.value, item.market_key))
        if predicate(result)
    )


def _reference_status(result: ProductQualityMarketGoalResult) -> str:
    if result.abstention.abstains:
        return result.sufficiency.value
    if result.abstention.is_provisional:
        return "provisional"
    return result.stability.status.value


def _contradiction_summaries(
    results: tuple[ProductQualityMarketGoalResult, ...],
) -> tuple[ProductQualityContradictionSummary, ...]:
    summaries: list[ProductQualityContradictionSummary] = []
    for result in sorted(results, key=lambda item: (item.goal.value, item.market_key)):
        if not result.contradictions:
            continue
        summaries.append(
            ProductQualityContradictionSummary(
                goal=result.goal,
                market_key=result.market_key,
                status=ContradictionStatus.BLOCKING
                if any(finding.blocks_recommendation for finding in result.contradictions)
                else ContradictionStatus.WARNINGS,
                codes=tuple(finding.code for finding in result.contradictions),
                blocks_recommendation=any(
                    finding.blocks_recommendation
                    for finding in result.contradictions
                ),
            )
        )
    return tuple(summaries)


def _differentiation_findings(
    audit: MarketDifferentiationAudit,
) -> tuple[DifferentiationFinding, ...]:
    return tuple(
        sorted(
            (
                *audit.duplicated_language_findings,
                *audit.repeated_driver_findings,
            ),
            key=lambda finding: (
                finding.code.value,
                finding.field,
                finding.market_keys,
                tuple(goal.value for goal in finding.goal_keys),
                finding.evidence,
            ),
        )
    )


def _findings_for_result(
    findings: tuple[DifferentiationFinding, ...],
    *,
    goal: CareerGoal,
    market_key: str,
) -> tuple[DifferentiationFinding, ...]:
    return tuple(
        finding
        for finding in findings
        if (not finding.market_keys or market_key in finding.market_keys)
        and (not finding.goal_keys or goal in finding.goal_keys)
    )


def _section_code(label: str) -> str:
    return label.rstrip(":").casefold().replace(" ", "_")


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
