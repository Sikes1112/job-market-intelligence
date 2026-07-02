import { PUBLIC_PAGE_PATHS, type PublicPage } from "./urlState";

export type LegalPublicPage =
  | "glossary"
  | "methodology"
  | "data-limitations"
  | "privacy"
  | "terms"
  | "sources";
export type PublicInfoPage = Exclude<PublicPage, "landing">;

export type PublicInfoLink = {
  page: PublicInfoPage;
  href: string;
  label: string;
};

export type PublicSection = {
  title: string;
  body: string;
  bullets?: string[];
};

export type LegalPageCopy = {
  eyebrow: string;
  title: string;
  intro: string;
  sections: PublicSection[];
};

export const PUBLIC_INFO_LINKS: PublicInfoLink[] = [
  { page: "guides", href: PUBLIC_PAGE_PATHS.guides, label: "Guides" },
  { page: "benchmarks", href: PUBLIC_PAGE_PATHS.benchmarks, label: "Benchmarks" },
  { page: "reports", href: PUBLIC_PAGE_PATHS.reports, label: "Reports" },
  { page: "forecasts", href: PUBLIC_PAGE_PATHS.forecasts, label: "Forecasts" },
  { page: "data-standards", href: PUBLIC_PAGE_PATHS["data-standards"], label: "Data standards" },
  { page: "developers", href: PUBLIC_PAGE_PATHS.developers, label: "Developers" },
  { page: "data-licensing", href: PUBLIC_PAGE_PATHS["data-licensing"], label: "Data licensing" },
  { page: "glossary", href: PUBLIC_PAGE_PATHS.glossary, label: "Glossary" },
  { page: "methodology", href: PUBLIC_PAGE_PATHS.methodology, label: "Methodology" },
  { page: "data-limitations", href: PUBLIC_PAGE_PATHS["data-limitations"], label: "Data limitations" },
  { page: "sources", href: PUBLIC_PAGE_PATHS.sources, label: "Source explanation" },
  { page: "privacy", href: PUBLIC_PAGE_PATHS.privacy, label: "Privacy" },
  { page: "terms", href: PUBLIC_PAGE_PATHS.terms, label: "Terms and disclaimer" },
];

export type DeveloperDocPageKey =
  | "developer-docs"
  | "developer-doc-authentication"
  | "developer-doc-errors"
  | "developer-doc-rate-limits"
  | "developer-doc-freshness-confidence"
  | "developer-doc-region-scores"
  | "developer-doc-company-geography"
  | "developer-doc-early-career-access"
  | "developer-doc-hiring-concentration"
  | "developer-doc-market-comparisons";

export type DeveloperDocCopy = {
  page: DeveloperDocPageKey;
  title: string;
  summary: string;
  sections: PublicSection[];
};

export type LicensingDatasetCopy = {
  datasetId: string;
  title: string;
  description: string;
  sampleFields: string[];
  restrictions: string[];
  sourceSafety: string;
};

export const DEVELOPER_DOCS_NAV: Array<{ page: DeveloperDocPageKey; label: string; href: string }> = [
  { page: "developer-docs", label: "Overview", href: PUBLIC_PAGE_PATHS["developer-docs"] },
  { page: "developer-doc-authentication", label: "Authentication", href: PUBLIC_PAGE_PATHS["developer-doc-authentication"] },
  { page: "developer-doc-errors", label: "Errors", href: PUBLIC_PAGE_PATHS["developer-doc-errors"] },
  { page: "developer-doc-rate-limits", label: "Rate limits", href: PUBLIC_PAGE_PATHS["developer-doc-rate-limits"] },
  { page: "developer-doc-freshness-confidence", label: "Freshness and confidence", href: PUBLIC_PAGE_PATHS["developer-doc-freshness-confidence"] },
  { page: "developer-doc-region-scores", label: "Region scores", href: PUBLIC_PAGE_PATHS["developer-doc-region-scores"] },
  { page: "developer-doc-company-geography", label: "Company geography", href: PUBLIC_PAGE_PATHS["developer-doc-company-geography"] },
  { page: "developer-doc-early-career-access", label: "Early-career access", href: PUBLIC_PAGE_PATHS["developer-doc-early-career-access"] },
  { page: "developer-doc-hiring-concentration", label: "Hiring concentration", href: PUBLIC_PAGE_PATHS["developer-doc-hiring-concentration"] },
  { page: "developer-doc-market-comparisons", label: "Market comparisons", href: PUBLIC_PAGE_PATHS["developer-doc-market-comparisons"] },
];

