"""Evidence sufficiency gates for Layer 34C market intelligence."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from backend.market_intelligence.goals import (
    career_goal_definition,
    classify_goal_evidence,
    goal_component_weights,
)
from backend.market_intelligence.schemas import (
    CareerGoal,
    EvidenceSufficiency,
    GoalEvidenceClassification,
    IntelligenceConfidence,
    IntelligenceFreshness,
)

_CONFIDENCE_ORDER = {
    IntelligenceConfidence.LIMITED: 1,
    IntelligenceConfidence.LOW: 2,
    IntelligenceConfidence.MODERATE: 3,
    IntelligenceConfidence.HIGH: 4,
}


@dataclass(frozen=True, slots=True)
class EvidenceSufficiencyDecision:
    sufficiency: EvidenceSufficiency
    classification: GoalEvidenceClassification
    capped_confidence: IntelligenceConfidence
    limitations: tuple[str, ...]
    is_provisional: bool
    abstention_reason: str | None


def evaluate_ranking_sufficiency(
    *,
    goal: CareerGoal | str,
    evidence_categories: Iterable[str],
    score: float,
    confidence: IntelligenceConfidence,
    freshness: IntelligenceFreshness,
    supporting_metrics: Mapping[str, int | float | str | None],
    limitations: tuple[str, ...],
) -> EvidenceSufficiencyDecision:
    """Apply the Layer 34C sufficiency contract to one market-goal result."""

    selected_goal = CareerGoal(goal)
    definition = career_goal_definition(selected_goal)
    classification = classify_goal_evidence(selected_goal, evidence_categories)
    sufficiency, reason = _sufficiency_state(
        selected_goal,
        classification=classification,
        score=score,
        confidence=confidence,
        freshness=freshness,
        supporting_metrics=supporting_metrics,
        limitations=limitations,
    )
    capped_confidence = _capped_confidence(
        confidence,
        sufficiency=sufficiency,
        classification=classification,
    )
    added_limitations = _sufficiency_limitations(
        goal_label=definition.label,
        sufficiency=sufficiency,
        reason=reason,
    )
    return EvidenceSufficiencyDecision(
        sufficiency=sufficiency,
        classification=classification,
        capped_confidence=capped_confidence,
        limitations=tuple(dict.fromkeys((*limitations, *added_limitations))),
        is_provisional=sufficiency is EvidenceSufficiency.LIMITED_EVIDENCE,
        abstention_reason=reason
        if sufficiency
        in {
            EvidenceSufficiency.INSUFFICIENT_EVIDENCE,
            EvidenceSufficiency.NOT_SUPPORTED,
        }
        else None,
    )


def combine_sufficiency(
    left: EvidenceSufficiency,
    right: EvidenceSufficiency,
) -> EvidenceSufficiency:
    """Return the most restrictive public sufficiency state across two results."""

    if EvidenceSufficiency.NOT_SUPPORTED in {left, right}:
        return EvidenceSufficiency.NOT_SUPPORTED
    if EvidenceSufficiency.INSUFFICIENT_EVIDENCE in {left, right}:
        return EvidenceSufficiency.INSUFFICIENT_EVIDENCE
    if EvidenceSufficiency.LIMITED_EVIDENCE in {left, right}:
        return EvidenceSufficiency.LIMITED_EVIDENCE
    return EvidenceSufficiency.COMPARISON_READY


def cap_confidence_for_sufficiency(
    confidence: IntelligenceConfidence,
    *,
    sufficiency: EvidenceSufficiency,
    proxy_only_confidence_cap: IntelligenceConfidence = IntelligenceConfidence.LOW,
    direct_evidence_count: int = 1,
) -> IntelligenceConfidence:
    if sufficiency is EvidenceSufficiency.COMPARISON_READY:
        return confidence
    if sufficiency in {
        EvidenceSufficiency.INSUFFICIENT_EVIDENCE,
        EvidenceSufficiency.NOT_SUPPORTED,
    }:
        return _min_confidence(confidence, IntelligenceConfidence.LIMITED)
    if direct_evidence_count <= 0:
        return _min_confidence(confidence, proxy_only_confidence_cap)
    return _min_confidence(confidence, IntelligenceConfidence.LOW)


def sufficiency_allows_recommendation(sufficiency: EvidenceSufficiency) -> bool:
    return sufficiency in {
        EvidenceSufficiency.COMPARISON_READY,
        EvidenceSufficiency.LIMITED_EVIDENCE,
    }


def sufficiency_requires_abstention(sufficiency: EvidenceSufficiency) -> bool:
    return sufficiency in {
        EvidenceSufficiency.INSUFFICIENT_EVIDENCE,
        EvidenceSufficiency.NOT_SUPPORTED,
    }


def _sufficiency_state(
    goal: CareerGoal,
    *,
    classification: GoalEvidenceClassification,
    score: float,
    confidence: IntelligenceConfidence,
    freshness: IntelligenceFreshness,
    supporting_metrics: Mapping[str, int | float | str | None],
    limitations: tuple[str, ...],
) -> tuple[EvidenceSufficiency, str | None]:
    if _canonical_goal_not_supported(goal):
        return (
            EvidenceSufficiency.NOT_SUPPORTED,
            "the current canonical data model does not include direct evidence "
            "needed for this goal",
        )
    if (
        score <= 0
        or classification.total_evidence_count <= 0
        or _metric(supporting_metrics, "ranking_eligible_fact_count") <= 0
    ):
        return (
            EvidenceSufficiency.INSUFFICIENT_EVIDENCE,
            "there is not enough qualifying ranking evidence",
        )
    if not classification.meets_minimum_total_evidence:
        return (
            EvidenceSufficiency.INSUFFICIENT_EVIDENCE,
            (
                f"only {classification.total_evidence_count} qualifying evidence "
                f"categor{'y is' if classification.total_evidence_count == 1 else 'ies are'} "
                f"available and {classification.minimum_total_evidence} are required"
            ),
        )
    if not classification.meets_minimum_direct_evidence:
        return (
            EvidenceSufficiency.LIMITED_EVIDENCE,
            "the result relies on proxy evidence without enough direct goal evidence",
        )
    if freshness in {IntelligenceFreshness.STALE, IntelligenceFreshness.UNKNOWN}:
        return (
            EvidenceSufficiency.LIMITED_EVIDENCE,
            "freshness limits the strength of the available evidence",
        )
    if confidence in {IntelligenceConfidence.LOW, IntelligenceConfidence.LIMITED}:
        return (
            EvidenceSufficiency.LIMITED_EVIDENCE,
            "backend confidence is too low for a normal ranking",
        )
    if _metric(supporting_metrics, "unknown_fact_count") > 0:
        return (
            EvidenceSufficiency.LIMITED_EVIDENCE,
            "some count facts are unknown and are not treated as zero",
        )
    if limitations:
        return (
            EvidenceSufficiency.LIMITED_EVIDENCE,
            "known limitations make the result provisional",
        )
    return EvidenceSufficiency.COMPARISON_READY, None


def _canonical_goal_not_supported(goal: CareerGoal) -> bool:
    definition = career_goal_definition(goal)
    supported_components = frozenset(goal_component_weights(goal))
    supported_direct = (
        frozenset(definition.direct_evidence_categories) & supported_components
    )
    return definition.minimum_direct_evidence > 0 and not supported_direct


def _capped_confidence(
    confidence: IntelligenceConfidence,
    *,
    sufficiency: EvidenceSufficiency,
    classification: GoalEvidenceClassification,
) -> IntelligenceConfidence:
    return cap_confidence_for_sufficiency(
        confidence,
        sufficiency=sufficiency,
        proxy_only_confidence_cap=classification.proxy_only_confidence_cap,
        direct_evidence_count=classification.direct_evidence_count,
    )


def _sufficiency_limitations(
    *,
    goal_label: str,
    sufficiency: EvidenceSufficiency,
    reason: str | None,
) -> tuple[str, ...]:
    if sufficiency is EvidenceSufficiency.COMPARISON_READY:
        return ()
    if sufficiency is EvidenceSufficiency.LIMITED_EVIDENCE:
        detail = f" because {reason}" if reason else ""
        return (
            f"Evidence sufficiency is limited for {goal_label}; treat the ordering "
            f"as provisional{detail}.",
        )
    if sufficiency is EvidenceSufficiency.INSUFFICIENT_EVIDENCE:
        detail = f" because {reason}" if reason else ""
        return (
            f"Insufficient evidence for {goal_label}; the backend abstains from a "
            f"firm recommendation{detail}. Any ranked order is diagnostic ordering only.",
        )
    detail = f" because {reason}" if reason else ""
    return (
        f"{goal_label} is not supported for an authoritative ranking by the "
        f"current canonical data model{detail}. Any ranked order is diagnostic "
        "ordering only.",
    )


def _min_confidence(
    confidence: IntelligenceConfidence,
    cap: IntelligenceConfidence,
) -> IntelligenceConfidence:
    return confidence if _CONFIDENCE_ORDER[confidence] <= _CONFIDENCE_ORDER[cap] else cap


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
