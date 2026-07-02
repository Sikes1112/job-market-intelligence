export const DEFAULT_REGION_A = "greater_boston";
export const DEFAULT_REGION_B = "greater_sf";

export const ROLE_TARGETS = ["product", "ai_cloud_adjacent", "cybersecurity"];
export const INDUSTRY_OPTIONS = ["software", "ai", "cloud", "data", "cybersecurity"];
export const PREFERENCE_LEVELS = ["low", "medium", "high"];
export const CAREER_STAGE_OPTIONS = ["entry_level"];

export type ProductPage =
  | "explore"
  | "region"
  | "company"
  | "compare"
  | "discovery"
  | "recommendations"
  | "career-agent"
  | "opportunity-routes"
  | "policy"
  | "plans"
  | "institution"
  | "account";
export type PublicPage =
  | "landing"
  | "benchmarks"
  | "data-standards"
  | "data-licensing"
  | "developers"
  | "developer-docs"
  | "developer-doc-authentication"
  | "developer-doc-errors"
  | "developer-doc-rate-limits"
  | "developer-doc-freshness-confidence"
  | "developer-doc-region-scores"
  | "developer-doc-company-geography"
  | "developer-doc-early-career-access"
  | "developer-doc-hiring-concentration"
  | "developer-doc-market-comparisons"
  | "embed-region-comparison"
  | "embed-market-score-card"
  | "guides"
  | "forecasts"
  | "reports"
  | "glossary"
  | "methodology"
  | "data-limitations"
  | "privacy"
  | "terms"
  | "sources";
export type AppPage = ProductPage | PublicPage;
export type InstitutionView =
  | "dashboard"
  | "decisions"
  | "advisor"
  | "reports"
  | "data-requests"
  | "imports";
export type PolicyView =
  | "landing"
  | "workforce"
  | "economic-development"
  | "education-alignment"
  | "peer-comparison"
  | "report";

export type ComparisonUrlState = {
  regionA: string;
  regionB: string;
};

export type DiscoveryFilters = {
  selectedRegions: string[];
  roleTargets: string[];
  industries: string[];
  careerStage: string;
  prestigePreference: string;
  brandPreference: string;
  limit: number;
};

export type RouteState = {
  page: AppPage;
  regionId?: string;
  companyId?: string;
  benchmarkSlug?: string;
  reportSlug?: string;
  seoPageSlug?: string;
  policyView?: PolicyView;
  policyReportId?: string;
  organizationId?: string;
  institutionView?: InstitutionView;
  comparison: ComparisonUrlState;
  discovery: DiscoveryFilters;
  recommendationGoalMode: string;
  unknownPath?: string;
};

export const DEFAULT_DISCOVERY_FILTERS: DiscoveryFilters = {
  selectedRegions: [DEFAULT_REGION_A, DEFAULT_REGION_B],
  roleTargets: ROLE_TARGETS,
  industries: ["software", "ai", "cloud"],
  careerStage: "entry_level",
  prestigePreference: "medium",
  brandPreference: "medium",
  limit: 10,
};

const PRODUCT_ROOT = "/markets";

export const PUBLIC_PAGE_PATHS: Record<Exclude<PublicPage, "landing">, string> = {
  benchmarks: "/benchmarks",
  "data-standards": "/data-standards",
  "data-licensing": "/data-licensing",
  developers: "/developers",
  "developer-docs": "/developers/docs",
  "developer-doc-authentication": "/developers/docs/authentication",
  "developer-doc-errors": "/developers/docs/errors",
  "developer-doc-rate-limits": "/developers/docs/rate-limits",
  "developer-doc-freshness-confidence": "/developers/docs/freshness-confidence",
  "developer-doc-region-scores": "/developers/docs/region-scores",
  "developer-doc-company-geography": "/developers/docs/company-geography",
  "developer-doc-early-career-access": "/developers/docs/early-career-access",
  "developer-doc-hiring-concentration": "/developers/docs/hiring-concentration",
  "developer-doc-market-comparisons": "/developers/docs/market-comparisons",
  "embed-region-comparison": "/embed/region-comparison",
  "embed-market-score-card": "/embed/market-score-card",
  guides: "/career-market-guides",
  forecasts: "/forecasts",
  reports: "/reports",
  glossary: "/glossary",
  methodology: "/methodology",
  "data-limitations": "/data-limitations",
  privacy: "/privacy",
  terms: "/terms",
  sources: "/sources",
};

