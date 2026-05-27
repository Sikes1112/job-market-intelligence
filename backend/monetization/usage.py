"""Provider-agnostic usage counter helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from backend.monetization.features import MonetizationFeatureKey
from backend.monetization.plans import UsageLimit, UsageLimitUnit


class UsageResetPolicy(StrEnum):
    MONTHLY = "monthly"
    STATIC = "static"


class UsageCounterSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    usage_counter_id: str | None = Field(default=None, min_length=1, max_length=64)
    monetization_account_id: str | None = Field(default=None, min_length=1, max_length=64)
    feature_key: MonetizationFeatureKey
    period_start: datetime
    period_end: datetime
    used_count: int = Field(ge=0)
    limit_count: int = Field(ge=0)
    reset_policy: UsageResetPolicy
    last_incremented_at: datetime | None = None


class UsagePeriod(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    period_start: datetime
    period_end: datetime
    reset_policy: UsageResetPolicy


def usage_period_for_limit(
    usage_limit: UsageLimit,
    *,
    now: datetime | None = None,
) -> UsagePeriod:
    now = _coerce_aware(now or datetime.now(UTC))
    if usage_limit.unit is UsageLimitUnit.PER_MONTH:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return UsagePeriod(
            period_start=start,
            period_end=end,
            reset_policy=UsageResetPolicy.MONTHLY,
        )

    return UsagePeriod(
        period_start=datetime(1970, 1, 1, tzinfo=UTC),
        period_end=datetime(9999, 12, 31, tzinfo=UTC),
        reset_policy=UsageResetPolicy.STATIC,
    )


def remaining_usage(usage: UsageCounterSnapshot) -> int:
    return max(usage.limit_count - usage.used_count, 0)


def _coerce_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value

