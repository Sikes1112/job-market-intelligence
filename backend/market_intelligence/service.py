"""Read-only orchestration service for Layer 34 market intelligence."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.imports.operations import (
    MarketOperationalSnapshot,
    UnknownCuratedMarket,
    build_all_market_operational_snapshots,
)
from backend.market_intelligence.calibration import build_calibration_report
from backend.market_intelligence.comparisons import compare_ranked_markets
from backend.market_intelligence.differentiation import evaluate_market_differentiation
from backend.market_intelligence.evaluation import build_product_quality_evaluation_report
from backend.market_intelligence.explanations import build_ranking_report_explanation
from backend.market_intelligence.goals import (
    career_goal_definition,
    career_goal_definitions,
    coerce_goal,
)
from backend.market_intelligence.profiles import build_market_profile
from backend.market_intelligence.robustness import evaluate_ranking_robustness
from backend.market_intelligence.schemas import (
    CareerGoal,
    CareerGoalComparisonReport,
    ContradictionStatus,
    EvidenceSufficiency,
    ExplainableRankingReport,
    IntelligenceConfidence,
    MarketCalibrationReport,
    MarketComparisonReport,
    MarketDifferentiationAudit,
    MarketGoalStabilityAnalysis,
    MarketIntelligenceProfile,
    PlatformMarketIntelligenceReport,
    ProductQualityEvaluationReport,
    RankingStabilityStatus,
)
from backend.market_intelligence.scoring import (
    MarketMetrics,
    metrics_from_snapshot,
    rank_profiles,
)
from backend.market_intelligence.sufficiency import sufficiency_allows_recommendation
from backend.scoring.models import RegionMarketScore


class UnknownMarketForIntelligence(KeyError):
    """Raised when a requested market is not registered for intelligence."""


class InvalidCareerGoal(ValueError):
    """Raised when a requested career goal is not supported."""


@dataclass(frozen=True, slots=True)
class _IntelligenceState:
    snapshots: tuple[MarketOperationalSnapshot, ...]
    profiles: tuple[MarketIntelligenceProfile, ...]
    metrics_by_market: dict[str, MarketMetrics]


class MarketIntelligenceService:
    """Build public-safe market intelligence from canonical imported data.

    The service performs no writes. It reads Layer 33 operational snapshots,
    stored region market scores, ranking eligibility, freshness, coverage, and
    confidence diagnostics, then composes deterministic profile and comparison
    DTOs for API callers.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def platform_summary(
        self,
        *,
        goal: CareerGoal | str = CareerGoal.SOFTWARE_ENGINEERING,
        as_of: date | datetime | None = None,
    ) -> PlatformMarketIntelligenceReport:
        selected_goal = _coerce_goal_or_raise(goal)
        state = self._build_state(as_of=as_of)
        default_ranking = self.ranking(
            goal=selected_goal,
            as_of=as_of,
            _state=state,
        )
        highest_confidence = _highest_confidence_market(state.profiles)
        return PlatformMarketIntelligenceReport(
            market_count=len(state.snapshots),
            profile_count=len(state.profiles),
            supported_goals=career_goal_definitions(),
            profiles=state.profiles,
            default_ranking=default_ranking,
            highest_confidence_market=highest_confidence.market_key
            if highest_confidence
            else None,
            public_summary=_platform_summary_text(state.profiles, default_ranking),
            limitations=_platform_limitations(state.profiles, default_ranking),
        )

    def profile(
        self,
        market_key: str,
        *,
        as_of: date | datetime | None = None,
    ) -> MarketIntelligenceProfile:
        state = self._build_state(as_of=as_of)
        by_market = {profile.market_key: profile for profile in state.profiles}
        try:
            return by_market[market_key]
        except KeyError as exc:
            raise UnknownMarketForIntelligence(market_key) from exc

    def ranking(
        self,
        *,
        goal: CareerGoal | str = CareerGoal.SOFTWARE_ENGINEERING,
        as_of: date | datetime | None = None,
        _state: _IntelligenceState | None = None,
        _include_stability: bool = True,
    ) -> ExplainableRankingReport:
        selected_goal = _coerce_goal_or_raise(goal)
        state = _state or self._build_state(as_of=as_of)
        ranking = rank_profiles(
            state.profiles,
            state.metrics_by_market,
            goal=selected_goal,
            goal_definition=career_goal_definition(selected_goal),
        )
        if not _include_stability:
            return ranking
        stability = evaluate_ranking_robustness(
            rankings={selected_goal: ranking},
            profiles=state.profiles,
            metrics_by_market=state.metrics_by_market,
        )
        return _ranking_with_stability(
            ranking,
            stability.get(selected_goal, {}),
        )

    def comparison(
        self,
        market_a: str,
        market_b: str,
        *,
        goal: CareerGoal | str = CareerGoal.SOFTWARE_ENGINEERING,
        as_of: date | datetime | None = None,
    ) -> MarketComparisonReport:
        selected_goal = _coerce_goal_or_raise(goal)
        state = self._build_state(as_of=as_of)
        market_keys = {profile.market_key for profile in state.profiles}
        missing = tuple(
            market for market in (market_a, market_b) if market not in market_keys
        )
        if missing:
            raise UnknownMarketForIntelligence(missing[0])
        ranking = self.ranking(goal=selected_goal, as_of=as_of, _state=state)
        return compare_ranked_markets(
            market_a,
            market_b,
            goal=selected_goal,
            ranking_items=ranking.ranked_markets,
        )

    def career_goal_comparison(
        self,
        *,
        goal: CareerGoal | str,
        as_of: date | datetime | None = None,
    ) -> CareerGoalComparisonReport:
        selected_goal = _coerce_goal_or_raise(goal)
        definition = career_goal_definition(selected_goal)
        ranking = self.ranking(goal=selected_goal, as_of=as_of)
        top = ranking.ranked_markets[0] if ranking.ranked_markets else None
        recommended = _recommended_item(top)
        limitations = tuple(
            sorted({*ranking.limitations, *definition.limitations})
        )
        return CareerGoalComparisonReport(
            goal=selected_goal,
            goal_definition=definition,
            ranking=ranking,
            recommended_market_key=recommended.market_key if recommended else None,
            recommendation_summary=_recommendation_summary(
                recommended,
                definition.label,
                top=top,
            ),
            confidence=top.confidence if top else IntelligenceConfidence.LIMITED,
            limitations=limitations,
            evidence_sufficiency=(
                top.evidence_sufficiency
                if top
                else EvidenceSufficiency.INSUFFICIENT_EVIDENCE
            ),
            is_provisional=bool(top and top.is_provisional),
            abstention_reason=(
                ranking.abstention_reason
                or (top.abstention_reason if top else "no ranked markets are available")
            ),
            contradiction_status=ranking.contradiction_status,
            contradictions=ranking.contradictions,
            grounding=ranking.grounding,
        )

    def all_career_goal_comparisons(
        self,
        *,
        as_of: date | datetime | None = None,
    ) -> tuple[CareerGoalComparisonReport, ...]:
        state = self._build_state(as_of=as_of)
        return tuple(
            self._career_goal_comparison_with_state(goal, as_of=as_of, state=state)
            for goal in CareerGoal
        )

    def calibration_report(
        self,
        *,
        as_of: date | datetime | None = None,
    ) -> MarketCalibrationReport:
        state = self._build_state(as_of=as_of)
        rankings = {
            goal: self.ranking(
                goal=goal,
                as_of=as_of,
                _state=state,
                _include_stability=False,
            )
            for goal in CareerGoal
        }
        stability = evaluate_ranking_robustness(
            rankings=rankings,
            profiles=state.profiles,
            metrics_by_market=state.metrics_by_market,
        )
        return build_calibration_report(
            rankings=rankings,
            stability_by_goal_market=stability,
            as_of=as_of,
        )

    def differentiation_audit(
        self,
        *,
        as_of: date | datetime | None = None,
    ) -> MarketDifferentiationAudit:
        state = self._build_state(as_of=as_of)
        rankings = {
            goal: self.ranking(
                goal=goal,
                as_of=as_of,
                _state=state,
                _include_stability=False,
            )
            for goal in CareerGoal
        }
        return evaluate_market_differentiation(
            profiles=state.profiles,
            rankings=rankings,
        )

    def product_quality_evaluation_report(
        self,
        *,
        as_of: date | datetime | None = None,
    ) -> ProductQualityEvaluationReport:
        state = self._build_state(as_of=as_of)
        rankings = {
            goal: self.ranking(
                goal=goal,
                as_of=as_of,
                _state=state,
                _include_stability=False,
            )
            for goal in CareerGoal
        }
        stability = evaluate_ranking_robustness(
            rankings=rankings,
            profiles=state.profiles,
            metrics_by_market=state.metrics_by_market,
        )
        calibration = build_calibration_report(
            rankings=rankings,
            stability_by_goal_market=stability,
            as_of=as_of,
        )
        differentiation = evaluate_market_differentiation(
            profiles=state.profiles,
            rankings=rankings,
        )
        return build_product_quality_evaluation_report(
            calibration_report=calibration,
            differentiation_audit=differentiation,
            rankings=rankings,
        )

    def _career_goal_comparison_with_state(
        self,
        goal: CareerGoal,
        *,
        as_of: date | datetime | None,
        state: _IntelligenceState,
    ) -> CareerGoalComparisonReport:
        definition = career_goal_definition(goal)
        ranking = self.ranking(goal=goal, as_of=as_of, _state=state)
        top = ranking.ranked_markets[0] if ranking.ranked_markets else None
        recommended = _recommended_item(top)
        limitations = tuple(
            sorted({*ranking.limitations, *definition.limitations})
        )
        return CareerGoalComparisonReport(
            goal=goal,
            goal_definition=definition,
            ranking=ranking,
            recommended_market_key=recommended.market_key if recommended else None,
            recommendation_summary=_recommendation_summary(
                recommended,
                definition.label,
                top=top,
            ),
            confidence=top.confidence if top else IntelligenceConfidence.LIMITED,
            limitations=limitations,
            evidence_sufficiency=(
                top.evidence_sufficiency
                if top
                else EvidenceSufficiency.INSUFFICIENT_EVIDENCE
            ),
            is_provisional=bool(top and top.is_provisional),
            abstention_reason=(
                ranking.abstention_reason
                or (top.abstention_reason if top else "no ranked markets are available")
            ),
            contradiction_status=ranking.contradiction_status,
            contradictions=ranking.contradictions,
            grounding=ranking.grounding,
        )

    def _build_state(
        self,
        *,
        as_of: date | datetime | None,
    ) -> _IntelligenceState:
        try:
            snapshots = build_all_market_operational_snapshots(
                self._session,
                as_of=as_of,
            )
        except UnknownCuratedMarket as exc:
            raise UnknownMarketForIntelligence(str(exc)) from exc
        region_ids = tuple(sorted({snapshot.region_id for snapshot in snapshots}))
        scores = self._scores_by_region(region_ids)
        metrics_by_market = {
            snapshot.market_key: metrics_from_snapshot(
                snapshot,
                score=scores.get(snapshot.region_id),
            )
            for snapshot in snapshots
        }
        all_metrics = tuple(metrics_by_market[key] for key in sorted(metrics_by_market))
        profiles = tuple(
            build_market_profile(
                snapshot,
                metrics_by_market[snapshot.market_key],
                all_metrics=all_metrics,
            )
            for snapshot in sorted(snapshots, key=lambda item: item.market_key)
        )
        return _IntelligenceState(
            snapshots=tuple(sorted(snapshots, key=lambda item: item.market_key)),
            profiles=profiles,
            metrics_by_market=metrics_by_market,
        )

    def _scores_by_region(
        self,
        region_ids: tuple[str, ...],
    ) -> dict[str, RegionMarketScore]:
        if not region_ids:
            return {}
        rows = (
            self._session.execute(
                select(RegionMarketScore)
                .where(RegionMarketScore.region_id.in_(region_ids))
                .order_by(
                    RegionMarketScore.region_id.asc(),
                    RegionMarketScore.region_score_id.asc(),
                )
            )
            .scalars()
            .all()
        )
        scores: dict[str, RegionMarketScore] = {}
        for row in rows:
            scores.setdefault(row.region_id, row)
        return scores