const PRODUCT_PAGES: ProductPage[] = [
  "explore",
  "region",
  "company",
  "compare",
  "discovery",
  "recommendations",
  "career-agent",
  "opportunity-routes",
  "policy",
  "plans",
  "institution",
  "account",
];
const DEFAULT_RECOMMENDATION_GOAL_MODE = "maximize_entry_level_access";

export function isProductPage(page: AppPage): page is ProductPage {
  return PRODUCT_PAGES.includes(page as ProductPage);
}

function safeDecodeSegment(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return "";
  }
}

function cleanToken(value: string | null | undefined): string | undefined {
  const trimmed = value?.trim();
  return trimmed ? trimmed : undefined;
}

function unique(values: string[]): string[] {
  return Array.from(new Set(values));
}

function parseListParam(
  params: URLSearchParams,
  key: string,
  fallback: string[],
  allowedValues?: readonly string[],
): string[] {
  if (!params.has(key)) return [...fallback];

  const allowed = allowedValues ? new Set(allowedValues) : null;
  const values = params
    .getAll(key)
    .flatMap((rawValue) => rawValue.split(","))
    .map((value) => value.trim())
    .filter((value) => value.length > 0)
    .filter((value) => !allowed || allowed.has(value));

  return unique(values);
}

function parsePreference(
  params: URLSearchParams,
  key: string,
  fallback: string,
): string {
  const value = cleanToken(params.get(key));
  return value && PREFERENCE_LEVELS.includes(value) ? value : fallback;
}

function parseCareerStage(params: URLSearchParams): string {
  const value = cleanToken(params.get("career") ?? params.get("career_stage"));
  return value && CAREER_STAGE_OPTIONS.includes(value)
    ? value
    : DEFAULT_DISCOVERY_FILTERS.careerStage;
}

function parseLimit(params: URLSearchParams): number {
  const rawValue = Number(params.get("limit"));
  if (!Number.isFinite(rawValue)) return DEFAULT_DISCOVERY_FILTERS.limit;
  return Math.max(1, Math.min(25, Math.trunc(rawValue)));
}

function parseComparison(params: URLSearchParams): ComparisonUrlState {
  return {
    regionA: cleanToken(params.get("region_a") ?? params.get("a")) ?? DEFAULT_REGION_A,
    regionB: cleanToken(params.get("region_b") ?? params.get("b")) ?? DEFAULT_REGION_B,
  };
}

function parseDiscovery(params: URLSearchParams): DiscoveryFilters {
  return {
    selectedRegions: parseListParam(
      params,
      "regions",
      DEFAULT_DISCOVERY_FILTERS.selectedRegions,
    ),
    roleTargets: parseListParam(
      params,
      "roles",
      DEFAULT_DISCOVERY_FILTERS.roleTargets,
      ROLE_TARGETS,
    ),
    industries: parseListParam(
      params,
      "industries",
      DEFAULT_DISCOVERY_FILTERS.industries,
      INDUSTRY_OPTIONS,
    ),
    careerStage: parseCareerStage(params),
    prestigePreference: parsePreference(
      params,
      "prestige",
      DEFAULT_DISCOVERY_FILTERS.prestigePreference,
    ),
    brandPreference: parsePreference(
      params,
      "brand",
      DEFAULT_DISCOVERY_FILTERS.brandPreference,
    ),
    limit: parseLimit(params),
  };
}

