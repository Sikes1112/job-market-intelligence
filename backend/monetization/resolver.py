"""Account-aware entitlement resolution.

The resolver turns internal, provider-agnostic plan assignment records into the
same plan and feature vocabulary used by the pure entitlement decision layer.
It deliberately does not import recommendation ranking or any billing adapter.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from backend.monetization.accounts import (
    MonetizationAccountSnapshot,
    MonetizationAccountType,
    PlanAssignmentSnapshot,
    PlanStatus,
    assignment_is_effective,
)
from backend.monetization.features import MonetizationFeatureKey
from backend.monetization.plans import PlanKey, UsageLimit, plan_definition


class EntitlementSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str | None = Field(default=None, min_length=1, max_length=64)
    monetization_account_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
    )
    account_type: MonetizationAccountType
    account_status: PlanStatus
    plan_key: PlanKey
    included_feature_keys: tuple[MonetizationFeatureKey, ...]
    usage_limits: tuple[UsageLimit, ...]
    assignment_source: str | None = Field(default=None, min_length=1, max_length=64)
    effective_at: datetime | None = None
    expires_at: datetime | None = None
    seat_limit: int | None = Field(default=None, ge=0)
    assigned_seats_count: int | None = Field(default=None, ge=0)
    safe_metadata: dict[str, Any] = Field(default_factory=dict)


class MonetizationAccountReader(Protocol):
    def get_account(self, monetization_account_id: str) -> Any | None:
        ...

    def get_account_for_user(self, user_id: str) -> Any | None:
        ...

    def list_plan_assignments(self, monetization_account_id: str) -> list[Any]:
        ...


def resolve_account_entitlements(
    repository: MonetizationAccountReader,
    *,
    user_id: str | None = None,
    monetization_account_id: str | None = None,
    now: datetime | None = None,
) -> EntitlementSnapshot:
    """Resolve the effective entitlements for an account or user.

    Unknown users and public visitors intentionally resolve to the Free plan.
    Expired, paused, canceled, or future-dated assignments also fall back to
    Free rather than granting paid workflow access.
    """

    now = _coerce_aware(now or datetime.now(UTC))
    account_row = _find_account(
        repository,
        user_id=user_id,
        monetization_account_id=monetization_account_id,
    )
    if account_row is None:
        account_type = (
            MonetizationAccountType.INDIVIDUAL
            if user_id is not None
            else MonetizationAccountType.PUBLIC_DEMO
        )
        return build_entitlement_snapshot(
            account=MonetizationAccountSnapshot(
                user_id=user_id,
                account_type=account_type,
            ),
            assignment=None,
            now=now,
        )

    account = _account_snapshot(account_row)
    assignments = [
        _assignment_snapshot(row)
        for row in repository.list_plan_assignments(account.monetization_account_id or "")
    ]
    effective_assignment = next(
        (
            assignment
            for assignment in assignments
            if assignment_is_effective(assignment, now=now)
        ),
        None,
    )
    return build_entitlement_snapshot(
        account=account,
        assignment=effective_assignment,
        latest_assignment=assignments[0] if assignments else None,
        now=now,
    )


def get_effective_plan_key(
    repository: MonetizationAccountReader,
    *,
    user_id: str | None = None,
    monetization_account_id: str | None = None,
    now: datetime | None = None,
) -> PlanKey:
    return resolve_account_entitlements(
        repository,
        user_id=user_id,
        monetization_account_id=monetization_account_id,
        now=now,
    ).plan_key


def build_entitlement_snapshot(
    *,
    account: MonetizationAccountSnapshot,
    assignment: PlanAssignmentSnapshot | None,
    latest_assignment: PlanAssignmentSnapshot | None = None,
    now: datetime | None = None,
) -> EntitlementSnapshot:
    now = _coerce_aware(now or datetime.now(UTC))
    effective = assignment
    plan_key = effective.plan_key if effective is not None else PlanKey.FREE
    plan = plan_definition(plan_key)
    status = _snapshot_status(effective or latest_assignment, now=now)

    return EntitlementSnapshot(
        user_id=account.user_id,
        monetization_account_id=account.monetization_account_id,
        account_type=account.account_type,
        account_status=status,
        plan_key=plan_key,
        included_feature_keys=plan.included_feature_keys,
        usage_limits=plan.usage_limits,
        assignment_source=(
            effective.assignment_source.value if effective is not None else None
        ),
        effective_at=effective.effective_at if effective is not None else None,
        expires_at=effective.expires_at if effective is not None else None,
        seat_limit=effective.seat_limit if effective is not None else None,
        assigned_seats_count=account.assigned_seats_count,
        safe_metadata=account.safe_metadata,
    )


def _find_account(
    repository: MonetizationAccountReader,
    *,
    user_id: str | None,
    monetization_account_id: str | None,
) -> Any | None:
    if monetization_account_id is not None:
        return repository.get_account(monetization_account_id)
    if user_id is not None:
        return repository.get_account_for_user(user_id)
    return None


def _account_snapshot(row: Any) -> MonetizationAccountSnapshot:
    return MonetizationAccountSnapshot(
        monetization_account_id=row.monetization_account_id,
        user_id=row.user_id,
        account_type=row.account_type,
        assigned_seats_count=row.assigned_seats_count,
        safe_metadata=dict(row.safe_metadata or {}),
    )


def _assignment_snapshot(row: Any) -> PlanAssignmentSnapshot:
    return PlanAssignmentSnapshot(
        plan_assignment_id=row.plan_assignment_id,
        monetization_account_id=row.monetization_account_id,
        plan_key=row.plan_key,
        plan_status=row.plan_status,
        assignment_source=row.assignment_source,
        effective_at=row.effective_at,
        expires_at=row.expires_at,
        seat_limit=row.seat_limit,
        safe_metadata=dict(row.safe_metadata or {}),
    )


def _snapshot_status(
    assignment: PlanAssignmentSnapshot | None,
    *,
    now: datetime,
) -> PlanStatus:
    if assignment is None:
        return PlanStatus.ACTIVE
    if assignment.expires_at is not None and _coerce_aware(assignment.expires_at) <= now:
        return PlanStatus.EXPIRED
    return assignment.plan_status


def _coerce_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
