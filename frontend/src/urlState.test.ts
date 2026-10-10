import { describe, expect, test } from "vitest";
import {
  canonicalizeExploreState,
  currentOpportunitiesUrl,
  exploreComparisonUrl,
  isProductPage,
  exploreUrl,
  marketIntelligenceUrl,
  mySearchApplicationUrl,
  mySearchPursuitUrl,
  parseRoute,
  roleExploreValueForQuery,
  savedExploreComparisonUrl,
  userIntelligenceDashboardUrl,
} from "./urlState";

describe("urlState dashboard route", () => {
  test("parses the user intelligence dashboard product route", () => {
    const route = parseRoute("/markets/dashboard", "");

    expect(route.page).toBe("dashboard");
    expect(isProductPage(route.page)).toBe(true);
    expect(userIntelligenceDashboardUrl()).toBe("/markets/dashboard");
  });
});

describe("Layer 42A product routes", () => {
  test("restores canonical Explore focus, view, overrides, and ordered comparison selection", () => {
    const url = exploreUrl({
      focus: "boston",
      view: "map",
      selected: ["boston", "new-york", "boston", "seattle", "austin", "chicago"],
      goal: "ai_ml",
      opportunityTypes: ["internship"],
      workArrangements: ["hybrid", "remote"],
      geographicScope: ["boston", "new-york"],
      industries: ["healthcare"],
    });
    const route = parseRoute("/markets", url.slice(url.indexOf("?")));

    expect(route.page).toBe("explore");
    expect(route.explore.focus).toBe("boston");
    expect(route.explore.view).toBe("map");
    expect(route.explore.selected).toEqual(["boston", "new-york", "seattle", "austin"]);
    expect(route.explore.goal).toBe("ai_ml");
    expect(route.explore.industries).toEqual(["healthcare"]);
  });

  test("keeps old routes addressable while exposing My Search and Profile", () => {
    expect(parseRoute("/markets/my-search", "").page).toBe("my-search");
    expect(parseRoute("/markets/profile", "").page).toBe("profile");
    expect(parseRoute("/markets/career-identity", "").page).toBe("career-identity");
    expect(parseRoute("/markets/policy", "").page).toBe("policy");
  });

  test("round-trips durable pursuit and application links", () => {
    const pursuit = mySearchPursuitUrl("decision 43");
    const application = mySearchApplicationUrl("application/43");
    expect(pursuit).toBe("/markets/my-search/pursuits/decision%2043");
    expect(application).toBe("/markets/my-search/applications/application%2F43");
    expect(parseRoute(pursuit, "").pursuitId).toBe("decision 43");
    expect(parseRoute(application, "").applicationId).toBe("application/43");
  });

  test("round-trips live and durable comparison deep links through the canonical Explore parser", () => {
    const live = exploreComparisonUrl({
      selected: ["boston", "new-york", "seattle"],
      goal: "ai_ml",
      opportunityTypes: ["internship"],
      view: "list",
    });
    expect(live).toBe("/markets/compare?selected=boston%2Cnew-york%2Cseattle&role=ai_ml&opportunity=internship");
    const parsed = parseRoute("/markets/compare", live.slice(live.indexOf("?")));
    expect(parsed.page).toBe("compare");
    expect(parsed.explore.selected).toEqual(["boston", "new-york", "seattle"]);
    expect(parsed.explore.goal).toBe("ai_ml");

    const saved = savedExploreComparisonUrl("comparison_42");
    expect(saved).toBe("/markets/comparisons/comparison_42");
    expect(parseRoute(saved, "").savedComparisonId).toBe("comparison_42");
  });

  test("canonicalizes IDs and aliases, drops malformed tokens, then applies the four-market cap", () => {
    const raw = parseRoute(
      "/markets",
      "?focus=greater_boston&selected=bad,greater_sf,boston,greater_nyc,seattle,austin,chicago&geography=greater_sf,unknown",
    ).explore;
    expect(raw.selected).toEqual(["bad", "greater_sf", "boston", "greater_nyc", "seattle", "austin", "chicago"]);
    const canonical = canonicalizeExploreState(raw, [
      { region_id: "greater_boston", public_slug: "boston" },
      { region_id: "sf_bay_area", public_slug: "san-francisco-bay-area", aliases: ["greater_sf"] },
      { region_id: "greater_nyc", public_slug: "new-york" },
      { region_id: "greater_seattle", public_slug: "seattle" },
      { region_id: "austin", public_slug: "austin" },
      { region_id: "chicago", public_slug: "chicago" },
    ]);
    expect(canonical.focus).toBe("boston");
    expect(canonical.selected).toEqual(["san-francisco-bay-area", "boston", "new-york", "seattle"]);
    expect(canonical.geographicScope).toEqual(["san-francisco-bay-area"]);
  });

  test("applies comparison limits only to valid unique canonical markets", () => {
    const identities = [
      { region_id: "greater_boston", public_slug: "boston", aliases: ["greater-boston"] },
      { region_id: "sf_bay_area", public_slug: "san-francisco-bay-area", aliases: ["greater_sf"] },
      { region_id: "greater_nyc", public_slug: "new-york" },
      { region_id: "greater_seattle", public_slug: "seattle" },
      { region_id: "austin", public_slug: "austin" },
    ];
    const base = {
      view: "list" as const,
      opportunityTypes: [], workArrangements: [], geographicScope: [], industries: [],
    };

    expect(canonicalizeExploreState({ ...base, selected: ["bad", "unknown"] }, identities).selected).toEqual([]);
    expect(canonicalizeExploreState({ ...base, selected: ["boston", "greater_boston", "greater-boston", "boston"] }, identities).selected).toEqual(["boston"]);
    expect(canonicalizeExploreState({ ...base, selected: ["greater_boston", "greater_sf", "greater_nyc", "greater_seattle", "austin"] }, identities).selected).toEqual([
      "boston", "san-francisco-bay-area", "new-york", "seattle",
    ]);

    const focusAndSelection = canonicalizeExploreState({
      ...base,
      focus: "greater-boston",
      selected: ["greater_boston", "greater_sf"],
    }, identities);
    expect(focusAndSelection.focus).toBe("boston");
    expect(focusAndSelection.selected).toEqual(["boston", "san-francisco-bay-area"]);
    expect(exploreUrl(focusAndSelection)).toBe("/markets?focus=boston&selected=boston%2Csan-francisco-bay-area");

    const repeatedRaw = parseRoute("/markets", "?selected=boston,boston,boston,boston,boston").explore;
    expect(repeatedRaw.selected).toEqual(["boston", "boston", "boston", "boston", "boston"]);
    expect(canonicalizeExploreState(repeatedRaw, identities).selected).toEqual(["boston"]);
  });

  test("routes recognized roles as Explore overrides and preserves opportunity context", () => {
    expect(roleExploreValueForQuery("AI / machine learning")).toBe("ai_ml");
    const url = currentOpportunitiesUrl({ market: "austin", roleFamily: "product_management", opportunityType: "internship", workArrangement: "hybrid", returnTo: "/markets?focus=austin" });
    expect(url).toContain("opportunity_type=internship");
    expect(url).toContain("work_arrangement=hybrid");
    const route = parseRoute("/markets/current-opportunities", url.slice(url.indexOf("?")));
    expect(route.currentOpportunities).toEqual({ market: "austin", roleFamily: "product_management", opportunityType: "internship", workArrangement: "hybrid", returnTo: "/markets?focus=austin" });
  });
});

describe("urlState market intelligence route", () => {
  test("parses and serializes the market intelligence product route", () => {
    const route = parseRoute(
      "/markets/intelligence",
      "?goal=data_science&market=atlanta&compare_a=atlanta&compare_b=boston",
    );

    expect(route.page).toBe("intelligence");
    expect(isProductPage(route.page)).toBe(true);
    expect(route.intelligence).toEqual({
      goal: "data_science",
      marketKey: "atlanta",
      compareA: "atlanta",
      compareB: "boston",
    });
    expect(marketIntelligenceUrl(route.intelligence)).toBe(
      "/markets/intelligence?goal=data_science&market=atlanta&compare_a=atlanta&compare_b=boston",
    );
  });
});
