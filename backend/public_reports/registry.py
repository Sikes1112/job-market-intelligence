"""Static public report registry for Layer 19B.

The registry assembles public report artifacts from curated category-language
templates and existing public market vocabulary. It intentionally does not
calculate benchmark/index scores or recommendation rankings.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from backend.geography.market_coverage import PRIORITY_MARKETS, priority_market_by_id
from backend.public_reports.schemas import (
    PublicReportCitation,
    PublicReportInstitutionalCta,
    PublicReportLink,
    PublicReportListPayload,
    PublicReportMarket,
    PublicReportMarketResult,
    PublicReportPayload,
    PublicReportShareSummary,
    PublicReportSourceAuthority,
    PublicReportSummary,
    PublicSourceProvenanceSummary,
)
from backend.shared.confidence import Confidence
from backend.shared.freshness import FreshnessStatus

REQUIRED_PUBLIC_REPORT_SLUGS = frozenset(
    {
        "best-cities-early-career-ai-careers",
        "top-product-management-markets",
        "hidden-tech-hubs-new-graduates",
    }
)

_FRESHNESS_DATE = date(2026, 6, 18)
_REPORT_PERIOD = "2026 methodology preview"
_REPORT_WARNING = (
    "Layer 19B public reports are demo-safe templates. They feature markets "
    "from existing public market vocabulary and do not create benchmark scores "
    "or recommendation rankings."
)
_LIMITATIONS = (
    "No benchmark/index scoring is performed in Layer 19B.",
    "Featured order is editorial/template order, not a computed ranking.",
    "Markets can be absent because coverage is incomplete, not because opportunity is absent.",
    "Use the report as career market intelligence context and verify current "
    "decisions independently.",
)
_PROVENANCE = PublicSourceProvenanceSummary(
    data_basis="demo_template",
    source_count=len(PRIORITY_MARKETS),
    source_categories=(
        "Layer 19 category language",
        "public priority-market vocabulary",
        "public methodology foundation",
    ),
    provenance_notes=(
        "No raw source references are exposed.",
        "No internal formula weights, review notes, or private source IDs are included.",
        "Featured markets are drawn from the existing public market registry.",
    ),
)
_RELATED_PUBLIC_LINKS = (
    PublicReportLink(label="Category glossary", href="/glossary", link_type="public_page"),
    PublicReportLink(label="Methodology foundation", href="/methodology", link_type="public_page"),
    PublicReportLink(label="Public benchmarks", href="/benchmarks", link_type="public_page"),
    PublicReportLink(label="Data limitations", href="/data-limitations", link_type="public_page"),
)
_PRODUCT_ATTRIBUTION = (
    "Opportunity Geography Intelligence / Career Market Intelligence"
)
_SOURCE_AUTHORITY = PublicReportSourceAuthority(
    labels=(
        "demo-safe",
        "low-confidence",
        "methodology-backed",
        "not production ranking truth",
        "Layer 19 public report artifact",
    ),
    summary=(
        "This report is a public Layer 19 display artifact. It packages public "
        "category language, methodology, limitations, freshness, confidence, and "
        "provenance notes without creating production rankings or hidden scoring."
    ),
)
_INSTITUTIONAL_CTA = PublicReportInstitutionalCta(
    label="Use this report for career-center planning",
    body=(
        "Apply the report as directional career-market intelligence for advising "
        "and placement strategy, then verify current coverage before decisions."
    ),
    href="/career-market-guides",
    link_type="public_page",
)


@dataclass(frozen=True, slots=True)
class MarketResultTemplate:
    market_id: str
    headline: str
    rationale: str
    evidence_signals: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PublicReportTemplate:
    slug: str
    title: str
    category: str
    summary: str
    methodology_summary: str
    market_results: tuple[MarketResultTemplate, ...]


_TEMPLATES: tuple[PublicReportTemplate, ...] = (
    PublicReportTemplate(
        slug="best-cities-early-career-ai-careers",
        title="Best Cities for Early-Career AI Careers",
        category="early-career-ai",
        summary=(
            "A public career-market intelligence template for understanding where "
            "early-career AI opportunity may be worth deeper investigation."
        ),
        methodology_summary=(
            "This report uses Layer 19 category language and existing public "
            "priority-market vocabulary to present featured markets for early-career "
            "AI career exploration. It does not calculate new AI scores, benchmark "
            "indices, recommendation rankings, or live job-board availability."
        ),
        market_results=(
            MarketResultTemplate(
                market_id="boston",
                headline="Research, university, and AI-adjacent ecosystem signal",
                rationale=(
                    "Boston is featured as a category-example market where AI, "
                    "research, university recruiting, and early-career access are "
                    "natural evidence areas to inspect before any ranked claim."
                ),
                evidence_signals=(
                    "early-career access",
                    "AI/cloud-adjacent role family",
                    "regional opportunity density",
                ),
            ),
            MarketResultTemplate(
                market_id="sf_bay_area",
                headline="Dense AI employer ecosystem with high competition caveat",
                rationale=(
                    "SF Bay Area is featured because it is a known technology ecosystem "
                    "that future reports may examine with explicit coverage, competition, "
                    "freshness, and confidence caveats."
                ),
                evidence_signals=(
                    "company-region presence",
                    "AI ecosystem concentration",
                    "market fit caveat",
                ),
            ),
            MarketResultTemplate(
                market_id="seattle",
                headline="Large-platform and cloud-adjacent AI market signal",
                rationale=(
                    "Seattle is featured as a public-market-vocabulary example for "
                    "cloud-adjacent AI careers, subject to current-source verification."
                ),
                evidence_signals=(
                    "AI/cloud-adjacent signal",
                    "company-region presence",
                    "source verification required",
                ),
            ),
        ),
    ),
    PublicReportTemplate(
        slug="top-product-management-markets",
        title="Top Product Management Markets",
        category="product-management",
        summary=(
            "A public career-market intelligence template for comparing product "
            "management market context without claiming computed rankings."
        ),
        methodology_summary=(
            "This report frames product management market intelligence around "
            "company-region presence, role-family relevance, regional opportunity "
            "density, and early-career access. Layer 19B presents featured examples "
            "only; it does not create product-market scores or recommendation order."
        ),
        market_results=(
            MarketResultTemplate(
                market_id="nyc",
                headline="Large cross-industry product-market signal",
                rationale=(
                    "NYC is featured because product careers often span finance, media, "
                    "enterprise, consumer, and startup contexts that future coverage can "
                    "inspect with evidence and freshness labels."
                ),
                evidence_signals=(
                    "role-family breadth",
                    "regional opportunity density",
                    "company-region presence",
                ),
            ),
            MarketResultTemplate(
                market_id="austin",
                headline="Growing product and startup-market context",
                rationale=(
                    "Austin is featured as a market where product-management opportunity "
                    "may require careful distinction between durable company presence and "
                    "short-term hiring noise."
                ),
                evidence_signals=(
                    "product role-family context",
                    "market fit",
                    "coverage caveat",
                ),
            ),
            MarketResultTemplate(
                market_id="chicago",
                headline="Enterprise and diversified product-market context",
                rationale=(
                    "Chicago is featured as a diversified market example where future "
                    "reports should inspect employer mix, entry-level access, and sector "
                    "coverage before any comparative claim."
                ),
                evidence_signals=(
                    "enterprise product context",
                    "sector mix",
                    "early-career access caveat",
                ),
            ),
        ),
    ),
    PublicReportTemplate(
        slug="hidden-tech-hubs-new-graduates",
        title="Hidden Tech Hubs for New Graduates",
        category="hidden-tech-hubs",
        summary=(
            "A public opportunity-geography template for markets that may deserve "
            "attention from new graduates, with explicit low-confidence caveats."
        ),
        methodology_summary=(
            "This report uses featured-market templates to demonstrate how hidden-hub "
            "claims should disclose evidence, missing data, freshness, and confidence. "
            "It does not identify hidden markets through a proprietary score or index."
        ),
        market_results=(
            MarketResultTemplate(
                market_id="raleigh_durham",
                headline="Research-triangle market context for new graduates",
                rationale=(
                    "Raleigh-Durham is featured as a market where university, research, "
                    "and regional employer signals can be useful but need current coverage "
                    "checks before recommendations."
                ),
                evidence_signals=(
                    "early-career access",
                    "regional opportunity density",
                    "source freshness required",
                ),
            ),
            MarketResultTemplate(
                market_id="pittsburgh",
                headline="Robotics, AI, and university-adjacent market context",
                rationale=(
                    "Pittsburgh is featured as an example hidden-hub candidate where "
                    "career-market signals should remain cautious until employer presence "
                    "and entry-level pathways are verified."
                ),
                evidence_signals=(
                    "university-adjacent ecosystem",
                    "AI/robotics context",
                    "low-confidence caveat",
                ),
            ),
            MarketResultTemplate(
                market_id="minneapolis",
                headline="Diversified employer base with coverage caveat",
                rationale=(
                    "Minneapolis is featured as a diversified-market example for new "
                    "graduates, but Layer 19B does not assert hidden-opportunity strength."
                ),
                evidence_signals=(
                    "diversified employer base",
                    "new-graduate market fit",
                    "coverage caveat",
                ),
            ),
        ),
    ),
)


def list_public_reports() -> PublicReportListPayload:
    return PublicReportListPayload(
        reports=tuple(_summary_for_report(build_public_report(template)) for template in _TEMPLATES)
    )


def get_public_report(slug: str) -> PublicReportPayload | None:
    normalized = slug.strip().lower()
    for template in _TEMPLATES:
        if template.slug == normalized:
            return build_public_report(template)
    return None


def build_public_report(template: PublicReportTemplate) -> PublicReportPayload:
    results = tuple(_result_from_template(result) for result in template.market_results)
    markets = tuple(
        PublicReportMarket(
            market_id=result.market_id,
            market_label=result.market_label,
            coverage_note=(
                "Coverage must be checked in current market outputs before treating "
                "this featured market as actionable."
            ),
        )
        for result in results
    )
    return PublicReportPayload(
        report_id=f"public_report:{template.slug}",
        slug=template.slug,
        title=template.title,
        category=template.category,
        report_period=_REPORT_PERIOD,
        summary=template.summary,
        markets_covered=markets,
        market_results=results,
        methodology_summary=template.methodology_summary,
        limitations=_LIMITATIONS,
        freshness_date=_FRESHNESS_DATE,
        freshness_status=FreshnessStatus.UNKNOWN,
        confidence=Confidence.LOW,
        warnings=(_REPORT_WARNING,),
        source_provenance_summary=_PROVENANCE,
        related_links=_related_links(template.slug),
        suggested_citation=_citation_for_template(template),
        share_summary=_share_summary_for_template(template),
        source_authority=_SOURCE_AUTHORITY,
        institutional_cta=_INSTITUTIONAL_CTA,
    )


def _result_from_template(template: MarketResultTemplate) -> PublicReportMarketResult:
    market = priority_market_by_id(template.market_id)
    if market is None:
        raise RuntimeError(f"unknown public priority market: {template.market_id}")
    return PublicReportMarketResult(
        result_type="featured",
        rank=None,
        market_id=market.market_id,
        market_label=market.display_name,
        headline=template.headline,
        rationale=template.rationale,
        evidence_signals=template.evidence_signals,
        freshness_date=_FRESHNESS_DATE,
        confidence=Confidence.LOW,
        warnings=(
            "Featured-market example only; not a computed ranking.",
            "Current coverage, freshness, and source evidence must be checked before use.",
        ),
        source_provenance_summary=_PROVENANCE,
    )


def _summary_for_report(report: PublicReportPayload) -> PublicReportSummary:
    return PublicReportSummary(
        report_id=report.report_id,
        slug=report.slug,
        title=report.title,
        category=report.category,
        report_period=report.report_period,
        summary=report.summary,
        freshness_date=report.freshness_date,
        confidence=report.confidence,
        warnings=report.warnings,
    )


def _related_links(slug: str) -> tuple[PublicReportLink, ...]:
    related_reports = tuple(
        PublicReportLink(
            label=template.title,
            href=f"/reports/{template.slug}",
            link_type="report",
        )
        for template in _TEMPLATES
        if template.slug != slug
    )
    return (*related_reports[:2], *_RELATED_PUBLIC_LINKS)


def _citation_for_template(template: PublicReportTemplate) -> PublicReportCitation:
    return PublicReportCitation(
        source_name="Job Market Intelligence",
        title=template.title,
        period=_REPORT_PERIOD,
        product_attribution=_PRODUCT_ATTRIBUTION,
        public_path=f"/reports/{template.slug}",
        accessed_or_freshness_date=_FRESHNESS_DATE,
    )


def _share_summary_for_template(template: PublicReportTemplate) -> PublicReportShareSummary:
    return PublicReportShareSummary(
        title=template.title,
        category_claim="Public career market intelligence report",
        confidence_label="Low confidence",
        freshness_label=f"Freshness unknown - {_FRESHNESS_DATE.isoformat()}",
        takeaway=template.summary,
        public_path=f"/reports/{template.slug}",
        warning="Demo-safe public report; not production ranking truth.",
    )
