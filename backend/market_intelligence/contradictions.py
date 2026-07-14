"""Public-safe contradiction detection for Layer 34C intelligence outputs."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import replace

from backend.market_intelligence.goals import (
    career_goal_definition,
    classify_goal_evidence,
)
from backend.market_intelligence.schemas import (
    CareerGoal,
    ComparisonOutcome,
    ContradictionAnalysis,
    ContradictionCode,
    ContradictionFinding,
    ContradictionSeverity,
    ContradictionStatus,
    EvidenceBasis,
    EvidenceSufficiency,
    ExplainableRankingItem,
    ExplainableRankingReport,
    IntelligenceConfidence,
    IntelligenceFreshness,
    MarketComparisonReport,
    RankingDriver,
)

_BLOCKING_SUFFICIENCY = {
    EvidenceSufficiency.INSUFFICIENT_EVIDENCE,
    EvidenceSufficiency.NOT_SUPPORTED,
}

_NEGATIVE_TERMS = (
    "absent",
    "lack",
    "lacks",
    "limited",
    "low",
    "missing",
    "no ",
    "unavailable",
    "weak",
)

_STRONG_INTERNSHIP_PATTERNS = (
    "deep internship",
    "many internship",
    "robust internship",
    "strong internship",
    "substantial internship",
    "internship access is strong",
    "internship ecosystem is strong",
)

_DRIVER_KEYWORDS = {
    "ai_cloud_activity": ("ai", "cloud"),
    "ai_cloud_employers": ("ai", "cloud"),
    "cybersecurity_activity": ("cybersecurity", "security"),
    "cybersecurity_employers": ("cybersecurity", "security"),
    "early_career": ("early-career", "entry-level", "pathway"),
    "employer_presence": ("employer",),
    "formal_programs": ("program", "rotational"),
    "hiring_activity": ("hiring", "posting"),
    "internship": ("internship",),
    "product_activity": ("product",),
    "tech_signal": ("tech", "technical", "technology"),
}


def evaluate_ranking_item_contradictions(
    item: ExplainableRankingItem,
    *,
    ranking_items: tuple[ExplainableRankingItem, ...] = (),
    top_market_key: str | None = None,
    tie_breaker: str = "",
    explanation: str = "",
) -> ContradictionAnalysis:
    findings: list[ContradictionFinding] = [*item.contradictions]

    if (
        item.confidence is IntelligenceConfidence.HIGH
        and item.evidence_sufficiency in _BLOCKING_SUFFICIENCY
    ):
        findings.append(
            _finding(
                ContradictionCode.HIGH_CONFIDENCE_INSUFFICIENT_EVIDENCE,
                "High confidence is inconsistent with an abstention-level evidence state.",
                (
                    f"{item.market_name} has confidence {item.confidence.value} and "
                    f"evidence sufficiency {item.evidence_sufficiency.value}."
                ),
            )
        )

    if _has_strong_internship_claim((*item.strengths, explanation)) and (
        _missing_internship_evidence(item)
    ):
        findings.append(
            _finding(
                ContradictionCode.STRONG_INTERNSHIP_MISSING_EVIDENCE,
                "A strong internship claim is not supported by internship evidence.",
                (
                    f"{item.market_name} includes strong internship language, but "
                    "internship evidence is missing or unavailable."
                ),
            )
        )

    if (
        item.freshness is IntelligenceFreshness.CURRENT
        and _metric(item.supporting_metrics, "stale_source_count")
        + _metric(item.supporting_metrics, "expired_source_count")
        > 0
    ):
        findings.append(
            _finding(
                ContradictionCode.CURRENT_FRESHNESS_STALE_PRIMARY_SOURCE,
                "Current freshness conflicts with stale or expired source evidence.",
                (
                    f"{item.market_name} is marked current while stale or expired "
                    "source counts are present."
                ),
            )
        )

    opposite = _opposite_weakness_and_driver(item)
    if opposite:
        findings.append(
            _finding(
                ContradictionCode.OPPOSITE_WEAKNESS_AND_DRIVER,
                "A positive driver and weakness make opposite claims about the same evidence area.",
                opposite,
            )
        )

    if _specific_role_recommendation_without_direct_evidence(
        item,
        top_market_key=top_market_key,
        explanation=explanation,
    ):
        findings.append(
            _finding(
                ContradictionCode.SPECIFIC_ROLE_RECOMMENDATION_WITHOUT_DIRECT_EVIDENCE,
                "A role-specific recommendation is not backed by direct role evidence.",
                (
                    f"{item.market_name} is presented as a specific {item.goal.value} "
                    "recommendation without direct evidence for that goal."
                ),
            )
        )

    if (
        item.evidence_sufficiency is EvidenceSufficiency.COMPARISON_READY
        and not _has_qualifying_evidence(item)
    ):
        findings.append(
            _finding(
                ContradictionCode.COMPARISON_READY_WITHOUT_QUALIFYING_EVIDENCE,
                "Comparison-ready sufficiency requires qualifying evidence.",
                (
                    f"{item.market_name} is marked comparison_ready without "
                    "qualifying ranking evidence."
                ),
            )
        )

    if _critical_gap_count(item.supporting_metrics) > 0 and not item.limitations:
        findings.append(
            _finding(
                ContradictionCode.NO_LIMITATIONS_DESPITE_CRITICAL_GAPS,
                "Critical coverage gaps must appear as public limitations.",
                (
                    f"{item.market_name} has critical or high coverage gaps, but "
                    "no limitations are shown."
                ),
            )
        )

    if (
        top_market_key == item.market_key
        and _has_equal_score_peer(item, ranking_items)
        and _tie_breaker_is_alphabetical(tie_breaker)
    ):
        findings.append(
            _finding(
                ContradictionCode.ALPHABETICAL_TIE_DISPLAYED_AS_WINNER,
                "A market-key tie break must not be presented as substantive superiority.",
                (
                    f"{item.market_name} is displayed as the top market despite an "
                    "equal score tie resolved by market-key ordering."
                ),
            )
        )

    return _analysis(findings)


def apply_ranking_contradictions(
    report: ExplainableRankingReport,
) -> ExplainableRankingReport:
    updated_items: list[ExplainableRankingItem] = []
    for item in report.ranked_markets:
        analysis = evaluate_ranking_item_contradictions(
            item,
            ranking_items=report.ranked_markets,
            top_market_key=report.top_market_key,
            tie_breaker=report.tie_breaker,
            explanation=report.explanation,
        )
        updated_items.append(
            replace(
                item,
                contradiction_status=analysis.status,
                contradictions=analysis.findings,
            )
        )

    top_findings = tuple(
        finding
        for item in updated_items
        if item.market_key == report.top_market_key
        for finding in item.contradictions
    )
    analysis = _analysis((*report.contradictions, *top_findings))
    limitations = _with_contradiction_limitation(report.limitations, analysis)
    if not analysis.has_blocking:
        return replace(
            report,
            ranked_markets=tuple(updated_items),
            limitations=limitations,
            contradiction_status=analysis.status,
            contradictions=analysis.findings,
        )

    reason = _blocking_reason(analysis)
    return replace(
        report,
        ranked_markets=tuple(updated_items),
        top_market_key=None,
        explanation=f"Contradiction detection: {reason} {report.explanation}",
        limitations=limitations,
        abstention_reason=reason,
        contradiction_status=analysis.status,
        contradictions=analysis.findings,
    )


def evaluate_comparison_contradictions(
    report: MarketComparisonReport,
) -> ContradictionAnalysis:
    findings: list[ContradictionFinding] = [*report.contradictions]

    if (
        report.confidence is IntelligenceConfidence.HIGH
        and report.evidence_sufficiency in _BLOCKING_SUFFICIENCY
    ):
        findings.append(
            _finding(
                ContradictionCode.HIGH_CONFIDENCE_INSUFFICIENT_EVIDENCE,
                "High comparison confidence is inconsistent with abstention-level evidence.",
                (
                    f"Comparison confidence is {report.confidence.value} and "
                    f"evidence sufficiency is {report.evidence_sufficiency.value}."
                ),
            )
        )

    winner = _comparison_winner_side(report)
    loser = _comparison_loser_side(report)
    if winner and loser and winner["score"] < loser["score"]:
        findings.append(
            _finding(
                ContradictionCode.WINNER_WITH_LOWER_SCORE,
                "The declared winner has a lower score than the other market.",
                (
                    f"{winner['market_name']} is declared winner with score "
                    f"{winner['score']:.4f} below {loser['market_name']} at "
                    f"{loser['score']:.4f}."
                ),
            )
        )

    if report.winner_market_key and report.market_a.score == report.market_b.score:
        findings.append(
            _finding(
                ContradictionCode.ALPHABETICAL_TIE_DISPLAYED_AS_WINNER,
                "An equal-score tie is displayed as a winner.",
                (
                    f"{report.market_a.market_name} and {report.market_b.market_name} "
                    f"both score {report.market_a.score:.4f}."
                ),
            )
        )

    if (
        report.evidence_sufficiency is EvidenceSufficiency.COMPARISON_READY
        and (
            not _side_has_qualifying_evidence(report.market_a.supporting_metrics)
            or not _side_has_qualifying_evidence(report.market_b.supporting_metrics)
        )
    ):
        findings.append(
            _finding(
                ContradictionCode.COMPARISON_READY_WITHOUT_QUALIFYING_EVIDENCE,
                "Comparison-ready pairwise output requires qualifying evidence on both sides.",
                "At least one comparison side lacks qualifying ranking evidence.",
            )
        )

    if (
        _critical_gap_count(report.market_a.supporting_metrics)
        + _critical_gap_count(report.market_b.supporting_metrics)
        + _critical_gap_count(report.supporting_metrics)
        > 0
        and not report.limitations
    ):
        findings.append(
            _finding(
                ContradictionCode.NO_LIMITATIONS_DESPITE_CRITICAL_GAPS,
                "Critical coverage gaps must appear as public comparison limitations.",
                "The comparison includes critical or high coverage gaps without limitations.",
            )
        )

    return _analysis(findings)


def apply_comparison_contradictions(
    report: MarketComparisonReport,
) -> MarketComparisonReport:
    analysis = evaluate_comparison_contradictions(report)
    limitations = _with_contradiction_limitation(report.limitations, analysis)
    if not analysis.has_blocking:
        return replace(
            report,
            limitations=limitations,
            contradiction_status=analysis.status,
            contradictions=analysis.findings,
        )

    reason = _blocking_reason(analysis)
    return replace(
        report,
        outcome=ComparisonOutcome.NO_WINNER,
        winner_market_key=None,
        explanation=f"Contradiction detection: {reason} {report.explanation}",
        limitations=limitations,
        is_provisional=False,
        abstention_reason=reason,
        contradiction_status=analysis.status,
        contradictions=analysis.findings,
    )


def contradiction_status(
    findings: Iterable[ContradictionFinding],
) -> ContradictionStatus:
    return _analysis(findings).status


def contradiction_blocks_recommendation(
    findings: Iterable[ContradictionFinding],
) -> bool:
    return _analysis(findings).has_blocking


def contradiction_limitation(analysis: ContradictionAnalysis) -> str | None:
    if not analysis.findings:
        return None
    if analysis.has_blocking:
        return f"Contradiction detection blocked a normal recommendation: {_codes(analysis)}."
    return f"Contradiction detection returned warning(s): {_codes(analysis)}."


def _finding(
    code: ContradictionCode,
    message: str,
    evidence: str,
    *,
    severity: ContradictionSeverity = ContradictionSeverity.BLOCKING,
) -> ContradictionFinding:
    return ContradictionFinding(
        code=code,
        severity=severity,
        message=message,
        evidence=evidence,
        blocks_recommendation=severity is ContradictionSeverity.BLOCKING,
    )


def _analysis(
    findings: Iterable[ContradictionFinding],
) -> ContradictionAnalysis:
    stable_findings = _stable_findings(findings)
    has_blocking = any(finding.blocks_recommendation for finding in stable_findings)
    if has_blocking:
        status = ContradictionStatus.BLOCKING
    elif stable_findings:
        status = ContradictionStatus.WARNINGS
    else:
        status = ContradictionStatus.CLEAR
    return ContradictionAnalysis(
        status=status,
        findings=stable_findings,
        has_blocking=has_blocking,
    )


def _stable_findings(
    findings: Iterable[ContradictionFinding],
) -> tuple[ContradictionFinding, ...]:
    by_key: dict[tuple[str, str, str], ContradictionFinding] = {}
    for finding in findings:
        key = (finding.code.value, finding.message, finding.evidence)
        by_key[key] = finding
    return tuple(
        sorted(
            by_key.values(),
            key=lambda finding: (
                0 if finding.severity is ContradictionSeverity.BLOCKING else 1,
                finding.code.value,
                finding.evidence,
                finding.message,
            ),
        )
    )


def _with_contradiction_limitation(
    limitations: tuple[str, ...],
    analysis: ContradictionAnalysis,
) -> tuple[str, ...]:
    limitation = contradiction_limitation(analysis)
    if not limitation:
        return limitations
    return tuple(dict.fromkeys((*limitations, limitation)))


def _blocking_reason(analysis: ContradictionAnalysis) -> str:
    return (
        "normal recommendation is blocked by contradiction code(s) "
        f"{_codes(analysis)}."
    )


def _codes(analysis: ContradictionAnalysis) -> str:
    return ", ".join(finding.code.value for finding in analysis.findings)


def _has_strong_internship_claim(texts: Iterable[str]) -> bool:
    normalized = " ".join(_normalize_text(text) for text in texts)
    return any(pattern in normalized for pattern in _STRONG_INTERNSHIP_PATTERNS)


def _missing_internship_evidence(item: ExplainableRankingItem) -> bool:
    if any(driver.code == "internship" for driver in item.ranking_drivers):
        return False
    internship_total = item.supporting_metrics.get("internship_total")
    if internship_total is None:
        return True
    if isinstance(internship_total, bool):
        return True
    if isinstance(internship_total, int | float):
        return internship_total <= 0 and _metric(
            item.supporting_metrics,
            "internship_unknown_rows",
        ) > 0
    return True


def _opposite_weakness_and_driver(item: ExplainableRankingItem) -> str | None:
    weakness_text = tuple(_normalize_text(weakness) for weakness in item.weaknesses)
    if not weakness_text:
        return None
    for driver in item.ranking_drivers:
        if driver.contribution <= 0:
            continue
        keywords = _driver_keywords(driver)
        for weakness in weakness_text:
            if not any(term in weakness for term in _NEGATIVE_TERMS):
                continue
            if any(_contains_keyword(weakness, keyword) for keyword in keywords):
                return (
                    f"{item.market_name} has positive driver {driver.code} while "
                    f"a weakness reports limited {driver.label}."
                )
    return None


def _specific_role_recommendation_without_direct_evidence(
    item: ExplainableRankingItem,
    *,
    top_market_key: str | None,
    explanation: str,
) -> bool:
    if top_market_key != item.market_key:
        return False
    if item.is_provisional:
        return False
    if item.evidence_sufficiency is not EvidenceSufficiency.COMPARISON_READY:
        return False
    definition = career_goal_definition(item.goal)
    if definition.minimum_direct_evidence <= 0:
        return False
    if _direct_evidence_count(item) > 0:
        return False
    text = _normalize_text(explanation)
    if not text:
        return True
    goal_terms = _goal_terms(item.goal)
    recommendation_terms = ("recommend", "strongest", "top ", "rank 1")
    return any(term in text for term in goal_terms) and any(
        term in text for term in recommendation_terms
    )


def _direct_evidence_count(item: ExplainableRankingItem) -> int:
    metric_value = item.supporting_metrics.get("direct_evidence_count")
    if isinstance(metric_value, bool):
        return 0
    if isinstance(metric_value, int | float):
        return int(metric_value)
    classification = classify_goal_evidence(
        item.goal,
        (driver.code for driver in item.ranking_drivers),
    )
    return classification.direct_evidence_count


def _has_qualifying_evidence(item: ExplainableRankingItem) -> bool:
    if item.evidence_basis is EvidenceBasis.NO_QUALIFYING_EVIDENCE:
        return False
    if _metric(item.supporting_metrics, "ranking_eligible_fact_count") <= 0:
        return False
    total = item.supporting_metrics.get("total_evidence_count")
    if isinstance(total, bool):
        return bool(item.ranking_drivers)
    if isinstance(total, int | float):
        return total > 0
    return bool(item.ranking_drivers)


def _side_has_qualifying_evidence(
    metrics: Mapping[str, int | float | str | None],
) -> bool:
    if _metric(metrics, "ranking_eligible_fact_count") <= 0:
        return False
    total = metrics.get("total_evidence_count")
    if isinstance(total, bool):
        return True
    if isinstance(total, int | float):
        return total > 0
    return True


def _has_equal_score_peer(
    item: ExplainableRankingItem,
    ranking_items: tuple[ExplainableRankingItem, ...],
) -> bool:
    return any(
        peer.market_key != item.market_key and peer.score == item.score
        for peer in ranking_items
    )


def _tie_breaker_is_alphabetical(tie_breaker: str) -> bool:
    normalized = _normalize_text(tie_breaker)
    return "market key" in normalized or "alphabet" in normalized


def _comparison_winner_side(
    report: MarketComparisonReport,
) -> dict[str, object] | None:
    if report.winner_market_key == report.market_a.market_key:
        return {
            "market_name": report.market_a.market_name,
            "score": report.market_a.score,
        }
    if report.winner_market_key == report.market_b.market_key:
        return {
            "market_name": report.market_b.market_name,
            "score": report.market_b.score,
        }
    return None


def _comparison_loser_side(
    report: MarketComparisonReport,
) -> dict[str, object] | None:
    if report.winner_market_key == report.market_a.market_key:
        return {
            "market_name": report.market_b.market_name,
            "score": report.market_b.score,
        }
    if report.winner_market_key == report.market_b.market_key:
        return {
            "market_name": report.market_a.market_name,
            "score": report.market_a.score,
        }
    return None


def _critical_gap_count(metrics: Mapping[str, int | float | str | None]) -> int:
    return _metric(metrics, "critical_gap_count") + _metric(metrics, "high_gap_count")


def _driver_keywords(driver: RankingDriver) -> tuple[str, ...]:
    return _DRIVER_KEYWORDS.get(driver.code, (driver.code.replace("_", " "),))


def _goal_terms(goal: CareerGoal) -> tuple[str, ...]:
    label = _normalize_text(career_goal_definition(goal).label)
    return (label, goal.value.replace("_", " "))


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().casefold())


def _contains_keyword(text: str, keyword: str) -> bool:
    if re.fullmatch(r"[a-z0-9]+", keyword):
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", text))
    return keyword in text


def _metric(metrics: Mapping[str, int | float | str | None], key: str) -> int:
    value = metrics.get(key)
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0
