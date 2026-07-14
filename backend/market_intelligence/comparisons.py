"""Cross-market comparison reports for Layer 34."""

from __future__ import annotations

from backend.market_intelligence.contradictions import apply_comparison_contradictions
from backend.market_intelligence.explanations import (
    build_pairwise_comparison_explanation,
)
from backend.market_intelligence.grounding import (
    build_comparison_grounding,
    grounding_for_comparison_side,
)
from backend.market_intelligence.schemas import (
    CareerGoal,
    ComparisonOutcome,
    EvidenceSufficiency,
    ExplainableRankingItem,
    IntelligenceConfidence,
    MarketComparisonReport,
    MarketComparisonSide,
)
from backend.market_intelligence.sufficiency import (
    cap_confidence_for_sufficiency,
    combine_sufficiency,
    sufficiency_requires_abstention,
)


def compare_ranked_markets(
    market_a: str,
    market_b: str,
    *,
    goal: CareerGoal,
    ranking_items: tuple[ExplainableRankingItem, ...],
) -> MarketComparisonReport:
    by_market = {item.market_key: item for item in ranking_items}
    left = by_market[market_a]
    right = by_market[market_b]
    sufficiency = combine_sufficiency(
        left.evidence_sufficiency,
        right.evidence_sufficiency,
    )
    outcome, winner = _winner(left, right, sufficiency=sufficiency)
    confidence = cap_confidence_for_sufficiency(
        _combined_confidence(left.confidence, right.confidence),
        sufficiency=sufficiency,
        proxy_only_confidence_cap=IntelligenceConfidence.LOW,
        direct_evidence_count=min(
            _metric(left.supporting_metrics, "direct_evidence_count"),
            _metric(right.supporting_metrics, "direct_evidence_count"),
        ),
    )
    limitations = tuple(
        sorted(
            {
                *left.limitations,
                *right.limitations,
                *_comparison_limitations(sufficiency),
            }
        )
    )
    abstention_reason = _comparison_abstention_reason(left, right, sufficiency)
    score_delta = round(abs(left.score - right.score), 4)
    report = MarketComparisonReport(
        goal=goal,
        market_a=_side(left),
        market_b=_side(right),
        outcome=outcome,
        winner_market_key=winner.market_key if winner else None,
        explanation=build_pairwise_comparison_explanation(
            left,
            right,
            winner,
            sufficiency=sufficiency,
            abstention_reason=abstention_reason,
        ),
        confidence=confidence,
        supporting_metrics={
            "market_a_score": left.score,
            "market_b_score": right.score,
            "score_delta": score_delta,
            "market_a_rank": left.rank,
            "market_b_rank": right.rank,
            "evidence_sufficiency": sufficiency.value,
        },
        limitations=limitations,
        evidence_sufficiency=sufficiency,
        is_provisional=sufficiency is EvidenceSufficiency.LIMITED_EVIDENCE,
        abstention_reason=abstention_reason,
        grounding=build_comparison_grounding(
            left=left,
            right=right,
            confidence=confidence,
            evidence_sufficiency=sufficiency,
            limitations=limitations,
            score_delta=score_delta,
        ),
    )
    return apply_comparison_contradictions(report)


def _winner(
    left: ExplainableRankingItem,
    right: ExplainableRankingItem,
    *,
    sufficiency: EvidenceSufficiency,
) -> tuple[ComparisonOutcome, ExplainableRankingItem | None]:
    if sufficiency_requires_abstention(sufficiency):
        return ComparisonOutcome.NO_WINNER, None
    if left.score == right.score:
        return ComparisonOutcome.TIE, None
    if left.score > right.score:
        return ComparisonOutcome.MARKET_A, left
    return ComparisonOutcome.MARKET_B, right


def _side(item: ExplainableRankingItem) -> MarketComparisonSide:
    return MarketComparisonSide(
        market_key=item.market_key,
        market_name=item.market_name,
        score=item.score,
        confidence=item.confidence,
        strengths=item.strengths,
        weaknesses=item.weaknesses,
        supporting_metrics=item.supporting_metrics,
        evidence_sufficiency=item.evidence_sufficiency,
        evidence_basis=item.evidence_basis,
        grounding=grounding_for_comparison_side(item),
    )


def _combined_confidence(
    left: IntelligenceConfidence,
    right: IntelligenceConfidence,
) -> IntelligenceConfidence:
    order = {
        IntelligenceConfidence.HIGH: 4,
        IntelligenceConfidence.MODERATE: 3,
        IntelligenceConfidence.LOW: 2,
        IntelligenceConfidence.LIMITED: 1,
    }
    return left if order[left] <= order[right] else right


def _comparison_abstention_reason(
    left: ExplainableRankingItem,
    right: ExplainableRankingItem,
    sufficiency: EvidenceSufficiency,
) -> str | None:
    if not sufficiency_requires_abstention(sufficiency):
        return None
    reasons = tuple(
        dict.fromkeys(
            reason
            for reason in (left.abstention_reason, right.abstention_reason)
            if reason
        )
    )
    if reasons:
        return "; ".join(reasons)
    if sufficiency is EvidenceSufficiency.NOT_SUPPORTED:
        return "the current canonical data model does not support this comparison"
    return "there is insufficient evidence for this comparison"


def _comparison_limitations(
    sufficiency: EvidenceSufficiency,
) -> tuple[str, ...]:
    if sufficiency is EvidenceSufficiency.COMPARISON_READY:
        return ()
    if sufficiency is EvidenceSufficiency.LIMITED_EVIDENCE:
        return ("Pairwise comparison is provisional because evidence is limited.",)
    if sufficiency is EvidenceSufficiency.INSUFFICIENT_EVIDENCE:
        return (
            "Pairwise comparison abstains from a winner because evidence is insufficient.",
        )
    return (
        "Pairwise comparison is not supported for an authoritative winner by the "
        "current canonical data model.",
    )


def _metric(metrics: dict[str, int | float | str | None], key: str) -> int:
    value = metrics.get(key)
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0
