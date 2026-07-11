from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.geography.market_coverage import (
    COVERAGE_SCORE_DIMENSIONS,
    COVERAGE_TIER_DEFINITIONS,
    PRIORITY_MARKETS,
    REGION_EXPANSION_PLAYBOOK,
    SECTOR_COVERAGE_DEFINITIONS,
    SECTOR_COVERAGE_LEVEL_DEFINITIONS,
    CoverageMetadataPayload,
    CoverageQualityLabel,
    CoverageQualityScore,
    CoverageQualityScorePayload,
    CoverageTier,
    RegionCoverageProfile,
    RegionExpansionPlaybookStep,
    SectorCoverageCategory,
    SectorCoverageLevel,
    SectorCoverageProfile,
    build_region_coverage_metadata,
    coverage_quality_total,
    declared_tier_is_supported,
    priority_market_by_id,
    sector_coverage_level_from_quality,
    suggest_coverage_tier,
    unknown_sector_coverage_metadata,
)
from backend.imports.bulk import (
    import_all_curated_market_datasets,
    run_all_curated_market_post_imports,
)
from backend.imports.coverage import (
    build_all_market_coverage_summaries,
    build_market_coverage_summary,
)
from backend.imports.post_import import run_curated_market_post_import
from backend.provenance.models import FactSourceLink
from backend.region_expansion.service import TARGET_REGION_EXPANSION_PLAN

AS_OF = date(2026, 7, 9)
ALL_MARKETS = {
    "nyc",
    "seattle",
    "san_francisco_bay_area",
    "boston",
    "washington_dc",
    "austin",
    "atlanta",
    "chicago",
}


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
        company_coverage=85.0,
        hiring_coverage=82.0,
        entry_level_coverage=81.0,
        freshness=80.0,
        source_diversity=70.0,
        confidence=84.0,
    )


