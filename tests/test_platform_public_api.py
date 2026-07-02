from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.api.app import create_app
from backend.api.dependencies import get_session
from backend.companies.models import Company
from backend.config.settings import Settings
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.outputs.models import OutputMetadata
from backend.platform.api_keys import (
    PlatformApiKeyCreateRequest,
    PlatformApiKeyEnvironment,
    create_platform_api_key,
    platform_api_key_display_from_row,
    revoke_platform_api_key,
)
from backend.platform.entitlements import PlatformApiTier
from backend.platform.models import (
    PlatformApiAuditLog,
    PlatformApiKey,
    PlatformApiUsageEvent,
)
from backend.platform.product_catalog import PLATFORM_API_PRODUCTS, PlatformApiProductId
from backend.platform.public_api_payloads import (
    FORBIDDEN_PUBLIC_API_FIELD_NAMES,
    PublicApiConfidenceMetadata,
    PublicApiEnvelope,
    PublicApiFreshnessMetadata,
    PublicApiResponseMeta,
    PublicApiSourceSummary,
    PublicRegionMarketSummary,
    PublicRegionScoresPayload,
    PublicScoreSet,
)
from backend.presence.models import CompanyRegionPresence
from backend.scoring.models import RegionMarketScore
from backend.shared.confidence import Confidence


def _seed_region(session: Session, region_id: str, display_name: str) -> None:
    session.add(
        Region(
            region_id=region_id,
            region_name=region_id,
            display_name=display_name,
            region_type="greater_region",
        )
    )
    session.flush()


def _seed_company(session: Session) -> None:
    session.add(
        Company(
            company_id="comp_alpha",
            company_name="Alpha Systems",
            normalized_company_name="alpha systems internal normalized",
            sector_primary="software",
            sector_secondary="cloud",
            public_or_private="private",
            eligibility_status="eligible",
            eligibility_score=0.94,
            eligibility_override_flag=True,
            eligibility_override_reason="internal override note",
            classification_confidence="high_confidence",
            prestige_score=0.91,
        )
    )
    session.flush()


def _seed_region_data(
    session: Session,
    *,
    region_id: str,
    company_id: str = "comp_alpha",
    active: int,
    posting_30d: int,
    posting_90d: int,
    opportunity: float,
    early_career: float,
) -> None:
    future = datetime.now(UTC) + timedelta(days=30)
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
                source_refs={"fact_source_link_id": f"secret_link_{region_id}"},
            ),
            CompanyRegionHiring(
                hiring_id=f"hiring_{company_id}_{region_id}",
                company_id=company_id,
                region_id=region_id,
                currently_hiring_flag=True,
                active_posting_count_now=active,
                posting_count_30d=posting_30d,
                posting_count_90d=posting_90d,
                hiring_confidence="high",
                freshness_expires_at=future,
                source_refs={"source_id": f"secret_source_{region_id}"},
            ),
            CompanyRegionEntryLevel(
                entry_level_id=f"entry_{company_id}_{region_id}",
                company_id=company_id,
                region_id=region_id,
                internship_count=2,
                coop_count=1,
                entry_level_full_time_count=3,
                formal_early_career_program_flag=True,
                entry_level_access_score=early_career,
                entry_level_confidence="high",
                freshness_expires_at=future,
                source_refs={"observation_id": f"secret_obs_{region_id}"},
            ),
            RegionMarketScore(
                region_score_id=f"score_{region_id}",
                region_id=region_id,
                structural_ecosystem_score=0.72,
                live_market_score=0.68,
                objective_opportunity_score=opportunity,
                raw_total_score=0.99,
                general_density_score=0.70,
                tech_market_density_score=0.74,
                early_career_accessibility_score=early_career,
                score_ruleset_version="internal_ruleset_v1",
                source_version_bundle={"hidden": "source_version_secret"},
            ),
        ]
    )
    session.flush()


def _seed_platform_fixture(session: Session) -> None:
    _seed_region(session, "greater_boston", "Greater Boston")
    _seed_region(session, "greater_atlanta", "Greater Atlanta")
    _seed_company(session)
    _seed_region_data(
        session,
        region_id="greater_boston",
        active=12,
        posting_30d=18,
        posting_90d=42,
        opportunity=0.81,
        early_career=0.86,
    )
    _seed_region_data(
        session,
        region_id="greater_atlanta",
        active=5,
        posting_30d=9,
        posting_90d=20,
        opportunity=0.67,
        early_career=0.58,
    )


