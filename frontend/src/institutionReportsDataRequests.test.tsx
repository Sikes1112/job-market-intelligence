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
    user: { email: "admin@example.com", sub: "auth0|admin" },
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
        organization_membership_id: "mem_demo_admin",
        organization_id: "org_demo",
        user_id: "user_admin",
        role: "ORG_ADMIN",
        status: "active",
        created_at: "2026-05-26T00:00:00Z",
        updated_at: "2026-05-26T00:00:00Z",
      },
    }],
  };
}

function reportPayload() {
  return {
    report_id: "instreport_demo",
    organization_id: "org_demo",
    report_type: "career_services",
    title: "Demo Career Center Career Services Report",
    generated_at: "2026-05-26T12:00:00Z",
    generated_by_user_id: "user_admin",
    date_range: null,
    minimum_group_size: 5,
    cohort_size: 28,
    sections: [{
      section_id: "career_interests",
      title: "Student Career Interest Aggregates",
      summary: "Visible role and market interest patterns for career services planning.",
      findings: ["2 visible role interest summary aggregate(s) met the privacy threshold."],
      metrics: {
        role_interest_summary: [{
          label: "Product",
          count: 10,
          suppressed: false,
        }],
      },
      warnings: ["Some cohort categories were withheld."],
      suppressions: [{
        section: "role_interest_summary",
        suppressed_count: 1,
        suppression_reason: "minimum_group_size_not_met",
        minimum_group_size: 5,
      }],
      limitations: [],
      recommended_actions: ["Use visible aggregate interests to prioritize workshops."],
    }],
    privacy_suppressions: [{
      section: "role_interest_summary",
      suppressed_count: 1,
      suppression_reason: "minimum_group_size_not_met",
      minimum_group_size: 5,
    }],
    coverage_warnings: ["Coverage warning for report test."],
    data_freshness: { freshness_status: "unknown" },
    limitations: ["PDF, CSV, PowerPoint, email delivery, and scheduled report workflows are deferred."],
    recommended_actions: ["Review privacy suppressions before sharing report conclusions."],
    export_status: "not_generated",
    export_options: { pdf: "deferred", csv: "deferred", powerpoint: "deferred" },
    privacy_notes: [
      "Layer 16 institutional reports are aggregate-first and privacy-aware.",
    ],
  };
}

function reportListPayload() {
  const report = reportPayload();
  return {
    reports: [{
      report_id: report.report_id,
      organization_id: "org_demo",
      report_type: "career_services",
      title: report.title,
      generated_at: report.generated_at,
      generated_by_user_id: "user_admin",
      minimum_group_size: 5,
      cohort_size: 28,
      status: "generated",
      privacy_summary: { suppression_count: 1 },
      coverage_summary: { coverage_warning_count: 1 },
    }],
  };
}

function dataRequestPayload() {
  return {
    data_request_id: "instdatareq_demo",
    organization_id: "org_demo",
    requester_user_id: "user_admin",
    request_type: "organization_export",
    subject_type: "organization",
    subject_user_id: null,
    status: "pending",
    reason: "annual review",
    created_at: "2026-05-26T12:00:00Z",
    updated_at: "2026-05-26T12:00:00Z",
    resolved_at: null,
    metadata: { automation_executed: false },
    execution_note: "Request record created only; destructive deletion is not executed.",
  };
}

function responseFor(input: RequestInfo | URL, init?: RequestInit) {
  const value = typeof input === "string" ? input : input.toString();
  const method = init?.method ?? "GET";
  if (value === "/health") return { service: "test" };
  if (value === "/regions") return { regions: [] };
  if (value === "/regions/search") return { regions: [], count: 0 };
  if (value === "/api/institutions/organizations/current") {
    return institutionOrganizationsPayload();
  }
  if (value === "/api/institutions/organizations/org_demo/reports") {
    return method === "POST" ? { report: reportPayload() } : reportListPayload();
  }
  if (value === "/api/institutions/organizations/org_demo/data-requests") {
    return method === "POST"
      ? { data_request: dataRequestPayload() }
      : { data_requests: [dataRequestPayload()] };
  }
  if (value === "/me") return { user: { user_id: "user_admin", status: "active" } };
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
  const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(async (input, init) =>
    new Response(JSON.stringify(envelope(responseFor(input, init))), {
      headers: { "Content-Type": "application/json" },
      status: 200,
    })
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("institutional reports and data requests UI", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    window.history.pushState(null, "", "/");
  });

  test("reports route generates and renders aggregate report details", async () => {
    const fetchMock = stubFetch();
    window.history.pushState(null, "", "/markets/institution/reports");

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Institutional Reports" })).toBeTruthy();
    expect(screen.getByLabelText("Report type")).toBeTruthy();
    expect(screen.getByText(/PDF, CSV, PowerPoint/i)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Generate report" }));

    expect(await screen.findByRole("heading", {
      name: "Demo Career Center Career Services Report",
    })).toBeTruthy();
    expect(screen.getByText("Student Career Interest Aggregates")).toBeTruthy();
    expect(screen.getByText(/Coverage warning for report test/i)).toBeTruthy();
    expect(screen.getAllByText(/aggregate-first and privacy-aware/i).length).toBeGreaterThan(0);
    expect(document.body.textContent ?? "").not.toContain("student_user_id");

    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) =>
        url === "/api/institutions/organizations/org_demo/reports"
        && (init as RequestInit).method === "POST"
      )).toBe(true);
    });
    const reportCall = fetchMock.mock.calls.find(([url, init]) =>
      url === "/api/institutions/organizations/org_demo/reports"
      && (init as RequestInit).method === "POST"
    );
    expect((reportCall?.[1] as RequestInit).headers).toMatchObject({
      "Authorization": "Bearer institution-token",
    });
    expect(JSON.parse(String((reportCall?.[1] as RequestInit).body))).toEqual({
      report_type: "career_services",
      minimum_group_size: 5,
    });
  });

  test("data request route submits auditable non-executing request record", async () => {
    const fetchMock = stubFetch();
    window.history.pushState(null, "", "/markets/institution/data-requests");

    render(<App />);

    expect(await screen.findByRole("heading", {
      name: "Institutional Data Requests",
    })).toBeTruthy();
    expect(screen.getByLabelText("Data request type")).toBeTruthy();
    expect(screen.getByText(/do not automatically execute destructive deletion/i)).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Reason"), {
      target: { value: "annual review" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Submit request record" }));

    expect(await screen.findByText(/Created Organization Export request/i)).toBeTruthy();
    expect(screen.getAllByText(/destructive deletion/i).length).toBeGreaterThan(0);
    expect(document.body.textContent ?? "").not.toContain("student_user_id");

    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) =>
        url === "/api/institutions/organizations/org_demo/data-requests"
        && (init as RequestInit).method === "POST"
      )).toBe(true);
    });
    const dataRequestCall = fetchMock.mock.calls.find(([url, init]) =>
      url === "/api/institutions/organizations/org_demo/data-requests"
      && (init as RequestInit).method === "POST"
    );
    expect((dataRequestCall?.[1] as RequestInit).headers).toMatchObject({
      "Authorization": "Bearer institution-token",
    });
    expect(JSON.parse(String((dataRequestCall?.[1] as RequestInit).body))).toEqual({
      request_type: "organization_export",
      subject_type: "organization",
      subject_user_id: null,
      reason: "annual review",
    });
  });
});
