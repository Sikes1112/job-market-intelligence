"""Developer documentation registry for the Layer 20 Platform API."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from backend.platform.entitlements import PLATFORM_API_TIER_DEFINITIONS
from backend.platform.product_catalog import PLATFORM_API_PRODUCTS, PlatformApiProductId
from backend.platform.versioning import platform_api_version_document


class PlatformDeveloperDocCategory(StrEnum):
    OVERVIEW = "overview"
    AUTHENTICATION = "authentication"
    GOVERNANCE = "governance"
    RESPONSE_CONTRACT = "response_contract"
    PRODUCT = "product"


class PlatformDeveloperDocEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_id: str = Field(min_length=1, max_length=96)
    slug: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=160)
    category: PlatformDeveloperDocCategory
    summary: str = Field(min_length=1, max_length=512)
    bullets: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    product_id: PlatformApiProductId | None = None
    route: str | None = Field(default=None, max_length=255)
    related_doc_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=16)


class PlatformDeveloperDocsRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    docs: tuple[PlatformDeveloperDocEntry, ...]
    product_ids: tuple[PlatformApiProductId, ...]
    versions: dict


def _tier_scope_bullet(definition) -> str:
    product_ids = ", ".join(
        product.value
        for product in sorted(
            definition.allowed_product_ids,
            key=lambda item: item.value,
        )
    )
    return f"{definition.label}: {product_ids}"


_COMMON_CONTRACT_DOCS: tuple[PlatformDeveloperDocEntry, ...] = (
    PlatformDeveloperDocEntry(
        doc_id="overview",
        slug="overview",
        title="Platform API overview",
        category=PlatformDeveloperDocCategory.OVERVIEW,
        summary=(
            "The Platform API exposes controlled, public-safe market intelligence "
            "outputs through versioned read-only endpoints."
        ),
        bullets=(
            "All data endpoints are under /api/v1/platform.",
            "Responses use the Layer 20 envelope with data, meta, and error fields.",
            "The API never exposes raw scrape records, scoring formulas, source ids, "
            "billing records, or private user data.",
        ),
        related_doc_ids=("authentication", "response-envelope", "versioning"),
    ),
    PlatformDeveloperDocEntry(
        doc_id="authentication",
        slug="authentication",
        title="Authentication with X-API-Key",
        category=PlatformDeveloperDocCategory.AUTHENTICATION,
        summary="Secured Platform API data endpoints require an API key in the X-API-Key header.",
        bullets=(
            "Use X-API-Key, not bearer auth, for Platform API access.",
            "Raw keys are shown only once at creation and are never stored.",
            "Docs/spec export routes are public metadata and do not return market data.",
        ),
        related_doc_ids=("api-key-safety", "tiers-scopes", "error-codes"),
    ),
    PlatformDeveloperDocEntry(
        doc_id="api-key-safety",
        slug="api-key-safety",
        title="API key safety",
        category=PlatformDeveloperDocCategory.AUTHENTICATION,
        summary="Keys are persisted as hashes with prefix/display metadata only.",
        bullets=(
            "Do not place keys in browser code or public embeds.",
            "Rotate keys if a raw key is exposed.",
            "Revoked keys return a safe Platform API error envelope.",
        ),
        related_doc_ids=("authentication", "error-codes"),
    ),
    PlatformDeveloperDocEntry(
        doc_id="tiers-scopes",
        slug="tiers-and-product-scopes",
        title="Tiers and product scopes",
        category=PlatformDeveloperDocCategory.AUTHENTICATION,
        summary="Access requires both a backend-owned tier entitlement and a stored product scope.",
        bullets=tuple(
            _tier_scope_bullet(definition)
            for definition in PLATFORM_API_TIER_DEFINITIONS.values()
        ),
        related_doc_ids=("rate-limits", "monthly-usage-limits"),
    ),
    PlatformDeveloperDocEntry(
        doc_id="rate-limits",
        slug="rate-limits",
        title="Rate limits",
        category=PlatformDeveloperDocCategory.AUTHENTICATION,
        summary="Each tier has a deterministic request window for Layer 20 data endpoints.",
        bullets=tuple(
            f"{definition.label}: {definition.rate_limit_count} request(s) per "
            f"{definition.rate_limit_window_seconds} seconds"
            for definition in PLATFORM_API_TIER_DEFINITIONS.values()
        ),
        related_doc_ids=("error-codes", "monthly-usage-limits"),
    ),
    PlatformDeveloperDocEntry(
        doc_id="monthly-usage-limits",
        slug="monthly-usage-limits",
        title="Monthly usage limits",
        category=PlatformDeveloperDocCategory.AUTHENTICATION,
        summary="Monthly usage is counted from successful allowed request units.",
        bullets=tuple(
            f"{definition.label}: {definition.monthly_request_unit_limit} "
            "request unit(s) per calendar month"
            for definition in PLATFORM_API_TIER_DEFINITIONS.values()
        ),
        related_doc_ids=("rate-limits", "usage-analytics"),
    ),
    PlatformDeveloperDocEntry(
        doc_id="error-codes",
        slug="errors",
        title="Error codes",
        category=PlatformDeveloperDocCategory.RESPONSE_CONTRACT,
        summary="Denied and invalid requests return a safe Platform API error envelope.",
        bullets=(
            "400 UNSUPPORTED_QUERY for unsupported query parameters.",
            "400 VALIDATION_ERROR for malformed required query input.",
            "401 MISSING_API_KEY, INVALID_API_KEY, or REVOKED_API_KEY.",
            "403 MISSING_PRODUCT_SCOPE or ENTITLEMENT_DENIED.",
            "429 RATE_LIMIT_EXCEEDED.",
            "402 USAGE_LIMIT_EXCEEDED for monthly usage exhaustion.",
        ),
        related_doc_ids=("authentication", "response-envelope"),
    ),
    PlatformDeveloperDocEntry(
        doc_id="response-envelope",
        slug="response-envelope",
        title="Response envelope",
        category=PlatformDeveloperDocCategory.RESPONSE_CONTRACT,
        summary="Every Platform API response uses status, data, meta, and error fields.",
        bullets=(
            "meta.api_version is v1.",
            "meta.schema_version is the current Layer 20 schema version.",
            "meta.product_id identifies the endpoint product.",
            "error is present only when status is error.",
        ),
        related_doc_ids=("freshness", "confidence", "source-summary", "warnings"),
    ),
    PlatformDeveloperDocEntry(
        doc_id="freshness",
        slug="freshness",
        title="Freshness metadata",
        category=PlatformDeveloperDocCategory.RESPONSE_CONTRACT,
        summary="Freshness metadata describes recency posture without exposing ingestion metadata.",
        bullets=(
            "status can be fresh, stale, partial, or unknown.",
            "freshness_expires_at and last_updated_at are public-safe timestamps when available.",
            "Unknown freshness means callers should independently verify time-sensitive decisions.",
        ),
        related_doc_ids=("confidence", "source-summary"),
    ),
    PlatformDeveloperDocEntry(
        doc_id="confidence",
        slug="confidence",
        title="Confidence metadata",
        category=PlatformDeveloperDocCategory.RESPONSE_CONTRACT,
        summary=(
            "Confidence metadata gives qualitative interpretation of public-safe "
            "output quality."
        ),
        bullets=(
            "Confidence does not expose scoring formulas or weights.",
            "Basis values explain whether confidence comes from coverage, output "
            "state, aggregate counts, or mixed signals.",
            "Low or unknown confidence should be displayed to end users.",
        ),
        related_doc_ids=("freshness", "warnings"),
    ),
    PlatformDeveloperDocEntry(
        doc_id="source-summary",
        slug="source-summary",
        title="Source summary",
        category=PlatformDeveloperDocCategory.RESPONSE_CONTRACT,
        summary="Source summaries provide public-safe counts, categories, and notes only.",
        bullets=(
            "Source identifiers, source refs, source bundles, and raw records are not exposed.",
            "source_count is directional and scoped to the returned payload.",
            "source_categories describe evidence classes rather than provider secrets.",
        ),
        related_doc_ids=("freshness", "warnings"),
    ),
    PlatformDeveloperDocEntry(
        doc_id="warnings",
        slug="warnings",
        title="Warnings",
        category=PlatformDeveloperDocCategory.RESPONSE_CONTRACT,
        summary="Warnings document limitations in a machine-readable, public-safe way.",
        bullets=(
            "Warnings include code, severity, and message.",
            "Warning text must not include internal notes or raw source references.",
            "Callers should render warning messages near the relevant output.",
        ),
        related_doc_ids=("response-envelope", "error-codes"),
    ),
    PlatformDeveloperDocEntry(
        doc_id="versioning",
        slug="versioning-and-deprecation",
        title="Versioning and deprecation",
        category=PlatformDeveloperDocCategory.GOVERNANCE,
        summary="Layer 20 uses versioned paths and an explicit schema version.",
        bullets=(
            "Current supported API version is v1.",
            "Breaking changes require a new versioned API path.",
            "Deprecated versions receive at least 180 days notice before removal.",
        ),
        related_doc_ids=("overview", "response-envelope"),
    ),
)


def platform_developer_docs_registry() -> PlatformDeveloperDocsRegistry:
    product_docs = tuple(
        PlatformDeveloperDocEntry(
            doc_id=product.product_id.value,
            slug=product.product_id.value.replace("_", "-"),
            title=product.label,
            category=PlatformDeveloperDocCategory.PRODUCT,
            summary=f"Read-only Platform API product for {product.label.lower()}.",
            bullets=(
                f"Product id: {product.product_id.value}.",
                f"Route: GET {product.route_family}.",
                "Requires X-API-Key plus tier entitlement and product scope.",
                "Returns the public Layer 20 envelope with freshness, confidence, "
                "source summary, and warnings.",
            ),
            product_id=product.product_id,
            route=product.route_family,
            related_doc_ids=("authentication", "response-envelope"),
        )
        for product in PLATFORM_API_PRODUCTS
    )
    return PlatformDeveloperDocsRegistry(
        docs=(*_COMMON_CONTRACT_DOCS, *product_docs),
        product_ids=tuple(product.product_id for product in PLATFORM_API_PRODUCTS),
        versions=platform_api_version_document(),
    )


def get_platform_developer_doc(doc_id: str) -> PlatformDeveloperDocEntry | None:
    for entry in platform_developer_docs_registry().docs:
        if entry.doc_id == doc_id or entry.slug == doc_id:
            return entry
    return None
