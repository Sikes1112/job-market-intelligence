import { PUBLIC_PAGE_PATHS, type PublicPage } from "./urlState";

export type LegalPublicPage = Exclude<PublicPage, "landing">;

export type PublicInfoLink = {
  page: LegalPublicPage;
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
  { page: "data-limitations", href: PUBLIC_PAGE_PATHS["data-limitations"], label: "Data limitations" },
  { page: "privacy", href: PUBLIC_PAGE_PATHS.privacy, label: "Privacy" },
  { page: "terms", href: PUBLIC_PAGE_PATHS.terms, label: "Terms and disclaimer" },
  { page: "sources", href: PUBLIC_PAGE_PATHS.sources, label: "Source explanation" },
];

export const DEMO_DISCLOSURE_COPY = {
  title: "Public demo disclosure",
  summary:
    "This demo may combine seeded demo data with real imported records. Coverage is partial; data can be incomplete, stale, or missing. Derived scores are directional signals, not absolute truth or individualized career advice.",
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
    "A demo interface for inspecting prepared regional job-market facts, company presence and hiring signals, source freshness, and derived opportunity scores.",
  ctaLabel: "Enter demo",
  secondaryCtaLabel: "Review data limitations",
  sections: [
    {
      title: "What it does",
      body:
        "The app organizes returned market outputs so visitors can explore regions, inspect company geography, compare regional score fields, and run a request-scoped discovery overlay.",
    },
    {
      title: "Who it is for",
      body:
        "It is intended for reviewers, builders, and early users who want to understand the shape of the demo and the data-quality signals behind it.",
    },
    {
      title: "What data it uses",
      body:
        "Views can include imported source records, prepared canonical facts, derived scoring outputs, freshness and provenance metadata, and seeded demo records where a full import is not present.",
    },
    {
      title: "Current limits",
      body:
        "The demo does not claim comprehensive job-market coverage, real-time completeness, or individualized career advice. Important decisions should be checked against independent sources.",
    },
  ],
};

export const LEGAL_PAGE_COPY: Record<LegalPublicPage, LegalPageCopy> = {
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