def _create_platform_key(
    session: Session,
    *,
    tier: PlatformApiTier = PlatformApiTier.ENTERPRISE,
    product_scopes: tuple[PlatformApiProductId, ...] | None = None,
    environment: PlatformApiKeyEnvironment = PlatformApiKeyEnvironment.TEST,
):
    result = create_platform_api_key(
        session,
        PlatformApiKeyCreateRequest(
            tier=tier,
            environment=environment,
            product_scopes=product_scopes,
            label="test platform key",
        ),
    )
    assert result.api_key.raw_key
    return result.api_key


def _key_headers(raw_key: str) -> dict[str, str]:
    return {"X-API-Key": raw_key}


def test_platform_product_catalog_defines_required_identifiers() -> None:
    assert {product.product_id for product in PLATFORM_API_PRODUCTS} == {
        PlatformApiProductId.REGION_SCORES,
        PlatformApiProductId.COMPANY_GEOGRAPHY,
        PlatformApiProductId.EARLY_CAREER_ACCESS,
        PlatformApiProductId.HIRING_CONCENTRATION,
        PlatformApiProductId.MARKET_COMPARISONS,
    }
    assert PlatformApiProductId.values() == {
        "region_scores",
        "company_geography",
        "early_career_access",
        "hiring_concentration",
        "market_comparisons",
    }


def test_platform_api_key_creation_hashes_and_reveals_raw_key_once(
    session: Session,
) -> None:
    key_payload = _create_platform_key(
        session,
        tier=PlatformApiTier.ENTERPRISE,
        product_scopes=(PlatformApiProductId.REGION_SCORES,),
    )

    assert key_payload.raw_key is not None
    assert key_payload.raw_key.startswith("jmi_platform_test_")
    assert key_payload.revealed_once is True
    assert "..." in key_payload.display_key

    row = session.get(PlatformApiKey, key_payload.platform_api_key_id)
    assert row is not None
    assert not hasattr(row, "raw_key")
    assert row.key_hash != key_payload.raw_key
    assert row.display_key == key_payload.display_key

    stored_display = platform_api_key_display_from_row(row, reveal_raw_key=None)
    assert stored_display.raw_key is None
    assert stored_display.revealed_once is False
    assert key_payload.raw_key not in json.dumps(stored_display.model_dump(mode="json"))


def test_public_api_payload_contract_rejects_internal_fields() -> None:
    valid = PublicRegionScoresPayload(
        region_id="greater_boston",
        region_name="Greater Boston",
        region_type="greater_region",
        scores=PublicScoreSet(opportunity=0.81),
        market_summary=PublicRegionMarketSummary(
            present_company_count=1,
            currently_hiring_company_count=1,
            early_career_signal_count=1,
        ),
        coverage_tier="tier_2",
        coverage_label="Tier 2 - partial but useful market",
    ).model_dump(mode="json")
    valid["raw_total_score"] = 0.99
    with pytest.raises(ValidationError):
        PublicRegionScoresPayload.model_validate(valid)

    with pytest.raises(ValidationError):
        PublicApiEnvelope(
            status="success",
            data={"score_ruleset_version": "internal_ruleset_v1"},
            meta=PublicApiResponseMeta(
                product_id=PlatformApiProductId.REGION_SCORES,
                freshness=PublicApiFreshnessMetadata(status="unknown"),
                confidence=PublicApiConfidenceMetadata(
                    level=Confidence.UNKNOWN,
                    label="Unknown",
                    basis="unknown",
                ),
                source_summary=PublicApiSourceSummary(),
            ),
        )


