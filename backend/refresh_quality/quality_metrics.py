"""Small metric helpers for refresh-quality diagnostics.

These helpers only compare already-supplied values. They do not fetch data,
recompute canonical scores, mutate rankings, or rebuild outputs.
"""

from __future__ import annotations

from collections.abc import Mapping

SUSPICIOUS_HIRING_DROP_RATIO = 0.50
MIN_PREVIOUS_HIRING_COUNT_FOR_DROP = 5
SOURCE_DOMINANCE_WARNING_RATIO = 0.80
LOW_CONFIDENCE_SCORE_WEIGHT_RATIO = 0.50
REPEATED_REFRESH_FAILURE_THRESHOLD = 3


def hiring_count_drop_ratio(
    previous_count: int | None,
    current_count: int | None,
) -> float | None:
    """Return the fractional count drop, or ``None`` when not comparable."""

    if previous_count is None or current_count is None:
        return None
    if previous_count <= 0:
        return None
    if current_count >= previous_count:
        return 0.0
    return (previous_count - current_count) / previous_count


def disappeared_source_refs(
    previous_source_refs: tuple[str, ...],
    current_source_refs: tuple[str, ...],
) -> tuple[str, ...]:
    """Return source refs present before but missing now."""

    previous = set(previous_source_refs)
    current = set(current_source_refs)
    return tuple(sorted(previous - current))


def dominant_source_weight(
    source_weights: Mapping[str, float],
) -> tuple[str, float] | None:
    """Return the highest weighted source contribution, if any."""

    if not source_weights:
        return None
    source_ref, weight = max(source_weights.items(), key=lambda item: item[1])
    return source_ref, weight


def coverage_gap_delta(
    previous_gap_count: int | None,
    current_gap_count: int | None,
) -> int | None:
    """Return positive/negative coverage gap movement when comparable."""

    if previous_gap_count is None or current_gap_count is None:
        return None
    return current_gap_count - previous_gap_count


__all__ = [
    "LOW_CONFIDENCE_SCORE_WEIGHT_RATIO",
    "MIN_PREVIOUS_HIRING_COUNT_FOR_DROP",
    "REPEATED_REFRESH_FAILURE_THRESHOLD",
    "SOURCE_DOMINANCE_WARNING_RATIO",
    "SUSPICIOUS_HIRING_DROP_RATIO",
    "coverage_gap_delta",
    "disappeared_source_refs",
    "dominant_source_weight",
    "hiring_count_drop_ratio",
]
