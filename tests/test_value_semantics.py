from backend.shared.freshness import FreshnessStatus
from backend.shared.provenance import ObservationStatus
from backend.shared.value_semantics import aggregate_counts, classify_count


def test_unknown_count_is_not_zero_observed() -> None:
    result = classify_count(None)
    assert result.value is None
    assert result.status is ObservationStatus.UNKNOWN


def test_not_collected_count_is_not_zero_observed() -> None:
    result = classify_count(None, collected=False)
    assert result.value is None
    assert result.status is ObservationStatus.NOT_COLLECTED


def test_stale_zero_remains_distinguishable_from_current_zero() -> None:
    result = classify_count(0, freshness_status=FreshnessStatus.STALE)
    assert result.value is None
    assert result.status is ObservationStatus.STALE


def test_zero_observed_requires_observed_basis() -> None:
    unobserved = classify_count(0, observed_basis=False)
    observed = classify_count(0, observed_basis=True)
    assert unobserved.status is ObservationStatus.UNKNOWN
    assert observed.status is ObservationStatus.ZERO_OBSERVED
    assert observed.value == 0


def test_positive_observed_remains_distinct_from_zero_observed() -> None:
    positive = classify_count(3)
    zero = classify_count(0)
    assert positive.status is ObservationStatus.POSITIVE_OBSERVED
    assert zero.status is ObservationStatus.ZERO_OBSERVED
    assert positive.status is not zero.status


def test_aggregate_counts_does_not_convert_unknown_to_zero() -> None:
    result = aggregate_counts([2, None])
    assert result.value is None
    assert result.status is ObservationStatus.UNKNOWN


def test_aggregate_counts_reports_observed_zero_only_for_observed_zeroes() -> None:
    result = aggregate_counts([0, 0])
    assert result.value == 0
    assert result.status is ObservationStatus.ZERO_OBSERVED
