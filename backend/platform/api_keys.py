"""API key lifecycle and validation for Layer 20 Platform API access."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.platform.entitlements import (
    PlatformApiTier,
    platform_api_tier_definition,
)
from backend.platform.models import PlatformApiKey
from backend.platform.product_catalog import PlatformApiProductId


class PlatformApiKeyStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class PlatformApiKeyEnvironment(StrEnum):
    TEST = "test"
    LIVE = "live"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class PlatformApiKeyValidationReason(StrEnum):
    VALID = "valid"
    MISSING_KEY = "missing_key"
    INVALID_KEY = "invalid_key"
    REVOKED_KEY = "revoked_key"


class PlatformApiKeyCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tier: PlatformApiTier = PlatformApiTier.TRIAL
    environment: PlatformApiKeyEnvironment = PlatformApiKeyEnvironment.TEST
    product_scopes: tuple[PlatformApiProductId, ...] | None = None
    label: str | None = Field(default=None, max_length=255)

    @field_validator("product_scopes")
    @classmethod
    def _unique_scopes(
        cls,
        value: tuple[PlatformApiProductId, ...] | None,
    ) -> tuple[PlatformApiProductId, ...] | None:
        if value is None:
            return None
        seen: set[PlatformApiProductId] = set()
        cleaned: list[PlatformApiProductId] = []
        for item in value:
            if item not in seen:
                cleaned.append(item)
                seen.add(item)
        return tuple(cleaned)

    @field_validator("label")
    @classmethod
    def _label_clean(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def _scopes_present(self) -> PlatformApiKeyCreateRequest:
        if self.product_scopes is not None and len(self.product_scopes) == 0:
            raise ValueError("Platform API keys require at least one product scope.")
        return self


class PlatformApiKeyDisplay(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    platform_api_key_id: str = Field(min_length=1, max_length=64)
    key_prefix: str = Field(min_length=1, max_length=24)
    display_key: str = Field(min_length=1, max_length=96)
    status: PlatformApiKeyStatus
    environment: PlatformApiKeyEnvironment
    tier: PlatformApiTier
    product_scopes: tuple[PlatformApiProductId, ...]
    label: str | None = None
    raw_key: str | None = None
    revealed_once: bool = False
    created_at: datetime
    updated_at: datetime
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None


class PlatformApiKeyCreateResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    api_key: PlatformApiKeyDisplay


@dataclass(frozen=True, slots=True)
class PlatformApiKeyValidationResult:
    valid: bool
    reason: PlatformApiKeyValidationReason
    status_code: int
    message: str
    api_key: PlatformApiKey | None = None


def create_platform_api_key(
    session: Session,
    request: PlatformApiKeyCreateRequest,
) -> PlatformApiKeyCreateResult:
    tier_definition = platform_api_tier_definition(request.tier)
    product_scopes = request.product_scopes or tuple(
        sorted(tier_definition.allowed_product_ids, key=lambda product: product.value)
    )
    raw_key = _generate_raw_key(request.environment)
    row = PlatformApiKey(
        platform_api_key_id=_new_platform_api_id("platkey"),
        key_prefix=_key_prefix(raw_key),
        key_hash=hash_platform_api_key(raw_key),
        display_key=_display_key(raw_key),
        label=request.label,
        status=PlatformApiKeyStatus.ACTIVE.value,
        environment=request.environment.value,
        tier=request.tier.value,
        product_scopes_json=[scope.value for scope in product_scopes],
    )
    session.add(row)
    session.flush()
    return PlatformApiKeyCreateResult(
        api_key=platform_api_key_display_from_row(row, reveal_raw_key=raw_key)
    )


def revoke_platform_api_key(
    session: Session,
    platform_api_key_id: str,
) -> PlatformApiKeyDisplay:
    row = session.get(PlatformApiKey, platform_api_key_id)
    if row is None:
        raise KeyError(platform_api_key_id)
    row.status = PlatformApiKeyStatus.REVOKED.value
    row.revoked_at = datetime.now(UTC)
    session.flush()
    return platform_api_key_display_from_row(row, reveal_raw_key=None)


def validate_platform_api_key(
    session: Session,
    raw_key: str | None,
) -> PlatformApiKeyValidationResult:
    if raw_key is None or not raw_key.strip():
        return PlatformApiKeyValidationResult(
            valid=False,
            reason=PlatformApiKeyValidationReason.MISSING_KEY,
            status_code=401,
            message="Platform API key required.",
        )

    key_hash = hash_platform_api_key(raw_key.strip())
    row = session.execute(
        select(PlatformApiKey).where(PlatformApiKey.key_hash == key_hash)
    ).scalar_one_or_none()
    if row is None:
        return PlatformApiKeyValidationResult(
            valid=False,
            reason=PlatformApiKeyValidationReason.INVALID_KEY,
            status_code=401,
            message="Invalid Platform API key.",
        )
    if row.status != PlatformApiKeyStatus.ACTIVE.value:
        return PlatformApiKeyValidationResult(
            valid=False,
            reason=PlatformApiKeyValidationReason.REVOKED_KEY,
            status_code=401,
            message="Revoked Platform API key.",
            api_key=row,
        )

    return PlatformApiKeyValidationResult(
        valid=True,
        reason=PlatformApiKeyValidationReason.VALID,
        status_code=200,
        message="Platform API key valid.",
        api_key=row,
    )


def mark_platform_api_key_used(
    session: Session,
    row: PlatformApiKey,
    *,
    used_at: datetime | None = None,
) -> None:
    row.last_used_at = used_at or datetime.now(UTC)
    session.flush()


def platform_api_key_display_from_row(
    row: PlatformApiKey,
    *,
    reveal_raw_key: str | None,
) -> PlatformApiKeyDisplay:
    return PlatformApiKeyDisplay(
        platform_api_key_id=row.platform_api_key_id,
        key_prefix=row.key_prefix,
        display_key=row.display_key,
        status=PlatformApiKeyStatus(row.status),
        environment=PlatformApiKeyEnvironment(row.environment),
        tier=PlatformApiTier(row.tier),
        product_scopes=tuple(
            PlatformApiProductId(scope) for scope in row.product_scopes_json
        ),
        label=row.label,
        raw_key=reveal_raw_key,
        revealed_once=reveal_raw_key is not None,
        created_at=row.created_at,
        updated_at=row.updated_at,
        last_used_at=row.last_used_at,
        revoked_at=row.revoked_at,
    )


def hash_platform_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _generate_raw_key(environment: PlatformApiKeyEnvironment) -> str:
    return f"jmi_platform_{environment.value}_{secrets.token_urlsafe(24)}"


def _key_prefix(raw_key: str) -> str:
    return raw_key[:20]


def _display_key(raw_key: str) -> str:
    return f"{raw_key[:20]}...{raw_key[-6:]}"


def _new_platform_api_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"