function baseRoute(
  page: AppPage,
  params: URLSearchParams,
  extra?: Pick<
    RouteState,
    | "regionId"
    | "companyId"
    | "benchmarkSlug"
    | "reportSlug"
    | "seoPageSlug"
    | "policyView"
    | "policyReportId"
    | "organizationId"
    | "institutionView"
    | "unknownPath"
  >,
): RouteState {
  return {
    page,
    comparison: parseComparison(params),
    discovery: parseDiscovery(params),
    recommendationGoalMode: cleanToken(params.get("goal")) ?? DEFAULT_RECOMMENDATION_GOAL_MODE,
    ...extra,
  };
}

export function parseRoute(pathname: string, search: string): RouteState {
  const params = new URLSearchParams(search);
  const segments = pathname.split("/").filter(Boolean).map(safeDecodeSegment);

  if (!segments.length) {
    return baseRoute("landing", params);
  }

  if (segments.length === 1) {
    const publicPage = Object.entries(PUBLIC_PAGE_PATHS).find(
      ([, path]) => path === `/${segments[0]}`,
    )?.[0] as Exclude<PublicPage, "landing"> | undefined;
    if (publicPage) return baseRoute(publicPage, params);
  }

  if (segments[0] === "benchmarks") {
    if (segments.length === 1) return baseRoute("benchmarks", params);
    if (segments.length === 2) {
      return baseRoute("benchmarks", params, { benchmarkSlug: cleanToken(segments[1]) });
    }
  }

  if (segments[0] === "reports") {
    if (segments.length === 1) return baseRoute("reports", params);
    if (segments.length === 2) {
      return baseRoute("reports", params, { reportSlug: cleanToken(segments[1]) });
    }
  }

  if (segments[0] === "career-market-guides" && segments.length === 1) {
    return baseRoute("guides", params);
  }

  if (segments[0] === "developers") {
    if (segments.length === 1) return baseRoute("developers", params);
    if (segments[1] === "docs") {
      const docRoute = developerDocRoute(segments[2]);
      return baseRoute(docRoute, params);
    }
  }

  if (segments[0] === "embed") {
    if (segments[1] === "region-comparison") {
      return baseRoute("embed-region-comparison", params);
    }
    if (segments[1] === "market-score-card") {
      return baseRoute("embed-market-score-card", params);
    }
  }

  if (["best-cities", "compare", "career-markets", "roles"].includes(segments[0])) {
    if (segments.length === 2) {
      return baseRoute("guides", params, { seoPageSlug: cleanToken(segments[1]) });
    }
  }

  if (segments[0] !== "markets") {
    return baseRoute("landing", params, { unknownPath: pathname });
  }

  const section = segments[1];
  if (!section) return baseRoute("explore", params);

  if (section === "region") {
    return baseRoute("region", params, { regionId: cleanToken(segments[2]) });
  }

  if (section === "company") {
    return baseRoute("company", params, { companyId: cleanToken(segments[2]) });
  }

  if (section === "compare") return baseRoute("compare", params);
  if (section === "discovery") return baseRoute("discovery", params);
  if (section === "recommendations") return baseRoute("recommendations", params);
  if (section === "career-agent" || section === "agent") {
    return baseRoute("career-agent", params);
  }
  if (section === "opportunity-routes" || section === "routes") {
    return baseRoute("opportunity-routes", params);
  }
  if (section === "policy") {
    if (segments[2] === "regions") {
      const regionId = cleanToken(segments[3]);
      const view = policyViewForSegment(segments[4]);
      return baseRoute("policy", params, {
        policyView: view,
        regionId,
      });
    }
    if (segments[2] === "reports") {
      return baseRoute("policy", params, {
        policyView: "report",
        regionId: cleanToken(segments[3]),
        policyReportId: cleanToken(segments[4]) ?? "early-career-opportunity",
      });
    }
    return baseRoute("policy", params, { policyView: "landing" });
  }
  if (section === "plans" || section === "pricing") return baseRoute("plans", params);
  if (section === "institution") {
    if (segments[2] === "decisions") {
      return baseRoute("institution", params, {
        institutionView: "decisions",
        organizationId: cleanToken(segments[3]),
      });
    }
    if (segments[2] === "advisor") {
      return baseRoute("institution", params, {
        institutionView: "advisor",
        organizationId: cleanToken(segments[3]),
      });
    }
    if (segments[2] === "reports") {
      return baseRoute("institution", params, {
        institutionView: "reports",
        organizationId: cleanToken(segments[3]),
      });
    }
    if (segments[2] === "data-requests") {
      return baseRoute("institution", params, {
        institutionView: "data-requests",
        organizationId: cleanToken(segments[3]),
      });
    }
    if (segments[2] === "imports") {
      return baseRoute("institution", params, {
        institutionView: "imports",
        organizationId: cleanToken(segments[3]),
      });
    }
    return baseRoute("institution", params, {
      institutionView: "dashboard",
      organizationId: cleanToken(segments[2]),
    });
  }
  if (section === "account") return baseRoute("account", params);

  return baseRoute("explore", params, { unknownPath: pathname });
}

