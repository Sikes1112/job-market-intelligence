"""Central entitlement decisions for monetization access.

This module is intentionally pure: it has no API, database, payment-provider,
or recommendation-ranking dependency. Billing adapters can provide plan keys
later, but product access remains decided here.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.monetization.features import MonetizationFeatureKey
from backend.monetization.plans import (
    PlanKey,
    UsageLimit,
    plan_definition,
    plan_definitions,
    usage_limit_for_feature,
)


class UsageContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    used: int | None = Field(default=None, ge=0)
    usage_period: str | None = Field(default=None, min_length=1, max_length=64)


class AccessDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed: bool
    plan_key: PlanKey
    feature_key: MonetizationFeatureKey
    reason: str = Field(min_length=1, max_length=360)
    upgrade_plan_keys: tuple[PlanKey, ...] = Field(default_factory=tuple, max_length=16)
    usage_limit: UsageLimit | None = None
    remaining_usage: int | None = Field(default=None, ge=0)
    account_status: str | None = Field(default=None, min_length=1, max_length=32)


def decide_access(
    plan_key: PlanKey | str,
    feature_key: MonetizationFeatureKey | str,
    usage_context: UsageContext | Mapping[str, Any] | None = None,
) -> AccessDecision:
    """Return a deterministic access decision for a plan and feature.

    ``usage_context`` is optional because feature inclusion can be evaluated
    without usage state. When ``used`` is supplied for a limited feature, the
    decision also reports remaining usage and blocks only if the configured
    limit is exhausted.
    """

    normalized_plan_key = PlanKey(plan_key)
    normalized_feature_key = MonetizationFeatureKey(feature_key)
    plan = plan_definition(normalized_plan_key)
    context = _normalize_usage_context(usage_context)

    if normalized_feature_key not in plan.included_feature_keys:
        return AccessDecision(
            allowed=False,
            plan_key=normalized_plan_key,
            feature_key=normalized_feature_key,
            reason=(
                f"{normalized_feature_key.value} is not included in "
                f"{normalized_plan_key.value}."
            ),
            upgrade_plan_keys=upgrade_targets_for_feature(
                normalized_plan_key,
                normalized_feature_key,
            ),
        )

    usage_limit = usage_limit_for_feature(plan, normalized_feature_key)
    if usage_limit is None:
        return AccessDecision(
            allowed=True,
            plan_key=normalized_plan_key,
            feature_key=normalized_feature_key,
            reason=f"{normalized_feature_key.value} is included in {normalized_plan_key.value}.",
        )

    if context is None or context.used is None:
        return AccessDecision(
            allowed=True,
            plan_key=normalized_plan_key,
            feature_key=normalized_feature_key,
            reason=(
                f"{normalized_feature_key.value} is included in "
                f"{normalized_plan_key.value} with a configured usage limit."
            ),
            usage_limit=usage_limit,
        )

    remaining = max(usage_limit.limit - context.used, 0)
    if context.used >= usage_limit.limit:
        return AccessDecision(
            allowed=False,
            plan_key=normalized_plan_key,
            feature_key=normalized_feature_key,
            reason=(
                f"{normalized_feature_key.value} usage limit reached for "
                f"{normalized_plan_key.value}."
            ),
            upgrade_plan_keys=upgrade_targets_for_feature(
                normalized_plan_key,
                normalized_feature_key,
            ),
            usage_limit=usage_limit,
            remaining_usage=remaining,
        )

    return AccessDecision(
        allowed=True,
        plan_key=normalized_plan_key,
        feature_key=normalized_feature_key,
        reason=(
            f"{normalized_feature_key.value} is included in {normalized_plan_key.value}; "
            f"{remaining} usage units remain."
        ),
        usage_limit=usage_limit,
        remaining_usage=remaining,
    )


def upgrade_targets_for_feature(
    current_plan_key: PlanKey | str,
    feature_key: MonetizationFeatureKey | str,
) -> tuple[PlanKey, ...]:
    current = plan_definition(current_plan_key)
    normalized_feature_key = MonetizationFeatureKey(feature_key)

    configured_targets = tuple(
        target
        for target in current.upgrade_plan_keys
        if normalized_feature_key in plan_definition(target).included_feature_keys
    )
    if configured_targets:
        return configured_targets

    return tuple(
        plan.plan_key
        for plan in plan_definitions()
        if plan.plan_key is not current.plan_key
        and normalized_feature_key in plan.included_feature_keys
    )


def _normalize_usage_context(
    usage_context: UsageContext | Mapping[str, Any] | None,
) -> UsageContext | None:
    if usage_context is None:
        return None
    if isinstance(usage_context, UsageContext):
        return usage_context
    return UsageContext.model_validate(dict(usage_context))
