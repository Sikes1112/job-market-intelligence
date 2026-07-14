"""Explanation quality helpers for Layer 34C market intelligence."""

from __future__ import annotations

import re
from collections.abc import Mapping

from backend.market_intelligence.goals import (
    classify_goal_evidence,
    public_evidence_label,
)
from backend.market_intelligence.schemas import (
    CareerGoalDefinition,
    EvidenceSufficiency,
    ExplainableRankingItem,
    RankingDriver,
    RankingStabilityStatus,
)
from backend.market_intelligence.sufficiency import sufficiency_requires_abstention

GENERIC_MARKET_LANGUAGE_PHRASES = (
    "good opportunities",
    "great opportunities",
    "great market",
    "robust ecosystem",
    "strong ecosystem",
    "strong market",
    "top destination",
    "vibrant ecosystem",
)

UNSUPPORTED_CITY_STEREOTYPE_PHRASES = (
    "booming",
    "coastal elite",
    "fast-growing",
    "hotbed",
    "mecca",
    "rust belt",
    "startup hub",
    "sunbelt",
    "talent magnet",
    "tech hub",
    "world-class",
)

PUBLIC_EVIDENCE_TERMS = (
    "canonical",
    "co-op",
    "count",
    "curated",
    "driver",
    "employer",
    "evidence",
    "fact",
    "hiring",
    "internship",
    "market",
    "metric",
    "observed",
    "posting",
    "program",
    "ranking",
    "score",
    "sector",
    "source",
    "unknown",
    "zero",
)


def build_ranking_report_explanation(
    top: ExplainableRankingItem | None,
    ranking_items: tuple[ExplainableRankingItem, ...],
    goal_definition: CareerGoalDefinition,
) -> str:
    """Build a deterministic, evidence-specific explanation for a ranking report."""

    if top is None:
        return "Ranking position: no imported markets are available for ranking."
    ordered_items = tuple(sorted(ranking_items, key=lambda item: (item.rank, item.market_key)))
    nearest_peer = _nearest_peer(top, ordered_items)
    return " ".join(
        (
            _ranking_position_clause(top, ordered_items, goal_definition, nearest_peer),
            _direct_evidence_clause(top, goal_definition),
            _proxy_evidence_clause(top),
            _comparative_driver_clause(
                "Strongest comparative advantage",
                top,
                nearest_peer,
                positive=True,
            ),
            _comparative_driver_clause(
                "Strongest comparative weakness",
                top,
                nearest_peer,
                positive=False,
            ),
            _missing_evidence_clause(top, goal_definition),
            _confidence_limitation_clause(top),
            _stability_limitation_clause(top),
        )
    )


def build_pairwise_comparison_explanation(
    left: ExplainableRankingItem,
    right: ExplainableRankingItem,
    winner: ExplainableRankingItem | None,
    *,
    sufficiency: EvidenceSufficiency,
    abstention_reason: str | None,
) -> str:
    """Build a deterministic, public-safe explanation for a pairwise comparison."""

    focus = winner or left
    peer = right if focus is left else left
    return " ".join(
        (
            _pairwise_position_clause(
                left,
                right,
                winner,
                sufficiency=sufficiency,
                abstention_reason=abstention_reason,
            ),
            _pairwise_evidence_basis_clause(left, right, direct=True),
            _pairwise_evidence_basis_clause(left, right, direct=False),
            _comparative_driver_clause(
                "Strongest comparative advantage",
                focus,
                peer,
                positive=True,
            ),
            _comparative_driver_clause(
                "Strongest comparative weakness",
                focus,
                peer,
                positive=False,
            ),
            _pairwise_missing_evidence_clause(left, right),
            _pairwise_confidence_limitation_clause(
                left,
                right,
                sufficiency=sufficiency,
                abstention_reason=abstention_reason,
            ),
            _stability_limitation_clause(left, right),
        )
    )


