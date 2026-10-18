"""Shared API-facing freshness and source explanation metadata.

Layer 5 uses these contracts to expose provenance/freshness summaries without
creating market facts, source facts, score facts, or provenance records.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.geography.market_coverage import (
    COVERAGE_SCORE_DIMENSIONS,
    COVERAGE_SCORE_MAX,
    COVERAGE_SCORE_MIN,
    COVERAGE_TIER_DEFINITIONS,
    PRIORITY_MARKETS,
    SECTOR_COVERAGE_DEFINITIONS,
    SECTOR_COVERAGE_LEVEL_DEFINITIONS,
    coverage_description_for_tier,
    coverage_limitations_for_tier,
)
from backend.shared.confidence import Confidence
from backend.shared.freshness import FreshnessStatus, evaluate_freshness
from backend.shared.provenance import (
    DEMO_DATA_ORIGINS,
    REAL_DATA_ORIGINS,
    DataOrigin,
    ObservationStatus,
)


class _Vocabulary(StrEnum):
    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class ApiFreshnessStatus(_Vocabulary):
    FRESH = "fresh"
    SIMULATED_CURRENT = "simulated_current"
    STALE = "stale"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    SEEDED_DEMO = "seeded_demo"


class ApiDataBasis(_Vocabulary):
    SEEDED_DEMO = "seeded_demo"
    REAL_IMPORTED = "real_imported"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class FreshnessSourceSummary(BaseModel):
    """Stable API contract for source/freshness explanation summaries."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    freshness_status: ApiFreshnessStatus = ApiFreshnessStatus.UNKNOWN
    data_basis: ApiDataBasis = ApiDataBasis.UNKNOWN
    last_collected_at: datetime | None = None
    source_count: int = Field(default=0, ge=0)
    low_confidence_warning: str | None = None

    @field_validator("last_collected_at")
    @classmethod
    def _last_collected_at_must_be_aware(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("last_collected_at must be timezone-aware")
        return value


def build_freshness_source_summary(
    source_records: Iterable[Any] = (),
    *,
    freshness_expires_at: datetime | None = None,
    partial: bool = False,
    now: datetime | None = None,
) -> FreshnessSourceSummary:
    """Map existing source evidence into the Layer 5 API summary shape.

    ``freshness_expires_at`` is intentionally used only when at least one source
    record exists. Output/cache freshness alone is not enough to claim source
    freshness for Layer 5 read contracts.
    """

    records = tuple(source_records)
    data_basis = _data_basis(records)
    source_count = _source_count(records)
    freshness_status = _freshness_status(
        records,
        data_basis=data_basis,
        source_count=source_count,
        freshness_expires_at=freshness_expires_at,
        partial=partial,
        now=now,
    )
    warning = _low_confidence_warning(
        records,
        data_basis=data_basis,
        freshness_status=freshness_status,
    )
    return FreshnessSourceSummary(
        freshness_status=freshness_status,
        data_basis=data_basis,
        last_collected_at=_last_collected_at(records),
        source_count=source_count,
        low_confidence_warning=warning,
    )


def _data_basis(records: tuple[Any, ...]) -> ApiDataBasis:
    if not records:
        return ApiDataBasis.UNKNOWN

    origins: list[DataOrigin | None] = [_data_origin(record) for record in records]
    has_demo = any(origin in DEMO_DATA_ORIGINS for origin in origins)
    has_real = any(origin in REAL_DATA_ORIGINS for origin in origins)
    has_unknown = any(
        origin is None or origin is DataOrigin.UNKNOWN_ORIGIN for origin in origins
    )

    if has_demo and not has_real and not has_unknown:
        return ApiDataBasis.SEEDED_DEMO
    if has_real and not has_demo and not has_unknown:
        return ApiDataBasis.REAL_IMPORTED
    if has_demo or has_real:
        return ApiDataBasis.MIXED
    return ApiDataBasis.UNKNOWN


def _freshness_status(
    records: tuple[Any, ...],
    *,
    data_basis: ApiDataBasis,
    source_count: int,
    freshness_expires_at: datetime | None,
    partial: bool,
    now: datetime | None,
) -> ApiFreshnessStatus:
    if source_count == 0:
        return ApiFreshnessStatus.UNKNOWN
    if partial:
        return ApiFreshnessStatus.PARTIAL
    if any(_observation_status(record) is ObservationStatus.STALE for record in records):
        return ApiFreshnessStatus.STALE
    if data_basis is ApiDataBasis.SEEDED_DEMO:
        declared_freshness = {
            value
            for record in records
            if (value := _string_attr(record, "freshness_status")) is not None
        }
        if declared_freshness & {"fresh", "current"}:
            return ApiFreshnessStatus.SIMULATED_CURRENT
        return ApiFreshnessStatus.SEEDED_DEMO
    if freshness_expires_at is None:
        return ApiFreshnessStatus.UNKNOWN

    evaluated = evaluate_freshness(_ensure_aware(freshness_expires_at), now=now)
    if evaluated is FreshnessStatus.FRESH:
        return ApiFreshnessStatus.FRESH
    if evaluated is FreshnessStatus.STALE:
        return ApiFreshnessStatus.STALE
    return ApiFreshnessStatus.UNKNOWN


def _source_count(records: tuple[Any, ...]) -> int:
    source_ids = {
        source_id
        for source_id in (_string_attr(record, "source_id") for record in records)
        if source_id is not None
    }
    if source_ids:
        return len(source_ids)

    observation_ids = {
        observation_id
        for observation_id in (
            _string_attr(record, "observation_id") for record in records
        )
        if observation_id is not None
    }
    if observation_ids:
        return len(observation_ids)
    return len(records)


def _last_collected_at(records: tuple[Any, ...]) -> datetime | None:
    collected = [
        _ensure_aware(value)
        for value in (_datetime_attr(record, "collected_at") for record in records)
        if value is not None
    ]
    return max(collected) if collected else None


def _low_confidence_warning(
    records: tuple[Any, ...],
    *,
    data_basis: ApiDataBasis,
    freshness_status: ApiFreshnessStatus,
) -> str | None:
    if data_basis is ApiDataBasis.SEEDED_DEMO:
        if freshness_status is ApiFreshnessStatus.SIMULATED_CURRENT:
            return (
                "Freshness is current only within the synthetic demonstration "
                "scenario; this is not real imported market evidence."
            )
        return "Data is seeded demo data, not real imported market evidence."
    if data_basis is ApiDataBasis.MIXED:
        return "Data basis is mixed and should be reviewed before trust."
    if data_basis is ApiDataBasis.UNKNOWN:
        return "Source evidence is unknown or incomplete."
    if freshness_status is ApiFreshnessStatus.STALE:
        return "Source freshness is stale; verify before trusting as current."
    if freshness_status is ApiFreshnessStatus.PARTIAL:
        return "Freshness/source evidence is partial."
    if freshness_status is ApiFreshnessStatus.UNKNOWN:
        return "Freshness is unknown from available source evidence."
    if any(_is_low_confidence(record) for record in records):
        return "One or more source records are low confidence."
    return None


def _data_origin(record: Any) -> DataOrigin | None:
    value = getattr(record, "data_origin", None)
    if value is None:
        return None
    if isinstance(value, DataOrigin):
        return value
    try:
        return DataOrigin(value)
    except ValueError:
        return None


def _observation_status(record: Any) -> ObservationStatus | None:
    value = getattr(record, "observation_status", None)
    if value is None:
        return None
    if isinstance(value, ObservationStatus):
        return value
    try:
        return ObservationStatus(value)
    except ValueError:
        return None


def _is_low_confidence(record: Any) -> bool:
    status = _observation_status(record)
    if status is ObservationStatus.LOW_CONFIDENCE:
        return True
    value = getattr(record, "confidence", None)
    if value is None:
        return False
    if isinstance(value, Confidence):
        confidence = value
    else:
        try:
            confidence = Confidence(value)
        except ValueError:
            return False
    return confidence in {Confidence.LOW, Confidence.UNKNOWN}


def _datetime_attr(record: Any, name: str) -> datetime | None:
    value = getattr(record, name, None)
    return value if isinstance(value, datetime) else None


def _string_attr(record: Any, name: str) -> str | None:
    value = getattr(record, name, None)
    return value if isinstance(value, str) and value else None


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def build_coverage_metadata_vocabulary() -> dict[str, Any]:
    """Stable public vocabulary for Layer 12 coverage read models."""

    return {
        "heuristic": True,
        "quality_score_bounds": {
            "min": COVERAGE_SCORE_MIN,
            "max": COVERAGE_SCORE_MAX,
        },
        "score_components": list(COVERAGE_SCORE_DIMENSIONS),
        "coverage_tiers": [
            {
                "tier": definition.tier.value,
                "label": definition.label,
                "meaning": definition.meaning,
                "coverage_description": coverage_description_for_tier(
                    definition.tier
                ),
                "coverage_limitations": coverage_limitations_for_tier(
                    definition.tier
                ),
                "required_conditions": list(definition.required_conditions),
                "safe_for_confident_market_comparison": (
                    definition.safe_for_confident_market_comparison
                ),
                "directionally_useful_for_comparison": (
                    definition.directionally_useful_for_comparison
                ),
                "requires_partial_label": definition.requires_partial_label,
                "should_rank_as_confident_recommendation": (
                    definition.should_rank_as_confident_recommendation
                ),
            }
            for definition in COVERAGE_TIER_DEFINITIONS.values()
        ],
        "sector_coverage_categories": [
            {
                "sector": definition.sector.value,
                "label": definition.label,
            }
            for definition in SECTOR_COVERAGE_DEFINITIONS.values()
        ],
        "sector_coverage_levels": [
            {
                "level": definition.level.value,
                "label": definition.label,
                "meaning": definition.meaning,
                "can_be_inferred_from_missing_evidence": (
                    definition.can_be_inferred_from_missing_evidence
                ),
                "can_be_displayed_as_strong": definition.can_be_displayed_as_strong,
            }
            for definition in SECTOR_COVERAGE_LEVEL_DEFINITIONS.values()
        ],
        "priority_markets": [
            market.model_dump(mode="json") for market in PRIORITY_MARKETS
        ],
    }
