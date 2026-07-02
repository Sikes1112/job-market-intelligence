from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.platform.analytics import summarize_platform_api_usage
from backend.platform.api_keys import PlatformApiKeyCreateRequest, create_platform_api_key
from backend.platform.audit_logs import (
    PlatformApiAuditDecision,
    PlatformApiAuditEventType,
    record_platform_api_audit_event,
)
from backend.platform.docs_exports import (
    build_platform_openapi_spec,
    build_platform_postman_collection,
)
from backend.platform.docs_registry import platform_developer_docs_registry
from backend.platform.embeds import (
    PlatformEmbedDenialReason,
    PlatformEmbedProductId,
    build_platform_embed_payload,
    clear_platform_embed_usage_events,
    decide_platform_embed_domain,
    decide_platform_embed_request,
    list_platform_embed_usage_events,
    platform_embed_usage_tracking_hook,
)
from backend.platform.entitlements import PlatformApiTier
from backend.platform.licensing import LicensedDatasetId, list_licensed_datasets
from backend.platform.models import PlatformApiKey
from backend.platform.product_catalog import PLATFORM_API_PRODUCTS, PlatformApiProductId
from backend.platform.usage import (
    PlatformApiUsageOutcome,
    record_platform_api_usage,
)
from backend.platform.versioning import (
    CURRENT_PLATFORM_API_SCHEMA_VERSION,
    CURRENT_PLATFORM_API_VERSION,
)


def test_developer_docs_registry_is_complete() -> None:
    registry = platform_developer_docs_registry()
    doc_ids = {entry.doc_id for entry in registry.docs}

    assert {
        "overview",
        "authentication",
        "api-key-safety",
        "tiers-scopes",
        "rate-limits",
        "monthly-usage-limits",
        "error-codes",
        "response-envelope",
        "freshness",
        "confidence",
        "source-summary",
        "warnings",
        "versioning",
    }.issubset(doc_ids)
    assert {entry.product_id for entry in registry.docs if entry.product_id} == {
        product.product_id for product in PLATFORM_API_PRODUCTS
    }
    assert registry.versions["current_api_version"] == CURRENT_PLATFORM_API_VERSION
    assert registry.versions["current_schema_version"] == CURRENT_PLATFORM_API_SCHEMA_VERSION


