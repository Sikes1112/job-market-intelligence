from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from backend.api.metadata import (
    ApiDataBasis,
    ApiFreshnessStatus,
    FreshnessSourceSummary,
)
from backend.api.search import SourceDetail, SourceExplanationResponse
from backend.geography.market_coverage import build_region_coverage_metadata
from backend.outputs.payloads import (
    CompanyOutput,
    CompanyOutputBody,
    CompanyRegionEntryLevelEntry,
    CompanyRegionHiringEntry,
    CompanyRegionPresenceEntry,
    EntryLevelSummary,
    Mag7Summary,
    MajorTechSummary,
    OutputPayloadMetadata,
    RegionOutput,
    RegionOutputBody,
    RegionScoresPayload,
    RegionSummary,
)
from backend.recommendations.goal_modes import (
    RecommendationScoreComponent,
    goal_mode_weight_profile,
)
from backend.recommendations.models import (
    ManualVerificationCategory,
    RecommendationClaimSupport,
    RecommendationEvidenceBasis,
    RecommendationExplanation,
    RecommendationGoalMode,
    RecommendationTargetType,
    RecommendationTradeoffCategory,
)
from backend.recommendations.ranking import (
    RecommendationRankingResult,
    ResolvedScoreComponent,
    ScoreComponentStatus,
    rank_company_recommendations,
    rank_region_recommendations,
)

NOW = datetime(2026, 5, 26, 12, tzinfo=UTC)


def _source_summary(subject_type: str, subject_id: str) -> SourceExplanationResponse:
    return SourceExplanationResponse(
        subject_type=subject_type,
        subject_id=subject_id,
        freshness=FreshnessSourceSummary(
            freshness_status=ApiFreshnessStatus.FRESH,
            data_basis=ApiDataBasis.REAL_IMPORTED,
            last_collected_at=NOW,
            source_count=1,
        ),
        sources=[
            SourceDetail(
                source_id=f"source_{subject_id}",
                source_type="company_official",
                source_name="Official source",
                collected_at=NOW,
                freshness_status=ApiFreshnessStatus.FRESH,
                data_basis=ApiDataBasis.REAL_IMPORTED,
            )
        ],
    )


def _coverage():
    return build_region_coverage_metadata(
        present_company_count=10,
        presence_record_count=10,
        hiring_record_count=7,
        entry_level_record_count=5,
        has_region_score=True,
        freshness_expires_at_known=True,
        freshness_is_stale=False,
        source_count=2,
        source_data_basis="real_imported",
        source_evidence_loaded=True,
    )


