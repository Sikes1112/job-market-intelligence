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
from backend.geography.models import Region
from backend.imports.bulk import (
    import_all_curated_market_datasets,
    run_all_curated_market_post_imports,
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
