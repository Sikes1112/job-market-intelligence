"""Backend-owned entitlement policy for Layer 20 Platform API products."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.platform.product_catalog import PlatformApiProductId


class PlatformApiTier(StrEnum):
    TRIAL = "trial"
    STARTER = "starter"
    GROWTH = "growth"
    ENTERPRISE = "enterprise"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class PlatformApiEntitlementReason(StrEnum):
    ALLOWED = "allowed"
    UNKNOWN_TIER = "unknown_tier"
    UNSUPPORTED_PRODUCT = "unsupported_product"
    TIER_NOT_ENTITLED = "tier_not_entitled"
    MISSING_PRODUCT_SCOPE = "missing_product_scope"


@dataclass(frozen=True, slots=True)
class PlatformApiTierDefinition:
    tier: PlatformApiTier
    label: str
    allowed_product_ids: frozenset[PlatformApiProductId]
    rate_limit_count: int
    rate_limit_window_seconds: int
    monthly_request_unit_limit: int


@dataclass(frozen=True, slots=True)
class PlatformApiEntitlementDecision:
    allowed: bool
    reason: PlatformApiEntitlementReason
    message: str
    product_id: PlatformApiProductId | None
    tier: PlatformApiTier | None


PLATFORM_API_TIER_DEFINITIONS: dict[PlatformApiTier, PlatformApiTierDefinition] = {
    PlatformApiTier.TRIAL: PlatformApiTierDefinition(
        tier=PlatformApiTier.TRIAL,
        label="Trial",
        allowed_product_ids=frozenset({PlatformApiProductId.REGION_SCORES}),
        rate_limit_count=10,
        rate_limit_window_seconds=60,
        monthly_request_unit_limit=1,
    ),
    PlatformApiTier.STARTER: PlatformApiTierDefinition(
        tier=PlatformApiTier.STARTER,
        label="Starter",
        allowed_product_ids=frozenset(
            {
                PlatformApiProductId.REGION_SCORES,
                PlatformApiProductId.COMPANY_GEOGRAPHY,
                PlatformApiProductId.EARLY_CAREER_ACCESS,
            }
        ),
        rate_limit_count=2,
        rate_limit_window_seconds=60,
        monthly_request_unit_limit=25,
    ),
    PlatformApiTier.GROWTH: PlatformApiTierDefinition(
        tier=PlatformApiTier.GROWTH,
        label="Growth",
        allowed_product_ids=frozenset(
            {
                PlatformApiProductId.REGION_SCORES,
                PlatformApiProductId.COMPANY_GEOGRAPHY,
                PlatformApiProductId.EARLY_CAREER_ACCESS,
                PlatformApiProductId.HIRING_CONCENTRATION,
            }
        ),
        rate_limit_count=100,
        rate_limit_window_seconds=60,
        monthly_request_unit_limit=1_000,
    ),
    PlatformApiTier.ENTERPRISE: PlatformApiTierDefinition(
        tier=PlatformApiTier.ENTERPRISE,
        label="Enterprise",
        allowed_product_ids=frozenset(PlatformApiProductId),
        rate_limit_count=1_000,
        rate_limit_window_seconds=60,
        monthly_request_unit_limit=100_000,
    ),
}


def platform_api_tier_definition(
    tier: PlatformApiTier | str,
) -> PlatformApiTierDefinition:
    normalized = PlatformApiTier(tier)
    return PLATFORM_API_TIER_DEFINITIONS[normalized]


def decide_platform_api_entitlement(
    *,
    tier: PlatformApiTier | str,
    product_id: PlatformApiProductId | str,
    product_scopes: frozenset[PlatformApiProductId | str] | set[str] | list[str],
) -> PlatformApiEntitlementDecision:
    normalized_product = _normalize_product(product_id)
    if normalized_product is None:
        return PlatformApiEntitlementDecision(
            allowed=False,
            reason=PlatformApiEntitlementReason.UNSUPPORTED_PRODUCT,
            message="Unsupported Platform API product.",
            product_id=None,
            tier=None,
        )

    try:
        normalized_tier = PlatformApiTier(tier)
        tier_definition = PLATFORM_API_TIER_DEFINITIONS[normalized_tier]
    except (KeyError, ValueError):
        return PlatformApiEntitlementDecision(
            allowed=False,
            reason=PlatformApiEntitlementReason.UNKNOWN_TIER,
            message="Unknown Platform API tier.",
            product_id=normalized_product,
            tier=None,
        )

    if normalized_product not in tier_definition.allowed_product_ids:
        return PlatformApiEntitlementDecision(
            allowed=False,
            reason=PlatformApiEntitlementReason.TIER_NOT_ENTITLED,
            message="The API key tier is not entitled to this product.",
            product_id=normalized_product,
            tier=normalized_tier,
        )

    normalized_scopes = _normalize_scopes(product_scopes)
    if normalized_product not in normalized_scopes:
        return PlatformApiEntitlementDecision(
            allowed=False,
            reason=PlatformApiEntitlementReason.MISSING_PRODUCT_SCOPE,
            message="The API key is missing the required product scope.",
            product_id=normalized_product,
            tier=normalized_tier,
        )

    return PlatformApiEntitlementDecision(
        allowed=True,
        reason=PlatformApiEntitlementReason.ALLOWED,
        message="Request allowed.",
        product_id=normalized_product,
        tier=normalized_tier,
    )


def _normalize_product(
    product_id: PlatformApiProductId | str,
) -> PlatformApiProductId | None:
    try:
        return (
            product_id
            if isinstance(product_id, PlatformApiProductId)
            else PlatformApiProductId(product_id)
        )
    except ValueError:
        return None


def _normalize_scopes(
    product_scopes: frozenset[PlatformApiProductId | str] | set[str] | list[str],
) -> frozenset[PlatformApiProductId]:
    normalized: set[PlatformApiProductId] = set()
    for scope in product_scopes:
        product = _normalize_product(scope)
        if product is not None:
            normalized.add(product)
    return frozenset(normalized)
