"""Minimal backend/frontend API contract tests.

These tests pin only the response fields the Vite frontend renders. They are
not browser tests and do not assert layout.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.api.app import create_app
from backend.api.dependencies import get_session
from backend.api.protection import _public_demo_route_allowed
from backend.geography.models import Region
from backend.imports.bulk import (
    import_all_curated_market_datasets,
    run_all_curated_market_post_imports,
)
from backend.market_intelligence.schemas import (
    CareerGoal,
    ComparisonOutcome,
    EvidenceBasis,
    EvidenceSufficiency,
    IntelligenceConfidence,
    IntelligenceFreshness,
    RankingStabilityStatus,
)
from seeds import mvp_seed
from seeds.mvp_data import REGION_BOSTON, REGION_SF

AS_OF = date(2026, 7, 9)


def _client_for_session(session: Session) -> TestClient:
    app = create_app(engine=session.bind)

    def _override() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_session] = _override
    return TestClient(app)


def _assert_envelope(body: dict[str, Any]) -> None:
    assert set(body) == {"status", "data", "metadata", "error"}
    assert "warnings" in body["metadata"]


def test_frontend_contract_seeded_api_shapes(session: Session) -> None:
    mvp_seed.run_seed(session)
    session.commit()
    client = _client_for_session(session)

    regions = client.get("/regions").json()
    _assert_envelope(regions)
    assert {"region_id", "display_name"}.issubset(regions["data"]["regions"][0].keys())

    region = client.get(f"/regions/{REGION_BOSTON}").json()
    _assert_envelope(region)
    assert {"freshness_status", "is_stale", "freshness_expires_at"}.issubset(
        region["metadata"]["freshness"].keys()
    )
    assert {
        "region_id",
        "display_name",
        "scores",
        "top_companies_present",
        "top_companies_hiring",
        "entry_level_summary",
        "major_tech_summary",
        "mag7_summary",
    }.issubset(region["data"].keys())

    company = client.get("/companies/comp_alphabet").json()
    _assert_envelope(company)
    assert {
        "company_id",
        "classification_confidence",
        "is_major_tech",
        "is_mag7",
        "regions_present",
        "regions_hiring",
        "entry_level_regions",
    }.issubset(company["data"].keys())

    comparison = client.get(
        "/compare", params={"region_a": REGION_BOSTON, "region_b": REGION_SF}
    ).json()
    _assert_envelope(comparison)
    assert isinstance(comparison["data"]["category_winners"], dict)
    for category, winner in comparison["data"]["category_winners"].items():
        assert isinstance(category, str)
        assert winner is None or isinstance(winner, str)

    personalized = client.post(
        "/discover/personalized",
        json={
            "region_ids": [REGION_BOSTON, REGION_SF],
            "role_targets": ["product", "ai_cloud_adjacent", "cybersecurity"],
            "industry_preferences": ["ai", "cloud"],
            "career_stage": "entry_level",
            "prestige_preference": "medium",
            "brand_preference": "medium",
            "limit": 5,
        },
    ).json()
    _assert_envelope(personalized)
    ranked_regions = personalized["data"]["ranked_regions"]
    ranked_companies = personalized["data"]["ranked_companies"]
    assert ranked_regions
    assert ranked_companies
    assert {"personal_market_score", "objective_opportunity_score"}.issubset(
        ranked_regions[0].keys()
    )
    assert {"personal_company_score", "role_fit", "industry_fit"}.issubset(
        ranked_companies[0].keys()
    )


def test_frontend_contract_warning_shape(session: Session) -> None:
    session.add(
        Region(
            region_id="contract_partial",
            region_name="contract_partial",
            display_name="Contract Partial",
            region_type="greater_region",
        )
    )
    session.flush()
    client = _client_for_session(session)

    body = client.get("/regions/contract_partial").json()

    _assert_envelope(body)
    assert body["status"] == "partial"
    warnings = body["metadata"]["warnings"]
    assert warnings
    for warning in warnings:
        assert {"warning_code", "severity", "message"}.issubset(warning.keys())
        assert isinstance(warning["warning_code"], str)
        assert warning["severity"] in {"low", "medium", "high"}
        assert isinstance(warning["message"], str)


def test_frontend_contract_imported_market_operations_shapes(session: Session) -> None:
    assert import_all_curated_market_datasets(session, as_of=AS_OF).ok
    assert run_all_curated_market_post_imports(session, as_of=AS_OF).ok
    client = _client_for_session(session)

    overview = client.get("/markets/imported/health", params={"as_of": AS_OF.isoformat()}).json()
    _assert_envelope(overview)
    summary = overview["data"]["summary"]
    assert {
        "registered_market_count",
        "healthy_market_count",
        "markets_needing_refresh",
        "markets_with_limited_coverage",
        "markets_with_stale_sources",
        "total_stale_source_count",
        "total_ranking_excluded_fact_count",
        "highest_priority_maintenance_market",
        "recommended_next_maintenance_action",
        "overall_health_status",
    }.issubset(summary.keys())
    assert summary["registered_market_count"] == 8
    assert summary["overall_health_status"] in {
        "healthy",
        "needs_refresh",
        "limited_coverage",
        "stale_sources",
        "validation_failed",
        "ranking_limited",
    }

    markets = overview["data"]["markets"]
    assert len(markets) == 8
    first_market = sorted(markets, key=lambda item: item["market_key"])[0]
    assert {
        "market_key",
        "market_name",
        "counts",
        "coverage_summary",
        "freshness_summary",
        "health_status",
        "recommended_next_action",
    }.issubset(first_market.keys())
    counts = first_market["counts"]
    assert counts["unknown_fact_count"] != counts["observed_zero_fact_count"]
    assert {"unknown_fact_count", "observed_zero_fact_count"}.issubset(counts.keys())

    market_key = first_market["market_key"]
    sources = client.get(
        f"/markets/imported/{market_key}/sources",
        params={"as_of": AS_OF.isoformat()},
    ).json()
    gaps = client.get(
        f"/markets/imported/{market_key}/gaps",
        params={"as_of": AS_OF.isoformat()},
    ).json()
    ranking = client.get(
        f"/markets/imported/{market_key}/ranking-diagnostics",
        params={"as_of": AS_OF.isoformat()},
    ).json()
    readiness = client.get(
        f"/markets/imported/{market_key}/refresh-readiness",
        params={"as_of": AS_OF.isoformat()},
    ).json()
    diff = client.get(
        f"/markets/imported/{market_key}/diff-preview",
        params={"as_of": AS_OF.isoformat()},
    ).json()

    for body in (sources, gaps, ranking, readiness, diff):
        _assert_envelope(body)
        assert body["status"] == "success"
        _assert_no_private_frontend_contract_tokens(body)

    assert {
        "source_count",
        "stale_source_count",
        "aging_source_count",
        "expired_source_count",
        "oldest_source_age_days",
        "important_stale_sources",
        "sources",
    }.issubset(sources["data"].keys())
    assert {"gap_count", "highest_severity", "gaps"}.issubset(gaps["data"].keys())
    assert {
        "excluded_fact_count",
        "ranking_limited_ratio",
        "affected_areas",
        "reason_counts",
        "diagnostics",
    }.issubset(ranking["data"].keys())
    assert {
        "readiness_status",
        "blocking_conditions",
        "warnings",
        "ordered_actions",
        "maintenance_priority",
        "priority_score",
    }.issubset(readiness["data"].keys())
    assert readiness["data"]["readiness_status"] in {
        "ready",
        "needs_source_refresh",
        "needs_coverage_expansion",
        "needs_validation_fix",
        "needs_ranking_review",
        "not_ready",
    }
    assert {
        "overall_diff_risk",
        "risk_reasons",
        "blocking_issues",
        "warnings",
        "summary_counts",
        "narrative_summary",
        "changes",
    }.issubset(diff["data"].keys())
    assert "unknown_to_zero_changes" in diff["data"]["summary_counts"]
    assert "zero_to_unknown_changes" in diff["data"]["summary_counts"]

    missing = client.get(
        "/markets/imported/not_registered/health",
        params={"as_of": AS_OF.isoformat()},
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"


def test_frontend_contract_market_intelligence_shapes(session: Session) -> None:
    assert import_all_curated_market_datasets(session, as_of=AS_OF).ok
    assert run_all_curated_market_post_imports(session, as_of=AS_OF).ok
    client = _client_for_session(session)

    platform = client.get(
        "/market-intelligence",
        params={"goal": "data_science", "as_of": AS_OF.isoformat()},
    ).json()
    _assert_envelope(platform)
    _assert_no_private_frontend_contract_tokens(platform)
    assert platform["status"] == "success"
    data = platform["data"]
    assert {
        "market_count",
        "profile_count",
        "supported_goals",
        "profiles",
        "default_ranking",
        "highest_confidence_market",
        "public_summary",
        "limitations",
    }.issubset(data.keys())
    assert data["market_count"] == 8
    assert {goal["goal"] for goal in data["supported_goals"]} == CareerGoal.values()
    assert any("data-science" in item for item in data["default_ranking"]["limitations"])

    ranking = data["default_ranking"]
    assert {
        "goal",
        "goal_definition",
        "ranked_markets",
        "top_market_key",
        "explanation",
        "limitations",
        "tie_breaker",
        "evidence_sufficiency",
        "is_provisional",
        "abstention_reason",
        "contradiction_status",
        "contradictions",
        "grounding",
    }.issubset(ranking.keys())
    assert ranking["goal"] == "data_science"
    assert ranking["evidence_sufficiency"] in EvidenceSufficiency.values()
    assert ranking["evidence_sufficiency"] == EvidenceSufficiency.NOT_SUPPORTED.value
    assert ranking["top_market_key"] is None
    assert "diagnostic ordering" in ranking["explanation"]
    assert "currently the top" not in data["public_summary"]
    assert isinstance(ranking["is_provisional"], bool)
    if ranking["evidence_sufficiency"] in {
        EvidenceSufficiency.INSUFFICIENT_EVIDENCE.value,
        EvidenceSufficiency.NOT_SUPPORTED.value,
    }:
        assert ranking["abstention_reason"]
    assert len(ranking["ranked_markets"]) == 8
    first_ranked = ranking["ranked_markets"][0]
    assert {
        "rank",
        "market_key",
        "market_name",
        "goal",
        "score",
        "confidence",
        "freshness",
        "ranking_drivers",
        "strengths",
        "weaknesses",
        "limitations",
        "supporting_metrics",
        "evidence_sufficiency",
        "evidence_basis",
        "is_provisional",
        "abstention_reason",
        "contradiction_status",
        "contradictions",
        "grounding",
    }.issubset(first_ranked.keys())
    assert first_ranked["confidence"] in IntelligenceConfidence.values()
    assert first_ranked["freshness"] in IntelligenceFreshness.values()
    assert first_ranked["evidence_sufficiency"] in EvidenceSufficiency.values()
    assert first_ranked["evidence_basis"] in EvidenceBasis.values()
    assert isinstance(first_ranked["is_provisional"], bool)
    if first_ranked["evidence_sufficiency"] in {
        EvidenceSufficiency.INSUFFICIENT_EVIDENCE.value,
        EvidenceSufficiency.NOT_SUPPORTED.value,
    }:
        assert first_ranked["abstention_reason"]
    assert first_ranked["ranking_drivers"]
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
    }.issubset(first_ranked["grounding"].keys())
    assert first_ranked["grounding"]["stability_status"] in RankingStabilityStatus.values()
    assert isinstance(first_ranked["grounding"]["stability_scenarios"], list)
    assert first_ranked["grounding"]["score_margin"] is None or (
        first_ranked["grounding"]["score_margin"] >= 0
    )
    assert {
        "code",
        "label",
        "contribution",
        "evidence",
    }.issubset(first_ranked["ranking_drivers"][0].keys())
    assert {
        "unknown_fact_count",
        "observed_zero_fact_count",
        "ranking_excluded_fact_count",
    }.issubset(first_ranked["supporting_metrics"].keys())

    profile = client.get(
        f"/market-intelligence/{first_ranked['market_key']}",
        params={"as_of": AS_OF.isoformat()},
    ).json()
    _assert_envelope(profile)
    _assert_no_private_frontend_contract_tokens(profile)
    assert {
        "market_key",
        "market_name",
        "overview",
        "strengths",
        "weaknesses",
        "hiring_summary",
        "employer_summary",
        "internship_summary",
        "coop_summary",
        "early_career_summary",
        "opportunity_environment",
        "confidence",
        "freshness",
        "coverage_summary",
        "limitations",
        "supporting_metrics",
        "grounding",
    }.issubset(profile["data"].keys())
    assert {
        "hiring_activity",
        "employer_diversity",
        "internship_ecosystem",
        "coop_ecosystem",
        "early_career_support",
        "hiring_momentum",
        "overall",
    }.issubset(profile["data"]["opportunity_environment"].keys())
    assert profile["data"]["confidence"] in IntelligenceConfidence.values()
    assert profile["data"]["freshness"] in IntelligenceFreshness.values()
    assert profile["data"]["supporting_metrics"]["unknown_fact_count"] != profile["data"][
        "supporting_metrics"
    ]["observed_zero_fact_count"]
    assert profile["data"]["grounding"]["score_margin"] is None
    assert profile["data"]["grounding"]["stability_status"] == "indeterminate"

    comparison = client.get(
        "/market-comparisons/atlanta/boston",
        params={"goal": "software_engineering", "as_of": AS_OF.isoformat()},
    ).json()
    _assert_envelope(comparison)
    _assert_no_private_frontend_contract_tokens(comparison)
    assert {
        "goal",
        "market_a",
        "market_b",
        "outcome",
        "winner_market_key",
        "explanation",
        "confidence",
        "supporting_metrics",
        "limitations",
        "evidence_sufficiency",
        "is_provisional",
        "abstention_reason",
        "contradiction_status",
        "contradictions",
        "grounding",
    }.issubset(comparison["data"].keys())
    assert comparison["data"]["outcome"] in ComparisonOutcome.values()
    assert comparison["data"]["confidence"] in IntelligenceConfidence.values()
    assert comparison["data"]["evidence_sufficiency"] in EvidenceSufficiency.values()
    assert isinstance(comparison["data"]["is_provisional"], bool)
    if comparison["data"]["evidence_sufficiency"] in {
        EvidenceSufficiency.INSUFFICIENT_EVIDENCE.value,
        EvidenceSufficiency.NOT_SUPPORTED.value,
    }:
        assert comparison["data"]["abstention_reason"]
    for side in ("market_a", "market_b"):
        assert {
            "market_key",
            "market_name",
            "score",
            "confidence",
            "strengths",
            "weaknesses",
            "supporting_metrics",
            "evidence_sufficiency",
            "evidence_basis",
            "grounding",
        }.issubset(comparison["data"][side].keys())
        assert comparison["data"][side]["evidence_basis"] in EvidenceBasis.values()
    assert comparison["data"]["grounding"]["score_margin"] == comparison["data"][
        "supporting_metrics"
    ]["score_delta"]
    assert comparison["data"]["grounding"]["stability_status"] in RankingStabilityStatus.values()
    assert isinstance(comparison["data"]["grounding"]["stability_scenarios"], list)

    unsupported_comparison = client.get(
        "/market-comparisons/atlanta/boston",
        params={"goal": "data_science", "as_of": AS_OF.isoformat()},
    ).json()
    _assert_envelope(unsupported_comparison)
    _assert_no_private_frontend_contract_tokens(unsupported_comparison)
    assert unsupported_comparison["data"]["goal"] == CareerGoal.DATA_SCIENCE.value
    assert unsupported_comparison["data"]["outcome"] == ComparisonOutcome.NO_WINNER.value
    assert unsupported_comparison["data"]["winner_market_key"] is None
    assert unsupported_comparison["data"]["evidence_sufficiency"] == (
        EvidenceSufficiency.NOT_SUPPORTED.value
    )
    assert unsupported_comparison["data"]["abstention_reason"]
    assert "does not name a winner" in unsupported_comparison["data"]["explanation"]

    goal_comparisons = client.get(
        "/career-goal-comparisons",
        params={"as_of": AS_OF.isoformat()},
    ).json()
    _assert_envelope(goal_comparisons)
    assert {
        report["goal"] for report in goal_comparisons["data"]["comparisons"]
    } == CareerGoal.values()

    missing = client.get(
        "/market-intelligence/not_registered",
        params={"as_of": AS_OF.isoformat()},
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"

    bad_goal = client.get(
        "/market-comparisons",
        params={"goal": "not_a_goal", "as_of": AS_OF.isoformat()},
    )
    assert bad_goal.status_code == 400
    assert bad_goal.json()["error"]["code"] == "VALIDATION_ERROR"


def test_frontend_contract_market_intelligence_routes_are_get_only_public_demo() -> None:
    app = create_app()
    expected_paths = {
        "/market-intelligence",
        "/market-intelligence/{market_key}",
        "/market-comparisons",
        "/market-comparisons/{market_a}/{market_b}",
        "/career-goal-comparisons",
        "/career-goal-comparisons/{goal}",
    }
    found = {
        route.path: route.methods
        for route in app.routes
        if getattr(route, "path", "") in expected_paths
    }
    assert found.keys() == expected_paths
    assert all(methods == {"GET"} for methods in found.values())

    assert _public_demo_route_allowed("GET", "/market-intelligence")
    assert _public_demo_route_allowed("GET", "/market-intelligence/atlanta")
    assert _public_demo_route_allowed("GET", "/market-comparisons")
    assert _public_demo_route_allowed("GET", "/market-comparisons/atlanta/boston")
    assert _public_demo_route_allowed("GET", "/career-goal-comparisons")
    assert _public_demo_route_allowed("GET", "/career-goal-comparisons/data_science")
    assert not _public_demo_route_allowed("POST", "/market-intelligence")
    assert not _public_demo_route_allowed("POST", "/market-comparisons/atlanta/boston")


def _assert_no_private_frontend_contract_tokens(value: Any) -> None:
    serialized = str(value).lower()
    forbidden = (
        "trust_assessment_id",
        "risk_routing_decision_id",
        "internal_policy_id",
        "reviewer_notes",
        "reporter_user_id",
        "reporter_session_id",
        "report_reason",
        "raw_internal_risk",
        "private_provenance",
        "traceback",
    )
    assert all(token not in serialized for token in forbidden)
