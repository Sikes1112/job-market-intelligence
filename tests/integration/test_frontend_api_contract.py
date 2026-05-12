"""Minimal backend/frontend API contract tests.

These tests pin only the response fields the Vite frontend renders. They are
not browser tests and do not assert layout.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.api.app import create_app
from backend.api.dependencies import get_session
from backend.geography.models import Region
from seeds import mvp_seed
from seeds.mvp_data import REGION_BOSTON, REGION_SF


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
    assert {"region_id", "display_name"}.issubset(
        regions["data"]["regions"][0].keys()
    )

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