export const DEVELOPER_DOCS_COPY: Record<DeveloperDocPageKey, DeveloperDocCopy> = {
  "developer-docs": {
    page: "developer-docs",
    title: "Platform API developer docs",
    summary:
      "Read-only market intelligence endpoints for external consumers. The API is versioned, key-authenticated, and intentionally public-safe.",
    sections: [
      {
        title: "Base surface",
        body:
          "All data endpoints live under /api/v1/platform and return a Layer 20 envelope with data, meta, and error fields.",
        bullets: [
          "GET /api/v1/platform/regions/{region_id}/scores",
          "GET /api/v1/platform/companies/{company_id}/geography",
          "GET /api/v1/platform/regions/{region_id}/early-career-access",
          "GET /api/v1/platform/markets/hiring-concentration",
          "GET /api/v1/platform/markets/compare",
        ],
      },
      {
        title: "Specs",
        body:
          "OpenAPI and Postman exports are available at /api/v1/platform/docs/openapi.json and /api/v1/platform/docs/postman.json.",
      },
    ],
  },
  "developer-doc-authentication": {
    page: "developer-doc-authentication",
    title: "Authentication",
    summary: "Secured Platform API endpoints require X-API-Key. Do not put raw keys in browser code or partner embeds.",
    sections: [
      {
        title: "Header",
        body: "Send X-API-Key with each Platform API data request.",
        bullets: ["Raw keys are returned only once.", "Stored keys use hashes, prefixes, and display strings only."],
      },
      {
        title: "Tiers and scopes",
        body:
          "Access requires both the backend-owned tier entitlement and the key's stored product scope for the requested product.",
      },
    ],
  },
  "developer-doc-errors": {
    page: "developer-doc-errors",
    title: "Errors",
    summary: "Errors use the same public-safe envelope as successful responses.",
    sections: [
      {
        title: "Access errors",
        body:
          "401 covers MISSING_API_KEY, INVALID_API_KEY, and REVOKED_API_KEY. 403 covers MISSING_PRODUCT_SCOPE and ENTITLEMENT_DENIED. 429 covers RATE_LIMIT_EXCEEDED.",
      },
      {
        title: "Request errors",
        body:
          "400 UNSUPPORTED_QUERY is returned for unsupported query parameters. 400 VALIDATION_ERROR is returned for malformed required query input.",
      },
    ],
  },
  "developer-doc-rate-limits": {
    page: "developer-doc-rate-limits",
    title: "Rate limits and usage",
    summary: "Tier limits are enforced before endpoint execution and successful requests consume monthly usage units.",
    sections: [
      {
        title: "Request windows",
        body: "Rate limits are tier-based request windows checked per API key.",
      },
      {
        title: "Monthly usage",
        body:
          "Monthly usage is counted from successful allowed request units. Denied requests are audit-logged but do not consume request units.",
      },
    ],
  },
  "developer-doc-freshness-confidence": {
    page: "developer-doc-freshness-confidence",
    title: "Freshness, confidence, source summary, and warnings",
    summary: "Every response meta block gives public-safe context for interpreting the returned data.",
    sections: [
      {
        title: "Freshness",
        body: "Freshness can be fresh, stale, partial, or unknown, with public-safe timestamps where available.",
      },
      {
        title: "Confidence and sources",
        body:
          "Confidence labels and source summaries explain output quality without exposing source ids, raw records, or scoring internals.",
      },
    ],
  },
  "developer-doc-region-scores": {
    page: "developer-doc-region-scores",
    title: "Region scores",
    summary: "GET /api/v1/platform/regions/{region_id}/scores returns public-safe regional score summaries.",
    sections: [{ title: "Product id", body: "region_scores" }],
  },
  "developer-doc-company-geography": {
    page: "developer-doc-company-geography",
    title: "Company geography",
    summary: "GET /api/v1/platform/companies/{company_id}/geography returns public-safe company-region coverage.",
    sections: [{ title: "Product id", body: "company_geography" }],
  },
  "developer-doc-early-career-access": {
    page: "developer-doc-early-career-access",
    title: "Early-career access",
    summary:
      "GET /api/v1/platform/regions/{region_id}/early-career-access returns public-safe early-career access summaries.",
    sections: [{ title: "Product id", body: "early_career_access" }],
  },
  "developer-doc-hiring-concentration": {
    page: "developer-doc-hiring-concentration",
    title: "Hiring concentration",
    summary:
      "GET /api/v1/platform/markets/hiring-concentration returns public-safe hiring concentration summaries.",
    sections: [{ title: "Product id", body: "hiring_concentration" }],
  },
  "developer-doc-market-comparisons": {
    page: "developer-doc-market-comparisons",
    title: "Market comparisons",
    summary:
      "GET /api/v1/platform/markets/compare returns public-safe comparisons for two region ids.",
    sections: [{ title: "Product id", body: "market_comparisons" }],
  },
};

