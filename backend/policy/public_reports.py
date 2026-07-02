"""Layer 24 public report assembly over policy intelligence payloads."""

from __future__ import annotations

from datetime import UTC, date, datetime

from backend.policy.schemas import PolicyMetric, WorkforceDashboardPayload
from backend.public_reports.schemas import (
    PublicReportCitation,
    PublicReportInstitutionalCta,
    PublicReportLink,
    PublicReportMarket,
    PublicReportMarketResult,
    PublicReportPayload,
    PublicReportShareSummary,
    PublicReportSourceAuthority,
    PublicSourceProvenanceSummary,
)
from backend.shared.confidence import Confidence
from backend.shared.freshness import FreshnessStatus

LAYER24_EARLY_CAREER_REPORT_ID = "early-career-opportunity"
LAYER24_EARLY_CAREER_REPORT_TITLE = "The Geography of Early-Career Tech Opportunity"
_PRODUCT_ATTRIBUTION = "Layer 24 Policy, Workforce, and Economic Intelligence"


def build_early_career_opportunity_report(
    dashboard: WorkforceDashboardPayload,
    *,
    now: datetime | None = None,
) -> PublicReportPayload:
    generated_at = now or datetime.now(UTC)
    generated_date = generated_at.date()
    slug = _report_slug(dashboard.region_summary.region_id)
    warnings = tuple(
        warning.public_interpretation for warning in dashboard.warnings[:8]
    )
    limitations = _report_limitations(dashboard)
    source_summary = _source_summary(dashboard)
    confidence = _confidence_for_report(dashboard.confidence.level)
    freshness_status = _freshness_status_for_report(
        dashboard.freshness.freshness_status,
    )
    market_result = _market_result(
        dashboard,
        confidence=confidence,
        freshness_date=generated_date,
        source_summary=source_summary,
    )
    summary = (
        f"Available Layer 24 signals for {dashboard.region_summary.region_name} "
        "summarize early-career access, internship pipeline, concentration, "
        "sector diversity, employer dependency, and talent export pressure."
    )
    methodology = (
        "This Layer 24 report is generated from the backend workforce dashboard "
        "payload for one region. It reuses policy metrics, policy findings, "
        "warnings, confidence, freshness, source summaries, and public-safety "
        "metadata produced by the policy intelligence service. It does not create "
        "new frontend scores, causal explanations, or prescriptive policy claims."
    )
    return PublicReportPayload(
        report_id=f"layer24_policy_report:{slug}",
        slug=slug,
        title=LAYER24_EARLY_CAREER_REPORT_TITLE,
        category="policy-workforce-intelligence",
        report_period=dashboard.freshness.generated_at.date().isoformat(),
        summary=summary,
        markets_covered=(
            PublicReportMarket(
                market_id=dashboard.region_summary.region_id,
                market_label=dashboard.region_summary.region_name,
                coverage_note=(
                    "Coverage follows the Layer 24 workforce dashboard source "
                    "summary and warnings for this region."
                ),
            ),
        ),
        market_results=(market_result,),
        methodology_summary=methodology,
        limitations=limitations,
        freshness_date=generated_date,
        freshness_status=freshness_status,
        confidence=confidence,
        warnings=warnings,
        source_provenance_summary=source_summary,
        related_links=(
            PublicReportLink(
                label="Policy dashboard",
                href=f"/markets/policy/regions/{dashboard.region_summary.region_id}/workforce",
                link_type="public_page",
            ),
            PublicReportLink(
                label="Policy methodology",
                href="/methodology",
                link_type="public_page",
            ),
        ),
        suggested_citation=PublicReportCitation(
            source_name="Job Market Intelligence",
            title=LAYER24_EARLY_CAREER_REPORT_TITLE,
            period=dashboard.freshness.generated_at.date().isoformat(),
            product_attribution=_PRODUCT_ATTRIBUTION,
            public_path=f"/reports/{slug}",
            accessed_or_freshness_date=generated_date,
        ),
        share_summary=PublicReportShareSummary(
            title=LAYER24_EARLY_CAREER_REPORT_TITLE,
            category_claim="Regional early-career opportunity and workforce access",
            confidence_label=f"{confidence.value.title()} confidence",
            freshness_label=f"{freshness_status.value.title()} freshness",
            takeaway=market_result.headline,
            public_path=f"/reports/{slug}",
            warning=(
                "Layer 24 report uses bounded policy intelligence and should be "
                "validated with local context."
            ),
        ),
        source_authority=PublicReportSourceAuthority(
            labels=(
                "demo-safe",
                "low-confidence",
                "methodology-backed",
                "Layer 24",
                "public-safe",
                "backend-generated",
                "bounded interpretation",
            ),
            summary=(
                "This report uses backend-generated Layer 24 workforce dashboard "
                "payloads and does not expose raw source references, private notes, "
                "partner submission internals, or student-level data."
            ),
        ),
        institutional_cta=PublicReportInstitutionalCta(
            label="Use this report for aggregate workforce planning",
            body=(
                "Career offices, chambers, workforce nonprofits, and public-sector "
                "teams can use the report as a starting point for local validation."
            ),
            href=f"/markets/policy/regions/{dashboard.region_summary.region_id}/workforce",
            link_type="public_page",
        ),
    )


