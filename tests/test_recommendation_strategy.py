from __future__ import annotations

from datetime import timedelta

import pytest
from pydantic import ValidationError

from backend.outputs.payloads import OutputPayloadMetadata
from backend.recommendations.models import (
    ManualVerificationCategory,
    RecommendationClaimSupport,
    RecommendationEvidenceBasis,
    RecommendationEvidenceStrength,
    RecommendationGoalMode,
)
from backend.recommendations.ranking import (
    RecommendationRankingResult,
    rank_company_recommendations,
    rank_region_recommendations,
)
from backend.recommendations.strategy import (
    MarketStrategyPlan,
    StrategyTimingCategory,
    StrategyTimingGuidance,
    StrategyWarningCategory,
    generate_market_strategy_plan,
)
from tests.test_recommendation_ranking import (
    NOW,
    _company_output,
    _region_output,
    _source_summary,
)


def _fresh_source_map(*region_ids: str):
    return {region_id: _source_summary("region", region_id) for region_id in region_ids}


def _company_source_map(*company_ids: str):
    return {company_id: _source_summary("company", company_id) for company_id in company_ids}


def _stale_region(region_id: str, display_name: str):
    output = _region_output(
        region_id=region_id,
        display_name=display_name,
        early_access=0.72,
        prestige=0.35,
        present_companies=7,
        internships=5,
    )
    return output.model_copy(
        update={
            "metadata": OutputPayloadMetadata(
                state="stale",
                freshness_expires_at=NOW - timedelta(days=1),
                source_versions={"region_version": 1},
                warnings=[],
            )
        }
    )


def _entry_region_rankings() -> RecommendationRankingResult:
    primary = _region_output(
        region_id="primary_access",
        display_name="Primary Access",
        early_access=0.92,
        prestige=0.25,
        present_companies=9,
        internships=9,
    )
    secondary = _region_output(
        region_id="secondary_access",
        display_name="Secondary Access",
        early_access=0.68,
        prestige=0.35,
        present_companies=8,
        internships=4,
    )
    stale = _stale_region("stale_watchlist", "Stale Watchlist")
    return rank_region_recommendations(
        [stale, secondary, primary],
        goal_mode=RecommendationGoalMode.MAXIMIZE_ENTRY_LEVEL_ACCESS,
        source_summaries=_fresh_source_map("primary_access", "secondary_access"),
    )


def test_strategy_plan_from_ranked_regions_selects_sections_and_sources() -> None:
    rankings = _entry_region_rankings()

    plan = generate_market_strategy_plan(rankings, max_primary_regions=1)

    assert isinstance(plan, MarketStrategyPlan)
    assert plan.goal_mode is RecommendationGoalMode.MAXIMIZE_ENTRY_LEVEL_ACCESS
    assert plan.primary_region_targets[0].target.target_id == "primary_access"
    assert plan.secondary_region_targets
    assert any(item.target.target_id == "stale_watchlist" for item in plan.watchlist_items)
    assert {source.target.target_id for source in plan.source_recommendations} == {
        item.target.target_id for item in rankings.ranked_recommendations
    }
    assert all(
        target.source_recommendation_ids
        for target in (
            *plan.primary_region_targets,
            *plan.secondary_region_targets,
            *plan.watchlist_items,
        )
    )
    assert plan.timing_guidance
    assert plan.manual_verification_checklist.items
    assert plan.evidence_warnings


def test_watchlist_items_capture_stale_or_missing_evidence_and_revisit_flag() -> None:
    plan = generate_market_strategy_plan(_entry_region_rankings(), max_primary_regions=1)

    watchlist = next(
        item for item in plan.watchlist_items if item.target.target_id == "stale_watchlist"
    )

    assert watchlist.revisit_after_refresh is True
    assert "verify" in watchlist.what_to_verify.casefold()
    assert watchlist.source_recommendation_ids
    assert watchlist.evidence_refs or RecommendationEvidenceBasis.MISSING_DATA in (
        watchlist.evidence_basis
    )
    assert any(
        warning.warning_category
        in {StrategyWarningCategory.FRESHNESS, StrategyWarningCategory.PROVENANCE}
        for warning in plan.evidence_warnings
    )


def test_lower_competition_mode_selects_fallback_from_ranked_outputs() -> None:
    high_competition = _region_output(
        region_id="high_competition",
        display_name="High Competition",
        early_access=0.7,
        prestige=0.9,
        present_companies=18,
        internships=2,
    )
    lower_competition = _region_output(
        region_id="lower_competition",
        display_name="Lower Competition",
        early_access=0.68,
        prestige=0.2,
        present_companies=4,
        internships=3,
    )
    backup = _region_output(
        region_id="backup_lower_competition",
        display_name="Backup Lower Competition",
        early_access=0.62,
        prestige=0.35,
        present_companies=7,
        internships=3,
    )
    rankings = rank_region_recommendations(
        [high_competition, lower_competition, backup],
        goal_mode=RecommendationGoalMode.MAXIMIZE_LOWER_COMPETITION,
        source_summaries=_fresh_source_map(
            "high_competition",
            "lower_competition",
            "backup_lower_competition",
        ),
    )

    plan = generate_market_strategy_plan(rankings, max_primary_regions=1)

    assert plan.primary_region_targets[0].target.target_id == "lower_competition"
    assert plan.fallback_region_targets
    assert plan.fallback_region_targets[0].target.target_id == "backup_lower_competition"
    assert any(
        warning.warning_category is StrategyWarningCategory.PROXY
        for warning in plan.evidence_warnings
    )