def _coerce_goal_or_raise(goal: CareerGoal | str) -> CareerGoal:
    try:
        return coerce_goal(goal)
    except ValueError as exc:
        raise InvalidCareerGoal(str(goal)) from exc


def _highest_confidence_market(
    profiles: tuple[MarketIntelligenceProfile, ...],
) -> MarketIntelligenceProfile | None:
    if not profiles:
        return None
    order = {
        IntelligenceConfidence.HIGH: 4,
        IntelligenceConfidence.MODERATE: 3,
        IntelligenceConfidence.LOW: 2,
        IntelligenceConfidence.LIMITED: 1,
    }
    return sorted(
        profiles,
        key=lambda item: (-order[item.confidence], -item.confidence_score, item.market_key),
    )[0]


def _platform_summary_text(
    profiles: tuple[MarketIntelligenceProfile, ...],
    ranking: ExplainableRankingReport,
) -> str:
    top = ranking.ranked_markets[0] if ranking.ranked_markets else None
    if top is None:
        return "No registered imported markets are available for intelligence."
    if ranking.abstention_reason:
        return (
            f"{len(profiles)} imported market profile(s) are available; the backend "
            f"abstains from naming a top {ranking.goal_definition.label} market "
            f"because {ranking.abstention_reason}."
        )
    if ranking.is_provisional:
        return (
            f"{len(profiles)} imported market profile(s) are available; "
            f"{top.market_name} is the provisional top {ranking.goal_definition.label} "
            "match under confidence-aware scoring."
        )
    return (
        f"{len(profiles)} imported market profile(s) are available; "
        f"{top.market_name} is currently the top {ranking.goal_definition.label} "
        "match under confidence-aware scoring."
    )


