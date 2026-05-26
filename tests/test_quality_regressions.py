from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from backend.refresh_quality.models import (
    QualityRegressionSnapshot,
    QualityRegressionType,
    QualitySeverity,
)
from backend.refresh_quality.regression_detection import detect_quality_regressions

NOW = datetime(2026, 5, 26, 12, tzinfo=UTC)


def _snapshot(**overrides) -> QualityRegressionSnapshot:
    base = {
        "entity_type": "company_region",
        "entity_id": "company_a::boston",
    }
    base.update(overrides)
    return QualityRegressionSnapshot(**base)


def test_quality_regression_type_vocabulary_is_complete() -> None:
    assert QualityRegressionType.values() == {
        "source_disappeared",
        "suspicious_hiring_count_drop",
        "company_region_presence_contradicted",
        "entry_level_signal_became_stale",
        "single_source_dominates_market_score",
        "market_score_relies_too_heavily_on_low_confidence_facts",
        "coverage_gap_worsened",
        "repeated_refresh_failure",
    }


def test_detects_all_required_quality_regression_types() -> None:
    snapshot = _snapshot(
        previous_source_refs=("source_a", "source_b"),
        current_source_refs=(),
        previous_hiring_count=100,
        current_hiring_count=35,
        previous_presence_status="present",
        current_presence_status="uncertain",
        entry_level_freshness_expires_at=NOW - timedelta(seconds=1),
        market_score_source_weights={"source_a": 0.85, "source_b": 0.15},
        market_score_low_confidence_weight=0.60,
        previous_coverage_gap_count=1,
        current_coverage_gap_count=4,
        refresh_failure_count=3,
        old_value={"quality": "better"},
        current_value={"quality": "worse"},
        evidence_values={"run_id": "refresh_quality_test"},
    )

    regressions = detect_quality_regressions([snapshot], now=NOW)
    by_type = {regression.regression_type: regression for regression in regressions}

    assert set(by_type) == set(QualityRegressionType)
    assert (
        by_type[QualityRegressionType.SUSPICIOUS_HIRING_COUNT_DROP]
        .evidence_values["drop_ratio"]
        == 0.65
    )
    assert (
        by_type[QualityRegressionType.SINGLE_SOURCE_DOMINATES_MARKET_SCORE]
        .evidence_values["dominant_source_ref"]
        == "source_a"
    )
    assert (
        by_type[QualityRegressionType.COVERAGE_GAP_WORSENED].severity
        is QualitySeverity.HIGH
    )
    assert all(regression.human_review_required for regression in regressions)
    assert all(regression.recommended_action for regression in regressions)
    assert all(
        regression.evidence_values["run_id"] == "refresh_quality_test"
        for regression in regressions
    )


def test_safe_comparable_quality_state_does_not_emit_regressions() -> None:
    snapshot = _snapshot(
        previous_source_refs=("source_a", "source_b"),
        current_source_refs=("source_a", "source_b", "source_c"),
        previous_hiring_count=20,
        current_hiring_count=18,
        previous_presence_status="present",
        current_presence_status="present",
        entry_level_freshness_expires_at=NOW + timedelta(days=1),
        market_score_source_weights={"source_a": 0.45, "source_b": 0.40},
        market_score_low_confidence_weight=0.20,
        previous_coverage_gap_count=2,
        current_coverage_gap_count=1,
        refresh_failure_count=1,
    )

    assert detect_quality_regressions([snapshot], now=NOW) == []


def test_regression_detection_keys_are_stable() -> None:
    snapshot = _snapshot(previous_hiring_count=10, current_hiring_count=2)

    first = detect_quality_regressions([snapshot], now=NOW)
    second = detect_quality_regressions([snapshot], now=NOW)

    assert [regression.regression_id for regression in first] == [
        regression.regression_id for regression in second
    ]


def test_quality_regression_snapshot_rejects_bad_weights() -> None:
    with pytest.raises(ValidationError, match="between 0 and 1"):
        _snapshot(market_score_source_weights={"source_a": 1.01})


def test_naive_now_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        detect_quality_regressions(
            [_snapshot(entry_level_freshness_expires_at=NOW)],
            now=datetime(2026, 5, 26, 12),
        )
