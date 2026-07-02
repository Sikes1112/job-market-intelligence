from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.models import Region
from backend.opportunities.repository import OpportunityRepository
from backend.opportunities.schemas import (
    OpportunityLocationMode,
    OpportunityProgramType,
    OpportunityRegionBindingCreate,
    OpportunityReviewAction,
    OpportunityReviewRequest,
    OpportunityRoleFamilyBindingCreate,
    OpportunitySeniorityLevel,
    OpportunitySubmissionRequest,
)
from backend.opportunities.submissions import OpportunitySubmissionService
from backend.outputs.models import OutputMetadata
from backend.platform_intelligence.models import (
    BenchmarkReport,
    BenchmarkReportRanking,
    MarketIndex,
    MarketIndexScore,
    MarketIndexVersion,
    MarketSnapshot,
    PredictiveSignal,
)
from backend.scoring.models import RegionMarketScore

NOW = datetime(2026, 6, 24, 12, tzinfo=UTC)


def _seed_market_authority(session: Session) -> None:
    session.add(
        Region(
            region_id="greater_boston",
            region_name="greater_boston",
            display_name="Greater Boston",
            region_type="metro",
        )
    )
    session.add(
        Company(
            company_id="comp_a",
            company_name="Company A",
            normalized_company_name="company a",
            sector_primary="software",
        )
    )
    session.flush()
    session.add_all(
        [
            RegionMarketScore(
                region_score_id="score_boston",
                region_id="greater_boston",
                objective_opportunity_score=0.61,
                early_career_accessibility_score=0.57,
                score_ruleset_version="canonical_v1",
            ),
            OutputMetadata(
                output_id="output_boston",
                output_type="region_output",
                subject_id="greater_boston",
                artifact_hash="stable-output",
            ),
            MarketSnapshot(
                market_snapshot_id="market_snap_boston",
                region_id="greater_boston",
                snapshot_date=date(2026, 1, 1),
                overall_score=0.50,
                created_at=NOW,
            ),
            MarketIndex(
                market_index_id="index_early",
                key="early_career_tech_access",
                name="Early Career Tech Access",
                description="Derived index.",
                status="active",
                created_at=NOW,
            ),
        ]
    )
    session.flush()
    session.add(
        MarketIndexVersion(
            market_index_version_id="index_early_v1",
            index_id="index_early",
            version="v1",
            formula_description="Public formula summary.",
            input_schema={},
            internal_weight_config={"hidden_weight": 1.0},
            status="active",
            effective_date=date(2026, 1, 1),
            created_at=NOW,
        )
    )
    session.flush()
    session.add_all(
        [
            MarketIndexScore(
                market_index_score_id="index_score_boston",
                index_id="index_early",
                index_version_id="index_early_v1",
                region_id="greater_boston",
                score=0.71,
                rank=1,
                confidence_score=0.8,
                freshness_state="fresh",
                evidence_summary={"warnings": []},
                calculated_at=NOW,
                created_at=NOW,
            ),
            PredictiveSignal(
                predictive_signal_id="signal_boston",
                signal_type="emerging_market",
                target_type="region",
                target_id="greater_boston",
                region_id="greater_boston",
                signal_strength="weak",
                confidence_level="low",
                evidence_window_start=date(2026, 1, 1),
                evidence_window_end=date(2026, 3, 1),
                snapshot_count=3,
                minimum_snapshot_count_met=True,
                summary="Emerging signal.",
                warnings=[],
                status="active",
                created_at=NOW,
            ),
            BenchmarkReport(
                benchmark_report_id="report_boston",
                report_key="top_emerging_tech_markets",
                title="Top Emerging Tech Markets",
                report_period="2026-Q2",
                report_type="emerging_tech_markets",
                status="published",
                summary="Published report.",
                methodology_summary="Public methodology.",
                data_window_start=date(2026, 1, 1),
                data_window_end=date(2026, 3, 1),
                limitations=[],
                created_at=NOW,
                published_at=NOW,
            ),
        ]
    )
    session.flush()
    session.add(
        BenchmarkReportRanking(
            benchmark_report_ranking_id="report_rank_boston",
            report_id="report_boston",
            region_id="greater_boston",
            rank=1,
            score=0.82,
            index_score_id="index_score_boston",
            explanation="Published ranking.",
            warnings=[],
            confidence_score=0.8,
            freshness_state="fresh",
            created_at=NOW,
        )
    )
    session.flush()


def _submission_request() -> OpportunitySubmissionRequest:
    return OpportunitySubmissionRequest(
        submission_id="sub_governance",
        opportunity_id="opp_governance",
        employer_id="comp_a",
        employer_name="Company A",
        program_name="Governed Employer Program",
        program_type=OpportunityProgramType.INTERNSHIP,
        location_mode=OpportunityLocationMode.HYBRID,
        seniority_level=OpportunitySeniorityLevel.INTERNSHIP,
        eligibility_summary="Open to students and recent graduates.",
        application_url="https://example.com/apply/governed",
        source_url="https://example.com/careers/governed",
        application_deadline=date(2099, 1, 1),
        submitter_contact="talent@example.com",
        partner_organization_id="partner_1",
        partner_organization_name="Partner Org",
        paid_partner=True,
        paid_partner_label="paid_partner_relationship",
        role_family_bindings=(
            OpportunityRoleFamilyBindingCreate(role_family="software_engineering"),
        ),
        region_bindings=(
            OpportunityRegionBindingCreate(
                region_id="greater_boston",
                region_label="Greater Boston",
            ),
        ),
        submitted_at=NOW,
    )


def test_submission_and_review_do_not_mutate_objective_intelligence(
    session: Session,
) -> None:
    _seed_market_authority(session)
    service = OpportunitySubmissionService(OpportunityRepository(session))

    submission = service.submit_opportunity(_submission_request())
    service.review_submission(
        submission.submission_id,
        OpportunityReviewRequest(
            review_action=OpportunityReviewAction.APPROVE_AS_VERIFIED,
            reviewer_id="reviewer_1",
            review_note="Internal note.",
            official_employer_url="https://example.com/careers",
            reviewed_at=NOW,
        ),
    )

    assert session.get(RegionMarketScore, "score_boston").objective_opportunity_score == 0.61
    assert session.get(RegionMarketScore, "score_boston").early_career_accessibility_score == (
        0.57
    )
    assert session.get(RegionMarketScore, "score_boston").score_ruleset_version == (
        "canonical_v1"
    )
    assert session.get(OutputMetadata, "output_boston").artifact_hash == "stable-output"
    assert session.get(MarketSnapshot, "market_snap_boston").overall_score == 0.50
    assert session.get(MarketIndexScore, "index_score_boston").score == 0.71
    assert session.get(MarketIndexScore, "index_score_boston").rank == 1
    assert session.get(PredictiveSignal, "signal_boston").status == "active"
    assert session.get(PredictiveSignal, "signal_boston").signal_strength == "weak"
    assert session.get(BenchmarkReport, "report_boston").status == "published"
    assert session.get(BenchmarkReportRanking, "report_rank_boston").score == 0.82
