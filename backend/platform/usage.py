"""Usage metering for Layer 20 Platform API access."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.platform.models import PlatformApiKey, PlatformApiUsageEvent
from backend.platform.product_catalog import PlatformApiProductId


class PlatformApiUsageOutcome(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"


class PlatformApiUsageEventPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    platform_api_usage_event_id: str
    platform_api_key_id: str | None = None
    key_prefix: str | None = None
    product_id: PlatformApiProductId
    endpoint: str = Field(min_length=1, max_length=255)
    method: str = Field(min_length=1, max_length=16)
    request_units: int = Field(ge=0)
    status_code: int = Field(ge=100, le=599)
    outcome: PlatformApiUsageOutcome
    decision_reason: str = Field(min_length=1, max_length=96)
    occurred_at: datetime


def record_platform_api_usage(
    session: Session,
    *,
    api_key: PlatformApiKey | None,
    product_id: PlatformApiProductId,
    endpoint: str,
    method: str,
    request_units: int,
    status_code: int,
    outcome: PlatformApiUsageOutcome,
    decision_reason: str,
    occurred_at: datetime | None = None,
) -> PlatformApiUsageEventPayload:
    event = PlatformApiUsageEvent(
        platform_api_usage_event_id=_new_usage_id(),
        platform_api_key_id=api_key.platform_api_key_id if api_key else None,
        key_prefix=api_key.key_prefix if api_key else None,
        product_id=product_id.value,
        endpoint=endpoint,
        method=method.upper(),
        request_units=request_units,
        status_code=status_code,
        outcome=outcome.value,
        decision_reason=decision_reason,
        occurred_at=occurred_at or datetime.now(UTC),
    )
    session.add(event)
    session.flush()
    return platform_api_usage_event_payload_from_row(event)


def count_allowed_platform_api_usage_since(
    session: Session,
    *,
    platform_api_key_id: str,
    since: datetime,
) -> int:
    value = session.execute(
        select(func.coalesce(func.sum(PlatformApiUsageEvent.request_units), 0)).where(
            PlatformApiUsageEvent.platform_api_key_id == platform_api_key_id,
            PlatformApiUsageEvent.outcome == PlatformApiUsageOutcome.ALLOWED.value,
            PlatformApiUsageEvent.occurred_at >= since,
        )
    ).scalar_one()
    return int(value or 0)


def count_monthly_platform_api_usage(
    session: Session,
    *,
    platform_api_key_id: str,
    now: datetime | None = None,
) -> int:
    effective_now = now or datetime.now(UTC)
    return count_allowed_platform_api_usage_since(
        session,
        platform_api_key_id=platform_api_key_id,
        since=monthly_usage_window_start(effective_now),
    )


def monthly_usage_window_start(now: datetime) -> datetime:
    aware_now = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    return aware_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def next_monthly_usage_window_start(now: datetime) -> datetime:
    start = monthly_usage_window_start(now)
    if start.month == 12:
        return start.replace(year=start.year + 1, month=1)
    return start.replace(month=start.month + 1)


def platform_api_usage_event_payload_from_row(
    row: PlatformApiUsageEvent,
) -> PlatformApiUsageEventPayload:
    return PlatformApiUsageEventPayload(
        platform_api_usage_event_id=row.platform_api_usage_event_id,
        platform_api_key_id=row.platform_api_key_id,
        key_prefix=row.key_prefix,
        product_id=PlatformApiProductId(row.product_id),
        endpoint=row.endpoint,
        method=row.method,
        request_units=row.request_units,
        status_code=row.status_code,
        outcome=PlatformApiUsageOutcome(row.outcome),
        decision_reason=row.decision_reason,
        occurred_at=row.occurred_at,
    )


def _new_usage_id() -> str:
    return f"platusage_{uuid4().hex}"
