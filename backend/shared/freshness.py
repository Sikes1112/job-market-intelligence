"""Freshness evaluation helpers.

Pure timestamp comparison. No object-type-specific freshness windows live here
(``OBJECT_STATE_MODEL.md`` §12 explicitly says thresholds are per-object-type
and belong with the domain that owns the object — slices 5–11). This module
only answers: given an expiry timestamp and a current time, is the object
fresh, stale, or freshness-unknown?
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum


class FreshnessStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


def _ensure_aware(value: datetime, *, label: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value


def evaluate_freshness(
    expires_at: datetime | None,
    *,
    now: datetime | None = None,
) -> FreshnessStatus:
    """Return :class:`FreshnessStatus` for an object given its expiry timestamp.

    * ``None`` ``expires_at`` → ``UNKNOWN`` (never silently treated as fresh).
    * ``now < expires_at`` → ``FRESH``.
    * ``now >= expires_at`` → ``STALE``.

    Both ``expires_at`` and ``now`` must be timezone-aware datetimes.
    """
    if expires_at is None:
        return FreshnessStatus.UNKNOWN
    expires_at = _ensure_aware(expires_at, label="expires_at")
    if now is None:
        now = datetime.now(UTC)
    else:
        now = _ensure_aware(now, label="now")
    return FreshnessStatus.FRESH if now < expires_at else FreshnessStatus.STALE


def is_fresh(expires_at: datetime | None, *, now: datetime | None = None) -> bool:
    """Convenience predicate for ``FRESH``."""
    return evaluate_freshness(expires_at, now=now) is FreshnessStatus.FRESH


def is_stale(expires_at: datetime | None, *, now: datetime | None = None) -> bool:
    """Convenience predicate for ``STALE``."""
    return evaluate_freshness(expires_at, now=now) is FreshnessStatus.STALE
