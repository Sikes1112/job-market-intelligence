"""Historical observation construction for Layer 18A."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from backend.platform_intelligence.models import HistoricalObservation
from backend.platform_intelligence.schemas import (
    DeltaDirection,
    HistoricalObservationType,
    HistoricalTargetType,
    ObservationSeverity,
)


@dataclass(frozen=True, slots=True)
class HistoricalObservationDraft:
    observation_type: HistoricalObservationType
    target_type: HistoricalTargetType
    target_id: str
    region_id: str | None
    previous_snapshot_id: str | None
    current_snapshot_id: str
    delta_value: float | None
    delta_direction: DeltaDirection
    severity: ObservationSeverity
    confidence_score: float | None
    evidence_summary: dict[str, Any]


def make_historical_observation(
    draft: HistoricalObservationDraft,
    *,
    created_at: datetime | None = None,
) -> HistoricalObservation:
    created_at = created_at or datetime.now(UTC)
    if created_at.tzinfo is None:
        raise ValueError("created_at must be timezone-aware")
    return HistoricalObservation(
        historical_observation_id=_new_id("historical_observation"),
        observation_type=draft.observation_type.value,
        target_type=draft.target_type.value,
        target_id=draft.target_id,
        region_id=draft.region_id,
        previous_snapshot_id=draft.previous_snapshot_id,
        current_snapshot_id=draft.current_snapshot_id,
        delta_value=draft.delta_value,
        delta_direction=draft.delta_direction.value,
        severity=draft.severity.value,
        confidence_score=draft.confidence_score,
        evidence_summary=draft.evidence_summary,
        created_at=created_at,
    )


def _new_id(prefix: str) -> str:
    suffix_length = max(8, 63 - len(prefix))
    return f"{prefix}_{uuid4().hex[:suffix_length]}"