def test_internship_mode_adds_internship_verification_and_timing() -> None:
    rankings = rank_region_recommendations(
        [
            _region_output(
                region_id="internship_market",
                display_name="Internship Market",
                early_access=0.8,
                prestige=0.4,
                present_companies=8,
                internships=8,
            )
        ],
        goal_mode=RecommendationGoalMode.MAXIMIZE_INTERNSHIP_COOP_ACCESS,
        source_summaries=_fresh_source_map("internship_market"),
    )

    plan = generate_market_strategy_plan(rankings)

    assert any(
        item.timing_category is StrategyTimingCategory.INTERNSHIP_COOP_CHECK
        for item in plan.timing_guidance
    )
    assert ManualVerificationCategory.INTERNSHIP_COOP_ACCESS in {
        entry.item.verification_category
        for entry in plan.manual_verification_checklist.items
    }


def test_ai_cloud_company_categories_and_role_guidance_are_inferred_when_proxy() -> None:
    region_rankings = rank_region_recommendations(
        [
            _region_output(
                region_id="ai_region",
                display_name="AI Region",
                early_access=0.7,
                prestige=0.5,
                present_companies=9,
                internships=3,
            )
        ],
        goal_mode=RecommendationGoalMode.MAXIMIZE_AI_CLOUD_CONCENTRATION,
        source_summaries=_fresh_source_map("ai_region"),
    )
    company_rankings = rank_company_recommendations(
        [
            _company_output(
                company_id="ai_company",
                company_name="AI Company",
                sector_primary="ai",
                prestige=0.68,
                entry_access=0.65,
                region_count=1,
            ),
            _company_output(
                company_id="tools_company",
                company_name="Tools Company",
                sector_primary="developer_tools",
                prestige=0.78,
                entry_access=0.58,
                region_count=4,
            ),
        ],
        goal_mode=RecommendationGoalMode.MAXIMIZE_AI_CLOUD_CONCENTRATION,
        source_summaries=_company_source_map("ai_company", "tools_company"),
    )

    plan = generate_market_strategy_plan(
        region_rankings,
        company_rankings=company_rankings,
    )

    assert [target.target.target_id for target in plan.company_targets] == [
        item.target.target_id for item in company_rankings.ranked_recommendations
    ]
    category = plan.company_category_targets[0]
    assert category.target.target_id == "ai_cloud_oriented_companies"
    assert category.support is RecommendationClaimSupport.INFERRED
    assert RecommendationEvidenceBasis.HEURISTIC_INFERENCE in category.evidence_basis
    assert plan.role_family_targets
    assert all(
        role.support is RecommendationClaimSupport.INFERRED
        and role.evidence_strength is RecommendationEvidenceStrength.INFERRED
        for role in plan.role_family_targets
    )
    assert any(
        entry.item.label == "Verify role-family fit"
        for entry in plan.manual_verification_checklist.items
    )


def test_geographic_flexibility_keeps_location_claims_heuristic() -> None:
    region_rankings = rank_region_recommendations(
        [
            _region_output(
                region_id="flex_region",
                display_name="Flex Region",
                early_access=0.7,
                prestige=0.4,
                present_companies=9,
                internships=3,
            )
        ],
        goal_mode=RecommendationGoalMode.MAXIMIZE_GEOGRAPHIC_FLEXIBILITY,
        source_summaries=_fresh_source_map("flex_region"),
    )

    plan = generate_market_strategy_plan(region_rankings)

    location_timing = next(
        item
        for item in plan.timing_guidance
        if item.timing_category is StrategyTimingCategory.LOCATION_REQUIREMENTS_CHECK
    )
    assert location_timing.support is RecommendationClaimSupport.INFERRED
    assert RecommendationEvidenceBasis.HEURISTIC_INFERENCE in location_timing.evidence_basis
    assert ManualVerificationCategory.LOCATION_REQUIREMENTS in {
        entry.item.verification_category
        for entry in plan.manual_verification_checklist.items
    }


def test_company_targets_are_not_invented_when_company_rankings_missing() -> None:
    rankings = _entry_region_rankings()

    plan = generate_market_strategy_plan(rankings)

    assert plan.company_targets == ()
    assert plan.company_category_targets == ()
    assert any(
        warning.label == "Company rankings were not supplied"
        for warning in plan.evidence_warnings
    )


def test_strategy_validation_rejects_free_floating_advice() -> None:
    with pytest.raises(ValidationError):
        StrategyTimingGuidance(
            timing_category=StrategyTimingCategory.PRIORITIZE_HIGH_FIT,
            label="Unsupported advice",
            guidance="Apply immediately.",
            source_recommendation_ids=(),
            evidence_strength=RecommendationEvidenceStrength.MODERATE,
            evidence_basis=(RecommendationEvidenceBasis.STRUCTURED_SCORE,),
        )

    with pytest.raises(ValidationError):
        StrategyTimingGuidance(
            timing_category=StrategyTimingCategory.PRIORITIZE_HIGH_FIT,
            label="Unsupported structured advice",
            guidance="Apply immediately.",
            source_recommendation_ids=("region:a:rank:1",),
            evidence_strength=RecommendationEvidenceStrength.MODERATE,
            evidence_basis=(RecommendationEvidenceBasis.STRUCTURED_SCORE,),
        )
