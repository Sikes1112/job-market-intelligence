"""Producer-owned exports from Layer 18 history into Layer 21 observations."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from backend.platform_intelligence.history_repository import HistoryRepository
from backend.predictive.contracts import (
    HistoricalMetricObservation,
    PredictiveEntityType,
    PredictiveMetric,
)


def export_predictive_observations(
    repository: HistoryRepository,
    *,
    region_ids: Iterable[str] = (),
    company_ids: Iterable[str] = (),
    limit_per_subject: int = 500,
) -> tuple[HistoricalMetricObservation, ...]:
    """Return API-safe neutral observations for Layer 21 report generation."""

    observations: list[HistoricalMetricObservation] = []
    seen: set[tuple[str, str, str, str, float]] = set()

    for region_id in _unique_clean(region_ids):
        for snapshot in repository.list_market_snapshots(region_id, limit=limit_per_subject):
            _extend_unique(observations, seen, _market_observations(snapshot))
        for snapshot in repository.list_sector_region_snapshots(
            region_id,
            limit=limit_per_subject,
        ):
            _extend_unique(observations, seen, _sector_observations(snapshot))
        for snapshot in repository.list_company_region_snapshots_for_region(
            region_id,
            limit=limit_per_subject,
        ):
            _extend_unique(observations, seen, _company_region_observations(snapshot))

    for company_id in _unique_clean(company_ids):
        for snapshot in repository.list_company_region_snapshots(
            company_id,
            limit=limit_per_subject,
        ):
            _extend_unique(observations, seen, _company_region_observations(snapshot))

    return tuple(
        sorted(
            observations,
            key=lambda row: (
                row.entity_type.value,
                row.entity_id,
                row.metric.value,
                row.observed_at,
                row.value,
            ),
        )
    )


def _market_observations(snapshot: Any) -> tuple[HistoricalMetricObservation, ...]:
    return tuple(
        _observation(
            snapshot,
            entity_type=PredictiveEntityType.REGION,
            entity_id=snapshot.region_id,
            metric=metric,
            value=value,
            region_id=snapshot.region_id,
            source_categories=("market_snapshot", "historical_export"),
        )
        for metric, value in (
            (PredictiveMetric.REGIONAL_SCORE, snapshot.overall_score),
            (PredictiveMetric.ENTRY_LEVEL_ACCESS, snapshot.entry_level_access_score),
            (PredictiveMetric.INTERNSHIP_DENSITY, snapshot.internship_density_score),
            (PredictiveMetric.AI_OPPORTUNITY, snapshot.ai_opportunity_score),
            (PredictiveMetric.PRODUCT_OPPORTUNITY, snapshot.product_opportunity_score),
            (PredictiveMetric.HIDDEN_OPPORTUNITY, snapshot.hidden_opportunity_score),
        )
        if value is not None
    )


def _sector_observations(snapshot: Any) -> tuple[HistoricalMetricObservation, ...]:
    rows = [
        _observation(
            snapshot,
            entity_type=PredictiveEntityType.SECTOR_REGION,
            entity_id=f"{snapshot.sector_id}:{snapshot.region_id}",
            metric=PredictiveMetric.SECTOR_GROWTH,
            value=_first_present(snapshot.overall_score, snapshot.hiring_activity_score),
            region_id=snapshot.region_id,
            sector_id=snapshot.sector_id,
            source_categories=("sector_region_snapshot", "historical_export"),
        )
    ]
    opportunity_metric = _sector_opportunity_metric(snapshot.sector_id)
    if opportunity_metric is not None:
        rows.append(
            _observation(
                snapshot,
                entity_type=PredictiveEntityType.REGION,
                entity_id=snapshot.region_id,
                metric=opportunity_metric,
                value=_first_present(snapshot.overall_score, snapshot.hiring_activity_score),
                region_id=snapshot.region_id,
                sector_id=snapshot.sector_id,
                source_categories=("sector_region_snapshot", "historical_export"),
            )
        )
    return tuple(row for row in rows if row is not None)


def _company_region_observations(snapshot: Any) -> tuple[HistoricalMetricObservation, ...]:
    entity_id = f"{snapshot.company_id}:{snapshot.region_id}"
    return tuple(
        _observation(
            snapshot,
            entity_type=PredictiveEntityType.COMPANY_REGION,
            entity_id=entity_id,
            metric=metric,
            value=value,
            region_id=snapshot.region_id,
            company_id=snapshot.company_id,
            source_categories=("company_region_snapshot", "historical_export"),
        )
        for metric, value in (
            (PredictiveMetric.COMPANY_EXPANSION, snapshot.company_presence_score),
            (
                PredictiveMetric.HIRING_ACTIVITY,
                _first_present(snapshot.hiring_activity_score, snapshot.active_posting_count),
            ),
            (PredictiveMetric.ENTRY_LEVEL_ACCESS, snapshot.entry_level_access_score),
            (
                PredictiveMetric.INTERNSHIP_DENSITY,
                _first_present(snapshot.internship_density_score, snapshot.internship_count),
            ),
        )
        if value is not None
    )


def _observation(
    snapshot: Any,
    *,
    entity_type: PredictiveEntityType,
    entity_id: str,
    metric: PredictiveMetric,
    value: float | int | None,
    region_id: str | None = None,
    company_id: str | None = None,
    sector_id: str | None = None,
    source_categories: tuple[str, ...],
) -> HistoricalMetricObservation | None:
    if value is None:
        return None
    return HistoricalMetricObservation(
        entity_type=entity_type,
        entity_id=entity_id,
        metric=metric,
        observed_at=snapshot.snapshot_date,
        value=float(value),
        region_id=region_id,
        company_id=company_id,
        sector_id=sector_id,
        source_categories=source_categories,
        source_count=1,
        data_basis="producer_owned_export",
        confidence_score=snapshot.confidence_score,
        freshness_state=snapshot.freshness_state,
        coverage_tier=snapshot.coverage_tier,
    )


def _sector_opportunity_metric(sector_id: str) -> PredictiveMetric | None:
    normalized = sector_id.strip().casefold().replace("-", "_")
    if normalized in {"ai", "artificial_intelligence", "machine_learning"}:
        return PredictiveMetric.AI_OPPORTUNITY
    if normalized in {"cloud", "cloud_computing", "infrastructure"}:
        return PredictiveMetric.CLOUD_OPPORTUNITY
    if normalized in {"cyber", "cybersecurity", "security"}:
        return PredictiveMetric.CYBERSECURITY_OPPORTUNITY
    return None


def _first_present(*values: float | int | None) -> float | int | None:
    for value in values:
        if value is not None:
            return value
    return None


def _extend_unique(
    output: list[HistoricalMetricObservation],
    seen: set[tuple[str, str, str, str, float]],
    rows: Iterable[HistoricalMetricObservation | None],
) -> None:
    for row in rows:
        if row is None:
            continue
        key = (
            row.entity_type.value,
            row.entity_id,
            row.metric.value,
            row.observed_at.isoformat(),
            row.value,
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(row)


def _unique_clean(values: Iterable[str]) -> tuple[str, ...]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        stripped = value.strip()
        if not stripped or stripped in seen:
            continue
        seen.add(stripped)
        cleaned.append(stripped)
    return tuple(cleaned)