export const DATA_LICENSING_COPY = {
  eyebrow: "Data licensing",
  title: "Derived market intelligence datasets",
  intro:
    "Licensing is limited to aggregated, derived, source-safe datasets. Raw scrape records, raw job listings, source ids, private user data, billing records, ingestion metadata, and scoring formulas are excluded.",
  cta: "Contact sales for enterprise licensing",
  datasets: [
    {
      datasetId: "regional_market_intelligence_v1",
      title: "Regional market intelligence",
      description: "Derived opportunity, coverage, early-career, and hiring summaries by region.",
      sampleFields: ["region_id", "coverage_tier", "opportunity_score", "early_career_access_score"],
      restrictions: ["No resale as raw job listings.", "No reverse-engineering source providers or scoring internals."],
      sourceSafety: "Raw scrape records, source ids, and ingestion metadata are excluded.",
    },
    {
      datasetId: "early_career_access_scores_v1",
      title: "Early-career access scores",
      description: "Derived internship, co-op, entry-level, and access pathway indicators.",
      sampleFields: ["region_id", "internship_count", "entry_level_full_time_count", "confidence_label"],
      restrictions: ["No applicant profiling or automated decisioning.", "Do not claim comprehensive market coverage."],
      sourceSafety: "Counts are derived summaries, not raw postings.",
    },
    {
      datasetId: "company_region_presence_v1",
      title: "Company-region presence",
      description: "Derived employer presence and regional activity summaries.",
      sampleFields: ["company_id", "region_id", "presence_status", "current_hiring"],
      restrictions: ["No employer CRM enrichment with raw source provenance.", "No redistribution as a source feed."],
      sourceSafety: "Presence basis is summarized without source refs.",
    },
    {
      datasetId: "historical_hiring_signal_snapshots_v1",
      title: "Historical hiring signal snapshots",
      description: "Derived time-window snapshots of hiring concentration and market signal changes.",
      sampleFields: ["snapshot_month", "region_id", "posting_count_30d", "concentration_share"],
      restrictions: ["No reconstruction of raw posting feeds.", "Historical gaps must remain visible."],
      sourceSafety: "Snapshots are aggregated and source-safe.",
    },
  ] satisfies LicensingDatasetCopy[],
};

export const DEMO_DISCLOSURE_COPY = {
  title: "Public demo disclosure",
  summary:
    "This Opportunity Geography Intelligence demo may combine seeded demo data with real imported records. Coverage is partial; data can be incomplete, stale, or missing. Derived scores are directional career-market signals, not absolute truth or individualized career advice.",
  bullets: [
    "Demo and real imported data may appear side by side.",
    "Coverage is partial and source availability varies by market, company, and date.",
    "Freshness and provenance metadata can be missing, stale, partial, or unknown.",
    "Scores summarize returned fields only; they do not cover the full job market or guarantee outcomes.",
    "Use this as informational context and independently verify important decisions.",
  ],
};