def _region_output(
    *,
    region_id: str,
    display_name: str,
    early_access: float,
    prestige: float,
    present_companies: int,
    internships: int,
    coops: int = 1,
    major_tech: int = 1,
    mag7: int = 0,
) -> RegionOutput:
    return RegionOutput(
        region=RegionOutputBody(
            region_id=region_id,
            display_name=display_name,
            region_type="greater_region",
            coverage=_coverage(),
            summary=RegionSummary(
                eligible_company_count=present_companies,
                major_tech_count=major_tech,
                mag7_count=mag7,
                present_company_count=present_companies,
                currently_hiring_company_count=max(1, present_companies // 2),
            ),
            scores=RegionScoresPayload(
                structural_ecosystem_score=prestige,
                objective_opportunity_score=(early_access + prestige) / 2,
                raw_total_score=(early_access + prestige) / 2,
                early_career_accessibility_score=early_access,
                live_market_score=0.7,
                general_density_score=min(present_companies / 20, 1.0),
                tech_market_density_score=prestige,
                score_ruleset_version="marketscore_v1",
            ),
            entry_level_summary=EntryLevelSummary(
                internship_count_total=internships,
                coop_count_total=coops,
                entry_level_full_time_count_total=internships + coops,
                formal_early_career_program_count=1,
                average_entry_level_access_score=early_access,
                pairs_with_entry_level_access=max(1, internships // 2),
            ),
            major_tech_summary=MajorTechSummary(count=major_tech, company_ids=["major_a"]),
            mag7_summary=Mag7Summary(count=mag7, company_ids=["mag7_a"] if mag7 else []),
        ),
        metadata=OutputPayloadMetadata(
            state="fresh",
            freshness_expires_at=NOW + timedelta(days=30),
            source_versions={"region_version": 1},
            warnings=[],
        ),
    )


def _company_output(
    *,
    company_id: str,
    company_name: str,
    sector_primary: str,
    prestige: float,
    entry_access: float,
    region_count: int,
) -> CompanyOutput:
    coverage = _coverage()
    regions_present = [
        CompanyRegionPresenceEntry(
            region_id=f"region_{index}",
            region_display_name=f"Region {index}",
            presence_status="present",
            presence_basis="office_plus_hiring",
            presence_confidence="high_confidence",
            coverage=coverage,
        )
        for index in range(region_count)
    ]
    return CompanyOutput(
        company=CompanyOutputBody(
            company_id=company_id,
            company_name=company_name,
            normalized_company_name=company_name.casefold(),
            sector_primary=sector_primary,
            sector_secondary="cloud" if sector_primary == "ai" else None,
            eligibility_status="eligible",
            classification_confidence="high_confidence",
            is_major_tech=prestige >= 0.7,
            prestige_score=prestige,
            regions_present=regions_present,
            regions_hiring=[
                CompanyRegionHiringEntry(
                    region_id=f"region_{index}",
                    region_display_name=f"Region {index}",
                    currently_hiring_flag=True,
                    active_posting_count_now=3,
                    coverage=coverage,
                )
                for index in range(region_count)
            ],
            entry_level_regions=[
                CompanyRegionEntryLevelEntry(
                    region_id="region_0",
                    region_display_name="Region 0",
                    internship_count=3,
                    coop_count=1,
                    entry_level_full_time_count=2,
                    entry_level_access_score=entry_access,
                    entry_level_confidence="high_confidence",
                    coverage=coverage,
                )
            ],
        ),
        metadata=OutputPayloadMetadata(
            state="fresh",
            freshness_expires_at=NOW + timedelta(days=30),
            source_versions={"company_version": 1},
            warnings=[],
        ),
    )


def test_region_rankings_change_by_goal_mode_and_expose_components() -> None:
    access_market = _region_output(
        region_id="access_market",
        display_name="Access Market",
        early_access=0.92,
        prestige=0.25,
        present_companies=8,
        internships=9,
    )
    prestige_market = _region_output(
        region_id="prestige_market",
        display_name="Prestige Market",
        early_access=0.3,
        prestige=0.95,
        present_companies=18,
        internships=1,
        major_tech=8,
        mag7=3,
    )

    source_summaries = {
        "access_market": _source_summary("region", "access_market"),
        "prestige_market": _source_summary("region", "prestige_market"),
    }
    entry_result = rank_region_recommendations(
        [prestige_market, access_market],
        goal_mode=RecommendationGoalMode.MAXIMIZE_ENTRY_LEVEL_ACCESS,
        source_summaries=source_summaries,
    )
    prestige_result = rank_region_recommendations(
        [access_market, prestige_market],
        goal_mode=RecommendationGoalMode.MAXIMIZE_PRESTIGE,
        source_summaries=source_summaries,
    )

    assert isinstance(entry_result, RecommendationRankingResult)
    assert entry_result.profile == goal_mode_weight_profile(
        RecommendationGoalMode.MAXIMIZE_ENTRY_LEVEL_ACCESS
    )
    assert entry_result.ranked_recommendations[0].target.target_id == "access_market"
    assert prestige_result.ranked_recommendations[0].target.target_id == "prestige_market"
    first = entry_result.ranked_recommendations[0]
    assert first.final_score == first.normalized_score
    assert first.score_components_used
    assert first.confidence_contribution is not None
    assert first.freshness_contribution is not None
    assert first.coverage_contribution is not None
    profile_weights = {
        component.component: component.weight
        for component in entry_result.profile.weighted_components
    }
    assert {
        component.component: component.weight for component in first.score_components_used
    }.items() <= profile_weights.items()
    assert all(component.evidence_refs for component in first.score_components_used)
    assert isinstance(first.explanation, RecommendationExplanation)
    assert first.explanation.fit_reasons[0].reason_category.value == "goal_alignment"


def test_region_ranking_is_deterministic_and_tie_breaks_by_label() -> None:
    beta = _region_output(
        region_id="region_b",
        display_name="Beta",
        early_access=0.7,
        prestige=0.5,
        present_companies=10,
        internships=3,
    )
    alpha = _region_output(
        region_id="region_a",
        display_name="Alpha",
        early_access=0.7,
        prestige=0.5,
        present_companies=10,
        internships=3,
    )

    first = rank_region_recommendations(
        [beta, alpha],
        goal_mode=RecommendationGoalMode.MAXIMIZE_ENTRY_LEVEL_ACCESS,
    )
    second = rank_region_recommendations(
        [alpha, beta],
        goal_mode=RecommendationGoalMode.MAXIMIZE_ENTRY_LEVEL_ACCESS,
    )

    assert [item.target.target_id for item in first.ranked_recommendations] == [
        "region_a",
        "region_b",
    ]
    assert [item.target.target_id for item in first.ranked_recommendations] == [
        item.target.target_id for item in second.ranked_recommendations
    ]
    assert first.ranked_recommendations[0].final_score == (
        second.ranked_recommendations[0].final_score
    )
    assert first.tie_breaker == (
        "Sort by final_score descending, then display label, then stable target id."
    )


def test_missing_proxy_and_penalty_behavior_are_visible_in_ranking_output() -> None:
    result = rank_region_recommendations(
        [
            _region_output(
                region_id="regional_target",
                display_name="Regional Target",
                early_access=0.75,
                prestige=0.45,
                present_companies=7,
                internships=4,
            )
        ],
        goal_mode=RecommendationGoalMode.MAXIMIZE_GEOGRAPHIC_FLEXIBILITY,
    )
    item = result.ranked_recommendations[0]

    assert any(
        component.component is RecommendationScoreComponent.GEOGRAPHIC_FLEXIBILITY
        for component in item.score_components_missing
    )
    assert item.score_components_proxy
    assert any("missing" in warning.casefold() for warning in item.warnings)
    assert any(
        weakness.label.startswith("Ranking component is missing")
        for weakness in item.explanation.weaknesses
    )
    assert ManualVerificationCategory.SOURCE_CONFIRMATION in {
        check.verification_category for check in item.explanation.manual_verification
    }


def test_lower_competition_ranking_surfaces_inferred_proxy_and_explicit_penalty() -> None:
    result = rank_region_recommendations(
        [
            _region_output(
                region_id="proxy_market",
                display_name="Proxy Market",
                early_access=0.7,
                prestige=0.2,
                present_companies=4,
                internships=4,
            )
        ],
        goal_mode=RecommendationGoalMode.MAXIMIZE_LOWER_COMPETITION,
    )
    item = result.ranked_recommendations[0]

    lower_competition = next(
        component
        for component in item.score_components_proxy
        if component.component is RecommendationScoreComponent.LOWER_COMPETITION_PROXY
    )
    assert lower_competition.inferred is True
    assert RecommendationEvidenceBasis.HEURISTIC_INFERENCE in (
        lower_competition.evidence_basis
    )
    assert item.penalties_applied
    assert all(penalty.penalty_value >= 0 for penalty in item.penalties_applied)
    assert any(
        weakness.support is RecommendationClaimSupport.INFERRED
        for weakness in item.explanation.weaknesses
        if weakness.label.startswith("Ranking penalty")
    )


def test_company_ranking_supported_and_explanations_are_bound() -> None:
    ai_company = _company_output(
        company_id="ai_company",
        company_name="AI Company",
        sector_primary="ai",
        prestige=0.65,
        entry_access=0.65,
        region_count=1,
    )
    tools_company = _company_output(
        company_id="tools_company",
        company_name="Tools Company",
        sector_primary="developer_tools",
        prestige=0.8,
        entry_access=0.6,
        region_count=4,
    )

    result = rank_company_recommendations(
        [tools_company, ai_company],
        goal_mode=RecommendationGoalMode.MAXIMIZE_AI_CLOUD_CONCENTRATION,
        source_summaries={
            "ai_company": _source_summary("company", "ai_company"),
            "tools_company": _source_summary("company", "tools_company"),
        },
    )
    first = result.ranked_recommendations[0]

    assert first.target.target_type is RecommendationTargetType.COMPANY
    assert first.target.target_id == "ai_company"
    assert first.explanation.target == first.target
    assert first.explanation.goal_mode is RecommendationGoalMode.MAXIMIZE_AI_CLOUD_CONCENTRATION
    assert first.explanation.fit_reasons
    assert any(
        tradeoff.tradeoff_category
        is RecommendationTradeoffCategory.AI_CLOUD_CONCENTRATION_VS_COMPANY_UNIVERSE
        for tradeoff in first.explanation.tradeoffs
    )


def test_unknown_goal_mode_is_rejected_before_ranking() -> None:
    with pytest.raises(ValueError):
        rank_region_recommendations(
            [
                _region_output(
                    region_id="access_market",
                    display_name="Access Market",
                    early_access=0.8,
                    prestige=0.5,
                    present_companies=8,
                    internships=4,
                )
            ],
            goal_mode="unknown_goal",
        )


def test_ranking_component_validation_rejects_free_floating_structured_claim() -> None:
    with pytest.raises(ValidationError):
        ResolvedScoreComponent(
            component=RecommendationScoreComponent.ENTRY_LEVEL_ACCESS,
            status=ScoreComponentStatus.USED,
            value=0.7,
            evidence_basis=(RecommendationEvidenceBasis.STRUCTURED_SCORE,),
        )

    with pytest.raises(ValidationError):
        ResolvedScoreComponent(
            component=RecommendationScoreComponent.LOWER_COMPETITION_PROXY,
            status=ScoreComponentStatus.PROXY,
            value=0.7,
            evidence_basis=(RecommendationEvidenceBasis.HEURISTIC_INFERENCE,),
            is_proxy=True,
            inferred=False,
        )
