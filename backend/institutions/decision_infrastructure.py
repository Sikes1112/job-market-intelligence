"""Layer 22 institutional decision infrastructure payloads and builders."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.companies.models import Company
from backend.entry_level.models import CompanyRegionEntryLevel
from backend.geography.models import Region
from backend.hiring.models import CompanyRegionHiring
from backend.institutions.dashboard import (
    InstitutionalAggregateItem,
    InstitutionalDashboardPayload,
)
from backend.institutions.privacy import (
    InstitutionPrivacyMetadata,
    build_privacy_metadata,
)
from backend.platform_intelligence.history_repository import HistoryRepository
from backend.platform_intelligence.predictive_exports import export_predictive_observations
from backend.predictive.reports import PredictiveReportBuilder
from backend.presence.models import CompanyRegionPresence

DEFAULT_DECISION_TIME_HORIZON = "next_12_months"


class InstitutionDecisionConfidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    level: str
    score: float = Field(ge=0.0, le=1.0)
    factors: list[str] = Field(default_factory=list)


class InstitutionDecisionEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    confidence: InstitutionDecisionConfidence
    freshness: str
    provenance: list[str] = Field(default_factory=list)
    source_basis: list[str] = Field(default_factory=list)
    historical_depth: dict[str, Any] = Field(default_factory=dict)


class InstitutionDecisionMetric(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_key: str
    label: str
    value: float | int | str | None
    unit: str | None = None
    decision_use: str
    evidence: InstitutionDecisionEvidence


class InstitutionDecisionSection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    section_key: str
    title: str
    what_is_happening: str
    why_it_matters: str
    considerations: list[str] = Field(default_factory=list)
    metrics: list[InstitutionDecisionMetric] = Field(default_factory=list)
    evidence: InstitutionDecisionEvidence
    warnings: list[str] = Field(default_factory=list)


class InstitutionForecastNote(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    forecast_label: str
    forecast_type: str
    affected_entity: str
    time_horizon: str
    safe_display_summary: str
    confidence: dict[str, Any]
    source_basis: dict[str, Any]
    historical_depth: dict[str, Any]
    uncertainty: dict[str, Any]
    reasoning_trail: list[str]
    supporting_signals: list[dict[str, Any]]


class InstitutionDecisionDashboardPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    organization_id: str
    organization_name: str
    generated_at: datetime
    time_horizon: str = DEFAULT_DECISION_TIME_HORIZON
    summary: InstitutionDecisionSection
    target_markets: list[InstitutionDecisionSection] = Field(default_factory=list)
    regional_trends: list[InstitutionDecisionSection] = Field(default_factory=list)
    program_alignment: list[InstitutionDecisionSection] = Field(default_factory=list)
    employer_geography: list[InstitutionDecisionSection] = Field(default_factory=list)
    internship_access: list[InstitutionDecisionSection] = Field(default_factory=list)
    industry_demand: list[InstitutionDecisionSection] = Field(default_factory=list)
    forecast_notes: list[InstitutionForecastNote] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    confidence: InstitutionDecisionConfidence
    freshness: str
    provenance: list[str] = Field(default_factory=list)
    privacy: InstitutionPrivacyMetadata
    limitations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CurriculumProgramMapping(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    program_name: str
    relevant_role_families: list[str] = Field(default_factory=list)
    strongest_aligned_markets: list[InstitutionDecisionMetric] = Field(default_factory=list)
    emerging_markets: list[InstitutionDecisionMetric] = Field(default_factory=list)
    weak_or_saturated_markets: list[InstitutionDecisionMetric] = Field(default_factory=list)
    skills_with_rising_demand: list[str] = Field(default_factory=list)
    employer_relationship_targets: list[str] = Field(default_factory=list)
    advising_recommendations: list[str] = Field(default_factory=list)
    confidence: InstitutionDecisionConfidence
    freshness: str
    provenance: list[str] = Field(default_factory=list)
    sparse_data_warnings: list[str] = Field(default_factory=list)
    privacy: InstitutionPrivacyMetadata


class CurriculumMarketMappingPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    organization_id: str
    organization_name: str
    generated_at: datetime
    programs: list[CurriculumProgramMapping] = Field(default_factory=list)
    confidence: InstitutionDecisionConfidence
    freshness: str
    provenance: list[str] = Field(default_factory=list)
    privacy: InstitutionPrivacyMetadata
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class InstitutionWorkforceReportType(StrEnum):
    REGIONAL_WORKFORCE_OPPORTUNITY = "regional_workforce_opportunity"
    EARLY_CAREER_MARKET_ACCESS = "early_career_market_access"
    TECH_SECTOR_GROWTH = "tech_sector_growth"
    STUDENT_PLACEMENT_STRATEGY = "student_placement_strategy"
    EMPLOYER_GEOGRAPHY = "employer_geography"
    PROGRAM_ALIGNMENT = "program_alignment"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class InstitutionWorkforceReportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str
    report_type: InstitutionWorkforceReportType
    audience: str
    scope: str
    generated_at: datetime
    summary: str
    key_findings: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    supporting_metrics: list[InstitutionDecisionMetric] = Field(default_factory=list)
    confidence: InstitutionDecisionConfidence
    freshness: str
    provenance: list[str] = Field(default_factory=list)
    privacy_statement: str
    privacy: InstitutionPrivacyMetadata
    limitations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    export_ready: dict[str, Any] = Field(default_factory=dict)


class InstitutionBenchmarkItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    benchmark_subject: str
    comparison_market_set: list[str] = Field(default_factory=list)
    opportunity_score: float = Field(ge=0.0, le=100.0)
    alignment_score: float = Field(ge=0.0, le=100.0)
    gap_score: float = Field(ge=0.0, le=100.0)
    emerging_region_gap: float = Field(ge=0.0, le=100.0)
    employer_access_gap: float = Field(ge=0.0, le=100.0)
    internship_access_gap: float = Field(ge=0.0, le=100.0)
    recommendation_summary: str
    supporting_rationale: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class InstitutionBenchmarkPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    organization_id: str
    organization_name: str
    generated_at: datetime
    benchmarks: list[InstitutionBenchmarkItem] = Field(default_factory=list)
    confidence: InstitutionDecisionConfidence
    freshness: str
    provenance: list[str] = Field(default_factory=list)
    privacy: InstitutionPrivacyMetadata
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class ProgramDefinition:
    program_name: str
    role_families: tuple[str, ...]
    sectors: tuple[str, ...]
    skills: tuple[str, ...]


@dataclass
class MarketDecisionSnapshot:
    region_id: str
    region_label: str
    active_postings: int = 0
    hiring_company_count: int = 0
    internship_count: int = 0
    coop_count: int = 0
    entry_level_count: int = 0
    formal_program_count: int = 0
    presence_company_count: int = 0
    entry_level_access_score: float = 0.0
    trend_signal: str = "unknown"
    sectors: Counter[str] = field(default_factory=Counter)
    role_families: Counter[str] = field(default_factory=Counter)
    employer_names: list[str] = field(default_factory=list)
    confidence_values: list[str] = field(default_factory=list)
    freshness_values: list[str] = field(default_factory=list)
    source_count: int = 0

    @property
    def opportunity_score(self) -> float:
        trend_boost = {
            "increasing": 10.0,
            "stable": 4.0,
            "seasonal": 3.0,
            "decreasing": -8.0,
            "weakening": -8.0,
        }.get(self.trend_signal, 0.0)
        score = (
            min(self.active_postings, 160) * 0.22
            + self.hiring_company_count * 7.0
            + self.internship_count * 4.0
            + self.coop_count * 3.0
            + self.entry_level_count * 2.0
            + self.formal_program_count * 4.0
            + self.presence_company_count * 2.0
            + min(self.entry_level_access_score, 100.0) * 0.25
            + trend_boost
        )
        return round(max(0.0, min(100.0, score)), 1)


PROGRAM_DEFINITIONS: tuple[ProgramDefinition, ...] = (
    ProgramDefinition(
        program_name="Computer Science",
        role_families=("software_engineering", "ai_ml", "cloud_infrastructure"),
        sectors=("software", "ai", "cloud"),
        skills=("distributed systems", "machine learning foundations", "cloud deployment"),
    ),
    ProgramDefinition(
        program_name="Cybersecurity",
        role_families=("security_engineering", "security_operations", "cloud_security"),
        sectors=("cybersecurity", "cloud", "software"),
        skills=("identity security", "incident response", "secure cloud architecture"),
    ),
    ProgramDefinition(
        program_name="Data Analytics",
        role_families=("data_analytics", "data_engineering", "business_intelligence"),
        sectors=("data", "ai", "software"),
        skills=("analytics engineering", "model evaluation", "data storytelling"),
    ),
    ProgramDefinition(
        program_name="Product Management",
        role_families=("product_management", "product_operations", "technical_product"),
        sectors=("product", "software", "ai"),
        skills=("market discovery", "technical roadmapping", "product analytics"),
    ),
)


def build_decision_dashboard(
    session: Session,
    *,
    dashboard: InstitutionalDashboardPayload,
) -> InstitutionDecisionDashboardPayload:
    generated_at = datetime.now(UTC)
    markets = _market_snapshots(session)
    privacy = _privacy_for_dashboard(dashboard, suppressed_fields=_suppressed_fields(dashboard))
    evidence = _overall_evidence(markets, dashboard)
    top_markets = _top_markets(markets, limit=5)
    visible_target_ids = _visible_target_region_ids(dashboard)
    forecast_notes = _forecast_notes(session, [market.region_id for market in top_markets])
    warnings = _dashboard_warnings(dashboard, markets, forecast_notes)
    summary = _section(
        section_key="summary",
        title="Institutional Decision Summary",
        what_is_happening=_summary_text(dashboard, top_markets),
        why_it_matters=(
            "This view connects aggregate student attention, market-level hiring, "
            "employer geography, internships, industry demand, and bounded forecasts "
            "to advising, curriculum, employer partnership, and workforce decisions."
        ),
        considerations=_recommended_actions(dashboard, markets, forecast_notes)[:3],
        metrics=[
            _metric(
                "cohort_size",
                "Cohort size",
                dashboard.cohort_size,
                "students",
                "Determines whether cohort-derived sections can be displayed.",
                evidence,
            ),
            _metric(
                "comparison_markets",
                "Markets compared",
                len(markets),
                "regions",
                "Shows the external market set used for opportunity comparisons.",
                evidence,
            ),
        ],
        evidence=evidence,
        warnings=warnings,
    )
    return InstitutionDecisionDashboardPayload(
        organization_id=dashboard.organization_id,
        organization_name=dashboard.organization_name,
        generated_at=generated_at,
        summary=summary,
        target_markets=_target_market_sections(dashboard, markets, evidence),
        regional_trends=_regional_trend_sections(top_markets, evidence),
        program_alignment=_program_alignment_sections(markets, evidence),
        employer_geography=_employer_geography_sections(markets, evidence),
        internship_access=_internship_access_sections(markets, evidence),
        industry_demand=_industry_demand_sections(markets, evidence),
        forecast_notes=forecast_notes,
        recommended_actions=_recommended_actions(dashboard, markets, forecast_notes),
        confidence=evidence.confidence,
        freshness=evidence.freshness,
        provenance=evidence.provenance,
        privacy=privacy,
        limitations=_limitations(dashboard, markets),
        warnings=warnings + _gap_warnings(visible_target_ids, markets),
    )


def build_curriculum_market_mapping(
    session: Session,
    *,
    dashboard: InstitutionalDashboardPayload,
) -> CurriculumMarketMappingPayload:
    generated_at = datetime.now(UTC)
    markets = _market_snapshots(session)
    privacy = _privacy_for_dashboard(dashboard)
    evidence = _overall_evidence(markets, dashboard)
    programs = [
        _program_mapping(program, markets, dashboard, privacy)
        for program in PROGRAM_DEFINITIONS
    ]
    return CurriculumMarketMappingPayload(
        organization_id=dashboard.organization_id,
        organization_name=dashboard.organization_name,
        generated_at=generated_at,
        programs=programs,
        confidence=evidence.confidence,
        freshness=evidence.freshness,
        provenance=evidence.provenance,
        privacy=privacy,
        warnings=_dashboard_warnings(dashboard, markets, []),
        limitations=[
            (
                "Program mappings are deterministic sample structures until "
                "producer-owned curriculum ingestion is connected."
            ),
            "Mappings are decision intelligence, not student-level placement predictions.",
        ],
    )


def build_workforce_report(
    session: Session,
    *,
    dashboard: InstitutionalDashboardPayload,
    report_type: InstitutionWorkforceReportType,
) -> InstitutionWorkforceReportPayload:
    generated_at = datetime.now(UTC)
    markets = _market_snapshots(session)
    evidence = _overall_evidence(markets, dashboard)
    privacy = _privacy_for_dashboard(dashboard)
    title = _report_title(report_type, dashboard.organization_name)
    findings = _report_findings(report_type, dashboard, markets)
    actions = _report_actions(report_type, dashboard, markets)
    return InstitutionWorkforceReportPayload(
        title=title,
        report_type=report_type,
        audience=_report_audience(report_type),
        scope=f"{dashboard.organization_name} aggregate cohort and public market intelligence",
        generated_at=generated_at,
        summary=_report_summary(report_type, findings),
        key_findings=findings,
        recommended_actions=actions,
        supporting_metrics=_report_metrics(report_type, markets, evidence),
        confidence=evidence.confidence,
        freshness=evidence.freshness,
        provenance=evidence.provenance,
        privacy_statement=(
            "This report is generated from aggregate cohort-level and public market-level "
            "signals; it does not include raw individual student behavior."
        ),
        privacy=privacy,
        limitations=_limitations(dashboard, markets),
        warnings=_dashboard_warnings(dashboard, markets, []),
        export_ready={
            "structure": "sectioned_json",
            "csv_summary": "available_from_supporting_metrics",
            "pdf_generation": "deferred_to_existing_export_infrastructure",
        },
    )


def build_institution_benchmarks(
    session: Session,
    *,
    dashboard: InstitutionalDashboardPayload,
) -> InstitutionBenchmarkPayload:
    generated_at = datetime.now(UTC)
    markets = _market_snapshots(session)
    evidence = _overall_evidence(markets, dashboard)
    privacy = _privacy_for_dashboard(
        dashboard,
        suppressed_fields=_suppressed_fields(dashboard),
    )
    benchmarks = _benchmark_items(dashboard, markets)
    return InstitutionBenchmarkPayload(
        organization_id=dashboard.organization_id,
        organization_name=dashboard.organization_name,
        generated_at=generated_at,
        benchmarks=benchmarks,
        confidence=evidence.confidence,
        freshness=evidence.freshness,
        provenance=evidence.provenance,
        privacy=privacy,
        warnings=_dashboard_warnings(dashboard, markets, []),
        limitations=[
            (
                "Benchmark scores are deterministic directional comparisons "
                "against observed market opportunity, not opaque model outputs."
            ),
            "Forecast-based gaps should be treated as prompts for review, not guarantees.",
        ],
    )


def _market_snapshots(session: Session) -> list[MarketDecisionSnapshot]:
    regions = {
        row.region_id: row.display_name
        for row in session.execute(select(Region).order_by(Region.region_id)).scalars()
    }
    markets = {
        region_id: MarketDecisionSnapshot(region_id=region_id, region_label=label)
        for region_id, label in regions.items()
    }
    companies = {
        row.company_id: row
        for row in session.execute(select(Company).order_by(Company.company_id)).scalars()
    }

    hiring_rows = list(
        session.execute(
            select(CompanyRegionHiring).order_by(
                CompanyRegionHiring.region_id,
                CompanyRegionHiring.company_id,
            )
        ).scalars()
    )
    for row in hiring_rows:
        market = markets.setdefault(
            row.region_id,
            MarketDecisionSnapshot(
                region_id=row.region_id,
                region_label=_display_label(row.region_id),
            ),
        )
        company = companies.get(row.company_id)
        market.active_postings += row.active_posting_count_now or 0
        if row.currently_hiring_flag:
            market.hiring_company_count += 1
        if row.hiring_program_count:
            market.formal_program_count += row.hiring_program_count
        market.trend_signal = _dominant_signal(
            [market.trend_signal, row.annualized_trend_signal]
        )
        market.confidence_values.append(row.hiring_confidence or "limited")
        market.source_count += 1
        _add_company_context(market, company, row.role_family_summary)

    entry_rows = list(
        session.execute(
            select(CompanyRegionEntryLevel).order_by(
                CompanyRegionEntryLevel.region_id,
                CompanyRegionEntryLevel.company_id,
            )
        ).scalars()
    )
    for row in entry_rows:
        market = markets.setdefault(
            row.region_id,
            MarketDecisionSnapshot(
                region_id=row.region_id,
                region_label=_display_label(row.region_id),
            ),
        )
        company = companies.get(row.company_id)
        market.internship_count += row.internship_count or 0
        market.coop_count += row.coop_count or 0
        market.entry_level_count += row.entry_level_full_time_count or 0
        if row.formal_early_career_program_flag:
            market.formal_program_count += 1
        if row.entry_level_access_score is not None:
            market.entry_level_access_score = max(
                market.entry_level_access_score,
                float(row.entry_level_access_score),
            )
        market.confidence_values.append(row.entry_level_confidence or "limited")
        market.source_count += 1
        _add_company_context(market, company, None)

    presence_rows = list(
        session.execute(
            select(CompanyRegionPresence).order_by(
                CompanyRegionPresence.region_id,
                CompanyRegionPresence.company_id,
            )
        ).scalars()
    )
    for row in presence_rows:
        market = markets.setdefault(
            row.region_id,
            MarketDecisionSnapshot(
                region_id=row.region_id,
                region_label=_display_label(row.region_id),
            ),
        )
        company = companies.get(row.company_id)
        if row.presence_status in {"present", "active", "confirmed"} or any(
            [
                row.office_evidence_flag,
                row.operations_evidence_flag,
                row.hiring_evidence_flag,
            ]
        ):
            market.presence_company_count += 1
        market.confidence_values.append(row.presence_confidence or "limited")
        market.source_count += 1
        _add_company_context(market, company, None)

    return sorted(
        [market for market in markets.values() if market.source_count > 0],
        key=lambda item: (-item.opportunity_score, item.region_label, item.region_id),
    )


def _add_company_context(
    market: MarketDecisionSnapshot,
    company: Company | None,
    role_family_summary: Any,
) -> None:
    if company is not None:
        if company.company_name not in market.employer_names:
            market.employer_names.append(company.company_name)
        for sector in (company.sector_primary, company.sector_secondary):
            if sector:
                market.sectors[_normalize_key(sector)] += 1
    if isinstance(role_family_summary, dict):
        for key, value in role_family_summary.items():
            if isinstance(value, (int, float)) and value > 0:
                market.role_families[_normalize_key(str(key))] += int(value)
            elif isinstance(value, str):
                market.role_families[_normalize_key(value)] += 1
    elif isinstance(role_family_summary, list):
        for value in role_family_summary:
            if isinstance(value, str):
                market.role_families[_normalize_key(value)] += 1


def _target_market_sections(
    dashboard: InstitutionalDashboardPayload,
    markets: list[MarketDecisionSnapshot],
    evidence: InstitutionDecisionEvidence,
) -> list[InstitutionDecisionSection]:
    market_lookup = {market.region_id: market for market in markets}
    sections: list[InstitutionDecisionSection] = []
    visible_items = [item for item in dashboard.popular_target_markets if not item.suppressed]
    if not visible_items:
        return [
            _section(
                section_key="target_markets_suppressed",
                title="Student Target Markets",
                what_is_happening=(
                    "Cohort target-market detail is suppressed because no category "
                    "met the minimum group threshold."
                ),
                why_it_matters=(
                    "Advising strategy should wait for a larger privacy-safe cohort "
                    "before interpreting student attention patterns."
                ),
                considerations=[
                    (
                        "Use public market opportunity sections without inferring "
                        "individual student intent."
                    )
                ],
                evidence=evidence,
                warnings=["Small-group target-market detail is withheld."],
            )
        ]
    for item in visible_items[:5]:
        region_id = _metadata_text(item, "region_id")
        market = market_lookup.get(region_id or "")
        sections.append(
            _section(
                section_key=f"target_market:{region_id or item.label}",
                title=item.label,
                what_is_happening=(
                    f"{item.count} students are represented in this aggregate target-market bucket."
                ),
                why_it_matters=(
                    "Student attention can be compared with external market opportunity "
                    "before prioritizing advising, alumni outreach, or employer relationships."
                ),
                considerations=_target_market_considerations(item, market),
                metrics=[
                    _metric(
                        "student_attention_count",
                        "Aggregate student attention",
                        item.count,
                        "students",
                        "Indicates cohort-level interest that met the privacy threshold.",
                        evidence,
                    ),
                    _metric(
                        "market_opportunity_score",
                        "Observed opportunity score",
                        market.opportunity_score if market else None,
                        "0-100",
                        "Compares cohort attention with public market opportunity.",
                        evidence,
                    ),
                ],
                evidence=evidence,
                warnings=(
                    []
                    if market
                    else ["Market opportunity context is limited for this target market."]
                ),
            )
        )
    return sections


def _regional_trend_sections(
    markets: list[MarketDecisionSnapshot],
    evidence: InstitutionDecisionEvidence,
) -> list[InstitutionDecisionSection]:
    return [
        _section(
            section_key=f"regional_trend:{market.region_id}",
            title=market.region_label,
            what_is_happening=(
                f"{market.region_label} has an observed opportunity score of "
                f"{market.opportunity_score} with {market.hiring_company_count} hiring employers."
            ),
            why_it_matters=(
                "Regional opportunity movement helps advisors decide which cities to "
                "prioritize, monitor, or treat cautiously."
            ),
            considerations=[
                _trend_consideration(market),
                "Verify current employer openings before making program-wide advising shifts.",
            ],
            metrics=_market_metrics(market, evidence),
            evidence=evidence,
            warnings=_market_warnings(market),
        )
        for market in markets[:5]
    ]


def _program_alignment_sections(
    markets: list[MarketDecisionSnapshot],
    evidence: InstitutionDecisionEvidence,
) -> list[InstitutionDecisionSection]:
    sections: list[InstitutionDecisionSection] = []
    for program in PROGRAM_DEFINITIONS:
        aligned = _aligned_markets(program, markets)
        sections.append(
            _section(
                section_key=f"program_alignment:{_normalize_key(program.program_name)}",
                title=program.program_name,
                what_is_happening=_program_alignment_summary(program, aligned),
                why_it_matters=(
                    "Program-market alignment shows where curriculum planning and "
                    "advising conversations can connect to observed employer demand."
                ),
                considerations=[
                    (
                        f"Discuss {', '.join(program.skills[:2])} in advising and "
                        "curriculum review."
                    ),
                    (
                        "Use weak or sparse market signals as review prompts, not "
                        "proof of program underperformance."
                    ),
                ],
                metrics=[
                    _metric(
                        "aligned_market_count",
                        "Aligned markets",
                        len(aligned),
                        "markets",
                        (
                            "Shows how many observed markets match the program role "
                            "families or sectors."
                        ),
                        evidence,
                    )
                ],
                evidence=evidence,
                warnings=(
                    []
                    if aligned
                    else ["Observed market data is sparse for this program mapping."]
                ),
            )
        )
    return sections


def _employer_geography_sections(
    markets: list[MarketDecisionSnapshot],
    evidence: InstitutionDecisionEvidence,
) -> list[InstitutionDecisionSection]:
    return [
        _section(
            section_key=f"employer_geography:{market.region_id}",
            title=f"{market.region_label} employer geography",
            what_is_happening=(
                f"{len(market.employer_names)} employers have observed hiring, entry-level, "
                "or presence signals in this region."
            ),
            why_it_matters=(
                "Employer geography helps partnership teams decide where to build "
                "relationships and where students may need broader search coverage."
            ),
            considerations=[
                (
                    "Review relationship coverage for "
                    f"{', '.join(market.employer_names[:3]) or 'observed employers'}."
                ),
                "Prioritize employers with both presence and early-career signals.",
            ],
            metrics=[
                _metric(
                    "employer_presence_count",
                    "Employer presence count",
                    len(market.employer_names),
                    "employers",
                    "Identifies relationship-building targets by geography.",
                    evidence,
                )
            ],
            evidence=evidence,
            warnings=_market_warnings(market),
        )
        for market in markets[:5]
    ]


def _internship_access_sections(
    markets: list[MarketDecisionSnapshot],
    evidence: InstitutionDecisionEvidence,
) -> list[InstitutionDecisionSection]:
    ranked = sorted(
        markets,
        key=lambda item: (
            -(item.internship_count + item.coop_count),
            -item.entry_level_access_score,
            item.region_label,
        ),
    )
    return [
        _section(
            section_key=f"internship_access:{market.region_id}",
            title=f"{market.region_label} internship access",
            what_is_happening=(
                f"{market.internship_count + market.coop_count} internship or co-op signals "
                f"and {market.entry_level_count} entry-level full-time signals are observed."
            ),
            why_it_matters=(
                "Internship access informs employer outreach, application timing, and "
                "whether students should be encouraged to include additional regions."
            ),
            considerations=[
                "Build internship-specific employer outreach where access signals are strong.",
                "Use sparse internship signals as a reason to diversify student target regions.",
            ],
            metrics=[
                _metric(
                    "internship_access_count",
                    "Internship and co-op signals",
                    market.internship_count + market.coop_count,
                    "opportunities",
                    "Supports internship strategy and employer partnership planning.",
                    evidence,
                )
            ],
            evidence=evidence,
            warnings=_market_warnings(market),
        )
        for market in ranked[:5]
    ]


def _industry_demand_sections(
    markets: list[MarketDecisionSnapshot],
    evidence: InstitutionDecisionEvidence,
) -> list[InstitutionDecisionSection]:
    sectors: Counter[str] = Counter()
    for market in markets:
        sectors.update(market.sectors)
    if not sectors:
        return [
            _section(
                section_key="industry_demand:sparse",
                title="Industry Demand",
                what_is_happening="Industry demand signals are sparse in the observed market data.",
                why_it_matters=(
                    "Sparse sector context limits curriculum and employer-category "
                    "decisions."
                ),
                considerations=[
                    "Use role-family and regional sections until sector coverage improves."
                ],
                evidence=evidence,
                warnings=["Sector-level market data is limited."],
            )
        ]
    sections: list[InstitutionDecisionSection] = []
    for sector, count in sectors.most_common(5):
        supporting_markets = [
            market.region_label
            for market in markets
            if market.sectors.get(sector, 0) > 0
        ][:4]
        sections.append(
            _section(
                section_key=f"industry_demand:{sector}",
                title=_display_label(sector),
                what_is_happening=(
                    f"{count} observed employer-region signals are associated with "
                    f"{_display_label(sector)}."
                ),
                why_it_matters=(
                    "Industry demand informs curriculum emphasis, employer categories, "
                    "and regional advising priorities."
                ),
                considerations=[
                    f"Review program and employer coverage in {', '.join(supporting_markets)}.",
                    "Use industry signals alongside role-family and internship access metrics.",
                ],
                metrics=[
                    _metric(
                        "industry_signal_count",
                        "Industry signal count",
                        count,
                        "signals",
                        "Shows observed employer-region demand by sector.",
                        evidence,
                    )
                ],
                evidence=evidence,
            )
        )
    return sections


def _program_mapping(
    program: ProgramDefinition,
    markets: list[MarketDecisionSnapshot],
    dashboard: InstitutionalDashboardPayload,
    privacy: InstitutionPrivacyMetadata,
) -> CurriculumProgramMapping:
    evidence = _overall_evidence(markets, dashboard)
    aligned = _aligned_markets(program, markets)
    emerging = [
        market
        for market in aligned
        if market.opportunity_score >= 60 and market.trend_signal in {"increasing", "seasonal"}
    ][:3]
    weak = [
        market
        for market in aligned
        if market.opportunity_score < 35 or market.trend_signal in {"decreasing", "weakening"}
    ][:3]
    employer_targets = _unique(
        employer
        for market in aligned[:4]
        for employer in market.employer_names[:3]
    )[:8]
    confidence = _mapping_confidence(aligned, evidence.confidence)
    sparse_warnings = []
    if len(aligned) < 2:
        sparse_warnings.append("Observed market coverage is sparse for this program.")
    if dashboard.cohort_size < dashboard.minimum_group_size:
        sparse_warnings.append("Cohort-derived student attention is suppressed for privacy.")
    return CurriculumProgramMapping(
        program_name=program.program_name,
        relevant_role_families=[_display_label(role) for role in program.role_families],
        strongest_aligned_markets=[
            _market_metric(market, evidence, "strongest_aligned_market")
            for market in aligned[:3]
        ],
        emerging_markets=[
            _market_metric(market, evidence, "emerging_market")
            for market in emerging
        ],
        weak_or_saturated_markets=[
            _market_metric(market, evidence, "weak_or_saturated_market")
            for market in weak
        ],
        skills_with_rising_demand=list(program.skills),
        employer_relationship_targets=employer_targets,
        advising_recommendations=[
            _program_advising_recommendation(program, aligned),
            "Discuss emerging regions as options to investigate, not guaranteed outcomes.",
        ],
        confidence=confidence,
        freshness=evidence.freshness,
        provenance=evidence.provenance,
        sparse_data_warnings=sparse_warnings,
        privacy=privacy,
    )


def _benchmark_items(
    dashboard: InstitutionalDashboardPayload,
    markets: list[MarketDecisionSnapshot],
) -> list[InstitutionBenchmarkItem]:
    visible_targets = _visible_target_region_ids(dashboard)
    target_set = set(visible_targets)
    top_markets = _top_markets(markets, limit=5)
    top_ids = {market.region_id for market in top_markets}
    average_opportunity = _average(market.opportunity_score for market in top_markets)
    target_markets = [market for market in markets if market.region_id in target_set]
    alignment_score = _alignment_score(target_markets, top_markets)
    emerging_gap = round(
        len(top_ids - target_set) / max(len(top_ids), 1) * 100,
        1,
    )
    employer_gap = _employer_access_gap(dashboard, top_markets)
    internship_gap = _internship_access_gap(target_markets, top_markets)
    outdated_gap = _outdated_hub_gap(target_markets, average_opportunity)
    warnings = []
    if dashboard.cohort_size < dashboard.minimum_group_size:
        warnings.append("Cohort-derived focus-region comparison is suppressed for privacy.")
    if not visible_targets:
            warnings.append("No student target market met the minimum group threshold.")
    return [
        InstitutionBenchmarkItem(
            benchmark_subject="Student target-market alignment",
            comparison_market_set=[market.region_label for market in top_markets],
            opportunity_score=round(average_opportunity, 1),
            alignment_score=alignment_score,
            gap_score=round(max(emerging_gap, outdated_gap, employer_gap, internship_gap), 1),
            emerging_region_gap=emerging_gap,
            employer_access_gap=employer_gap,
            internship_access_gap=internship_gap,
            recommendation_summary=_benchmark_recommendation(
                alignment_score,
                emerging_gap,
                employer_gap,
                internship_gap,
            ),
            supporting_rationale=[
                (
                    f"{len(top_ids & target_set)} of the top {len(top_ids)} "
                    "opportunity markets are visible in aggregate student "
                    "target-market attention."
                ),
                (
                    f"Outdated-hub gap score is {outdated_gap}; this rises when "
                    "visible attention clusters in markets below the comparison "
                    "opportunity average."
                ),
                (
                    f"Employer-access gap score is {employer_gap}; this rises "
                    "when high-opportunity employers are not represented in "
                    "aggregate saved-company attention."
                ),
                (
                    f"Internship-access gap score is {internship_gap}; this rises "
                    "when internship-rich markets are missing from visible "
                    "target-market attention."
                ),
            ],
            warnings=warnings,
        )
    ]


def _forecast_notes(session: Session, region_ids: list[str]) -> list[InstitutionForecastNote]:
    if not region_ids:
        return []
    observations = export_predictive_observations(
        HistoryRepository(session),
        region_ids=region_ids,
        limit_per_subject=500,
    )
    if not observations:
        return []
    report = PredictiveReportBuilder().build_report(observations)
    notes: list[InstitutionForecastNote] = []
    for section in report.sections:
        for forecast in section.forecasts:
            notes.append(
                InstitutionForecastNote(
                    forecast_label=_forecast_note_label(forecast.forecast_label),
                    forecast_type=forecast.forecast_type.value,
                    affected_entity=forecast.affected_entity.entity_id,
                    time_horizon=forecast.time_horizon,
                    safe_display_summary=forecast.safe_display_summary,
                    confidence=forecast.confidence.model_dump(mode="json"),
                    source_basis=forecast.source_basis.model_dump(mode="json"),
                    historical_depth=forecast.historical_depth.model_dump(mode="json"),
                    uncertainty=forecast.uncertainty.model_dump(mode="json"),
                    reasoning_trail=[step.summary for step in forecast.reasoning_trail],
                    supporting_signals=[
                        signal.model_dump(mode="json")
                        for signal in forecast.supporting_signals
                    ],
                )
            )
            if len(notes) >= 5:
                return notes
    return notes


def _forecast_note_label(label: str) -> str:
    if "forecast" in label.casefold():
        return label
    return f"{label} forecast"


def _overall_evidence(
    markets: list[MarketDecisionSnapshot],
    dashboard: InstitutionalDashboardPayload,
) -> InstitutionDecisionEvidence:
    source_count = sum(market.source_count for market in markets)
    factors: list[str] = []
    score = 0.35
    if source_count >= 10:
        score += 0.25
    elif source_count >= 4:
        score += 0.15
    else:
        factors.append("Market signal coverage is thin.")
    if markets:
        score += 0.15
    if dashboard.cohort_size >= dashboard.minimum_group_size:
        score += 0.15
    else:
        factors.append("Cohort-derived sections are suppressed below the minimum group threshold.")
    if dashboard.coverage_warnings:
        score -= 0.1
        factors.append("Coverage warnings are present on the source aggregate dashboard.")
    level = _confidence_level(score, insufficient=source_count == 0)
    confidence = InstitutionDecisionConfidence(
        level=level,
        score=round(max(0.0, min(1.0, score)), 2),
        factors=factors or ["Evidence spans aggregate cohort and public market-level sources."],
    )
    freshness_values = _unique(
        value
        for market in markets
        for value in market.freshness_values
        if value
    )
    return InstitutionDecisionEvidence(
        confidence=confidence,
        freshness=freshness_values[0] if freshness_values else "unknown",
        provenance=[
            "Layer 16 aggregate institutional dashboard",
            "Company-region hiring, entry-level, and presence tables",
            "Layer 21 predictive public-safe exports when historical snapshots exist",
        ],
        source_basis=[
            "aggregate_cohort_dashboard",
            "public_market_level_company_region_signals",
            "producer_owned_predictive_exports",
        ],
        historical_depth={
            "market_signal_count": source_count,
            "visible_target_market_count": len(_visible_target_region_ids(dashboard)),
            "cohort_size": dashboard.cohort_size,
            "minimum_cohort_size": dashboard.minimum_group_size,
        },
    )


def _privacy_for_dashboard(
    dashboard: InstitutionalDashboardPayload,
    *,
    suppressed_fields: list[str] | tuple[str, ...] = (),
) -> InstitutionPrivacyMetadata:
    fields = [*_suppressed_fields(dashboard), *suppressed_fields]
    if dashboard.cohort_size < dashboard.minimum_group_size:
        fields.extend(
            [
                "target_markets",
                "role_interest_summary",
                "saved_company_summary",
            ]
        )
    return build_privacy_metadata(
        cohort_size=dashboard.cohort_size,
        minimum_cohort_size=dashboard.minimum_group_size,
        aggregation_level="mixed_aggregate",
        suppressed_fields=fields,
        extra_notes=dashboard.privacy_notes,
    )


def _suppressed_fields(dashboard: InstitutionalDashboardPayload) -> list[str]:
    fields = [row.section for row in dashboard.suppressed_categories]
    if any(item.suppressed for item in dashboard.popular_target_markets):
        fields.append("target_market_low_sample_buckets")
    if any(item.suppressed for item in dashboard.role_interest_summary):
        fields.append("role_interest_low_sample_buckets")
    if any(item.suppressed for item in dashboard.saved_company_summary):
        fields.append("saved_company_low_sample_buckets")
    return sorted(set(fields))


def _section(
    *,
    section_key: str,
    title: str,
    what_is_happening: str,
    why_it_matters: str,
    considerations: list[str] | None = None,
    metrics: list[InstitutionDecisionMetric] | None = None,
    evidence: InstitutionDecisionEvidence,
    warnings: list[str] | None = None,
) -> InstitutionDecisionSection:
    return InstitutionDecisionSection(
        section_key=section_key,
        title=title,
        what_is_happening=what_is_happening,
        why_it_matters=why_it_matters,
        considerations=considerations or [],
        metrics=metrics or [],
        evidence=evidence,
        warnings=warnings or [],
    )


def _metric(
    metric_key: str,
    label: str,
    value: float | int | str | None,
    unit: str | None,
    decision_use: str,
    evidence: InstitutionDecisionEvidence,
) -> InstitutionDecisionMetric:
    return InstitutionDecisionMetric(
        metric_key=metric_key,
        label=label,
        value=value,
        unit=unit,
        decision_use=decision_use,
        evidence=evidence,
    )


def _market_metric(
    market: MarketDecisionSnapshot,
    evidence: InstitutionDecisionEvidence,
    metric_key: str,
) -> InstitutionDecisionMetric:
    return _metric(
        metric_key,
        market.region_label,
        market.opportunity_score,
        "0-100",
        (
            "Ranks observed regional market opportunity for curriculum and "
            "advising decisions."
        ),
        evidence,
    )


def _market_metrics(
    market: MarketDecisionSnapshot,
    evidence: InstitutionDecisionEvidence,
) -> list[InstitutionDecisionMetric]:
    return [
        _metric(
            "opportunity_score",
            "Opportunity score",
            market.opportunity_score,
            "0-100",
            (
                "Deterministic score from observed hiring, entry-level, "
                "internship, and employer presence signals."
            ),
            evidence,
        ),
        _metric(
            "active_postings",
            "Active postings",
            market.active_postings,
            "postings",
            "Supports regional demand and advising priority decisions.",
            evidence,
        ),
        _metric(
            "hiring_company_count",
            "Hiring companies",
            market.hiring_company_count,
            "companies",
            "Supports employer partnership and geography decisions.",
            evidence,
        ),
    ]


def _report_metrics(
    report_type: InstitutionWorkforceReportType,
    markets: list[MarketDecisionSnapshot],
    evidence: InstitutionDecisionEvidence,
) -> list[InstitutionDecisionMetric]:
    top = _top_markets(markets, limit=5)
    if report_type is InstitutionWorkforceReportType.EARLY_CAREER_MARKET_ACCESS:
        top = sorted(
            markets,
            key=lambda item: (
                -(item.internship_count + item.entry_level_count),
                item.region_label,
            ),
        )[:5]
    return [_market_metric(market, evidence, "report_supporting_market") for market in top]


def _top_markets(
    markets: list[MarketDecisionSnapshot],
    *,
    limit: int,
) -> list[MarketDecisionSnapshot]:
    return sorted(
        markets,
        key=lambda item: (-item.opportunity_score, item.region_label, item.region_id),
    )[:limit]


def _visible_target_region_ids(dashboard: InstitutionalDashboardPayload) -> list[str]:
    ids: list[str] = []
    for item in dashboard.popular_target_markets:
        if item.suppressed:
            continue
        region_id = _metadata_text(item, "region_id")
        if region_id:
            ids.append(region_id)
    return _unique(ids)


def _metadata_text(item: InstitutionalAggregateItem, key: str) -> str | None:
    value = item.metadata.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _target_market_considerations(
    item: InstitutionalAggregateItem,
    market: MarketDecisionSnapshot | None,
) -> list[str]:
    considerations = [
        (
            "Use the aggregate attention count to prioritize advising materials "
            "for this region."
        ),
    ]
    if market is None:
        considerations.append(
            "Collect more public market context before expanding employer outreach."
        )
        return considerations
    if market.opportunity_score >= 60:
        considerations.append(
            "Consider employer partnership outreach because market opportunity "
            "is comparatively strong."
        )
    elif market.opportunity_score < 35:
        considerations.append(
            "Balance student interest with additional markets because observed "
            "opportunity is limited."
        )
    if market.internship_count + market.coop_count > 0:
        considerations.append("Include internship application timing in regional advising.")
    return considerations


def _trend_consideration(market: MarketDecisionSnapshot) -> str:
    if market.trend_signal == "increasing":
        return (
            "Consider adding this region to advisor talking points while "
            "checking current postings."
        )
    if market.trend_signal in {"decreasing", "weakening"}:
        return "Treat this region as a watch item and broaden student alternatives."
    return "Use this region as a comparison market until stronger movement appears."


def _program_alignment_summary(
    program: ProgramDefinition,
    aligned: list[MarketDecisionSnapshot],
) -> str:
    if not aligned:
        return (
            f"{program.program_name} has limited observed alignment in the "
            "current market-level data."
        )
    labels = ", ".join(market.region_label for market in aligned[:3])
    return f"{program.program_name} aligns most strongly with observed signals in {labels}."


def _aligned_markets(
    program: ProgramDefinition,
    markets: list[MarketDecisionSnapshot],
) -> list[MarketDecisionSnapshot]:
    program_roles = {_normalize_key(role) for role in program.role_families}
    program_sectors = {_normalize_key(sector) for sector in program.sectors}

    def score(market: MarketDecisionSnapshot) -> tuple[float, float, str]:
        role_hits = sum(
            count
            for role, count in market.role_families.items()
            if role in program_roles
        )
        sector_hits = sum(
            count
            for sector, count in market.sectors.items()
            if sector in program_sectors
        )
        return (
            role_hits * 8.0 + sector_hits * 6.0 + market.opportunity_score,
            market.opportunity_score,
            market.region_label,
        )

    aligned = [
        market
        for market in markets
        if any(role in program_roles for role in market.role_families)
        or any(sector in program_sectors for sector in market.sectors)
    ]
    return sorted(aligned, key=score, reverse=True)


def _mapping_confidence(
    aligned: list[MarketDecisionSnapshot],
    base: InstitutionDecisionConfidence,
) -> InstitutionDecisionConfidence:
    score = base.score
    factors = list(base.factors)
    if len(aligned) < 2:
        score = min(score, 0.45)
        factors.append("Program mapping has fewer than two aligned observed markets.")
    return InstitutionDecisionConfidence(
        level=_confidence_level(score, insufficient=not aligned),
        score=round(score, 2),
        factors=_unique(factors),
    )


def _program_advising_recommendation(
    program: ProgramDefinition,
    aligned: list[MarketDecisionSnapshot],
) -> str:
    if not aligned:
        return (
            f"Use {program.program_name} mappings as a sparse-data review area "
            "until more market observations are available."
        )
    return (
        f"Use {aligned[0].region_label} as a first advising comparison market for "
        f"{program.program_name}, then compare with adjacent markets."
    )


def _report_title(
    report_type: InstitutionWorkforceReportType,
    organization_name: str,
) -> str:
    labels = {
        InstitutionWorkforceReportType.REGIONAL_WORKFORCE_OPPORTUNITY: (
            "Regional Workforce Opportunity Report"
        ),
        InstitutionWorkforceReportType.EARLY_CAREER_MARKET_ACCESS: (
            "Early-Career Market Access Report"
        ),
        InstitutionWorkforceReportType.TECH_SECTOR_GROWTH: "Tech-Sector Growth Report",
        InstitutionWorkforceReportType.STUDENT_PLACEMENT_STRATEGY: (
            "Student Placement Strategy Report"
        ),
        InstitutionWorkforceReportType.EMPLOYER_GEOGRAPHY: "Employer Geography Report",
        InstitutionWorkforceReportType.PROGRAM_ALIGNMENT: "Program Alignment Report",
    }
    return f"{organization_name} {labels[report_type]}"


def _report_audience(report_type: InstitutionWorkforceReportType) -> str:
    audiences = {
        InstitutionWorkforceReportType.REGIONAL_WORKFORCE_OPPORTUNITY: (
            "career centers, workforce boards, and regional strategy teams"
        ),
        InstitutionWorkforceReportType.EARLY_CAREER_MARKET_ACCESS: (
            "career services, internship offices, and program advisors"
        ),
        InstitutionWorkforceReportType.TECH_SECTOR_GROWTH: (
            "program directors, curriculum committees, and employer partnership teams"
        ),
        InstitutionWorkforceReportType.STUDENT_PLACEMENT_STRATEGY: (
            "career centers and placement strategy teams"
        ),
        InstitutionWorkforceReportType.EMPLOYER_GEOGRAPHY: (
            "employer relations and economic development teams"
        ),
        InstitutionWorkforceReportType.PROGRAM_ALIGNMENT: "academic leaders and program directors",
    }
    return audiences[report_type]


def _report_findings(
    report_type: InstitutionWorkforceReportType,
    dashboard: InstitutionalDashboardPayload,
    markets: list[MarketDecisionSnapshot],
) -> list[str]:
    top = _top_markets(markets, limit=3)
    if not top:
        return ["Observed market data is sparse, so findings are limited."]
    base = [
        (
            f"{top[0].region_label} has the strongest observed opportunity score "
            "among compared markets."
        ),
        (
            f"{sum(market.hiring_company_count for market in top)} "
            "hiring-company signals appear across the top comparison markets."
        ),
    ]
    if report_type is InstitutionWorkforceReportType.EARLY_CAREER_MARKET_ACCESS:
        return [
            (
                f"{sum(market.internship_count + market.coop_count for market in top)} "
                "internship or co-op signals appear across the top comparison markets."
            ),
            (
                "Internship access should be reviewed alongside entry-level full-time "
                "access before advising students to narrow search geography."
            ),
        ]
    if report_type is InstitutionWorkforceReportType.STUDENT_PLACEMENT_STRATEGY:
        visible_count = len(_visible_target_region_ids(dashboard))
        return base + [
            f"{visible_count} student target-market buckets met the privacy threshold.",
        ]
    if report_type is InstitutionWorkforceReportType.EMPLOYER_GEOGRAPHY:
        return [
            (
                f"{sum(len(market.employer_names) for market in top)} employer "
                "geography signals appear across the top comparison markets."
            ),
            (
                "Employer relationship planning should prioritize markets with "
                "both presence and hiring signals."
            ),
        ]
    if report_type is InstitutionWorkforceReportType.PROGRAM_ALIGNMENT:
        return [
            (
                "Program alignment is strongest where role-family or sector "
                "signals overlap with observed regional opportunity."
            ),
            (
                "Sample program mappings are deterministic until producer-owned "
                "curriculum ingestion is available."
            ),
        ]
    return base


def _report_actions(
    report_type: InstitutionWorkforceReportType,
    dashboard: InstitutionalDashboardPayload,
    markets: list[MarketDecisionSnapshot],
) -> list[str]:
    top = _top_markets(markets, limit=3)
    actions = [
        (
            "Use market signals as decision support and verify current employer "
            "openings before changing advising guidance."
        ),
        (
            "Review privacy suppression warnings before interpreting "
            "cohort-derived attention patterns."
        ),
    ]
    if top:
        actions.insert(0, f"Review {top[0].region_label} as a priority comparison market.")
    if report_type is InstitutionWorkforceReportType.PROGRAM_ALIGNMENT:
        actions.append(
            "Use curriculum mapping to identify where skills and employer "
            "relationships should be reviewed."
        )
    if report_type is InstitutionWorkforceReportType.EMPLOYER_GEOGRAPHY:
        actions.append(
            "Compare employer relationship coverage against markets with "
            "concentrated hiring and internship signals."
        )
    if dashboard.cohort_size < dashboard.minimum_group_size:
        actions.append(
            "Wait for a larger privacy-safe cohort before acting on student "
            "attention patterns."
        )
    return actions


def _report_summary(
    report_type: InstitutionWorkforceReportType,
    findings: list[str],
) -> str:
    if not findings:
        return "This report has limited findings because observed data is sparse."
    return (
        f"{report_type.value.replace('_', ' ').title()} generated from aggregate "
        f"cohort and public market signals. {findings[0]}"
    )


def _recommended_actions(
    dashboard: InstitutionalDashboardPayload,
    markets: list[MarketDecisionSnapshot],
    forecast_notes: list[InstitutionForecastNote],
) -> list[str]:
    actions = [
        (
            "Use high-opportunity markets as advisor comparison points for "
            "students exploring geography."
        ),
        (
            "Review employer relationship coverage in markets with hiring, "
            "internship, and presence signals."
        ),
        "Connect program review to observed role-family, sector, and skill demand signals.",
    ]
    if dashboard.cohort_size < dashboard.minimum_group_size:
        actions.append(
            "Do not infer student attention patterns until the cohort reaches "
            "the privacy threshold."
        )
    if forecast_notes:
        actions.append(
            "Treat forecast notes as bounded planning signals and preserve their "
            "confidence and uncertainty language."
        )
    if markets and markets[0].internship_count + markets[0].coop_count > 0:
        actions.append(
            "Use internship-rich markets for application timing and partnership planning."
        )
    return actions


def _summary_text(
    dashboard: InstitutionalDashboardPayload,
    top_markets: list[MarketDecisionSnapshot],
) -> str:
    if not top_markets:
        return "Market-level signals are sparse, so institutional decision support is limited."
    return (
        f"{dashboard.organization_name} has aggregate cohort context and "
        f"{top_markets[0].region_label} is the strongest observed comparison market."
    )


def _dashboard_warnings(
    dashboard: InstitutionalDashboardPayload,
    markets: list[MarketDecisionSnapshot],
    forecast_notes: list[InstitutionForecastNote],
) -> list[str]:
    warnings = list(dashboard.coverage_warnings)
    if dashboard.cohort_size < dashboard.minimum_group_size:
        warnings.append(
            "Cohort size is below the minimum threshold; cohort-derived detail is suppressed."
        )
    if not markets:
        warnings.append(
            "No public market-level signals are available for institutional decision scoring."
        )
    if not forecast_notes:
        warnings.append(
            "Forecast notes appear only when Layer 21 historical exports are available."
        )
    return _unique(warnings)


def _gap_warnings(
    visible_target_ids: list[str],
    markets: list[MarketDecisionSnapshot],
) -> list[str]:
    if not visible_target_ids:
        return []
    top_ids = {market.region_id for market in _top_markets(markets, limit=5)}
    missing = top_ids - set(visible_target_ids)
    if not missing:
        return []
    return [
        (
            "Some high-opportunity comparison markets are not visible in "
            "aggregate student target-market attention."
        )
    ]


def _limitations(
    dashboard: InstitutionalDashboardPayload,
    markets: list[MarketDecisionSnapshot],
) -> list[str]:
    limitations = [
        (
            "Layer 22A uses deterministic aggregate and market-level decision "
            "intelligence; it does not predict individual student outcomes."
        ),
        "Forecast-aware notes appear only when Layer 21 historical observations exist.",
        (
            "Sample curriculum mappings are structured placeholders for later "
            "producer-owned curriculum ingestion."
        ),
    ]
    if not markets:
        limitations.append(
            "Market scoring is limited because no public market-level records were available."
        )
    if dashboard.suppressed_categories:
        limitations.append(
            "Some cohort-derived categories are suppressed due to minimum cohort thresholds."
        )
    return limitations


def _market_warnings(market: MarketDecisionSnapshot) -> list[str]:
    warnings = []
    if market.source_count < 2:
        warnings.append("Market signal coverage is thin.")
    if market.trend_signal in {"decreasing", "weakening"}:
        warnings.append("Observed hiring movement is weakening; use as a review prompt.")
    return warnings


def _benchmark_recommendation(
    alignment_score: float,
    emerging_gap: float,
    employer_gap: float,
    internship_gap: float,
) -> str:
    if alignment_score >= 70:
        return (
            "Visible aggregate student attention is broadly aligned with "
            "observed market opportunity."
        )
    if emerging_gap >= 50:
        return (
            "Review emerging-region advising coverage because several strong "
            "comparison markets are missing from visible attention."
        )
    if employer_gap >= 50:
        return "Review employer relationship coverage for high-opportunity markets."
    if internship_gap >= 50:
        return "Review internship strategy against markets with stronger early-career access."
    return (
        "Use this benchmark as a directional planning input and monitor changes "
        "as coverage improves."
    )


def _alignment_score(
    target_markets: list[MarketDecisionSnapshot],
    top_markets: list[MarketDecisionSnapshot],
) -> float:
    if not top_markets:
        return 0.0
    if not target_markets:
        return 0.0
    top_ids = {market.region_id for market in top_markets}
    target_ids = {market.region_id for market in target_markets}
    overlap = len(top_ids & target_ids) / len(top_ids)
    target_quality = _average(market.opportunity_score for market in target_markets) / 100.0
    return round(
        max(0.0, min(100.0, (overlap * 65.0) + (target_quality * 35.0))),
        1,
    )


def _employer_access_gap(
    dashboard: InstitutionalDashboardPayload,
    top_markets: list[MarketDecisionSnapshot],
) -> float:
    visible_company_labels = {
        item.label
        for item in dashboard.saved_company_summary
        if not item.suppressed and item.label
    }
    target_employers = {
        employer
        for market in top_markets
        for employer in market.employer_names[:3]
    }
    if not target_employers:
        return 0.0
    if not visible_company_labels:
        return 100.0
    missing = target_employers - visible_company_labels
    return round(len(missing) / len(target_employers) * 100, 1)


def _internship_access_gap(
    target_markets: list[MarketDecisionSnapshot],
    top_markets: list[MarketDecisionSnapshot],
) -> float:
    internship_markets = {
        market.region_id
        for market in top_markets
        if market.internship_count + market.coop_count > 0
    }
    if not internship_markets:
        return 0.0
    target_ids = {market.region_id for market in target_markets}
    return round(len(internship_markets - target_ids) / len(internship_markets) * 100, 1)


def _outdated_hub_gap(
    target_markets: list[MarketDecisionSnapshot],
    comparison_average: float,
) -> float:
    if not target_markets:
        return 0.0
    below_average = [
        market
        for market in target_markets
        if market.opportunity_score < comparison_average
    ]
    return round(len(below_average) / len(target_markets) * 100, 1)


def _confidence_level(score: float, *, insufficient: bool = False) -> str:
    if insufficient:
        return "insufficient"
    if score >= 0.75:
        return "high"
    if score >= 0.55:
        return "medium"
    if score >= 0.3:
        return "low"
    return "insufficient"


def _dominant_signal(values: list[str | None]) -> str:
    cleaned = [value for value in values if value and value != "unknown"]
    if not cleaned:
        return "unknown"
    return Counter(cleaned).most_common(1)[0][0]


def _normalize_key(value: str) -> str:
    return value.strip().casefold().replace("-", "_").replace(" ", "_")


def _display_label(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").title()


def _average(values: Any) -> float:
    rows = [float(value) for value in values]
    if not rows:
        return 0.0
    return sum(rows) / len(rows)


def _unique(values: Any) -> list[Any]:
    unique_values: list[Any] = []
    seen: set[Any] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values
