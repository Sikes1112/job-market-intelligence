import { describe, expect, it } from "vitest";

import {
  canonicalRegionIdForToken,
  geographicInputFromPath,
  geographicRouteToken,
} from "./geography";
import { parseRoute, regionDetailUrl } from "./urlState";

describe("canonical geographic URL foundation", () => {
  it("builds a canonical public-slug URL when canonical identity is available", () => {
    const target = { region_id: "sf_bay_area", public_slug: "san-francisco-bay-area" };
    expect(geographicRouteToken(target)).toBe("san-francisco-bay-area");
    expect(regionDetailUrl(target)).toBe("/markets/region/san-francisco-bay-area");
  });

  it("preserves legacy route inputs for API compatibility resolution", () => {
    expect(parseRoute("/markets/region/greater_sf", "").regionId).toBe("greater_sf");
    expect(regionDetailUrl("greater_sf")).toBe("/markets/region/greater_sf");
    expect(geographicInputFromPath("  DC%2FNoVA  ")).toBe("DC%2FNoVA");
  });

  it("falls back to canonical Region ID when a slug is not yet published", () => {
    expect(geographicRouteToken({ region_id: "test_region", public_slug: null })).toBe(
      "test_region",
    );
  });

  it("maps known IDs and public slugs without maintaining a client alias registry", () => {
    const regions = [
      { region_id: "greater_boston", public_slug: "boston" },
      { region_id: "sf_bay_area", public_slug: "san-francisco-bay-area" },
    ];
    expect(canonicalRegionIdForToken("greater_boston", regions)).toBe("greater_boston");
    expect(canonicalRegionIdForToken("boston", regions)).toBe("greater_boston");
    expect(canonicalRegionIdForToken("greater_sf", regions)).toBeUndefined();
  });
});
