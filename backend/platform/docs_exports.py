"""OpenAPI and Postman export builders for the Layer 20 Platform API."""

from __future__ import annotations

from typing import Any

from backend.platform.docs_registry import platform_developer_docs_registry
from backend.platform.product_catalog import PLATFORM_API_PRODUCTS, PlatformApiProductId
from backend.platform.versioning import (
    CURRENT_PLATFORM_API_SCHEMA_VERSION,
    CURRENT_PLATFORM_API_VERSION,
)


def build_platform_openapi_spec() -> dict[str, Any]:
    registry = platform_developer_docs_registry()
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Job Market Intelligence Platform API",
            "version": CURRENT_PLATFORM_API_VERSION,
            "description": (
                "Versioned public-safe market intelligence API. Data endpoints "
                "require X-API-Key authentication and return Layer 20 envelopes."
            ),
            "x-schema-version": CURRENT_PLATFORM_API_SCHEMA_VERSION,
        },
        "jsonSchemaDialect": "https://json-schema.org/draft/2020-12/schema",
        "security": [{"PlatformApiKey": []}],
        "components": {
            "securitySchemes": {
                "PlatformApiKey": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key",
                    "description": "Layer 20 Platform API key returned once at creation.",
                }
            },
            "schemas": {
                "PlatformApiEnvelope": _envelope_schema(),
                "PlatformApiError": _error_schema(),
            },
        },
        "paths": {
            product.route_family: _path_item_for_product(product.product_id)
            for product in PLATFORM_API_PRODUCTS
        },
        "x-platform-docs": registry.model_dump(mode="json"),
    }


def build_platform_postman_collection() -> dict[str, Any]:
    return {
        "info": {
            "name": "Job Market Intelligence Platform API",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            "version": CURRENT_PLATFORM_API_VERSION,
            "description": (
                f"Layer 20 Platform API {CURRENT_PLATFORM_API_VERSION}, schema "
                f"{CURRENT_PLATFORM_API_SCHEMA_VERSION}."
            ),
        },
        "auth": {
            "type": "apikey",
            "apikey": [
                {"key": "key", "value": "X-API-Key", "type": "string"},
                {"key": "value", "value": "{{platform_api_key}}", "type": "string"},
                {"key": "in", "value": "header", "type": "string"},
            ],
        },
        "variable": [
            {"key": "base_url", "value": "https://api.example.com"},
            {"key": "platform_api_key", "value": "replace-with-platform-api-key"},
            {"key": "region_id", "value": "greater_boston"},
            {"key": "company_id", "value": "comp_alpha"},
            {"key": "region_a", "value": "greater_boston"},
            {"key": "region_b", "value": "greater_atlanta"},
        ],
        "item": [
            _postman_item_for_product(product.product_id, product.route_family)
            for product in PLATFORM_API_PRODUCTS
        ],
    }


def _path_item_for_product(product_id: PlatformApiProductId) -> dict[str, Any]:
    path_parameters = []
    query_parameters = []
    if product_id in {
        PlatformApiProductId.REGION_SCORES,
        PlatformApiProductId.EARLY_CAREER_ACCESS,
    }:
        path_parameters.append(_path_parameter("region_id"))
    elif product_id is PlatformApiProductId.COMPANY_GEOGRAPHY:
        path_parameters.append(_path_parameter("company_id"))
    elif product_id is PlatformApiProductId.HIRING_CONCENTRATION:
        query_parameters.append(
            {
                "name": "limit",
                "in": "query",
                "required": False,
                "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
                "description": "Maximum number of markets to return.",
            }
        )
    elif product_id is PlatformApiProductId.MARKET_COMPARISONS:
        query_parameters.extend(
            [
                _query_parameter("region_a", required=True),
                _query_parameter("region_b", required=True),
            ]
        )

    return {
        "get": {
            "summary": _summary_for_product(product_id),
            "operationId": f"get_{product_id.value}",
            "tags": ["Platform API"],
            "security": [{"PlatformApiKey": []}],
            "parameters": [*path_parameters, *query_parameters],
            "responses": {
                "200": {
                    "description": "Public-safe Platform API response.",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/PlatformApiEnvelope"}
                        }
                    },
                },
                "400": {
                    "description": "Unsupported query or validation error.",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/PlatformApiEnvelope"}
                        }
                    },
                },
                "401": {
                    "description": "Missing, invalid, or revoked X-API-Key.",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/PlatformApiEnvelope"}
                        }
                    },
                },
                "402": {
                    "description": "Monthly usage limit exceeded.",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/PlatformApiEnvelope"}
                        }
                    },
                },
                "403": {
                    "description": "Tier entitlement or product scope denied.",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/PlatformApiEnvelope"}
                        }
                    },
                },
                "404": {
                    "description": "Requested region or company was not found.",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/PlatformApiEnvelope"}
                        }
                    },
                },
                "429": {
                    "description": "Tier rate limit exceeded.",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/PlatformApiEnvelope"}
                        }
                    },
                },
            },
            "x-platform-product-id": product_id.value,
            "x-platform-api-version": CURRENT_PLATFORM_API_VERSION,
            "x-platform-schema-version": CURRENT_PLATFORM_API_SCHEMA_VERSION,
        }
    }


