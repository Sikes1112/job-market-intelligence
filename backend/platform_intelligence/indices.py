"""Versioned proprietary market indices for Layer 18B."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

from backend.platform_intelligence.history_repository import HistoryRepository
from backend.platform_intelligence.models import (
    CompanyRegionSnapshot,
    HistoricalObservation,
    MarketIndex,
    MarketIndexInput,
    MarketIndexScore,
    MarketIndexVersion,
    MarketSnapshot,
    SectorRegionSnapshot,
)
from backend.platform_intelligence.schemas import (
    MarketIndexInputCreate,
    MarketIndexScoreCreate,
    MarketIndexScoresResponse,
    MarketIndexScoreSummary,
    MarketIndexStatus,
    MarketIndexSummary,
    MarketIndexVersionCreate,
    MarketIndexVersionStatus,
)

DEFAULT_INDEX_VERSION = "2026.06"


@dataclass(frozen=True, slots=True)
class IndexDefinition:
    key: str
    name: str
    description: str
    formula_description: str
    input_schema: dict[str, Any]
    internal_weight_config: dict[str, float]


@dataclass(frozen=True, slots=True)
class _IndexCalculation:
    region_id: str
    score: float
    confidence_score: float | None
    freshness_state: str | None
    evidence_summary: dict[str, Any]
    inputs: tuple[MarketIndexInputCreate, ...]


REQUIRED_INDEX_DEFINITIONS: tuple[IndexDefinition, ...] = (
    IndexDefinition(
        key="early_career_tech_access",
        name="Early-Career Tech Access Index",
        description="Measures accessible early-career technology opportunity by region.",
        formula_description=(
            "Blends available entry-level access, internship density, company "
            "presence quality, freshness, confidence, and coverage warnings."
        ),
        input_schema={
            "entry_level_access_score": "optional 0-1 historical score",
            "internship_density_score": "optional 0-1 historical score",
            "company_presence_score": "optional 0-1 historical score",
        },
        internal_weight_config={
            "entry_level_access_score": 0.45,
            "internship_density_score": 0.25,
            "company_presence_score": 0.20,
            "confidence_score": 0.10,
        },
    ),
    IndexDefinition(
        key="ai_opportunity_geography",
        name="AI Opportunity Geography Index",
        description="Measures regional AI opportunity strength from available evidence.",
        formula_description=(
            "Blends available AI opportunity score, AI sector-region evidence, "
            "entry-level access, freshness, confidence, and coverage warnings."
        ),
        input_schema={
            "ai_opportunity_score": "optional 0-1 historical score",
            "ai_sector_score": "optional 0-1 sector-region score",
            "entry_level_access_score": "optional 0-1 historical score",
        },
        internal_weight_config={
            "ai_opportunity_score": 0.50,
            "ai_sector_score": 0.30,
            "entry_level_access_score": 0.10,
            "confidence_score": 0.10,
        },
    ),
    IndexDefinition(
        key="internship_density",
        name="Internship Density Index",
        description="Measures internship opportunity concentration and quality by region.",
        formula_description=(
            "Blends available internship density, internship-related observations, "
            "entry-level access, freshness, confidence, and coverage warnings."
        ),
        input_schema={
            "internship_density_score": "optional 0-1 historical score",
            "internship_observation_signal": "normalized internship observation support",
            "entry_level_access_score": "optional 0-1 historical score",
        },
        internal_weight_config={
            "internship_density_score": 0.60,
            "internship_observation_signal": 0.20,
            "entry_level_access_score": 0.10,
            "confidence_score": 0.10,
        },
    ),
    IndexDefinition(
        key="company_presence_quality",
        name="Company Presence Quality Index",
        description="Measures useful company presence rather than raw company count.",
        formula_description=(
            "Blends company presence, hiring activity, entry-level roles, internship "
            "availability, freshness, confidence, and coverage warnings."
        ),
        input_schema={
            "company_presence_score": "optional 0-1 historical score",
            "hiring_activity_average": "optional company-region snapshot average",
            "entry_level_average": "optional company-region snapshot average",
            "internship_availability": "normalized company-region internship count",
        },
        internal_weight_config={
            "company_presence_score": 0.35,
            "hiring_activity_average": 0.25,
            "entry_level_average": 0.20,
            "internship_availability": 0.10,
            "confidence_score": 0.10,
        },
    ),
    IndexDefinition(
        key="hidden_market_opportunity",
        name="Hidden Market Opportunity Index",
        description="Measures underrated or improving regional opportunity signals.",
        formula_description=(
            "Blends available hidden opportunity score, improving historical "
            "observations, entry-level improvement, sector growth, freshness, "
            "confidence, and coverage warnings."
        ),
        input_schema={
            "hidden_opportunity_score": "optional 0-1 historical score",
            "improvement_observation_signal": "normalized improving observation support",
            "entry_level_access_score": "optional 0-1 historical score",
            "sector_growth_signal": "normalized sector-growth observation support",
        },
        internal_weight_config={
            "hidden_opportunity_score": 0.40,
            "improvement_observation_signal": 0.25,
            "entry_level_access_score": 0.15,
            "sector_growth_signal": 0.10,
            "confidence_score": 0.10,
        },
    ),
)


class MarketIndexService:
    def __init__(self, repository: HistoryRepository) -> None:
        self._repo = repository

    def ensure_required_indices(
        self,
        *,
        effective_date: date,
        created_at: datetime | None = None,
    ) -> tuple[MarketIndex, ...]:
        created_at = created_at or datetime.now(UTC)
        rows: list[MarketIndex] = []
        for definition in REQUIRED_INDEX_DEFINITIONS:
            index = self._repo.get_market_index_by_key(definition.key)
            if index is None:
                index = MarketIndex(
                    market_index_id=_new_id("market_index"),
                    key=definition.key,
                    name=definition.name,
                    description=definition.description,
                    status=MarketIndexStatus.ACTIVE.value,
                    created_at=created_at,
                )
                self._repo.add_market_index(index)
                self._repo.flush()
            rows.append(index)
            if (
                self._repo.get_market_index_version(
                    index_id=index.market_index_id,
                    version=DEFAULT_INDEX_VERSION,
                )
                is None
            ):
                self.create_index_version(
                    MarketIndexVersionCreate(
                        index_id=index.market_index_id,
                        version=DEFAULT_INDEX_VERSION,
                        formula_description=definition.formula_description,
                        input_schema=definition.input_schema,
                        internal_weight_config=definition.internal_weight_config,
                        status=MarketIndexVersionStatus.ACTIVE,
                        effective_date=effective_date,
                        created_at=created_at,
                    )
                )
        self._repo.flush()
        return tuple(rows)

    def create_index_version(
        self,
        request: MarketIndexVersionCreate,
    ) -> MarketIndexVersion:
        row = MarketIndexVersion(
            market_index_version_id=(
                request.market_index_version_id or _new_id("market_index_version")
            ),
            index_id=request.index_id,
            version=request.version,
            formula_description=request.formula_description,
            input_schema=dict(request.input_schema),
            internal_weight_config=dict(request.internal_weight_config),
            status=request.status.value,
            effective_date=request.effective_date,
            created_at=request.created_at or datetime.now(UTC),
        )
        self._repo.add_market_index_version(row)
        self._repo.flush()
        return row

    def calculate_scores(
        self,
        *,
        index_key: str,
        region_ids: tuple[str, ...],
        calculated_at: datetime | None = None,
    ) -> tuple[MarketIndexScore, ...]:
        index = self._repo.get_market_index_by_key(index_key)
        if index is None:
            raise ValueError(f"unknown market index: {index_key}")
        version = self._repo.latest_active_index_version(index.market_index_id)
        if version is None:
            raise ValueError(f"market index has no active version: {index_key}")
        calculated_at = calculated_at or datetime.now(UTC)

        calculations = [
            calculation
            for calculation in (
                self._calculate_region(index_key, region_id)
                for region_id in region_ids
            )
            if calculation is not None
        ]
        ranked = sorted(calculations, key=lambda item: item.score, reverse=True)
        rows: list[MarketIndexScore] = []
        for rank, calculation in enumerate(ranked, start=1):
            row = self._create_score(
                MarketIndexScoreCreate(
                    index_id=index.market_index_id,
                    index_version_id=version.market_index_version_id,
                    region_id=calculation.region_id,
                    score=calculation.score,
                    rank=rank,
                    confidence_score=calculation.confidence_score,
                    freshness_state=calculation.freshness_state,
                    evidence_summary=calculation.evidence_summary,
                    calculated_at=calculated_at,
                    created_at=calculated_at,
                    inputs=calculation.inputs,
                )
            )
            rows.append(row)
        self._repo.flush()
        return tuple(rows)

    def list_indices(self) -> tuple[MarketIndexSummary, ...]:
        summaries: list[MarketIndexSummary] = []
        for index in self._repo.list_market_indices():
            version = self._repo.latest_active_index_version(index.market_index_id)
            summaries.append(_index_summary(index, version))
        return tuple(summaries)

    def list_index_scores(
        self,
        index_key: str,
        *,
        limit: int = 100,
    ) -> MarketIndexScoresResponse:
        index = self._repo.get_market_index_by_key(index_key)
        if index is None:
            return MarketIndexScoresResponse(index_key=index_key, scores=())
        versions = {
            version.market_index_version_id: version
            for version in self._repo.list_index_versions(index.market_index_id)
        }
        scores = tuple(
            _score_summary(index, versions[row.index_version_id], row)
            for row in self._repo.list_index_scores(index.market_index_id, limit=limit)
            if row.index_version_id in versions
        )
        return MarketIndexScoresResponse(index_key=index_key, scores=scores)

    def _create_score(self, request: MarketIndexScoreCreate) -> MarketIndexScore:
        created_at = request.created_at or datetime.now(UTC)
        row = MarketIndexScore(
            market_index_score_id=(
                request.market_index_score_id or _new_id("market_index_score")
            ),
            index_id=request.index_id,
            index_version_id=request.index_version_id,
            region_id=request.region_id,
            score=request.score,
            rank=request.rank,
            confidence_score=request.confidence_score,
            freshness_state=request.freshness_state,
            evidence_summary=request.evidence_summary,
            calculated_at=request.calculated_at,
            created_at=created_at,
        )
        self._repo.add_market_index_score(row)
        self._repo.flush()
        for index_input in request.inputs:
            self._repo.add_market_index_input(
                MarketIndexInput(
                    market_index_input_id=_new_id("market_index_input"),
                    index_score_id=row.market_index_score_id,
                    input_name=index_input.input_name,
                    input_value=index_input.input_value,
                    input_weight=index_input.input_weight,
                    source_type=index_input.source_type,
                    source_id=index_input.source_id,
                    created_at=created_at,
                )
            )
        return row

    def _calculate_region(
        self,
        index_key: str,
        region_id: str,
    ) -> _IndexCalculation | None:
        market_snapshots = self._repo.list_market_snapshots(region_id, limit=500)
        latest = market_snapshots[-1] if market_snapshots else None
        observations = self._repo.list_region_observations(region_id, limit=500)
        company_snapshots = self._repo.list_company_region_snapshots_for_region(
            region_id,
            limit=1_000,
        )
        sector_snapshots = self._repo.list_sector_region_snapshots(region_id, limit=500)
        definition = _definition_by_key(index_key)
        warnings = _base_warnings(latest)
        inputs = _inputs_for_index(
            definition=definition,
            latest=latest,
            observations=observations,
            company_snapshots=company_snapshots,
            sector_snapshots=sector_snapshots,
            warnings=warnings,
        )
        if not inputs:
            return None
        score = _weighted_score(inputs)
        evidence_summary = {
            "input_count": len(inputs),
            "snapshot_count": len(market_snapshots),
            "coverage_tier": latest.coverage_tier if latest is not None else None,
            "warnings": warnings,
        }
        return _IndexCalculation(
            region_id=region_id,
            score=score,
            confidence_score=latest.confidence_score if latest is not None else None,
            freshness_state=latest.freshness_state if latest is not None else None,
            evidence_summary=evidence_summary,
            inputs=tuple(inputs),
        )


def _inputs_for_index(
    *,
    definition: IndexDefinition,
    latest: MarketSnapshot | None,
    observations: tuple[HistoricalObservation, ...] | list[HistoricalObservation],
    company_snapshots: tuple[CompanyRegionSnapshot, ...] | list[CompanyRegionSnapshot],
    sector_snapshots: tuple[SectorRegionSnapshot, ...] | list[SectorRegionSnapshot],
    warnings: list[str],
) -> list[MarketIndexInputCreate]:
    weights = definition.internal_weight_config
    if definition.key == "early_career_tech_access":
        return _market_inputs(
            latest,
            weights,
            warnings,
            (
                "entry_level_access_score",
                "internship_density_score",
                "company_presence_score",
                "confidence_score",
            ),
        )
    if definition.key == "ai_opportunity_geography":
        inputs = _market_inputs(
            latest,
            weights,
            warnings,
            ("ai_opportunity_score", "entry_level_access_score", "confidence_score"),
        )
        ai_sector = _latest_sector_snapshot(sector_snapshots, "ai")
        _append_input(
            inputs,
            name="ai_sector_score",
            value=ai_sector.overall_score if ai_sector is not None else None,
            weight=weights["ai_sector_score"],
            source_type="sector_region_snapshot",
            source_id=(
                ai_sector.sector_region_snapshot_id if ai_sector is not None else None
            ),
            warnings=warnings,
        )
        return inputs
    if definition.key == "internship_density":
        inputs = _market_inputs(
            latest,
            weights,
            warnings,
            ("internship_density_score", "entry_level_access_score", "confidence_score"),
        )
        _append_input(
            inputs,
            name="internship_observation_signal",
            value=_observation_signal(observations, {"internship_density_changed"}),
            weight=weights["internship_observation_signal"],
            source_type="historical_observations",
            source_id=None,
            warnings=warnings,
        )
        return inputs
    if definition.key == "company_presence_quality":
        inputs = _market_inputs(
            latest,
            weights,
            warnings,
            ("company_presence_score", "confidence_score"),
        )
        latest_company = _latest_company_snapshots(company_snapshots)
        _append_input(
            inputs,
            name="hiring_activity_average",
            value=_average([row.hiring_activity_score for row in latest_company]),
            weight=weights["hiring_activity_average"],
            source_type="company_region_snapshot_set",
            source_id=None,
            warnings=warnings,
        )
        _append_input(
            inputs,
            name="entry_level_average",
            value=_average([row.entry_level_access_score for row in latest_company]),
            weight=weights["entry_level_average"],
            source_type="company_region_snapshot_set",
            source_id=None,
            warnings=warnings,
        )
        _append_input(
            inputs,
            name="internship_availability",
            value=_normalized_count([row.internship_count for row in latest_company]),
            weight=weights["internship_availability"],
            source_type="company_region_snapshot_set",
            source_id=None,
            warnings=warnings,
        )
        return inputs
    if definition.key == "hidden_market_opportunity":
        inputs = _market_inputs(
            latest,
            weights,
            warnings,
            (
                "hidden_opportunity_score",
                "entry_level_access_score",
                "confidence_score",
            ),
        )
        _append_input(
            inputs,
            name="improvement_observation_signal",
            value=_observation_signal(
                observations,
                {
                    "regional_score_increased",
                    "entry_level_access_improved",
                    "company_presence_increased",
                    "hiring_activity_increased",
                    "sector_growth_detected",
                },
            ),
            weight=weights["improvement_observation_signal"],
            source_type="historical_observations",
            source_id=None,
            warnings=warnings,
        )
        _append_input(
            inputs,
            name="sector_growth_signal",
            value=_observation_signal(observations, {"sector_growth_detected"}),
            weight=weights["sector_growth_signal"],
            source_type="historical_observations",
            source_id=None,
            warnings=warnings,
        )
        return inputs
    raise ValueError(f"unsupported market index: {definition.key}")


def _market_inputs(
    latest: MarketSnapshot | None,
    weights: dict[str, float],
    warnings: list[str],
    names: tuple[str, ...],
) -> list[MarketIndexInputCreate]:
    inputs: list[MarketIndexInputCreate] = []
    for name in names:
        _append_input(
            inputs,
            name=name,
            value=getattr(latest, name, None) if latest is not None else None,
            weight=weights[name],
            source_type="market_snapshot",
            source_id=latest.market_snapshot_id if latest is not None else None,
            warnings=warnings,
        )
    return inputs


def _append_input(
    inputs: list[MarketIndexInputCreate],
    *,
    name: str,
    value: float | None,
    weight: float,
    source_type: str,
    source_id: str | None,
    warnings: list[str],
) -> None:
    if value is None:
        warnings.append(f"missing_input:{name}")
        return
    inputs.append(
        MarketIndexInputCreate(
            input_name=name,
            input_value=_clip01(float(value)),
            input_weight=weight,
            source_type=source_type,
            source_id=source_id,
        )
    )


def _weighted_score(
    inputs: tuple[MarketIndexInputCreate, ...] | list[MarketIndexInputCreate],
) -> float:
    weight_total = sum(input_row.input_weight or 0.0 for input_row in inputs)
    if weight_total <= 0:
        return 0.0
    return _clip01(
        sum(
            (input_row.input_value or 0.0) * (input_row.input_weight or 0.0)
            for input_row in inputs
        )
        / weight_total
    )


def _base_warnings(latest: MarketSnapshot | None) -> list[str]:
    if latest is None:
        return ["missing_market_snapshot"]
    warnings = [str(item) for item in (latest.warnings or [])]
    if latest.coverage_tier in {"tier_3", "tier_4"}:
        warnings.append(f"limited_coverage:{latest.coverage_tier}")
    return warnings


def _latest_sector_snapshot(
    rows: tuple[SectorRegionSnapshot, ...] | list[SectorRegionSnapshot],
    sector_id: str,
) -> SectorRegionSnapshot | None:
    matches = [row for row in rows if row.sector_id == sector_id]
    if not matches:
        return None
    return sorted(matches, key=lambda row: (row.snapshot_date, row.created_at))[-1]


def _latest_company_snapshots(
    rows: tuple[CompanyRegionSnapshot, ...] | list[CompanyRegionSnapshot],
) -> tuple[CompanyRegionSnapshot, ...]:
    grouped: dict[str, list[CompanyRegionSnapshot]] = defaultdict(list)
    for row in rows:
        grouped[row.company_id].append(row)
    return tuple(
        sorted(values, key=lambda row: (row.snapshot_date, row.created_at))[-1]
        for values in grouped.values()
    )


def _average(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _normalized_count(values: list[int | None]) -> float | None:
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    return _clip01(sum(clean) / 20)


def _observation_signal(
    observations: tuple[HistoricalObservation, ...] | list[HistoricalObservation],
    observation_types: set[str],
) -> float | None:
    count = sum(1 for row in observations if row.observation_type in observation_types)
    if count == 0:
        return None
    return _clip01(count / 4)


def _index_summary(
    index: MarketIndex,
    version: MarketIndexVersion | None,
) -> MarketIndexSummary:
    return MarketIndexSummary(
        index_id=index.market_index_id,
        key=index.key,
        name=index.name,
        description=index.description,
        status=index.status,
        latest_version=version.version if version is not None else None,
        methodology_summary=version.formula_description if version is not None else None,
        created_at=index.created_at,
    )


def _score_summary(
    index: MarketIndex,
    version: MarketIndexVersion,
    row: MarketIndexScore,
) -> MarketIndexScoreSummary:
    return MarketIndexScoreSummary(
        score_id=row.market_index_score_id,
        index_key=index.key,
        index_version_id=row.index_version_id,
        index_version=version.version,
        region_id=row.region_id,
        score=row.score,
        rank=row.rank,
        confidence_score=row.confidence_score,
        freshness_state=row.freshness_state,
        evidence_summary=row.evidence_summary,
        methodology_summary=version.formula_description,
        calculated_at=row.calculated_at,
        created_at=row.created_at,
    )


def _definition_by_key(index_key: str) -> IndexDefinition:
    for definition in REQUIRED_INDEX_DEFINITIONS:
        if definition.key == index_key:
            return definition
    raise ValueError(f"unsupported market index: {index_key}")


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _new_id(prefix: str) -> str:
    suffix_length = max(8, 63 - len(prefix))
    return f"{prefix}_{uuid4().hex[:suffix_length]}"
