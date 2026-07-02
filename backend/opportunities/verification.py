"""Verification and expiration helpers for Layer 23A opportunities."""

from __future__ import annotations

from datetime import UTC, datetime

from backend.opportunities.models import Opportunity
from backend.opportunities.schemas import (
    OpportunityExpirationState,
    OpportunityReviewStatus,
    OpportunityTrustLabel,
)

ACTIVE_VERIFIED_TRUST_LABELS = frozenset(
    {
        OpportunityTrustLabel.VERIFIED.value,
        OpportunityTrustLabel.SOURCE_CHECKED.value,
    }
)
ACTIVE_VERIFIED_REVIEW_STATUSES = frozenset(
    {
        OpportunityReviewStatus.APPROVED.value,
        OpportunityReviewStatus.SOURCE_CHECKED.value,
    }
)
INACTIVE_TRUST_LABELS = frozenset(
    {
        OpportunityTrustLabel.EXPIRED.value,
        OpportunityTrustLabel.REJECTED.value,
    }
)
INACTIVE_REVIEW_STATUSES = frozenset(
    {
        OpportunityReviewStatus.EXPIRED.value,
        OpportunityReviewStatus.REJECTED.value,
    }
)


def opportunity_expiration_state(
    opportunity: Opportunity,
    *,
    now: datetime | None = None,
) -> OpportunityExpirationState:
    return (
        OpportunityExpirationState.EXPIRED
        if is_opportunity_expired(opportunity, now=now)
        else OpportunityExpirationState.ACTIVE
    )


def is_opportunity_expired(
    opportunity: Opportunity,
    *,
    now: datetime | None = None,
) -> bool:
    checked_at = _aware_now(now)
    if opportunity.trust_label == OpportunityTrustLabel.EXPIRED.value:
        return True
    if opportunity.review_status == OpportunityReviewStatus.EXPIRED.value:
        return True
    if opportunity.application_deadline is not None:
        if opportunity.application_deadline < checked_at.date():
            return True
    if opportunity.expires_at is not None:
        expires_at = opportunity.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= checked_at:
            return True
    return False


def is_active_opportunity(
    opportunity: Opportunity,
    *,
    now: datetime | None = None,
) -> bool:
    if is_opportunity_expired(opportunity, now=now):
        return False
    if opportunity.trust_label in INACTIVE_TRUST_LABELS:
        return False
    if opportunity.review_status in INACTIVE_REVIEW_STATUSES:
        return False
    return True


def is_active_verified_opportunity(
    opportunity: Opportunity,
    *,
    now: datetime | None = None,
) -> bool:
    return (
        is_active_opportunity(opportunity, now=now)
        and opportunity.trust_label in ACTIVE_VERIFIED_TRUST_LABELS
        and opportunity.review_status in ACTIVE_VERIFIED_REVIEW_STATUSES
    )


def _aware_now(value: datetime | None) -> datetime:
    now = value or datetime.now(UTC)
    if now.tzinfo is None:
        return now.replace(tzinfo=UTC)
    return now
