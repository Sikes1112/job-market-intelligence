from __future__ import annotations

import ast
import json
import socket
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.api.protection import _public_demo_route_allowed
from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.hiring.models import CompanyRegionHiring
from backend.imports.bulk import (
    import_all_curated_market_datasets,
    run_all_curated_market_post_imports,
)
from backend.imports.registry import load_market_registry
from backend.market_intelligence.calibration import build_calibration_report
from backend.market_intelligence.comparisons import compare_ranked_markets
from backend.market_intelligence.contradictions import (
    apply_comparison_contradictions,
    apply_ranking_contradictions,
    evaluate_ranking_item_contradictions,
)
from backend.market_intelligence.differentiation import evaluate_market_differentiation
from backend.market_intelligence.evaluation import (
    PRODUCT_QUALITY_DIFFERENTIATION_THRESHOLD,
    PRODUCT_QUALITY_EVALUATION_REPORT_ARTIFACT_PATH,
    _stability_alignment_check,
    build_product_quality_evaluation_report,
)
from backend.market_intelligence.explanations import explanation_language_rejections
from backend.market_intelligence.goals import (
    GOAL_COMPONENT_WEIGHTS,
    career_goal_definition,
    career_goal_definitions,
    classify_goal_evidence,
)
from backend.market_intelligence.robustness import (
    _scenario_result,
    evaluate_ranking_robustness,
)
from backend.market_intelligence.schemas import (
    CalibrationTieStatus,
    CareerGoal,
    CareerGoalDefinition,
    ComparisonOutcome,
    ContradictionCode,
    ContradictionFinding,
    ContradictionSeverity,
    ContradictionStatus,
    DifferentiationFindingCode,
    DifferentiationSeverity,
    EvidenceBasis,
    EvidenceGrounding,
    EvidenceSufficiency,
    ExplainableRankingItem,
    ExplainableRankingReport,
    ExplanationQualityStatus,
    IntelligenceConfidence,
    IntelligenceFreshness,
    MarketComparisonReport,
    MarketComparisonSide,
    MarketInsight,
    MarketIntelligenceProfile,
    OpportunityEnvironment,
    RankingDriver,
    RankingStabilityStatus,
    RobustnessScenarioCode,
    RobustnessScenarioRankingResult,
)
from backend.market_intelligence.scoring import MarketMetrics, rank_profiles
from backend.market_intelligence.service import MarketIntelligenceService
from backend.market_intelligence.sufficiency import evaluate_ranking_sufficiency
from backend.presence.models import CompanyRegionPresence
from backend.provenance.models import FactSourceLink, SourceRef
from backend.scoring.models import RegionMarketScore
from backend.trust.models import (
    AutomatedRecheckJob,
    ExceptionCase,
    RiskRoutingDecision,
    TrustAssessment,
    UserReport,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
AS_OF = date(2026, 7, 9)
EXPECTED_MARKETS = {
    "nyc",
    "seattle",
    "san_francisco_bay_area",
    "boston",
    "washington_dc",
    "austin",
    "atlanta",
    "chicago",
}
EXPECTED_ROBUSTNESS_SCENARIOS = frozenset(
    {
        "unknown_to_observed_zero",
        "observed_zero_to_unknown",
        "stale_source",
        "expired_source",
        "low_confidence_exclusion",
        "ranking_exclusion",
        "missing_internship",
        "missing_coop",
        "dominant_employer",
        "source_concentration",
        "sparse_coverage",
        "direct_evidence_removed",
        "proxy_only_evidence",
        "equal_evidence_tie",
        "small_score_perturbation",
        "contradictory_inputs",
    }
)
_CONFIDENCE_ORDER_FOR_TEST = {
    IntelligenceConfidence.LIMITED: 1,
    IntelligenceConfidence.LOW: 2,
    IntelligenceConfidence.MODERATE: 3,
    IntelligenceConfidence.HIGH: 4,
}


def test_layer34_platform_profiles_are_deterministic_and_semantic(
    session: Session,
) -> None:
    _seed_all_markets(session)
    service = MarketIntelligenceService(session)

    first = service.platform_summary(as_of=AS_OF).as_dict()
    second = service.platform_summary(as_of=AS_OF).as_dict()

    assert first == second
    assert first["market_count"] == 8
    assert first["profile_count"] == 8
    assert {profile["market_key"] for profile in first["profiles"]} == EXPECTED_MARKETS
    assert first["default_ranking"]["top_market_key"] in EXPECTED_MARKETS
    assert first["public_summary"]
    assert {goal["goal"] for goal in first["supported_goals"]} == CareerGoal.values()

    for profile in first["profiles"]:
        assert profile["overview"]
        assert profile["strengths"]
        assert profile["weaknesses"]
        assert profile["confidence"] in IntelligenceConfidence.values()
        assert profile["freshness"] in IntelligenceFreshness.values()
        assert profile["coverage_summary"]
        assert profile["opportunity_environment"]["overall"]
        metrics = profile["supporting_metrics"]
        assert metrics["ranking_eligible_fact_count"] == 13
        assert metrics["ranking_excluded_fact_count"] == 0
        assert "unknown_fact_count" in metrics
        assert "observed_zero_fact_count" in metrics
    assert any(
        "not treated as zero" in " ".join(profile["limitations"])
        for profile in first["profiles"]
    )
    assert any(
        profile["supporting_metrics"]["unknown_fact_count"] > 0
        for profile in first["profiles"]
    )
    assert any(
        profile["supporting_metrics"]["observed_zero_fact_count"] > 0
        for profile in first["profiles"]
    )
    assert len(
        {
            profile["supporting_metrics"]["unknown_fact_count"]
            for profile in first["profiles"]
        }
    ) > 1
    assert len(
        {
            profile["supporting_metrics"]["observed_zero_fact_count"]
            for profile in first["profiles"]
        }
    ) > 1


def test_layer34_market_profile_opportunity_environment_uses_canonical_metrics(
    session: Session,
) -> None:
    _seed_all_markets(session)
    profile = MarketIntelligenceService(session).profile("nyc", as_of=AS_OF).as_dict()

    assert profile["market_key"] == "nyc"
    assert "curated employer" in profile["employer_summary"]
    assert "observed active posting" in profile["hiring_summary"]
    assert "internship" in profile["internship_summary"]
    assert "co-op" in profile["coop_summary"]
    assert "early-career" in profile["early_career_summary"]
    assert "unsupported trend" in profile["opportunity_environment"]["hiring_momentum"]
    for key, status_key in (
        ("product_active_postings", "product_activity_status"),
        ("ai_cloud_active_postings", "ai_cloud_activity_status"),
        ("cybersecurity_active_postings", "cybersecurity_activity_status"),
    ):
        value = profile["supporting_metrics"][key]
        if value is None:
            assert profile["supporting_metrics"][status_key] in {"unknown", "unavailable"}
        else:
            assert value >= 0


def test_layer34_comparisons_are_deterministic_explainable_and_tie_safe(
    session: Session,
) -> None:
    _seed_all_markets(session)
    service = MarketIntelligenceService(session)

    ranking = service.ranking(goal=CareerGoal.AI_ML, as_of=AS_OF)
    repeated = service.ranking(goal=CareerGoal.AI_ML, as_of=AS_OF)
    assert ranking.as_dict() == repeated.as_dict()
    assert [item.rank for item in ranking.ranked_markets] == list(range(1, 9))
    assert [item.score for item in ranking.ranked_markets] == sorted(
        (item.score for item in ranking.ranked_markets),
        reverse=True,
    )
    for item in ranking.ranked_markets:
        assert item.ranking_drivers
        assert [driver.contribution for driver in item.ranking_drivers] == sorted(
            (driver.contribution for driver in item.ranking_drivers),
            reverse=True,
        )
        assert "component_ai_cloud_activity" in item.supporting_metrics
        if item.supporting_metrics["component_ai_cloud_activity"] is None:
            assert item.supporting_metrics["ai_cloud_activity_status"] in {
                "unknown",
                "unavailable",
            }

    comparison = service.comparison(
        "atlanta",
        "boston",
        goal=CareerGoal.PRODUCT_MANAGEMENT,
        as_of=AS_OF,
    )
    assert comparison.as_dict() == service.comparison(
        "atlanta",
        "boston",
        goal=CareerGoal.PRODUCT_MANAGEMENT,
        as_of=AS_OF,
    ).as_dict()
    assert comparison.winner_market_key in {"atlanta", "boston"}
    assert comparison.explanation
    assert comparison.supporting_metrics["score_delta"] >= 0

    tied = service.comparison(
        "nyc",
        "nyc",
        goal=CareerGoal.SOFTWARE_ENGINEERING,
        as_of=AS_OF,
    )
    assert tied.outcome is ComparisonOutcome.TIE
    assert tied.winner_market_key is None
    assert "tied" in tied.explanation


def test_layer34_career_goals_return_recommendations_or_explicit_abstentions(
    session: Session,
) -> None:
    _seed_all_markets(session)
    service = MarketIntelligenceService(session)

    for goal in CareerGoal:
        report = service.career_goal_comparison(goal=goal, as_of=AS_OF)
        payload = report.as_dict()
        assert payload["goal"] == goal.value
        assert payload["recommendation_summary"]
        assert payload["confidence"] in IntelligenceConfidence.values()
        assert payload["evidence_sufficiency"] in EvidenceSufficiency.values()
        assert len(payload["ranking"]["ranked_markets"]) == 8
        if payload["evidence_sufficiency"] in {
            EvidenceSufficiency.INSUFFICIENT_EVIDENCE.value,
            EvidenceSufficiency.NOT_SUPPORTED.value,
        }:
            assert payload["recommended_market_key"] is None
            assert payload["abstention_reason"]
            assert "No firm" in payload["recommendation_summary"]
        else:
            assert payload["recommended_market_key"] in EXPECTED_MARKETS
        _assert_public_payload_safe(payload)

    data_science = service.career_goal_comparison(
        goal=CareerGoal.DATA_SCIENCE,
        as_of=AS_OF,
    )
    assert data_science.evidence_sufficiency is EvidenceSufficiency.NOT_SUPPORTED
    assert data_science.recommended_market_key is None
    assert any("data-science" in item for item in data_science.limitations)


def test_layer34_confidence_and_freshness_reflect_layer33_diagnostics(
    session: Session,
) -> None:
    _seed_all_markets(session)
    service = MarketIntelligenceService(session)
    current = service.profile("nyc", as_of=AS_OF)
    source = session.get(SourceRef, "src_nyc_hiring_snapshot_2026_06")
    source.observed_at = datetime(2024, 1, 1, tzinfo=UTC)
    session.flush()

    stale = service.profile("nyc", as_of=AS_OF)

    assert stale.freshness is IntelligenceFreshness.STALE
    assert stale.confidence_score < current.confidence_score
    assert "One or more source references are stale." in stale.limitations


def test_layer34_api_routes_are_schema_shaped_public_safe_and_deterministic(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_all_markets(session)

    endpoints = (
        "/market-intelligence",
        "/market-intelligence/nyc",
        "/market-comparisons",
        "/market-comparisons/atlanta/boston?goal=product_management",
        "/career-goal-comparisons?goal=data_science",
        "/career-goal-comparisons/data_science",
        "/career-goal-comparisons",
    )
    for endpoint in endpoints:
        first = api_client.get(endpoint, params={"as_of": AS_OF.isoformat()})
        second = api_client.get(endpoint, params={"as_of": AS_OF.isoformat()})
        assert first.status_code == 200, endpoint
        assert first.json() == second.json()
        assert first.json()["status"] == "success"
        _assert_public_payload_safe(first.json())

    platform = api_client.get(
        "/market-intelligence",
        params={"as_of": AS_OF.isoformat()},
    ).json()["data"]
    assert platform["market_count"] == 8
    assert platform["default_ranking"]["top_market_key"] in EXPECTED_MARKETS

    goals = api_client.get(
        "/career-goal-comparisons",
        params={"as_of": AS_OF.isoformat()},
    ).json()["data"]
    assert {item["goal"] for item in goals["comparisons"]} == CareerGoal.values()

    missing = api_client.get(
        "/market-intelligence/not_registered",
        params={"as_of": AS_OF.isoformat()},
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"
    _assert_public_payload_safe(missing.json())

    bad_goal = api_client.get(
        "/market-comparisons",
        params={"goal": "not_a_goal", "as_of": AS_OF.isoformat()},
    )
    assert bad_goal.status_code == 400
    assert bad_goal.json()["error"]["code"] == "VALIDATION_ERROR"
    _assert_public_payload_safe(bad_goal.json())


def test_layer34_routes_are_public_demo_get_only() -> None:
    assert _public_demo_route_allowed("GET", "/market-intelligence")
    assert _public_demo_route_allowed("GET", "/market-intelligence/nyc")
    assert _public_demo_route_allowed("GET", "/market-comparisons")
    assert _public_demo_route_allowed("GET", "/market-comparisons/atlanta/boston")
    assert _public_demo_route_allowed("GET", "/career-goal-comparisons")
    assert _public_demo_route_allowed("GET", "/career-goal-comparisons/data_science")
    assert not _public_demo_route_allowed("POST", "/market-intelligence")
    assert not _public_demo_route_allowed("POST", "/market-comparisons/atlanta/boston")
    assert not _public_demo_route_allowed("GET", "/market-comparisons/atlanta")


def test_layer34_service_and_api_are_read_only(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_all_markets(session)
    before = _table_counts(session)
    service = MarketIntelligenceService(session)

    service.platform_summary(as_of=AS_OF)
    service.profile("nyc", as_of=AS_OF)
    service.ranking(goal=CareerGoal.CYBERSECURITY, as_of=AS_OF)
    service.comparison("nyc", "seattle", goal=CareerGoal.AI_ML, as_of=AS_OF)
    service.career_goal_comparison(goal=CareerGoal.DATA_SCIENCE, as_of=AS_OF)
    api_client.get("/market-intelligence", params={"as_of": AS_OF.isoformat()})
    api_client.get(
        "/market-comparisons/nyc/seattle",
        params={"as_of": AS_OF.isoformat()},
    )
    api_client.get(
        "/career-goal-comparisons",
        params={"goal": "software_engineering", "as_of": AS_OF.isoformat()},
    )

    assert _table_counts(session) == before
    assert session.query(UserReport).count() == 0
    assert session.query(AutomatedRecheckJob).count() == 0
    assert session.query(ExceptionCase).count() == 0


def test_layer34_boundaries_add_no_scraping_scheduler_or_approval_workflow(
    monkeypatch,
    session: Session,
) -> None:
    def _blocked_network(*_args, **_kwargs):
        raise AssertionError("network access is not allowed for Layer 34 intelligence")

    monkeypatch.setattr(socket, "create_connection", _blocked_network)
    _seed_all_markets(session)
    assert MarketIntelligenceService(session).platform_summary(as_of=AS_OF).market_count == 8

    forbidden_imports = {
        "requests",
        "httpx",
        "selenium",
        "playwright",
        "apscheduler",
        "celery",
        "schedule",
    }
    for path in sorted((REPO_ROOT / "backend" / "market_intelligence").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported.update(
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        assert forbidden_imports.isdisjoint(imported)

    assert session.query(UserReport).count() == 0
    assert session.query(AutomatedRecheckJob).count() == 0
    assert session.query(ExceptionCase).count() == 0


def test_layer34c_goal_registry_definitions_are_complete_and_route_free() -> None:
    definitions = career_goal_definitions()

    assert tuple(definition.goal for definition in definitions) == tuple(CareerGoal)
    json.dumps([definition.as_dict() for definition in definitions], sort_keys=True)
    _assert_public_payload_safe([definition.as_dict() for definition in definitions])

    for definition in definitions:
        label_codes = {label.code for label in definition.public_safe_labels}
        assert definition.direct_evidence_categories
        assert definition.proxy_evidence_categories
        assert definition.minimum_direct_evidence >= 1
        assert definition.minimum_total_evidence >= definition.minimum_direct_evidence
        assert definition.proxy_only_confidence_cap in {
            IntelligenceConfidence.LOW,
            IntelligenceConfidence.LIMITED,
        }
        assert definition.unsupported_conditions
        assert definition.weighting_rationale
        assert set(definition.direct_evidence_categories).issubset(label_codes)
        assert set(definition.proxy_evidence_categories).issubset(label_codes)
        assert set(definition.direct_evidence_categories).isdisjoint(
            definition.proxy_evidence_categories
        )

    route_source = (REPO_ROOT / "backend" / "api" / "market_intelligence.py").read_text(
        encoding="utf-8"
    )
    assert "GOAL_COMPONENT_WEIGHTS" not in route_source
    assert "direct_evidence_categories" not in route_source
    assert "career_goal_definition" not in route_source


def test_layer34c_goal_weights_and_definitions_are_not_aliases() -> None:
    signatures = {}
    for goal in CareerGoal:
        definition = career_goal_definition(goal)
        weights = GOAL_COMPONENT_WEIGHTS[goal]
        assert round(sum(weights.values()), 8) == 1.0
        assert set(weights).issubset(
            set(definition.direct_evidence_categories)
            | set(definition.proxy_evidence_categories)
        )
        signatures[goal] = (
            definition.direct_evidence_categories,
            definition.proxy_evidence_categories,
            tuple(weights.items()),
            definition.weighting_rationale,
        )

    assert len(set(signatures.values())) == len(CareerGoal)

    goals_using_generic_company_counts = {
        goal for goal, weights in GOAL_COMPONENT_WEIGHTS.items() if "employer_presence" in weights
    }
    assert goals_using_generic_company_counts
    assert goals_using_generic_company_counts != set(CareerGoal)
    for goal in goals_using_generic_company_counts:
        weights = GOAL_COMPONENT_WEIGHTS[goal]
        assert weights["employer_presence"] < max(weights.values())


def test_layer34c_direct_vs_proxy_classification_is_goal_specific() -> None:
    product = classify_goal_evidence(
        CareerGoal.PRODUCT_MANAGEMENT,
        ("product_activity", "employer_presence"),
    )

    assert product.evidence_basis is EvidenceBasis.DIRECT_AND_PROXY
    assert product.direct_evidence_categories == ("product_activity",)
    assert product.proxy_evidence_categories == ("employer_presence",)
    assert product.direct_evidence_count == 1
    assert product.proxy_evidence_count == 1
    assert product.meets_minimum_direct_evidence
    assert product.meets_minimum_total_evidence

    generic_program_product = classify_goal_evidence(
        CareerGoal.PRODUCT_MANAGEMENT,
        ("formal_programs", "early_career", "employer_presence"),
    )
    assert generic_program_product.evidence_basis is EvidenceBasis.PROXY
    assert generic_program_product.direct_evidence_categories == ()
    assert generic_program_product.proxy_evidence_categories == (
        "formal_programs",
        "early_career",
        "employer_presence",
    )
    assert generic_program_product.direct_evidence_count == 0
    assert generic_program_product.proxy_evidence_count == 3
    assert not generic_program_product.meets_minimum_direct_evidence
    assert generic_program_product.meets_minimum_total_evidence

    cyber_proxy_only = classify_goal_evidence(
        CareerGoal.CYBERSECURITY,
        ("hiring_activity",),
    )
    assert cyber_proxy_only.evidence_basis is EvidenceBasis.PROXY
    assert cyber_proxy_only.direct_evidence_count == 0
    assert cyber_proxy_only.proxy_evidence_categories == ("hiring_activity",)
    assert not cyber_proxy_only.meets_minimum_direct_evidence
    assert cyber_proxy_only.proxy_only_confidence_cap is IntelligenceConfidence.LOW

    ai_unknown = classify_goal_evidence(
        CareerGoal.AI_ML,
        ("tech_signal", "not_a_goal_evidence_category"),
    )
    assert ai_unknown.evidence_basis is EvidenceBasis.PROXY
    assert ai_unknown.proxy_evidence_categories == ("tech_signal",)
    assert ai_unknown.unknown_evidence_categories == ("not_a_goal_evidence_category",)


def test_layer34c_data_science_is_explicitly_proxy_limited() -> None:
    definition = career_goal_definition(CareerGoal.DATA_SCIENCE)
    weights = GOAL_COMPONENT_WEIGHTS[CareerGoal.DATA_SCIENCE]

    assert "data-science" in " ".join(definition.limitations)
    assert "data-science" in " ".join(definition.unsupported_conditions)
    assert "proxy" in definition.weighting_rationale
    assert set(weights).issubset(definition.proxy_evidence_categories)
    assert set(weights).isdisjoint(definition.direct_evidence_categories)

    classification = classify_goal_evidence(CareerGoal.DATA_SCIENCE, weights.keys())
    assert classification.evidence_basis is EvidenceBasis.PROXY
    assert classification.direct_evidence_count == 0
    assert classification.proxy_evidence_count == len(weights)
    assert classification.minimum_direct_evidence == 1
    assert not classification.meets_minimum_direct_evidence
    assert classification.meets_minimum_total_evidence
    assert classification.proxy_only_confidence_cap is IntelligenceConfidence.LIMITED


def test_layer34c_sufficiency_gates_cover_all_states_and_confidence_caps() -> None:
    ready = evaluate_ranking_sufficiency(
        goal=CareerGoal.SOFTWARE_ENGINEERING,
        evidence_categories=("hiring_activity", "tech_signal", "early_career"),
        score=0.82,
        confidence=IntelligenceConfidence.HIGH,
        freshness=IntelligenceFreshness.CURRENT,
        supporting_metrics={"ranking_eligible_fact_count": 5, "unknown_fact_count": 0},
        limitations=(),
    )
    assert ready.sufficiency is EvidenceSufficiency.COMPARISON_READY
    assert ready.capped_confidence is IntelligenceConfidence.HIGH
    assert not ready.is_provisional
    assert ready.abstention_reason is None

    limited = evaluate_ranking_sufficiency(
        goal=CareerGoal.PRODUCT_MANAGEMENT,
        evidence_categories=("early_career", "employer_presence"),
        score=0.54,
        confidence=IntelligenceConfidence.HIGH,
        freshness=IntelligenceFreshness.CURRENT,
        supporting_metrics={"ranking_eligible_fact_count": 5, "unknown_fact_count": 0},
        limitations=(),
    )
    assert limited.sufficiency is EvidenceSufficiency.LIMITED_EVIDENCE
    assert limited.capped_confidence is IntelligenceConfidence.LOW
    assert limited.is_provisional
    assert limited.abstention_reason is None
    assert "provisional" in " ".join(limited.limitations)

    insufficient = evaluate_ranking_sufficiency(
        goal=CareerGoal.CYBERSECURITY,
        evidence_categories=("hiring_activity",),
        score=0.21,
        confidence=IntelligenceConfidence.HIGH,
        freshness=IntelligenceFreshness.CURRENT,
        supporting_metrics={"ranking_eligible_fact_count": 5, "unknown_fact_count": 0},
        limitations=(),
    )
    assert insufficient.sufficiency is EvidenceSufficiency.INSUFFICIENT_EVIDENCE
    assert insufficient.capped_confidence is IntelligenceConfidence.LIMITED
    assert insufficient.abstention_reason
    assert "Insufficient evidence" in " ".join(insufficient.limitations)

    not_supported = evaluate_ranking_sufficiency(
        goal=CareerGoal.DATA_SCIENCE,
        evidence_categories=("ai_cloud_activity", "product_activity", "tech_signal"),
        score=0.64,
        confidence=IntelligenceConfidence.HIGH,
        freshness=IntelligenceFreshness.CURRENT,
        supporting_metrics={"ranking_eligible_fact_count": 5, "unknown_fact_count": 0},
        limitations=(),
    )
    assert not_supported.sufficiency is EvidenceSufficiency.NOT_SUPPORTED
    assert not_supported.capped_confidence is IntelligenceConfidence.LIMITED
    assert not_supported.abstention_reason
    assert "current canonical data model" in " ".join(not_supported.limitations)


def test_layer34c_product_management_generic_formal_programs_are_proxy_only() -> None:
    generic_program_metrics = replace(
        _robustness_metrics(
            "generic_program_pm",
            active_postings=10,
            employers=6,
            tech_density=2.0,
            early_career=3.0,
            internship=0,
            coop=0,
            product=0,
            ai_cloud=0,
            cybersecurity=0,
        ),
        market_name="Generic Program PM",
        entry_level_full_time_total=0,
        formal_program_count=4,
        unknown_fact_count=0,
        observed_zero_fact_count=1,
        limitations=(),
    )
    comparison_metrics = replace(
        _robustness_metrics(
            "comparison_pm",
            active_postings=4,
            employers=2,
            tech_density=1.0,
            early_career=0.5,
            internship=0,
            coop=0,
            product=0,
            ai_cloud=0,
            cybersecurity=0,
        ),
        market_name="Comparison PM",
        entry_level_full_time_total=0,
        formal_program_count=0,
        unknown_fact_count=0,
        observed_zero_fact_count=1,
        limitations=(),
    )
    metrics_by_market = {
        generic_program_metrics.market_key: generic_program_metrics,
        comparison_metrics.market_key: comparison_metrics,
    }
    ranking = rank_profiles(
        tuple(_robustness_profile(metrics) for metrics in metrics_by_market.values()),
        metrics_by_market,
        goal=CareerGoal.PRODUCT_MANAGEMENT,
        goal_definition=career_goal_definition(CareerGoal.PRODUCT_MANAGEMENT),
    )
    item = next(
        ranked
        for ranked in ranking.ranked_markets
        if ranked.market_key == "generic_program_pm"
    )

    assert item.supporting_metrics["formal_program_count"] == 4
    assert item.supporting_metrics["product_active_postings"] == 0
    assert item.supporting_metrics["direct_evidence_count"] == 0
    assert item.supporting_metrics["proxy_evidence_count"] >= 1
    assert item.evidence_basis is EvidenceBasis.PROXY
    assert item.evidence_sufficiency is EvidenceSufficiency.LIMITED_EVIDENCE
    assert item.confidence is IntelligenceConfidence.LOW
    assert item.grounding is not None
    assert all(
        "formal" not in summary.casefold()
        for summary in item.grounding.direct_evidence_summary
    )
    assert any(
        "Generic formal early-career program proxy" in summary
        for summary in item.grounding.proxy_evidence_summary
    )
    assert "formal_programs" in {
        driver.code for driver in item.ranking_drivers
    }


def test_layer34c_ranking_abstains_for_not_supported_goal(session: Session) -> None:
    _seed_all_markets(session)

    ranking = MarketIntelligenceService(session).ranking(
        goal=CareerGoal.DATA_SCIENCE,
        as_of=AS_OF,
    )
    payload = ranking.as_dict()

    assert ranking.evidence_sufficiency is EvidenceSufficiency.NOT_SUPPORTED
    assert ranking.top_market_key is None
    assert ranking.abstention_reason
    assert "abstains" in ranking.explanation
    assert "diagnostic ordering" in ranking.explanation
    assert {item.evidence_sufficiency for item in ranking.ranked_markets} == {
        EvidenceSufficiency.NOT_SUPPORTED
    }
    assert {item.confidence for item in ranking.ranked_markets} == {
        IntelligenceConfidence.LIMITED
    }
    assert payload["ranked_markets"][0]["evidence_sufficiency"] == (
        EvidenceSufficiency.NOT_SUPPORTED.value
    )
    assert payload["ranked_markets"][0]["abstention_reason"]
    assert "Any ranked order is diagnostic ordering only." in " ".join(
        payload["ranked_markets"][0]["limitations"]
    )
    _assert_public_payload_safe(payload)


def test_layer34c_pairwise_comparison_can_return_no_winner() -> None:
    left = _calibration_item(
        "alpha",
        rank=1,
        score=0.7,
        evidence_sufficiency=EvidenceSufficiency.INSUFFICIENT_EVIDENCE,
        confidence=IntelligenceConfidence.LIMITED,
        abstention_reason="there is not enough qualifying ranking evidence",
    )
    right = _calibration_item(
        "beta",
        rank=2,
        score=0.3,
        evidence_sufficiency=EvidenceSufficiency.COMPARISON_READY,
        confidence=IntelligenceConfidence.HIGH,
    )

    comparison = compare_ranked_markets(
        "alpha",
        "beta",
        goal=CareerGoal.SOFTWARE_ENGINEERING,
        ranking_items=(left, right),
    )
    payload = comparison.as_dict()

    assert comparison.outcome is ComparisonOutcome.NO_WINNER
    assert comparison.winner_market_key is None
    assert comparison.evidence_sufficiency is EvidenceSufficiency.INSUFFICIENT_EVIDENCE
    assert comparison.confidence is IntelligenceConfidence.LIMITED
    assert comparison.abstention_reason
    assert "does not name a winner" in comparison.explanation
    assert payload["outcome"] == ComparisonOutcome.NO_WINNER.value
    assert payload["winner_market_key"] is None
    _assert_public_payload_safe(payload)


def test_layer34c_api_schema_exposes_sufficiency_and_safe_abstention(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_all_markets(session)

    ranking = api_client.get(
        "/market-comparisons",
        params={"goal": "data_science", "as_of": AS_OF.isoformat()},
    ).json()["data"]
    assert ranking["evidence_sufficiency"] == EvidenceSufficiency.NOT_SUPPORTED.value
    assert ranking["top_market_key"] is None
    assert ranking["abstention_reason"]
    assert ranking["ranked_markets"]
    assert {
        "evidence_sufficiency",
        "evidence_basis",
        "is_provisional",
        "abstention_reason",
    }.issubset(ranking["ranked_markets"][0])

    comparison = api_client.get(
        "/market-comparisons/atlanta/boston",
        params={"goal": "data_science", "as_of": AS_OF.isoformat()},
    ).json()["data"]
    assert comparison["outcome"] == ComparisonOutcome.NO_WINNER.value
    assert comparison["winner_market_key"] is None
    assert comparison["evidence_sufficiency"] == EvidenceSufficiency.NOT_SUPPORTED.value
    assert comparison["abstention_reason"]
    assert comparison["confidence"] == IntelligenceConfidence.LIMITED.value
    assert {
        "evidence_sufficiency",
        "evidence_basis",
    }.issubset(comparison["market_a"])

    goal_report = api_client.get(
        "/career-goal-comparisons/data_science",
        params={"as_of": AS_OF.isoformat()},
    ).json()["data"]
    assert goal_report["recommended_market_key"] is None
    assert goal_report["evidence_sufficiency"] == EvidenceSufficiency.NOT_SUPPORTED.value
    assert goal_report["abstention_reason"]
    _assert_public_payload_safe(
        {
            "ranking": ranking,
            "comparison": comparison,
            "goal_report": goal_report,
        }
    )


def test_layer34c_calibration_report_covers_registered_markets_and_goals(
    session: Session,
) -> None:
    _seed_all_markets(session)
    service = MarketIntelligenceService(session)

    payload = service.calibration_report(as_of=AS_OF).as_dict()
    repeated = service.calibration_report(as_of=AS_OF).as_dict()

    ready_markets = {
        key for key, entry in load_market_registry().items() if entry.import_status == "ready"
    }
    assert payload == repeated
    assert set(payload["markets"]) == ready_markets
    assert set(payload["goals"]) == CareerGoal.values()
    assert payload["result_count"] == len(ready_markets) * len(CareerGoal.values())
    assert payload["as_of"] == AS_OF.isoformat()
    assert payload["near_tie_threshold"] > 0
    assert "market key" in payload["tie_breaker"]
    assert set(payload["market_goal_matrix"]) == CareerGoal.values()

    for goal, by_market in payload["market_goal_matrix"].items():
        assert set(by_market) == ready_markets
        assert {item["rank"] for item in by_market.values()} == set(
            range(1, len(ready_markets) + 1)
        )
        for market_key, item in by_market.items():
            assert item["market_key"] == market_key
            assert item["goal"] == goal
            assert isinstance(item["score"], float)
            assert item["score_margin"] >= 0
            assert item["confidence"] in IntelligenceConfidence.values()
            assert item["freshness"] in IntelligenceFreshness.values()
            assert item["evidence_sufficiency"] in EvidenceSufficiency.values()
            assert item["direct_evidence_summary"]
            assert item["proxy_evidence_summary"]
            assert item["top_drivers"]
            assert item["tie_status"] in CalibrationTieStatus.values()
            assert item["stability_status"] in RankingStabilityStatus.values()
            assert {
                scenario["scenario"] for scenario in item["stability_scenarios"]
            } == EXPECTED_ROBUSTNESS_SCENARIOS
            for scenario in item["stability_scenarios"]:
                assert scenario["status"] in RankingStabilityStatus.values()
                assert {
                    "baseline_result",
                    "scenario_result",
                    "rank_change",
                    "winner_change",
                    "score_delta",
                    "confidence_delta",
                    "sufficiency_delta",
                    "explanation",
                }.issubset(scenario)
                assert scenario["baseline_result"]["market_key"] == market_key
                assert scenario["scenario_result"]["market_key"] == market_key
            if item["stability_status"] in {
                RankingStabilityStatus.SENSITIVE.value,
                RankingStabilityStatus.UNSTABLE.value,
            }:
                assert any(
                    "Sensitivity analysis" in limitation
                    for limitation in item["limitations"]
                )
            assert item["contradiction_status"] in ContradictionStatus.values()
            assert isinstance(item["contradictions"], list)


def test_layer34c_calibration_report_marks_exact_and_near_ties() -> None:
    ranking = ExplainableRankingReport(
        goal=CareerGoal.SOFTWARE_ENGINEERING,
        goal_definition=CareerGoalDefinition(
            goal=CareerGoal.SOFTWARE_ENGINEERING,
            label="Software engineering",
            description="Synthetic calibration fixture.",
            direct_signals=("observed hiring facts",),
        ),
        ranked_markets=(
            _calibration_item("alpha", rank=1, score=0.5),
            _calibration_item("beta", rank=2, score=0.5),
            _calibration_item("gamma", rank=3, score=0.506),
        ),
        top_market_key="alpha",
        explanation="Synthetic ranking.",
        limitations=(),
        tie_breaker="Sort by confidence-adjusted score descending, then market key.",
    )

    report = build_calibration_report(
        rankings={CareerGoal.SOFTWARE_ENGINEERING: ranking},
        as_of=AS_OF,
    ).as_dict()
    matrix = report["market_goal_matrix"][CareerGoal.SOFTWARE_ENGINEERING.value]

    assert matrix["alpha"]["tie_status"] == CalibrationTieStatus.TIE.value
    assert matrix["alpha"]["tied_market_keys"] == ["beta"]
    assert matrix["alpha"]["near_tie_market_keys"] == ["gamma"]
    assert matrix["beta"]["tie_status"] == CalibrationTieStatus.TIE.value
    assert matrix["gamma"]["tie_status"] == CalibrationTieStatus.NEAR_TIE.value
    assert matrix["gamma"]["score_margin"] == 0.006
    assert report["tie_breaker"].endswith("market key.")


def test_layer34c_calibration_report_is_read_only(session: Session) -> None:
    _seed_all_markets(session)
    before = _table_counts(session)

    MarketIntelligenceService(session).calibration_report(as_of=AS_OF)

    assert _table_counts(session) == before
    assert session.query(UserReport).count() == 0
    assert session.query(AutomatedRecheckJob).count() == 0
    assert session.query(ExceptionCase).count() == 0


def test_layer34c_calibration_report_serializes_public_safe_unknown_and_zero(
    session: Session,
) -> None:
    _seed_all_markets(session)

    payload = MarketIntelligenceService(session).calibration_report(as_of=AS_OF).as_dict()

    json.dumps(payload, sort_keys=True)
    _assert_public_payload_safe(payload)
    proxy_summaries = [
        " ".join(item["proxy_evidence_summary"])
        for by_market in payload["market_goal_matrix"].values()
        for item in by_market.values()
    ]
    assert any("unknown count fact" in summary for summary in proxy_summaries)
    assert any("observed zero count fact" in summary for summary in proxy_summaries)
    assert any(
        item["evidence_sufficiency"] == EvidenceSufficiency.LIMITED_EVIDENCE.value
        for by_market in payload["market_goal_matrix"].values()
        for item in by_market.values()
    )


def test_layer34c_robustness_engine_outputs_required_scenarios_and_deltas() -> None:
    profiles, metrics_by_market, rankings = _synthetic_robustness_inputs()

    first = evaluate_ranking_robustness(
        rankings=rankings,
        profiles=profiles,
        metrics_by_market=metrics_by_market,
    )
    second = evaluate_ranking_robustness(
        rankings=rankings,
        profiles=profiles,
        metrics_by_market=metrics_by_market,
    )

    assert _stability_payload(first) == _stability_payload(second)

    analysis = first[CareerGoal.SOFTWARE_ENGINEERING]["alpha"]
    scenario_by_code = {scenario.scenario: scenario for scenario in analysis.scenarios}

    assert analysis.status in set(RankingStabilityStatus)
    assert {scenario.value for scenario in scenario_by_code} == (
        EXPECTED_ROBUSTNESS_SCENARIOS
    )
    assert any(
        scenario.status
        in {RankingStabilityStatus.SENSITIVE, RankingStabilityStatus.UNSTABLE}
        for scenario in analysis.scenarios
    )

    for scenario in analysis.scenarios:
        payload = scenario.as_dict()
        json.dumps(payload, sort_keys=True)
        _assert_public_payload_safe(payload)
        assert scenario.baseline_result.market_key == "alpha"
        assert scenario.scenario_result.market_key == "alpha"
        assert isinstance(scenario.rank_change, int)
        assert isinstance(scenario.winner_change, bool)
        assert isinstance(scenario.score_delta, float)
        assert isinstance(scenario.confidence_delta, int)
        assert scenario.sufficiency_delta
        assert scenario.explanation

    assert "zero remains distinct" in scenario_by_code[
        RobustnessScenarioCode.UNKNOWN_TO_OBSERVED_ZERO
    ].explanation
    assert scenario_by_code[
        RobustnessScenarioCode.OBSERVED_ZERO_TO_UNKNOWN
    ].confidence_delta <= 0
    assert (
        scenario_by_code[RobustnessScenarioCode.STALE_SOURCE].scenario_result.freshness
        is IntelligenceFreshness.STALE
    )
    assert (
        scenario_by_code[RobustnessScenarioCode.EXPIRED_SOURCE].scenario_result.freshness
        is IntelligenceFreshness.STALE
    )
    assert scenario_by_code[
        RobustnessScenarioCode.EXPIRED_SOURCE
    ].confidence_delta <= 0
    assert "expired" in scenario_by_code[
        RobustnessScenarioCode.EXPIRED_SOURCE
    ].explanation
    assert "source coverage" in scenario_by_code[
        RobustnessScenarioCode.SOURCE_CONCENTRATION
    ].explanation
    assert "contradictory-input" in scenario_by_code[
        RobustnessScenarioCode.CONTRADICTORY_INPUTS
    ].explanation
    assert "small perturbation" in scenario_by_code[
        RobustnessScenarioCode.SMALL_SCORE_PERTURBATION
    ].explanation
    assert scenario_by_code[
        RobustnessScenarioCode.EQUAL_EVIDENCE_TIE
    ].score_delta <= 0
    assert "market-key ordering" in scenario_by_code[
        RobustnessScenarioCode.EQUAL_EVIDENCE_TIE
    ].explanation


def test_layer34c_robustness_missing_data_never_improves_confidence_silently() -> None:
    profiles, metrics_by_market, rankings = _synthetic_robustness_inputs()
    analysis = evaluate_ranking_robustness(
        rankings=rankings,
        profiles=profiles,
        metrics_by_market=metrics_by_market,
    )[CareerGoal.SOFTWARE_ENGINEERING]["alpha"]

    missing_data_scenarios = {
        RobustnessScenarioCode.OBSERVED_ZERO_TO_UNKNOWN,
        RobustnessScenarioCode.STALE_SOURCE,
        RobustnessScenarioCode.EXPIRED_SOURCE,
        RobustnessScenarioCode.LOW_CONFIDENCE_EXCLUSION,
        RobustnessScenarioCode.RANKING_EXCLUSION,
        RobustnessScenarioCode.MISSING_INTERNSHIP,
        RobustnessScenarioCode.MISSING_COOP,
        RobustnessScenarioCode.SPARSE_COVERAGE,
        RobustnessScenarioCode.DIRECT_EVIDENCE_REMOVED,
        RobustnessScenarioCode.PROXY_ONLY_EVIDENCE,
    }
    scenario_by_code = {scenario.scenario: scenario for scenario in analysis.scenarios}

    for code in missing_data_scenarios:
        scenario = scenario_by_code[code]
        assert scenario.confidence_delta <= 0
        assert scenario.score_delta <= 0
        assert scenario.rank_change >= 0
        assert "confidence delta" in scenario.explanation


def test_layer34c_missing_data_improvement_is_flagged_unstable() -> None:
    baseline = RobustnessScenarioRankingResult(
        market_key="alpha",
        rank=3,
        score=0.5000,
        confidence=IntelligenceConfidence.MODERATE,
        freshness=IntelligenceFreshness.CURRENT,
        evidence_sufficiency=EvidenceSufficiency.COMPARISON_READY,
        top_market_key="leader",
    )
    improved_by_missing_data = RobustnessScenarioRankingResult(
        market_key="alpha",
        rank=2,
        score=0.5100,
        confidence=IntelligenceConfidence.MODERATE,
        freshness=IntelligenceFreshness.CURRENT,
        evidence_sufficiency=EvidenceSufficiency.COMPARISON_READY,
        top_market_key="leader",
    )

    result = _scenario_result(
        scenario_code=RobustnessScenarioCode.OBSERVED_ZERO_TO_UNKNOWN,
        label="Observed zero becomes unknown",
        baseline=baseline,
        scenario=improved_by_missing_data,
        applied=True,
        missing_data=True,
        reason="missing evidence is represented as unknown.",
    )

    assert result.score_delta > 0
    assert result.rank_change < 0
    assert result.status is RankingStabilityStatus.UNSTABLE
    assert "is unstable" in result.explanation


def test_layer34c_robustness_small_score_perturbation_flags_winner_reversal() -> None:
    profiles, metrics_by_market, _rankings = _synthetic_robustness_inputs()
    alpha = _contradiction_item("alpha", rank=1, score=0.7000)
    beta = _contradiction_item("beta", rank=2, score=0.6950)
    ranking = ExplainableRankingReport(
        goal=CareerGoal.SOFTWARE_ENGINEERING,
        goal_definition=career_goal_definition(CareerGoal.SOFTWARE_ENGINEERING),
        ranked_markets=(alpha, beta),
        top_market_key="alpha",
        explanation="Synthetic near-tie ranking.",
        limitations=(),
        tie_breaker="Sort by confidence-adjusted score descending, then market key.",
        evidence_sufficiency=EvidenceSufficiency.COMPARISON_READY,
    )

    analysis = evaluate_ranking_robustness(
        rankings={CareerGoal.SOFTWARE_ENGINEERING: ranking},
        profiles=tuple(
            profile for profile in profiles if profile.market_key in {"alpha", "beta"}
        ),
        metrics_by_market=metrics_by_market,
    )[CareerGoal.SOFTWARE_ENGINEERING]["alpha"]
    scenario = next(
        item
        for item in analysis.scenarios
        if item.scenario is RobustnessScenarioCode.SMALL_SCORE_PERTURBATION
    )

    assert scenario.status is RankingStabilityStatus.UNSTABLE
    assert scenario.winner_change
    assert scenario.rank_change == 1
    assert -0.01 <= scenario.score_delta < 0
    assert "small perturbation" in scenario.explanation


def test_layer34c_robustness_engine_does_not_mutate_inputs() -> None:
    profiles, metrics_by_market, rankings = _synthetic_robustness_inputs()
    before_rankings = {
        goal.value: report.as_dict() for goal, report in rankings.items()
    }
    before_profiles = [profile.as_dict() for profile in profiles]
    before_metrics = {
        market_key: metrics.supporting_metrics()
        for market_key, metrics in metrics_by_market.items()
    }

    evaluate_ranking_robustness(
        rankings=rankings,
        profiles=profiles,
        metrics_by_market=metrics_by_market,
    )

    assert {goal.value: report.as_dict() for goal, report in rankings.items()} == (
        before_rankings
    )
    assert [profile.as_dict() for profile in profiles] == before_profiles
    assert {
        market_key: metrics.supporting_metrics()
        for market_key, metrics in metrics_by_market.items()
    } == before_metrics


def test_layer34c_role_specific_unknown_activity_does_not_outscore_observed_zero() -> None:
    unknown_metrics = replace(
        _robustness_metrics(
            "unknown_role",
            active_postings=20,
            employers=4,
            tech_density=2.0,
            early_career=3.0,
            internship=2,
            coop=1,
            product=0,
            ai_cloud=0,
            cybersecurity=0,
        ),
        market_name="Unknown Role",
        role_active_postings={},
        role_observed_rows={},
        role_unknown_rows={"product": 1},
        unknown_fact_count=1,
        observed_zero_fact_count=0,
        limitations=("Some count facts are unknown and are not treated as zero.",),
    )
    observed_zero_metrics = replace(
        unknown_metrics,
        market_key="observed_zero_role",
        market_name="Observed Zero Role",
        region_id="region_observed_zero_role",
        role_active_postings={"product": 0},
        role_observed_rows={"product": 1},
        role_unknown_rows={},
        unknown_fact_count=0,
        observed_zero_fact_count=1,
        limitations=(),
    )
    metrics_by_market = {
        unknown_metrics.market_key: unknown_metrics,
        observed_zero_metrics.market_key: observed_zero_metrics,
    }
    ranking = rank_profiles(
        tuple(_robustness_profile(metrics) for metrics in metrics_by_market.values()),
        metrics_by_market,
        goal=CareerGoal.PRODUCT_MANAGEMENT,
        goal_definition=career_goal_definition(CareerGoal.PRODUCT_MANAGEMENT),
    )
    by_market = {item.market_key: item for item in ranking.ranked_markets}
    unknown_item = by_market["unknown_role"]
    zero_item = by_market["observed_zero_role"]

    assert unknown_item.supporting_metrics["component_product_activity"] is None
    assert unknown_item.supporting_metrics["product_active_postings"] is None
    assert unknown_item.supporting_metrics["product_activity_status"] == "unknown"
    assert unknown_item.supporting_metrics["product_activity_unknown_rows"] == 1
    assert any("not treated as observed zero" in item for item in unknown_item.limitations)
    assert zero_item.supporting_metrics["component_product_activity"] == 0.0
    assert zero_item.supporting_metrics["product_active_postings"] == 0
    assert zero_item.supporting_metrics["product_activity_status"] == "observed_zero"
    assert zero_item.supporting_metrics["product_activity_observed_rows"] == 1
    assert unknown_item.raw_score <= zero_item.raw_score
    assert unknown_item.score <= zero_item.score
    assert unknown_item.rank >= zero_item.rank


def test_layer34c_unknown_internship_does_not_improve_score_rank_or_winner() -> None:
    unknown_metrics = replace(
        _robustness_metrics(
            "unknown_internship",
            active_postings=20,
            employers=4,
            tech_density=2.0,
            early_career=3.0,
            internship=0,
            coop=1,
            product=2,
            ai_cloud=1,
            cybersecurity=1,
        ),
        market_name="Unknown Internship",
        internship_total=None,
        internship_observed_rows=0,
        internship_unknown_rows=1,
        unknown_fact_count=1,
        observed_zero_fact_count=0,
        limitations=("Some count facts are unknown and are not treated as zero.",),
    )
    observed_zero_metrics = replace(
        unknown_metrics,
        market_key="observed_zero_internship",
        market_name="Observed Zero Internship",
        region_id="region_observed_zero_internship",
        internship_total=0,
        internship_observed_rows=1,
        internship_unknown_rows=0,
        unknown_fact_count=0,
        observed_zero_fact_count=1,
        limitations=(),
    )
    metrics_by_market = {
        unknown_metrics.market_key: unknown_metrics,
        observed_zero_metrics.market_key: observed_zero_metrics,
    }
    ranking = rank_profiles(
        tuple(_robustness_profile(metrics) for metrics in metrics_by_market.values()),
        metrics_by_market,
        goal=CareerGoal.SOFTWARE_ENGINEERING,
        goal_definition=career_goal_definition(CareerGoal.SOFTWARE_ENGINEERING),
    )
    by_market = {item.market_key: item for item in ranking.ranked_markets}
    unknown_item = by_market["unknown_internship"]
    zero_item = by_market["observed_zero_internship"]

    assert unknown_item.supporting_metrics["component_internship"] is None
    assert unknown_item.supporting_metrics["internship_total"] is None
    assert unknown_item.supporting_metrics["internship_unknown_rows"] == 1
    assert any("not treated as zero" in item for item in unknown_item.limitations)
    assert zero_item.supporting_metrics["component_internship"] == 0.0
    assert zero_item.supporting_metrics["internship_total"] == 0
    assert zero_item.supporting_metrics["internship_unknown_rows"] == 0
    assert unknown_item.raw_score <= zero_item.raw_score
    assert unknown_item.score <= zero_item.score
    assert unknown_item.rank >= zero_item.rank
    assert ranking.top_market_key != unknown_item.market_key
    assert _CONFIDENCE_ORDER_FOR_TEST[unknown_item.confidence] <= (
        _CONFIDENCE_ORDER_FOR_TEST[zero_item.confidence]
    )


def test_layer34c_differentiation_audit_flags_duplicated_profile_language() -> None:
    profiles = (
        _differentiation_profile(
            "alpha",
            overview="A strong market with great opportunities.",
            strength_message="Strong ecosystem.",
            strength_evidence="The market is generally strong.",
            weakness_message="Limited evidence.",
            weakness_evidence="No market-specific evidence is provided.",
        ),
        _differentiation_profile(
            "beta",
            overview="A strong market with great opportunities.",
            strength_message="Strong ecosystem.",
            strength_evidence="The market is generally strong.",
            weakness_message="Limited evidence.",
            weakness_evidence="No market-specific evidence is provided.",
        ),
        _differentiation_profile(
            "gamma",
            overview="Gamma is a startup hub with great opportunities.",
            strength_message="Strong ecosystem.",
            strength_evidence="The market is generally strong.",
            weakness_message="Limited evidence.",
            weakness_evidence="No market-specific evidence is provided.",
        ),
    )

    audit = evaluate_market_differentiation(profiles=profiles, rankings={})
    payload = audit.as_dict()
    codes = {finding.code for finding in audit.duplicated_language_findings}

    assert audit.differentiation_score < 1
    assert DifferentiationFindingCode.REPEATED_OVERVIEW in codes
    assert DifferentiationFindingCode.REPEATED_STRENGTH in codes
    assert DifferentiationFindingCode.REPEATED_WEAKNESS in codes
    assert DifferentiationFindingCode.GENERIC_DESCRIPTION in codes
    assert DifferentiationFindingCode.UNSUPPORTED_STEREOTYPE in codes
    assert DifferentiationFindingCode.MISSING_MARKET_SPECIFIC_EVIDENCE in codes
    assert any(
        finding.severity is DifferentiationSeverity.NEEDS_IMPROVEMENT
        for finding in audit.duplicated_language_findings
    )
    assert any(
        "do not invent" in recommendation
        for recommendation in audit.required_improvement_recommendations
    )
    json.dumps(payload, sort_keys=True)
    _assert_public_payload_safe(payload)


def test_layer34c_differentiation_audit_preserves_legitimate_similarity() -> None:
    metrics = {
        "employer_count": 5,
        "active_posting_total": 10,
        "internship_total": 4,
        "formal_program_count": 2,
        "unknown_fact_count": 0,
        "observed_zero_fact_count": 0,
        "ranking_eligible_fact_count": 8,
    }
    profiles = (
        _differentiation_profile(
            "alpha",
            overview="This market has 5 curated employers and 10 observed postings.",
            strength_message="Observed hiring evidence is available.",
            strength_evidence="10 observed postings and 4 internship counts are canonical.",
            weakness_message="No critical coverage weakness is detected.",
            weakness_evidence="8 ranking-eligible facts are available.",
            metrics=metrics,
        ),
        _differentiation_profile(
            "beta",
            overview="This market has 5 curated employers and 10 observed postings.",
            strength_message="Observed hiring evidence is available.",
            strength_evidence="10 observed postings and 4 internship counts are canonical.",
            weakness_message="No critical coverage weakness is detected.",
            weakness_evidence="8 ranking-eligible facts are available.",
            metrics=metrics,
        ),
    )

    audit = evaluate_market_differentiation(profiles=profiles, rankings={})

    assert audit.differentiation_score == 1
    assert audit.duplicated_language_findings == ()
    assert audit.true_similarity_notes


def test_layer34c_differentiation_audit_flags_repeated_drivers() -> None:
    rankings = {
        CareerGoal.SOFTWARE_ENGINEERING: _differentiation_ranking(
            CareerGoal.SOFTWARE_ENGINEERING,
            ("alpha", "beta", "gamma"),
            driver_codes=("hiring_activity", "tech_signal", "early_career"),
            repeated_driver_evidence=True,
        )
    }

    audit = evaluate_market_differentiation(profiles=(), rankings=rankings)
    finding = audit.repeated_driver_findings[0]

    assert finding.code is DifferentiationFindingCode.REPEATED_DRIVER
    assert finding.severity is DifferentiationSeverity.NEEDS_IMPROVEMENT
    assert finding.goal_keys == (CareerGoal.SOFTWARE_ENGINEERING,)
    assert finding.market_keys == ("alpha", "beta", "gamma")
    assert "hiring_activity" in finding.evidence
    assert audit.required_improvement_recommendations


def test_layer34c_differentiation_audit_summarizes_cross_goal_similarity() -> None:
    rankings = {
        CareerGoal.SOFTWARE_ENGINEERING: _differentiation_ranking(
            CareerGoal.SOFTWARE_ENGINEERING,
            ("alpha", "beta", "gamma"),
        ),
        CareerGoal.PRODUCT_MANAGEMENT: _differentiation_ranking(
            CareerGoal.PRODUCT_MANAGEMENT,
            ("alpha", "beta", "gamma"),
        ),
        CareerGoal.CYBERSECURITY: _differentiation_ranking(
            CareerGoal.CYBERSECURITY,
            ("alpha", "gamma", "beta"),
        ),
    }

    audit = evaluate_market_differentiation(profiles=(), rankings=rankings)
    by_pair = {
        (item.goal_a, item.goal_b): item
        for item in audit.cross_goal_rank_correlation_summary
    }
    identical = by_pair[(CareerGoal.PRODUCT_MANAGEMENT, CareerGoal.SOFTWARE_ENGINEERING)]

    assert identical.identical_order
    assert identical.nearly_identical
    assert identical.spearman_correlation == 1.0
    assert identical.shared_top_market_key == "alpha"
    assert identical.rank_deltas == {"alpha": 0, "beta": 0, "gamma": 0}
    assert any(
        "cross-goal ordering is nearly identical" in recommendation
        for recommendation in audit.required_improvement_recommendations
    )


def test_layer34c_differentiation_service_is_deterministic_public_safe_and_read_only(
    session: Session,
) -> None:
    _seed_all_markets(session)
    before = _table_counts(session)
    service = MarketIntelligenceService(session)

    first = service.differentiation_audit(as_of=AS_OF).as_dict()
    second = service.differentiation_audit(as_of=AS_OF).as_dict()

    assert first == second
    assert first["profile_count"] == 8
    assert first["goal_count"] == len(CareerGoal.values())
    assert isinstance(first["differentiation_score"], float)
    assert {
        "duplicated_language_findings",
        "repeated_driver_findings",
        "cross_goal_rank_correlation_summary",
        "required_improvement_recommendations",
        "true_similarity_notes",
    }.issubset(first)
    assert first["cross_goal_rank_correlation_summary"]
    assert any(
        "data_science" in note and "not counted as substantive market superiority" in note
        for note in first["true_similarity_notes"]
    )
    json.dumps(first, sort_keys=True)
    _assert_public_payload_safe(first)
    assert _table_counts(session) == before
    assert session.query(UserReport).count() == 0
    assert session.query(AutomatedRecheckJob).count() == 0
    assert session.query(ExceptionCase).count() == 0


def test_layer34c_ranking_explanation_is_comparative_specific_and_ordered() -> None:
    profiles, metrics_by_market, _rankings = _synthetic_robustness_inputs()

    ranking = rank_profiles(
        profiles,
        metrics_by_market,
        goal=CareerGoal.PRODUCT_MANAGEMENT,
        goal_definition=career_goal_definition(CareerGoal.PRODUCT_MANAGEMENT),
    )

    explanation = ranking.explanation
    top = ranking.ranked_markets[0]
    section_labels = (
        "Ranking position:",
        "Direct evidence:",
        "Proxy evidence:",
        "Strongest comparative advantage:",
        "Strongest comparative weakness:",
        "Missing evidence:",
        "Confidence limitation:",
        "Stability limitation:",
    )

    assert [explanation.index(label) for label in section_labels] == sorted(
        explanation.index(label) for label in section_labels
    )
    assert top.market_name in explanation
    assert top.ranking_drivers[0].label in explanation
    assert f"{top.ranking_drivers[0].contribution:.4f}" in explanation
    assert "score margin to nearest ranked peer" in explanation
    assert "Product role-family hiring evidence" in explanation
    assert "Early-career accessibility proxy" in explanation
    assert "unknown count fact" in explanation
    assert "observed zero count fact" in explanation
    assert "not treated as zero" in explanation
    assert "limited_evidence" in explanation
    assert not explanation_language_rejections(explanation)
    _assert_public_payload_safe({"explanation": explanation})


def test_layer34c_pairwise_explanation_aligns_with_driver_and_score_delta() -> None:
    left = _calibration_item("alpha", rank=1, score=0.7)
    right = _calibration_item("beta", rank=2, score=0.3)

    comparison = compare_ranked_markets(
        "alpha",
        "beta",
        goal=CareerGoal.SOFTWARE_ENGINEERING,
        ranking_items=(left, right),
    )

    explanation = comparison.explanation
    assert "Ranking position:" in explanation
    assert "Score margin: score delta is 0.4000" in explanation
    assert left.ranking_drivers[0].label in explanation
    assert "Direct evidence:" in explanation
    assert "Proxy evidence:" in explanation
    assert "Strongest comparative advantage:" in explanation
    assert "Strongest comparative weakness:" in explanation
    assert "Missing evidence:" in explanation
    assert "Confidence limitation:" in explanation
    assert "Stability limitation:" in explanation
    assert "comparison confidence is high" in explanation
    assert not explanation_language_rejections(explanation)
    _assert_public_payload_safe({"explanation": explanation})


def test_layer34c_explanation_aligns_with_confidence_limitations_and_abstention() -> None:
    profiles, metrics_by_market, _rankings = _synthetic_robustness_inputs()

    ranking = rank_profiles(
        profiles,
        metrics_by_market,
        goal=CareerGoal.DATA_SCIENCE,
        goal_definition=career_goal_definition(CareerGoal.DATA_SCIENCE),
    )

    explanation = ranking.explanation
    top = ranking.ranked_markets[0]
    assert ranking.evidence_sufficiency is EvidenceSufficiency.NOT_SUPPORTED
    assert ranking.top_market_key is None
    assert "abstains from naming a top Data science market" in explanation
    assert "Direct evidence: no positive direct Data science driver" in explanation
    assert "Data-science role-family hiring evidence" in explanation
    assert "Confidence limitation: confidence is limited with not_supported" in explanation
    assert top.abstention_reason in explanation
    assert top.limitations[0] in explanation
    assert "Stability limitation:" in explanation
    assert not explanation_language_rejections(explanation)


def test_layer34c_explanation_language_rejects_generic_city_stereotypes() -> None:
    generic = (
        "This city is a strong market and startup hub with great opportunities."
    )
    grounded = (
        "This market has 5 curated employer count facts, 10 observed postings, "
        "and 1 observed zero count fact."
    )

    assert explanation_language_rejections(generic) == (
        "generic_market_language",
        "unsupported_city_stereotype",
    )
    assert explanation_language_rejections(grounded) == ()


def test_layer34c_explanation_construction_stays_out_of_routes() -> None:
    route_source = (REPO_ROOT / "backend" / "api" / "market_intelligence.py").read_text(
        encoding="utf-8"
    )

    assert "build_ranking_report_explanation" not in route_source
    assert "build_pairwise_comparison_explanation" not in route_source
    assert "Ranking position:" not in route_source
    assert "Strongest comparative advantage:" not in route_source


def test_layer34c_contradiction_detects_high_confidence_with_insufficient_evidence() -> None:
    item = _contradiction_item(
        evidence_sufficiency=EvidenceSufficiency.INSUFFICIENT_EVIDENCE,
        confidence=IntelligenceConfidence.HIGH,
    )

    analysis = evaluate_ranking_item_contradictions(item)

    assert analysis.status is ContradictionStatus.BLOCKING
    assert ContradictionCode.HIGH_CONFIDENCE_INSUFFICIENT_EVIDENCE in _contradiction_codes(
        analysis.findings
    )
    assert analysis.findings[0].blocks_recommendation


def test_layer34c_contradiction_detects_strong_internship_with_missing_evidence() -> None:
    item = _contradiction_item(
        strengths=("Strong internship ecosystem for early talent.",),
        supporting_metrics={
            "ranking_eligible_fact_count": 3,
            "internship_total": None,
            "internship_unknown_rows": 1,
        },
    )

    analysis = evaluate_ranking_item_contradictions(item)

    assert analysis.status is ContradictionStatus.BLOCKING
    assert ContradictionCode.STRONG_INTERNSHIP_MISSING_EVIDENCE in _contradiction_codes(
        analysis.findings
    )


def test_layer34c_contradiction_detects_current_freshness_with_stale_source() -> None:
    item = _contradiction_item(
        freshness=IntelligenceFreshness.CURRENT,
        supporting_metrics={
            "ranking_eligible_fact_count": 3,
            "stale_source_count": 1,
        },
    )

    analysis = evaluate_ranking_item_contradictions(item)

    assert analysis.status is ContradictionStatus.BLOCKING
    assert ContradictionCode.CURRENT_FRESHNESS_STALE_PRIMARY_SOURCE in _contradiction_codes(
        analysis.findings
    )


def test_layer34c_contradiction_detects_declared_winner_with_lower_score() -> None:
    comparison = _contradiction_comparison(
        market_a_score=0.21,
        market_b_score=0.72,
        winner_market_key="alpha",
        outcome=ComparisonOutcome.MARKET_A,
    )

    updated = apply_comparison_contradictions(comparison)

    assert updated.contradiction_status is ContradictionStatus.BLOCKING
    assert ContradictionCode.WINNER_WITH_LOWER_SCORE in _contradiction_codes(
        updated.contradictions
    )
    assert updated.outcome is ComparisonOutcome.NO_WINNER
    assert updated.winner_market_key is None
    assert updated.abstention_reason


def test_layer34c_contradiction_detects_opposite_weakness_and_driver() -> None:
    item = _contradiction_item(
        ranking_drivers=(
            RankingDriver(
                code="internship",
                label="internship ecosystem",
                contribution=0.3,
                evidence="internship ecosystem is supported by canonical metric value 5.",
            ),
        ),
        weaknesses=("Limited internship evidence is a weakness.",),
        supporting_metrics={
            "ranking_eligible_fact_count": 3,
            "internship_total": 5,
        },
    )

    analysis = evaluate_ranking_item_contradictions(item)

    assert analysis.status is ContradictionStatus.BLOCKING
    assert ContradictionCode.OPPOSITE_WEAKNESS_AND_DRIVER in _contradiction_codes(
        analysis.findings
    )


def test_layer34c_contradiction_blocks_role_recommendation_without_direct_evidence() -> None:
    item = _contradiction_item(
        goal=CareerGoal.PRODUCT_MANAGEMENT,
        ranking_drivers=(
            RankingDriver(
                code="early_career",
                label="early-career accessibility proxy",
                contribution=0.3,
                evidence="early-career evidence is supported by canonical metric value 4.",
            ),
            RankingDriver(
                code="employer_presence",
                label="broad employer ecosystem proxy",
                contribution=0.2,
                evidence="employer evidence is supported by canonical metric value 6.",
            ),
        ),
        evidence_sufficiency=EvidenceSufficiency.COMPARISON_READY,
        evidence_basis=EvidenceBasis.PROXY,
        supporting_metrics={
            "ranking_eligible_fact_count": 3,
            "direct_evidence_count": 0,
            "proxy_evidence_count": 2,
            "total_evidence_count": 2,
        },
    )
    ranking = _contradiction_ranking(
        item,
        explanation="Alpha is the top Product management recommendation.",
    )

    updated = apply_ranking_contradictions(ranking)

    assert updated.contradiction_status is ContradictionStatus.BLOCKING
    assert ContradictionCode.SPECIFIC_ROLE_RECOMMENDATION_WITHOUT_DIRECT_EVIDENCE in (
        _contradiction_codes(updated.contradictions)
    )
    assert updated.top_market_key is None
    assert updated.abstention_reason


def test_layer34c_career_goal_summary_abstains_for_blocking_contradiction(
    monkeypatch,
) -> None:
    finding = ContradictionFinding(
        code=ContradictionCode.SPECIFIC_ROLE_RECOMMENDATION_WITHOUT_DIRECT_EVIDENCE,
        severity=ContradictionSeverity.BLOCKING,
        message="A role-specific recommendation is not backed by direct role evidence.",
        evidence="Product management recommendation lacks direct product evidence.",
        blocks_recommendation=True,
    )
    top = replace(
        _contradiction_item(
            "alpha",
            goal=CareerGoal.PRODUCT_MANAGEMENT,
            ranking_drivers=(
                RankingDriver(
                    code="product_activity",
                    label="product role activity",
                    contribution=0.4,
                    evidence="product role activity is supported by canonical metric value 8.",
                ),
            ),
        ),
        contradiction_status=ContradictionStatus.BLOCKING,
        contradictions=(finding,),
    )
    ranking = ExplainableRankingReport(
        goal=CareerGoal.PRODUCT_MANAGEMENT,
        goal_definition=career_goal_definition(CareerGoal.PRODUCT_MANAGEMENT),
        ranked_markets=(top,),
        top_market_key=None,
        explanation="Contradiction detection: normal recommendation is blocked.",
        limitations=("Contradiction detection blocked a normal recommendation.",),
        tie_breaker="Sort by confidence-adjusted score descending, then market key.",
        evidence_sufficiency=EvidenceSufficiency.COMPARISON_READY,
        abstention_reason=(
            "normal recommendation is blocked by contradiction code(s) "
            "specific_role_recommendation_without_direct_evidence."
        ),
        contradiction_status=ContradictionStatus.BLOCKING,
        contradictions=(finding,),
    )
    service = MarketIntelligenceService.__new__(MarketIntelligenceService)
    monkeypatch.setattr(service, "ranking", lambda **_: ranking)

    report = service.career_goal_comparison(goal=CareerGoal.PRODUCT_MANAGEMENT)
    summary = report.recommendation_summary.casefold()

    assert report.recommended_market_key is None
    assert "strongest" not in summary
    assert "top" not in summary
    assert "contradiction" in summary
    assert "specific_role_recommendation_without_direct_evidence" in summary


def test_layer34c_contradiction_detects_comparison_ready_without_qualifying_evidence() -> None:
    item = _contradiction_item(
        ranking_drivers=(),
        evidence_sufficiency=EvidenceSufficiency.COMPARISON_READY,
        evidence_basis=EvidenceBasis.NO_QUALIFYING_EVIDENCE,
        supporting_metrics={
            "ranking_eligible_fact_count": 0,
            "total_evidence_count": 0,
        },
    )

    analysis = evaluate_ranking_item_contradictions(item)

    assert analysis.status is ContradictionStatus.BLOCKING
    assert ContradictionCode.COMPARISON_READY_WITHOUT_QUALIFYING_EVIDENCE in (
        _contradiction_codes(analysis.findings)
    )


def test_layer34c_contradiction_detects_no_limitations_despite_critical_gaps() -> None:
    item = _contradiction_item(
        limitations=(),
        supporting_metrics={
            "ranking_eligible_fact_count": 3,
            "high_gap_count": 1,
        },
    )

    analysis = evaluate_ranking_item_contradictions(item)

    assert analysis.status is ContradictionStatus.BLOCKING
    assert ContradictionCode.NO_LIMITATIONS_DESPITE_CRITICAL_GAPS in _contradiction_codes(
        analysis.findings
    )


def test_layer34c_contradiction_detects_alphabetical_tie_displayed_as_winner() -> None:
    alpha = _contradiction_item("alpha", rank=1, score=0.5)
    beta = _contradiction_item("beta", rank=2, score=0.5)
    ranking = _contradiction_ranking(
        alpha,
        ranked_markets=(alpha, beta),
        tie_breaker="Sort by confidence-adjusted score descending, then market key.",
    )

    updated = apply_ranking_contradictions(ranking)

    assert updated.contradiction_status is ContradictionStatus.BLOCKING
    assert ContradictionCode.ALPHABETICAL_TIE_DISPLAYED_AS_WINNER in (
        _contradiction_codes(updated.contradictions)
    )
    assert updated.top_market_key is None


def test_layer34c_api_serializes_public_safe_contradiction_fields(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_all_markets(session)

    ranking = api_client.get(
        "/market-comparisons",
        params={"goal": "software_engineering", "as_of": AS_OF.isoformat()},
    ).json()["data"]
    comparison = api_client.get(
        "/market-comparisons/atlanta/boston",
        params={"goal": "software_engineering", "as_of": AS_OF.isoformat()},
    ).json()["data"]

    assert ranking["contradiction_status"] in ContradictionStatus.values()
    assert isinstance(ranking["contradictions"], list)
    assert {
        "contradiction_status",
        "contradictions",
    }.issubset(ranking["ranked_markets"][0])
    assert comparison["contradiction_status"] in ContradictionStatus.values()
    assert isinstance(comparison["contradictions"], list)
    _assert_public_payload_safe({"ranking": ranking, "comparison": comparison})


def test_layer34c_profile_grounding_is_public_safe_and_coverage_aware(
    session: Session,
) -> None:
    _seed_all_markets(session)

    payload = MarketIntelligenceService(session).profile("nyc", as_of=AS_OF).as_dict()
    grounding = payload["grounding"]

    _assert_grounding_shape(grounding)
    assert grounding["score_margin"] is None
    assert grounding["stability_status"] == RankingStabilityStatus.INDETERMINATE.value
    assert grounding["freshness"] in IntelligenceFreshness.values()
    assert grounding["coverage"]
    assert grounding["evidence_areas_used"]
    assert "excluded" in grounding["excluded_fact_summary"]
    assert any("unknown count fact" in item for item in grounding["proxy_evidence_summary"])
    assert any("observed zero count fact" in item for item in grounding["proxy_evidence_summary"])
    _assert_public_payload_safe(payload)


def test_layer34c_ranking_grounding_includes_evidence_areas_and_score_margin(
    session: Session,
) -> None:
    _seed_all_markets(session)

    payload = MarketIntelligenceService(session).ranking(
        goal=CareerGoal.DATA_SCIENCE,
        as_of=AS_OF,
    ).as_dict()
    first = payload["ranked_markets"][0]
    grounding = first["grounding"]

    _assert_grounding_shape(payload["grounding"])
    _assert_grounding_shape(grounding)
    assert payload["grounding"] == grounding
    assert grounding["score_margin"] >= 0
    assert grounding["stability_status"] in RankingStabilityStatus.values()
    if grounding["stability_status"] != RankingStabilityStatus.INDETERMINATE.value:
        assert grounding["stability_scenarios"]
    assert grounding["freshness"] == first["freshness"]
    assert "Data-science role-family hiring evidence" in grounding[
        "evidence_areas_missing"
    ]
    assert any("No direct Data science evidence" in item for item in grounding[
        "direct_evidence_summary"
    ])
    assert any("Evidence basis is proxy" in item for item in grounding[
        "proxy_evidence_summary"
    ])
    assert any("not supported" in item for item in grounding["confidence_constraints"])
    _assert_public_payload_safe(payload)


def test_layer34c_comparison_grounding_covers_sides_and_pairwise_margin(
    session: Session,
) -> None:
    _seed_all_markets(session)

    payload = MarketIntelligenceService(session).comparison(
        "atlanta",
        "boston",
        goal=CareerGoal.SOFTWARE_ENGINEERING,
        as_of=AS_OF,
    ).as_dict()
    grounding = payload["grounding"]

    _assert_grounding_shape(grounding)
    _assert_grounding_shape(payload["market_a"]["grounding"])
    _assert_grounding_shape(payload["market_b"]["grounding"])
    assert grounding["score_margin"] == payload["supporting_metrics"]["score_delta"]
    assert payload["market_a"]["grounding"]["score_margin"] >= 0
    assert payload["market_b"]["grounding"]["score_margin"] >= 0
    assert "Atlanta" in " ".join(grounding["direct_evidence_summary"])
    assert "Boston" in " ".join(grounding["direct_evidence_summary"])
    assert "Comparison confidence" in " ".join(grounding["confidence_constraints"])
    _assert_public_payload_safe(payload)


def test_layer34c_public_ranking_and_comparison_grounding_include_evaluated_stability(
    session: Session,
) -> None:
    _seed_all_markets(session)
    service = MarketIntelligenceService(session)

    ranking = service.ranking(goal=CareerGoal.SOFTWARE_ENGINEERING, as_of=AS_OF)
    evaluated_items = [
        item
        for item in ranking.ranked_markets
        if item.grounding
        and item.grounding.stability_status
        in {RankingStabilityStatus.UNSTABLE, RankingStabilityStatus.SENSITIVE}
    ]

    assert evaluated_items
    evaluated = evaluated_items[0]
    assert evaluated.grounding is not None
    assert evaluated.grounding.stability_scenarios
    assert any(
        scenario.status
        in {RankingStabilityStatus.UNSTABLE, RankingStabilityStatus.SENSITIVE}
        for scenario in evaluated.grounding.stability_scenarios
    )
    assert any("Sensitivity analysis" in item for item in evaluated.limitations)
    assert evaluated.grounding.stability_status is not RankingStabilityStatus.INDETERMINATE

    peer = next(
        item
        for item in ranking.ranked_markets
        if item.market_key != evaluated.market_key
    )
    comparison = service.comparison(
        evaluated.market_key,
        peer.market_key,
        goal=CareerGoal.SOFTWARE_ENGINEERING,
        as_of=AS_OF,
    )
    assert comparison.grounding is not None
    assert comparison.grounding.stability_status in {
        RankingStabilityStatus.UNSTABLE,
        RankingStabilityStatus.SENSITIVE,
    }
    assert comparison.grounding.stability_scenarios
    assert comparison.market_a.grounding is not None
    assert comparison.market_a.grounding.stability_scenarios
    _assert_public_payload_safe(
        {
            "ranking": ranking.as_dict(),
            "comparison": comparison.as_dict(),
        }
    )


def test_layer34c_calibration_grounding_carries_stability_status(
    session: Session,
) -> None:
    _seed_all_markets(session)

    payload = MarketIntelligenceService(session).calibration_report(as_of=AS_OF).as_dict()
    item = payload["market_goal_matrix"][CareerGoal.SOFTWARE_ENGINEERING.value]["nyc"]
    grounding = item["grounding"]

    _assert_grounding_shape(grounding)
    assert grounding["score_margin"] == item["score_margin"]
    assert grounding["stability_status"] == item["stability_status"]
    assert grounding["direct_evidence_summary"] == item["direct_evidence_summary"]
    assert grounding["proxy_evidence_summary"] == item["proxy_evidence_summary"]
    _assert_public_payload_safe(payload)


def test_layer34c_product_quality_evaluation_report_schema_count_and_summaries(
    session: Session,
) -> None:
    _seed_all_markets(session)

    payload = MarketIntelligenceService(session).product_quality_evaluation_report(
        as_of=AS_OF
    ).as_dict()
    ready_markets = {
        key for key, entry in load_market_registry().items() if entry.import_status == "ready"
    }

    assert payload["schema_version"] == "34C.11"
    assert payload["report_type"] == "layer_34c_product_quality_evaluation"
    assert payload["artifact_path"] == PRODUCT_QUALITY_EVALUATION_REPORT_ARTIFACT_PATH
    assert payload["differentiation_threshold"] == PRODUCT_QUALITY_DIFFERENTIATION_THRESHOLD
    assert payload["differentiation_score"] >= PRODUCT_QUALITY_DIFFERENTIATION_THRESHOLD
    assert payload["differentiation_passed"] is True
    assert payload["differentiation_notes"]
    assert set(payload["markets"]) == ready_markets
    assert set(payload["goals"]) == CareerGoal.values()
    assert payload["expected_result_count"] == len(ready_markets) * len(CareerGoal)
    assert payload["result_count"] == 40
    assert len(payload["results"]) == payload["expected_result_count"]
    assert [(result["goal"], result["market_key"]) for result in payload["results"]] == [
        (goal.value, market_key)
        for goal in sorted(CareerGoal, key=lambda item: item.value)
        for market_key in sorted(ready_markets)
    ]
    assert {
        (result["goal"], result["market_key"]) for result in payload["results"]
    } == {
        (goal, market_key)
        for goal in CareerGoal.values()
        for market_key in ready_markets
    }

    first = payload["results"][0]
    assert {
        "rank",
        "score",
        "score_margin",
        "confidence",
        "freshness",
        "sufficiency",
        "direct_proxy_evidence",
        "top_drivers",
        "limitations",
        "stability",
        "contradictions",
        "abstention",
        "explanation_quality_status",
        "differentiation_findings",
    }.issubset(first)
    assert first["direct_proxy_evidence"]["evidence_basis"] in EvidenceBasis.values()
    assert first["direct_proxy_evidence"]["direct_evidence_summary"]
    assert first["direct_proxy_evidence"]["proxy_evidence_summary"]
    assert first["stability"]["status"] in RankingStabilityStatus.values()
    assert isinstance(first["stability"]["scenario_count"], int)
    assert isinstance(first["abstention"]["abstains"], bool)
    assert first["explanation_quality_status"]["status"] in (
        ExplanationQualityStatus.values()
    )
    assert first["explanation_quality_status"]["checks"]
    assert not any(
        finding["severity"] == DifferentiationSeverity.NEEDS_IMPROVEMENT.value
        for result in payload["results"]
        for finding in result["differentiation_findings"]
    )
    data_science_results = [
        result
        for result in payload["results"]
        if result["goal"] == CareerGoal.DATA_SCIENCE.value
    ]
    assert data_science_results
    assert all(result["abstention"]["abstains"] for result in data_science_results)
    assert all(
        result["differentiation_findings"] == [] for result in data_science_results
    )
    product_management_results = [
        result
        for result in payload["results"]
        if result["goal"] == CareerGoal.PRODUCT_MANAGEMENT.value
    ]
    assert product_management_results
    for result in product_management_results:
        direct_evidence_text = " ".join(
            result["direct_proxy_evidence"]["direct_evidence_summary"]
        ).casefold()
        assert "formal early-career" not in direct_evidence_text
        assert "formal_program" not in direct_evidence_text
        if result["direct_proxy_evidence"]["direct_evidence_count"] == 0:
            assert result["direct_proxy_evidence"]["evidence_basis"] in {
                EvidenceBasis.PROXY.value,
                EvidenceBasis.NO_QUALIFYING_EVIDENCE.value,
            }

    platform = payload["platform_summary"]
    assert {
        "cross_goal_ranking_similarity",
        "score_clustering",
        "dominant_metrics",
        "unsupported_goals",
        "provisional_results",
        "abstentions",
        "unstable_results",
        "contradictions",
    }.issubset(platform)
    assert len(platform["score_clustering"]) == len(CareerGoal)
    assert platform["cross_goal_ranking_similarity"]
    assert not any(
        {
            item["goal_a"],
            item["goal_b"],
        }
        == {CareerGoal.DATA_SCIENCE.value, CareerGoal.SOFTWARE_ENGINEERING.value}
        for item in platform["cross_goal_ranking_similarity"]
    )
    assert platform["dominant_metrics"]
    assert any(
        item["goal"] == CareerGoal.DATA_SCIENCE.value
        for item in platform["unsupported_goals"]
    )
    assert any(
        item["goal"] == CareerGoal.DATA_SCIENCE.value
        for item in platform["abstentions"]
    )
    unstable_or_sensitive = [
        result
        for result in payload["results"]
        if result["stability"]["status"]
        in {
            RankingStabilityStatus.UNSTABLE.value,
            RankingStabilityStatus.SENSITIVE.value,
        }
    ]
    assert unstable_or_sensitive
    assert all(
        any(
            check["code"] == "stability_alignment" and check["passed"]
            for check in result["explanation_quality_status"]["checks"]
        )
        for result in unstable_or_sensitive
    )
    evidence_text = " ".join(
        " ".join(result["direct_proxy_evidence"]["proxy_evidence_summary"])
        for result in payload["results"]
    )
    assert "unknown count fact" in evidence_text
    assert "observed zero count fact" in evidence_text


def test_layer34c_explanation_quality_fails_when_evaluated_stability_is_omitted() -> None:
    check = _stability_alignment_check(
        RankingStabilityStatus.UNSTABLE,
        "Stability limitation: scenario stability is reported by calibration.",
    )

    assert check.code == "stability_alignment"
    assert check.passed is False


def test_layer34c_product_quality_evaluation_report_is_deterministic_public_safe_and_read_only(
    session: Session,
) -> None:
    _seed_all_markets(session)
    before = _table_counts(session)
    service = MarketIntelligenceService(session)

    first = service.product_quality_evaluation_report(as_of=AS_OF).as_dict()
    second = service.product_quality_evaluation_report(as_of=AS_OF).as_dict()

    assert first == second
    json.dumps(first, sort_keys=True)
    _assert_public_payload_safe(first)
    assert _table_counts(session) == before
    assert session.query(UserReport).count() == 0
    assert session.query(AutomatedRecheckJob).count() == 0
    assert session.query(ExceptionCase).count() == 0


def test_layer34c_product_quality_evaluation_report_redacts_internal_tokens() -> None:
    unsafe_driver = RankingDriver(
        code="hiring_activity",
        label="observed hiring activity",
        contribution=0.4,
        evidence="Traceback /Users/private/path source_ref_id leaked.",
    )
    unsafe_item = replace(
        _calibration_item("alpha", rank=1, score=0.7),
        ranking_drivers=(unsafe_driver,),
        limitations=("trust_assessment_id leaked in limitation.",),
    )
    ranking = ExplainableRankingReport(
        goal=CareerGoal.SOFTWARE_ENGINEERING,
        goal_definition=career_goal_definition(CareerGoal.SOFTWARE_ENGINEERING),
        ranked_markets=(unsafe_item,),
        top_market_key="alpha",
        explanation="Alpha is the top Software engineering recommendation.",
        limitations=("trust_assessment_id leaked in report limitation.",),
        tie_breaker="Sort by confidence-adjusted score descending, then market key.",
    )
    calibration = build_calibration_report(
        rankings={CareerGoal.SOFTWARE_ENGINEERING: ranking},
        as_of=AS_OF,
    )
    differentiation = evaluate_market_differentiation(
        profiles=(),
        rankings={CareerGoal.SOFTWARE_ENGINEERING: ranking},
    )

    payload = build_product_quality_evaluation_report(
        calibration_report=calibration,
        differentiation_audit=differentiation,
        rankings={CareerGoal.SOFTWARE_ENGINEERING: ranking},
    ).as_dict()
    serialized = json.dumps(payload, sort_keys=True)

    assert "[redacted]" in serialized
    assert "source_ref_id" not in serialized
    assert "trust_assessment_id" not in serialized
    assert "Traceback" not in serialized
    assert "/Users/private/path" not in serialized
    _assert_public_payload_safe(payload)


def test_layer34c_nested_grounding_redaction_removes_internal_tokens() -> None:
    item = replace(
        _calibration_item("alpha", rank=1, score=0.7),
        supporting_metrics={
            "safe_metric": 1,
            "raw_internal_risk": "do not serialize",
            "nested": {
                "safe_nested_metric": 2,
                "trust_assessment_id": "trust_assessment_id_private",
                "message": "Traceback /Users/private/path",
            },
        },
        grounding=EvidenceGrounding(
            evidence_areas_used=("Observed hiring activity",),
            evidence_areas_missing=("trust_assessment_id leaked",),
            direct_evidence_summary=("Safe direct summary.",),
            proxy_evidence_summary=("private_provenance leaked",),
            freshness=IntelligenceFreshness.CURRENT,
            coverage="Safe coverage summary.",
            excluded_fact_summary="No ranking-excluded facts are used in the score.",
            confidence_constraints=("Traceback /Users/private/path",),
            score_margin=0.0,
            stability_status=RankingStabilityStatus.INDETERMINATE,
        ),
    )

    payload = item.as_dict()

    assert payload["supporting_metrics"]["safe_metric"] == 1
    assert payload["supporting_metrics"]["nested"]["safe_nested_metric"] == 2
    assert "raw_internal_risk" not in payload["supporting_metrics"]
    assert "trust_assessment_id" not in payload["supporting_metrics"]["nested"]
    assert payload["supporting_metrics"]["nested"]["message"] == "[redacted]"
    assert "[redacted]" in json.dumps(payload, sort_keys=True)
    _assert_public_payload_safe(payload)


def _seed_all_markets(session: Session) -> None:
    assert import_all_curated_market_datasets(session, as_of=AS_OF).ok
    assert run_all_curated_market_post_imports(session, as_of=AS_OF).ok


def _differentiation_profile(
    market_key: str,
    *,
    overview: str,
    strength_message: str,
    strength_evidence: str,
    weakness_message: str,
    weakness_evidence: str,
    metrics: dict[str, int | float | str | None] | None = None,
) -> MarketIntelligenceProfile:
    supporting_metrics = metrics or {
        "employer_count": 0,
        "active_posting_total": None,
        "internship_total": None,
        "formal_program_count": 0,
        "unknown_fact_count": 0,
        "observed_zero_fact_count": 0,
        "ranking_eligible_fact_count": 0,
    }
    opportunity = OpportunityEnvironment(
        hiring_activity="Synthetic hiring language.",
        employer_diversity="Synthetic employer language.",
        internship_ecosystem="Synthetic internship language.",
        coop_ecosystem="Synthetic co-op language.",
        early_career_support="Synthetic early-career language.",
        hiring_momentum="No unsupported trend is inferred.",
        overall=overview,
    )
    return MarketIntelligenceProfile(
        market_key=market_key,
        market_name=market_key.title(),
        region_id=f"region_{market_key}",
        overview=overview,
        strengths=(
            MarketInsight(
                code="synthetic_strength",
                message=strength_message,
                evidence=strength_evidence,
                impact="Synthetic differentiation test impact.",
            ),
        ),
        weaknesses=(
            MarketInsight(
                code="synthetic_weakness",
                message=weakness_message,
                evidence=weakness_evidence,
                impact="Synthetic differentiation test limitation.",
            ),
        ),
        hiring_summary="Synthetic hiring language.",
        employer_summary="Synthetic employer language.",
        internship_summary="Synthetic internship language.",
        coop_summary="Synthetic co-op language.",
        early_career_summary="Synthetic early-career language.",
        opportunity_environment=opportunity,
        confidence=IntelligenceConfidence.MODERATE,
        confidence_score=0.7,
        freshness=IntelligenceFreshness.CURRENT,
        coverage_summary="Synthetic coverage language.",
        limitations=(),
        supporting_metrics=supporting_metrics,
    )


def _differentiation_ranking(
    goal: CareerGoal,
    market_order: tuple[str, ...],
    *,
    driver_codes: tuple[str, ...] = ("hiring_activity", "tech_signal"),
    repeated_driver_evidence: bool = False,
) -> ExplainableRankingReport:
    items = tuple(
        _differentiation_ranking_item(
            market_key,
            goal=goal,
            rank=rank,
            score=round(1.0 - (rank * 0.1), 4),
            driver_codes=driver_codes,
            repeated_driver_evidence=repeated_driver_evidence,
        )
        for rank, market_key in enumerate(market_order, start=1)
    )
    return ExplainableRankingReport(
        goal=goal,
        goal_definition=career_goal_definition(goal),
        ranked_markets=items,
        top_market_key=items[0].market_key if items else None,
        explanation="Synthetic differentiation ranking.",
        limitations=(),
        tie_breaker="Synthetic rank order.",
        evidence_sufficiency=EvidenceSufficiency.COMPARISON_READY,
    )


def _differentiation_ranking_item(
    market_key: str,
    *,
    goal: CareerGoal,
    rank: int,
    score: float,
    driver_codes: tuple[str, ...],
    repeated_driver_evidence: bool,
) -> ExplainableRankingItem:
    drivers = tuple(
        RankingDriver(
            code=code,
            label=code.replace("_", " "),
            contribution=round(0.4 - (index * 0.05), 4),
            evidence=(
                f"{code} uses the same synthetic canonical metric value 10."
                if repeated_driver_evidence
                else f"{code} uses synthetic canonical metric value {10 + rank + index}."
            ),
        )
        for index, code in enumerate(driver_codes)
    )
    return ExplainableRankingItem(
        rank=rank,
        market_key=market_key,
        market_name=market_key.title(),
        goal=goal,
        score=score,
        raw_score=score,
        confidence=IntelligenceConfidence.HIGH,
        freshness=IntelligenceFreshness.CURRENT,
        ranking_drivers=drivers,
        strengths=("Synthetic ranking strength.",),
        weaknesses=(),
        limitations=(),
        supporting_metrics={
            "ranking_eligible_fact_count": 4,
            "unknown_fact_count": 0,
            "observed_zero_fact_count": 0,
        },
        evidence_sufficiency=EvidenceSufficiency.COMPARISON_READY,
        evidence_basis=EvidenceBasis.DIRECT_AND_PROXY,
    )


def _calibration_item(
    market_key: str,
    *,
    rank: int,
    score: float,
    evidence_sufficiency: EvidenceSufficiency = EvidenceSufficiency.COMPARISON_READY,
    confidence: IntelligenceConfidence = IntelligenceConfidence.HIGH,
    abstention_reason: str | None = None,
) -> ExplainableRankingItem:
    return ExplainableRankingItem(
        rank=rank,
        market_key=market_key,
        market_name=market_key.title(),
        goal=CareerGoal.SOFTWARE_ENGINEERING,
        score=score,
        raw_score=score,
        confidence=confidence,
        freshness=IntelligenceFreshness.CURRENT,
        ranking_drivers=(
            RankingDriver(
                code="hiring_activity",
                label="observed hiring activity",
                contribution=0.4,
                evidence="observed hiring activity is supported by canonical metric value 10.",
            ),
        ),
        strengths=("Strong observed hiring activity.",),
        weaknesses=(),
        limitations=(),
        supporting_metrics={
            "ranking_eligible_fact_count": 3,
            "ranking_excluded_fact_count": 0,
            "unknown_fact_count": 0,
            "observed_zero_fact_count": 0,
        },
        evidence_sufficiency=evidence_sufficiency,
        evidence_basis=EvidenceBasis.DIRECT,
        is_provisional=evidence_sufficiency is EvidenceSufficiency.LIMITED_EVIDENCE,
        abstention_reason=abstention_reason,
    )


def _contradiction_codes(findings) -> set[ContradictionCode]:
    return {finding.code for finding in findings}


def _contradiction_item(
    market_key: str = "alpha",
    *,
    rank: int = 1,
    score: float = 0.72,
    goal: CareerGoal = CareerGoal.SOFTWARE_ENGINEERING,
    confidence: IntelligenceConfidence = IntelligenceConfidence.MODERATE,
    freshness: IntelligenceFreshness = IntelligenceFreshness.CURRENT,
    ranking_drivers: tuple[RankingDriver, ...] | None = None,
    strengths: tuple[str, ...] = ("Synthetic ranking strength.",),
    weaknesses: tuple[str, ...] = (),
    limitations: tuple[str, ...] = ("Synthetic limitation.",),
    supporting_metrics: dict[str, int | float | str | None] | None = None,
    evidence_sufficiency: EvidenceSufficiency = EvidenceSufficiency.COMPARISON_READY,
    evidence_basis: EvidenceBasis = EvidenceBasis.DIRECT_AND_PROXY,
    is_provisional: bool = False,
) -> ExplainableRankingItem:
    drivers = ranking_drivers
    if drivers is None:
        drivers = (
            RankingDriver(
                code="hiring_activity",
                label="observed hiring activity",
                contribution=0.4,
                evidence="observed hiring activity is supported by canonical metric value 10.",
            ),
            RankingDriver(
                code="tech_signal",
                label="technology employer signal",
                contribution=0.2,
                evidence="technology employer signal is supported by canonical metric value 6.",
            ),
        )
    metrics = {
        "ranking_eligible_fact_count": 3,
        "ranking_excluded_fact_count": 0,
        "unknown_fact_count": 0,
        "observed_zero_fact_count": 0,
        "direct_evidence_count": 2,
        "proxy_evidence_count": 1,
        "total_evidence_count": 3,
    }
    metrics.update(supporting_metrics or {})
    return ExplainableRankingItem(
        rank=rank,
        market_key=market_key,
        market_name=market_key.title(),
        goal=goal,
        score=score,
        raw_score=score,
        confidence=confidence,
        freshness=freshness,
        ranking_drivers=drivers,
        strengths=strengths,
        weaknesses=weaknesses,
        limitations=limitations,
        supporting_metrics=metrics,
        evidence_sufficiency=evidence_sufficiency,
        evidence_basis=evidence_basis,
        is_provisional=is_provisional,
    )


def _contradiction_ranking(
    top: ExplainableRankingItem,
    *,
    ranked_markets: tuple[ExplainableRankingItem, ...] | None = None,
    explanation: str = "Alpha is the top Software engineering recommendation.",
    tie_breaker: str = "Sort by confidence-adjusted score descending, then market key.",
) -> ExplainableRankingReport:
    items = ranked_markets or (top,)
    return ExplainableRankingReport(
        goal=top.goal,
        goal_definition=career_goal_definition(top.goal),
        ranked_markets=items,
        top_market_key=top.market_key,
        explanation=explanation,
        limitations=(),
        tie_breaker=tie_breaker,
        evidence_sufficiency=top.evidence_sufficiency,
        is_provisional=top.is_provisional,
    )


def _contradiction_comparison(
    *,
    market_a_score: float,
    market_b_score: float,
    winner_market_key: str | None,
    outcome: ComparisonOutcome,
) -> MarketComparisonReport:
    side_a = MarketComparisonSide(
        market_key="alpha",
        market_name="Alpha",
        score=market_a_score,
        confidence=IntelligenceConfidence.HIGH,
        strengths=("Alpha strength.",),
        weaknesses=(),
        supporting_metrics={
            "ranking_eligible_fact_count": 3,
            "total_evidence_count": 2,
        },
        evidence_sufficiency=EvidenceSufficiency.COMPARISON_READY,
        evidence_basis=EvidenceBasis.DIRECT,
    )
    side_b = MarketComparisonSide(
        market_key="beta",
        market_name="Beta",
        score=market_b_score,
        confidence=IntelligenceConfidence.HIGH,
        strengths=("Beta strength.",),
        weaknesses=(),
        supporting_metrics={
            "ranking_eligible_fact_count": 3,
            "total_evidence_count": 2,
        },
        evidence_sufficiency=EvidenceSufficiency.COMPARISON_READY,
        evidence_basis=EvidenceBasis.DIRECT,
    )
    return MarketComparisonReport(
        goal=CareerGoal.SOFTWARE_ENGINEERING,
        market_a=side_a,
        market_b=side_b,
        outcome=outcome,
        winner_market_key=winner_market_key,
        explanation="Synthetic comparison declares a winner.",
        confidence=IntelligenceConfidence.HIGH,
        supporting_metrics={
            "market_a_score": market_a_score,
            "market_b_score": market_b_score,
            "score_delta": abs(market_a_score - market_b_score),
        },
        limitations=("Synthetic limitation.",),
        evidence_sufficiency=EvidenceSufficiency.COMPARISON_READY,
    )


def _synthetic_robustness_inputs() -> tuple[
    tuple[MarketIntelligenceProfile, ...],
    dict[str, MarketMetrics],
    dict[CareerGoal, ExplainableRankingReport],
]:
    metrics_by_market = {
        "alpha": _robustness_metrics(
            "alpha",
            active_postings=40,
            employers=9,
            tech_density=8.0,
            early_career=7.0,
            internship=8,
            coop=2,
            product=8,
            ai_cloud=6,
            cybersecurity=5,
        ),
        "beta": _robustness_metrics(
            "beta",
            active_postings=38,
            employers=8,
            tech_density=7.5,
            early_career=6.5,
            internship=7,
            coop=1,
            product=7,
            ai_cloud=5,
            cybersecurity=4,
        ),
        "gamma": _robustness_metrics(
            "gamma",
            active_postings=12,
            employers=5,
            tech_density=3.0,
            early_career=2.5,
            internship=2,
            coop=1,
            product=3,
            ai_cloud=2,
            cybersecurity=1,
        ),
    }
    profiles = tuple(
        _robustness_profile(metrics)
        for metrics in sorted(metrics_by_market.values(), key=lambda item: item.market_key)
    )
    ranking = rank_profiles(
        profiles,
        metrics_by_market,
        goal=CareerGoal.SOFTWARE_ENGINEERING,
        goal_definition=career_goal_definition(CareerGoal.SOFTWARE_ENGINEERING),
    )
    return profiles, metrics_by_market, {CareerGoal.SOFTWARE_ENGINEERING: ranking}


def _robustness_metrics(
    market_key: str,
    *,
    active_postings: int,
    employers: int,
    tech_density: float,
    early_career: float,
    internship: int,
    coop: int,
    product: int,
    ai_cloud: int,
    cybersecurity: int,
) -> MarketMetrics:
    role_active = {
        "ai_cloud_adjacent": ai_cloud,
        "cybersecurity": cybersecurity,
        "product": product,
    }
    return MarketMetrics(
        market_key=market_key,
        market_name=market_key.title(),
        region_id=f"region_{market_key}",
        employer_count=employers,
        sector_count=max(1, min(employers, 5)),
        major_tech_count=2,
        mag7_count=1,
        ai_cloud_employer_count=2,
        cybersecurity_employer_count=1,
        active_posting_total=active_postings,
        active_posting_observed_rows=2,
        active_posting_unknown_rows=1,
        active_posting_zero_rows=1,
        role_active_postings=role_active,
        role_observed_rows={key: 1 for key in role_active},
        role_unknown_rows={},
        internship_total=internship,
        internship_observed_rows=1,
        internship_unknown_rows=0,
        coop_total=coop,
        coop_observed_rows=1,
        coop_unknown_rows=0,
        entry_level_full_time_total=4,
        formal_program_count=2,
        positive_entry_level_score_count=1,
        structural_score=0.75,
        live_market_score=0.70,
        objective_score=0.72,
        tech_density_score=tech_density,
        early_career_score=early_career,
        source_count=3,
        aging_source_count=0,
        stale_source_count=0,
        expired_source_count=0,
        unknown_fact_count=1,
        observed_zero_fact_count=1,
        total_fact_count=12,
        ranking_eligible_fact_count=10,
        ranking_excluded_fact_count=0,
        high_gap_count=0,
        medium_gap_count=0,
        confidence_score=0.9,
        confidence=IntelligenceConfidence.HIGH,
        freshness=IntelligenceFreshness.CURRENT,
        limitations=(),
    )


def _robustness_profile(metrics: MarketMetrics) -> MarketIntelligenceProfile:
    insight = MarketInsight(
        code="synthetic_evidence",
        message="Synthetic evidence is available.",
        evidence="Synthetic canonical metrics support the robustness fixture.",
        impact="Supports deterministic sensitivity tests.",
    )
    opportunity = OpportunityEnvironment(
        hiring_activity="Synthetic hiring evidence is available.",
        employer_diversity="Synthetic employer evidence is available.",
        internship_ecosystem="Synthetic internship evidence is available.",
        coop_ecosystem="Synthetic co-op evidence is available.",
        early_career_support="Synthetic early-career evidence is available.",
        hiring_momentum="No unsupported trend is inferred.",
        overall="Synthetic robustness fixture.",
    )
    return MarketIntelligenceProfile(
        market_key=metrics.market_key,
        market_name=metrics.market_name,
        region_id=metrics.region_id,
        overview="Synthetic robustness profile.",
        strengths=(insight,),
        weaknesses=(),
        hiring_summary="Synthetic hiring summary.",
        employer_summary="Synthetic employer summary.",
        internship_summary="Synthetic internship summary.",
        coop_summary="Synthetic co-op summary.",
        early_career_summary="Synthetic early-career summary.",
        opportunity_environment=opportunity,
        confidence=metrics.confidence,
        confidence_score=metrics.confidence_score,
        freshness=metrics.freshness,
        coverage_summary="Synthetic coverage summary.",
        limitations=metrics.limitations,
        supporting_metrics=metrics.supporting_metrics(),
    )


def _stability_payload(
    analysis: dict[CareerGoal, dict[str, object]],
) -> dict[str, dict[str, object]]:
    return {
        goal.value: {
            market_key: result.as_dict()
            for market_key, result in sorted(by_market.items())
        }
        for goal, by_market in sorted(analysis.items(), key=lambda item: item[0].value)
    }


def _table_counts(session: Session) -> dict[str, int]:
    models = (
        Company,
        CompanyRegionPresence,
        CompanyRegionHiring,
        CompanyRegionEntryLevel,
        SourceRef,
        FactSourceLink,
        RegionMarketScore,
        TrustAssessment,
        RiskRoutingDecision,
        UserReport,
        AutomatedRecheckJob,
        ExceptionCase,
    )
    return {
        model.__tablename__: session.query(model).count() for model in models
    }


def _assert_grounding_shape(grounding) -> None:
    assert {
        "evidence_areas_used",
        "evidence_areas_missing",
        "direct_evidence_summary",
        "proxy_evidence_summary",
        "freshness",
        "coverage",
        "excluded_fact_summary",
        "confidence_constraints",
        "score_margin",
        "stability_status",
        "stability_scenarios",
    }.issubset(grounding)
    assert isinstance(grounding["evidence_areas_used"], list)
    assert isinstance(grounding["evidence_areas_missing"], list)
    assert isinstance(grounding["direct_evidence_summary"], list)
    assert isinstance(grounding["proxy_evidence_summary"], list)
    assert grounding["freshness"] in IntelligenceFreshness.values()
    assert isinstance(grounding["coverage"], str)
    assert isinstance(grounding["excluded_fact_summary"], str)
    assert isinstance(grounding["confidence_constraints"], list)
    assert grounding["stability_status"] in RankingStabilityStatus.values()
    assert isinstance(grounding["stability_scenarios"], list)


def _assert_public_payload_safe(payload) -> None:
    serialized = json.dumps(payload, sort_keys=True)
    forbidden = (
        "trust_assessment_id",
        "risk_routing_decision_id",
        "internal_policy_id",
        "reviewer_notes",
        "reviewer_id",
        "reporter_id",
        "reporter_user_id",
        "reporter_session_id",
        "freeform_report",
        "report_reason",
        "raw_risk",
        "raw_internal_risk",
        "provenance_internal",
        "private_provenance",
        "Traceback",
        str(REPO_ROOT),
    )
    assert all(token not in serialized for token in forbidden)
