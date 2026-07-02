import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import {
  ApiError,
  acceptPartnerImport,
  archivePartnerImport,
  createApiClient,
  createApiKey,
  createBillingCheckoutSession,
  createBillingPortalSession,
  createCareerPlatformExport,
  createCareerPlatformReference,
  createIntegrationExport,
  createIntegrationReminder,
  createInstitutionDataRequest,
  createPartnerImport,
  createSavedMarketArtifact,
  deleteSavedMarketArtifact,
  dismissAlert,
  explainAlert,
  explainComparison,
  explainCompany,
  explainRegion,
  getCurrentUser,
  getBillingStatus,
  getCareerPlatformRegistry,
  getInstitutionCurrentOrganizations,
  getInstitutionDashboard,
  getPartnerImport,
  getPartnerImportReceipt,
  generateInstitutionReport,
  getMonetizationAccessPreview,
  getMonetizationFeatures,
  getMonetizationPlans,
  getMonetizationReports,
  getMyMonetization,
  getMyMonetizationEntitlements,
  getMyMonetizationUsage,
  getPublicBenchmark,
  getPublicBenchmarks,
  getPublicReport,
  getPublicReports,
  getRecommendationGoalModes,
  getRecommendationStrategy,
  getRegions,
  listInstitutionDataRequests,
  listInstitutionReports,
  listApiClients,
  listApiUsage,
  listCareerPlatformReferences,
  listPartnerImports,
  listAlerts,
  listSavedMarketArtifacts,
  markAlertRead,
  previewScoringOverlay,
  rejectPartnerImport,
  revokeApiKey,
  runInstitutionAdvisorComparison,
  validatePartnerImport,
} from "./api";
import { configureFrontendErrorReporter } from "./errorMonitoring";

function envelope(data: unknown) {
  return {
    status: "success",
    data,
    metadata: { state: "test", source_versions: {}, warnings: [] },
    error: null,
  };
}

