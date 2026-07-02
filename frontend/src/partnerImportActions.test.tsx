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
    user: { email: "imports@example.com", sub: "auth0|imports" },
    login: vi.fn(async () => undefined),
    logout: vi.fn(),
    getAccessTokenSilently: vi.fn(async () => "import-token"),
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

function partnerImport(status = "validated") {
  return {
    import_batch_id: "pib_demo",
    organization_id: "org_demo",
    uploaded_by_user_id: "user_demo",
    source_type: "local_employer_list",
    status,
    import_format: "csv",
    source_attribution: "Career center partner list",
    original_filename: "partner-import.csv",
    record_count: 1,
    accepted_record_count: 1,
    quarantined_record_count: 0,
    rejected_record_count: 0,
    validation_result: {
      status,
      record_count: 1,
      accepted_record_count: 1,
      quarantined_record_count: 0,
      rejected_record_count: 0,
      warning_count: 0,
      warnings: [],
      required_fields_missing: [],
      unsupported_fields: [],
      has_blocking_privacy_issue: false,
      has_blocking_source_issue: false,
      can_accept: true,
    },
    receipt: {
      import_batch_id: "pib_demo",
      organization_id: "org_demo",
      uploaded_by_user_id: "user_demo",
      source_type: "local_employer_list",
      status,
      source_attribution: "Career center partner list",
      validation_result: {
        status,
        record_count: 1,
        accepted_record_count: 1,
        quarantined_record_count: 0,
        rejected_record_count: 0,
        warning_count: 0,
        warnings: [],
        required_fields_missing: [],
        unsupported_fields: [],
        has_blocking_privacy_issue: false,
        has_blocking_source_issue: false,
        can_accept: true,
      },
      permission_decision: {
        allowed: true,
        reason: "ok",
        boundary: "organization_membership",
        owner_user_id: "user_demo",
        organization_id: "org_demo",
      },
      partner_contributed_evidence: true,
      canonical_truth: false,
      canonical_identity_overwrite_performed: false,
      canonical_region_overwrite_performed: false,
      product_scoring_override_performed: false,
      governance_warnings_removed: false,
      student_level_pii_imported: false,
      individual_outcome_records_imported: false,
      sensitive_demographics_imported: false,
      internal_only_fields_exposed: false,
      limitations: ["Partner imports are contributed evidence, not canonical product truth."],
      governance_warnings: [],
      created_at: "2026-06-16T12:00:00Z",
    },
    governance_warnings: [],
    records: [],
    preview_records: [{
      record_index: 0,
      decision: "accept",
      partner_contributed_evidence: true,
      canonical_truth: false,
      partner_payload: {
        marker: "partner_contributed_evidence",
        employer_name: "Alpha Systems",
      },
    }],
    created_at: "2026-06-16T12:00:00Z",
    updated_at: "2026-06-16T12:00:00Z",
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
  if (value === "/api/institutions/organizations/current") {
    return {
      organizations: [{
        organization: {
          organization_id: "org_demo",
          name: "Demo Career Center",
          organization_type: "career_center",
          status: "active",
        },
        membership: {
          organization_membership_id: "mem_demo",
          organization_id: "org_demo",
          user_id: "user_demo",
          role: "ORG_ADMIN",
          status: "active",
        },
      }],
    };
  }
  if (value === "/api/integrations/partner-imports?organization_id=org_demo") {
    return { imports: [] };
  }
  if (value === "/api/integrations/partner-imports" && method === "POST") {
    return { partner_import: partnerImport() };
  }
  if (value === "/api/integrations/partner-imports/pib_demo/accept" && method === "POST") {
    return { partner_import: partnerImport("accepted") };
  }
  if (value === "/api/integrations/partner-imports/pib_demo/receipt") {
    return { receipt: partnerImport("accepted").receipt };
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

describe("partner import center UI", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    window.history.pushState(null, "", "/");
  });

  test("renders import governance actions safely", async () => {
    const fetchMock = stubFetch();
    window.history.pushState(null, "", "/markets/institution/imports/org_demo");

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Partner Import Center" })).toBeTruthy();
    expect(screen.getByText(/partner-contributed evidence, not canonical truth/i)).toBeTruthy();
    expect(screen.getByText(/cannot overwrite company identity/i)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Upload and validate" }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) =>
        url === "/api/integrations/partner-imports"
        && (init as RequestInit).method === "POST"
      )).toBe(true);
    });
    const uploadCall = fetchMock.mock.calls.find(([url]) => url === "/api/integrations/partner-imports");
    expect((uploadCall?.[1] as RequestInit).headers).toMatchObject({
      "Authorization": "Bearer import-token",
    });
    expect(JSON.parse(String((uploadCall?.[1] as RequestInit).body))).toMatchObject({
      organization_id: "org_demo",
      source_type: "local_employer_list",
      import_format: "csv",
      source_attribution: "Career center partner list",
    });
    expect(await screen.findByText("Partner-contributed")).toBeTruthy();
    expect(screen.getAllByText("Canonical truth false").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Accept evidence" }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) =>
        url === "/api/integrations/partner-imports/pib_demo/accept"
        && (init as RequestInit).method === "POST"
      )).toBe(true);
    });

    fireEvent.click(screen.getAllByRole("button", { name: "Receipt" })[0]);
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url]) =>
        url === "/api/integrations/partner-imports/pib_demo/receipt"
      )).toBe(true);
    });
    expect(await screen.findByText(/Internal fields exposed false/i)).toBeTruthy();
  });
});