def explanation_language_rejections(text: str) -> tuple[str, ...]:
    """Return stable rejection codes for unsupported generic explanation language."""

    rejections: list[str] = []
    if is_generic_market_language(text):
        rejections.append("generic_market_language")
    if has_unsupported_city_stereotype(text):
        rejections.append("unsupported_city_stereotype")
    return tuple(rejections)


def is_generic_market_language(text: str) -> bool:
    normalized = normalize_public_text(text)
    if has_public_evidence_detail(text):
        return False
    return any(phrase in normalized for phrase in GENERIC_MARKET_LANGUAGE_PHRASES)


def has_unsupported_city_stereotype(text: str) -> bool:
    normalized = normalize_public_text(text)
    return any(phrase in normalized for phrase in UNSUPPORTED_CITY_STEREOTYPE_PHRASES)


def has_public_evidence_detail(text: str) -> bool:
    normalized = normalize_public_text(text)
    return bool(re.search(r"\d", normalized)) and any(
        term in normalized for term in PUBLIC_EVIDENCE_TERMS
    )


def normalize_public_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().casefold())


def _ranking_position_clause(
    item: ExplainableRankingItem,
    ranking_items: tuple[ExplainableRankingItem, ...],
    goal_definition: CareerGoalDefinition,
    nearest_peer: ExplainableRankingItem | None,
) -> str:
    count = len(ranking_items)
    driver = _top_driver(item)
    driver_text = (
        f" because {driver.label} contributes {driver.contribution:.4f}"
        if driver
        else " because no positive ranking driver is available"
    )
    margin_text = _score_margin_text(item, nearest_peer)
    if item.evidence_sufficiency is EvidenceSufficiency.NOT_SUPPORTED:
        return (
            "Ranking position: the backend abstains from naming a top "
            f"{goal_definition.label} market because {item.abstention_reason}; "
            f"{item.market_name} is listed at rank {item.rank} of {count} for "
            f"diagnostic ordering with score {item.score:.4f}; {margin_text}."
        )
    if item.evidence_sufficiency is EvidenceSufficiency.INSUFFICIENT_EVIDENCE:
        return (
            "Ranking position: the backend abstains from a firm "
            f"{goal_definition.label} ranking because {item.abstention_reason}; "
            f"{item.market_name} is listed at rank {item.rank} of {count} for "
            "diagnostic ordering with "
            f"score {item.score:.4f}; {margin_text}."
        )
    qualifier = "provisional " if item.is_provisional else ""
    return (
        f"Ranking position: {item.market_name} is the {qualifier}rank "
        f"{item.rank} of {count} for {goal_definition.label}{driver_text}; "
        f"{margin_text}."
    )


def _pairwise_position_clause(
    left: ExplainableRankingItem,
    right: ExplainableRankingItem,
    winner: ExplainableRankingItem | None,
    *,
    sufficiency: EvidenceSufficiency,
    abstention_reason: str | None,
) -> str:
    score_delta = abs(left.score - right.score)
    margin = (
        f"Score margin: score delta is {score_delta:.4f}; "
        f"{left.market_name} rank {left.rank}, {right.market_name} rank {right.rank}."
    )
    if sufficiency_requires_abstention(sufficiency):
        reason = abstention_reason or "evidence is insufficient for a normal winner"
        return (
            f"Ranking position: the backend does not name a winner between "
            f"{left.market_name} and {right.market_name} because {reason}. {margin}"
        )
    if winner is None:
        return (
            f"Ranking position: {left.market_name} and {right.market_name} are "
            f"tied after confidence-aware scoring; market-key ordering is only "
            f"diagnostic. {margin}"
        )
    loser = right if winner is left else left
    qualifier = "provisional " if sufficiency is EvidenceSufficiency.LIMITED_EVIDENCE else ""
    return (
        f"Ranking position: {winner.market_name} is the {qualifier}higher-ranked "
        f"market than {loser.market_name}. {margin}"
    )


