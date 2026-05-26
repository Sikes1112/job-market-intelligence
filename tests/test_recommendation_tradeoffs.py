from __future__ import annotations

from backend.recommendations.goal_modes import RecommendationScoreComponent
from backend.recommendations.models import (
    ManualVerificationCategory,
    RecommendationClaimSupport,
    RecommendationEvidenceBasis,
    RecommendationEvidenceReference,
    RecommendationEvidenceStrength,
    RecommendationExplanation,
    RecommendationImportance,
    RecommendationManualVerificationItem,
    RecommendationTarget,
    RecommendationTargetType,
    RecommendationTradeoff,
    RecommendationTradeoffCategory,
)
from backend.recommendations.tradeoffs import (
    TradeoffSignal,
    TradeoffSignalStatus,
    generate_controlled_tradeoffs,
)


def _ref(
    basis: RecommendationEvidenceBasis = RecommendationEvidenceBasis.STRUCTURED_SCORE,
) -> RecommendationEvidenceReference:
    return RecommendationEvidenceReference(
        basis=basis,
        strength=RecommendationEvidenceStrength.MODERATE,
        label=f"{basis.value} evidence",
        reference_type="test_reference",
        reference_id=f"{basis.value}:reference",
    )


def _signal(
    component: RecommendationScoreComponent,
    value: float,
    *,
    basis: RecommendationEvidenceBasis = RecommendationEvidenceBasis.STRUCTURED_SCORE,
    is_proxy: bool = False,
    inferred: bool = False,
) -> TradeoffSignal:
    return TradeoffSignal(
        component=component,
        value=value,
        status=TradeoffSignalStatus.PROXY if is_proxy else TradeoffSignalStatus.USED,
        evidence_basis=(
            (basis, RecommendationEvidenceBasis.HEURISTIC_INFERENCE)
            if inferred and basis is not RecommendationEvidenceBasis.HEURISTIC_INFERENCE
            else (basis,)
        ),
        evidence_refs=(
            ()
            if basis is RecommendationEvidenceBasis.HEURISTIC_INFERENCE
            else (_ref(basis),)
        ),
        is_proxy=is_proxy,
        inferred=inferred,
    )


def _missing(component: RecommendationScoreComponent) -> TradeoffSignal:
    return TradeoffSignal(
        component=component,
        value=None,
        status=TradeoffSignalStatus.MISSING,
        evidence_basis=(RecommendationEvidenceBasis.MISSING_DATA,),
    )


def test_broad_opportunity_and_weak_lower_competition_proxy_generates_tradeoff() -> None:
    tradeoffs = generate_controlled_tradeoffs(
        {
            RecommendationScoreComponent.COMPANY_DENSITY: _signal(
                RecommendationScoreComponent.COMPANY_DENSITY,
                0.9,
                basis=RecommendationEvidenceBasis.REGION_METADATA,
            ),
            RecommendationScoreComponent.LOWER_COMPETITION_PROXY: _signal(
                RecommendationScoreComponent.LOWER_COMPETITION_PROXY,
                0.2,
                basis=RecommendationEvidenceBasis.HEURISTIC_INFERENCE,
                is_proxy=True,
                inferred=True,
            ),
        }
    )

    tradeoff = next(
        item
        for item in tradeoffs
        if item.tradeoff_category
        is RecommendationTradeoffCategory.OPPORTUNITY_VS_COMPETITION
    )
    assert isinstance(tradeoff, RecommendationTradeoff)
    assert tradeoff.support is RecommendationClaimSupport.INFERRED
    assert RecommendationEvidenceBasis.HEURISTIC_INFERENCE in tradeoff.evidence_basis


def test_high_prestige_and_weak_entry_level_access_generates_direct_tradeoff() -> None:
    tradeoffs = generate_controlled_tradeoffs(
        {
            RecommendationScoreComponent.PRESTIGE_DENSITY: _signal(
                RecommendationScoreComponent.PRESTIGE_DENSITY,
                0.92,
                basis=RecommendationEvidenceBasis.COMPANY_METADATA,
            ),
            RecommendationScoreComponent.ENTRY_LEVEL_ACCESS: _signal(
                RecommendationScoreComponent.ENTRY_LEVEL_ACCESS,
                0.25,
                basis=RecommendationEvidenceBasis.STRUCTURED_SCORE,
            ),
        }
    )

    tradeoff = next(
        item
        for item in tradeoffs
        if item.tradeoff_category
        is RecommendationTradeoffCategory.PRESTIGE_VS_ENTRY_LEVEL_ACCESS
    )
    assert tradeoff.support is RecommendationClaimSupport.DIRECT
    assert tradeoff.evidence_refs
    assert RecommendationEvidenceBasis.HEURISTIC_INFERENCE not in tradeoff.evidence_basis


