"""Tier-based request and monthly usage limits for Layer 20 Platform API."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.platform.entitlements import PlatformApiTier, platform_api_tier_definition
from backend.platform.usage import (
    count_allowed_platform_api_usage_since,
    count_monthly_platform_api_usage,
    next_monthly_usage_window_start,
)


class PlatformApiRateLimitDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed: bool
    limit: int = Field(ge=1)
    remaining: int = Field(ge=0)
    reset_at: datetime
    window_seconds: int = Field(ge=1)
    reason: str


class PlatformApiMonthlyUsageDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed: bool
    limit: int = Field(ge=1)
    used: int = Field(ge=0)
    remaining: int = Field(ge=0)
    reset_at: datetime
    reason: str


def check_platform_api_rate_limit(
    session: Session,
    *,
    platform_api_key_id: str,
    tier: PlatformApiTier | str,
    now: datetime | None = None,
) -> PlatformApiRateLimitDecision:
    effective_now = now or datetime.now(UTC)
    tier_definition = platform_api_tier_definition(tier)
    window = timedelta(seconds=tier_definition.rate_limit_window_seconds)
    used = count_allowed_platform_api_usage_since(
        session,
        platform_api_key_id=platform_api_key_id,
        since=effective_now - window,
    )
    allowed = used < tier_definition.rate_limit_count
    remaining = max(
        tier_definition.rate_limit_count - used - (1 if allowed else 0),
        0,
    )
    return PlatformApiRateLimitDecision(
        allowed=allowed,
        limit=tier_definition.rate_limit_count,
        remaining=remaining,
        reset_at=effective_now + window,
        window_seconds=tier_definition.rate_limit_window_seconds,
        reason="request allowed" if allowed else "rate limit exhausted",
    )


def check_platform_api_monthly_usage_limit(
    session: Session,
    *,
    platform_api_key_id: str,
    tier: PlatformApiTier | str,
    now: datetime | None = None,
) -> PlatformApiMonthlyUsageDecision:
    effective_now = now or datetime.now(UTC)
    tier_definition = platform_api_tier_definition(tier)
    used = count_monthly_platform_api_usage(
        session,
        platform_api_key_id=platform_api_key_id,
        now=effective_now,
    )
    allowed = used < tier_definition.monthly_request_unit_limit
    remaining = max(
        tier_definition.monthly_request_unit_limit - used - (1 if allowed else 0),
        0,
    )
    return PlatformApiMonthlyUsageDecision(
        allowed=allowed,
        limit=tier_definition.monthly_request_unit_limit,
        used=used,
        remaining=remaining,
        reset_at=next_monthly_usage_window_start(effective_now),
        reason="request allowed" if allowed else "monthly usage limit exhausted",
    )
