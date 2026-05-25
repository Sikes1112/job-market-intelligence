from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.geography.market_coverage import (
    COVERAGE_SCORE_DIMENSIONS,
    COVERAGE_TIER_DEFINITIONS,
    PRIORITY_MARKETS,
    REGION_EXPANSION_PLAYBOOK,
    SECTOR_COVERAGE_DEFINITIONS,
    CoverageQualityLabel,
    CoverageQualityScore,
    CoverageTier,
    RegionCoverageProfile,
    RegionExpansionPlaybookStep,
    SectorCoverageCategory,
    SectorCoverageProfile,
    build_region_coverage_metadata,
    coverage_quality_total,
    declared_tier_is_supported,
    priority_market_by_id,
    suggest_coverage_tier,
)
from backend.region_expansion.service import TARGET_REGION_EXPANSION_PLAN


def _quality(**overrides) -> CoverageQualityScore:
    base = {
        "company_coverage": 0.0,
        "hiring_coverage": 0.0,
        "entry_level_coverage": 0.0,
        "freshness": 0.0,
        "source_diversity": 0.0,
        "confidence": 0.0,
    }
    base.update(overrides)
    return CoverageQualityScore(**base)


def _tier_1_quality() -> CoverageQualityScore:
    return _quality(
        company_coverage=0.85,
        hiring_coverage=0.82,
        entry_level_coverage=0.81,
        freshness=0.80,
        source_diversity=0.70,
        confidence=0.84,
    )


def _tier_2_quality() -> CoverageQualityScore:
    return _quality(
        company_coverage=0.72,
        hiring_coverage=0.30,
        entry_level_coverage=0.80,
        freshness=0.54,
        source_diversity=0.44,
        confidence=0.55,
    )


def test_priority_market_registry_is_canonical_ordered_and_complete() -> None:
    assert [(m.rank, m.market_id, m.display_name) for m in PRIORITY_MARKETS] == [
        (1, "nyc", "NYC"),
        (2, "seattle", "Seattle"),
        (3, "austin", "Austin"),
        (4, "dc_nova", "DC / NoVA"),
        (5, "atlanta", "Atlanta"),
        (6, "chicago", "Chicago"),
        (7, "los_angeles", "Los Angeles"),
        (8, "raleigh_durham", "Raleigh-Durham"),
        (9, "denver_boulder", "Denver / Boulder"),
        (10, "boston", "Boston"),
        (11, "sf_bay_area", "SF Bay Area"),
        (12, "dallas", "Dallas"),
        (13, "miami", "Miami"),
        (14, "pittsburgh", "Pittsburgh"),
        (15, "minneapolis", "Minneapolis"),
    ]
    assert priority_market_by_id("dc_nova").display_name == "DC / NoVA"
    assert priority_market_by_id("missing") is None


def test_region_expansion_targets_derive_from_priority_markets() -> None:
    assert TARGET_REGION_EXPANSION_PLAN == tuple(
        (market.market_id, market.display_name) for market in PRIORITY_MARKETS
    )


def test_region_expansion_playbook_contains_required_staged_path() -> None:
    assert [step.step for step in REGION_EXPANSION_PLAYBOOK] == [
        RegionExpansionPlaybookStep.SOURCE_COLLECTION,
        RegionExpansionPlaybookStep.COMPANY_UNIVERSE_DEFINITION,
        RegionExpansionPlaybookStep.PRESENCE_VALIDATION,
        RegionExpansionPlaybookStep.HIRING_SIGNAL_COLLECTION,
        RegionExpansionPlaybookStep.ENTRY_LEVEL_SIGNAL_COLLECTION,
        RegionExpansionPlaybookStep.FRESHNESS_CLASSIFICATION,
        RegionExpansionPlaybookStep.AUDIT_PASS,
        RegionExpansionPlaybookStep.FRONTEND_RELEASE,
    ]
    assert all(step.completion_rule for step in REGION_EXPANSION_PLAYBOOK)
    assert any(
        "does not make a region covered" in step.coverage_warning.lower()
        for step in REGION_EXPANSION_PLAYBOOK
    )
    assert any(
        "unknown freshness cannot be presented as fresh"
        in step.coverage_warning.lower()
        for step in REGION_EXPANSION_PLAYBOOK
    )


def test_coverage_tier_semantics_are_explicit_and_conservative() -> None:
    tier_1 = COVERAGE_TIER_DEFINITIONS[CoverageTier.TIER_1]
    tier_2 = COVERAGE_TIER_DEFINITIONS[CoverageTier.TIER_2]
    tier_3 = COVERAGE_TIER_DEFINITIONS[CoverageTier.TIER_3]
    tier_4 = COVERAGE_TIER_DEFINITIONS[CoverageTier.TIER_4]

    assert tier_1.safe_for_confident_market_comparison is True
    assert tier_1.should_rank_as_confident_recommendation is True
    assert "Presence validated" in tier_1.required_conditions
    assert "Entry-level signals present" in tier_1.required_conditions
    assert tier_2.directionally_useful_for_comparison is True
    assert tier_2.requires_partial_label is True
    assert tier_2.should_rank_as_confident_recommendation is False
    assert tier_3.safe_for_confident_market_comparison is False
    assert tier_3.should_rank_as_confident_recommendation is False
    assert tier_4.directionally_useful_for_comparison is False
    assert tier_4.should_rank_as_confident_recommendation is False


