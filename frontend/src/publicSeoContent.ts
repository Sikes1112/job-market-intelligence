export type PublicSeoPageFamily =
  | "best_cities"
  | "city_comparison"
  | "city_market"
  | "role_market"
  | "methodology_linked";

export type PublicSeoConfidence = "high" | "medium" | "low" | "unknown";

export type PublicSeoLinkType = "report" | "benchmark" | "public_page" | "seo_page";

export type PublicSeoLink = {
  label: string;
  href: string;
  linkType: PublicSeoLinkType;
  slug?: string;
};

export type PublicSeoSection = {
  title: string;
  body: string;
  bullets?: string[];
};

export type PublicSeoMarketResult = {
  marketLabel: string;
  marketId?: string;
  resultType: "featured" | "ranked";
  rank?: number;
  headline: string;
  explanation: string;
  signals: string[];
};

export type PublicSeoComparisonMarket = {
  marketLabel: string;
  summary: string;
  bestFor: string[];
  tradeoffs: string[];
};

export type PublicSeoMetadata = {
  title: string;
  description: string;
  canonicalPath: string;
  topicTags: string[];
};

export type PublicSeoCitation = {
  sourceName: string;
  title: string;
  period: string;
  productAttribution: string;
  publicPath: string;
  accessedOrFreshnessDate: string;
};

export type PublicSeoShareSummary = {
  title: string;
  categoryClaim: string;
  confidenceLabel: string;
  freshnessLabel: string;
  takeaway: string;
  publicPath: string;
  warning: string;
};

export type PublicSeoSourceAuthority = {
  labels: string[];
  summary: string;
};

export type PublicSeoInstitutionalCta = {
  label: string;
  body: string;
  href: string;
  linkType: "public_page";
};

export type PublicSeoPage = {
  id: string;
  slug: string;
  routePath: string;
  title: string;
  pageFamily: PublicSeoPageFamily;
  summary: string;
  canonicalCategoryLanguage: string[];
  intendedSearchIntent: string;
  contentPeriod: string;
  freshnessDate: string;
  confidence: PublicSeoConfidence;
  methodologySummary: string;
  methodologyLink: PublicSeoLink;
  limitations: string[];
  warnings: string[];
  primarySections: PublicSeoSection[];
  featuredMarkets: PublicSeoMarketResult[];
  comparisonMarkets?: PublicSeoComparisonMarket[];
  bestFor?: string[];
  tradeoffs?: string[];
  relatedReports: PublicSeoLink[];
  relatedBenchmarks: PublicSeoLink[];
  relatedLinks: PublicSeoLink[];
  suggestedCitation: PublicSeoCitation;
  shareSummary: PublicSeoShareSummary;
  sourceAuthority: PublicSeoSourceAuthority;
  institutionalCta: PublicSeoInstitutionalCta;
  seo: PublicSeoMetadata;
};

export const REQUIRED_PUBLIC_SEO_SLUGS = [
  "best-cities-product-managers",
  "best-cities-ai-jobs",
  "best-cities-tech-internships",
  "nyc-vs-seattle-tech-careers",
  "austin-vs-atlanta-product-jobs",
  "atlanta-product-management-market",
  "seattle-ai-careers-market",
  "cybersecurity-entry-level-markets",
];

const METHODOLOGY_LINK: PublicSeoLink = {
  label: "Methodology foundation",
  href: "/methodology",
  linkType: "public_page",
};

const GLOSSARY_LINK: PublicSeoLink = {
  label: "Category glossary",
  href: "/glossary",
  linkType: "public_page",
};

const DATA_LIMITATIONS_LINK: PublicSeoLink = {
  label: "Data limitations",
  href: "/data-limitations",
  linkType: "public_page",
};

const REPORTS_LINK: PublicSeoLink = {
  label: "Market intelligence reports",
  href: "/reports",
  linkType: "public_page",
};

const BENCHMARKS_LINK: PublicSeoLink = {
  label: "Career market indices",
  href: "/benchmarks",
  linkType: "public_page",
};