def _postman_item_for_product(
    product_id: PlatformApiProductId,
    route_family: str,
) -> dict[str, Any]:
    url_path = route_family.strip("/").split("/")
    raw_path = route_family
    if "{region_id}" in raw_path:
        raw_path = raw_path.replace("{region_id}", "{{region_id}}")
        url_path = [part.replace("{region_id}", "{{region_id}}") for part in url_path]
    if "{company_id}" in raw_path:
        raw_path = raw_path.replace("{company_id}", "{{company_id}}")
        url_path = [part.replace("{company_id}", "{{company_id}}") for part in url_path]

    query = []
    if product_id is PlatformApiProductId.HIRING_CONCENTRATION:
        query.append({"key": "limit", "value": "50"})
    elif product_id is PlatformApiProductId.MARKET_COMPARISONS:
        query.extend(
            [
                {"key": "region_a", "value": "{{region_a}}"},
                {"key": "region_b", "value": "{{region_b}}"},
            ]
        )

    return {
        "name": _summary_for_product(product_id),
        "request": {
            "method": "GET",
            "header": [{"key": "X-API-Key", "value": "{{platform_api_key}}"}],
            "auth": {"type": "apikey"},
            "url": {
                "raw": f"{{{{base_url}}}}{raw_path}"
                + (
                    "?"
                    + "&".join(f"{item['key']}={item['value']}" for item in query)
                    if query
                    else ""
                ),
                "host": ["{{base_url}}"],
                "path": url_path,
                **({"query": query} if query else {}),
            },
            "description": (
                f"Product id: {product_id.value}. Requires X-API-Key and returns "
                "a Layer 20 public-safe envelope."
            ),
        },
        "response": [],
    }


def _summary_for_product(product_id: PlatformApiProductId) -> str:
    return {
        PlatformApiProductId.REGION_SCORES: "Get region scores",
        PlatformApiProductId.COMPANY_GEOGRAPHY: "Get company geography",
        PlatformApiProductId.EARLY_CAREER_ACCESS: "Get early-career access",
        PlatformApiProductId.HIRING_CONCENTRATION: "Get hiring concentration",
        PlatformApiProductId.MARKET_COMPARISONS: "Compare markets",
    }[product_id]


def _path_parameter(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "in": "path",
        "required": True,
        "schema": {"type": "string", "minLength": 1},
    }


def _query_parameter(name: str, *, required: bool) -> dict[str, Any]:
    return {
        "name": name,
        "in": "query",
        "required": required,
        "schema": {"type": "string", "minLength": 1},
    }


def _envelope_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["status", "data", "meta", "error"],
        "properties": {
            "status": {"type": "string", "enum": ["success", "partial", "error"]},
            "data": {},
            "meta": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "api_version",
                    "schema_version",
                    "product_id",
                    "generated_at",
                    "freshness",
                    "confidence",
                    "source_summary",
                    "warnings",
                ],
                "properties": {
                    "api_version": {"type": "string", "const": CURRENT_PLATFORM_API_VERSION},
                    "schema_version": {
                        "type": "string",
                        "const": CURRENT_PLATFORM_API_SCHEMA_VERSION,
                    },
                    "product_id": {
                        "type": "string",
                        "enum": sorted(product.value for product in PlatformApiProductId),
                    },
                    "generated_at": {"type": "string", "format": "date-time"},
                    "freshness": {"type": "object"},
                    "confidence": {"type": "object"},
                    "source_summary": {"type": "object"},
                    "warnings": {"type": "array"},
                },
            },
            "error": {
                "anyOf": [
                    {"$ref": "#/components/schemas/PlatformApiError"},
                    {"type": "null"},
                ]
            },
        },
    }


def _error_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["code", "message"],
        "properties": {
            "code": {
                "type": "string",
                "enum": [
                    "UNSUPPORTED_QUERY",
                    "VALIDATION_ERROR",
                    "MISSING_API_KEY",
                    "INVALID_API_KEY",
                    "REVOKED_API_KEY",
                    "MISSING_PRODUCT_SCOPE",
                    "ENTITLEMENT_DENIED",
                    "USAGE_LIMIT_EXCEEDED",
                    "RATE_LIMIT_EXCEEDED",
                    "NOT_FOUND",
                ],
            },
            "message": {"type": "string"},
        },
    }
