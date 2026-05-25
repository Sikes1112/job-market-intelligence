"""Unknown/zero semantics for count-like market values.

These helpers keep Layer 3C behavior narrow: they classify and aggregate
nullable count fields without changing storage shapes. They do not enforce
provenance, collect sources, or run audit checks.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.shared.freshness import FreshnessStatus
from backend.shared.provenance import ObservationStatus

OBSERVED_COUNT_STATUSES: frozenset[ObservationStatus] = frozenset(
    {
        ObservationStatus.ZERO_OBSERVED,
        ObservationStatus.POSITIVE_OBSERVED,
    }
)


@dataclass(frozen=True, slots=True)
class CountSemantics:
    value: int | None
    status: ObservationStatus

    @property
    def has_current_observed_value(self) -> bool:
        return self.status in OBSERVED_COUNT_STATUSES


def classify_count(
    value: int | None,
    *,
    observed_basis: bool | None = None,
    collected: bool = True,
    applicable: bool = True,
    freshness_status: FreshnessStatus = FreshnessStatus.FRESH,
) -> CountSemantics:
    """Classify a single nullable count.

    ``0`` becomes ``zero_observed`` only when an observed basis is present.
    ``None`` stays ``unknown`` or ``not_collected``. Stale values are reported
    as ``stale`` before numeric interpretation, so stale zero never appears as
    current observed zero.
    """
    if not applicable:
        return CountSemantics(value=None, status=ObservationStatus.NOT_APPLICABLE)
    if not collected:
        return CountSemantics(value=None, status=ObservationStatus.NOT_COLLECTED)
    if freshness_status is FreshnessStatus.STALE:
        return CountSemantics(value=None, status=ObservationStatus.STALE)
    if observed_basis is None:
        observed_basis = value is not None
    if not observed_basis:
        return CountSemantics(value=None, status=ObservationStatus.UNKNOWN)
    if value is None:
        return CountSemantics(value=None, status=ObservationStatus.UNKNOWN)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"count must be an int or None, got {value!r}")
    if value < 0:
        raise ValueError(f"count must be non-negative, got {value}")
    if value == 0:
        return CountSemantics(value=0, status=ObservationStatus.ZERO_OBSERVED)
    return CountSemantics(value=value, status=ObservationStatus.POSITIVE_OBSERVED)


def current_observed_count(value: int | None, **kwargs) -> int | None:
    """Return the numeric count only when it is current and observed."""
    semantics = classify_count(value, **kwargs)
    return semantics.value if semantics.has_current_observed_value else None


def aggregate_counts(
    values: list[int | None] | tuple[int | None, ...],
    *,
    collected: bool = True,
    applicable: bool = True,
    freshness_status: FreshnessStatus = FreshnessStatus.FRESH,
) -> CountSemantics:
    """Aggregate count values without treating unknown as zero.

    The aggregate is numeric only when every applicable input is currently
    observed. Any unknown/not-collected/stale input makes the aggregate status
    non-numeric, preserving the distinction from observed zero.
    """
    if not applicable:
        return CountSemantics(value=None, status=ObservationStatus.NOT_APPLICABLE)
    if not collected:
        return CountSemantics(value=None, status=ObservationStatus.NOT_COLLECTED)
    if not values:
        return CountSemantics(value=None, status=ObservationStatus.NOT_COLLECTED)

    items = [
        classify_count(value, freshness_status=freshness_status) for value in values
    ]
    for status in (
        ObservationStatus.STALE,
        ObservationStatus.NOT_COLLECTED,
        ObservationStatus.UNKNOWN,
        ObservationStatus.NOT_APPLICABLE,
    ):
        if any(item.status is status for item in items):
            return CountSemantics(value=None, status=status)

    total = sum(item.value for item in items if item.value is not None)
    status = (
        ObservationStatus.POSITIVE_OBSERVED
        if total > 0
        else ObservationStatus.ZERO_OBSERVED
    )
    return CountSemantics(value=total, status=status)
