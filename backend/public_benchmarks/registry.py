"""Static public benchmark registry for Layer 19C.

The registry packages public benchmark/index artifacts from curated category
language and existing public market vocabulary. It intentionally does not
calculate production benchmark scores, create recommendation rankings, or
modify market coverage authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from backend.geography.market_coverage import PRIORITY_MARKETS, priority_market_by_id
from backend.public_benchmarks.schemas import (
    PublicBenchmarkCitation,
    PublicBenchmarkInstitutionalCta,
    PublicBenchmarkLink,
    PublicBenchmarkListPayload,
    PublicBenchmarkMarketResult,
    PublicBenchmarkPayload,
    PublicBenchmarkScoreDisplay,
    PublicBenchmarkShareSummary,
    PublicBenchmarkSourceAuthority,
    PublicBenchmarkSourceSummary,
    PublicBenchmarkSubscore,
    PublicBenchmarkSummary,
)
from backend.shared.confidence import Confidence
from backend.shared.freshness import FreshnessStatus

REQUIRED_PUBLIC_BENCHMARK_SLUGS = frozenset(
    {
        "early-career-tech-access-index",
        "ai-career-geography-index",
        "product-career-market-index",
    }
)

_FRESHNESS_DATE = date(2026, 6, 18)
_BENCHMARK_PERIOD = "2026 methodology preview"
_BENCHMARK_WARNING = (
    "Layer 19C public benchmarks are demo-safe display templates and not "
    "production benchmark scores. They package existing public market vocabulary "
    "without changing recommendation, coverage, freshness, or provenance authority."
)
_LIMITATIONS = (
    "No production benchmark/index scoring is performed in Layer 19C.",
    "Demo display values are static examples, not production-grade truth.",
    "Featured order is editorial/template order, not a computed ranking.",
    "Markets can be absent because coverage is incomplete, not because opportunity is absent.",
    "Use benchmark pages as category explanation surfaces and verify decisions independently.",
)
_PROVENANCE = PublicBenchmarkSourceSummary(
    data_basis="demo_template",
    source_count=len(PRIORITY_MARKETS),
    source_categories=(
        "Layer 19 benchmark methodology",
        "public priority-market vocabulary",
        "shared freshness and confidence vocabulary",
    ),
    provenance_notes=(
        "No raw source references are exposed.",
        "No internal formula weights, review notes, or private source IDs are included.",
        "Demo display values are static public templates, not platform score rows.",
    ),
)
_RELATED_PUBLIC_LINKS = (
    PublicBenchmarkLink(
        label="Benchmark methodology",
        href="/methodology",
        link_type="public_page",
    ),
    PublicBenchmarkLink(label="Category glossary", href="/glossary", link_type="public_page"),
    PublicBenchmarkLink(
        label="Market intelligence reports",
        href="/reports",
        link_type="public_page",
    ),
    PublicBenchmarkLink(
        label="Data limitations",
        href="/data-limitations",
        link_type="public_page",
    ),
)
_PRODUCT_ATTRIBUTION = (
    "Opportunity Geography Intelligence / Career Market Intelligence"
)
_SOURCE_AUTHORITY = PublicBenchmarkSourceAuthority(
    labels=(
        "demo-safe",
        "low-confidence",
        "methodology-backed",
        "not production benchmark truth",
        "Layer 19 public benchmark artifact",
    ),
    summary=(
        "This benchmark is a public Layer 19 display artifact. It normalizes "
        "public category language and score-display caveats without creating "
        "production benchmark scoring, recommendation ranking, or market "
        "coverage authority."
    ),
)
_INSTITUTIONAL_CTA = PublicBenchmarkInstitutionalCta(
    label="Compare markets for student placement strategy",
    body=(
        "Use this index as directional career-market intelligence for advising "
        "and planning, then verify authorized coverage and current-source evidence."
    ),
    href="/career-market-guides",
    link_type="public_page",
)
_REPORT_LINKS = {
    "early-career-tech-access-index": PublicBenchmarkLink(
        label="Best Cities for Early-Career AI Careers",
        href="/reports/best-cities-early-career-ai-careers",
        link_type="report",
    ),
    "ai-career-geography-index": PublicBenchmarkLink(
        label="Best Cities for Early-Career AI Careers",
        href="/reports/best-cities-early-career-ai-careers",
        link_type="report",
    ),
    "product-career-market-index": PublicBenchmarkLink(
        label="Top Product Management Markets",
        href="/reports/top-product-management-markets",
        link_type="report",
    ),
}


@dataclass(frozen=True, slots=True)
class SubscoreTemplate:
    key: str
    label: str
    value: float
    explanation: str


@dataclass(frozen=True, slots=True)
class BenchmarkMarketTemplate:
    market_id: str
    display_value: float
    explanation: str
    subscores: tuple[SubscoreTemplate, ...]


@dataclass(frozen=True, slots=True)
class PublicBenchmarkTemplate:
    slug: str
    name: str
    category: str
    summary: str
    methodology_summary: str
    market_results: tuple[BenchmarkMarketTemplate, ...]


_TEMPLATES: tuple[PublicBenchmarkTemplate, ...] = (
    PublicBenchmarkTemplate(
        slug="early-career-tech-access-index",
        name="Early-Career Tech Access Index",
        category="early-career-access",
        summary=(
            "A demo-safe public benchmark template for explaining how early-career "
            "technology access could be displayed once authorized scoring inputs are wired."
        ),
        methodology_summary=(
            "This benchmark packages public category language around early-career "
            "access, company-region presence, and regional opportunity density. "
            "Layer 19C does not calculate production benchmark scores or rankings; "
            "the values shown are not production-grade benchmark truth."
        ),
        market_results=(
            BenchmarkMarketTemplate(
                market_id="boston",
                display_value=68.0,
                explanation=(
                    "Boston is featured as a demo-safe early-career access example "
                    "because it has natural university, research, and employer-presence "
                    "signals to inspect. This is not production benchmark scoring."
                ),
                subscores=(
                    SubscoreTemplate(
                        key="early_career_access",
                        label="Early-career access",
                        value=70.0,
                        explanation=(
                            "Static display proxy for internship and entry-level signal areas."
                        ),
                    ),
                    SubscoreTemplate(
                        key="company_region_presence",
                        label="Company-region presence",
                        value=64.0,
                        explanation="Static display proxy for employer presence categories.",
                    ),
                    SubscoreTemplate(
                        key="coverage_readiness",
                        label="Coverage readiness",
                        value=62.0,
                        explanation="Static display proxy reminding readers to inspect coverage.",
                    ),
                ),
            ),
            BenchmarkMarketTemplate(
                market_id="raleigh_durham",
                display_value=61.0,
                explanation=(
                    "Raleigh-Durham is featured as a demo-safe market where research, "
                    "university, and employer signals may matter. This is not production "
                    "benchmark scoring."
                ),
                subscores=(
                    SubscoreTemplate(
                        key="early_career_access",
                        label="Early-career access",
                        value=63.0,
                        explanation="Static display proxy for new-graduate access signals.",
                    ),
                    SubscoreTemplate(
                        key="company_region_presence",
                        label="Company-region presence",
                        value=58.0,
                        explanation="Static display proxy for employer mix visibility.",
                    ),
                    SubscoreTemplate(
                        key="coverage_readiness",
                        label="Coverage readiness",
                        value=55.0,
                        explanation="Static display proxy for coverage-check needs.",
                    ),
                ),
            ),
            BenchmarkMarketTemplate(
                market_id="chicago",
                display_value=57.0,
                explanation=(
                    "Chicago is featured as a demo-safe diversified-market example. "
                    "The display value is not production benchmark scoring."
                ),
                subscores=(
                    SubscoreTemplate(
                        key="early_career_access",
                        label="Early-career access",
                        value=56.0,
                        explanation="Static display proxy for broad entry-level access categories.",
                    ),
                    SubscoreTemplate(
                        key="company_region_presence",
                        label="Company-region presence",
                        value=60.0,
                        explanation="Static display proxy for diversified employer presence.",
                    ),
                    SubscoreTemplate(
                        key="coverage_readiness",
                        label="Coverage readiness",
                        value=52.0,
                        explanation="Static display proxy for public coverage caveats.",
                    ),
                ),
            ),
        ),
    ),
    PublicBenchmarkTemplate(
        slug="ai-career-geography-index",
        name="AI Career Geography Index",
        category="ai-career-geography",
        summary=(
            "A demo-safe public benchmark template for explaining AI career geography "
            "signals without asserting production-grade AI market rankings."
        ),
        methodology_summary=(
            "This benchmark frames AI career geography around AI-adjacent employer "
            "presence, early-career access, and source coverage. Layer 19C uses "
            "static display values only; it does not calculate production AI index "
            "scores or recommendation rankings."
        ),
        market_results=(
            BenchmarkMarketTemplate(
                market_id="sf_bay_area",
                display_value=72.0,
                explanation=(
                    "SF Bay Area is featured as a demo-safe AI ecosystem example with "
                    "high competition caveats. This is not production benchmark scoring."
                ),
                subscores=(
                    SubscoreTemplate(
                        key="ai_ecosystem_signal",
                        label="AI ecosystem signal",
                        value=74.0,
                        explanation="Static display proxy for AI-adjacent ecosystem categories.",
                    ),
                    SubscoreTemplate(
                        key="early_career_access",
                        label="Early-career access",
                        value=55.0,
                        explanation="Static display proxy that keeps access caveats visible.",
                    ),
                    SubscoreTemplate(
                        key="source_coverage",
                        label="Source coverage",
                        value=66.0,
                        explanation="Static display proxy for source verification needs.",
                    ),
                ),
            ),
            BenchmarkMarketTemplate(
                market_id="seattle",
                display_value=66.0,
                explanation=(
                    "Seattle is featured as a demo-safe cloud and AI-adjacent example. "
                    "The display value is not production benchmark scoring."
                ),
                subscores=(
                    SubscoreTemplate(
                        key="ai_ecosystem_signal",
                        label="AI ecosystem signal",
                        value=65.0,
                        explanation="Static display proxy for AI/cloud-adjacent signals.",
                    ),
                    SubscoreTemplate(
                        key="early_career_access",
                        label="Early-career access",
                        value=58.0,
                        explanation="Static display proxy for entry-level pathway categories.",
                    ),
                    SubscoreTemplate(
                        key="source_coverage",
                        label="Source coverage",
                        value=61.0,
                        explanation="Static display proxy for freshness and provenance checks.",
                    ),
                ),
            ),
            BenchmarkMarketTemplate(
                market_id="boston",
                display_value=63.0,
                explanation=(
                    "Boston is featured as a demo-safe research and AI-adjacent market "
                    "example. This is not production benchmark scoring."
                ),
                subscores=(
                    SubscoreTemplate(
                        key="ai_ecosystem_signal",
                        label="AI ecosystem signal",
                        value=61.0,
                        explanation="Static display proxy for AI research and employer categories.",
                    ),
                    SubscoreTemplate(
                        key="early_career_access",
                        label="Early-career access",
                        value=64.0,
                        explanation="Static display proxy for university-adjacent pathways.",
                    ),
                    SubscoreTemplate(
                        key="source_coverage",
                        label="Source coverage",
                        value=59.0,
                        explanation="Static display proxy for coverage-check requirements.",
                    ),
                ),
            ),
        ),
    ),
    PublicBenchmarkTemplate(
        slug="product-career-market-index",
        name="Product Career Market Index",
        category="product-career-market",
        summary=(
            "A demo-safe public benchmark template for explaining product-career "
            "market fit and regional opportunity density without production scoring."
        ),
        methodology_summary=(
            "This benchmark packages public product-career market language around "
            "role-family breadth, company-region presence, market fit, and coverage. "
            "Layer 19C does not calculate production product-market scores or rankings."
        ),
        market_results=(
            BenchmarkMarketTemplate(
                market_id="nyc",
                display_value=69.0,
                explanation=(
                    "NYC is featured as a demo-safe cross-industry product market "
                    "example. This is not production benchmark scoring."
                ),
                subscores=(
                    SubscoreTemplate(
                        key="role_family_breadth",
                        label="Role-family breadth",
                        value=70.0,
                        explanation="Static display proxy for product role-family diversity.",
                    ),
                    SubscoreTemplate(
                        key="company_region_presence",
                        label="Company-region presence",
                        value=68.0,
                        explanation="Static display proxy for cross-industry employer presence.",
                    ),
                    SubscoreTemplate(
                        key="market_fit_context",
                        label="Market fit context",
                        value=62.0,
                        explanation="Static display proxy for fit caveats and sector mix.",
                    ),
                ),
            ),
            BenchmarkMarketTemplate(
                market_id="austin",
                display_value=60.0,
                explanation=(
                    "Austin is featured as a demo-safe startup and product-market "
                    "context example. The display value is not production benchmark scoring."
                ),
                subscores=(
                    SubscoreTemplate(
                        key="role_family_breadth",
                        label="Role-family breadth",
                        value=58.0,
                        explanation="Static display proxy for product role-family visibility.",
                    ),
                    SubscoreTemplate(
                        key="company_region_presence",
                        label="Company-region presence",
                        value=60.0,
                        explanation="Static display proxy for employer presence categories.",
                    ),
                    SubscoreTemplate(
                        key="market_fit_context",
                        label="Market fit context",
                        value=57.0,
                        explanation="Static display proxy for market-fit caveats.",
                    ),
                ),
            ),
            BenchmarkMarketTemplate(
                market_id="chicago",
                display_value=58.0,
                explanation=(
                    "Chicago is featured as a demo-safe diversified product-market "
                    "example. This is not production benchmark scoring."
                ),
                subscores=(
                    SubscoreTemplate(
                        key="role_family_breadth",
                        label="Role-family breadth",
                        value=56.0,
                        explanation="Static display proxy for enterprise product context.",
                    ),
                    SubscoreTemplate(
                        key="company_region_presence",
                        label="Company-region presence",
                        value=61.0,
                        explanation="Static display proxy for diversified employer presence.",
                    ),
                    SubscoreTemplate(
                        key="market_fit_context",
                        label="Market fit context",
                        value=55.0,
                        explanation="Static display proxy for sector and fit interpretation.",
                    ),
                ),
            ),
        ),
    ),
)


def list_public_benchmarks() -> PublicBenchmarkListPayload:
    return PublicBenchmarkListPayload(
        benchmarks=tuple(
            _summary_for_benchmark(build_public_benchmark(template))
            for template in _TEMPLATES
        )
    )


def get_public_benchmark(slug: str) -> PublicBenchmarkPayload | None:
    normalized = slug.strip().lower()
    for template in _TEMPLATES:
        if template.slug == normalized:
            return build_public_benchmark(template)
    return None


def build_public_benchmark(template: PublicBenchmarkTemplate) -> PublicBenchmarkPayload:
    return PublicBenchmarkPayload(
        benchmark_id=f"public_benchmark:{template.slug}",
        slug=template.slug,
        name=template.name,
        category=template.category,
        period=_BENCHMARK_PERIOD,
        summary=template.summary,
        methodology_summary=template.methodology_summary,
        limitations=_LIMITATIONS,
        freshness_date=_FRESHNESS_DATE,
        freshness_status=FreshnessStatus.UNKNOWN,
        confidence=Confidence.LOW,
        warnings=(_BENCHMARK_WARNING,),
        market_results=tuple(
            _result_from_template(result) for result in template.market_results
        ),
        source_provenance_summary=_PROVENANCE,
        related_links=_related_links(template.slug),
        suggested_citation=_citation_for_template(template),
        share_summary=_share_summary_for_template(template),
        source_authority=_SOURCE_AUTHORITY,
        institutional_cta=_INSTITUTIONAL_CTA,
    )


def _result_from_template(template: BenchmarkMarketTemplate) -> PublicBenchmarkMarketResult:
    market = priority_market_by_id(template.market_id)
    if market is None:
        raise RuntimeError(f"unknown public priority market: {template.market_id}")
    return PublicBenchmarkMarketResult(
        result_type="featured",
        rank=None,
        market_id=market.market_id,
        market_label=market.display_name,
        score_display=PublicBenchmarkScoreDisplay(
            label="Demo display score",
            value=template.display_value,
            display_value=f"{template.display_value:.0f} / 100 demo-safe display",
            score_basis="demo_static",
            caveat="Demo display value only; not production benchmark scoring.",
        ),
        subscores=tuple(_subscore_from_template(subscore) for subscore in template.subscores),
        explanation=template.explanation,
        warnings=(
            "Demo-safe benchmark display only; not production-grade truth.",
            "Current coverage, freshness, source evidence, and authorized scoring must be checked.",
        ),
        freshness_date=_FRESHNESS_DATE,
        confidence=Confidence.LOW,
        source_provenance_summary=_PROVENANCE,
    )


def _subscore_from_template(template: SubscoreTemplate) -> PublicBenchmarkSubscore:
    return PublicBenchmarkSubscore(
        key=template.key,
        label=template.label,
        value=template.value,
        display_value=f"{template.value:.0f} / 100 demo-safe display",
        explanation=template.explanation,
    )


def _summary_for_benchmark(benchmark: PublicBenchmarkPayload) -> PublicBenchmarkSummary:
    return PublicBenchmarkSummary(
        benchmark_id=benchmark.benchmark_id,
        slug=benchmark.slug,
        name=benchmark.name,
        category=benchmark.category,
        period=benchmark.period,
        summary=benchmark.summary,
        freshness_date=benchmark.freshness_date,
        confidence=benchmark.confidence,
        warnings=benchmark.warnings,
    )


def _related_links(slug: str) -> tuple[PublicBenchmarkLink, ...]:
    related_benchmarks = tuple(
        PublicBenchmarkLink(
            label=template.name,
            href=f"/benchmarks/{template.slug}",
            link_type="benchmark",
        )
        for template in _TEMPLATES
        if template.slug != slug
    )
    report_link = _REPORT_LINKS.get(slug)
    links = (*related_benchmarks[:2], *_RELATED_PUBLIC_LINKS)
    return (report_link, *links) if report_link is not None else links


def _citation_for_template(template: PublicBenchmarkTemplate) -> PublicBenchmarkCitation:
    return PublicBenchmarkCitation(
        source_name="Job Market Intelligence",
        title=template.name,
        period=_BENCHMARK_PERIOD,
        product_attribution=_PRODUCT_ATTRIBUTION,
        public_path=f"/benchmarks/{template.slug}",
        accessed_or_freshness_date=_FRESHNESS_DATE,
    )


def _share_summary_for_template(
    template: PublicBenchmarkTemplate,
) -> PublicBenchmarkShareSummary:
    return PublicBenchmarkShareSummary(
        title=template.name,
        category_claim="Public career market intelligence benchmark",
        confidence_label="Low confidence",
        freshness_label=f"Freshness unknown - {_FRESHNESS_DATE.isoformat()}",
        takeaway=template.summary,
        public_path=f"/benchmarks/{template.slug}",
        warning="Demo-safe public benchmark; not production benchmark truth.",
    )
