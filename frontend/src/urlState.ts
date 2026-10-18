import {
  geographicInputFromPath,
  geographicRouteToken,
  type GeographicRouteTarget,
} from "./geography";

export const DEFAULT_REGION_A = "greater_boston";
export const DEFAULT_REGION_B = "sf_bay_area";

export const ROLE_TARGETS = ["product", "ai_cloud_adjacent", "cybersecurity"];
export const INDUSTRY_OPTIONS = ["software", "ai", "cloud", "data", "cybersecurity"];
export const PREFERENCE_LEVELS = ["low", "medium", "high"];
export const CAREER_STAGE_OPTIONS = ["entry_level"];

export type ProductPage =
  | "dashboard"
  | "explore"
  | "my-search"
  | "profile"
  | "intelligence"
  | "region"
  | "company"
  | "compare"
  | "discovery"
  | "career-identity"
  | "decisions"
  | "recommendations"
  | "career-agent"
  | "opportunity-routes"
  | "current-opportunities"
  | "current-opportunity-operations"
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

export type MarketIntelligenceUrlState = {
  goal: string;
  marketKey?: string;
  compareA?: string;
  compareB?: string;
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
  opportunityId?: string;
  pursuitId?: string;
  applicationId?: string;
  savedComparisonId?: string;
  organizationId?: string;
  institutionView?: InstitutionView;
  comparison: ComparisonUrlState;
  discovery: DiscoveryFilters;
  intelligence: MarketIntelligenceUrlState;
  recommendationGoalMode: string;
  recommendationView: RecommendationView;
  explore: ExploreUrlState;
  currentOpportunities: CurrentOpportunityUrlState;
  unknownPath?: string;
};

export type RecommendationView = "for-you" | "by-goal";

export type ExploreUrlState = {
  query?: string;
  focus?: string;
  view: "map" | "list";
  selected: string[];
  goal?: string;
  opportunityTypes: string[];
  workArrangements: string[];
  geographicScope: string[];
  industries: string[];
};

export type CurrentOpportunityUrlState = {
  market?: string;
  roleFamily?: string;
  opportunityType?: string;
  workArrangement?: string;
  returnTo?: string;
};

export type ExploreGeographicIdentity = {
  region_id: string;
  public_slug: string | null;
  aliases?: string[];
};

export const EXPLORE_ROLE_OPTIONS = [
  ["software_engineering", "Software engineering"],
  ["product_management", "Product management"],
  ["ai_ml", "AI / machine learning"],
  ["cybersecurity", "Cybersecurity"],
  ["data_science", "Data science"],
] as const;

export function roleExploreValueForQuery(query: string): string | undefined {
  const normalized = query.trim().toLowerCase().replaceAll("-", " ").replaceAll("_", " ");
  return EXPLORE_ROLE_OPTIONS.find(([value, roleLabel]) =>
    value.replaceAll("_", " ") === normalized || roleLabel.toLowerCase() === normalized
  )?.[0];
}

export function canonicalizeExploreState(
  state: ExploreUrlState,
  identities: ExploreGeographicIdentity[],
): ExploreUrlState {
  const lookup = new Map<string, string>();
  for (const identity of identities) {
    const slug = identity.public_slug || identity.region_id;
    for (const token of [identity.region_id, identity.public_slug, ...(identity.aliases ?? [])]) {
      const normalized = token?.trim().toLowerCase();
      if (normalized) lookup.set(normalized, slug);
    }
  }
  const resolve = (token: string | undefined): string | undefined => {
    const normalized = token?.trim().toLowerCase();
    return normalized ? lookup.get(normalized) : undefined;
  };
  const resolvedSelected = unique(state.selected.flatMap((token) => {
    const slug = resolve(token);
    return slug ? [slug] : [];
  })).slice(0, 4);
  const resolvedGeography = unique(state.geographicScope.flatMap((token) => {
    const slug = resolve(token);
    return slug ? [slug] : [];
  }));
  return {
    ...state,
    focus: resolve(state.focus),
    selected: resolvedSelected,
    geographicScope: resolvedGeography,
  };
}

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
  "dashboard",
  "explore",
  "my-search",
  "profile",
  "intelligence",
  "region",
  "company",
  "compare",
  "discovery",
  "career-identity",
  "decisions",
  "recommendations",
  "career-agent",
  "opportunity-routes",
  "current-opportunities",
  "current-opportunity-operations",
  "policy",
  "plans",
  "institution",
  "account",
];
const DEFAULT_RECOMMENDATION_GOAL_MODE = "maximize_entry_level_access";
const DEFAULT_MARKET_INTELLIGENCE_GOAL = "software_engineering";

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
  return unique(parseRawListParam(params, key, fallback, allowedValues));
}

