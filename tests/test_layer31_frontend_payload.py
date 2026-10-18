from __future__ import annotations

from datetime import date
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.geography.models import Region
from backend.imports.nyc import import_nyc_dataset, run_nyc_post_import
from backend.scoring.models import RegionMarketScore

AS_OF = date(2026, 7, 9)


def test_nyc_region_payload_exposes_public_import_display_state(
    api_client: TestClient,
    session: Session,
) -> None:
    import_nyc_dataset(session, as_of=AS_OF)
    run_nyc_post_import(session, as_of=AS_OF)

    response = api_client.get("/regions/greater_nyc")

    assert response.status_code == 200
    payload = response.json()["data"]
    metadata = payload["import_metadata"]
    assert metadata["data_basis"] == "seeded_demo"
    assert metadata["imported_data_label"] == "Demonstration data"
    assert metadata["source_label"] == "Synthetic fixture-backed"
    assert metadata["coverage_label"] == "Demonstration coverage"
    assert metadata["freshness_label"] == "Freshness: demonstration snapshot"
    assert metadata["trust_label"] == "Demonstration only"
    assert metadata["risk_label"] == "Low risk"
    assert metadata["ranking_label"] == "Demo ranking only"

    entry_summary = payload["entry_level_summary"]
    assert entry_summary["internship_count_total"] is None
    assert entry_summary["internship_count_total_status"] == "unknown"
    assert entry_summary["coop_count_total"] is None
    assert entry_summary["coop_count_total_status"] == "not_collected"

    hiring = {
        row["company_id"]: row for row in payload["top_companies_hiring"]
    }
    assert hiring["cmp_brooklyn_cloudworks"]["active_posting_count_now"] == 0
    assert (
        hiring["cmp_brooklyn_cloudworks"]["active_posting_count_now_status"]
        == "zero_observed"
    )
    assert hiring["cmp_liberty_cyber_systems"]["active_posting_count_now"] is None
    assert (
        hiring["cmp_liberty_cyber_systems"]["active_posting_count_now_status"]
        == "unknown"
    )
    assert hiring["cmp_hudson_applied_ai"]["active_posting_count_now"] == 9
    assert (
        hiring["cmp_hudson_applied_ai"]["active_posting_count_now_status"]
        == "positive_observed"
    )
    assert hiring["cmp_hudson_applied_ai"]["import_metadata"]["source_label"] == (
        "Synthetic fixture-backed"
    )
    _assert_public_payload_safe(payload)


def test_company_payload_preserves_unknown_and_observed_zero_for_display(
    api_client: TestClient,
    session: Session,
) -> None:
    import_nyc_dataset(session, as_of=AS_OF)
    run_nyc_post_import(session, as_of=AS_OF)

    response = api_client.get("/companies/cmp_brooklyn_cloudworks")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["import_metadata"]["imported_data_label"] == "Demonstration data"
    assert payload["import_metadata"]["ranking_label"] == "Demo ranking only"

    hiring = payload["regions_hiring"][0]
    assert hiring["active_posting_count_now"] == 0
    assert hiring["active_posting_count_now_status"] == "zero_observed"
    assert hiring["import_metadata"]["trust_label"] == "Demonstration only"

    entry = payload["entry_level_regions"][0]
    assert entry["internship_count"] == 0
    assert entry["internship_count_status"] == "zero_observed"
    assert entry["coop_count"] is None
    assert entry["coop_count_status"] == "not_collected"
    assert entry["entry_level_full_time_count"] == 1
    assert entry["entry_level_full_time_count_status"] == "positive_observed"
    _assert_public_payload_safe(payload)


def test_comparison_payload_marks_nyc_side_as_demonstration_data(
    api_client: TestClient,
    session: Session,
) -> None:
    import_nyc_dataset(session, as_of=AS_OF)
    _seed_peer_region_score(session)
    run_nyc_post_import(
        session,
        as_of=AS_OF,
        comparison_region_ids=("greater_boston",),
    )

    response = api_client.get(
        "/compare",
        params={"region_a": "greater_nyc", "region_b": "greater_boston"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    sides = {
        payload["region_a"]["region_id"]: payload["region_a"],
        payload["region_b"]["region_id"]: payload["region_b"],
    }
    nyc_metadata = sides["greater_nyc"]["import_metadata"]
    assert nyc_metadata["imported_data_label"] == "Demonstration data"
    assert nyc_metadata["source_label"] == "Synthetic fixture-backed"
    assert nyc_metadata["freshness_label"] == "Freshness: demonstration snapshot"
    assert nyc_metadata["ranking_label"] == "Demo ranking only"
    assert sides["greater_boston"]["import_metadata"]["source_label"] == (
        "Source evidence unknown"
    )
    _assert_public_payload_safe(payload)


def _seed_peer_region_score(session: Session) -> None:
    session.add(
        Region(
            region_id="greater_boston",
            region_name="Greater Boston",
            display_name="Greater Boston",
            region_type="greater_region",
        )
    )
    session.add(
        RegionMarketScore(
            region_score_id="rms_greater_boston",
            region_id="greater_boston",
            structural_ecosystem_score=0.2,
            live_market_score=0.2,
            objective_opportunity_score=0.2,
            raw_total_score=0.2,
            general_density_score=0.2,
            tech_market_density_score=0.2,
            early_career_accessibility_score=0.2,
            score_ruleset_version="peer_fixture",
            source_version_bundle={"fixture": "peer"},
        )
    )
    session.flush()


def _assert_public_payload_safe(value: Any) -> None:
    forbidden = {
        "internal_notes",
        "reporter_user_id",
        "reporter_session_id",
        "report_reason",
        "related_user_report_id",
        "assigned_owner",
        "exception_case_id",
        "risk_routing_decision_id",
        "trust_assessment_id",
        "raw_internal_risk",
    }
    assert forbidden.isdisjoint(_keys(value))


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