function encodePathValue(value: string): string {
  return encodeURIComponent(value.trim());
}

function appendListParam(params: URLSearchParams, key: string, values: string[]) {
  params.set(key, unique(values).join(","));
}

export function exploreUrl(): string {
  return PRODUCT_ROOT;
}

export function landingUrl(): string {
  return "/";
}

export function publicPageUrl(page: Exclude<PublicPage, "landing">): string {
  return PUBLIC_PAGE_PATHS[page];
}

function developerDocRoute(slug: string | undefined): PublicPage {
  if (slug === "authentication") return "developer-doc-authentication";
  if (slug === "errors") return "developer-doc-errors";
  if (slug === "rate-limits") return "developer-doc-rate-limits";
  if (slug === "freshness-confidence") return "developer-doc-freshness-confidence";
  if (slug === "region-scores") return "developer-doc-region-scores";
  if (slug === "company-geography") return "developer-doc-company-geography";
  if (slug === "early-career-access") return "developer-doc-early-career-access";
  if (slug === "hiring-concentration") return "developer-doc-hiring-concentration";
  if (slug === "market-comparisons") return "developer-doc-market-comparisons";
  return "developer-docs";
}

export function publicReportUrl(slug: string): string {
  return `${PUBLIC_PAGE_PATHS.reports}/${encodePathValue(slug)}`;
}

export function publicBenchmarkUrl(slug: string): string {
  return `${PUBLIC_PAGE_PATHS.benchmarks}/${encodePathValue(slug)}`;
}

export function regionDetailUrl(regionId?: string): string {
  return regionId ? `${PRODUCT_ROOT}/region/${encodePathValue(regionId)}` : `${PRODUCT_ROOT}/region`;
}

export function companyGeographyUrl(companyId?: string): string {
  return companyId ? `${PRODUCT_ROOT}/company/${encodePathValue(companyId)}` : `${PRODUCT_ROOT}/company`;
}

export function compareMarketsUrl(regionA: string, regionB: string): string {
  const params = new URLSearchParams({ region_a: regionA, region_b: regionB });
  return `${PRODUCT_ROOT}/compare?${params.toString()}`;
}

export function personalizedDiscoveryUrl(filters: DiscoveryFilters): string {
  const params = new URLSearchParams();
  appendListParam(params, "regions", filters.selectedRegions);
  appendListParam(params, "roles", filters.roleTargets);
  appendListParam(params, "industries", filters.industries);
  params.set("career", filters.careerStage);
  params.set("prestige", filters.prestigePreference);
  params.set("brand", filters.brandPreference);
  params.set("limit", String(filters.limit));
  return `${PRODUCT_ROOT}/discovery?${params.toString()}`;
}

