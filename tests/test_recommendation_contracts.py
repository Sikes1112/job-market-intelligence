from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.recommendations import (
    ManualVerificationCategory,
    RecommendationClaimSupport,
    RecommendationConfidenceSummary,
    RecommendationEvidenceBasis,
    RecommendationEvidenceReference,
    RecommendationEvidenceStrength,
    RecommendationExplanation,
    RecommendationFreshnessSummary,
    RecommendationGoalMode,
    RecommendationImportance,
    RecommendationManualVerificationItem,
    RecommendationProvenanceReference,
    RecommendationReason,
    RecommendationReasonCategory,
    RecommendationTarget,
    RecommendationTargetType,
    RecommendationTradeoff,
    RecommendationTradeoffCategory,
    RecommendationWeakness,
    RecommendationWeaknessCategory,
    recommendation_goal_mode_definitions,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = REPO_ROOT / "backend" / "recommendations"
NOW = datetime(2026, 5, 26, 12, tzinfo=UTC)


def _confidence() -> RecommendationConfidenceSummary:
    return RecommendationConfidenceSummary(
        confidence_level="high_confidence",
        confidence_score=0.86,
        confidence_status="current",
        confidence_ref="region_market_scores:greater_boston:confidence",
    )


def _freshness() -> RecommendationFreshnessSummary:
    return RecommendationFreshnessSummary(
        freshness_status="fresh",
        data_basis="real_derived",
        last_updated_at=NOW,
        freshness_expires_at=datetime(2026, 6, 26, 12, tzinfo=UTC),
        source_count=3,
        freshness_ref="output_metadata:greater_boston:freshness",
    )


def _provenance() -> RecommendationProvenanceReference:
    return RecommendationProvenanceReference(
        provenance_ref="fact_source_link:score_boston:v1",
        source_ref_id="source_ref:regional_dataset",
        source_refs=("source_ref:regional_dataset",),
    )


def _score_ref() -> RecommendationEvidenceReference:
    return RecommendationEvidenceReference(
        basis=RecommendationEvidenceBasis.STRUCTURED_SCORE,
        strength=RecommendationEvidenceStrength.STRONG,
        label="Objective opportunity score",
        reference_type="region_market_score",
        reference_id="region_market_scores:greater_boston:v1",
        provenance=_provenance(),
        confidence=_confidence(),
        freshness=_freshness(),
    )


def _coverage_ref() -> RecommendationEvidenceReference:
    return RecommendationEvidenceReference(
        basis=RecommendationEvidenceBasis.MARKET_COVERAGE,
        strength=RecommendationEvidenceStrength.MODERATE,
        label="Coverage metadata",
        reference_type="coverage_metadata",
        reference_id="coverage:greater_boston",
        coverage_warning_refs=("region_coverage_not_confident",),
    )


def _heuristic_ref() -> RecommendationEvidenceReference:
    return RecommendationEvidenceReference(
        basis=RecommendationEvidenceBasis.HEURISTIC_INFERENCE,
        strength=RecommendationEvidenceStrength.INFERRED,
        label="Lower competition thesis inferred from structured proxies",
    )


def test_goal_mode_vocabulary_and_metadata_are_complete() -> None:
    expected = {
        "maximize_entry_level_access",
        "maximize_prestige",
        "maximize_ai_cloud_concentration",
        "maximize_underrated_markets",
        "maximize_internship_coop_access",
        "maximize_lower_competition",
        "maximize_geographic_flexibility",
    }

    assert RecommendationGoalMode.values() == expected

    definitions = recommendation_goal_mode_definitions()
    assert {definition.goal_mode.value for definition in definitions} == expected
    assert all(definition.label for definition in definitions)
    assert all(definition.description for definition in definitions)
    assert all("weight" not in definition.model_dump() for definition in definitions)


def test_target_type_vocabulary_supports_required_recommendation_targets() -> None:
    assert RecommendationTargetType.values() >= {
        "region",
        "company",
        "company_category",
        "role_family",
        "market_strategy",
        "watchlist_item",
    }

    target = RecommendationTarget(
        target_type=RecommendationTargetType.REGION,
        target_id="greater_boston",
        display_label="Greater Boston",
    )

    assert target.target_type is RecommendationTargetType.REGION


def test_explanation_represents_fit_tradeoffs_weaknesses_and_manual_verification() -> None:
    reason = RecommendationReason(
        reason_category=RecommendationReasonCategory.REGION_FIT,
        label="Strong early-career fit",
        detail="Supported by app-owned region score metadata.",
        evidence_strength=RecommendationEvidenceStrength.STRONG,
        evidence_basis=(RecommendationEvidenceBasis.STRUCTURED_SCORE,),
        evidence_refs=(_score_ref(),),
    )
    data_strength = RecommendationReason(
        reason_category=RecommendationReasonCategory.DATA_STRENGTH,
        label="Fresh, source-linked score context",
        evidence_strength=RecommendationEvidenceStrength.STRONG,
        evidence_basis=(
            RecommendationEvidenceBasis.CONFIDENCE,
            RecommendationEvidenceBasis.FRESHNESS,
        ),
        evidence_refs=(
            RecommendationEvidenceReference(
                basis=RecommendationEvidenceBasis.CONFIDENCE,
                strength=RecommendationEvidenceStrength.STRONG,
                confidence=_confidence(),
            ),
            RecommendationEvidenceReference(
                basis=RecommendationEvidenceBasis.FRESHNESS,
                strength=RecommendationEvidenceStrength.STRONG,
                freshness=_freshness(),
            ),
        ),
    )
    tradeoff = RecommendationTradeoff(
        tradeoff_category=RecommendationTradeoffCategory.OPPORTUNITY_VS_COMPETITION,
        label="Broad opportunity but likely competition",
        positive_side="The structured score supports broad opportunity.",
        negative_side="Competition risk is an explicitly labeled heuristic inference.",
        importance=RecommendationImportance.HIGH,
        evidence_strength=RecommendationEvidenceStrength.INFERRED,
        evidence_basis=(
            RecommendationEvidenceBasis.STRUCTURED_SCORE,
            RecommendationEvidenceBasis.HEURISTIC_INFERENCE,
        ),
        support=RecommendationClaimSupport.INFERRED,
        evidence_refs=(_score_ref(), _heuristic_ref()),
    )
    weakness = RecommendationWeakness(
        weakness_category=RecommendationWeaknessCategory.COVERAGE_GAP,
        label="Coverage is not Tier 1",
        detail="Coverage metadata should be treated as directional.",
        evidence_strength=RecommendationEvidenceStrength.MODERATE,
        evidence_basis=(RecommendationEvidenceBasis.MARKET_COVERAGE,),
        evidence_refs=(_coverage_ref(),),
    )
    manual_check = RecommendationManualVerificationItem(
        verification_category=ManualVerificationCategory.CURRENT_JOB_POSTINGS,
        label="Verify current postings",
        question="Do currently posted roles still match the target role family?",
        rationale="Posting counts can change faster than durable region metadata.",
        importance=RecommendationImportance.HIGH,
        evidence_strength=RecommendationEvidenceStrength.STRONG,
        evidence_basis=(RecommendationEvidenceBasis.FRESHNESS,),
        evidence_refs=(
            RecommendationEvidenceReference(
                basis=RecommendationEvidenceBasis.FRESHNESS,
                strength=RecommendationEvidenceStrength.STRONG,
                freshness=_freshness(),
            ),
        ),
    )

    explanation = RecommendationExplanation(
        target=RecommendationTarget(
            target_type=RecommendationTargetType.REGION,
            target_id="greater_boston",
            display_label="Greater Boston",
        ),
        goal_mode=RecommendationGoalMode.MAXIMIZE_ENTRY_LEVEL_ACCESS,
        headline="Greater Boston fits this goal with caveats",
        fit_reasons=(reason,),
        data_strengths=(data_strength,),
        tradeoffs=(tradeoff,),
        weaknesses=(weakness,),
        manual_verification=(manual_check,),
        evidence_refs=(_score_ref(), _coverage_ref()),
        confidence_summary=_confidence(),
        freshness_summary=_freshness(),
        provenance_refs=(_provenance(),),
        coverage_warnings=("region_coverage_not_confident",),
    )

    assert explanation.fit_reasons[0].reason_category is RecommendationReasonCategory.REGION_FIT
    assert explanation.tradeoffs[0].positive_side.startswith("The structured score")
    assert explanation.tradeoffs[0].support is RecommendationClaimSupport.INFERRED
    assert (
        explanation.weaknesses[0].weakness_category
        is RecommendationWeaknessCategory.COVERAGE_GAP
    )
    assert (
        explanation.manual_verification[0].verification_category
        is ManualVerificationCategory.CURRENT_JOB_POSTINGS
    )
    assert explanation.confidence_summary.confidence_level == "high_confidence"
    assert explanation.freshness_summary.freshness_status == "fresh"
    assert explanation.provenance_refs[0].source_ref_id == "source_ref:regional_dataset"


def test_evidence_strength_basis_and_target_types_are_validated() -> None:
    with pytest.raises(ValidationError):
        RecommendationTarget(target_type="city", target_id="greater_boston")

    with pytest.raises(ValidationError):
        RecommendationEvidenceReference(
            basis=RecommendationEvidenceBasis.STRUCTURED_SCORE,
            strength="excellent",
            reference_id="score:1",
        )

    with pytest.raises(ValidationError):
        RecommendationEvidenceReference(
            basis="raw_ai_text",
            strength=RecommendationEvidenceStrength.STRONG,
            reference_id="score:1",
        )


def test_tradeoff_contract_carries_upside_downside_importance_and_basis() -> None:
    tradeoff = RecommendationTradeoff(
        tradeoff_category=RecommendationTradeoffCategory.PRESTIGE_VS_ENTRY_LEVEL_ACCESS,
        label="High prestige but weaker entry-level accessibility",
        positive_side="Prestige metadata can support a high-brand target.",
        negative_side="Entry-level access may be weaker and should be checked.",
        importance=RecommendationImportance.MEDIUM,
        evidence_strength=RecommendationEvidenceStrength.MODERATE,
        evidence_basis=(RecommendationEvidenceBasis.COMPANY_METADATA,),
        evidence_refs=(
            RecommendationEvidenceReference(
                basis=RecommendationEvidenceBasis.COMPANY_METADATA,
                strength=RecommendationEvidenceStrength.MODERATE,
                reference_type="company",
                reference_id="company:example",
            ),
        ),
    )

    assert tradeoff.positive_side
    assert tradeoff.negative_side
    assert tradeoff.importance is RecommendationImportance.MEDIUM
    assert tradeoff.support is RecommendationClaimSupport.DIRECT


def test_heuristic_claims_must_be_explicitly_marked_inferred() -> None:
    with pytest.raises(ValidationError):
        RecommendationTradeoff(
            tradeoff_category=RecommendationTradeoffCategory.LOWER_COMPETITION_VS_ROLE_VOLUME,
            label="Lower competition but fewer roles",
            positive_side="May be less crowded.",
            negative_side="May have fewer total roles.",
            importance=RecommendationImportance.MEDIUM,
            evidence_strength=RecommendationEvidenceStrength.INFERRED,
            evidence_basis=(RecommendationEvidenceBasis.HEURISTIC_INFERENCE,),
        )

    with pytest.raises(ValidationError):
        RecommendationReason(
            reason_category=RecommendationReasonCategory.GOAL_ALIGNMENT,
            label="Looks underrated",
            evidence_strength=RecommendationEvidenceStrength.INFERRED,
            evidence_basis=(RecommendationEvidenceBasis.STRUCTURED_SCORE,),
            support=RecommendationClaimSupport.INFERRED,
            evidence_refs=(_score_ref(),),
        )

    valid = RecommendationReason(
        reason_category=RecommendationReasonCategory.GOAL_ALIGNMENT,
        label="Looks underrated",
        evidence_strength=RecommendationEvidenceStrength.INFERRED,
        evidence_basis=(RecommendationEvidenceBasis.HEURISTIC_INFERENCE,),
        support=RecommendationClaimSupport.INFERRED,
    )

    assert valid.support is RecommendationClaimSupport.INFERRED


def test_free_floating_claims_and_empty_explanations_fail_validation() -> None:
    with pytest.raises(ValidationError):
        RecommendationEvidenceReference(
            basis=RecommendationEvidenceBasis.STRUCTURED_SCORE,
            strength=RecommendationEvidenceStrength.STRONG,
            label="Score with no app ref",
        )

    with pytest.raises(ValidationError):
        RecommendationReason(
            reason_category=RecommendationReasonCategory.REGION_FIT,
            label="Great market",
            detail="Free text only is not enough.",
            evidence_strength=RecommendationEvidenceStrength.STRONG,
            evidence_basis=(RecommendationEvidenceBasis.STRUCTURED_SCORE,),
        )

    with pytest.raises(ValidationError):
        RecommendationExplanation(
            target=RecommendationTarget(
                target_type=RecommendationTargetType.REGION,
                target_id="greater_boston",
            ),
            headline="Free-text-only explanation",
        )


def test_recommendation_contract_package_has_no_runtime_or_ai_dependencies() -> None:
    forbidden_fragments = (
        "openai",
        "anthropic",
        "transformers",
        "requests",
        "httpx",
        "selenium",
        "playwright",
        "sqlalchemy",
        "fastapi",
        "backend.api",
        "backend.scoring.service",
        "backend.personalization.service",
        "backend.refresh",
        "backend.provenance.repository",
    )
    violations: dict[str, list[str]] = {}
    for path in PACKAGE_ROOT.glob("*.py"):
        text = path.read_text()
        bad = [fragment for fragment in forbidden_fragments if fragment in text]
        if bad:
            violations[str(path.relative_to(REPO_ROOT))] = bad

    assert not violations, violations
