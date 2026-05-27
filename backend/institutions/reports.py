"""Aggregate-first institutional report payloads."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.institutions.dashboard import (
    DEFAULT_MINIMUM_GROUP_SIZE,
    MAXIMUM_GROUP_SIZE,
    InstitutionalAggregateItem,
    InstitutionalDashboardPayload,
    InstitutionalSuppressedCategory,
)


class InstitutionalReportType(StrEnum):
    CAREER_SERVICES = "career_services"
    PROGRAM_DIRECTOR = "program_director"
    WORKFORCE_PLANNER = "workforce_planner"
    ECONOMIC_DEVELOPMENT_PARTNER = "economic_development_partner"

    @classmethod
    def values(cls) -> frozenset[str]:
        return frozenset(member.value for member in cls)


class InstitutionalReportSection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    section_id: str
    title: str
    summary: str
    findings: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    suppressions: list[InstitutionalSuppressedCategory] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class InstitutionalReportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    report_id: str
    organization_id: str
    report_type: InstitutionalReportType
    title: str
    generated_at: datetime
    generated_by_user_id: str
    date_range: dict[str, str | None] | None = None
    minimum_group_size: int
    cohort_size: int
    sections: list[InstitutionalReportSection] = Field(default_factory=list)
    privacy_suppressions: list[InstitutionalSuppressedCategory] = Field(default_factory=list)
    coverage_warnings: list[str] = Field(default_factory=list)
    data_freshness: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    export_status: str = "not_generated"
    export_options: dict[str, str] = Field(default_factory=dict)
    privacy_notes: list[str] = Field(default_factory=list)


class InstitutionalReportSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    report_id: str
    organization_id: str
    report_type: InstitutionalReportType
    title: str
    generated_at: datetime
    generated_by_user_id: str
    minimum_group_size: int
    cohort_size: int
    status: str
    privacy_summary: dict[str, Any] = Field(default_factory=dict)
    coverage_summary: dict[str, Any] = Field(default_factory=dict)


class InstitutionalReportCreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    report_type: InstitutionalReportType
    minimum_group_size: int = Field(
        default=DEFAULT_MINIMUM_GROUP_SIZE,
        ge=DEFAULT_MINIMUM_GROUP_SIZE,
        le=MAXIMUM_GROUP_SIZE,
    )
    date_range: dict[str, str | None] | None = None


class InstitutionalReportListPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reports: list[InstitutionalReportSummary] = Field(default_factory=list)


def build_institutional_report(
    *,
    report_id: str,
    report_type: InstitutionalReportType,
    generated_by_user_id: str,
    dashboard: InstitutionalDashboardPayload,
    date_range: dict[str, str | None] | None = None,
) -> InstitutionalReportPayload:
    sections = _sections_for_report_type(report_type, dashboard)
    coverage_warnings = _coverage_warnings(dashboard)
    limitations = _limitations_for_report_type(report_type, dashboard)
    recommended_actions = _recommended_actions_for_report_type(report_type, dashboard)
    return InstitutionalReportPayload(
        report_id=report_id,
        organization_id=dashboard.organization_id,
        report_type=report_type,
        title=_report_title(report_type, dashboard.organization_name),
        generated_at=dashboard.generated_at,
        generated_by_user_id=generated_by_user_id,
        date_range=date_range,
        minimum_group_size=dashboard.minimum_group_size,
        cohort_size=dashboard.cohort_size,
        sections=sections,
        privacy_suppressions=dashboard.suppressed_categories,
        coverage_warnings=coverage_warnings,
        data_freshness=dashboard.data_freshness,
        limitations=limitations,
        recommended_actions=recommended_actions,
        export_options={
            "pdf": "deferred",
            "csv": "deferred",
            "powerpoint": "deferred",
        },
        privacy_notes=[
            "Layer 16 institutional reports are aggregate-first and privacy-aware.",
            "Low-sample categories are suppressed before report generation.",
            "Reports do not expose student-level searches, saved companies, "
            "recommendations, preferences, or personal activity histories.",
        ],
    )


def report_summary_from_payload(
    payload: InstitutionalReportPayload,
    *,
    status: str = "generated",
) -> InstitutionalReportSummary:
    return InstitutionalReportSummary(
        report_id=payload.report_id,
        organization_id=payload.organization_id,
        report_type=payload.report_type,
        title=payload.title,
        generated_at=payload.generated_at,
        generated_by_user_id=payload.generated_by_user_id,
        minimum_group_size=payload.minimum_group_size,
        cohort_size=payload.cohort_size,
        status=status,
        privacy_summary=privacy_summary(payload),
        coverage_summary=coverage_summary(payload),
    )


def privacy_summary(payload: InstitutionalReportPayload) -> dict[str, Any]:
    return {
        "minimum_group_size": payload.minimum_group_size,
        "suppression_count": len(payload.privacy_suppressions),
        "suppressed_sections": [item.section for item in payload.privacy_suppressions],
        "student_level_data_exposed": False,
    }


def coverage_summary(payload: InstitutionalReportPayload) -> dict[str, Any]:
    return {
        "coverage_warning_count": len(payload.coverage_warnings),
        "freshness_status": payload.data_freshness.get("freshness_status", "unknown"),
    }


def _sections_for_report_type(
    report_type: InstitutionalReportType,
    dashboard: InstitutionalDashboardPayload,
) -> list[InstitutionalReportSection]:
    if report_type == InstitutionalReportType.CAREER_SERVICES:
        return [
            _aggregate_section(
                "career_interests",
                "Student Career Interest Aggregates",
                "Visible role and market interest patterns for career services planning.",
                {
                    "role_interest_summary": dashboard.role_interest_summary,
                    "popular_target_markets": dashboard.popular_target_markets,
                    "saved_company_summary": dashboard.saved_company_summary,
                },
                dashboard,
                actions=[
                    "Use visible aggregate interests to prioritize workshops and "
                    "employer outreach.",
                    "Review suppressed categories only as a signal that additional "
                    "privacy-safe data is needed.",
                ],
            ),
            _aggregate_section(
                "application_timing",
                "Application Timing Guidance",
                "Directional timing guidance derived from visible market demand trends.",
                {"market_demand_trends": dashboard.market_demand_trends},
                dashboard,
                findings=_timing_findings(dashboard),
                actions=[
                    "Verify current postings before advising students to prioritize "
                    "an application window.",
                ],
            ),
            _coverage_section(dashboard),
        ]
    if report_type == InstitutionalReportType.PROGRAM_DIRECTOR:
        return [
            _aggregate_section(
                "program_market_alignment",
                "Program-Market Alignment",
                "Visible role interests and demand trends that can inform program planning.",
                {
                    "role_interest_summary": dashboard.role_interest_summary,
                    "market_demand_trends": dashboard.market_demand_trends,
                },
                dashboard,
                limitations=[
                    "Skills-level curriculum alignment is not modeled in this batch.",
                    "Industry interest coverage is limited to existing aggregate-safe inputs.",
                ],
                actions=[
                    "Treat gaps as prompts for curriculum review, not as proof of "
                    "program deficiency.",
                ],
            ),
            _coverage_section(dashboard),
        ]
    if report_type == InstitutionalReportType.WORKFORCE_PLANNER:
        return [
            _aggregate_section(
                "regional_demand_trends",
                "Regional Demand Trends",
                "Visible regional interest and hiring demand trends for workforce planning.",
                {
                    "popular_target_markets": dashboard.popular_target_markets,
                    "market_demand_trends": dashboard.market_demand_trends,
                },
                dashboard,
                actions=[
                    "Use visible alignment patterns to identify employer-engagement priorities.",
                    "Treat underserved opportunities as directional until coverage improves.",
                ],
            ),
            _coverage_section(dashboard),
        ]
    return [
        _aggregate_section(
            "regional_talent_interest",
            "Regional Talent Interest",
            "Aggregate student interest and employer demand signals for partner planning.",
            {
                "popular_target_markets": dashboard.popular_target_markets,
                "market_demand_trends": dashboard.market_demand_trends,
            },
            dashboard,
            actions=[
                "Use visible local-market interest to frame talent-retention conversations.",
                "Pair report findings with direct employer verification before external claims.",
            ],
        ),
        _coverage_section(dashboard),
    ]


def _aggregate_section(
    section_id: str,
    title: str,
    summary: str,
    metrics: dict[str, list[InstitutionalAggregateItem]],
    dashboard: InstitutionalDashboardPayload,
    *,
    findings: list[str] | None = None,
    limitations: list[str] | None = None,
    actions: list[str] | None = None,
) -> InstitutionalReportSection:
    section_findings = findings or _findings_from_metrics(metrics)
    return InstitutionalReportSection(
        section_id=section_id,
        title=title,
        summary=summary,
        findings=section_findings,
        metrics={
            key: [item.model_dump(mode="json") for item in values]
            for key, values in metrics.items()
        },
        warnings=_warnings_for_empty_metrics(metrics, dashboard),
        suppressions=[
            item
            for item in dashboard.suppressed_categories
            if item.section in metrics
        ],
        limitations=limitations or [],
        recommended_actions=actions or [],
    )


def _coverage_section(dashboard: InstitutionalDashboardPayload) -> InstitutionalReportSection:
    return InstitutionalReportSection(
        section_id="coverage_gaps",
        title="Coverage Gaps And Data Quality",
        summary="Coverage warnings and suppressed categories that affect interpretation.",
        findings=_findings_from_metrics({"coverage_gaps": dashboard.coverage_gaps}),
        metrics={
            "coverage_gaps": [
                item.model_dump(mode="json") for item in dashboard.coverage_gaps
            ],
            "privacy_suppressions": [
                item.model_dump(mode="json") for item in dashboard.suppressed_categories
            ],
        },
        warnings=_coverage_warnings(dashboard),
        suppressions=dashboard.suppressed_categories,
        limitations=[
            "Coverage warnings are directional and should be reviewed before external reporting.",
            "Suppressed categories intentionally withhold labels and exact low-sample counts.",
        ],
        recommended_actions=[
            "Review source freshness and coverage limits before sharing findings "
            "outside the institution.",
        ],
    )


def _findings_from_metrics(
    metrics: dict[str, list[InstitutionalAggregateItem]],
) -> list[str]:
    findings: list[str] = []
    for key, items in metrics.items():
        visible = [item for item in items if not item.suppressed]
        if visible:
            findings.append(
                f"{len(visible)} visible {key.replace('_', ' ')} aggregate(s) "
                "met the privacy threshold."
            )
        else:
            findings.append(
                f"No {key.replace('_', ' ')} aggregate met the configured privacy threshold."
            )
    return findings


def _timing_findings(dashboard: InstitutionalDashboardPayload) -> list[str]:
    if not dashboard.market_demand_trends:
        return [
            "No visible target market had enough aggregate support for timing guidance."
        ]
    findings = []
    for item in dashboard.market_demand_trends[:3]:
        trend = item.metadata.get("trend_signal", "unknown")
        findings.append(
            f"{item.label} has a {trend} demand trend in visible aggregate market context."
        )
    return findings


def _warnings_for_empty_metrics(
    metrics: dict[str, list[InstitutionalAggregateItem]],
    dashboard: InstitutionalDashboardPayload,
) -> list[str]:
    warnings = []
    if any(not [item for item in values if not item.suppressed] for values in metrics.values()):
        warnings.append(
            "One or more report sections has no visible category because of "
            "privacy suppression or missing data."
        )
    warnings.extend(dashboard.coverage_warnings)
    return sorted(set(warnings))


def _coverage_warnings(dashboard: InstitutionalDashboardPayload) -> list[str]:
    warnings = list(dashboard.coverage_warnings)
    if not warnings:
        warnings.append(
            "No specific coverage warning was generated, but source freshness "
            "remains unknown and should be verified."
        )
    return warnings


def _limitations_for_report_type(
    report_type: InstitutionalReportType,
    dashboard: InstitutionalDashboardPayload,
) -> list[str]:
    limitations = [
        "Reports are aggregate-first decision-support outputs and do not guarantee outcomes.",
        "Low-sample categories are suppressed before report assembly.",
        "PDF, CSV, PowerPoint, email delivery, and scheduled report workflows are deferred.",
    ]
    if dashboard.cohort_size < dashboard.minimum_group_size:
        limitations.append(
            "Cohort size is below the configured minimum group size, so "
            "category-level detail is withheld."
        )
    if report_type == InstitutionalReportType.PROGRAM_DIRECTOR:
        limitations.append("Skills-level curriculum mapping is not implemented in this batch.")
    if report_type == InstitutionalReportType.ECONOMIC_DEVELOPMENT_PARTNER:
        limitations.append(
            "Economic-development findings must not be presented as comprehensive "
            "labor-market forecasts."
        )
    return limitations


def _recommended_actions_for_report_type(
    report_type: InstitutionalReportType,
    dashboard: InstitutionalDashboardPayload,
) -> list[str]:
    actions = [
        "Review privacy suppressions before sharing report conclusions.",
        "Validate coverage warnings with source review before high-stakes use.",
    ]
    if report_type == InstitutionalReportType.CAREER_SERVICES:
        actions.append("Prioritize advising content around visible role and market aggregates.")
    elif report_type == InstitutionalReportType.PROGRAM_DIRECTOR:
        actions.append("Use aggregate role-interest gaps as prompts for program review.")
    elif report_type == InstitutionalReportType.WORKFORCE_PLANNER:
        actions.append("Pair visible interest-demand alignment with employer outreach planning.")
    else:
        actions.append("Use regional aggregate interest as a cautious talent-retention signal.")
    return actions


def _report_title(
    report_type: InstitutionalReportType,
    organization_name: str,
) -> str:
    labels = {
        InstitutionalReportType.CAREER_SERVICES: "Career Services Report",
        InstitutionalReportType.PROGRAM_DIRECTOR: "Program Director Report",
        InstitutionalReportType.WORKFORCE_PLANNER: "Workforce Planner Report",
        InstitutionalReportType.ECONOMIC_DEVELOPMENT_PARTNER: (
            "Economic Development Partner Report"
        ),
    }
    return f"{organization_name} {labels[report_type]}"
