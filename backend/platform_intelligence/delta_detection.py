"""Conservative delta detection for append-only historical snapshots."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from backend.platform_intelligence.models import (
    CompanyRegionSnapshot,
    MarketSnapshot,
    SectorRegionSnapshot,
)
from backend.platform_intelligence.observations import HistoricalObservationDraft
from backend.platform_intelligence.schemas import (
    DeltaDirection,
    HistoricalObservationType,
    HistoricalTargetType,
    ObservationSeverity,
)

SCORE_DELTA_THRESHOLD = 0.05
COUNT_DELTA_THRESHOLD = 2


def detect_market_snapshot_deltas(
    previous: MarketSnapshot | None,
    current: MarketSnapshot,
) -> tuple[HistoricalObservationDraft, ...]:
    if previous is None:
        return ()
    drafts = [
        _score_delta(
            previous,
            current,
            field="overall_score",
            increase_type=HistoricalObservationType.REGIONAL_SCORE_INCREASED,
            decrease_type=HistoricalObservationType.REGIONAL_SCORE_DECREASED,
            target_type=HistoricalTargetType.REGION,
            target_id=current.region_id,
            region_id=current.region_id,
        ),
        _score_delta(
            previous,
            current,
            field="entry_level_access_score",
            increase_type=HistoricalObservationType.ENTRY_LEVEL_ACCESS_IMPROVED,
            decrease_type=HistoricalObservationType.ENTRY_LEVEL_ACCESS_DECLINED,
            target_type=HistoricalTargetType.REGION,
            target_id=current.region_id,
            region_id=current.region_id,
        ),
        _score_delta(
            previous,
            current,
            field="internship_density_score",
            increase_type=HistoricalObservationType.INTERNSHIP_DENSITY_CHANGED,
            decrease_type=HistoricalObservationType.INTERNSHIP_DENSITY_CHANGED,
            target_type=HistoricalTargetType.REGION,
            target_id=current.region_id,
            region_id=current.region_id,
        ),
    ]
    return _present(drafts)


def detect_company_region_snapshot_deltas(
    previous: CompanyRegionSnapshot | None,
    current: CompanyRegionSnapshot,
) -> tuple[HistoricalObservationDraft, ...]:
    if previous is None:
        return ()
    target_id = f"{current.company_id}:{current.region_id}"
    drafts: list[HistoricalObservationDraft | None] = [
        _score_delta(
            previous,
            current,
            field="company_presence_score",
            increase_type=HistoricalObservationType.COMPANY_PRESENCE_INCREASED,
            decrease_type=HistoricalObservationType.COMPANY_PRESENCE_DECREASED,
            target_type=HistoricalTargetType.COMPANY_REGION,
            target_id=target_id,
            region_id=current.region_id,
        ),
        _score_delta(
            previous,
            current,
            field="entry_level_access_score",
            increase_type=HistoricalObservationType.ENTRY_LEVEL_ACCESS_IMPROVED,
            decrease_type=HistoricalObservationType.ENTRY_LEVEL_ACCESS_DECLINED,
            target_type=HistoricalTargetType.COMPANY_REGION,
            target_id=target_id,
            region_id=current.region_id,
        ),
        _score_delta(
            previous,
            current,
            field="internship_density_score",
            increase_type=HistoricalObservationType.INTERNSHIP_DENSITY_CHANGED,
            decrease_type=HistoricalObservationType.INTERNSHIP_DENSITY_CHANGED,
            target_type=HistoricalTargetType.COMPANY_REGION,
            target_id=target_id,
            region_id=current.region_id,
        )
        or _count_delta(
            previous,
            current,
            field="internship_count",
            increase_type=HistoricalObservationType.INTERNSHIP_DENSITY_CHANGED,
            decrease_type=HistoricalObservationType.INTERNSHIP_DENSITY_CHANGED,
            target_type=HistoricalTargetType.COMPANY_REGION,
            target_id=target_id,
            region_id=current.region_id,
        ),
        _score_delta(
            previous,
            current,
            field="hiring_activity_score",
            increase_type=HistoricalObservationType.HIRING_ACTIVITY_INCREASED,
            decrease_type=HistoricalObservationType.HIRING_ACTIVITY_DECREASED,
            target_type=HistoricalTargetType.COMPANY_REGION,
            target_id=target_id,
            region_id=current.region_id,
        )
        or _count_delta(
            previous,
            current,
            field="active_posting_count",
            increase_type=HistoricalObservationType.HIRING_ACTIVITY_INCREASED,
            decrease_type=HistoricalObservationType.HIRING_ACTIVITY_DECREASED,
            target_type=HistoricalTargetType.COMPANY_REGION,
            target_id=target_id,
            region_id=current.region_id,
        )
        or _count_delta(
            previous,
            current,
            field="posting_count_30d",
            increase_type=HistoricalObservationType.HIRING_ACTIVITY_INCREASED,
            decrease_type=HistoricalObservationType.HIRING_ACTIVITY_DECREASED,
            target_type=HistoricalTargetType.COMPANY_REGION,
            target_id=target_id,
            region_id=current.region_id,
        ),
    ]
    return _present(drafts)


def detect_sector_region_snapshot_deltas(
    previous: SectorRegionSnapshot | None,
    current: SectorRegionSnapshot,
) -> tuple[HistoricalObservationDraft, ...]:
    if previous is None:
        return ()
    target_id = f"{current.sector_id}:{current.region_id}"
    drafts: list[HistoricalObservationDraft | None] = [
        _score_delta(
            previous,
            current,
            field="overall_score",
            increase_type=HistoricalObservationType.SECTOR_GROWTH_DETECTED,
            decrease_type=HistoricalObservationType.SECTOR_DECLINE_DETECTED,
            target_type=HistoricalTargetType.SECTOR_REGION,
            target_id=target_id,
            region_id=current.region_id,
        )
        or _count_delta(
            previous,
            current,
            field="sector_company_count",
            increase_type=HistoricalObservationType.SECTOR_GROWTH_DETECTED,
            decrease_type=HistoricalObservationType.SECTOR_DECLINE_DETECTED,
            target_type=HistoricalTargetType.SECTOR_REGION,
            target_id=target_id,
            region_id=current.region_id,
        )
        or _count_delta(
            previous,
            current,
            field="active_company_count",
            increase_type=HistoricalObservationType.SECTOR_GROWTH_DETECTED,
            decrease_type=HistoricalObservationType.SECTOR_DECLINE_DETECTED,
            target_type=HistoricalTargetType.SECTOR_REGION,
            target_id=target_id,
            region_id=current.region_id,
        ),
        _score_delta(
            previous,
            current,
            field="entry_level_access_score",
            increase_type=HistoricalObservationType.ENTRY_LEVEL_ACCESS_IMPROVED,
            decrease_type=HistoricalObservationType.ENTRY_LEVEL_ACCESS_DECLINED,
            target_type=HistoricalTargetType.SECTOR_REGION,
            target_id=target_id,
            region_id=current.region_id,
        ),
        _score_delta(
            previous,
            current,
            field="internship_density_score",
            increase_type=HistoricalObservationType.INTERNSHIP_DENSITY_CHANGED,
            decrease_type=HistoricalObservationType.INTERNSHIP_DENSITY_CHANGED,
            target_type=HistoricalTargetType.SECTOR_REGION,
            target_id=target_id,
            region_id=current.region_id,
        ),
    ]
    return _present(drafts)


def _score_delta(
    previous: Any,
    current: Any,
    *,
    field: str,
    increase_type: HistoricalObservationType,
    decrease_type: HistoricalObservationType,
    target_type: HistoricalTargetType,
    target_id: str,
    region_id: str,
) -> HistoricalObservationDraft | None:
    return _numeric_delta(
        previous,
        current,
        field=field,
        threshold=SCORE_DELTA_THRESHOLD,
        increase_type=increase_type,
        decrease_type=decrease_type,
        target_type=target_type,
        target_id=target_id,
        region_id=region_id,
        severity_fn=_score_severity,
    )


def _count_delta(
    previous: Any,
    current: Any,
    *,
    field: str,
    increase_type: HistoricalObservationType,
    decrease_type: HistoricalObservationType,
    target_type: HistoricalTargetType,
    target_id: str,
    region_id: str,
) -> HistoricalObservationDraft | None:
    return _numeric_delta(
        previous,
        current,
        field=field,
        threshold=COUNT_DELTA_THRESHOLD,
        increase_type=increase_type,
        decrease_type=decrease_type,
        target_type=target_type,
        target_id=target_id,
        region_id=region_id,
        severity_fn=_count_severity,
    )


def _numeric_delta(
    previous: Any,
    current: Any,
    *,
    field: str,
    threshold: float,
    increase_type: HistoricalObservationType,
    decrease_type: HistoricalObservationType,
    target_type: HistoricalTargetType,
    target_id: str,
    region_id: str,
    severity_fn,
) -> HistoricalObservationDraft | None:  # noqa: ANN001
    previous_value = getattr(previous, field, None)
    current_value = getattr(current, field, None)
    if previous_value is None or current_value is None:
        return None

    delta = float(current_value) - float(previous_value)
    if abs(delta) < threshold:
        return None

    direction = DeltaDirection.INCREASED if delta > 0 else DeltaDirection.DECREASED
    observation_type = increase_type if delta > 0 else decrease_type
    return HistoricalObservationDraft(
        observation_type=observation_type,
        target_type=target_type,
        target_id=target_id,
        region_id=region_id,
        previous_snapshot_id=_snapshot_id(previous),
        current_snapshot_id=_snapshot_id(current),
        delta_value=delta,
        delta_direction=direction,
        severity=severity_fn(abs(delta)),
        confidence_score=_conservative_confidence(previous, current),
        evidence_summary={
            "field": field,
            "previous_value": previous_value,
            "current_value": current_value,
            "threshold": threshold,
            "previous_snapshot_date": str(previous.snapshot_date),
            "current_snapshot_date": str(current.snapshot_date),
        },
    )


def _score_severity(abs_delta: float) -> ObservationSeverity:
    if abs_delta >= 0.20:
        return ObservationSeverity.HIGH
    if abs_delta >= 0.10:
        return ObservationSeverity.MEDIUM
    return ObservationSeverity.LOW


def _count_severity(abs_delta: float) -> ObservationSeverity:
    if abs_delta >= 20:
        return ObservationSeverity.HIGH
    if abs_delta >= 5:
        return ObservationSeverity.MEDIUM
    return ObservationSeverity.LOW


def _conservative_confidence(previous: Any, current: Any) -> float | None:
    values = [
        value
        for value in (
            getattr(previous, "confidence_score", None),
            getattr(current, "confidence_score", None),
        )
        if value is not None
    ]
    if not values:
        return None
    return min(float(value) for value in values)


def _snapshot_id(snapshot: Any) -> str:
    for field in (
        "market_snapshot_id",
        "company_region_snapshot_id",
        "sector_region_snapshot_id",
    ):
        value = getattr(snapshot, field, None)
        if value is not None:
            return str(value)
    raise ValueError("unsupported snapshot object")


def _present(
    drafts: Iterable[HistoricalObservationDraft | None],
) -> tuple[HistoricalObservationDraft, ...]:
    return tuple(draft for draft in drafts if draft is not None)
