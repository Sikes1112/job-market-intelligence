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
  | "plans"
  | "institution"
  | "account";
export type PublicPage = "landing" | "data-limitations" | "privacy" | "terms" | "sources";
export type AppPage = ProductPage | PublicPage;
export type InstitutionView = "dashboard" | "advisor" | "reports" | "data-requests";

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
    "regionId" | "companyId" | "organizationId" | "institutionView" | "unknownPath"
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
  if (section === "plans" || section === "pricing") return baseRoute("plans", params);
  if (section === "institution") {
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

export function plansUrl(): string {
  return `${PRODUCT_ROOT}/plans`;
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

export function accountUrl(): string {
  return `${PRODUCT_ROOT}/account`;
}