def test_openapi_export_matches_secured_platform_routes(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/platform/docs/openapi.json")
    assert response.status_code == 200
    spec = response.json()

    assert spec == build_platform_openapi_spec()
    assert spec["info"]["version"] == CURRENT_PLATFORM_API_VERSION
    assert spec["info"]["x-schema-version"] == CURRENT_PLATFORM_API_SCHEMA_VERSION
    security = spec["components"]["securitySchemes"]["PlatformApiKey"]
    assert security == {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
        "description": security["description"],
    }
    assert {path for path in spec["paths"]} == {
        product.route_family for product in PLATFORM_API_PRODUCTS
    }
    assert {
        spec["paths"][product.route_family]["get"]["x-platform-product-id"]
        for product in PLATFORM_API_PRODUCTS
    } == PlatformApiProductId.values()
    for path_item in spec["paths"].values():
        operation = path_item["get"]
        assert operation["security"] == [{"PlatformApiKey": []}]
        assert "400" in operation["responses"]
        assert "401" in operation["responses"]
        assert "403" in operation["responses"]
        assert "429" in operation["responses"]

    error_codes = set(
        spec["components"]["schemas"]["PlatformApiError"]["properties"]["code"]["enum"]
    )
    assert {
        "UNSUPPORTED_QUERY",
        "MISSING_API_KEY",
        "INVALID_API_KEY",
        "REVOKED_API_KEY",
        "MISSING_PRODUCT_SCOPE",
        "ENTITLEMENT_DENIED",
        "RATE_LIMIT_EXCEEDED",
    }.issubset(error_codes)


def test_postman_export_matches_secured_platform_routes(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/platform/docs/postman.json")
    assert response.status_code == 200
    collection = response.json()

    assert collection == build_platform_postman_collection()
    assert collection["info"]["version"] == CURRENT_PLATFORM_API_VERSION
    assert collection["auth"]["type"] == "apikey"
    assert any(item["value"] == "X-API-Key" for item in collection["auth"]["apikey"])
    raw_urls = [item["request"]["url"]["raw"] for item in collection["item"]]
    for product in PLATFORM_API_PRODUCTS:
        normalized = product.route_family.replace("{region_id}", "{{region_id}}").replace(
            "{company_id}",
            "{{company_id}}",
        )
        assert any(normalized in raw_url for raw_url in raw_urls)
    serialized = json.dumps(collection)
    assert "raw_key" not in serialized
    assert "source_id" not in serialized


def test_usage_analytics_summarizes_allowed_denied_and_limits(session: Session) -> None:
    created = create_platform_api_key(
        session,
        PlatformApiKeyCreateRequest(
            tier=PlatformApiTier.TRIAL,
            product_scopes=(PlatformApiProductId.REGION_SCORES,),
        ),
    )
    key = session.get(PlatformApiKey, created.api_key.platform_api_key_id)
    assert key is not None

    record_platform_api_usage(
        session,
        api_key=key,
        product_id=PlatformApiProductId.REGION_SCORES,
        endpoint="/api/v1/platform/regions/greater_boston/scores",
        method="GET",
        request_units=1,
        status_code=200,
        outcome=PlatformApiUsageOutcome.ALLOWED,
        decision_reason="allowed",
        occurred_at=datetime.now(UTC),
    )
    record_platform_api_usage(
        session,
        api_key=key,
        product_id=PlatformApiProductId.REGION_SCORES,
        endpoint="/api/v1/platform/regions/greater_boston/scores",
        method="GET",
        request_units=0,
        status_code=429,
        outcome=PlatformApiUsageOutcome.DENIED,
        decision_reason="rate_limit_exceeded",
        occurred_at=datetime.now(UTC),
    )
    record_platform_api_audit_event(
        session,
        api_key=key,
        product_id=PlatformApiProductId.REGION_SCORES,
        endpoint="/api/v1/platform/regions/greater_boston/scores",
        method="GET",
        event_type=PlatformApiAuditEventType.RATE_LIMITED,
        decision=PlatformApiAuditDecision.DENIED,
        status_code=429,
        metadata={"rate_limit": {"limit": 1}},
    )

    summary = summarize_platform_api_usage(session)

    assert summary.total_allowed_request_units == 1
    assert summary.usage_by_product[0].product_id == PlatformApiProductId.REGION_SCORES
    assert summary.usage_by_product[0].allowed_request_count == 1
    assert summary.usage_by_product[0].denied_request_count == 1
    assert summary.rate_limit_denial_count == 1
    assert summary.usage_by_key[0].monthly_limit == 1
    assert summary.usage_by_key[0].monthly_used == 1
    assert summary.usage_by_key[0].monthly_remaining == 0


def test_embed_policy_and_payloads_are_public_safe() -> None:
    allowed = decide_platform_embed_domain(
        embed_product_id=PlatformEmbedProductId.REGION_COMPARISON,
        origin="https://careers.example.edu/path",
    )
    blocked = decide_platform_embed_domain(
        embed_product_id=PlatformEmbedProductId.REGION_COMPARISON,
        origin="https://blocked.example",
    )
    unapproved = decide_platform_embed_domain(
        embed_product_id=PlatformEmbedProductId.MARKET_SCORE_CARD,
        origin="https://unknown.example",
    )

    assert allowed.allowed is True
    assert allowed.domain == "careers.example.edu"
    assert blocked.allowed is False
    assert blocked.reason is PlatformEmbedDenialReason.BLOCKED_DOMAIN
    assert unapproved.allowed is False
    assert unapproved.reason is PlatformEmbedDenialReason.UNAPPROVED_DOMAIN

    payload = build_platform_embed_payload(PlatformEmbedProductId.REGION_COMPARISON)
    assert payload.attribution
    assert payload.freshness["status"]
    assert payload.confidence["level"]
    assert payload.source_summary["source_categories"]
    assert payload.warnings

    hook = platform_embed_usage_tracking_hook(
        embed_product_id=PlatformEmbedProductId.REGION_COMPARISON,
        origin="example.edu",
        allowed=True,
    )
    assert hook["event_type"] == "platform_embed_view"
    serialized = payload.model_dump_json()
    assert "raw_job" not in serialized
    assert "source_id" not in serialized

    request_decision = decide_platform_embed_request(
        embed_product_id=PlatformEmbedProductId.MARKET_SCORE_CARD,
        origin_header=None,
        referer_header="https://unknown.example/post",
        declared_origin="https://careers.example.edu/frame",
    )
    assert request_decision.allowed is True
    assert request_decision.domain == "careers.example.edu"


def test_embed_routes_enforce_domain_policy_and_track_attempts(api_client: TestClient) -> None:
    clear_platform_embed_usage_events()

    allowed_region = api_client.get(
        "/api/v1/platform/embeds/region-comparison",
        params={"origin": "https://careers.example.edu/path"},
    )
    allowed_score = api_client.get(
        "/api/v1/platform/embeds/market-score-card",
        params={"origin": "https://partners.example.org/page"},
    )
    blocked_region = api_client.get(
        "/api/v1/platform/embeds/region-comparison",
        params={"origin": "https://blocked.example/frame"},
    )
    blocked_score = api_client.get(
        "/api/v1/platform/embeds/market-score-card",
        params={"origin": "https://scraper.example/frame"},
    )
    missing_domain = api_client.get("/api/v1/platform/embeds/region-comparison")

    assert allowed_region.status_code == 200
    assert allowed_region.json()["data"]["payload"]["title"] == "Regional market comparison"
    assert allowed_score.status_code == 200
    assert allowed_score.json()["data"]["payload"]["title"] == "Market score card"

    for response in (blocked_region, blocked_score, missing_domain):
        body = response.json()
        serialized = json.dumps(body)
        assert response.status_code == 403
        assert body["error"]["code"] == "EMBED_DOMAIN_NOT_ALLOWED"
        assert body["data"] is None
        assert "raw_job" not in serialized
        assert "raw_scrape" not in serialized
        assert "source_id" not in serialized
        assert "billing" not in serialized
        assert "ingestion" not in serialized

    events = list_platform_embed_usage_events()
    assert len(events) == 5
    assert [event["event_type"] for event in events].count("platform_embed_view") == 2
    assert [event["event_type"] for event in events].count("platform_embed_denied") == 3
    assert all("raw_key" not in json.dumps(event) for event in events)


def test_licensing_registry_includes_derived_source_safe_datasets() -> None:
    datasets = list_licensed_datasets()
    assert {entry.dataset_id for entry in datasets} == set(LicensedDatasetId)
    for entry in datasets:
        sample = " ".join(entry.sample_fields).casefold()
        excluded = " ".join(entry.excluded_fields).casefold()
        assert "raw_job" not in sample
        assert "raw_scrape" not in sample
        assert "source_id" not in sample
        assert "scoring_formula" not in sample
        assert "raw_job" in excluded
        assert "raw_scrape" in excluded
        assert "source_id" in excluded
        assert "ingestion" in excluded
        assert entry.attribution_rules
        assert entry.source_safety_notes