def test_ai_cloud_proxy_and_narrow_company_universe_generates_controlled_tradeoff() -> None:
    tradeoffs = generate_controlled_tradeoffs(
        {
            RecommendationScoreComponent.AI_CLOUD_CONCENTRATION: _signal(
                RecommendationScoreComponent.AI_CLOUD_CONCENTRATION,
                1.0,
                basis=RecommendationEvidenceBasis.COMPANY_METADATA,
                is_proxy=True,
            ),
            RecommendationScoreComponent.COMPANY_DENSITY: _signal(
                RecommendationScoreComponent.COMPANY_DENSITY,
                0.2,
                basis=RecommendationEvidenceBasis.REGION_METADATA,
            ),
        }
    )

    tradeoff = next(
        item
        for item in tradeoffs
        if item.tradeoff_category
        is RecommendationTradeoffCategory.AI_CLOUD_CONCENTRATION_VS_COMPANY_UNIVERSE
    )
    assert "AI/cloud concentration" in tradeoff.positive_side
    assert "company universe" in tradeoff.negative_side
    assert tradeoff.support is RecommendationClaimSupport.INFERRED


def test_weak_or_missing_evidence_quality_generates_data_quality_tradeoff() -> None:
    tradeoffs = generate_controlled_tradeoffs(
        {
            RecommendationScoreComponent.ENTRY_LEVEL_ACCESS: _signal(
                RecommendationScoreComponent.ENTRY_LEVEL_ACCESS,
                0.85,
            ),
            RecommendationScoreComponent.MARKET_COVERAGE: _signal(
                RecommendationScoreComponent.MARKET_COVERAGE,
                0.2,
                basis=RecommendationEvidenceBasis.MARKET_COVERAGE,
            ),
            RecommendationScoreComponent.FRESHNESS: _missing(
                RecommendationScoreComponent.FRESHNESS
            ),
        },
        final_score=0.7,
    )

    tradeoff = next(
        item
        for item in tradeoffs
        if item.tradeoff_category is RecommendationTradeoffCategory.DATA_QUALITY
    )
    assert tradeoff.support is RecommendationClaimSupport.DIRECT
    assert RecommendationEvidenceBasis.MISSING_DATA in tradeoff.evidence_basis


def test_manual_verification_can_generate_data_quality_tradeoff_from_existing_items() -> None:
    explanation = RecommendationExplanation(
        target=RecommendationTarget(
            target_type=RecommendationTargetType.REGION,
            target_id="region_a",
        ),
        manual_verification=(
            RecommendationManualVerificationItem(
                verification_category=ManualVerificationCategory.SOURCE_CONFIRMATION,
                label="Verify source evidence",
                question="Which sources support this recommendation?",
                importance=RecommendationImportance.HIGH,
                evidence_strength=RecommendationEvidenceStrength.MISSING,
                evidence_basis=(RecommendationEvidenceBasis.MISSING_DATA,),
            ),
        ),
    )
    tradeoffs = generate_controlled_tradeoffs(
        {
            RecommendationScoreComponent.ENTRY_LEVEL_ACCESS: _signal(
                RecommendationScoreComponent.ENTRY_LEVEL_ACCESS,
                0.9,
            )
        },
        explanation=explanation,
    )

    assert any(
        item.tradeoff_category is RecommendationTradeoffCategory.DATA_QUALITY
        for item in tradeoffs
    )


def test_unsupported_sector_vs_consumer_tech_narrative_is_not_invented() -> None:
    tradeoffs = generate_controlled_tradeoffs(
        {
            RecommendationScoreComponent.COMPANY_DENSITY: _signal(
                RecommendationScoreComponent.COMPANY_DENSITY,
                0.8,
                basis=RecommendationEvidenceBasis.REGION_METADATA,
            ),
            RecommendationScoreComponent.AI_CLOUD_CONCENTRATION: _signal(
                RecommendationScoreComponent.AI_CLOUD_CONCENTRATION,
                0.4,
                basis=RecommendationEvidenceBasis.COMPANY_METADATA,
                is_proxy=True,
            ),
        }
    )

    assert all(
        item.tradeoff_category
        is not RecommendationTradeoffCategory.SECTOR_STRENGTH_VS_CONSUMER_TECH
        for item in tradeoffs
    )
    rendered = " ".join(
        f"{item.label} {item.positive_side} {item.negative_side}"
        for item in tradeoffs
    )
    assert "consumer tech" not in rendered.casefold()
