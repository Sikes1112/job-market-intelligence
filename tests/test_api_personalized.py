"""POST /discover/personalized endpoint tests."""

from __future__ import annotations

import json

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


def _auth_headers(subject: str = "auth0|personalized_career_identity") -> dict[str, str]:
    claims = {
        "iss": "https://jmi.us.auth0.com/",
        "sub": subject,
        "email": "personalized@example.com",
        "email_verified": True,
        "name": "Personalized Career User",
    }
    return {"X-Verified-OIDC-Claims": json.dumps(claims)}


def _seed_career_identity_personalization_world(session: Session) -> None:
    session.add(
        Region(
            region_id="greater_boston",
            region_name="greater_boston",
            display_name="Greater Boston",
            region_type="greater_region",
        )
    )
    session.add_all(
        [
            Company(
                company_id="comp_ai",
                company_name="AI Product Co",
                normalized_company_name="ai product co",
                eligibility_status="eligible",
                sector_primary="ai",
                is_major_tech=False,
            ),
            Company(
                company_id="comp_finance",
                company_name="Finance Security Co",
                normalized_company_name="finance security co",
                eligibility_status="eligible",
                sector_primary="finance",
                is_major_tech=False,
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            CompanyRegionPresence(
                presence_id="p_ai",
                company_id="comp_ai",
                region_id="greater_boston",
                presence_status="present",
                presence_basis="office_plus_hiring",
                office_evidence_flag=True,
                hiring_evidence_flag=True,
            ),
            CompanyRegionPresence(
                presence_id="p_finance",
                company_id="comp_finance",
                region_id="greater_boston",
                presence_status="present",
                presence_basis="office_plus_hiring",
                office_evidence_flag=True,
                hiring_evidence_flag=True,
            ),
            CompanyRegionHiring(
                hiring_id="h_ai",
                company_id="comp_ai",
                region_id="greater_boston",
                currently_hiring_flag=True,
                role_family_summary={"product": 10, "cybersecurity": 1},
            ),
            CompanyRegionHiring(
                hiring_id="h_finance",
                company_id="comp_finance",
                region_id="greater_boston",
                currently_hiring_flag=True,
                role_family_summary={"product": 1, "cybersecurity": 10},
            ),
            RegionMarketScore(
                region_score_id="rms_ci",
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
    assert data["ranked_regions"][0]["coverage"]["heuristic"] is True
    assert data["ranked_regions"][0]["coverage"]["coverage_tier"] == (
        data["ranked_regions"][0]["coverage"]["tier"]
    )
    assert data["ranked_regions"][0]["coverage"]["coverage_limitations"]
    assert data["ranked_regions"][0]["coverage"]["tier"] in {
        "tier_2",
        "tier_3",
    }
    assert body["error"] is None


def test_career_identity_personalization_overlays_authenticated_recommendations(
    api_client,
    session,
) -> None:
    _seed_career_identity_personalization_world(session)
    headers = _auth_headers()
    base_request = {
        "region_ids": ["greater_boston"],
        "role_targets": ["cybersecurity"],
        "industry_preferences": ["finance"],
        "career_stage": "entry_level",
        "prestige_preference": "medium",
        "brand_preference": "medium",
        "limit": 10,
    }

    fallback = api_client.post(
        "/me/discover/personalized",
        headers=headers,
        json=base_request,
    )
    assert fallback.status_code == 200
    fallback_body = fallback.json()
    assert fallback_body["data"]["ranked_companies"][0]["company_id"] == "comp_finance"
    assert fallback_body["metadata"]["career_identity_personalization"] == {
        "source": "request",
        "career_identity_applied": False,
    }

    identity = api_client.get("/me/career-identity", headers=headers).json()["data"]
    consent = api_client.put(
        "/me/career-identity/privacy",
        headers=headers,
        json={
            "downstream_personalization_consent_granted": True,
            "expected_version": identity["current_version"],
        },
    )
    assert consent.status_code == 200
    identity = consent.json()["data"]
    role = api_client.post(
        "/me/career-identity/facts",
        headers=headers,
        json={
            "fact_type": "role_preference",
            "payload": {
                "function": "product",
                "role_title": "Product Manager",
                "preference_kind": "preferred",
            },
            "expected_version": identity["current_version"],
        },
    )
    assert role.status_code == 201
    identity = role.json()["data"]["identity"]
    industry = api_client.post(
        "/me/career-identity/facts",
        headers=headers,
        json={
            "fact_type": "industry_preference",
            "payload": {"industry": "ai", "preference_kind": "preferred"},
            "expected_version": identity["current_version"],
        },
    )
    assert industry.status_code == 201

    personalized = api_client.post(
        "/me/discover/personalized",
        headers=headers,
        json=base_request,
    )
    assert personalized.status_code == 200
    body = personalized.json()
    assert body["data"]["ranked_companies"][0]["company_id"] == "comp_ai"
    top = body["data"]["ranked_companies"][0]
    assert "role:product" in top["match_notes"]
    assert "industry_primary:ai" in top["match_notes"]
    metadata = body["metadata"]["career_identity_personalization"]
    assert metadata["source"] == "career_identity"
    assert metadata["career_identity_applied"] is True
    assert metadata["role_targets"][:1] == ["product"]
    assert metadata["industry_preferences"] == ["ai"]


def test_career_identity_personalization_respects_exclusions_and_consent(
    api_client,
    session,
) -> None:
    _seed_career_identity_personalization_world(session)
    headers = _auth_headers("auth0|personalized_career_identity_exclusions")
    identity = api_client.get("/me/career-identity", headers=headers).json()["data"]
    for payload in [
        {
            "fact_type": "industry_preference",
            "payload": {"industry": "finance", "preference_kind": "excluded"},
        },
        {
            "fact_type": "role_preference",
            "payload": {"function": "cybersecurity", "preference_kind": "excluded"},
        },
    ]:
        response = api_client.post(
            "/me/career-identity/facts",
            headers=headers,
            json=payload | {"expected_version": identity["current_version"]},
        )
        assert response.status_code == 201
        identity = response.json()["data"]["identity"]

    request = {
        "region_ids": ["greater_boston"],
        "role_targets": ["cybersecurity"],
        "industry_preferences": ["finance"],
        "career_stage": "entry_level",
        "prestige_preference": "medium",
        "brand_preference": "medium",
        "limit": 10,
    }
    no_consent = api_client.post(
        "/me/discover/personalized",
        headers=headers,
        json=request,
    )
    assert no_consent.status_code == 200
    assert no_consent.json()["data"]["ranked_companies"][0]["company_id"] == "comp_finance"
    assert (
        no_consent.json()["metadata"]["career_identity_personalization"]["reason"]
        == "downstream_personalization_consent_not_granted"
    )

    consent = api_client.put(
        "/me/career-identity/privacy",
        headers=headers,
        json={
            "downstream_personalization_consent_granted": True,
            "expected_version": identity["current_version"],
        },
    )
    assert consent.status_code == 200
    applied = api_client.post(
        "/me/discover/personalized",
        headers=headers,
        json=request,
    )
    assert applied.status_code == 200
    metadata = applied.json()["metadata"]["career_identity_personalization"]
    assert metadata["career_identity_applied"] is True
    assert metadata["role_targets"] == []
    assert metadata["industry_preferences"] == []
    assert metadata["excluded_roles"] == ["cybersecurity"]
    assert metadata["excluded_industries"] == ["finance"]


def test_authenticated_personalization_is_identity_sensitive_deterministic_and_isolated(
    api_client,
    session,
) -> None:
    _seed_career_identity_personalization_world(session)
    request = {
        "region_ids": ["greater_boston"],
        "role_targets": [],
        "industry_preferences": [],
        "career_stage": "entry_level",
        "prestige_preference": "medium",
        "brand_preference": "medium",
        "limit": 10,
    }

    def configure_identity(
        subject: str,
        *,
        role: str,
        industry: str,
    ) -> dict[str, str]:
        headers = _auth_headers(subject)
        identity = api_client.get(
            "/me/career-identity", headers=headers
        ).json()["data"]
        privacy = api_client.put(
            "/me/career-identity/privacy",
            headers=headers,
            json={
                "downstream_personalization_consent_granted": True,
                "expected_version": identity["current_version"],
            },
        )
        assert privacy.status_code == 200
        identity = privacy.json()["data"]
        role_response = api_client.post(
            "/me/career-identity/facts",
            headers=headers,
            json={
                "fact_type": "role_preference",
                "payload": {
                    "function": role,
                    "preference_kind": "preferred",
                },
                "expected_version": identity["current_version"],
            },
        )
        assert role_response.status_code == 201
        identity = role_response.json()["data"]["identity"]
        industry_response = api_client.post(
            "/me/career-identity/facts",
            headers=headers,
            json={
                "fact_type": "industry_preference",
                "payload": {
                    "industry": industry,
                    "preference_kind": "preferred",
                },
                "expected_version": identity["current_version"],
            },
        )
        assert industry_response.status_code == 201
        return headers

    product_headers = configure_identity(
        "auth0|identity_product_ai",
        role="product",
        industry="ai",
    )
    security_headers = configure_identity(
        "auth0|identity_security_finance",
        role="cybersecurity",
        industry="finance",
    )

    product_first = api_client.post(
        "/me/discover/personalized", headers=product_headers, json=request
    )
    product_repeat = api_client.post(
        "/me/discover/personalized", headers=product_headers, json=request
    )
    security = api_client.post(
        "/me/discover/personalized", headers=security_headers, json=request
    )
    assert product_first.status_code == product_repeat.status_code == 200
    assert security.status_code == 200
    assert product_first.json()["data"] == product_repeat.json()["data"]
    assert (
        product_first.json()["data"]["ranked_companies"][0]["company_id"]
        == "comp_ai"
    )
    assert security.json()["data"]["ranked_companies"][0]["company_id"] == (
        "comp_finance"
    )
    product_metadata = product_first.json()["metadata"][
        "career_identity_personalization"
    ]
    security_metadata = security.json()["metadata"][
        "career_identity_personalization"
    ]
    assert product_metadata["role_targets"] == ["product"]
    assert product_metadata["industry_preferences"] == ["ai"]
    assert security_metadata["role_targets"] == ["cybersecurity"]
    assert security_metadata["industry_preferences"] == ["finance"]
    assert "finance" not in product_metadata["industry_preferences"]
    assert "ai" not in security_metadata["industry_preferences"]

    empty_headers = _auth_headers("auth0|identity_empty")
    empty = api_client.post(
        "/me/discover/personalized", headers=empty_headers, json=request
    )
    assert empty.status_code == 200
    assert empty.json()["metadata"]["career_identity_personalization"] == {
        "source": "request",
        "career_identity_applied": False,
    }


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
    assert "coverage" in response.json()["data"]["ranked_regions"][0]
    assert response.json()["data"]["ranked_regions"][0]["coverage"]["tier"] == "tier_4"
    assert (
        response.json()["data"]["ranked_regions"][0]["coverage"]["coverage_tier"]
        == "tier_4"
    )
    assert any(
        warning["warning_code"] == "region_coverage_not_confident"
        for warning in warnings
    )
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