def _platform_limitations(
    profiles: tuple[MarketIntelligenceProfile, ...],
    ranking: ExplainableRankingReport,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                *ranking.limitations,
                *(
                    limitation
                    for profile in profiles
                    for limitation in profile.limitations
                ),
            }
        )
    )


def _ranking_with_stability(
    ranking: ExplainableRankingReport,
    stability_by_market: dict[str, MarketGoalStabilityAnalysis],
) -> ExplainableRankingReport:
    if not ranking.ranked_markets or not stability_by_market:
        return ranking

    updated_items = tuple(
        _item_with_stability(
            item,
            stability_by_market.get(item.market_key),
        )
        for item in ranking.ranked_markets
    )
    report_limitations = tuple(
        sorted(
            {
                *ranking.limitations,
                *(limitation for item in updated_items for limitation in item.limitations),
            }
        )
    )
    grounding = _report_grounding(ranking, updated_items)
    explanation = ranking.explanation
    if ranking.contradiction_status is not ContradictionStatus.BLOCKING:
        top = _explanation_top_item(ranking, updated_items)
        explanation = build_ranking_report_explanation(
            top,
            updated_items,
            ranking.goal_definition,
        )
    return replace(
        ranking,
        ranked_markets=updated_items,
        explanation=explanation,
        limitations=report_limitations,
        grounding=grounding,
    )


