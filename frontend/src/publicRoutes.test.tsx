// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import App from "./App";
import { FrontendAuthProvider } from "./auth";

function envelope(data: unknown) {
  return {
    status: "success",
    data,
    metadata: { state: "test", source_versions: {}, warnings: [] },
    error: null,
  };
}

function responseDataFor(input: RequestInfo | URL): unknown {
  const value = typeof input === "string" ? input : input.toString();

  if (value === "/health") return { service: "test" };
  if (value === "/regions") {
    return {
      regions: [
        {
          region_id: "greater_boston",
          display_name: "Greater Boston",
          region_type: "greater_region",
          parent_region_id: null,
          labor_market_group: "boston",
          state: "fresh",
        },
      ],
    };
  }
  if (value === "/regions/greater_boston") {
    return {
      region_id: "greater_boston",
      display_name: "Greater Boston",
      region_type: "greater_region",
      parent_region_id: null,
      labor_market_group: "boston",
      summary: { eligible_company_count: 1 },
      scores: {
        structural_ecosystem_score: 0.7,
        live_market_score: 0.6,
        objective_opportunity_score: 0.74,
        raw_total_score: 0.68,
        general_density_score: 0.5,
        tech_market_density_score: 0.55,
        early_career_accessibility_score: 0.66,
        score_ruleset_version: "marketscore_v1",
      },
      top_companies_present: [],
      top_companies_hiring: [],
      entry_level_summary: {},
      major_tech_summary: { count: 0, company_ids: [] },
      mag7_summary: { count: 0, company_ids: [] },
    };
  }
  if (value.startsWith("/regions/greater_boston/sources")) {
    return {
      subject_type: "region",
      subject_id: "greater_boston",
      freshness: {
        freshness_status: "fresh",
        data_basis: "real_imported",
        last_collected_at: null,
        source_count: 1,
        low_confidence_warning: null,
      },
      sources: [],
    };
  }
  if (value.startsWith("/regions/search")) {
    return {
      regions: [
        {
          region_id: "greater_boston",
          name: "Greater Boston",
          region_name: "greater_boston",
          region_type: "greater_region",
          parent_region_id: null,
          labor_market_group: "boston",
          opportunity_score: 0.74,
          freshness: {
            freshness_status: "fresh",
            data_basis: "real_imported",
            last_collected_at: null,
            source_count: 1,
            low_confidence_warning: null,
          },
          has_real_data: true,
        },
      ],
    };
  }
  if (value.startsWith("/companies/search")) return { companies: [] };
  return null;
}

function stubPublicFetch() {
  const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(async (input) =>
    new Response(JSON.stringify(envelope(responseDataFor(input))), {
      headers: { "Content-Type": "application/json" },
      status: 200,
    })
  );
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
    expect(screen.getAllByText("Current snapshot").length).toBeGreaterThan(0);
    expect(screen.getByText("Unsupported visualization state")).toBeTruthy();
    expect(screen.getByText("Historical trend view")).toBeTruthy();
    expect(screen.getByText("Opportunity heatmap")).toBeTruthy();
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
