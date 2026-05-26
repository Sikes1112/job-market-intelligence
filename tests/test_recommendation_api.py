"""Layer 14E recommendation API tests."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.outputs.repository import OutputMetadataRepository
from backend.presence.models import CompanyRegionPresence
from backend.recommendations.models import RecommendationGoalMode
from backend.scoring.models import RegionMarketScore


def _seed_region(
    session: Session,
    *,
    region_id: str,
    display_name: str,
    objective: float | None = None,
    early_career: float | None = None,
    density: float | None = None,
) -> None:
    session.add(
        Region(
            region_id=region_id,
            region_name=region_id,
            display_name=display_name,
            region_type="greater_region",
        )
    )
    session.flush()
    if objective is not None or early_career is not None or density is not None:
        session.add(
            RegionMarketScore(
                region_score_id=f"score_{region_id}",
                region_id=region_id,
                objective_opportunity_score=objective,
                early_career_accessibility_score=early_career,
                tech_market_density_score=density,
                general_density_score=density,
                score_ruleset_version="marketscore_v1",
            )
        )
        session.flush()


def _seed_company(
    session: Session,
    *,
    company_id: str,
    name: str,
    region_id: str,
    sector: str | None = "ai",
    prestige: float | None = None,
    internships: int | None = 3,
    entry_score: float | None = 0.7,
) -> None:
    session.add(
        Company(
            company_id=company_id,
            company_name=name,
            normalized_company_name=name.casefold(),
            sector_primary=sector,
            eligibility_status="eligible",
            classification_confidence="high",
            is_major_tech=bool(prestige and prestige >= 0.7),
            prestige_score=prestige,
        )
    )
    session.flush()
    session.add_all(
        [
            CompanyRegionPresence(
                presence_id=f"presence_{company_id}_{region_id}",
                company_id=company_id,
                region_id=region_id,
                presence_status="present",
                presence_basis="office_plus_hiring",
                office_evidence_flag=True,
                hiring_evidence_flag=True,
                presence_confidence="high",
            ),
            CompanyRegionHiring(
                hiring_id=f"hiring_{company_id}_{region_id}",
                company_id=company_id,
                region_id=region_id,
                currently_hiring_flag=True,
                active_posting_count_now=8,
                posting_count_30d=12,
                role_family_summary={"product": 3, "ai_cloud_adjacent": 4},
                hiring_confidence="high",
            ),
            CompanyRegionEntryLevel(
                entry_level_id=f"entry_{company_id}_{region_id}",
                company_id=company_id,
                region_id=region_id,
                internship_count=internships,
                coop_count=1,
                entry_level_full_time_count=4,
                formal_early_career_program_flag=True,
                entry_level_access_score=entry_score,
                entry_level_confidence="high",
            ),
        ]
    )
    session.flush()


def _seed_recommendation_world(session: Session) -> None:
    _seed_region(
        session,
        region_id="greater_boston",
        display_name="Greater Boston",
        objective=0.82,
        early_career=0.86,
        density=0.78,
    )
    _seed_region(
        session,
        region_id="raleigh_durham",
        display_name="Raleigh-Durham",
        objective=0.67,
        early_career=0.74,
        density=0.52,
    )
    _seed_region(
        session,
        region_id="cleveland",
        display_name="Cleveland",
        objective=0.42,
        early_career=0.48,
        density=0.24,
    )
    _seed_company(
        session,
        company_id="comp_ai",
        name="Example AI",
        region_id="greater_boston",
        sector="ai",
        prestige=0.9,
        internships=5,
        entry_score=0.82,
    )
    _seed_company(
        session,
        company_id="comp_tools",
        name="Example Tools",
        region_id="raleigh_durham",
        sector="developer_tools",
        prestige=0.45,
        internships=2,
        entry_score=0.64,
    )


def test_goal_modes_endpoint_returns_required_metadata(api_client) -> None:
    response = api_client.get("/recommendations/goal-modes")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    payload = body["data"]
    goal_modes = payload["goal_modes"]
    assert {item["goal_mode"] for item in goal_modes} == {
        mode.value for mode in RecommendationGoalMode
    }
    for item in goal_modes:
        assert item["label"]
        assert item["description"]
        assert item["prioritization_summary"]
        assert item["weighted_components"]
        assert "available_from" not in item["weighted_components"][0]


def test_strategy_endpoint_returns_ranked_recommendations_and_plan(
    api_client,
    session,
) -> None:
    _seed_recommendation_world(session)

    response = api_client.post(
        "/recommendations/strategy",
        json={
            "goal_mode": RecommendationGoalMode.MAXIMIZE_ENTRY_LEVEL_ACCESS.value,
            "include_company_recommendations": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"success", "partial"}
    data = body["data"]
    assert data["selected_goal_mode"]["goal_mode"] == (
        RecommendationGoalMode.MAXIMIZE_ENTRY_LEVEL_ACCESS.value
    )
    assert data["ranking_tie_breaker"]
    assert data["ranked_region_recommendations"]
    assert data["ranked_company_recommendations"]
    first = data["ranked_region_recommendations"][0]
    assert {"rank", "target", "final_score", "normalized_score"}.issubset(first)
    assert first["score_components_used"]
    assert "score_components_missing" in first
    assert "score_components_proxy" in first
    assert "penalties_applied" in first
    assert "warnings" in first
    assert first["explanation"]["fit_reasons"]
    assert "manual_verification" in first["explanation"]
    assert first["explanation"]["evidence_refs"]

    plan = data["market_strategy_plan"]
    assert plan["goal_mode"] == RecommendationGoalMode.MAXIMIZE_ENTRY_LEVEL_ACCESS.value
    assert plan["source_recommendations"]
    assert plan["primary_region_targets"] or plan["watchlist_items"]
    assert plan["timing_guidance"]
    assert plan["manual_verification_checklist"]["items"]
    assert "ai_summary" not in data


def test_strategy_endpoint_rejects_unknown_goal_mode(api_client) -> None:
    response = api_client.post(
        "/recommendations/strategy",
        json={"goal_mode": "maximize_ghost_markets"},
    )

    assert response.status_code == 422


def test_strategy_endpoint_rejects_free_form_ai_prompt(api_client) -> None:
    response = api_client.post(
        "/recommendations/strategy",
        json={
            "goal_mode": RecommendationGoalMode.MAXIMIZE_PRESTIGE.value,
            "prompt": "Tell me where to apply.",
        },
    )

    assert response.status_code == 422


def test_strategy_endpoint_validates_limits(api_client) -> None:
    response = api_client.post(
        "/recommendations/strategy",
        json={
            "goal_mode": RecommendationGoalMode.MAXIMIZE_PRESTIGE.value,
            "region_limit": 0,
        },
    )

    assert response.status_code == 422


def test_strategy_endpoint_handles_missing_company_data_without_invention(
    api_client,
    session,
) -> None:
    _seed_region(
        session,
        region_id="solo_region",
        display_name="Solo Region",
        objective=0.5,
        early_career=0.6,
        density=0.3,
    )

    response = api_client.post(
        "/recommendations/strategy",
        json={
            "goal_mode": RecommendationGoalMode.MAXIMIZE_ENTRY_LEVEL_ACCESS.value,
            "include_company_recommendations": True,
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["ranked_company_recommendations"] == []
    assert data["market_strategy_plan"]["company_targets"] == []
    assert data["market_strategy_plan"]["company_category_targets"] == []
    assert any("no company outputs" in warning for warning in data["warnings"])


def test_strategy_response_preserves_proxy_and_evidence_quality_fields(
    api_client,
    session,
) -> None:
    _seed_recommendation_world(session)

    response = api_client.post(
        "/recommendations/strategy",
        json={
            "goal_mode": (
                RecommendationGoalMode.MAXIMIZE_AI_CLOUD_CONCENTRATION.value
            ),
            "include_company_recommendations": True,
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    ranked = data["ranked_region_recommendations"]
    assert any(item["score_components_proxy"] for item in ranked)
    assert any(
        weakness["support"] == "inferred"
        for item in ranked
        for weakness in item["explanation"]["weaknesses"]
    )
    assert any(
        ref["basis"] in {"market_coverage", "confidence", "freshness"}
        for item in ranked
        for ref in item["explanation"]["evidence_refs"]
    )
    assert data["market_strategy_plan"]["evidence_warnings"]


def test_recommendation_api_routes_are_mounted(api_client, session) -> None:
    _seed_recommendation_world(session)

    goal_modes = api_client.get("/recommendations/goal-modes")
    strategy = api_client.post(
        "/recommendations/strategy",
        json={"goal_mode": RecommendationGoalMode.MAXIMIZE_PRESTIGE.value},
    )

    assert goal_modes.status_code == 200
    assert strategy.status_code == 200


def test_strategy_endpoint_does_not_persist_outputs(api_client, session) -> None:
    _seed_recommendation_world(session)

    api_client.post(
        "/recommendations/strategy",
        json={"goal_mode": RecommendationGoalMode.MAXIMIZE_LOWER_COMPETITION.value},
    )

    assert OutputMetadataRepository(session).list() == []
