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
    user: { email: "paid@example.com", sub: "auth0|paid" },
    login: vi.fn(async () => undefined),
    logout: vi.fn(),
    getAccessTokenSilently: vi.fn(async () => "account-token"),
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

function plansPayload() {
  return {
    plans: [
      {
        plan_key: "free",
        display_name: "Free",
        buyer_kind: "individual",
        buyer_segment: null,
        billing_interval: "free",
        intended_audience: ["students"],
        included_feature_keys: ["basic_region_exploration", "basic_recommendation_preview"],
        usage_limits: [{
          feature_key: "limited_comparisons",
          limit: 3,
          unit: "per_month",
          description: "Free users can compare a few markets each month.",
        }],
        upgrade_plan_keys: ["individual_monthly"],
        price: {
          price_config_key: null,
          placeholder_amount_cents: 0,
          currency: "USD",
          final_price: false,
          note: "Free access.",
        },
      },
      {
        plan_key: "individual_monthly",
        display_name: "Individual Monthly",
        buyer_kind: "individual",
        buyer_segment: null,
        billing_interval: "monthly",
        intended_audience: ["early_career_job_seekers"],
        included_feature_keys: [
          "basic_region_exploration",
          "basic_recommendation_preview",
          "saved_watchlists",
          "alerts",
          "full_report_generation",
        ],
        usage_limits: [{
          feature_key: "full_report_generation",
          limit: 3,
          unit: "per_month",
          description: "Report generation test limit.",
        }],
        upgrade_plan_keys: [],
        price: {
          price_config_key: "TEST_INDIVIDUAL_MONTHLY",
          placeholder_amount_cents: 1900,
          currency: "USD",
          final_price: false,
          note: "Placeholder test value.",
        },
      },
    ],
  };
}

function featuresPayload() {
  const feature = (feature_key: string, boundary: "free" | "paid", display_name: string) => ({
    feature_key,
    boundary,
    display_name,
    description: display_name,
    boundary_rationale: boundary === "free"
      ? "Free users still receive useful basic guidance."
      : "Paid plans add workflow and report value.",
    trust_constraint: "Does not alter recommendation ranking.",
    exposes_core_recommendation_conclusion: feature_key === "basic_recommendation_preview",
    recommendation_influence: "none",
  });
  return {
    features: [
      feature("basic_region_exploration", "free", "Basic region exploration"),
      feature("basic_recommendation_preview", "free", "Basic recommendation preview"),
      feature("limited_comparisons", "free", "Limited comparisons"),
      feature("saved_watchlists", "paid", "Saved watchlists"),
      feature("alerts", "paid", "Alerts"),
      feature("full_report_generation", "paid", "Full report generation"),
      feature("exportable_strategy_plans", "paid", "Exportable strategy plans"),
      feature("full_market_coverage", "paid", "Full market coverage"),
    ],
  };
}

function reportsPayload() {
  return {
    reports: [{
      report_key: "personalized_market_strategy_report",
      display_name: "Personalized Market Strategy Report",
      intended_segments: ["early_career_job_seekers"],
      free_preview_available: true,
      preview_feature_key: "basic_recommendation_preview",
      paid_full_report_required: true,
      paid_full_report_feature_keys: ["full_report_generation"],
      included_sections: ["recommendation conclusion"],
      exportable: true,
      export_feature_key: "exportable_strategy_plans",
    }],
  };
}

function entitlementsPayload() {
  return {
    entitlements: {
      user_id: "user_paid",
      monetization_account_id: "monacct_paid",
      account_type: "individual",
      account_status: "active",
      plan_key: "individual_monthly",
      included_feature_keys: ["basic_recommendation_preview", "saved_watchlists", "alerts", "full_report_generation"],
      usage_limits: [{
        feature_key: "full_report_generation",
        limit: 3,
        unit: "per_month",
        description: "Report generation test limit.",
      }],
      assignment_source: "test_fixture",
      effective_at: "2026-05-26T00:00:00Z",
      expires_at: null,
      seat_limit: null,
      assigned_seats_count: null,
      safe_metadata: {},
    },
  };
}

function accountPayload() {
  return {
    account: {
      monetization_account_id: "monacct_paid",
      user_id: "user_paid",
      account_type: "individual",
      account_status: "active",
      assigned_seats_count: null,
      seat_limit: null,
      safe_metadata: {},
    },
    ...entitlementsPayload(),
  };
}

function accessPreviewPayload(input: RequestInfo | URL) {
  const value = typeof input === "string" ? input : input.toString();
  const params = new URLSearchParams(value.split("?")[1] ?? "");
  const featureKey = params.get("feature_key") ?? "full_report_generation";
  const allowed = featureKey !== "full_market_coverage";
  return {
    decision: {
      allowed,
      plan_key: "individual_monthly",
      feature_key: featureKey,
      reason: allowed
        ? `${featureKey} is included in individual_monthly.`
        : `${featureKey} is not included in individual_monthly.`,
      upgrade_plan_keys: allowed ? [] : ["individual_annual"],
      usage_limit: featureKey === "full_report_generation"
        ? {
            feature_key: "full_report_generation",
            limit: 3,
            unit: "per_month",
            description: "Report generation test limit.",
          }
        : null,
      remaining_usage: featureKey === "full_report_generation" ? 2 : null,
      account_status: "active",
    },
  };
}