export const LANDING_COPY = {
  eyebrow: "Public demo",
  title: "Job Market Intelligence",
  intro:
    "An Opportunity Geography Intelligence and Career Market Intelligence platform for inspecting regional opportunity density, company-region presence, early-career access, source freshness, and market fit signals.",
  ctaLabel: "Enter demo",
  secondaryCtaLabel: "Review methodology",
  sections: [
    {
      title: "What it does",
      body:
        "The app organizes returned market outputs so visitors can explore regions, inspect company-region presence, compare regional score fields, and run a request-scoped discovery overlay.",
    },
    {
      title: "Category",
      body:
        "The product category is career market intelligence: public, structured explanation of where opportunity is concentrated, how employer presence varies by region, and which evidence is strong enough to treat as directional.",
    },
    {
      title: "What data it uses",
      body:
        "Views can include imported source records, prepared canonical facts, derived scoring outputs, freshness and provenance metadata, and seeded demo records where a full import is not present.",
    },
    {
      title: "Current limits",
      body:
        "The demo does not claim comprehensive job-market coverage, real-time completeness, public report rankings, benchmark scoring, or individualized career advice. Important decisions should be checked against independent sources.",
    },
  ],
};

export const LEGAL_PAGE_COPY: Record<LegalPublicPage, LegalPageCopy> = {
  glossary: {
    eyebrow: "Category language",
    title: "Category glossary",
    intro:
      "These terms make the product publicly legible as opportunity geography and career market intelligence rather than a job board.",
    sections: [
      {
        title: "Opportunity geography",
        body:
          "Opportunity geography describes how career opportunity varies across regions, employers, sectors, and access conditions. It is the map of where opportunity appears concentrated, accessible, durable, or under-covered.",
      },
      {
        title: "Career market intelligence",
        body:
          "Career market intelligence is structured analysis of regional labor-market conditions, employer presence, hiring signals, access patterns, source quality, and limitations for career planning. It explains market context without claiming to be an exhaustive list of open jobs.",
      },
      {
        title: "Company-region presence",
        body:
          "Company-region presence means observable evidence that an employer has meaningful activity in a region, such as offices, roles, hiring traces, internship activity, partnerships, or other verified market signals.",
      },
      {
        title: "Early-career access",
        body:
          "Early-career access describes whether a market or employer has visible pathways for students, interns, new graduates, career switchers, and other candidates without extensive prior experience.",
      },
      {
        title: "Market fit",
        body:
          "Market fit is the alignment between a user's goals and the visible evidence for a region, company, role family, industry, career stage, preferences, and constraints. It is directional and should not be treated as individualized advice.",
      },
      {
        title: "Regional opportunity density",
        body:
          "Regional opportunity density describes the concentration of relevant employers, hiring signals, company-region presence, sector activity, access pathways, and evidence quality in a specific geography.",
      },
      {
        title: "Career-market signal",
        body:
          "A career-market signal is a structured piece of evidence or derived indicator about opportunity conditions. Signals can be strong, weak, stale, partial, missing, or inferred, and must be read with coverage and freshness context.",
      },
    ],
  },
  methodology: {
    eyebrow: "Public methodology",
    title: "Methodology foundation",
    intro:
      "This page explains how public opportunity geography and career market intelligence surfaces should be read. It defines explanation posture only; Batch 19A does not create report rankings or benchmark scoring.",
    sections: [
      {
        title: "What the product explains",
        body:
          "Public pages explain regional opportunity density, company-region presence, early-career access, market fit, career-market signals, coverage quality, freshness, source posture, and known limitations.",
      },
      {
        title: "Evidence posture",
        body:
          "Visible intelligence should separate source records, prepared canonical facts, derived signals, freshness metadata, confidence context, and demo data. Missing evidence is treated as unknown, not as proof that opportunity is absent.",
      },
      {
        title: "Report methodology",
        body:
          "Public report methodology should disclose report purpose, included geography, data windows, evidence categories, freshness posture, confidence posture, coverage limits, and caveats before any future report is published.",
      },
      {
        title: "Benchmark methodology",
        body:
          "Benchmark methodology should explain comparison boundaries, eligible inputs, coverage thresholds, confidence rules, limitations, and review expectations before any future benchmark score is exposed.",
      },
      {
        title: "Batch 19A boundary",
        body:
          "This foundation does not rank regions, score benchmarks, change recommendations, expand market coverage, refresh data, alter billing, add institutional authority, or personalize outputs. It only defines public language and explanation surfaces.",
      },
    ],
  },
  "data-limitations": {
    eyebrow: "Demo limitations",
    title: "Data limitations",
    intro:
      "This public demo exposes prepared job-market outputs with explicit caveats. It should not be treated as a complete or current map of the job market.",
    sections: [
      {
        title: "Coverage is partial",
        body:
          "The app only shows markets, companies, and fields returned by the current backend dataset. Missing regions, companies, industries, roles, or employers do not prove those opportunities are absent.",
      },
      {
        title: "Freshness can vary",
        body:
          "Source records and prepared outputs can be fresh, stale, partial, seeded demo, or unknown. Freshness labels and warnings should be read before relying on a result.",
      },
      {
        title: "Source coverage is incomplete",
        body:
          "Imported data may cover only selected sources and selected collection windows. A source not appearing in the demo does not mean it was checked exhaustively.",
      },
      {
        title: "Scores are derived signals",
        body:
          "Scores summarize returned fields and scoring logic. They are not absolute truth, individualized career advice, or guarantees of hiring outcomes.",
      },
    ],
  },
  privacy: {
    eyebrow: "Public demo posture",
    title: "Privacy notice",
    intro:
      "This notice describes the frontend demo posture visible in this repository. A deployed environment may add hosting or backend logs that are outside this frontend page.",
    sections: [
      {
        title: "Public browsing",
        body:
          "The public overview, limitation pages, and market exploration can be viewed without signing in. The frontend calls public backend endpoints to load market data when visitors enter the demo.",
      },
      {
        title: "Account features",
        body:
          "If Auth0 is configured and a visitor signs in, account screens may send app-owned profile, preference, saved artifact, recommendation snapshot, export, and deactivation requests to protected /me endpoints.",
      },
      {
        title: "No extra practices invented here",
        body:
          "This frontend does not define payment collection, advertising tracking, or a newsletter signup. Review the deployment and backend configuration for server logs, authentication provider records, and operational monitoring.",
      },
    ],
  },
  terms: {
    eyebrow: "Informational demo",
    title: "Terms and disclaimer",
    intro:
      "This is a public demo, not a production advisory service. Use it to understand the product concept and returned data shape.",
    sections: [
      {
        title: "No guarantee",
        body:
          "The demo is provided for informational review only. It does not guarantee accuracy, completeness, timeliness, availability, hiring outcomes, interviews, offers, compensation, or career results.",
      },
      {
        title: "No individualized advice",
        body:
          "The app may show derived scores or preference overlays, but those outputs are not individualized career, legal, financial, or employment advice.",
      },
      {
        title: "Verify independently",
        body:
          "Before making important job-market, relocation, application, or career decisions, verify facts with primary sources, current employer postings, public labor data, and qualified advisors where appropriate.",
      },
    ],
  },
  sources: {
    eyebrow: "Data provenance",
    title: "Source explanation",
    intro:
      "The app separates source records, prepared facts, derived outputs, metadata, and demo data so visitors can see what kind of evidence they are viewing.",
    sections: [
      {
        title: "Imported or source data",
        body:
          "Imported/source data is evidence collected from configured providers or seed inputs. Source labels may include provider names, source types, collection timestamps, and freshness state when returned by the API.",
      },
      {
        title: "Prepared canonical facts",
        body:
          "Prepared facts are normalized records the app uses for regions, companies, presence, hiring, entry-level signals, and related fields. They are still limited by the source data available to the demo.",
      },
      {
        title: "Derived scoring",
        body:
          "Derived scores and recommendations are computed from returned fields. They help compare visible records but should not be read as comprehensive market truth.",
      },
      {
        title: "Freshness and provenance metadata",
        body:
          "Freshness, warnings, source counts, and version metadata describe the evidence returned for a view when available. Unknown metadata means the frontend cannot prove recency from that response.",
      },
      {
        title: "Demo or seed data",
        body:
          "Seeded demo data may appear when real imports are absent or incomplete. It is useful for demonstrating behavior, not for proving live market conditions.",
      },
    ],
  },
};