const REPORT_LINKS = {
  ai: {
    label: "Best Cities for Early-Career AI Careers",
    href: "/reports/best-cities-early-career-ai-careers",
    linkType: "report",
    slug: "best-cities-early-career-ai-careers",
  },
  product: {
    label: "Top Product Management Markets",
    href: "/reports/top-product-management-markets",
    linkType: "report",
    slug: "top-product-management-markets",
  },
  hiddenHubs: {
    label: "Hidden Tech Hubs for New Graduates",
    href: "/reports/hidden-tech-hubs-new-graduates",
    linkType: "report",
    slug: "hidden-tech-hubs-new-graduates",
  },
} satisfies Record<string, PublicSeoLink>;

const BENCHMARK_LINKS = {
  earlyCareer: {
    label: "Early-Career Tech Access Index",
    href: "/benchmarks/early-career-tech-access-index",
    linkType: "benchmark",
    slug: "early-career-tech-access-index",
  },
  ai: {
    label: "AI Career Geography Index",
    href: "/benchmarks/ai-career-geography-index",
    linkType: "benchmark",
    slug: "ai-career-geography-index",
  },
  product: {
    label: "Product Career Market Index",
    href: "/benchmarks/product-career-market-index",
    linkType: "benchmark",
    slug: "product-career-market-index",
  },
} satisfies Record<string, PublicSeoLink>;

const CATEGORY_LANGUAGE = [
  "opportunity geography",
  "career market intelligence",
  "company-region presence",
  "early-career access",
  "market fit",
  "regional opportunity density",
  "career-market signal",
];

const DEMO_WARNINGS = [
  "This public guide is demo-safe, low-confidence category content and not a production ranking.",
  "Coverage, freshness, source evidence, and current hiring conditions must be verified before use.",
];

const COMMON_LIMITATIONS = [
  "This page does not claim exhaustive job-market coverage.",
  "Featured order is editorial/template order unless a linked public report or benchmark states otherwise.",
  "Missing market evidence means unknown, not absence of opportunity.",
  "This page is informational career market intelligence, not individualized career advice.",
];

const PRODUCT_ATTRIBUTION =
  "Opportunity Geography Intelligence / Career Market Intelligence";

const SOURCE_AUTHORITY: PublicSeoSourceAuthority = {
  labels: [
    "demo-safe",
    "low-confidence",
    "methodology-backed",
    "not production ranking truth",
    "Layer 19 public guide artifact",
  ],
  summary:
    "This guide is a public Layer 19 display artifact. It uses category language, methodology, limitations, freshness, confidence, and related public assets without creating production rankings or hidden scoring.",
};

const INSTITUTIONAL_CTA: PublicSeoInstitutionalCta = {
  label: "Explore institutional market intelligence",
  body:
    "Use this guide as directional context for advising, placement planning, and student-market conversations, then verify current coverage before decisions.",
  href: "/career-market-guides",
  linkType: "public_page",
};

function page(
  input: Omit<
    PublicSeoPage,
    | "id"
    | "canonicalCategoryLanguage"
    | "confidence"
    | "methodologyLink"
    | "warnings"
    | "suggestedCitation"
    | "shareSummary"
    | "sourceAuthority"
    | "institutionalCta"
  >,
): PublicSeoPage {
  return {
    ...input,
    id: `public_seo:${input.slug}`,
    canonicalCategoryLanguage: CATEGORY_LANGUAGE,
    confidence: "low",
    methodologyLink: METHODOLOGY_LINK,
    warnings: DEMO_WARNINGS,
    suggestedCitation: {
      sourceName: "Job Market Intelligence",
      title: input.title,
      period: input.contentPeriod,
      productAttribution: PRODUCT_ATTRIBUTION,
      publicPath: input.routePath,
      accessedOrFreshnessDate: input.freshnessDate,
    },
    shareSummary: {
      title: input.title,
      categoryClaim: pageFamilyClaim(input.pageFamily),
      confidenceLabel: "Low confidence",
      freshnessLabel: `Freshness unknown - ${input.freshnessDate}`,
      takeaway: input.summary,
      publicPath: input.routePath,
      warning: "Demo-safe public guide; not production ranking truth.",
    },
    sourceAuthority: SOURCE_AUTHORITY,
    institutionalCta: INSTITUTIONAL_CTA,
  };
}

