import type {
  ApiEnvelope,
  AccountDeactivationResult,
  ApiClientCreatePayload,
  ApiClientCreateRequest,
  ApiClientListPayload,
  ApiClientUpdateRequest,
  ApiKeyCreatePayload,
  ApiUsageListPayload,
  BillingCheckoutSessionPayload,
  BillingPortalSessionPayload,
  BillingStatusPayload,
  CompanyDetail,
  CompanyGeographyResponse,
  CompanySearchResponse,
  ComparisonDetail,
  DataQualityCertificationResult,
  DataQualityLabelListPayload,
  DataStandardDefinitionListPayload,
  CareerPlatformExportPayload,
  CareerPlatformExportRequest,
  CareerPlatformReferenceCreateRequest,
  CareerPlatformReferenceListPayload,
  CareerPlatformReferencePayload,
  CareerPlatformRegistryPayload,
  CurrentUserProfile,
  GovernanceFrameworkPayload,
  ExplanationRequest,
  ExplanationResult,
  FreshnessStatus,
  InstitutionAdvisorComparisonType,
  InstitutionAdvisorRequest,
  InstitutionAdvisorToolResponse,
  InstitutionBenchmarkPayload,
  InstitutionCurrentOrganizationsPayload,
  InstitutionDecisionDashboardPayload,
  InstitutionDataRequestCreatePayload,
  InstitutionDataRequestCreateRequest,
  InstitutionDataRequestListPayload,
  InstitutionDashboardPayload,
  InstitutionWorkforceReportPayload,
  InstitutionWorkforceReportType,
  CurriculumMarketMappingPayload,
  IntegrationExportCreatePayload,
  IntegrationExportCreateRequest,
  IntegrationReminderCreatePayload,
  IntegrationReminderCreateRequest,
  InstitutionReportCreateRequest,
  InstitutionReportGeneratePayload,
  InstitutionReportListPayload,
  ImportedCoverageGapReport,
  ImportedDatasetHealthReport,
  ImportedDiffPreview,
  ImportedFactHealthReport,
  ImportedMarketHealthOverviewPayload,
  ImportedMarketOperationDetails,
  ImportedMarketOperationsViewPayload,
  ImportedRankingExclusionReport,
  ImportedRefreshReadinessReport,
  ImportedSourceAgingReport,
  MarketComparisonReport,
  MarketIntelligenceGoal,
  MarketIntelligenceProfile,
  MarketCoverageListPayload,
  PlatformMarketIntelligencePayload,
  EconomicDevelopmentProfile,
  EducationWorkforceAlignmentProfile,
  MonetizationAccessPreviewPayload,
  MonetizationFeatureKey,
  MonetizationFeaturesPayload,
  MonetizationEntitlementsPayload,
  MonetizationMePayload,
  MonetizationPlanKey,
  MonetizationPlansPayload,
  MonetizationReportExportPayload,
  MonetizationReportGenerationPayload,
  MonetizationReportProductKey,
  MonetizationReportsPayload,
  MonetizationUsagePayload,
  PartnerRegistryPayload,
  PartnerSubmissionSchemaPayload,
  PartnerImportActionRequest,
  PartnerImportCreatePayload,
  PartnerImportCreateRequest,
  PartnerImportListPayload,
  PartnerImportReceiptPayload,
  PersonalizedRecommendationSnapshot,
  PersonalizedRecommendationSnapshotInput,
  PersonalizedRequest,
  PersonalizedResult,
  PlatformEmbedAccessPayload,
  PredictiveReportPayload,
  PublicBenchmark,
  PublicBenchmarkListPayload,
  PublicReport,
  PublicReportListPayload,
  PeerComparisonProfile,
  WorkforceDashboardPayload,
  RecommendationGoalModesPayload,
  RecommendationSnapshotList,
  RecommendationStrategyPayload,
  RecommendationStrategyRequest,
  RegionDetail,
  RegionListItem,
  RegionSearchResponse,
  SavedMarketArtifact,
  SavedMarketArtifactInput,
  SavedMarketArtifactList,
  ScoringPreviewRequest,
  ScoringPreviewResult,
  SourceExplanation,
  TrustExplanation,
  UserReportCreateRequest,
  UserReportSubmissionResult,
  UserAlert,
  UserAlertList,
  UserDataExport,
  UserIntelligenceDashboardPayload,
  UserPreferenceProfile,
  UserPreferenceProfileInput,
  WarningItem,
} from "./types";
import type {
  OpportunityRouteRequest as TypedOpportunityRouteRequest,
  OpportunityRouteResponse as TypedOpportunityRouteResponse,
} from "./opportunityTypes";
import type {
  CareerActionPlan,
  CareerActionPlanRequest,
  CareerAgentAnswer,
  CareerAgentRequest as TypedCareerAgentRequest,
  CareerAgentToolApproval,
  CareerAgentToolExecution,
  CareerAgentToolList,
  CareerAgentToolPreview,
  CareerAgentToolRequest,
  CareerMemoryDeleteRequest,
  CareerMemoryProfile,
  CareerMemoryUpdateRequest,
} from "./careerAgentTypes";
import { isFreshnessStatus, isRecord } from "./dataQuality";
import { reportFrontendError } from "./errorMonitoring";

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "");

