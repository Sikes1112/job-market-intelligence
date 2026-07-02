"""Peer metro comparison logic for Layer 24B."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.geography.models import Region
from backend.policy.schemas import (
    PeerComparisonProfile,
    PeerMetricComparison,
    PeerMetroComparison,
    PolicyWarning,
    RegionalPolicyProfile,
)
from backend.shared.confidence import Confidence

_PEER_METRICS = (
    "opportunity_concentration_score",
    "early_career_access_score",
    "internship_pipeline_score",
    "employer_dependency_score",
    "sector_diversity_score",
    "talent_export_risk_score",
)


@dataclass(frozen=True, slots=True)
class PeerSelectionResult:
    comparisons: tuple[PeerMetroComparison, ...]
    warnings: tuple[PolicyWarning, ...]
    limitations: tuple[str, ...]


def build_peer_metro_comparisons(
    session: Session,
    *,
    target_profile: RegionalPolicyProfile,
    limit: int = 3,
) -> PeerSelectionResult:
    from backend.policy.service import PolicyIntelligenceService

    service = PolicyIntelligenceService(session)
    regions = tuple(
        session.execute(select(Region).order_by(Region.region_id)).scalars()
    )
    comparisons: list[PeerMetroComparison] = []
    warnings: list[PolicyWarning] = []
    for region in regions:
        if region.region_id == target_profile.region_id:
            continue
        try:
            peer = service.build_regional_policy_profile(region.region_id)
        except Exception:
            continue
        comparison = _comparison(target_profile, peer)
        if comparison.similarity_score is not None:
            comparisons.append(comparison)
    comparisons = sorted(
        comparisons,
        key=lambda item: (
            -(item.similarity_score or 0.0),
            item.peer_region_name,
            item.peer_region_id,
        ),
    )[:limit]
    limitations = [
        "Peer selection uses available canonical region scores and Layer 24A metrics.",
        "Population, wages, commuting patterns, and full industry inventories are not modeled.",
    ]
    if len(comparisons) < min(limit, 2):
        warnings.append(
            PolicyWarning(
                code="low_peer_comparison_coverage",
                severity="medium",
                message="Few comparable regions had enough structured signals for peer comparison.",
                public_interpretation=(
                    "Peer comparisons are directional and should be validated with "
                    "local regional context."
                ),
            )
        )
        limitations.append(
            "The peer set is limited because not enough regions have comparable data."
        )
    return PeerSelectionResult(
        comparisons=tuple(comparisons),
        warnings=tuple(warnings),
        limitations=tuple(limitations),
    )


def peer_comparison_profile_from_result(
    *,
    target_profile: RegionalPolicyProfile,
    result: PeerSelectionResult,
) -> PeerComparisonProfile:
    return PeerComparisonProfile(
        region_id=target_profile.region_id,
        region_name=target_profile.region_name,
        analysis_window=target_profile.analysis_window,
        peer_metro_comparisons=result.comparisons,
        warnings=tuple((*target_profile.warnings, *result.warnings)),
        confidence=target_profile.confidence,
        freshness=target_profile.freshness,
        source_summary=target_profile.source_summary,
        limitations=result.limitations,
        public_safe=True,
        public_safety=target_profile.public_safety,
    )


def _comparison(
    target: RegionalPolicyProfile,
    peer: RegionalPolicyProfile,
) -> PeerMetroComparison:
    metrics = tuple(_metric_comparison(metric_id, target, peer) for metric_id in _PEER_METRICS)
    comparable = tuple(item for item in metrics if item.comparison != "unknown")
    if not comparable:
        similarity_score = None
    else:
        diffs = [
            abs((item.target_value or 0.0) - (item.peer_value or 0.0))
            for item in comparable
            if item.target_value is not None and item.peer_value is not None
        ]
        similarity_score = round(max(0.0, min(1.0, 1.0 - (sum(diffs) / len(diffs)))), 4)
    stronger = tuple(
        item.metric_id for item in comparable if item.comparison == "target_stronger"
    )
    weaker = tuple(item.metric_id for item in comparable if item.comparison == "target_weaker")
    confidence = Confidence.LOW
    if similarity_score is not None and len(comparable) >= 3:
        confidence = Confidence.MEDIUM
    return PeerMetroComparison(
        peer_region_id=peer.region_id,
        peer_region_name=peer.region_name,
        similarity_score=similarity_score,
        similarity_rationale=(
            "Peer selected by similarity across available policy metrics including "
            "early-career access, internship pipeline, employer dependency, sector "
            "diversity, and talent export risk."
        ),
        metrics_compared=comparable,
        target_region_stronger=stronger,
        target_region_weaker=weaker,
        confidence=confidence,
        limitations=(
            "Similarity is based on available structured product signals.",
            "The peer set is not a full economic benchmark model.",
        ),
    )


def _metric_comparison(
    metric_id: str,
    target: RegionalPolicyProfile,
    peer: RegionalPolicyProfile,
) -> PeerMetricComparison:
    target_metric = getattr(target, metric_id)
    peer_metric = getattr(peer, metric_id)
    target_value = target_metric.score
    peer_value = peer_metric.score
    if target_value is None or peer_value is None:
        comparison = "unknown"
    elif abs(target_value - peer_value) < 0.08:
        comparison = "similar"
    elif metric_id in {
        "opportunity_concentration_score",
        "employer_dependency_score",
        "talent_export_risk_score",
    }:
        comparison = "target_stronger" if target_value < peer_value else "target_weaker"
    else:
        comparison = "target_stronger" if target_value > peer_value else "target_weaker"
    return PeerMetricComparison(
        metric_id=metric_id.replace("_score", ""),
        target_value=target_value,
        peer_value=peer_value,
        comparison=comparison,  # type: ignore[arg-type]
    )