function pageFamilyClaim(pageFamily: PublicSeoPageFamily): string {
  if (pageFamily === "best_cities") return "Public opportunity geography guide";
  if (pageFamily === "city_comparison") return "Public city comparison guide";
  if (pageFamily === "city_market") return "Public city career market guide";
  if (pageFamily === "role_market") return "Public role market guide";
  return "Public methodology-linked career market guide";
}

export const PUBLIC_SEO_PAGES: PublicSeoPage[] = [
  page({
    slug: "best-cities-product-managers",
    routePath: "/best-cities/best-cities-product-managers",
    title: "Best Cities for Product Managers",
    pageFamily: "best_cities",
    summary:
      "A public career market intelligence guide to product-management market fit, regional opportunity density, and company-region presence.",
    intendedSearchIntent:
      "Compare cities for product management careers without treating demo-safe content as a production ranking.",
    contentPeriod: "2026 methodology preview",
    freshnessDate: "2026-06-18",
    methodologySummary:
      "This guide links product-management report and benchmark artifacts, then explains featured markets with explicit low-confidence caveats.",
    limitations: COMMON_LIMITATIONS,
    primarySections: [
      {
        title: "What this page is measuring",
        body:
          "This page looks at product career-market signals: role-family breadth, company-region presence, early-career access, and market fit context.",
      },
    ],
    featuredMarkets: [
      {
        marketLabel: "NYC",
        marketId: "nyc",
        resultType: "featured",
        headline: "Cross-industry product market signal",
        explanation:
          "NYC is useful to inspect for product roles across finance, media, enterprise, consumer, and startup contexts. This is a featured example, not a production rank.",
        signals: ["company-region presence", "regional opportunity density", "market fit"],
      },
      {
        marketLabel: "Austin",
        marketId: "austin",
        resultType: "featured",
        headline: "Startup and product-market context",
        explanation:
          "Austin is useful to inspect where startup/product signals appear, with a clear distinction between durable presence and hiring noise.",
        signals: ["market fit", "career-market signal", "coverage caveat"],
      },
      {
        marketLabel: "Chicago",
        marketId: "chicago",
        resultType: "featured",
        headline: "Diversified enterprise product context",
        explanation:
          "Chicago is useful to inspect for diversified employer presence and enterprise product context, subject to current coverage checks.",
        signals: ["company-region presence", "sector mix", "early-career access"],
      },
    ],
    relatedReports: [REPORT_LINKS.product],
    relatedBenchmarks: [BENCHMARK_LINKS.product, BENCHMARK_LINKS.earlyCareer],
    relatedLinks: [GLOSSARY_LINK, METHODOLOGY_LINK, DATA_LIMITATIONS_LINK],
    seo: {
      title: "Best Cities for Product Managers | Job Market Intelligence",
      description:
        "Demo-safe career market intelligence guide to product management markets, methodology, limitations, and related public benchmarks.",
      canonicalPath: "/best-cities/best-cities-product-managers",
      topicTags: ["product management", "best cities", "career market intelligence"],
    },
  }),
  page({
    slug: "best-cities-ai-jobs",
    routePath: "/best-cities/best-cities-ai-jobs",
    title: "Best Cities for AI Jobs",
    pageFamily: "best_cities",
    summary:
      "A public opportunity geography guide to AI career-market signals, early-career access, and source-coverage caveats.",
    intendedSearchIntent:
      "Understand AI market examples while avoiding unsupported claims about current job availability.",
    contentPeriod: "2026 methodology preview",
    freshnessDate: "2026-06-18",
    methodologySummary:
      "This guide uses the AI public report and AI Career Geography Index as related explanation surfaces, not as hidden scoring authority.",
    limitations: COMMON_LIMITATIONS,
    primarySections: [
      {
        title: "What this page is measuring",
        body:
          "This page explains where AI career-market signals may deserve inspection: AI-adjacent employer presence, early-career access, source coverage, and market fit.",
      },
    ],
    featuredMarkets: [
      {
        marketLabel: "SF Bay Area",
        marketId: "sf_bay_area",
        resultType: "featured",
        headline: "Dense AI ecosystem with competition caveat",
        explanation:
          "SF Bay Area is a useful AI geography example, but high competition and current-source verification must stay visible.",
        signals: ["company-region presence", "AI career-market signal", "market fit caveat"],
      },
      {
        marketLabel: "Seattle",
        marketId: "seattle",
        resultType: "featured",
        headline: "Cloud and AI-adjacent market context",
        explanation:
          "Seattle is useful to inspect for cloud-adjacent AI roles and large-platform presence, subject to freshness checks.",
        signals: ["AI/cloud-adjacent signal", "regional opportunity density", "source freshness"],
      },
      {
        marketLabel: "Boston",
        marketId: "boston",
        resultType: "featured",
        headline: "Research and university-adjacent AI context",
        explanation:
          "Boston is useful to inspect for AI research, university pathways, and early-career access signals.",
        signals: ["early-career access", "research ecosystem", "company-region presence"],
      },
    ],
    relatedReports: [REPORT_LINKS.ai],
    relatedBenchmarks: [BENCHMARK_LINKS.ai, BENCHMARK_LINKS.earlyCareer],
    relatedLinks: [GLOSSARY_LINK, METHODOLOGY_LINK, DATA_LIMITATIONS_LINK],
    seo: {
      title: "Best Cities for AI Jobs | Job Market Intelligence",
      description:
        "Demo-safe opportunity geography guide to AI career markets, early-career access, methodology, and related public reports.",
      canonicalPath: "/best-cities/best-cities-ai-jobs",
      topicTags: ["AI jobs", "opportunity geography", "career market intelligence"],
    },
  }),
  page({
    slug: "best-cities-tech-internships",
    routePath: "/best-cities/best-cities-tech-internships",
    title: "Best Cities for Tech Internships",
    pageFamily: "best_cities",
    summary:
      "A public guide to early-career access and internship visibility across featured technology markets.",
    intendedSearchIntent:
      "Compare internship access examples while keeping demo-safe confidence and source limitations visible.",
    contentPeriod: "2026 methodology preview",
    freshnessDate: "2026-06-18",
    methodologySummary:
      "This guide links early-career access benchmark language and hidden-hub report context without creating a new internship score.",
    limitations: COMMON_LIMITATIONS,
    primarySections: [
      {
        title: "What this page is measuring",
        body:
          "This page focuses on early-career access, internship visibility, entry-level pathways, and the coverage limits around those signals.",
      },
    ],
    featuredMarkets: [
      {
        marketLabel: "Boston",
        marketId: "boston",
        resultType: "featured",
        headline: "University and research access context",
        explanation:
          "Boston is useful to inspect for internship and new-graduate pathways, but current employer evidence must be verified.",
        signals: ["early-career access", "company-region presence", "source freshness"],
      },
      {
        marketLabel: "Raleigh-Durham",
        marketId: "raleigh_durham",
        resultType: "featured",
        headline: "Research-triangle access context",
        explanation:
          "Raleigh-Durham is useful to inspect for university-adjacent access and employer presence signals.",
        signals: ["regional opportunity density", "early-career access", "coverage caveat"],
      },
      {
        marketLabel: "Seattle",
        marketId: "seattle",
        resultType: "featured",
        headline: "Large-platform internship context",
        explanation:
          "Seattle is useful to inspect for large-platform internship pathways and cloud-adjacent entry routes.",
        signals: ["company-region presence", "early-career access", "career-market signal"],
      },
    ],
    relatedReports: [REPORT_LINKS.hiddenHubs, REPORT_LINKS.ai],
    relatedBenchmarks: [BENCHMARK_LINKS.earlyCareer],
    relatedLinks: [GLOSSARY_LINK, METHODOLOGY_LINK, DATA_LIMITATIONS_LINK],
    seo: {
      title: "Best Cities for Tech Internships | Job Market Intelligence",
      description:
        "Demo-safe guide to tech internship access, early-career market signals, limitations, and related career-market benchmarks.",
      canonicalPath: "/best-cities/best-cities-tech-internships",
      topicTags: ["tech internships", "early-career access", "best cities"],
    },
  }),
  page({
    slug: "nyc-vs-seattle-tech-careers",
    routePath: "/compare/nyc-vs-seattle-tech-careers",
    title: "NYC vs Seattle for Tech Careers",
    pageFamily: "city_comparison",
    summary:
      "A city-vs-city career market intelligence guide comparing NYC and Seattle for technology career exploration.",
    intendedSearchIntent:
      "Compare NYC and Seattle tradeoffs without treating the page as a personalized recommendation.",
    contentPeriod: "2026 methodology preview",
    freshnessDate: "2026-06-18",
    methodologySummary:
      "This comparison uses public category language and related report/benchmark pages to structure tradeoffs. It does not compute a winner.",
    limitations: COMMON_LIMITATIONS,
    primarySections: [
      {
        title: "Comparison summary",
        body:
          "NYC and Seattle represent different opportunity geography patterns: NYC is broader across industries, while Seattle is more concentrated around cloud, large-platform, and AI-adjacent contexts.",
      },
    ],
    featuredMarkets: [],
    comparisonMarkets: [
      {
        marketLabel: "NYC",
        summary:
          "NYC may fit candidates who want broad sector exposure, product-adjacent paths, and dense cross-industry company-region presence.",
        bestFor: ["Cross-industry exploration", "Product and business-facing roles", "Dense network effects"],
        tradeoffs: ["High competition", "Sector breadth can make targeting harder"],
      },
      {
        marketLabel: "Seattle",
        summary:
          "Seattle may fit candidates who want cloud, large-platform, AI-adjacent, and infrastructure-oriented career-market signals.",
        bestFor: ["Cloud and platform contexts", "AI-adjacent career exploration", "Focused employer presence"],
        tradeoffs: ["Employer mix can be more concentrated", "Access varies by career stage"],
      },
    ],
    bestFor: [
      "NYC: candidates prioritizing cross-industry regional opportunity density.",
      "Seattle: candidates prioritizing cloud, platform, and AI-adjacent company-region presence.",
    ],
    tradeoffs: [
      "Neither market is universally best; market fit depends on role family, career stage, and current evidence.",
      "Current hiring should be checked directly with employers and source records.",
    ],
    relatedReports: [REPORT_LINKS.product, REPORT_LINKS.ai],
    relatedBenchmarks: [BENCHMARK_LINKS.product, BENCHMARK_LINKS.ai],
    relatedLinks: [GLOSSARY_LINK, METHODOLOGY_LINK, DATA_LIMITATIONS_LINK],
    seo: {
      title: "NYC vs Seattle Tech Careers | Job Market Intelligence",
      description:
        "Demo-safe city comparison for NYC and Seattle tech careers, including market fit, tradeoffs, methodology, and limitations.",
      canonicalPath: "/compare/nyc-vs-seattle-tech-careers",
      topicTags: ["NYC tech careers", "Seattle tech careers", "city comparison"],
    },
  }),
  page({
    slug: "austin-vs-atlanta-product-jobs",
    routePath: "/compare/austin-vs-atlanta-product-jobs",
    title: "Austin vs Atlanta for Product Jobs",
    pageFamily: "city_comparison",
    summary:
      "A product-career comparison guide for Austin and Atlanta, focused on market fit and company-region presence.",
    intendedSearchIntent:
      "Compare Austin and Atlanta for product roles with explicit low-confidence limitations.",
    contentPeriod: "2026 methodology preview",
    freshnessDate: "2026-06-18",
    methodologySummary:
      "This comparison structures public product-market language and related product benchmark/report pages without computing a winner.",
    limitations: COMMON_LIMITATIONS,
    primarySections: [
      {
        title: "Comparison summary",
        body:
          "Austin and Atlanta can represent different product-market paths: Austin for startup and software contexts, Atlanta for regional business, logistics, fintech, and diversified employer contexts.",
      },
    ],
    featuredMarkets: [],
    comparisonMarkets: [
      {
        marketLabel: "Austin",
        summary:
          "Austin may fit product candidates looking for software, startup, and growth-market context, subject to coverage checks.",
        bestFor: ["Startup product exploration", "Software product context", "Growth-market fit"],
        tradeoffs: ["Hiring noise can be hard to separate from durable presence"],
      },
      {
        marketLabel: "Atlanta",
        summary:
          "Atlanta may fit product candidates looking for regional enterprise, fintech, logistics, and diversified company-region presence.",
        bestFor: ["Enterprise product context", "Regional business networks", "Diversified market fit"],
        tradeoffs: ["Role-family visibility needs current source verification"],
      },
    ],
    bestFor: [
      "Austin: candidates prioritizing software and startup product-market context.",
      "Atlanta: candidates prioritizing diversified regional product-market context.",
    ],
    tradeoffs: [
      "Both markets require current employer and role-family verification.",
      "This comparison does not infer compensation, offer probability, or individualized fit.",
    ],
    relatedReports: [REPORT_LINKS.product],
    relatedBenchmarks: [BENCHMARK_LINKS.product],
    relatedLinks: [GLOSSARY_LINK, METHODOLOGY_LINK, DATA_LIMITATIONS_LINK],
    seo: {
      title: "Austin vs Atlanta Product Jobs | Job Market Intelligence",
      description:
        "Demo-safe product job market comparison for Austin and Atlanta, including tradeoffs, methodology, and related benchmarks.",
      canonicalPath: "/compare/austin-vs-atlanta-product-jobs",
      topicTags: ["Austin product jobs", "Atlanta product jobs", "product management"],
    },
  }),
  page({
    slug: "atlanta-product-management-market",
    routePath: "/career-markets/atlanta-product-management-market",
    title: "Atlanta Product Management Market",
    pageFamily: "city_market",
    summary:
      "A city career market page for Atlanta product-management exploration, company-region presence, and market fit context.",
    intendedSearchIntent:
      "Understand Atlanta product-management market context without unsupported rankings or production scores.",
    contentPeriod: "2026 methodology preview",
    freshnessDate: "2026-06-18",
    methodologySummary:
      "This page uses Layer 19 category language and related product report/benchmark pages to explain what to verify in Atlanta.",
    limitations: COMMON_LIMITATIONS,
    primarySections: [
      {
        title: "Market overview",
        body:
          "Atlanta is presented as a product-management market context page, not as a scored conclusion. The useful questions are employer mix, role-family visibility, early-career access, and sector fit.",
      },
      {
        title: "Career-market signals",
        body:
          "Relevant signals include company-region presence in regional enterprise categories, product role-family visibility, early-career access, and market fit for candidates seeking diversified business contexts.",
      },
    ],
    featuredMarkets: [
      {
        marketLabel: "Atlanta",
        marketId: "atlanta",
        resultType: "featured",
        headline: "Diversified regional product-market context",
        explanation:
          "Atlanta is framed as a market to inspect for company-region presence, regional opportunity density, and product role-family fit.",
        signals: ["company-region presence", "market fit", "career-market signal"],
      },
    ],
    relatedReports: [REPORT_LINKS.product],
    relatedBenchmarks: [BENCHMARK_LINKS.product],
    relatedLinks: [GLOSSARY_LINK, METHODOLOGY_LINK, DATA_LIMITATIONS_LINK],
    seo: {
      title: "Atlanta Product Management Market | Job Market Intelligence",
      description:
        "Demo-safe Atlanta product management market guide with career-market signals, limitations, methodology, and related benchmarks.",
      canonicalPath: "/career-markets/atlanta-product-management-market",
      topicTags: ["Atlanta product management", "career market intelligence", "market fit"],
    },
  }),
  page({
    slug: "seattle-ai-careers-market",
    routePath: "/career-markets/seattle-ai-careers-market",
    title: "Seattle AI Careers Market",
    pageFamily: "city_market",
    summary:
      "A city career market page for Seattle AI career exploration, cloud-adjacent signals, and early-career access caveats.",
    intendedSearchIntent:
      "Understand Seattle AI career-market context without claiming current hiring certainty.",
    contentPeriod: "2026 methodology preview",
    freshnessDate: "2026-06-18",
    methodologySummary:
      "This page links AI report and benchmark artifacts while keeping market coverage, freshness, and confidence caveats visible.",
    limitations: COMMON_LIMITATIONS,
    primarySections: [
      {
        title: "Market overview",
        body:
          "Seattle is presented as an AI career-market context page where cloud, platform, and AI-adjacent company-region presence may be relevant to inspect.",
      },
      {
        title: "Career-market signals",
        body:
          "Relevant signals include AI/cloud-adjacent employer presence, early-career access pathways, source freshness, and role-family fit.",
      },
    ],
    featuredMarkets: [
      {
        marketLabel: "Seattle",
        marketId: "seattle",
        resultType: "featured",
        headline: "Cloud and AI-adjacent geography",
        explanation:
          "Seattle is framed as a market to inspect for AI-adjacent company-region presence and early-career access signals.",
        signals: ["company-region presence", "AI career-market signal", "early-career access"],
      },
    ],
    relatedReports: [REPORT_LINKS.ai],
    relatedBenchmarks: [BENCHMARK_LINKS.ai, BENCHMARK_LINKS.earlyCareer],
    relatedLinks: [GLOSSARY_LINK, METHODOLOGY_LINK, DATA_LIMITATIONS_LINK],
    seo: {
      title: "Seattle AI Careers Market | Job Market Intelligence",
      description:
        "Demo-safe Seattle AI careers market guide with opportunity geography language, methodology, limitations, and related benchmarks.",
      canonicalPath: "/career-markets/seattle-ai-careers-market",
      topicTags: ["Seattle AI careers", "AI jobs", "opportunity geography"],
    },
  }),
  page({
    slug: "cybersecurity-entry-level-markets",
    routePath: "/roles/cybersecurity-entry-level-markets",
    title: "Cybersecurity Entry-Level Markets",
    pageFamily: "role_market",
    summary:
      "A role market guide for entry-level cybersecurity exploration across featured markets, with early-career access caveats.",
    intendedSearchIntent:
      "Understand entry-level cybersecurity market examples without unsupported city rankings.",
    contentPeriod: "2026 methodology preview",
    freshnessDate: "2026-06-18",
    methodologySummary:
      "This role page uses Layer 19 vocabulary and related early-career benchmark/report pages. It does not create a cybersecurity scoring model.",
    limitations: COMMON_LIMITATIONS,
    primarySections: [
      {
        title: "Role market overview",
        body:
          "Entry-level cybersecurity market fit depends on employer mix, security role-family visibility, early-career access, internships, apprenticeships, and current source evidence.",
      },
      {
        title: "Early-career access",
        body:
          "Early-career access should be checked through current employer postings, public training pathways, internships, entry-level roles, and source freshness.",
      },
    ],
    featuredMarkets: [
      {
        marketLabel: "NYC",
        marketId: "nyc",
        resultType: "featured",
        headline: "Cross-industry security context",
        explanation:
          "NYC is useful to inspect for security roles across finance, media, enterprise, and public-sector-adjacent contexts.",
        signals: ["regional opportunity density", "company-region presence", "career-market signal"],
      },
      {
        marketLabel: "Seattle",
        marketId: "seattle",
        resultType: "featured",
        headline: "Cloud and platform security context",
        explanation:
          "Seattle is useful to inspect for cloud, infrastructure, and platform security pathways.",
        signals: ["company-region presence", "early-career access", "market fit"],
      },
      {
        marketLabel: "Atlanta",
        marketId: "atlanta",
        resultType: "featured",
        headline: "Regional enterprise security context",
        explanation:
          "Atlanta is useful to inspect for diversified regional employers and entry-level security pathways.",
        signals: ["market fit", "early-career access", "coverage caveat"],
      },
    ],
    relatedReports: [REPORT_LINKS.hiddenHubs],
    relatedBenchmarks: [BENCHMARK_LINKS.earlyCareer],
    relatedLinks: [
      GLOSSARY_LINK,
      METHODOLOGY_LINK,
      DATA_LIMITATIONS_LINK,
      REPORTS_LINK,
      BENCHMARKS_LINK,
    ],
    seo: {
      title: "Cybersecurity Entry-Level Markets | Job Market Intelligence",
      description:
        "Demo-safe guide to entry-level cybersecurity markets, early-career access, methodology, limitations, and related public benchmarks.",
      canonicalPath: "/roles/cybersecurity-entry-level-markets",
      topicTags: ["cybersecurity entry-level", "early-career access", "role markets"],
    },
  }),
];

export function publicSeoPageUrl(page: PublicSeoPage): string {
  return page.routePath;
}

export function getPublicSeoPageBySlug(slug: string | undefined): PublicSeoPage | null {
  if (!slug) return null;
  return PUBLIC_SEO_PAGES.find((page) => page.slug === slug) ?? null;
}

export function relatedSeoPages(currentSlug?: string): PublicSeoLink[] {
  return PUBLIC_SEO_PAGES
    .filter((page) => page.slug !== currentSlug)
    .slice(0, 3)
    .map((page) => ({
      label: page.title,
      href: page.routePath,
      linkType: "seo_page",
      slug: page.slug,
    }));
}
