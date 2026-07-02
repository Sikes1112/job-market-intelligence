"""Audit logging for external Layer 20 Platform API access."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.platform.models import PlatformApiAuditLog, PlatformApiKey
from backend.platform.product_catalog import PlatformApiProductId


class PlatformApiAuditEventType(StrEnum):
    ALLOWED_REQUEST = "allowed_request"
    DENIED_REQUEST = "denied_request"
    RATE_LIMITED = "rate_limited"
    USAGE_LIMIT_EXCEEDED = "usage_limit_exceeded"
    MISSING_KEY = "missing_key"
    INVALID_KEY = "invalid_key"
    REVOKED_KEY = "revoked_key"
    ENTITLEMENT_DENIED = "entitlement_denied"


class PlatformApiAuditDecision(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"


class PlatformApiAuditLogPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    platform_api_audit_log_id: str
    platform_api_key_id: str | None = None
    key_prefix: str | None = None
    product_id: PlatformApiProductId | None = None
    endpoint: str = Field(min_length=1, max_length=255)
    method: str = Field(min_length=1, max_length=16)
    event_type: PlatformApiAuditEventType
    decision: PlatformApiAuditDecision
    status_code: int = Field(ge=100, le=599)
    metadata: dict[str, Any] | list[Any] | None = None
    occurred_at: datetime


def record_platform_api_audit_event(
    session: Session,
    *,
    api_key: PlatformApiKey | None,
    product_id: PlatformApiProductId | None,
    endpoint: str,
    method: str,
    event_type: PlatformApiAuditEventType,
    decision: PlatformApiAuditDecision,
    status_code: int,
    metadata: dict[str, Any] | list[Any] | None = None,
    occurred_at: datetime | None = None,
) -> PlatformApiAuditLogPayload:
    row = PlatformApiAuditLog(
        platform_api_audit_log_id=_new_audit_id(),
        platform_api_key_id=api_key.platform_api_key_id if api_key else None,
        key_prefix=api_key.key_prefix if api_key else None,
        product_id=product_id.value if product_id else None,
        endpoint=endpoint,
        method=method.upper(),
        event_type=event_type.value,
        decision=decision.value,
        status_code=status_code,
        event_metadata=metadata,
        occurred_at=occurred_at or datetime.now(UTC),
    )
    session.add(row)
    session.flush()
    return platform_api_audit_log_payload_from_row(row)


def platform_api_audit_log_payload_from_row(
    row: PlatformApiAuditLog,
) -> PlatformApiAuditLogPayload:
    return PlatformApiAuditLogPayload(
        platform_api_audit_log_id=row.platform_api_audit_log_id,
        platform_api_key_id=row.platform_api_key_id,
        key_prefix=row.key_prefix,
        product_id=PlatformApiProductId(row.product_id) if row.product_id else None,
        endpoint=row.endpoint,
        method=row.method,
        event_type=PlatformApiAuditEventType(row.event_type),
        decision=PlatformApiAuditDecision(row.decision),
        status_code=row.status_code,
        metadata=row.event_metadata,
        occurred_at=row.occurred_at,
    )


def _new_audit_id() -> str:
    return f"plataudit_{uuid4().hex}"
