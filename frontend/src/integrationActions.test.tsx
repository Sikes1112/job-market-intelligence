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
    user: { email: "integration@example.com", sub: "auth0|integration" },
    login: vi.fn(async () => undefined),
    logout: vi.fn(),
    getAccessTokenSilently: vi.fn(async () => "integration-token"),
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

function regionPayload() {
  return {
    region_id: "greater_boston",
    display_name: "Greater Boston",
    region_type: "greater_region",
    parent_region_id: null,
    labor_market_group: "northeast",
    priority_market: null,
    coverage: { tier: "tier_3", label: "Partial coverage", heuristic: true },
    sector_coverage: {},
    summary: {
      eligible_company_count: 1,
      major_tech_count: 0,
      mag7_count: 0,
      present_company_count: 1,
      currently_hiring_company_count: 1,
    },
    scores: {
      structural_ecosystem_score: 0.7,
      live_market_score: 0.6,
      objective_opportunity_score: 0.8,
      raw_total_score: 0.75,
      general_density_score: 0.65,
      tech_market_density_score: 0.7,
      early_career_accessibility_score: 0.85,
    },
    top_companies_present: [],
    top_companies_hiring: [],
    entry_level_summary: {
      internship_count_total: 4,
      coop_count_total: 1,
      entry_level_full_time_count_total: 5,
      formal_early_career_program_count: 1,
      average_entry_level_access_score: 0.82,
      pairs_with_entry_level_access: 1,
    },
    major_tech_summary: { count: 0, company_ids: [] },
    mag7_summary: { count: 0, company_ids: [] },
  };
}

function integrationExportPayload(body: Record<string, unknown>) {
  return {
    export: {
      export_id: "intexp_demo",
      product_object_type: body.product_object_type,
      product_object_id: body.product_object_id,
      export_format: body.export_format,
      destination: body.export_format === "csv" ? "csv" : "google_sheets",
      capability: body.export_format === "csv" ? "export_file" : "prepared_payload",
      risk_posture: body.export_format === "csv" ? "local_download_only" : "prepared_no_sync",
      status: "created",
      filename: body.export_format === "csv" ? "greater-boston.csv" : null,
      content_type: body.export_format === "csv" ? "text/csv" : null,
      payload: { external_write_performed: false, live_sync_enabled: false },
      receipt: {
        integration_id: "intexp_demo",
        destination: body.export_format === "csv" ? "csv" : "google_sheets",
        capability: body.export_format === "csv" ? "export_file" : "prepared_payload",
        risk_posture: body.export_format === "csv" ? "local_download_only" : "prepared_no_sync",
        status: "created",
        external_write_performed: false,
        live_sync_enabled: false,
        oauth_performed: false,
        two_way_sync_enabled: false,
        product_authority_retained: true,
        permission_decision: {
          allowed: true,
          reason: "ok",
          boundary: "current_user",
          owner_user_id: "user_demo",
          organization_id: null,
        },
        provenance: {
          product_object_type: body.product_object_type,
          product_object_id: body.product_object_id,
          product_object_label: "Greater Boston",
          generated_at: "2026-06-16T12:00:00Z",
          generated_by_user_id: "user_demo",
          organization_id: null,
          freshness_status: "fresh",
          freshness_as_of: null,
          confidence_label: "partial",
          evidence_basis: ["region_output"],
          source_object_version: null,
          limitations: [],
          governance_warnings: [],
        },
        limitations: [],
        governance_warnings: [],
      },
      created_at: "2026-06-16T12:00:00Z",
      updated_at: "2026-06-16T12:00:00Z",
    },
  };
}

