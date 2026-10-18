"""Read-only diagnostics and maintenance reports for curated imported markets."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from backend.imports.operations import (
    UNOBSERVED_STATUSES,
    FactSnapshot,
    MarketOperationalSnapshot,
    SourceSnapshot,
    build_all_market_operational_snapshots,
    build_market_operational_snapshot,
)
from backend.imports.schemas import (
    CoverageGap,
    CoverageGapReport,
    DatasetHealthReport,
    FactArea,
    FactHealthFinding,
    FactHealthReport,
    GapSeverity,
    MaintenancePriority,
    MarketHealthStatus,
    MarketOperationalCounts,
    OperationalSourceFreshnessStatus,
    PlatformImportedMarketSummary,
    RankingExclusionCategory,
    RankingExclusionDiagnostic,
    RankingExclusionReport,
    RefreshReadinessReport,
    RefreshReadinessStatus,
    SourceAgingReport,
    SourceDiagnostic,
)
from backend.shared.freshness import FreshnessStatus
from backend.shared.provenance import ObservationStatus
from backend.trust.schemas import RankingInfluenceReasonCode

MIN_COMPANY_COUNT = 3
MIN_SOURCE_COUNT = 5
MIN_PRESENCE_FACT_COUNT = 3
MIN_HIRING_FACT_COUNT = 3
MIN_ENTRY_LEVEL_FACT_COUNT = 3
HIGH_UNKNOWN_RATIO = 0.30
EXCESSIVE_RANKING_EXCLUDED_RATIO = 0.25
SOURCE_CONCENTRATION_RATIO = 0.60

_STATUS_PRECEDENCE: tuple[MarketHealthStatus, ...] = (
    MarketHealthStatus.VALIDATION_FAILED,
    MarketHealthStatus.STALE_SOURCES,
    MarketHealthStatus.RANKING_LIMITED,
    MarketHealthStatus.LIMITED_COVERAGE,
    MarketHealthStatus.NEEDS_REFRESH,
    MarketHealthStatus.HEALTHY,
)
_GAP_SEVERITY_ORDER: dict[GapSeverity, int] = {
    GapSeverity.LOW: 1,
    GapSeverity.MEDIUM: 2,
    GapSeverity.HIGH: 3,
    GapSeverity.CRITICAL: 4,
}


def build_dataset_health_report(
    session: Session,
    market_key: str,
    *,
    registry_path: str | Path | None = None,
    as_of: date | datetime | None = None,
) -> DatasetHealthReport:
    return dataset_health_from_snapshot(
        build_market_operational_snapshot(
            session,
            market_key,
            registry_path=registry_path,
            as_of=as_of,
        )
    )


def build_all_dataset_health_reports(
    session: Session,
    *,
    registry_path: str | Path | None = None,
    as_of: date | datetime | None = None,
) -> tuple[DatasetHealthReport, ...]:
    snapshots = build_all_market_operational_snapshots(
        session,
        registry_path=registry_path,
        as_of=as_of,
    )
    return tuple(dataset_health_from_snapshot(snapshot) for snapshot in snapshots)


def dataset_health_from_snapshot(snapshot: MarketOperationalSnapshot) -> DatasetHealthReport:
    source_report = source_aging_from_snapshot(snapshot)
    fact_report = fact_health_from_snapshot(snapshot)
    gap_report = coverage_gaps_from_snapshot(snapshot, fact_report=fact_report)
    ranking_report = ranking_exclusions_from_snapshot(snapshot)
    counts = _counts(snapshot)
    status, reasons = _health_status(
        snapshot,
        source_report=source_report,
        fact_report=fact_report,
        gap_report=gap_report,
        ranking_report=ranking_report,
    )
    return DatasetHealthReport(
        market_key=snapshot.market_key,
        market_name=snapshot.display_name,
        validation_ok=snapshot.validation.ok,
        missing_required_files=snapshot.missing_required_files,
        counts=counts,
        oldest_source_age_days=source_report.oldest_source_age_days,
        newest_source_age_days=source_report.newest_source_age_days,
        coverage_summary=_coverage_summary(snapshot, gap_report),
        freshness_summary=_freshness_summary(source_report),
        health_status=status,
        reasons=reasons,
        recommended_next_action=_recommended_health_action(status),
    )


def source_aging_from_snapshot(snapshot: MarketOperationalSnapshot) -> SourceAgingReport:
    diagnostics = tuple(_source_diagnostic(source) for source in snapshot.sources)
    stale = tuple(
        item
        for item in diagnostics
        if item.freshness_status
        in {
            OperationalSourceFreshnessStatus.STALE,
            OperationalSourceFreshnessStatus.EXPIRED,
        }
    )
    aging = tuple(
        item
        for item in diagnostics
        if item.freshness_status is OperationalSourceFreshnessStatus.AGING
    )
    expired = tuple(
        item
        for item in diagnostics
        if item.freshness_status is OperationalSourceFreshnessStatus.EXPIRED
    )
    ages = sorted(item.age_days for item in diagnostics if item.age_days is not None)
    return SourceAgingReport(
        market_key=snapshot.market_key,
        source_count=len(diagnostics),
        stale_source_count=len(stale),
        aging_source_count=len(aging),
        expired_source_count=len(expired),
        oldest_source_age_days=ages[-1] if ages else None,
        newest_source_age_days=ages[0] if ages else None,
        oldest_sources=tuple(
            sorted(
                diagnostics,
                key=lambda item: (-(item.age_days or -1), item.source_id),
            )[:5]
        ),
        greatest_fact_impact_sources=tuple(
            sorted(
                diagnostics,
                key=lambda item: (-item.fact_usage_count, item.source_id),
            )[:5]
        ),
        important_stale_sources=tuple(
            sorted(
                stale,
                key=lambda item: (-item.fact_usage_count, -(item.age_days or -1), item.source_id),
            )[:5]
        ),
        sources=tuple(sorted(diagnostics, key=lambda item: item.source_id)),
    )


def fact_health_from_snapshot(snapshot: MarketOperationalSnapshot) -> FactHealthReport:
    findings = tuple(_fact_finding(fact) for fact in snapshot.facts)
    stale_count = sum(1 for fact in snapshot.facts if fact.stale)
    low_confidence_count = sum(1 for fact in snapshot.facts if fact.low_confidence)
    missing_useful = sum(1 for fact in snapshot.facts if _missing_useful_dimensions(fact))
    weak_source = sum(1 for fact in snapshot.facts if _weak_source_coverage(fact))
    trust_or_risk_limited = sum(1 for fact in snapshot.facts if _trust_or_risk_limited(fact))
    limiting_categories = _limiting_fact_categories(snapshot.facts)
    return FactHealthReport(
        market_key=snapshot.market_key,
        total_facts=len(snapshot.facts),
        ranking_eligible_facts=sum(1 for fact in snapshot.facts if fact.ranking_eligible),
        ranking_excluded_facts=sum(1 for fact in snapshot.facts if fact.ranking_excluded),
        stale_facts=stale_count,
        low_confidence_facts=low_confidence_count,
        unknown_facts=sum(1 for fact in snapshot.facts if fact.unknown),
        observed_zero_facts=sum(1 for fact in snapshot.facts if fact.observed_zero),
        missing_useful_dimension_facts=missing_useful,
        weak_source_coverage_facts=weak_source,
        trust_or_risk_limited_facts=trust_or_risk_limited,
        limiting_categories=limiting_categories,
        findings=findings,
    )


def coverage_gaps_from_snapshot(
    snapshot: MarketOperationalSnapshot,
    *,
    fact_report: FactHealthReport | None = None,
) -> CoverageGapReport:
    fact_report = fact_report or fact_health_from_snapshot(snapshot)
    gaps: list[CoverageGap] = []
    _add_min_count_gap(
        gaps,
        snapshot=snapshot,
        code="too_few_companies",
        area=FactArea.COMPANY,
        actual=len(snapshot.companies),
        minimum=MIN_COMPANY_COUNT,
        message="Market has fewer curated companies than the Layer 32 seed standard.",
        action="Expand the curated company roster for this market.",
    )
    _add_min_count_gap(
        gaps,
        snapshot=snapshot,
        code="too_few_source_references",
        area=FactArea.SOURCE,
        actual=len(snapshot.sources),
        minimum=MIN_SOURCE_COUNT,
        message="Market has fewer source references than the curated import standard.",
        action="Add market-specific source references for company, hiring, and early-career facts.",
    )
    _add_min_count_gap(
        gaps,
        snapshot=snapshot,
        code="too_few_presence_facts",
        area=FactArea.PRESENCE,
        actual=len(snapshot.presence_facts),
        minimum=MIN_PRESENCE_FACT_COUNT,
        message="Market has too few company-presence facts.",
        action="Collect presence observations for each curated company.",
    )
    _add_min_count_gap(
        gaps,
        snapshot=snapshot,
        code="too_few_hiring_facts",
        area=FactArea.HIRING,
        actual=len(snapshot.hiring_facts),
        minimum=MIN_HIRING_FACT_COUNT,
        message="Market has too few hiring facts.",
        action="Refresh regional hiring counts for each curated company.",
    )
    _add_min_count_gap(
        gaps,
        snapshot=snapshot,
        code="too_few_entry_level_facts",
        area=FactArea.ENTRY_LEVEL,
        actual=len(snapshot.entry_level_facts),
        minimum=MIN_ENTRY_LEVEL_FACT_COUNT,
        message="Market has too few early-career facts.",
        action="Refresh internship, co-op, and entry-level program facts.",
    )
    _add_dimension_gap(
        gaps,
        snapshot=snapshot,
        code="missing_internship_data",
        area=FactArea.ENTRY_LEVEL,
        observed_count=sum(
            1
            for row in snapshot.entry_level_facts
            if row.internship_count_status
            in {ObservationStatus.ZERO_OBSERVED.value, ObservationStatus.POSITIVE_OBSERVED.value}
        ),
        total=len(snapshot.entry_level_facts),
        severity=GapSeverity.HIGH,
        message="No comparison-ready internship data is available.",
        action="Refresh early-career internship source references.",
    )
    _add_dimension_gap(
        gaps,
        snapshot=snapshot,
        code="missing_coop_data",
        area=FactArea.ENTRY_LEVEL,
        observed_count=sum(
            1
            for row in snapshot.entry_level_facts
            if row.coop_count_status
            in {ObservationStatus.ZERO_OBSERVED.value, ObservationStatus.POSITIVE_OBSERVED.value}
        ),
        total=len(snapshot.entry_level_facts),
        severity=GapSeverity.MEDIUM,
        message="No comparison-ready co-op data is available.",
        action="Refresh early-career co-op source references.",
    )
    _add_dimension_gap(
        gaps,
        snapshot=snapshot,
        code="missing_30_day_hiring_counts",
        area=FactArea.HIRING,
        observed_count=sum(
            1
            for row in snapshot.hiring_facts
            if row.posting_count_30d_status
            in {ObservationStatus.ZERO_OBSERVED.value, ObservationStatus.POSITIVE_OBSERVED.value}
        ),
        total=len(snapshot.hiring_facts),
        severity=GapSeverity.LOW,
        message="30-day hiring counts are not collected for this market.",
        action="Add 30-day hiring count coverage during the next curated refresh.",
    )
    _add_dimension_gap(
        gaps,
        snapshot=snapshot,
        code="missing_90_day_hiring_counts",
        area=FactArea.HIRING,
        observed_count=sum(
            1
            for row in snapshot.hiring_facts
            if row.posting_count_90d_status
            in {ObservationStatus.ZERO_OBSERVED.value, ObservationStatus.POSITIVE_OBSERVED.value}
        ),
        total=len(snapshot.hiring_facts),
        severity=GapSeverity.LOW,
        message="90-day hiring counts are not collected for this market.",
        action="Add 90-day hiring count coverage during the next curated refresh.",
    )
    unknown_ratio = _ratio(fact_report.unknown_facts, max(fact_report.total_facts, 1))
    if unknown_ratio >= HIGH_UNKNOWN_RATIO:
        gaps.append(
            CoverageGap(
                gap_code="high_unknown_ratio",
                severity=GapSeverity.HIGH,
                market_key=snapshot.market_key,
                affected_area=FactArea.MARKET_IDENTITY,
                message="Unknown fact ratio is high for this market.",
                supporting_counts={
                    "unknown_facts": fact_report.unknown_facts,
                    "total_facts": fact_report.total_facts,
                    "unknown_ratio": round(unknown_ratio, 4),
                },
                recommended_action="Resolve unknown hiring and early-career counts.",
                estimated_impact="ranking_and_output_quality",
            )
        )
    excluded_ratio = _ratio(
        fact_report.ranking_excluded_facts,
        max(fact_report.total_facts, 1),
    )
    if excluded_ratio >= EXCESSIVE_RANKING_EXCLUDED_RATIO:
        gaps.append(
            CoverageGap(
                gap_code="excessive_ranking_exclusions",
                severity=GapSeverity.HIGH,
                market_key=snapshot.market_key,
                affected_area=FactArea.MARKET_IDENTITY,
                message="Too many market facts are excluded from ranking.",
                supporting_counts={
                    "ranking_excluded_facts": fact_report.ranking_excluded_facts,
                    "total_facts": fact_report.total_facts,
                    "ranking_excluded_ratio": round(excluded_ratio, 4),
                },
                recommended_action=(
                    "Review ranking-excluded facts and refresh weak source evidence."
                ),
                estimated_impact="ranking_quality",
            )
        )
    if fact_report.ranking_eligible_facts == 0 and fact_report.total_facts > 0:
        gaps.append(
            CoverageGap(
                gap_code="no_comparison_ready_facts",
                severity=GapSeverity.CRITICAL,
                market_key=snapshot.market_key,
                affected_area=FactArea.MARKET_IDENTITY,
                message="No facts are currently eligible for comparison or ranking.",
                supporting_counts={
                    "ranking_eligible_facts": 0,
                    "total_facts": fact_report.total_facts,
                },
                recommended_action="Run post-import trust and ranking refresh for the market.",
                estimated_impact="comparison_blocking",
            )
        )
    if not _has_strong_early_career_signal(snapshot):
        gaps.append(
            CoverageGap(
                gap_code="no_strong_early_career_signal",
                severity=GapSeverity.MEDIUM,
                market_key=snapshot.market_key,
                affected_area=FactArea.ENTRY_LEVEL,
                message="No strong early-career signal is present.",
                supporting_counts={"entry_level_facts": len(snapshot.entry_level_facts)},
                recommended_action=(
                    "Expand internship, co-op, and formal early-career program evidence."
                ),
                estimated_impact="entry_level_quality",
            )
        )
    concentration = _source_concentration_gap(snapshot)
    if concentration is not None:
        gaps.append(concentration)

    sorted_gaps = tuple(
        sorted(
            gaps,
            key=lambda gap: (
                -_GAP_SEVERITY_ORDER[gap.severity],
                gap.gap_code,
                gap.affected_area.value,
            ),
        )
    )
    return CoverageGapReport(
        market_key=snapshot.market_key,
        gap_count=len(sorted_gaps),
        highest_severity=sorted_gaps[0].severity if sorted_gaps else None,
        gaps=sorted_gaps,
    )


def ranking_exclusions_from_snapshot(
    snapshot: MarketOperationalSnapshot,
) -> RankingExclusionReport:
    diagnostics = tuple(
        _ranking_diagnostic(fact) for fact in snapshot.facts if fact.ranking_excluded
    )
    reason_counts: dict[str, int] = {}
    for diagnostic in diagnostics:
        for category in diagnostic.reason_categories:
            reason_counts[category.value] = reason_counts.get(category.value, 0) + 1
    reason_counts = dict(sorted(reason_counts.items()))
    total = len(snapshot.facts)
    return RankingExclusionReport(
        market_key=snapshot.market_key,
        excluded_fact_count=len(diagnostics),
        total_fact_count=total,
        ranking_limited_ratio=round(_ratio(len(diagnostics), max(total, 1)), 4),
        affected_areas=tuple(sorted({diagnostic.area.value for diagnostic in diagnostics})),
        reason_counts=reason_counts,
        stale_source_exclusion_count=reason_counts.get(
            RankingExclusionCategory.STALE_SOURCE.value,
            0,
        ),
        low_confidence_exclusion_count=reason_counts.get(
            RankingExclusionCategory.LOW_CONFIDENCE.value,
            0,
        ),
        insufficient_evidence_exclusion_count=reason_counts.get(
            RankingExclusionCategory.INSUFFICIENT_EVIDENCE.value,
            0,
        ),
        unsupported_freshness_exclusion_count=reason_counts.get(
            RankingExclusionCategory.UNSUPPORTED_FRESHNESS.value,
            0,
        ),
        trust_or_risk_limitation_count=reason_counts.get(
            RankingExclusionCategory.TRUST_OR_RISK_LIMITED.value,
            0,
        ),
        diagnostics=diagnostics,
    )


def refresh_readiness_from_snapshot(
    snapshot: MarketOperationalSnapshot,
) -> RefreshReadinessReport:
    health = dataset_health_from_snapshot(snapshot)
    source_report = source_aging_from_snapshot(snapshot)
    fact_report = fact_health_from_snapshot(snapshot)
    gap_report = coverage_gaps_from_snapshot(snapshot, fact_report=fact_report)
    ranking_report = ranking_exclusions_from_snapshot(snapshot)
    blocker_classes: list[str] = []
    blocking_conditions: list[str] = []
    warnings: list[str] = []
    actions: list[str] = []

    if not snapshot.validation.ok:
        blocker_classes.append("validation")
        blocking_conditions.append("validation_failed")
        actions.append("Fix curated import validation errors before refresh.")
    if source_report.stale_source_count or source_report.expired_source_count:
        blocker_classes.append("sources")
        blocking_conditions.append("stale_or_expired_sources")
        actions.append("Refresh stale or expired source references.")
    high_gaps = tuple(
        gap
        for gap in gap_report.gaps
        if gap.severity in {GapSeverity.HIGH, GapSeverity.CRITICAL}
        and gap.gap_code not in {"excessive_ranking_exclusions", "no_comparison_ready_facts"}
    )
    if high_gaps:
        blocker_classes.append("coverage")
        blocking_conditions.extend(gap.gap_code for gap in high_gaps)
        actions.append("Expand coverage for high-severity market gaps.")
    if ranking_report.ranking_limited_ratio >= EXCESSIVE_RANKING_EXCLUDED_RATIO:
        blocker_classes.append("ranking")
        blocking_conditions.append("ranking_limited")
        actions.append("Review ranking-excluded facts and weak evidence.")

    if source_report.aging_source_count:
        warnings.append("aging_sources")
        actions.append("Schedule source refresh before sources become stale.")
    low_medium_gaps = tuple(
        gap for gap in gap_report.gaps if gap.severity in {GapSeverity.LOW, GapSeverity.MEDIUM}
    )
    if low_medium_gaps:
        warnings.extend(gap.gap_code for gap in low_medium_gaps)
        actions.extend(gap.recommended_action for gap in low_medium_gaps)

    status = _readiness_status(blocker_classes)
    priority_score = _priority_score(
        health=health,
        source_report=source_report,
        fact_report=fact_report,
        gap_report=gap_report,
        ranking_report=ranking_report,
    )
    return RefreshReadinessReport(
        market_key=snapshot.market_key,
        readiness_status=status,
        blocking_conditions=tuple(dict.fromkeys(blocking_conditions)),
        warnings=tuple(dict.fromkeys(warnings)),
        recommended_next_action=_recommended_readiness_action(status),
        ordered_actions=tuple(dict.fromkeys(actions)) or ("No immediate maintenance action.",),
        reasons=tuple(dict.fromkeys((*blocking_conditions, *warnings))),
        expected_impact=_expected_impact(status),
        maintenance_priority=_maintenance_priority(priority_score),
        priority_score=priority_score,
    )


def build_refresh_readiness_reports(
    session: Session,
    *,
    registry_path: str | Path | None = None,
    as_of: date | datetime | None = None,
) -> tuple[RefreshReadinessReport, ...]:
    reports = [
        refresh_readiness_from_snapshot(snapshot)
        for snapshot in build_all_market_operational_snapshots(
            session,
            registry_path=registry_path,
            as_of=as_of,
        )
    ]
    return tuple(sorted(reports, key=lambda item: (-item.priority_score, item.market_key)))


def platform_summary_from_health_reports(
    health_reports: tuple[DatasetHealthReport, ...],
    readiness_reports: tuple[RefreshReadinessReport, ...],
) -> PlatformImportedMarketSummary:
    highest_priority = readiness_reports[0] if readiness_reports else None
    return PlatformImportedMarketSummary(
        registered_market_count=len(health_reports),
        healthy_market_count=sum(
            1 for report in health_reports if report.health_status is MarketHealthStatus.HEALTHY
        ),
        markets_needing_refresh=sum(
            1
            for report in health_reports
            if report.health_status
            in {
                MarketHealthStatus.NEEDS_REFRESH,
                MarketHealthStatus.STALE_SOURCES,
            }
        ),
        markets_with_limited_coverage=sum(
            1
            for report in health_reports
            if report.health_status is MarketHealthStatus.LIMITED_COVERAGE
        ),
        markets_with_stale_sources=sum(
            1 for report in health_reports if report.counts.stale_source_count > 0
        ),
        total_stale_source_count=sum(report.counts.stale_source_count for report in health_reports),
        total_ranking_excluded_fact_count=sum(
            report.counts.ranking_excluded_fact_count for report in health_reports
        ),
        highest_priority_maintenance_market=(
            highest_priority.market_key if highest_priority is not None else None
        ),
        recommended_next_maintenance_action=(
            highest_priority.recommended_next_action
            if highest_priority is not None
            else "No imported markets are registered for maintenance."
        ),
        overall_health_status=_platform_health_status(health_reports),
    )


def _platform_health_status(
    health_reports: tuple[DatasetHealthReport, ...],
) -> MarketHealthStatus:
    if not health_reports:
        return MarketHealthStatus.NEEDS_REFRESH
    statuses = {report.health_status for report in health_reports}
    for status in _STATUS_PRECEDENCE:
        if status in statuses:
            return status
    return MarketHealthStatus.NEEDS_REFRESH


def _counts(snapshot: MarketOperationalSnapshot) -> MarketOperationalCounts:
    return MarketOperationalCounts(
        company_count=len(snapshot.companies),
        source_count=len(snapshot.sources),
        presence_fact_count=len(snapshot.presence_facts),
        hiring_fact_count=len(snapshot.hiring_facts),
        entry_level_fact_count=len(snapshot.entry_level_facts),
        total_fact_count=len(snapshot.facts),
        unknown_fact_count=sum(1 for fact in snapshot.facts if fact.unknown),
        observed_zero_fact_count=sum(1 for fact in snapshot.facts if fact.observed_zero),
        ranking_eligible_fact_count=sum(1 for fact in snapshot.facts if fact.ranking_eligible),
        ranking_excluded_fact_count=sum(1 for fact in snapshot.facts if fact.ranking_excluded),
        stale_fact_count=sum(1 for fact in snapshot.facts if fact.stale),
        stale_source_count=sum(1 for source in snapshot.sources if source.is_stale),
    )


def _health_status(
    snapshot: MarketOperationalSnapshot,
    *,
    source_report: SourceAgingReport,
    fact_report: FactHealthReport,
    gap_report: CoverageGapReport,
    ranking_report: RankingExclusionReport,
) -> tuple[MarketHealthStatus, tuple[str, ...]]:
    candidates: list[tuple[MarketHealthStatus, str]] = []
    if not snapshot.validation.ok:
        candidates.append((MarketHealthStatus.VALIDATION_FAILED, "validation_failed"))
    if source_report.stale_source_count or source_report.expired_source_count:
        candidates.append((MarketHealthStatus.STALE_SOURCES, "stale_sources_present"))
    if ranking_report.ranking_limited_ratio >= EXCESSIVE_RANKING_EXCLUDED_RATIO:
        candidates.append((MarketHealthStatus.RANKING_LIMITED, "ranking_limited"))
    if snapshot.registry_entry.coverage_status == "partial_curated" or any(
        gap.severity in {GapSeverity.HIGH, GapSeverity.CRITICAL}
        and gap.gap_code not in {"excessive_ranking_exclusions", "no_comparison_ready_facts"}
        for gap in gap_report.gaps
    ):
        candidates.append((MarketHealthStatus.LIMITED_COVERAGE, "coverage_limited"))
    if source_report.aging_source_count or fact_report.stale_facts:
        candidates.append((MarketHealthStatus.NEEDS_REFRESH, "refresh_recommended"))
    if not candidates:
        return (MarketHealthStatus.HEALTHY, ("all_primary_checks_passed",))
    for status in _STATUS_PRECEDENCE:
        reasons = tuple(reason for candidate, reason in candidates if candidate is status)
        if reasons:
            return status, reasons
    return (MarketHealthStatus.HEALTHY, ("all_primary_checks_passed",))


def _recommended_health_action(status: MarketHealthStatus) -> str:
    return {
        MarketHealthStatus.HEALTHY: "Keep the dataset on the normal curated refresh cadence.",
        MarketHealthStatus.NEEDS_REFRESH: (
            "Refresh aging source references before they become stale."
        ),
        MarketHealthStatus.LIMITED_COVERAGE: (
            "Expand curated market coverage before relying on comparisons."
        ),
        MarketHealthStatus.STALE_SOURCES: (
            "Refresh stale source references and rerun post-import diagnostics."
        ),
        MarketHealthStatus.VALIDATION_FAILED: "Fix curated source-file validation errors.",
        MarketHealthStatus.RANKING_LIMITED: (
            "Review ranking-excluded facts and refresh weak evidence."
        ),
    }[status]


def _source_diagnostic(source: SourceSnapshot) -> SourceDiagnostic:
    affected_areas = tuple(sorted({fact_type for fact_type, _fact_id in source.fact_refs}))
    impact = (
        "Stale or expired source affects ranking eligibility."
        if source.is_stale and source.fact_refs
        else "Source is current for imported facts."
        if source.fact_refs
        else "Source is not currently linked to canonical imported facts."
    )
    return SourceDiagnostic(
        source_id=source.source_id,
        source_label=source.source_label,
        source_type=source.source_type,
        data_origin=source.data_origin,
        observed_date=source.observed_date.isoformat() if source.observed_date else None,
        collected_date=source.collected_date.isoformat() if source.collected_date else None,
        age_days=source.age_days,
        freshness_status=source.freshness_status,
        is_stale=source.is_stale,
        license_or_terms_category=source.license_or_terms_category,
        fact_usage_count=len(source.fact_refs),
        affected_areas=affected_areas,
        affects_ranking_eligibility=source.is_stale and bool(source.fact_refs),
        impact=impact,
    )


def _fact_finding(fact: FactSnapshot) -> FactHealthFinding:
    reasons = tuple(category.value for category in _ranking_categories(fact))
    if fact.ranking_eligible:
        message = "Fact is ranking-eligible."
    elif reasons:
        message = f"Fact is ranking-excluded: {', '.join(reasons)}."
    else:
        message = "Fact is ranking-excluded."
    return FactHealthFinding(
        fact_type=fact.fact_type,
        fact_id=fact.fact_id,
        company_id=fact.company_id,
        region_id=fact.region_id,
        area=fact.area,
        ranking_eligible=fact.ranking_eligible,
        ranking_excluded_reasons=reasons,
        freshness_status=fact.freshness_status,
        confidence=fact.confidence,
        observation_status=fact.observation_status,
        source_count=fact.source_count,
        public_message=message,
    )


def _missing_useful_dimensions(fact: FactSnapshot) -> bool:
    if fact.area not in {FactArea.HIRING, FactArea.ENTRY_LEVEL}:
        return False
    return any(status in UNOBSERVED_STATUSES for status in fact.count_statuses)


def _weak_source_coverage(fact: FactSnapshot) -> bool:
    return fact.source_count == 0 or fact.low_confidence or fact.freshness_status == "unknown"


def _trust_or_risk_limited(fact: FactSnapshot) -> bool:
    if fact.ranking_eligible:
        return False
    return fact.risk_level in {"medium", "high", "critical", "unknown", None}


def _limiting_fact_categories(facts: tuple[FactSnapshot, ...]) -> tuple[str, ...]:
    categories: set[str] = set()
    for fact in facts:
        if fact.stale:
            categories.add("stale_facts")
        if fact.low_confidence:
            categories.add("low_confidence_facts")
        if fact.unknown:
            categories.add("unknown_facts")
        if fact.ranking_excluded:
            categories.add(f"{fact.area.value}_ranking_excluded")
    return tuple(sorted(categories))


def _add_min_count_gap(
    gaps: list[CoverageGap],
    *,
    snapshot: MarketOperationalSnapshot,
    code: str,
    area: FactArea,
    actual: int,
    minimum: int,
    message: str,
    action: str,
) -> None:
    if actual >= minimum:
        return
    severity = GapSeverity.CRITICAL if actual == 0 else GapSeverity.HIGH
    gaps.append(
        CoverageGap(
            gap_code=code,
            severity=severity,
            market_key=snapshot.market_key,
            affected_area=area,
            message=message,
            supporting_counts={"actual": actual, "minimum": minimum},
            recommended_action=action,
            estimated_impact="coverage",
        )
    )


def _add_dimension_gap(
    gaps: list[CoverageGap],
    *,
    snapshot: MarketOperationalSnapshot,
    code: str,
    area: FactArea,
    observed_count: int,
    total: int,
    severity: GapSeverity,
    message: str,
    action: str,
) -> None:
    if total == 0 or observed_count > 0:
        return
    gaps.append(
        CoverageGap(
            gap_code=code,
            severity=severity,
            market_key=snapshot.market_key,
            affected_area=area,
            message=message,
            supporting_counts={"observed_count": observed_count, "total": total},
            recommended_action=action,
            estimated_impact="coverage",
        )
    )


def _has_strong_early_career_signal(snapshot: MarketOperationalSnapshot) -> bool:
    return any(
        (row.internship_count or 0) > 0
        or (row.coop_count or 0) > 0
        or (row.entry_level_full_time_count or 0) > 0
        or row.formal_early_career_program_flag
        for row in snapshot.entry_level_facts
    )


def _source_concentration_gap(
    snapshot: MarketOperationalSnapshot,
) -> CoverageGap | None:
    if not snapshot.sources or not snapshot.facts:
        return None
    most_used = max(snapshot.sources, key=lambda source: (len(source.fact_refs), source.source_id))
    ratio = _ratio(len(most_used.fact_refs), len(snapshot.facts))
    weak_or_stale = most_used.is_stale or most_used.confidence in {"low", "unknown"}
    if ratio < SOURCE_CONCENTRATION_RATIO or not weak_or_stale:
        return None
    return CoverageGap(
        gap_code="source_concentration_risk",
        severity=GapSeverity.HIGH if most_used.is_stale else GapSeverity.MEDIUM,
        market_key=snapshot.market_key,
        affected_area=FactArea.SOURCE,
        message="Too many facts depend on one weak or stale source reference.",
        supporting_counts={
            "source_fact_usage_count": len(most_used.fact_refs),
            "total_facts": len(snapshot.facts),
            "source_usage_ratio": round(ratio, 4),
        },
        recommended_action=(
            "Add corroborating source references for facts using the concentrated source."
        ),
        estimated_impact="source_resilience",
    )


def _ranking_diagnostic(fact: FactSnapshot) -> RankingExclusionDiagnostic:
    categories = _ranking_categories(fact)
    explanation = (
        "Ranking exclusion is caused by "
        + ", ".join(category.value for category in categories)
        + "."
    )
    return RankingExclusionDiagnostic(
        fact_type=fact.fact_type,
        fact_id=fact.fact_id,
        area=fact.area,
        reason_categories=categories,
        explanation=explanation,
    )


def _ranking_categories(fact: FactSnapshot) -> tuple[RankingExclusionCategory, ...]:
    if fact.ranking_eligible:
        return ()
    categories: list[RankingExclusionCategory] = []
    codes = set(fact.ranking_reason_codes)
    if RankingInfluenceReasonCode.STALE_SOURCE.value in codes:
        categories.append(RankingExclusionCategory.STALE_SOURCE)
    if RankingInfluenceReasonCode.LOW_CONFIDENCE.value in codes:
        categories.append(RankingExclusionCategory.LOW_CONFIDENCE)
    if RankingInfluenceReasonCode.SOURCE_NOT_ALLOWED.value in codes:
        categories.append(RankingExclusionCategory.SOURCE_NOT_ALLOWED)
    if RankingInfluenceReasonCode.MISSING_SOURCE.value in codes:
        categories.append(RankingExclusionCategory.MISSING_SOURCE)
    if (
        RankingInfluenceReasonCode.EVIDENCE_REQUIREMENTS_MISSING.value in codes
        or RankingInfluenceReasonCode.CORROBORATION_MISSING.value in codes
    ):
        categories.append(RankingExclusionCategory.INSUFFICIENT_EVIDENCE)
    if (
        RankingInfluenceReasonCode.ASSESSMENT_MISSING.value in codes
        or RankingInfluenceReasonCode.LEGACY_UNASSESSED.value in codes
        or not codes
    ):
        categories.append(RankingExclusionCategory.UNASSESSED)
        categories.append(RankingExclusionCategory.INSUFFICIENT_EVIDENCE)
    if fact.freshness_status == FreshnessStatus.UNKNOWN.value:
        categories.append(RankingExclusionCategory.UNSUPPORTED_FRESHNESS)
    if RankingInfluenceReasonCode.RANKING_DEFAULT_DENIED.value in codes:
        categories.append(RankingExclusionCategory.DEFAULT_DENIED)
    if fact.trust_tier in {
        "partner_submitted",
        "conflicting",
        "quarantined",
        "blocked",
        "ranking_ineligible",
        "not_assessed",
        None,
    }:
        categories.append(RankingExclusionCategory.TRUST_OR_RISK_LIMITED)
    return tuple(dict.fromkeys(categories))


def _readiness_status(blocker_classes: list[str]) -> RefreshReadinessStatus:
    distinct = set(blocker_classes)
    if "validation" in distinct:
        return RefreshReadinessStatus.NEEDS_VALIDATION_FIX
    if len(distinct) > 1:
        return RefreshReadinessStatus.NOT_READY
    if "sources" in distinct:
        return RefreshReadinessStatus.NEEDS_SOURCE_REFRESH
    if "coverage" in distinct:
        return RefreshReadinessStatus.NEEDS_COVERAGE_EXPANSION
    if "ranking" in distinct:
        return RefreshReadinessStatus.NEEDS_RANKING_REVIEW
    return RefreshReadinessStatus.READY


def _priority_score(
    *,
    health: DatasetHealthReport,
    source_report: SourceAgingReport,
    fact_report: FactHealthReport,
    gap_report: CoverageGapReport,
    ranking_report: RankingExclusionReport,
) -> int:
    score = 0
    if health.health_status is MarketHealthStatus.VALIDATION_FAILED:
        score += 100
    score += source_report.expired_source_count * 20
    score += source_report.stale_source_count * 15
    score += sum(source.fact_usage_count for source in source_report.important_stale_sources)
    score += ranking_report.excluded_fact_count * 3
    score += fact_report.unknown_facts
    for gap in gap_report.gaps:
        score += {
            GapSeverity.CRITICAL: 25,
            GapSeverity.HIGH: 15,
            GapSeverity.MEDIUM: 6,
            GapSeverity.LOW: 2,
        }[gap.severity]
    return score


def _maintenance_priority(priority_score: int) -> MaintenancePriority:
    if priority_score >= 75:
        return MaintenancePriority.CRITICAL
    if priority_score >= 35:
        return MaintenancePriority.HIGH
    if priority_score >= 12:
        return MaintenancePriority.MEDIUM
    return MaintenancePriority.LOW


def _recommended_readiness_action(status: RefreshReadinessStatus) -> str:
    return {
        RefreshReadinessStatus.READY: "Dataset is ready for the normal curated refresh path.",
        RefreshReadinessStatus.NEEDS_SOURCE_REFRESH: "Refresh stale source references first.",
        RefreshReadinessStatus.NEEDS_COVERAGE_EXPANSION: (
            "Expand coverage before treating the refresh as complete."
        ),
        RefreshReadinessStatus.NEEDS_VALIDATION_FIX: (
            "Fix validation errors before any import refresh."
        ),
        RefreshReadinessStatus.NEEDS_RANKING_REVIEW: (
            "Review ranking-excluded facts before comparison use."
        ),
        RefreshReadinessStatus.NOT_READY: (
            "Resolve validation, source, coverage, or ranking blockers before refresh."
        ),
    }[status]


def _expected_impact(status: RefreshReadinessStatus) -> str:
    return {
        RefreshReadinessStatus.READY: "normal_maintenance",
        RefreshReadinessStatus.NEEDS_SOURCE_REFRESH: "freshness_and_ranking",
        RefreshReadinessStatus.NEEDS_COVERAGE_EXPANSION: "coverage_and_output_quality",
        RefreshReadinessStatus.NEEDS_VALIDATION_FIX: "import_blocking",
        RefreshReadinessStatus.NEEDS_RANKING_REVIEW: "ranking_quality",
        RefreshReadinessStatus.NOT_READY: "multiple_blockers",
    }[status]


def _coverage_summary(
    snapshot: MarketOperationalSnapshot,
    gap_report: CoverageGapReport,
) -> str:
    if not snapshot.canonical_imported:
        return "Canonical imported records are not loaded."
    if snapshot.registry_entry.coverage_status == "partial_curated":
        return "Partial curated coverage with diagnostic gaps available."
    if gap_report.gap_count:
        return "Curated coverage is loaded with maintenance gaps."
    return "Curated coverage is loaded."


def _freshness_summary(source_report: SourceAgingReport) -> str:
    if source_report.expired_source_count:
        return "One or more source references are expired."
    if source_report.stale_source_count:
        return "One or more source references are stale."
    if source_report.aging_source_count:
        return "One or more source references are aging."
    return "Source references are current."


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator
