from __future__ import annotations

from datetime import date
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.imports.bulk import (
    import_all_curated_market_datasets,
    rebuild_all_curated_market_outputs,
)
from backend.imports.post_import import run_curated_market_post_import
from backend.provenance.models import FactSourceLink

AS_OF = date(2026, 7, 9)
EXPECTED_MARKETS = {
    "nyc": ("greater_nyc", "Greater NYC"),
    "seattle": ("greater_seattle", "Greater Seattle"),
    "san_francisco_bay_area": ("sf_bay_area", "San Francisco Bay Area"),
    "boston": ("greater_boston", "Greater Boston"),
    "washington_dc": ("washington_dc", "Washington DC"),
    "austin": ("austin", "Austin"),
    "atlanta": ("atlanta", "Atlanta"),
    "chicago": ("chicago", "Chicago"),
}


def test_imported_markets_route_exposes_public_safe_multi_market_coverage(
    api_client: TestClient,
    session: Session,
) -> None:
    assert import_all_curated_market_datasets(session, as_of=AS_OF).ok
    assert rebuild_all_curated_market_outputs(session, as_of=AS_OF).ok
    _mark_stale_fact(session, "company_region_hiring", "hiring_cmp_microsoft_atlanta")
    assert run_curated_market_post_import(session, "atlanta", as_of=AS_OF).ok

    response = api_client.get("/markets/imported")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["market_count"] == 8
    by_market = {row["market_key"]: row for row in payload["markets"]}
    assert set(by_market) == set(EXPECTED_MARKETS)

    for market_key, (region_id, display_name) in EXPECTED_MARKETS.items():
        row = by_market[market_key]
        assert row["region_id"] == region_id
        assert row["display_name"] == display_name
        assert row["imported_data_label"] == "Demonstration data"
        assert row["source_label"] == "Synthetic fixture-backed"
        assert row["coverage_label"] == "Demonstration coverage"
        assert row["freshness_label"] in {
            "Demonstration snapshot",
            "Demonstration snapshot needs refresh",
        }
        assert row["trust_label"] == "Demonstration only"
        assert row["risk_label"] in {"Low risk", "Use with caution", "Not assessed"}
        assert row["ranking_label"] in {
            "Demo ranking only",
            "Some data ranking-excluded",
            "Ranking not assessed",
        }
        assert row["company_count"] == 3
        assert row["presence_fact_count"] == 3
        assert row["hiring_fact_count"] == 3
        assert row["entry_level_fact_count"] == 3
        assert row["source_count"] >= 3
        assert isinstance(row["comparison_available"], bool)

    assert sum(row["unknown_count_dimensions"] for row in payload["markets"]) > 0
    assert sum(row["observed_zero_count_dimensions"] for row in payload["markets"]) > 0
    assert len(
        {
            (row["unknown_count_dimensions"], row["observed_zero_count_dimensions"])
            for row in payload["markets"]
        }
    ) > 1
    assert any(
        row["ranking_excluded_fact_count"] > 0 for row in payload["markets"]
    )
    assert all(row["ranking_label"] == "Demo ranking only" for row in payload["markets"])
    _assert_public_payload_safe(payload)


def test_frontend_visible_comparison_payload_includes_multiple_imported_markets(
    api_client: TestClient,
    session: Session,
) -> None:
    assert import_all_curated_market_datasets(session, as_of=AS_OF).ok
    assert rebuild_all_curated_market_outputs(session, as_of=AS_OF).ok

    response = api_client.get(
        "/compare",
        params={"region_a": "greater_nyc", "region_b": "sf_bay_area"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    sides = {
        payload["region_a"]["region_id"]: payload["region_a"],
        payload["region_b"]["region_id"]: payload["region_b"],
    }
    assert set(sides) == {"greater_nyc", "sf_bay_area"}
    assert sides["greater_nyc"]["import_metadata"]["imported_data_label"] == (
        "Demonstration data"
    )
    assert sides["sf_bay_area"]["import_metadata"]["source_label"] == (
        "Synthetic fixture-backed"
    )
    assert payload["category_winners"]
    _assert_public_payload_safe(payload)


def _assert_public_payload_safe(value: Any) -> None:
    forbidden = {
        "assigned_owner",
        "exception_case_id",
        "fact_source_link_id",
        "internal_notes",
        "raw_internal_risk",
        "related_risk_routing_decision_id",
        "related_trust_assessment_id",
        "related_user_report_id",
        "report_reason",
        "reporter_session_id",
        "reporter_user_id",
        "risk_routing_decision_id",
        "source_ref_id",
        "trust_assessment_id",
        "user_report_id",
    }
    assert forbidden.isdisjoint(_keys(value))


def _mark_stale_fact(session: Session, fact_type: str, fact_id: str) -> None:
    link = session.execute(
        select(FactSourceLink)
        .where(FactSourceLink.fact_type == fact_type)
        .where(FactSourceLink.fact_id == fact_id)
    ).scalar_one()
    link.freshness_status = "stale"
    session.flush()


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
