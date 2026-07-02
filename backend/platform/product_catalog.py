"""Stable product identifiers for the public Platform API surface."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PlatformApiProductId(StrEnum):
    REGION_SCORES = "region_scores"
    COMPANY_GEOGRAPHY = "company_geography"
    EARLY_CAREER_ACCESS = "early_career_access"
    HIRING_CONCENTRATION = "hiring_concentration"
    MARKET_COMPARISONS = "market_comparisons"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


@dataclass(frozen=True, slots=True)
class PlatformApiProduct:
    product_id: PlatformApiProductId
    label: str
    route_family: str


PLATFORM_API_PRODUCTS: tuple[PlatformApiProduct, ...] = (
    PlatformApiProduct(
        product_id=PlatformApiProductId.REGION_SCORES,
        label="Region scores",
        route_family="/api/v1/platform/regions/{region_id}/scores",
    ),
    PlatformApiProduct(
        product_id=PlatformApiProductId.COMPANY_GEOGRAPHY,
        label="Company geography",
        route_family="/api/v1/platform/companies/{company_id}/geography",
    ),
    PlatformApiProduct(
        product_id=PlatformApiProductId.EARLY_CAREER_ACCESS,
        label="Early-career access",
        route_family="/api/v1/platform/regions/{region_id}/early-career-access",
    ),
    PlatformApiProduct(
        product_id=PlatformApiProductId.HIRING_CONCENTRATION,
        label="Hiring concentration",
        route_family="/api/v1/platform/markets/hiring-concentration",
    ),
    PlatformApiProduct(
        product_id=PlatformApiProductId.MARKET_COMPARISONS,
        label="Market comparisons",
        route_family="/api/v1/platform/markets/compare",
    ),
)


def product_by_id(product_id: PlatformApiProductId | str) -> PlatformApiProduct:
    normalized = (
        product_id
        if isinstance(product_id, PlatformApiProductId)
        else PlatformApiProductId(product_id)
    )
    for product in PLATFORM_API_PRODUCTS:
        if product.product_id is normalized:
            return product
    raise ValueError(f"Unsupported Platform API product id: {product_id!r}")