def _direct_evidence_clause(
    item: ExplainableRankingItem,
    goal_definition: CareerGoalDefinition,
) -> str:
    classification = classify_goal_evidence(
        item.goal,
        (driver.code for driver in item.ranking_drivers),
    )
    direct_codes = frozenset(classification.direct_evidence_categories)
    direct_drivers = tuple(
        driver for driver in item.ranking_drivers if driver.code in direct_codes
    )
    if not direct_drivers:
        return (
            f"Direct evidence: no positive direct {goal_definition.label} "
            "driver is present in the ranking drivers."
        )
    details = "; ".join(
        _driver_evidence_text(item.goal, driver) for driver in direct_drivers[:3]
    )
    return f"Direct evidence: {details}."


def _proxy_evidence_clause(item: ExplainableRankingItem) -> str:
    classification = classify_goal_evidence(
        item.goal,
        (driver.code for driver in item.ranking_drivers),
    )
    proxy_codes = frozenset(classification.proxy_evidence_categories)
    proxy_drivers = tuple(
        driver for driver in item.ranking_drivers if driver.code in proxy_codes
    )
    if not proxy_drivers:
        return (
            "Proxy evidence: no positive proxy driver is present in the ranking "
            f"drivers; evidence basis is {classification.evidence_basis.value}."
        )
    details = "; ".join(
        _driver_evidence_text(item.goal, driver) for driver in proxy_drivers[:3]
    )
    return (
        f"Proxy evidence: {details}; evidence basis is "
        f"{classification.evidence_basis.value}."
    )


def _pairwise_evidence_basis_clause(
    left: ExplainableRankingItem,
    right: ExplainableRankingItem,
    *,
    direct: bool,
) -> str:
    prefix = "Direct evidence" if direct else "Proxy evidence"
    left_summary = _evidence_basis_summary(left, direct=direct)
    right_summary = _evidence_basis_summary(right, direct=direct)
    return (
        f"{prefix}: {left.market_name} uses {left_summary}; "
        f"{right.market_name} uses {right_summary}."
    )


def _evidence_basis_summary(item: ExplainableRankingItem, *, direct: bool) -> str:
    classification = classify_goal_evidence(
        item.goal,
        (driver.code for driver in item.ranking_drivers),
    )
    categories = (
        classification.direct_evidence_categories
        if direct
        else classification.proxy_evidence_categories
    )
    if not categories:
        return "no positive driver in this evidence class"
    return ", ".join(public_evidence_label(item.goal, category) for category in categories)


def _comparative_driver_clause(
    label: str,
    item: ExplainableRankingItem,
    peer: ExplainableRankingItem | None,
    *,
    positive: bool,
) -> str:
    if peer is None:
        return f"{label}: no peer market is available for comparative driver analysis."
    deltas = _driver_deltas(item, peer)
    candidates = (
        [delta for delta in deltas if delta[0] > 0]
        if positive
        else [delta for delta in deltas if delta[0] < 0]
    )
    if candidates:
        delta, code, driver = sorted(
            candidates,
            key=lambda entry: (
                -abs(entry[0]),
                entry[1],
            ),
        )[0]
        return (
            f"{label}: {driver.label} contributes {driver.contribution:.4f}, "
            f"{abs(delta):.4f} {'above' if positive else 'below'} "
            f"{peer.market_name}; {driver.evidence}"
        )
    fallback = _profile_weakness_text(item) if not positive else _top_driver_text(item)
    direction = "above" if positive else "below"
    return (
        f"{label}: no positive ranking driver is {direction} {peer.market_name}; "
        f"{fallback}"
    )


def _driver_deltas(
    item: ExplainableRankingItem,
    peer: ExplainableRankingItem,
) -> tuple[tuple[float, str, RankingDriver], ...]:
    item_drivers = {driver.code: driver for driver in item.ranking_drivers}
    peer_drivers = {driver.code: driver for driver in peer.ranking_drivers}
    fallback_drivers = item_drivers or peer_drivers
    result: list[tuple[float, str, RankingDriver]] = []
    for code in sorted(set(item_drivers) | set(peer_drivers)):
        item_driver = item_drivers.get(code)
        peer_driver = peer_drivers.get(code)
        driver = item_driver or peer_driver or fallback_drivers[code]
        result.append(
            (
                (item_driver.contribution if item_driver else 0.0)
                - (peer_driver.contribution if peer_driver else 0.0),
                code,
                driver,
            )
        )
    return tuple(result)


