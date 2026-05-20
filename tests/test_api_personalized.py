"""POST /discover/personalized endpoint tests."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.outputs.repository import OutputMetadataRepository
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore


def _seed_basic_world(session: Session) -> None:
    session.add_all(
        [
            Region(
                region_id="greater_boston",
                region_name="greater_boston",
                display_name="Greater Boston",
                region_type="greater_region",
            ),
            Company(
                company_id="comp_a",
                company_name="Example",
                normalized_company_name="example",
                eligibility_status="eligible",
                sector_primary="ai",
                is_major_tech=True,
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            CompanyRegionPresence(
                presence_id="p_a",
                company_id="comp_a",
                region_id="greater_boston",
                presence_status="present",
                presence_basis="office_plus_hiring",
                office_evidence_flag=True,
                hiring_evidence_flag=True,
            ),
            CompanyRegionHiring(
                hiring_id="h_a",
                company_id="comp_a",
                region_id="greater_boston",
                currently_hiring_flag=True,
                role_family_summary={"product": 5, "ai_cloud_adjacent": 5},
            ),
            RegionMarketScore(
                region_score_id="rms_b",
                region_id="greater_boston",
                objective_opportunity_score=0.74,
                score_ruleset_version="marketscore_v1",
            ),
        ]
    )
    session.flush()


def test_discover_endpoint_returns_envelope(api_client, session) -> None:
    _seed_basic_world(session)
    response = api_client.post(
        "/discover/personalized",
        json={
            "region_ids": ["greater_boston"],
            "role_targets": ["product"],
            "industry_preferences": ["ai"],
            "prestige_preference": "high",
            "brand_preference": "medium",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    data = body["data"]
    assert "ranked_regions" in data
    assert "ranked_companies" in data
    assert data["ranked_regions"][0]["region_id"] == "greater_boston"
    assert data["ranked_regions"][0]["objective_opportunity_score"] == 0.74
    assert body["error"] is None


def test_discover_endpoint_warning_metadata_uses_standard_shape(
    api_client,
    session,
) -> None:
    session.add(
        Region(
            region_id="empty_region",
            region_name="empty_region",
            display_name="Empty Region",
            region_type="greater_region",
        )
    )
    session.flush()

    response = api_client.post(
        "/discover/personalized",
        json={"region_ids": ["empty_region"]},
    )

    assert response.status_code == 200
    warnings = response.json()["metadata"]["warnings"]
    assert warnings
    for warning in warnings:
        assert {"warning_code", "severity", "message"}.issubset(warning)
        assert isinstance(warning["warning_code"], str)
        assert warning["severity"] in {"low", "medium", "high", "critical"}
        assert isinstance(warning["message"], str)
        assert warning["message"]


def test_discover_endpoint_requires_region_ids(api_client) -> None:
    response = api_client.post(
        "/discover/personalized", json={"role_targets": ["product"]}
    )
    # Missing required field — Pydantic returns 422 via FastAPI.
    assert response.status_code == 422


def test_discover_endpoint_rejects_unknown_region(api_client, session) -> None:
    response = api_client.post(
        "/discover/personalized", json={"region_ids": ["ghost"]}
    )
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "NOT_FOUND"


def test_discover_endpoint_rejects_extra_fields(api_client) -> None:
    response = api_client.post(
        "/discover/personalized",
        json={"region_ids": ["greater_boston"], "rogue": True},
    )
    # extra=forbid → 422 from Pydantic.
    assert response.status_code == 422


def test_discover_endpoint_rejects_invalid_career_stage(api_client) -> None:
    response = api_client.post(
        "/discover/personalized",
        json={"region_ids": ["greater_boston"], "career_stage": "senior"},
    )
    assert response.status_code == 422


def test_discover_endpoint_does_not_persist_anything(api_client, session) -> None:
    _seed_basic_world(session)
    api_client.post(
        "/discover/personalized",
        json={
            "region_ids": ["greater_boston"],
            "role_targets": ["product"],
        },
    )
    # OutputMetadata stays empty — personalization never persists.
    assert OutputMetadataRepository(session).list() == []


def test_discover_endpoint_requires_no_login(api_client, session) -> None:
    """A bare request with no auth headers must succeed."""
    _seed_basic_world(session)
    response = api_client.post(
        "/discover/personalized",
        json={"region_ids": ["greater_boston"]},
    )
    assert response.status_code == 200


def test_discover_endpoint_is_deterministic_for_same_inputs(
    api_client, session
) -> None:
    _seed_basic_world(session)
    body = {
        "region_ids": ["greater_boston"],
        "role_targets": ["product"],
        "industry_preferences": ["ai"],
        "prestige_preference": "medium",
    }
    a = api_client.post("/discover/personalized", json=body).json()
    b = api_client.post("/discover/personalized", json=body).json()
    assert a["data"] == b["data"]


def test_discover_endpoint_does_not_mutate_canonical_truth(
    api_client, session
) -> None:
    _seed_basic_world(session)
    region = session.get(Region, "greater_boston")
    score = session.get(RegionMarketScore, "rms_b")
    region_version = region.version
    score_version = score.version
    score_value = score.objective_opportunity_score

    api_client.post(
        "/discover/personalized",
        json={"region_ids": ["greater_boston"], "role_targets": ["product"]},
    )

    session.refresh(region)
    session.refresh(score)
    assert region.version == region_version
    assert score.version == score_version
    assert score.objective_opportunity_score == score_value


def test_discover_endpoint_health_still_works(api_client) -> None:
    """Carry-over: /health still works after the personalization router is mounted."""
    response = api_client.get("/health")
    assert response.status_code == 200
