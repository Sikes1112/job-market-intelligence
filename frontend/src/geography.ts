/** Canonical frontend geographic identity. Aliases are resolved by the API. */
export type GeographicCentroid = {
  latitude: number;
  longitude: number;
};

export type CanonicalGeographicIdentity = {
  region_id: string;
  public_slug: string | null;
  display_name: string;
  region_type: string;
  primary_city: string | null;
  state_codes: string[];
  centroid: GeographicCentroid | null;
  focus_bounds: Record<string, number> | null;
  market_support_status: "supported" | "unsupported" | "unknown" | string;
};

export type GeographicResolution = CanonicalGeographicIdentity & {
  status: "resolved";
  input: string;
  normalized_input: string;
  resolution_source: string;
  candidate_region_ids: string[];
};

export type GeographicRouteTarget =
  | string
  | { region_id: string; public_slug?: string | null };

export function geographicRouteToken(target: GeographicRouteTarget): string {
  if (typeof target === "string") return target.trim();
  return target.public_slug?.trim() || target.region_id.trim();
}

export function geographicInputFromPath(value: string | undefined): string | undefined {
  const trimmed = value?.trim();
  return trimmed || undefined;
}

export function canonicalRegionIdForToken(
  token: string,
  regions: Array<{ region_id: string; public_slug?: string | null }>,
): string | undefined {
  const normalized = token.trim();
  if (!normalized) return undefined;
  return regions.find(
    (region) => region.region_id === normalized || region.public_slug === normalized,
  )?.region_id;
}
