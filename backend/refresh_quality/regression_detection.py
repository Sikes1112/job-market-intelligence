"""Quality regression detection helpers.

Regression records explain risk. They never repair data, rewrite scores,
change rankings, enqueue execution jobs, or rebuild outputs.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from backend.shared.freshness import FreshnessStatus, evaluate_freshness

from .models import (
    QualityRegressionRecord,
    QualityRegressionSnapshot,
    QualityRegressionType,
    QualitySeverity,
    stable_quality_regression_id,
)
from .quality_metrics import (
    LOW_CONFIDENCE_SCORE_WEIGHT_RATIO,
    MIN_PREVIOUS_HIRING_COUNT_FOR_DROP,
    REPEATED_REFRESH_FAILURE_THRESHOLD,
    SOURCE_DOMINANCE_WARNING_RATIO,
    SUSPICIOUS_HIRING_DROP_RATIO,
    coverage_gap_delta,
    disappeared_source_refs,
    dominant_source_weight,
    hiring_count_drop_ratio,
)


def detect_quality_regressions(
    snapshots: Iterable[QualityRegressionSnapshot],
    *,
    now: datetime | None = None,
    suspicious_hiring_drop_ratio: float = SUSPICIOUS_HIRING_DROP_RATIO,
    min_previous_hiring_count: int = MIN_PREVIOUS_HIRING_COUNT_FOR_DROP,
    source_dominance_ratio: float = SOURCE_DOMINANCE_WARNING_RATIO,
    low_confidence_score_weight_ratio: float = LOW_CONFIDENCE_SCORE_WEIGHT_RATIO,
    repeated_refresh_failure_threshold: int = REPEATED_REFRESH_FAILURE_THRESHOLD,
) -> list[QualityRegressionRecord]:
    """Return deterministic quality regressions for supplied snapshots."""

    checked_at = _checked_at(now)
    regressions: list[QualityRegressionRecord] = []
    for snapshot in snapshots:
        regressions.extend(
            _source_disappeared_regression(snapshot)
        )
        hiring_drop = hiring_count_drop_ratio(
            snapshot.previous_hiring_count,
            snapshot.current_hiring_count,
        )
        if (
            hiring_drop is not None
            and snapshot.previous_hiring_count is not None
            and snapshot.previous_hiring_count >= min_previous_hiring_count
            and hiring_drop >= suspicious_hiring_drop_ratio
        ):
            regressions.append(
                _record(
                    snapshot,
                    QualityRegressionType.SUSPICIOUS_HIRING_COUNT_DROP,
                    severity=QualitySeverity.HIGH,
                    explanation=(
                        "Hiring count dropped sharply enough to require review."
                    ),
                    evidence_values={
                        "previous_hiring_count": snapshot.previous_hiring_count,
                        "current_hiring_count": snapshot.current_hiring_count,
                        "drop_ratio": hiring_drop,
                    },
                    old_value=snapshot.previous_hiring_count,
                    current_value=snapshot.current_hiring_count,
                    recommended_action=(
                        "Review source evidence before treating the hiring drop as real."
                    ),
                )
            )

        if _presence_was_contradicted(snapshot):
            regressions.append(
                _record(
                    snapshot,
                    QualityRegressionType.COMPANY_REGION_PRESENCE_CONTRADICTED,
                    severity=QualitySeverity.HIGH,
                    explanation=(
                        "Company-region presence moved from present to an "
                        "uncertain or contrary status."
                    ),
                    evidence_values={
                        "previous_presence_status": snapshot.previous_presence_status,
                        "current_presence_status": snapshot.current_presence_status,
                    },
                    old_value=snapshot.previous_presence_status,
                    current_value=snapshot.current_presence_status,
                    recommended_action=(
                        "Human reviewer should compare presence evidence before "
                        "accepting the contradiction."
                    ),
                )
            )

        if _entry_level_signal_stale(snapshot, now=checked_at):
            regressions.append(
                _record(
                    snapshot,
                    QualityRegressionType.ENTRY_LEVEL_SIGNAL_BECAME_STALE,
                    severity=QualitySeverity.MEDIUM,
                    explanation="Entry-level signal freshness has expired.",
                    evidence_values={
                        "entry_level_freshness_expires_at": (
                            snapshot.entry_level_freshness_expires_at.isoformat()
                            if snapshot.entry_level_freshness_expires_at
                            else None
                        )
                    },
                    old_value=snapshot.old_value,
                    current_value=snapshot.current_value,
                    recommended_action=(
                        "Queue human-reviewed entry-level source refresh before "
                        "trusting this signal."
                    ),
                )
            )

        dominant = dominant_source_weight(snapshot.market_score_source_weights)
        if dominant is not None:
            source_ref, weight = dominant
            if weight >= source_dominance_ratio:
                regressions.append(
                    _record(
                        snapshot,
                        QualityRegressionType.SINGLE_SOURCE_DOMINATES_MARKET_SCORE,
                        severity=QualitySeverity.MEDIUM,
                        explanation=(
                            "One source contributes too much of the market score "
                            "evidence weight."
                        ),
                        evidence_values={
                            "dominant_source_ref": source_ref,
                            "dominant_source_weight": weight,
                            "threshold": source_dominance_ratio,
                        },
                        old_value=snapshot.old_value,
                        current_value=snapshot.current_value,
                        recommended_action=(
                            "Add or review independent source evidence before "
                            "using the score confidently."
                        ),
                    )
                )

        low_confidence_weight = snapshot.market_score_low_confidence_weight
        if (
            low_confidence_weight is not None
            and low_confidence_weight >= low_confidence_score_weight_ratio
        ):
            regressions.append(
                _record(
                    snapshot,
                    QualityRegressionType.MARKET_SCORE_LOW_CONFIDENCE_OVERRELIANCE,
                    severity=QualitySeverity.HIGH,
                    explanation=(
                        "Market score evidence relies too heavily on "
                        "low-confidence facts."
                    ),
                    evidence_values={
                        "low_confidence_weight": low_confidence_weight,
                        "threshold": low_confidence_score_weight_ratio,
                    },
                    old_value=snapshot.old_value,
                    current_value=snapshot.current_value,
                    recommended_action=(
                        "Human reviewer should improve source confidence before "
                        "trusting this market score."
                    ),
                )
            )

        gap_delta = coverage_gap_delta(
            snapshot.previous_coverage_gap_count,
            snapshot.current_coverage_gap_count,
        )
        if gap_delta is not None and gap_delta > 0:
            regressions.append(
                _record(
                    snapshot,
                    QualityRegressionType.COVERAGE_GAP_WORSENED,
                    severity=QualitySeverity.HIGH
                    if gap_delta >= 3
                    else QualitySeverity.MEDIUM,
                    explanation="Coverage gap count increased.",
                    evidence_values={
                        "previous_coverage_gap_count": (
                            snapshot.previous_coverage_gap_count
                        ),
                        "current_coverage_gap_count": (
                            snapshot.current_coverage_gap_count
                        ),
                        "gap_delta": gap_delta,
                    },
                    old_value=snapshot.previous_coverage_gap_count,
                    current_value=snapshot.current_coverage_gap_count,
                    recommended_action=(
                        "Review missing coverage areas and queue manual refresh "
                        "work where appropriate."
                    ),
                )
            )

        if snapshot.refresh_failure_count >= repeated_refresh_failure_threshold:
            regressions.append(
                _record(
                    snapshot,
                    QualityRegressionType.REPEATED_REFRESH_FAILURE,
                    severity=QualitySeverity.HIGH,
                    explanation="Refresh has failed repeatedly for this entity.",
                    evidence_values={
                        "refresh_failure_count": snapshot.refresh_failure_count,
                        "threshold": repeated_refresh_failure_threshold,
                    },
                    old_value=snapshot.old_value,
                    current_value=snapshot.current_value,
                    recommended_action=(
                        "Pause automation assumptions and require human review "
                        "of the failure history."
                    ),
                )
            )

    return sorted(regressions, key=lambda regression: regression.regression_id)


def _source_disappeared_regression(
    snapshot: QualityRegressionSnapshot,
) -> list[QualityRegressionRecord]:
    missing = disappeared_source_refs(
        snapshot.previous_source_refs,
        snapshot.current_source_refs,
    )
    if not missing:
        return []
    severity = (
        QualitySeverity.HIGH
        if snapshot.previous_source_refs and not snapshot.current_source_refs
        else QualitySeverity.MEDIUM
    )
    return [
        _record(
            snapshot,
            QualityRegressionType.SOURCE_DISAPPEARED,
            severity=severity,
            explanation="Previously attached source evidence is no longer present.",
            evidence_values={
                "previous_source_refs": list(snapshot.previous_source_refs),
                "current_source_refs": list(snapshot.current_source_refs),
                "disappeared_source_refs": list(missing),
            },
            old_value=list(snapshot.previous_source_refs),
            current_value=list(snapshot.current_source_refs),
            recommended_action=(
                "Human reviewer should determine whether the source was removed, "
                "renamed, or contradicted before trusting the fact."
            ),
        )
    ]


def _presence_was_contradicted(snapshot: QualityRegressionSnapshot) -> bool:
    previous = (snapshot.previous_presence_status or "").strip().lower()
    current = (snapshot.current_presence_status or "").strip().lower()
    return previous == "present" and current in {"not_present", "uncertain"}


def _entry_level_signal_stale(
    snapshot: QualityRegressionSnapshot,
    *,
    now: datetime,
) -> bool:
    expires_at = snapshot.entry_level_freshness_expires_at
    if expires_at is None:
        return False
    return evaluate_freshness(expires_at, now=now) is FreshnessStatus.STALE


def _record(
    snapshot: QualityRegressionSnapshot,
    regression_type: QualityRegressionType,
    *,
    severity: QualitySeverity,
    explanation: str,
    evidence_values: dict,
    old_value,
    current_value,
    recommended_action: str,
) -> QualityRegressionRecord:
    combined_evidence = dict(snapshot.evidence_values)
    combined_evidence.update(evidence_values)
    return QualityRegressionRecord(
        regression_id=stable_quality_regression_id(
            entity_type=snapshot.entity_type,
            entity_id=snapshot.entity_id,
            regression_type=regression_type,
        ),
        entity_type=snapshot.entity_type,
        entity_id=snapshot.entity_id,
        regression_type=regression_type,
        severity=severity,
        explanation=explanation,
        evidence_values=combined_evidence,
        old_value=old_value,
        current_value=current_value,
        recommended_action=recommended_action,
        human_review_required=True,
    )


def _checked_at(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now


__all__ = ["detect_quality_regressions"]
