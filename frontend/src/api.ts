import type {
  ApiEnvelope,
  CompanyDetail,
  CompanyGeographyResponse,
  CompanySearchResponse,
  ComparisonDetail,
  FreshnessStatus,
  PersonalizedRequest,
  PersonalizedResult,
  RegionDetail,
  RegionListItem,
  RegionSearchResponse,
  SourceExplanation,
  WarningItem,
} from "./types";
import { isFreshnessStatus, isRecord } from "./dataQuality";

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "");

export const API_BASE_URL = configuredBaseUrl ?? "";
export const API_TARGET_LABEL =
  configuredBaseUrl ?? "Vite dev proxy -> http://127.0.0.1:8000";

export class ApiError extends Error {
  envelope?: ApiEnvelope<unknown>;
  statusCode?: number;

  constructor(message: string, options?: { envelope?: ApiEnvelope<unknown>; statusCode?: number }) {
    super(message);
    this.name = "ApiError";
    this.envelope = options?.envelope;
    this.statusCode = options?.statusCode;
  }
}

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
    throw new ApiError(
      error instanceof Error
        ? error.message
        : `Network request failed for ${path}`,
    );
  }

  let envelope: ApiEnvelope<T>;
  try {
    envelope = normalizeEnvelope<T>(await response.json(), response.ok);
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(`Invalid JSON response from ${path}`, {
      statusCode: response.status,
    });
  }

  if (!response.ok || envelope.status === "error") {
    throw new ApiError(envelope.error?.message ?? `Request failed: ${path}`, {
      envelope: envelope as ApiEnvelope<unknown>,
      statusCode: response.status,
    });
  }

  return envelope;
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
