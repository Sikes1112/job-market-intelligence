// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, test, vi } from "vitest";
import App from "./App";

const authState = vi.hoisted(() => ({
  value: {
    isConfigured: true,
    isAuthenticated: true,
    isLoading: false,
    error: null,
    user: { email: "advisor@example.com", sub: "auth0|advisor" },
    login: vi.fn(async () => undefined),
    logout: vi.fn(),
    getAccessTokenSilently: vi.fn(async () => "institution-token"),
  },
}));

vi.mock("./auth", () => ({
  useFrontendAuth: () => authState.value,
  FrontendAuthProvider: ({ children }: { children: ReactNode }) => children,
}));

function envelope(data: unknown) {
  return {
    status: "success",
    data,
    metadata: { state: "test", source_versions: {}, warnings: [] },
    error: null,
  };
}

function institutionOrganizationsPayload() {
  return {
    organizations: [{
      organization: {
        organization_id: "org_demo",
        name: "Demo Career Center",
        organization_type: "career_center",
        status: "active",
        created_at: "2026-05-26T00:00:00Z",
        updated_at: "2026-05-26T00:00:00Z",
      },
      membership: {
        organization_membership_id: "mem_demo_advisor",
        organization_id: "org_demo",
        user_id: "user_advisor",
        role: "ADVISOR",
        status: "active",
        created_at: "2026-05-26T00:00:00Z",
        updated_at: "2026-05-26T00:00:00Z",
      },
    }],
  };
}

function dashboardPayload() {
  return {
    organization_id: "org_demo",
    organization_name: "Demo Career Center",
    generated_at: "2026-05-26T12:00:00Z",
    minimum_group_size: 5,
    cohort_size: 28,
    visible_student_count: 28,
    popular_target_markets: [{
      label: "Greater Boston",
      count: 12,
      percentage: 42.9,
      category: "target_market",
      suppressed: false,
      suppression_reason: null,
      source_count: 12,
      coverage: null,
      confidence: "aggregate",
      metadata: { region_id: "greater_boston" },
    }, {
      label: "Other / insufficient sample size",
      count: null,
      percentage: null,
      category: "target_market",
      suppressed: true,
      suppression_reason: "minimum_group_size_not_met",
      source_count: 2,
      coverage: null,
      confidence: "suppressed",
      metadata: { minimum_group_size: 5 },
    }],
    role_interest_summary: [{
      label: "Product",
      count: 10,
      percentage: 35.7,
      category: "role_interest",
      suppressed: false,
      suppression_reason: null,
      source_count: 10,
      coverage: null,
      confidence: "aggregate",
      metadata: {},
    }],
    saved_company_summary: [{
      label: "Alpha Systems",
      count: 8,
      percentage: 28.6,
      category: "saved_company",
      suppressed: false,
      suppression_reason: null,
      source_count: 8,
      coverage: null,
      confidence: "aggregate",
      metadata: { company_id: "comp_alpha" },
    }],
    market_demand_trends: [{
      label: "Greater Boston",
      count: 36,
      percentage: null,
      category: "market_demand",
      suppressed: false,
      suppression_reason: null,
      source_count: 4,
      coverage: null,
      confidence: "medium",
      metadata: {
        region_id: "greater_boston",
        currently_hiring_company_count: 6,
        trend_signal: "increasing",
      },
    }],
    coverage_gaps: [{
      label: "Greater Boston",
      count: 12,
      percentage: null,
      category: "coverage_gap",
      suppressed: false,
      suppression_reason: null,
      source_count: 12,
      coverage: {
        tier: "tier_3",
        label: "Partial",
        quality_score: 44,
      },
      confidence: "Partial",
      metadata: { region_id: "greater_boston" },
    }],
    suppressed_categories: [{
      section: "popular_target_markets",
      suppressed_count: 2,
      suppression_reason: "minimum_group_size_not_met",
      minimum_group_size: 5,
    }],
    privacy_notes: [
      "Layer 16 cohort dashboards are aggregate-first.",
      "Low-sample categories are suppressed according to the configured minimum group threshold.",
    ],
    coverage_warnings: [
      "One or more visible target markets have limited coverage quality.",
    ],
    data_freshness: {
      generated_at: "2026-05-26T12:00:00Z",
      freshness_status: "unknown",
    },
  };
}

function responseFor(input: RequestInfo | URL) {
  const value = typeof input === "string" ? input : input.toString();
  if (value === "/health") return { service: "test" };
  if (value === "/regions") return { regions: [] };
  if (value === "/regions/search") return { regions: [], count: 0 };
  if (value === "/api/institutions/organizations/current") {
    return institutionOrganizationsPayload();
  }
  if (value === "/api/institutions/organizations/org_demo/dashboard") {
    return dashboardPayload();
  }
  if (value === "/me") return { user: { user_id: "user_advisor", status: "active" } };
  if (value === "/me/preferences") return {};
  if (value === "/me/saved-market-artifacts") return { saved_market_artifacts: [] };
  if (value === "/me/alerts?include_dismissed=false") return { alerts: [] };
  if (value === "/me/recommendation-snapshots") {
    return { personalized_recommendation_snapshots: [] };
  }
  if (value === "/monetization/me") return {};
  if (value === "/monetization/entitlements") return {};
  if (value === "/monetization/usage") return { usage: [] };
  if (value.startsWith("/monetization/access-preview")) {
    return {
      decision: {
        allowed: true,
        plan_key: "free",
        feature_key: "basic_recommendation_preview",
        reason: "Available in test.",
        upgrade_plan_keys: [],
        usage_limit: null,
        remaining_usage: null,
      },
    };
  }
  return {};
}

function stubFetch() {
  const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(async (input) =>
    new Response(JSON.stringify(envelope(responseFor(input))), {
      headers: { "Content-Type": "application/json" },
      status: 200,
    })
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("institutional dashboard UI", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    window.history.pushState(null, "", "/");
  });

  test("dashboard route renders aggregate sections and privacy metadata", async () => {
    const fetchMock = stubFetch();
    window.history.pushState(null, "", "/markets/institution");

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Institution Dashboard" })).toBeTruthy();
    expect(await screen.findByText("Demo Career Center")).toBeTruthy();
    expect(await screen.findByText("Popular Target Markets")).toBeTruthy();
    expect(screen.getByText("Role Interest Distribution")).toBeTruthy();
    expect(screen.getByText("Saved Company Trends")).toBeTruthy();
    expect(screen.getByText("Market Demand Trends")).toBeTruthy();
    expect(screen.getByText("Coverage Gaps")).toBeTruthy();
    expect(screen.getAllByText("Greater Boston").length).toBeGreaterThan(0);
    expect(screen.getByText("Product")).toBeTruthy();
    expect(screen.getByText("Alpha Systems")).toBeTruthy();
    expect(screen.getByText("Other / insufficient sample size")).toBeTruthy();
    expect(screen.getByText(/Low-sample categories are suppressed/i)).toBeTruthy();
    expect(screen.getByText(/Coverage warning/i)).toBeTruthy();
    expect(document.body.textContent ?? "").not.toContain("student_user_id");

    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url]) =>
        url === "/api/institutions/organizations/org_demo/dashboard"
      )).toBe(true);
    });
    const dashboardCall = fetchMock.mock.calls.find(([url]) =>
      url === "/api/institutions/organizations/org_demo/dashboard"
    );
    expect((dashboardCall?.[1] as RequestInit).headers).toMatchObject({
      "Authorization": "Bearer institution-token",
    });
  });
});