def _missing_evidence_clause(
    item: ExplainableRankingItem,
    goal_definition: CareerGoalDefinition,
) -> str:
    classification = classify_goal_evidence(
        item.goal,
        (driver.code for driver in item.ranking_drivers),
    )
    if classification.missing_direct_evidence_categories:
        missing = ", ".join(
            public_evidence_label(item.goal, category)
            for category in classification.missing_direct_evidence_categories[:3]
        )
        missing_text = f"{missing} are not present among positive drivers"
    else:
        missing_text = (
            f"no required direct {goal_definition.label} evidence category is "
            "missing from positive drivers"
        )
    return (
        f"Missing evidence: {missing_text}. "
        f"{_count_semantics_text(item.supporting_metrics)}"
    )


def _pairwise_missing_evidence_clause(
    left: ExplainableRankingItem,
    right: ExplainableRankingItem,
) -> str:
    return (
        "Missing evidence: "
        f"{left.market_name}: {_missing_direct_summary(left)}; "
        f"{right.market_name}: {_missing_direct_summary(right)}. "
        f"{left.market_name} {_count_semantics_text(left.supporting_metrics)} "
        f"{right.market_name} {_count_semantics_text(right.supporting_metrics)}"
    )


def _missing_direct_summary(item: ExplainableRankingItem) -> str:
    classification = classify_goal_evidence(
        item.goal,
        (driver.code for driver in item.ranking_drivers),
    )
    if not classification.missing_direct_evidence_categories:
        return "no required direct evidence category is missing from positive drivers"
    return ", ".join(
        public_evidence_label(item.goal, category)
        for category in classification.missing_direct_evidence_categories[:3]
    )


def _confidence_limitation_clause(item: ExplainableRankingItem) -> str:
    limitation = _first_limitation(item)
    if item.evidence_sufficiency is EvidenceSufficiency.COMPARISON_READY and not limitation:
        return (
            f"Confidence limitation: confidence is {item.confidence.value} and no "
            "sufficiency cap is applied."
        )
    if sufficiency_requires_abstention(item.evidence_sufficiency):
        reason = item.abstention_reason or "evidence is insufficient"
        detail = f" Limitation: {limitation}" if limitation else ""
        return (
            f"Confidence limitation: confidence is {item.confidence.value} with "
            f"{item.evidence_sufficiency.value}; a firm recommendation is blocked "
            f"because {reason}.{detail}"
        )
    detail = f"; limitation: {limitation}" if limitation else ""
    return (
        f"Confidence limitation: confidence is {item.confidence.value} with "
        f"{item.evidence_sufficiency.value}, so the ranking is provisional{detail}."
    )


def _pairwise_confidence_limitation_clause(
    left: ExplainableRankingItem,
    right: ExplainableRankingItem,
    *,
    sufficiency: EvidenceSufficiency,
    abstention_reason: str | None,
) -> str:
    confidence = _combined_confidence(left, right)
    if sufficiency_requires_abstention(sufficiency):
        reason = abstention_reason or "evidence is insufficient"
        return (
            f"Confidence limitation: comparison confidence is {confidence} with "
            f"{sufficiency.value}; a normal winner is blocked because {reason}."
        )
    if sufficiency is EvidenceSufficiency.LIMITED_EVIDENCE:
        return (
            f"Confidence limitation: comparison confidence is {confidence} with "
            "limited_evidence, so the comparison is provisional."
        )
    return (
        f"Confidence limitation: comparison confidence is {confidence}; no "
        "pairwise sufficiency cap is applied."
    )


