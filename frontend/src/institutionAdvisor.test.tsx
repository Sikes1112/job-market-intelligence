// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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

function advisorPayload() {
  return {
    organization_id: "org_demo",
    generated_at: "2026-05-26T12:00:00Z",
    comparison_type: "regions",
    compared_items: [{
      item_id: "greater_boston",
      label: "Greater Boston",
      item_type: "region",
      demand_signals: {
        active_posting_count_now: 12,
        currently_hiring_company_count: 3,
      },
      coverage: {
        label: "Partial",
        quality_score: 44,
      },
      explanation_summary: [
        "Region comparison uses existing region search, coverage, hiring, and entry-level signals.",
      ],
      warnings: ["Greater Boston has limited coverage."],
      metadata: {
        region_id: "greater_boston",
      },
    }],
    guidance: [
      "Use region comparisons to frame tradeoffs, not to guarantee outcomes.",
    ],
    tradeoffs: [{
      category: "market_signal",
      summary: "Greater Boston has stronger current posting evidence.",
      evidence_level: "directional",
    }],
    coverage_warnings: ["Greater Boston has limited coverage."],
    data_freshness: {
      freshness_status: "unknown",
      generated_at: "2026-05-26T12:00:00Z",
    },
    limitations: [
      "Advisor tools are decision-support surfaces and do not guarantee student outcomes.",
    ],
    privacy_notes: [
      "Student-specific advising remains disabled until explicit scoped consent exists.",
    ],
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
  if (value === "/api/institutions/organizations/org_demo/advisor/compare-regions") {
    return advisorPayload();
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

describe("institutional advisor tools UI", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    window.history.pushState(null, "", "/");
  });

  test("advisor route runs a guidance comparison without student-level fields", async () => {
    const fetchMock = stubFetch();
    window.history.pushState(null, "", "/markets/institution/advisor");

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Advisor Tools" })).toBeTruthy();
    expect(await screen.findByText("Demo Career Center")).toBeTruthy();
    expect(screen.getByLabelText("Comparison type")).toBeTruthy();
    expect(screen.getByText(/do not expose raw student searches/i)).toBeTruthy();
    expect(screen.getByText(/Student-specific advising remains disabled/i)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Run advisor comparison" }));

    expect(await screen.findByRole("heading", { name: "Advisor Guidance Results" })).toBeTruthy();
    expect(screen.getByText("Greater Boston")).toBeTruthy();
    expect(screen.getByText(/stronger current posting evidence/i)).toBeTruthy();
    expect(screen.getAllByText(/Coverage warning/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/decision-support surfaces/i)).toBeTruthy();
    expect(document.body.textContent ?? "").not.toContain("student_user_id");

    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url]) =>
        url === "/api/institutions/organizations/org_demo/advisor/compare-regions"
      )).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url]) =>
      url === "/api/institutions/organizations/org_demo/dashboard"
    )).toBe(false);
    const advisorCall = fetchMock.mock.calls.find(([url]) =>
      url === "/api/institutions/organizations/org_demo/advisor/compare-regions"
    );
    expect((advisorCall?.[1] as RequestInit).headers).toMatchObject({
      "Authorization": "Bearer institution-token",
    });
    const body = JSON.parse(String((advisorCall?.[1] as RequestInit).body));
    expect(body).toEqual({
      regions: ["greater_boston", "sf_bay_area"],
      role_context: "software engineering",
      industry_context: "software",
      career_stage: "entry_level",
    });
    expect(JSON.stringify(body)).not.toContain("student");
  });
});
