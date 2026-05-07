from datetime import UTC, datetime, timedelta, timezone

import pytest

from backend.shared.freshness import (
    FreshnessStatus,
    evaluate_freshness,
    is_fresh,
    is_stale,
)


def _utc(year=2026, month=5, day=6, hour=12) -> datetime:
    return datetime(year, month, day, hour, tzinfo=UTC)


def test_unknown_when_expires_at_is_none() -> None:
    assert evaluate_freshness(None, now=_utc()) is FreshnessStatus.UNKNOWN
    assert is_fresh(None, now=_utc()) is False
    assert is_stale(None, now=_utc()) is False


def test_fresh_when_now_before_expiry() -> None:
    now = _utc(hour=12)
    expires = now + timedelta(hours=1)
    assert evaluate_freshness(expires, now=now) is FreshnessStatus.FRESH
    assert is_fresh(expires, now=now) is True
    assert is_stale(expires, now=now) is False


def test_stale_when_now_at_or_after_expiry() -> None:
    now = _utc(hour=12)
    just_expired = now
    long_expired = now - timedelta(days=1)
    assert evaluate_freshness(just_expired, now=now) is FreshnessStatus.STALE
    assert evaluate_freshness(long_expired, now=now) is FreshnessStatus.STALE


def test_now_defaults_to_current_utc() -> None:
    far_future = datetime.now(UTC) + timedelta(days=365)
    assert evaluate_freshness(far_future) is FreshnessStatus.FRESH

    long_past = datetime.now(UTC) - timedelta(days=365)
    assert evaluate_freshness(long_past) is FreshnessStatus.STALE


def test_naive_expires_at_raises() -> None:
    naive = datetime(2026, 5, 6, 12, 0)
    with pytest.raises(ValueError):
        evaluate_freshness(naive, now=_utc())


def test_naive_now_raises() -> None:
    aware = _utc(hour=13)
    naive_now = datetime(2026, 5, 6, 12, 0)
    with pytest.raises(ValueError):
        evaluate_freshness(aware, now=naive_now)


def test_non_utc_timezone_is_accepted() -> None:
    eastern = timezone(timedelta(hours=-5))
    expires = datetime(2026, 5, 6, 7, 0, tzinfo=eastern)  # 12:00 UTC
    now_utc = datetime(2026, 5, 6, 11, 30, tzinfo=UTC)
    assert evaluate_freshness(expires, now=now_utc) is FreshnessStatus.FRESH

    now_utc_after = datetime(2026, 5, 6, 12, 30, tzinfo=UTC)
    assert evaluate_freshness(expires, now=now_utc_after) is FreshnessStatus.STALE