function integrationReminderPayload(body: Record<string, unknown>) {
  return {
    reminder: {
      reminder_id: "intrem_demo",
      reminder_type: body.reminder_type,
      product_object_type: body.product_object_type,
      product_object_id: body.product_object_id,
      destination: "ics_calendar",
      capability: "calendar_file",
      risk_posture: "calendar_file_no_sync",
      status: "created",
      title: body.title,
      due_at: body.due_at,
      timezone: body.timezone ?? "UTC",
      ics_filename: "intrem_demo.ics",
      receipt: {
        integration_id: "intrem_demo",
        destination: "ics_calendar",
        capability: "calendar_file",
        risk_posture: "calendar_file_no_sync",
        status: "created",
        external_write_performed: false,
        live_sync_enabled: false,
        oauth_performed: false,
        two_way_sync_enabled: false,
        product_authority_retained: true,
        permission_decision: {
          allowed: true,
          reason: "ok",
          boundary: "current_user",
          owner_user_id: "user_demo",
          organization_id: null,
        },
        provenance: {
          product_object_type: body.product_object_type,
          product_object_id: body.product_object_id,
          product_object_label: "Greater Boston",
          generated_at: "2026-06-16T12:00:00Z",
          generated_by_user_id: "user_demo",
          organization_id: null,
          freshness_status: "fresh",
          freshness_as_of: null,
          confidence_label: "partial",
          evidence_basis: ["region_output"],
          source_object_version: null,
          limitations: [],
          governance_warnings: [],
        },
        limitations: ["Reminder records do not create applicant tracking status."],
        governance_warnings: [],
      },
      created_at: "2026-06-16T12:00:00Z",
      updated_at: "2026-06-16T12:00:00Z",
    },
  };
}

function companyPayload() {
  return {
    company_id: "comp_alpha",
    company_name: "Alpha Systems",
    normalized_company_name: "alpha systems",
    sector_primary: "software",
    sector_secondary: null,
    eligibility_status: "eligible",
    eligibility_override_flag: false,
    classification_confidence: "high",
    is_major_tech: false,
    is_mag7: false,
    prestige_score: 0.71,
    regions_present: [],
    regions_hiring: [],
    entry_level_regions: [],
  };
}

function careerPlatformRegistryPayload() {
  return {
    platforms: [
      {
        platform: "linkedin",
        display_name: "LinkedIn",
        risk_posture: "deep_link_only",
        allowed_capabilities: ["manual_company_search", "manual_export"],
        blocked_capabilities: ["scraping", "automation", "application_submission"],
        notes: ["Search links are user-opened deep links only."],
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
        notes: ["Employer lookup is manual."],
        manual_only: true,
        automation_performed: false,
        ats_state_created: false,
      },
    ],
  };
}

function careerPlatformExportPayload(body: Record<string, unknown>) {
  return {
    export: {
      career_platform_export_id: "cpe_demo",
      platform: body.platform,
      risk_posture: body.platform === "linkedin" ? "deep_link_only" : "export_only",
      export_mode: "manual_lookup_export",
      rows: [{
        company_id: Array.isArray(body.company_ids) ? body.company_ids[0] : null,
        employer_name: "Alpha Systems",
        manual_only: true,
        automation_performed: false,
        ats_state_created: false,
        application_status_created: false,
        recruiter_outreach_created: false,
      }],
      manual_only: true,
      automation_performed: false,
      ats_state_created: false,
      application_status_created: false,
      recruiter_outreach_created: false,
      created_at: "2026-06-16T12:00:00Z",
    },
  };
}