def test_region_scores_route_returns_versioned_public_contract(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_platform_fixture(session)
    key_payload = _create_platform_key(session)

    response = api_client.get(
        "/api/v1/platform/regions/greater_boston/scores",
        headers=_key_headers(key_payload.raw_key),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["meta"]["api_version"] == "v1"
    assert body["meta"]["schema_version"] == "2026-06-20a"
    assert body["meta"]["product_id"] == "region_scores"
    assert body["data"]["region_id"] == "greater_boston"
    assert body["data"]["scores"]["opportunity"] == 0.81
    assert body["data"]["scores"]["early_career_access"] == 0.86
    assert body["data"]["market_summary"]["present_company_count"] == 1
    _assert_required_meta(body)
    _assert_no_internal_leakage(body)


def test_company_geography_and_early_career_routes_are_public_safe(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_platform_fixture(session)
    key_payload = _create_platform_key(session)
    headers = _key_headers(key_payload.raw_key)

    geography = api_client.get(
        "/api/v1/platform/companies/comp_alpha/geography",
        headers=headers,
    ).json()
    early = api_client.get(
        "/api/v1/platform/regions/greater_boston/early-career-access",
        headers=headers,
    ).json()

    assert geography["meta"]["product_id"] == "company_geography"
    assert geography["data"]["company_id"] == "comp_alpha"
    assert geography["data"]["company_name"] == "Alpha Systems"
    assert geography["data"]["sector"] == "software"
    assert geography["data"]["region_count"] == 2
    assert {row["region_id"] for row in geography["data"]["regions"]} == {
        "greater_atlanta",
        "greater_boston",
    }
    assert all(row["has_early_career_access"] for row in geography["data"]["regions"])

    assert early["meta"]["product_id"] == "early_career_access"
    assert early["data"]["internship_count"] == 2
    assert early["data"]["coop_count"] == 1
    assert early["data"]["entry_level_full_time_count"] == 3
    assert early["data"]["formal_early_career_program_count"] == 1
    _assert_required_meta(geography)
    _assert_required_meta(early)
    _assert_no_internal_leakage(geography)
    _assert_no_internal_leakage(early)


def test_hiring_concentration_and_market_compare_routes(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_platform_fixture(session)
    key_payload = _create_platform_key(session)
    headers = _key_headers(key_payload.raw_key)

    concentration = api_client.get(
        "/api/v1/platform/markets/hiring-concentration",
        params={"limit": 1},
        headers=headers,
    )
    comparison = api_client.get(
        "/api/v1/platform/markets/compare",
        params={"region_a": "greater_boston", "region_b": "greater_atlanta"},
        headers=headers,
    )

    assert concentration.status_code == 200
    concentration_body = concentration.json()
    assert concentration_body["meta"]["product_id"] == "hiring_concentration"
    assert concentration_body["data"]["market_count"] == 1
    assert concentration_body["data"]["markets"][0]["region_id"] == "greater_boston"
    assert concentration_body["data"]["markets"][0]["active_posting_count"] == 12
    assert concentration_body["data"]["total_active_posting_count"] == 17

    assert comparison.status_code == 200
    comparison_body = comparison.json()
    assert comparison_body["meta"]["product_id"] == "market_comparisons"
    assert comparison_body["data"]["comparison_id"] == (
        "greater_atlanta__greater_boston"
    )
    keys = {row["key"] for row in comparison_body["data"]["score_comparisons"]}
    assert "opportunity" in keys
    assert "early_career_access" in keys
    assert "raw_total_score" not in keys
    _assert_required_meta(concentration_body)
    _assert_required_meta(comparison_body)
    _assert_no_internal_leakage(concentration_body)
    _assert_no_internal_leakage(comparison_body)


def test_public_platform_routes_reject_unsupported_queries_and_missing_objects(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_platform_fixture(session)
    key_payload = _create_platform_key(session)
    headers = _key_headers(key_payload.raw_key)

    unsupported = api_client.get(
        "/api/v1/platform/markets/hiring-concentration",
        params={"limit": 5, "include_raw": "true"},
        headers=headers,
    )
    missing = api_client.get(
        "/api/v1/platform/regions/ghost/scores",
        headers=headers,
    )
    invalid_compare = api_client.get(
        "/api/v1/platform/markets/compare",
        params={"region_a": "greater_boston", "region_b": "greater_boston"},
        headers=headers,
    )

    assert unsupported.status_code == 400
    assert unsupported.json()["error"]["code"] == "UNSUPPORTED_QUERY"
    assert unsupported.json()["meta"]["api_version"] == "v1"
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"
    assert invalid_compare.status_code == 400
    assert invalid_compare.json()["error"]["code"] == "VALIDATION_ERROR"
    assert session.query(PlatformApiAuditLog).filter_by(decision="denied").count() == 3


def test_public_platform_routes_require_api_key_and_do_not_create_output_metadata(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_platform_fixture(session)
    missing_key = api_client.get("/api/v1/platform/regions/greater_boston/scores")
    assert missing_key.status_code == 401
    assert missing_key.json()["error"]["code"] == "MISSING_API_KEY"

    key_payload = _create_platform_key(session)
    headers = _key_headers(key_payload.raw_key)

    assert (
        api_client.get(
            "/api/v1/platform/regions/greater_boston/scores",
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        api_client.get(
            "/api/v1/platform/companies/comp_alpha/geography",
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        api_client.get(
            "/api/v1/platform/regions/greater_boston/early-career-access",
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        api_client.get(
            "/api/v1/platform/markets/hiring-concentration",
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        api_client.get(
            "/api/v1/platform/markets/compare",
            params={"region_a": "greater_boston", "region_b": "greater_atlanta"},
            headers=headers,
        ).status_code
        == 200
    )
    assert session.query(OutputMetadata).count() == 0
    assert session.query(PlatformApiUsageEvent).filter_by(outcome="allowed").count() == 5
    assert session.query(PlatformApiAuditLog).filter_by(decision="allowed").count() == 5


def test_platform_api_rejects_missing_invalid_and_revoked_keys(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_platform_fixture(session)
    key_payload = _create_platform_key(
        session,
        product_scopes=(PlatformApiProductId.REGION_SCORES,),
    )

    missing = api_client.get("/api/v1/platform/regions/greater_boston/scores")
    invalid = api_client.get(
        "/api/v1/platform/regions/greater_boston/scores",
        headers=_key_headers("jmi_platform_test_invalid"),
    )
    revoke_platform_api_key(session, key_payload.platform_api_key_id)
    revoked = api_client.get(
        "/api/v1/platform/regions/greater_boston/scores",
        headers=_key_headers(key_payload.raw_key),
    )

    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "MISSING_API_KEY"
    assert invalid.status_code == 401
    assert invalid.json()["error"]["code"] == "INVALID_API_KEY"
    assert revoked.status_code == 401
    assert revoked.json()["error"]["code"] == "REVOKED_API_KEY"

    audit_types = {
        row.event_type for row in session.query(PlatformApiAuditLog).all()
    }
    assert {"missing_key", "invalid_key", "revoked_key"}.issubset(audit_types)
    serialized = json.dumps([response.json() for response in (missing, invalid, revoked)])
    assert key_payload.raw_key not in serialized
    assert not _find_forbidden_fields(missing.json())


def test_platform_api_rejects_wrong_tier_and_missing_product_scope(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_platform_fixture(session)
    wrong_tier_key = _create_platform_key(
        session,
        tier=PlatformApiTier.STARTER,
        product_scopes=(PlatformApiProductId.MARKET_COMPARISONS,),
    )
    missing_scope_key = _create_platform_key(
        session,
        tier=PlatformApiTier.ENTERPRISE,
        product_scopes=(PlatformApiProductId.REGION_SCORES,),
    )

    wrong_tier = api_client.get(
        "/api/v1/platform/markets/compare",
        params={"region_a": "greater_boston", "region_b": "greater_atlanta"},
        headers=_key_headers(wrong_tier_key.raw_key),
    )
    missing_scope = api_client.get(
        "/api/v1/platform/companies/comp_alpha/geography",
        headers=_key_headers(missing_scope_key.raw_key),
    )

    assert wrong_tier.status_code == 403
    assert wrong_tier.json()["error"]["code"] == "ENTITLEMENT_DENIED"
    assert missing_scope.status_code == 403
    assert missing_scope.json()["error"]["code"] == "MISSING_PRODUCT_SCOPE"

    audit_rows = session.query(PlatformApiAuditLog).all()
    assert [row.event_type for row in audit_rows].count("entitlement_denied") == 2
    assert {row.event_metadata["reason"] for row in audit_rows} == {
        "tier_not_entitled",
        "missing_product_scope",
    }


def test_platform_api_rate_and_monthly_limits_are_enforced(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_platform_fixture(session)
    rate_limited_key = _create_platform_key(
        session,
        tier=PlatformApiTier.STARTER,
        product_scopes=(PlatformApiProductId.REGION_SCORES,),
    )
    rate_headers = _key_headers(rate_limited_key.raw_key)

    first = api_client.get(
        "/api/v1/platform/regions/greater_boston/scores",
        headers=rate_headers,
    )
    second = api_client.get(
        "/api/v1/platform/regions/greater_boston/scores",
        headers=rate_headers,
    )
    exhausted = api_client.get(
        "/api/v1/platform/regions/greater_boston/scores",
        headers=rate_headers,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert exhausted.status_code == 429
    assert exhausted.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"

    monthly_limited_key = _create_platform_key(
        session,
        tier=PlatformApiTier.TRIAL,
        product_scopes=(PlatformApiProductId.REGION_SCORES,),
    )
    monthly_headers = _key_headers(monthly_limited_key.raw_key)
    allowed = api_client.get(
        "/api/v1/platform/regions/greater_boston/scores",
        headers=monthly_headers,
    )
    exceeded = api_client.get(
        "/api/v1/platform/regions/greater_boston/scores",
        headers=monthly_headers,
    )

    assert allowed.status_code == 200
    assert exceeded.status_code == 402
    assert exceeded.json()["error"]["code"] == "USAGE_LIMIT_EXCEEDED"

    usage_rows = session.query(PlatformApiUsageEvent).all()
    assert sum(row.request_units for row in usage_rows if row.outcome == "allowed") == 3
    assert any(row.decision_reason == "rate_limit_exceeded" for row in usage_rows)
    assert any(
        row.event_type == "usage_limit_exceeded"
        for row in session.query(PlatformApiAuditLog).all()
    )


def test_platform_api_enforcement_does_not_affect_non_platform_routes(
    api_client: TestClient,
    session: Session,
) -> None:
    _seed_platform_fixture(session)

    assert api_client.get("/health").status_code == 200
    assert api_client.get("/regions").status_code == 200
    assert api_client.get("/public/reports").status_code == 200
    assert api_client.get("/public/benchmarks").status_code == 200
    assert (
        api_client.get("/api/v1/platform/regions/greater_boston/scores").status_code
        == 401
    )


def test_public_demo_allows_only_read_platform_public_api(
    session: Session,
) -> None:
    _seed_platform_fixture(session)
    key_payload = _create_platform_key(session)
    headers = _key_headers(key_payload.raw_key)
    app = create_app(
        engine=session.bind,
        settings=Settings(
            app_env="public_demo",
            database_url="sqlite:///explicit-demo.db",
            cors_allowed_origins="https://demo.example",
            _env_file=None,
        ),
    )

    def _override_get_session() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    client = TestClient(app)

    missing_key = client.get("/api/v1/platform/regions/greater_boston/scores")
    assert missing_key.status_code == 401
    assert missing_key.json()["error"]["code"] == "MISSING_API_KEY"
    assert (
        client.get(
            "/api/v1/platform/regions/greater_boston/scores",
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/v1/platform/companies/comp_alpha/geography",
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/v1/platform/regions/greater_boston/early-career-access",
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/v1/platform/markets/hiring-concentration",
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/v1/platform/markets/compare",
            params={"region_a": "greater_boston", "region_b": "greater_atlanta"},
            headers=headers,
        ).status_code
        == 200
    )
    denied = client.post("/api/v1/platform/markets/hiring-concentration", json={})
    assert denied.status_code == 403
    assert denied.json()["error"]["type"] == "public_demo_read_only"


def _assert_required_meta(body: dict) -> None:
    assert body["meta"]["generated_at"]
    assert set(body["meta"]["freshness"]) == {
        "status",
        "freshness_expires_at",
        "last_updated_at",
    }
    assert set(body["meta"]["confidence"]) == {"level", "label", "basis"}
    assert set(body["meta"]["source_summary"]) == {
        "data_basis",
        "source_count",
        "source_categories",
        "notes",
    }
    assert isinstance(body["meta"]["warnings"], list)


def _assert_no_internal_leakage(body: dict) -> None:
    serialized = json.dumps(body)
    forbidden_strings = {
        "internal_ruleset_v1",
        "source_version_secret",
        "alpha systems internal normalized",
        "internal override note",
        "secret_link_",
        "secret_source_",
        "secret_obs_",
        "raw_total_score",
        "score_ruleset_version",
        "normalized_company_name",
        "classification_confidence",
        "prestige_score",
        "eligibility_override",
        "source_versions",
        "source_version_bundle",
        "source_refs",
        "billing",
        "ingestion",
        "uploaded_by_user_id",
    }
    leaked = {value for value in forbidden_strings if value in serialized}
    assert not leaked
    found = _find_forbidden_fields(body)
    assert not found


def _find_forbidden_fields(value: object, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if str(key).casefold() in FORBIDDEN_PUBLIC_API_FIELD_NAMES:
                found.append(child_path)
            found.extend(_find_forbidden_fields(child, child_path))
    elif isinstance(value, list | tuple):
        for index, child in enumerate(value):
            found.extend(_find_forbidden_fields(child, f"{path}[{index}]"))
    return found
