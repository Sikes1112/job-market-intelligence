"""Reproducible API-level release gate for the controlled-beta workflow."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.imports.bulk import (
    import_all_curated_market_datasets,
    run_all_curated_market_post_imports,
)
from tests.test_api_user_routes import _auth_headers


def test_empty_user_can_complete_beta_flow_and_restore_state(
    api_client: TestClient,
    session: Session,
) -> None:
    imported = import_all_curated_market_datasets(session, as_of=date(2026, 10, 9))
    assert imported.ok
    refreshed = run_all_curated_market_post_imports(session, as_of=date(2026, 10, 9))
    assert refreshed.ok
    headers = _auth_headers("auth0|layer44a_acceptance")

    signed_in = api_client.get("/me", headers=headers)
    assert signed_in.status_code == 200

    empty_profile = api_client.get("/me/career-identity", headers=headers)
    assert empty_profile.status_code == 200
    assert not any(empty_profile.json()["data"]["facts"].values())
    version = empty_profile.json()["data"]["current_version"]

    consent = api_client.put(
        "/me/career-identity/privacy",
        headers=headers,
        json={
            "downstream_personalization_consent_granted": True,
            "expected_version": version,
        },
    )
    assert consent.status_code == 200
    version = consent.json()["data"]["current_version"]
    role = api_client.post(
        "/me/career-identity/facts",
        headers=headers,
        json={
            "fact_type": "role_preference",
            "payload": {
                "role_title": "Software Engineer",
                "seniority": "entry_level",
                "employment_type": "full_time",
                "preference_kind": "preferred",
            },
            "state": "explicit",
            "expected_version": version,
        },
    )
    assert role.status_code == 201

    explored = api_client.post(
        "/me/explore/markets",
        headers=headers,
        json={"session_overrides": {}},
    )
    assert explored.status_code == 200
    explore_data = explored.json()["data"]
    assert explore_data["context"]["personalization_state"] == "personalized"
    assert explore_data["ranking_universe"]["market_count"] == 8
    market_refs = [
        item["region"]["public_slug"] or item["region"]["region_id"]
        for item in explore_data["markets"][:4]
    ]

    compared = api_client.post(
        "/me/explore/compare",
        headers=headers,
        json={"market_refs": market_refs, "session_overrides": {}},
    )
    assert compared.status_code == 200
    comparison = compared.json()["data"]
    assert len(comparison["compared_markets"]) == 4

    saved = api_client.post(
        "/me/explore/comparisons",
        headers=headers,
        json={
            "market_refs": market_refs,
            "session_overrides": {},
            "comparison_identity": comparison["comparison_identity"],
        },
    )
    assert saved.status_code == 201
    comparison_id = saved.json()["data"]["comparison"]["comparison_id"]

    prioritized = api_client.post(
        "/me/explore/prioritize",
        headers=headers,
        json={
            "comparison_id": comparison_id,
            "selected_market_ref": market_refs[0],
        },
    )
    assert prioritized.status_code == 200
    prioritization = prioritized.json()["data"]["prioritization"]
    decision_id = prioritization["decision_id"]

    workspace = api_client.get("/me/search-workspace", headers=headers)
    assert workspace.status_code == 200
    assert any(
        item["decision_id"] == decision_id for item in workspace.json()["data"]["active_pursuits"]
    )

    plan = api_client.post(
        f"/me/decisions/{decision_id}/plan",
        headers=headers,
        json={},
    )
    assert plan.status_code == 201
    action_id = plan.json()["data"]["action_plan"]["actions"][0]["action_id"]
    completed = api_client.patch(
        f"/me/actions/{action_id}",
        headers=headers,
        json={"status": "completed"},
    )
    assert completed.status_code == 200

    application = api_client.post(
        "/me/applications",
        headers=headers,
        json={
            "decision_id": decision_id,
            "role_title": "Beta acceptance role",
            "status": "applied",
            "notes": "Designated test-account acceptance record.",
        },
    )
    assert application.status_code == 201
    application_id = application.json()["data"]["application"]["application_id"]
    interviewing = api_client.patch(
        f"/me/applications/{application_id}/transition",
        headers=headers,
        json={"to_status": "interview"},
    )
    assert interviewing.status_code == 200
    assert interviewing.json()["data"]["application"]["status"] == "interview"

    # A fresh stateless browser client restores server-side Profile, comparison,
    # pursuit, action, and application state using only the same identity.
    with TestClient(api_client.app) as returning_client:
        restored_profile = returning_client.get("/me/career-identity", headers=headers)
        restored_comparisons = returning_client.get("/me/explore/comparisons", headers=headers)
        restored_workspace = returning_client.get("/me/search-workspace", headers=headers)

    assert restored_profile.status_code == 200
    assert (
        restored_profile.json()["data"]["privacy"]["downstream_personalization_consent_granted"]
        is True
    )
    assert restored_comparisons.status_code == 200
    assert restored_comparisons.json()["data"]["comparisons"][0]["comparison_id"] == (comparison_id)
    restored = restored_workspace.json()["data"]
    assert any(item["decision_id"] == decision_id for item in restored["active_pursuits"])
    assert any(item["application_id"] == application_id for item in restored["applications"])
    assert any(item["kind"] == "action_completed" for item in restored["history"])
