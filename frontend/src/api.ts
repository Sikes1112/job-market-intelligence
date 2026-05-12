import type {
  ApiEnvelope,
  CompanyDetail,
  ComparisonDetail,
  PersonalizedRequest,
  PersonalizedResult,
  RegionDetail,
  RegionListItem,
} from "./types";

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
    envelope = (await response.json()) as ApiEnvelope<T>;
  } catch {
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

export function getCompany(companyId: string) {
  return request<CompanyDetail>(`/companies/${encodeURIComponent(companyId)}`);
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
