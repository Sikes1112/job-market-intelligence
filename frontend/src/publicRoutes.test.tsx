// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import App from "./App";
import { FrontendAuthProvider } from "./auth";

type MockPayload = {
  data: unknown;
  warnings?: unknown[];
};

function envelope(data: unknown, warnings: unknown[] = []) {
  return {
    status: "success",
    data,
    metadata: { state: "test", source_versions: {}, warnings },
    error: null,
  };
}

const coverageLabels: Record<string, string> = {
  tier_1: "Tier 1 - fully covered market",
  tier_2: "Tier 2 - partial but useful market",
  tier_3: "Tier 3 - watchlist / emerging market",
  tier_4: "Tier 4 - placeholder only",
};

const coverageScores: Record<string, number> = {
  tier_1: 0.86,
  tier_2: 0.62,
  tier_3: 0.24,
  tier_4: 0,
};

const coverageDescriptions: Record<string, string> = {
  tier_1: "API fixture says this market is ready for confident comparison.",
  tier_2: "API fixture says this market is directionally useful but incomplete.",
  tier_3: "API fixture says this market is tracked but not ready for confident recommendations.",
  tier_4: "API fixture says this market is placeholder-only and not analyzed.",
};

const coverageLimitations: Record<string, string> = {
  tier_1: "",
  tier_2: "Coverage is partial; compare this market with caution.",
  tier_3: "Coverage is watchlist-level; do not treat it as a confident recommendation market.",
  tier_4: "Coverage is placeholder-only; do not treat it as analyzed market intelligence.",
};

function coverage(tier: "tier_1" | "tier_2" | "tier_3" | "tier_4") {
  const score = coverageScores[tier];
  return {
    tier,
    label: coverageLabels[tier],
    quality_score: score,
    components: {
      company_coverage: score,
      hiring_coverage: tier === "tier_4" ? 0 : Math.max(0.12, score - 0.08),
      entry_level_coverage: tier === "tier_1" ? 0.82 : tier === "tier_2" ? 0.52 : 0,
      freshness: tier === "tier_4" ? 0 : 0.72,
      source_diversity: tier === "tier_1" ? 0.78 : tier === "tier_2" ? 0.42 : 0.12,
      confidence: score,
    },
    coverage_tier: tier,
    coverage_label: coverageLabels[tier],
    coverage_description: coverageDescriptions[tier],
    coverage_quality_score: {
      overall_score: score * 100,
      components: {
        company_coverage: score * 100,
        hiring_coverage: tier === "tier_4" ? 0 : Math.max(12, (score - 0.08) * 100),
        entry_level_coverage: tier === "tier_1" ? 82 : tier === "tier_2" ? 52 : 0,
        freshness: tier === "tier_4" ? 0 : 72,
        source_diversity: tier === "tier_1" ? 78 : tier === "tier_2" ? 42 : 12,
        confidence: score * 100,
      },
    },
    coverage_limitations: coverageLimitations[tier] ? [coverageLimitations[tier]] : [],
    notes: [`Fixture ${coverageLabels[tier].toLowerCase()} coverage note.`],
    heuristic: true,
    safe_for_confident_market_comparison: tier === "tier_1",
    should_rank_as_confident_recommendation: tier === "tier_1",
  };
}

function priorityMarket() {
  return {
    rank: 10,
    market_id: "boston",
    display_name: "Boston",
  };
}

function sectorCoverage(tier: "tier_1" | "tier_2" | "tier_3" | "tier_4", coverage_level = "watchlist") {
  return {
    sector: "ai",
    label: "AI",
    coverage_level,
    coverage: coverage(tier),
  };
}

function freshnessSummary() {
  return {
    freshness_status: "fresh",
    data_basis: "real_imported",
    last_collected_at: null,
    source_count: 1,
    low_confidence_warning: null,
  };
}

function regionScores(score = 0.74) {
  return {
    structural_ecosystem_score: 0.7,
    live_market_score: 0.6,
    objective_opportunity_score: score,
    raw_total_score: 0.68,
    general_density_score: 0.5,
    tech_market_density_score: 0.55,
    early_career_accessibility_score: 0.66,
    score_ruleset_version: "marketscore_v1",
  };
}

function regionDetail(
  regionId: string,
  displayName: string,
  tier?: "tier_1" | "tier_2" | "tier_3" | "tier_4",
  sectorCoverage: Record<string, unknown> = {},
) {
  return {
    region_id: regionId,
    display_name: displayName,
    region_type: "greater_region",
    parent_region_id: null,
    labor_market_group: regionId.replace("greater_", ""),
    ...(tier ? { coverage: coverage(tier), sector_coverage: sectorCoverage } : {}),
    ...(regionId === "greater_boston" ? { priority_market: priorityMarket() } : {}),
    summary: { eligible_company_count: 1 },
    scores: regionScores(tier === "tier_4" ? 0.28 : 0.74),
    top_companies_present: [
      {
        company_id: "comp_a",
        company_name: "Acme AI",
        sector_primary: "ai",
        eligibility_status: "eligible",
        is_major_tech: false,
        is_mag7: false,
        prestige_score: 0.45,
      },
    ],
    top_companies_hiring: [],
    entry_level_summary: {},
    major_tech_summary: { count: 0, company_ids: [] },
    mag7_summary: { count: 0, company_ids: [] },
  };
}