def _report_slug(region_id: str) -> str:
    safe_region = region_id.strip().casefold().replace("_", "-")
    return f"layer-24-early-career-opportunity-{safe_region}"


def _market_result(
    dashboard: WorkforceDashboardPayload,
    *,
    confidence: Confidence,
    freshness_date: date,
    source_summary: PublicSourceProvenanceSummary,
) -> PublicReportMarketResult:
    finding = dashboard.policy_findings[0] if dashboard.policy_findings else None
    headline = finding.title if finding is not None else _metric_headline(dashboard)
    rationale = (
        finding.summary if finding is not None else _metric_rationale(dashboard)
    )
    evidence = tuple(
        dict.fromkeys(
            (
                "early-career access",
                "internship pipeline",
                "employer dependency",
                "sector diversity",
                *(
                    tuple(finding.evidence_references[:4])
                    if finding is not None
                    else ()
                ),
            )
        )
    )
    return PublicReportMarketResult(
        result_type="featured",
        rank=None,
        market_id=dashboard.region_summary.region_id,
        market_label=dashboard.region_summary.region_name,
        headline=headline,
        rationale=rationale,
        evidence_signals=evidence[:8],
        freshness_date=freshness_date,
        confidence=confidence,
        warnings=tuple(warning.public_interpretation for warning in dashboard.warnings[:4]),
        source_provenance_summary=source_summary,
    )


def _metric_headline(dashboard: WorkforceDashboardPayload) -> str:
    return (
        f"{dashboard.region_summary.region_name} has a bounded early-career "
        "opportunity profile from available signals"
    )


def _metric_rationale(dashboard: WorkforceDashboardPayload) -> str:
    metrics = dashboard.core_metrics
    labels = (
        metrics.early_career_access_score.interpretation_label,
        metrics.internship_pipeline_score.interpretation_label,
        metrics.employer_dependency_score.interpretation_label,
        metrics.sector_diversity_score.interpretation_label,
    )
    return (
        "Available Layer 24 metrics report: "
        f"{'; '.join(label for label in labels if label)}. "
        "Further local validation is recommended."
    )


def _report_limitations(dashboard: WorkforceDashboardPayload) -> tuple[str, ...]:
    limitations: list[str] = [
        "This report is generated from Layer 24 backend policy payloads.",
        "It is an interpretive public report, not a causal or political claim.",
        "Short-term postings alone do not determine regional or education strategy.",
    ]
    for metric in _dashboard_metrics(dashboard):
        limitations.extend(metric.limitations[:2])
    limitations.extend(
        "Further local validation is recommended."
        for warning in dashboard.warnings
        if "validation" in warning.public_interpretation.casefold()
    )
    return tuple(dict.fromkeys(limitations))[:12]


def _dashboard_metrics(dashboard: WorkforceDashboardPayload) -> tuple[PolicyMetric, ...]:
    metrics = dashboard.core_metrics
    return (
        metrics.opportunity_concentration_score,
        metrics.early_career_access_score,
        metrics.internship_pipeline_score,
        metrics.employer_dependency_score,
        metrics.sector_diversity_score,
        metrics.talent_export_risk_score,
    )


def _source_summary(
    dashboard: WorkforceDashboardPayload,
) -> PublicSourceProvenanceSummary:
    return PublicSourceProvenanceSummary(
        data_basis="public_safe_summary",
        source_count=dashboard.source_summary.source_count,
        source_categories=dashboard.source_summary.source_categories or ("Layer 24",),
        provenance_notes=(
            *dashboard.source_summary.evidence_summary[:9],
            "No raw source references or private review fields are exposed.",
        ),
    )


def _confidence_for_report(level: Confidence) -> Confidence:
    if level is Confidence.HIGH:
        return Confidence.MEDIUM
    return level


def _freshness_status_for_report(status: FreshnessStatus) -> FreshnessStatus:
    if status in {FreshnessStatus.FRESH, FreshnessStatus.STALE}:
        return status
    return FreshnessStatus.UNKNOWN