function parseRawListParam(
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

  return values;
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

function parseMarketIntelligence(params: URLSearchParams): MarketIntelligenceUrlState {
  return {
    goal: cleanToken(params.get("goal")) ?? DEFAULT_MARKET_INTELLIGENCE_GOAL,
    marketKey: cleanToken(params.get("market")),
    compareA: cleanToken(params.get("compare_a") ?? params.get("a")),
    compareB: cleanToken(params.get("compare_b") ?? params.get("b")),
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
    | "opportunityId"
    | "pursuitId"
    | "applicationId"
    | "savedComparisonId"
    | "organizationId"
    | "institutionView"
    | "unknownPath"
  >,
): RouteState {
  return {
    page,
    comparison: parseComparison(params),
    discovery: parseDiscovery(params),
    intelligence: parseMarketIntelligence(params),
    recommendationGoalMode: cleanToken(params.get("goal")) ?? DEFAULT_RECOMMENDATION_GOAL_MODE,
    recommendationView: params.get("mode") === "for-you" ? "for-you" : "by-goal",
    explore: parseExploreState(params),
    currentOpportunities: parseCurrentOpportunityState(params),
    ...extra,
  };
}

function parseCurrentOpportunityState(params: URLSearchParams): CurrentOpportunityUrlState {
  const returnTo = cleanToken(params.get("return"));
  return {
    market: cleanToken(params.get("market")),
    roleFamily: cleanToken(params.get("role")),
    opportunityType: cleanToken(params.get("opportunity_type") ?? params.get("opportunity")),
    workArrangement: cleanToken(params.get("work_arrangement") ?? params.get("work")),
    returnTo: returnTo?.startsWith("/markets") ? returnTo : undefined,
  };
}

function parseExploreState(params: URLSearchParams): ExploreUrlState {
  const view = params.get("view") === "map" ? "map" : "list";
  return {
    query: cleanToken(params.get("q")),
    focus: cleanToken(params.get("focus")),
    view,
    selected: parseRawListParam(params, "selected", []),
    goal: cleanToken(params.get("role") ?? params.get("goal")),
    opportunityTypes: parseListParam(params, "opportunity", []),
    workArrangements: parseListParam(params, "work", []),
    geographicScope: parseListParam(params, "geography", []),
    industries: parseListParam(params, "industry", []),
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
    return baseRoute("region", params, {
      regionId: geographicInputFromPath(segments[2]),
    });
  }

  if (section === "company") {
    return baseRoute("company", params, { companyId: cleanToken(segments[2]) });
  }

  if (section === "compare") return baseRoute("compare", params);
  if (section === "comparisons" && segments[2]) {
    return baseRoute("compare", params, {
      savedComparisonId: cleanToken(segments[2]),
    });
  }
  if (section === "my-search") {
    if (segments[2] === "pursuits" && segments[3]) {
      return baseRoute("my-search", params, { pursuitId: cleanToken(segments[3]) });
    }
    if (segments[2] === "applications" && segments[3]) {
      return baseRoute("my-search", params, { applicationId: cleanToken(segments[3]) });
    }
    return baseRoute("my-search", params);
  }
  if (section === "dashboard") {
    return baseRoute("dashboard", params);
  }
  if (section === "intelligence") return baseRoute("intelligence", params);
  if (section === "discovery") return baseRoute("discovery", params);
  if (section === "career-identity") return baseRoute("career-identity", params);
  if (section === "profile") return baseRoute("profile", params);
  if (section === "decisions" || section === "decision-workspace") {
    return baseRoute("decisions", params);
  }
  if (section === "recommendations") return baseRoute("recommendations", params);
  if (section === "career-agent" || section === "agent") {
    return baseRoute("career-agent", params);
  }
  if (section === "opportunity-routes" || section === "routes") {
    return baseRoute("opportunity-routes", params);
  }
  if (section === "current-opportunities" || section === "opportunities") {
    if (segments[2] === "operations") {
      return baseRoute("current-opportunity-operations", params);
    }
    if (segments[2]) {
      return baseRoute("current-opportunities", params, {
        opportunityId: cleanToken(segments[2]),
      });
    }
    return baseRoute("current-opportunities", params);
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

function exploreStateParams(state?: Partial<ExploreUrlState>): URLSearchParams {
  const params = new URLSearchParams();
  if (state?.query) params.set("q", state.query);
  if (state?.focus) params.set("focus", state.focus);
  if (state?.view === "map") params.set("view", "map");
  if (state?.selected?.length) params.set("selected", unique(state.selected).slice(0, 4).join(","));
  if (state?.goal) params.set("role", state.goal);
  if (state?.opportunityTypes?.length) params.set("opportunity", unique(state.opportunityTypes).join(","));
  if (state?.workArrangements?.length) params.set("work", unique(state.workArrangements).join(","));
  if (state?.geographicScope?.length) params.set("geography", unique(state.geographicScope).join(","));
  if (state?.industries?.length) params.set("industry", unique(state.industries).join(","));
  return params;
}

export function exploreUrl(state?: Partial<ExploreUrlState>): string {
  const query = exploreStateParams(state).toString();
  return `${PRODUCT_ROOT}${query ? `?${query}` : ""}`;
}

export function exploreComparisonUrl(state: Partial<ExploreUrlState>): string {
  const query = exploreStateParams(state).toString();
  return `${PRODUCT_ROOT}/compare${query ? `?${query}` : ""}`;
}

export function savedExploreComparisonUrl(comparisonId: string): string {
  return `${PRODUCT_ROOT}/comparisons/${encodePathValue(comparisonId)}`;
}

export function mySearchUrl(): string {
  return `${PRODUCT_ROOT}/my-search`;
}

export function mySearchPursuitUrl(decisionId: string): string {
  return `${PRODUCT_ROOT}/my-search/pursuits/${encodePathValue(decisionId)}`;
}

export function mySearchApplicationUrl(applicationId: string): string {
  return `${PRODUCT_ROOT}/my-search/applications/${encodePathValue(applicationId)}`;
}

export function profileUrl(): string {
  return `${PRODUCT_ROOT}/profile`;
}

export function userIntelligenceDashboardUrl(): string {
  return `${PRODUCT_ROOT}/dashboard`;
}

export function marketIntelligenceUrl(state?: Partial<MarketIntelligenceUrlState>): string {
  const params = new URLSearchParams();
  if (state?.goal) params.set("goal", state.goal);
  if (state?.marketKey) params.set("market", state.marketKey);
  if (state?.compareA) params.set("compare_a", state.compareA);
  if (state?.compareB) params.set("compare_b", state.compareB);
  const query = params.toString();
  return `${PRODUCT_ROOT}/intelligence${query ? `?${query}` : ""}`;
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

export function regionDetailUrl(region?: GeographicRouteTarget): string {
  return region
    ? `${PRODUCT_ROOT}/region/${encodePathValue(geographicRouteToken(region))}`
    : `${PRODUCT_ROOT}/region`;
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

export function careerIdentityUrl(): string {
  return `${PRODUCT_ROOT}/career-identity`;
}

export function decisionsUrl(decisionId?: string): string {
  if (!decisionId) return `${PRODUCT_ROOT}/decisions`;
  return `${PRODUCT_ROOT}/decisions?decision=${encodeURIComponent(decisionId)}`;
}

export function recommendationsUrl(
  goalMode = DEFAULT_RECOMMENDATION_GOAL_MODE,
  view: RecommendationView = "for-you",
): string {
  const params = new URLSearchParams({ goal: goalMode, mode: view });
  return `${PRODUCT_ROOT}/recommendations?${params.toString()}`;
}

export function careerAgentUrl(): string {
  return `${PRODUCT_ROOT}/career-agent`;
}

export function opportunityRoutesUrl(): string {
  return `${PRODUCT_ROOT}/opportunity-routes`;
}

export function currentOpportunitiesUrl(state?: CurrentOpportunityUrlState): string {
  const params = new URLSearchParams();
  if (state?.market) params.set("market", state.market);
  if (state?.roleFamily) params.set("role", state.roleFamily);
  if (state?.opportunityType) params.set("opportunity_type", state.opportunityType);
  if (state?.workArrangement) params.set("work_arrangement", state.workArrangement);
  if (state?.returnTo?.startsWith("/markets")) params.set("return", state.returnTo);
  const query = params.toString();
  return `${PRODUCT_ROOT}/current-opportunities${query ? `?${query}` : ""}`;
}

export function currentOpportunityDetailUrl(opportunityId: string): string {
  return `${PRODUCT_ROOT}/current-opportunities/${encodePathValue(opportunityId)}`;
}

export function currentOpportunityOperationsUrl(): string {
  return `${PRODUCT_ROOT}/current-opportunities/operations`;
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