function sourceExplanation(subjectId: string, subjectType: "company" | "region" = "region") {
  return {
    subject_type: subjectType,
    subject_id: subjectId,
    freshness: freshnessSummary(),
    sources: [],
  };
}

function coverageWarning(scopeRef: string) {
  return {
    warning_code: "region_coverage_not_confident",
    severity: "medium",
    message: `Region ${scopeRef} is not covered enough for confident recommendations.`,
    scope_type: "region",
    scope_ref: scopeRef,
  };
}

function responsePayloadFor(input: RequestInfo | URL): MockPayload {
  const value = typeof input === "string" ? input : input.toString();

  if (value === "/health") return { data: { service: "test" } };
  if (value === "/regions") {
    return {
      data: {
        regions: [
          {
            region_id: "greater_boston",
            display_name: "Greater Boston",
            region_type: "greater_region",
            parent_region_id: null,
            labor_market_group: "boston",
            state: "fresh",
            coverage: coverage("tier_2"),
            sector_coverage: {},
            priority_market: priorityMarket(),
          },
          {
            region_id: "greater_sf",
            display_name: "Greater SF",
            region_type: "greater_region",
            parent_region_id: null,
            labor_market_group: "sf",
            state: "fresh",
            coverage: coverage("tier_4"),
            sector_coverage: {},
          },
          {
            region_id: "legacy_market",
            display_name: "Legacy Market",
            region_type: "placeholder",
            parent_region_id: null,
            labor_market_group: null,
            state: "unknown",
          },
        ],
      },
    };
  }
  if (value === "/regions/greater_boston") {
    return {
      data: regionDetail("greater_boston", "Greater Boston", "tier_2", {
        ai: sectorCoverage("tier_3"),
      }),
    };
  }
  if (value === "/regions/greater_sf") {
    return { data: regionDetail("greater_sf", "Greater SF", "tier_4") };
  }
  if (value === "/regions/legacy_market") {
    return { data: regionDetail("legacy_market", "Legacy Market") };
  }
  if (value.startsWith("/regions/greater_boston/sources")) {
    return { data: sourceExplanation("greater_boston") };
  }
  if (value.startsWith("/regions/greater_sf/sources")) {
    return { data: sourceExplanation("greater_sf") };
  }
  if (value.startsWith("/regions/legacy_market/sources")) {
    return { data: sourceExplanation("legacy_market") };
  }
  if (value.startsWith("/regions/search")) {
    return {
      data: {
        regions: [
          {
            region_id: "greater_boston",
            name: "Greater Boston",
            region_name: "greater_boston",
            region_type: "greater_region",
            parent_region_id: null,
            labor_market_group: "boston",
            opportunity_score: 0.74,
            coverage: coverage("tier_1"),
            sector_coverage: {},
            priority_market: priorityMarket(),
            freshness: freshnessSummary(),
            has_real_data: true,
          },
          {
            region_id: "greater_sf",
            name: "Greater SF",
            region_name: "greater_sf",
            region_type: "greater_region",
            parent_region_id: null,
            labor_market_group: "sf",
            opportunity_score: 0.28,
            coverage: coverage("tier_4"),
            sector_coverage: {},
            freshness: freshnessSummary(),
            has_real_data: true,
          },
        ],
      },
    };
  }
  if (value.startsWith("/companies/search")) {
    return {
      data: {
        companies: [
          {
            company_id: "comp_a",
            name: "Acme AI",
            sector: "ai",
            industry: "software",
            role_families: ["product"],
            matched_region_ids: ["greater_boston"],
            matched_region_coverage: { greater_boston: coverage("tier_2") },
            current_hiring: true,
            has_entry_level_access: true,
            presence_status: "present",
            freshness: freshnessSummary(),
            has_real_data: true,
          },
        ],
      },
    };
  }
  if (value === "/companies/comp_a") {
    return {
      data: {
        company_id: "comp_a",
        company_name: "Acme AI",
        normalized_company_name: "acme ai",
        sector_primary: "ai",
        sector_secondary: null,
        eligibility_status: "eligible",
        eligibility_override_flag: false,
        classification_confidence: "high",
        is_major_tech: false,
        is_mag7: false,
        prestige_score: 0.45,
        regions_present: [
          {
            region_id: "greater_boston",
            region_display_name: "Greater Boston",
            presence_status: "present",
            presence_basis: "office",
            presence_confidence: "high",
            coverage: coverage("tier_2"),
            sector_coverage: { ai: sectorCoverage("tier_3") },
            priority_market: priorityMarket(),
          },
        ],
        regions_hiring: [
          {
            region_id: "greater_sf",
            region_display_name: "Greater SF",
            currently_hiring_flag: true,
            active_posting_count_now: 3,
            posting_count_30d: 5,
            posting_count_90d: 8,
            coverage: coverage("tier_4"),
            sector_coverage: {},
          },
        ],
        entry_level_regions: [
          {
            region_id: "greater_boston",
            region_display_name: "Greater Boston",
            internship_count: 1,
            coop_count: 0,
            entry_level_full_time_count: 1,
            formal_early_career_program_flag: true,
            entry_level_access_score: 0.62,
            entry_level_confidence: "high",
            coverage: coverage("tier_2"),
            sector_coverage: {},
            priority_market: priorityMarket(),
          },
        ],
      },
    };
  }
  if (value.startsWith("/companies/comp_a/sources")) {
    return { data: sourceExplanation("comp_a", "company") };
  }
  if (value.startsWith("/companies/comp_a/regions")) {
    return {
      data: {
        company_id: "comp_a",
        company_name: "Acme AI",
        regions: [
          {
            region_id: "greater_boston",
            region_name: "Greater Boston",
            presence_status: "present",
            current_hiring: true,
            has_entry_level_access: true,
            coverage: coverage("tier_2"),
            sector_coverage: { ai: sectorCoverage("tier_3") },
            priority_market: priorityMarket(),
            freshness: freshnessSummary(),
            has_real_data: true,
          },
          {
            region_id: "greater_sf",
            region_name: "Greater SF",
            presence_status: "present",
            current_hiring: true,
            has_entry_level_access: false,
            coverage: coverage("tier_4"),
            sector_coverage: {},
            freshness: freshnessSummary(),
            has_real_data: true,
          },
        ],
      },
    };
  }
  if (value.startsWith("/compare")) {
    return {
      data: {
        comparison_id: "greater_boston__greater_sf",
        region_a: {
          region_id: "greater_boston",
          display_name: "Greater Boston",
          scores: regionScores(0.74),
          coverage: coverage("tier_3"),
          sector_coverage: {},
          priority_market: priorityMarket(),
        },
        region_b: {
          region_id: "greater_sf",
          display_name: "Greater SF",
          scores: regionScores(0.28),
          coverage: coverage("tier_4"),
          sector_coverage: {},
        },
        category_winners: { objective_opportunity_score: "greater_boston" },
        notes: [],
      },
      warnings: [coverageWarning("greater_boston"), coverageWarning("greater_sf")],
    };
  }
  if (value === "/discover/personalized") {
    return {
      data: {
        ranked_regions: [
          {
            region_id: "greater_boston",
            display_name: "Greater Boston",
            personal_market_score: 0.78,
            objective_opportunity_score: 0.74,
            coverage: coverage("tier_3"),
            priority_market: priorityMarket(),
            match_notes: ["region_coverage_not_confident"],
          },
          {
            region_id: "greater_sf",
            display_name: "Greater SF",
            personal_market_score: 0.44,
            objective_opportunity_score: 0.28,
            coverage: coverage("tier_4"),
            match_notes: ["region_coverage_not_confident"],
          },
        ],
        ranked_companies: [
          {
            company_id: "comp_a",
            company_name: "Acme AI",
            region_id: "greater_boston",
            region_display_name: "Greater Boston",
            personal_company_score: 0.72,
            role_fit: 0.7,
            industry_fit: 0.8,
            prestige_fit: 0.5,
            brand_fit: 0.4,
            match_notes: ["region_coverage_not_confident"],
          },
        ],
      },
      warnings: [coverageWarning("greater_boston")],
    };
  }
  return { data: null };
}