function responseFor(input: RequestInfo | URL) {
  const value = typeof input === "string" ? input : input.toString();
  if (value === "/health") return { service: "test" };
  if (value === "/regions") return { regions: [] };
  if (value === "/regions/search") return { regions: [], count: 0 };
  if (value === "/monetization/plans") return plansPayload();
  if (value === "/monetization/features") return featuresPayload();
  if (value === "/monetization/reports") return reportsPayload();
  if (value === "/billing/status") {
    return {
      provider: "stripe",
      checkout_available: true,
      portal_available: false,
      checkout_plan_keys: ["individual_monthly"],
      disabled_reason: null,
    };
  }
  if (value === "/billing/checkout-session") {
    return {
      provider: "stripe",
      checkout_session_id: "cs_test_frontend",
      checkout_url: "https://checkout.stripe.test/session/cs_test_frontend",
      plan_key: "individual_monthly",
      access_granted: false,
    };
  }
  if (value === "/monetization/me") return accountPayload();
  if (value === "/monetization/entitlements") return entitlementsPayload();
  if (value === "/monetization/usage") {
    return {
      plan_key: "individual_monthly",
      account_status: "active",
      usage: [{
        usage_counter_id: "usage_report",
        monetization_account_id: "monacct_paid",
        feature_key: "full_report_generation",
        period_start: "2026-05-01T00:00:00Z",
        period_end: "2026-06-01T00:00:00Z",
        used_count: 1,
        limit_count: 3,
        reset_policy: "monthly",
        last_incremented_at: "2026-05-26T00:00:00Z",
      }],
    };
  }
  if (value.startsWith("/monetization/access-preview")) return accessPreviewPayload(input);
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

describe("account-aware monetization UI", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    window.history.pushState(null, "", "/");
  });

  test("plans page displays effective plan usage and account-aware access", async () => {
    const fetchMock = stubFetch();
    window.history.pushState(null, "", "/markets/plans");

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Current account access" })).toBeTruthy();
    await waitFor(() => {
      expect(screen.getAllByText("Individual Monthly").length).toBeGreaterThan(0);
    });
    expect(screen.getByText("Status: active")).toBeTruthy();
    expect(screen.getByText(/Full report generation: 2 remaining of 3 per month/i)).toBeTruthy();
    expect(screen.getAllByText(/full_report_generation is included in individual_monthly/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/View plans for Individual Annual/i).length).toBeGreaterThan(0);

    const protectedCalls = fetchMock.mock.calls.filter(([url]) =>
      String(url) === "/monetization/me"
      || String(url) === "/monetization/entitlements"
      || String(url) === "/monetization/usage"
      || String(url).startsWith("/monetization/access-preview")
    );
    expect(protectedCalls.some(([url]) => url === "/monetization/me")).toBe(true);
    expect(protectedCalls.some(([url]) => String(url).startsWith("/monetization/access-preview"))).toBe(true);
    expect(protectedCalls.every(([, init]) => {
      const headers = (init as RequestInit).headers as Record<string, string>;
      return headers.Authorization === "Bearer account-token";
    })).toBe(true);

    const pageText = document.body.textContent ?? "";
    expect(pageText).not.toMatch(/Buy now/i);
    expect(pageText).not.toMatch(/payment success/i);
    expect(pageText).not.toMatch(/Unlock the truth/i);
  });

  test("checkout action calls backend and redirects only with returned provider URL", async () => {
    const fetchMock = stubFetch();
    const redirects: string[] = [];
    const onRedirect = ((event: Event) => {
      redirects.push((event as CustomEvent<{ url: string }>).detail.url);
    }) as EventListener;
    window.addEventListener("jmi:billing-provider-redirect", onRedirect);
    window.history.pushState(null, "", "/markets/plans");

    render(<App />);

    const checkoutButton = await screen.findByRole("button", { name: "Start checkout" });
    fireEvent.click(checkoutButton);

    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url]) => url === "/billing/checkout-session")).toBe(true);
    });
    const checkoutCall = fetchMock.mock.calls.find(([url]) => url === "/billing/checkout-session");
    expect(checkoutCall).toBeTruthy();
    expect(JSON.parse(String((checkoutCall?.[1] as RequestInit).body))).toEqual({
      plan_key: "individual_monthly",
    });
    expect(redirects).toEqual(["https://checkout.stripe.test/session/cs_test_frontend"]);
    expect(document.body.textContent ?? "").not.toMatch(/payment success/i);

    window.removeEventListener("jmi:billing-provider-redirect", onRedirect);
  });
});
