"""Central account-aware monetization enforcement helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.monetization.entitlements import AccessDecision, UsageContext, decide_access
from backend.monetization.features import MonetizationFeatureKey
from backend.monetization.resolver import (
    EntitlementSnapshot,
    MonetizationAccountReader,
    resolve_account_entitlements,
)
from backend.monetization.usage import (
    UsageCounterSnapshot,
    usage_period_for_limit,
)


def evaluate_account_access(
    repository: MonetizationAccountReader,
    *,
    feature_key: MonetizationFeatureKey | str,
    user_id: str | None = None,
    monetization_account_id: str | None = None,
    now: datetime | None = None,
    create_usage_counter: bool = False,
) -> AccessDecision:
    """Return an access decision using the effective account plan and usage.

    The helper is intentionally the single place where account state meets the
    pure entitlement decision layer. Route handlers should call this helper
    instead of checking plan keys directly.
    """

    now = _coerce_aware(now or datetime.now(UTC))
    snapshot = resolve_account_entitlements(
        repository,
        user_id=user_id,
        monetization_account_id=monetization_account_id,
        now=now,
    )
    usage_context = _usage_context_for_feature(
        repository,
        snapshot=snapshot,
        feature_key=feature_key,
        now=now,
        create_usage_counter=create_usage_counter,
    )
    decision = decide_access(
        plan_key=snapshot.plan_key,
        feature_key=feature_key,
        usage_context=usage_context,
    )
    return decision.model_copy(update={"account_status": snapshot.account_status.value})


def increment_feature_usage(
    repository: MonetizationAccountReader,
    *,
    feature_key: MonetizationFeatureKey | str,
    amount: int = 1,
    user_id: str | None = None,
    monetization_account_id: str | None = None,
    now: datetime | None = None,
) -> AccessDecision:
    """Increment a limited feature only after central entitlement approval."""

    if amount < 1:
        raise ValueError("usage increment amount must be positive")

    now = _coerce_aware(now or datetime.now(UTC))
    before = evaluate_account_access(
        repository,
        feature_key=feature_key,
        user_id=user_id,
        monetization_account_id=monetization_account_id,
        now=now,
        create_usage_counter=True,
    )
    if not before.allowed or before.usage_limit is None:
        return before
    if before.remaining_usage is not None and before.remaining_usage < amount:
        blocked = decide_access(
            before.plan_key,
            feature_key,
            usage_context={"used": before.usage_limit.limit},
        )
        return blocked.model_copy(
            update={"account_status": before.account_status}
        )

    snapshot = resolve_account_entitlements(
        repository,
        user_id=user_id,
        monetization_account_id=monetization_account_id,
        now=now,
    )
    if snapshot.monetization_account_id is None:
        return before

    period = usage_period_for_limit(before.usage_limit, now=now)
    counter = repository.ensure_usage_counter(
        monetization_account_id=snapshot.monetization_account_id,
        feature_key=feature_key,
        period=period,
        limit_count=before.usage_limit.limit,
    )
    repository.increment_usage(counter, amount=amount, now=now)
    remaining_after = (
        max(before.remaining_usage - amount, 0)
        if before.remaining_usage is not None
        else None
    )
    return before.model_copy(update={"remaining_usage": remaining_after})


def usage_counter_snapshot(row: Any) -> UsageCounterSnapshot:
    return UsageCounterSnapshot(
        usage_counter_id=row.usage_counter_id,
        monetization_account_id=row.monetization_account_id,
        feature_key=row.feature_key,
        period_start=row.period_start,
        period_end=row.period_end,
        used_count=row.used_count,
        limit_count=row.limit_count,
        reset_policy=row.reset_policy,
        last_incremented_at=row.last_incremented_at,
    )


def _usage_context_for_feature(
    repository: MonetizationAccountReader,
    *,
    snapshot: EntitlementSnapshot,
    feature_key: MonetizationFeatureKey | str,
    now: datetime,
    create_usage_counter: bool,
) -> UsageContext | None:
    normalized_feature_key = MonetizationFeatureKey(feature_key)
    usage_limit = next(
        (
            limit
            for limit in snapshot.usage_limits
            if limit.feature_key is normalized_feature_key
        ),
        None,
    )
    if usage_limit is None or snapshot.monetization_account_id is None:
        return None

    period = usage_period_for_limit(usage_limit, now=now)
    if create_usage_counter:
        counter = repository.ensure_usage_counter(
            monetization_account_id=snapshot.monetization_account_id,
            feature_key=normalized_feature_key,
            period=period,
            limit_count=usage_limit.limit,
        )
    else:
        counter = repository.get_usage_counter(
            monetization_account_id=snapshot.monetization_account_id,
            feature_key=normalized_feature_key,
            period=period,
        )

    used = counter.used_count if counter is not None else 0
    return UsageContext(
        used=used,
        usage_period=f"{period.reset_policy.value}:{period.period_start.isoformat()}",
    )


def _coerce_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