def _item_with_stability(
    item: Any,
    stability: MarketGoalStabilityAnalysis | None,
) -> Any:
    if stability is None:
        return item
    limitations = tuple(
        dict.fromkeys(
            (
                *item.limitations,
                *_stability_limitations(stability.status),
            )
        )
    )
    grounding = item.grounding
    if grounding is not None:
        grounding = replace(
            grounding,
            stability_status=stability.status,
            stability_scenarios=stability.scenarios,
        )
    return replace(item, limitations=limitations, grounding=grounding)


def _report_grounding(
    ranking: ExplainableRankingReport,
    updated_items: tuple[Any, ...],
) -> Any:
    if ranking.top_market_key:
        for item in updated_items:
            if item.market_key == ranking.top_market_key:
                return item.grounding
    return updated_items[0].grounding if updated_items else ranking.grounding


def _explanation_top_item(
    ranking: ExplainableRankingReport,
    updated_items: tuple[Any, ...],
) -> Any:
    if ranking.top_market_key:
        for item in updated_items:
            if item.market_key == ranking.top_market_key:
                return item
    return updated_items[0] if updated_items else None


def _stability_limitations(
    status: RankingStabilityStatus,
) -> tuple[str, ...]:
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


def _recommendation_summary(recommended: Any, goal_label: str, *, top: Any | None) -> str:
    if recommended is None:
        if top is not None and getattr(top, "contradiction_status", None) is (
            ContradictionStatus.BLOCKING
        ):
            reason = _contradiction_reason(top)
            return (
                f"No firm {goal_label} market can be recommended because "
                f"contradiction detection blocked the result: {reason}."
            )
        if top is not None and not sufficiency_allows_recommendation(
            top.evidence_sufficiency
        ):
            reason = top.abstention_reason or "evidence is insufficient"
            return f"No firm {goal_label} market can be recommended because {reason}."
        return f"No imported market can be recommended for {goal_label}."
    drivers = ", ".join(driver.label for driver in recommended.ranking_drivers[:3])
    if not drivers:
        drivers = "available canonical metrics"
    if recommended.is_provisional:
        return (
            f"{recommended.market_name} is the provisional strongest current {goal_label} "
            f"match because of {drivers}; confidence is {recommended.confidence.value}."
        )
    return (
        f"{recommended.market_name} is the strongest current {goal_label} match because "
        f"of {drivers}; confidence is {recommended.confidence.value}."
    )


def _contradiction_reason(top: Any) -> str:
    findings = getattr(top, "contradictions", ())
    codes = tuple(finding.code.value for finding in findings)
    if codes:
        return ", ".join(codes)
    return "blocking contradiction status is present"


def _recommended_item(top: Any) -> Any:
    if top is None:
        return None
    if not sufficiency_allows_recommendation(top.evidence_sufficiency):
        return None
    if getattr(top, "contradiction_status", None) is ContradictionStatus.BLOCKING:
        return None
    return top