function stubPublicFetch() {
  const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(async (input) => {
    const payload = responsePayloadFor(input);
    return new Response(JSON.stringify(envelope(payload.data, payload.warnings)), {
      headers: { "Content-Type": "application/json" },
      status: 200,
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderAt(path: string) {
  window.history.pushState(null, "", path);
  return render(
    <FrontendAuthProvider>
      <App />
    </FrontendAuthProvider>,
  );
}

describe("public demo routes", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    window.history.pushState(null, "", "/");
  });

  test("landing page route renders disclosure and public links", () => {
    renderAt("/");

    expect(screen.getByRole("heading", { name: "Job Market Intelligence" })).toBeTruthy();
    expect(screen.getByText("Public demo disclosure")).toBeTruthy();
    expect(screen.getAllByText(/Coverage is partial/i).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Enter demo" }).some((link) =>
      link.getAttribute("href") === "/markets"
    )).toBe(true);
    expect(screen.getAllByRole("link", { name: "Data limitations" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Privacy" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Terms and disclaimer" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Source explanation" }).length).toBeGreaterThan(0);
  });

  test("demo CTA routes into the existing markets experience", async () => {
    stubPublicFetch();
    renderAt("/");

    fireEvent.click(screen.getAllByRole("link", { name: "Enter demo" })[0]);

    expect(window.location.pathname).toBe("/markets");
    expect(await screen.findByRole("heading", { name: "Explore markets" })).toBeTruthy();
  });

  test("region page renders read-only visualization and unsupported precision states", async () => {
    stubPublicFetch();
    renderAt("/markets/region/greater_boston");

    expect(await screen.findByText("Canonical/default score breakdown")).toBeTruthy();
    expect(screen.getAllByText("Coverage: Tier 2 - partial but useful market").length).toBeGreaterThan(0);
    expect(screen.getByText("Heuristic coverage score: 62%")).toBeTruthy();
    expect(screen.getAllByText("Coverage is partial; compare this market with caution.").length).toBeGreaterThan(0);
    expect(screen.getByText("Sector coverage")).toBeTruthy();
    expect(screen.getAllByText("Sector level: Watchlist").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Coverage: Tier 3 - watchlist / emerging market").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Priority #10: Boston").length).toBeGreaterThan(0);
    expect((await screen.findAllByText("Real imported data")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Fresh").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Current snapshot").length).toBeGreaterThan(0);
    expect(screen.getByText("Unsupported visualization state")).toBeTruthy();
    expect(screen.getByText("Historical trend view")).toBeTruthy();
    expect(screen.getByText("Opportunity heatmap")).toBeTruthy();
  });

  test("explore markets renders coverage labels for fully covered and placeholder markets", async () => {
    stubPublicFetch();
    renderAt("/markets");

    expect((await screen.findAllByText("Coverage: Tier 1 - fully covered market")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Coverage: Tier 4 - placeholder only").length).toBeGreaterThan(0);
    expect(screen.getByText(/Coverage labels separately show/i)).toBeTruthy();
  });

  test("comparison renders weak coverage warnings beside region results", async () => {
    stubPublicFetch();
    renderAt("/markets/compare?region_a=greater_boston&region_b=greater_sf");

    expect(await screen.findByRole("heading", { name: "Coverage context" })).toBeTruthy();
    expect(screen.getAllByText("Coverage: Tier 3 - watchlist / emerging market").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Coverage: Tier 4 - placeholder only").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/not covered enough for confident recommendations/i).length).toBeGreaterThan(0);
  });

  test("personalized discovery renders coverage warnings and cautious ranked labels", async () => {
    stubPublicFetch();
    renderAt("/markets/discovery");

    fireEvent.click(await screen.findByRole("button", { name: "Run discovery" }));

    expect(await screen.findByRole("heading", { name: "Ranked regions" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Ranked company-region pairs" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Recommended regions" })).toBeNull();
    expect(screen.getAllByText("Coverage: Tier 3 - watchlist / emerging market").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Coverage: Tier 4 - placeholder only").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/not covered enough for confident recommendations/i).length).toBeGreaterThan(0);
  });

  test("company geography keeps coverage separate from freshness and sector coverage", async () => {
    stubPublicFetch();
    renderAt("/markets/company/comp_a");

    expect(await screen.findByRole("heading", { name: "Observed region signals" })).toBeTruthy();
    expect(screen.getAllByText("Coverage: Tier 2 - partial but useful market").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Coverage: Tier 4 - placeholder only").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Sector coverage").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Real imported data").length).toBeGreaterThan(0);
  });

  test("older region responses without coverage render fallback without sector noise", async () => {
    stubPublicFetch();
    renderAt("/markets/region/legacy_market");

    expect(await screen.findByRole("heading", { name: "Legacy Market" })).toBeTruthy();
    expect(screen.getByText("Coverage unavailable")).toBeTruthy();
    expect(screen.getByText("Coverage metadata is unavailable for this response.")).toBeTruthy();
    expect(screen.queryByText("Sector coverage")).toBeNull();
  });

  test.each([
    ["/data-limitations", "Data limitations", /Scores are derived signals/i],
    ["/privacy", "Privacy notice", /Public browsing/i],
    ["/terms", "Terms and disclaimer", /No guarantee/i],
    ["/sources", "Source explanation", /Imported or source data/i],
  ])("%s renders public legal content", (path, heading, marker) => {
    renderAt(path);

    expect(screen.getByRole("heading", { name: heading })).toBeTruthy();
    expect(screen.getByText(marker)).toBeTruthy();
  });
});