function mockFetch(data: unknown) {
  const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(async () =>
    new Response(JSON.stringify(envelope(data)), {
      headers: { "Content-Type": "application/json" },
      status: 200,
    })
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("frontend API client auth boundary", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    configureFrontendErrorReporter(null);
    vi.unstubAllGlobals();
  });

  test("public market requests do not attach bearer tokens", async () => {
    const fetchMock = mockFetch({ regions: [] });

    await getRegions();

    const [, init] = fetchMock.mock.calls[0];
    expect(fetchMock.mock.calls[0][0]).toBe("/regions");
    expect((init as RequestInit).headers).toEqual({ "Content-Type": "application/json" });
  });

  test("recommendation API calls stay public and structured", async () => {
    const fetchMock = mockFetch({ goal_modes: [] });

    await getRecommendationGoalModes();
    await getRecommendationStrategy({
      goal_mode: "maximize_entry_level_access",
      region_limit: 10,
      company_limit: 10,
    });

    expect(fetchMock.mock.calls[0][0]).toBe("/recommendations/goal-modes");
    expect(fetchMock.mock.calls[1][0]).toBe("/recommendations/strategy");
    expect((fetchMock.mock.calls[1][1] as RequestInit).method).toBe("POST");
    expect(JSON.parse(String((fetchMock.mock.calls[1][1] as RequestInit).body))).toEqual({
      goal_mode: "maximize_entry_level_access",
      region_limit: 10,
      company_limit: 10,
    });
    expect(String((fetchMock.mock.calls[1][1] as RequestInit).body)).not.toContain("prompt");
    for (const [, init] of fetchMock.mock.calls) {
      expect((init as RequestInit).headers).toEqual({ "Content-Type": "application/json" });
    }
  });

  test("monetization catalog and access-preview calls stay public", async () => {
    const fetchMock = mockFetch({
      plans: [],
      features: [],
      reports: [],
      decision: { allowed: false },
    });

    await getMonetizationPlans();
    await getMonetizationFeatures();
    await getMonetizationReports();
    await getBillingStatus();
    await getMonetizationAccessPreview({
      plan_key: "free",
      feature_key: "full_report_generation",
      used: 2,
    });
    await getMonetizationAccessPreview({
      feature_key: "saved_watchlists",
    });

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/monetization/plans",
      "/monetization/features",
      "/monetization/reports",
      "/billing/status",
      "/monetization/access-preview?feature_key=full_report_generation&plan_key=free&used=2",
      "/monetization/access-preview?feature_key=saved_watchlists",
    ]);
    for (const [, init] of fetchMock.mock.calls) {
      expect((init as RequestInit).headers).toEqual({ "Content-Type": "application/json" });
    }
  });

  test("public report and benchmark requests stay unauthenticated", async () => {
    const fetchMock = mockFetch({
      reports: [],
      benchmarks: [],
      report_id: "public_report:test",
      benchmark_id: "public_benchmark:test",
      slug: "test",
      title: "Test",
      name: "Test",
    });

    await getPublicReports();
    await getPublicReport("best-cities-early-career-ai-careers");
    await getPublicBenchmarks();
    await getPublicBenchmark("early-career-tech-access-index");

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/public/reports",
      "/public/reports/best-cities-early-career-ai-careers",
      "/public/benchmarks",
      "/public/benchmarks/early-career-tech-access-index",
    ]);
    for (const [, init] of fetchMock.mock.calls) {
      expect((init as RequestInit).headers).toEqual({ "Content-Type": "application/json" });
    }
  });

  test("protected /me requests attach bearer tokens", async () => {
    const fetchMock = mockFetch({
      user: { user_id: "user_a", status: "active" },
      profile: { email: "a@example.com" },
    });

    await getCurrentUser({ getAccessToken: async () => "access-token" });

    const [, init] = fetchMock.mock.calls[0];
    expect(fetchMock.mock.calls[0][0]).toBe("/me");
    expect((init as RequestInit).headers).toMatchObject({
      "Authorization": "Bearer access-token",
      "Content-Type": "application/json",
    });
  });

  test("protected monetization account requests attach bearer tokens", async () => {
    const fetchMock = mockFetch({
      account: { account_type: "individual", account_status: "active" },
      entitlements: { plan_key: "free" },
      usage: [],
    });
    const auth = { getAccessToken: async () => "monetization-token" };

    await getMyMonetization(auth);
    await getMyMonetizationEntitlements(auth);
    await getMyMonetizationUsage(auth);
    await getMonetizationAccessPreview({ feature_key: "alerts" }, auth);

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/monetization/me",
      "/monetization/entitlements",
      "/monetization/usage",
      "/monetization/access-preview?feature_key=alerts",
    ]);
    for (const [, init] of fetchMock.mock.calls) {
      expect((init as RequestInit).headers).toMatchObject({
        "Authorization": "Bearer monetization-token",
        "Content-Type": "application/json",
      });
    }
  });

  test("protected billing requests attach bearer tokens", async () => {
    const fetchMock = mockFetch({
      checkout_session_id: "cs_test",
      checkout_url: "https://checkout.stripe.test/session/cs_test",
      portal_session_id: "bps_test",
      portal_url: "https://billing.stripe.test/session/bps_test",
    });
    const auth = { getAccessToken: async () => "billing-token" };

    await createBillingCheckoutSession("individual_monthly", auth);
    await createBillingPortalSession(auth);

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/billing/checkout-session",
      "/billing/portal-session",
    ]);
    expect(JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body))).toEqual({
      plan_key: "individual_monthly",
    });
    for (const [, init] of fetchMock.mock.calls) {
      expect((init as RequestInit).headers).toMatchObject({
        "Authorization": "Bearer billing-token",
        "Content-Type": "application/json",
      });
    }
  });

  test("protected institutional requests attach bearer tokens", async () => {
    const fetchMock = mockFetch({
      organizations: [],
      organization_id: "org_demo",
      cohort_size: 0,
    });
    const auth = { getAccessToken: async () => "institution-token" };

    await getInstitutionCurrentOrganizations(auth);
    await getInstitutionDashboard("org_demo", auth);
    await runInstitutionAdvisorComparison(
      "org_demo",
      "regions",
      {
        regions: ["greater_boston", "greater_sf"],
        role_context: "software engineering",
        career_stage: "entry_level",
      },
      auth,
    );
    await generateInstitutionReport(
      "org_demo",
      { report_type: "career_services", minimum_group_size: 5 },
      auth,
    );
    await listInstitutionReports("org_demo", auth);
    await createInstitutionDataRequest(
      "org_demo",
      { request_type: "organization_export", reason: "test" },
      auth,
    );
    await listInstitutionDataRequests("org_demo", auth);

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/api/institutions/organizations/current",
      "/api/institutions/organizations/org_demo/dashboard",
      "/api/institutions/organizations/org_demo/advisor/compare-regions",
      "/api/institutions/organizations/org_demo/reports",
      "/api/institutions/organizations/org_demo/reports",
      "/api/institutions/organizations/org_demo/data-requests",
      "/api/institutions/organizations/org_demo/data-requests",
    ]);
    expect(JSON.parse(String((fetchMock.mock.calls[2][1] as RequestInit).body))).toEqual({
      regions: ["greater_boston", "greater_sf"],
      role_context: "software engineering",
      career_stage: "entry_level",
    });
    expect(JSON.parse(String((fetchMock.mock.calls[3][1] as RequestInit).body))).toEqual({
      report_type: "career_services",
      minimum_group_size: 5,
    });
    expect(JSON.parse(String((fetchMock.mock.calls[5][1] as RequestInit).body))).toEqual({
      request_type: "organization_export",
      reason: "test",
    });
    for (const [, init] of fetchMock.mock.calls) {
      expect((init as RequestInit).headers).toMatchObject({
        "Authorization": "Bearer institution-token",
        "Content-Type": "application/json",
      });
    }
  });

  test("protected integration requests attach bearer tokens", async () => {
    const fetchMock = mockFetch({
      export: { export_id: "intexp_1" },
      reminder: { reminder_id: "intrem_1" },
      partner_import: { import_batch_id: "pib_1" },
      imports: [],
      receipt: { import_batch_id: "pib_1" },
      api_client: { api_client_id: "apic_1" },
      api_clients: [],
      api_key: { api_key_id: "apikey_1", raw_key: "jmi_live_secret" },
      usage: [],
      platforms: [],
      reference: { reference_id: "cpr_1" },
    });
    const auth = { getAccessToken: async () => "integration-token" };

    await createIntegrationExport(
      {
        product_object_type: "region",
        product_object_id: "greater_boston",
        export_format: "prepared_google_sheets",
      },
      auth,
    );
    await createIntegrationReminder(
      {
        reminder_type: "market_refresh_alert",
        product_object_type: "region",
        product_object_id: "greater_boston",
        title: "Review Greater Boston",
        due_at: "2026-06-23T12:00:00.000Z",
      },
      auth,
    );
    await createPartnerImport(
      {
        organization_id: "org_demo",
        source_type: "local_employer_list",
        import_format: "csv",
        source_attribution: "Career center partner list",
        content: "employer_name,region\nAlpha Systems,Greater Boston\n",
      },
      auth,
    );
    await listPartnerImports("org_demo", auth);
    await getPartnerImport("pib_1", auth);
    await validatePartnerImport("pib_1", auth);
    await acceptPartnerImport("pib_1", { reason: "ok" }, auth);
    await rejectPartnerImport("pib_1", { reason: "bad source" }, auth);
    await archivePartnerImport("pib_1", { reason: "closed" }, auth);
    await getPartnerImportReceipt("pib_1", auth);
    await createApiClient(
      {
        display_name: "Read client",
        scopes: ["region:read", "market_signal:read"],
        rate_limit_count: 60,
        rate_limit_window_seconds: 3600,
      },
      auth,
    );
    await listApiClients(auth);
    await createApiKey("apic_1", auth);
    await revokeApiKey("apikey_1", auth);
    await listApiUsage("apic_1", auth);
    await getCareerPlatformRegistry(auth);
    await createCareerPlatformReference(
      {
        platform: "company_career_page",
        subject_type: "company",
        subject_id: "comp_alpha",
        url: "https://example.com/careers",
      },
      auth,
    );
    await listCareerPlatformReferences(auth, {
      subjectType: "company",
      subjectId: "comp_alpha",
    });
    await createCareerPlatformExport(
      {
        platform: "linkedin",
        company_ids: ["comp_alpha"],
        employer_names: [],
      },
      auth,
    );

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/api/integrations/exports",
      "/api/integrations/reminders",
      "/api/integrations/partner-imports",
      "/api/integrations/partner-imports?organization_id=org_demo",
      "/api/integrations/partner-imports/pib_1",
      "/api/integrations/partner-imports/pib_1/validate",
      "/api/integrations/partner-imports/pib_1/accept",
      "/api/integrations/partner-imports/pib_1/reject",
      "/api/integrations/partner-imports/pib_1/archive",
      "/api/integrations/partner-imports/pib_1/receipt",
      "/api/integrations/api-clients",
      "/api/integrations/api-clients",
      "/api/integrations/api-clients/apic_1/keys",
      "/api/integrations/api-keys/apikey_1/revoke",
      "/api/integrations/api-clients/apic_1/usage",
      "/api/integrations/career-platforms",
      "/api/integrations/career-platform-references",
      "/api/integrations/career-platform-references?subject_type=company&subject_id=comp_alpha",
      "/api/integrations/career-platform-exports",
    ]);
    expect(JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body))).toEqual({
      product_object_type: "region",
      product_object_id: "greater_boston",
      export_format: "prepared_google_sheets",
    });
    expect(JSON.parse(String((fetchMock.mock.calls[1][1] as RequestInit).body))).toMatchObject({
      reminder_type: "market_refresh_alert",
      product_object_type: "region",
      product_object_id: "greater_boston",
    });
    expect(JSON.parse(String((fetchMock.mock.calls[2][1] as RequestInit).body))).toMatchObject({
      organization_id: "org_demo",
      source_type: "local_employer_list",
      import_format: "csv",
    });
    expect(JSON.parse(String((fetchMock.mock.calls[6][1] as RequestInit).body))).toEqual({
      reason: "ok",
    });
    expect(JSON.parse(String((fetchMock.mock.calls[10][1] as RequestInit).body))).toMatchObject({
      scopes: ["region:read", "market_signal:read"],
      rate_limit_count: 60,
    });
    expect(JSON.parse(String((fetchMock.mock.calls[18][1] as RequestInit).body))).toEqual({
      platform: "linkedin",
      company_ids: ["comp_alpha"],
      employer_names: [],
    });
    for (const [, init] of fetchMock.mock.calls) {
      expect((init as RequestInit).headers).toMatchObject({
        "Authorization": "Bearer integration-token",
        "Content-Type": "application/json",
      });
    }
  });

  test("protected /me requests fail before fetch without a token", async () => {
    const fetchMock = mockFetch({});

    await expect(getCurrentUser({ getAccessToken: async () => null })).rejects.toBeInstanceOf(ApiError);

    expect(fetchMock).not.toHaveBeenCalled();
  });

  test("account calls stay under /me and use the bearer token", async () => {
    const fetchMock = mockFetch({
      saved_market_artifacts: [],
      saved_artifact_id: "saved_artifact_1",
      artifact_type: "region",
      artifact_ref: "greater_boston",
    });
    const auth = { getAccessToken: async () => "token" };

    await createSavedMarketArtifact({ artifact_type: "region", artifact_ref: "greater_boston" }, auth);
    await listSavedMarketArtifacts(auth, "region");
    await deleteSavedMarketArtifact("saved_artifact_1", auth);
    await previewScoringOverlay({ region_ids: ["greater_boston"] }, auth);
    await listAlerts(auth);
    await markAlertRead("user_alert_1", auth);
    await dismissAlert("user_alert_1", auth);
    await explainRegion({ evidence: { entity_type: "region", subject_refs: { region_id: "greater_boston" } } }, auth);
    await explainCompany({ evidence: { entity_type: "company", subject_refs: { company_id: "comp_a" } } }, auth);
    await explainComparison({ evidence: { entity_type: "comparison", subject_refs: { comparison_id: "a__b" } } }, auth);
    await explainAlert({ evidence: { entity_type: "alert", subject_refs: { alert_event_id: "event_1" } } }, auth);

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/me/saved-market-artifacts",
      "/me/saved-market-artifacts?artifact_type=region",
      "/me/saved-market-artifacts/saved_artifact_1",
      "/me/scoring-preview",
      "/me/alerts?include_dismissed=false",
      "/me/alerts/user_alert_1/read",
      "/me/alerts/user_alert_1/dismiss",
      "/me/explanations/region",
      "/me/explanations/company",
      "/me/explanations/comparison",
      "/me/explanations/alert",
    ]);
    for (const [, init] of fetchMock.mock.calls) {
      expect((init as RequestInit).headers).toMatchObject({ "Authorization": "Bearer token" });
    }
  });

  test("API failures carry safe request IDs and report provider-neutral events", async () => {
    const reporter = vi.fn();
    configureFrontendErrorReporter(reporter);
    vi.stubGlobal("fetch", vi.fn(async () =>
      new Response(JSON.stringify({
        error: {
          type: "database_error",
          message: "Database unavailable",
          request_id: "api-req-1",
        },
      }), {
        headers: { "Content-Type": "application/json", "X-Request-ID": "api-req-1" },
        status: 503,
      })
    ));

    await expect(getRegions()).rejects.toMatchObject({
      name: "ApiError",
      requestId: "api-req-1",
      statusCode: 503,
      message: "Database unavailable Reference ID: api-req-1",
    });
    expect(reporter).toHaveBeenCalledWith(expect.objectContaining({
      source: "api_request",
      path: "/regions",
      requestId: "api-req-1",
      statusCode: 503,
    }));
  });
});
