from __future__ import annotations

from datetime import UTC, datetime, timedelta

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
from backend.recommendations.assembly import (
    assemble_company_recommendation_explanation,
    assemble_region_recommendation_explanation,
)
from backend.recommendations.models import (
    ManualVerificationCategory,
    RecommendationClaimSupport,
    RecommendationEvidenceBasis,
    RecommendationEvidenceStrength,
    RecommendationExplanation,
    RecommendationGoalMode,
    RecommendationWeaknessCategory,
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
                source_id="source_real",
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
        present_company_count=8,
        presence_record_count=8,
        hiring_record_count=6,
        entry_level_record_count=4,
        has_region_score=True,
        freshness_expires_at_known=True,
        freshness_is_stale=False,
        source_count=2,
        source_data_basis="real_imported",
        source_evidence_loaded=True,
    )


def _region_output(*, partial: bool = False) -> RegionOutput:
    scores = None if partial else RegionScoresPayload(
        objective_opportunity_score=0.74,
        raw_total_score=0.71,
        early_career_accessibility_score=0.79,
        live_market_score=0.68,
        score_ruleset_version="marketscore_v1",
    )
    return RegionOutput(
        region=RegionOutputBody(
            region_id="greater_boston",
            display_name="Greater Boston",
            region_type="greater_region",
            coverage=_coverage(),
            summary=RegionSummary(
                eligible_company_count=6,
                major_tech_count=2,
                mag7_count=1,
                present_company_count=8,
                currently_hiring_company_count=4,
            ),
            scores=scores,
            entry_level_summary=EntryLevelSummary(
                internship_count_total=None if partial else 5,
                coop_count_total=2,
                entry_level_full_time_count_total=7,
                average_entry_level_access_score=0.69,
                pairs_with_entry_level_access=4,
            ),
            major_tech_summary=MajorTechSummary(count=2, company_ids=["comp_a"]),
            mag7_summary=Mag7Summary(count=1, company_ids=["comp_mag7"]),
        ),
        metadata=OutputPayloadMetadata(
            state="partial" if partial else "fresh",
            freshness_expires_at=NOW + timedelta(days=30),
            source_versions={"region_version": 1},
            warnings=[],
        ),
    )


def _company_output(*, partial: bool = False) -> CompanyOutput:
    coverage = _coverage()
    regions_present = [] if partial else [
        CompanyRegionPresenceEntry(
            region_id="greater_boston",
            region_display_name="Greater Boston",
            presence_status="present",
            presence_basis="office_plus_hiring",
            presence_confidence="high_confidence",
            coverage=coverage,
        )
    ]
    return CompanyOutput(
        company=CompanyOutputBody(
            company_id="comp_a",
            company_name="Company A",
            normalized_company_name="company a",
            sector_primary="ai",
            sector_secondary="cloud",
            eligibility_status="eligible",
            classification_confidence="moderate_confidence",
            is_major_tech=True,
            prestige_score=0.72,
            regions_present=regions_present,
            regions_hiring=[
                CompanyRegionHiringEntry(
                    region_id="greater_boston",
                    region_display_name="Greater Boston",
                    currently_hiring_flag=True,
                    active_posting_count_now=5,
                    coverage=coverage,
                )
            ],
            entry_level_regions=[
                CompanyRegionEntryLevelEntry(
                    region_id="greater_boston",
                    region_display_name="Greater Boston",
                    internship_count=2,
                    coop_count=1,
                    entry_level_full_time_count=3,
                    entry_level_access_score=0.7,
                    entry_level_confidence="high_confidence",
                    coverage=coverage,
                )
            ],
        ),
        metadata=OutputPayloadMetadata(
            state="partial" if partial else "fresh",
            freshness_expires_at=NOW + timedelta(days=30),
            source_versions={"company_version": 1},
            warnings=[],
        ),
    )


