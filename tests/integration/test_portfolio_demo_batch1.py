"""Golden behavior for the governed eight-market portfolio demonstration."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.career_decisions.models import CareerAction, CareerDecision
from backend.career_identity.models import CareerIdentity, CareerIdentityFact
from backend.companies.models import Company
from backend.current_opportunities.models import (
    CurrentOpportunity,
    CurrentOpportunitySourceLink,
    OpportunityCoverageContract,
    OpportunitySourceObservation,
)
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.opportunities.models import Opportunity, OpportunitySource
from backend.recommendations.models import RecommendationGoalMode
from backend.users.models import SavedMarketArtifact, UserPreferenceProfile
from seeds.mvp_seed import run_seed
from seeds.portfolio_seed import run_portfolio_seed

NOW = datetime.now(UTC)
LOCAL_HEADERS = {
    "X-Verified-OIDC-Claims": json.dumps(
        {
            "iss": "https://local.job-market-intelligence.test/",
            "sub": "local|explorer",
            "email": "local-explorer@example.test",
            "name": "Local explorer",
        }
    )
}


def _seed_portfolio(session: Session):
    seed = run_seed(session, demo_now=NOW)
    portfolio = run_portfolio_seed(
        session,
        seed,
        as_of=NOW.date(),
        demo_now=NOW,
    )
    session.flush()
    return portfolio


def test_portfolio_seed_is_canonical_governed_and_idempotent(session: Session) -> None:
    first = _seed_portfolio(session)

    assert session.query(Region).count() == 8
    assert session.query(Company).count() == 20
    microsoft = session.query(Company).filter(func.lower(Company.company_name) == "microsoft").all()
    assert [row.company_id for row in microsoft] == ["cmp_microsoft"]
    assert session.get(Company, "comp_microsoft") is None

    assert session.query(Opportunity).count() == 24
    assert session.query(CurrentOpportunity).count() == 24
    assert Counter(row.market_id for row in session.query(CurrentOpportunity).all()) == {
        "greater_boston": 3,
        "greater_nyc": 3,
        "sf_bay_area": 3,
        "greater_seattle": 3,
        "washington_dc": 3,
        "austin": 3,
        "atlanta": 3,
        "chicago": 3,
    }
    assert Counter(row.role_family for row in session.query(CurrentOpportunity).all()) == {
        "software_engineering": 6,
        "product_management": 5,
        "solutions_engineering": 5,
        "applied_ai": 4,
        "data_ai": 4,
    }
    assert Counter(row.seniority_level for row in session.query(CurrentOpportunity).all()) == {
        "entry_level": 12,
        "early_career": 8,
        "new_graduate": 2,
        "internship": 2,
    }

    current_rows = session.query(CurrentOpportunity).all()
    assert sum(row.ranking_eligible for row in current_rows) == 20
    assert {row.freshness_state for row in current_rows} == {"fresh", "aging", "stale"}
    assert {row.canonical_status for row in current_rows} == {"active", "closed"}
    exclusion_codes = {code for row in current_rows for code in row.ranking_ineligible_reasons}
    assert {
        "coverage_experimental",
        "coverage_unsupported",
        "identity_confidence_too_low",
        "not_active_current_opportunity",
    } <= exclusion_codes

    assert session.query(OpportunityCoverageContract).count() == 10
    assert {row.status for row in session.query(OpportunityCoverageContract).all()} == {
        "limited",
        "experimental",
        "unsupported",
    }
    assert session.query(OpportunitySourceObservation).count() == 27
    assert session.query(CurrentOpportunitySourceLink).count() == 24
    # Each marketplace row retains both its primary URL evidence and the
    # explicit verification source supplied by the scenario.
    assert session.query(OpportunitySource).count() == 48
    assert all(
        row.source_url.startswith("https://portfolio-demo.example/")
        for row in session.query(OpportunitySource).all()
    )
    assert all(
        row.application_url is None
        or row.application_url.startswith("https://portfolio-demo.example/")
        for row in current_rows
    )

    identity = session.query(CareerIdentity).one()
    counts_before = {
        "companies": session.query(Company).count(),
        "marketplace": session.query(Opportunity).count(),
        "current": session.query(CurrentOpportunity).count(),
        "observations": session.query(OpportunitySourceObservation).count(),
        "coverage": session.query(OpportunityCoverageContract).count(),
        "facts": session.query(CareerIdentityFact).count(),
        "decisions": session.query(CareerDecision).count(),
        "actions": session.query(CareerAction).count(),
        "identity_version": identity.current_version,
    }
    second = _seed_portfolio(session)
    identity = session.query(CareerIdentity).one()
    counts_after = {
        "companies": session.query(Company).count(),
        "marketplace": session.query(Opportunity).count(),
        "current": session.query(CurrentOpportunity).count(),
        "observations": session.query(OpportunitySourceObservation).count(),
        "coverage": session.query(OpportunityCoverageContract).count(),
        "facts": session.query(CareerIdentityFact).count(),
        "decisions": session.query(CareerDecision).count(),
        "actions": session.query(CareerAction).count(),
        "identity_version": identity.current_version,
    }
    assert counts_after == counts_before
    assert first.reviewer.decision_id == second.reviewer.decision_id
    assert second.reviewer.created_decision is False


def test_portfolio_opportunity_filters_preserve_eligibility_and_unknowns(
    session: Session,
    api_client: TestClient,
) -> None:
    _seed_portfolio(session)

    boston = api_client.get(
        "/current-opportunities",
        params={
            "market": "greater_boston",
            "role_family": "software_engineering",
            "opportunity_type": "job",
        },
        headers=LOCAL_HEADERS,
    )
    assert boston.status_code == 200
    boston_rows = boston.json()["data"]["opportunities"]
    assert len(boston_rows) == 3
    assert {row["work_arrangement"] for row in boston_rows} == {
        "onsite",
        "hybrid",
        "remote",
    }
    assert {row["seniority_level"] for row in boston_rows} == {
        "entry_level",
        "new_graduate",
        "early_career",
    }
    assert all(row["ranking_eligible"] for row in boston_rows)
    assert all(row["coverage_status"] == "limited" for row in boston_rows)
    assert all(row["provenance"]["sources"][0]["synthetic"] for row in boston_rows)

    applied_ai = api_client.get(
        "/current-opportunities",
        params={"role_family": "applied_ai", "opportunity_type": "job"},
        headers=LOCAL_HEADERS,
    ).json()["data"]["opportunities"]
    assert len(applied_ai) == 4
    assert {row["market_id"] for row in applied_ai} == {
        "greater_nyc",
        "sf_bay_area",
        "greater_seattle",
        "chicago",
    }

    all_chicago = api_client.get(
        "/current-opportunities",
        params={"market": "chicago", "include_ineligible": True},
        headers=LOCAL_HEADERS,
    ).json()["data"]["opportunities"]
    # Closed records are correctly suppressed from display even when the
    # caller asks to include ranking-ineligible but still displayable rows.
    assert len(all_chicago) == 2
    assert any("coverage_unsupported" in row["ranking_ineligible_reasons"] for row in all_chicago)
    closed = (
        session.query(CurrentOpportunity)
        .filter_by(market_id="chicago", canonical_status="closed")
        .one()
    )
    assert "not_active_current_opportunity" in closed.ranking_ineligible_reasons

    nyc_unknown = session.get(
        CompanyRegionHiring,
        "hiring_cmp_liberty_cyber_systems_greater_nyc",
    )
    nyc_zero = session.get(
        CompanyRegionHiring,
        "hiring_cmp_brooklyn_cloudworks_greater_nyc",
    )
    assert nyc_unknown.active_posting_count_now is None
    assert nyc_unknown.active_posting_count_now_status == "unknown"
    assert nyc_zero.active_posting_count_now == 0
    assert nyc_zero.active_posting_count_now_status == "zero_observed"


def test_all_modes_and_three_reviewer_scenarios_are_behaviorally_distinct(
    session: Session,
    api_client: TestClient,
) -> None:
    portfolio = _seed_portfolio(session)

    expected_top = {
        "maximize_entry_level_access": "sf_bay_area",
        "maximize_prestige": "sf_bay_area",
        "maximize_ai_cloud_concentration": "greater_nyc",
        "maximize_underrated_markets": "greater_boston",
        "maximize_internship_coop_access": "sf_bay_area",
        "maximize_lower_competition": "austin",
        "maximize_geographic_flexibility": "greater_boston",
    }
    signatures: set[tuple[str, ...]] = set()
    actionable_modes = 0
    for mode in RecommendationGoalMode:
        first = api_client.post(
            "/recommendations/strategy",
            json={"goal_mode": mode.value, "include_company_recommendations": True},
        )
        repeated = api_client.post(
            "/recommendations/strategy",
            json={"goal_mode": mode.value, "include_company_recommendations": True},
        )
        assert first.status_code == repeated.status_code == 200
        data = first.json()["data"]
        repeated_data = repeated.json()["data"]
        ranked = data["ranked_region_recommendations"]
        signature = tuple(item["target"]["target_id"] for item in ranked)
        assert signature == tuple(
            item["target"]["target_id"] for item in repeated_data["ranked_region_recommendations"]
        )
        assert signature[0] == expected_top[mode.value]
        signatures.add(signature)
        assert ranked[0]["explanation"]["fit_reasons"]
        assert ranked[0]["explanation"]["evidence_refs"]
        assert ranked[0]["explanation"]["confidence_summary"]
        assert ranked[0]["explanation"]["freshness_summary"]["freshness_status"] == (
            "simulated_current"
        )
        assert any(
            "synthetic demonstration" in warning.lower()
            for warning in ranked[0]["explanation"]["freshness_summary"]["warnings"]
        )
        plan = data["market_strategy_plan"]
        target_count = sum(
            len(plan[key])
            for key in (
                "primary_region_targets",
                "secondary_region_targets",
                "fallback_region_targets",
            )
        )
        actionable_modes += target_count > 0
        assert target_count or plan["watchlist_items"]
        if mode is RecommendationGoalMode.MAXIMIZE_LOWER_COMPETITION:
            assert ranked[0]["target"]["target_id"] == "austin"
            assert any(
                item["target"]["target_id"] == "austin"
                for item in plan["watchlist_items"]
            )
            actionable = [
                *plan["primary_region_targets"],
                *plan["secondary_region_targets"],
                *plan["fallback_region_targets"],
            ]
            assert actionable
            assert actionable[0]["target"]["target_id"] != "austin"

    assert len(signatures) == 7
    assert actionable_modes == 7

    # Public goal strategies use shared market evidence. Supplying two
    # different authenticated identities must not silently personalize them.
    goal_request = {
        "goal_mode": "maximize_entry_level_access",
        "include_company_recommendations": True,
    }
    seeded_identity_result = api_client.post(
        "/recommendations/strategy", json=goal_request, headers=LOCAL_HEADERS
    )
    other_identity_result = api_client.post(
        "/recommendations/strategy",
        json=goal_request,
        headers={
            "X-Verified-OIDC-Claims": json.dumps(
                {
                    "iss": "https://local.job-market-intelligence.test/",
                    "sub": "local|different-goal-reviewer",
                }
            )
        },
    )
    assert seeded_identity_result.status_code == other_identity_result.status_code == 200
    assert seeded_identity_result.json()["data"] == other_identity_result.json()["data"]

    # Scenario A: the default Boston/software/job workflow has three governed
    # routes and requires no Career Identity setup.
    scenario_a = api_client.get(
        "/current-opportunities",
        params={
            "market": "greater_boston",
            "role_family": "software_engineering",
            "opportunity_type": "job",
        },
        headers=LOCAL_HEADERS,
    ).json()["data"]["opportunities"]
    assert len(scenario_a) == 3

    # Scenario B: alternatives are explicitly user-selected and persisted; no
    # proximity or radius calculation is represented by the fixture.
    comparison = (
        session.query(SavedMarketArtifact)
        .filter_by(artifact_ref="reviewer-scenario-b-nyc-boston-dc")
        .one()
    )
    assert comparison.snapshot["region_ids"] == [
        "greater_nyc",
        "greater_boston",
        "washington_dc",
    ]
    assert "no automatic radius" in comparison.notes.lower()
    for alternative in ("greater_boston", "washington_dc"):
        response = api_client.get(
            "/compare",
            params={"region_a": "greater_nyc", "region_b": alternative},
        )
        assert response.status_code == 200
        assert response.json()["status"] in {"success", "partial"}

    # Scenario C: the explicit local-only identity, preferences, strategic
    # matches, decision, selection, and next actions are all persisted through
    # their domain services.
    identity = api_client.get("/me/career-identity", headers=LOCAL_HEADERS)
    assert identity.status_code == 200
    assert identity.json()["data"]["sufficiency_state"] == "sufficient"
    assert session.query(UserPreferenceProfile).one().career_stage == "entry_level"
    matches = api_client.get(
        "/current-opportunities/matches",
        params={"limit": 10},
        headers=LOCAL_HEADERS,
    )
    assert matches.status_code == 200
    match_rows = matches.json()["data"]["matches"]
    assert len(match_rows) >= 3
    assert len({row["opportunity"]["market_id"] for row in match_rows[:5]}) >= 3
    assert all(row["limitations"] for row in match_rows[:3])

    decisions = api_client.get("/me/decisions", headers=LOCAL_HEADERS)
    assert decisions.status_code == 200
    decision_rows = decisions.json()["data"]["decisions"]
    seeded = next(
        row for row in decision_rows if row["decision_id"] == portfolio.reviewer.decision_id
    )
    assert seeded["selected_option_id"] is not None
    assert portfolio.reviewer.action_count == 3

    # Only the explicit local reviewer is populated. A distinct fresh local
    # identity still begins empty rather than inheriting fabricated persona data.
    clean_headers = {
        "X-Verified-OIDC-Claims": json.dumps(
            {
                "iss": "https://local.job-market-intelligence.test/",
                "sub": "local|clean-reviewer",
                "email": "clean-reviewer@example.test",
            }
        )
    }
    clean = api_client.get("/me/career-identity", headers=clean_headers)
    assert clean.status_code == 200
    clean_data = clean.json()["data"]
    assert clean_data["completeness_state"] == "empty"
    assert sum(len(rows) for rows in clean_data["facts"].values()) == 0
