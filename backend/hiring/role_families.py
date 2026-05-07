"""Role-family helpers.

The ``role_family_summary`` column on ``CompanyRegionHiring`` is a free-form
``dict[str, int]`` mapping role-family name to count. This module provides:

* a documented set of MVP-recommended role-family keys (callers may use any
  string; this set is informational for tests and seeds);
* a tiny validator that rejects malformed shapes (negative counts, non-int
  values, blank keys).

It does **not** attempt to parse job descriptions or extract role families
from text. That belongs to a real ingestion pipeline (Deferred A) — out of
MVP scope.
"""

from __future__ import annotations

from typing import Any

# Documented MVP role families per MVP_SCOPE.md "In-scope role families".
DOCUMENTED_ROLE_FAMILIES: frozenset[str] = frozenset(
    {
        "product",
        "ai_cloud_adjacent",
        "cybersecurity",
    }
)


def validate_role_family_summary(summary: Any) -> None:
    """Raise :class:`ValueError` if ``summary`` is not a clean ``dict[str, int]``.

    ``None`` is accepted (means "no information") and returns without raising.
    """
    if summary is None:
        return
    if not isinstance(summary, dict):
        raise ValueError(f"role_family_summary must be a dict or None: {type(summary).__name__}")
    for key, count in summary.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"role family key must be a non-empty string: {key!r}")
        if isinstance(count, bool) or not isinstance(count, int):
            raise ValueError(
                f"role family count must be an int, got {type(count).__name__}: {count!r}"
            )
        if count < 0:
            raise ValueError(f"role family count must be non-negative: {count!r}")