export const API_BASE_URL = configuredBaseUrl ?? "";
export const API_TARGET_LABEL =
  configuredBaseUrl ?? "Vite dev proxy -> http://127.0.0.1:8000";

export class ApiError extends Error {
  envelope?: ApiEnvelope<unknown>;
  requestId?: string;
  statusCode?: number;

  constructor(
    message: string,
    options?: { envelope?: ApiEnvelope<unknown>; requestId?: string; statusCode?: number },
  ) {
    super(message);
    this.name = "ApiError";
    this.envelope = options?.envelope;
    this.requestId = options?.requestId;
    this.statusCode = options?.statusCode;
  }
}

export type ProtectedRequestOptions = {
  getAccessToken: () => Promise<string | null>;
};

function isEnvelopeStatus(value: unknown): value is ApiEnvelope<unknown>["status"] {
  return value === "success" || value === "partial" || value === "error";
}

function optionalString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function normalizeFreshness(value: unknown): ApiEnvelope<unknown>["metadata"]["freshness"] | undefined {
  if (!isRecord(value)) return undefined;
  const freshnessStatus = isFreshnessStatus(value.freshness_status)
    ? value.freshness_status as FreshnessStatus
    : undefined;
  const expiresAt = optionalString(value.freshness_expires_at);
  return {
    last_updated_at: optionalString(value.last_updated_at),
    freshness_expires_at: expiresAt,
    is_stale: typeof value.is_stale === "boolean"
      ? value.is_stale
      : freshnessStatus === "stale",
    freshness_status: freshnessStatus,
  };
}

function normalizeSourceVersions(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {};
}

function normalizeWarnings(value: unknown): WarningItem[] {
  return Array.isArray(value) ? value as WarningItem[] : [];
}

function normalizeEnvelope<T>(value: unknown, responseOk: boolean): ApiEnvelope<T> {
  if (!value || typeof value !== "object") {
    throw new ApiError("Response was not an API envelope");
  }

  const rawEnvelope = value as Partial<ApiEnvelope<T>>;
  const metadata = rawEnvelope.metadata;
  const metadataRecord: Record<string, unknown> = isRecord(metadata) ? metadata : {};
  return {
    status: isEnvelopeStatus(rawEnvelope.status)
      ? rawEnvelope.status
      : responseOk
        ? "success"
        : "error",
    data: "data" in rawEnvelope ? (rawEnvelope.data as T | null) : null,
    metadata: {
      state: typeof metadataRecord.state === "string" ? metadataRecord.state : "unknown",
      freshness: normalizeFreshness(metadataRecord.freshness),
      source_versions: normalizeSourceVersions(metadataRecord.source_versions),
      warnings: normalizeWarnings(metadataRecord.warnings),
    },
    error: rawEnvelope.error ?? null,
  };
}

function appendOptionalParam(params: URLSearchParams, key: string, value: string | number | boolean | null | undefined) {
  if (value === null || value === undefined || value === "") return;
  params.set(key, String(value));
}

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<ApiEnvelope<T>> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
      ...options,
    });
  } catch (error) {
    const apiError = new ApiError(
      error instanceof Error
        ? error.message
        : `Network request failed for ${path}`,
    );
    reportApiFailure(path, apiError);
    throw apiError;
  }

  let envelope: ApiEnvelope<T>;
  try {
    envelope = normalizeEnvelope<T>(await response.json(), response.ok);
  } catch (error) {
    const requestId = response.headers.get("x-request-id") ?? undefined;
    const message = error instanceof ApiError
      ? error.message
      : `Invalid JSON response from ${path}`;
    const apiError = new ApiError(publicApiErrorMessage(message, requestId), {
      requestId,
      statusCode: response.status,
    });
    reportApiFailure(path, apiError);
    throw apiError;
  }

  if (!response.ok || envelope.status === "error") {
    const requestId = apiErrorRequestId(envelope, response);
    const apiError = new ApiError(
      publicApiErrorMessage(envelope.error?.message ?? `Request failed: ${path}`, requestId),
      {
        envelope: envelope as ApiEnvelope<unknown>,
        requestId,
        statusCode: response.status,
      },
    );
    reportApiFailure(path, apiError);
    throw apiError;
  }

  return envelope;
}

function apiErrorRequestId(envelope: ApiEnvelope<unknown>, response: Response): string | undefined {
  return envelope.error?.request_id ?? response.headers.get("x-request-id") ?? undefined;
}

function publicApiErrorMessage(message: string, requestId: string | undefined): string {
  return requestId ? `${message} Reference ID: ${requestId}` : message;
}

