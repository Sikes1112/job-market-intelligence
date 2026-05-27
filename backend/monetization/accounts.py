"""Provider-agnostic monetization account contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.monetization.plans import PlanKey


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class MonetizationAccountType(_Vocabulary):
    INDIVIDUAL = "individual"
    STUDENT = "student"
    INSTITUTIONAL = "institutional"
    PUBLIC_DEMO = "public_demo"
    INTERNAL_TEST = "internal_test"


class PlanStatus(_Vocabulary):
    ACTIVE = "active"
    TRIALING = "trialing"
    PAUSED = "paused"
    EXPIRED = "expired"
    CANCELED = "canceled"
    TEST = "test"
    MANUAL = "manual"


class PlanAssignmentSource(_Vocabulary):
    MANUAL = "manual"
    ADMIN_SEED = "admin_seed"
    TEST_FIXTURE = "test_fixture"
    FUTURE_BILLING_PROVIDER = "future_billing_provider"


ENTITLING_PLAN_STATUSES: frozenset[PlanStatus] = frozenset(
    {
        PlanStatus.ACTIVE,
        PlanStatus.TRIALING,
        PlanStatus.TEST,
        PlanStatus.MANUAL,
    }
)


class MonetizationAccountSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    monetization_account_id: str | None = Field(default=None, min_length=1, max_length=64)
    user_id: str | None = Field(default=None, min_length=1, max_length=64)
    account_type: MonetizationAccountType
    assigned_seats_count: int | None = Field(default=None, ge=0)
    safe_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("safe_metadata")
    @classmethod
    def _metadata_must_be_safe(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_safe_metadata(value)
        return value


class PlanAssignmentSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plan_assignment_id: str | None = Field(default=None, min_length=1, max_length=64)
    monetization_account_id: str | None = Field(default=None, min_length=1, max_length=64)
    plan_key: PlanKey
    plan_status: PlanStatus
    assignment_source: PlanAssignmentSource
    effective_at: datetime
    expires_at: datetime | None = None
    seat_limit: int | None = Field(default=None, ge=0)
    safe_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("safe_metadata")
    @classmethod
    def _metadata_must_be_safe(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_safe_metadata(value)
        return value


SAFE_METADATA_FORBIDDEN_KEY_PARTS: tuple[str, ...] = (
    "billing_provider",
    "checkout",
    "payment",
    "preference",
    "recommendation_detail",
    "recommendation_internals",
    "stripe",
)


def plan_status_grants_entitlements(status: PlanStatus | str) -> bool:
    return PlanStatus(status) in ENTITLING_PLAN_STATUSES


def assignment_is_effective(
    assignment: PlanAssignmentSnapshot,
    *,
    now: datetime,
) -> bool:
    now = _coerce_aware(now)
    effective_at = _coerce_aware(assignment.effective_at)
    expires_at = (
        _coerce_aware(assignment.expires_at)
        if assignment.expires_at is not None
        else None
    )
    if effective_at > now:
        return False
    if expires_at is not None and expires_at <= now:
        return False
    return plan_status_grants_entitlements(assignment.plan_status)


def _validate_safe_metadata(value: dict[str, Any]) -> None:
    for key in value:
        folded = str(key).casefold()
        if any(part in folded for part in SAFE_METADATA_FORBIDDEN_KEY_PARTS):
            raise ValueError(f"unsafe monetization metadata key: {key!r}")


def _coerce_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