def _tier_2_quality() -> CoverageQualityScore:
    return _quality(
        company_coverage=72.0,
        hiring_coverage=30.0,
        entry_level_coverage=80.0,
        freshness=54.0,
        source_diversity=44.0,
        confidence=55.0,
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


def test_sector_coverage_levels_are_canonical_and_conservative() -> None:
    assert SectorCoverageLevel.values() == {
        "unknown",
        "limited",
        "watchlist",
        "partial",
        "strong",
    }
    assert (
        SECTOR_COVERAGE_LEVEL_DEFINITIONS[
            SectorCoverageLevel.UNKNOWN
        ].can_be_inferred_from_missing_evidence
        is True
    )
    assert (
        SECTOR_COVERAGE_LEVEL_DEFINITIONS[
            SectorCoverageLevel.STRONG
        ].can_be_displayed_as_strong
        is True
    )

    assert sector_coverage_level_from_quality(None) is SectorCoverageLevel.UNKNOWN
    assert sector_coverage_level_from_quality(_quality()) is SectorCoverageLevel.UNKNOWN
    assert (
        sector_coverage_level_from_quality(_quality(company_coverage=10.0))
        is SectorCoverageLevel.LIMITED
    )
    assert (
        sector_coverage_level_from_quality(
            _quality(company_coverage=30.0, confidence=25.0)
        )
        is SectorCoverageLevel.WATCHLIST
    )
    assert (
        sector_coverage_level_from_quality(_tier_2_quality())
        is SectorCoverageLevel.PARTIAL
    )
    assert (
        sector_coverage_level_from_quality(_tier_1_quality())
        is SectorCoverageLevel.STRONG
    )


def test_coverage_quality_score_is_bounded_and_explainable() -> None:
    quality = _tier_2_quality()

    assert set(quality.component_scores) == set(COVERAGE_SCORE_DIMENSIONS)
    assert coverage_quality_total(quality) == quality.total_score
    assert quality.suggested_tier is CoverageTier.TIER_2
    assert quality.quality_label is CoverageQualityLabel.PARTIAL

    with pytest.raises(ValidationError):
        _quality(company_coverage=100.01)
    with pytest.raises(ValidationError):
        _quality(confidence=-0.01)


def test_api_coverage_payload_component_scores_are_bounded() -> None:
    with pytest.raises(ValidationError, match="between 0 and 100"):
        CoverageQualityScorePayload(
            overall_score=50.0,
            components={"company_coverage": 100.1},
        )
    with pytest.raises(ValidationError, match="between 0 and 100"):
        CoverageMetadataPayload(
            tier=CoverageTier.TIER_2,
            label="Tier 2 - partial but useful market",
            quality_score=50.0,
            components={"company_coverage": -0.1},
        )


def test_incomplete_quality_cannot_be_declared_tier_1() -> None:
    incomplete = _quality(
        company_coverage=90.0,
        hiring_coverage=90.0,
        entry_level_coverage=0.0,
        freshness=90.0,
        source_diversity=90.0,
        confidence=90.0,
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
    watchlist = _quality(company_coverage=20.0)
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
                coverage_level=SectorCoverageLevel.STRONG,
                quality_score=_tier_1_quality(),
            ),
            SectorCoverageCategory.CLOUD: SectorCoverageProfile(
                sector=SectorCoverageCategory.CLOUD,
                coverage_tier=CoverageTier.TIER_3,
                coverage_level=SectorCoverageLevel.UNKNOWN,
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


def test_sector_coverage_level_cannot_overstate_missing_or_weak_evidence() -> None:
    SectorCoverageProfile(
        sector=SectorCoverageCategory.AI,
        coverage_tier=CoverageTier.TIER_4,
        coverage_level=SectorCoverageLevel.UNKNOWN,
    )
    SectorCoverageProfile(
        sector=SectorCoverageCategory.AI,
        coverage_tier=CoverageTier.TIER_4,
        coverage_level=SectorCoverageLevel.LIMITED,
    )

    with pytest.raises(ValidationError, match="strong coverage requires tier_1"):
        SectorCoverageProfile(
            sector=SectorCoverageCategory.AI,
            coverage_tier=CoverageTier.TIER_2,
            coverage_level=SectorCoverageLevel.STRONG,
            quality_score=_tier_1_quality(),
        )
    with pytest.raises(ValidationError, match="partial coverage is not supported"):
        SectorCoverageProfile(
            sector=SectorCoverageCategory.AI,
            coverage_tier=CoverageTier.TIER_3,
            coverage_level=SectorCoverageLevel.PARTIAL,
            quality_score=_quality(company_coverage=30.0, confidence=25.0),
        )
    with pytest.raises(ValidationError, match="requires a quality score"):
        SectorCoverageProfile(
            sector=SectorCoverageCategory.AI,
            coverage_tier=CoverageTier.TIER_3,
            coverage_level=SectorCoverageLevel.WATCHLIST,
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
    assert coverage.coverage_tier is CoverageTier.TIER_4
    assert coverage.coverage_label == "Tier 4 - placeholder only"
    assert "placeholder only" in coverage.coverage_description
    assert coverage.quality_score == 0.0
    assert coverage.coverage_quality_score.overall_score == 0.0
    assert coverage.coverage_quality_score.components == coverage.components
    assert any("placeholder" in item for item in coverage.coverage_limitations)
    assert coverage.heuristic is True
    assert coverage.should_rank_as_confident_recommendation is False


def test_unknown_sector_coverage_defaults_are_explicit_and_not_strong() -> None:
    sector_coverage = unknown_sector_coverage_metadata()

    assert set(sector_coverage) == SectorCoverageCategory.values()
    assert {entry.coverage_level for entry in sector_coverage.values()} == {
        SectorCoverageLevel.UNKNOWN
    }
    assert {
        entry.coverage.coverage_tier for entry in sector_coverage.values()
    } == {CoverageTier.TIER_4}
    assert all(
        entry.coverage.should_rank_as_confident_recommendation is False
        for entry in sector_coverage.values()
    )


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
    assert coverage.components["source_diversity"] == 67.0
    assert coverage.safe_for_confident_market_comparison is (
        coverage.tier is CoverageTier.TIER_1
    )


def test_coverage_summaries_are_computed_for_every_market(
    session: Session,
) -> None:
    assert import_all_curated_market_datasets(session, as_of=AS_OF).ok
    assert run_all_curated_market_post_imports(session, as_of=AS_OF).ok

    summaries = build_all_market_coverage_summaries(session)

    assert set(summaries) == ALL_MARKETS
    for market_key, summary in summaries.items():
        assert summary.market_key == market_key
        assert summary.company_count == 3
        assert summary.presence_fact_count == 3
        assert summary.hiring_fact_count == 3
        assert summary.entry_level_fact_count == 3
        assert summary.source_count == 5
        assert summary.ranking_eligible_fact_count == 13
        assert summary.ranking_excluded_fact_count == 0
        assert summary.last_import_status == "imported"
        assert summary.last_refresh_status == "refreshed"
        assert summary.source_label == "Source-backed"
        assert summary.ranking_label == "Ranking-safe"


def test_coverage_summaries_include_unknown_and_zero_dimensions(
    session: Session,
) -> None:
    assert import_all_curated_market_datasets(session, as_of=AS_OF).ok
    assert run_all_curated_market_post_imports(session, as_of=AS_OF).ok

    summaries = build_all_market_coverage_summaries(session)

    for summary in summaries.values():
        assert summary.unknown_count_dimensions > 0
        assert summary.observed_zero_count_dimensions > 0
        breakdown = summary.count_status_breakdown
        assert breakdown["unknown"] > 0
        assert breakdown["zero_observed"] > 0
        assert breakdown["positive_observed"] > 0
        assert any(
            breakdown.get(status, 0) > 0
            for status in ("not_collected", "not_applicable")
        )


def test_coverage_summaries_are_public_safe(session: Session) -> None:
    assert import_all_curated_market_datasets(session, as_of=AS_OF).ok
    assert run_all_curated_market_post_imports(session, as_of=AS_OF).ok

    summaries = build_all_market_coverage_summaries(session)

    for summary in summaries.values():
        payload = summary.as_dict()
        assert payload["coverage_label"] in {"Seed coverage", "Partial coverage"}
        assert payload["freshness_label"] == "Current"
        _assert_public_payload_safe(payload)


def test_stale_coverage_and_ranking_exclusion_are_market_specific(
    session: Session,
) -> None:
    assert import_all_curated_market_datasets(session, as_of=AS_OF).ok
    assert run_all_curated_market_post_imports(session, as_of=AS_OF).ok

    link = _fact_link(
        session,
        "company_region_hiring",
        "hiring_cmp_microsoft_atlanta",
    )
    link.freshness_status = "stale"
    session.flush()
    assert run_curated_market_post_import(session, "atlanta", as_of=AS_OF).ok

    atlanta = build_market_coverage_summary(session, "atlanta")
    seattle = build_market_coverage_summary(session, "seattle")

    assert atlanta.freshness_status == "stale"
    assert atlanta.freshness_label == "Needs refresh"
    assert atlanta.ranking_excluded_fact_count == 1
    assert atlanta.ranking_label == "Some data ranking-excluded"
    assert seattle.freshness_status == "fresh"
    assert seattle.ranking_excluded_fact_count == 0
    assert seattle.ranking_label == "Ranking-safe"


def _fact_link(
    session: Session,
    fact_type: str,
    fact_id: str,
) -> FactSourceLink:
    return session.execute(
        select(FactSourceLink).where(
            FactSourceLink.fact_type == fact_type,
            FactSourceLink.fact_id == fact_id,
        )
    ).scalar_one()


def _assert_public_payload_safe(value: Any) -> None:
    forbidden = {
        "internal_notes",
        "reporter_user_id",
        "reporter_session_id",
        "report_reason",
        "related_user_report_id",
        "assigned_owner",
        "exception_case_id",
        "risk_routing_decision_id",
        "trust_assessment_id",
        "raw_internal_risk",
        "source_id",
        "source_ref",
        "fact_source_link_id",
    }
    assert forbidden.isdisjoint(_keys(value))


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        keys = set(value)
        for item in value.values():
            keys.update(_keys(item))
        return keys
    if isinstance(value, list | tuple):
        keys: set[str] = set()
        for item in value:
            keys.update(_keys(item))
        return keys
    return set()