export function recommendationsUrl(goalMode = DEFAULT_RECOMMENDATION_GOAL_MODE): string {
  const params = new URLSearchParams({ goal: goalMode });
  return `${PRODUCT_ROOT}/recommendations?${params.toString()}`;
}

export function careerAgentUrl(): string {
  return `${PRODUCT_ROOT}/career-agent`;
}

export function opportunityRoutesUrl(): string {
  return `${PRODUCT_ROOT}/opportunity-routes`;
}

export function policyLandingUrl(): string {
  return `${PRODUCT_ROOT}/policy`;
}

export function policyRegionUrl(regionId?: string): string {
  return regionId
    ? `${PRODUCT_ROOT}/policy/regions/${encodePathValue(regionId)}/workforce`
    : `${PRODUCT_ROOT}/policy`;
}

export function policyEconomicDevelopmentUrl(regionId?: string): string {
  return regionId
    ? `${PRODUCT_ROOT}/policy/regions/${encodePathValue(regionId)}/economic-development`
    : `${PRODUCT_ROOT}/policy`;
}

export function policyEducationAlignmentUrl(regionId?: string): string {
  return regionId
    ? `${PRODUCT_ROOT}/policy/regions/${encodePathValue(regionId)}/education-alignment`
    : `${PRODUCT_ROOT}/policy`;
}

export function policyPeerComparisonUrl(regionId?: string): string {
  return regionId
    ? `${PRODUCT_ROOT}/policy/regions/${encodePathValue(regionId)}/peer-comparison`
    : `${PRODUCT_ROOT}/policy`;
}

export function policyReportUrl(
  regionId?: string,
  reportId = "early-career-opportunity",
): string {
  return regionId
    ? `${PRODUCT_ROOT}/policy/reports/${encodePathValue(regionId)}/${encodePathValue(reportId)}`
    : `${PRODUCT_ROOT}/policy`;
}

export function plansUrl(): string {
  return `${PRODUCT_ROOT}/plans`;
}

function policyViewForSegment(segment: string | undefined): PolicyView {
  if (segment === "economic-development") return "economic-development";
  if (segment === "education-alignment") return "education-alignment";
  if (segment === "peer-comparison") return "peer-comparison";
  return "workforce";
}

export function institutionDashboardUrl(organizationId?: string): string {
  return organizationId
    ? `${PRODUCT_ROOT}/institution/${encodePathValue(organizationId)}`
    : `${PRODUCT_ROOT}/institution`;
}

export function institutionAdvisorUrl(organizationId?: string): string {
  return organizationId
    ? `${PRODUCT_ROOT}/institution/advisor/${encodePathValue(organizationId)}`
    : `${PRODUCT_ROOT}/institution/advisor`;
}

export function institutionDecisionsUrl(organizationId?: string): string {
  return organizationId
    ? `${PRODUCT_ROOT}/institution/decisions/${encodePathValue(organizationId)}`
    : `${PRODUCT_ROOT}/institution/decisions`;
}

export function institutionReportsUrl(organizationId?: string): string {
  return organizationId
    ? `${PRODUCT_ROOT}/institution/reports/${encodePathValue(organizationId)}`
    : `${PRODUCT_ROOT}/institution/reports`;
}

export function institutionDataRequestsUrl(organizationId?: string): string {
  return organizationId
    ? `${PRODUCT_ROOT}/institution/data-requests/${encodePathValue(organizationId)}`
    : `${PRODUCT_ROOT}/institution/data-requests`;
}

export function institutionImportsUrl(organizationId?: string): string {
  return organizationId
    ? `${PRODUCT_ROOT}/institution/imports/${encodePathValue(organizationId)}`
    : `${PRODUCT_ROOT}/institution/imports`;
}

export function accountUrl(): string {
  return `${PRODUCT_ROOT}/account`;
}