def test_region_assembly_produces_valid_structured_explanation() -> None:
    explanation = assemble_region_recommendation_explanation(
        _region_output(),
        goal_mode=RecommendationGoalMode.MAXIMIZE_ENTRY_LEVEL_ACCESS,
        source_summary=_source_summary("region", "greater_boston"),
    )

    assert isinstance(explanation, RecommendationExplanation)
    assert explanation.target.target_id == "greater_boston"
    assert explanation.fit_reasons
    assert explanation.data_strengths
    assert explanation.evidence_refs
    assert explanation.confidence_summary is not None
    assert explanation.freshness_summary.freshness_status == "fresh"
    assert explanation.provenance_refs[0].source_ref_id == "source_real"
    assert all(reason.evidence_refs for reason in explanation.fit_reasons)
    assert not any(
        reason.support is RecommendationClaimSupport.INFERRED
        for reason in explanation.fit_reasons
    )


def test_region_assembly_turns_missing_data_into_weaknesses_and_verification() -> None:
    explanation = assemble_region_recommendation_explanation(_region_output(partial=True))

    labels = {weakness.label for weakness in explanation.weaknesses}
    verification = {item.verification_category for item in explanation.manual_verification}

    assert "Region scores are missing" in labels
    assert "Source/provenance references are missing" in labels
    assert ManualVerificationCategory.INTERNSHIP_COOP_ACCESS in verification
    assert ManualVerificationCategory.SOURCE_CONFIRMATION in verification
    assert explanation.fit_reasons or explanation.weaknesses or explanation.manual_verification


def test_company_assembly_uses_metadata_coverage_freshness_and_sources() -> None:
    explanation = assemble_company_recommendation_explanation(
        _company_output(),
        source_summary=_source_summary("company", "comp_a"),
    )

    assert explanation.target.target_id == "comp_a"
    assert explanation.fit_reasons
    assert any(
        ref.basis is RecommendationEvidenceBasis.COMPANY_METADATA
        for ref in explanation.evidence_refs
    )
    assert any(
        ref.basis is RecommendationEvidenceBasis.MARKET_COVERAGE
        for ref in explanation.evidence_refs
    )
    assert explanation.confidence_summary.confidence_level == "moderate_confidence"
    assert explanation.freshness_summary.freshness_status == "fresh"
    assert explanation.provenance_refs[0].source_ref_id == "source_real"


def test_company_assembly_missing_structured_inputs_are_visible() -> None:
    explanation = assemble_company_recommendation_explanation(_company_output(partial=True))

    labels = {weakness.label for weakness in explanation.weaknesses}
    verification = {item.verification_category for item in explanation.manual_verification}

    assert "No present-region records are attached" in labels
    assert "Source/provenance references are missing" in labels
    assert ManualVerificationCategory.SOURCE_CONFIRMATION in verification


def test_company_assembly_deduplicates_and_bounds_coverage_warnings() -> None:
    rows = [
        {
            "region_id": f"region_{index}",
            "coverage": {
                "coverage_limitations": [
                    "shared coverage warning",
                    *(f"warning_{index}_{item}" for item in range(5)),
                ],
                "should_rank_as_confident_recommendation": False,
            },
        }
        for index in range(8)
    ]
    explanation = assemble_company_recommendation_explanation({
        "company_id": "comp_many_warnings",
        "company_name": "Many Warnings Co",
        "regions_present": rows,
        "regions_hiring": [],
        "entry_level_regions": [],
    })

    assert len(explanation.coverage_warnings) == 30
    assert explanation.coverage_warnings.count("shared coverage warning") == 1


def test_proxy_goal_modes_are_explicitly_inferred() -> None:
    explanation = assemble_region_recommendation_explanation(
        _region_output(),
        goal_mode=RecommendationGoalMode.MAXIMIZE_LOWER_COMPETITION,
    )

    heuristic = [
        weakness
        for weakness in explanation.weaknesses
        if RecommendationEvidenceBasis.HEURISTIC_INFERENCE in weakness.evidence_basis
    ]
    assert heuristic
    assert all(item.support is RecommendationClaimSupport.INFERRED for item in heuristic)
    assert all(
        item.evidence_strength is RecommendationEvidenceStrength.INFERRED
        for item in heuristic
    )


def test_assembly_does_not_emit_free_text_only_explanations() -> None:
    explanation = assemble_region_recommendation_explanation(_region_output(partial=True))

    assert explanation.headline
    assert explanation.fit_reasons or explanation.weaknesses or explanation.manual_verification
    assert any(
        weakness.weakness_category is RecommendationWeaknessCategory.MISSING_DATA
        for weakness in explanation.weaknesses
    )