function responseFor(input: RequestInfo | URL, init?: RequestInit) {
  const value = typeof input === "string" ? input : input.toString();
  const method = init?.method ?? "GET";
  if (value === "/health") return { service: "test" };
  if (value === "/regions") {
    return {
      regions: [{
        region_id: "greater_boston",
        display_name: "Greater Boston",
        region_type: "greater_region",
        parent_region_id: null,
        labor_market_group: "northeast",
        state: "fresh",
        coverage: { tier: "tier_3", label: "Partial coverage", heuristic: true },
        sector_coverage: {},
        priority_market: null,
      }],
    };
  }
  if (value === "/regions/search") return { regions: [], count: 0 };
  if (value === "/regions/greater_boston") return regionPayload();
  if (value === "/regions/greater_boston/sources") {
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
      warnings: [],
    };
  }
  if (value === "/companies/comp_alpha") return companyPayload();
  if (value === "/companies/comp_alpha/sources") {
    return {
      subject_type: "company",
      subject_id: "comp_alpha",
      freshness: {
        freshness_status: "fresh",
        data_basis: "real_imported",
        last_collected_at: null,
        source_count: 1,
        low_confidence_warning: null,
      },
      sources: [],
      warnings: [],
    };
  }
  if (value === "/companies/comp_alpha/regions") {
    return { company_id: "comp_alpha", company_name: "Alpha Systems", regions: [], count: 0 };
  }
  if (value.startsWith("/companies/search")) return { companies: [], count: 0 };
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
  if (value === "/api/integrations/exports" && method === "POST") {
    return integrationExportPayload(JSON.parse(String(init?.body)));
  }
  if (value === "/api/integrations/reminders" && method === "POST") {
    return integrationReminderPayload(JSON.parse(String(init?.body)));
  }
  if (value === "/api/integrations/career-platforms") return careerPlatformRegistryPayload();
  if (value === "/api/integrations/career-platform-exports" && method === "POST") {
    return careerPlatformExportPayload(JSON.parse(String(init?.body)));
  }
  if (value === "/me/explanations/region" && method === "POST") {
    return {
      provider_mode: "deterministic_structured_guidance",
      status: "ok",
      entity_type: "region",
      subject_refs: { region_id: "greater_boston" },
      sections: [],
      limitations: [],
      evidence_refs: [],
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

describe("integration actions UI", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    window.history.pushState(null, "", "/");
  });

  test("region view renders export and reminder actions safely", async () => {
    const fetchMock = stubFetch();
    window.history.pushState(null, "", "/markets/region/greater_boston");

    render(<App />);

    expect(await screen.findByText("Exports and reminders")).toBeTruthy();
    expect(screen.getByText(/Files and previews only; no external accounts are changed/i)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "CSV" }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) =>
        url === "/api/integrations/exports"
        && (init as RequestInit).method === "POST"
      )).toBe(true);
    });
    const exportCall = fetchMock.mock.calls.find(([url]) => url === "/api/integrations/exports");
    expect((exportCall?.[1] as RequestInit).headers).toMatchObject({
      "Authorization": "Bearer integration-token",
    });
    expect(JSON.parse(String((exportCall?.[1] as RequestInit).body))).toMatchObject({
      product_object_type: "region",
      product_object_id: "greater_boston",
      export_format: "csv",
    });
    expect(await screen.findByText(/No external write or live sync was performed/i)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "ICS reminder" }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) =>
        url === "/api/integrations/reminders"
        && (init as RequestInit).method === "POST"
      )).toBe(true);
    });
    const reminderCall = fetchMock.mock.calls.find(([url]) => url === "/api/integrations/reminders");
    expect(JSON.parse(String((reminderCall?.[1] as RequestInit).body))).toMatchObject({
      reminder_type: "market_refresh_alert",
      product_object_type: "region",
      product_object_id: "greater_boston",
    });
    expect(await screen.findByText(/No ATS application status or calendar write was created/i)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Explain guidance" }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url]) => url === "/me/explanations/region")).toBe(true);
    });
    const explanationCall = fetchMock.mock.calls.find(([url]) => url === "/me/explanations/region");
    const explanationBody = JSON.parse(String((explanationCall?.[1] as RequestInit).body));
    expect(explanationBody.evidence.canonical_scores).not.toHaveProperty("raw_total_score");
    expect(explanationBody.evidence.canonical_scores).toHaveProperty("objective_opportunity_score", 0.8);
  });

  test("company view renders manual career platform actions safely", async () => {
    const fetchMock = stubFetch();
    window.history.pushState(null, "", "/markets/company/comp_alpha");

    render(<App />);

    expect(await screen.findByText("Exports and reminders")).toBeTruthy();
    expect(screen.getByRole("button", { name: "LinkedIn manual search" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Handshake manual lookup" })).toBeTruthy();
    expect(screen.getByText(/Files and previews only; no external accounts are changed/i)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "LinkedIn manual search" }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) =>
        url === "/api/integrations/career-platform-exports"
        && (init as RequestInit).method === "POST"
      )).toBe(true);
    });
    const platformCall = fetchMock.mock.calls.find(([url]) =>
      url === "/api/integrations/career-platform-exports"
    );
    expect(JSON.parse(String((platformCall?.[1] as RequestInit).body))).toEqual({
      platform: "linkedin",
      company_ids: ["comp_alpha"],
      employer_names: [],
      organization_id: null,
    });
    expect(await screen.findByText(/No scraping, application submission, recruiter outreach, or ATS state was created/i)).toBeTruthy();
  });
});