def test_sector_coverage_categories_are_separate_from_region_tiers() -> None:
    assert SectorCoverageCategory.values() == {
        "ai",
        "cloud",
        "cybersecurity",
        "fintech",
        "healthtech",
        "edtech",
        "enterprise_saas",
        "public_sector_tech",
        "defense_tech",
        "consumer_tech",
    }
    assert SECTOR_COVERAGE_DEFINITIONS[SectorCoverageCategory.AI].label == "AI"
    assert (
        SECTOR_COVERAGE_DEFINITIONS[SectorCoverageCategory.ENTERPRISE_SAAS].label
        == "enterprise SaaS"
    )


def test_coverage_quality_score_is_bounded_and_explainable() -> None:
    quality = _tier_2_quality()

    assert set(quality.component_scores) == set(COVERAGE_SCORE_DIMENSIONS)
    assert coverage_quality_total(quality) == quality.total_score
    assert quality.suggested_tier is CoverageTier.TIER_2
    assert quality.quality_label is CoverageQualityLabel.PARTIAL

    with pytest.raises(ValidationError):
        _quality(company_coverage=1.01)
    with pytest.raises(ValidationError):
        _quality(confidence=-0.01)


def test_incomplete_quality_cannot_be_declared_tier_1() -> None:
    incomplete = _quality(
        company_coverage=0.90,
        hiring_coverage=0.90,
        entry_level_coverage=0.0,
        freshness=0.90,
        source_diversity=0.90,
        confidence=0.90,
    )

    assert suggest_coverage_tier(incomplete) is not CoverageTier.TIER_1
    assert declared_tier_is_supported(CoverageTier.TIER_1, incomplete) is False
    with pytest.raises(ValidationError, match="declared tier_1 is not supported"):
        RegionCoverageProfile(
            region_id="nyc",
            overall_tier=CoverageTier.TIER_1,
            overall_quality_score=incomplete,
        )


def test_tier_3_and_tier_4_are_structurally_distinguishable() -> None:
    watchlist = _quality(company_coverage=0.20)
    placeholder = _quality()

    assert watchlist.suggested_tier is CoverageTier.TIER_3
    assert watchlist.quality_label is CoverageQualityLabel.WATCHLIST
    assert placeholder.suggested_tier is CoverageTier.TIER_4
    assert placeholder.quality_label is CoverageQualityLabel.PLACEHOLDER
    RegionCoverageProfile(region_id="watch", overall_tier=CoverageTier.TIER_3)
    RegionCoverageProfile(region_id="placeholder", overall_tier=CoverageTier.TIER_4)


def test_sector_specific_coverage_does_not_overwrite_region_coverage() -> None:
    profile = RegionCoverageProfile(
        region_id="austin",
        overall_tier=CoverageTier.TIER_2,
        overall_quality_score=_tier_2_quality(),
        sector_coverage={
            SectorCoverageCategory.AI: SectorCoverageProfile(
                sector=SectorCoverageCategory.AI,
                coverage_tier=CoverageTier.TIER_1,
                quality_score=_tier_1_quality(),
            ),
            SectorCoverageCategory.CLOUD: SectorCoverageProfile(
                sector=SectorCoverageCategory.CLOUD,
                coverage_tier=CoverageTier.TIER_3,
            ),
        },
    )

    assert profile.overall_tier is CoverageTier.TIER_2
    assert (
        profile.sector_coverage[SectorCoverageCategory.AI].coverage_tier
        is CoverageTier.TIER_1
    )
    assert (
        profile.sector_coverage[SectorCoverageCategory.CLOUD].coverage_tier
        is CoverageTier.TIER_3
    )


def test_sector_coverage_key_must_match_profile_sector() -> None:
    with pytest.raises(ValidationError, match="sector coverage key must match"):
        RegionCoverageProfile(
            region_id="boston",
            overall_tier=CoverageTier.TIER_3,
            sector_coverage={
                SectorCoverageCategory.AI: SectorCoverageProfile(
                    sector=SectorCoverageCategory.CLOUD,
                    coverage_tier=CoverageTier.TIER_3,
                )
            },
        )


def test_region_coverage_metadata_payload_is_conservative_for_empty_surface() -> None:
    coverage = build_region_coverage_metadata(source_evidence_loaded=True)

    assert coverage.tier is CoverageTier.TIER_4
    assert coverage.quality_score == 0.0
    assert coverage.heuristic is True
    assert coverage.should_rank_as_confident_recommendation is False


def test_region_coverage_metadata_keeps_components_explainable() -> None:
    coverage = build_region_coverage_metadata(
        present_company_count=3,
        presence_record_count=3,
        hiring_record_count=3,
        entry_level_record_count=3,
        has_region_score=True,
        freshness_expires_at_known=True,
        source_count=2,
        source_data_basis="real_imported",
        source_evidence_loaded=True,
    )

    assert coverage.tier in {CoverageTier.TIER_1, CoverageTier.TIER_2}
    assert set(coverage.components) == set(COVERAGE_SCORE_DIMENSIONS)
    assert coverage.components["source_diversity"] == 0.67
    assert coverage.safe_for_confident_market_comparison is (
        coverage.tier is CoverageTier.TIER_1
    )
