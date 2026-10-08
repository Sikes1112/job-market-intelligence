"""Public Platform API mapping service for Layer 20A."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.data_standards.ranking_gate import ranking_eligible_fact_ids
from backend.geography.repository import RegionRepository
from backend.hiring.models import CompanyRegionHiring
from backend.outputs.models import OutputMetadata
from backend.outputs.payloads import (
    CompanyOutput,
    ComparisonOutput,
    OutputPayloadMetadata,
    RegionOutput,
    RegionScoresPayload,
)
from backend.outputs.service import OutputAssemblyService
from backend.platform.product_catalog import PlatformApiProductId
from backend.platform.public_api_payloads import (
    PublicApiConfidenceMetadata,
    PublicApiEnvelope,
    PublicApiFreshnessMetadata,
    PublicApiSourceSummary,
    PublicApiWarning,
    PublicCompanyGeographyPayload,
    PublicCompanyRegionGeography,
    PublicComparisonRegion,
    PublicEarlyCareerAccessPayload,
    PublicHiringConcentrationMarket,
    PublicHiringConcentrationPayload,
    PublicMarketComparisonPayload,
    PublicRegionMarketSummary,
    PublicRegionScoresPayload,
    PublicScoreComparison,
    PublicScoreSet,
    build_public_api_envelope,
)
from backend.shared.confidence import Confidence

_PUBLIC_SCORE_FIELDS: tuple[tuple[str, str], ...] = (
    ("objective_opportunity_score", "opportunity"),
    ("structural_ecosystem_score", "structural_ecosystem"),
    ("live_market_score", "live_market"),
    ("general_density_score", "general_density"),
    ("tech_market_density_score", "tech_market_density"),
    ("early_career_accessibility_score", "early_career_access"),
)

_SOURCE_CATEGORY_LABELS = {
    "region_version": "region identity",
    "region_versions": "region identity",
    "region_market_score_version": "region score summary",
    "company_version": "company identity",
    "company_versions": "company summaries",
    "presence_versions": "company-region presence summaries",
    "hiring_versions": "company-region hiring summaries",
    "entry_level_versions": "early-career access summaries",
    "region_a": "comparison region summary",
    "region_b": "comparison region summary",
}


@dataclass(slots=True)
class _MergedCompanyRegion:
    region_id: str
    region_name: str
    presence_status: str | None = None
    current_hiring: bool = False
    active_posting_count: int | None = None
    has_early_career_access: bool = False
    early_career_access_score: float | None = None
    coverage_tier: str = "unknown"
    coverage_label: str = "Coverage unavailable"
    coverage_quality: float | None = None


@dataclass(slots=True)
class _HiringMarketAggregate:
    region_id: str
    region_name: str
    currently_hiring_company_ids: set[str]
    active_values: list[int]
    posting_30d_values: list[int]
    posting_90d_values: list[int]


class PlatformPublicApiService:
    def __init__(
        self,
        *,
        session: Session,
        output_service: OutputAssemblyService,
    ) -> None:
        self._session = session
        self._output_service = output_service

    def region_scores(self, region_id: str) -> PublicApiEnvelope:
        result = self._output_service.read_region(region_id)
        payload = result.payload
        region = payload.region
        data = PublicRegionScoresPayload(
            region_id=region.region_id,
            region_name=region.display_name,
            region_type=region.region_type,
            scores=_public_scores(region.scores),
            market_summary=PublicRegionMarketSummary(
                present_company_count=region.summary.present_company_count,
                currently_hiring_company_count=(
                    region.summary.currently_hiring_company_count
                ),
                early_career_signal_count=(
                    region.entry_level_summary.pairs_with_entry_level_access
                ),
            ),
            coverage_tier=_coverage_tier(region.coverage),
            coverage_label=_coverage_label(region.coverage),
        )
        return _envelope_for_output(
            product_id=PlatformApiProductId.REGION_SCORES,
            data=data,
            output=payload,
            row=result.metadata,
            coverage=region.coverage,
        )

    def company_geography(self, company_id: str) -> PublicApiEnvelope:
        result = self._output_service.read_company(company_id)
        payload = result.payload
        company = payload.company
        merged = _merge_company_regions(payload)
        regions = tuple(
            PublicCompanyRegionGeography(
                region_id=item.region_id,
                region_name=item.region_name,
                presence_status=item.presence_status,
                current_hiring=item.current_hiring,
                active_posting_count=item.active_posting_count,
                has_early_career_access=item.has_early_career_access,
                early_career_access_score=item.early_career_access_score,
                coverage_tier=item.coverage_tier,
                coverage_label=item.coverage_label,
            )
            for item in merged
        )
        data = PublicCompanyGeographyPayload(
            company_id=company.company_id,
            company_name=company.company_name,
            sector=company.sector_primary,
            regions=regions,
            region_count=len(regions),
        )
        return _envelope_for_output(
            product_id=PlatformApiProductId.COMPANY_GEOGRAPHY,
            data=data,
            output=payload,
            row=result.metadata,
            coverage_quality=_average_quality(item.coverage_quality for item in merged),
        )

    def early_career_access(self, region_id: str) -> PublicApiEnvelope:
        result = self._output_service.read_region(region_id)
        payload = result.payload
        region = payload.region
        entry = region.entry_level_summary
        data = PublicEarlyCareerAccessPayload(
            region_id=region.region_id,
            region_name=region.display_name,
            early_career_access_score=(
                region.scores.early_career_accessibility_score
                if region.scores is not None
                else None
            ),
            internship_count=entry.internship_count_total,
            coop_count=entry.coop_count_total,
            entry_level_full_time_count=entry.entry_level_full_time_count_total,
            formal_early_career_program_count=(
                entry.formal_early_career_program_count
            ),
            company_pairs_with_access=entry.pairs_with_entry_level_access,
            coverage_tier=_coverage_tier(region.coverage),
            coverage_label=_coverage_label(region.coverage),
        )
        return _envelope_for_output(
            product_id=PlatformApiProductId.EARLY_CAREER_ACCESS,
            data=data,
            output=payload,
            row=result.metadata,
            coverage=region.coverage,
        )

    def hiring_concentration(self, *, limit: int = 50) -> PublicApiEnvelope:
        rows = list(
            self._session.execute(
                select(CompanyRegionHiring).order_by(
                    CompanyRegionHiring.region_id,
                    CompanyRegionHiring.company_id,
                )
            ).scalars()
        )
        eligible_hiring_ids = ranking_eligible_fact_ids(
            self._session,
            "company_region_hiring",
            [row.hiring_id for row in rows],
        )
        rows = [row for row in rows if row.hiring_id in eligible_hiring_ids]
        regions_by_id = {
            region.region_id: region
            for region in RegionRepository(self._session).list()
        }

        aggregates: dict[str, _HiringMarketAggregate] = {}
        for row in rows:
            region = regions_by_id.get(row.region_id)
            aggregate = aggregates.setdefault(
                row.region_id,
                _HiringMarketAggregate(
                    region_id=row.region_id,
                    region_name=region.display_name if region else row.region_id,
                    currently_hiring_company_ids=set(),
                    active_values=[],
                    posting_30d_values=[],
                    posting_90d_values=[],
                ),
            )
            if row.currently_hiring_flag:
                aggregate.currently_hiring_company_ids.add(row.company_id)
            if row.active_posting_count_now is not None:
                aggregate.active_values.append(row.active_posting_count_now)
            if row.posting_count_30d is not None:
                aggregate.posting_30d_values.append(row.posting_count_30d)
            if row.posting_count_90d is not None:
                aggregate.posting_90d_values.append(row.posting_count_90d)

        ranked = sorted(
            aggregates.values(),
            key=lambda item: (
                -(_sum_or_none(item.active_values) or 0),
                -len(item.currently_hiring_company_ids),
                item.region_id,
            ),
        )[:limit]
        total_active = _sum_or_none(
            [
                active
                for item in aggregates.values()
                for active in (
                    [_sum_or_none(item.active_values)]
                    if _sum_or_none(item.active_values) is not None
                    else []
                )
            ]
        )
        markets = tuple(
            PublicHiringConcentrationMarket(
                region_id=item.region_id,
                region_name=item.region_name,
                currently_hiring_company_count=len(item.currently_hiring_company_ids),
                active_posting_count=_sum_or_none(item.active_values),
                posting_count_30d=_sum_or_none(item.posting_30d_values),
                posting_count_90d=_sum_or_none(item.posting_90d_values),
                concentration_share=_share(
                    _sum_or_none(item.active_values),
                    total_active,
                ),
            )
            for item in ranked
        )
        data = PublicHiringConcentrationPayload(
            markets=markets,
            market_count=len(markets),
            total_active_posting_count=total_active,
        )
        warnings = ()
        if not rows:
            warnings = (
                PublicApiWarning(
                    code="hiring_data_unavailable",
                    severity="medium",
                    message="No aggregate hiring rows are available for this response.",
                ),
            )
        return build_public_api_envelope(
            product_id=PlatformApiProductId.HIRING_CONCENTRATION,
            data=data,
            freshness=PublicApiFreshnessMetadata(status="unknown"),
            confidence=_aggregate_confidence(
                has_rows=bool(rows),
                has_observed_counts=total_active is not None,
            ),
            source_summary=PublicApiSourceSummary(
                data_basis="public_safe_summary" if rows else "unknown",
                source_count=len(rows),
                source_categories=(
                    ("company-region hiring summaries", "region identity")
                    if rows
                    else ()
                ),
                notes=(
                    "Only aggregate market counts are returned.",
                    "Record identifiers and collection metadata are withheld.",
                )
                if rows
                else ("No aggregate hiring summaries were available.",),
            ),
            warnings=warnings,
            status="success" if rows else "partial",
        )

    def market_comparison(self, region_a: str, region_b: str) -> PublicApiEnvelope:
        result = self._output_service.read_comparison(region_a, region_b)
        payload = result.payload
        comparison = payload.comparison
        data = PublicMarketComparisonPayload(
            comparison_id=comparison.comparison_id,
            region_a=_public_comparison_region(comparison.region_a),
            region_b=_public_comparison_region(comparison.region_b),
            score_comparisons=_public_score_comparisons(payload),
            notes=tuple(comparison.notes),
        )
        return _envelope_for_output(
            product_id=PlatformApiProductId.MARKET_COMPARISONS,
            data=data,
            output=payload,
            row=result.metadata,
            coverage_quality=_average_quality(
                (
                    _coverage_quality(comparison.region_a.coverage),
                    _coverage_quality(comparison.region_b.coverage),
                )
            ),
        )


def _envelope_for_output(
    *,
    product_id: PlatformApiProductId,
    data: Any,
    output: RegionOutput | CompanyOutput | ComparisonOutput,
    row: OutputMetadata | None,
    coverage: Any | None = None,
    coverage_quality: float | None = None,
) -> PublicApiEnvelope:
    metadata = output.metadata
    status = "partial" if metadata.state in {"partial", "stale"} else "success"
    return build_public_api_envelope(
        product_id=product_id,
        data=data,
        freshness=_freshness(metadata, row),
        confidence=_confidence(
            state=metadata.state,
            coverage=coverage,
            coverage_quality=coverage_quality,
        ),
        source_summary=_source_summary(metadata),
        warnings=_warnings(metadata),
        status=status,
    )


def _public_scores(scores: RegionScoresPayload | None) -> PublicScoreSet:
    if scores is None:
        return PublicScoreSet()
    values: dict[str, float | None] = {}
    for source_key, public_key in _PUBLIC_SCORE_FIELDS:
        values[public_key] = getattr(scores, source_key, None)
    return PublicScoreSet(**values)


def _merge_company_regions(payload: CompanyOutput) -> tuple[_MergedCompanyRegion, ...]:
    merged: dict[str, _MergedCompanyRegion] = {}

    def _region(region_id: str, region_name: str, coverage: Any) -> _MergedCompanyRegion:
        item = merged.get(region_id)
        if item is None:
            item = _MergedCompanyRegion(
                region_id=region_id,
                region_name=region_name,
                coverage_tier=_coverage_tier(coverage),
                coverage_label=_coverage_label(coverage),
                coverage_quality=_coverage_quality(coverage),
            )
            merged[region_id] = item
        return item

    for presence in payload.company.regions_present:
        item = _region(
            presence.region_id,
            presence.region_display_name,
            presence.coverage,
        )
        item.presence_status = presence.presence_status
    for hiring in payload.company.regions_hiring:
        item = _region(hiring.region_id, hiring.region_display_name, hiring.coverage)
        item.current_hiring = hiring.currently_hiring_flag
        item.active_posting_count = hiring.active_posting_count_now
    for entry in payload.company.entry_level_regions:
        item = _region(entry.region_id, entry.region_display_name, entry.coverage)
        item.has_early_career_access = (
            entry.entry_level_access_score is not None
            and entry.entry_level_access_score > 0
        )
        item.early_career_access_score = entry.entry_level_access_score

    return tuple(merged[region_id] for region_id in sorted(merged))


def _public_comparison_region(side: Any) -> PublicComparisonRegion:
    return PublicComparisonRegion(
        region_id=side.region_id,
        region_name=side.display_name,
        scores=_public_scores(side.scores),
        coverage_tier=_coverage_tier(side.coverage),
        coverage_label=_coverage_label(side.coverage),
    )


def _public_score_comparisons(
    payload: ComparisonOutput,
) -> tuple[PublicScoreComparison, ...]:
    comparison = payload.comparison
    rows: list[PublicScoreComparison] = []
    for source_key, public_key in _PUBLIC_SCORE_FIELDS:
        a_value = (
            getattr(comparison.region_a.scores, source_key)
            if comparison.region_a.scores is not None
            else None
        )
        b_value = (
            getattr(comparison.region_b.scores, source_key)
            if comparison.region_b.scores is not None
            else None
        )
        if a_value is None and b_value is None:
            continue
        rows.append(
            PublicScoreComparison(
                key=public_key,
                region_a_value=a_value,
                region_b_value=b_value,
                winner_region_id=comparison.category_winners.get(source_key),
            )
        )
    return tuple(rows)


def _freshness(
    metadata: OutputPayloadMetadata,
    row: OutputMetadata | None,
) -> PublicApiFreshnessMetadata:
    expires_at = _ensure_aware_or_none(metadata.freshness_expires_at)
    last_updated_at = _ensure_aware_or_none(row.updated_at if row is not None else None)
    if metadata.state == "partial":
        status = "partial"
    elif metadata.state == "stale":
        status = "stale"
    elif expires_at is None:
        status = "unknown"
    elif expires_at <= datetime.now(UTC):
        status = "stale"
    else:
        status = "fresh"
    return PublicApiFreshnessMetadata(
        status=status,
        freshness_expires_at=expires_at,
        last_updated_at=last_updated_at,
    )


def _confidence(
    *,
    state: str,
    coverage: Any | None = None,
    coverage_quality: float | None = None,
) -> PublicApiConfidenceMetadata:
    if state == "stale":
        return PublicApiConfidenceMetadata(
            level=Confidence.LOW,
            label="Low confidence because freshness is stale",
            basis="output_state",
        )
    if state == "partial":
        return PublicApiConfidenceMetadata(
            level=Confidence.LOW,
            label="Low confidence because the output is partial",
            basis="output_state",
        )
    quality = coverage_quality if coverage_quality is not None else _coverage_quality(coverage)
    if quality is None:
        return PublicApiConfidenceMetadata(
            level=Confidence.UNKNOWN,
            label="Confidence unknown",
            basis="unknown",
        )
    if quality >= 75:
        level = Confidence.HIGH
        label = "High confidence coverage"
    elif quality >= 40:
        level = Confidence.MEDIUM
        label = "Medium confidence coverage"
    else:
        level = Confidence.LOW
        label = "Low confidence coverage"
    return PublicApiConfidenceMetadata(
        level=level,
        label=label,
        basis="coverage_quality",
    )


def _aggregate_confidence(
    *,
    has_rows: bool,
    has_observed_counts: bool,
) -> PublicApiConfidenceMetadata:
    if not has_rows:
        return PublicApiConfidenceMetadata(
            level=Confidence.UNKNOWN,
            label="Confidence unknown",
            basis="unknown",
        )
    if has_observed_counts:
        return PublicApiConfidenceMetadata(
            level=Confidence.MEDIUM,
            label="Medium confidence aggregate counts",
            basis="aggregate_counts",
        )
    return PublicApiConfidenceMetadata(
        level=Confidence.LOW,
        label="Low confidence aggregate counts",
        basis="aggregate_counts",
    )


def _source_summary(metadata: OutputPayloadMetadata) -> PublicApiSourceSummary:
    categories: list[str] = []
    source_count = 0
    for key, value in metadata.source_versions.items():
        label = _SOURCE_CATEGORY_LABELS.get(key)
        count = _public_source_count(value)
        if count <= 0:
            continue
        source_count += count
        if label and label not in categories:
            categories.append(label)
    return PublicApiSourceSummary(
        data_basis="public_safe_summary" if source_count else "unknown",
        source_count=source_count,
        source_categories=tuple(categories),
        notes=(
            "Only summarized public product categories are returned.",
            "Record identifiers and collection metadata are withheld.",
        )
        if source_count
        else ("No summarized source categories are available.",),
    )


def _public_source_count(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, dict):
        if all(not isinstance(child, dict) for child in value.values()):
            return 1 if any(child is not None for child in value.values()) else 0
        return sum(_public_source_count(child) for child in value.values())
    if isinstance(value, list | tuple | set):
        return len(value)
    return 1


def _warnings(metadata: OutputPayloadMetadata) -> tuple[PublicApiWarning, ...]:
    public: list[PublicApiWarning] = []
    for warning in metadata.warnings:
        severity = getattr(warning.severity, "value", warning.severity)
        public.append(
            PublicApiWarning(
                code=warning.warning_code,
                severity=_warning_severity(str(severity)),
                message=warning.message,
            )
        )
    return tuple(public)


def _warning_severity(value: str) -> str:
    if value in {"info", "low", "medium", "high"}:
        return value
    return "medium"


def _coverage_tier(coverage: Any) -> str:
    value = getattr(coverage, "coverage_tier", None) or getattr(coverage, "tier", None)
    return _enum_value(value) or "unknown"


def _coverage_label(coverage: Any) -> str:
    value = getattr(coverage, "coverage_label", None) or getattr(coverage, "label", None)
    return str(value) if value else "Coverage unavailable"


def _coverage_quality(coverage: Any) -> float | None:
    value = getattr(coverage, "quality_score", None)
    if isinstance(value, bool):
        return None
    return float(value) if isinstance(value, int | float) else None


def _average_quality(values: Any) -> float | None:
    known = [float(value) for value in values if isinstance(value, int | float)]
    return sum(known) / len(known) if known else None


def _sum_or_none(values: list[int | None]) -> int | None:
    known = [value for value in values if value is not None]
    return sum(known) if known else None


def _share(value: int | None, total: int | None) -> float | None:
    if value is None or total is None or total <= 0:
        return None
    return value / total


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    enum_value = getattr(value, "value", None)
    return str(enum_value if enum_value is not None else value)


def _ensure_aware_or_none(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
