from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.models import Region
from backend.opportunities.governance import (
    OPPORTUNITY_ROUTING_MUTATES_OBJECTIVE_AUTHORITY,
    ROUTE_FIRST_OPPORTUNITY_ROUTING_ENABLED,
    opportunity_governance_summary,
)
from backend.opportunities.repository import OpportunityRepository
from backend.opportunities.route_schemas import OpportunityRouteRequest
from backend.opportunities.routing import OpportunityRouteService
from backend.opportunities.schemas import (
    OpportunityCreate,
    OpportunityLocationMode,
    OpportunityProgramType,
    OpportunityRegionBindingCreate,
    OpportunityReviewStatus,
    OpportunityRoleFamilyBindingCreate,
    OpportunitySeniorityLevel,
    OpportunitySourceType,
    OpportunityTrustLabel,
)
from backend.opportunities.service import OpportunityService
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


def _seed_authority_rows(session: Session) -> None:
    session.add_all(
        [
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
                region_type="metro",
            ),
            Company(
                company_id="comp_a",
                company_name="Company A",
                normalized_company_name="company a",
                sector_primary="software",
            ),
        ]
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


def _seed_opportunity(session: Session) -> None:
    OpportunityService(OpportunityRepository(session)).create_opportunity(
        OpportunityCreate(
            opportunity_id="opp_route_governance",
            employer_id="comp_a",
            employer_name="Company A",
            program_name="Governed Route Internship",
            program_type=OpportunityProgramType.INTERNSHIP,
            location_mode=OpportunityLocationMode.HYBRID,
            seniority_level=OpportunitySeniorityLevel.INTERNSHIP,
            eligibility_summary="Students enrolled in a degree program.",
            application_url="https://example.com/apply/governed-route",
            source_url="https://example.com/careers/governed-route",
            source_type=OpportunitySourceType.EMPLOYER_OFFICIAL,
            application_deadline=date(2099, 1, 1),
            trust_label=OpportunityTrustLabel.VERIFIED,
            review_status=OpportunityReviewStatus.APPROVED,
            region_bindings=(
                OpportunityRegionBindingCreate(
                    region_id="greater_boston",
                    region_label="Greater Boston",
                ),
            ),
            role_family_bindings=(
                OpportunityRoleFamilyBindingCreate(role_family="software_engineering"),
            ),
            created_at=NOW,
        )
    )


def _route_request() -> OpportunityRouteRequest:
    return OpportunityRouteRequest(
        profile_summary="Internship-seeking software engineering student.",
        target_regions=("greater_boston",),
        target_role_families=("software_engineering",),
        preferred_program_types=(OpportunityProgramType.INTERNSHIP,),
        preferred_location_modes=(OpportunityLocationMode.HYBRID,),
        experience_level=OpportunitySeniorityLevel.INTERNSHIP,
        skills=("python",),
        limit=1,
    )


def test_routing_governance_constants() -> None:
    summary = opportunity_governance_summary()

    assert ROUTE_FIRST_OPPORTUNITY_ROUTING_ENABLED is True
    assert OPPORTUNITY_ROUTING_MUTATES_OBJECTIVE_AUTHORITY is False
    assert summary["route_first_routing_enabled"] is True
    assert summary["routing_mutates_objective_authority"] is False
    assert "generic_job_listing_feed" in summary["non_goals"]
    assert "sponsored_ranking" in summary["non_goals"]


def test_route_generation_does_not_mutate_objective_intelligence(
    session: Session,
) -> None:
    _seed_authority_rows(session)
    _seed_opportunity(session)

    payload = OpportunityRouteService(OpportunityRepository(session)).generate_routes(
        _route_request(),
        now=NOW,
    )

    assert payload.routes[0].opportunity_fit_score > 0
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
