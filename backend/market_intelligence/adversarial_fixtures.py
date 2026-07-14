"""Synthetic adversarial fixtures for Layer 34C quality checks."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from backend.market_intelligence.goals import career_goal_definition
from backend.market_intelligence.schemas import (
    CareerGoal,
    ExplainableRankingReport,
    IntelligenceConfidence,
    IntelligenceFreshness,
    MarketInsight,
    MarketIntelligenceProfile,
    OpportunityEnvironment,
    RobustnessScenarioCode,
)
from backend.market_intelligence.scoring import MarketMetrics, rank_profiles


@dataclass(frozen=True, slots=True)
class AdversarialMarketFixture:
    code: str
    market_key: str
    market_name: str
    primary_goal: CareerGoal
    description: str
    expected_scenarios: tuple[RobustnessScenarioCode, ...]
    metrics: MarketMetrics

    def validation_payload(self) -> dict[str, object]:
        """Return deterministic public-safe metadata for fixture validation tests."""

        return {
            "code": self.code,
            "market_key": self.market_key,
            "market_name": self.market_name,
            "primary_goal": self.primary_goal.value,
            "description": self.description,
            "expected_scenarios": tuple(
                scenario.value for scenario in self.expected_scenarios
            ),
            "supporting_metrics": self.metrics.supporting_metrics(),
        }


@dataclass(frozen=True, slots=True)
class AdversarialFixtureBundle:
    fixtures: tuple[AdversarialMarketFixture, ...]
    profiles: tuple[MarketIntelligenceProfile, ...]
    metrics_by_market: Mapping[str, MarketMetrics]
    rankings: Mapping[CareerGoal, ExplainableRankingReport]


def adversarial_market_fixtures() -> tuple[AdversarialMarketFixture, ...]:
    """Build the required Layer 34C synthetic scenario fixtures."""

    return (
        AdversarialMarketFixture(
            code="strong_ai_weak_internships",
            market_key="layer34c_fixture_strong_ai_weak_internships",
            market_name="Synthetic AI Market",
            primary_goal=CareerGoal.AI_ML,
            description=(
                "Synthetic strong AI market with direct AI/cloud evidence and weak "
                "internship coverage."
            ),
            expected_scenarios=(
                RobustnessScenarioCode.MISSING_INTERNSHIP,
                RobustnessScenarioCode.DIRECT_EVIDENCE_REMOVED,
                RobustnessScenarioCode.SMALL_SCORE_PERTURBATION,
            ),
            metrics=_metrics(
                "layer34c_fixture_strong_ai_weak_internships",
                "Synthetic AI Market",
                employer_count=7,
                sector_count=4,
                major_tech_count=3,
                mag7_count=1,
                ai_cloud_employer_count=5,
                cybersecurity_employer_count=1,
                active_posting_total=46,
                role_active_postings={
                    "ai_cloud_adjacent": 36,
                    "cybersecurity": 2,
                    "product": 5,
                },
                internship_total=1,
                coop_total=0,
                entry_level_full_time_total=4,
                formal_program_count=1,
                tech_density_score=8.5,
                early_career_score=4.0,
                observed_zero_fact_count=1,
            ),
        ),
        AdversarialMarketFixture(
            code="broad_employer_weak_early_career",
            market_key="layer34c_fixture_broad_employer_weak_early_career",
            market_name="Synthetic Broad Employer Market",
            primary_goal=CareerGoal.PRODUCT_MANAGEMENT,
            description=(
                "Synthetic broad employer market with weak early-career access and "
                "no direct product evidence."
            ),
            expected_scenarios=(
                RobustnessScenarioCode.DOMINANT_EMPLOYER,
                RobustnessScenarioCode.SOURCE_CONCENTRATION,
                RobustnessScenarioCode.RANKING_EXCLUSION,
            ),
            metrics=_metrics(
                "layer34c_fixture_broad_employer_weak_early_career",
                "Synthetic Broad Employer Market",
                employer_count=20,
                sector_count=8,
                major_tech_count=1,
                mag7_count=0,
                ai_cloud_employer_count=1,
                cybersecurity_employer_count=1,
                active_posting_total=18,
                role_active_postings={
                    "ai_cloud_adjacent": 1,
                    "cybersecurity": 1,
                    "product": 0,
                },
                internship_total=0,
                coop_total=0,
                entry_level_full_time_total=0,
                formal_program_count=0,
                tech_density_score=2.0,
                early_career_score=0.4,
                observed_zero_fact_count=2,
            ),
        ),
        AdversarialMarketFixture(
            code="smaller_market_strong_coop",
            market_key="layer34c_fixture_smaller_market_strong_coop",
            market_name="Synthetic Co-op Market",
            primary_goal=CareerGoal.SOFTWARE_ENGINEERING,
            description=(
                "Synthetic smaller market with strong co-op evidence despite a "
                "smaller employer base."
            ),
            expected_scenarios=(
                RobustnessScenarioCode.MISSING_COOP,
                RobustnessScenarioCode.DIRECT_EVIDENCE_REMOVED,
            ),
            metrics=_metrics(
                "layer34c_fixture_smaller_market_strong_coop",
                "Synthetic Co-op Market",
                employer_count=4,
                sector_count=3,
                major_tech_count=1,
                mag7_count=0,
                ai_cloud_employer_count=1,
                cybersecurity_employer_count=1,
                active_posting_total=13,
                role_active_postings={
                    "ai_cloud_adjacent": 3,
                    "cybersecurity": 2,
                    "product": 2,
                },
                internship_total=4,
                coop_total=12,
                entry_level_full_time_total=5,
                formal_program_count=2,
                tech_density_score=3.5,
                early_career_score=6.0,
                observed_zero_fact_count=1,
            ),
        ),
        AdversarialMarketFixture(
            code="stale_otherwise_strong",
            market_key="layer34c_fixture_stale_otherwise_strong",
            market_name="Synthetic Stale Strong Market",
            primary_goal=CareerGoal.SOFTWARE_ENGINEERING,
            description=(
                "Synthetic otherwise strong market whose primary evidence is stale."
            ),
            expected_scenarios=(
                RobustnessScenarioCode.EXPIRED_SOURCE,
                RobustnessScenarioCode.DIRECT_EVIDENCE_REMOVED,
                RobustnessScenarioCode.MISSING_INTERNSHIP,
            ),
            metrics=_metrics(
                "layer34c_fixture_stale_otherwise_strong",
                "Synthetic Stale Strong Market",
                employer_count=10,
                sector_count=5,
                major_tech_count=3,
                mag7_count=1,
                ai_cloud_employer_count=3,
                cybersecurity_employer_count=2,
                active_posting_total=52,
                role_active_postings={
                    "ai_cloud_adjacent": 12,
                    "cybersecurity": 8,
                    "product": 9,
                },
                internship_total=9,
                coop_total=4,
                entry_level_full_time_total=8,
                formal_program_count=3,
                tech_density_score=8.0,
                early_career_score=8.0,
                confidence_score=0.72,
                confidence=IntelligenceConfidence.MODERATE,
                freshness=IntelligenceFreshness.STALE,
                stale_source_count=1,
                observed_zero_fact_count=1,
                limitations=("One or more source references are stale.",),
            ),
        ),
        AdversarialMarketFixture(
            code="dominant_single_employer",
            market_key="layer34c_fixture_dominant_single_employer",
            market_name="Synthetic Single Employer Market",
            primary_goal=CareerGoal.CYBERSECURITY,
            description=(
                "Synthetic market where otherwise strong evidence is concentrated "
                "in one employer."
            ),
            expected_scenarios=(
                RobustnessScenarioCode.SOURCE_CONCENTRATION,
                RobustnessScenarioCode.DIRECT_EVIDENCE_REMOVED,
                RobustnessScenarioCode.PROXY_ONLY_EVIDENCE,
            ),
            metrics=_metrics(
                "layer34c_fixture_dominant_single_employer",
                "Synthetic Single Employer Market",
                employer_count=1,
                sector_count=1,
                major_tech_count=1,
                mag7_count=0,
                ai_cloud_employer_count=1,
                cybersecurity_employer_count=1,
                active_posting_total=31,
                role_active_postings={
                    "ai_cloud_adjacent": 2,
                    "cybersecurity": 26,
                    "product": 1,
                },
                internship_total=2,
                coop_total=1,
                entry_level_full_time_total=3,
                formal_program_count=1,
                tech_density_score=4.0,
                early_career_score=3.0,
                observed_zero_fact_count=1,
                limitations=(
                    "Employer evidence is concentrated in one dominant employer.",
                ),
            ),
        ),
        AdversarialMarketFixture(
            code="many_unknowns",
            market_key="layer34c_fixture_many_unknowns",
            market_name="Synthetic Unknown Coverage Market",
            primary_goal=CareerGoal.SOFTWARE_ENGINEERING,
            description=(
                "Synthetic market with many unknown count facts that must remain "
                "distinct from observed zeroes."
            ),
            expected_scenarios=(
                RobustnessScenarioCode.UNKNOWN_TO_OBSERVED_ZERO,
                RobustnessScenarioCode.OBSERVED_ZERO_TO_UNKNOWN,
                RobustnessScenarioCode.CONTRADICTORY_INPUTS,
            ),
            metrics=_metrics(
                "layer34c_fixture_many_unknowns",
                "Synthetic Unknown Coverage Market",
                employer_count=6,
                sector_count=4,
                major_tech_count=1,
                mag7_count=0,
                ai_cloud_employer_count=1,
                cybersecurity_employer_count=1,
                active_posting_total=22,
                role_active_postings={
                    "ai_cloud_adjacent": 4,
                    "cybersecurity": 0,
                    "product": 4,
                },
                internship_total=2,
                coop_total=1,
                entry_level_full_time_total=3,
                formal_program_count=1,
                tech_density_score=3.0,
                early_career_score=3.0,
                active_posting_unknown_rows=4,
                internship_unknown_rows=2,
                coop_unknown_rows=2,
                unknown_fact_count=10,
                observed_zero_fact_count=2,
                total_fact_count=18,
                ranking_eligible_fact_count=7,
                confidence_score=0.45,
                confidence=IntelligenceConfidence.LOW,
                limitations=(
                    "Some count facts are unknown and are not treated as zero.",
                ),
            ),
        ),
        AdversarialMarketFixture(
            code="strong_direct_role_evidence",
            market_key="layer34c_fixture_strong_direct_role_evidence",
            market_name="Synthetic Direct Role Market",
            primary_goal=CareerGoal.CYBERSECURITY,
            description=(
                "Synthetic market with strong direct role-family and employer evidence."
            ),
            expected_scenarios=(
                RobustnessScenarioCode.DIRECT_EVIDENCE_REMOVED,
                RobustnessScenarioCode.PROXY_ONLY_EVIDENCE,
            ),
            metrics=_metrics(
                "layer34c_fixture_strong_direct_role_evidence",
                "Synthetic Direct Role Market",
                employer_count=8,
                sector_count=5,
                major_tech_count=2,
                mag7_count=1,
                ai_cloud_employer_count=2,
                cybersecurity_employer_count=5,
                active_posting_total=37,
                role_active_postings={
                    "ai_cloud_adjacent": 5,
                    "cybersecurity": 27,
                    "product": 3,
                },
                internship_total=4,
                coop_total=2,
                entry_level_full_time_total=5,
                formal_program_count=2,
                tech_density_score=6.0,
                early_career_score=5.0,
                observed_zero_fact_count=1,
            ),
        ),
        AdversarialMarketFixture(
            code="mostly_proxy_evidence",
            market_key="layer34c_fixture_mostly_proxy_evidence",
            market_name="Synthetic Proxy Evidence Market",
            primary_goal=CareerGoal.PRODUCT_MANAGEMENT,
            description=(
                "Synthetic market relying mostly on proxy evidence with direct "
                "product-management signals absent."
            ),
            expected_scenarios=(
                RobustnessScenarioCode.DOMINANT_EMPLOYER,
                RobustnessScenarioCode.CONTRADICTORY_INPUTS,
                RobustnessScenarioCode.RANKING_EXCLUSION,
            ),
            metrics=_metrics(
                "layer34c_fixture_mostly_proxy_evidence",
                "Synthetic Proxy Evidence Market",
                employer_count=12,
                sector_count=6,
                major_tech_count=2,
                mag7_count=0,
                ai_cloud_employer_count=2,
                cybersecurity_employer_count=1,
                active_posting_total=24,
                role_active_postings={
                    "ai_cloud_adjacent": 4,
                    "cybersecurity": 2,
                    "product": 0,
                },
                internship_total=0,
                coop_total=0,
                entry_level_full_time_total=5,
                formal_program_count=0,
                tech_density_score=4.5,
                early_career_score=7.0,
                observed_zero_fact_count=2,
            ),
        ),
    )


def build_adversarial_fixture_bundle(
    *,
    goals: Iterable[CareerGoal] = tuple(CareerGoal),
) -> AdversarialFixtureBundle:
    """Return profiles, metrics, and rankings over the synthetic fixtures."""

    fixtures = adversarial_market_fixtures()
    metrics_by_market = {
        fixture.market_key: fixture.metrics for fixture in fixtures
    }
    profiles = tuple(_profile_for_fixture(fixture) for fixture in fixtures)
    rankings = {
        goal: rank_profiles(
            profiles,
            dict(metrics_by_market),
            goal=goal,
            goal_definition=career_goal_definition(goal),
        )
        for goal in tuple(goals)
    }
    return AdversarialFixtureBundle(
        fixtures=fixtures,
        profiles=profiles,
        metrics_by_market=metrics_by_market,
        rankings=rankings,
    )


def _metrics(
    market_key: str,
    market_name: str,
    *,
    employer_count: int,
    sector_count: int,
    major_tech_count: int,
    mag7_count: int,
    ai_cloud_employer_count: int,
    cybersecurity_employer_count: int,
    active_posting_total: int | None,
    role_active_postings: Mapping[str, int],
    internship_total: int | None,
    coop_total: int | None,
    entry_level_full_time_total: int | None,
    formal_program_count: int,
    tech_density_score: float,
    early_career_score: float,
    confidence_score: float = 0.9,
    confidence: IntelligenceConfidence = IntelligenceConfidence.HIGH,
    freshness: IntelligenceFreshness = IntelligenceFreshness.CURRENT,
    active_posting_unknown_rows: int = 0,
    internship_unknown_rows: int = 0,
    coop_unknown_rows: int = 0,
    unknown_fact_count: int = 0,
    observed_zero_fact_count: int = 0,
    total_fact_count: int = 12,
    ranking_eligible_fact_count: int = 12,
    stale_source_count: int = 0,
    limitations: tuple[str, ...] = (),
) -> MarketMetrics:
    observed_hiring_rows = 0 if active_posting_total is None else 2
    role_active = dict(sorted(role_active_postings.items()))
    return MarketMetrics(
        market_key=market_key,
        market_name=market_name,
        region_id=f"region_{market_key}",
        employer_count=employer_count,
        sector_count=sector_count,
        major_tech_count=major_tech_count,
        mag7_count=mag7_count,
        ai_cloud_employer_count=ai_cloud_employer_count,
        cybersecurity_employer_count=cybersecurity_employer_count,
        active_posting_total=active_posting_total,
        active_posting_observed_rows=observed_hiring_rows,
        active_posting_unknown_rows=active_posting_unknown_rows,
        active_posting_zero_rows=observed_zero_fact_count,
        role_active_postings=role_active,
        role_observed_rows={key: 1 for key in role_active},
        role_unknown_rows={"unknown": active_posting_unknown_rows}
        if active_posting_unknown_rows
        else {},
        internship_total=internship_total,
        internship_observed_rows=0 if internship_total is None else 1,
        internship_unknown_rows=internship_unknown_rows,
        coop_total=coop_total,
        coop_observed_rows=0 if coop_total is None else 1,
        coop_unknown_rows=coop_unknown_rows,
        entry_level_full_time_total=entry_level_full_time_total,
        formal_program_count=formal_program_count,
        positive_entry_level_score_count=1 if early_career_score > 0 else 0,
        structural_score=0.7,
        live_market_score=0.7,
        objective_score=0.7,
        tech_density_score=tech_density_score,
        early_career_score=early_career_score,
        source_count=3,
        aging_source_count=0,
        stale_source_count=stale_source_count,
        expired_source_count=0,
        unknown_fact_count=unknown_fact_count,
        observed_zero_fact_count=observed_zero_fact_count,
        total_fact_count=total_fact_count,
        ranking_eligible_fact_count=ranking_eligible_fact_count,
        ranking_excluded_fact_count=0,
        high_gap_count=0,
        medium_gap_count=0,
        confidence_score=confidence_score,
        confidence=confidence,
        freshness=freshness,
        limitations=limitations,
    )


def _profile_for_fixture(
    fixture: AdversarialMarketFixture,
) -> MarketIntelligenceProfile:
    metrics = fixture.metrics
    weaknesses = _weaknesses_for_fixture(fixture)
    opportunity = OpportunityEnvironment(
        hiring_activity=(
            f"{metrics.active_posting_total or 0} synthetic active posting count(s) "
            f"with {metrics.active_posting_unknown_rows} unknown count row(s)."
        ),
        employer_diversity=(
            f"{metrics.employer_count} synthetic employer count(s) across "
            f"{metrics.sector_count} sector(s)."
        ),
        internship_ecosystem=(
            f"{metrics.internship_total if metrics.internship_total is not None else 'unknown'} "
            "synthetic internship count(s)."
        ),
        coop_ecosystem=(
            f"{metrics.coop_total if metrics.coop_total is not None else 'unknown'} "
            "synthetic co-op count(s)."
        ),
        early_career_support=(
            f"Synthetic early-career score is {metrics.early_career_score or 0:g}."
        ),
        hiring_momentum="No unsupported trend is inferred from synthetic fixtures.",
        overall=fixture.description,
    )
    return MarketIntelligenceProfile(
        market_key=fixture.market_key,
        market_name=fixture.market_name,
        region_id=metrics.region_id,
        overview=fixture.description,
        strengths=(
            MarketInsight(
                code=fixture.code,
                message="Synthetic adversarial fixture strength.",
                evidence=(
                    f"{fixture.market_name} uses deterministic synthetic metrics "
                    f"for {fixture.primary_goal.value} stress coverage."
                ),
                impact="Supports read-only scenario tests.",
            ),
        ),
        weaknesses=weaknesses,
        hiring_summary=opportunity.hiring_activity,
        employer_summary=opportunity.employer_diversity,
        internship_summary=opportunity.internship_ecosystem,
        coop_summary=opportunity.coop_ecosystem,
        early_career_summary=opportunity.early_career_support,
        opportunity_environment=opportunity,
        confidence=metrics.confidence,
        confidence_score=metrics.confidence_score,
        freshness=metrics.freshness,
        coverage_summary="Synthetic fixture coverage; no production dataset is altered.",
        limitations=metrics.limitations,
        supporting_metrics=metrics.supporting_metrics(),
    )


def _weaknesses_for_fixture(
    fixture: AdversarialMarketFixture,
) -> tuple[MarketInsight, ...]:
    metrics = fixture.metrics
    weaknesses: list[MarketInsight] = []
    if metrics.internship_total is not None and metrics.internship_total <= 1:
        weaknesses.append(
            _weakness(
                "weak_internship_coverage",
                "Thin early-talent pipeline.",
                f"{metrics.internship_total} synthetic internship count(s) are present.",
            )
        )
    if (metrics.early_career_score or 0) < 1:
        weaknesses.append(
            _weakness(
                "weak_early_career_access",
                "Weak early-career access.",
                f"Synthetic early-career score is {metrics.early_career_score or 0:g}.",
            )
        )
    if metrics.freshness is IntelligenceFreshness.STALE:
        weaknesses.append(
            _weakness(
                "stale_source_fixture",
                "Stale primary evidence.",
                "Synthetic source freshness is stale.",
            )
        )
    if metrics.employer_count <= 1:
        weaknesses.append(
            _weakness(
                "single_employer_concentration",
                "Employer evidence is concentrated.",
                "Synthetic employer count is one.",
            )
        )
    if metrics.unknown_fact_count:
        weaknesses.append(
            _weakness(
                "many_unknown_counts",
                "Many count facts are unknown.",
                (
                    f"{metrics.unknown_fact_count} synthetic count fact(s) are "
                    "unknown and not treated as zero."
                ),
            )
        )
    if fixture.code == "mostly_proxy_evidence":
        weaknesses.append(
            _weakness(
                "proxy_only_role_evidence",
                "Direct product-management evidence is absent.",
                "Synthetic product role and formal program counts are zero.",
            )
        )
    return tuple(weaknesses) or (
        _weakness(
            "adversarial_fixture_context",
            "Synthetic stress fixture.",
            "This fixture is for deterministic adversarial test coverage.",
        ),
    )


def _weakness(code: str, message: str, evidence: str) -> MarketInsight:
    return MarketInsight(
        code=code,
        message=message,
        evidence=evidence,
        impact="Used to stress ranking, sufficiency, or robustness behavior.",
    )
