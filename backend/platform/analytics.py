"""Usage and audit analytics helpers for Layer 20 Platform API access."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.platform.entitlements import PlatformApiTier, platform_api_tier_definition
from backend.platform.models import PlatformApiAuditLog, PlatformApiKey, PlatformApiUsageEvent
from backend.platform.product_catalog import PlatformApiProductId
from backend.platform.usage import count_monthly_platform_api_usage


class PlatformApiProductUsageSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    product_id: PlatformApiProductId
    allowed_request_count: int = Field(ge=0)
    allowed_request_units: int = Field(ge=0)
    denied_request_count: int = Field(ge=0)


class PlatformApiKeyUsageSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    platform_api_key_id: str | None = None
    key_prefix: str | None = None
    tier: PlatformApiTier | None = None
    allowed_request_count: int = Field(ge=0)
    allowed_request_units: int = Field(ge=0)
    denied_request_count: int = Field(ge=0)
    monthly_limit: int | None = Field(default=None, ge=1)
    monthly_used: int | None = Field(default=None, ge=0)
    monthly_remaining: int | None = Field(default=None, ge=0)


class PlatformApiUsageAnalyticsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    generated_at: datetime
    usage_by_product: tuple[PlatformApiProductUsageSummary, ...]
    usage_by_key: tuple[PlatformApiKeyUsageSummary, ...]
    denied_request_counts: dict[str, int]
    rate_limit_denial_count: int = Field(ge=0)
    monthly_usage_denial_count: int = Field(ge=0)
    total_allowed_request_units: int = Field(ge=0)


def summarize_platform_api_usage(
    session: Session,
    *,
    platform_api_key_id: str | None = None,
    now: datetime | None = None,
) -> PlatformApiUsageAnalyticsSummary:
    effective_now = now or datetime.now(UTC)
    usage_rows = list(
        session.execute(_usage_select(platform_api_key_id)).scalars()
    )
    audit_rows = list(
        session.execute(_audit_select(platform_api_key_id)).scalars()
    )
    keys = {
        key.platform_api_key_id: key
        for key in session.execute(select(PlatformApiKey)).scalars()
    }

    product_allowed_counts: Counter[str] = Counter()
    product_allowed_units: Counter[str] = Counter()
    product_denied_counts: Counter[str] = Counter()
    key_allowed_counts: Counter[str | None] = Counter()
    key_allowed_units: Counter[str | None] = Counter()
    key_denied_counts: Counter[str | None] = Counter()
    key_prefixes: dict[str | None, str | None] = {}

    for row in usage_rows:
        key_id = row.platform_api_key_id
        key_prefixes.setdefault(key_id, row.key_prefix)
        if row.outcome == "allowed":
            product_allowed_counts[row.product_id] += 1
            product_allowed_units[row.product_id] += row.request_units
            key_allowed_counts[key_id] += 1
            key_allowed_units[key_id] += row.request_units
        else:
            product_denied_counts[row.product_id] += 1
            key_denied_counts[key_id] += 1

    denied_counts: Counter[str] = Counter(
        row.event_type for row in audit_rows if row.decision == "denied"
    )
    products = sorted(
        set(product_allowed_counts) | set(product_allowed_units) | set(product_denied_counts)
    )
    usage_by_product = tuple(
        PlatformApiProductUsageSummary(
            product_id=PlatformApiProductId(product_id),
            allowed_request_count=product_allowed_counts[product_id],
            allowed_request_units=product_allowed_units[product_id],
            denied_request_count=product_denied_counts[product_id],
        )
        for product_id in products
    )

    key_ids = sorted(
        set(key_allowed_counts) | set(key_allowed_units) | set(key_denied_counts),
        key=lambda value: value or "",
    )
    usage_by_key = tuple(
        _key_summary(
            session=session,
            key_id=key_id,
            key=keys.get(key_id or ""),
            key_prefix=key_prefixes.get(key_id),
            allowed_request_count=key_allowed_counts[key_id],
            allowed_request_units=key_allowed_units[key_id],
            denied_request_count=key_denied_counts[key_id],
            now=effective_now,
        )
        for key_id in key_ids
    )

    return PlatformApiUsageAnalyticsSummary(
        generated_at=effective_now,
        usage_by_product=usage_by_product,
        usage_by_key=usage_by_key,
        denied_request_counts=dict(sorted(denied_counts.items())),
        rate_limit_denial_count=denied_counts.get("rate_limited", 0),
        monthly_usage_denial_count=denied_counts.get("usage_limit_exceeded", 0),
        total_allowed_request_units=sum(product_allowed_units.values()),
    )


def _usage_select(platform_api_key_id: str | None):
    statement = select(PlatformApiUsageEvent).order_by(
        PlatformApiUsageEvent.occurred_at,
        PlatformApiUsageEvent.platform_api_usage_event_id,
    )
    if platform_api_key_id is not None:
        statement = statement.where(
            PlatformApiUsageEvent.platform_api_key_id == platform_api_key_id
        )
    return statement


def _audit_select(platform_api_key_id: str | None):
    statement = select(PlatformApiAuditLog).order_by(
        PlatformApiAuditLog.occurred_at,
        PlatformApiAuditLog.platform_api_audit_log_id,
    )
    if platform_api_key_id is not None:
        statement = statement.where(
            PlatformApiAuditLog.platform_api_key_id == platform_api_key_id
        )
    return statement


def _key_summary(
    *,
    session: Session,
    key_id: str | None,
    key: PlatformApiKey | None,
    key_prefix: str | None,
    allowed_request_count: int,
    allowed_request_units: int,
    denied_request_count: int,
    now: datetime,
) -> PlatformApiKeyUsageSummary:
    if key is None:
        return PlatformApiKeyUsageSummary(
            platform_api_key_id=key_id,
            key_prefix=key_prefix,
            tier=None,
            allowed_request_count=allowed_request_count,
            allowed_request_units=allowed_request_units,
            denied_request_count=denied_request_count,
        )

    tier = PlatformApiTier(key.tier)
    definition = platform_api_tier_definition(tier)
    monthly_used = count_monthly_platform_api_usage(
        session,
        platform_api_key_id=key.platform_api_key_id,
        now=now,
    )
    return PlatformApiKeyUsageSummary(
        platform_api_key_id=key.platform_api_key_id,
        key_prefix=key.key_prefix,
        tier=tier,
        allowed_request_count=allowed_request_count,
        allowed_request_units=allowed_request_units,
        denied_request_count=denied_request_count,
        monthly_limit=definition.monthly_request_unit_limit,
        monthly_used=monthly_used,
        monthly_remaining=max(definition.monthly_request_unit_limit - monthly_used, 0),
    )