function reportApiFailure(path: string, error: ApiError): void {
  reportFrontendError(error, {
    source: "api_request",
    path,
    route: currentFrontendRoute(),
    requestId: error.requestId,
    statusCode: error.statusCode,
  });
}

function currentFrontendRoute(): string | undefined {
  if (typeof window === "undefined") return undefined;
  return `${window.location.pathname}${window.location.search}`;
}

async function protectedRequest<T>(
  path: string,
  auth: ProtectedRequestOptions,
  options?: RequestInit,
): Promise<ApiEnvelope<T>> {
  if (
    path !== "/me"
    && !path.startsWith("/me/")
    && !path.startsWith("/monetization/")
    && !path.startsWith("/billing/")
    && !path.startsWith("/api/institutions/")
    && !path.startsWith("/api/integrations/")
  ) {
    throw new ApiError(
      "Protected requests are restricted to /me, /monetization, /billing, /api/institutions, and /api/integrations routes",
    );
  }

  const token = await auth.getAccessToken();
  if (!token) {
    throw new ApiError("Authentication required for account request", { statusCode: 401 });
  }

  return request<T>(path, {
    ...options,
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
}

export function getHealth() {
  return request<{ service: string }>("/health");
}

export function getRegions() {
  return request<{ regions: RegionListItem[] }>("/regions");
}

export function getImportedMarkets() {
  return request<MarketCoverageListPayload>("/markets/imported");
}

export function getImportedMarketHealthOverview() {
  return request<ImportedMarketHealthOverviewPayload>("/markets/imported/health");
}

export function getImportedMarketHealth(marketKey: string) {
  return request<ImportedDatasetHealthReport>(
    `/markets/imported/${encodeURIComponent(marketKey)}/health`,
  );
}

export function getImportedMarketSources(marketKey: string) {
  return request<ImportedSourceAgingReport>(
    `/markets/imported/${encodeURIComponent(marketKey)}/sources`,
  );
}

export function getImportedMarketFacts(marketKey: string) {
  return request<ImportedFactHealthReport>(
    `/markets/imported/${encodeURIComponent(marketKey)}/facts`,
  );
}

export function getImportedMarketGaps(marketKey: string) {
  return request<ImportedCoverageGapReport>(
    `/markets/imported/${encodeURIComponent(marketKey)}/gaps`,
  );
}

export function getImportedMarketRankingDiagnostics(marketKey: string) {
  return request<ImportedRankingExclusionReport>(
    `/markets/imported/${encodeURIComponent(marketKey)}/ranking-diagnostics`,
  );
}

export function getImportedMarketRefreshReadiness(marketKey: string) {
  return request<ImportedRefreshReadinessReport>(
    `/markets/imported/${encodeURIComponent(marketKey)}/refresh-readiness`,
  );
}

export function getImportedMarketDiffPreview(marketKey: string) {
  return request<ImportedDiffPreview>(
    `/markets/imported/${encodeURIComponent(marketKey)}/diff-preview`,
  );
}

export function getMarketIntelligence(goal?: MarketIntelligenceGoal | string) {
  const params = new URLSearchParams();
  appendOptionalParam(params, "goal", goal);
  const query = params.toString();
  return request<PlatformMarketIntelligencePayload>(
    `/market-intelligence${query ? `?${query}` : ""}`,
  );
}

export function getMarketIntelligenceProfile(marketKey: string) {
  return request<MarketIntelligenceProfile>(
    `/market-intelligence/${encodeURIComponent(marketKey)}`,
  );
}

export function getMarketComparisonRanking(goal?: MarketIntelligenceGoal | string) {
  const params = new URLSearchParams();
  appendOptionalParam(params, "goal", goal);
  const query = params.toString();
  return request<PlatformMarketIntelligencePayload["default_ranking"]>(
    `/market-comparisons${query ? `?${query}` : ""}`,
  );
}

export function getMarketComparison(
  marketA: string,
  marketB: string,
  goal?: MarketIntelligenceGoal | string,
) {
  const params = new URLSearchParams();
  appendOptionalParam(params, "goal", goal);
  const query = params.toString();
  return request<MarketComparisonReport>(
    `/market-comparisons/${encodeURIComponent(marketA)}/${encodeURIComponent(marketB)}${query ? `?${query}` : ""}`,
  );
}

export async function getImportedMarketOperationDetails(
  marketKey: string,
): Promise<ImportedMarketOperationDetails> {
  const [sources, facts, gaps, ranking, readiness, diff] = await Promise.all([
    getImportedMarketSources(marketKey),
    getImportedMarketFacts(marketKey),
    getImportedMarketGaps(marketKey),
    getImportedMarketRankingDiagnostics(marketKey),
    getImportedMarketRefreshReadiness(marketKey),
    getImportedMarketDiffPreview(marketKey),
  ]);
  if (
    !sources.data
    || !facts.data
    || !gaps.data
    || !ranking.data
    || !readiness.data
    || !diff.data
  ) {
    throw new ApiError("Imported market diagnostics response was incomplete");
  }
  return {
    sources: sources.data,
    facts: facts.data,
    gaps: gaps.data,
    ranking: ranking.data,
    readiness: readiness.data,
    diff: diff.data,
  };
}

export async function getImportedMarketOperationsView() {
  const overview = await getImportedMarketHealthOverview();
  if (!overview.data) {
    throw new ApiError("Imported market health overview response was incomplete");
  }
  const detailEntries = await Promise.all(
    overview.data.markets.map(async (market) => [
      market.market_key,
      await getImportedMarketOperationDetails(market.market_key),
    ] as const),
  );
  return {
    ...overview,
    data: {
      overview: overview.data,
      details_by_market: Object.fromEntries(detailEntries),
    } satisfies ImportedMarketOperationsViewPayload,
  };
}

export function getRegion(regionId: string) {
  return request<RegionDetail>(`/regions/${encodeURIComponent(regionId)}`);
}

export function searchRegions(filters?: {
  query?: string;
  freshness_status?: FreshnessStatus;
  min_opportunity_score?: number;
  has_real_data?: boolean;
}) {
  const params = new URLSearchParams();
  appendOptionalParam(params, "query", filters?.query);
  appendOptionalParam(params, "freshness_status", filters?.freshness_status);
  appendOptionalParam(params, "min_opportunity_score", filters?.min_opportunity_score);
  appendOptionalParam(params, "has_real_data", filters?.has_real_data);
  const query = params.toString();
  return request<RegionSearchResponse>(`/regions/search${query ? `?${query}` : ""}`);
}

export function getRegionSources(regionId: string) {
  return request<SourceExplanation>(`/regions/${encodeURIComponent(regionId)}/sources`);
}

export function getCompany(companyId: string) {
  return request<CompanyDetail>(`/companies/${encodeURIComponent(companyId)}`);
}

export function searchCompanies(filters?: {
  query?: string;
  region_id?: string;
  current_hiring?: boolean;
  has_entry_level_access?: boolean;
}) {
  const params = new URLSearchParams();
  appendOptionalParam(params, "query", filters?.query);
  appendOptionalParam(params, "region_id", filters?.region_id);
  appendOptionalParam(params, "current_hiring", filters?.current_hiring);
  appendOptionalParam(params, "has_entry_level_access", filters?.has_entry_level_access);
  const query = params.toString();
  return request<CompanySearchResponse>(`/companies/search${query ? `?${query}` : ""}`);
}

export function getCompanyGeography(companyId: string) {
  return request<CompanyGeographyResponse>(`/companies/${encodeURIComponent(companyId)}/regions`);
}

export function getCompanySources(companyId: string) {
  return request<SourceExplanation>(`/companies/${encodeURIComponent(companyId)}/sources`);
}

export function getComparison(regionA: string, regionB: string) {
  const params = new URLSearchParams({ region_a: regionA, region_b: regionB });
  return request<ComparisonDetail>(`/compare?${params.toString()}`);
}

export function getPublicReports() {
  return request<PublicReportListPayload>("/public/reports");
}

export function getPublicReport(slug: string) {
  return request<PublicReport>(`/public/reports/${encodeURIComponent(slug)}`);
}

export function getPolicyWorkforceDashboard(regionId: string) {
  return request<WorkforceDashboardPayload>(
    `/policy/regions/${encodeURIComponent(regionId)}/workforce-dashboard`,
  );
}

export function getPolicyEconomicDevelopment(regionId: string) {
  return request<EconomicDevelopmentProfile>(
    `/policy/regions/${encodeURIComponent(regionId)}/economic-development`,
  );
}

export function getPolicyPeerComparison(regionId: string) {
  return request<PeerComparisonProfile>(
    `/policy/regions/${encodeURIComponent(regionId)}/peer-comparison`,
  );
}

export function getPolicyEducationAlignment(regionId: string) {
  return request<EducationWorkforceAlignmentProfile>(
    `/policy/regions/${encodeURIComponent(regionId)}/education-alignment`,
  );
}

export function getPolicyEarlyCareerReport(regionId: string) {
  return request<PublicReport>(
    `/policy/regions/${encodeURIComponent(regionId)}/reports/early-career-opportunity`,
  );
}

export function getPublicBenchmarks() {
  return request<PublicBenchmarkListPayload>("/public/benchmarks");
}

export function getPublicBenchmark(slug: string) {
  return request<PublicBenchmark>(`/public/benchmarks/${encodeURIComponent(slug)}`);
}

export function getPlatformEmbed(embedSlug: string, origin?: string | null) {
  const params = new URLSearchParams();
  appendOptionalParam(params, "origin", origin);
  const query = params.toString();
  return request<PlatformEmbedAccessPayload>(
    `/api/v1/platform/embeds/${encodeURIComponent(embedSlug)}${query ? `?${query}` : ""}`,
  );
}

export function getPredictiveReport(regionIds: string[] = [], companyIds: string[] = []) {
  const params = new URLSearchParams();
  for (const regionId of regionIds) {
    if (regionId) params.append("region_id", regionId);
  }
  for (const companyId of companyIds) {
    if (companyId) params.append("company_id", companyId);
  }
  const query = params.toString();
  return request<PredictiveReportPayload>(
    `/platform/predictive/reports${query ? `?${query}` : ""}`,
  );
}

export function getDataStandardDefinitions() {
  return request<DataStandardDefinitionListPayload>("/data-standards/definitions");
}

export function getDataStandardsPartnerSchema() {
  return request<PartnerSubmissionSchemaPayload>("/data-standards/partner-schema");
}

export function getDataStandardsPartners() {
  return request<PartnerRegistryPayload>("/data-standards/partners");
}

export function getDataStandardsQualityLabels() {
  return request<DataQualityLabelListPayload>("/data-standards/quality-labels");
}

export function getDataStandardsGovernanceFramework() {
  return request<GovernanceFrameworkPayload>("/data-standards/governance-framework");
}

export function evaluateDataQualityLabel(body: Record<string, unknown>) {
  return request<DataQualityCertificationResult>("/data-standards/quality-labels/evaluate", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function discoverPersonalized(body: PersonalizedRequest) {
  return request<PersonalizedResult>("/discover/personalized", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getRecommendationGoalModes() {
  return request<RecommendationGoalModesPayload>("/recommendations/goal-modes");
}

export function getRecommendationStrategy(body: RecommendationStrategyRequest) {
  return request<RecommendationStrategyPayload>("/recommendations/strategy", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getUserIntelligenceDashboard() {
  return request<UserIntelligenceDashboardPayload>("/user-intelligence/dashboard");
}

export function getTrustExplanation(subjectType: string, subjectId: string) {
  const params = new URLSearchParams({
    subject_type: subjectType,
    subject_id: subjectId,
  });
  return request<TrustExplanation>(`/trust/explanation?${params.toString()}`);
}

export function submitUserReport(body: UserReportCreateRequest) {
  return request<UserReportSubmissionResult>("/user-reports", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getOpportunityRoutes(body: TypedOpportunityRouteRequest) {
  return request<TypedOpportunityRouteResponse>("/opportunities/routes", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getCareerAgentAnswer(body: TypedCareerAgentRequest) {
  return request<CareerAgentAnswer>("/career-agent/answers", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getCareerActionPlan(body: CareerActionPlanRequest) {
  return request<CareerActionPlan>("/career-agent/action-plans", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getMonetizationPlans() {
  return request<MonetizationPlansPayload>("/monetization/plans");
}

export function getMonetizationFeatures() {
  return request<MonetizationFeaturesPayload>("/monetization/features");
}

export function getMonetizationReports() {
  return request<MonetizationReportsPayload>("/monetization/reports");
}

export function getBillingStatus() {
  return request<BillingStatusPayload>("/billing/status");
}

export function getMonetizationAccessPreview(filters: {
  plan_key?: MonetizationPlanKey;
  feature_key: MonetizationFeatureKey;
  used?: number;
}, auth?: ProtectedRequestOptions) {
  const params = new URLSearchParams({ feature_key: filters.feature_key });
  appendOptionalParam(params, "plan_key", filters.plan_key);
  appendOptionalParam(params, "used", filters.used);
  const path = `/monetization/access-preview?${params.toString()}`;
  return auth
    ? protectedRequest<MonetizationAccessPreviewPayload>(path, auth)
    : request<MonetizationAccessPreviewPayload>(path);
}

export function getMyMonetization(auth: ProtectedRequestOptions) {
  return protectedRequest<MonetizationMePayload>("/monetization/me", auth);
}

export function getMyMonetizationEntitlements(auth: ProtectedRequestOptions) {
  return protectedRequest<MonetizationEntitlementsPayload>("/monetization/entitlements", auth);
}

export function getMyMonetizationUsage(auth: ProtectedRequestOptions) {
  return protectedRequest<MonetizationUsagePayload>("/monetization/usage", auth);
}

export function getInstitutionCurrentOrganizations(auth: ProtectedRequestOptions) {
  return protectedRequest<InstitutionCurrentOrganizationsPayload>(
    "/api/institutions/organizations/current",
    auth,
  );
}

export function getInstitutionDashboard(
  organizationId: string,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<InstitutionDashboardPayload>(
    `/api/institutions/organizations/${encodeURIComponent(organizationId)}/dashboard`,
    auth,
  );
}

export function getInstitutionDecisionDashboard(
  organizationId: string,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<InstitutionDecisionDashboardPayload>(
    `/api/institutions/organizations/${encodeURIComponent(organizationId)}/decision-dashboard`,
    auth,
  );
}

export function getInstitutionCurriculumMarketMap(
  organizationId: string,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<CurriculumMarketMappingPayload>(
    `/api/institutions/organizations/${encodeURIComponent(organizationId)}/curriculum-market-map`,
    auth,
  );
}

export function getInstitutionWorkforceReport(
  organizationId: string,
  reportType: InstitutionWorkforceReportType,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<InstitutionWorkforceReportPayload>(
    `/api/institutions/organizations/${encodeURIComponent(organizationId)}/workforce-reports/${encodeURIComponent(reportType)}`,
    auth,
  );
}

export function getInstitutionBenchmarks(
  organizationId: string,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<InstitutionBenchmarkPayload>(
    `/api/institutions/organizations/${encodeURIComponent(organizationId)}/benchmarks`,
    auth,
  );
}

const INSTITUTION_ADVISOR_ENDPOINTS: Record<InstitutionAdvisorComparisonType, string> = {
  regions: "compare-regions",
  industries: "compare-industries",
  companies: "compare-companies",
  career_stages: "compare-career-stages",
  application_timing: "application-timing",
};

export function runInstitutionAdvisorComparison(
  organizationId: string,
  comparisonType: InstitutionAdvisorComparisonType,
  body: InstitutionAdvisorRequest,
  auth: ProtectedRequestOptions,
) {
  const endpoint = INSTITUTION_ADVISOR_ENDPOINTS[comparisonType];
  return protectedRequest<InstitutionAdvisorToolResponse>(
    `/api/institutions/organizations/${encodeURIComponent(organizationId)}/advisor/${endpoint}`,
    auth,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}

export function generateInstitutionReport(
  organizationId: string,
  body: InstitutionReportCreateRequest,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<InstitutionReportGeneratePayload>(
    `/api/institutions/organizations/${encodeURIComponent(organizationId)}/reports`,
    auth,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}

export function listInstitutionReports(
  organizationId: string,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<InstitutionReportListPayload>(
    `/api/institutions/organizations/${encodeURIComponent(organizationId)}/reports`,
    auth,
  );
}

export function getInstitutionReport(
  organizationId: string,
  reportId: string,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<InstitutionReportGeneratePayload>(
    `/api/institutions/organizations/${encodeURIComponent(organizationId)}/reports/${encodeURIComponent(reportId)}`,
    auth,
  );
}

export function createInstitutionDataRequest(
  organizationId: string,
  body: InstitutionDataRequestCreateRequest,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<InstitutionDataRequestCreatePayload>(
    `/api/institutions/organizations/${encodeURIComponent(organizationId)}/data-requests`,
    auth,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}

export function listInstitutionDataRequests(
  organizationId: string,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<InstitutionDataRequestListPayload>(
    `/api/institutions/organizations/${encodeURIComponent(organizationId)}/data-requests`,
    auth,
  );
}

export function createIntegrationExport(
  body: IntegrationExportCreateRequest,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<IntegrationExportCreatePayload>("/api/integrations/exports", auth, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function createIntegrationReminder(
  body: IntegrationReminderCreateRequest,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<IntegrationReminderCreatePayload>("/api/integrations/reminders", auth, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function createPartnerImport(
  body: PartnerImportCreateRequest,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<PartnerImportCreatePayload>("/api/integrations/partner-imports", auth, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listPartnerImports(
  organizationId: string,
  auth: ProtectedRequestOptions,
) {
  const params = new URLSearchParams({ organization_id: organizationId });
  return protectedRequest<PartnerImportListPayload>(
    `/api/integrations/partner-imports?${params.toString()}`,
    auth,
  );
}

export function getPartnerImport(
  importBatchId: string,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<PartnerImportCreatePayload>(
    `/api/integrations/partner-imports/${encodeURIComponent(importBatchId)}`,
    auth,
  );
}

export function validatePartnerImport(
  importBatchId: string,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<PartnerImportCreatePayload>(
    `/api/integrations/partner-imports/${encodeURIComponent(importBatchId)}/validate`,
    auth,
    { method: "POST" },
  );
}

export function acceptPartnerImport(
  importBatchId: string,
  body: PartnerImportActionRequest,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<PartnerImportCreatePayload>(
    `/api/integrations/partner-imports/${encodeURIComponent(importBatchId)}/accept`,
    auth,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}

export function rejectPartnerImport(
  importBatchId: string,
  body: PartnerImportActionRequest,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<PartnerImportCreatePayload>(
    `/api/integrations/partner-imports/${encodeURIComponent(importBatchId)}/reject`,
    auth,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}

export function archivePartnerImport(
  importBatchId: string,
  body: PartnerImportActionRequest,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<PartnerImportCreatePayload>(
    `/api/integrations/partner-imports/${encodeURIComponent(importBatchId)}/archive`,
    auth,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}

export function getPartnerImportReceipt(
  importBatchId: string,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<PartnerImportReceiptPayload>(
    `/api/integrations/partner-imports/${encodeURIComponent(importBatchId)}/receipt`,
    auth,
  );
}

export function createApiClient(
  body: ApiClientCreateRequest,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<ApiClientCreatePayload>("/api/integrations/api-clients", auth, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listApiClients(auth: ProtectedRequestOptions) {
  return protectedRequest<ApiClientListPayload>("/api/integrations/api-clients", auth);
}

export function updateApiClient(
  apiClientId: string,
  body: ApiClientUpdateRequest,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<ApiClientCreatePayload>(
    `/api/integrations/api-clients/${encodeURIComponent(apiClientId)}`,
    auth,
    {
      method: "PATCH",
      body: JSON.stringify(body),
    },
  );
}

export function createApiKey(apiClientId: string, auth: ProtectedRequestOptions) {
  return protectedRequest<ApiKeyCreatePayload>(
    `/api/integrations/api-clients/${encodeURIComponent(apiClientId)}/keys`,
    auth,
    {
      method: "POST",
      body: JSON.stringify({}),
    },
  );
}

export function revokeApiKey(apiKeyId: string, auth: ProtectedRequestOptions) {
  return protectedRequest<ApiKeyCreatePayload>(
    `/api/integrations/api-keys/${encodeURIComponent(apiKeyId)}/revoke`,
    auth,
    { method: "POST" },
  );
}

export function listApiUsage(apiClientId: string, auth: ProtectedRequestOptions) {
  return protectedRequest<ApiUsageListPayload>(
    `/api/integrations/api-clients/${encodeURIComponent(apiClientId)}/usage`,
    auth,
  );
}

export function getCareerPlatformRegistry(auth: ProtectedRequestOptions) {
  return protectedRequest<CareerPlatformRegistryPayload>(
    "/api/integrations/career-platforms",
    auth,
  );
}

export function createCareerPlatformReference(
  body: CareerPlatformReferenceCreateRequest,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<CareerPlatformReferencePayload>(
    "/api/integrations/career-platform-references",
    auth,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}

export function listCareerPlatformReferences(
  auth: ProtectedRequestOptions,
  params?: { organizationId?: string | null; subjectType?: string | null; subjectId?: string | null },
) {
  const query = new URLSearchParams();
  appendOptionalParam(query, "organization_id", params?.organizationId ?? undefined);
  appendOptionalParam(query, "subject_type", params?.subjectType ?? undefined);
  appendOptionalParam(query, "subject_id", params?.subjectId ?? undefined);
  const suffix = query.toString();
  return protectedRequest<CareerPlatformReferenceListPayload>(
    `/api/integrations/career-platform-references${suffix ? `?${suffix}` : ""}`,
    auth,
  );
}

export function createCareerPlatformExport(
  body: CareerPlatformExportRequest,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<CareerPlatformExportPayload>(
    "/api/integrations/career-platform-exports",
    auth,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}

export function generateMonetizationReport(
  reportKey: MonetizationReportProductKey,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<MonetizationReportGenerationPayload>(
    `/monetization/reports/${encodeURIComponent(reportKey)}/generate`,
    auth,
    { method: "POST" },
  );
}

export function exportMonetizationReport(
  reportKey: MonetizationReportProductKey,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<MonetizationReportExportPayload>(
    `/monetization/reports/${encodeURIComponent(reportKey)}/export`,
    auth,
    { method: "POST" },
  );
}

export function createBillingCheckoutSession(
  planKey: MonetizationPlanKey,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<BillingCheckoutSessionPayload>("/billing/checkout-session", auth, {
    method: "POST",
    body: JSON.stringify({ plan_key: planKey }),
  });
}

export function createBillingPortalSession(auth: ProtectedRequestOptions) {
  return protectedRequest<BillingPortalSessionPayload>("/billing/portal-session", auth, {
    method: "POST",
  });
}

export function getCurrentUser(auth: ProtectedRequestOptions) {
  return protectedRequest<CurrentUserProfile>("/me", auth);
}

export function getPreferences(auth: ProtectedRequestOptions) {
  return protectedRequest<UserPreferenceProfile>("/me/preferences", auth);
}

export function updatePreferences(
  body: UserPreferenceProfileInput,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<UserPreferenceProfile>("/me/preferences", auth, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function deletePreferences(auth: ProtectedRequestOptions) {
  return protectedRequest<{ deleted_preference_profiles: number }>("/me/preferences", auth, {
    method: "DELETE",
  });
}

export function previewScoringOverlay(
  body: ScoringPreviewRequest,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<ScoringPreviewResult>("/me/scoring-preview", auth, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getCareerMemory(auth: ProtectedRequestOptions) {
  return protectedRequest<CareerMemoryProfile>("/me/career-memory", auth);
}

export function updateCareerMemory(
  body: CareerMemoryUpdateRequest,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<CareerMemoryProfile>("/me/career-memory", auth, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function deleteCareerMemory(
  body: CareerMemoryDeleteRequest,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<CareerMemoryProfile>("/me/career-memory", auth, {
    method: "DELETE",
    body: JSON.stringify(body),
  });
}

export function getCareerActionPlanWithMemory(
  body: CareerActionPlanRequest,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<CareerActionPlan>("/me/career-agent/action-plans", auth, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function previewCareerAgentTool(
  body: CareerAgentToolRequest,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<CareerAgentToolPreview>("/me/career-agent/tools/preview", auth, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listCareerAgentTools(auth: ProtectedRequestOptions) {
  return protectedRequest<CareerAgentToolList>("/me/career-agent/tools", auth);
}

export function getCareerAgentTool(toolRequestId: string, auth: ProtectedRequestOptions) {
  return protectedRequest<CareerAgentToolPreview>(
    `/me/career-agent/tools/${encodeURIComponent(toolRequestId)}`,
    auth,
  );
}

export function approveCareerAgentTool(
  body: CareerAgentToolApproval,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<CareerAgentToolExecution>("/me/career-agent/tools/approve", auth, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function rejectCareerAgentTool(
  body: CareerAgentToolApproval,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<CareerAgentToolExecution>("/me/career-agent/tools/reject", auth, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function createSavedMarketArtifact(
  body: SavedMarketArtifactInput,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<SavedMarketArtifact>("/me/saved-market-artifacts", auth, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listSavedMarketArtifacts(auth: ProtectedRequestOptions, artifactType?: string) {
  const params = new URLSearchParams();
  appendOptionalParam(params, "artifact_type", artifactType);
  const query = params.toString();
  return protectedRequest<SavedMarketArtifactList>(
    `/me/saved-market-artifacts${query ? `?${query}` : ""}`,
    auth,
  );
}

export function getSavedMarketArtifact(savedArtifactId: string, auth: ProtectedRequestOptions) {
  return protectedRequest<SavedMarketArtifact>(
    `/me/saved-market-artifacts/${encodeURIComponent(savedArtifactId)}`,
    auth,
  );
}

export function deleteSavedMarketArtifact(savedArtifactId: string, auth: ProtectedRequestOptions) {
  return protectedRequest<{ deleted_saved_market_artifacts: number }>(
    `/me/saved-market-artifacts/${encodeURIComponent(savedArtifactId)}`,
    auth,
    { method: "DELETE" },
  );
}

export function listAlerts(auth: ProtectedRequestOptions, includeDismissed = false) {
  const params = new URLSearchParams();
  appendOptionalParam(params, "include_dismissed", includeDismissed);
  const query = params.toString();
  return protectedRequest<UserAlertList>(`/me/alerts${query ? `?${query}` : ""}`, auth);
}

export function markAlertRead(userAlertId: string, auth: ProtectedRequestOptions) {
  return protectedRequest<UserAlert>(
    `/me/alerts/${encodeURIComponent(userAlertId)}/read`,
    auth,
    { method: "POST" },
  );
}

export function dismissAlert(userAlertId: string, auth: ProtectedRequestOptions) {
  return protectedRequest<UserAlert>(
    `/me/alerts/${encodeURIComponent(userAlertId)}/dismiss`,
    auth,
    { method: "POST" },
  );
}

export function explainRegion(body: ExplanationRequest, auth: ProtectedRequestOptions) {
  return protectedRequest<ExplanationResult>("/me/explanations/region", auth, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function explainCompany(body: ExplanationRequest, auth: ProtectedRequestOptions) {
  return protectedRequest<ExplanationResult>("/me/explanations/company", auth, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function explainComparison(body: ExplanationRequest, auth: ProtectedRequestOptions) {
  return protectedRequest<ExplanationResult>("/me/explanations/comparison", auth, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function explainAlert(body: ExplanationRequest, auth: ProtectedRequestOptions) {
  return protectedRequest<ExplanationResult>("/me/explanations/alert", auth, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function createRecommendationSnapshot(
  body: PersonalizedRecommendationSnapshotInput,
  auth: ProtectedRequestOptions,
) {
  return protectedRequest<PersonalizedRecommendationSnapshot>("/me/recommendation-snapshots", auth, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listRecommendationSnapshots(auth: ProtectedRequestOptions) {
  return protectedRequest<RecommendationSnapshotList>("/me/recommendation-snapshots", auth);
}

export function getRecommendationSnapshot(recommendationSnapshotId: string, auth: ProtectedRequestOptions) {
  return protectedRequest<PersonalizedRecommendationSnapshot>(
    `/me/recommendation-snapshots/${encodeURIComponent(recommendationSnapshotId)}`,
    auth,
  );
}

export function exportUserData(auth: ProtectedRequestOptions) {
  return protectedRequest<UserDataExport>("/me/export", auth);
}

export function deactivateAccount(auth: ProtectedRequestOptions) {
  return protectedRequest<AccountDeactivationResult>("/me", auth, { method: "DELETE" });
}
