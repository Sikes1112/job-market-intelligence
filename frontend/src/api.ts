import type {
  ApiEnvelope,
  AccountDeactivationResult,
  BillingCheckoutSessionPayload,
  BillingPortalSessionPayload,
  BillingStatusPayload,
  CompanyDetail,
  CompanyGeographyResponse,
  CompanySearchResponse,
  ComparisonDetail,
  CurrentUserProfile,
  ExplanationRequest,
  ExplanationResult,
  FreshnessStatus,
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
  PersonalizedRecommendationSnapshot,
  PersonalizedRecommendationSnapshotInput,
  PersonalizedRequest,
  PersonalizedResult,
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
  UserAlert,
  UserAlertList,
  UserDataExport,
  UserPreferenceProfile,
  UserPreferenceProfileInput,
  WarningItem,
} from "./types";
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
  ) {
    throw new ApiError("Protected requests are restricted to /me, /monetization, and /billing routes");
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
