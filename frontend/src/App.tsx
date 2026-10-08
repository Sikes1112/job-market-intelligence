import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent, type FormEvent, type MouseEvent, type ReactNode } from "react";
import {
  ApiError,
  API_TARGET_LABEL,
  acceptPartnerImport,
  archivePartnerImport,
  createApiClient,
  createApiKey,
  createBillingCheckoutSession,
  createBillingPortalSession,
  createCareerPlatformExport,
  createIntegrationExport,
  createIntegrationReminder,
  createInstitutionDataRequest,
  createPartnerImport,
  createRecommendationSnapshot,
  createSavedMarketArtifact,
  deactivateAccount,
  dismissAlert,
  deletePreferences,
  deleteSavedMarketArtifact,
  discoverPersonalized,
  discoverPersonalizedFromCareerIdentity,
  explainAlert,
  explainComparison,
  explainCompany,
  explainRegion,
  exportUserData,
  getCompany,
  getCompanyGeography,
  getCompanySources,
  getComparison,
  getCurrentUser,
  getBillingStatus,
  getCareerPlatformRegistry,
  getHealth,
  getImportedMarkets,
  getImportedMarketOperationsView,
  getInstitutionBenchmarks,
  getInstitutionCurrentOrganizations,
  getInstitutionCurriculumMarketMap,
  getInstitutionDecisionDashboard,
  getInstitutionDashboard,
  getInstitutionWorkforceReport,
  getPartnerImportReceipt,
  generateInstitutionReport,
  getMonetizationAccessPreview,
  getMonetizationFeatures,
  getMonetizationPlans,
  getMonetizationReports,
  getMyMonetization,
  getMyMonetizationEntitlements,
  getMyMonetizationUsage,
  getPreferences,
  getPlatformEmbed,
  getPredictiveReport,
  getPublicBenchmark,
  getPublicBenchmarks,
  getPublicReport,
  getPublicReports,
  getRegion,
  getRecommendationGoalModes,
  getRecommendationStrategy,
  getRegionSources,
  getRegions,
  listInstitutionDataRequests,
  listInstitutionReports,
  listApiClients,
  listApiUsage,
  listPartnerImports,
  listAlerts,
  listRecommendationSnapshots,
  listSavedMarketArtifacts,
  markAlertRead,
  previewScoringOverlay,
  rejectPartnerImport,
  revokeApiKey,
  runInstitutionAdvisorComparison,
  searchCompanies,
  searchRegions,
  validatePartnerImport,
  updatePreferences,
  type ProtectedRequestOptions,
} from "./api";
import { useFrontendAuth, type FrontendAuthContextValue } from "./auth";
import {
  canonicalRegionIdForToken,
  geographicRouteToken,
} from "./geography";
import { isPublicDemoBlockedProduct } from "./demoMode";
import {
  coverageComponentEntries,
  coverageDescription,
  coverageDisplayLabel,
  coverageIsWeak,
  coverageLimitations,
  coverageScoreText,
  coverageTone,
  dataBasisLabel,
  envelopeFreshnessStatus,
  freshnessLabel,
  isSeedDemoFreshness,
  qualityBadges,
  qualityNotices,
  sectorCoverageLevelLabel,
  sectorCoverageTone,
} from "./dataQuality";
import {
  CountStatusValue,
  ImportedMarketBadges,
  ImportedMarketCoveragePanel,
} from "./ImportedMarketDisplay";
import { ImportedMarketOperationsPanel } from "./ImportedMarketOperations";
import { formatCountStatus } from "./importedMarketFormat";
import type {
  ApiEnvelope,
  AccountDeactivationResult,
  ApiClientCreatePayload,
  ApiClientCreateRequest,
  ApiClientListPayload,
  ApiScope,
  ApiKeyCreatePayload,
  ApiUsageListPayload,
  BillingStatusPayload,
  CareerPlatform,
  CareerPlatformExportPayload,
  CareerPlatformExportRequest,
  CareerPlatformRegistryPayload,
  CompanyGeographyResponse,
  CompanyDetail,
  CompanySearchResponse,
  ComparisonDetail,
  CoverageMetadata,
  SectorCoverageMap,
  CurrentUserProfile,
  ExplanationEvidencePacket,
  ExplanationResult,
  EntryLevelSummary,
  FreshnessSourceSummary,
  FreshnessStatus,
  InstitutionAggregateItem,
  InstitutionAdvisorApplicationTimingRequest,
  InstitutionAdvisorCareerStageRequest,
  InstitutionAdvisorCompanyRequest,
  InstitutionAdvisorComparisonType,
  InstitutionAdvisorComparedItem,
  InstitutionAdvisorIndustryRequest,
  InstitutionAdvisorRegionRequest,
  InstitutionAdvisorRequest,
  InstitutionAdvisorToolResponse,
  InstitutionAdvisorTradeoff,
  InstitutionBenchmarkPayload,
  InstitutionDecisionDashboardPayload,
  InstitutionDecisionEvidence,
  InstitutionDecisionMetric,
  InstitutionDecisionSection,
  InstitutionPrivacyMetadata,
  InstitutionCurrentOrganizationsPayload,
  CurriculumMarketMappingPayload,
  InstitutionDataRequestCreatePayload,
  InstitutionDataRequestCreateRequest,
  InstitutionDataRequestListPayload,
  InstitutionDataRequestPayload,
  InstitutionDataRequestType,
  InstitutionDashboardPayload,
  IntegrationExportCreateRequest,
  IntegrationExportFormat,
  IntegrationProductObjectType,
  IntegrationReminderCreateRequest,
  IntegrationReminderType,
  InstitutionReportCreateRequest,
  InstitutionReportGeneratePayload,
  InstitutionReportListPayload,
  InstitutionReportPayload,
  InstitutionReportSection,
  InstitutionReportSummary,
  InstitutionReportType,
  InstitutionWorkforceReportPayload,
  ImportedMarketOperationsViewPayload,
  MarketCoverageListPayload,
  MonetizationAccessPreviewPayload,
  MonetizationFeature,
  MonetizationFeatureKey,
  MonetizationFeaturesPayload,
  MonetizationEntitlementsPayload,
  MonetizationMePayload,
  MonetizationPlan,
  MonetizationPlanKey,
  MonetizationPlansPayload,
  MonetizationReportProduct,
  MonetizationReportsPayload,
  MonetizationUsagePayload,
  PartnerImportBatchPayload,
  PartnerImportCreatePayload,
  PartnerImportCreateRequest,
  PartnerImportFormat,
  PartnerImportListPayload,
  PartnerImportReceiptPayload,
  PartnerImportSourceType,
  PersonalizedRecommendationSnapshot,
  PersonalizedRecommendationSnapshotInput,
  PersonalizedResult,
  PlatformEmbedPayload,
  PredictiveReportForecast,
  PredictiveReportPayload,
  PredictiveReportSection,
  PreferenceLevel,
  PriorityMarket,
  PublicBenchmark,
  PublicBenchmarkListPayload,
  PublicBenchmarkMarketResult,
  PublicCitation,
  PublicInstitutionalCta,
  PublicReport,
  PublicReportListPayload,
  PublicReportMarketResult,
  PublicShareSummary,
  PublicSourceAuthority,
  AppliedRankingPenalty,
  MissingScoreComponent,
  RecommendationEvidenceReference,
  RecommendationGoalMode,
  RecommendationGoalModeProfilePayload,
  RecommendationGoalModesPayload,
  RecommendationManualVerificationItem,
  RecommendationRankingItem,
  RecommendationReason,
  RecommendationStrategyPayload,
  RecommendationTradeoff,
  RecommendationWeakness,
  RegionDetail,
  RegionListItem,
  RegionSearchResult,
  RegionSearchResponse,
  RegionScores,
  RemoteHybridPreference,
  SavedMarketArtifact,
  SavedMarketArtifactInput,
  ScoringPreviewResult,
  ScoringWeights,
  SourceExplanation,
  UserAlert,
  UserAlertList,
  UserDataExport,
  UserPreferenceProfile,
  UserPreferenceProfileInput,
  WarningItem,
  StrategyCompanyCategoryTarget,
  StrategyCompanyTarget,
  StrategyEvidenceWarning,
  StrategyRegionTarget,
  StrategyRoleFamilyTarget,
  StrategyTimingGuidance,
  StrategyWatchlistItem,
  WeightedScoreComponent,
} from "./types";
import {
  DEFAULT_REGION_A,
  DEFAULT_REGION_B,
  CAREER_STAGE_OPTIONS,
  INDUSTRY_OPTIONS,
  PREFERENCE_LEVELS,
  ROLE_TARGETS,
  accountUrl,
  careerAgentUrl,
  careerIdentityUrl,
  companyGeographyUrl,
  compareMarketsUrl,
  currentOpportunityOperationsUrl,
  currentOpportunitiesUrl,
  decisionsUrl,
  exploreUrl,
  institutionAdvisorUrl,
  institutionDataRequestsUrl,
  institutionDecisionsUrl,
  institutionDashboardUrl,
  institutionImportsUrl,
  institutionReportsUrl,
  isProductPage,
  landingUrl,
  marketIntelligenceUrl,
  opportunityRoutesUrl,
  policyLandingUrl,
  parseRoute,
  personalizedDiscoveryUrl,
  plansUrl,
  publicBenchmarkUrl,
  publicPageUrl,
  publicReportUrl,
  recommendationsUrl,
  regionDetailUrl,
  userIntelligenceDashboardUrl,
  type DiscoveryFilters,
  type ProductPage,
  type PublicPage,
  type RouteState,
} from "./urlState";
import {
  DATA_LICENSING_COPY,
  DEVELOPER_DOCS_COPY,
  DEVELOPER_DOCS_NAV,
  DEMO_DISCLOSURE_COPY,
  LANDING_COPY,
  LEGAL_PAGE_COPY,
  PUBLIC_INFO_LINKS,
  type DeveloperDocPageKey,
  type LegalPublicPage,
} from "./publicContent";
import {
  PUBLIC_SEO_PAGES,
  getPublicSeoPageBySlug,
  publicSeoPageUrl,
  relatedSeoPages,
  type PublicSeoConfidence,
  type PublicSeoLink,
  type PublicSeoPage,
} from "./publicSeoContent";
const PolicyIntelligencePage = lazy(() => import("./PolicyIntelligencePage"));
const MarketIntelligencePage = lazy(() =>
  import("./MarketIntelligencePage").then((module) => ({ default: module.MarketIntelligencePage })),
);
const CareerIdentityPage = lazy(() => import("./CareerIdentityPage"));
const DecisionWorkspacePage = lazy(() => import("./DecisionWorkspacePage"));
const OpportunityRoutesPage = lazy(() => import("./OpportunityRoutesPage"));
const CurrentOpportunitiesPage = lazy(() => import("./CurrentOpportunitiesPage"));
const CareerAgentPage = lazy(() => import("./CareerAgentPage"));
const DataStandardsPage = lazy(() => import("./DataStandardsPage"));
const UserIntelligenceDashboardPage = lazy(() => import("./UserIntelligenceDashboardPage"));

const SCORE_FIELDS: Array<{ key: keyof RegionScores; label: string; short: string }> = [
  {
    key: "structural_ecosystem_score",
    label: "Structural ecosystem",
    short: "Ecosystem",
  },
  { key: "live_market_score", label: "Live market", short: "Live market" },
  {
    key: "objective_opportunity_score",
    label: "Objective opportunity",
    short: "Opportunity",
  },
  { key: "raw_total_score", label: "Raw total", short: "Total" },
  { key: "general_density_score", label: "General density", short: "Density" },
  {
    key: "tech_market_density_score",
    label: "Tech market density",
    short: "Tech density",
  },
  {
    key: "early_career_accessibility_score",
    label: "Early-career accessibility",
    short: "Early career",
  },
];
const DEFAULT_FORECAST_REGION_IDS = ["greater_boston", "atlanta", "sf_bay_area", "austin"];
const SCORING_WEIGHT_FIELDS: Array<{ key: keyof ScoringWeights; label: string }> = [
  { key: "entry_level_access", label: "Entry-level access" },
  { key: "hiring_density", label: "Hiring density" },
  { key: "prestige", label: "Prestige" },
  { key: "industry_fit", label: "Industry fit" },
  { key: "role_fit", label: "Role fit" },
];
const DEFAULT_SCORING_WEIGHTS: ScoringWeights = {
  entry_level_access: 0.30,
  hiring_density: 0.25,
  prestige: 0.15,
  industry_fit: 0.15,
  role_fit: 0.15,
};
const DEFAULT_RECOMMENDATION_GOAL_MODE: RecommendationGoalMode = "maximize_entry_level_access";
const RECOMMENDATION_GOAL_MODES: RecommendationGoalMode[] = [
  "maximize_entry_level_access",
  "maximize_prestige",
  "maximize_ai_cloud_concentration",
  "maximize_underrated_markets",
  "maximize_internship_coop_access",
  "maximize_lower_competition",
  "maximize_geographic_flexibility",
];

type LoadState<T> = {
  loading: boolean;
  envelope: ApiEnvelope<T> | null;
  error: string | null;
};
type CompanyOption = {
  company_id: string;
  company_name: string;
  sector_primary?: string | null;
  source_regions: string[];
};
type OpportunityFilter = "any" | "0.70" | "0.50" | "missing";
type CareerStageFilter = "any" | "entry_level_reported" | "entry_level_unknown";
type FreshnessFilter = "any" | FreshnessStatus;
type PreferenceDraft = {
  roleInterests: string;
  industryInterests: string;
  preferredRegions: string;
  prestigeWeighting: "" | PreferenceLevel;
  brandWeighting: "" | PreferenceLevel;
  careerStage: "" | "entry_level";
  remoteHybridPreference: "" | RemoteHybridPreference;
  scoringWeights: ScoringWeights;
};
type AccountActionState = {
  loading: boolean;
  message: string | null;
  error: string | null;
};
type BillingActionState = {
  loadingPlanKey: MonetizationPlanKey | null;
  loadingPortal: boolean;
  message: string | null;
  error: string | null;
};
type AdvisorFormState = {
  regions: string;
  roleContext: string;
  industryContext: string;
  careerStage: string;
  industries: string;
  regionContext: string;
  companies: string;
  companyContext: string;
  careerStages: string;
  applicationWindow: string;
};
type InstitutionReportFormState = {
  reportType: InstitutionReportType;
  minimumGroupSize: number;
};
type InstitutionDataRequestFormState = {
  requestType: InstitutionDataRequestType;
  subjectUserId: string;
  reason: string;
};
type PartnerImportFormState = {
  sourceType: PartnerImportSourceType;
  importFormat: PartnerImportFormat;
  sourceAttribution: string;
  originalFilename: string;
  content: string;
};
type ApiAccessFormState = {
  displayName: string;
  organizationId: string;
  scopes: ApiScope[];
  rateLimitCount: number;
  rateLimitWindowSeconds: number;
};

const ADVISOR_COMPARISON_OPTIONS: Array<{
  id: InstitutionAdvisorComparisonType;
  label: string;
}> = [
  { id: "regions", label: "Regions" },
  { id: "industries", label: "Industries" },
  { id: "companies", label: "Companies" },
  { id: "career_stages", label: "Career stages" },
  { id: "application_timing", label: "Application timing" },
];

const DEFAULT_ADVISOR_FORM_STATE: AdvisorFormState = {
  regions: "greater_boston, sf_bay_area",
  roleContext: "software engineering",
  industryContext: "software",
  careerStage: "entry_level",
  industries: "software, cloud",
  regionContext: "greater_boston",
  companies: "comp_alpha, comp_beta",
  companyContext: "",
  careerStages: "entry_level, internship, career_changer",
  applicationWindow: "fall recruiting",
};

const INSTITUTION_REPORT_OPTIONS: Array<{
  id: InstitutionReportType;
  label: string;
}> = [
  { id: "career_services", label: "Career services" },
  { id: "program_director", label: "Program director" },
  { id: "workforce_planner", label: "Workforce planner" },
  { id: "economic_development_partner", label: "Economic development partner" },
];

const INSTITUTION_DATA_REQUEST_OPTIONS: Array<{
  id: InstitutionDataRequestType;
  label: string;
}> = [
  { id: "organization_export", label: "Organization export" },
  { id: "organization_deletion", label: "Organization deletion" },
  { id: "student_export", label: "Student export" },
  { id: "student_deletion", label: "Student deletion" },
];

const PARTNER_IMPORT_SOURCE_OPTIONS: Array<{
  id: PartnerImportSourceType;
  label: string;
}> = [
  { id: "local_employer_list", label: "Local employer list" },
  { id: "internship_partner_list", label: "Internship partner list" },
  { id: "regional_workforce_data", label: "Regional workforce data" },
  {
    id: "aggregated_career_center_outcome_data",
    label: "Aggregated outcome data",
  },
];

const PARTNER_IMPORT_FORMAT_OPTIONS: Array<{
  id: PartnerImportFormat;
  label: string;
}> = [
  { id: "csv", label: "CSV" },
  { id: "json", label: "JSON" },
];

const API_SCOPE_OPTIONS: Array<{ id: ApiScope; label: string }> = [
  { id: "region:read", label: "Region read" },
  { id: "company_geography:read", label: "Company geography read" },
  { id: "market_signal:read", label: "Market signal read" },
  { id: "institution_dashboard:read", label: "Institution dashboard read" },
  { id: "exports:create", label: "Create exports" },
  { id: "imports:create", label: "Create imports" },
];

const CAREER_PLATFORM_OPTIONS: Array<{ id: CareerPlatform; label: string }> = [
  { id: "linkedin", label: "LinkedIn manual search" },
  { id: "handshake", label: "Handshake manual lookup" },
];

const DEFAULT_REPORT_FORM_STATE: InstitutionReportFormState = {
  reportType: "career_services",
  minimumGroupSize: 5,
};

const DEFAULT_DATA_REQUEST_FORM_STATE: InstitutionDataRequestFormState = {
  requestType: "organization_export",
  subjectUserId: "",
  reason: "",
};

const DEFAULT_PARTNER_IMPORT_FORM_STATE: PartnerImportFormState = {
  sourceType: "local_employer_list",
  importFormat: "csv",
  sourceAttribution: "Career center partner list",
  originalFilename: "partner-import.csv",
  content: "employer_name,region,source_attribution,observed_at\nAlpha Systems,Greater Boston,Career center partner list,2026-01-10\n",
};

const DEFAULT_API_ACCESS_FORM_STATE: ApiAccessFormState = {
  displayName: "Read-only market intelligence client",
  organizationId: "",
  scopes: ["region:read", "company_geography:read", "market_signal:read"],
  rateLimitCount: 60,
  rateLimitWindowSeconds: 3600,
};

const INTEGRATION_EXPORT_OPTIONS: Array<{
  id: IntegrationExportFormat;
  label: string;
  description: string;
}> = [
  { id: "csv", label: "CSV", description: "Local file download" },
  { id: "pdf", label: "PDF", description: "Governance-marked file" },
  { id: "prepared_google_sheets", label: "Sheets", description: "Prepared manual payload" },
  { id: "prepared_notion", label: "Notion", description: "Prepared manual payload" },
  { id: "prepared_airtable", label: "Airtable", description: "Prepared manual payload" },
];

const NAV_ITEMS: Array<{ id: ProductPage; label: string; kicker: string }> = [
  { id: "dashboard", label: "Dashboard", kicker: "User intelligence" },
  { id: "explore", label: "Explore Markets", kicker: "Market map" },
  { id: "intelligence", label: "Market Intelligence", kicker: "Goal rankings" },
  { id: "region", label: "Region Detail", kicker: "Regional output" },
  { id: "company", label: "Company Geography", kicker: "Presence and hiring" },
  { id: "compare", label: "Compare Markets", kicker: "Score comparison" },
  { id: "discovery", label: "Personalized Discovery", kicker: "Personal overlay" },
  { id: "career-identity", label: "Career Identity", kicker: "Profile source" },
  { id: "decisions", label: "Decisions", kicker: "Decision workspace" },
  { id: "recommendations", label: "Recommendations", kicker: "Decision support" },
  { id: "career-agent", label: "Career Agent", kicker: "Grounded answers" },
  { id: "opportunity-routes", label: "Opportunity Routes", kicker: "Route guidance" },
  { id: "current-opportunities", label: "Current Opportunities", kicker: "Strategic openings" },
  { id: "policy", label: "Policy", kicker: "Workforce intel" },
  { id: "plans", label: "Plans", kicker: "Access model" },
  { id: "institution", label: "Institution", kicker: "Cohort dashboard" },
  { id: "account", label: "Account", kicker: "Saved overlays" },
];

const REMOTE_HYBRID_OPTIONS: RemoteHybridPreference[] = ["remote", "hybrid", "onsite", "flexible"];
const ACCESS_PREVIEW_REQUESTS: Array<{
  plan_key?: MonetizationPlanKey;
  feature_key: MonetizationFeatureKey;
  used?: number;
}> = [
  { feature_key: "basic_recommendation_preview" },
  { feature_key: "limited_comparisons", used: 2 },
  { feature_key: "saved_watchlists" },
  { feature_key: "alerts" },
  { feature_key: "full_report_generation" },
  { feature_key: "exportable_strategy_plans" },
  { feature_key: "full_market_coverage" },
];

const PLAN_DISPLAY_ORDER: MonetizationPlanKey[] = [
  "free",
  "individual_monthly",
  "individual_annual",
  "student_annual",
  "career_center_license",
  "bootcamp_license",
  "university_license",
  "workforce_board_license",
];

const FEATURE_DISPLAY_ORDER: MonetizationFeatureKey[] = [
  "basic_region_exploration",
  "public_demo_markets",
  "limited_comparisons",
  "limited_personalized_discovery",
  "basic_recommendation_preview",
  "saved_watchlists",
  "alerts",
  "advanced_recommendation_reports",
  "full_market_coverage",
  "exportable_strategy_plans",
  "deeper_company_geography",
  "saved_comparison_history",
  "full_report_generation",
  "institutional_license_management",
  "cohort_guidance_templates",
  "privacy_preserving_program_insights",
];

function emptyLoadState<T>(): LoadState<T> {
  return { loading: false, envelope: null, error: null };
}

function readCurrentRoute(): RouteState {
  return parseRoute(window.location.pathname, window.location.search);
}

function currentUrl(): string {
  return `${window.location.pathname}${window.location.search}`;
}

function redirectToBillingProvider(url: string): void {
  window.dispatchEvent(new CustomEvent("jmi:billing-provider-redirect", { detail: { url } }));
  if (import.meta.env.MODE !== "test") {
    window.location.assign(url);
  }
}

function isPlainLeftClick(event: MouseEvent<HTMLAnchorElement>): boolean {
  return event.button === 0 && !event.metaKey && !event.altKey && !event.ctrlKey && !event.shiftKey;
}

function getDefaultRegionId(regions: RegionListItem[]): string {
  if (regions.some((region) => region.region_id === DEFAULT_REGION_A)) return DEFAULT_REGION_A;
  return regions[0]?.region_id ?? DEFAULT_REGION_A;
}

function getFallbackComparisonRegion(regions: RegionListItem[], regionA: string): string {
  if (regionA !== DEFAULT_REGION_B && regions.some((region) => region.region_id === DEFAULT_REGION_B)) {
    return DEFAULT_REGION_B;
  }

  return regions.find((region) => region.region_id !== regionA)?.region_id ?? DEFAULT_REGION_B;
}

function isKnownRegion(regionId: string, regions: RegionListItem[], loaded: boolean): boolean {
  return !loaded || Boolean(canonicalRegionIdForToken(regionId, regions));
}

function getNavigationUrl(
  page: ProductPage,
  selectedRegionId: string,
  selectedCompanyId: string,
  comparisonA: string,
  comparisonB: string,
  discoveryFilters: DiscoveryFilters,
): string {
  if (page === "dashboard") return userIntelligenceDashboardUrl();
  if (page === "intelligence") return marketIntelligenceUrl();
  if (page === "region") return regionDetailUrl(selectedRegionId);
  if (page === "company") return companyGeographyUrl(selectedCompanyId);
  if (page === "compare") return compareMarketsUrl(comparisonA, comparisonB);
  if (page === "discovery") return personalizedDiscoveryUrl(discoveryFilters);
  if (page === "career-identity") return careerIdentityUrl();
  if (page === "decisions") return decisionsUrl();
  if (page === "recommendations") return recommendationsUrl();
  if (page === "career-agent") return careerAgentUrl();
  if (page === "opportunity-routes") return opportunityRoutesUrl();
  if (page === "current-opportunities") return currentOpportunitiesUrl();
  if (page === "current-opportunity-operations") return currentOpportunityOperationsUrl();
  if (page === "policy") return policyLandingUrl();
  if (page === "plans") return plansUrl();
  if (page === "institution") return institutionDashboardUrl();
  if (page === "account") return accountUrl();
  return exploreUrl();
}

function prettyKey(value: string) {
  return value.replaceAll("_", " ");
}

function segmentLabel(value: string): string {
  return prettyKey(value).replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function featureByKey(features: MonetizationFeature[]): Map<MonetizationFeatureKey, MonetizationFeature> {
  return new Map(features.map((feature) => [feature.feature_key, feature]));
}

function orderedFeatures(features: MonetizationFeature[]): MonetizationFeature[] {
  const order = new Map(FEATURE_DISPLAY_ORDER.map((featureKey, index) => [featureKey, index]));
  return [...features].sort((left, right) =>
    (order.get(left.feature_key) ?? 999) - (order.get(right.feature_key) ?? 999)
    || left.display_name.localeCompare(right.display_name),
  );
}

function orderedPlans(plans: MonetizationPlan[]): MonetizationPlan[] {
  const order = new Map(PLAN_DISPLAY_ORDER.map((planKey, index) => [planKey, index]));
  return [...plans].sort((left, right) =>
    (order.get(left.plan_key) ?? 999) - (order.get(right.plan_key) ?? 999)
    || left.display_name.localeCompare(right.display_name),
  );
}

function usageLimitLabel(limit: { limit: number; unit: string; description: string }): string {
  return `${limit.limit} ${prettyKey(limit.unit)} · ${limit.description}`;
}

function priceLabel(plan: MonetizationPlan): string {
  if (plan.price.placeholder_amount_cents === 0) return "Free";
  if (plan.price.placeholder_amount_cents === null) return "Configurable quote";
  const amount = (plan.price.placeholder_amount_cents / 100).toLocaleString(undefined, {
    currency: plan.price.currency,
    style: "currency",
  });
  return plan.price.final_price ? amount : `Placeholder test price: ${amount}`;
}

function accessPreviewKey(request: {
  plan_key?: MonetizationPlanKey;
  feature_key: MonetizationFeatureKey;
  used?: number;
}): string {
  return `${request.plan_key ?? "account"}:${request.feature_key}:${request.used ?? "none"}`;
}

function isRecommendationGoalMode(value: string): value is RecommendationGoalMode {
  return RECOMMENDATION_GOAL_MODES.includes(value as RecommendationGoalMode);
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "n/a";
  if (typeof value === "number") {
    return Number.isInteger(value) ? `${value}` : value.toFixed(2);
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "None";
  return String(value);
}

function emptyPreferenceDraft(): PreferenceDraft {
  return {
    roleInterests: "",
    industryInterests: "",
    preferredRegions: "",
    prestigeWeighting: "",
    brandWeighting: "",
    careerStage: "",
    remoteHybridPreference: "",
    scoringWeights: { ...DEFAULT_SCORING_WEIGHTS },
  };
}

function splitDraftList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function optionalDraftValue(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function advisorRequestFromForm(
  comparisonType: InstitutionAdvisorComparisonType,
  form: AdvisorFormState,
): { request: InstitutionAdvisorRequest | null; error: string | null } {
  if (comparisonType === "regions") {
    const regions = splitDraftList(form.regions);
    if (!regions.length) return { request: null, error: "Add at least one region to compare." };
    const request: InstitutionAdvisorRegionRequest = {
      regions,
      role_context: optionalDraftValue(form.roleContext),
      industry_context: optionalDraftValue(form.industryContext),
      career_stage: optionalDraftValue(form.careerStage),
    };
    return { request, error: null };
  }

  if (comparisonType === "industries") {
    const industries = splitDraftList(form.industries);
    if (!industries.length) return { request: null, error: "Add at least one industry to compare." };
    const request: InstitutionAdvisorIndustryRequest = {
      industries,
      region_context: splitDraftList(form.regionContext),
      career_stage: optionalDraftValue(form.careerStage),
    };
    return { request, error: null };
  }

  if (comparisonType === "companies") {
    const companies = splitDraftList(form.companies);
    if (!companies.length) return { request: null, error: "Add at least one company to compare." };
    const request: InstitutionAdvisorCompanyRequest = {
      companies,
      region_context: splitDraftList(form.regionContext),
      industry_context: optionalDraftValue(form.industryContext),
      career_stage: optionalDraftValue(form.careerStage),
    };
    return { request, error: null };
  }

  if (comparisonType === "career_stages") {
    const careerStages = splitDraftList(form.careerStages);
    if (!careerStages.length) return { request: null, error: "Add at least one career stage to compare." };
    const request: InstitutionAdvisorCareerStageRequest = {
      career_stages: careerStages,
      region_context: splitDraftList(form.regionContext),
      industry_context: optionalDraftValue(form.industryContext),
      company_context: splitDraftList(form.companyContext),
    };
    return { request, error: null };
  }

  const request: InstitutionAdvisorApplicationTimingRequest = {
    target_regions: splitDraftList(form.regions),
    target_industries: splitDraftList(form.industries),
    target_companies: splitDraftList(form.companies),
    career_stage: optionalDraftValue(form.careerStage),
    application_window: optionalDraftValue(form.applicationWindow),
  };
  if (
    !request.target_regions?.length
    && !request.target_industries?.length
    && !request.target_companies?.length
    && !request.career_stage
    && !request.application_window
  ) {
    return { request: null, error: "Add at least one timing context." };
  }
  return { request, error: null };
}

function reportRequestFromForm(form: InstitutionReportFormState): InstitutionReportCreateRequest {
  return {
    report_type: form.reportType,
    minimum_group_size: Math.max(5, Math.min(50, Math.trunc(form.minimumGroupSize || 5))),
  };
}

function dataRequestFromForm(
  form: InstitutionDataRequestFormState,
): InstitutionDataRequestCreateRequest {
  const isOrganizationRequest = form.requestType.startsWith("organization_");
  const subjectUserId = optionalDraftValue(form.subjectUserId);
  return {
    request_type: form.requestType,
    subject_type: isOrganizationRequest ? "organization" : "student",
    subject_user_id: isOrganizationRequest ? null : subjectUserId,
    reason: optionalDraftValue(form.reason),
  };
}

function partnerImportRequestFromForm(
  organizationId: string,
  form: PartnerImportFormState,
): PartnerImportCreateRequest {
  return {
    organization_id: organizationId,
    source_type: form.sourceType,
    import_format: form.importFormat,
    source_attribution: optionalDraftValue(form.sourceAttribution),
    content: form.content,
    original_filename: optionalDraftValue(form.originalFilename),
  };
}

function apiClientRequestFromForm(form: ApiAccessFormState): ApiClientCreateRequest {
  return {
    display_name: form.displayName,
    scopes: form.scopes,
    organization_id: optionalDraftValue(form.organizationId),
    rate_limit_count: Math.max(1, Math.trunc(form.rateLimitCount || 60)),
    rate_limit_window_seconds: Math.max(
      60,
      Math.trunc(form.rateLimitWindowSeconds || 3600),
    ),
    allowed_origins: [],
  };
}

function formatAdvisorSignalValue(value: unknown): string {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return JSON.stringify(value);
  }
  return formatValue(value);
}

function joinDraftList(values?: string[]): string {
  return values?.join(", ") ?? "";
}

function preferenceDraftFromProfile(profile?: UserPreferenceProfile | null): PreferenceDraft {
  if (!profile) return emptyPreferenceDraft();
  return {
    roleInterests: joinDraftList(profile.role_interests),
    industryInterests: joinDraftList(profile.industry_interests),
    preferredRegions: joinDraftList(profile.preferred_regions),
    prestigeWeighting: profile.prestige_weighting ?? "",
    brandWeighting: profile.brand_weighting ?? "",
    careerStage: profile.career_stage ?? "",
    remoteHybridPreference: profile.remote_hybrid_preference ?? "",
    scoringWeights: normalizeScoringWeights(profile.scoring_weights),
  };
}

function preferenceInputFromDraft(draft: PreferenceDraft): UserPreferenceProfileInput {
  return {
    role_interests: splitDraftList(draft.roleInterests),
    industry_interests: splitDraftList(draft.industryInterests),
    preferred_regions: splitDraftList(draft.preferredRegions),
    prestige_weighting: draft.prestigeWeighting || null,
    brand_weighting: draft.brandWeighting || null,
    career_stage: draft.careerStage || null,
    remote_hybrid_preference: draft.remoteHybridPreference || null,
    scoring_weights: normalizeScoringWeights(draft.scoringWeights),
  };
}

function savedArtifactKey(type: SavedMarketArtifactInput["artifact_type"], ref: string): string {
  return `${type}:${ref}`;
}

function watchlistGroupLabel(type: SavedMarketArtifact["artifact_type"]): string {
  if (type === "region") return "Regions";
  if (type === "company") return "Companies";
  if (type === "role_family") return "Role families";
  if (type === "comparison") return "Comparison sets";
  return "Discovery results";
}

function watchlistGroups(artifacts: SavedMarketArtifact[]): Array<{
  type: SavedMarketArtifact["artifact_type"];
  label: string;
  items: SavedMarketArtifact[];
}> {
  const order: SavedMarketArtifact["artifact_type"][] = [
    "region",
    "company",
    "role_family",
    "comparison",
    "discovery_result",
  ];
  return order
    .map((type) => ({
      type,
      label: watchlistGroupLabel(type),
      items: artifacts.filter((artifact) => artifact.artifact_type === type),
    }))
    .filter((group) => group.items.length);
}

function normalizeScoringWeights(weights?: Partial<ScoringWeights> | null): ScoringWeights {
  return {
    entry_level_access: clampWeight(weights?.entry_level_access ?? DEFAULT_SCORING_WEIGHTS.entry_level_access),
    hiring_density: clampWeight(weights?.hiring_density ?? DEFAULT_SCORING_WEIGHTS.hiring_density),
    prestige: clampWeight(weights?.prestige ?? DEFAULT_SCORING_WEIGHTS.prestige),
    industry_fit: clampWeight(weights?.industry_fit ?? DEFAULT_SCORING_WEIGHTS.industry_fit),
    role_fit: clampWeight(weights?.role_fit ?? DEFAULT_SCORING_WEIGHTS.role_fit),
  };
}

function clampWeight(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(1, value));
}

function updateScoringWeight(
  weights: ScoringWeights,
  key: keyof ScoringWeights,
  percentValue: number,
): ScoringWeights {
  return normalizeScoringWeights({
    ...weights,
    [key]: percentValue / 100,
  });
}

function canonicalComparisonRef(regionA: string, regionB: string): string {
  return [regionA, regionB].filter(Boolean).sort().join("__");
}

async function sha256Label(value: unknown): Promise<string> {
  const serialized = JSON.stringify(value);
  if (window.crypto?.subtle) {
    const bytes = new TextEncoder().encode(serialized);
    const digest = await window.crypto.subtle.digest("SHA-256", bytes);
    const hex = Array.from(new Uint8Array(digest))
      .map((byte) => byte.toString(16).padStart(2, "0"))
      .join("");
    return `sha256:${hex}`;
  }

  let hash = 0;
  for (const char of serialized) {
    hash = Math.imul(31, hash) + char.charCodeAt(0);
  }
  return `sha256:fallback-${Math.abs(hash).toString(16)}`;
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "n/a";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function formatDateOnly(value: string | null | undefined): string {
  if (!value) return "n/a";
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
}

function scorePercent(value: number | null | undefined) {
  if (typeof value !== "number") return 0;
  return Math.max(0, Math.min(100, value * 100));
}

function warningCode(warning: WarningItem): string {
  if (typeof warning === "string") return warning;
  const code = warning.warning_code ?? warning.code;
  return typeof code === "string" && code.trim() ? code : "warning";
}

function warningMessage(warning: WarningItem): string {
  if (typeof warning === "string") return warning;
  return typeof warning.message === "string" && warning.message.trim()
    ? warning.message
    : "No warning message provided.";
}

function warningSeverity(warning: WarningItem): string | null {
  if (typeof warning === "string") return null;
  return typeof warning.severity === "string" && warning.severity.trim()
    ? warning.severity
    : null;
}

function warningScope(warning: WarningItem): string | null {
  if (typeof warning === "string") return null;
  const scopeType = typeof warning.scope_type === "string" ? warning.scope_type : "";
  const scopeRef = typeof warning.scope_ref === "string" ? warning.scope_ref : "";
  if (!scopeType && !scopeRef) return null;
  return [scopeType, scopeRef].filter(Boolean).join(": ");
}

function hasStructuredWarningDetails(warning: WarningItem): boolean {
  return typeof warning !== "string";
}

function freshnessText(freshness: ApiEnvelope<unknown>["metadata"]["freshness"]): string {
  if (!freshness) return "";
  const status =
    freshness.freshness_status
    ?? (freshness.freshness_expires_at
      ? freshness.is_stale
        ? "stale"
        : "fresh"
      : "unknown");
  if (status === "unknown") return "Freshness not tracked";
  const expires = formatDateTime(freshness.freshness_expires_at);
  if (status === "partial") return `Partial freshness · Expires: ${expires}`;
  if (status === "seeded_demo" || isSeedDemoFreshness(freshness.freshness_expires_at)) {
    return `Seeded demo freshness · Expires: ${expires}`;
  }
  if (status === "stale") return `Stale · Expires: ${expires}`;
  return `Fresh · Expires: ${expires}`;
}

function winnerLabel(regionId: string | null | undefined, regions: RegionListItem[], comparison?: ComparisonDetail | null) {
  if (!regionId) return "Tie";
  const fromComparison = [comparison?.region_a, comparison?.region_b].find(
    (region) => region?.region_id === regionId,
  );
  if (fromComparison?.display_name) return fromComparison.display_name;
  return regions.find((region) => region.region_id === regionId)?.display_name ?? regionId;
}

function getCompanyOptions(regionDetails: Record<string, ApiEnvelope<RegionDetail>>): CompanyOption[] {
  const companies = new Map<string, CompanyOption>();

  Object.values(regionDetails).forEach((envelope) => {
    const region = envelope.data;
    if (!region) return;

    [...(region.top_companies_present ?? []), ...(region.top_companies_hiring ?? [])].forEach((company) => {
      const current = companies.get(company.company_id);
      if (current) {
        current.source_regions = Array.from(
          new Set([...current.source_regions, region.display_name]),
        );
        return;
      }

      companies.set(company.company_id, {
        company_id: company.company_id,
        company_name: company.company_name,
        sector_primary: "sector_primary" in company ? company.sector_primary : null,
        source_regions: [region.display_name],
      });
    });
  });

  return Array.from(companies.values()).sort((left, right) =>
    left.company_name.localeCompare(right.company_name),
  );
}

function pickEnvelopeWarnings(envelope?: ApiEnvelope<unknown> | null) {
  return envelope?.metadata?.warnings ?? [];
}

function qualityBadgeClass(tone: string): string {
  return `badge badge-${tone}`;
}

function QualityBadgeRow({
  envelope,
  source,
}: {
  envelope?: ApiEnvelope<unknown> | null;
  source?: SourceExplanation | FreshnessSourceSummary | null;
}) {
  return (
    <div className="metadata-row">
      {qualityBadges(envelope, source).map((badge) => (
        <span className={qualityBadgeClass(badge.tone)} key={`${badge.label}-${badge.tone}`}>
          {badge.label}
        </span>
      ))}
    </div>
  );
}

function CoverageBadge({ coverage }: { coverage?: CoverageMetadata | null }) {
  return (
    <span className={qualityBadgeClass(coverageTone(coverage))}>
      {coverageDisplayLabel(coverage)}
    </span>
  );
}

function PriorityMarketBadge({ priorityMarket }: { priorityMarket?: PriorityMarket | null }) {
  if (!priorityMarket) return null;
  return (
    <span className="badge badge-unknown">
      Priority #{priorityMarket.rank}: {priorityMarket.display_name}
    </span>
  );
}

function CoverageInlineNote({ coverage }: { coverage?: CoverageMetadata | null }) {
  if (!coverageIsWeak(coverage)) return null;
  const [firstLimitation] = coverageLimitations(coverage);
  return <p className="meta-copy coverage-note">{firstLimitation ?? coverageDescription(coverage)}</p>;
}

function CoverageWarningList({ warnings }: { warnings: WarningItem[] }) {
  const coverageWarnings = warnings.filter((warning) => warningCode(warning) === "region_coverage_not_confident");
  if (!coverageWarnings.length) return null;
  return (
    <div className="warning-list coverage-warning-list" aria-label="Coverage warnings">
      {coverageWarnings.map((warning, index) => (
        <div className="warning-item" key={index}>
          <div className="warning-header">
            <span className="warning-code">{prettyKey(warningCode(warning))}</span>
            {warningSeverity(warning) ? (
              <span className="badge badge-warning">{warningSeverity(warning)}</span>
            ) : null}
          </div>
          <p>{warningMessage(warning)}</p>
          {warningScope(warning) ? <small>{warningScope(warning)}</small> : null}
        </div>
      ))}
    </div>
  );
}

function SectorCoveragePanel({ sectorCoverage }: { sectorCoverage?: SectorCoverageMap | null }) {
  const sectors = Object.values(sectorCoverage ?? {}).filter((sector) => sector?.coverage);
  if (!sectors.length) return null;

  return (
    <div className="sector-coverage-panel">
      <div className="coverage-section-heading">
        <strong>Sector coverage</strong>
        <small>Separate from overall region coverage</small>
      </div>
      <div className="sector-coverage-list">
        {sectors.map((sector) => (
          <div className="sector-coverage-row" key={sector.sector}>
            <span>{sector.label ?? prettyKey(sector.sector)}</span>
            <span className={qualityBadgeClass(sectorCoverageTone(sector.coverage_level))}>
              Sector level: {sectorCoverageLevelLabel(sector.coverage_level)}
            </span>
            <CoverageBadge coverage={sector.coverage} />
          </div>
        ))}
      </div>
    </div>
  );
}

function CoveragePanel({
  coverage,
  sectorCoverage,
}: {
  coverage?: CoverageMetadata | null;
  sectorCoverage?: SectorCoverageMap | null;
}) {
  const scoreText = coverageScoreText(coverage);
  const components = coverageComponentEntries(coverage);
  const description = coverageDescription(coverage);
  const limitations = coverageLimitations(coverage).filter((limitation) => limitation !== description);
  const notes = coverage?.notes ?? [];

  return (
    <div className="coverage-panel">
      <div className="metadata-row">
        <CoverageBadge coverage={coverage} />
        {coverage?.heuristic ? <span className="badge badge-unknown">Heuristic</span> : null}
      </div>
      {scoreText ? <p className="coverage-score">{scoreText}</p> : null}
      <p className="meta-copy">{description}</p>
      {limitations.length ? (
        <ul className="coverage-notes" aria-label="Coverage limitations">
          {limitations.map((limitation) => (
            <li key={limitation}>{limitation}</li>
          ))}
        </ul>
      ) : null}
      {components.length ? (
        <div className="coverage-component-grid" aria-label="Coverage components">
          {components.map((component) => (
            <div className="coverage-component-row" key={component.key}>
              <span>{component.label}</span>
              <strong>{component.value}%</strong>
            </div>
          ))}
        </div>
      ) : null}
      {notes.length ? (
        <ul className="coverage-notes">
          {notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      ) : null}
      <SectorCoveragePanel sectorCoverage={sectorCoverage} />
    </div>
  );
}

function getSourceSummary(
  source?: SourceExplanation | FreshnessSourceSummary | null,
): FreshnessSourceSummary | null {
  if (!source) return null;
  return "freshness" in source ? source.freshness : source;
}

function getRegionSearchMap(search?: ApiEnvelope<RegionSearchResponse> | null): Map<string, RegionSearchResult> {
  return new Map((search?.data?.regions ?? []).map((region) => [region.region_id, region]));
}

function coverageForRegion(
  region: RegionListItem,
  searchItem?: RegionSearchResult,
  detail?: RegionDetail | null,
): {
  coverage?: CoverageMetadata;
  sectorCoverage?: SectorCoverageMap;
  priorityMarket?: PriorityMarket | null;
} {
  return {
    coverage: searchItem?.coverage ?? detail?.coverage ?? region.coverage,
    sectorCoverage: searchItem?.sector_coverage ?? detail?.sector_coverage ?? region.sector_coverage,
    priorityMarket: searchItem?.priority_market ?? detail?.priority_market ?? region.priority_market,
  };
}

function regionOpportunityScore(
  regionId: string,
  searchMap: Map<string, RegionSearchResult>,
  regionDetails: Record<string, ApiEnvelope<RegionDetail>>,
): number | null {
  return searchMap.get(regionId)?.opportunity_score
    ?? regionDetails[regionId]?.data?.scores?.objective_opportunity_score
    ?? null;
}

function entryLevelSignalState(region?: RegionDetail | null): "reported" | "unknown" {
  const summary = region?.entry_level_summary;
  if (!summary) return "unknown";
  const values = Object.values(summary);
  return values.some((value) => typeof value === "number" && value > 0) ? "reported" : "unknown";
}

function hasEntryLevelAccess(row: NonNullable<CompanyDetail["entry_level_regions"]>[number]): boolean {
  return Boolean(
    (row.entry_level_access_score !== null && row.entry_level_access_score !== undefined && row.entry_level_access_score > 0)
      || (row.internship_count !== null && row.internship_count !== undefined && row.internship_count > 0)
      || (row.coop_count !== null && row.coop_count !== undefined && row.coop_count > 0)
      || (row.entry_level_full_time_count !== null && row.entry_level_full_time_count !== undefined && row.entry_level_full_time_count > 0)
      || row.formal_early_career_program_flag,
  );
}

function roleFamilyCounts(response?: CompanySearchResponse | null): Array<{ role: string; count: number }> {
  const counts = new Map<string, number>();
  for (const company of response?.companies ?? []) {
    for (const role of company.role_families ?? []) {
      counts.set(role, (counts.get(role) ?? 0) + 1);
    }
  }
  return Array.from(counts.entries())
    .map(([role, count]) => ({ role, count }))
    .sort((left, right) => right.count - left.count || left.role.localeCompare(right.role));
}

function comparisonSideLabel(
  side: ComparisonDetail["region_a"] | undefined,
  fallbackRegionId: string,
  regions: RegionListItem[],
): string {
  return side?.display_name
    ?? regions.find((region) => region.region_id === fallbackRegionId)?.display_name
    ?? fallbackRegionId
    ?? "Unknown region";
}

function objectiveComparison(
  comparison: ComparisonDetail | null | undefined,
): {
  winnerId: string | null;
  winnerLabel: string;
  message: string;
  delta: number | null;
} {
  const aValue = comparison?.region_a?.scores?.objective_opportunity_score;
  const bValue = comparison?.region_b?.scores?.objective_opportunity_score;
  const aName = comparison?.region_a?.display_name ?? "Region A";
  const bName = comparison?.region_b?.display_name ?? "Region B";

  if (typeof aValue !== "number" || typeof bValue !== "number") {
    return {
      winnerId: null,
      winnerLabel: "No objective winner",
      message: "Objective opportunity cannot be compared because one or both regions are missing that score.",
      delta: null,
    };
  }

  if (aValue === bValue) {
    return {
      winnerId: null,
      winnerLabel: "Tie on objective opportunity",
      message: "Both regions have the same objective opportunity score in the returned comparison.",
      delta: 0,
    };
  }

  const winnerIsA = aValue > bValue;
  const delta = Math.abs(aValue - bValue);
  return {
    winnerId: winnerIsA ? comparison?.region_a?.region_id ?? null : comparison?.region_b?.region_id ?? null,
    winnerLabel: winnerIsA ? aName : bName,
    message: `${winnerIsA ? aName : bName} has the higher objective opportunity score by ${(delta * 100).toFixed(0)} percentage point(s).`,
    delta,
  };
}

function comparisonDataLimitations(
  comparison: ComparisonDetail | null | undefined,
  envelope?: ApiEnvelope<unknown> | null,
  sourceA?: SourceExplanation | null,
  sourceB?: SourceExplanation | null,
): string[] {
  const notices = new Set<string>();
  const missingCategories = SCORE_FIELDS.filter((score) => {
    const aValue = comparison?.region_a?.scores?.[score.key];
    const bValue = comparison?.region_b?.scores?.[score.key];
    return typeof aValue !== "number" || typeof bValue !== "number";
  }).map((score) => score.label);

  if (!comparison?.region_a || !comparison.region_b) {
    notices.add("The comparison response is missing one or both region sides.");
  }
  if (missingCategories.length) {
    notices.add(`Missing comparable score data for: ${missingCategories.join(", ")}.`);
  }
  for (const notice of qualityNotices(envelope)) notices.add(notice);
  for (const notice of qualityNotices(undefined, sourceA)) notices.add(`Region A: ${notice}`);
  for (const notice of qualityNotices(undefined, sourceB)) notices.add(`Region B: ${notice}`);
  return Array.from(notices);
}

function missingScoreLabels(scores?: RegionScores | null): string[] {
  if (!scores) return SCORE_FIELDS.map((score) => score.label);
  return SCORE_FIELDS
    .filter((score) => typeof scores[score.key] !== "number")
    .map((score) => score.label);
}

function sourceRefsFromExplanation(source?: SourceExplanation | null): string[] {
  return (source?.sources ?? []).map((item) => `${item.source_type}:${item.source_id}`);
}

function compactSubjectRefs(refs: Record<string, string | null | undefined>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(refs).filter((entry): entry is [string, string] =>
      typeof entry[1] === "string" && entry[1].trim().length > 0,
    ),
  );
}

function explanationFreshness(
  envelope?: ApiEnvelope<unknown> | null,
  source?: SourceExplanation | FreshnessSourceSummary | null,
) {
  const envelopeFreshness = envelope?.metadata.freshness;
  const summary = getSourceSummary(source);
  const freshnessStatus = summary?.freshness_status ?? envelopeFreshness?.freshness_status ?? null;
  const dataBasis = summary?.data_basis ?? null;
  if (!freshnessStatus && !dataBasis && !envelopeFreshness) return null;
  return {
    freshness_status: freshnessStatus,
    data_basis: dataBasis,
    last_updated_at: envelopeFreshness?.last_updated_at ?? summary?.last_collected_at ?? null,
    freshness_expires_at: envelopeFreshness?.freshness_expires_at ?? null,
    source_count: summary?.source_count ?? null,
  };
}

function regionExplanationEvidence(
  region: RegionDetail,
  envelope?: ApiEnvelope<RegionDetail> | null,
  source?: SourceExplanation | null,
): ExplanationEvidencePacket {
  const freshness = explanationFreshness(envelope, source);
  return {
    entity_type: "region",
    subject_refs: { region_id: region.region_id },
    display_label: region.display_name,
    canonical_scores: Object.fromEntries(
      SCORE_FIELDS.map((score) => {
        const value = region.scores?.[score.key];
        return [score.key, typeof value === "number" ? value : null];
      }),
    ) as Record<string, number | null>,
    freshness,
    source_refs: sourceRefsFromExplanation(source),
    missing_data: missingScoreLabels(region.scores),
    unsupported_data: [
      "historical trend",
      "map geometry",
      "opportunity heatmap density",
      "company-region network layout",
    ],
    demo_or_seeded: Boolean(
      freshness?.freshness_status === "seeded_demo"
        || freshness?.data_basis === "seeded_demo",
    ),
    notes: ["Current snapshot only"],
  };
}

function companyExplanationEvidence(
  company: CompanyDetail,
  envelope?: ApiEnvelope<CompanyDetail> | null,
  source?: SourceExplanation | null,
): ExplanationEvidencePacket {
  const freshness = explanationFreshness(envelope, source);
  const missingData = [
    company.prestige_score === null ? "prestige score" : null,
    (company.regions_present ?? []).length ? null : "presence rows",
    (company.regions_hiring ?? []).length ? null : "hiring rows",
    (company.entry_level_regions ?? []).length ? null : "entry-level rows",
  ].filter(Boolean) as string[];
  return {
    entity_type: "company",
    subject_refs: { company_id: company.company_id },
    display_label: company.company_name,
    canonical_scores: { prestige_score: company.prestige_score },
    freshness,
    source_refs: sourceRefsFromExplanation(source),
    missing_data: missingData,
    unsupported_data: ["market-wide company ranking", "unobserved region presence"],
    demo_or_seeded: Boolean(
      freshness?.freshness_status === "seeded_demo"
        || freshness?.data_basis === "seeded_demo",
    ),
    notes: [
      `Presence rows: ${(company.regions_present ?? []).length}`,
      `Hiring rows: ${(company.regions_hiring ?? []).length}`,
      `Entry-level rows: ${(company.entry_level_regions ?? []).length}`,
    ],
  };
}

function comparisonExplanationEvidence(
  comparison: ComparisonDetail,
  envelope?: ApiEnvelope<ComparisonDetail> | null,
  sourceA?: SourceExplanation | null,
  sourceB?: SourceExplanation | null,
): ExplanationEvidencePacket {
  const freshness = explanationFreshness(envelope, sourceA ?? sourceB);
  const missing = [
    ...missingScoreLabels(comparison.region_a?.scores).map((label) => `Region A ${label}`),
    ...missingScoreLabels(comparison.region_b?.scores).map((label) => `Region B ${label}`),
  ];
  return {
    entity_type: "comparison",
    subject_refs: compactSubjectRefs({
      comparison_id: comparison.comparison_id,
      region_a: comparison.region_a?.region_id ?? "",
      region_b: comparison.region_b?.region_id ?? "",
    }),
    display_label: `${comparison.region_a?.display_name ?? "Region A"} vs ${comparison.region_b?.display_name ?? "Region B"}`,
    canonical_scores: {
      region_a_objective_opportunity_score: comparison.region_a?.scores?.objective_opportunity_score ?? null,
      region_b_objective_opportunity_score: comparison.region_b?.scores?.objective_opportunity_score ?? null,
      region_a_early_career_accessibility_score: comparison.region_a?.scores?.early_career_accessibility_score ?? null,
      region_b_early_career_accessibility_score: comparison.region_b?.scores?.early_career_accessibility_score ?? null,
    },
    freshness,
    source_refs: [
      ...sourceRefsFromExplanation(sourceA),
      ...sourceRefsFromExplanation(sourceB),
    ],
    missing_data: missing,
    unsupported_data: ["historical trend", "geographic distance or commute comparison"],
    notes: comparison.notes ?? [],
  };
}

function alertExplanationEvidence(alert: UserAlert): ExplanationEvidencePacket {
  const summary = alert.event.change_summary;
  const changedFields = summary && !Array.isArray(summary) && Array.isArray(summary.changed_fields)
    ? summary.changed_fields.filter((item): item is string => typeof item === "string")
    : [];
  return {
    entity_type: "alert",
    subject_refs: compactSubjectRefs({
      user_alert_id: alert.user_alert_id,
      alert_event_id: alert.alert_event_id,
      company_id: alert.event.company_id ?? "",
      region_id: alert.event.region_id ?? "",
    }),
    display_label: alertEventLabel(alert),
    freshness: {
      freshness_status: alert.event.freshness_status,
      freshness_expires_at: alert.event.freshness_expires_at,
      last_updated_at: alert.event.freshness_observed_at,
      source_count: alert.event.source_refs.length,
    },
    source_refs: [...alert.event.source_refs, ...alert.event.change_basis_refs],
    alert: {
      event_type: alert.event.event_type,
      relevance_reason: alert.relevance.reason,
      changed_fields: changedFields,
      detection_basis: alert.event.detection_basis,
    },
    watchlist_context: [
      alert.relevance.reason,
      alert.relevance.artifact_type ?? "",
      alert.relevance.artifact_ref ?? "",
    ].filter(Boolean),
    missing_data: alert.event.freshness_status ? [] : ["freshness status"],
    unsupported_data: ["unobserved future hiring changes"],
  };
}

function recommendationNotes(notes: string[] | undefined): string[] {
  return notes?.length ? notes : ["The API did not return detailed match notes for this recommendation."];
}

function preferenceInfluencesForCompany(
  company: NonNullable<PersonalizedResult["ranked_companies"]>[number],
): Array<{ label: string; value: number }> {
  return [
    { label: "Role preference", value: company.role_fit },
    { label: "Industry preference", value: company.industry_fit },
    { label: "Prestige preference", value: company.prestige_fit },
    { label: "Brand preference", value: company.brand_fit },
  ].filter((item) => typeof item.value === "number");
}

function sourceForRegion(
  regionId: string,
  sourceStates: Record<string, LoadState<SourceExplanation>>,
): SourceExplanation | null {
  return sourceStates[regionId]?.envelope?.data ?? null;
}

function strongestCompanyRegions(
  company: CompanyDetail,
  geography?: CompanyGeographyResponse | null,
): Array<{
  regionId: string;
  regionName: string;
  signalCount: number;
  signals: string[];
  entryScore: number | null;
  activePostings: number | null;
  freshness?: FreshnessSourceSummary;
  coverage?: CoverageMetadata;
  sectorCoverage?: SectorCoverageMap;
  priorityMarket?: PriorityMarket | null;
}> {
  const regions = new Map<string, {
    regionId: string;
    regionName: string;
    signals: Set<string>;
    entryScore: number | null;
    activePostings: number | null;
    freshness?: FreshnessSourceSummary;
    coverage?: CoverageMetadata;
    sectorCoverage?: SectorCoverageMap;
    priorityMarket?: PriorityMarket | null;
  }>();

  function ensure(regionId: string, regionName: string) {
    const current = regions.get(regionId);
    if (current) return current;
    const next: {
      regionId: string;
      regionName: string;
      signals: Set<string>;
      entryScore: number | null;
      activePostings: number | null;
      freshness?: FreshnessSourceSummary;
      coverage?: CoverageMetadata;
      sectorCoverage?: SectorCoverageMap;
      priorityMarket?: PriorityMarket | null;
    } = {
      regionId,
      regionName,
      signals: new Set<string>(),
      entryScore: null,
      activePostings: null,
    };
    regions.set(regionId, next);
    return next;
  }

  for (const row of company.regions_present ?? []) {
    if (row.presence_status === "present") {
      const item = ensure(row.region_id, row.region_display_name);
      item.coverage ??= row.coverage;
      item.sectorCoverage ??= row.sector_coverage;
      item.priorityMarket ??= row.priority_market;
      item.signals.add("Presence");
    }
  }

  for (const row of company.regions_hiring ?? []) {
    const item = ensure(row.region_id, row.region_display_name);
    item.activePostings = row.active_posting_count_now;
    item.coverage ??= row.coverage;
    item.sectorCoverage ??= row.sector_coverage;
    item.priorityMarket ??= row.priority_market;
    if (row.currently_hiring_flag || (row.active_posting_count_now ?? 0) > 0) {
      item.signals.add("Hiring activity");
    }
  }

  for (const row of company.entry_level_regions ?? []) {
    const item = ensure(row.region_id, row.region_display_name);
    item.entryScore = row.entry_level_access_score;
    item.coverage ??= row.coverage;
    item.sectorCoverage ??= row.sector_coverage;
    item.priorityMarket ??= row.priority_market;
    if (hasEntryLevelAccess(row)) {
      item.signals.add("Entry-level access");
    }
  }

  for (const row of geography?.regions ?? []) {
    const item = ensure(row.region_id, row.region_name);
    item.freshness = row.freshness;
    item.coverage ??= row.coverage;
    item.sectorCoverage ??= row.sector_coverage;
    item.priorityMarket ??= row.priority_market;
    if (row.presence_status === "present") item.signals.add("Presence");
    if (row.current_hiring) item.signals.add("Hiring activity");
    if (row.has_entry_level_access) item.signals.add("Entry-level access");
  }

  return Array.from(regions.values())
    .map((item) => ({
      regionId: item.regionId,
      regionName: item.regionName,
      signalCount: item.signals.size,
      signals: Array.from(item.signals).sort(),
      entryScore: item.entryScore,
      activePostings: item.activePostings,
      freshness: item.freshness,
      coverage: item.coverage,
      sectorCoverage: item.sectorCoverage,
      priorityMarket: item.priorityMarket,
    }))
    .filter((item) => item.signalCount > 0)
    .sort((left, right) =>
      right.signalCount - left.signalCount
      || (right.entryScore ?? -1) - (left.entryScore ?? -1)
      || (right.activePostings ?? -1) - (left.activePostings ?? -1)
      || left.regionName.localeCompare(right.regionName),
    );
}

function confidenceTone(value: string | null | undefined): "fresh" | "warning" | "unknown" {
  if (!value) return "unknown";
  if (value.includes("high")) return "fresh";
  if (value.includes("low") || value.includes("unknown")) return "warning";
  return "unknown";
}

function StateBadge({
  envelope,
  loading,
  error,
}: {
  envelope?: ApiEnvelope<unknown> | null;
  loading?: boolean;
  error?: string | null;
}) {
  const state = error ? "error" : loading ? "loading" : envelope?.metadata.state ?? "unknown";
  const className = `badge badge-${state}`;
  return <span className={className}>{state}</span>;
}

function MetadataPanel({
  envelope,
  source,
}: {
  envelope?: ApiEnvelope<unknown> | null;
  source?: SourceExplanation | FreshnessSourceSummary | null;
}) {
  const freshness = envelope?.metadata.freshness;
  const warnings = pickEnvelopeWarnings(envelope);
  const sourceSummary = getSourceSummary(source);
  const sourceDetails = source && "sources" in source ? source.sources ?? [] : [];
  const notices = qualityNotices(envelope, source);

  return (
    <div className="metadata-panel">
      <QualityBadgeRow envelope={envelope} source={source} />
      <div className="metadata-row metadata-row-secondary">
        <StateBadge envelope={envelope} />
        {warnings.length ? <span className="badge badge-warning">{warnings.length} warning(s)</span> : null}
        {sourceSummary ? <span className="badge badge-unknown">{sourceSummary.source_count} source(s)</span> : null}
      </div>
      {freshness ? (
        <div className="freshness-copy">
          <p>{freshnessText(freshness)}</p>
          <small>Updated: {formatDateTime(freshness.last_updated_at)}</small>
        </div>
      ) : null}
      {sourceSummary ? (
        <div className="freshness-copy">
          <p>
            {dataBasisLabel(sourceSummary.data_basis)} · {freshnessLabel(sourceSummary.freshness_status)}
          </p>
          <small>
            Last source collection: {formatDateTime(sourceSummary.last_collected_at)}
          </small>
        </div>
      ) : null}
      {sourceDetails.length ? (
        <details className="source-details">
          <summary>Source evidence</summary>
          <div className="source-list">
            {sourceDetails.map((item) => (
              <div className="source-row" key={item.source_id}>
                <strong>{item.source_name}</strong>
                <span>
                  {prettyKey(item.source_type)} · {dataBasisLabel(item.data_basis)} ·{" "}
                  {freshnessLabel(item.freshness_status)}
                </span>
                <small>{item.url ?? "No source URL/provider returned"}</small>
              </div>
            ))}
          </div>
        </details>
      ) : null}
      {notices.length || warnings.length ? (
        <div className="warning-list">
          {notices.map((notice) => (
            <div className="warning-item" key={notice}>
              <div className="warning-header">
                <span className="warning-code">Data quality note</span>
              </div>
              <p>{notice}</p>
            </div>
          ))}
          {warnings.map((warning, index) => (
            <div className="warning-item" key={index}>
              <div className="warning-header">
                <span className="warning-code">{prettyKey(warningCode(warning))}</span>
                {warningSeverity(warning) ? (
                  <span className="badge badge-warning">{warningSeverity(warning)}</span>
                ) : null}
              </div>
              <p>{warningMessage(warning)}</p>
              {warningScope(warning) ? <small>{warningScope(warning)}</small> : null}
              {hasStructuredWarningDetails(warning) ? (
                <details className="warning-debug">
                  <summary>Details</summary>
                  <pre>{JSON.stringify(warning, null, 2)}</pre>
                </details>
              ) : null}
            </div>
          ))}
        </div>
      ) : (
        <p className="meta-copy">No metadata warnings or source caveats were returned.</p>
      )}
    </div>
  );
}

function ShellCard({
  title,
  eyebrow,
  action,
  children,
}: {
  title: string;
  eyebrow?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="card">
      <div className="card-header">
        <div>
          {eyebrow ? <p className="card-eyebrow">{eyebrow}</p> : null}
          <h2>{title}</h2>
        </div>
        {action ? <div className="card-action">{action}</div> : null}
      </div>
      {children}
    </section>
  );
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <p>{body}</p>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="error-state">
      <strong>Request failed</strong>
      <p>{message}</p>
    </div>
  );
}

function LoadingBlock({ label = "Loading data" }: { label?: string }) {
  return (
    <div className="loading-block">
      <span />
      {label}
    </div>
  );
}

function AuthStatusPanel({
  auth,
  onOpenAccount,
}: {
  auth: FrontendAuthContextValue;
  onOpenAccount: () => void;
}) {
  if (!auth.isConfigured) {
    return (
      <div className="auth-panel">
        <span className="badge badge-unknown">Local account mode</span>
        <p>Auth0 frontend config is not set. Public market exploration remains available.</p>
      </div>
    );
  }

  if (auth.isLoading) {
    return (
      <div className="auth-panel">
        <span className="badge badge-loading">Checking account</span>
      </div>
    );
  }

  if (!auth.isAuthenticated) {
    return (
      <div className="auth-panel">
        <span className="badge">Signed out</span>
        <p>Sign in to save personal overlays.</p>
        <button className="secondary-button" type="button" onClick={() => void auth.login()}>
          Sign in
        </button>
      </div>
    );
  }

  return (
    <div className="auth-panel">
      <span className="badge badge-success">Signed in</span>
      <strong>{auth.user?.name ?? auth.user?.email ?? "Auth0 user"}</strong>
      <div className="auth-actions">
        <button className="secondary-button" type="button" onClick={onOpenAccount}>
          Account
        </button>
        <button className="secondary-button" type="button" onClick={auth.logout}>
          Sign out
        </button>
      </div>
    </div>
  );
}

type LinkClickHandler = (event: MouseEvent<HTMLAnchorElement>, url: string) => void;

function DemoDisclosure({ compact = false }: { compact?: boolean }) {
  return (
    <aside className={compact ? "demo-disclosure demo-disclosure-compact" : "demo-disclosure"}>
      <div>
        <strong>{DEMO_DISCLOSURE_COPY.title}</strong>
        <p>{DEMO_DISCLOSURE_COPY.summary}</p>
      </div>
      {!compact ? (
        <ul>
          {DEMO_DISCLOSURE_COPY.bullets.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
    </aside>
  );
}

function PublicInfoLinks({
  activePage,
  onNavigate,
  variant,
  includeOverview = false,
}: {
  activePage: PublicPage | null;
  onNavigate: LinkClickHandler;
  variant: "sidebar" | "footer" | "top";
  includeOverview?: boolean;
}) {
  return (
    <nav className={`public-link-list public-link-list-${variant}`} aria-label="Public information">
      {includeOverview ? (
        <a
          className={activePage === "landing" ? "public-link-active" : ""}
          href={landingUrl()}
          onClick={(event) => onNavigate(event, landingUrl())}
        >
          Overview
        </a>
      ) : null}
      {PUBLIC_INFO_LINKS.map((item) => (
        <a
          className={activePage === item.page ? "public-link-active" : ""}
          href={item.href}
          key={item.page}
          onClick={(event) => onNavigate(event, item.href)}
        >
          {item.label}
        </a>
      ))}
    </nav>
  );
}

function PublicFooter({
  activePage,
  onNavigate,
}: {
  activePage: PublicPage | null;
  onNavigate: LinkClickHandler;
}) {
  return (
    <footer className="public-footer">
      <p>Public demo only. Verify important decisions independently.</p>
      <PublicInfoLinks activePage={activePage} includeOverview onNavigate={onNavigate} variant="footer" />
    </footer>
  );
}

function PublicShell({
  activePage,
  children,
  onNavigate,
}: {
  activePage: PublicPage;
  children: ReactNode;
  onNavigate: LinkClickHandler;
}) {
  return (
    <main className="public-shell">
      <header className="public-header">
        <a className="public-brand" href={landingUrl()} onClick={(event) => onNavigate(event, landingUrl())}>
          <span className="brand-mark">JM</span>
          <span>
            <strong>Job Market Intelligence</strong>
            <small>Opportunity geography intelligence</small>
          </span>
        </a>
        <div className="public-header-actions">
          <PublicInfoLinks activePage={activePage} onNavigate={onNavigate} variant="top" />
          <a className="primary-button" href={exploreUrl()} onClick={(event) => onNavigate(event, exploreUrl())}>
            Enter demo
          </a>
        </div>
      </header>
      <section className="public-content">
        {children}
      </section>
      <PublicFooter activePage={activePage} onNavigate={onNavigate} />
    </main>
  );
}

function LandingPage({
  onNavigate,
  unknownPath,
}: {
  onNavigate: LinkClickHandler;
  unknownPath?: string;
}) {
  return (
    <div className="public-page">
      <section className="public-intro">
        <p className="eyebrow">{LANDING_COPY.eyebrow}</p>
        <h1>{LANDING_COPY.title}</h1>
        <p className="public-lead">{LANDING_COPY.intro}</p>
        {unknownPath ? (
          <p className="meta-copy">Unknown public path opened the overview: {unknownPath}</p>
        ) : null}
        <div className="hero-actions">
          <a className="primary-button" href={exploreUrl()} onClick={(event) => onNavigate(event, exploreUrl())}>
            {LANDING_COPY.ctaLabel}
          </a>
          <a
            className="secondary-button"
            href={publicPageUrl("methodology")}
            onClick={(event) => onNavigate(event, publicPageUrl("methodology"))}
          >
            {LANDING_COPY.secondaryCtaLabel}
          </a>
        </div>
      </section>

      <DemoDisclosure />

      <section className="public-section-grid" aria-label="Demo overview">
        {LANDING_COPY.sections.map((section) => (
          <article className="public-section" key={section.title}>
            <h2>{section.title}</h2>
            <p>{section.body}</p>
          </article>
        ))}
      </section>
    </div>
  );
}

function LegalPage({ page }: { page: LegalPublicPage }) {
  const copy = LEGAL_PAGE_COPY[page];
  return (
    <div className="public-page public-document">
      <section className="public-intro public-document-intro">
        <p className="eyebrow">{copy.eyebrow}</p>
        <h1>{copy.title}</h1>
        <p className="public-lead">{copy.intro}</p>
      </section>
      <DemoDisclosure compact />
      <section className="public-document-list" aria-label={copy.title}>
        {copy.sections.map((section) => (
          <article className="public-section" key={section.title}>
            <h2>{section.title}</h2>
            <p>{section.body}</p>
            {section.bullets?.length ? (
              <ul>
                {section.bullets.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : null}
          </article>
        ))}
      </section>
    </div>
  );
}

function DevelopersPage({ onNavigate }: { onNavigate: LinkClickHandler }) {
  return (
    <div className="public-page public-document">
      <section className="public-intro public-document-intro">
        <p className="eyebrow">Developer portal</p>
        <h1>Platform API developer portal</h1>
        <p className="public-lead">
          Build against secured, versioned, public-safe market intelligence endpoints with documented authentication,
          response metadata, limits, and product contracts.
        </p>
        <div className="hero-actions">
          <a
            className="primary-button"
            href={publicPageUrl("developer-docs")}
            onClick={(event) => onNavigate(event, publicPageUrl("developer-docs"))}
          >
            Read docs
          </a>
          <a
            className="secondary-button"
            href="/api/v1/platform/docs/openapi.json"
          >
            OpenAPI JSON
          </a>
          <a
            className="secondary-button"
            href="/api/v1/platform/docs/postman.json"
          >
            Postman JSON
          </a>
        </div>
      </section>
      <section className="public-section-grid" aria-label="Developer documentation areas">
        {DEVELOPER_DOCS_NAV.slice(0, 5).map((item) => (
          <article className="public-section" key={item.page}>
            <h2>{item.label}</h2>
            <p>{DEVELOPER_DOCS_COPY[item.page].summary}</p>
            <a href={item.href} onClick={(event) => onNavigate(event, item.href)}>
              Open {item.label.toLowerCase()}
            </a>
          </article>
        ))}
      </section>
    </div>
  );
}

function DeveloperDocsPage({
  page,
  onNavigate,
}: {
  page: DeveloperDocPageKey;
  onNavigate: LinkClickHandler;
}) {
  const copy = DEVELOPER_DOCS_COPY[page];
  return (
    <div className="public-page public-document">
      <section className="public-intro public-document-intro">
        <p className="eyebrow">Platform API docs</p>
        <h1>{copy.title}</h1>
        <p className="public-lead">{copy.summary}</p>
      </section>
      <nav className="developer-doc-nav" aria-label="Developer docs">
        {DEVELOPER_DOCS_NAV.map((item) => (
          <a
            className={item.page === page ? "public-link-active" : ""}
            href={item.href}
            key={item.page}
            onClick={(event) => onNavigate(event, item.href)}
          >
            {item.label}
          </a>
        ))}
      </nav>
      <section className="public-document-list" aria-label={copy.title}>
        {copy.sections.map((section) => (
          <article className="public-section" key={section.title}>
            <h2>{section.title}</h2>
            <p>{section.body}</p>
            {section.bullets?.length ? (
              <ul>
                {section.bullets.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : null}
          </article>
        ))}
      </section>
    </div>
  );
}

function DataLicensingPage() {
  return (
    <div className="public-page public-document">
      <section className="public-intro public-document-intro">
        <p className="eyebrow">{DATA_LICENSING_COPY.eyebrow}</p>
        <h1>{DATA_LICENSING_COPY.title}</h1>
        <p className="public-lead">{DATA_LICENSING_COPY.intro}</p>
        <div className="hero-actions">
          <a className="primary-button" href="mailto:sales@example.com">
            {DATA_LICENSING_COPY.cta}
          </a>
        </div>
      </section>
      <section className="public-section-grid" aria-label="Licensed datasets">
        {DATA_LICENSING_COPY.datasets.map((dataset) => (
          <article className="public-section" key={dataset.datasetId}>
            <p className="eyebrow">{dataset.datasetId}</p>
            <h2>{dataset.title}</h2>
            <p>{dataset.description}</p>
            <dl className="authority-detail-list">
              <div>
                <dt>Sample fields</dt>
                <dd>{dataset.sampleFields.join(", ")}</dd>
              </div>
              <div>
                <dt>Source safety</dt>
                <dd>{dataset.sourceSafety}</dd>
              </div>
            </dl>
            <ul>
              {dataset.restrictions.map((restriction) => (
                <li key={restriction}>{restriction}</li>
              ))}
            </ul>
          </article>
        ))}
      </section>
    </div>
  );
}

type PlatformEmbedPage = "embed-region-comparison" | "embed-market-score-card";
type PlatformEmbedViewState = {
  loading: boolean;
  payload: PlatformEmbedPayload | null;
  denialCode: string | null;
};
type LocationWithAncestorOrigins = Location & {
  ancestorOrigins?: {
    length: number;
    [index: number]: string | undefined;
    item?: (index: number) => string | null;
  };
};

const PLATFORM_EMBED_SLUG_BY_PAGE: Record<PlatformEmbedPage, string> = {
  "embed-region-comparison": "region-comparison",
  "embed-market-score-card": "market-score-card",
};

function PlatformEmbedView({ page }: { page: PlatformEmbedPage }) {
  const productSlug = PLATFORM_EMBED_SLUG_BY_PAGE[page];
  const [state, setState] = useState<PlatformEmbedViewState>({
    loading: true,
    payload: null,
    denialCode: null,
  });

  useEffect(() => {
    let cancelled = false;
    setState({ loading: true, payload: null, denialCode: null });
    getPlatformEmbed(productSlug, readPlatformEmbedOrigin())
      .then((envelope) => {
        if (cancelled) return;
        const payload = envelope.data?.payload ?? null;
        setState({
          loading: false,
          payload,
          denialCode: payload ? null : "EMBED_POLICY_DENIED",
        });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        const denialCode = error instanceof ApiError
          ? error.envelope?.error?.code ?? "EMBED_POLICY_DENIED"
          : "EMBED_POLICY_DENIED";
        setState({ loading: false, payload: null, denialCode });
      });
    return () => {
      cancelled = true;
    };
  }, [productSlug]);

  if (state.loading) {
    return (
      <main className="embed-shell">
        <section className="embed-card" aria-label="Embed loading">
          <p className="eyebrow">Partner embed</p>
          <h1>Checking embed access</h1>
        </section>
      </main>
    );
  }

  if (!state.payload) {
    return (
      <main className="embed-shell">
        <section className="embed-card embed-denial" aria-label="Embed denied">
          <p className="eyebrow">Partner embed</p>
          <h1>Embed unavailable</h1>
          <p className="meta-copy">{state.denialCode ?? "EMBED_POLICY_DENIED"}</p>
          <p>This embed is not approved for the requesting domain.</p>
        </section>
      </main>
    );
  }

  const payload = state.payload;
  return (
    <main className="embed-shell">
      <section className="embed-card" aria-label={`${payload.title} embed`}>
        <div>
          <p className="eyebrow">Partner embed</p>
          <h1>{payload.title}</h1>
          <p className="meta-copy">{payload.attribution}</p>
        </div>
        <div className="embed-metric-grid">
          {payload.metrics.map((metric, index) => (
            <article className="public-section" key={`${payload.embed_product_id}-${index}`}>
              <h2>{String(metric.label ?? "Metric")}</h2>
              {Object.entries(metric)
                .filter(([key]) => key !== "label")
                .map(([key, value]) => (
                  <p key={key}>
                    <strong>{formatEmbedMetricKey(key)}:</strong>{" "}
                    {formatEmbedMetricValue(value)}
                  </p>
                ))}
            </article>
          ))}
        </div>
        <dl className="authority-detail-list">
          <div>
            <dt>Freshness</dt>
            <dd>{formatEmbedFreshness(payload.freshness.status)}</dd>
          </div>
          <div>
            <dt>Confidence</dt>
            <dd>{payload.confidence.label}</dd>
          </div>
          <div>
            <dt>Source summary</dt>
            <dd>
              {payload.source_summary.source_categories.join(", ")}
              {payload.source_summary.notes.length
                ? `; ${payload.source_summary.notes.join(" ")}`
                : ""}
            </dd>
          </div>
        </dl>
        <div className="warning-list" aria-label="Embed warnings">
          {payload.warnings.map((warning) => (
            <div className="warning-item" key={warning}>
              <div className="warning-header">
                <span className="warning-code">Embed warning</span>
              </div>
              <p>{warning}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}

function readPlatformEmbedOrigin(): string | null {
  const locationWithAncestors = window.location as LocationWithAncestorOrigins;
  const ancestorOrigin = locationWithAncestors.ancestorOrigins?.[0]
    ?? locationWithAncestors.ancestorOrigins?.item?.(0)
    ?? null;
  if (ancestorOrigin) return ancestorOrigin;
  if (document.referrer) return document.referrer;
  return null;
}

function formatEmbedMetricKey(value: string): string {
  return value.replace(/_/g, " ");
}

function formatEmbedMetricValue(value: string | number | boolean | null): string {
  if (typeof value === "number") return value.toFixed(2);
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return value ?? "Unknown";
}

function formatEmbedFreshness(status: string): string {
  if (status === "partial") return "Partial freshness metadata available";
  if (status === "fresh") return "Fresh metadata available";
  if (status === "stale") return "Freshness metadata is stale";
  return "Freshness metadata unavailable";
}

function publicConfidenceClass(
  confidence: PublicReport["confidence"] | PublicBenchmark["confidence"] | PublicSeoConfidence,
): string {
  if (confidence === "high") return "badge badge-success";
  if (confidence === "medium") return "badge badge-real";
  if (confidence === "low") return "badge badge-warning";
  return "badge badge-unknown";
}

function PublicReportBadgeRow({
  confidence,
  freshnessDate,
  freshnessStatus,
  warningCount,
}: {
  confidence: PublicReport["confidence"];
  freshnessDate: string;
  freshnessStatus?: FreshnessStatus;
  warningCount: number;
}) {
  return (
    <div className="metadata-row">
      <span className={publicConfidenceClass(confidence)}>
        Confidence: {segmentLabel(confidence)}
      </span>
      <span className="badge badge-unknown">
        Freshness: {freshnessStatus ? segmentLabel(freshnessStatus) : "Unknown"}
      </span>
      <span className="badge badge-unknown">Freshness date: {formatDateOnly(freshnessDate)}</span>
      {warningCount ? <span className="badge badge-warning">{warningCount} warning(s)</span> : null}
    </div>
  );
}

function PublicBenchmarkBadgeRow({
  confidence,
  freshnessDate,
  freshnessStatus,
  warningCount,
}: {
  confidence: PublicBenchmark["confidence"];
  freshnessDate: string;
  freshnessStatus?: FreshnessStatus;
  warningCount: number;
}) {
  return (
    <div className="metadata-row">
      <span className={publicConfidenceClass(confidence)}>
        Confidence: {segmentLabel(confidence)}
      </span>
      <span className="badge badge-unknown">
        Freshness: {freshnessStatus ? segmentLabel(freshnessStatus) : "Unknown"}
      </span>
      <span className="badge badge-unknown">Freshness date: {formatDateOnly(freshnessDate)}</span>
      {warningCount ? <span className="badge badge-warning">{warningCount} warning(s)</span> : null}
    </div>
  );
}

type CitationView = {
  sourceName: string;
  title: string;
  period: string;
  productAttribution: string;
  publicPath: string;
  accessedOrFreshnessDate: string;
};

type ShareSummaryView = {
  title: string;
  categoryClaim: string;
  confidenceLabel: string;
  freshnessLabel: string;
  takeaway: string;
  publicPath: string;
  warning: string;
};

type SourceAuthorityView = {
  labels: string[];
  summary: string;
};

type InstitutionalCtaView = {
  label: string;
  body: string;
  href: string;
};

function publicCitationView(citation: PublicCitation): CitationView {
  return {
    sourceName: citation.source_name,
    title: citation.title,
    period: citation.period,
    productAttribution: citation.product_attribution,
    publicPath: citation.public_path,
    accessedOrFreshnessDate: citation.accessed_or_freshness_date,
  };
}

function publicShareSummaryView(summary: PublicShareSummary): ShareSummaryView {
  return {
    title: summary.title,
    categoryClaim: summary.category_claim,
    confidenceLabel: summary.confidence_label,
    freshnessLabel: summary.freshness_label,
    takeaway: summary.takeaway,
    publicPath: summary.public_path,
    warning: summary.warning,
  };
}

function publicAuthorityView(authority: PublicSourceAuthority): SourceAuthorityView {
  return {
    labels: authority.labels,
    summary: authority.summary,
  };
}

function publicInstitutionalCtaView(cta: PublicInstitutionalCta): InstitutionalCtaView {
  return {
    label: cta.label,
    body: cta.body,
    href: cta.href,
  };
}

function CitationBlock({ citation }: { citation: CitationView }) {
  return (
    <article className="public-section authority-section">
      <h2>Suggested citation</h2>
      <p className="citation-copy">
        {citation.sourceName}. {citation.title}. {citation.period}.{" "}
        {citation.productAttribution}. {citation.publicPath}. Freshness date{" "}
        {formatDateOnly(citation.accessedOrFreshnessDate)}.
      </p>
      <dl className="authority-detail-list">
        <div>
          <dt>Source</dt>
          <dd>{citation.sourceName}</dd>
        </div>
        <div>
          <dt>Public path</dt>
          <dd>{citation.publicPath}</dd>
        </div>
        <div>
          <dt>Period</dt>
          <dd>{citation.period}</dd>
        </div>
      </dl>
    </article>
  );
}

function ShareSummaryCard({ summary }: { summary: ShareSummaryView }) {
  return (
    <article className="public-section share-summary-card">
      <h2>Share summary</h2>
      <p className="eyebrow">{summary.categoryClaim}</p>
      <strong className="share-summary-title">{summary.title}</strong>
      <div className="metadata-row">
        <span className="badge badge-warning">{summary.confidenceLabel}</span>
        <span className="badge badge-unknown">{summary.freshnessLabel}</span>
      </div>
      <p>{summary.takeaway}</p>
      <small>{summary.publicPath}</small>
      <div className="warning-list" aria-label="Share summary warning">
        <div className="warning-item">
          <div className="warning-header">
            <span className="warning-code">Share warning</span>
          </div>
          <p>{summary.warning}</p>
        </div>
      </div>
    </article>
  );
}

function SourceAuthorityLabel({ authority }: { authority: SourceAuthorityView }) {
  return (
    <article className="public-section authority-section">
      <h2>Source authority</h2>
      <div className="metadata-row">
        {authority.labels.map((label) => (
          <span className="badge badge-unknown" key={label}>{label}</span>
        ))}
      </div>
      <p>{authority.summary}</p>
    </article>
  );
}

function InstitutionalCtaBlock({
  cta,
  onNavigate,
}: {
  cta: InstitutionalCtaView;
  onNavigate: LinkClickHandler;
}) {
  return (
    <article className="public-section institutional-cta-block">
      <h2>Institutional use</h2>
      <p>{cta.body}</p>
      <a className="secondary-button" href={cta.href} onClick={(event) => onNavigate(event, cta.href)}>
        {cta.label}
      </a>
    </article>
  );
}

function PublicBenchmarksPage({
  benchmarksState,
  onNavigate,
}: {
  benchmarksState: LoadState<PublicBenchmarkListPayload>;
  onNavigate: LinkClickHandler;
}) {
  const benchmarks = benchmarksState.envelope?.data?.benchmarks ?? [];
  return (
    <div className="public-page public-document">
      <section className="public-intro public-document-intro">
        <p className="eyebrow">Public benchmarks</p>
        <h1>Career market indices</h1>
        <p className="public-lead">
          Category-defining benchmark templates for opportunity geography and career market
          intelligence. Current Layer 19C indices are demo-safe, low-confidence display artifacts
          with explicit methodology, limitations, freshness, warnings, and public provenance.
        </p>
      </section>
      <DemoDisclosure compact />
      {benchmarksState.loading ? <LoadingBlock label="Loading public benchmarks" /> : null}
      {benchmarksState.error ? <ErrorState message={benchmarksState.error} /> : null}
      {benchmarks.length ? (
        <section className="public-section-grid" aria-label="Public benchmark list">
          {benchmarks.map((benchmark) => (
            <article className="public-section public-report-card" key={benchmark.slug}>
              <div className="metadata-row">
                <span className="badge badge-real">{segmentLabel(benchmark.category)}</span>
                <span className="badge badge-unknown">{benchmark.period}</span>
              </div>
              <h2>{benchmark.name}</h2>
              <p>{benchmark.summary}</p>
              <PublicBenchmarkBadgeRow
                confidence={benchmark.confidence}
                freshnessDate={benchmark.freshness_date}
                warningCount={benchmark.warnings.length}
              />
              <a
                className="secondary-button"
                href={publicBenchmarkUrl(benchmark.slug)}
                onClick={(event) => onNavigate(event, publicBenchmarkUrl(benchmark.slug))}
              >
                View index
              </a>
            </article>
          ))}
        </section>
      ) : !benchmarksState.loading && !benchmarksState.error ? (
        <EmptyState
          title="No public benchmarks"
          body="The public benchmark registry did not return benchmark templates."
        />
      ) : null}
    </div>
  );
}

function PublicBenchmarkResultCard({ result }: { result: PublicBenchmarkMarketResult }) {
  return (
    <article className="public-section public-report-result">
      <div className="metadata-row">
        <span className="badge badge-real">
          {result.result_type === "ranked" ? `Rank ${result.rank}` : "Featured"}
        </span>
        <span className={publicConfidenceClass(result.confidence)}>
          Confidence: {segmentLabel(result.confidence)}
        </span>
        <span className="badge badge-unknown">Freshness date: {formatDateOnly(result.freshness_date)}</span>
      </div>
      <h3>{result.market_label}</h3>
      <div className="score-display-row">
        <strong>{result.score_display.label}</strong>
        <span>{result.score_display.display_value}</span>
        <small>{result.score_display.caveat}</small>
      </div>
      <p>{result.explanation}</p>
      <h4>Subscores</h4>
      <table className="benchmark-table">
        <thead>
          <tr>
            <th>Subscore</th>
            <th>Display</th>
            <th>Explanation</th>
          </tr>
        </thead>
        <tbody>
          {result.subscores.map((subscore) => (
            <tr key={subscore.key}>
              <td>{subscore.label}</td>
              <td>{subscore.display_value}</td>
              <td>{subscore.explanation}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {result.warnings.length ? (
        <div className="warning-list" aria-label={`${result.market_label} benchmark warnings`}>
          {result.warnings.map((warning) => (
            <div className="warning-item" key={warning}>
              <div className="warning-header">
                <span className="warning-code">Benchmark warning</span>
              </div>
              <p>{warning}</p>
            </div>
          ))}
        </div>
      ) : null}
    </article>
  );
}

function PublicBenchmarkDetailPage({
  detailState,
  slug,
  onNavigate,
}: {
  detailState: LoadState<PublicBenchmark>;
  slug: string;
  onNavigate: LinkClickHandler;
}) {
  const benchmark = detailState.envelope?.data ?? null;
  if (detailState.loading) {
    return <LoadingBlock label="Loading public benchmark" />;
  }
  if (detailState.error) {
    return (
      <div className="public-page public-document">
        <section className="public-intro public-document-intro">
          <p className="eyebrow">Public benchmark</p>
          <h1>Benchmark not found</h1>
          <p className="public-lead">
            No public benchmark is registered for {slug}. Use the benchmark index to choose a
            published template.
          </p>
          <a
            className="secondary-button"
            href={publicPageUrl("benchmarks")}
            onClick={(event) => onNavigate(event, publicPageUrl("benchmarks"))}
          >
            Back to benchmarks
          </a>
        </section>
        <ErrorState message={detailState.error} />
      </div>
    );
  }
  if (!benchmark) {
    return <EmptyState title="No benchmark loaded" body="The public benchmark detail has not loaded yet." />;
  }

  return (
    <div className="public-page public-document">
      <section className="public-intro public-document-intro">
        <p className="eyebrow">Public benchmark · {segmentLabel(benchmark.category)}</p>
        <h1>{benchmark.name}</h1>
        <p className="public-lead">{benchmark.summary}</p>
        <PublicBenchmarkBadgeRow
          confidence={benchmark.confidence}
          freshnessDate={benchmark.freshness_date}
          freshnessStatus={benchmark.freshness_status}
          warningCount={benchmark.warnings.length}
        />
      </section>
      <DemoDisclosure compact />
      <section className="public-document-list" aria-label={`${benchmark.name} detail`}>
        <SourceAuthorityLabel authority={publicAuthorityView(benchmark.source_authority)} />
        <ShareSummaryCard summary={publicShareSummaryView(benchmark.share_summary)} />
        <CitationBlock citation={publicCitationView(benchmark.suggested_citation)} />
        <InstitutionalCtaBlock
          cta={publicInstitutionalCtaView(benchmark.institutional_cta)}
          onNavigate={onNavigate}
        />
        <article className="public-section">
          <h2>Methodology</h2>
          <p>{benchmark.methodology_summary}</p>
        </article>
        <article className="public-section">
          <h2>Score display</h2>
          <table className="benchmark-table">
            <thead>
              <tr>
                <th>Market</th>
                <th>Result</th>
                <th>Score display</th>
                <th>Caveat</th>
              </tr>
            </thead>
            <tbody>
              {benchmark.market_results.map((result) => (
                <tr key={result.market_id}>
                  <td>{result.market_label}</td>
                  <td>{result.result_type === "ranked" ? `Rank ${result.rank}` : "Featured"}</td>
                  <td>{result.score_display.display_value}</td>
                  <td>{result.score_display.caveat}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
        <article className="public-section">
          <h2>Featured market table</h2>
          <div className="public-report-result-list">
            {benchmark.market_results.map((result) => (
              <PublicBenchmarkResultCard key={result.market_id} result={result} />
            ))}
          </div>
        </article>
        <article className="public-section">
          <h2>Limitations</h2>
          <ul>
            {benchmark.limitations.map((limitation) => (
              <li key={limitation}>{limitation}</li>
            ))}
          </ul>
        </article>
        <article className="public-section">
          <h2>Warnings</h2>
          <div className="warning-list" aria-label="Benchmark warnings">
            {benchmark.warnings.map((warning) => (
              <div className="warning-item" key={warning}>
                <div className="warning-header">
                  <span className="warning-code">Benchmark warning</span>
                </div>
                <p>{warning}</p>
              </div>
            ))}
          </div>
        </article>
        <article className="public-section">
          <h2>Source and provenance summary</h2>
          <p>
            {segmentLabel(benchmark.source_provenance_summary.data_basis)} ·{" "}
            {benchmark.source_provenance_summary.source_count} public source category reference(s)
          </p>
          <ul>
            {[
              ...benchmark.source_provenance_summary.source_categories,
              ...benchmark.source_provenance_summary.provenance_notes,
            ].map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>
        {benchmark.related_links.length ? (
          <article className="public-section">
            <h2>Related links</h2>
            <div className="public-link-list">
              {benchmark.related_links.map((link) => (
                <a href={link.href} key={`${link.link_type}:${link.href}`} onClick={(event) => onNavigate(event, link.href)}>
                  {link.label}
                </a>
              ))}
            </div>
          </article>
        ) : null}
      </section>
    </div>
  );
}

function usePublicSeoMetadata(page: PublicSeoPage | null) {
  useEffect(() => {
    if (!page || typeof document === "undefined") return;
    const previousTitle = document.title;
    const previousDescription = document
      .querySelector('meta[name="description"]')
      ?.getAttribute("content") ?? null;
    const previousCanonical = document
      .querySelector('link[rel="canonical"]')
      ?.getAttribute("href") ?? null;
    const description = ensureHeadElement("meta", "name", "description");
    description.setAttribute("content", page.seo.description);
    const canonical = ensureHeadElement("link", "rel", "canonical");
    canonical.setAttribute("href", page.seo.canonicalPath);
    document.title = page.seo.title;
    return () => {
      document.title = previousTitle;
      if (previousDescription === null) {
        description.remove();
      } else {
        description.setAttribute("content", previousDescription);
      }
      if (previousCanonical === null) {
        canonical.remove();
      } else {
        canonical.setAttribute("href", previousCanonical);
      }
    };
  }, [page]);
}

function ensureHeadElement<K extends keyof HTMLElementTagNameMap>(
  tagName: K,
  attr: string,
  value: string,
): HTMLElementTagNameMap[K] {
  const existing = document.querySelector(`${tagName}[${attr}="${value}"]`);
  if (existing) return existing as HTMLElementTagNameMap[K];
  const element = document.createElement(tagName);
  element.setAttribute(attr, value);
  document.head.appendChild(element);
  return element;
}

function PublicSeoBadgeRow({ page }: { page: PublicSeoPage }) {
  return (
    <div className="metadata-row">
      <span className={publicConfidenceClass(page.confidence)}>
        Confidence: {segmentLabel(page.confidence)}
      </span>
      <span className="badge badge-unknown">Content period: {page.contentPeriod}</span>
      <span className="badge badge-unknown">Freshness date: {formatDateOnly(page.freshnessDate)}</span>
      <span className="badge badge-warning">{page.warnings.length} warning(s)</span>
    </div>
  );
}

function PublicSeoLinkList({
  links,
  onNavigate,
}: {
  links: PublicSeoLink[];
  onNavigate: LinkClickHandler;
}) {
  if (!links.length) return null;
  return (
    <div className="public-link-list">
      {links.map((link) => (
        <a href={link.href} key={`${link.linkType}:${link.href}`} onClick={(event) => onNavigate(event, link.href)}>
          {link.label}
        </a>
      ))}
    </div>
  );
}

function PublicSeoMarketList({ page }: { page: PublicSeoPage }) {
  if (!page.featuredMarkets.length) return null;
  return (
    <article className="public-section">
      <h2>{page.pageFamily === "best_cities" ? "Featured cities" : "Market examples"}</h2>
      <div className="seo-market-grid">
        {page.featuredMarkets.map((market) => (
          <section className="seo-market-card" key={`${page.slug}:${market.marketLabel}`}>
            <div className="metadata-row">
              <span className="badge badge-real">
                {market.resultType === "ranked" ? `Rank ${market.rank}` : "Featured"}
              </span>
              {market.marketId ? <span className="badge badge-unknown">{market.marketId}</span> : null}
            </div>
            <h3>{market.marketLabel}</h3>
            <strong>{market.headline}</strong>
            <p>{market.explanation}</p>
            <div className="metadata-row">
              {market.signals.map((signal) => (
                <span className="badge badge-unknown" key={signal}>{signal}</span>
              ))}
            </div>
          </section>
        ))}
      </div>
    </article>
  );
}

function PublicSeoComparisonBlocks({ page }: { page: PublicSeoPage }) {
  if (page.pageFamily !== "city_comparison") return null;
  return (
    <>
      <article className="public-section">
        <h2>Market-by-market sections</h2>
        <div className="seo-market-grid">
          {(page.comparisonMarkets ?? []).map((market) => (
            <section className="seo-market-card" key={market.marketLabel}>
              <h3>{market.marketLabel}</h3>
              <p>{market.summary}</p>
              <strong>Best for</strong>
              <ul>
                {market.bestFor.map((item) => <li key={item}>{item}</li>)}
              </ul>
              <strong>Tradeoffs</strong>
              <ul>
                {market.tradeoffs.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </section>
          ))}
        </div>
      </article>
      <article className="public-section">
        <h2>Best-for guidance</h2>
        <ul>
          {(page.bestFor ?? []).map((item) => <li key={item}>{item}</li>)}
        </ul>
      </article>
      <article className="public-section">
        <h2>Tradeoffs</h2>
        <ul>
          {(page.tradeoffs ?? []).map((item) => <li key={item}>{item}</li>)}
        </ul>
      </article>
    </>
  );
}

function PublicSeoListingPage({ onNavigate }: { onNavigate: LinkClickHandler }) {
  return (
    <div className="public-page public-document">
      <section className="public-intro public-document-intro">
        <p className="eyebrow">Career market guides</p>
        <h1>Opportunity geography guides</h1>
        <p className="public-lead">
          Public SEO/content pages for career market intelligence. These guides use Layer 19
          language, public report links, and public benchmark links without creating production
          rankings or hidden scoring authority.
        </p>
      </section>
      <DemoDisclosure compact />
      <section className="public-section-grid" aria-label="Career market guide list">
        {PUBLIC_SEO_PAGES.map((page) => (
          <article className="public-section public-report-card" key={page.slug}>
            <div className="metadata-row">
              <span className="badge badge-real">{segmentLabel(page.pageFamily)}</span>
              <span className="badge badge-warning">Confidence: {segmentLabel(page.confidence)}</span>
            </div>
            <h2>{page.title}</h2>
            <p>{page.summary}</p>
            <a
              className="secondary-button"
              href={publicSeoPageUrl(page)}
              onClick={(event) => onNavigate(event, publicSeoPageUrl(page))}
            >
              Read guide
            </a>
          </article>
        ))}
      </section>
    </div>
  );
}

function PublicSeoDetailPage({
  page,
  slug,
  onNavigate,
}: {
  page: PublicSeoPage | null;
  slug: string;
  onNavigate: LinkClickHandler;
}) {
  usePublicSeoMetadata(page);
  if (!page) {
    return (
      <div className="public-page public-document">
        <section className="public-intro public-document-intro">
          <p className="eyebrow">Career market guide</p>
          <h1>Guide not found</h1>
          <p className="public-lead">
            No public career market guide is registered for {slug}. Use the guide index to choose
            a published public page.
          </p>
          <a
            className="secondary-button"
            href={publicPageUrl("guides")}
            onClick={(event) => onNavigate(event, publicPageUrl("guides"))}
          >
            Back to guides
          </a>
        </section>
      </div>
    );
  }

  return (
    <div className="public-page public-document">
      <section className="public-intro public-document-intro">
        <p className="eyebrow">Career market guide · {segmentLabel(page.pageFamily)}</p>
        <h1>{page.title}</h1>
        <p className="public-lead">{page.summary}</p>
        <PublicSeoBadgeRow page={page} />
      </section>
      <DemoDisclosure compact />
      <section className="public-document-list" aria-label={`${page.title} detail`}>
        <SourceAuthorityLabel authority={page.sourceAuthority} />
        <ShareSummaryCard summary={page.shareSummary} />
        <CitationBlock citation={page.suggestedCitation} />
        <InstitutionalCtaBlock cta={page.institutionalCta} onNavigate={onNavigate} />
        <article className="public-section">
          <h2>{page.pageFamily === "city_comparison" ? "Comparison summary" : page.primarySections[0]?.title ?? "Overview"}</h2>
          <p>{page.primarySections[0]?.body ?? page.summary}</p>
        </article>
        {page.primarySections.slice(1).map((section) => (
          <article className="public-section" key={section.title}>
            <h2>{section.title}</h2>
            <p>{section.body}</p>
            {section.bullets?.length ? (
              <ul>
                {section.bullets.map((item) => <li key={item}>{item}</li>)}
              </ul>
            ) : null}
          </article>
        ))}
        <PublicSeoMarketList page={page} />
        <PublicSeoComparisonBlocks page={page} />
        <article className="public-section">
          <h2>Methodology</h2>
          <p>{page.methodologySummary}</p>
          <PublicSeoLinkList links={[page.methodologyLink]} onNavigate={onNavigate} />
        </article>
        <article className="public-section">
          <h2>Limitations</h2>
          <ul>
            {page.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}
          </ul>
        </article>
        <article className="public-section">
          <h2>Warnings</h2>
          <div className="warning-list" aria-label="SEO page warnings">
            {page.warnings.map((warning) => (
              <div className="warning-item" key={warning}>
                <div className="warning-header">
                  <span className="warning-code">Guide warning</span>
                </div>
                <p>{warning}</p>
              </div>
            ))}
          </div>
        </article>
        <article className="public-section">
          <h2>Category language</h2>
          <div className="metadata-row">
            {page.canonicalCategoryLanguage.map((term) => (
              <span className="badge badge-unknown" key={term}>{term}</span>
            ))}
          </div>
        </article>
        <article className="public-section">
          <h2>Related reports</h2>
          <PublicSeoLinkList links={page.relatedReports} onNavigate={onNavigate} />
        </article>
        <article className="public-section">
          <h2>Related benchmarks</h2>
          <PublicSeoLinkList links={page.relatedBenchmarks} onNavigate={onNavigate} />
        </article>
        <article className="public-section">
          <h2>Related methodology and glossary</h2>
          <PublicSeoLinkList
            links={[...page.relatedLinks, ...relatedSeoPages(page.slug)]}
            onNavigate={onNavigate}
          />
        </article>
      </section>
    </div>
  );
}

function PublicReportsPage({
  reportsState,
  onNavigate,
}: {
  reportsState: LoadState<PublicReportListPayload>;
  onNavigate: LinkClickHandler;
}) {
  const reports = reportsState.envelope?.data?.reports ?? [];
  return (
    <div className="public-page public-document">
      <section className="public-intro public-document-intro">
        <p className="eyebrow">Public reports</p>
        <h1>Market intelligence reports</h1>
        <p className="public-lead">
          Recurring public report templates for opportunity geography and career market intelligence.
          Current Layer 19B reports are demo-safe artifacts with explicit methodology, limitations,
          freshness, confidence, warnings, and public provenance summaries.
        </p>
      </section>
      <DemoDisclosure compact />
      {reportsState.loading ? <LoadingBlock label="Loading public reports" /> : null}
      {reportsState.error ? <ErrorState message={reportsState.error} /> : null}
      {reports.length ? (
        <section className="public-section-grid" aria-label="Public report list">
          {reports.map((report) => (
            <article className="public-section public-report-card" key={report.slug}>
              <div className="metadata-row">
                <span className="badge badge-real">{segmentLabel(report.category)}</span>
                <span className="badge badge-unknown">{report.report_period}</span>
              </div>
              <h2>{report.title}</h2>
              <p>{report.summary}</p>
              <PublicReportBadgeRow
                confidence={report.confidence}
                freshnessDate={report.freshness_date}
                warningCount={report.warnings.length}
              />
              <a
                className="secondary-button"
                href={publicReportUrl(report.slug)}
                onClick={(event) => onNavigate(event, publicReportUrl(report.slug))}
              >
                Read report
              </a>
            </article>
          ))}
        </section>
      ) : !reportsState.loading && !reportsState.error ? (
        <EmptyState
          title="No public reports"
          body="The public report registry did not return report templates."
        />
      ) : null}
    </div>
  );
}

function PublicReportResultCard({ result }: { result: PublicReportMarketResult }) {
  return (
    <article className="public-section public-report-result">
      <div className="metadata-row">
        <span className="badge badge-real">{result.result_type === "ranked" ? `Rank ${result.rank}` : "Featured"}</span>
        <span className={publicConfidenceClass(result.confidence)}>
          Confidence: {segmentLabel(result.confidence)}
        </span>
        <span className="badge badge-unknown">Freshness date: {formatDateOnly(result.freshness_date)}</span>
      </div>
      <h2>{result.market_label}</h2>
      <strong>{result.headline}</strong>
      <p>{result.rationale}</p>
      <div className="metadata-row">
        {result.evidence_signals.map((signal) => (
          <span className="badge badge-unknown" key={signal}>{signal}</span>
        ))}
      </div>
      {result.warnings.length ? (
        <div className="warning-list" aria-label={`${result.market_label} warnings`}>
          {result.warnings.map((warning) => (
            <div className="warning-item" key={warning}>
              <div className="warning-header">
                <span className="warning-code">Warning</span>
              </div>
              <p>{warning}</p>
            </div>
          ))}
        </div>
      ) : null}
    </article>
  );
}

function PublicReportDetailPage({
  detailState,
  slug,
  onNavigate,
}: {
  detailState: LoadState<PublicReport>;
  slug: string;
  onNavigate: LinkClickHandler;
}) {
  const report = detailState.envelope?.data ?? null;
  if (detailState.loading) {
    return <LoadingBlock label="Loading public report" />;
  }
  if (detailState.error) {
    return (
      <div className="public-page public-document">
        <section className="public-intro public-document-intro">
          <p className="eyebrow">Public report</p>
          <h1>Report not found</h1>
          <p className="public-lead">
            No public report is registered for {slug}. Use the report index to choose a published template.
          </p>
          <a className="secondary-button" href={publicPageUrl("reports")} onClick={(event) => onNavigate(event, publicPageUrl("reports"))}>
            Back to reports
          </a>
        </section>
        <ErrorState message={detailState.error} />
      </div>
    );
  }
  if (!report) {
    return <EmptyState title="No report loaded" body="The public report detail has not loaded yet." />;
  }

  return (
    <div className="public-page public-document">
      <section className="public-intro public-document-intro">
        <p className="eyebrow">Public report · {segmentLabel(report.category)}</p>
        <h1>{report.title}</h1>
        <p className="public-lead">{report.summary}</p>
        <PublicReportBadgeRow
          confidence={report.confidence}
          freshnessDate={report.freshness_date}
          freshnessStatus={report.freshness_status}
          warningCount={report.warnings.length}
        />
      </section>
      <DemoDisclosure compact />
      <section className="public-document-list" aria-label={`${report.title} detail`}>
        <SourceAuthorityLabel authority={publicAuthorityView(report.source_authority)} />
        <ShareSummaryCard summary={publicShareSummaryView(report.share_summary)} />
        <CitationBlock citation={publicCitationView(report.suggested_citation)} />
        <InstitutionalCtaBlock
          cta={publicInstitutionalCtaView(report.institutional_cta)}
          onNavigate={onNavigate}
        />
        <article className="public-section">
          <h2>Methodology</h2>
          <p>{report.methodology_summary}</p>
        </article>
        <article className="public-section">
          <h2>Markets covered</h2>
          <ul>
            {report.markets_covered.map((market) => (
              <li key={market.market_id}>
                <strong>{market.market_label}</strong>: {market.coverage_note}
              </li>
            ))}
          </ul>
        </article>
        <article className="public-section">
          <h2>Featured market results</h2>
          <div className="public-report-result-list">
            {report.market_results.map((result) => (
              <PublicReportResultCard key={result.market_id} result={result} />
            ))}
          </div>
        </article>
        <article className="public-section">
          <h2>Limitations</h2>
          <ul>
            {report.limitations.map((limitation) => (
              <li key={limitation}>{limitation}</li>
            ))}
          </ul>
        </article>
        <article className="public-section">
          <h2>Warnings</h2>
          {report.warnings.length ? (
            <div className="warning-list" aria-label="Report warnings">
              {report.warnings.map((warning) => (
                <div className="warning-item" key={warning}>
                  <div className="warning-header">
                    <span className="warning-code">Report warning</span>
                  </div>
                  <p>{warning}</p>
                </div>
              ))}
            </div>
          ) : (
            <p>No report warnings were returned.</p>
          )}
        </article>
        <article className="public-section">
          <h2>Source and provenance summary</h2>
          <p>
            {segmentLabel(report.source_provenance_summary.data_basis)} ·{" "}
            {report.source_provenance_summary.source_count} public source category reference(s)
          </p>
          <ul>
            {[
              ...report.source_provenance_summary.source_categories,
              ...report.source_provenance_summary.provenance_notes,
            ].map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>
        {report.related_links.length ? (
          <article className="public-section">
            <h2>Related links</h2>
            <div className="public-link-list">
              {report.related_links.map((link) => (
                <a href={link.href} key={`${link.link_type}:${link.href}`} onClick={(event) => onNavigate(event, link.href)}>
                  {link.label}
                </a>
              ))}
            </div>
          </article>
        ) : null}
      </section>
    </div>
  );
}

function PredictiveForecastCard({ forecast }: { forecast: PredictiveReportForecast }) {
  return (
    <article className="public-section public-report-result forecast-card">
      <div className="metadata-row">
        <span className="badge badge-real">Forecast</span>
        <span className={publicConfidenceClass(forecast.confidence.level)}>
          Confidence: {segmentLabel(forecast.confidence.level)} ({Math.round(forecast.confidence.score * 100)}%)
        </span>
        <span className="badge badge-unknown">
          Time horizon: {segmentLabel(forecast.time_horizon)}
        </span>
      </div>
      <h2>{forecast.forecast_title}</h2>
      <strong>{forecast.forecast_label}</strong>
      <p>{forecast.safe_display_summary}</p>
      <p className="meta-copy">{forecast.why_this_forecast_exists}</p>
      <div className="metadata-row">
        <span className="badge badge-unknown">
          Historical depth: {forecast.historical_depth.observation_count} observation(s)
        </span>
        <span className="badge badge-unknown">
          Source basis: {forecast.source_basis.source_count} signal input(s)
        </span>
        <span className="badge badge-unknown">
          Uncertainty: {segmentLabel(forecast.uncertainty.level)}
        </span>
      </div>
      <div className="forecast-detail-grid">
        <section className="forecast-detail-block">
          <h3>Source basis</h3>
          <p>
            {segmentLabel(forecast.source_basis.data_basis)} -{" "}
            {forecast.source_basis.source_categories.map(segmentLabel).join(", ") || "No source categories"}
          </p>
          <p className="meta-copy">
            Window: {formatDateOnly(forecast.historical_depth.window_start)} to{" "}
            {formatDateOnly(forecast.historical_depth.window_end)}
          </p>
        </section>
        <section className="forecast-detail-block">
          <h3>Uncertainty</h3>
          <ul>
            {forecast.uncertainty.known_uncertainties.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
        <section className="forecast-detail-block">
          <h3>Reasoning trail</h3>
          <ol>
            {forecast.reasoning_trail.map((step) => (
              <li key={step.code}>{step.summary}</li>
            ))}
          </ol>
        </section>
        <section className="forecast-detail-block">
          <h3>Supporting signals</h3>
          <ul>
            {forecast.supporting_signals.map((signal) => (
              <li key={signal.signal_key}>
                <strong>{segmentLabel(signal.signal_kind)}</strong>:{" "}
                {segmentLabel(signal.signal_type)} - {segmentLabel(signal.signal_status)}.{" "}
                {signal.summary}
              </li>
            ))}
          </ul>
        </section>
      </div>
    </article>
  );
}

function PredictiveReportSectionBlock({ section }: { section: PredictiveReportSection }) {
  return (
    <article className="public-section">
      <h2>{section.title}</h2>
      <p>{section.summary}</p>
      <p className="meta-copy">{section.why_this_section_exists}</p>
      {section.forecasts.length ? (
        <div className="public-report-result-list">
          {section.forecasts.map((forecast) => (
            <PredictiveForecastCard forecast={forecast} key={forecast.forecast_id} />
          ))}
        </div>
      ) : (
        <EmptyState
          title="No forecast emitted"
          body="The available historical evidence did not produce a forecast for this section."
        />
      )}
    </article>
  );
}

function PredictiveReportsPage({
  reportState,
}: {
  reportState: LoadState<PredictiveReportPayload>;
}) {
  const report = reportState.envelope?.data ?? null;
  return (
    <div className="public-page public-document">
      <section className="public-intro public-document-intro">
        <p className="eyebrow">Predictive reports</p>
        <h1>Labor-market forecasts</h1>
        <p className="public-lead">
          Forecast cards translate historical trend, emerging-market, and warning signals
          into bounded directional intelligence with confidence, uncertainty, source basis,
          historical depth, and reasoning trail.
        </p>
      </section>
      <DemoDisclosure compact />
      {reportState.loading ? <LoadingBlock label="Loading predictive forecasts" /> : null}
      {reportState.error ? <ErrorState message={reportState.error} /> : null}
      {report ? (
        <section className="public-document-list" aria-label={`${report.title} detail`}>
          <article className="public-section">
            <div className="metadata-row">
              <span className="badge badge-real">Forecast report</span>
              <span className="badge badge-unknown">Generated: {formatDateTime(report.generated_at)}</span>
              <span className="badge badge-unknown">Horizon: {segmentLabel(report.time_horizon)}</span>
            </div>
            <h2>{report.title}</h2>
            <p>{report.forecast_disclaimer}</p>
            <p>{report.methodology_summary}</p>
          </article>
          {report.sections.map((section) => (
            <PredictiveReportSectionBlock section={section} key={section.section_key} />
          ))}
          <article className="public-section">
            <h2>Limitations</h2>
            <ul>
              {report.limitations.map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
          </article>
        </section>
      ) : !reportState.loading && !reportState.error ? (
        <EmptyState
          title="No predictive report loaded"
          body="The predictive report endpoint did not return a report payload."
        />
      ) : null}
    </div>
  );
}

function PublicRouteView({
  route,
  onNavigate,
  publicBenchmarkListState,
  publicBenchmarkDetailState,
  publicReportListState,
  publicReportDetailState,
  predictiveReportState,
}: {
  route: RouteState;
  onNavigate: LinkClickHandler;
  publicBenchmarkListState: LoadState<PublicBenchmarkListPayload>;
  publicBenchmarkDetailState: LoadState<PublicBenchmark>;
  publicReportListState: LoadState<PublicReportListPayload>;
  publicReportDetailState: LoadState<PublicReport>;
  predictiveReportState: LoadState<PredictiveReportPayload>;
}) {
  if (route.page === "embed-region-comparison" || route.page === "embed-market-score-card") {
    return <PlatformEmbedView page={route.page} />;
  }
  const activePage = route.page as PublicPage;
  return (
    <PublicShell activePage={activePage} onNavigate={onNavigate}>
      <LazyRoute>
        {activePage === "landing" ? (
          <LandingPage onNavigate={onNavigate} unknownPath={route.unknownPath} />
        ) : activePage === "developers" ? (
          <DevelopersPage onNavigate={onNavigate} />
        ) : activePage === "data-licensing" ? (
          <DataLicensingPage />
        ) : activePage === "data-standards" ? (
          <DataStandardsPage />
        ) : isDeveloperDocPage(activePage) ? (
          <DeveloperDocsPage page={activePage} onNavigate={onNavigate} />
        ) : activePage === "guides" ? (
          route.seoPageSlug ? (
            <PublicSeoDetailPage
              onNavigate={onNavigate}
              page={getPublicSeoPageBySlug(route.seoPageSlug)}
              slug={route.seoPageSlug}
            />
          ) : (
            <PublicSeoListingPage onNavigate={onNavigate} />
          )
        ) : activePage === "benchmarks" ? (
          route.benchmarkSlug ? (
            <PublicBenchmarkDetailPage
              detailState={publicBenchmarkDetailState}
              onNavigate={onNavigate}
              slug={route.benchmarkSlug}
            />
          ) : (
            <PublicBenchmarksPage
              benchmarksState={publicBenchmarkListState}
              onNavigate={onNavigate}
            />
          )
        ) : activePage === "reports" ? (
          route.reportSlug ? (
            <PublicReportDetailPage
              detailState={publicReportDetailState}
              onNavigate={onNavigate}
              slug={route.reportSlug}
            />
          ) : (
            <PublicReportsPage
              onNavigate={onNavigate}
              reportsState={publicReportListState}
            />
          )
        ) : activePage === "forecasts" ? (
          <PredictiveReportsPage reportState={predictiveReportState} />
        ) : (
          <LegalPage page={activePage as LegalPublicPage} />
        )}
      </LazyRoute>
    </PublicShell>
  );
}

function RouteLoadingFallback() {
  return (
    <div className="route-loading-state" role="status" aria-live="polite">
      Loading workspace
    </div>
  );
}

function LazyRoute({ children }: { children: ReactNode }) {
  return <Suspense fallback={<RouteLoadingFallback />}>{children}</Suspense>;
}

function isDeveloperDocPage(page: PublicPage): page is DeveloperDocPageKey {
  return page.startsWith("developer-doc");
}

function JsonBlock({ value }: { value: unknown }) {
  return <pre className="json-block">{JSON.stringify(value, null, 2)}</pre>;
}

function alertEventLabel(alert: UserAlert): string {
  return prettyKey(alert.event.event_type);
}

function alertFreshnessText(alert: UserAlert): string {
  const status = alert.event.freshness_status ? prettyKey(alert.event.freshness_status) : "Freshness unknown";
  const observed = formatDateTime(alert.event.freshness_observed_at);
  const expires = formatDateTime(alert.event.freshness_expires_at);
  if (alert.event.freshness_observed_at || alert.event.freshness_expires_at) {
    return `${status} · observed ${observed} · expires ${expires}`;
  }
  return status;
}

function alertScopeText(alert: UserAlert): string {
  const parts = [
    alert.event.company_id ? `Company ${alert.event.company_id}` : null,
    alert.event.region_id ? `Region ${alert.event.region_id}` : null,
    alert.event.role_family ? `Role ${alert.event.role_family}` : null,
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : "System event";
}

function alertChangeText(alert: UserAlert): string {
  const summary = alert.event.change_summary;
  if (!summary || Array.isArray(summary)) return "Structured change metadata only.";
  const changed = Array.isArray(summary.changed_fields)
    ? summary.changed_fields.join(", ")
    : null;
  return changed ? `Changed fields: ${changed}` : "Structured change metadata only.";
}

function ApiAccessAndCareerPlatformPanel({
  apiClientCreateState,
  apiClientListState,
  apiKeyCreateState,
  apiUsageState,
  careerPlatformRegistryState,
  careerPlatformExportState,
  onCreateApiClient,
  onCreateApiKey,
  onRevokeApiKey,
  onLoadApiUsage,
  onRefreshApiClients,
  onRefreshCareerPlatforms,
  onCreateCareerPlatformExport,
}: {
  apiClientCreateState: LoadState<ApiClientCreatePayload>;
  apiClientListState: LoadState<ApiClientListPayload>;
  apiKeyCreateState: LoadState<ApiKeyCreatePayload>;
  apiUsageState: LoadState<ApiUsageListPayload>;
  careerPlatformRegistryState: LoadState<CareerPlatformRegistryPayload>;
  careerPlatformExportState: LoadState<CareerPlatformExportPayload>;
  onCreateApiClient: (request: ApiClientCreateRequest) => void;
  onCreateApiKey: (apiClientId: string) => void;
  onRevokeApiKey: (apiKeyId: string) => void;
  onLoadApiUsage: (apiClientId: string) => void;
  onRefreshApiClients: () => void;
  onRefreshCareerPlatforms: () => void;
  onCreateCareerPlatformExport: (request: CareerPlatformExportRequest) => void;
}) {
  const [formState, setFormState] = useState<ApiAccessFormState>({
    ...DEFAULT_API_ACCESS_FORM_STATE,
  });
  const clients = apiClientListState.envelope?.data?.api_clients ?? [];
  const registry = careerPlatformRegistryState.envelope?.data?.platforms ?? [];
  const createdClient = apiClientCreateState.envelope?.data?.api_client ?? null;
  const revealedKey = apiKeyCreateState.envelope?.data?.api_key ?? null;
  const latestPlatformExport = careerPlatformExportState.envelope?.data?.export ?? null;

  function toggleScope(scope: ApiScope, checked: boolean) {
    setFormState((current) => {
      const next = checked
        ? Array.from(new Set([...current.scopes, scope]))
        : current.scopes.filter((item) => item !== scope);
      return { ...current, scopes: next };
    });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onCreateApiClient(apiClientRequestFromForm(formState));
  }

  return (
    <div className="split-grid">
      <ShellCard
        title="Controlled API Access"
        eyebrow="Layer 17C"
        action={<button className="secondary-button compact-button" type="button" onClick={onRefreshApiClients}>Refresh</button>}
      >
        <p className="meta-copy">
          API clients are scoped, rate-limited read/access surfaces. Raw API keys are shown only once.
        </p>
        <form className="account-form-grid" onSubmit={handleSubmit}>
          <label>
            Client name
            <input
              aria-label="API client name"
              onChange={(event) =>
                setFormState((current) => ({ ...current, displayName: event.target.value }))
              }
              value={formState.displayName}
            />
          </label>
          <label>
            Institution scope
            <input
              aria-label="API client institution scope"
              onChange={(event) =>
                setFormState((current) => ({ ...current, organizationId: event.target.value }))
              }
              placeholder="Optional organization id"
              value={formState.organizationId}
            />
          </label>
          <label>
            Request limit
            <input
              aria-label="API client request limit"
              min={1}
              onChange={(event) =>
                setFormState((current) => ({
                  ...current,
                  rateLimitCount: Number(event.target.value),
                }))
              }
              type="number"
              value={formState.rateLimitCount}
            />
          </label>
          <label>
            Window seconds
            <input
              aria-label="API client window seconds"
              min={60}
              onChange={(event) =>
                setFormState((current) => ({
                  ...current,
                  rateLimitWindowSeconds: Number(event.target.value),
                }))
              }
              type="number"
              value={formState.rateLimitWindowSeconds}
            />
          </label>
          <div className="wide-field checkbox-grid">
            {API_SCOPE_OPTIONS.map((option) => (
              <label className="checkbox-label" key={option.id}>
                <input
                  checked={formState.scopes.includes(option.id)}
                  onChange={(event) => toggleScope(option.id, event.target.checked)}
                  type="checkbox"
                />
                <span>{option.label}</span>
              </label>
            ))}
          </div>
          <button className="primary-button" disabled={apiClientCreateState.loading} type="submit">
            Create API client
          </button>
        </form>
        {apiClientCreateState.loading ? <LoadingBlock label="Creating API client" /> : null}
        {apiClientCreateState.error ? <ErrorState message={apiClientCreateState.error} /> : null}
        {createdClient ? (
          <div className="notice-state">
            <strong>{createdClient.display_name}</strong>
            <p>{createdClient.policy.scopes.join(", ")}</p>
          </div>
        ) : null}
        {revealedKey?.raw_key ? (
          <div className="notice-state">
            <strong>One-time API key reveal</strong>
            <p>{revealedKey.raw_key}</p>
          </div>
        ) : null}
        {apiKeyCreateState.error ? <ErrorState message={apiKeyCreateState.error} /> : null}
        {apiClientListState.loading ? <LoadingBlock label="Loading API clients" /> : null}
        {apiClientListState.error ? <ErrorState message={apiClientListState.error} /> : null}
        {clients.length ? (
          <div className="account-list">
            {clients.map((client) => (
              <div className="account-list-row" key={client.api_client_id}>
                <div>
                  <div className="metadata-row">
                    <span className={client.status === "active" ? "badge badge-success" : "badge badge-unknown"}>
                      {client.status}
                    </span>
                    <span className="badge badge-unknown">
                      {client.policy.rate_limit_count}/{client.policy.rate_limit_window_seconds}s
                    </span>
                    {client.organization_id ? (
                      <span className="badge badge-real">{client.organization_id}</span>
                    ) : null}
                  </div>
                  <strong>{client.display_name}</strong>
                  <small>{client.policy.scopes.join(", ") || "No scopes"}</small>
                  {client.keys.length ? (
                    <p className="meta-copy">
                      Keys: {client.keys.map((key) => key.display_key).join(", ")}
                    </p>
                  ) : null}
                </div>
                <div className="account-button-row">
                  <button className="secondary-button compact-button" type="button" onClick={() => onCreateApiKey(client.api_client_id)}>
                    Create key
                  </button>
                  <button className="secondary-button compact-button" type="button" onClick={() => onLoadApiUsage(client.api_client_id)}>
                    Usage
                  </button>
                  {client.keys[0] ? (
                    <button className="secondary-button compact-button" type="button" onClick={() => onRevokeApiKey(client.keys[0].api_key_id)}>
                      Revoke key
                    </button>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="meta-copy">No API clients loaded.</p>
        )}
        {apiUsageState.envelope?.data?.usage.length ? (
          <JsonBlock value={apiUsageState.envelope.data.usage.slice(0, 5)} />
        ) : null}
        {apiUsageState.error ? <ErrorState message={apiUsageState.error} /> : null}
      </ShellCard>

      <ShellCard
        title="Career Platform Registry"
        eyebrow="Manual integration posture"
        action={<button className="secondary-button compact-button" type="button" onClick={onRefreshCareerPlatforms}>Refresh</button>}
      >
        <p className="meta-copy">
          LinkedIn, Handshake, job boards, and career pages remain manual/export/deep-link workflows only.
        </p>
        <div className="metadata-row">
          <span className="badge badge-success">No scraping</span>
          <span className="badge badge-success">No application submission</span>
          <span className="badge badge-success">No ATS pipeline</span>
          <span className="badge badge-unknown">Deferred automation blocked</span>
        </div>
        <div className="integration-action-grid">
          {CAREER_PLATFORM_OPTIONS.map((option) => (
            <button
              className="secondary-button compact-button"
              key={option.id}
              onClick={() =>
                onCreateCareerPlatformExport({
                  platform: option.id,
                  employer_names: ["Alpha Systems"],
                  company_ids: [],
                })
              }
              type="button"
            >
              {option.label}
            </button>
          ))}
        </div>
        {careerPlatformRegistryState.loading ? <LoadingBlock label="Loading platform registry" /> : null}
        {careerPlatformRegistryState.error ? <ErrorState message={careerPlatformRegistryState.error} /> : null}
        {registry.length ? (
          <div className="stack-list">
            {registry.map((platform) => (
              <div className="account-list-row" key={platform.platform}>
                <div>
                  <div className="metadata-row">
                    <span className="badge badge-real">{platform.risk_posture}</span>
                    <span className="badge badge-success">Manual only {String(platform.manual_only)}</span>
                  </div>
                  <strong>{platform.display_name}</strong>
                  <small>Allowed: {platform.allowed_capabilities.join(", ") || "none"}</small>
                  <p className="meta-copy">Blocked: {platform.blocked_capabilities.join(", ")}</p>
                </div>
              </div>
            ))}
          </div>
        ) : null}
        {latestPlatformExport ? (
          <div className="notice-state">
            <strong>{latestPlatformExport.platform} export prepared</strong>
            <p>
              Manual only {String(latestPlatformExport.manual_only)} · automation{" "}
              {String(latestPlatformExport.automation_performed)} · ATS{" "}
              {String(latestPlatformExport.ats_state_created)}
            </p>
          </div>
        ) : null}
        {careerPlatformExportState.error ? <ErrorState message={careerPlatformExportState.error} /> : null}
      </ShellCard>
    </div>
  );
}

function AccountView({
  auth,
  currentUserState,
  preferenceState,
  preferenceDraft,
  artifactsState,
  alertsState,
  snapshotsState,
  scoringPreviewState,
  apiClientCreateState,
  apiClientListState,
  apiKeyCreateState,
  apiUsageState,
  careerPlatformRegistryState,
  careerPlatformExportState,
  alertExplanationStates,
  exportState,
  deactivationResult,
  actionState,
  deactivateConfirmed,
  onLogin,
  onRefresh,
  onPreferenceDraft,
  onSavePreferences,
  onPreviewScoring,
  onDeletePreferences,
  onDeleteArtifact,
  onMarkAlertRead,
  onDismissAlert,
  onExplainAlert,
  onExport,
  onCreateApiClient,
  onCreateApiKey,
  onRevokeApiKey,
  onLoadApiUsage,
  onRefreshApiClients,
  onRefreshCareerPlatforms,
  onCreateCareerPlatformExport,
  onDeactivate,
  onDeactivateConfirmed,
}: {
  auth: FrontendAuthContextValue;
  currentUserState: LoadState<CurrentUserProfile>;
  preferenceState: LoadState<UserPreferenceProfile>;
  preferenceDraft: PreferenceDraft;
  artifactsState: LoadState<{ saved_market_artifacts: SavedMarketArtifact[] }>;
  alertsState: LoadState<UserAlertList>;
  snapshotsState: LoadState<{ personalized_recommendation_snapshots: PersonalizedRecommendationSnapshot[] }>;
  scoringPreviewState: LoadState<ScoringPreviewResult>;
  apiClientCreateState: LoadState<ApiClientCreatePayload>;
  apiClientListState: LoadState<ApiClientListPayload>;
  apiKeyCreateState: LoadState<ApiKeyCreatePayload>;
  apiUsageState: LoadState<ApiUsageListPayload>;
  careerPlatformRegistryState: LoadState<CareerPlatformRegistryPayload>;
  careerPlatformExportState: LoadState<CareerPlatformExportPayload>;
  alertExplanationStates: Record<string, LoadState<ExplanationResult>>;
  exportState: LoadState<UserDataExport>;
  deactivationResult: AccountDeactivationResult | null;
  actionState: AccountActionState;
  deactivateConfirmed: boolean;
  onLogin: () => void;
  onRefresh: () => void;
  onPreferenceDraft: (draft: PreferenceDraft) => void;
  onSavePreferences: () => void;
  onPreviewScoring: () => void;
  onDeletePreferences: () => void;
  onDeleteArtifact: (savedArtifactId: string) => void;
  onMarkAlertRead: (userAlertId: string) => void;
  onDismissAlert: (userAlertId: string) => void;
  onExplainAlert: (alert: UserAlert) => void;
  onExport: () => void;
  onCreateApiClient: (request: ApiClientCreateRequest) => void;
  onCreateApiKey: (apiClientId: string) => void;
  onRevokeApiKey: (apiKeyId: string) => void;
  onLoadApiUsage: (apiClientId: string) => void;
  onRefreshApiClients: () => void;
  onRefreshCareerPlatforms: () => void;
  onCreateCareerPlatformExport: (request: CareerPlatformExportRequest) => void;
  onDeactivate: () => void;
  onDeactivateConfirmed: (confirmed: boolean) => void;
}) {
  const currentUser = currentUserState.envelope?.data;
  const preferences = preferenceState.envelope?.data;
  const artifacts = artifactsState.envelope?.data?.saved_market_artifacts ?? [];
  const alerts = alertsState.envelope?.data?.alerts ?? [];
  const groupedWatchlists = watchlistGroups(artifacts);
  const snapshots = snapshotsState.envelope?.data?.personalized_recommendation_snapshots ?? [];

  if (!auth.isConfigured) {
    return (
      <div className="view-grid">
        <ShellCard title="Account" eyebrow="Auth0 configuration required">
          <EmptyState
            title="Local demo mode"
            body="Auth0 frontend variables are not configured, so account workflows are disabled while public market exploration remains available."
          />
        </ShellCard>
      </div>
    );
  }

  if (!auth.isAuthenticated) {
    return (
      <div className="view-grid">
        <ShellCard title="Account" eyebrow="Signed out">
          <p className="lead-copy">
            Account and personalization workflows use protected /me routes. Public market
            exploration does not require sign-in.
          </p>
          <button className="primary-button" type="button" onClick={onLogin}>Sign in with Auth0</button>
        </ShellCard>
      </div>
    );
  }

  return (
    <div className="view-grid">
      {actionState.message ? (
        <div className="notice-state">
          <strong>Account update</strong>
          <p>{actionState.message}</p>
        </div>
      ) : null}
      {actionState.error ? <ErrorState message={actionState.error} /> : null}

      <div className="split-grid">
        <ShellCard
          title="Current user"
          eyebrow="Internal app account"
          action={<button className="secondary-button" type="button" onClick={onRefresh}>Refresh</button>}
        >
          {currentUserState.loading ? <LoadingBlock label="Loading account" /> : null}
          {currentUserState.error ? <ErrorState message={currentUserState.error} /> : null}
          {currentUser ? (
            <div className="account-summary">
              <div>
                <span>User ID</span>
                <strong>{currentUser.user.user_id}</strong>
              </div>
              <div>
                <span>Status</span>
                <strong>{currentUser.user.status}</strong>
              </div>
              <div>
                <span>Email</span>
                <strong>{currentUser.profile.email ?? "n/a"}</strong>
              </div>
              <div>
                <span>Display</span>
                <strong>{currentUser.profile.display_name ?? auth.user?.name ?? "n/a"}</strong>
              </div>
            </div>
          ) : null}
          <p className="meta-copy">
            Auth0 identity is mapped to this internal user. Saved overlays use the internal user id,
            not the Auth0 subject, as their durable owner.
          </p>
        </ShellCard>

        <ShellCard title="Privacy controls" eyebrow="App-owned data only">
          <p className="meta-copy">
            Export and deactivation operate on Layer 7 account data. They do not delete or change
            canonical regions, companies, objective scores, source freshness, ingestion records, or
            output metadata.
          </p>
          <div className="account-button-row">
            <button className="secondary-button" disabled={actionState.loading} type="button" onClick={onExport}>
              Export user data
            </button>
            <label className="checkbox-label">
              <input
                checked={deactivateConfirmed}
                onChange={(event) => onDeactivateConfirmed(event.target.checked)}
                type="checkbox"
              />
              <span>Confirm app account deactivation</span>
            </label>
            <button
              className="danger-button"
              disabled={!deactivateConfirmed || actionState.loading}
              type="button"
              onClick={onDeactivate}
            >
              Deactivate app account
            </button>
          </div>
          {deactivationResult ? <JsonBlock value={deactivationResult} /> : null}
        </ShellCard>
      </div>

      <ApiAccessAndCareerPlatformPanel
        apiClientCreateState={apiClientCreateState}
        apiClientListState={apiClientListState}
        apiKeyCreateState={apiKeyCreateState}
        apiUsageState={apiUsageState}
        careerPlatformExportState={careerPlatformExportState}
        careerPlatformRegistryState={careerPlatformRegistryState}
        onCreateApiClient={onCreateApiClient}
        onCreateApiKey={onCreateApiKey}
        onCreateCareerPlatformExport={onCreateCareerPlatformExport}
        onLoadApiUsage={onLoadApiUsage}
        onRefreshApiClients={onRefreshApiClients}
        onRefreshCareerPlatforms={onRefreshCareerPlatforms}
        onRevokeApiKey={onRevokeApiKey}
      />

      <ShellCard title="Alerts" eyebrow="In-app change feed">
        {alertsState.loading ? <LoadingBlock label="Loading alerts" /> : null}
        {alertsState.error ? <ErrorState message={alertsState.error} /> : null}
        <AlertSummaryVisualization alerts={alerts} />
        {alerts.length ? (
          <div className="account-list alert-feed">
            {alerts.map((alert) => (
              <div
                className={alert.is_read ? "account-list-row alert-row" : "account-list-row alert-row alert-row-unread"}
                key={alert.user_alert_id}
              >
                <div>
                  <div className="metadata-row">
                    <span className="badge">{alertEventLabel(alert)}</span>
                    <span className={alert.is_read ? "badge badge-unknown" : "badge badge-success"}>
                      {alert.is_read ? "Read" : "Unread"}
                    </span>
                    <span className="badge badge-unknown">{alertFreshnessText(alert)}</span>
                  </div>
                  <strong>{alertScopeText(alert)}</strong>
                  <small>
                    Relevance: {prettyKey(alert.relevance.reason)}
                    {alert.relevance.artifact_ref ? ` · ${alert.relevance.artifact_ref}` : ""}
                    {" · "}
                    created {formatDateTime(alert.created_at)}
                  </small>
                  <p className="meta-copy">{alertChangeText(alert)}</p>
                </div>
                <div className="alert-actions">
                  <button
                    className="secondary-button"
                    disabled={actionState.loading || alert.is_read}
                    type="button"
                    onClick={() => onMarkAlertRead(alert.user_alert_id)}
                  >
                    Mark read
                  </button>
                  <button
                    className="secondary-button"
                    disabled={actionState.loading || alert.dismissed}
                    type="button"
                    onClick={() => onDismissAlert(alert.user_alert_id)}
                  >
                    Dismiss
                  </button>
                  <button
                    className="secondary-button"
                    disabled={actionState.loading}
                    type="button"
                    onClick={() => onExplainAlert(alert)}
                  >
                    Explain
                  </button>
                </div>
                <ExplanationResultPanel
                  emptyCopy="Use Explain to render alert guidance from this alert event packet."
                  state={alertExplanationStates[alert.user_alert_id]}
                />
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No alerts"
            body="Alerts appear here when structured market changes match saved watchlists or preferences."
          />
        )}
      </ShellCard>

      <ShellCard title="Saved preferences" eyebrow="User-owned inputs">
        {preferenceState.loading ? <LoadingBlock label="Loading preferences" /> : null}
        {preferenceState.error ? <ErrorState message={preferenceState.error} /> : null}
        <p className="meta-copy">
          These inputs are personal preferences only. They do not alter objective market records.
          Current state: {preferences?.persisted ? "saved" : "empty/default"}.
        </p>
        <div className="account-form-grid">
          <label>
            Role interests
            <input
              onChange={(event) => onPreferenceDraft({ ...preferenceDraft, roleInterests: event.target.value })}
              placeholder="product, cybersecurity"
              value={preferenceDraft.roleInterests}
            />
          </label>
          <label>
            Industry interests
            <input
              onChange={(event) => onPreferenceDraft({ ...preferenceDraft, industryInterests: event.target.value })}
              placeholder="software, ai, cloud"
              value={preferenceDraft.industryInterests}
            />
          </label>
          <label>
            Preferred regions
            <input
              onChange={(event) => onPreferenceDraft({ ...preferenceDraft, preferredRegions: event.target.value })}
              placeholder="greater_boston, sf_bay_area"
              value={preferenceDraft.preferredRegions}
            />
          </label>
          <label>
            Prestige weighting
            <select
              value={preferenceDraft.prestigeWeighting}
              onChange={(event) =>
                onPreferenceDraft({
                  ...preferenceDraft,
                  prestigeWeighting: event.target.value as PreferenceDraft["prestigeWeighting"],
                })
              }
            >
              <option value="">No saved weighting</option>
              {PREFERENCE_LEVELS.map((level) => (
                <option key={level} value={level}>{level}</option>
              ))}
            </select>
          </label>
          <label>
            Brand weighting
            <select
              value={preferenceDraft.brandWeighting}
              onChange={(event) =>
                onPreferenceDraft({
                  ...preferenceDraft,
                  brandWeighting: event.target.value as PreferenceDraft["brandWeighting"],
                })
              }
            >
              <option value="">No saved weighting</option>
              {PREFERENCE_LEVELS.map((level) => (
                <option key={level} value={level}>{level}</option>
              ))}
            </select>
          </label>
          <label>
            Career stage
            <select
              value={preferenceDraft.careerStage}
              onChange={(event) =>
                onPreferenceDraft({
                  ...preferenceDraft,
                  careerStage: event.target.value as PreferenceDraft["careerStage"],
                })
              }
            >
              <option value="">No saved stage</option>
              {CAREER_STAGE_OPTIONS.map((stage) => (
                <option key={stage} value={stage}>{prettyKey(stage)}</option>
              ))}
            </select>
          </label>
          <label>
            Remote/hybrid preference
            <select
              value={preferenceDraft.remoteHybridPreference}
              onChange={(event) =>
                onPreferenceDraft({
                  ...preferenceDraft,
                  remoteHybridPreference: event.target.value as PreferenceDraft["remoteHybridPreference"],
                })
              }
            >
              <option value="">No saved preference</option>
              {REMOTE_HYBRID_OPTIONS.map((option) => (
                <option key={option} value={option}>{prettyKey(option)}</option>
              ))}
            </select>
          </label>
        </div>
        <div className="scoring-control-grid">
          {SCORING_WEIGHT_FIELDS.map((field) => (
            <label className="range-label" key={field.key}>
              <span>
                {field.label}
                <strong>{Math.round(preferenceDraft.scoringWeights[field.key] * 100)}%</strong>
              </span>
              <input
                max={100}
                min={0}
                onChange={(event) =>
                  onPreferenceDraft({
                    ...preferenceDraft,
                    scoringWeights: updateScoringWeight(
                      preferenceDraft.scoringWeights,
                      field.key,
                      Number(event.target.value),
                    ),
                  })
                }
                type="range"
                value={Math.round(preferenceDraft.scoringWeights[field.key] * 100)}
              />
            </label>
          ))}
        </div>
        <div className="account-button-row">
          <button disabled={actionState.loading} type="button" onClick={onSavePreferences}>
            Save preferences
          </button>
          <button
            className="secondary-button"
            disabled={actionState.loading || scoringPreviewState.loading}
            type="button"
            onClick={onPreviewScoring}
          >
            Preview scoring overlay
          </button>
          <button
            className="secondary-button"
            disabled={actionState.loading || !preferences?.persisted}
            type="button"
            onClick={onDeletePreferences}
          >
            Delete preferences
          </button>
        </div>
        {scoringPreviewState.loading ? <LoadingBlock label="Loading scoring preview" /> : null}
        {scoringPreviewState.error ? <ErrorState message={scoringPreviewState.error} /> : null}
        {scoringPreviewState.envelope?.data ? (
          <ScoringPreviewPanel preview={scoringPreviewState.envelope.data} />
        ) : null}
      </ShellCard>

      <ShellCard title="Watchlist" eyebrow="Saved references">
        {artifactsState.loading ? <LoadingBlock label="Loading saved artifacts" /> : null}
        {artifactsState.error ? <ErrorState message={artifactsState.error} /> : null}
        {groupedWatchlists.length ? (
          <div className="watchlist-dashboard">
            {groupedWatchlists.map((group) => (
              <section className="watchlist-group" key={group.type}>
                <div className="watchlist-group-header">
                  <strong>{group.label}</strong>
                  <span className="badge">{group.items.length}</span>
                </div>
                <div className="account-list">
                  {group.items.map((artifact) => (
                    <div className="account-list-row" key={artifact.saved_artifact_id}>
                      <div>
                        <strong>{artifact.label ?? artifact.artifact_ref}</strong>
                        <small>{artifact.artifact_ref} · saved {formatDateTime(artifact.created_at)}</small>
                        {artifact.notes ? <p className="meta-copy">{artifact.notes}</p> : null}
                      </div>
                      <button
                        className="secondary-button"
                        disabled={actionState.loading}
                        type="button"
                        onClick={() => onDeleteArtifact(artifact.saved_artifact_id)}
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                </div>
              </section>
            ))}
          </div>
        ) : (
          <EmptyState title="No watchlist items" body="Save a visible region, company, role family, or comparison set." />
        )}
      </ShellCard>

      <ShellCard title="Recommendation snapshots" eyebrow="Persisted derived overlays">
        {snapshotsState.loading ? <LoadingBlock label="Loading snapshots" /> : null}
        {snapshotsState.error ? <ErrorState message={snapshotsState.error} /> : null}
        {snapshots.length ? (
          <div className="account-list">
            {snapshots.map((snapshot) => (
              <details className="account-list-row account-details-row" key={snapshot.recommendation_snapshot_id}>
                <summary>
                  <span>
                    <strong>{snapshot.recommendation_version}</strong>
                    <small>{formatDateTime(snapshot.generated_at)}</small>
                  </span>
                </summary>
                <JsonBlock value={snapshot} />
              </details>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No recommendation snapshots"
            body="Run personalized discovery while signed in, then persist the visible output as a recommendation snapshot."
          />
        )}
      </ShellCard>

      {exportState.envelope?.data ? (
        <ShellCard title="Export preview" eyebrow="Current user-owned data">
          <JsonBlock value={exportState.envelope.data} />
        </ShellCard>
      ) : null}
      {exportState.error ? <ErrorState message={exportState.error} /> : null}
    </div>
  );
}

function ScoreCard({
  label,
  value,
  compact = false,
}: {
  label: string;
  value: number | null | undefined;
  compact?: boolean;
}) {
  return (
    <div className={compact ? "score-card score-card-compact" : "score-card"}>
      <div className="score-topline">
        <span>{label}</span>
        <strong>{formatValue(value)}</strong>
      </div>
      <div className="score-track" aria-hidden="true">
        <span style={{ width: `${scorePercent(value)}%` }} />
      </div>
    </div>
  );
}

function ScoringPreviewPanel({ preview }: { preview: ScoringPreviewResult }) {
  if (!preview.regions.length) {
    return <EmptyState title="No preview regions" body="Choose at least one preferred region." />;
  }

  return (
    <div className="preview-panel">
      {preview.regions.map((region) => (
        <div className="preview-row" key={region.region_id}>
          <div>
            <span className="badge">Personalized overlay</span>
            <CoverageBadge coverage={region.coverage} />
            <PriorityMarketBadge priorityMarket={region.priority_market} />
            <strong>{region.display_name}</strong>
            <small>{region.region_id}</small>
            <CoverageInlineNote coverage={region.coverage} />
          </div>
          <ScoreCard
            compact
            label="Canonical/default objective"
            value={region.canonical_default_scores.objective_opportunity_score}
          />
          <ScoreCard
            compact
            label="Personalized overlay"
            value={region.personalized_overlay_score}
          />
          <div className="preview-component-list">
            {SCORING_WEIGHT_FIELDS.map((field) => {
              const component = region.components[field.key];
              return (
                <span className="badge" key={field.key}>
                  {field.label}: {formatValue(component?.value)} · weight{" "}
                  {Math.round((component?.effective_weight ?? 0) * 100)}%
                </span>
              );
            })}
          </div>
          <CoveragePanel coverage={region.coverage} />
        </div>
      ))}
    </div>
  );
}

function StatGrid({ values }: { values: Record<string, unknown> }) {
  const entries = Object.entries(values);
  if (!entries.length) {
    return <EmptyState title="No values" body="This output did not include summary metrics." />;
  }

  return (
    <div className="stat-grid">
      {entries.map(([key, value]) => (
        <div className="stat-card" key={key}>
          <span>{prettyKey(key)}</span>
          <strong>{formatValue(value)}</strong>
        </div>
      ))}
    </div>
  );
}

function EntryLevelSummaryGrid({ summary }: { summary?: EntryLevelSummary | null }) {
  if (!summary) {
    return <EmptyState title="No entry-level summary" body="No early-career summary was returned." />;
  }

  return (
    <div className="stat-grid">
      <div className="stat-card">
        <span>Internships</span>
        <strong>
          <CountStatusValue
            value={summary.internship_count_total}
            status={summary.internship_count_total_status}
          />
        </strong>
      </div>
      <div className="stat-card">
        <span>Co-ops</span>
        <strong>
          <CountStatusValue
            value={summary.coop_count_total}
            status={summary.coop_count_total_status}
          />
        </strong>
      </div>
      <div className="stat-card">
        <span>Entry-level full-time</span>
        <strong>
          <CountStatusValue
            value={summary.entry_level_full_time_count_total}
            status={summary.entry_level_full_time_count_total_status}
          />
        </strong>
      </div>
      <div className="stat-card">
        <span>Formal programs</span>
        <strong>{formatValue(summary.formal_early_career_program_count)}</strong>
      </div>
      <div className="stat-card">
        <span>Average access score</span>
        <strong>{formatValue(summary.average_entry_level_access_score)}</strong>
      </div>
      <div className="stat-card">
        <span>Pairs with access</span>
        <strong>{formatValue(summary.pairs_with_entry_level_access)}</strong>
      </div>
    </div>
  );
}

function RegionScoreGrid({ scores }: { scores: RegionScores | null | undefined }) {
  if (!scores) {
    return <EmptyState title="Scores unavailable" body="No score object was returned for this region." />;
  }

  return (
    <div className="score-grid">
      {SCORE_FIELDS.map((score) => (
        <ScoreCard key={score.key} label={score.label} value={scores[score.key] as number | null} />
      ))}
    </div>
  );
}

function ScoreBreakdownChart({
  scores,
  title = "Canonical/default score breakdown",
}: {
  scores: RegionScores | null | undefined;
  title?: string;
}) {
  if (!scores) {
    return (
      <UnsupportedVisualizationPanel
        items={["Score breakdown chart"]}
        reason="No score object was returned for the current snapshot."
      />
    );
  }

  return (
    <div className="visualization-panel">
      <div className="visualization-header">
        <strong>{title}</strong>
        <span className="badge badge-unknown">Current snapshot</span>
      </div>
      <div className="visual-bar-list" aria-label={title}>
        {SCORE_FIELDS.map((score) => {
          const value = scores[score.key] as number | null;
          const missing = typeof value !== "number";
          return (
            <div className="visual-bar-row" key={score.key}>
              <span>{score.label}</span>
              <div className={missing ? "visual-bar visual-bar-missing" : "visual-bar"}>
                <span style={{ width: `${scorePercent(value)}%` }} />
              </div>
              <strong>{missing ? "Missing" : `${Math.round(value * 100)}%`}</strong>
            </div>
          );
        })}
      </div>
      <p className="meta-copy">
        This chart renders stored score fields only. Missing values are not
        converted to zero.
      </p>
    </div>
  );
}

function ComparisonScoreChart({
  comparison,
  regionALabel,
  regionBLabel,
}: {
  comparison: ComparisonDetail;
  regionALabel: string;
  regionBLabel: string;
}) {
  return (
    <div className="visualization-panel">
      <div className="visualization-header">
        <strong>Region comparison visualization</strong>
        <span className="badge badge-unknown">Current snapshot</span>
      </div>
      <div className="comparison-visual-list">
        {SCORE_FIELDS.map((score) => {
          const aValue = comparison.region_a?.scores?.[score.key] as number | null | undefined;
          const bValue = comparison.region_b?.scores?.[score.key] as number | null | undefined;
          return (
            <div className="comparison-visual-row" key={score.key}>
              <span>{score.label}</span>
              <div>
                <small>{regionALabel}</small>
                <div className={typeof aValue === "number" ? "visual-bar" : "visual-bar visual-bar-missing"}>
                  <span style={{ width: `${scorePercent(aValue)}%` }} />
                </div>
              </div>
              <div>
                <small>{regionBLabel}</small>
                <div className={typeof bValue === "number" ? "visual-bar" : "visual-bar visual-bar-missing"}>
                  <span style={{ width: `${scorePercent(bValue)}%` }} />
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <p className="meta-copy">
        Bars compare returned canonical/default score fields. This is not a new
        scoring model.
      </p>
    </div>
  );
}

function AlertSummaryVisualization({ alerts }: { alerts: UserAlert[] }) {
  if (!alerts.length) {
    return (
      <UnsupportedVisualizationPanel
        items={["Alert summary chart"]}
        reason="No current in-app alerts were returned for this account."
      />
    );
  }
  const counts = new Map<string, number>();
  for (const alert of alerts) {
    counts.set(alert.event.event_type, (counts.get(alert.event.event_type) ?? 0) + 1);
  }
  const maxCount = Math.max(...counts.values(), 1);
  return (
    <div className="visualization-panel">
      <div className="visualization-header">
        <strong>Alert change summary</strong>
        <span className="badge badge-unknown">Feed metadata</span>
      </div>
      <div className="visual-bar-list">
        {Array.from(counts.entries()).sort().map(([eventType, count]) => (
          <div className="visual-bar-row" key={eventType}>
            <span>{prettyKey(eventType)}</span>
            <div className="visual-bar">
              <span style={{ width: `${(count / maxCount) * 100}%` }} />
            </div>
            <strong>{count}</strong>
          </div>
        ))}
      </div>
      <p className="meta-copy">
        This summarizes alert feed metadata only. It does not infer additional
        market change events.
      </p>
    </div>
  );
}

function UnsupportedVisualizationPanel({
  items,
  reason,
}: {
  items: string[];
  reason: string;
}) {
  return (
    <div className="unsupported-visualization">
      <div className="visualization-header">
        <strong>Unsupported visualization state</strong>
        <span className="badge badge-warning">Disabled</span>
      </div>
      <p className="meta-copy">{reason}</p>
      <div className="chip-row">
        {items.map((item) => (
          <span className="badge badge-unknown" key={item}>{item}</span>
        ))}
      </div>
    </div>
  );
}

function ExplanationResultPanel({
  state,
  emptyCopy,
}: {
  state?: LoadState<ExplanationResult>;
  emptyCopy: string;
}) {
  if (state?.loading) return <LoadingBlock label="Rendering structured guidance" />;
  if (state?.error) return <ErrorState message={state.error} />;
  const explanation = state?.envelope?.data;
  if (!explanation) {
    return <EmptyState title="No explanation yet" body={emptyCopy} />;
  }
  return (
    <div className="explanation-panel">
      <div className="metadata-row">
        <span className="badge">Structured guidance</span>
        <span className={explanation.status === "ok" ? "badge badge-success" : "badge badge-warning"}>
          {prettyKey(explanation.status)}
        </span>
        <span className="badge badge-unknown">{prettyKey(explanation.provider_mode)}</span>
      </div>
      {explanation.sections.map((section) => (
        <div className="explanation-section" key={section.section_type}>
          <strong>{section.title}</strong>
          <ul className="notes-list">
            {section.statements.map((statement) => (
              <li key={statement}>{statement}</li>
            ))}
          </ul>
        </div>
      ))}
      {explanation.limitations.length ? (
        <div className="warning-list">
          {explanation.limitations.map((limitation) => (
            <div className="warning-item" key={limitation}>
              <div className="warning-header">
                <span className="warning-code">Explanation boundary</span>
              </div>
              <p>{limitation}</p>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function CompanyList({
  companies,
  mode,
  onSelectCompany,
}: {
  companies: NonNullable<RegionDetail["top_companies_present"]> | NonNullable<RegionDetail["top_companies_hiring"]>;
  mode: "present" | "hiring";
  onSelectCompany: (companyId: string) => void;
}) {
  if (!companies.length) {
    return <EmptyState title="No companies" body="This section is empty for the selected output." />;
  }

  return (
    <div className="company-list">
      {companies.map((company) => {
        const hiringCopy =
          "active_posting_count_now" in company
            ? `${formatCountStatus(
                company.active_posting_count_now,
                company.active_posting_count_now_status,
              )} active · ${formatCountStatus(
                company.posting_count_90d,
                company.posting_count_90d_status,
              )} in 90d`
            : "";
        return (
          <button
            className="company-row"
            key={company.company_id}
            type="button"
            onClick={() => onSelectCompany(company.company_id)}
          >
            <span>
              <strong>{company.company_name}</strong>
              <small>
                {mode === "present"
                  ? `${formatValue("sector_primary" in company ? company.sector_primary : null)} · ${formatValue(
                      "eligibility_status" in company ? company.eligibility_status : null,
                    )}`
                  : hiringCopy}
              </small>
              <ImportedMarketBadges metadata={company.import_metadata} />
            </span>
            <span className="row-arrow">View</span>
          </button>
        );
      })}
    </div>
  );
}

function ExploreMarkets({
  health,
  marketCoverage,
  marketOperations,
  regions,
  regionSearch,
  regionDetails,
  onOpenCompare,
  onOpenRegionDetail,
  onSelectRegion,
}: {
  health: LoadState<{ service: string }>;
  marketCoverage: LoadState<MarketCoverageListPayload>;
  marketOperations: LoadState<ImportedMarketOperationsViewPayload>;
  regions: LoadState<{ regions: RegionListItem[] }>;
  regionSearch: LoadState<RegionSearchResponse>;
  regionDetails: Record<string, ApiEnvelope<RegionDetail>>;
  onOpenCompare: () => void;
  onOpenRegionDetail: () => void;
  onSelectRegion: (regionId: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [opportunityFilter, setOpportunityFilter] = useState<OpportunityFilter>("any");
  const [careerFilter, setCareerFilter] = useState<CareerStageFilter>("any");
  const [freshnessFilter, setFreshnessFilter] = useState<FreshnessFilter>("any");
  const regionList = useMemo(() => regions.envelope?.data?.regions ?? [], [regions.envelope]);
  const searchMap = getRegionSearchMap(regionSearch.envelope);
  const normalizedQuery = query.toLocaleLowerCase().trim();
  const filteredRegions = regionList.filter((region) => {
    const searchItem = searchMap.get(region.region_id);
    const detail = regionDetails[region.region_id]?.data;
    const searchableValues = [
      region.display_name,
      region.region_id,
      region.region_type,
      region.labor_market_group,
      searchItem?.name,
      searchItem?.region_name,
    ];
    const matchesQuery =
      !normalizedQuery
      || searchableValues.some((value) => value?.toLocaleLowerCase().includes(normalizedQuery));
    if (!matchesQuery) return false;

    const opportunityScore = regionOpportunityScore(region.region_id, searchMap, regionDetails);
    if (opportunityFilter === "missing" && typeof opportunityScore === "number") return false;
    if (opportunityFilter !== "any" && opportunityFilter !== "missing") {
      if (typeof opportunityScore !== "number" || opportunityScore < Number(opportunityFilter)) return false;
    }

    const careerState = entryLevelSignalState(detail);
    if (careerFilter === "entry_level_reported" && careerState !== "reported") return false;
    if (careerFilter === "entry_level_unknown" && careerState !== "unknown") return false;

    const freshnessStatus = searchItem?.freshness.freshness_status
      ?? envelopeFreshnessStatus(regionDetails[region.region_id]);
    if (freshnessFilter !== "any" && freshnessStatus !== freshnessFilter) return false;

    return true;
  });
  const detailCount = regionList.filter((region) => regionDetails[region.region_id]?.data).length;
  const realImportedCount = regionList.filter(
    (region) => searchMap.get(region.region_id)?.freshness.data_basis === "real_imported",
  ).length;
  const seededCount = regionList.filter(
    (region) => searchMap.get(region.region_id)?.freshness.data_basis === "seeded_demo"
      || envelopeFreshnessStatus(regionDetails[region.region_id]) === "seeded_demo",
  ).length;

  return (
    <div className="view-grid">
      <ShellCard
        title="Explore markets"
        eyebrow="Explore markets"
        action={<StateBadge envelope={health.envelope} loading={health.loading} error={health.error} />}
      >
        <p className="lead-copy">
          Compare prepared regional market outputs for early-career tech decisions. Scores
          are derived signals, source labels show whether evidence is seeded demo, real
          imported, mixed, partial, stale, or unknown. Coverage labels separately show
          whether each market is fully covered, partial, watchlist, or placeholder.
        </p>
        <div className="hero-actions">
          <button type="button" onClick={onOpenRegionDetail}>
            Open region detail
          </button>
          <button className="secondary-button" type="button" onClick={onOpenCompare}>
            Compare markets
          </button>
        </div>
        <UpgradePrompt
          feature="full_market_coverage"
          title="Broader market coverage is an added-value plan feature."
          body="The demo still shows useful basic exploration; paid coverage expands the maintained market catalog without changing recommendation ranking."
        />
      </ShellCard>

      <ShellCard title="Imported markets" eyebrow="Curated coverage">
        {marketCoverage.loading ? <LoadingBlock label="Loading imported market coverage" /> : null}
        {marketCoverage.error ? (
          <ErrorState message={`Imported market coverage unavailable: ${marketCoverage.error}`} />
        ) : null}
        <ImportedMarketCoveragePanel markets={marketCoverage.envelope?.data?.markets ?? []} />
        <ImportedMarketOperationsPanel
          error={marketOperations.error}
          loading={marketOperations.loading}
          payload={marketOperations.envelope?.data ?? null}
        />
      </ShellCard>

      <ShellCard title="Market filters" eyebrow="Search and narrow">
        <div className="market-filter-grid">
          <label>
            Region search
            <input
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search name, id, labor market"
              type="search"
              value={query}
            />
          </label>
          <label>
            Opportunity score
            <select
              onChange={(event) => setOpportunityFilter(event.target.value as OpportunityFilter)}
              value={opportunityFilter}
            >
              <option value="any">Any score</option>
              <option value="0.70">At least 70%</option>
              <option value="0.50">At least 50%</option>
              <option value="missing">Missing score</option>
            </select>
          </label>
          <label>
            Career stage
            <select
              onChange={(event) => setCareerFilter(event.target.value as CareerStageFilter)}
              value={careerFilter}
            >
              <option value="any">Any available stage signal</option>
              <option value="entry_level_reported">Entry-level access reported</option>
              <option value="entry_level_unknown">Entry-level unknown or missing</option>
            </select>
          </label>
          <label>
            Data freshness
            <select
              onChange={(event) => setFreshnessFilter(event.target.value as FreshnessFilter)}
              value={freshnessFilter}
            >
              <option value="any">Any freshness state</option>
              <option value="fresh">Fresh real/imported evidence</option>
              <option value="seeded_demo">Seeded demo</option>
              <option value="partial">Partial</option>
              <option value="stale">Stale</option>
              <option value="unknown">Unknown freshness</option>
            </select>
          </label>
        </div>
        <div className="market-summary-strip">
          <div>
            <strong>{filteredRegions.length}</strong>
            <span>matching region(s)</span>
          </div>
          <div>
            <strong>{detailCount}/{regionList.length}</strong>
            <span>detail outputs loaded</span>
          </div>
          <div>
            <strong>{realImportedCount}</strong>
            <span>real imported evidence</span>
          </div>
          <div>
            <strong>{seededCount}</strong>
            <span>seed/demo evidence</span>
          </div>
        </div>
        {regionSearch.error ? (
          <ErrorState message={`Region source search unavailable: ${regionSearch.error}`} />
        ) : null}
        <p className="meta-copy">
          Unknown freshness is intentionally kept separate from fresh. Missing scores and
          missing entry-level values are not converted into zeroes. Coverage is a separate
          readiness estimate and does not replace source or freshness evidence.
        </p>
      </ShellCard>

      <ShellCard title="Markets" eyebrow="Filtered region outputs">
        {regions.loading ? <LoadingBlock label="Loading regions" /> : null}
        {regions.error ? <ErrorState message={regions.error} /> : null}
        {regionSearch.loading ? <LoadingBlock label="Loading source and freshness labels" /> : null}
        {!regions.loading && !filteredRegions.length ? (
          <EmptyState
            title="No markets match these filters"
            body="Try clearing search, allowing unknown freshness, or including missing opportunity scores."
          />
        ) : null}
        {filteredRegions.length ? (
          <div className="market-card-grid">
            {filteredRegions.map((region) => {
              const searchItem = searchMap.get(region.region_id);
              const detailEnvelope = regionDetails[region.region_id] ?? null;
              const detail = detailEnvelope?.data;
              const opportunityScore = regionOpportunityScore(region.region_id, searchMap, regionDetails);
              const careerState = entryLevelSignalState(detail);
              const { coverage, priorityMarket } = coverageForRegion(region, searchItem, detail);
              return (
                <button
                  className="market-card"
                  key={region.region_id}
                  type="button"
                  onClick={() => onSelectRegion(region.region_id)}
                >
                  <div className="market-card-topline">
                    <span>{prettyKey(region.region_type)}</span>
                    <CoverageBadge coverage={coverage} />
                    <PriorityMarketBadge priorityMarket={priorityMarket} />
                    <QualityBadgeRow envelope={detailEnvelope} source={searchItem?.freshness} />
                  </div>
                  <strong>{region.display_name}</strong>
                  <small>
                    {region.region_id} · {region.labor_market_group ?? "unknown labor market"}
                  </small>
                  <CoverageInlineNote coverage={coverage} />
                  <div className="market-card-metrics">
                    <ScoreCard compact label="Opportunity" value={opportunityScore} />
                    <div className="stat-card">
                      <span>Career-stage signal</span>
                      <strong>
                        {careerState === "reported" ? "Entry-level reported" : "Entry-level unknown"}
                      </strong>
                    </div>
                    <div className="stat-card">
                      <span>Source count</span>
                      <strong>{searchItem?.freshness.source_count ?? "Unknown"}</strong>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        ) : null}
      </ShellCard>

      <ShellCard title="Region expansion status" eyebrow="Operator workflow">
        <UnsupportedVisualizationPanel
          items={["Expansion workflow status visualization"]}
          reason="Region expansion workflow rows are operator/checklist state and are not exposed through a public frontend API in this batch."
        />
      </ShellCard>

      <div className="quick-region-grid">
        {filteredRegions.slice(0, 2).map((region) => {
          const detail = regionDetails[region.region_id]?.data;
          const searchItem = searchMap.get(region.region_id);
          const { coverage, priorityMarket } = coverageForRegion(region, searchItem, detail);
          return detail ? (
            <button
              className="quick-region-card"
              key={detail.region_id}
              type="button"
              onClick={() => {
                onSelectRegion(detail.region_id);
              }}
            >
              <span>{detail.region_type}</span>
              <CoverageBadge coverage={coverage} />
              <PriorityMarketBadge priorityMarket={priorityMarket} />
              <strong>{detail.display_name}</strong>
              <div className="quick-score-row">
                <ScoreCard compact label="Total score" value={detail.scores?.raw_total_score} />
                <ScoreCard
                  compact
                  label="Early career"
                  value={detail.scores?.early_career_accessibility_score}
                />
              </div>
            </button>
          ) : (
            <div className="quick-region-card quick-region-placeholder" key={region.region_id}>
              <LoadingBlock label={`Loading ${region.display_name}`} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

function RegionExplorer({
  regions,
  selectedRegionId,
  regionState,
  sourceState,
  roleFamilyState,
  canSavePersonalOverlays,
  canExplainGuidance,
  canUseIntegrations,
  savedArtifactsByKey,
  explanationState,
  onSelectRegion,
  onSelectCompany,
  onCompareRegion,
  onSaveRegion,
  onSaveRoleFamily,
  onRemoveSavedArtifact,
  onExplainRegion,
  onCreateIntegrationExport,
  onCreateIntegrationReminder,
}: {
  regions: RegionListItem[];
  selectedRegionId: string;
  regionState: LoadState<RegionDetail>;
  sourceState: LoadState<SourceExplanation>;
  roleFamilyState: LoadState<CompanySearchResponse>;
  canSavePersonalOverlays: boolean;
  canExplainGuidance: boolean;
  canUseIntegrations: boolean;
  savedArtifactsByKey: Map<string, SavedMarketArtifact>;
  explanationState?: LoadState<ExplanationResult>;
  onSelectRegion: (regionId: string) => void;
  onSelectCompany: (companyId: string) => void;
  onCompareRegion: (regionId: string) => void;
  onSaveRegion: (region: RegionDetail) => void;
  onSaveRoleFamily: (roleFamily: string) => void;
  onRemoveSavedArtifact: (savedArtifactId: string) => void;
  onExplainRegion: (region: RegionDetail) => void;
  onCreateIntegrationExport: (request: IntegrationExportCreateRequest) => void;
  onCreateIntegrationReminder: (request: IntegrationReminderCreateRequest) => void;
}) {
  const region = regionState.envelope?.data;
  const hasSelectedRegion = regions.some((item) => item.region_id === selectedRegionId);
  const source = sourceState.envelope?.data;
  const roleCounts = roleFamilyCounts(roleFamilyState.envelope?.data);
  const entrySummary = region?.entry_level_summary ?? null;
  const savedRegionArtifact = savedArtifactsByKey.get(savedArtifactKey("region", selectedRegionId));

  return (
    <div className="view-grid">
      <ShellCard
        title="Region detail"
        eyebrow="Market output"
        action={<QualityBadgeRow envelope={regionState.envelope} source={source} />}
      >
        <div className="toolbar">
          <label>
            Select region
            <select value={selectedRegionId} onChange={(event) => onSelectRegion(event.target.value)}>
              {selectedRegionId && !hasSelectedRegion ? (
                <option value={selectedRegionId}>
                  {regions.length ? `Unknown region: ${selectedRegionId}` : selectedRegionId}
                </option>
              ) : null}
              {regions.map((item) => (
                <option key={item.region_id} value={item.region_id}>
                  {item.display_name}
                </option>
              ))}
            </select>
          </label>
          <div className="toolbar-actions">
            <button
              className="secondary-button toolbar-button"
              disabled={!region}
              onClick={() => onCompareRegion(selectedRegionId)}
              type="button"
            >
              Compare this market
            </button>
            <button
              className="secondary-button toolbar-button"
              disabled={!region || !canSavePersonalOverlays}
              onClick={() => {
                if (savedRegionArtifact) {
                  onRemoveSavedArtifact(savedRegionArtifact.saved_artifact_id);
                } else if (region) {
                  onSaveRegion(region);
                }
              }}
              type="button"
            >
              {savedRegionArtifact ? "Remove region" : canSavePersonalOverlays ? "Save region" : "Sign in to save"}
            </button>
            <button
              className="secondary-button toolbar-button"
              disabled={!region || !canExplainGuidance}
              onClick={() => {
                if (region) onExplainRegion(region);
              }}
              type="button"
            >
              {canExplainGuidance ? "Explain guidance" : "Sign in to explain"}
            </button>
          </div>
        </div>

        {regionState.loading ? <LoadingBlock label="Loading region output" /> : null}
        {regionState.error ? <ErrorState message={regionState.error} /> : null}
        {sourceState.error ? <ErrorState message={`Source explanation unavailable: ${sourceState.error}`} /> : null}
        {!regionState.loading && !regionState.error && !region ? (
          <EmptyState title="No region selected" body="Choose a region from the dropdown." />
        ) : null}
        <UpgradePrompt
          feature="saved_watchlists"
          title="Save this market to a watchlist with Individual."
          body="Watchlists add persistence and follow-up workflow value while keeping the region facts and basic guidance available in the free experience."
        />
      </ShellCard>

      {region ? (
        <IntegrationActionPanel
          canUseIntegrations={canUseIntegrations}
          label={region.display_name}
          objectId={region.region_id}
          objectType="region"
          onCreateExport={onCreateIntegrationExport}
          onCreateReminder={onCreateIntegrationReminder}
          reminderType="market_refresh_alert"
        />
      ) : null}

      {region ? (
        <>
          <ShellCard title={region.display_name} eyebrow="Factual regional output">
            <div className="detail-hero">
              <div>
                <p className="meta-copy">
                  {region.region_id} · {region.labor_market_group ?? "unknown labor market"}
                </p>
                {region.priority_market ? (
                  <div className="metadata-row">
                    <PriorityMarketBadge priorityMarket={region.priority_market} />
                  </div>
                ) : null}
                <ImportedMarketBadges metadata={region.import_metadata} />
                <h3>What this output contains</h3>
                <p className="meta-copy">
                  Counts are returned facts from the prepared output. Missing fields are shown
                  as unknown rather than converted to zero.
                </p>
              </div>
              <div className="detail-side-panels">
                <CoveragePanel coverage={region.coverage} sectorCoverage={region.sector_coverage} />
                <MetadataPanel envelope={regionState.envelope} source={source} />
              </div>
            </div>
            <StatGrid values={region.summary ?? {}} />
          </ShellCard>

          <ShellCard title="Derived market scores" eyebrow="Interpretation">
            <p className="meta-copy">
              These scores are derived from stored scoring fields. They are not a claim of
              complete market coverage or real-time hiring certainty.
            </p>
            <ScoreBreakdownChart scores={region.scores} />
            <RegionScoreGrid scores={region.scores} />
          </ShellCard>

          <ShellCard title="Structured guidance" eyebrow="Evidence packet explanation">
            <p className="meta-copy">
              Guidance is generated from returned structured fields only. It is not source
              data and is not stored as market truth.
            </p>
            <ExplanationResultPanel
              emptyCopy="Use Explain guidance to render a constrained explanation from this region output."
              state={explanationState}
            />
          </ShellCard>

          <ShellCard title="Deferred visualizations" eyebrow="No unsupported precision">
            <UnsupportedVisualizationPanel
              items={[
                "Historical trend view",
                "Map",
                "Opportunity heatmap",
                "Company-region network graph",
              ]}
              reason="The current region response does not include historical snapshots, map geometry, heatmap cells, or network layout coordinates."
            />
          </ShellCard>

          <div className="split-grid">
            <ShellCard title="Companies present" eyebrow="Presence facts">
              <p className="meta-copy">
                Presence means the backend has a company-region presence record. It does not
                imply current hiring.
              </p>
              <CompanyList
                companies={region.top_companies_present ?? []}
                mode="present"
                onSelectCompany={onSelectCompany}
              />
            </ShellCard>

            <ShellCard title="Hiring activity" eyebrow="Hiring snapshot">
              <p className="meta-copy">
                Hiring counts are snapshots from prepared records. Unknown posting counts stay unknown.
              </p>
              <CompanyList
                companies={region.top_companies_hiring ?? []}
                mode="hiring"
                onSelectCompany={onSelectCompany}
              />
            </ShellCard>
          </div>

          <div className="split-grid">
            <ShellCard title="Entry-level access" eyebrow="Early-career facts">
              <p className="meta-copy">
                Internship, co-op, full-time, and formal program signals are separate inputs.
                Unknown totals are not treated as zero.
              </p>
              <EntryLevelSummaryGrid summary={entrySummary} />
            </ShellCard>

            <ShellCard title="Role-family concentration" eyebrow="Derived from company search rows">
              <p className="meta-copy">
                This summarizes role families visible in company search rows for this region.
                Absence here does not prove there are no jobs in a family.
              </p>
              {roleFamilyState.loading ? <LoadingBlock label="Loading role-family signals" /> : null}
              {roleFamilyState.error ? <ErrorState message={roleFamilyState.error} /> : null}
              {roleCounts.length ? (
                <div className="signal-list">
                  {roleCounts.map((item) => {
                    const savedRoleArtifact = savedArtifactsByKey.get(
                      savedArtifactKey("role_family", item.role),
                    );
                    return (
                      <div className="signal-row" key={item.role}>
                        <span>{prettyKey(item.role)}</span>
                        <strong>{item.count} company signal(s)</strong>
                        <button
                          className="secondary-button"
                          disabled={!canSavePersonalOverlays}
                          type="button"
                          onClick={() => {
                            if (savedRoleArtifact) {
                              onRemoveSavedArtifact(savedRoleArtifact.saved_artifact_id);
                            } else {
                              onSaveRoleFamily(item.role);
                            }
                          }}
                        >
                          {savedRoleArtifact ? "Remove" : canSavePersonalOverlays ? "Save" : "Sign in"}
                        </button>
                      </div>
                    );
                  })}
                </div>
              ) : !roleFamilyState.loading ? (
                <EmptyState
                  title="No role-family signals"
                  body="No company search rows returned role-family summaries for this region."
                />
              ) : null}
            </ShellCard>
          </div>

          <ShellCard title="Classification context" eyebrow="Factual tags">
            <StatGrid
              values={{
                major_tech_count: region.major_tech_summary?.count,
                major_tech_companies: region.major_tech_summary?.company_ids,
                mag7_count: region.mag7_summary?.count,
                mag7_companies: region.mag7_summary?.company_ids,
              }}
            />
          </ShellCard>
        </>
      ) : null}
    </div>
  );
}

function CompanyExplorer({
  companyOptions,
  selectedCompanyId,
  companyState,
  geographyState,
  sourceState,
  canSavePersonalOverlays,
  canExplainGuidance,
  canUseIntegrations,
  savedCompanyArtifact,
  explanationState,
  onSelectCompany,
  onSaveCompany,
  onRemoveSavedArtifact,
  onExplainCompany,
  onCreateIntegrationExport,
  onCreateIntegrationReminder,
  onCreateCareerPlatformExport,
}: {
  companyOptions: CompanyOption[];
  selectedCompanyId: string;
  companyState: LoadState<CompanyDetail>;
  geographyState: LoadState<CompanyGeographyResponse>;
  sourceState: LoadState<SourceExplanation>;
  canSavePersonalOverlays: boolean;
  canExplainGuidance: boolean;
  canUseIntegrations: boolean;
  savedCompanyArtifact?: SavedMarketArtifact;
  explanationState?: LoadState<ExplanationResult>;
  onSelectCompany: (companyId: string) => void;
  onSaveCompany: (company: CompanyDetail) => void;
  onRemoveSavedArtifact: (savedArtifactId: string) => void;
  onExplainCompany: (company: CompanyDetail) => void;
  onCreateIntegrationExport: (request: IntegrationExportCreateRequest) => void;
  onCreateIntegrationReminder: (request: IntegrationReminderCreateRequest) => void;
  onCreateCareerPlatformExport: (request: CareerPlatformExportRequest) => void;
}) {
  const company = companyState.envelope?.data;
  const hasSelectedCompany = companyOptions.some((item) => item.company_id === selectedCompanyId);
  const source = sourceState.envelope?.data;
  const geography = geographyState.envelope?.data;
  const strongestRegions = company ? strongestCompanyRegions(company, geography).slice(0, 5) : [];

  return (
    <div className="view-grid">
      <ShellCard
        title="Company geography"
        eyebrow="Presence, hiring, and entry-level access by region"
        action={<QualityBadgeRow envelope={companyState.envelope} source={source} />}
      >
        <div className="toolbar">
          <label>
            Select company
            <select
              value={selectedCompanyId}
              onChange={(event) => onSelectCompany(event.target.value)}
              disabled={!companyOptions.length}
            >
              {selectedCompanyId && !hasSelectedCompany ? (
                <option value={selectedCompanyId}>{selectedCompanyId} from URL</option>
              ) : null}
              {companyOptions.map((item) => (
                <option key={item.company_id} value={item.company_id}>
                  {item.company_name}
                </option>
              ))}
            </select>
          </label>
          <div className="toolbar-actions">
            <button
              className="secondary-button toolbar-button"
              disabled={!company || !canSavePersonalOverlays}
              onClick={() => {
                if (savedCompanyArtifact) {
                  onRemoveSavedArtifact(savedCompanyArtifact.saved_artifact_id);
                } else if (company) {
                  onSaveCompany(company);
                }
              }}
              type="button"
            >
              {savedCompanyArtifact ? "Remove company" : canSavePersonalOverlays ? "Save company" : "Sign in to save"}
            </button>
            <button
              className="secondary-button toolbar-button"
              disabled={!company || !canExplainGuidance}
              onClick={() => {
                if (company) onExplainCompany(company);
              }}
              type="button"
            >
              {canExplainGuidance ? "Explain guidance" : "Sign in to explain"}
            </button>
          </div>
        </div>
        {!companyOptions.length ? (
          <EmptyState
            title="No company list endpoint"
            body="Company choices are derived from loaded region outputs. Deep links still load by company ID."
          />
        ) : null}
        {companyState.loading ? <LoadingBlock label="Loading company output" /> : null}
        {companyState.error ? <ErrorState message={companyState.error} /> : null}
        {sourceState.error ? <ErrorState message={`Source explanation unavailable: ${sourceState.error}`} /> : null}
        {geographyState.error ? <ErrorState message={`Company geography summary unavailable: ${geographyState.error}`} /> : null}
        <UpgradePrompt
          feature="deeper_company_geography"
          title="Use deeper company geography with Individual."
          body="Paid company geography adds maintained depth around company-region coverage; it does not bias market recommendations."
        />
      </ShellCard>

      {company ? (
        <IntegrationActionPanel
          canUseIntegrations={canUseIntegrations}
          label={company.company_name}
          objectId={company.company_id}
          objectType="company"
          onCreateCareerPlatformExport={onCreateCareerPlatformExport}
          onCreateExport={onCreateIntegrationExport}
          onCreateReminder={onCreateIntegrationReminder}
          reminderType="follow_up"
        />
      ) : null}

      {company ? (
        <>
          <ShellCard title={company.company_name} eyebrow="Company facts and source quality">
            <div className="classification-layout">
              <StatGrid
                values={{
                  eligibility_status: company.eligibility_status,
                  classification_confidence: company.classification_confidence,
                  sector_primary: company.sector_primary,
                  sector_secondary: company.sector_secondary,
                  eligibility_override: company.eligibility_override_flag,
                  prestige_score: company.prestige_score,
                }}
              />
              <div className="badge-stack">
                <span className={company.is_major_tech ? "badge badge-fresh" : "badge"}>Major tech: {formatValue(company.is_major_tech)}</span>
                <span className={company.is_mag7 ? "badge badge-fresh" : "badge"}>Mag 7: {formatValue(company.is_mag7)}</span>
                <span className={qualityBadgeClass(confidenceTone(company.classification_confidence))}>
                  Classification confidence: {formatValue(company.classification_confidence)}
                </span>
              </div>
            </div>
            <ImportedMarketBadges metadata={company.import_metadata} />
            <MetadataPanel envelope={companyState.envelope} source={source} />
          </ShellCard>

          <ShellCard title="Observed region signals" eyebrow="Derived from visible geography rows">
            <p className="meta-copy">
              This section counts distinct observed signals: presence, hiring activity, and
              entry-level access. It is not a comprehensive ranking of all possible markets.
              Coverage labels describe each region's readiness separately from source freshness.
            </p>
            {geographyState.loading ? <LoadingBlock label="Loading geography source summaries" /> : null}
            {strongestRegions.length ? (
              <div className="market-card-grid">
                {strongestRegions.map((region) => (
                  <div className="market-card market-card-static" key={region.regionId}>
                    <div className="market-card-topline">
                      <span>{region.signalCount} observed signal(s)</span>
                      <CoverageBadge coverage={region.coverage} />
                      <PriorityMarketBadge priorityMarket={region.priorityMarket} />
                      {region.freshness ? <QualityBadgeRow source={region.freshness} /> : null}
                    </div>
                    <strong>{region.regionName}</strong>
                    <small>{region.regionId}</small>
                    <CoverageInlineNote coverage={region.coverage} />
                    <div className="chip-row">
                      {region.signals.map((signal) => (
                        <span className="badge" key={signal}>{signal}</span>
                      ))}
                    </div>
                    <SectorCoveragePanel sectorCoverage={region.sectorCoverage} />
                    <div className="market-card-metrics">
                      <ScoreCard compact label="Entry access" value={region.entryScore} />
                      <div className="stat-card">
                        <span>Active postings</span>
                        <strong>{formatValue(region.activePostings)}</strong>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : !geographyState.loading ? (
              <EmptyState
                title="No strongest-region signal"
                body="The company output did not include enough presence, hiring, or entry-level rows to identify stronger observed regions."
              />
            ) : null}
          </ShellCard>

          <ShellCard title="Structured guidance" eyebrow="Evidence packet explanation">
            <p className="meta-copy">
              Guidance summarizes returned company fields and source labels only. It does
              not infer unobserved presence or hiring.
            </p>
            <ExplanationResultPanel
              emptyCopy="Use Explain guidance to render a constrained explanation from this company output."
              state={explanationState}
            />
          </ShellCard>

          <div className="split-grid">
            <ShellCard title="Where the company is present" eyebrow="Presence only">
              <p className="meta-copy">
                Presence is a company-region relationship. It does not imply active hiring
                or entry-level access in that region.
              </p>
              {(company.regions_present ?? []).length ? (
                <div className="stack-list">
                  {(company.regions_present ?? []).map((region) => (
                    <div className="stack-row" key={region.region_id}>
                      <strong>{region.region_display_name}</strong>
                      <CoverageBadge coverage={region.coverage} />
                      <PriorityMarketBadge priorityMarket={region.priority_market} />
                      <CoverageInlineNote coverage={region.coverage} />
                      <ImportedMarketBadges metadata={region.import_metadata} />
                      <span>
                        {formatValue(region.presence_basis)} · {formatValue(region.presence_confidence)}
                      </span>
                      <span className={qualityBadgeClass(confidenceTone(region.presence_confidence))}>
                        Confidence: {formatValue(region.presence_confidence)}
                      </span>
                      <SectorCoveragePanel sectorCoverage={region.sector_coverage} />
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="No presence rows" body="No region presence was returned." />
              )}
            </ShellCard>

            <ShellCard title="Where the company is hiring" eyebrow="Hiring snapshot">
              <p className="meta-copy">
                Hiring rows are separate from presence rows. A present region can have no
                returned hiring signal.
              </p>
              {(company.regions_hiring ?? []).length ? (
                <div className="stack-list">
                  {(company.regions_hiring ?? []).map((region) => (
                    <div className="stack-row" key={region.region_id}>
                      <strong>{region.region_display_name}</strong>
                      <CoverageBadge coverage={region.coverage} />
                      <PriorityMarketBadge priorityMarket={region.priority_market} />
                      <CoverageInlineNote coverage={region.coverage} />
                      <ImportedMarketBadges metadata={region.import_metadata} />
                      <span>
                        {formatCountStatus(
                          region.active_posting_count_now,
                          region.active_posting_count_now_status,
                        )} active ·{" "}
                        {formatCountStatus(
                          region.posting_count_90d,
                          region.posting_count_90d_status,
                        )} in 90d
                      </span>
                      <span className={region.currently_hiring_flag ? "badge badge-fresh" : "badge badge-unknown"}>
                        Currently hiring: {formatValue(region.currently_hiring_flag)}
                      </span>
                      <SectorCoveragePanel sectorCoverage={region.sector_coverage} />
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="No hiring rows" body="No active hiring rows were returned." />
              )}
            </ShellCard>
          </div>

          <ShellCard title="Where entry-level access exists" eyebrow="Early-career access">
            <p className="meta-copy">
              Entry-level access combines internships, co-ops, full-time entry-level roles,
              and formal program signals when those fields are present.
            </p>
            {(company.entry_level_regions ?? []).length ? (
              <div className="entry-grid">
                {(company.entry_level_regions ?? []).map((region) => (
                  <div className="entry-card" key={region.region_id}>
                    <h3>{region.region_display_name}</h3>
                    <CoverageBadge coverage={region.coverage} />
                    <PriorityMarketBadge priorityMarket={region.priority_market} />
                    <CoverageInlineNote coverage={region.coverage} />
                    <ImportedMarketBadges metadata={region.import_metadata} />
                    <span className={qualityBadgeClass(confidenceTone(region.entry_level_confidence))}>
                      Confidence: {formatValue(region.entry_level_confidence)}
                    </span>
                    <ScoreCard label="Access score" value={region.entry_level_access_score} />
                    <div className="stat-grid">
                      <div className="stat-card">
                        <span>Internships</span>
                        <strong>
                          <CountStatusValue
                            value={region.internship_count}
                            status={region.internship_count_status}
                          />
                        </strong>
                      </div>
                      <div className="stat-card">
                        <span>Co-ops</span>
                        <strong>
                          <CountStatusValue
                            value={region.coop_count}
                            status={region.coop_count_status}
                          />
                        </strong>
                      </div>
                      <div className="stat-card">
                        <span>Entry-level full-time</span>
                        <strong>
                          <CountStatusValue
                            value={region.entry_level_full_time_count}
                            status={region.entry_level_full_time_count_status}
                          />
                        </strong>
                      </div>
                      <div className="stat-card">
                        <span>Formal program</span>
                        <strong>{formatValue(region.formal_early_career_program_flag)}</strong>
                      </div>
                      <div className="stat-card">
                        <span>Confidence</span>
                        <strong>{formatValue(region.entry_level_confidence)}</strong>
                      </div>
                    </div>
                    <SectorCoveragePanel sectorCoverage={region.sector_coverage} />
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No entry-level rows" body="No early-career output was returned." />
            )}
          </ShellCard>
        </>
      ) : null}
    </div>
  );
}

function ComparisonView({
  regions,
  regionA,
  regionB,
  comparisonState,
  sourceAState,
  sourceBState,
  validationError,
  canSavePersonalOverlays,
  canExplainGuidance,
  canUseIntegrations,
  savedComparisonArtifact,
  explanationState,
  onRegionA,
  onRegionB,
  onSaveComparison,
  onRemoveSavedArtifact,
  onExplainComparison,
  onCreateIntegrationExport,
  onCreateIntegrationReminder,
}: {
  regions: RegionListItem[];
  regionA: string;
  regionB: string;
  comparisonState: LoadState<ComparisonDetail>;
  sourceAState: LoadState<SourceExplanation>;
  sourceBState: LoadState<SourceExplanation>;
  validationError?: string | null;
  canSavePersonalOverlays: boolean;
  canExplainGuidance: boolean;
  canUseIntegrations: boolean;
  savedComparisonArtifact?: SavedMarketArtifact;
  explanationState?: LoadState<ExplanationResult>;
  onRegionA: (regionId: string) => void;
  onRegionB: (regionId: string) => void;
  onSaveComparison: (comparison: ComparisonDetail, label: string) => void;
  onRemoveSavedArtifact: (savedArtifactId: string) => void;
  onExplainComparison: (comparison: ComparisonDetail) => void;
  onCreateIntegrationExport: (request: IntegrationExportCreateRequest) => void;
  onCreateIntegrationReminder: (request: IntegrationReminderCreateRequest) => void;
}) {
  const comparison = validationError ? null : comparisonState.envelope?.data;
  const hasRegionA = regions.some((region) => region.region_id === regionA);
  const hasRegionB = regions.some((region) => region.region_id === regionB);
  const regionALabel = comparisonSideLabel(comparison?.region_a, regionA, regions);
  const regionBLabel = comparisonSideLabel(comparison?.region_b, regionB, regions);
  const categoryWinners = comparison?.category_winners ?? {};
  const notes = comparison?.notes ?? [];
  const objective = objectiveComparison(comparison);
  const sourceA = sourceAState.envelope?.data ?? null;
  const sourceB = sourceBState.envelope?.data ?? null;
  const limitations = comparisonDataLimitations(comparison, comparisonState.envelope, sourceA, sourceB);
  const earlyCareerA = comparison?.region_a?.scores?.early_career_accessibility_score;
  const earlyCareerB = comparison?.region_b?.scores?.early_career_accessibility_score;

  return (
    <div className="view-grid">
      <ShellCard
        title="Compare markets"
        eyebrow="Objective and category tradeoffs"
        action={<QualityBadgeRow envelope={comparisonState.envelope} />}
      >
        <div className="comparison-controls">
          <label>
            Region A
            <select value={regionA} onChange={(event) => onRegionA(event.target.value)}>
              {regionA && !hasRegionA ? (
                <option value={regionA}>{regions.length ? `Unknown region: ${regionA}` : regionA}</option>
              ) : null}
              {regions.map((region) => (
                <option key={region.region_id} value={region.region_id}>
                  {region.display_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Region B
            <select value={regionB} onChange={(event) => onRegionB(event.target.value)}>
              {regionB && !hasRegionB ? (
                <option value={regionB}>{regions.length ? `Unknown region: ${regionB}` : regionB}</option>
              ) : null}
              {regions.map((region) => (
                <option key={region.region_id} value={region.region_id}>
                  {region.display_name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="account-inline-actions">
          <button
            className="secondary-button"
            disabled={!comparison || !canSavePersonalOverlays}
            onClick={() => {
              if (savedComparisonArtifact) {
                onRemoveSavedArtifact(savedComparisonArtifact.saved_artifact_id);
              } else if (comparison) {
                onSaveComparison(comparison, `${regionALabel} vs ${regionBLabel}`);
              }
            }}
            type="button"
          >
            {savedComparisonArtifact ? "Remove comparison" : canSavePersonalOverlays ? "Save comparison" : "Sign in to save"}
          </button>
          <button
            className="secondary-button"
            disabled={!comparison || !canExplainGuidance}
            onClick={() => {
              if (comparison) onExplainComparison(comparison);
            }}
            type="button"
          >
            {canExplainGuidance ? "Explain guidance" : "Sign in to explain"}
          </button>
        </div>

        {regionA === regionB ? (
          <ErrorState message="Choose two distinct regions before running comparison." />
        ) : null}
        {validationError && regionA !== regionB ? <ErrorState message={validationError} /> : null}
        {comparisonState.loading ? <LoadingBlock label="Loading comparison output" /> : null}
        {comparisonState.error ? <ErrorState message={comparisonState.error} /> : null}
        <p className="meta-copy">
          The comparison uses returned score fields only. Missing values are shown as
          unavailable and are not treated as zero. Coverage warnings identify markets
          that should not be treated as confident recommendations.
        </p>
        <UpgradePrompt
          feature="saved_comparison_history"
          title="Save comparison history with Individual."
          body="Paid plans add durable comparison history so previous tradeoff analysis can be revisited; the current comparison result remains visible here."
        />
        <CoverageWarningList warnings={pickEnvelopeWarnings(comparisonState.envelope)} />
      </ShellCard>

      {comparison ? (
        <IntegrationActionPanel
          canUseIntegrations={canUseIntegrations}
          label={`${regionALabel} vs ${regionBLabel}`}
          objectId={comparison.comparison_id ?? canonicalComparisonRef(regionA, regionB)}
          objectType="comparison"
          onCreateExport={onCreateIntegrationExport}
          onCreateReminder={onCreateIntegrationReminder}
          reminderType="application_window"
          sourceContext={{ region_ids: [regionA, regionB] }}
        />
      ) : null}

      {comparison ? (
        <>
          <ShellCard title="Coverage context" eyebrow="Comparison readiness">
            <div className="source-compare-grid">
              <div className="source-compare-card">
                <strong>{regionALabel}</strong>
                <PriorityMarketBadge priorityMarket={comparison.region_a?.priority_market} />
                <ImportedMarketBadges metadata={comparison.region_a?.import_metadata} />
                <CoveragePanel
                  coverage={comparison.region_a?.coverage}
                  sectorCoverage={comparison.region_a?.sector_coverage}
                />
              </div>
              <div className="source-compare-card">
                <strong>{regionBLabel}</strong>
                <PriorityMarketBadge priorityMarket={comparison.region_b?.priority_market} />
                <ImportedMarketBadges metadata={comparison.region_b?.import_metadata} />
                <CoveragePanel
                  coverage={comparison.region_b?.coverage}
                  sectorCoverage={comparison.region_b?.sector_coverage}
                />
              </div>
            </div>
          </ShellCard>

          <ShellCard title="Objective winner" eyebrow="Overall comparison signal">
            <div className="objective-winner-panel">
              <div>
                <span className="badge badge-real">Objective opportunity score</span>
                <h2>{objective.winnerLabel}</h2>
                <p className="lead-copy">{objective.message}</p>
                <p className="meta-copy">
                  This is a narrow objective-score winner, not a guarantee that the region
                  is best for every role, company, or career-stage preference.
                </p>
              </div>
              <div className="objective-score-grid">
                <ScoreCard compact label={regionALabel} value={comparison.region_a?.scores?.objective_opportunity_score} />
                <ScoreCard compact label={regionBLabel} value={comparison.region_b?.scores?.objective_opportunity_score} />
              </div>
            </div>
          </ShellCard>

          <ShellCard title={`${regionALabel} vs ${regionBLabel}`} eyebrow="Category-level score fields">
            <ComparisonScoreChart
              comparison={comparison}
              regionALabel={regionALabel}
              regionBLabel={regionBLabel}
            />
            <div className="comparison-score-table">
              <div className="comparison-table-head">
                <span>Category</span>
                <strong>{regionALabel}</strong>
                <strong>{regionBLabel}</strong>
                <strong>Winner</strong>
              </div>
              {SCORE_FIELDS.map((score) => {
                const aValue = comparison.region_a?.scores?.[score.key] as number | null | undefined;
                const bValue = comparison.region_b?.scores?.[score.key] as number | null | undefined;
                const hasWinner = Object.prototype.hasOwnProperty.call(categoryWinners, score.key);
                const winner = categoryWinners[score.key];
                const missing = typeof aValue !== "number" || typeof bValue !== "number";
                return (
                  <div className="comparison-table-row" key={score.key}>
                    <span>{score.label}</span>
                    <ScoreCard compact label={score.short} value={aValue} />
                    <ScoreCard compact label={score.short} value={bValue} />
                    <strong>{missing ? "Missing data" : hasWinner ? winnerLabel(winner, regions, comparison) : "Not available"}</strong>
                  </div>
                );
              })}
            </div>
          </ShellCard>

          <ShellCard title="Structured guidance" eyebrow="Evidence packet explanation">
            <p className="meta-copy">
              Guidance summarizes returned comparison fields only. Missing score values
              remain missing.
            </p>
            <ExplanationResultPanel
              emptyCopy="Use Explain guidance to render a constrained explanation from this comparison output."
              state={explanationState}
            />
          </ShellCard>

          <ShellCard title="Deferred visualizations" eyebrow="No unsupported precision">
            <UnsupportedVisualizationPanel
              items={["Trend view", "Map", "Heatmap"]}
              reason="The comparison response has current score fields only; it does not include historical snapshots or geographic precision."
            />
          </ShellCard>

          <div className="split-grid">
            <ShellCard title="Category winners" eyebrow="Separate from objective winner">
              {Object.keys(categoryWinners).length ? (
                <div className="winner-grid">
                  {Object.entries(categoryWinners).map(([category, winner]) => (
                    <div className="winner-card" key={category}>
                      <span>{prettyKey(category)}</span>
                      <strong>{winnerLabel(winner, regions, comparison)}</strong>
                      {winner ? <small>{winner}</small> : null}
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState
                  title="No resolved winners"
                  body="One or both regions may be missing comparable score values."
                />
              )}
            </ShellCard>

            <ShellCard title="Early-career tradeoffs" eyebrow="Accessibility signal">
              {typeof earlyCareerA === "number" && typeof earlyCareerB === "number" ? (
                <div className="tradeoff-grid">
                  <ScoreCard compact label={regionALabel} value={earlyCareerA} />
                  <ScoreCard compact label={regionBLabel} value={earlyCareerB} />
                  <p className="meta-copy">
                    {earlyCareerA === earlyCareerB
                      ? "Both regions return the same early-career accessibility score."
                      : `${earlyCareerA > earlyCareerB ? regionALabel : regionBLabel} has the higher early-career accessibility score in this comparison.`}
                  </p>
                </div>
              ) : (
                <EmptyState
                  title="Early-career comparison unavailable"
                  body="One or both regions are missing the early-career accessibility score."
                />
              )}
            </ShellCard>
          </div>

          <div className="split-grid">
            <ShellCard title="Source and freshness differences" eyebrow="Comparison confidence">
              <div className="source-compare-grid">
                <div className="source-compare-card">
                  <strong>{regionALabel}</strong>
                  {sourceAState.loading ? <LoadingBlock label="Loading source details" /> : null}
                  {sourceAState.error ? <ErrorState message={sourceAState.error} /> : null}
                  <QualityBadgeRow envelope={comparisonState.envelope} source={sourceA} />
                  {sourceA ? <MetadataPanel source={sourceA} /> : null}
                </div>
                <div className="source-compare-card">
                  <strong>{regionBLabel}</strong>
                  {sourceBState.loading ? <LoadingBlock label="Loading source details" /> : null}
                  {sourceBState.error ? <ErrorState message={sourceBState.error} /> : null}
                  <QualityBadgeRow envelope={comparisonState.envelope} source={sourceB} />
                  {sourceB ? <MetadataPanel source={sourceB} /> : null}
                </div>
              </div>
            </ShellCard>

            <ShellCard title="Limits and warnings" eyebrow="Do not overread">
              {limitations.length ? (
                <div className="warning-list">
                  {limitations.map((notice) => (
                    <div className="warning-item" key={notice}>
                      <div className="warning-header">
                        <span className="warning-code">Comparison caveat</span>
                      </div>
                      <p>{notice}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="No caveats returned" body="No comparison caveats were detected from returned metadata." />
              )}
              {notes.length ? (
                <ul className="notes-list">
                  {notes.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              ) : (
                <EmptyState title="No notes" body="The comparison output did not include notes." />
              )}
              <MetadataPanel envelope={comparisonState.envelope} />
            </ShellCard>
          </div>
        </>
      ) : null}
    </div>
  );
}

function PersonalizedDiscovery({
  regions,
  sourceStates,
  discoveryState,
  selectedRegions,
  roleTargets,
  industries,
  careerStage,
  prestigePreference,
  brandPreference,
  limit,
  onToggleRegion,
  onToggleRole,
  onToggleIndustry,
  onCareerStage,
  onPrestigePreference,
  onBrandPreference,
  onLimit,
  onSubmit,
  canSavePersonalOverlays,
  onSaveDiscoveryResult,
  onSaveRecommendationSnapshot,
}: {
  regions: RegionListItem[];
  sourceStates: Record<string, LoadState<SourceExplanation>>;
  discoveryState: LoadState<PersonalizedResult>;
  selectedRegions: string[];
  roleTargets: string[];
  industries: string[];
  careerStage: string;
  prestigePreference: string;
  brandPreference: string;
  limit: number;
  onToggleRegion: (regionId: string) => void;
  onToggleRole: (role: string) => void;
  onToggleIndustry: (industry: string) => void;
  onCareerStage: (stage: string) => void;
  onPrestigePreference: (level: string) => void;
  onBrandPreference: (level: string) => void;
  onLimit: (limit: number) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  canSavePersonalOverlays: boolean;
  onSaveDiscoveryResult: (discovery: PersonalizedResult) => void;
  onSaveRecommendationSnapshot: (discovery: PersonalizedResult) => void;
}) {
  const discovery = discoveryState.envelope?.data;
  const knownRegionIds = new Set(regions.map((region) => region.region_id));
  const unknownSelectedRegions = regions.length
    ? selectedRegions.filter((regionId) => !knownRegionIds.has(regionId))
    : [];
  const rankedRegions = discovery?.ranked_regions ?? [];
  const rankedCompanies = discovery?.ranked_companies ?? [];
  const rankedRegionCoverage = new Map(rankedRegions.map((region) => [region.region_id, region.coverage]));
  const regionListCoverage = new Map(regions.map((region) => [region.region_id, region.coverage]));
  const rankedRegionPriorityMarkets = new Map(
    rankedRegions.map((region) => [region.region_id, region.priority_market]),
  );
  const regionListPriorityMarkets = new Map(regions.map((region) => [region.region_id, region.priority_market]));

  return (
    <div className="view-grid">
      <ShellCard
        title="Personalized discovery"
        eyebrow="Request-scoped exploration"
        action={<QualityBadgeRow envelope={discoveryState.envelope} />}
      >
        <p className="lead-copy">
          Discovery scores are exploratory overlays on the returned market data. Filters are
          shareable in the URL, but generated results are not saved or restored after reload.
        </p>
        <form className="discovery-form" onSubmit={onSubmit}>
          <fieldset>
            <legend>Regions</legend>
            {regions.map((region) => (
              <label className="checkbox-label" key={region.region_id}>
                <input
                  checked={selectedRegions.includes(region.region_id)}
                  onChange={() => onToggleRegion(region.region_id)}
                  type="checkbox"
                />
                <span>{region.display_name}</span>
                <CoverageBadge coverage={region.coverage} />
                <PriorityMarketBadge priorityMarket={region.priority_market} />
              </label>
            ))}
            {unknownSelectedRegions.map((regionId) => (
              <label className="checkbox-label" key={regionId}>
                <input checked onChange={() => onToggleRegion(regionId)} type="checkbox" />
                <span>{regionId} (unknown)</span>
              </label>
            ))}
          </fieldset>

          <fieldset>
            <legend>Role targets</legend>
            <p className="fieldset-copy">Role fit only uses role-family summaries returned by the API.</p>
            {ROLE_TARGETS.map((role) => (
              <label className="checkbox-label" key={role}>
                <input
                  checked={roleTargets.includes(role)}
                  onChange={() => onToggleRole(role)}
                  type="checkbox"
                />
                <span>{prettyKey(role)}</span>
              </label>
            ))}
          </fieldset>

          <fieldset>
            <legend>Industries</legend>
            <p className="fieldset-copy">Industry fit comes from company sector fields, not inferred descriptions.</p>
            {INDUSTRY_OPTIONS.map((industry) => (
              <label className="checkbox-label" key={industry}>
                <input
                  checked={industries.includes(industry)}
                  onChange={() => onToggleIndustry(industry)}
                  type="checkbox"
                />
                <span>{prettyKey(industry)}</span>
              </label>
            ))}
          </fieldset>

          <div className="form-row">
            <label>
              Career stage
              <select value={careerStage} onChange={(event) => onCareerStage(event.target.value)}>
                {CAREER_STAGE_OPTIONS.map((stage) => (
                  <option key={stage} value={stage}>
                    {prettyKey(stage)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Limit
              <input
                max={25}
                min={1}
                onChange={(event) => onLimit(Number(event.target.value))}
                type="number"
                value={limit}
              />
            </label>
          </div>

          <div className="form-row">
            <label>
              Prestige preference
              <select value={prestigePreference} onChange={(event) => onPrestigePreference(event.target.value)}>
                {PREFERENCE_LEVELS.map((level) => (
                  <option key={level} value={level}>
                    {level}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Brand preference
              <select value={brandPreference} onChange={(event) => onBrandPreference(event.target.value)}>
                {PREFERENCE_LEVELS.map((level) => (
                  <option key={level} value={level}>
                    {level}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="preference-summary">
            <span className="badge">Roles: {roleTargets.length ? roleTargets.map(prettyKey).join(", ") : "neutral"}</span>
            <span className="badge">Industries: {industries.length ? industries.map(prettyKey).join(", ") : "neutral"}</span>
            <span className="badge">Prestige: {prestigePreference}</span>
            <span className="badge">Brand: {brandPreference}</span>
          </div>

          <button
            type="submit"
            disabled={!selectedRegions.length || Boolean(unknownSelectedRegions.length) || discoveryState.loading}
          >
            {discoveryState.loading ? "Running..." : "Run discovery"}
          </button>
        </form>
        {unknownSelectedRegions.length ? (
          <ErrorState message={`Discovery URL includes unknown region ID(s): ${unknownSelectedRegions.join(", ")}`} />
        ) : null}
        {discoveryState.error ? <ErrorState message={discoveryState.error} /> : null}
        <MetadataPanel envelope={discoveryState.envelope} />
        <CoverageWarningList warnings={pickEnvelopeWarnings(discoveryState.envelope)} />
        {discovery ? (
          <div className="account-inline-actions">
            <button
              className="secondary-button"
              disabled={!canSavePersonalOverlays}
              type="button"
              onClick={() => onSaveDiscoveryResult(discovery)}
            >
              {canSavePersonalOverlays ? "Save discovery result" : "Sign in to save result"}
            </button>
            <button
              className="secondary-button"
              disabled={!canSavePersonalOverlays}
              type="button"
              onClick={() => onSaveRecommendationSnapshot(discovery)}
            >
              {canSavePersonalOverlays ? "Save recommendation snapshot" : "Sign in to save snapshot"}
            </button>
          </div>
        ) : null}
      </ShellCard>

      {discovery ? (
        <div className="split-grid">
          <ShellCard title="Ranked regions" eyebrow="Exploratory market overlay">
            {rankedRegions.length ? (
              <div className="rank-list">
                {rankedRegions.map((region, index) => (
                  <div className="rank-row" key={region.region_id}>
                    <span className="rank-number">{index + 1}</span>
                    <div>
                      <strong>{region.display_name}</strong>
                      <CoverageBadge coverage={region.coverage} />
                      <PriorityMarketBadge priorityMarket={region.priority_market} />
                      <CoverageInlineNote coverage={region.coverage} />
                      <small>
                        Objective score: {formatValue(region.objective_opportunity_score)}
                      </small>
                      <div className="chip-row">
                        <QualityBadgeRow source={sourceForRegion(region.region_id, sourceStates)} />
                      </div>
                      <ul className="notes-list recommendation-notes">
                        {recommendationNotes(region.match_notes).map((note) => (
                          <li key={note}>{prettyKey(note)}</li>
                        ))}
                      </ul>
                    </div>
                    <ScoreCard compact label="Personalized" value={region.personal_market_score} />
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No ranked regions"
                body="The personalization response returned no ranked region rows for this request."
              />
            )}
          </ShellCard>

          <ShellCard title="Ranked company-region pairs" eyebrow="Preference fit components">
            {rankedCompanies.length ? (
              <div className="rank-list">
                {rankedCompanies.map((company, index) => {
                  const coverage = rankedRegionCoverage.get(company.region_id) ?? regionListCoverage.get(company.region_id);
                  const priorityMarket = rankedRegionPriorityMarkets.get(company.region_id)
                    ?? regionListPriorityMarkets.get(company.region_id);
                  return (
                    <div className="rank-row rank-row-company" key={`${company.company_id}-${company.region_id}`}>
                      <span className="rank-number">{index + 1}</span>
                      <div>
                        <strong>{company.company_name}</strong>
                        <CoverageBadge coverage={coverage} />
                        <PriorityMarketBadge priorityMarket={priorityMarket} />
                        <CoverageInlineNote coverage={coverage} />
                        <small>{company.region_display_name}</small>
                        <div className="chip-row">
                          <QualityBadgeRow source={sourceForRegion(company.region_id, sourceStates)} />
                        </div>
                        <ul className="notes-list recommendation-notes">
                          {recommendationNotes(company.match_notes).map((note) => (
                            <li key={note}>{prettyKey(note)}</li>
                          ))}
                        </ul>
                      </div>
                      <div className="fit-grid">
                        <ScoreCard compact label="Personal" value={company.personal_company_score} />
                        {preferenceInfluencesForCompany(company).map((item) => (
                          <ScoreCard compact key={item.label} label={item.label} value={item.value} />
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <EmptyState
                title="No ranked companies"
                body="The personalization response returned no ranked company-region rows for this request."
              />
            )}
          </ShellCard>
        </div>
      ) : (
        <EmptyState
          title="No discovery run yet"
          body="Choose URL-shareable filters and run the request-scoped personalization overlay."
        />
      )}
    </div>
  );
}

function recommendationTargetLabel(target?: { display_label?: string | null; target_id: string }) {
  return target?.display_label ?? target?.target_id ?? "Unknown target";
}

function evidenceBasisText(values?: string[]): string {
  return values?.length ? values.map(prettyKey).join(", ") : "No evidence basis returned";
}

function isHeuristicEvidence(values?: string[], support?: string): boolean {
  return support === "inferred" || Boolean(values?.includes("heuristic_inference"));
}

function evidenceBadgeClass(strength?: string): string {
  if (strength === "strong") return "badge badge-success";
  if (strength === "moderate") return "badge badge-real";
  if (strength === "weak" || strength === "missing" || strength === "inferred") return "badge badge-warning";
  return "badge badge-unknown";
}

function evidenceRefLabel(ref: RecommendationEvidenceReference): string {
  const anchor = ref.reference_id ?? ref.provenance?.source_ref_id ?? ref.provenance?.provenance_ref;
  return [
    prettyKey(ref.basis),
    ref.label ?? null,
    anchor ? `ref ${anchor}` : null,
  ].filter(Boolean).join(" · ");
}

function RecommendationGoalModeSelector({
  goalModes,
  loading,
  selectedGoalMode,
  onSelectGoalMode,
}: {
  goalModes: RecommendationGoalModeProfilePayload[];
  loading: boolean;
  selectedGoalMode: RecommendationGoalMode;
  onSelectGoalMode: (goalMode: RecommendationGoalMode) => void;
}) {
  const selected = goalModes.find((goal) => goal.goal_mode === selectedGoalMode);
  return (
    <div className="recommendation-control-grid">
      <label>
        Goal mode
        <select
          aria-label="Recommendation goal mode"
          disabled={loading || !goalModes.length}
          value={selectedGoalMode}
          onChange={(event) => {
            if (isRecommendationGoalMode(event.target.value)) {
              onSelectGoalMode(event.target.value);
            }
          }}
        >
          {(goalModes.length ? goalModes : [{
            goal_mode: DEFAULT_RECOMMENDATION_GOAL_MODE,
            label: "Maximize entry-level access",
            description: "Favor markets and employers with stronger early-career access signals.",
            prioritization_summary: "",
            weighted_components: [],
            penalty_components: [],
            missing_data_behavior: "",
            warnings: [],
          }]).map((goal) => (
            <option key={goal.goal_mode} value={goal.goal_mode}>
              {goal.label}
            </option>
          ))}
        </select>
      </label>
      <div className="recommendation-profile-card">
        <div className="metadata-row">
          <span className="badge">{selected?.label ?? prettyKey(selectedGoalMode)}</span>
          {selected?.warnings?.map((warning) => (
            <span className="badge badge-warning" key={warning}>{warning}</span>
          ))}
        </div>
        <p className="meta-copy">{selected?.description ?? "Goal mode metadata is loading."}</p>
        {selected?.prioritization_summary ? (
          <p className="meta-copy">{selected.prioritization_summary}</p>
        ) : null}
        {selected?.weighted_components?.length ? (
          <div className="component-chip-grid" aria-label="Goal mode weighted components">
            {selected.weighted_components.slice(0, 6).map((component) => (
              <span className={component.is_proxy ? "badge badge-warning" : "badge"} key={component.component}>
                {prettyKey(component.component)} · {Math.round(component.weight * 100)}%
                {component.is_proxy ? " · proxy" : ""}
              </span>
            ))}
          </div>
        ) : null}
        {selected?.missing_data_behavior ? (
          <p className="meta-copy">{selected.missing_data_behavior}</p>
        ) : null}
      </div>
    </div>
  );
}

function WeightedComponentList({ components }: { components: WeightedScoreComponent[] }) {
  if (!components.length) {
    return <EmptyState title="No components" body="No score components were returned in this section." />;
  }
  return (
    <div className="component-list">
      {components.map((component) => (
        <div className="component-row" key={`${component.component}-${component.weighted_value}-${component.is_proxy}`}>
          <div>
            <strong>{prettyKey(component.component)}</strong>
            <small>
              value {formatValue(component.value)} · weight {Math.round(component.weight * 100)}% · contribution{" "}
              {formatValue(component.weighted_value)}
            </small>
          </div>
          <div className="metadata-row">
            {component.is_proxy ? <span className="badge badge-warning">Proxy</span> : null}
            {component.inferred ? <span className="badge badge-warning">Inferred</span> : null}
            <span className="badge badge-unknown">{evidenceBasisText(component.evidence_basis)}</span>
          </div>
          {component.warning ? <p className="meta-copy">{component.warning}</p> : null}
        </div>
      ))}
    </div>
  );
}

function MissingComponentList({ components }: { components: MissingScoreComponent[] }) {
  if (!components.length) return null;
  return (
    <div className="warning-list" aria-label="Missing recommendation score components">
      {components.map((component) => (
        <div className="warning-item" key={component.component}>
          <div className="warning-header">
            <span className="warning-code">Missing component</span>
            <span className="badge badge-warning">{prettyKey(component.component)}</span>
          </div>
          <p>{component.unavailable_behavior}</p>
          {component.warning ? <small>{component.warning}</small> : null}
        </div>
      ))}
    </div>
  );
}

function PenaltyList({ penalties }: { penalties: AppliedRankingPenalty[] }) {
  if (!penalties.length) return null;
  return (
    <div className="warning-list" aria-label="Recommendation ranking penalties">
      {penalties.map((penalty) => (
        <div className="warning-item" key={`${penalty.component}-${penalty.penalty_value}`}>
          <div className="warning-header">
            <span className="warning-code">Penalty</span>
            <span className="badge badge-warning">{prettyKey(penalty.component)}</span>
            <span className="badge badge-unknown">-{formatValue(penalty.penalty_value)}</span>
          </div>
          <p>{penalty.explanation}</p>
          {penalty.is_proxy || penalty.inferred ? (
            <small>{penalty.is_proxy ? "Proxy" : ""}{penalty.is_proxy && penalty.inferred ? " · " : ""}{penalty.inferred ? "Inferred" : ""}</small>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function ClaimList({
  title,
  items,
}: {
  title: string;
  items: Array<RecommendationReason | RecommendationWeakness>;
}) {
  if (!items.length) return null;
  return (
    <div className="claim-list">
      <strong>{title}</strong>
      {items.map((item) => (
        <div className="claim-row" key={`${item.label}-${item.evidence_strength}`}>
          <div className="metadata-row">
            <span className={evidenceBadgeClass(item.evidence_strength)}>{prettyKey(item.evidence_strength)}</span>
            <span className={isHeuristicEvidence(item.evidence_basis, item.support) ? "badge badge-warning" : "badge"}>
              {item.support === "inferred" ? "Inferred" : "Direct"}
            </span>
            <span className="badge badge-unknown">{evidenceBasisText(item.evidence_basis)}</span>
          </div>
          <strong>{item.label}</strong>
          {item.detail ? <p className="meta-copy">{item.detail}</p> : null}
        </div>
      ))}
    </div>
  );
}

function TradeoffList({ tradeoffs }: { tradeoffs: RecommendationTradeoff[] }) {
  if (!tradeoffs.length) {
    return <EmptyState title="No tradeoffs returned" body="The ranking did not generate tradeoffs for this item." />;
  }
  return (
    <div className="claim-list">
      {tradeoffs.map((tradeoff) => (
        <div className="claim-row" key={`${tradeoff.tradeoff_category}-${tradeoff.label}`}>
          <div className="metadata-row">
            <span className="badge badge-warning">{prettyKey(tradeoff.tradeoff_category)}</span>
            <span className={evidenceBadgeClass(tradeoff.evidence_strength)}>{prettyKey(tradeoff.evidence_strength)}</span>
            {isHeuristicEvidence(tradeoff.evidence_basis, tradeoff.support) ? (
              <span className="badge badge-warning">Inferred</span>
            ) : null}
          </div>
          <strong>{tradeoff.label}</strong>
          <p className="meta-copy">Upside: {tradeoff.positive_side}</p>
          <p className="meta-copy">Downside: {tradeoff.negative_side}</p>
        </div>
      ))}
    </div>
  );
}

function ManualVerificationList({ items }: { items: RecommendationManualVerificationItem[] }) {
  if (!items.length) {
    return <EmptyState title="No manual checks returned" body="No manual verification items were attached." />;
  }
  return (
    <div className="claim-list">
      {items.map((item) => (
        <div className="claim-row" key={`${item.verification_category}-${item.label}`}>
          <div className="metadata-row">
            <span className="badge badge-warning">{prettyKey(item.verification_category)}</span>
            <span className={evidenceBadgeClass(item.evidence_strength)}>{prettyKey(item.evidence_strength)}</span>
          </div>
          <strong>{item.label}</strong>
          <p className="meta-copy">{item.question}</p>
          {item.rationale ? <small>{item.rationale}</small> : null}
        </div>
      ))}
    </div>
  );
}

function EvidenceReferencePanel({ refs }: { refs: RecommendationEvidenceReference[] }) {
  if (!refs.length) {
    return <EmptyState title="No evidence refs" body="No evidence references were attached to this section." />;
  }
  return (
    <div className="component-list">
      {refs.slice(0, 12).map((ref, index) => (
        <div className="component-row" key={`${ref.basis}-${ref.reference_id ?? index}`}>
          <div className="metadata-row">
            <span className={evidenceBadgeClass(ref.strength)}>{prettyKey(ref.strength)}</span>
            <span className="badge badge-unknown">{prettyKey(ref.basis)}</span>
          </div>
          <strong>{evidenceRefLabel(ref)}</strong>
          {ref.confidence ? (
            <small>
              Confidence: {formatValue(ref.confidence.confidence_status ?? ref.confidence.confidence_level)}
              {typeof ref.confidence.confidence_score === "number" ? ` · ${formatValue(ref.confidence.confidence_score)}` : ""}
            </small>
          ) : null}
          {ref.freshness ? (
            <small>
              Freshness: {formatValue(ref.freshness.freshness_status)} · sources {formatValue(ref.freshness.source_count)}
            </small>
          ) : null}
          {ref.provenance ? (
            <small>
              Provenance: {formatValue(ref.provenance.source_ref_id ?? ref.provenance.provenance_ref)}
            </small>
          ) : null}
          {ref.note ? <p className="meta-copy">{ref.note}</p> : null}
        </div>
      ))}
    </div>
  );
}

function RecommendationCard({ item }: { item: RecommendationRankingItem }) {
  const explanation = item.explanation;
  return (
    <article className="recommendation-card">
      <div className="recommendation-card-header">
        <span className="rank-number">{item.rank}</span>
        <div>
          <div className="metadata-row">
            <span className="badge">{prettyKey(item.target.target_type)}</span>
            <span className="badge badge-unknown">{prettyKey(item.goal_mode)}</span>
          </div>
          <h3>{recommendationTargetLabel(item.target)}</h3>
          <small>{item.target.target_id}</small>
        </div>
        <div className="recommendation-score-pair">
          <ScoreCard compact label="Final score" value={item.final_score} />
          <ScoreCard compact label="Normalized" value={item.normalized_score} />
        </div>
      </div>

      <div className="metadata-row">
        {typeof item.confidence_contribution === "number" ? (
          <span className="badge">Confidence contribution {formatValue(item.confidence_contribution)}</span>
        ) : null}
        {typeof item.freshness_contribution === "number" ? (
          <span className="badge">Freshness contribution {formatValue(item.freshness_contribution)}</span>
        ) : null}
        {typeof item.coverage_contribution === "number" ? (
          <span className="badge">Coverage contribution {formatValue(item.coverage_contribution)}</span>
        ) : null}
      </div>

      {item.warnings.length ? (
        <div className="warning-list">
          {item.warnings.map((warning) => (
            <div className="warning-item" key={warning}>
              <div className="warning-header">
                <span className="warning-code">Recommendation warning</span>
              </div>
              <p>{warning}</p>
            </div>
          ))}
        </div>
      ) : null}

      <details className="recommendation-details" open>
        <summary>Why this fits</summary>
        <ClaimList title="Fit reasons" items={explanation.fit_reasons} />
        <ClaimList title="Data strengths" items={explanation.data_strengths} />
      </details>

      <details className="recommendation-details" open>
        <summary>Score components and penalties</summary>
        <WeightedComponentList components={item.score_components_used.slice(0, 8)} />
        {item.score_components_proxy.length ? (
          <>
            <h3>Proxy or inferred components</h3>
            <WeightedComponentList components={item.score_components_proxy} />
          </>
        ) : null}
        <MissingComponentList components={item.score_components_missing} />
        <PenaltyList penalties={item.penalties_applied} />
      </details>

      <details className="recommendation-details" open>
        <summary>Tradeoffs</summary>
        <TradeoffList tradeoffs={explanation.tradeoffs} />
      </details>

      <details className="recommendation-details">
        <summary>Weak evidence and manual verification</summary>
        <ClaimList title="Weaknesses" items={explanation.weaknesses} />
        <ManualVerificationList items={explanation.manual_verification} />
      </details>

      <details className="recommendation-details">
        <summary>Evidence references</summary>
        <div className="metadata-row">
          {explanation.confidence_summary ? (
            <span className="badge">Confidence: {formatValue(explanation.confidence_summary.confidence_status ?? explanation.confidence_summary.confidence_level)}</span>
          ) : null}
          {explanation.freshness_summary ? (
            <span className="badge">Freshness: {formatValue(explanation.freshness_summary.freshness_status)}</span>
          ) : null}
          {explanation.provenance_refs.length ? (
            <span className="badge">Provenance refs: {explanation.provenance_refs.length}</span>
          ) : null}
          {explanation.coverage_warnings.length ? (
            <span className="badge badge-warning">Coverage warnings: {explanation.coverage_warnings.length}</span>
          ) : null}
        </div>
        <EvidenceReferencePanel refs={explanation.evidence_refs} />
      </details>
    </article>
  );
}

function RecommendationRankingSection({
  title,
  items,
  emptyTitle,
  emptyBody,
}: {
  title: string;
  items: RecommendationRankingItem[];
  emptyTitle: string;
  emptyBody: string;
}) {
  return (
    <ShellCard title={title} eyebrow="Deterministic ranking">
      {items.length ? (
        <div className="recommendation-card-list">
          {items.map((item) => (
            <RecommendationCard item={item} key={`${item.target.target_type}:${item.target.target_id}`} />
          ))}
        </div>
      ) : (
        <EmptyState title={emptyTitle} body={emptyBody} />
      )}
    </ShellCard>
  );
}

function StrategyRegionTargetList({
  title,
  items,
}: {
  title: string;
  items: StrategyRegionTarget[];
}) {
  return (
    <div className="strategy-section">
      <h3>{title}</h3>
      {items.length ? (
        <div className="stack-list">
          {items.map((item) => (
            <div className="stack-row" key={`${item.target_role}-${item.target.target_id}`}>
              <div className="metadata-row">
                <span className="badge">{prettyKey(item.target_role)}</span>
                <span className={evidenceBadgeClass(item.evidence_strength)}>{prettyKey(item.evidence_strength)}</span>
                {isHeuristicEvidence(item.evidence_basis, item.support) ? (
                  <span className="badge badge-warning">Heuristic / inferred</span>
                ) : null}
              </div>
              <strong>{recommendationTargetLabel(item.target)}</strong>
              <small>Source rank {item.source_rank} · score {formatValue(item.final_score)}</small>
              <p className="meta-copy">{item.rationale}</p>
              {item.tradeoff_categories.length ? (
                <div className="chip-row">
                  {item.tradeoff_categories.map((category) => (
                    <span className="badge badge-warning" key={category}>{prettyKey(category)}</span>
                  ))}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : (
        <EmptyState title={`No ${title.toLocaleLowerCase()}`} body="The strategy plan did not include items for this section." />
      )}
    </div>
  );
}

function StrategyTargetList({
  title,
  items,
}: {
  title: string;
  items: Array<StrategyCompanyTarget | StrategyCompanyCategoryTarget | StrategyRoleFamilyTarget>;
}) {
  return (
    <div className="strategy-section">
      <h3>{title}</h3>
      {items.length ? (
        <div className="stack-list">
          {items.map((item) => (
            <div className="stack-row" key={`${item.target.target_type}:${item.target.target_id}`}>
              <div className="metadata-row">
                <span className="badge">{prettyKey(item.target.target_type)}</span>
                <span className={evidenceBadgeClass(item.evidence_strength)}>{prettyKey(item.evidence_strength)}</span>
                {isHeuristicEvidence(item.evidence_basis, item.support) ? (
                  <span className="badge badge-warning">Heuristic / inferred</span>
                ) : null}
              </div>
              <strong>{recommendationTargetLabel(item.target)}</strong>
              {"final_score" in item ? <small>Score {formatValue(item.final_score)}</small> : null}
              <p className="meta-copy">{item.rationale}</p>
              {item.target.related_target_ids?.length ? (
                <small>Related targets: {item.target.related_target_ids.join(", ")}</small>
              ) : null}
            </div>
          ))}
        </div>
      ) : (
        <EmptyState title={`No ${title.toLocaleLowerCase()}`} body="No grounded items were returned for this section." />
      )}
    </div>
  );
}

function TimingGuidanceList({ items }: { items: StrategyTimingGuidance[] }) {
  if (!items.length) {
    return <EmptyState title="No timing guidance" body="No conservative timing guidance was returned." />;
  }
  return (
    <div className="stack-list">
      {items.map((item) => (
        <div className="stack-row" key={`${item.timing_category}-${item.label}`}>
          <div className="metadata-row">
            <span className="badge">{prettyKey(item.timing_category)}</span>
            <span className={evidenceBadgeClass(item.evidence_strength)}>{prettyKey(item.evidence_strength)}</span>
            {isHeuristicEvidence(item.evidence_basis, item.support) ? (
              <span className="badge badge-warning">Heuristic / inferred</span>
            ) : null}
          </div>
          <strong>{item.label}</strong>
          <p className="meta-copy">{item.guidance}</p>
        </div>
      ))}
    </div>
  );
}

function StrategyWatchlist({ items }: { items: StrategyWatchlistItem[] }) {
  if (!items.length) {
    return <EmptyState title="No watchlist items" body="No watchlist targets were returned for this strategy." />;
  }
  return (
    <div className="stack-list">
      {items.map((item) => (
        <div className="stack-row" key={`${item.watchlist_category}-${item.target.target_id}`}>
          <div className="metadata-row">
            <span className="badge badge-warning">{prettyKey(item.watchlist_category)}</span>
            <span className={evidenceBadgeClass(item.evidence_strength)}>{prettyKey(item.evidence_strength)}</span>
            {item.revisit_after_refresh ? <span className="badge badge-warning">Revisit after refresh</span> : null}
          </div>
          <strong>{recommendationTargetLabel(item.target)}</strong>
          <p className="meta-copy">{item.reason}</p>
          <p className="meta-copy">Upside: {item.upside}</p>
          <p className="meta-copy">Verify: {item.what_to_verify}</p>
        </div>
      ))}
    </div>
  );
}

function StrategyWarnings({ warnings }: { warnings: StrategyEvidenceWarning[] }) {
  if (!warnings.length) {
    return <EmptyState title="No strategy evidence warnings" body="The strategy plan did not return evidence warnings." />;
  }
  return (
    <div className="warning-list">
      {warnings.map((warning) => (
        <div className="warning-item" key={`${warning.warning_category}-${warning.label}`}>
          <div className="warning-header">
            <span className="warning-code">{prettyKey(warning.warning_category)}</span>
            <span className={evidenceBadgeClass(warning.evidence_strength)}>{prettyKey(warning.evidence_strength)}</span>
            {isHeuristicEvidence(warning.evidence_basis, warning.support) ? (
              <span className="badge badge-warning">Heuristic / inferred</span>
            ) : null}
          </div>
          <p>{warning.label}</p>
          {warning.detail ? <small>{warning.detail}</small> : null}
        </div>
      ))}
    </div>
  );
}

function MarketStrategyView({ strategy }: { strategy: RecommendationStrategyPayload["market_strategy_plan"] }) {
  return (
    <ShellCard title="Market strategy plan" eyebrow="Structured plan from ranked outputs">
      <div className="metadata-row">
        <span className="badge">{prettyKey(strategy.goal_mode)}</span>
        <span className="badge badge-unknown">{strategy.strategy_version}</span>
        <span className="badge">Sources: {strategy.source_recommendations.length}</span>
      </div>
      <div className="strategy-grid">
        <StrategyRegionTargetList title="Primary regions" items={strategy.primary_region_targets} />
        <StrategyRegionTargetList title="Secondary regions" items={strategy.secondary_region_targets} />
        <StrategyRegionTargetList title="Fallback regions" items={strategy.fallback_region_targets} />
        <div className="strategy-section">
          <h3>Watchlist</h3>
          <StrategyWatchlist items={strategy.watchlist_items} />
        </div>
        <StrategyTargetList title="Company targets" items={strategy.company_targets} />
        <StrategyTargetList title="Company categories" items={strategy.company_category_targets} />
        <StrategyTargetList title="Role-family guidance" items={strategy.role_family_targets} />
        <div className="strategy-section">
          <h3>Timing guidance</h3>
          <TimingGuidanceList items={strategy.timing_guidance} />
        </div>
      </div>
      <div className="split-grid">
        <div className="strategy-section">
          <h3>Manual verification checklist</h3>
          <div className="stack-list">
            {strategy.manual_verification_checklist.items.map((entry) => (
              <div className="stack-row" key={`${entry.item.verification_category}-${entry.item.label}`}>
                <ManualVerificationList items={[entry.item]} />
                <small>Source recommendations: {entry.source_recommendation_ids.join(", ")}</small>
              </div>
            ))}
          </div>
        </div>
        <div className="strategy-section">
          <h3>Evidence warnings</h3>
          <StrategyWarnings warnings={strategy.evidence_warnings} />
        </div>
      </div>
    </ShellCard>
  );
}

function UpgradePrompt({
  title,
  body,
  feature,
  decision,
  plans,
}: {
  title: string;
  body: string;
  feature: MonetizationFeatureKey;
  decision?: MonetizationAccessPreviewPayload["decision"] | null;
  plans?: Map<MonetizationPlanKey, MonetizationPlan>;
}) {
  const availableWith = decision && !decision.allowed && decision.upgrade_plan_keys.length
    ? decision.upgrade_plan_keys.map((planKey) => plans?.get(planKey)?.display_name ?? prettyKey(planKey)).join(", ")
    : null;
  return (
    <aside className="upgrade-prompt" data-feature={feature}>
      <div>
        <span className={decision?.allowed ? "badge badge-success" : "badge badge-real"}>
          {decision?.allowed ? "Available in your plan" : "Added workflow value"}
        </span>
        <strong>{title}</strong>
        <p>{body}</p>
        {decision ? <p className="meta-copy">{decision.reason}</p> : null}
        {availableWith ? <p className="meta-copy">View plans for {availableWith}.</p> : null}
      </div>
      <a className="secondary-button" href={plansUrl()}>
        Upgrade options
      </a>
    </aside>
  );
}

function IntegrationActionPanel({
  objectType,
  objectId,
  label,
  organizationId,
  sourceContext,
  canUseIntegrations,
  reminderType,
  showExports = true,
  onCreateExport,
  onCreateReminder,
  onCreateCareerPlatformExport,
}: {
  objectType: IntegrationProductObjectType;
  objectId: string;
  label: string;
  organizationId?: string | null;
  sourceContext?: Record<string, unknown>;
  canUseIntegrations: boolean;
  reminderType: IntegrationReminderType;
  showExports?: boolean;
  onCreateExport: (request: IntegrationExportCreateRequest) => void;
  onCreateReminder: (request: IntegrationReminderCreateRequest) => void;
  onCreateCareerPlatformExport?: (request: CareerPlatformExportRequest) => void;
}) {
  const disabled = !objectId || !canUseIntegrations;
  const reminderDate = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();
  const organizationScope = organizationId || null;
  const showCareerPlatforms = objectType === "company" && Boolean(onCreateCareerPlatformExport);

  return (
    <ShellCard title="Export and reminder actions" eyebrow="Layer 17A integrations">
      <p className="meta-copy">
        Exports are local files or prepared manual payloads. Calendar support creates an ICS file only.
      </p>
      <div className="integration-action-grid">
        {showExports ? INTEGRATION_EXPORT_OPTIONS.map((option) => (
          <button
            className="secondary-button compact-button"
            disabled={disabled}
            key={option.id}
            onClick={() =>
              onCreateExport({
                product_object_type: objectType,
                product_object_id: objectId,
                export_format: option.id,
                organization_id: organizationScope,
                source_context: sourceContext,
              })
            }
            title={option.description}
            type="button"
          >
            {option.label}
          </button>
        )) : null}
        <button
          className="secondary-button compact-button"
          disabled={disabled}
          onClick={() =>
            onCreateReminder({
              reminder_type: reminderType,
              product_object_type: objectType,
              product_object_id: objectId,
              title: `Review ${label}`,
              due_at: reminderDate,
              organization_id: organizationScope,
              timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
              description: `Review ${label} in Job Market Intelligence.`,
            })
          }
          title="Downloadable ICS file only"
          type="button"
        >
          ICS reminder
        </button>
      </div>
      <div className="metadata-row">
        <span className="badge badge-success">No OAuth</span>
        <span className="badge badge-success">No live sync</span>
        <span className="badge badge-success">No external writes</span>
        <span className="badge badge-unknown">Product authority retained</span>
      </div>
      {showCareerPlatforms ? (
        <>
          <div className="integration-action-grid">
            <button
              className="secondary-button compact-button"
              disabled={disabled}
              onClick={() =>
                onCreateCareerPlatformExport?.({
                  platform: "linkedin",
                  company_ids: [objectId],
                  employer_names: [],
                  organization_id: organizationScope,
                })
              }
              title="Manual LinkedIn company search export only"
              type="button"
            >
              LinkedIn manual search
            </button>
            <button
              className="secondary-button compact-button"
              disabled={disabled}
              onClick={() =>
                onCreateCareerPlatformExport?.({
                  platform: "handshake",
                  company_ids: [objectId],
                  employer_names: [],
                  organization_id: organizationScope,
                })
              }
              title="Manual Handshake employer lookup export only"
              type="button"
            >
              Handshake manual lookup
            </button>
          </div>
          <div className="metadata-row">
            <span className="badge badge-real">Deep link only</span>
            <span className="badge badge-real">Export only</span>
            <span className="badge badge-success">No scraping</span>
            <span className="badge badge-success">No ATS state</span>
          </div>
        </>
      ) : null}
      <div className="warning-list" aria-label="Deferred integration states">
        <div className="warning-item">
          <div className="warning-header">
            <span className="warning-code">Deferred direct integrations</span>
          </div>
          <p>
            Google Sheets, Notion, and Airtable receive prepared payloads only.
            Google Calendar and Outlook direct writes remain deferred behind the ICS file export.
          </p>
        </div>
      </div>
      {!canUseIntegrations ? (
        <p className="meta-copy">Sign in to create user-owned export and reminder records.</p>
      ) : null}
    </ShellCard>
  );
}

function PlanCard({
  plan,
  features,
  plansByKey,
  billingStatus,
  billingAction,
  authenticated,
  currentPlanKey,
  onStartCheckout,
}: {
  plan: MonetizationPlan;
  features: Map<MonetizationFeatureKey, MonetizationFeature>;
  plansByKey: Map<MonetizationPlanKey, MonetizationPlan>;
  billingStatus: BillingStatusPayload | null;
  billingAction: BillingActionState;
  authenticated: boolean;
  currentPlanKey: MonetizationPlanKey | null;
  onStartCheckout: (planKey: MonetizationPlanKey) => void;
}) {
  const visibleFeatureKeys = plan.included_feature_keys.slice(0, 7);
  const checkoutEligible = Boolean(
    billingStatus?.checkout_available
    && billingStatus.checkout_plan_keys.includes(plan.plan_key)
    && plan.plan_key !== "free",
  );
  const isCurrentPlan = currentPlanKey === plan.plan_key;
  return (
    <article className="plan-card">
      <div className="plan-card-topline">
        <span className={plan.plan_key === "free" ? "badge badge-success" : "badge"}>
          {prettyKey(plan.billing_interval)}
        </span>
        <span className="badge badge-unknown">{prettyKey(plan.buyer_kind)}</span>
      </div>
      <h3>{plan.display_name}</h3>
      <strong className="plan-price">{priceLabel(plan)}</strong>
      <p className="meta-copy">{plan.price.note}</p>
      <div className="chip-row">
        {plan.buyer_segment ? (
          <span className="badge badge-real">{segmentLabel(plan.buyer_segment)}</span>
        ) : null}
        {plan.intended_audience.map((segment) => (
          <span className="badge" key={segment}>{segmentLabel(segment)}</span>
        ))}
      </div>
      <div className="plan-section">
        <strong>Included features</strong>
        <ul>
          {visibleFeatureKeys.map((featureKey) => (
            <li key={featureKey}>{features.get(featureKey)?.display_name ?? prettyKey(featureKey)}</li>
          ))}
        </ul>
        {plan.included_feature_keys.length > visibleFeatureKeys.length ? (
          <small>{plan.included_feature_keys.length - visibleFeatureKeys.length} more feature(s)</small>
        ) : null}
      </div>
      {plan.usage_limits.length ? (
        <div className="plan-section">
          <strong>Usage limits</strong>
          <ul>
            {plan.usage_limits.map((limit) => (
              <li key={`${limit.feature_key}-${limit.unit}`}>{usageLimitLabel(limit)}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {plan.upgrade_plan_keys.length ? (
        <div className="plan-section">
          <strong>Upgrade path</strong>
          <p className="meta-copy">
            {plan.upgrade_plan_keys
              .map((planKey) => plansByKey.get(planKey)?.display_name ?? prettyKey(planKey))
              .join(", ")}
          </p>
        </div>
      ) : null}
      <div className="plan-action-row">
        {isCurrentPlan ? <span className="badge badge-success">Current plan</span> : null}
        {checkoutEligible ? (
          <button
            className="primary-button compact-button"
            disabled={!authenticated || billingAction.loadingPlanKey === plan.plan_key}
            onClick={() => onStartCheckout(plan.plan_key)}
            type="button"
          >
            {billingAction.loadingPlanKey === plan.plan_key ? "Creating session" : "Start checkout"}
          </button>
        ) : plan.plan_key !== "free" ? (
          <p className="meta-copy">
            {plan.buyer_kind === "institutional"
              ? "Institutional licenses remain sales-assisted."
              : billingStatus?.disabled_reason ?? "Checkout is not available for this plan."}
          </p>
        ) : null}
      </div>
    </article>
  );
}

function FeatureBoundaryPanel({ features }: { features: MonetizationFeature[] }) {
  const grouped = {
    free: orderedFeatures(features.filter((feature) => feature.boundary === "free")),
    paid: orderedFeatures(features.filter((feature) => feature.boundary === "paid")),
  };
  return (
    <div className="split-grid">
      <div className="feature-boundary-panel">
        <div className="metadata-row">
          <span className="badge badge-success">Free</span>
          <span className="badge badge-real">Basic guidance remains useful</span>
        </div>
        {grouped.free.map((feature) => (
          <div className="feature-row" key={feature.feature_key}>
            <strong>{feature.display_name}</strong>
            <p className="meta-copy">{feature.boundary_rationale}</p>
            {feature.exposes_core_recommendation_conclusion ? (
              <span className="badge badge-success">Basic recommendation result remains visible</span>
            ) : null}
          </div>
        ))}
      </div>
      <div className="feature-boundary-panel">
        <div className="metadata-row">
          <span className="badge badge-warning">Paid</span>
          <span className="badge badge-real">Workflow, coverage, reports</span>
        </div>
        {grouped.paid.map((feature) => (
          <div className="feature-row" key={feature.feature_key}>
            <strong>{feature.display_name}</strong>
            <p className="meta-copy">{feature.boundary_rationale}</p>
            <small>{feature.trust_constraint}</small>
          </div>
        ))}
      </div>
    </div>
  );
}

function ReportProductCard({
  report,
  features,
}: {
  report: MonetizationReportProduct;
  features: Map<MonetizationFeatureKey, MonetizationFeature>;
}) {
  return (
    <article className="report-product-card">
      <div className="metadata-row">
        {report.free_preview_available ? (
          <span className="badge badge-success">Free preview</span>
        ) : null}
        {report.paid_full_report_required ? (
          <span className="badge badge-warning">Full report requires paid feature</span>
        ) : null}
        {report.exportable ? <span className="badge badge-real">Exportable</span> : null}
      </div>
      <h3>{report.display_name}</h3>
      <div className="chip-row">
        {report.intended_segments.map((segment) => (
          <span className="badge" key={segment}>{segmentLabel(segment)}</span>
        ))}
      </div>
      <div className="plan-section">
        <strong>Included sections</strong>
        <ul>
          {report.included_sections.map((section) => (
            <li key={section}>{section}</li>
          ))}
        </ul>
      </div>
      <p className="meta-copy">
        Full report access maps to{" "}
        {report.paid_full_report_feature_keys
          .map((featureKey) => features.get(featureKey)?.display_name ?? prettyKey(featureKey))
          .join(", ")}
        .
      </p>
    </article>
  );
}

function MonetizationAccountPanel({
  meState,
  entitlementsState,
  usageState,
  plans,
  features,
  authenticated,
  billingStatus,
  billingAction,
  onManageBilling,
}: {
  meState: LoadState<MonetizationMePayload>;
  entitlementsState: LoadState<MonetizationEntitlementsPayload>;
  usageState: LoadState<MonetizationUsagePayload>;
  plans: Map<MonetizationPlanKey, MonetizationPlan>;
  features: Map<MonetizationFeatureKey, MonetizationFeature>;
  authenticated: boolean;
  billingStatus: BillingStatusPayload | null;
  billingAction: BillingActionState;
  onManageBilling: () => void;
}) {
  if (!authenticated) {
    return (
      <div className="account-entitlement-panel">
        <div className="metadata-row">
          <span className="badge badge-success">Free preview</span>
          <span className="badge badge-unknown">Account state not loaded</span>
        </div>
        <p className="meta-copy">
          Sign in to view account-specific plan status, usage limits, and available paid workflow features.
          Your free plan still includes basic recommendations and exploration.
        </p>
      </div>
    );
  }

  const entitlements = entitlementsState.envelope?.data?.entitlements ?? meState.envelope?.data?.entitlements ?? null;
  const usage = usageState.envelope?.data?.usage ?? [];
  const plan = entitlements ? plans.get(entitlements.plan_key) : null;

  return (
    <div className="account-entitlement-panel">
      <div className="metadata-row">
        <span className="badge badge-real">Current effective plan</span>
        <span className="badge">{plan?.display_name ?? (entitlements ? prettyKey(entitlements.plan_key) : "Loading")}</span>
        {entitlements?.account_status ? (
          <span className="badge badge-unknown">Status: {prettyKey(entitlements.account_status)}</span>
        ) : null}
      </div>
      {meState.loading || entitlementsState.loading || usageState.loading ? <LoadingBlock label="Loading account entitlements" /> : null}
      {meState.error ? <ErrorState message={meState.error} /> : null}
      {entitlementsState.error ? <ErrorState message={entitlementsState.error} /> : null}
      {usageState.error ? <ErrorState message={usageState.error} /> : null}
      {entitlements ? (
        <>
          <p className="meta-copy">
            {prettyKey(entitlements.account_type)} account. Free guidance remains available; paid workflow features are checked against this plan.
          </p>
          <div className="chip-row">
            {entitlements.included_feature_keys.slice(0, 10).map((featureKey) => (
              <span className="badge" key={featureKey}>{features.get(featureKey)?.display_name ?? prettyKey(featureKey)}</span>
            ))}
          </div>
          {entitlements.usage_limits.length ? (
            <div className="plan-section">
              <strong>Usage limits and counters</strong>
              <ul>
                {entitlements.usage_limits.map((limit) => {
                  const counter = usage.find((row) => row.feature_key === limit.feature_key);
                  const remaining = counter ? Math.max(counter.limit_count - counter.used_count, 0) : limit.limit;
                  return (
                    <li key={`${limit.feature_key}-${limit.unit}`}>
                      {features.get(limit.feature_key)?.display_name ?? prettyKey(limit.feature_key)}: {remaining} remaining of {limit.limit} {prettyKey(limit.unit)}
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : null}
          {billingStatus?.portal_available ? (
            <div className="plan-action-row">
              <button
                className="secondary-button"
                disabled={billingAction.loadingPortal}
                onClick={onManageBilling}
                type="button"
              >
                {billingAction.loadingPortal ? "Opening billing" : "Manage billing"}
              </button>
              <p className="meta-copy">
                Billing management opens through the provider portal only when a billing customer exists.
              </p>
            </div>
          ) : null}
        </>
      ) : !meState.loading && !entitlementsState.loading ? (
        <p className="meta-copy">Account entitlement state has not loaded yet.</p>
      ) : null}
    </div>
  );
}

function AccessPreviewPanel({
  previews,
  features,
  plans,
}: {
  previews: Record<string, LoadState<MonetizationAccessPreviewPayload>>;
  features: Map<MonetizationFeatureKey, MonetizationFeature>;
  plans: Map<MonetizationPlanKey, MonetizationPlan>;
}) {
  return (
    <div className="access-preview-grid">
      {ACCESS_PREVIEW_REQUESTS.map((request) => {
        const state = previews[accessPreviewKey(request)] ?? emptyLoadState<MonetizationAccessPreviewPayload>();
        const decision = state.envelope?.data?.decision;
        return (
          <div className="access-preview-card" key={accessPreviewKey(request)}>
            <div className="metadata-row">
              <span className={decision?.allowed ? "badge badge-success" : "badge badge-warning"}>
                {state.loading ? "Checking" : decision?.allowed ? "Available" : "View plans option"}
              </span>
              <span className="badge badge-unknown">
                {features.get(request.feature_key)?.display_name ?? prettyKey(request.feature_key)}
              </span>
            </div>
            {state.error ? <ErrorState message={state.error} /> : null}
            {decision ? (
              <>
                <p className="meta-copy">{decision.reason}</p>
                {decision.usage_limit ? (
                  <p className="meta-copy">
                    Usage limit: {usageLimitLabel(decision.usage_limit)}
                    {decision.remaining_usage !== null
                      ? ` · remaining in this preview: ${decision.remaining_usage}`
                      : ""}
                  </p>
                ) : null}
                {!decision.allowed && decision.upgrade_plan_keys.length ? (
                  <p className="meta-copy">
                    View plans for{" "}
                    {decision.upgrade_plan_keys
                      .map((planKey) => plans.get(planKey)?.display_name ?? prettyKey(planKey))
                      .join(", ")}
                    .
                  </p>
                ) : null}
              </>
            ) : !state.loading ? (
              <p className="meta-copy">Access preview has not loaded yet.</p>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function InstitutionDashboardView({
  auth,
  dashboardState,
  organizationsState,
  selectedOrganizationId,
  onLogin,
  onOpenAdvisor,
  onOpenDecisions,
  onOpenImports,
  onOpenReports,
  onSelectOrganization,
  onCreateIntegrationExport,
  onCreateIntegrationReminder,
}: {
  auth: FrontendAuthContextValue;
  dashboardState: LoadState<InstitutionDashboardPayload>;
  organizationsState: LoadState<InstitutionCurrentOrganizationsPayload>;
  selectedOrganizationId: string;
  onLogin: () => void;
  onOpenAdvisor: () => void;
  onOpenDecisions: () => void;
  onOpenImports: () => void;
  onOpenReports: () => void;
  onSelectOrganization: (organizationId: string) => void;
  onCreateIntegrationExport: (request: IntegrationExportCreateRequest) => void;
  onCreateIntegrationReminder: (request: IntegrationReminderCreateRequest) => void;
}) {
  if (!auth.isConfigured) {
    return (
      <div className="view-grid">
        <ShellCard title="Institution Dashboard" eyebrow="Authentication required">
          <EmptyState
            title="Institutional access is unavailable"
            body="Auth0 frontend configuration is required for organization-scoped dashboards."
          />
        </ShellCard>
      </div>
    );
  }

  if (!auth.isAuthenticated) {
    return (
      <div className="view-grid">
        <ShellCard
          title="Institution Dashboard"
          eyebrow="Signed out"
          action={<button type="button" onClick={onLogin}>Sign in</button>}
        >
          <EmptyState
            title="Sign in required"
            body="Institutional cohort dashboards are organization-scoped and require backend authorization."
          />
        </ShellCard>
      </div>
    );
  }

  const organizationRows = organizationsState.envelope?.data?.organizations ?? [];
  const selectedRow =
    organizationRows.find((row) => row.organization.organization_id === selectedOrganizationId)
    ?? organizationRows[0]
    ?? null;
  const dashboard = dashboardState.envelope?.data ?? null;

  return (
    <div className="view-grid">
      <ShellCard
        title="Institution Dashboard"
        eyebrow={selectedRow?.organization.name ?? "Organization context"}
        action={
          selectedRow ? (
            <div className="badge-stack">
              <button className="secondary-button compact-button" onClick={onOpenAdvisor} type="button">
                Advisor tools
              </button>
              <button className="secondary-button compact-button" onClick={onOpenDecisions} type="button">
                Decisions
              </button>
              <button className="secondary-button compact-button" onClick={onOpenReports} type="button">
                Reports
              </button>
              <button className="secondary-button compact-button" onClick={onOpenImports} type="button">
                Imports
              </button>
              <span className="badge badge-success">{selectedRow.membership.role}</span>
              <span className="badge">{selectedRow.organization.organization_type}</span>
            </div>
          ) : null
        }
      >
        {organizationsState.loading ? <LoadingBlock label="Loading organizations" /> : null}
        {organizationsState.error ? <ErrorState message={organizationsState.error} /> : null}
        {organizationRows.length > 1 ? (
          <div className="metadata-row">
            {organizationRows.map((row) => (
              <button
                className={
                  row.organization.organization_id === selectedOrganizationId
                    ? "primary-button compact-button"
                    : "secondary-button compact-button"
                }
                key={row.organization.organization_id}
                onClick={() => onSelectOrganization(row.organization.organization_id)}
                type="button"
              >
                {row.organization.name}
              </button>
            ))}
          </div>
        ) : null}
        {!organizationsState.loading && !organizationsState.error && !organizationRows.length ? (
          <EmptyState
            title="No institutional organization"
            body="Your account does not currently have an active institutional membership."
          />
        ) : null}
        {dashboardState.loading ? <LoadingBlock label="Loading cohort dashboard" /> : null}
        {dashboardState.error ? <ErrorState message={dashboardState.error} /> : null}
        {dashboard ? (
          <div className="stat-grid">
            <div className="stat-card">
              <span>Cohort size</span>
              <strong>{dashboard.cohort_size}</strong>
            </div>
            <div className="stat-card">
              <span>Visible safe summary</span>
              <strong>{dashboard.visible_student_count}</strong>
            </div>
            <div className="stat-card">
              <span>Suppression threshold</span>
              <strong>{dashboard.minimum_group_size}</strong>
            </div>
            <div className="stat-card">
              <span>Generated</span>
              <strong>{formatDateTime(dashboard.generated_at)}</strong>
            </div>
          </div>
        ) : null}
      </ShellCard>

      {dashboard && selectedRow ? (
        <IntegrationActionPanel
          canUseIntegrations={auth.isAuthenticated}
          label={`${selectedRow.organization.name} dashboard`}
          objectId={selectedRow.organization.organization_id}
          objectType="institutional_dashboard"
          onCreateExport={onCreateIntegrationExport}
          onCreateReminder={onCreateIntegrationReminder}
          organizationId={selectedRow.organization.organization_id}
          reminderType="institutional_report_review"
        />
      ) : null}

      {dashboard ? (
        <>
          <div className="split-grid">
            <InstitutionAggregateSection
              emptyBody="No target-market category met the minimum group threshold."
              items={dashboard.popular_target_markets}
              title="Popular Target Markets"
            />
            <InstitutionAggregateSection
              emptyBody="No role-interest category met the minimum group threshold."
              items={dashboard.role_interest_summary}
              title="Role Interest Distribution"
            />
          </div>

          <div className="split-grid">
            <InstitutionAggregateSection
              emptyBody="No saved-company category met the minimum group threshold."
              items={dashboard.saved_company_summary}
              title="Saved Company Trends"
            />
            <InstitutionAggregateSection
              emptyBody="No visible target market has enough demand context yet."
              items={dashboard.market_demand_trends}
              title="Market Demand Trends"
            />
          </div>

          <div className="split-grid">
            <InstitutionAggregateSection
              emptyBody="No visible target market currently carries a coverage-gap warning."
              items={dashboard.coverage_gaps}
              title="Coverage Gaps"
            />
            <ShellCard title="Privacy And Coverage Notes" eyebrow="Aggregate-first">
              <ul className="notes-list">
                {dashboard.privacy_notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
              {dashboard.suppressed_categories.length ? (
                <div className="warning-list" aria-label="Suppressed categories">
                  {dashboard.suppressed_categories.map((category) => (
                    <div className="warning-item" key={`${category.section}-${category.minimum_group_size}`}>
                      <div className="warning-header">
                        <span className="warning-code">{prettyKey(category.section)}</span>
                        <span className="badge badge-warning">Suppressed</span>
                      </div>
                      <p>
                        {category.suppressed_count} category bucket(s) withheld at
                        minimum group size {category.minimum_group_size}.
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="meta-copy">No low-sample categories were reported.</p>
              )}
              {dashboard.coverage_warnings.length ? (
                <div className="warning-list" aria-label="Coverage warnings">
                  {dashboard.coverage_warnings.map((warning) => (
                    <div className="warning-item" key={warning}>
                      <div className="warning-header">
                        <span className="warning-code">Coverage warning</span>
                      </div>
                      <p>{warning}</p>
                    </div>
                  ))}
                </div>
              ) : null}
              <p className="meta-copy">
                Data freshness: {formatValue(dashboard.data_freshness.freshness_status)} ·{" "}
                generated {formatDateTime(String(dashboard.data_freshness.generated_at ?? ""))}
              </p>
            </ShellCard>
          </div>
        </>
      ) : null}
    </div>
  );
}

function InstitutionDecisionInfrastructureView({
  auth,
  organizationsState,
  selectedOrganizationId,
  decisionDashboardState,
  curriculumState,
  workforceReportState,
  benchmarkState,
  onLogin,
  onOpenDashboard,
  onOpenReports,
  onSelectOrganization,
}: {
  auth: FrontendAuthContextValue;
  organizationsState: LoadState<InstitutionCurrentOrganizationsPayload>;
  selectedOrganizationId: string;
  decisionDashboardState: LoadState<InstitutionDecisionDashboardPayload>;
  curriculumState: LoadState<CurriculumMarketMappingPayload>;
  workforceReportState: LoadState<InstitutionWorkforceReportPayload>;
  benchmarkState: LoadState<InstitutionBenchmarkPayload>;
  onLogin: () => void;
  onOpenDashboard: () => void;
  onOpenReports: () => void;
  onSelectOrganization: (organizationId: string) => void;
}) {
  if (!auth.isConfigured) {
    return (
      <div className="view-grid">
        <ShellCard title="Institutional Decisions" eyebrow="Authentication required">
          <EmptyState
            title="Institutional decision infrastructure is unavailable"
            body="Auth0 frontend configuration is required for organization-scoped decision views."
          />
        </ShellCard>
      </div>
    );
  }

  if (!auth.isAuthenticated) {
    return (
      <div className="view-grid">
        <ShellCard
          title="Institutional Decisions"
          eyebrow="Signed out"
          action={<button type="button" onClick={onLogin}>Sign in</button>}
        >
          <EmptyState
            title="Sign in required"
            body="Institutional decision infrastructure is organization-scoped and requires backend authorization."
          />
        </ShellCard>
      </div>
    );
  }

  const organizationRows = organizationsState.envelope?.data?.organizations ?? [];
  const selectedRow =
    organizationRows.find((row) => row.organization.organization_id === selectedOrganizationId)
    ?? organizationRows[0]
    ?? null;
  const decisionDashboard = decisionDashboardState.envelope?.data ?? null;
  const curriculum = curriculumState.envelope?.data ?? null;
  const workforceReport = workforceReportState.envelope?.data ?? null;
  const benchmarks = benchmarkState.envelope?.data ?? null;
  const anyLoading =
    decisionDashboardState.loading
    || curriculumState.loading
    || workforceReportState.loading
    || benchmarkState.loading;
  const error =
    decisionDashboardState.error
    ?? curriculumState.error
    ?? workforceReportState.error
    ?? benchmarkState.error;
  const privacy =
    decisionDashboard?.privacy
    ?? curriculum?.privacy
    ?? workforceReport?.privacy
    ?? benchmarks?.privacy
    ?? null;

  return (
    <div className="view-grid">
      <ShellCard
        title="Institutional Decisions"
        eyebrow={selectedRow?.organization.name ?? "Organization context"}
        action={
          selectedRow ? (
            <div className="badge-stack">
              <button className="secondary-button compact-button" onClick={onOpenDashboard} type="button">
                Cohort dashboard
              </button>
              <button className="secondary-button compact-button" onClick={onOpenReports} type="button">
                Reports
              </button>
              <span className="badge badge-success">{selectedRow.membership.role}</span>
              <span className="badge">{selectedRow.organization.organization_type}</span>
            </div>
          ) : null
        }
      >
        {organizationsState.loading ? <LoadingBlock label="Loading organizations" /> : null}
        {organizationsState.error ? <ErrorState message={organizationsState.error} /> : null}
        {organizationRows.length > 1 ? (
          <div className="metadata-row">
            {organizationRows.map((row) => (
              <button
                className={
                  row.organization.organization_id === selectedOrganizationId
                    ? "primary-button compact-button"
                    : "secondary-button compact-button"
                }
                key={row.organization.organization_id}
                onClick={() => onSelectOrganization(row.organization.organization_id)}
                type="button"
              >
                {row.organization.name}
              </button>
            ))}
          </div>
        ) : null}
        {anyLoading ? <LoadingBlock label="Loading institutional decision infrastructure" /> : null}
        {error ? <ErrorState message={error} /> : null}
        {!anyLoading && !error && !selectedRow ? (
          <EmptyState
            title="No institutional organization"
            body="Your account does not currently have an active institutional membership."
          />
        ) : null}
        {decisionDashboard ? (
          <>
            <div className="metadata-row">
              <span className="badge badge-real">Forecast-aware decision view</span>
              <span className={confidenceBadgeClass(decisionDashboard.confidence.level)}>
                Confidence {decisionDashboard.confidence.level} · {Math.round(decisionDashboard.confidence.score * 100)}%
              </span>
              <span className="badge">Freshness {prettyKey(decisionDashboard.freshness)}</span>
              <span className="badge">Horizon {prettyKey(decisionDashboard.time_horizon)}</span>
            </div>
            <p className="meta-copy">{decisionDashboard.summary.what_is_happening}</p>
            <p className="meta-copy">{decisionDashboard.summary.why_it_matters}</p>
            <InstitutionDecisionEvidenceBlock evidence={decisionDashboard.summary.evidence} />
          </>
        ) : null}
      </ShellCard>

      {privacy ? <InstitutionPrivacyNotice privacy={privacy} /> : null}

      {decisionDashboard ? (
        <>
          <InstitutionDecisionSectionList
            title="Target Markets"
            sections={decisionDashboard.target_markets}
          />
          <InstitutionDecisionSectionList
            title="Regional Trends"
            sections={decisionDashboard.regional_trends}
          />
          <div className="split-grid">
            <InstitutionDecisionSectionList
              title="Program Alignment"
              sections={decisionDashboard.program_alignment}
            />
            <InstitutionDecisionSectionList
              title="Employer Geography"
              sections={decisionDashboard.employer_geography}
            />
          </div>
          <div className="split-grid">
            <InstitutionDecisionSectionList
              title="Internship Access"
              sections={decisionDashboard.internship_access}
            />
            <InstitutionDecisionSectionList
              title="Industry Demand"
              sections={decisionDashboard.industry_demand}
            />
          </div>
          <ShellCard title="Forecast Notes" eyebrow="Layer 21 bounded signals">
            {decisionDashboard.forecast_notes.length ? (
              <div className="warning-list">
                {decisionDashboard.forecast_notes.map((note) => (
                  <div className="warning-item" key={`${note.forecast_type}-${note.affected_entity}-${note.forecast_label}`}>
                    <div className="warning-header">
                      <span className="warning-code">{note.forecast_label}</span>
                      <span className="badge">{prettyKey(note.time_horizon)}</span>
                    </div>
                    <p>{note.safe_display_summary}</p>
                    <p className="meta-copy">
                      Confidence {formatValue(note.confidence.level)} · Historical depth {formatValue(note.historical_depth.observation_count)}
                    </p>
                    {note.reasoning_trail.length ? (
                      <ul className="notes-list">
                        {note.reasoning_trail.slice(0, 3).map((reason) => (
                          <li key={reason}>{reason}</li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No forecast notes available"
                body="Forecast notes appear only when producer-owned historical exports provide enough Layer 21 evidence."
              />
            )}
          </ShellCard>
          <ShellCard title="Recommended Actions" eyebrow="Decision support">
            <ul className="notes-list">
              {decisionDashboard.recommended_actions.map((action) => (
                <li key={action}>{action}</li>
              ))}
            </ul>
          </ShellCard>
          <InstitutionWarningsLimitationsCard
            warnings={decisionDashboard.warnings}
            limitations={decisionDashboard.limitations}
          />
        </>
      ) : null}

      {curriculum ? <InstitutionCurriculumMappingView payload={curriculum} /> : null}
      {workforceReport ? <InstitutionWorkforceReportView report={workforceReport} /> : null}
      {benchmarks ? <InstitutionBenchmarkView payload={benchmarks} /> : null}
    </div>
  );
}

function InstitutionPrivacyNotice({ privacy }: { privacy: InstitutionPrivacyMetadata }) {
  return (
    <ShellCard title="Privacy-Safe Aggregation" eyebrow={prettyKey(privacy.privacy_mode)}>
      <div className="stat-grid">
        <div className="stat-card">
          <span>Aggregation</span>
          <strong>{prettyKey(privacy.aggregation_level)}</strong>
        </div>
        <div className="stat-card">
          <span>Cohort size</span>
          <strong>{privacy.cohort_size}</strong>
        </div>
        <div className="stat-card">
          <span>Minimum cohort</span>
          <strong>{privacy.minimum_cohort_size}</strong>
        </div>
        <div className="stat-card">
          <span>Suppression</span>
          <strong>{privacy.suppression_applied ? "Applied" : "Not applied"}</strong>
        </div>
      </div>
      {privacy.suppression_applied ? (
        <div className="warning-list" aria-label="Suppressed data state">
          <div className="warning-item">
            <div className="warning-header">
              <span className="warning-code">Suppressed data</span>
              <span className="badge badge-warning">Minimum cohort rule</span>
            </div>
            <p>
              Some cohort-derived fields are withheld before rendering:
              {" "}
              {privacy.suppressed_fields.length
                ? privacy.suppressed_fields.map(prettyKey).join(", ")
                : "low-sample detail"}.
            </p>
          </div>
        </div>
      ) : null}
      <ul className="notes-list">
        {privacy.privacy_notes.slice(0, 4).map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
    </ShellCard>
  );
}

function InstitutionWarningsLimitationsCard({
  warnings,
  limitations,
}: {
  warnings?: string[];
  limitations?: string[];
}) {
  if (!warnings?.length && !limitations?.length) return null;
  return (
    <ShellCard title="Warnings And Limitations" eyebrow="Decision boundaries">
      <InstitutionWarningsLimitationsList warnings={warnings} limitations={limitations} />
    </ShellCard>
  );
}

function InstitutionWarningsLimitationsList({
  warnings,
  limitations,
}: {
  warnings?: string[];
  limitations?: string[];
}) {
  const warningItems = warnings ?? [];
  const limitationItems = limitations ?? [];
  if (!warningItems.length && !limitationItems.length) return null;
  return (
    <div className="warning-list" aria-label="Institutional warnings and limitations">
      {warningItems.map((warning) => (
        <div className="warning-item" key={`warning-${warning}`}>
          <div className="warning-header">
            <span className="warning-code">Warning</span>
            <span className="badge badge-warning">Review context</span>
          </div>
          <p>{warning}</p>
        </div>
      ))}
      {limitationItems.map((limitation) => (
        <div className="warning-item" key={`limitation-${limitation}`}>
          <div className="warning-header">
            <span className="warning-code">Limitation</span>
            <span className="badge">Decision boundary</span>
          </div>
          <p>{limitation}</p>
        </div>
      ))}
    </div>
  );
}

function InstitutionDecisionSectionList({
  title,
  sections,
}: {
  title: string;
  sections: InstitutionDecisionSection[];
}) {
  return (
    <ShellCard title={title} eyebrow="Decision sections">
      {sections.length ? (
        <div className="warning-list">
          {sections.slice(0, 5).map((section) => (
            <InstitutionDecisionSectionCard key={section.section_key} section={section} />
          ))}
        </div>
      ) : (
        <EmptyState
          title={`${title} unavailable`}
          body="This section needs more aggregate or market-level evidence before it can be displayed."
        />
      )}
    </ShellCard>
  );
}

function InstitutionDecisionSectionCard({ section }: { section: InstitutionDecisionSection }) {
  return (
    <div className="warning-item">
      <div className="warning-header">
        <span className="warning-code">{section.title}</span>
        <span className={confidenceBadgeClass(section.evidence.confidence.level)}>
          {prettyKey(section.evidence.confidence.level)}
        </span>
      </div>
      <p>{section.what_is_happening}</p>
      <p className="meta-copy">{section.why_it_matters}</p>
      {section.metrics.length ? <InstitutionDecisionMetricList metrics={section.metrics} /> : null}
      {section.considerations.length ? (
        <ul className="notes-list">
          {section.considerations.slice(0, 3).map((consideration) => (
            <li key={consideration}>{consideration}</li>
          ))}
        </ul>
      ) : null}
      {section.warnings.length ? (
        <div className="coverage-warning-list">
          {section.warnings.map((warning) => (
            <span className="badge badge-warning" key={warning}>{warning}</span>
          ))}
        </div>
      ) : null}
      <InstitutionDecisionEvidenceBlock evidence={section.evidence} />
    </div>
  );
}

function InstitutionDecisionMetricList({ metrics }: { metrics: InstitutionDecisionMetric[] }) {
  return (
    <div className="stat-grid">
      {metrics.slice(0, 4).map((metric) => (
        <div className="stat-card" key={`${metric.metric_key}-${metric.label}`}>
          <span>{metric.label}</span>
          <strong>
            {formatValue(metric.value)}
            {metric.unit ? ` ${metric.unit}` : ""}
          </strong>
          <p>{metric.decision_use}</p>
        </div>
      ))}
    </div>
  );
}

function InstitutionDecisionEvidenceBlock({ evidence }: { evidence: InstitutionDecisionEvidence }) {
  return (
    <div className="forecast-detail-grid">
      <div className="forecast-detail-block">
        <strong>Source basis</strong>
        <p>{evidence.source_basis.map(prettyKey).join(", ") || "Unknown"}</p>
      </div>
      <div className="forecast-detail-block">
        <strong>Historical depth</strong>
        <p>
          {Object.entries(evidence.historical_depth)
            .map(([key, value]) => `${prettyKey(key)}: ${formatValue(value)}`)
            .join(" · ") || "Unknown"}
        </p>
      </div>
      <div className="forecast-detail-block">
        <strong>Provenance</strong>
        <p>{evidence.provenance.join(", ") || "Unknown"}</p>
      </div>
    </div>
  );
}

function InstitutionCurriculumMappingView({ payload }: { payload: CurriculumMarketMappingPayload }) {
  return (
    <ShellCard title="Curriculum-To-Market Mapping" eyebrow="Programs and markets">
      <div className="warning-list">
        {payload.programs.map((program) => (
          <div className="warning-item" key={program.program_name}>
            <div className="warning-header">
              <span className="warning-code">{program.program_name}</span>
              <span className={confidenceBadgeClass(program.confidence.level)}>
                {prettyKey(program.confidence.level)}
              </span>
            </div>
            <p className="meta-copy">
              Role families: {program.relevant_role_families.join(", ") || "Sparse"}
            </p>
            <InstitutionDecisionMetricList metrics={program.strongest_aligned_markets} />
            <p className="meta-copy">
              Skills with rising demand: {program.skills_with_rising_demand.join(", ") || "Sparse"}
            </p>
            <p className="meta-copy">
              Employer targets: {program.employer_relationship_targets.join(", ") || "Sparse"}
            </p>
            <ul className="notes-list">
              {program.advising_recommendations.map((recommendation) => (
                <li key={recommendation}>{recommendation}</li>
              ))}
            </ul>
            {program.sparse_data_warnings.length ? (
              <div className="coverage-warning-list">
                {program.sparse_data_warnings.map((warning) => (
                  <span className="badge badge-warning" key={warning}>{warning}</span>
                ))}
              </div>
            ) : null}
          </div>
        ))}
      </div>
      <InstitutionWarningsLimitationsList
        warnings={payload.warnings}
        limitations={payload.limitations}
      />
    </ShellCard>
  );
}

function InstitutionWorkforceReportView({ report }: { report: InstitutionWorkforceReportPayload }) {
  return (
    <ShellCard title={report.title} eyebrow={prettyKey(report.report_type)}>
      <div className="metadata-row">
        <span className={confidenceBadgeClass(report.confidence.level)}>
          Confidence {prettyKey(report.confidence.level)}
        </span>
        <span className="badge">Freshness {prettyKey(report.freshness)}</span>
        <span className="badge">Audience {report.audience}</span>
      </div>
      <p className="meta-copy">{report.summary}</p>
      <p className="meta-copy">{report.privacy_statement}</p>
      <InstitutionDecisionMetricList metrics={report.supporting_metrics} />
      <div className="split-grid">
        <div>
          <strong>Key findings</strong>
          <ul className="notes-list">
            {report.key_findings.map((finding) => (
              <li key={finding}>{finding}</li>
            ))}
          </ul>
        </div>
        <div>
          <strong>Recommended actions</strong>
          <ul className="notes-list">
            {report.recommended_actions.map((action) => (
              <li key={action}>{action}</li>
            ))}
          </ul>
        </div>
      </div>
      <InstitutionWarningsLimitationsList
        warnings={report.warnings}
        limitations={report.limitations}
      />
    </ShellCard>
  );
}

function InstitutionBenchmarkView({ payload }: { payload: InstitutionBenchmarkPayload }) {
  return (
    <ShellCard title="Institutional Benchmarks" eyebrow="Market opportunity comparison">
      <div className="warning-list">
        {payload.benchmarks.map((benchmark) => (
          <div className="warning-item" key={benchmark.benchmark_subject}>
            <div className="warning-header">
              <span className="warning-code">{benchmark.benchmark_subject}</span>
              <span className="badge badge-real">Gap {benchmark.gap_score}</span>
            </div>
            <div className="stat-grid">
              <div className="stat-card">
                <span>Opportunity</span>
                <strong>{benchmark.opportunity_score}</strong>
              </div>
              <div className="stat-card">
                <span>Alignment</span>
                <strong>{benchmark.alignment_score}</strong>
              </div>
              <div className="stat-card">
                <span>Emerging gap</span>
                <strong>{benchmark.emerging_region_gap}</strong>
              </div>
              <div className="stat-card">
                <span>Employer gap</span>
                <strong>{benchmark.employer_access_gap}</strong>
              </div>
              <div className="stat-card">
                <span>Internship gap</span>
                <strong>{benchmark.internship_access_gap}</strong>
              </div>
            </div>
            <p>{benchmark.recommendation_summary}</p>
            <p className="meta-copy">
              Comparison markets: {benchmark.comparison_market_set.join(", ") || "Sparse"}
            </p>
            <ul className="notes-list">
              {benchmark.supporting_rationale.map((rationale) => (
                <li key={rationale}>{rationale}</li>
              ))}
            </ul>
            {benchmark.warnings.length ? (
              <div className="coverage-warning-list">
                {benchmark.warnings.map((warning) => (
                  <span className="badge badge-warning" key={warning}>{warning}</span>
                ))}
              </div>
            ) : null}
          </div>
        ))}
      </div>
      <InstitutionWarningsLimitationsList
        warnings={payload.warnings}
        limitations={payload.limitations}
      />
    </ShellCard>
  );
}

function confidenceBadgeClass(level: string): string {
  const normalized = level.toLowerCase();
  if (normalized === "high") return "badge badge-success";
  if (normalized === "medium") return "badge badge-real";
  if (normalized === "insufficient") return "badge badge-warning";
  return "badge badge-unknown";
}

function InstitutionAdvisorWorkspace({
  auth,
  advisorState,
  organizationsState,
  selectedOrganizationId,
  onLogin,
  onOpenDashboard,
  onOpenImports,
  onOpenReports,
  onSelectOrganization,
  onSubmit,
}: {
  auth: FrontendAuthContextValue;
  advisorState: LoadState<InstitutionAdvisorToolResponse>;
  organizationsState: LoadState<InstitutionCurrentOrganizationsPayload>;
  selectedOrganizationId: string;
  onLogin: () => void;
  onOpenDashboard: () => void;
  onOpenImports: () => void;
  onOpenReports: () => void;
  onSelectOrganization: (organizationId: string) => void;
  onSubmit: (
    comparisonType: InstitutionAdvisorComparisonType,
    request: InstitutionAdvisorRequest,
  ) => void;
}) {
  const [comparisonType, setComparisonType] =
    useState<InstitutionAdvisorComparisonType>("regions");
  const [formState, setFormState] = useState<AdvisorFormState>({
    ...DEFAULT_ADVISOR_FORM_STATE,
  });
  const [formError, setFormError] = useState<string | null>(null);

  if (!auth.isConfigured) {
    return (
      <div className="view-grid">
        <ShellCard title="Advisor Tools" eyebrow="Authentication required">
          <EmptyState
            title="Advisor workspace is unavailable"
            body="Auth0 frontend configuration is required for organization-scoped advisor tools."
          />
        </ShellCard>
      </div>
    );
  }

  if (!auth.isAuthenticated) {
    return (
      <div className="view-grid">
        <ShellCard
          title="Advisor Tools"
          eyebrow="Signed out"
          action={<button type="button" onClick={onLogin}>Sign in</button>}
        >
          <EmptyState
            title="Sign in required"
            body="Advisor tools are organization-scoped and require backend authorization."
          />
        </ShellCard>
      </div>
    );
  }

  const organizationRows = organizationsState.envelope?.data?.organizations ?? [];
  const selectedRow =
    organizationRows.find((row) => row.organization.organization_id === selectedOrganizationId)
    ?? organizationRows[0]
    ?? null;
  const result = advisorState.envelope?.data ?? null;

  function updateField(field: keyof AdvisorFormState, value: string) {
    setFormState((current) => ({ ...current, [field]: value }));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const { request, error } = advisorRequestFromForm(comparisonType, formState);
    if (!request || error) {
      setFormError(error ?? "Advisor request is incomplete.");
      return;
    }
    setFormError(null);
    onSubmit(comparisonType, request);
  }

  return (
    <div className="view-grid">
      <ShellCard
        title="Advisor Tools"
        eyebrow={selectedRow?.organization.name ?? "Organization context"}
        action={
          selectedRow ? (
            <div className="badge-stack">
              <button className="secondary-button compact-button" onClick={onOpenDashboard} type="button">
                Cohort dashboard
              </button>
              <button className="secondary-button compact-button" onClick={onOpenReports} type="button">
                Reports
              </button>
              <button className="secondary-button compact-button" onClick={onOpenImports} type="button">
                Imports
              </button>
              <span className="badge badge-success">{selectedRow.membership.role}</span>
              <span className="badge">{selectedRow.organization.organization_type}</span>
            </div>
          ) : null
        }
      >
        {organizationsState.loading ? <LoadingBlock label="Loading organizations" /> : null}
        {organizationsState.error ? <ErrorState message={organizationsState.error} /> : null}
        {organizationRows.length > 1 ? (
          <div className="metadata-row">
            {organizationRows.map((row) => (
              <button
                className={
                  row.organization.organization_id === selectedOrganizationId
                    ? "primary-button compact-button"
                    : "secondary-button compact-button"
                }
                key={row.organization.organization_id}
                onClick={() => onSelectOrganization(row.organization.organization_id)}
                type="button"
              >
                {row.organization.name}
              </button>
            ))}
          </div>
        ) : null}
        {!organizationsState.loading && !organizationsState.error && !organizationRows.length ? (
          <EmptyState
            title="No institutional organization"
            body="Your account does not currently have an active institutional membership."
          />
        ) : null}
        <p className="meta-copy">
          Advisor tools compare existing market intelligence, coverage, and explanation
          signals. They do not expose raw student searches, saved companies,
          recommendations, or personal activity.
        </p>
      </ShellCard>

      <div className="split-grid">
        <ShellCard title="Comparison Workspace" eyebrow="Guidance tool">
          <form className="account-form-grid" onSubmit={handleSubmit}>
            <label>
              Comparison type
              <select
                aria-label="Comparison type"
                onChange={(event) =>
                  setComparisonType(event.target.value as InstitutionAdvisorComparisonType)
                }
                value={comparisonType}
              >
                {ADVISOR_COMPARISON_OPTIONS.map((option) => (
                  <option key={option.id} value={option.id}>{option.label}</option>
                ))}
              </select>
            </label>

            {comparisonType === "regions" ? (
              <>
                <AdvisorTextField
                  label="Regions"
                  onChange={(value) => updateField("regions", value)}
                  value={formState.regions}
                />
                <AdvisorTextField
                  label="Role context"
                  onChange={(value) => updateField("roleContext", value)}
                  value={formState.roleContext}
                />
                <AdvisorTextField
                  label="Industry context"
                  onChange={(value) => updateField("industryContext", value)}
                  value={formState.industryContext}
                />
                <AdvisorTextField
                  label="Career stage"
                  onChange={(value) => updateField("careerStage", value)}
                  value={formState.careerStage}
                />
              </>
            ) : null}

            {comparisonType === "industries" ? (
              <>
                <AdvisorTextField
                  label="Industries"
                  onChange={(value) => updateField("industries", value)}
                  value={formState.industries}
                />
                <AdvisorTextField
                  label="Region context"
                  onChange={(value) => updateField("regionContext", value)}
                  value={formState.regionContext}
                />
                <AdvisorTextField
                  label="Career stage"
                  onChange={(value) => updateField("careerStage", value)}
                  value={formState.careerStage}
                />
              </>
            ) : null}

            {comparisonType === "companies" ? (
              <>
                <AdvisorTextField
                  label="Companies"
                  onChange={(value) => updateField("companies", value)}
                  value={formState.companies}
                />
                <AdvisorTextField
                  label="Region context"
                  onChange={(value) => updateField("regionContext", value)}
                  value={formState.regionContext}
                />
                <AdvisorTextField
                  label="Industry context"
                  onChange={(value) => updateField("industryContext", value)}
                  value={formState.industryContext}
                />
                <AdvisorTextField
                  label="Career stage"
                  onChange={(value) => updateField("careerStage", value)}
                  value={formState.careerStage}
                />
              </>
            ) : null}

            {comparisonType === "career_stages" ? (
              <>
                <AdvisorTextField
                  label="Career stages"
                  onChange={(value) => updateField("careerStages", value)}
                  value={formState.careerStages}
                />
                <AdvisorTextField
                  label="Region context"
                  onChange={(value) => updateField("regionContext", value)}
                  value={formState.regionContext}
                />
                <AdvisorTextField
                  label="Company context"
                  onChange={(value) => updateField("companyContext", value)}
                  value={formState.companyContext}
                />
                <AdvisorTextField
                  label="Industry context"
                  onChange={(value) => updateField("industryContext", value)}
                  value={formState.industryContext}
                />
              </>
            ) : null}

            {comparisonType === "application_timing" ? (
              <>
                <AdvisorTextField
                  label="Target regions"
                  onChange={(value) => updateField("regions", value)}
                  value={formState.regions}
                />
                <AdvisorTextField
                  label="Target industries"
                  onChange={(value) => updateField("industries", value)}
                  value={formState.industries}
                />
                <AdvisorTextField
                  label="Target companies"
                  onChange={(value) => updateField("companies", value)}
                  value={formState.companies}
                />
                <AdvisorTextField
                  label="Career stage"
                  onChange={(value) => updateField("careerStage", value)}
                  value={formState.careerStage}
                />
                <AdvisorTextField
                  label="Application window"
                  onChange={(value) => updateField("applicationWindow", value)}
                  value={formState.applicationWindow}
                />
              </>
            ) : null}

            {formError ? <ErrorState message={formError} /> : null}
            <div className="metadata-row">
              <button
                className="primary-button"
                disabled={advisorState.loading || !selectedRow}
                type="submit"
              >
                Run advisor comparison
              </button>
              {advisorState.loading ? <span className="badge badge-partial">Running</span> : null}
            </div>
          </form>
        </ShellCard>

        <ShellCard title="Privacy Boundary" eyebrow="Education-privacy-aware">
          <ul className="notes-list">
            <li>Advisor access is authorized by backend organization membership checks.</li>
            <li>Student-specific advising remains disabled until explicit scoped consent exists.</li>
            <li>Outputs are decision-support guidance, not outcome guarantees.</li>
          </ul>
        </ShellCard>
      </div>

      {advisorState.error ? <ErrorState message={advisorState.error} /> : null}
      {advisorState.loading && !result ? <LoadingBlock label="Running advisor comparison" /> : null}
      {result ? <InstitutionAdvisorResults result={result} /> : null}
    </div>
  );
}

function AdvisorTextField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label>
      {label}
      <input value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function InstitutionAdvisorResults({ result }: { result: InstitutionAdvisorToolResponse }) {
  return (
    <>
      <ShellCard title="Advisor Guidance Results" eyebrow={segmentLabel(result.comparison_type)}>
        <div className="stat-grid">
          <div className="stat-card">
            <span>Comparison</span>
            <strong>{segmentLabel(result.comparison_type)}</strong>
          </div>
          <div className="stat-card">
            <span>Items compared</span>
            <strong>{result.compared_items.length}</strong>
          </div>
          <div className="stat-card">
            <span>Generated</span>
            <strong>{formatDateTime(result.generated_at)}</strong>
          </div>
          <div className="stat-card">
            <span>Freshness</span>
            <strong>{formatValue(result.data_freshness.freshness_status)}</strong>
          </div>
        </div>
        {result.guidance.length ? (
          <ul className="notes-list">
            {result.guidance.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : null}
      </ShellCard>

      <div className="split-grid">
        <ShellCard title="Compared Options" eyebrow="Market signals">
          {result.compared_items.length ? (
            <div className="stack-list">
              {result.compared_items.map((item) => (
                <InstitutionAdvisorComparedItemCard item={item} key={`${item.item_type}-${item.item_id}`} />
              ))}
            </div>
          ) : (
            <EmptyState title="No compared options" body="The advisor service returned no comparison items." />
          )}
        </ShellCard>

        <ShellCard title="Tradeoffs And Warnings" eyebrow="Decision support">
          {result.tradeoffs.length ? (
            <div className="stack-list">
              {result.tradeoffs.map((tradeoff) => (
                <InstitutionAdvisorTradeoffCard key={`${tradeoff.category}-${tradeoff.summary}`} tradeoff={tradeoff} />
              ))}
            </div>
          ) : (
            <p className="meta-copy">No tradeoff summary was returned.</p>
          )}
          {result.coverage_warnings.length ? (
            <div className="warning-list" aria-label="Advisor coverage warnings">
              {result.coverage_warnings.map((warning) => (
                <div className="warning-item" key={warning}>
                  <div className="warning-header">
                    <span className="warning-code">Coverage warning</span>
                  </div>
                  <p>{warning}</p>
                </div>
              ))}
            </div>
          ) : null}
        </ShellCard>
      </div>

      <ShellCard title="Limitations And Privacy Notes" eyebrow="Boundary">
        <div className="split-grid">
          <ul className="notes-list">
            {result.limitations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <ul className="notes-list">
            {result.privacy_notes.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </ShellCard>
    </>
  );
}

function InstitutionAdvisorComparedItemCard({ item }: { item: InstitutionAdvisorComparedItem }) {
  const signalEntries = Object.entries(item.demand_signals);
  return (
    <div className="stack-row">
      <div className="metadata-row">
        <strong>{item.label}</strong>
        <span className="badge">{prettyKey(item.item_type)}</span>
      </div>
      {item.explanation_summary.length ? (
        <ul className="notes-list">
          {item.explanation_summary.map((summary) => (
            <li key={summary}>{summary}</li>
          ))}
        </ul>
      ) : null}
      {signalEntries.length ? (
        <div className="metadata-row">
          {signalEntries.map(([key, value]) => (
            <span className="badge badge-unknown" key={key}>
              {prettyKey(key)}: {formatAdvisorSignalValue(value)}
            </span>
          ))}
        </div>
      ) : null}
      {item.coverage ? (
        <small>
          Coverage: {Object.entries(item.coverage)
            .map(([key, value]) => `${prettyKey(key)} ${formatAdvisorSignalValue(value)}`)
            .join(" · ")}
        </small>
      ) : null}
      {item.warnings.length ? (
        <div className="warning-list">
          {item.warnings.map((warning) => (
            <div className="warning-item" key={warning}>
              <div className="warning-header">
                <span className="warning-code">Item warning</span>
              </div>
              <p>{warning}</p>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function InstitutionAdvisorTradeoffCard({ tradeoff }: { tradeoff: InstitutionAdvisorTradeoff }) {
  return (
    <div className="stack-row">
      <div className="metadata-row">
        <strong>{prettyKey(tradeoff.category)}</strong>
        <span className="badge">{tradeoff.evidence_level}</span>
      </div>
      <span>{tradeoff.summary}</span>
    </div>
  );
}

function InstitutionReportsView({
  auth,
  reportState,
  reportListState,
  organizationsState,
  selectedOrganizationId,
  onLogin,
  onOpenDashboard,
  onOpenDataRequests,
  onOpenImports,
  onSelectOrganization,
  onGenerate,
  onCreateIntegrationExport,
  onCreateIntegrationReminder,
}: {
  auth: FrontendAuthContextValue;
  reportState: LoadState<InstitutionReportGeneratePayload>;
  reportListState: LoadState<InstitutionReportListPayload>;
  organizationsState: LoadState<InstitutionCurrentOrganizationsPayload>;
  selectedOrganizationId: string;
  onLogin: () => void;
  onOpenDashboard: () => void;
  onOpenDataRequests: () => void;
  onOpenImports: () => void;
  onSelectOrganization: (organizationId: string) => void;
  onGenerate: (request: InstitutionReportCreateRequest) => void;
  onCreateIntegrationExport: (request: IntegrationExportCreateRequest) => void;
  onCreateIntegrationReminder: (request: IntegrationReminderCreateRequest) => void;
}) {
  const [formState, setFormState] = useState<InstitutionReportFormState>({
    ...DEFAULT_REPORT_FORM_STATE,
  });

  if (!auth.isConfigured) {
    return (
      <div className="view-grid">
        <ShellCard title="Institutional Reports" eyebrow="Authentication required">
          <EmptyState
            title="Reports are unavailable"
            body="Auth0 frontend configuration is required for organization-scoped reports."
          />
        </ShellCard>
      </div>
    );
  }

  if (!auth.isAuthenticated) {
    return (
      <div className="view-grid">
        <ShellCard
          title="Institutional Reports"
          eyebrow="Signed out"
          action={<button type="button" onClick={onLogin}>Sign in</button>}
        >
          <EmptyState
            title="Sign in required"
            body="Institutional reports are organization-scoped and require backend authorization."
          />
        </ShellCard>
      </div>
    );
  }

  const organizationRows = organizationsState.envelope?.data?.organizations ?? [];
  const selectedRow =
    organizationRows.find((row) => row.organization.organization_id === selectedOrganizationId)
    ?? organizationRows[0]
    ?? null;
  const report = reportState.envelope?.data?.report ?? null;
  const reportList = reportListState.envelope?.data?.reports ?? [];

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onGenerate(reportRequestFromForm(formState));
  }

  return (
    <div className="view-grid">
      <ShellCard
        title="Institutional Reports"
        eyebrow={selectedRow?.organization.name ?? "Organization context"}
        action={
          selectedRow ? (
            <div className="badge-stack">
              <button className="secondary-button compact-button" onClick={onOpenDashboard} type="button">
                Cohort dashboard
              </button>
              <button className="secondary-button compact-button" onClick={onOpenDataRequests} type="button">
                Data requests
              </button>
              <button className="secondary-button compact-button" onClick={onOpenImports} type="button">
                Imports
              </button>
              <span className="badge badge-success">{selectedRow.membership.role}</span>
            </div>
          ) : null
        }
      >
        {organizationsState.loading ? <LoadingBlock label="Loading organizations" /> : null}
        {organizationsState.error ? <ErrorState message={organizationsState.error} /> : null}
        {organizationRows.length > 1 ? (
          <div className="metadata-row">
            {organizationRows.map((row) => (
              <button
                className={
                  row.organization.organization_id === selectedOrganizationId
                    ? "primary-button compact-button"
                    : "secondary-button compact-button"
                }
                key={row.organization.organization_id}
                onClick={() => onSelectOrganization(row.organization.organization_id)}
                type="button"
              >
                {row.organization.name}
              </button>
            ))}
          </div>
        ) : null}
        <p className="meta-copy">
          Reports are aggregate-first and privacy-aware. PDF, CSV, PowerPoint,
          email delivery, and scheduled report exports are deferred.
        </p>
      </ShellCard>

      <div className="split-grid">
        <ShellCard title="Generate Report" eyebrow="Aggregate report">
          <form className="account-form-grid" onSubmit={handleSubmit}>
            <label>
              Report type
              <select
                aria-label="Report type"
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    reportType: event.target.value as InstitutionReportType,
                  }))
                }
                value={formState.reportType}
              >
                {INSTITUTION_REPORT_OPTIONS.map((option) => (
                  <option key={option.id} value={option.id}>{option.label}</option>
                ))}
              </select>
            </label>
            <label>
              Minimum group size
              <input
                min={5}
                max={50}
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    minimumGroupSize: Number(event.target.value),
                  }))
                }
                type="number"
                value={formState.minimumGroupSize}
              />
            </label>
            <div className="metadata-row">
              <button className="primary-button" disabled={reportState.loading || !selectedRow} type="submit">
                Generate report
              </button>
              {reportState.loading ? <span className="badge badge-partial">Generating</span> : null}
            </div>
          </form>
          {reportState.error ? <ErrorState message={reportState.error} /> : null}
        </ShellCard>

        <ShellCard title="Generated Reports" eyebrow="Persisted records">
          {reportListState.loading ? <LoadingBlock label="Loading reports" /> : null}
          {reportListState.error ? <ErrorState message={reportListState.error} /> : null}
          {reportList.length ? (
            <div className="stack-list">
              {reportList.map((summary) => (
                <InstitutionReportSummaryRow key={summary.report_id} summary={summary} />
              ))}
            </div>
          ) : (
            <EmptyState
              title="No reports yet"
              body="Generate an aggregate institutional report to create a record."
            />
          )}
        </ShellCard>
      </div>

      {report ? (
        <InstitutionReportResult
          canUseIntegrations={auth.isAuthenticated}
          onCreateIntegrationExport={onCreateIntegrationExport}
          onCreateIntegrationReminder={onCreateIntegrationReminder}
          report={report}
        />
      ) : null}
    </div>
  );
}

function InstitutionReportSummaryRow({ summary }: { summary: InstitutionReportSummary }) {
  return (
    <div className="stack-row">
      <div className="metadata-row">
        <strong>{summary.title}</strong>
        <span className="badge">{segmentLabel(summary.report_type)}</span>
      </div>
      <small>
        Generated {formatDateTime(summary.generated_at)} · cohort {summary.cohort_size} ·
        threshold {summary.minimum_group_size}
      </small>
      <div className="metadata-row">
        <span className="badge badge-success">{summary.status}</span>
        <span className="badge badge-unknown">
          Suppressions {formatValue(summary.privacy_summary.suppression_count)}
        </span>
        <span className="badge badge-partial">
          Coverage warnings {formatValue(summary.coverage_summary.coverage_warning_count)}
        </span>
      </div>
    </div>
  );
}

function InstitutionPartnerImportsView({
  auth,
  createState,
  listState,
  actionState,
  receiptState,
  organizationsState,
  selectedOrganizationId,
  onLogin,
  onOpenDashboard,
  onOpenReports,
  onOpenDataRequests,
  onSelectOrganization,
  onSubmit,
  onValidate,
  onAccept,
  onReject,
  onArchive,
  onViewReceipt,
}: {
  auth: FrontendAuthContextValue;
  createState: LoadState<PartnerImportCreatePayload>;
  listState: LoadState<PartnerImportListPayload>;
  actionState: LoadState<PartnerImportCreatePayload>;
  receiptState: LoadState<PartnerImportReceiptPayload>;
  organizationsState: LoadState<InstitutionCurrentOrganizationsPayload>;
  selectedOrganizationId: string;
  onLogin: () => void;
  onOpenDashboard: () => void;
  onOpenReports: () => void;
  onOpenDataRequests: () => void;
  onSelectOrganization: (organizationId: string) => void;
  onSubmit: (request: PartnerImportCreateRequest) => void;
  onValidate: (importBatchId: string) => void;
  onAccept: (importBatchId: string) => void;
  onReject: (importBatchId: string) => void;
  onArchive: (importBatchId: string) => void;
  onViewReceipt: (importBatchId: string) => void;
}) {
  const [formState, setFormState] = useState<PartnerImportFormState>({
    ...DEFAULT_PARTNER_IMPORT_FORM_STATE,
  });

  if (!auth.isConfigured) {
    return (
      <div className="view-grid">
        <ShellCard title="Partner Import Center" eyebrow="Authentication required">
          <EmptyState
            title="Partner imports are unavailable"
            body="Auth0 frontend configuration is required for organization-scoped imports."
          />
        </ShellCard>
      </div>
    );
  }

  if (!auth.isAuthenticated) {
    return (
      <div className="view-grid">
        <ShellCard
          title="Partner Import Center"
          eyebrow="Signed out"
          action={<button type="button" onClick={onLogin}>Sign in</button>}
        >
          <EmptyState
            title="Sign in required"
            body="Partner imports are institution-scoped and require backend authorization."
          />
        </ShellCard>
      </div>
    );
  }

  const organizationRows = organizationsState.envelope?.data?.organizations ?? [];
  const selectedRow =
    organizationRows.find((row) => row.organization.organization_id === selectedOrganizationId)
    ?? organizationRows[0]
    ?? null;
  const createdImport = createState.envelope?.data?.partner_import ?? null;
  const actionImport = actionState.envelope?.data?.partner_import ?? null;
  const imports = listState.envelope?.data?.imports ?? [];
  const activeImport = actionImport ?? createdImport ?? imports[0] ?? null;
  const receipt = receiptState.envelope?.data?.receipt ?? activeImport?.receipt ?? null;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedRow) return;
    onSubmit(partnerImportRequestFromForm(selectedRow.organization.organization_id, formState));
  }

  function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      setFormState((current) => ({
        ...current,
        content: typeof reader.result === "string" ? reader.result : current.content,
        originalFilename: file.name,
        importFormat: file.name.toLowerCase().endsWith(".json") ? "json" : "csv",
      }));
    };
    reader.readAsText(file);
  }

  return (
    <div className="view-grid">
      <ShellCard
        title="Partner Import Center"
        eyebrow={selectedRow?.organization.name ?? "Organization context"}
        action={
          selectedRow ? (
            <div className="badge-stack">
              <button className="secondary-button compact-button" onClick={onOpenDashboard} type="button">
                Cohort dashboard
              </button>
              <button className="secondary-button compact-button" onClick={onOpenReports} type="button">
                Reports
              </button>
              <button className="secondary-button compact-button" onClick={onOpenDataRequests} type="button">
                Data requests
              </button>
              <span className="badge badge-success">{selectedRow.membership.role}</span>
            </div>
          ) : null
        }
      >
        {organizationsState.loading ? <LoadingBlock label="Loading organizations" /> : null}
        {organizationsState.error ? <ErrorState message={organizationsState.error} /> : null}
        {organizationRows.length > 1 ? (
          <div className="metadata-row">
            {organizationRows.map((row) => (
              <button
                className={
                  row.organization.organization_id === selectedOrganizationId
                    ? "primary-button compact-button"
                    : "secondary-button compact-button"
                }
                key={row.organization.organization_id}
                onClick={() => onSelectOrganization(row.organization.organization_id)}
                type="button"
              >
                {row.organization.name}
              </button>
            ))}
          </div>
        ) : null}
        <p className="meta-copy">
          Partner data is partner-contributed evidence, not canonical truth.
          Accepted rows remain institution-scoped and cannot overwrite company
          identity, region intelligence, scoring, or governance warnings.
        </p>
      </ShellCard>

      <div className="split-grid">
        <ShellCard title="Upload CSV Or JSON" eyebrow="Validated evidence">
          <form className="account-form-grid" onSubmit={handleSubmit}>
            <label>
              Import type
              <select
                aria-label="Partner import type"
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    sourceType: event.target.value as PartnerImportSourceType,
                  }))
                }
                value={formState.sourceType}
              >
                {PARTNER_IMPORT_SOURCE_OPTIONS.map((option) => (
                  <option key={option.id} value={option.id}>{option.label}</option>
                ))}
              </select>
            </label>
            <label>
              Format
              <select
                aria-label="Partner import format"
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    importFormat: event.target.value as PartnerImportFormat,
                  }))
                }
                value={formState.importFormat}
              >
                {PARTNER_IMPORT_FORMAT_OPTIONS.map((option) => (
                  <option key={option.id} value={option.id}>{option.label}</option>
                ))}
              </select>
            </label>
            <label>
              Source attribution
              <input
                aria-label="Partner source attribution"
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    sourceAttribution: event.target.value,
                  }))
                }
                value={formState.sourceAttribution}
              />
            </label>
            <label>
              Upload file
              <input
                accept=".csv,.json,text/csv,application/json"
                aria-label="Partner import file"
                onChange={handleFile}
                type="file"
              />
            </label>
            <label>
              File name
              <input
                aria-label="Partner import filename"
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    originalFilename: event.target.value,
                  }))
                }
                value={formState.originalFilename}
              />
            </label>
            <label className="wide-field">
              Import content
              <textarea
                aria-label="Partner import content"
                onChange={(event) =>
                  setFormState((current) => ({ ...current, content: event.target.value }))
                }
                rows={8}
                value={formState.content}
              />
            </label>
            <div className="metadata-row">
              <button className="primary-button" disabled={createState.loading || !selectedRow} type="submit">
                Upload and validate
              </button>
              {createState.loading ? <span className="badge badge-partial">Validating</span> : null}
            </div>
          </form>
          {createState.error ? <ErrorState message={createState.error} /> : null}
        </ShellCard>

        <ShellCard title="Validation Preview" eyebrow="Warnings preserved">
          {activeImport ? (
            <PartnerImportSummaryCard
              partnerImport={activeImport}
              onAccept={onAccept}
              onArchive={onArchive}
              onReject={onReject}
              onValidate={onValidate}
              onViewReceipt={onViewReceipt}
            />
          ) : (
            <EmptyState
              title="No import selected"
              body="Upload a CSV or JSON partner import to preview validation results."
            />
          )}
          {actionState.loading ? <LoadingBlock label="Applying import action" /> : null}
          {actionState.error ? <ErrorState message={actionState.error} /> : null}
        </ShellCard>
      </div>

      <div className="split-grid">
        <ShellCard title="Import Batches" eyebrow="Institution scoped">
          {listState.loading ? <LoadingBlock label="Loading partner imports" /> : null}
          {listState.error ? <ErrorState message={listState.error} /> : null}
          {imports.length ? (
            <div className="stack-list">
              {imports.map((partnerImport) => (
                <PartnerImportBatchRow
                  key={partnerImport.import_batch_id}
                  partnerImport={partnerImport}
                  onAccept={onAccept}
                  onArchive={onArchive}
                  onReject={onReject}
                  onValidate={onValidate}
                  onViewReceipt={onViewReceipt}
                />
              ))}
            </div>
          ) : (
            <EmptyState
              title="No partner imports"
              body="Validated partner evidence batches will appear here for this institution only."
            />
          )}
        </ShellCard>

        <ShellCard title="Import Receipt" eyebrow="Governance record">
          {receiptState.loading ? <LoadingBlock label="Loading import receipt" /> : null}
          {receiptState.error ? <ErrorState message={receiptState.error} /> : null}
          {receipt ? (
            <div className="stack-row">
              <div className="metadata-row">
                <strong>{segmentLabel(receipt.source_type)}</strong>
                <span className="badge badge-success">
                  Partner-contributed evidence
                </span>
                <span className="badge badge-unknown">Canonical truth false</span>
              </div>
              <small>
                Source {receipt.source_attribution} · status {segmentLabel(receipt.status)}
              </small>
              <ul className="notes-list">
                {receipt.limitations.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              <div className="metadata-row">
                <span className="badge badge-success">
                  Identity overwrite {String(receipt.canonical_identity_overwrite_performed)}
                </span>
                <span className="badge badge-success">
                  Region overwrite {String(receipt.canonical_region_overwrite_performed)}
                </span>
                <span className="badge badge-success">
                  Scoring override {String(receipt.product_scoring_override_performed)}
                </span>
                <span className="badge badge-success">
                  Internal fields exposed {String(receipt.internal_only_fields_exposed)}
                </span>
              </div>
            </div>
          ) : (
            <EmptyState
              title="No receipt loaded"
              body="Open a receipt to inspect source attribution, warnings, and boundary decisions."
            />
          )}
        </ShellCard>
      </div>
    </div>
  );
}

function PartnerImportSummaryCard({
  partnerImport,
  onAccept,
  onArchive,
  onReject,
  onValidate,
  onViewReceipt,
}: {
  partnerImport: PartnerImportBatchPayload;
  onAccept: (importBatchId: string) => void;
  onArchive: (importBatchId: string) => void;
  onReject: (importBatchId: string) => void;
  onValidate: (importBatchId: string) => void;
  onViewReceipt: (importBatchId: string) => void;
}) {
  const result = partnerImport.validation_result;
  return (
    <div className="stack-row">
      <div className="metadata-row">
        <strong>{segmentLabel(partnerImport.source_type)}</strong>
        <span className="badge">{segmentLabel(partnerImport.status)}</span>
        <span className="badge badge-success">Partner-contributed</span>
      </div>
      <small>
        Records {result.record_count} · accepted {result.accepted_record_count} ·
        quarantined {result.quarantined_record_count} · rejected {result.rejected_record_count}
      </small>
      <p className="meta-copy">
        Source: {partnerImport.source_attribution || "Missing source attribution"}
      </p>
      <div className="metadata-row">
        <button
          className="secondary-button compact-button"
          onClick={() => onValidate(partnerImport.import_batch_id)}
          type="button"
        >
          Revalidate
        </button>
        <button
          className="primary-button compact-button"
          disabled={!result.can_accept}
          onClick={() => onAccept(partnerImport.import_batch_id)}
          type="button"
        >
          Accept evidence
        </button>
        <button
          className="secondary-button compact-button"
          onClick={() => onReject(partnerImport.import_batch_id)}
          type="button"
        >
          Reject
        </button>
        <button
          className="secondary-button compact-button"
          onClick={() => onArchive(partnerImport.import_batch_id)}
          type="button"
        >
          Archive
        </button>
        <button
          className="secondary-button compact-button"
          onClick={() => onViewReceipt(partnerImport.import_batch_id)}
          type="button"
        >
          Receipt
        </button>
      </div>
      <PartnerImportWarnings warnings={result.warnings} />
      {partnerImport.preview_records.length ? (
        <div className="stack-list">
          {partnerImport.preview_records.slice(0, 3).map((record, index) => (
            <div className="stack-row compact-row" key={`${partnerImport.import_batch_id}-${index}`}>
              <div className="metadata-row">
                <span className="badge">{formatValue(record.decision)}</span>
                <span className="badge badge-unknown">Canonical truth false</span>
              </div>
              <small>{JSON.stringify(record.partner_payload ?? record).slice(0, 220)}</small>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function PartnerImportBatchRow({
  partnerImport,
  onAccept,
  onArchive,
  onReject,
  onValidate,
  onViewReceipt,
}: {
  partnerImport: PartnerImportBatchPayload;
  onAccept: (importBatchId: string) => void;
  onArchive: (importBatchId: string) => void;
  onReject: (importBatchId: string) => void;
  onValidate: (importBatchId: string) => void;
  onViewReceipt: (importBatchId: string) => void;
}) {
  return (
    <div className="stack-row">
      <div className="metadata-row">
        <strong>{segmentLabel(partnerImport.source_type)}</strong>
        <span className="badge">{segmentLabel(partnerImport.status)}</span>
        <span className="badge badge-success">Institution scoped</span>
      </div>
      <small>
        Uploaded {formatDateTime(partnerImport.created_at)} ·
        records {partnerImport.record_count} · warnings {partnerImport.validation_result.warning_count}
      </small>
      <div className="metadata-row">
        <button className="secondary-button compact-button" onClick={() => onValidate(partnerImport.import_batch_id)} type="button">
          Validate
        </button>
        <button
          className="primary-button compact-button"
          disabled={!partnerImport.validation_result.can_accept}
          onClick={() => onAccept(partnerImport.import_batch_id)}
          type="button"
        >
          Accept
        </button>
        <button className="secondary-button compact-button" onClick={() => onReject(partnerImport.import_batch_id)} type="button">
          Reject
        </button>
        <button className="secondary-button compact-button" onClick={() => onArchive(partnerImport.import_batch_id)} type="button">
          Archive
        </button>
        <button className="secondary-button compact-button" onClick={() => onViewReceipt(partnerImport.import_batch_id)} type="button">
          Receipt
        </button>
      </div>
    </div>
  );
}

function PartnerImportWarnings({
  warnings,
}: {
  warnings: PartnerImportBatchPayload["validation_result"]["warnings"];
}) {
  if (!warnings.length) {
    return <p className="meta-copy">No validation warnings were returned.</p>;
  }
  return (
    <div className="warning-list" aria-label="Partner import validation warnings">
      {warnings.slice(0, 8).map((warning, index) => (
        <div className="warning-item" key={`${warning.code}-${warning.field}-${index}`}>
          <div className="warning-header">
            <span className="warning-code">{prettyKey(warning.code)}</span>
            <span className="badge badge-warning">{warning.severity}</span>
          </div>
          <p>{warning.message}</p>
          <small>
            Record {warning.record_index ?? "batch"} · action {segmentLabel(warning.action)}
          </small>
        </div>
      ))}
    </div>
  );
}

function InstitutionReportResult({
  report,
  canUseIntegrations,
  onCreateIntegrationExport,
  onCreateIntegrationReminder,
}: {
  report: InstitutionReportPayload;
  canUseIntegrations: boolean;
  onCreateIntegrationExport: (request: IntegrationExportCreateRequest) => void;
  onCreateIntegrationReminder: (request: IntegrationReminderCreateRequest) => void;
}) {
  return (
    <>
      <ShellCard title={report.title} eyebrow={segmentLabel(report.report_type)}>
        <div className="stat-grid">
          <div className="stat-card">
            <span>Cohort size</span>
            <strong>{report.cohort_size}</strong>
          </div>
          <div className="stat-card">
            <span>Suppression threshold</span>
            <strong>{report.minimum_group_size}</strong>
          </div>
          <div className="stat-card">
            <span>Sections</span>
            <strong>{report.sections.length}</strong>
          </div>
          <div className="stat-card">
            <span>Export status</span>
            <strong>{segmentLabel(report.export_status)}</strong>
          </div>
        </div>
        <ul className="notes-list">
          {report.recommended_actions.map((action) => (
            <li key={action}>{action}</li>
          ))}
        </ul>
      </ShellCard>

      <IntegrationActionPanel
        canUseIntegrations={canUseIntegrations}
        label={report.title}
        objectId={report.report_id}
        objectType="institutional_report"
        onCreateExport={onCreateIntegrationExport}
        onCreateReminder={onCreateIntegrationReminder}
        organizationId={report.organization_id}
        reminderType="institutional_report_review"
      />

      <div className="split-grid">
        {report.sections.map((section) => (
          <InstitutionReportSectionCard key={section.section_id} section={section} />
        ))}
      </div>

      <ShellCard title="Report Privacy And Limitations" eyebrow="Aggregate-first">
        <div className="split-grid">
          <div>
            <h3>Privacy notes</h3>
            <ul className="notes-list">
              {report.privacy_notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
            {report.privacy_suppressions.length ? (
              <div className="warning-list">
                {report.privacy_suppressions.map((suppression) => (
                  <div className="warning-item" key={suppression.section}>
                    <div className="warning-header">
                      <span className="warning-code">{prettyKey(suppression.section)}</span>
                      <span className="badge badge-warning">Suppressed</span>
                    </div>
                    <p>
                      {suppression.suppressed_count} bucket(s) withheld at minimum group
                      size {suppression.minimum_group_size}.
                    </p>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
          <div>
            <h3>Warnings and limitations</h3>
            <ul className="notes-list">
              {[...report.coverage_warnings, ...report.limitations].map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            <p className="meta-copy">
              Data freshness: {formatValue(report.data_freshness.freshness_status)}
            </p>
            <p className="meta-copy">
              Export options: {Object.entries(report.export_options)
                .map(([key, value]) => `${key} ${value}`)
                .join(", ")}
            </p>
          </div>
        </div>
      </ShellCard>
    </>
  );
}

function InstitutionReportSectionCard({ section }: { section: InstitutionReportSection }) {
  return (
    <ShellCard title={section.title} eyebrow={prettyKey(section.section_id)}>
      <p className="meta-copy">{section.summary}</p>
      <ul className="notes-list">
        {section.findings.map((finding) => (
          <li key={finding}>{finding}</li>
        ))}
      </ul>
      {section.warnings.length ? (
        <div className="warning-list">
          {section.warnings.map((warning) => (
            <div className="warning-item" key={warning}>
              <div className="warning-header">
                <span className="warning-code">Report warning</span>
              </div>
              <p>{warning}</p>
            </div>
          ))}
        </div>
      ) : null}
      {section.recommended_actions.length ? (
        <div className="metadata-row">
          {section.recommended_actions.map((action) => (
            <span className="badge badge-unknown" key={action}>{action}</span>
          ))}
        </div>
      ) : null}
    </ShellCard>
  );
}

function InstitutionDataRequestsView({
  auth,
  createState,
  listState,
  organizationsState,
  selectedOrganizationId,
  onLogin,
  onOpenDashboard,
  onOpenImports,
  onOpenReports,
  onSelectOrganization,
  onSubmit,
  onCreateIntegrationReminder,
}: {
  auth: FrontendAuthContextValue;
  createState: LoadState<InstitutionDataRequestCreatePayload>;
  listState: LoadState<InstitutionDataRequestListPayload>;
  organizationsState: LoadState<InstitutionCurrentOrganizationsPayload>;
  selectedOrganizationId: string;
  onLogin: () => void;
  onOpenDashboard: () => void;
  onOpenImports: () => void;
  onOpenReports: () => void;
  onSelectOrganization: (organizationId: string) => void;
  onSubmit: (request: InstitutionDataRequestCreateRequest) => void;
  onCreateIntegrationReminder: (request: IntegrationReminderCreateRequest) => void;
}) {
  const [formState, setFormState] = useState<InstitutionDataRequestFormState>({
    ...DEFAULT_DATA_REQUEST_FORM_STATE,
  });

  if (!auth.isConfigured) {
    return (
      <div className="view-grid">
        <ShellCard title="Institutional Data Requests" eyebrow="Authentication required">
          <EmptyState
            title="Data requests are unavailable"
            body="Auth0 frontend configuration is required for organization-scoped requests."
          />
        </ShellCard>
      </div>
    );
  }

  if (!auth.isAuthenticated) {
    return (
      <div className="view-grid">
        <ShellCard
          title="Institutional Data Requests"
          eyebrow="Signed out"
          action={<button type="button" onClick={onLogin}>Sign in</button>}
        >
          <EmptyState
            title="Sign in required"
            body="Data request records are organization-scoped and require backend authorization."
          />
        </ShellCard>
      </div>
    );
  }

  const organizationRows = organizationsState.envelope?.data?.organizations ?? [];
  const selectedRow =
    organizationRows.find((row) => row.organization.organization_id === selectedOrganizationId)
    ?? organizationRows[0]
    ?? null;
  const createdRequest = createState.envelope?.data?.data_request ?? null;
  const dataRequests = listState.envelope?.data?.data_requests ?? [];

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit(dataRequestFromForm(formState));
  }

  return (
    <div className="view-grid">
      <ShellCard
        title="Institutional Data Requests"
        eyebrow={selectedRow?.organization.name ?? "Organization context"}
        action={
          selectedRow ? (
            <div className="badge-stack">
              <button className="secondary-button compact-button" onClick={onOpenDashboard} type="button">
                Cohort dashboard
              </button>
              <button className="secondary-button compact-button" onClick={onOpenReports} type="button">
                Reports
              </button>
              <button className="secondary-button compact-button" onClick={onOpenImports} type="button">
                Imports
              </button>
              <span className="badge badge-success">{selectedRow.membership.role}</span>
            </div>
          ) : null
        }
      >
        {organizationsState.loading ? <LoadingBlock label="Loading organizations" /> : null}
        {organizationsState.error ? <ErrorState message={organizationsState.error} /> : null}
        {organizationRows.length > 1 ? (
          <div className="metadata-row">
            {organizationRows.map((row) => (
              <button
                className={
                  row.organization.organization_id === selectedOrganizationId
                    ? "primary-button compact-button"
                    : "secondary-button compact-button"
                }
                key={row.organization.organization_id}
                onClick={() => onSelectOrganization(row.organization.organization_id)}
                type="button"
              >
                {row.organization.name}
              </button>
            ))}
          </div>
        ) : null}
        <p className="meta-copy">
          Data export/deletion workflows create auditable request records only.
          They do not automatically execute destructive deletion or generate full
          export packages in this batch.
        </p>
      </ShellCard>

      {selectedRow ? (
        <IntegrationActionPanel
          canUseIntegrations={auth.isAuthenticated}
          label={`${selectedRow.organization.name} data request follow-up`}
          objectId={selectedRow.organization.organization_id}
          objectType="institutional_dashboard"
          onCreateExport={() => undefined}
          onCreateReminder={onCreateIntegrationReminder}
          organizationId={selectedRow.organization.organization_id}
          reminderType="data_request_due"
          showExports={false}
        />
      ) : null}

      <div className="split-grid">
        <ShellCard title="Create Request Record" eyebrow="Auditable request">
          <form className="account-form-grid" onSubmit={handleSubmit}>
            <label>
              Request type
              <select
                aria-label="Data request type"
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    requestType: event.target.value as InstitutionDataRequestType,
                  }))
                }
                value={formState.requestType}
              >
                {INSTITUTION_DATA_REQUEST_OPTIONS.map((option) => (
                  <option key={option.id} value={option.id}>{option.label}</option>
                ))}
              </select>
            </label>
            <label>
              Subject user id
              <input
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    subjectUserId: event.target.value,
                  }))
                }
                value={formState.subjectUserId}
              />
            </label>
            <label>
              Reason
              <input
                onChange={(event) =>
                  setFormState((current) => ({ ...current, reason: event.target.value }))
                }
                value={formState.reason}
              />
            </label>
            <div className="metadata-row">
              <button className="primary-button" disabled={createState.loading || !selectedRow} type="submit">
                Submit request record
              </button>
              {createState.loading ? <span className="badge badge-partial">Submitting</span> : null}
            </div>
          </form>
          {createState.error ? <ErrorState message={createState.error} /> : null}
          {createdRequest ? (
            <p className="meta-copy">
              Created {segmentLabel(createdRequest.request_type)} request:
              {" "}{createdRequest.execution_note}
            </p>
          ) : null}
        </ShellCard>

        <ShellCard title="Current Request Records" eyebrow="No execution">
          {listState.loading ? <LoadingBlock label="Loading data requests" /> : null}
          {listState.error ? <ErrorState message={listState.error} /> : null}
          {dataRequests.length ? (
            <div className="stack-list">
              {dataRequests.map((request) => (
                <InstitutionDataRequestRow key={request.data_request_id} request={request} />
              ))}
            </div>
          ) : (
            <EmptyState
              title="No request records"
              body="Create a data export or deletion request record to track it here."
            />
          )}
        </ShellCard>
      </div>
    </div>
  );
}

function InstitutionDataRequestRow({ request }: { request: InstitutionDataRequestPayload }) {
  return (
    <div className="stack-row">
      <div className="metadata-row">
        <strong>{segmentLabel(request.request_type)}</strong>
        <span className="badge badge-warning">{request.status}</span>
      </div>
      <small>
        Subject {request.subject_type}
        {request.subject_user_id ? ` · ${request.subject_user_id}` : ""} · created{" "}
        {formatDateTime(request.created_at)}
      </small>
      {request.reason ? <span>{request.reason}</span> : null}
      <p className="meta-copy">{request.execution_note}</p>
    </div>
  );
}

function InstitutionAggregateSection({
  title,
  items,
  emptyBody,
}: {
  title: string;
  items: InstitutionAggregateItem[];
  emptyBody: string;
}) {
  return (
    <ShellCard title={title} eyebrow="Cohort aggregate">
      {items.length ? (
        <div className="stack-list">
          {items.map((item, index) => (
            <div className="stack-row" key={`${title}-${item.label}-${index}`}>
              <div className="metadata-row">
                <strong>{item.label}</strong>
                {item.suppressed ? (
                  <span className="badge badge-warning">Suppressed</span>
                ) : (
                  <span className="badge badge-success">Visible aggregate</span>
                )}
              </div>
              <span>
                {institutionAggregateCountLabel(item)}
                {typeof item.percentage === "number" ? ` · ${formatValue(item.percentage)}%` : ""}
              </span>
              <div className="metadata-row">
                {item.confidence ? <span className="badge">{item.confidence}</span> : null}
                {item.source_count !== null ? (
                  <span className="badge badge-unknown">
                    Source count {formatValue(item.source_count)}
                  </span>
                ) : null}
                {institutionAggregateTrendLabel(item) ? (
                  <span className="badge badge-partial">{institutionAggregateTrendLabel(item)}</span>
                ) : null}
              </div>
              {item.coverage ? (
                <small>
                  Coverage: {formatValue(item.coverage.label)} · tier{" "}
                  {formatValue(item.coverage.tier)} · quality{" "}
                  {formatValue(item.coverage.quality_score)}
                </small>
              ) : null}
            </div>
          ))}
        </div>
      ) : (
        <EmptyState title="No visible aggregate" body={emptyBody} />
      )}
    </ShellCard>
  );
}

function institutionAggregateCountLabel(item: InstitutionAggregateItem): string {
  if (item.suppressed) return "Count withheld";
  if (item.count === null) return "Count unavailable";
  if (item.category === "market_demand") {
    return `${item.count} active posting(s)`;
  }
  if (item.category === "coverage_gap") {
    return `${item.count} student(s) in visible target market`;
  }
  return `${item.count} student(s)`;
}

function institutionAggregateTrendLabel(item: InstitutionAggregateItem): string | null {
  const trendSignal = item.metadata.trend_signal;
  if (typeof trendSignal === "string" && trendSignal) {
    return `Trend ${trendSignal}`;
  }
  const hiringCount = item.metadata.currently_hiring_company_count;
  if (typeof hiringCount === "number") {
    return `${hiringCount} hiring company(s)`;
  }
  return null;
}

function MonetizationView({
  plansState,
  featuresState,
  reportsState,
  accessPreviewStates,
  monetizationMeState,
  monetizationEntitlementsState,
  monetizationUsageState,
  billingStatusState,
  billingAction,
  authenticated,
  onStartCheckout,
  onManageBilling,
}: {
  plansState: LoadState<MonetizationPlansPayload>;
  featuresState: LoadState<MonetizationFeaturesPayload>;
  reportsState: LoadState<MonetizationReportsPayload>;
  accessPreviewStates: Record<string, LoadState<MonetizationAccessPreviewPayload>>;
  monetizationMeState: LoadState<MonetizationMePayload>;
  monetizationEntitlementsState: LoadState<MonetizationEntitlementsPayload>;
  monetizationUsageState: LoadState<MonetizationUsagePayload>;
  billingStatusState: LoadState<BillingStatusPayload>;
  billingAction: BillingActionState;
  authenticated: boolean;
  onStartCheckout: (planKey: MonetizationPlanKey) => void;
  onManageBilling: () => void;
}) {
  const plans = orderedPlans(plansState.envelope?.data?.plans ?? []);
  const features = orderedFeatures(featuresState.envelope?.data?.features ?? []);
  const reports = reportsState.envelope?.data?.reports ?? [];
  const featuresByKey = featureByKey(features);
  const plansByKey = new Map(plans.map((plan) => [plan.plan_key, plan]));
  const billingStatus = billingStatusState.envelope?.data ?? null;
  const currentPlanKey =
    monetizationEntitlementsState.envelope?.data?.entitlements.plan_key
    ?? monetizationMeState.envelope?.data?.entitlements.plan_key
    ?? null;

  return (
    <div className="view-grid">
      <ShellCard
        title="Plans and access model"
        eyebrow="Layer 15 monetization surface"
        action={<StateBadge envelope={plansState.envelope} loading={plansState.loading} error={plansState.error} />}
      >
        <p className="lead-copy">
          Plans describe workflow access around the same recommendation engine. Free users
          still receive useful market exploration and the basic recommendation preview;
          paid plans add saving, alerts, reports, exports, broader coverage, and
          institutional workflows.
        </p>
        <div className="metadata-row">
          <span className="badge badge-success">Checkout requires backend configuration</span>
          <span className="badge badge-real">Stripe adapter only</span>
          <span className="badge badge-unknown">Recommendations unchanged</span>
        </div>
        {plansState.error ? <ErrorState message={plansState.error} /> : null}
        {featuresState.error ? <ErrorState message={featuresState.error} /> : null}
        {reportsState.error ? <ErrorState message={reportsState.error} /> : null}
        {billingStatusState.error ? <ErrorState message={billingStatusState.error} /> : null}
        {billingAction.error ? <ErrorState message={billingAction.error} /> : null}
        {billingAction.message ? <p className="meta-copy">{billingAction.message}</p> : null}
        {billingStatus ? (
          <p className="meta-copy">
            {billingStatus.checkout_available
              ? "Self-serve checkout is available for mapped individual plans. Access changes only after verified billing events update the internal plan assignment."
              : billingStatus.disabled_reason ?? "Self-serve checkout is currently unavailable."}
          </p>
        ) : null}
      </ShellCard>

      <ShellCard title="Current account access" eyebrow="Account-aware entitlement state">
        <MonetizationAccountPanel
          authenticated={authenticated}
          billingAction={billingAction}
          billingStatus={billingStatus}
          entitlementsState={monetizationEntitlementsState}
          features={featuresByKey}
          meState={monetizationMeState}
          onManageBilling={onManageBilling}
          plans={plansByKey}
          usageState={monetizationUsageState}
        />
      </ShellCard>

      <ShellCard title="Plan catalog" eyebrow="Backend-owned metadata">
        {plansState.loading ? <LoadingBlock label="Loading plans" /> : null}
        {plans.length ? (
          <div className="plan-grid">
            {plans.map((plan) => (
              <PlanCard
                authenticated={authenticated}
                billingAction={billingAction}
                billingStatus={billingStatus}
                currentPlanKey={currentPlanKey}
                features={featuresByKey}
                key={plan.plan_key}
                onStartCheckout={onStartCheckout}
                plan={plan}
                plansByKey={plansByKey}
              />
            ))}
          </div>
        ) : !plansState.loading ? (
          <EmptyState title="No plans returned" body="The monetization plan endpoint returned no plan metadata." />
        ) : null}
      </ShellCard>

      <ShellCard title="Free and paid feature boundary" eyebrow="Trust-safe monetization">
        {featuresState.loading ? <LoadingBlock label="Loading feature boundary" /> : null}
        {features.length ? (
          <FeatureBoundaryPanel features={features} />
        ) : !featuresState.loading ? (
          <EmptyState title="No features returned" body="The monetization feature endpoint returned no metadata." />
        ) : null}
      </ShellCard>

      <ShellCard title="Report product catalog" eyebrow="Preview now, full report later">
        {reportsState.loading ? <LoadingBlock label="Loading report catalog" /> : null}
        {reports.length ? (
          <div className="report-product-grid">
            {reports.map((report) => (
              <ReportProductCard features={featuresByKey} key={report.report_key} report={report} />
            ))}
          </div>
        ) : !reportsState.loading ? (
          <EmptyState title="No reports returned" body="The report product endpoint returned no catalog entries." />
        ) : null}
      </ShellCard>

      <ShellCard title="Access preview" eyebrow="Central entitlement decision">
        <p className="meta-copy">
          These previews call the backend entitlement endpoint with the current account when available. The copy is
          explanatory: paid features add durable workflow and report value; they do not hide
          the basic recommendation result.
        </p>
        <AccessPreviewPanel features={featuresByKey} plans={plansByKey} previews={accessPreviewStates} />
      </ShellCard>
    </div>
  );
}

function RecommendationsView({
  goalModesState,
  strategyState,
  selectedGoalMode,
  onSelectGoalMode,
  accessPreviewStates,
  monetizationPlansState,
  canUseIntegrations,
  onCreateIntegrationExport,
  onCreateIntegrationReminder,
}: {
  goalModesState: LoadState<RecommendationGoalModesPayload>;
  strategyState: LoadState<RecommendationStrategyPayload>;
  selectedGoalMode: RecommendationGoalMode;
  onSelectGoalMode: (goalMode: RecommendationGoalMode) => void;
  accessPreviewStates: Record<string, LoadState<MonetizationAccessPreviewPayload>>;
  monetizationPlansState: LoadState<MonetizationPlansPayload>;
  canUseIntegrations: boolean;
  onCreateIntegrationExport: (request: IntegrationExportCreateRequest) => void;
  onCreateIntegrationReminder: (request: IntegrationReminderCreateRequest) => void;
}) {
  const strategy = strategyState.envelope?.data;
  const goalModes = goalModesState.envelope?.data?.goal_modes ?? strategy?.available_goal_modes ?? [];
  const companyWarnings = strategy?.warnings.filter((warning) => warning.toLocaleLowerCase().includes("company")) ?? [];
  const plansByKey = new Map((monetizationPlansState.envelope?.data?.plans ?? []).map((plan) => [plan.plan_key, plan]));
  const reportDecision = accessPreviewStates[accessPreviewKey({ feature_key: "full_report_generation" })]?.envelope?.data?.decision;

  return (
    <div className="view-grid">
      <ShellCard
        title="Recommendation decision support"
        eyebrow="Layer 14 structured recommendations"
        action={<StateBadge envelope={strategyState.envelope} loading={strategyState.loading} error={strategyState.error} />}
      >
        <p className="lead-copy">
          Select a goal mode to load ranked recommendations and a structured market strategy
          from backend-owned evidence, confidence, freshness, provenance, coverage, and
          explicitly labeled heuristic inference.
        </p>
        {goalModesState.loading ? <LoadingBlock label="Loading goal modes" /> : null}
        {goalModesState.error ? <ErrorState message={goalModesState.error} /> : null}
        <RecommendationGoalModeSelector
          goalModes={goalModes}
          loading={goalModesState.loading}
          selectedGoalMode={selectedGoalMode}
          onSelectGoalMode={onSelectGoalMode}
        />
        {strategyState.loading ? <LoadingBlock label="Loading recommendation strategy" /> : null}
        {strategyState.error ? <ErrorState message={strategyState.error} /> : null}
        {strategy?.warnings.length ? (
          <div className="warning-list">
            {strategy.warnings.map((warning) => (
              <div className="warning-item" key={warning}>
                <div className="warning-header">
                  <span className="warning-code">API warning</span>
                </div>
                <p>{warning}</p>
              </div>
            ))}
          </div>
        ) : null}
        <MetadataPanel envelope={strategyState.envelope} />
        <UpgradePrompt
          decision={reportDecision}
          feature="full_report_generation"
          plans={plansByKey}
          title="Generate a full strategy report with Individual."
          body="The ranked recommendation stays visible here. Paid reports package sections, exports, and verification steps for sharing or advising."
        />
      </ShellCard>

      {strategy ? (
        <IntegrationActionPanel
          canUseIntegrations={canUseIntegrations}
          label={`${segmentLabel(selectedGoalMode)} strategy`}
          objectId={selectedGoalMode}
          objectType="recommendation_strategy"
          onCreateExport={onCreateIntegrationExport}
          onCreateReminder={onCreateIntegrationReminder}
          reminderType="follow_up"
          sourceContext={{ goal_mode: selectedGoalMode }}
        />
      ) : null}

      {strategy ? (
        <>
          <RecommendationRankingSection
            title="Ranked region recommendations"
            items={strategy.ranked_region_recommendations}
            emptyTitle="No region recommendations"
            emptyBody="The backend returned no ranked region recommendations."
          />
          <RecommendationRankingSection
            title="Ranked company recommendations"
            items={strategy.ranked_company_recommendations}
            emptyTitle="No company recommendations"
            emptyBody={companyWarnings[0] ?? "The backend returned no company recommendations and did not invent company targets."}
          />
          <MarketStrategyView strategy={strategy.market_strategy_plan} />
        </>
      ) : !strategyState.loading ? (
        <EmptyState
          title="No recommendation strategy loaded"
          body="Goal modes may still be loading or the backend recommendation endpoint returned an error."
        />
      ) : null}
    </div>
  );
}

function App() {
  const auth = useFrontendAuth();
  const [route, setRoute] = useState<RouteState>(() => readCurrentRoute());
  const isProductRoute = isProductPage(route.page);
  const visibleNavItems = NAV_ITEMS.filter(
    (item) => !isPublicDemoBlockedProduct(item.id),
  );
  const [health, setHealth] = useState<LoadState<{ service: string }>>(emptyLoadState);
  const [regions, setRegions] = useState<LoadState<{ regions: RegionListItem[] }>>(emptyLoadState);
  const [marketCoverageState, setMarketCoverageState] =
    useState<LoadState<MarketCoverageListPayload>>(emptyLoadState);
  const [marketOperationsState, setMarketOperationsState] =
    useState<LoadState<ImportedMarketOperationsViewPayload>>(emptyLoadState);
  const [regionDetails, setRegionDetails] = useState<Record<string, ApiEnvelope<RegionDetail>>>({});
  const [regionErrors, setRegionErrors] = useState<Record<string, string>>({});
  const [regionLoading, setRegionLoading] = useState<Record<string, boolean>>({});
  const [regionSearchState, setRegionSearchState] = useState<LoadState<RegionSearchResponse>>(emptyLoadState);
  const [regionSourceStates, setRegionSourceStates] = useState<Record<string, LoadState<SourceExplanation>>>({});
  const [regionCompanySearchStates, setRegionCompanySearchStates] = useState<Record<string, LoadState<CompanySearchResponse>>>({});
  const [companyState, setCompanyState] = useState<LoadState<CompanyDetail>>(emptyLoadState);
  const [companySourceStates, setCompanySourceStates] = useState<Record<string, LoadState<SourceExplanation>>>({});
  const [companyGeographyStates, setCompanyGeographyStates] = useState<Record<string, LoadState<CompanyGeographyResponse>>>({});
  const [comparisonState, setComparisonState] = useState<LoadState<ComparisonDetail>>(emptyLoadState);
  const [discoveryState, setDiscoveryState] = useState<LoadState<PersonalizedResult>>(emptyLoadState);
  const [recommendationGoalModesState, setRecommendationGoalModesState] =
    useState<LoadState<RecommendationGoalModesPayload>>(emptyLoadState);
  const [recommendationStrategyState, setRecommendationStrategyState] =
    useState<LoadState<RecommendationStrategyPayload>>(emptyLoadState);
  const [publicBenchmarkListState, setPublicBenchmarkListState] =
    useState<LoadState<PublicBenchmarkListPayload>>(emptyLoadState);
  const [publicBenchmarkDetailStates, setPublicBenchmarkDetailStates] =
    useState<Record<string, LoadState<PublicBenchmark>>>({});
  const [publicReportListState, setPublicReportListState] =
    useState<LoadState<PublicReportListPayload>>(emptyLoadState);
  const [publicReportDetailStates, setPublicReportDetailStates] =
    useState<Record<string, LoadState<PublicReport>>>({});
  const [predictiveReportState, setPredictiveReportState] =
    useState<LoadState<PredictiveReportPayload>>(emptyLoadState);
  const [monetizationPlansState, setMonetizationPlansState] =
    useState<LoadState<MonetizationPlansPayload>>(emptyLoadState);
  const [monetizationFeaturesState, setMonetizationFeaturesState] =
    useState<LoadState<MonetizationFeaturesPayload>>(emptyLoadState);
  const [monetizationReportsState, setMonetizationReportsState] =
    useState<LoadState<MonetizationReportsPayload>>(emptyLoadState);
  const [monetizationAccessPreviewStates, setMonetizationAccessPreviewStates] =
    useState<Record<string, LoadState<MonetizationAccessPreviewPayload>>>({});
  const [monetizationMeState, setMonetizationMeState] =
    useState<LoadState<MonetizationMePayload>>(emptyLoadState);
  const [monetizationEntitlementsState, setMonetizationEntitlementsState] =
    useState<LoadState<MonetizationEntitlementsPayload>>(emptyLoadState);
  const [monetizationUsageState, setMonetizationUsageState] =
    useState<LoadState<MonetizationUsagePayload>>(emptyLoadState);
  const [billingStatusState, setBillingStatusState] =
    useState<LoadState<BillingStatusPayload>>(emptyLoadState);
  const [institutionOrganizationsState, setInstitutionOrganizationsState] =
    useState<LoadState<InstitutionCurrentOrganizationsPayload>>(emptyLoadState);
  const [institutionDashboardState, setInstitutionDashboardState] =
    useState<LoadState<InstitutionDashboardPayload>>(emptyLoadState);
  const [institutionDecisionDashboardState, setInstitutionDecisionDashboardState] =
    useState<LoadState<InstitutionDecisionDashboardPayload>>(emptyLoadState);
  const [institutionCurriculumState, setInstitutionCurriculumState] =
    useState<LoadState<CurriculumMarketMappingPayload>>(emptyLoadState);
  const [institutionWorkforceReportState, setInstitutionWorkforceReportState] =
    useState<LoadState<InstitutionWorkforceReportPayload>>(emptyLoadState);
  const [institutionBenchmarkState, setInstitutionBenchmarkState] =
    useState<LoadState<InstitutionBenchmarkPayload>>(emptyLoadState);
  const [institutionAdvisorState, setInstitutionAdvisorState] =
    useState<LoadState<InstitutionAdvisorToolResponse>>(emptyLoadState);
  const [institutionReportState, setInstitutionReportState] =
    useState<LoadState<InstitutionReportGeneratePayload>>(emptyLoadState);
  const [institutionReportsListState, setInstitutionReportsListState] =
    useState<LoadState<InstitutionReportListPayload>>(emptyLoadState);
  const [institutionDataRequestState, setInstitutionDataRequestState] =
    useState<LoadState<InstitutionDataRequestCreatePayload>>(emptyLoadState);
  const [institutionDataRequestsListState, setInstitutionDataRequestsListState] =
    useState<LoadState<InstitutionDataRequestListPayload>>(emptyLoadState);
  const [partnerImportCreateState, setPartnerImportCreateState] =
    useState<LoadState<PartnerImportCreatePayload>>(emptyLoadState);
  const [partnerImportListState, setPartnerImportListState] =
    useState<LoadState<PartnerImportListPayload>>(emptyLoadState);
  const [partnerImportActionState, setPartnerImportActionState] =
    useState<LoadState<PartnerImportCreatePayload>>(emptyLoadState);
  const [partnerImportReceiptState, setPartnerImportReceiptState] =
    useState<LoadState<PartnerImportReceiptPayload>>(emptyLoadState);
  const [apiClientCreateState, setApiClientCreateState] =
    useState<LoadState<ApiClientCreatePayload>>(emptyLoadState);
  const [apiClientListState, setApiClientListState] =
    useState<LoadState<ApiClientListPayload>>(emptyLoadState);
  const [apiKeyCreateState, setApiKeyCreateState] =
    useState<LoadState<ApiKeyCreatePayload>>(emptyLoadState);
  const [apiUsageState, setApiUsageState] =
    useState<LoadState<ApiUsageListPayload>>(emptyLoadState);
  const [careerPlatformRegistryState, setCareerPlatformRegistryState] =
    useState<LoadState<CareerPlatformRegistryPayload>>(emptyLoadState);
  const [careerPlatformExportState, setCareerPlatformExportState] =
    useState<LoadState<CareerPlatformExportPayload>>(emptyLoadState);
  const [currentUserState, setCurrentUserState] = useState<LoadState<CurrentUserProfile>>(emptyLoadState);
  const [preferenceState, setPreferenceState] = useState<LoadState<UserPreferenceProfile>>(emptyLoadState);
  const [preferenceDraft, setPreferenceDraft] = useState<PreferenceDraft>(() => emptyPreferenceDraft());
  const [artifactsState, setArtifactsState] = useState<LoadState<{ saved_market_artifacts: SavedMarketArtifact[] }>>(emptyLoadState);
  const [alertsState, setAlertsState] = useState<LoadState<UserAlertList>>(emptyLoadState);
  const [snapshotsState, setSnapshotsState] = useState<LoadState<{ personalized_recommendation_snapshots: PersonalizedRecommendationSnapshot[] }>>(emptyLoadState);
  const [scoringPreviewState, setScoringPreviewState] = useState<LoadState<ScoringPreviewResult>>(emptyLoadState);
  const [explanationStates, setExplanationStates] = useState<Record<string, LoadState<ExplanationResult>>>({});
  const [exportState, setExportState] = useState<LoadState<UserDataExport>>(emptyLoadState);
  const [deactivationResult, setDeactivationResult] = useState<AccountDeactivationResult | null>(null);
  const [accountAction, setAccountAction] = useState<AccountActionState>({ loading: false, message: null, error: null });
  const [billingAction, setBillingAction] = useState<BillingActionState>({
    loadingPlanKey: null,
    loadingPortal: false,
    message: null,
    error: null,
  });
  const [deactivateConfirmed, setDeactivateConfirmed] = useState(false);
  const [accountDeactivated, setAccountDeactivated] = useState(false);
  const discoveryRequestKey = useRef(0);
  const recommendationRequestKey = useRef(0);

  const regionList = useMemo(() => regions.envelope?.data?.regions ?? [], [regions.envelope]);
  const hasLoadedRegionList = Boolean(regions.envelope?.data?.regions);
  const companyOptions = getCompanyOptions(regionDetails);
  const defaultRegionId = getDefaultRegionId(regionList);
  const selectedRouteRegionToken = route.regionId;
  const selectedRegionId = selectedRouteRegionToken
    ? canonicalRegionIdForToken(selectedRouteRegionToken, regionList)
      ?? regionDetails[selectedRouteRegionToken]?.data?.region_id
      ?? selectedRouteRegionToken
    : defaultRegionId;
  const selectedRegionIdentity = regionList.find(
    (region) => region.region_id === selectedRegionId,
  );
  const selectedRegionRouteToken = geographicRouteToken(
    selectedRegionIdentity ?? selectedRegionId,
  );
  const selectedRegionIsKnown = isKnownRegion(selectedRegionId, regionList, hasLoadedRegionList)
    || (route.page === "region" && Boolean(selectedRouteRegionToken));
  const selectedCompanyId = route.companyId ?? companyOptions[0]?.company_id ?? "";
  const comparisonA = route.comparison.regionA || defaultRegionId;
  const comparisonB = route.comparison.regionB || getFallbackComparisonRegion(regionList, comparisonA);
  const comparisonRegionAKnown = isKnownRegion(comparisonA, regionList, hasLoadedRegionList);
  const comparisonRegionBKnown = isKnownRegion(comparisonB, regionList, hasLoadedRegionList);
  const discoveryFilters = route.discovery;
  const discoveryUrl = personalizedDiscoveryUrl(discoveryFilters);
  const selectedRecommendationGoalMode = isRecommendationGoalMode(route.recommendationGoalMode)
    ? route.recommendationGoalMode
    : DEFAULT_RECOMMENDATION_GOAL_MODE;
  const institutionOrganizations = institutionOrganizationsState.envelope?.data?.organizations ?? [];
  const selectedInstitutionOrganizationId =
    route.organizationId ?? institutionOrganizations[0]?.organization.organization_id ?? "";
  const protectedOptions = useMemo<ProtectedRequestOptions>(
    () => ({ getAccessToken: auth.getAccessTokenSilently }),
    [auth.getAccessTokenSilently],
  );
  const comparisonValidationError =
    comparisonA === comparisonB
      ? "Choose two distinct regions before running comparison."
      : !comparisonRegionAKnown || !comparisonRegionBKnown
        ? `Comparison URL includes unknown region ID(s): ${[
            comparisonRegionAKnown ? null : comparisonA,
            comparisonRegionBKnown ? null : comparisonB,
          ]
            .filter(Boolean)
            .join(", ")}`
        : null;
  const selectedRegionState: LoadState<RegionDetail> = {
    loading: selectedRegionIsKnown ? Boolean(regionLoading[selectedRegionId]) : false,
    envelope: selectedRegionIsKnown ? regionDetails[selectedRegionId] ?? null : null,
    error: selectedRegionIsKnown
      ? regionErrors[selectedRegionId] ?? null
      : `Unknown region ID: ${selectedRegionId}`,
  };
  const selectedRegionSourceState = regionSourceStates[selectedRegionId] ?? emptyLoadState<SourceExplanation>();
  const selectedRegionRoleFamilyState =
    regionCompanySearchStates[selectedRegionId] ?? emptyLoadState<CompanySearchResponse>();
  const selectedCompanySourceState = companySourceStates[selectedCompanyId] ?? emptyLoadState<SourceExplanation>();
  const selectedCompanyGeographyState =
    companyGeographyStates[selectedCompanyId] ?? emptyLoadState<CompanyGeographyResponse>();
  const selectedPublicBenchmarkDetailState = route.benchmarkSlug
    ? publicBenchmarkDetailStates[route.benchmarkSlug] ?? emptyLoadState<PublicBenchmark>()
    : emptyLoadState<PublicBenchmark>();
  const selectedPublicReportDetailState = route.reportSlug
    ? publicReportDetailStates[route.reportSlug] ?? emptyLoadState<PublicReport>()
    : emptyLoadState<PublicReport>();
  const savedArtifactRefs = useMemo(() => {
    const refs = new Set<string>();
    for (const artifact of artifactsState.envelope?.data?.saved_market_artifacts ?? []) {
      refs.add(savedArtifactKey(artifact.artifact_type, artifact.artifact_ref));
    }
    return refs;
  }, [artifactsState.envelope]);
  const savedArtifactByKey = useMemo(() => {
    const refs = new Map<string, SavedMarketArtifact>();
    for (const artifact of artifactsState.envelope?.data?.saved_market_artifacts ?? []) {
      refs.set(savedArtifactKey(artifact.artifact_type, artifact.artifact_ref), artifact);
    }
    return refs;
  }, [artifactsState.envelope]);
  const comparisonArtifactRef = comparisonState.envelope?.data?.comparison_id
    ?? canonicalComparisonRef(comparisonA, comparisonB);
  const canSavePersonalOverlays = auth.isConfigured && auth.isAuthenticated && !accountDeactivated;
  const canExplainGuidance = canSavePersonalOverlays;
  const canUseIntegrations = canSavePersonalOverlays;
  const regionSourceIdsNeeded = useMemo(() => {
    const ids: string[] = [];
    if (isProductRoute && selectedRegionId && selectedRegionIsKnown) ids.push(selectedRegionId);
    if (route.page === "compare") {
      if (comparisonRegionAKnown) ids.push(comparisonA);
      if (comparisonRegionBKnown) ids.push(comparisonB);
    }
    if (route.page === "discovery") {
      for (const regionId of discoveryFilters.selectedRegions) {
        if (isKnownRegion(regionId, regionList, hasLoadedRegionList)) ids.push(regionId);
      }
    }
    return Array.from(new Set(ids));
  }, [
    comparisonA,
    comparisonB,
    comparisonRegionAKnown,
    comparisonRegionBKnown,
    discoveryFilters.selectedRegions,
    hasLoadedRegionList,
    isProductRoute,
    regionList,
    route.page,
    selectedRegionId,
    selectedRegionIsKnown,
  ]);

  const navigateTo = useCallback((url: string, options?: { replace?: boolean }) => {
    if (url === currentUrl()) {
      setRoute(readCurrentRoute());
      return;
    }

    if (options?.replace) {
      window.history.replaceState(null, "", url);
    } else {
      window.history.pushState(null, "", url);
    }
    setRoute(readCurrentRoute());
  }, []);

  const loadPublicBenchmarks = useCallback(async () => {
    setPublicBenchmarkListState((current) => ({ ...current, loading: true, error: null }));
    try {
      const envelope = await getPublicBenchmarks();
      setPublicBenchmarkListState({ loading: false, envelope, error: null });
    } catch (error) {
      setPublicBenchmarkListState({
        loading: false,
        envelope: null,
        error: error instanceof Error ? error.message : "Failed to load public benchmarks",
      });
    }
  }, []);

  const loadPublicBenchmark = useCallback(async (slug: string) => {
    setPublicBenchmarkDetailStates((current) => ({
      ...current,
      [slug]: { ...(current[slug] ?? emptyLoadState<PublicBenchmark>()), loading: true, error: null },
    }));
    try {
      const envelope = await getPublicBenchmark(slug);
      setPublicBenchmarkDetailStates((current) => ({
        ...current,
        [slug]: { loading: false, envelope, error: null },
      }));
    } catch (error) {
      setPublicBenchmarkDetailStates((current) => ({
        ...current,
        [slug]: {
          loading: false,
          envelope: null,
          error: error instanceof Error ? error.message : "Failed to load public benchmark",
        },
      }));
    }
  }, []);

  const loadPublicReports = useCallback(async () => {
    setPublicReportListState((current) => ({ ...current, loading: true, error: null }));
    try {
      const envelope = await getPublicReports();
      setPublicReportListState({ loading: false, envelope, error: null });
    } catch (error) {
      setPublicReportListState({
        loading: false,
        envelope: null,
        error: error instanceof Error ? error.message : "Failed to load public reports",
      });
    }
  }, []);

  const loadPublicReport = useCallback(async (slug: string) => {
    setPublicReportDetailStates((current) => ({
      ...current,
      [slug]: { ...(current[slug] ?? emptyLoadState<PublicReport>()), loading: true, error: null },
    }));
    try {
      const envelope = await getPublicReport(slug);
      setPublicReportDetailStates((current) => ({
        ...current,
        [slug]: { loading: false, envelope, error: null },
      }));
    } catch (error) {
      setPublicReportDetailStates((current) => ({
        ...current,
        [slug]: {
          loading: false,
          envelope: null,
          error: error instanceof Error ? error.message : "Failed to load public report",
        },
      }));
    }
  }, []);

  const loadPredictiveReport = useCallback(async () => {
    setPredictiveReportState((current) => ({ ...current, loading: true, error: null }));
    try {
      const envelope = await getPredictiveReport(DEFAULT_FORECAST_REGION_IDS);
      setPredictiveReportState({ loading: false, envelope, error: null });
    } catch (error) {
      setPredictiveReportState({
        loading: false,
        envelope: null,
        error: error instanceof Error ? error.message : "Failed to load predictive forecasts",
      });
    }
  }, []);

  const resetAccountState = useCallback(() => {
    setCurrentUserState(emptyLoadState());
    setPreferenceState(emptyLoadState());
    setPreferenceDraft(emptyPreferenceDraft());
    setArtifactsState(emptyLoadState());
    setAlertsState(emptyLoadState());
    setSnapshotsState(emptyLoadState());
    setScoringPreviewState(emptyLoadState());
    setExplanationStates({});
    setExportState(emptyLoadState());
    setMonetizationMeState(emptyLoadState());
    setMonetizationEntitlementsState(emptyLoadState());
    setMonetizationUsageState(emptyLoadState());
    setInstitutionOrganizationsState(emptyLoadState());
    setInstitutionDashboardState(emptyLoadState());
    setInstitutionAdvisorState(emptyLoadState());
    setInstitutionReportState(emptyLoadState());
    setInstitutionReportsListState(emptyLoadState());
    setInstitutionDataRequestState(emptyLoadState());
    setInstitutionDataRequestsListState(emptyLoadState());
    setPartnerImportCreateState(emptyLoadState());
    setPartnerImportListState(emptyLoadState());
    setPartnerImportActionState(emptyLoadState());
    setPartnerImportReceiptState(emptyLoadState());
    setApiClientCreateState(emptyLoadState());
    setApiClientListState(emptyLoadState());
    setApiKeyCreateState(emptyLoadState());
    setApiUsageState(emptyLoadState());
    setCareerPlatformRegistryState(emptyLoadState());
    setCareerPlatformExportState(emptyLoadState());
    setBillingAction({ loadingPlanKey: null, loadingPortal: false, message: null, error: null });
    setDeactivationResult(null);
    setDeactivateConfirmed(false);
  }, []);

  const loadAccountData = useCallback(async () => {
    if (!auth.isAuthenticated || accountDeactivated) return;

    setCurrentUserState((current) => ({ ...current, loading: true, error: null }));
    setPreferenceState((current) => ({ ...current, loading: true, error: null }));
    setArtifactsState((current) => ({ ...current, loading: true, error: null }));
    setAlertsState((current) => ({ ...current, loading: true, error: null }));
    setSnapshotsState((current) => ({ ...current, loading: true, error: null }));
    setMonetizationMeState((current) => ({ ...current, loading: true, error: null }));
    setMonetizationEntitlementsState((current) => ({ ...current, loading: true, error: null }));
    setMonetizationUsageState((current) => ({ ...current, loading: true, error: null }));

    const [
      userResult,
      preferenceResult,
      artifactResult,
      alertResult,
      snapshotResult,
      monetizationMeResult,
      monetizationEntitlementsResult,
      monetizationUsageResult,
    ] = await Promise.allSettled([
      getCurrentUser(protectedOptions),
      getPreferences(protectedOptions),
      listSavedMarketArtifacts(protectedOptions),
      listAlerts(protectedOptions),
      listRecommendationSnapshots(protectedOptions),
      getMyMonetization(protectedOptions),
      getMyMonetizationEntitlements(protectedOptions),
      getMyMonetizationUsage(protectedOptions),
    ]);

    if (userResult.status === "fulfilled") {
      setCurrentUserState({ loading: false, envelope: userResult.value, error: null });
    } else {
      setCurrentUserState({
        loading: false,
        envelope: null,
        error: userResult.reason instanceof Error ? userResult.reason.message : "Failed to load account",
      });
    }

    if (preferenceResult.status === "fulfilled") {
      setPreferenceState({ loading: false, envelope: preferenceResult.value, error: null });
      setPreferenceDraft(preferenceDraftFromProfile(preferenceResult.value.data));
    } else {
      setPreferenceState({
        loading: false,
        envelope: null,
        error: preferenceResult.reason instanceof Error ? preferenceResult.reason.message : "Failed to load preferences",
      });
    }

    if (artifactResult.status === "fulfilled") {
      setArtifactsState({ loading: false, envelope: artifactResult.value, error: null });
    } else {
      setArtifactsState({
        loading: false,
        envelope: null,
        error: artifactResult.reason instanceof Error ? artifactResult.reason.message : "Failed to load saved artifacts",
      });
    }

    if (alertResult.status === "fulfilled") {
      setAlertsState({ loading: false, envelope: alertResult.value, error: null });
    } else {
      setAlertsState({
        loading: false,
        envelope: null,
        error: alertResult.reason instanceof Error ? alertResult.reason.message : "Failed to load alerts",
      });
    }

    if (snapshotResult.status === "fulfilled") {
      setSnapshotsState({ loading: false, envelope: snapshotResult.value, error: null });
    } else {
      setSnapshotsState({
        loading: false,
        envelope: null,
        error: snapshotResult.reason instanceof Error ? snapshotResult.reason.message : "Failed to load snapshots",
      });
    }

    if (monetizationMeResult.status === "fulfilled") {
      setMonetizationMeState({ loading: false, envelope: monetizationMeResult.value, error: null });
    } else {
      setMonetizationMeState({
        loading: false,
        envelope: null,
        error: monetizationMeResult.reason instanceof Error ? monetizationMeResult.reason.message : "Failed to load monetization account",
      });
    }

    if (monetizationEntitlementsResult.status === "fulfilled") {
      setMonetizationEntitlementsState({ loading: false, envelope: monetizationEntitlementsResult.value, error: null });
    } else {
      setMonetizationEntitlementsState({
        loading: false,
        envelope: null,
        error: monetizationEntitlementsResult.reason instanceof Error ? monetizationEntitlementsResult.reason.message : "Failed to load entitlements",
      });
    }

    if (monetizationUsageResult.status === "fulfilled") {
      setMonetizationUsageState({ loading: false, envelope: monetizationUsageResult.value, error: null });
    } else {
      setMonetizationUsageState({
        loading: false,
        envelope: null,
        error: monetizationUsageResult.reason instanceof Error ? monetizationUsageResult.reason.message : "Failed to load monetization usage",
      });
    }
  }, [accountDeactivated, auth.isAuthenticated, protectedOptions]);

  const handleStartCheckout = useCallback(async (planKey: MonetizationPlanKey) => {
    if (!auth.isAuthenticated || accountDeactivated) {
      setBillingAction({
        loadingPlanKey: null,
        loadingPortal: false,
        message: null,
        error: "Sign in to start checkout for paid workflow plans.",
      });
      return;
    }
    const billingStatus = billingStatusState.envelope?.data;
    if (!billingStatus?.checkout_available || !billingStatus.checkout_plan_keys.includes(planKey)) {
      setBillingAction({
        loadingPlanKey: null,
        loadingPortal: false,
        message: null,
        error: billingStatus?.disabled_reason ?? "Checkout is not available for this plan.",
      });
      return;
    }

    setBillingAction({ loadingPlanKey: planKey, loadingPortal: false, message: null, error: null });
    try {
      const envelope = await createBillingCheckoutSession(planKey, protectedOptions);
      const checkoutUrl = envelope.data?.checkout_url;
      if (!checkoutUrl) throw new Error("Checkout session did not include a redirect URL.");
      setBillingAction({
        loadingPlanKey: null,
        loadingPortal: false,
        message: "Checkout session created. Redirecting to the billing provider; access updates after verified confirmation.",
        error: null,
      });
      redirectToBillingProvider(checkoutUrl);
    } catch (error) {
      setBillingAction({
        loadingPlanKey: null,
        loadingPortal: false,
        message: null,
        error: error instanceof Error ? error.message : "Failed to create checkout session",
      });
    }
  }, [
    accountDeactivated,
    auth.isAuthenticated,
    billingStatusState.envelope,
    protectedOptions,
  ]);

  const handleManageBilling = useCallback(async () => {
    if (!auth.isAuthenticated || accountDeactivated) {
      setBillingAction({
        loadingPlanKey: null,
        loadingPortal: false,
        message: null,
        error: "Sign in to manage billing.",
      });
      return;
    }
    setBillingAction({ loadingPlanKey: null, loadingPortal: true, message: null, error: null });
    try {
      const envelope = await createBillingPortalSession(protectedOptions);
      const portalUrl = envelope.data?.portal_url;
      if (!portalUrl) throw new Error("Billing portal session did not include a redirect URL.");
      setBillingAction({
        loadingPlanKey: null,
        loadingPortal: false,
        message: "Opening billing management.",
        error: null,
      });
      redirectToBillingProvider(portalUrl);
    } catch (error) {
      setBillingAction({
        loadingPlanKey: null,
        loadingPortal: false,
        message: null,
        error: error instanceof Error ? error.message : "Failed to open billing portal",
      });
    }
  }, [accountDeactivated, auth.isAuthenticated, protectedOptions]);

  const loadRegion = useCallback(async (regionId: string) => {
    if (!regionId) return;
    setRegionLoading((current) => ({ ...current, [regionId]: true }));
    setRegionErrors((current) => ({ ...current, [regionId]: "" }));
    try {
      const envelope = await getRegion(regionId);
      const canonicalRegionId = envelope.data?.region_id;
      const publicSlug = envelope.data?.public_slug;
      setRegionDetails((current) => ({
        ...current,
        [regionId]: envelope,
        ...(canonicalRegionId ? { [canonicalRegionId]: envelope } : {}),
        ...(publicSlug ? { [publicSlug]: envelope } : {}),
      }));
    } catch (error) {
      setRegionErrors((current) => ({
        ...current,
        [regionId]: error instanceof Error ? error.message : "Failed to load region",
      }));
    } finally {
      setRegionLoading((current) => ({ ...current, [regionId]: false }));
    }
  }, []);

  useEffect(() => {
    const handlePopState = () => setRoute(readCurrentRoute());
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  useEffect(() => {
    if (route.page !== "benchmarks") return;
    if (publicBenchmarkListState.loading || publicBenchmarkListState.envelope) return;
    void loadPublicBenchmarks();
  }, [
    loadPublicBenchmarks,
    publicBenchmarkListState.envelope,
    publicBenchmarkListState.loading,
    route.page,
  ]);

  useEffect(() => {
    if (route.page !== "benchmarks" || !route.benchmarkSlug) return;
    const detailState = publicBenchmarkDetailStates[route.benchmarkSlug];
    if (detailState?.loading || detailState?.envelope || detailState?.error) return;
    void loadPublicBenchmark(route.benchmarkSlug);
  }, [
    loadPublicBenchmark,
    publicBenchmarkDetailStates,
    route.benchmarkSlug,
    route.page,
  ]);

  useEffect(() => {
    if (route.page !== "reports") return;
    if (publicReportListState.loading || publicReportListState.envelope) return;
    void loadPublicReports();
  }, [
    loadPublicReports,
    publicReportListState.envelope,
    publicReportListState.loading,
    route.page,
  ]);

  useEffect(() => {
    if (route.page !== "reports" || !route.reportSlug) return;
    const detailState = publicReportDetailStates[route.reportSlug];
    if (detailState?.loading || detailState?.envelope || detailState?.error) return;
    void loadPublicReport(route.reportSlug);
  }, [
    loadPublicReport,
    publicReportDetailStates,
    route.page,
    route.reportSlug,
  ]);

  useEffect(() => {
    if (route.page !== "forecasts") return;
    if (predictiveReportState.loading || predictiveReportState.envelope) return;
    void loadPredictiveReport();
  }, [
    loadPredictiveReport,
    predictiveReportState.envelope,
    predictiveReportState.loading,
    route.page,
  ]);

  useEffect(() => {
    if (!auth.isAuthenticated) {
      resetAccountState();
      setAccountDeactivated(false);
      return;
    }
    void loadAccountData();
  }, [auth.isAuthenticated, loadAccountData, resetAccountState]);

  useEffect(() => {
    if (route.page !== "institution") return;
    if (!auth.isAuthenticated || accountDeactivated) return;
    if (institutionOrganizationsState.loading || institutionOrganizationsState.envelope) return;

    async function loadInstitutionOrganizations() {
      setInstitutionOrganizationsState((current) => ({ ...current, loading: true, error: null }));
      try {
        const envelope = await getInstitutionCurrentOrganizations(protectedOptions);
        setInstitutionOrganizationsState({ loading: false, envelope, error: null });
      } catch (error) {
        setInstitutionOrganizationsState({
          loading: false,
          envelope: null,
          error: error instanceof Error ? error.message : "Failed to load institutional organizations",
        });
      }
    }

    void loadInstitutionOrganizations();
  }, [
    accountDeactivated,
    auth.isAuthenticated,
    institutionOrganizationsState.envelope,
    institutionOrganizationsState.loading,
    protectedOptions,
    route.page,
  ]);

  useEffect(() => {
    if (route.page !== "institution") return;
    if (route.institutionView && route.institutionView !== "dashboard") {
      setInstitutionDashboardState(emptyLoadState());
      return;
    }
    if (!auth.isAuthenticated || accountDeactivated) {
      setInstitutionDashboardState(emptyLoadState());
      return;
    }
    if (!selectedInstitutionOrganizationId) {
      setInstitutionDashboardState(emptyLoadState());
      return;
    }

    let cancelled = false;
    async function loadInstitutionDashboard() {
      setInstitutionDashboardState((current) => ({ ...current, loading: true, error: null }));
      try {
        const envelope = await getInstitutionDashboard(
          selectedInstitutionOrganizationId,
          protectedOptions,
        );
        if (!cancelled) {
          setInstitutionDashboardState({ loading: false, envelope, error: null });
        }
      } catch (error) {
        if (!cancelled) {
          setInstitutionDashboardState({
            loading: false,
            envelope: null,
            error: error instanceof Error ? error.message : "Failed to load institutional dashboard",
          });
        }
      }
    }

    void loadInstitutionDashboard();
    return () => {
      cancelled = true;
    };
  }, [
    accountDeactivated,
    auth.isAuthenticated,
    protectedOptions,
    route.institutionView,
    route.page,
    selectedInstitutionOrganizationId,
  ]);

  useEffect(() => {
    if (route.page !== "institution" || route.institutionView !== "decisions") {
      setInstitutionDecisionDashboardState(emptyLoadState());
      setInstitutionCurriculumState(emptyLoadState());
      setInstitutionWorkforceReportState(emptyLoadState());
      setInstitutionBenchmarkState(emptyLoadState());
      return;
    }
    if (!auth.isAuthenticated || accountDeactivated || !selectedInstitutionOrganizationId) {
      setInstitutionDecisionDashboardState(emptyLoadState());
      setInstitutionCurriculumState(emptyLoadState());
      setInstitutionWorkforceReportState(emptyLoadState());
      setInstitutionBenchmarkState(emptyLoadState());
      return;
    }

    let cancelled = false;
    async function loadInstitutionDecisionInfrastructure() {
      setInstitutionDecisionDashboardState((current) => ({ ...current, loading: true, error: null }));
      setInstitutionCurriculumState((current) => ({ ...current, loading: true, error: null }));
      setInstitutionWorkforceReportState((current) => ({ ...current, loading: true, error: null }));
      setInstitutionBenchmarkState((current) => ({ ...current, loading: true, error: null }));
      try {
        const [dashboardEnvelope, curriculumEnvelope, reportEnvelope, benchmarkEnvelope] = await Promise.all([
          getInstitutionDecisionDashboard(selectedInstitutionOrganizationId, protectedOptions),
          getInstitutionCurriculumMarketMap(selectedInstitutionOrganizationId, protectedOptions),
          getInstitutionWorkforceReport(
            selectedInstitutionOrganizationId,
            "regional_workforce_opportunity",
            protectedOptions,
          ),
          getInstitutionBenchmarks(selectedInstitutionOrganizationId, protectedOptions),
        ]);
        if (!cancelled) {
          setInstitutionDecisionDashboardState({ loading: false, envelope: dashboardEnvelope, error: null });
          setInstitutionCurriculumState({ loading: false, envelope: curriculumEnvelope, error: null });
          setInstitutionWorkforceReportState({ loading: false, envelope: reportEnvelope, error: null });
          setInstitutionBenchmarkState({ loading: false, envelope: benchmarkEnvelope, error: null });
        }
      } catch (error) {
        const message = error instanceof Error
          ? error.message
          : "Failed to load institutional decision infrastructure";
        if (!cancelled) {
          setInstitutionDecisionDashboardState({ loading: false, envelope: null, error: message });
          setInstitutionCurriculumState({ loading: false, envelope: null, error: message });
          setInstitutionWorkforceReportState({ loading: false, envelope: null, error: message });
          setInstitutionBenchmarkState({ loading: false, envelope: null, error: message });
        }
      }
    }

    void loadInstitutionDecisionInfrastructure();
    return () => {
      cancelled = true;
    };
  }, [
    accountDeactivated,
    auth.isAuthenticated,
    protectedOptions,
    route.institutionView,
    route.page,
    selectedInstitutionOrganizationId,
  ]);

  useEffect(() => {
    setInstitutionAdvisorState(emptyLoadState());
  }, [route.page, route.institutionView, selectedInstitutionOrganizationId]);

  useEffect(() => {
    setInstitutionReportState(emptyLoadState());
    setInstitutionReportsListState(emptyLoadState());
    setInstitutionDataRequestState(emptyLoadState());
    setInstitutionDataRequestsListState(emptyLoadState());
    setPartnerImportCreateState(emptyLoadState());
    setPartnerImportListState(emptyLoadState());
    setPartnerImportActionState(emptyLoadState());
    setPartnerImportReceiptState(emptyLoadState());
  }, [route.page, route.institutionView, selectedInstitutionOrganizationId]);

  useEffect(() => {
    if (route.page !== "institution" || route.institutionView !== "reports") return;
    if (!auth.isAuthenticated || accountDeactivated || !selectedInstitutionOrganizationId) {
      setInstitutionReportsListState(emptyLoadState());
      return;
    }
    if (institutionReportsListState.loading || institutionReportsListState.envelope) return;

    async function loadInstitutionReports() {
      setInstitutionReportsListState((current) => ({ ...current, loading: true, error: null }));
      try {
        const envelope = await listInstitutionReports(
          selectedInstitutionOrganizationId,
          protectedOptions,
        );
        setInstitutionReportsListState({ loading: false, envelope, error: null });
      } catch (error) {
        setInstitutionReportsListState({
          loading: false,
          envelope: null,
          error: error instanceof Error ? error.message : "Failed to load institutional reports",
        });
      }
    }

    void loadInstitutionReports();
  }, [
    accountDeactivated,
    auth.isAuthenticated,
    institutionReportsListState.envelope,
    institutionReportsListState.loading,
    protectedOptions,
    route.institutionView,
    route.page,
    selectedInstitutionOrganizationId,
  ]);

  useEffect(() => {
    if (route.page !== "institution" || route.institutionView !== "data-requests") return;
    if (!auth.isAuthenticated || accountDeactivated || !selectedInstitutionOrganizationId) {
      setInstitutionDataRequestsListState(emptyLoadState());
      return;
    }
    if (
      institutionDataRequestsListState.loading
      || institutionDataRequestsListState.envelope
    ) {
      return;
    }

    async function loadInstitutionDataRequests() {
      setInstitutionDataRequestsListState((current) => ({
        ...current,
        loading: true,
        error: null,
      }));
      try {
        const envelope = await listInstitutionDataRequests(
          selectedInstitutionOrganizationId,
          protectedOptions,
        );
        setInstitutionDataRequestsListState({ loading: false, envelope, error: null });
      } catch (error) {
        setInstitutionDataRequestsListState({
          loading: false,
          envelope: null,
          error: error instanceof Error
            ? error.message
            : "Failed to load institutional data requests",
        });
      }
    }

    void loadInstitutionDataRequests();
  }, [
    accountDeactivated,
    auth.isAuthenticated,
    institutionDataRequestsListState.envelope,
    institutionDataRequestsListState.loading,
    protectedOptions,
    route.institutionView,
    route.page,
    selectedInstitutionOrganizationId,
  ]);

  useEffect(() => {
    if (route.page !== "institution" || route.institutionView !== "imports") return;
    if (!auth.isAuthenticated || accountDeactivated || !selectedInstitutionOrganizationId) {
      setPartnerImportListState(emptyLoadState());
      return;
    }
    if (partnerImportListState.loading || partnerImportListState.envelope) return;

    async function loadPartnerImports() {
      setPartnerImportListState((current) => ({
        ...current,
        loading: true,
        error: null,
      }));
      try {
        const envelope = await listPartnerImports(
          selectedInstitutionOrganizationId,
          protectedOptions,
        );
        setPartnerImportListState({ loading: false, envelope, error: null });
      } catch (error) {
        setPartnerImportListState({
          loading: false,
          envelope: null,
          error: error instanceof Error
            ? error.message
            : "Failed to load partner imports",
        });
      }
    }

    void loadPartnerImports();
  }, [
    accountDeactivated,
    auth.isAuthenticated,
    partnerImportListState.envelope,
    partnerImportListState.loading,
    protectedOptions,
    route.institutionView,
    route.page,
    selectedInstitutionOrganizationId,
  ]);

  useEffect(() => {
    if (!auth.isAuthenticated || accountDeactivated) {
      setCareerPlatformRegistryState(emptyLoadState());
      return;
    }
    if (
      careerPlatformRegistryState.loading
      || careerPlatformRegistryState.envelope
      || careerPlatformRegistryState.error
    ) {
      return;
    }

    async function loadCareerPlatformRegistry() {
      setCareerPlatformRegistryState((current) => ({
        ...current,
        loading: true,
        error: null,
      }));
      try {
        const envelope = await getCareerPlatformRegistry(protectedOptions);
        setCareerPlatformRegistryState({ loading: false, envelope, error: null });
      } catch (error) {
        setCareerPlatformRegistryState({
          loading: false,
          envelope: null,
          error: error instanceof Error ? error.message : "Failed to load career platforms",
        });
      }
    }

    void loadCareerPlatformRegistry();
  }, [
    accountDeactivated,
    auth.isAuthenticated,
    careerPlatformRegistryState.envelope,
    careerPlatformRegistryState.error,
    careerPlatformRegistryState.loading,
    protectedOptions,
  ]);

  useEffect(() => {
    setMonetizationAccessPreviewStates({});
  }, [auth.isAuthenticated]);

  useEffect(() => {
    if (!isProductRoute) return;

    async function loadInitialData() {
      setHealth((current) => ({ ...current, loading: true, error: null }));
      setRegions((current) => ({ ...current, loading: true, error: null }));
      setMarketCoverageState((current) => ({ ...current, loading: true, error: null }));
      setMarketOperationsState((current) => ({ ...current, loading: true, error: null }));

      const [healthResult, regionsResult, marketCoverageResult, marketOperationsResult] = await Promise.allSettled([
        getHealth(),
        getRegions(),
        getImportedMarkets(),
        getImportedMarketOperationsView(),
      ]);

      if (healthResult.status === "fulfilled") {
        setHealth({ loading: false, envelope: healthResult.value, error: null });
      } else {
        setHealth({
          loading: false,
          envelope: null,
          error: healthResult.reason instanceof Error ? healthResult.reason.message : "Failed to load health",
        });
      }

      if (regionsResult.status === "fulfilled") {
        setRegions({ loading: false, envelope: regionsResult.value, error: null });
        const regionIds = regionsResult.value.data?.regions.map((region) => region.region_id) ?? [];
        const defaults = [DEFAULT_REGION_A, DEFAULT_REGION_B].filter((regionId) =>
          regionIds.includes(regionId),
        );
        await Promise.all(defaults.map((regionId) => loadRegion(regionId)));
      } else {
        setRegions({
          loading: false,
          envelope: null,
          error: regionsResult.reason instanceof Error ? regionsResult.reason.message : "Failed to load regions",
        });
      }

      if (marketCoverageResult.status === "fulfilled") {
        setMarketCoverageState({
          loading: false,
          envelope: marketCoverageResult.value,
          error: null,
        });
      } else {
        setMarketCoverageState({
          loading: false,
          envelope: null,
          error: marketCoverageResult.reason instanceof Error
            ? marketCoverageResult.reason.message
            : "Failed to load imported market coverage",
        });
      }

      if (marketOperationsResult.status === "fulfilled") {
        setMarketOperationsState({
          loading: false,
          envelope: marketOperationsResult.value,
          error: null,
        });
      } else {
        setMarketOperationsState({
          loading: false,
          envelope: null,
          error: marketOperationsResult.reason instanceof Error
            ? marketOperationsResult.reason.message
            : "Failed to load imported market operations",
        });
      }
    }

    void loadInitialData();
  }, [isProductRoute, loadRegion]);

  useEffect(() => {
    if (!isProductRoute) return;

    async function loadRegionSearch() {
      setRegionSearchState((current) => ({ ...current, loading: true, error: null }));
      try {
        const envelope = await searchRegions();
        setRegionSearchState({ loading: false, envelope, error: null });
      } catch (error) {
        setRegionSearchState({
          loading: false,
          envelope: null,
          error: error instanceof Error ? error.message : "Failed to load region search",
        });
      }
    }

    void loadRegionSearch();
  }, [isProductRoute]);

  useEffect(() => {
    if (route.page !== "recommendations") return;
    if (recommendationGoalModesState.loading || recommendationGoalModesState.envelope) return;

    async function loadRecommendationGoalModes() {
      setRecommendationGoalModesState((current) => ({ ...current, loading: true, error: null }));
      try {
        const envelope = await getRecommendationGoalModes();
        setRecommendationGoalModesState({ loading: false, envelope, error: null });
      } catch (error) {
        setRecommendationGoalModesState({
          loading: false,
          envelope: null,
          error: error instanceof Error ? error.message : "Failed to load recommendation goal modes",
        });
      }
    }

    void loadRecommendationGoalModes();
  }, [recommendationGoalModesState.envelope, recommendationGoalModesState.loading, route.page]);

  useEffect(() => {
    if (route.page !== "recommendations") {
      recommendationRequestKey.current += 1;
      setRecommendationStrategyState(emptyLoadState());
      return;
    }

    const requestKey = ++recommendationRequestKey.current;
    async function loadRecommendationStrategy() {
      setRecommendationStrategyState((current) => ({ ...current, loading: true, error: null }));
      try {
        const envelope = await getRecommendationStrategy({
          goal_mode: selectedRecommendationGoalMode,
          include_company_recommendations: true,
          region_limit: 10,
          company_limit: 10,
        });
        if (requestKey === recommendationRequestKey.current) {
          setRecommendationStrategyState({ loading: false, envelope, error: null });
        }
      } catch (error) {
        if (requestKey === recommendationRequestKey.current) {
          setRecommendationStrategyState({
            loading: false,
            envelope: null,
            error: error instanceof Error ? error.message : "Failed to load recommendation strategy",
          });
        }
      }
    }

    void loadRecommendationStrategy();
  }, [route.page, selectedRecommendationGoalMode]);

  useEffect(() => {
    if (route.page !== "plans" && route.page !== "recommendations") return;
    if (
      monetizationPlansState.loading
      || monetizationFeaturesState.loading
      || monetizationReportsState.loading
      || billingStatusState.loading
      || (
        monetizationPlansState.envelope
        && monetizationFeaturesState.envelope
        && monetizationReportsState.envelope
        && billingStatusState.envelope
      )
    ) {
      return;
    }

    async function loadMonetizationCatalog() {
      setMonetizationPlansState((current) => ({ ...current, loading: true, error: null }));
      setMonetizationFeaturesState((current) => ({ ...current, loading: true, error: null }));
      setMonetizationReportsState((current) => ({ ...current, loading: true, error: null }));
      setBillingStatusState((current) => ({ ...current, loading: true, error: null }));

      const [plansResult, featuresResult, reportsResult, billingResult] = await Promise.allSettled([
        getMonetizationPlans(),
        getMonetizationFeatures(),
        getMonetizationReports(),
        getBillingStatus(),
      ]);

      if (plansResult.status === "fulfilled") {
        setMonetizationPlansState({ loading: false, envelope: plansResult.value, error: null });
      } else {
        setMonetizationPlansState({
          loading: false,
          envelope: null,
          error: plansResult.reason instanceof Error ? plansResult.reason.message : "Failed to load plans",
        });
      }

      if (featuresResult.status === "fulfilled") {
        setMonetizationFeaturesState({ loading: false, envelope: featuresResult.value, error: null });
      } else {
        setMonetizationFeaturesState({
          loading: false,
          envelope: null,
          error: featuresResult.reason instanceof Error ? featuresResult.reason.message : "Failed to load features",
        });
      }

      if (reportsResult.status === "fulfilled") {
        setMonetizationReportsState({ loading: false, envelope: reportsResult.value, error: null });
      } else {
        setMonetizationReportsState({
          loading: false,
          envelope: null,
          error: reportsResult.reason instanceof Error ? reportsResult.reason.message : "Failed to load reports",
        });
      }

      if (billingResult.status === "fulfilled") {
        setBillingStatusState({ loading: false, envelope: billingResult.value, error: null });
      } else {
        setBillingStatusState({
          loading: false,
          envelope: null,
          error: billingResult.reason instanceof Error ? billingResult.reason.message : "Failed to load billing status",
        });
      }
    }

    void loadMonetizationCatalog();
  }, [
    billingStatusState.envelope,
    billingStatusState.loading,
    monetizationFeaturesState.envelope,
    monetizationFeaturesState.loading,
    monetizationPlansState.envelope,
    monetizationPlansState.loading,
    monetizationReportsState.envelope,
    monetizationReportsState.loading,
    route.page,
  ]);

  useEffect(() => {
    if (!isProductRoute) return;

    ACCESS_PREVIEW_REQUESTS.forEach((request) => {
      const key = accessPreviewKey(request);
      const current = monetizationAccessPreviewStates[key];
      if (current?.loading || current?.envelope || current?.error) return;

      setMonetizationAccessPreviewStates((states) => ({
        ...states,
        [key]: { loading: true, envelope: null, error: null },
      }));
      getMonetizationAccessPreview(
        request,
        auth.isAuthenticated && !accountDeactivated ? protectedOptions : undefined,
      )
        .then((envelope) => {
          setMonetizationAccessPreviewStates((states) => ({
            ...states,
            [key]: { loading: false, envelope, error: null },
          }));
        })
        .catch((error) => {
          setMonetizationAccessPreviewStates((states) => ({
            ...states,
            [key]: {
              loading: false,
              envelope: null,
              error: error instanceof Error ? error.message : "Failed to load access preview",
            },
          }));
        });
    });
  }, [
    accountDeactivated,
    auth.isAuthenticated,
    isProductRoute,
    monetizationAccessPreviewStates,
    protectedOptions,
  ]);

  useEffect(() => {
    if (!isProductRoute) return;
    if (
      !selectedRegionId
      || !selectedRegionIsKnown
      || regionDetails[selectedRegionId]
      || regionLoading[selectedRegionId]
      || regionErrors[selectedRegionId]
    ) {
      return;
    }
    void loadRegion(selectedRegionId);
  }, [isProductRoute, loadRegion, regionDetails, regionErrors, regionLoading, selectedRegionId, selectedRegionIsKnown]);

  useEffect(() => {
    if (route.page !== "explore") return;
    regionList.forEach((region) => {
      if (
        !regionDetails[region.region_id]
        && !regionLoading[region.region_id]
        && !regionErrors[region.region_id]
      ) {
        void loadRegion(region.region_id);
      }
    });
  }, [loadRegion, regionDetails, regionErrors, regionList, regionLoading, route.page]);

  useEffect(() => {
    regionSourceIdsNeeded.forEach((regionId) => {
      const current = regionSourceStates[regionId];
      if (current?.loading || current?.envelope || current?.error) return;

      setRegionSourceStates((states) => ({
        ...states,
        [regionId]: { loading: true, envelope: null, error: null },
      }));
      getRegionSources(regionId)
        .then((envelope) => {
          setRegionSourceStates((states) => ({
            ...states,
            [regionId]: { loading: false, envelope, error: null },
          }));
        })
        .catch((error) => {
          setRegionSourceStates((states) => ({
            ...states,
            [regionId]: {
              loading: false,
              envelope: null,
              error: error instanceof Error ? error.message : "Failed to load region sources",
            },
          }));
        });
    });
  }, [regionSourceIdsNeeded, regionSourceStates]);

  useEffect(() => {
    if (route.page !== "compare") return;
    [comparisonA, comparisonB].forEach((regionId) => {
      if (!regionId || !isKnownRegion(regionId, regionList, hasLoadedRegionList)) return;
      if (!regionDetails[regionId] && !regionLoading[regionId] && !regionErrors[regionId]) {
        void loadRegion(regionId);
      }
    });
  }, [
    comparisonA,
    comparisonB,
    hasLoadedRegionList,
    loadRegion,
    regionDetails,
    regionErrors,
    regionList,
    regionLoading,
    route.page,
  ]);

  useEffect(() => {
    if (!isProductRoute) return;
    if (!selectedRegionId || !selectedRegionIsKnown) return;
    const current = regionCompanySearchStates[selectedRegionId];
    if (current?.loading || current?.envelope || current?.error) return;

    setRegionCompanySearchStates((states) => ({
      ...states,
      [selectedRegionId]: { loading: true, envelope: null, error: null },
    }));
    searchCompanies({ region_id: selectedRegionId })
      .then((envelope) => {
        setRegionCompanySearchStates((states) => ({
          ...states,
          [selectedRegionId]: { loading: false, envelope, error: null },
        }));
      })
      .catch((error) => {
        setRegionCompanySearchStates((states) => ({
          ...states,
          [selectedRegionId]: {
            loading: false,
            envelope: null,
            error: error instanceof Error ? error.message : "Failed to load company role-family search",
          },
        }));
      });
  }, [isProductRoute, regionCompanySearchStates, selectedRegionId, selectedRegionIsKnown]);

  useEffect(() => {
    if (route.page === "region" && !route.regionId && selectedRegionId) {
      navigateTo(regionDetailUrl(selectedRegionRouteToken), { replace: true });
    }
  }, [navigateTo, route.page, route.regionId, selectedRegionId, selectedRegionRouteToken]);

  useEffect(() => {
    if (route.page !== "region" || !route.regionId) return;
    const resolved = regionDetails[route.regionId]?.data;
    if (!resolved) return;
    const canonicalToken = geographicRouteToken(resolved);
    if (canonicalToken && canonicalToken !== route.regionId) {
      navigateTo(regionDetailUrl(canonicalToken), { replace: true });
    }
  }, [navigateTo, regionDetails, route.page, route.regionId]);

  useEffect(() => {
    if (route.page === "company" && !route.companyId && selectedCompanyId) {
      navigateTo(companyGeographyUrl(selectedCompanyId), { replace: true });
    }
  }, [navigateTo, route.companyId, route.page, selectedCompanyId]);

  useEffect(() => {
    if (!isProductRoute) {
      setCompanyState(emptyLoadState());
      return;
    }

    async function loadCompany() {
      if (!selectedCompanyId) {
        setCompanyState(emptyLoadState());
        return;
      }
      setCompanyState((current) => ({ loading: true, envelope: current.envelope, error: null }));
      try {
        const envelope = await getCompany(selectedCompanyId);
        setCompanyState({ loading: false, envelope, error: null });
      } catch (error) {
        setCompanyState({
          loading: false,
          envelope: null,
          error: error instanceof Error ? error.message : "Failed to load company",
        });
      }
    }

    void loadCompany();
  }, [isProductRoute, selectedCompanyId]);

  useEffect(() => {
    if (!isProductRoute) return;
    if (!selectedCompanyId) return;
    const current = companySourceStates[selectedCompanyId];
    if (current?.loading || current?.envelope || current?.error) return;

    setCompanySourceStates((states) => ({
      ...states,
      [selectedCompanyId]: { loading: true, envelope: null, error: null },
    }));
    getCompanySources(selectedCompanyId)
      .then((envelope) => {
        setCompanySourceStates((states) => ({
          ...states,
          [selectedCompanyId]: { loading: false, envelope, error: null },
        }));
      })
      .catch((error) => {
        setCompanySourceStates((states) => ({
          ...states,
          [selectedCompanyId]: {
            loading: false,
            envelope: null,
            error: error instanceof Error ? error.message : "Failed to load company sources",
          },
        }));
      });
  }, [companySourceStates, isProductRoute, selectedCompanyId]);

  useEffect(() => {
    if (!isProductRoute) return;
    if (!selectedCompanyId) return;
    const current = companyGeographyStates[selectedCompanyId];
    if (current?.loading || current?.envelope || current?.error) return;

    setCompanyGeographyStates((states) => ({
      ...states,
      [selectedCompanyId]: { loading: true, envelope: null, error: null },
    }));
    getCompanyGeography(selectedCompanyId)
      .then((envelope) => {
        setCompanyGeographyStates((states) => ({
          ...states,
          [selectedCompanyId]: { loading: false, envelope, error: null },
        }));
      })
      .catch((error) => {
        setCompanyGeographyStates((states) => ({
          ...states,
          [selectedCompanyId]: {
            loading: false,
            envelope: null,
            error: error instanceof Error ? error.message : "Failed to load company geography",
          },
        }));
      });
  }, [companyGeographyStates, isProductRoute, selectedCompanyId]);

  useEffect(() => {
    if (!isProductRoute) return;
    if (comparisonValidationError) {
      setComparisonState(emptyLoadState());
      return;
    }

    async function loadComparison() {
      if (!comparisonA || !comparisonB) return;
      setComparisonState((current) => ({ loading: true, envelope: current.envelope, error: null }));
      try {
        const envelope = await getComparison(comparisonA, comparisonB);
        setComparisonState({ loading: false, envelope, error: null });
      } catch (error) {
        setComparisonState({
          loading: false,
          envelope: null,
          error: error instanceof Error ? error.message : "Failed to load comparison",
        });
      }
    }

    void loadComparison();
  }, [comparisonA, comparisonB, comparisonValidationError, isProductRoute]);

  useEffect(() => {
    discoveryRequestKey.current += 1;
    setDiscoveryState(emptyLoadState());
  }, [discoveryUrl]);

  function handleRouteLink(event: MouseEvent<HTMLAnchorElement>, url: string) {
    if (!isPlainLeftClick(event)) return;
    event.preventDefault();
    navigateTo(url);
  }

  function selectRegion(regionId: string) {
    const identity = regionList.find((region) => region.region_id === regionId);
    navigateTo(regionDetailUrl(identity ?? regionId));
  }

  function selectCompany(companyId: string) {
    navigateTo(companyGeographyUrl(companyId));
  }

  function selectComparisonA(regionId: string) {
    navigateTo(compareMarketsUrl(regionId, comparisonB));
  }

  function selectComparisonB(regionId: string) {
    navigateTo(compareMarketsUrl(comparisonA, regionId));
  }

  function compareRegion(regionId: string) {
    const fallbackRegion = getFallbackComparisonRegion(regionList, regionId);
    const otherRegion = comparisonB && comparisonB !== regionId ? comparisonB : fallbackRegion;
    navigateTo(compareMarketsUrl(regionId, otherRegion));
  }

  function updateDiscoveryFilters(nextFilters: DiscoveryFilters) {
    navigateTo(personalizedDiscoveryUrl(nextFilters));
  }

  function updateRecommendationGoalMode(goalMode: RecommendationGoalMode) {
    navigateTo(recommendationsUrl(goalMode));
  }

  function handleInstitutionAdvisorSubmit(
    comparisonType: InstitutionAdvisorComparisonType,
    request: InstitutionAdvisorRequest,
  ) {
    void (async () => {
      if (!selectedInstitutionOrganizationId) {
        setInstitutionAdvisorState({
          loading: false,
          envelope: null,
          error: "Select an institutional organization before running advisor tools.",
        });
        return;
      }
      setInstitutionAdvisorState((current) => ({ ...current, loading: true, error: null }));
      try {
        const envelope = await runInstitutionAdvisorComparison(
          selectedInstitutionOrganizationId,
          comparisonType,
          request,
          protectedOptions,
        );
        setInstitutionAdvisorState({ loading: false, envelope, error: null });
      } catch (error) {
        setInstitutionAdvisorState({
          loading: false,
          envelope: null,
          error: error instanceof Error ? error.message : "Failed to run advisor tool",
        });
      }
    })();
  }

  function handleInstitutionReportGenerate(request: InstitutionReportCreateRequest) {
    void (async () => {
      if (!selectedInstitutionOrganizationId) {
        setInstitutionReportState({
          loading: false,
          envelope: null,
          error: "Select an institutional organization before generating a report.",
        });
        return;
      }
      setInstitutionReportState((current) => ({ ...current, loading: true, error: null }));
      try {
        const envelope = await generateInstitutionReport(
          selectedInstitutionOrganizationId,
          request,
          protectedOptions,
        );
        setInstitutionReportState({ loading: false, envelope, error: null });
        const listEnvelope = await listInstitutionReports(
          selectedInstitutionOrganizationId,
          protectedOptions,
        );
        setInstitutionReportsListState({ loading: false, envelope: listEnvelope, error: null });
      } catch (error) {
        setInstitutionReportState({
          loading: false,
          envelope: null,
          error: error instanceof Error ? error.message : "Failed to generate report",
        });
      }
    })();
  }

  function handleInstitutionDataRequestSubmit(request: InstitutionDataRequestCreateRequest) {
    void (async () => {
      if (!selectedInstitutionOrganizationId) {
        setInstitutionDataRequestState({
          loading: false,
          envelope: null,
          error: "Select an institutional organization before creating a request.",
        });
        return;
      }
      setInstitutionDataRequestState((current) => ({
        ...current,
        loading: true,
        error: null,
      }));
      try {
        const envelope = await createInstitutionDataRequest(
          selectedInstitutionOrganizationId,
          request,
          protectedOptions,
        );
        setInstitutionDataRequestState({ loading: false, envelope, error: null });
        const listEnvelope = await listInstitutionDataRequests(
          selectedInstitutionOrganizationId,
          protectedOptions,
        );
        setInstitutionDataRequestsListState({
          loading: false,
          envelope: listEnvelope,
          error: null,
        });
      } catch (error) {
        setInstitutionDataRequestState({
          loading: false,
          envelope: null,
          error: error instanceof Error ? error.message : "Failed to create data request",
        });
      }
    })();
  }

  async function refreshPartnerImports() {
    if (!selectedInstitutionOrganizationId) return;
    const listEnvelope = await listPartnerImports(
      selectedInstitutionOrganizationId,
      protectedOptions,
    );
    setPartnerImportListState({ loading: false, envelope: listEnvelope, error: null });
  }

  function handlePartnerImportCreate(request: PartnerImportCreateRequest) {
    void (async () => {
      if (!selectedInstitutionOrganizationId) {
        setPartnerImportCreateState({
          loading: false,
          envelope: null,
          error: "Select an institutional organization before uploading partner data.",
        });
        return;
      }
      setPartnerImportCreateState((current) => ({ ...current, loading: true, error: null }));
      try {
        const envelope = await createPartnerImport(request, protectedOptions);
        setPartnerImportCreateState({ loading: false, envelope, error: null });
        await refreshPartnerImports();
      } catch (error) {
        setPartnerImportCreateState({
          loading: false,
          envelope: null,
          error: error instanceof Error ? error.message : "Failed to upload partner import",
        });
      }
    })();
  }

  function handlePartnerImportValidate(importBatchId: string) {
    void (async () => {
      setPartnerImportActionState((current) => ({ ...current, loading: true, error: null }));
      try {
        const envelope = await validatePartnerImport(importBatchId, protectedOptions);
        setPartnerImportActionState({ loading: false, envelope, error: null });
        await refreshPartnerImports();
      } catch (error) {
        setPartnerImportActionState({
          loading: false,
          envelope: null,
          error: error instanceof Error ? error.message : "Failed to validate partner import",
        });
      }
    })();
  }

  function handlePartnerImportAccept(importBatchId: string) {
    void (async () => {
      setPartnerImportActionState((current) => ({ ...current, loading: true, error: null }));
      try {
        const envelope = await acceptPartnerImport(
          importBatchId,
          { reason: "Accepted as partner-contributed evidence." },
          protectedOptions,
        );
        setPartnerImportActionState({ loading: false, envelope, error: null });
        await refreshPartnerImports();
      } catch (error) {
        setPartnerImportActionState({
          loading: false,
          envelope: null,
          error: error instanceof Error ? error.message : "Failed to accept partner import",
        });
      }
    })();
  }

  function handlePartnerImportReject(importBatchId: string) {
    void (async () => {
      setPartnerImportActionState((current) => ({ ...current, loading: true, error: null }));
      try {
        const envelope = await rejectPartnerImport(
          importBatchId,
          { reason: "Rejected during import governance review." },
          protectedOptions,
        );
        setPartnerImportActionState({ loading: false, envelope, error: null });
        await refreshPartnerImports();
      } catch (error) {
        setPartnerImportActionState({
          loading: false,
          envelope: null,
          error: error instanceof Error ? error.message : "Failed to reject partner import",
        });
      }
    })();
  }

  function handlePartnerImportArchive(importBatchId: string) {
    void (async () => {
      setPartnerImportActionState((current) => ({ ...current, loading: true, error: null }));
      try {
        const envelope = await archivePartnerImport(
          importBatchId,
          { reason: "Archived from import center." },
          protectedOptions,
        );
        setPartnerImportActionState({ loading: false, envelope, error: null });
        await refreshPartnerImports();
      } catch (error) {
        setPartnerImportActionState({
          loading: false,
          envelope: null,
          error: error instanceof Error ? error.message : "Failed to archive partner import",
        });
      }
    })();
  }

  function handlePartnerImportReceipt(importBatchId: string) {
    void (async () => {
      setPartnerImportReceiptState((current) => ({ ...current, loading: true, error: null }));
      try {
        const envelope = await getPartnerImportReceipt(importBatchId, protectedOptions);
        setPartnerImportReceiptState({ loading: false, envelope, error: null });
      } catch (error) {
        setPartnerImportReceiptState({
          loading: false,
          envelope: null,
          error: error instanceof Error ? error.message : "Failed to load import receipt",
        });
      }
    })();
  }

  async function refreshApiClients() {
    setApiClientListState((current) => ({ ...current, loading: true, error: null }));
    try {
      const envelope = await listApiClients(protectedOptions);
      setApiClientListState({ loading: false, envelope, error: null });
    } catch (error) {
      setApiClientListState({
        loading: false,
        envelope: null,
        error: error instanceof Error ? error.message : "Failed to load API clients",
      });
    }
  }

  function handleCreateApiClient(request: ApiClientCreateRequest) {
    void (async () => {
      setApiClientCreateState((current) => ({ ...current, loading: true, error: null }));
      try {
        const envelope = await createApiClient(request, protectedOptions);
        setApiClientCreateState({ loading: false, envelope, error: null });
        await refreshApiClients();
      } catch (error) {
        setApiClientCreateState({
          loading: false,
          envelope: null,
          error: error instanceof Error ? error.message : "Failed to create API client",
        });
      }
    })();
  }

  function handleCreateApiKey(apiClientId: string) {
    void (async () => {
      setApiKeyCreateState((current) => ({ ...current, loading: true, error: null }));
      try {
        const envelope = await createApiKey(apiClientId, protectedOptions);
        setApiKeyCreateState({ loading: false, envelope, error: null });
        await refreshApiClients();
      } catch (error) {
        setApiKeyCreateState({
          loading: false,
          envelope: null,
          error: error instanceof Error ? error.message : "Failed to create API key",
        });
      }
    })();
  }

  function handleRevokeApiKey(apiKeyId: string) {
    void (async () => {
      setApiKeyCreateState((current) => ({ ...current, loading: true, error: null }));
      try {
        const envelope = await revokeApiKey(apiKeyId, protectedOptions);
        setApiKeyCreateState({ loading: false, envelope, error: null });
        await refreshApiClients();
      } catch (error) {
        setApiKeyCreateState({
          loading: false,
          envelope: null,
          error: error instanceof Error ? error.message : "Failed to revoke API key",
        });
      }
    })();
  }

  function handleLoadApiUsage(apiClientId: string) {
    void (async () => {
      setApiUsageState((current) => ({ ...current, loading: true, error: null }));
      try {
        const envelope = await listApiUsage(apiClientId, protectedOptions);
        setApiUsageState({ loading: false, envelope, error: null });
      } catch (error) {
        setApiUsageState({
          loading: false,
          envelope: null,
          error: error instanceof Error ? error.message : "Failed to load API usage",
        });
      }
    })();
  }

  function handleRefreshCareerPlatforms() {
    void (async () => {
      setCareerPlatformRegistryState((current) => ({ ...current, loading: true, error: null }));
      try {
        const envelope = await getCareerPlatformRegistry(protectedOptions);
        setCareerPlatformRegistryState({ loading: false, envelope, error: null });
      } catch (error) {
        setCareerPlatformRegistryState({
          loading: false,
          envelope: null,
          error: error instanceof Error ? error.message : "Failed to load career platforms",
        });
      }
    })();
  }

  function handleCreateCareerPlatformExport(request: CareerPlatformExportRequest) {
    void (async () => {
      setCareerPlatformExportState((current) => ({ ...current, loading: true, error: null }));
      setAccountAction({ loading: true, message: null, error: null });
      try {
        const envelope = await createCareerPlatformExport(request, protectedOptions);
        setCareerPlatformExportState({ loading: false, envelope, error: null });
        setAccountAction({
          loading: false,
          message: "Career platform manual export prepared. No scraping, application submission, recruiter outreach, or ATS state was created.",
          error: null,
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to create platform export";
        setCareerPlatformExportState({
          loading: false,
          envelope: null,
          error: message,
        });
        setAccountAction({ loading: false, message: null, error: message });
      }
    })();
  }

  function handleCreateIntegrationExport(request: IntegrationExportCreateRequest) {
    void (async () => {
      if (!canUseIntegrations) {
        setAccountAction({ loading: false, message: "Sign in to create integration exports.", error: null });
        return;
      }
      setAccountAction({ loading: true, message: null, error: null });
      try {
        const envelope = await createIntegrationExport(request, protectedOptions);
        const created = envelope.data?.export;
        const actionLabel = created?.capability === "prepared_payload"
          ? "Prepared manual payload"
          : "Downloadable export";
        setAccountAction({
          loading: false,
          message: created
            ? `${actionLabel} created for ${segmentLabel(created.destination)}. No external write or live sync was performed.`
            : "Integration export created.",
          error: null,
        });
      } catch (error) {
        setAccountAction({
          loading: false,
          message: null,
          error: error instanceof Error ? error.message : "Failed to create integration export",
        });
      }
    })();
  }

  function handleCreateIntegrationReminder(request: IntegrationReminderCreateRequest) {
    void (async () => {
      if (!canUseIntegrations) {
        setAccountAction({ loading: false, message: "Sign in to create calendar reminders.", error: null });
        return;
      }
      setAccountAction({ loading: true, message: null, error: null });
      try {
        const envelope = await createIntegrationReminder(request, protectedOptions);
        const reminder = envelope.data?.reminder;
        setAccountAction({
          loading: false,
          message: reminder
            ? `ICS reminder created for ${segmentLabel(reminder.reminder_type)}. No ATS application status or calendar write was created.`
            : "ICS reminder created.",
          error: null,
        });
      } catch (error) {
        setAccountAction({
          loading: false,
          message: null,
          error: error instanceof Error ? error.message : "Failed to create calendar reminder",
        });
      }
    })();
  }

  function toggleFilterValue(value: string, values: string[]): string[] {
    return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
  }

  async function handleDiscoverySubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const requestKey = discoveryRequestKey.current;
    setDiscoveryState((current) => ({ ...current, loading: true, error: null }));
    try {
      const request = {
        region_ids: discoveryFilters.selectedRegions,
        role_targets: discoveryFilters.roleTargets,
        industry_preferences: discoveryFilters.industries,
        career_stage: discoveryFilters.careerStage,
        prestige_preference: discoveryFilters.prestigePreference,
        brand_preference: discoveryFilters.brandPreference,
        limit: discoveryFilters.limit,
      };
      const envelope = auth.isAuthenticated && !accountDeactivated
        ? await discoverPersonalizedFromCareerIdentity(request, protectedOptions)
        : await discoverPersonalized(request);
      if (requestKey === discoveryRequestKey.current) {
        setDiscoveryState({ loading: false, envelope, error: null });
      }
    } catch (error) {
      if (requestKey === discoveryRequestKey.current) {
        setDiscoveryState({
          loading: false,
          envelope: null,
          error: error instanceof Error ? error.message : "Failed to run personalized discovery",
        });
      }
    }
  }

  async function handleSaveArtifact(input: SavedMarketArtifactInput, successMessage: string) {
    if (!canSavePersonalOverlays) {
      setAccountAction({ loading: false, message: "Sign in to save personal overlays.", error: null });
      return;
    }
    if (savedArtifactRefs.has(savedArtifactKey(input.artifact_type, input.artifact_ref))) {
      setAccountAction({ loading: false, message: "This artifact is already saved for your account.", error: null });
      return;
    }

    setAccountAction({ loading: true, message: null, error: null });
    try {
      await createSavedMarketArtifact(input, protectedOptions);
      await loadAccountData();
      setAccountAction({ loading: false, message: successMessage, error: null });
    } catch (error) {
      setAccountAction({
        loading: false,
        message: null,
        error: error instanceof Error ? error.message : "Failed to save artifact",
      });
    }
  }

  function handleSaveRegion(region: RegionDetail) {
    void handleSaveArtifact(
      {
        artifact_type: "region",
        artifact_ref: region.region_id,
        label: region.display_name,
        snapshot: {
          ref_kind: "canonical_region_id",
          saved_from: "region_detail",
        },
      },
      "Region saved to your watchlist.",
    );
  }

  function handleSaveCompany(company: CompanyDetail) {
    void handleSaveArtifact(
      {
        artifact_type: "company",
        artifact_ref: company.company_id,
        label: company.company_name,
        snapshot: {
          ref_kind: "canonical_company_id",
          saved_from: "company_geography",
        },
      },
      "Company saved to your watchlist.",
    );
  }

  function handleSaveRoleFamily(roleFamily: string) {
    void handleSaveArtifact(
      {
        artifact_type: "role_family",
        artifact_ref: roleFamily,
        label: prettyKey(roleFamily),
        snapshot: {
          ref_kind: "role_family_key",
          saved_from: "region_role_family",
        },
      },
      "Role family saved to your watchlist.",
    );
  }

  function handleSaveComparison(comparison: ComparisonDetail, label: string) {
    void handleSaveArtifact(
      {
        artifact_type: "comparison",
        artifact_ref: comparison.comparison_id ?? comparisonArtifactRef,
        label,
        snapshot: {
          ref_kind: "canonical_comparison_set",
          region_ids: [
            comparison.region_a?.region_id,
            comparison.region_b?.region_id,
          ].filter(Boolean),
          saved_from: "compare_markets",
        },
      },
      "Comparison set saved to your watchlist.",
    );
  }

  function discoveryObjectiveRefs(discovery: PersonalizedResult): Array<Record<string, unknown>> {
    return [
      ...(discovery.ranked_regions ?? []).map((region) => ({
        output_type: "region",
        subject_id: region.region_id,
      })),
      ...(discovery.ranked_companies ?? []).map((company) => ({
        output_type: "company_region",
        company_id: company.company_id,
        region_id: company.region_id,
      })),
    ];
  }

  function handleSaveDiscoveryResult(discovery: PersonalizedResult) {
    void (async () => {
      const refs = discoveryObjectiveRefs(discovery);
      const hash = await sha256Label({ discoveryFilters, refs });
      await handleSaveArtifact(
        {
          artifact_type: "discovery_result",
          artifact_ref: `discovery:${hash.slice(7, 39)}`,
          label: `Discovery result ${formatDateTime(new Date().toISOString())}`,
          snapshot: {
            filters: discoveryFilters,
            objective_output_refs: refs,
            saved_from: "personalized_discovery",
          },
        },
        "Discovery result saved to your account overlays.",
      );
    })();
  }

  function handleSaveRecommendationSnapshot(discovery: PersonalizedResult) {
    void (async () => {
      if (!canSavePersonalOverlays) {
        setAccountAction({ loading: false, message: "Sign in to save recommendation snapshots.", error: null });
        return;
      }
      const refs = discoveryObjectiveRefs(discovery);
      const sourceVersionBundle = discoveryState.envelope?.metadata.source_versions ?? {};
      const recommendationInputsHash = await sha256Label({
        discoveryFilters,
        refs,
        sourceVersionBundle,
      });
      const preferenceProfile = preferenceState.envelope?.data;
      const snapshot: PersonalizedRecommendationSnapshotInput = {
        preference_profile_id: preferenceProfile?.persisted ? preferenceProfile.user_id : null,
        personalized_output: { ...discovery } as Record<string, unknown>,
        recommendation_version: "frontend_discovery_snapshot_v1",
        source_version_bundle: sourceVersionBundle,
        objective_output_refs: refs,
        recommendation_inputs_hash: recommendationInputsHash,
        generated_at: new Date().toISOString(),
      };

      setAccountAction({ loading: true, message: null, error: null });
      try {
        await createRecommendationSnapshot(snapshot, protectedOptions);
        await loadAccountData();
        setAccountAction({ loading: false, message: "Recommendation snapshot saved.", error: null });
      } catch (error) {
        setAccountAction({
          loading: false,
          message: null,
          error: error instanceof Error ? error.message : "Failed to save recommendation snapshot",
        });
      }
    })();
  }

  function handleSavePreferences() {
    void (async () => {
      setAccountAction({ loading: true, message: null, error: null });
      try {
        const envelope = await updatePreferences(preferenceInputFromDraft(preferenceDraft), protectedOptions);
        setPreferenceState({ loading: false, envelope, error: null });
        setPreferenceDraft(preferenceDraftFromProfile(envelope.data));
        setAccountAction({ loading: false, message: "Preferences saved.", error: null });
      } catch (error) {
        setAccountAction({
          loading: false,
          message: null,
          error: error instanceof Error ? error.message : "Failed to save preferences",
        });
      }
    })();
  }

  function handlePreviewScoring() {
    void (async () => {
      if (!canSavePersonalOverlays) {
        setAccountAction({ loading: false, message: "Sign in to preview scoring overlays.", error: null });
        return;
      }
      const preferredRegionIds = splitDraftList(preferenceDraft.preferredRegions);
      const fallbackRegionIds = regionList.slice(0, 2).map((region) => region.region_id);
      const regionIds = preferredRegionIds.length
        ? preferredRegionIds
        : fallbackRegionIds.length
          ? fallbackRegionIds
          : [selectedRegionId].filter(Boolean);

      setScoringPreviewState((current) => ({ ...current, loading: true, error: null }));
      try {
        const envelope = await previewScoringOverlay(
          {
            region_ids: regionIds,
            role_interests: splitDraftList(preferenceDraft.roleInterests),
            industry_interests: splitDraftList(preferenceDraft.industryInterests),
            scoring_weights: normalizeScoringWeights(preferenceDraft.scoringWeights),
          },
          protectedOptions,
        );
        setScoringPreviewState({ loading: false, envelope, error: null });
        setAccountAction({ loading: false, message: "Scoring preview updated.", error: null });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to preview scoring overlay";
        setScoringPreviewState({ loading: false, envelope: null, error: message });
        setAccountAction({ loading: false, message: null, error: message });
      }
    })();
  }

  function handleDeletePreferences() {
    void (async () => {
      setAccountAction({ loading: true, message: null, error: null });
      try {
        await deletePreferences(protectedOptions);
        const envelope = await getPreferences(protectedOptions);
        setPreferenceState({ loading: false, envelope, error: null });
        setPreferenceDraft(preferenceDraftFromProfile(envelope.data));
        setAccountAction({ loading: false, message: "Preferences deleted.", error: null });
      } catch (error) {
        setAccountAction({
          loading: false,
          message: null,
          error: error instanceof Error ? error.message : "Failed to delete preferences",
        });
      }
    })();
  }

  function handleDeleteArtifact(savedArtifactId: string) {
    void (async () => {
      setAccountAction({ loading: true, message: null, error: null });
      try {
        await deleteSavedMarketArtifact(savedArtifactId, protectedOptions);
        await loadAccountData();
        setAccountAction({ loading: false, message: "Saved artifact deleted.", error: null });
      } catch (error) {
        setAccountAction({
          loading: false,
          message: null,
          error: error instanceof Error ? error.message : "Failed to delete saved artifact",
        });
      }
    })();
  }

  function handleMarkAlertRead(userAlertId: string) {
    void (async () => {
      setAccountAction({ loading: true, message: null, error: null });
      try {
        await markAlertRead(userAlertId, protectedOptions);
        const envelope = await listAlerts(protectedOptions);
        setAlertsState({ loading: false, envelope, error: null });
        setAccountAction({ loading: false, message: "Alert marked read.", error: null });
      } catch (error) {
        setAccountAction({
          loading: false,
          message: null,
          error: error instanceof Error ? error.message : "Failed to mark alert read",
        });
      }
    })();
  }

  function handleDismissAlert(userAlertId: string) {
    void (async () => {
      setAccountAction({ loading: true, message: null, error: null });
      try {
        await dismissAlert(userAlertId, protectedOptions);
        const envelope = await listAlerts(protectedOptions);
        setAlertsState({ loading: false, envelope, error: null });
        setAccountAction({ loading: false, message: "Alert dismissed.", error: null });
      } catch (error) {
        setAccountAction({
          loading: false,
          message: null,
          error: error instanceof Error ? error.message : "Failed to dismiss alert",
        });
      }
    })();
  }

  function runExplanation(
    key: string,
    request: { evidence: ExplanationEvidencePacket },
    endpoint: (
      body: { evidence: ExplanationEvidencePacket },
      authOptions: ProtectedRequestOptions,
    ) => Promise<ApiEnvelope<ExplanationResult>>,
  ) {
    void (async () => {
      if (!canExplainGuidance) {
        setAccountAction({ loading: false, message: "Sign in to render structured guidance.", error: null });
        return;
      }
      setExplanationStates((current) => ({
        ...current,
        [key]: { loading: true, envelope: current[key]?.envelope ?? null, error: null },
      }));
      try {
        const envelope = await endpoint(request, protectedOptions);
        setExplanationStates((current) => ({
          ...current,
          [key]: { loading: false, envelope, error: null },
        }));
        setAccountAction({ loading: false, message: "Structured guidance rendered.", error: null });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to render structured guidance";
        setExplanationStates((current) => ({
          ...current,
          [key]: { loading: false, envelope: null, error: message },
        }));
        setAccountAction({ loading: false, message: null, error: message });
      }
    })();
  }

  function handleExplainRegion(region: RegionDetail) {
    runExplanation(
      `region:${region.region_id}`,
      {
        evidence: regionExplanationEvidence(
          region,
          selectedRegionState.envelope,
          selectedRegionSourceState.envelope?.data ?? null,
        ),
      },
      explainRegion,
    );
  }

  function handleExplainCompany(company: CompanyDetail) {
    runExplanation(
      `company:${company.company_id}`,
      {
        evidence: companyExplanationEvidence(
          company,
          companyState.envelope,
          selectedCompanySourceState.envelope?.data ?? null,
        ),
      },
      explainCompany,
    );
  }

  function handleExplainComparison(comparison: ComparisonDetail) {
    runExplanation(
      `comparison:${comparison.comparison_id ?? comparisonArtifactRef}`,
      {
        evidence: comparisonExplanationEvidence(
          comparison,
          comparisonState.envelope,
          regionSourceStates[comparisonA]?.envelope?.data ?? null,
          regionSourceStates[comparisonB]?.envelope?.data ?? null,
        ),
      },
      explainComparison,
    );
  }

  function handleExplainAlert(alert: UserAlert) {
    runExplanation(
      `alert:${alert.user_alert_id}`,
      { evidence: alertExplanationEvidence(alert) },
      explainAlert,
    );
  }

  function handleExportUserData() {
    void (async () => {
      setExportState((current) => ({ ...current, loading: true, error: null }));
      setAccountAction({ loading: true, message: null, error: null });
      try {
        const envelope = await exportUserData(protectedOptions);
        setExportState({ loading: false, envelope, error: null });
        setAccountAction({ loading: false, message: "User-owned data export loaded.", error: null });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to export user data";
        setExportState({ loading: false, envelope: null, error: message });
        setAccountAction({ loading: false, message: null, error: message });
      }
    })();
  }

  function handleDeactivateAccount() {
    void (async () => {
      if (!deactivateConfirmed) return;
      setAccountAction({ loading: true, message: null, error: null });
      try {
        const envelope = await deactivateAccount(protectedOptions);
        setDeactivationResult(envelope.data);
        setAccountDeactivated(true);
        setCurrentUserState(emptyLoadState());
        setPreferenceState(emptyLoadState());
        setPreferenceDraft(emptyPreferenceDraft());
        setArtifactsState(emptyLoadState());
        setAlertsState(emptyLoadState());
        setSnapshotsState(emptyLoadState());
        setScoringPreviewState(emptyLoadState());
        setExplanationStates({});
        setExportState(emptyLoadState());
        setMonetizationMeState(emptyLoadState());
        setMonetizationEntitlementsState(emptyLoadState());
        setMonetizationUsageState(emptyLoadState());
        setInstitutionOrganizationsState(emptyLoadState());
        setInstitutionDashboardState(emptyLoadState());
        setInstitutionAdvisorState(emptyLoadState());
        setInstitutionReportState(emptyLoadState());
        setInstitutionReportsListState(emptyLoadState());
        setInstitutionDataRequestState(emptyLoadState());
        setInstitutionDataRequestsListState(emptyLoadState());
        setPartnerImportCreateState(emptyLoadState());
        setPartnerImportListState(emptyLoadState());
        setPartnerImportActionState(emptyLoadState());
        setPartnerImportReceiptState(emptyLoadState());
        setApiClientCreateState(emptyLoadState());
        setApiClientListState(emptyLoadState());
        setApiKeyCreateState(emptyLoadState());
        setApiUsageState(emptyLoadState());
        setCareerPlatformRegistryState(emptyLoadState());
        setCareerPlatformExportState(emptyLoadState());
        setDeactivateConfirmed(false);
        setAccountAction({
          loading: false,
          message: "App account deactivated. Auth0 provider account deletion is not performed here.",
          error: null,
        });
      } catch (error) {
        setAccountAction({
          loading: false,
          message: null,
          error: error instanceof Error ? error.message : "Failed to deactivate account",
        });
      }
    })();
  }

  if (!isProductRoute) {
    return (
      <PublicRouteView
        onNavigate={handleRouteLink}
        publicBenchmarkDetailState={selectedPublicBenchmarkDetailState}
        publicBenchmarkListState={publicBenchmarkListState}
        publicReportDetailState={selectedPublicReportDetailState}
        publicReportListState={publicReportListState}
        predictiveReportState={predictiveReportState}
        route={route}
      />
    );
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <aside className="sidebar">
        <div className="brand-block">
          <span className="brand-mark">JM</span>
          <div>
            <strong>Job Market Intelligence</strong>
            <small>MVP demo</small>
          </div>
        </div>
        <nav className="nav-list" aria-label="Main navigation">
          {visibleNavItems.map((item) => {
            const url = getNavigationUrl(
              item.id,
              selectedRegionRouteToken,
              selectedCompanyId,
              comparisonA,
              comparisonB,
              discoveryFilters,
            );
            return (
              <a
                className={route.page === item.id ? "nav-item nav-item-active" : "nav-item"}
                href={url}
                key={item.id}
                onClick={(event) => handleRouteLink(event, url)}
              >
                <span>{item.label}</span>
                <small>{item.kicker}</small>
              </a>
            );
          })}
        </nav>
        <AuthStatusPanel auth={auth} onOpenAccount={() => navigateTo(accountUrl())} />
        <PublicInfoLinks activePage={null} onNavigate={handleRouteLink} variant="sidebar" />
        <div className="api-target">
          <span>API target</span>
          <code>{API_TARGET_LABEL}</code>
        </div>
      </aside>

      <main className="content-shell" id="main-content">
        <header className="topbar">
          <div>
            <p className="eyebrow">Prepared market truth · derived outputs · personal overlays</p>
            <h1>Job Market Intelligence</h1>
            {route.unknownPath ? <p className="meta-copy">Unknown path redirected to Explore Markets.</p> : null}
          </div>
          <div className="topbar-badges">
            <StateBadge envelope={health.envelope} loading={health.loading} error={health.error} />
            <span className="badge">{regionList.length} regions</span>
            <span className="badge">{companyOptions.length} companies</span>
          </div>
        </header>

        <DemoDisclosure compact />

        {route.page !== "account" && accountAction.message ? (
          <div className="notice-state">
            <strong>Integration update</strong>
            <p>{accountAction.message}</p>
          </div>
        ) : null}
        {route.page !== "account" && accountAction.error ? (
          <ErrorState message={accountAction.error} />
        ) : null}

        <LazyRoute>
        {route.page === "explore" ? (
          <ExploreMarkets
            health={health}
            marketCoverage={marketCoverageState}
            marketOperations={marketOperationsState}
            onOpenCompare={() => navigateTo(compareMarketsUrl(comparisonA, comparisonB))}
            onOpenRegionDetail={() => navigateTo(regionDetailUrl(selectedRegionRouteToken))}
            onSelectRegion={selectRegion}
            regionDetails={regionDetails}
            regionSearch={regionSearchState}
            regions={regions}
          />
        ) : null}

        {route.page === "dashboard" ? (
          <UserIntelligenceDashboardPage />
        ) : null}

        {route.page === "intelligence" ? (
          <MarketIntelligencePage
            onNavigate={navigateTo}
            state={route.intelligence}
          />
        ) : null}

        {route.page === "region" ? (
          <RegionExplorer
            canExplainGuidance={canExplainGuidance}
            canSavePersonalOverlays={canSavePersonalOverlays}
            canUseIntegrations={canUseIntegrations}
            explanationState={explanationStates[`region:${selectedRegionId}`]}
            onCreateIntegrationExport={handleCreateIntegrationExport}
            onCreateIntegrationReminder={handleCreateIntegrationReminder}
            onExplainRegion={handleExplainRegion}
            onCompareRegion={compareRegion}
            onRemoveSavedArtifact={handleDeleteArtifact}
            onSaveRegion={handleSaveRegion}
            onSaveRoleFamily={handleSaveRoleFamily}
            onSelectCompany={selectCompany}
            onSelectRegion={selectRegion}
            roleFamilyState={selectedRegionRoleFamilyState}
            regionState={selectedRegionState}
            regions={regionList}
            savedArtifactsByKey={savedArtifactByKey}
            selectedRegionId={selectedRegionId}
            sourceState={selectedRegionSourceState}
          />
        ) : null}

        {route.page === "company" ? (
          <CompanyExplorer
            canExplainGuidance={canExplainGuidance}
            canSavePersonalOverlays={canSavePersonalOverlays}
            canUseIntegrations={canUseIntegrations}
            companyOptions={companyOptions}
            companyState={companyState}
            explanationState={explanationStates[`company:${selectedCompanyId}`]}
            geographyState={selectedCompanyGeographyState}
            onCreateCareerPlatformExport={handleCreateCareerPlatformExport}
            onCreateIntegrationExport={handleCreateIntegrationExport}
            onCreateIntegrationReminder={handleCreateIntegrationReminder}
            onExplainCompany={handleExplainCompany}
            onRemoveSavedArtifact={handleDeleteArtifact}
            onSaveCompany={handleSaveCompany}
            onSelectCompany={selectCompany}
            savedCompanyArtifact={savedArtifactByKey.get(savedArtifactKey("company", selectedCompanyId))}
            selectedCompanyId={selectedCompanyId}
            sourceState={selectedCompanySourceState}
          />
        ) : null}

        {route.page === "compare" ? (
          <ComparisonView
            canExplainGuidance={canExplainGuidance}
            canSavePersonalOverlays={canSavePersonalOverlays}
            canUseIntegrations={canUseIntegrations}
            comparisonState={comparisonState}
            explanationState={explanationStates[`comparison:${comparisonArtifactRef}`]}
            onCreateIntegrationExport={handleCreateIntegrationExport}
            onCreateIntegrationReminder={handleCreateIntegrationReminder}
            onExplainComparison={handleExplainComparison}
            savedComparisonArtifact={savedArtifactByKey.get(savedArtifactKey("comparison", comparisonArtifactRef))}
            onRemoveSavedArtifact={handleDeleteArtifact}
            onRegionA={selectComparisonA}
            onRegionB={selectComparisonB}
            onSaveComparison={handleSaveComparison}
            regionA={comparisonA}
            regionB={comparisonB}
            regions={regionList}
            sourceAState={regionSourceStates[comparisonA] ?? emptyLoadState<SourceExplanation>()}
            sourceBState={regionSourceStates[comparisonB] ?? emptyLoadState<SourceExplanation>()}
            validationError={comparisonValidationError}
          />
        ) : null}

        {route.page === "discovery" ? (
          <PersonalizedDiscovery
            brandPreference={discoveryFilters.brandPreference}
            canSavePersonalOverlays={canSavePersonalOverlays}
            careerStage={discoveryFilters.careerStage}
            discoveryState={discoveryState}
            industries={discoveryFilters.industries}
            limit={discoveryFilters.limit}
            onBrandPreference={(brandPreference) =>
              updateDiscoveryFilters({ ...discoveryFilters, brandPreference })
            }
            onCareerStage={(careerStage) =>
              updateDiscoveryFilters({ ...discoveryFilters, careerStage })
            }
            onLimit={(nextLimit) =>
              updateDiscoveryFilters({
                ...discoveryFilters,
                limit: Math.max(1, Math.min(25, nextLimit || 1)),
              })
            }
            onPrestigePreference={(prestigePreference) =>
              updateDiscoveryFilters({ ...discoveryFilters, prestigePreference })
            }
            onSaveDiscoveryResult={handleSaveDiscoveryResult}
            onSaveRecommendationSnapshot={handleSaveRecommendationSnapshot}
            onSubmit={handleDiscoverySubmit}
            onToggleIndustry={(industry) =>
              updateDiscoveryFilters({
                ...discoveryFilters,
                industries: toggleFilterValue(industry, discoveryFilters.industries),
              })
            }
            onToggleRegion={(regionId) =>
              updateDiscoveryFilters({
                ...discoveryFilters,
                selectedRegions: toggleFilterValue(regionId, discoveryFilters.selectedRegions),
              })
            }
            onToggleRole={(role) =>
              updateDiscoveryFilters({
                ...discoveryFilters,
                roleTargets: toggleFilterValue(role, discoveryFilters.roleTargets),
              })
            }
            prestigePreference={discoveryFilters.prestigePreference}
            regions={regionList}
            roleTargets={discoveryFilters.roleTargets}
            selectedRegions={discoveryFilters.selectedRegions}
            sourceStates={regionSourceStates}
          />
        ) : null}

        {route.page === "career-identity" ? (
          <CareerIdentityPage
            auth={auth}
            defaultRegionIds={regionList.map((region) => region.region_id)}
          />
        ) : null}

        {route.page === "decisions" ? (
          <DecisionWorkspacePage
            auth={auth}
            onOpenCareerIdentity={() => navigateTo(careerIdentityUrl())}
          />
        ) : null}

        {route.page === "recommendations" ? (
          <RecommendationsView
            accessPreviewStates={monetizationAccessPreviewStates}
            canUseIntegrations={canUseIntegrations}
            goalModesState={recommendationGoalModesState}
            monetizationPlansState={monetizationPlansState}
            onCreateIntegrationExport={handleCreateIntegrationExport}
            onCreateIntegrationReminder={handleCreateIntegrationReminder}
            onSelectGoalMode={updateRecommendationGoalMode}
            selectedGoalMode={selectedRecommendationGoalMode}
            strategyState={recommendationStrategyState}
          />
        ) : null}

        {route.page === "career-agent" ? (
          <CareerAgentPage
            authenticated={auth.isAuthenticated && !accountDeactivated}
            protectedOptions={
              auth.isAuthenticated && !accountDeactivated ? protectedOptions : undefined
            }
          />
        ) : null}

        {route.page === "opportunity-routes" ? (
          <OpportunityRoutesPage />
        ) : null}

        {route.page === "current-opportunities" ? (
          <CurrentOpportunitiesPage
            auth={auth}
            onNavigate={navigateTo}
            opportunityId={route.opportunityId}
          />
        ) : null}

        {route.page === "current-opportunity-operations" ? (
          <CurrentOpportunitiesPage
            auth={auth}
            operations
            onNavigate={navigateTo}
          />
        ) : null}

        {route.page === "policy" ? (
          <PolicyIntelligencePage
            onNavigate={handleRouteLink}
            policyView={route.policyView ?? "landing"}
            regionId={route.regionId ?? selectedRegionId}
            regions={regionList}
          />
        ) : null}

        {route.page === "plans" ? (
          <MonetizationView
            accessPreviewStates={monetizationAccessPreviewStates}
            authenticated={auth.isAuthenticated && !accountDeactivated}
            billingAction={billingAction}
            billingStatusState={billingStatusState}
            featuresState={monetizationFeaturesState}
            monetizationEntitlementsState={monetizationEntitlementsState}
            monetizationMeState={monetizationMeState}
            monetizationUsageState={monetizationUsageState}
            onManageBilling={handleManageBilling}
            onStartCheckout={handleStartCheckout}
            plansState={monetizationPlansState}
            reportsState={monetizationReportsState}
          />
        ) : null}

        {route.page === "institution" && route.institutionView === "advisor" ? (
          <InstitutionAdvisorWorkspace
            advisorState={institutionAdvisorState}
            auth={auth}
            organizationsState={institutionOrganizationsState}
            onLogin={() => void auth.login()}
            onOpenDashboard={() =>
              navigateTo(institutionDashboardUrl(selectedInstitutionOrganizationId))
            }
            onOpenImports={() =>
              navigateTo(institutionImportsUrl(selectedInstitutionOrganizationId))
            }
            onOpenReports={() =>
              navigateTo(institutionReportsUrl(selectedInstitutionOrganizationId))
            }
            onSelectOrganization={(organizationId) =>
              navigateTo(institutionAdvisorUrl(organizationId))
            }
            onSubmit={handleInstitutionAdvisorSubmit}
            selectedOrganizationId={selectedInstitutionOrganizationId}
          />
        ) : null}

        {route.page === "institution" && route.institutionView === "decisions" ? (
          <InstitutionDecisionInfrastructureView
            auth={auth}
            benchmarkState={institutionBenchmarkState}
            curriculumState={institutionCurriculumState}
            decisionDashboardState={institutionDecisionDashboardState}
            organizationsState={institutionOrganizationsState}
            workforceReportState={institutionWorkforceReportState}
            onLogin={() => void auth.login()}
            onOpenDashboard={() =>
              navigateTo(institutionDashboardUrl(selectedInstitutionOrganizationId))
            }
            onOpenReports={() =>
              navigateTo(institutionReportsUrl(selectedInstitutionOrganizationId))
            }
            onSelectOrganization={(organizationId) =>
              navigateTo(institutionDecisionsUrl(organizationId))
            }
            selectedOrganizationId={selectedInstitutionOrganizationId}
          />
        ) : null}

        {route.page === "institution" && route.institutionView === "reports" ? (
          <InstitutionReportsView
            auth={auth}
            organizationsState={institutionOrganizationsState}
            onCreateIntegrationExport={handleCreateIntegrationExport}
            onCreateIntegrationReminder={handleCreateIntegrationReminder}
            onGenerate={handleInstitutionReportGenerate}
            onLogin={() => void auth.login()}
            onOpenDashboard={() =>
              navigateTo(institutionDashboardUrl(selectedInstitutionOrganizationId))
            }
            onOpenDataRequests={() =>
              navigateTo(institutionDataRequestsUrl(selectedInstitutionOrganizationId))
            }
            onOpenImports={() =>
              navigateTo(institutionImportsUrl(selectedInstitutionOrganizationId))
            }
            onSelectOrganization={(organizationId) =>
              navigateTo(institutionReportsUrl(organizationId))
            }
            reportListState={institutionReportsListState}
            reportState={institutionReportState}
            selectedOrganizationId={selectedInstitutionOrganizationId}
          />
        ) : null}

        {route.page === "institution" && route.institutionView === "data-requests" ? (
          <InstitutionDataRequestsView
            auth={auth}
            createState={institutionDataRequestState}
            listState={institutionDataRequestsListState}
            organizationsState={institutionOrganizationsState}
            onCreateIntegrationReminder={handleCreateIntegrationReminder}
            onLogin={() => void auth.login()}
            onOpenDashboard={() =>
              navigateTo(institutionDashboardUrl(selectedInstitutionOrganizationId))
            }
            onOpenImports={() =>
              navigateTo(institutionImportsUrl(selectedInstitutionOrganizationId))
            }
            onOpenReports={() =>
              navigateTo(institutionReportsUrl(selectedInstitutionOrganizationId))
            }
            onSelectOrganization={(organizationId) =>
              navigateTo(institutionDataRequestsUrl(organizationId))
            }
            onSubmit={handleInstitutionDataRequestSubmit}
            selectedOrganizationId={selectedInstitutionOrganizationId}
          />
        ) : null}

        {route.page === "institution" && route.institutionView === "imports" ? (
          <InstitutionPartnerImportsView
            actionState={partnerImportActionState}
            auth={auth}
            createState={partnerImportCreateState}
            listState={partnerImportListState}
            organizationsState={institutionOrganizationsState}
            receiptState={partnerImportReceiptState}
            onAccept={handlePartnerImportAccept}
            onArchive={handlePartnerImportArchive}
            onLogin={() => void auth.login()}
            onOpenDashboard={() =>
              navigateTo(institutionDashboardUrl(selectedInstitutionOrganizationId))
            }
            onOpenDataRequests={() =>
              navigateTo(institutionDataRequestsUrl(selectedInstitutionOrganizationId))
            }
            onOpenReports={() =>
              navigateTo(institutionReportsUrl(selectedInstitutionOrganizationId))
            }
            onReject={handlePartnerImportReject}
            onSelectOrganization={(organizationId) =>
              navigateTo(institutionImportsUrl(organizationId))
            }
            onSubmit={handlePartnerImportCreate}
            onValidate={handlePartnerImportValidate}
            onViewReceipt={handlePartnerImportReceipt}
            selectedOrganizationId={selectedInstitutionOrganizationId}
          />
        ) : null}

        {route.page === "institution" && (!route.institutionView || route.institutionView === "dashboard") ? (
          <InstitutionDashboardView
            auth={auth}
            dashboardState={institutionDashboardState}
            organizationsState={institutionOrganizationsState}
            onCreateIntegrationExport={handleCreateIntegrationExport}
            onCreateIntegrationReminder={handleCreateIntegrationReminder}
            onLogin={() => void auth.login()}
            onOpenAdvisor={() =>
              navigateTo(institutionAdvisorUrl(selectedInstitutionOrganizationId))
            }
            onOpenDecisions={() =>
              navigateTo(institutionDecisionsUrl(selectedInstitutionOrganizationId))
            }
            onOpenImports={() =>
              navigateTo(institutionImportsUrl(selectedInstitutionOrganizationId))
            }
            onOpenReports={() =>
              navigateTo(institutionReportsUrl(selectedInstitutionOrganizationId))
            }
            onSelectOrganization={(organizationId) =>
              navigateTo(institutionDashboardUrl(organizationId))
            }
            selectedOrganizationId={selectedInstitutionOrganizationId}
          />
        ) : null}

        {route.page === "account" ? (
          <AccountView
            actionState={accountAction}
            alertExplanationStates={Object.fromEntries(
              Object.entries(explanationStates)
                .filter(([key]) => key.startsWith("alert:"))
                .map(([key, value]) => [key.slice("alert:".length), value]),
            )}
            alertsState={alertsState}
            apiClientCreateState={apiClientCreateState}
            apiClientListState={apiClientListState}
            apiKeyCreateState={apiKeyCreateState}
            apiUsageState={apiUsageState}
            artifactsState={artifactsState}
            auth={auth}
            careerPlatformExportState={careerPlatformExportState}
            careerPlatformRegistryState={careerPlatformRegistryState}
            currentUserState={currentUserState}
            deactivateConfirmed={deactivateConfirmed}
            deactivationResult={deactivationResult}
            exportState={exportState}
            onDeactivate={handleDeactivateAccount}
            onDeactivateConfirmed={setDeactivateConfirmed}
            onCreateApiClient={handleCreateApiClient}
            onCreateApiKey={handleCreateApiKey}
            onCreateCareerPlatformExport={handleCreateCareerPlatformExport}
            onDeleteArtifact={handleDeleteArtifact}
            onDeletePreferences={handleDeletePreferences}
            onDismissAlert={handleDismissAlert}
            onExplainAlert={handleExplainAlert}
            onExport={handleExportUserData}
            onLoadApiUsage={handleLoadApiUsage}
            onLogin={() => void auth.login()}
            onMarkAlertRead={handleMarkAlertRead}
            onPreferenceDraft={setPreferenceDraft}
            onPreviewScoring={handlePreviewScoring}
            onRefreshApiClients={() => void refreshApiClients()}
            onRefreshCareerPlatforms={handleRefreshCareerPlatforms}
            onRefresh={() => void loadAccountData()}
            onRevokeApiKey={handleRevokeApiKey}
            onSavePreferences={handleSavePreferences}
            preferenceDraft={preferenceDraft}
            preferenceState={preferenceState}
            scoringPreviewState={scoringPreviewState}
            snapshotsState={snapshotsState}
          />
        ) : null}
        </LazyRoute>

        <PublicFooter activePage={null} onNavigate={handleRouteLink} />
      </main>
    </div>
  );
}

export default App;
