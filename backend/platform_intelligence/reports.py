"""Benchmark reports for Layer 18C."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import uuid4

from backend.platform_intelligence.history_repository import HistoryRepository
from backend.platform_intelligence.models import (
    BenchmarkReport,
    BenchmarkReportEvidence,
    BenchmarkReportRanking,
    BenchmarkReportSection,
    HistoricalObservation,
    MarketIndexScore,
    MarketSnapshot,
    PredictiveSignal,
)
from backend.platform_intelligence.schemas import (
    BenchmarkReportCreate,
    BenchmarkReportDetail,
    BenchmarkReportEvidenceCreate,
    BenchmarkReportEvidenceSummary,
    BenchmarkReportKey,
    BenchmarkReportListResponse,
    BenchmarkReportRankingCreate,
    BenchmarkReportRankingSummary,
    BenchmarkReportSectionCreate,
    BenchmarkReportSectionSummary,
    BenchmarkReportStatus,
    BenchmarkReportSummary,
    BenchmarkReportType,
)


class BenchmarkReportLifecycleError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ReportDefinition:
    report_key: BenchmarkReportKey
    report_type: BenchmarkReportType
    title: str
    summary: str
    methodology_summary: str
    index_keys: tuple[str, ...]
    observation_types: frozenset[str]
    signal_types: frozenset[str]
    extra_market_score_fields: tuple[str, ...] = ()


REPORT_DEFINITIONS: tuple[ReportDefinition, ...] = (
    ReportDefinition(
        report_key=BenchmarkReportKey.BEST_CITIES_EARLY_CAREER_AI_ROLES,
        report_type=BenchmarkReportType.EARLY_CAREER_AI_ROLES,
        title="Best Cities for Early-Career AI Roles",
        summary=(
            "A benchmark of regions with stronger early-career AI opportunity "
            "signals based on indexed and historical evidence."
        ),
        methodology_summary=(
            "Uses public-safe summaries of the AI Opportunity Geography, "
            "Early-Career Tech Access, and Company Presence Quality indices, "
            "plus relevant historical observations and active signals."
        ),
        index_keys=(
            "ai_opportunity_geography",
            "early_career_tech_access",
            "company_presence_quality",
        ),
        observation_types=frozenset(
            {
                "entry_level_access_improved",
                "sector_growth_detected",
                "company_presence_increased",
                "hiring_activity_increased",
            }
        ),
        signal_types=frozenset(
            {
                "emerging_market",
                "entry_level_access_trend",
                "company_expansion_signal",
            }
        ),
        extra_market_score_fields=("ai_opportunity_score", "entry_level_access_score"),
    ),
    ReportDefinition(
        report_key=BenchmarkReportKey.TOP_EMERGING_TECH_MARKETS,
        report_type=BenchmarkReportType.EMERGING_TECH_MARKETS,
        title="Top Emerging Tech Markets",
        summary=(
            "A benchmark of regions showing improving technology-market signals "
            "from historical observations, active signals, and derived indices."
        ),
        methodology_summary=(
            "Uses public-safe summaries of the Hidden Market Opportunity and "
            "Company Presence Quality indices, plus expansion and growth evidence."
        ),
        index_keys=("hidden_market_opportunity", "company_presence_quality"),
        observation_types=frozenset(
            {
                "regional_score_increased",
                "company_presence_increased",
                "hiring_activity_increased",
                "sector_growth_detected",
            }
        ),
        signal_types=frozenset({"emerging_market", "company_expansion_signal"}),
        extra_market_score_fields=("hidden_opportunity_score",),
    ),
    ReportDefinition(
        report_key=BenchmarkReportKey.BEST_MARKETS_PRODUCT_CAREERS,
        report_type=BenchmarkReportType.PRODUCT_CAREERS,
        title="Best Markets for Product Careers",
        summary=(
            "A benchmark of markets with stronger product-career access signals "
            "based on available indexed and historical evidence."
        ),
        methodology_summary=(
            "Uses public-safe summaries of the Company Presence Quality and "
            "Early-Career Tech Access indices, plus product opportunity fields "
            "where available."
        ),
        index_keys=("company_presence_quality", "early_career_tech_access"),
        observation_types=frozenset(
            {
                "company_presence_increased",
                "hiring_activity_increased",
                "entry_level_access_improved",
            }
        ),
        signal_types=frozenset({"emerging_market", "company_expansion_signal"}),
        extra_market_score_fields=("product_opportunity_score",),
    ),
    ReportDefinition(
        report_key=BenchmarkReportKey.BEST_REGIONS_INTERNSHIP_ACCESS,
        report_type=BenchmarkReportType.INTERNSHIP_ACCESS,
        title="Best Regions for Internship Access",
        summary=(
            "A benchmark of regions with stronger internship access signals "
            "using internship-density evidence and relevant historical signals."
        ),
        methodology_summary=(
            "Uses public-safe summaries of the Internship Density Index, "
            "internship-density history, and active seasonal hiring signals."
        ),
        index_keys=("internship_density",),
        observation_types=frozenset({"internship_density_changed"}),
        signal_types=frozenset({"seasonal_hiring_window"}),
        extra_market_score_fields=("internship_density_score",),
    ),
)


class BenchmarkReportService:
    def __init__(self, repository: HistoryRepository) -> None:
        self._repo = repository

    def create_report(self, request: BenchmarkReportCreate) -> BenchmarkReport:
        if request.status not in {
            BenchmarkReportStatus.DRAFT,
            BenchmarkReportStatus.REVIEW_READY,
        }:
            raise BenchmarkReportLifecycleError(
                "reports must be created as draft or review_ready"
            )
        created_at = request.created_at or datetime.now(UTC)
        row = BenchmarkReport(
            benchmark_report_id=request.benchmark_report_id or _new_id("benchmark_report"),
            report_key=request.report_key.value,
            title=request.title,
            report_period=request.report_period,
            report_type=request.report_type.value,
            status=request.status.value,
            summary=request.summary,
            methodology_summary=request.methodology_summary,
            data_window_start=request.data_window_start,
            data_window_end=request.data_window_end,
            freshness_notes=request.freshness_notes,
            confidence_notes=request.confidence_notes,
            coverage_notes=request.coverage_notes,
            limitations=list(request.limitations),
            created_at=created_at,
        )
        self._repo.add_benchmark_report(row)
        self._repo.flush()
        for section in request.sections:
            self._repo.add_benchmark_report_section(
                BenchmarkReportSection(
                    benchmark_report_section_id=_new_id("benchmark_section"),
                    report_id=row.benchmark_report_id,
                    section_key=section.section_key,
                    title=section.title,
                    body=section.body,
                    display_order=section.display_order,
                    created_at=created_at,
                )
            )
        for ranking in request.rankings:
            self._repo.add_benchmark_report_ranking(
                BenchmarkReportRanking(
                    benchmark_report_ranking_id=_new_id("benchmark_ranking"),
                    report_id=row.benchmark_report_id,
                    region_id=ranking.region_id,
                    rank=ranking.rank,
                    score=ranking.score,
                    index_score_id=ranking.index_score_id,
                    explanation=ranking.explanation,
                    warnings=list(ranking.warnings),
                    confidence_score=ranking.confidence_score,
                    freshness_state=ranking.freshness_state,
                    created_at=created_at,
                )
            )
        for evidence in request.evidence:
            self._repo.add_benchmark_report_evidence(
                BenchmarkReportEvidence(
                    benchmark_report_evidence_id=_new_id("benchmark_evidence"),
                    report_id=row.benchmark_report_id,
                    target_type=evidence.target_type,
                    target_id=evidence.target_id,
                    source_type=evidence.source_type,
                    source_id=evidence.source_id,
                    evidence_summary=evidence.evidence_summary,
                    created_at=created_at,
                )
            )
        self._repo.flush()
        return row

    def generate_report(
        self,
        report_key: BenchmarkReportKey | str,
        *,
        report_period: str,
        region_ids: tuple[str, ...],
        status: BenchmarkReportStatus = BenchmarkReportStatus.REVIEW_READY,
        created_at: datetime | None = None,
    ) -> BenchmarkReport:
        created_at = created_at or datetime.now(UTC)
        definition = report_definition(report_key)
        ranking_inputs = [
            ranking
            for ranking in (
                self._ranking_for_region(definition, region_id, now=created_at)
                for region_id in region_ids
            )
            if ranking is not None
        ]
        ranked = sorted(ranking_inputs, key=lambda row: row.score or 0.0, reverse=True)
        rankings = tuple(
            ranking.model_copy(update={"rank": rank})
            for rank, ranking in enumerate(ranked, start=1)
        )
        evidence = tuple(
            evidence
            for region_id in region_ids
            for evidence in self._evidence_for_region(definition, region_id, now=created_at)
        )
        data_window_start, data_window_end = self._data_window(region_ids, rankings, created_at)
        limitations = _limitations(rankings)
        sections = _sections(definition, rankings, limitations)
        return self.create_report(
            BenchmarkReportCreate(
                report_key=definition.report_key,
                title=definition.title,
                report_period=report_period,
                report_type=definition.report_type,
                status=status,
                summary=definition.summary,
                methodology_summary=definition.methodology_summary,
                data_window_start=data_window_start,
                data_window_end=data_window_end,
                freshness_notes=_freshness_notes(rankings),
                confidence_notes=_confidence_notes(rankings),
                coverage_notes=_coverage_notes(rankings),
                limitations=limitations,
                created_at=created_at,
                sections=sections,
                rankings=rankings,
                evidence=evidence,
            )
        )

    def publish_report(
        self,
        report_id: str,
        *,
        published_at: datetime | None = None,
    ) -> BenchmarkReport:
        report = self._require_report(report_id)
        if report.status != BenchmarkReportStatus.REVIEW_READY.value:
            raise BenchmarkReportLifecycleError("only review_ready reports can publish")
        published_at = published_at or datetime.now(UTC)
        for existing in self._repo.list_benchmark_reports_by_key(
            report.report_key,
            status=BenchmarkReportStatus.PUBLISHED.value,
        ):
            if existing.benchmark_report_id != report.benchmark_report_id:
                existing.status = BenchmarkReportStatus.SUPERSEDED.value
                existing.superseded_at = published_at
        report.status = BenchmarkReportStatus.PUBLISHED.value
        report.published_at = published_at
        self._repo.flush()
        return report

    def archive_report(
        self,
        report_id: str,
        *,
        archived_at: datetime | None = None,
    ) -> BenchmarkReport:
        report = self._require_report(report_id)
        if report.status not in {
            BenchmarkReportStatus.PUBLISHED.value,
            BenchmarkReportStatus.SUPERSEDED.value,
        }:
            raise BenchmarkReportLifecycleError("only published/superseded reports can archive")
        report.status = BenchmarkReportStatus.ARCHIVED.value
        report.archived_at = archived_at or datetime.now(UTC)
        self._repo.flush()
        return report

    def supersede_report(
        self,
        report_id: str,
        *,
        superseded_at: datetime | None = None,
    ) -> BenchmarkReport:
        report = self._require_report(report_id)
        if report.status != BenchmarkReportStatus.PUBLISHED.value:
            raise BenchmarkReportLifecycleError("only published reports can supersede")
        report.status = BenchmarkReportStatus.SUPERSEDED.value
        report.superseded_at = superseded_at or datetime.now(UTC)
        self._repo.flush()
        return report

    def list_public_reports(self, *, limit: int = 100) -> BenchmarkReportListResponse:
        return BenchmarkReportListResponse(
            reports=tuple(
                _report_summary(row)
                for row in self._repo.list_published_benchmark_reports(limit=limit)
            )
        )

    def public_report_detail(self, report_key: str) -> BenchmarkReportDetail | None:
        report = self._repo.latest_published_benchmark_report(report_key)
        if report is None:
            return None
        return self.report_detail(report.benchmark_report_id)

    def report_detail(self, report_id: str) -> BenchmarkReportDetail:
        report = self._require_report(report_id)
        rankings = self._repo.list_report_rankings(report_id)
        sections = self._repo.list_report_sections(report_id)
        evidence = self._repo.list_report_evidence(report_id)
        warnings = tuple(
            warning
            for ranking in rankings
            for warning in (ranking.warnings or [])
        )
        return BenchmarkReportDetail(
            report_id=report.benchmark_report_id,
            report_key=report.report_key,
            title=report.title,
            report_period=report.report_period,
            report_type=report.report_type,
            status=report.status,
            summary=report.summary,
            methodology_summary=report.methodology_summary,
            data_window_start=report.data_window_start,
            data_window_end=report.data_window_end,
            freshness_notes=report.freshness_notes,
            confidence_notes=report.confidence_notes,
            coverage_notes=report.coverage_notes,
            limitations=tuple(report.limitations or ()),
            ranked_regions=tuple(_ranking_summary(row) for row in rankings),
            sections=tuple(_section_summary(row) for row in sections),
            evidence=tuple(_evidence_summary(row) for row in evidence),
            warnings=warnings,
            published_at=report.published_at,
        )

    def _require_report(self, report_id: str) -> BenchmarkReport:
        report = self._repo.get_benchmark_report(report_id)
        if report is None:
            raise BenchmarkReportLifecycleError(f"benchmark report not found: {report_id}")
        return report

    def _ranking_for_region(
        self,
        definition: ReportDefinition,
        region_id: str,
        *,
        now: datetime,
    ) -> BenchmarkReportRankingCreate | None:
        index_scores = self._latest_index_scores(definition.index_keys, region_id)
        latest_snapshot = self._latest_market_snapshot(region_id)
        market_values = [
            getattr(latest_snapshot, field, None)
            for field in definition.extra_market_score_fields
            if latest_snapshot is not None
        ]
        score_values = [row.score for row in index_scores] + [
            value for value in market_values if value is not None
        ]
        if not score_values:
            return None
        warnings = _warnings(index_scores, latest_snapshot, definition.index_keys)
        observations = _matching_observations(
            self._repo.list_region_observations(region_id, limit=500),
            definition.observation_types,
        )
        active_signals = _matching_signals(
            self._repo.list_active_region_signals(region_id, now=now, limit=100),
            definition.signal_types,
        )
        if not observations and not active_signals:
            warnings.append("limited_historical_context")
        score = sum(score_values) / len(score_values)
        confidence_values = [
            row.confidence_score for row in index_scores if row.confidence_score is not None
        ]
        if latest_snapshot is not None and latest_snapshot.confidence_score is not None:
            confidence_values.append(latest_snapshot.confidence_score)
        primary_index_score = index_scores[0] if index_scores else None
        freshness_state = _freshness_state(index_scores, latest_snapshot)
        return BenchmarkReportRankingCreate(
            region_id=region_id,
            rank=1,
            score=score,
            index_score_id=(
                primary_index_score.market_index_score_id
                if primary_index_score is not None
                else None
            ),
            explanation=_ranking_explanation(definition, observations, active_signals),
            warnings=tuple(warnings),
            confidence_score=(
                sum(confidence_values) / len(confidence_values)
                if confidence_values
                else None
            ),
            freshness_state=freshness_state,
        )

    def _evidence_for_region(
        self,
        definition: ReportDefinition,
        region_id: str,
        *,
        now: datetime,
    ) -> tuple[BenchmarkReportEvidenceCreate, ...]:
        evidence: list[BenchmarkReportEvidenceCreate] = []
        for score in self._latest_index_scores(definition.index_keys, region_id):
            evidence.append(
                BenchmarkReportEvidenceCreate(
                    target_type="region",
                    target_id=region_id,
                    source_type="market_index_score",
                    source_id=score.market_index_score_id,
                    evidence_summary={
                        "score": score.score,
                        "confidence_score": score.confidence_score,
                        "freshness_state": score.freshness_state,
                    },
                )
            )
        for observation in _matching_observations(
            self._repo.list_region_observations(region_id, limit=500),
            definition.observation_types,
        ):
            evidence.append(
                BenchmarkReportEvidenceCreate(
                    target_type="region",
                    target_id=region_id,
                    source_type="historical_observation",
                    source_id=observation.historical_observation_id,
                    evidence_summary={
                        "observation_type": observation.observation_type,
                        "delta_direction": observation.delta_direction,
                        "severity": observation.severity,
                    },
                )
            )
        for signal in _matching_signals(
            self._repo.list_active_region_signals(region_id, now=now, limit=100),
            definition.signal_types,
        ):
            evidence.append(
                BenchmarkReportEvidenceCreate(
                    target_type="region",
                    target_id=region_id,
                    source_type="predictive_signal",
                    source_id=signal.predictive_signal_id,
                    evidence_summary={
                        "signal_type": signal.signal_type,
                        "signal_strength": signal.signal_strength,
                        "confidence_level": signal.confidence_level,
                    },
                )
            )
        return tuple(evidence)

    def _latest_index_scores(
        self,
        index_keys: Sequence[str],
        region_id: str,
    ) -> tuple[MarketIndexScore, ...]:
        scores: list[MarketIndexScore] = []
        for index_key in index_keys:
            index = self._repo.get_market_index_by_key(index_key)
            if index is None:
                continue
            region_scores = [
                row
                for row in self._repo.list_index_scores(index.market_index_id, limit=1_000)
                if row.region_id == region_id
            ]
            if region_scores:
                scores.append(
                    sorted(
                        region_scores,
                        key=lambda row: (row.calculated_at, row.created_at),
                        reverse=True,
                    )[0]
                )
        return tuple(scores)

    def _latest_market_snapshot(self, region_id: str) -> MarketSnapshot | None:
        snapshots = self._repo.list_market_snapshots(region_id, limit=1_000)
        return snapshots[-1] if snapshots else None

    def _data_window(
        self,
        region_ids: Iterable[str],
        rankings: Sequence[BenchmarkReportRankingCreate],
        created_at: datetime,
    ) -> tuple[date, date]:
        dates: list[date] = []
        for region_id in region_ids:
            snapshots = self._repo.list_market_snapshots(region_id, limit=1_000)
            dates.extend(row.snapshot_date for row in snapshots)
        if not dates:
            return created_at.date(), created_at.date()
        return min(dates), max(dates)


def report_definition(report_key: BenchmarkReportKey | str) -> ReportDefinition:
    key = BenchmarkReportKey(report_key)
    for definition in REPORT_DEFINITIONS:
        if definition.report_key is key:
            return definition
    raise ValueError(f"unsupported benchmark report key: {report_key}")


def _warnings(
    index_scores: Sequence[MarketIndexScore],
    latest_snapshot: MarketSnapshot | None,
    index_keys: Sequence[str],
) -> list[str]:
    warnings: list[str] = []
    if len(index_scores) < len(index_keys):
        warnings.append("missing_relevant_index_score")
    for score in index_scores:
        summary = score.evidence_summary
        if isinstance(summary, dict):
            warnings.extend(str(item) for item in summary.get("warnings", []))
    if latest_snapshot is None:
        warnings.append("missing_market_snapshot")
    elif latest_snapshot.coverage_tier in {"tier_3", "tier_4"}:
        warnings.append(f"partial_coverage:{latest_snapshot.coverage_tier}")
    return list(dict.fromkeys(warnings))


def _matching_observations(
    observations: Sequence[HistoricalObservation],
    observation_types: frozenset[str],
) -> tuple[HistoricalObservation, ...]:
    return tuple(row for row in observations if row.observation_type in observation_types)


def _matching_signals(
    signals: Sequence[PredictiveSignal],
    signal_types: frozenset[str],
) -> tuple[PredictiveSignal, ...]:
    return tuple(row for row in signals if row.signal_type in signal_types)


def _freshness_state(
    index_scores: Sequence[MarketIndexScore],
    latest_snapshot: MarketSnapshot | None,
) -> str | None:
    states = [row.freshness_state for row in index_scores if row.freshness_state]
    if latest_snapshot is not None and latest_snapshot.freshness_state:
        states.append(latest_snapshot.freshness_state)
    if "stale" in states:
        return "stale"
    if states:
        return states[0]
    return None


def _ranking_explanation(
    definition: ReportDefinition,
    observations: Sequence[HistoricalObservation],
    signals: Sequence[PredictiveSignal],
) -> str:
    context: list[str] = []
    if observations:
        context.append(f"{len(observations)} relevant historical observations")
    if signals:
        context.append(f"{len(signals)} active predictive signals")
    suffix = f" with {', '.join(context)}" if context else " with limited history"
    return f"Rank reflects {definition.title.lower()} methodology{suffix}."


def _freshness_notes(rankings: Sequence[BenchmarkReportRankingCreate]) -> str:
    states = {ranking.freshness_state or "unknown" for ranking in rankings}
    return f"Freshness states represented in ranked regions: {', '.join(sorted(states))}."


def _confidence_notes(rankings: Sequence[BenchmarkReportRankingCreate]) -> str:
    values = [
        ranking.confidence_score
        for ranking in rankings
        if ranking.confidence_score is not None
    ]
    if not values:
        return "Confidence is unknown for the ranked regions."
    return f"Average confidence across ranked regions is {sum(values) / len(values):.2f}."


def _coverage_notes(rankings: Sequence[BenchmarkReportRankingCreate]) -> str:
    warning_count = sum(
        1
        for ranking in rankings
        for warning in ranking.warnings
        if "coverage" in str(warning)
    )
    if warning_count:
        return "Some ranked regions include partial coverage warnings."
    return "No ranked region carried a partial coverage warning in this report run."


def _limitations(rankings: Sequence[BenchmarkReportRankingCreate]) -> tuple[str, ...]:
    limitations = {
        "Reports use app-owned historical and derived intelligence only.",
        "Missing inputs are not inferred or replaced with unverified data.",
    }
    if any(ranking.warnings for ranking in rankings):
        limitations.add("Partial or missing data is disclosed in ranking warnings.")
    if not rankings:
        limitations.add("No eligible regions had enough report evidence.")
    return tuple(sorted(limitations))


def _sections(
    definition: ReportDefinition,
    rankings: Sequence[BenchmarkReportRankingCreate],
    limitations: Sequence[str],
) -> tuple[BenchmarkReportSectionCreate, ...]:
    top_regions = ", ".join(ranking.region_id for ranking in rankings[:5]) or "none"
    return (
        BenchmarkReportSectionCreate(
            section_key="methodology",
            title="Methodology",
            body=definition.methodology_summary,
            display_order=1,
        ),
        BenchmarkReportSectionCreate(
            section_key="rankings",
            title="Ranked Regions",
            body=f"Top ranked regions in this run: {top_regions}.",
            display_order=2,
        ),
        BenchmarkReportSectionCreate(
            section_key="limitations",
            title="Limitations",
            body=" ".join(str(item) for item in limitations),
            display_order=3,
        ),
    )


def _report_summary(row: BenchmarkReport) -> BenchmarkReportSummary:
    return BenchmarkReportSummary(
        report_id=row.benchmark_report_id,
        report_key=row.report_key,
        title=row.title,
        report_period=row.report_period,
        report_type=row.report_type,
        status=row.status,
        summary=row.summary,
        data_window_start=row.data_window_start,
        data_window_end=row.data_window_end,
        published_at=row.published_at,
    )


def _ranking_summary(row: BenchmarkReportRanking) -> BenchmarkReportRankingSummary:
    return BenchmarkReportRankingSummary(
        region_id=row.region_id,
        rank=row.rank,
        score=row.score,
        explanation=row.explanation,
        warnings=tuple(row.warnings or ()),
        confidence_score=row.confidence_score,
        freshness_state=row.freshness_state,
    )


def _section_summary(row: BenchmarkReportSection) -> BenchmarkReportSectionSummary:
    return BenchmarkReportSectionSummary(
        section_key=row.section_key,
        title=row.title,
        body=row.body,
        display_order=row.display_order,
    )


def _evidence_summary(row: BenchmarkReportEvidence) -> BenchmarkReportEvidenceSummary:
    return BenchmarkReportEvidenceSummary(
        target_type=row.target_type,
        target_id=row.target_id,
        source_type=row.source_type,
        evidence_summary=row.evidence_summary,
    )


def _new_id(prefix: str) -> str:
    suffix_length = max(8, 63 - len(prefix))
    return f"{prefix}_{uuid4().hex[:suffix_length]}"
