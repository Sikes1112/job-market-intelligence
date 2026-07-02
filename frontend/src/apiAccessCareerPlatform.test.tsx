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
    user: { email: "api-access@example.com", sub: "auth0|api_access" },
    login: vi.fn(async () => undefined),
    logout: vi.fn(),
    getAccessTokenSilently: vi.fn(async () => "api-access-token"),
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
    metadata: { state: "fresh", source_versions: {}, warnings: [] },
    error: null,
  };
}

function apiClientPayload() {
  return {
    api_client_id: "apic_demo",
    display_name: "Read-only market intelligence client",
    created_by_user_id: "user_demo",
    organization_id: null,
    status: "active",
    policy: {
      scopes: ["region:read", "company_geography:read", "market_signal:read"],
      organization_id: null,
      rate_limit_count: 60,
      rate_limit_window_seconds: 3600,
      allowed_origins: [],
    },
    keys: [],
    created_at: "2026-06-16T12:00:00Z",
    updated_at: "2026-06-16T12:00:00Z",
  };
}

function platformRegistry() {
  return {
    platforms: [
      {
        platform: "linkedin",
        display_name: "LinkedIn",
        risk_posture: "deep_link_only",
        allowed_capabilities: ["manual_company_search", "manual_export"],
        blocked_capabilities: ["scraping", "automation", "application_submission"],
        notes: [],
        manual_only: true,
        automation_performed: false,
        ats_state_created: false,
      },
      {
        platform: "handshake",
        display_name: "Handshake",
        risk_posture: "export_only",
        allowed_capabilities: ["manual_employer_lookup", "manual_export"],
        blocked_capabilities: ["automation", "login_crawling", "application_submission"],
        notes: [],
        manual_only: true,
        automation_performed: false,
        ats_state_created: false,
      },
    ],
  };
}

function responseFor(input: RequestInfo | URL, init?: RequestInit) {
  const value = typeof input === "string" ? input : input.toString();
  const method = init?.method ?? "GET";
  if (value === "/health") return { service: "test" };
  if (value === "/regions") return { regions: [] };
  if (value === "/regions/search") return { regions: [], count: 0 };
  if (value === "/me") return { user: { user_id: "user_demo", status: "active" }, profile: {} };
  if (value === "/me/preferences") return {};
  if (value === "/me/saved-market-artifacts") return { saved_market_artifacts: [] };
  if (value === "/me/alerts?include_dismissed=false") return { alerts: [] };
  if (value === "/me/recommendation-snapshots") {
    return { personalized_recommendation_snapshots: [] };
  }
  if (value === "/monetization/me") return {};
  if (value === "/monetization/entitlements") return {};
  if (value === "/monetization/usage") return { usage: [] };
  if (value === "/api/integrations/career-platforms") return platformRegistry();
  if (value === "/api/integrations/api-clients" && method === "POST") {
    return { api_client: apiClientPayload() };
  }
  if (value === "/api/integrations/api-clients") {
    return { api_clients: [apiClientPayload()] };
  }
  if (value === "/api/integrations/api-clients/apic_demo/keys" && method === "POST") {
    return {
      api_key: {
        api_key_id: "apikey_demo",
        key_prefix: "jmi_live_abc",
        display_key: "jmi_live_abc...xyz",
        raw_key: "jmi_live_abcdefxyz",
        revealed_once: true,
      },
    };
  }
  if (value === "/api/integrations/api-clients/apic_demo/usage") return { usage: [] };
  if (value === "/api/integrations/career-platform-exports" && method === "POST") {
    return {
      export: {
        career_platform_export_id: "cpe_demo",
        platform: "linkedin",
        risk_posture: "deep_link_only",
        export_mode: "manual_lookup_export",
        rows: [],
        manual_only: true,
        automation_performed: false,
        ats_state_created: false,
        application_status_created: false,
        recruiter_outreach_created: false,
        created_at: "2026-06-16T12:00:00Z",
      },
    };
  }
  return {};
}

function stubFetch() {
  const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(async (input, init) =>
    new Response(JSON.stringify(envelope(responseFor(input, init))), {
      headers: { "Content-Type": "application/json" },
      status: 200,
    })
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("API access and career platform UI", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    window.history.pushState(null, "", "/");
  });

  test("renders controlled API and manual platform actions safely", async () => {
    const fetchMock = stubFetch();
    window.history.pushState(null, "", "/markets/account");

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Controlled API Access" })).toBeTruthy();
    expect(await screen.findByRole("heading", { name: "Career Platform Registry" })).toBeTruthy();
    expect(screen.getByText("No scraping")).toBeTruthy();
    expect(screen.getByText("No application submission")).toBeTruthy();
    expect(screen.getByText("No ATS pipeline")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Create API client" }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) =>
        url === "/api/integrations/api-clients"
        && (init as RequestInit).method === "POST"
      )).toBe(true);
    });
    const createClientCall = fetchMock.mock.calls.find(([url, init]) =>
      url === "/api/integrations/api-clients"
      && (init as RequestInit).method === "POST"
    );
    expect((createClientCall?.[1] as RequestInit).headers).toMatchObject({
      "Authorization": "Bearer api-access-token",
    });
    expect(JSON.parse(String((createClientCall?.[1] as RequestInit).body))).toMatchObject({
      display_name: "Read-only market intelligence client",
      scopes: ["region:read", "company_geography:read", "market_signal:read"],
      rate_limit_count: 60,
      rate_limit_window_seconds: 3600,
    });

    expect(
      (await screen.findAllByText("region:read, company_geography:read, market_signal:read")).length,
    ).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Create key" }));
    expect(await screen.findByText("jmi_live_abcdefxyz")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "LinkedIn manual search" }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) =>
        url === "/api/integrations/career-platform-exports"
        && (init as RequestInit).method === "POST"
      )).toBe(true);
    });
    expect(await screen.findByText(/automation false · ATS false/i)).toBeTruthy();
  });
});