def _stability_limitation_clause(*items: ExplainableRankingItem) -> str:
    status = _combined_stability_status(items)
    scenario_count = sum(
        len(item.grounding.stability_scenarios)
        for item in items
        if item.grounding is not None
    )
    if status is RankingStabilityStatus.UNSTABLE:
        return (
            "Stability limitation: backend stability status is unstable; scenario "
            f"analysis includes {scenario_count} public scenario result(s), so this "
            "ranking should not be treated as durable."
        )
    if status is RankingStabilityStatus.SENSITIVE:
        return (
            "Stability limitation: backend stability status is sensitive; scenario "
            f"analysis includes {scenario_count} public scenario result(s), so small "
            "evidence changes can affect the ranking."
        )
    if status is RankingStabilityStatus.STABLE:
        return (
            "Stability limitation: backend stability status is stable across the "
            f"{scenario_count} public scenario result(s) currently attached."
        )
    return (
        "Stability limitation: backend stability status is indeterminate, so "
        "scenario sensitivity has not established a durable recommendation."
    )


def _combined_stability_status(
    items: tuple[ExplainableRankingItem, ...],
) -> RankingStabilityStatus:
    order = {
        RankingStabilityStatus.UNSTABLE: 4,
        RankingStabilityStatus.SENSITIVE: 3,
        RankingStabilityStatus.INDETERMINATE: 2,
        RankingStabilityStatus.STABLE: 1,
    }
    statuses = [
        item.grounding.stability_status
        for item in items
        if item.grounding is not None
    ]
    if not statuses:
        return RankingStabilityStatus.INDETERMINATE
    return sorted(statuses, key=lambda status: (-order[status], status.value))[0]


def _nearest_peer(
    item: ExplainableRankingItem,
    ranking_items: tuple[ExplainableRankingItem, ...],
) -> ExplainableRankingItem | None:
    peers = tuple(peer for peer in ranking_items if peer.market_key != item.market_key)
    if not peers:
        return None
    return sorted(peers, key=lambda peer: (abs(item.score - peer.score), peer.market_key))[0]


def _score_margin_text(
    item: ExplainableRankingItem,
    nearest_peer: ExplainableRankingItem | None,
) -> str:
    if nearest_peer is None:
        return "score margin to nearest ranked peer is unavailable"
    return (
        f"score margin to nearest ranked peer {nearest_peer.market_name} is "
        f"{abs(item.score - nearest_peer.score):.4f}"
    )


def _driver_evidence_text(goal: object, driver: RankingDriver) -> str:
    return (
        f"{public_evidence_label(goal, driver.code)} via {driver.label} "
        f"({driver.contribution:.4f} contribution; {driver.evidence})"
    )


def _top_driver(item: ExplainableRankingItem) -> RankingDriver | None:
    return item.ranking_drivers[0] if item.ranking_drivers else None


def _top_driver_text(item: ExplainableRankingItem) -> str:
    driver = _top_driver(item)
    if driver is None:
        return "no positive ranking driver is available."
    return f"strongest driver remains {driver.label} at {driver.contribution:.4f}."


def _profile_weakness_text(item: ExplainableRankingItem) -> str:
    if item.weaknesses:
        return f"profile weakness: {item.weaknesses[0]}"
    if item.limitations:
        return f"limitation: {item.limitations[0]}"
    return "no public profile weakness is identified for this comparison."


def _first_limitation(item: ExplainableRankingItem) -> str | None:
    return item.limitations[0] if item.limitations else None


def _count_semantics_text(metrics: Mapping[str, int | float | str | None]) -> str:
    return (
        f"Count semantics: {_metric(metrics, 'unknown_fact_count')} unknown count "
        f"fact(s) and {_metric(metrics, 'observed_zero_fact_count')} observed zero "
        "count fact(s); unknown is not treated as zero."
    )


def _combined_confidence(
    left: ExplainableRankingItem,
    right: ExplainableRankingItem,
) -> str:
    order = {
        "limited": 1,
        "low": 2,
        "moderate": 3,
        "high": 4,
    }
    left_value = left.confidence.value
    right_value = right.confidence.value
    return left_value if order[left_value] <= order[right_value] else right_value


def _metric(metrics: Mapping[str, int | float | str | None], key: str) -> int:
    value = metrics.get(key)
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0
