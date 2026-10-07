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
  deleteCareerMemory,
  deleteSavedMarketArtifact,
  dismissAlert,
  explainAlert,
  explainComparison,
  explainCompany,
  explainRegion,
  getCurrentUser,
  getBillingStatus,
  getCareerActionPlan,
  getCareerActionPlanWithMemory,
  getCareerAgentAnswer,
  getCareerMemory,
  getCareerPlatformRegistry,
  getCurrentOpportunities,
  getCurrentOpportunityCoverage,
  getCurrentOpportunityDiagnostics,
  getCurrentOpportunityMatches,
  getCurrentOpportunityRefreshRuns,
  getDataStandardDefinitions,
  getDataStandardsGovernanceFramework,
  getDataStandardsPartnerSchema,
  getDataStandardsPartners,
  getDataStandardsQualityLabels,
  getImportedMarketDiffPreview,
  getImportedMarketFacts,
  getImportedMarketGaps,
  getImportedMarketHealth,
  getImportedMarketHealthOverview,
  getImportedMarketOperationDetails,
  getImportedMarketOperationsView,
  getImportedMarketRankingDiagnostics,
  getImportedMarketRefreshReadiness,
  getImportedMarketSources,
  getImportedMarkets,
  getMarketComparison,
  getMarketComparisonRanking,
  getMarketIntelligence,
  getMarketIntelligenceProfile,
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
  getOpportunityRoutes,
  getPolicyEarlyCareerReport,
  getPolicyEconomicDevelopment,
  getPolicyEducationAlignment,
  getPolicyPeerComparison,
  getPolicyWorkforceDashboard,
  getPredictiveReport,
  getPublicBenchmark,
  getPublicBenchmarks,
  getPublicReport,
  getPublicReports,
  getRecommendationGoalModes,
  getRecommendationStrategy,
  getTrustExplanation,
  getUserIntelligenceDashboard,
  submitUserReport,
  getCareerAgentTool,
  getRegions,
  listInstitutionDataRequests,
  listInstitutionReports,
  listApiClients,
  listApiUsage,
  listCareerAgentTools,
  listCareerPlatformReferences,
  listPartnerImports,
  listAlerts,
  listSavedMarketArtifacts,
  markAlertRead,
  previewCareerAgentTool,
  previewScoringOverlay,
  rejectPartnerImport,
  approveCareerAgentTool,
  rejectCareerAgentTool,
  revokeApiKey,
  runInstitutionAdvisorComparison,
  updateCareerMemory,
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

  test("imported market coverage request stays public and read-only", async () => {
    const fetchMock = mockFetch({ markets: [], market_count: 0 });

    await getImportedMarkets();

    const [, init] = fetchMock.mock.calls[0];
    expect(fetchMock.mock.calls[0][0]).toBe("/markets/imported");
    expect((init as RequestInit).method).toBeUndefined();
    expect((init as RequestInit).headers).toEqual({ "Content-Type": "application/json" });
  });

  test("imported market operations helpers use public read-only Layer 33 routes", async () => {
    const fetchMock = mockFetch({});

    await getImportedMarketHealthOverview();
    await getImportedMarketHealth("atlanta");
    await getImportedMarketSources("atlanta");
    await getImportedMarketFacts("atlanta");
    await getImportedMarketGaps("atlanta");
    await getImportedMarketRankingDiagnostics("atlanta");
    await getImportedMarketRefreshReadiness("atlanta");
    await getImportedMarketDiffPreview("atlanta");

    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      "/markets/imported/health",
      "/markets/imported/atlanta/health",
      "/markets/imported/atlanta/sources",
      "/markets/imported/atlanta/facts",
      "/markets/imported/atlanta/gaps",
      "/markets/imported/atlanta/ranking-diagnostics",
      "/markets/imported/atlanta/refresh-readiness",
      "/markets/imported/atlanta/diff-preview",
    ]);
    for (const [, init] of fetchMock.mock.calls) {
      expect((init as RequestInit).method).toBeUndefined();
      expect((init as RequestInit).headers).toEqual({ "Content-Type": "application/json" });
    }
  });

  test("current opportunity helpers use authenticated Layer 38 routes", async () => {
    const fetchMock = mockFetch({});
    const auth = { getAccessToken: async () => "token-current-opps" };

    await getCurrentOpportunities(
      {
        market: "greater_boston",
        role_family: "software_engineering",
        opportunity_type: "job",
        work_arrangement: "hybrid",
        include_ineligible: true,
        limit: 25,
      },
      auth,
    );
    await getCurrentOpportunityMatches({ include_ineligible: true, limit: 10 }, auth);
    await getCurrentOpportunityCoverage(
      { market_key: "greater_boston", role_family: "software_engineering", opportunity_type: "job" },
      auth,
    );
    await getCurrentOpportunityDiagnostics(auth);
    await getCurrentOpportunityRefreshRuns({ limit: 5 }, auth);

    expect(fetchMock.mock.calls[0][0]).toBe(
      "/current-opportunities?market=greater_boston&role_family=software_engineering&opportunity_type=job&work_arrangement=hybrid&include_ineligible=true&limit=25",
    );
    expect(fetchMock.mock.calls[1][0]).toBe("/current-opportunities/matches?include_ineligible=true&limit=10");
    expect(fetchMock.mock.calls[2][0]).toBe(
      "/current-opportunities/coverage?market_key=greater_boston&role_family=software_engineering&opportunity_type=job",
    );
    expect(fetchMock.mock.calls[3][0]).toBe("/current-opportunities/diagnostics");
    expect(fetchMock.mock.calls[4][0]).toBe("/current-opportunities/refresh-runs?limit=5");
    for (const [, init] of fetchMock.mock.calls) {
      expect((init as RequestInit).headers).toMatchObject({ Authorization: "Bearer token-current-opps" });
    }
  });

  test("imported market operations bundle follows backend route contract without write calls", async () => {
    const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(async (input) => {
      const path = String(input);
      const data = path === "/markets/imported/health"
        ? {
          summary: {
            registered_market_count: 1,
            healthy_market_count: 1,
            markets_needing_refresh: 0,
            markets_with_limited_coverage: 0,
            markets_with_stale_sources: 0,
            total_stale_source_count: 0,
            total_ranking_excluded_fact_count: 0,
            highest_priority_maintenance_market: "atlanta",
            recommended_next_maintenance_action: "No immediate maintenance action.",
            overall_health_status: "healthy",
          },
          markets: [{ market_key: "atlanta", market_name: "Atlanta", health_status: "healthy" }],
        }
        : { market_key: "atlanta" };
      return new Response(JSON.stringify(envelope(data)), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const details = await getImportedMarketOperationDetails("atlanta");
    const view = await getImportedMarketOperationsView();

    expect(details.diff).toEqual({ market_key: "atlanta" });
    expect(view.data?.overview.summary.registered_market_count).toBe(1);
    expect(view.data?.details_by_market.atlanta.diff).toEqual({ market_key: "atlanta" });
    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      "/markets/imported/atlanta/sources",
      "/markets/imported/atlanta/facts",
      "/markets/imported/atlanta/gaps",
      "/markets/imported/atlanta/ranking-diagnostics",
      "/markets/imported/atlanta/refresh-readiness",
      "/markets/imported/atlanta/diff-preview",
      "/markets/imported/health",
      "/markets/imported/atlanta/sources",
      "/markets/imported/atlanta/facts",
      "/markets/imported/atlanta/gaps",
      "/markets/imported/atlanta/ranking-diagnostics",
      "/markets/imported/atlanta/refresh-readiness",
      "/markets/imported/atlanta/diff-preview",
    ]);
    for (const [, init] of fetchMock.mock.calls) {
      expect((init as RequestInit).method).toBeUndefined();
    }
  });

  test("market intelligence helpers use public read-only Layer 34 routes", async () => {
    const fetchMock = mockFetch({});

    await getMarketIntelligence("ai_ml");
    await getMarketIntelligenceProfile("atlanta");
    await getMarketComparisonRanking("product_management");
    await getMarketComparison("atlanta", "boston", "data_science");

    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      "/market-intelligence?goal=ai_ml",
      "/market-intelligence/atlanta",
      "/market-comparisons?goal=product_management",
      "/market-comparisons/atlanta/boston?goal=data_science",
    ]);
    for (const [, init] of fetchMock.mock.calls) {
      expect((init as RequestInit).method).toBeUndefined();
      expect((init as RequestInit).headers).toEqual({ "Content-Type": "application/json" });
    }
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

  test("opportunity route API call stays route-first and public", async () => {
    const fetchMock = mockFetch({ routes: [], route_count: 0 });

    await getOpportunityRoutes({
      user_intent_summary: "Software internship route",
      target_regions: ["greater_boston"],
      target_role_families: ["software_engineering"],
      preferred_program_types: ["internship"],
      preferred_location_modes: ["hybrid"],
      experience_level: "internship",
      include_unverified: false,
      limit: 3,
    });

    expect(fetchMock.mock.calls[0][0]).toBe("/opportunities/routes");
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe("POST");
    expect(JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body))).toEqual({
      user_intent_summary: "Software internship route",
      target_regions: ["greater_boston"],
      target_role_families: ["software_engineering"],
      preferred_program_types: ["internship"],
      preferred_location_modes: ["hybrid"],
      experience_level: "internship",
      include_unverified: false,
      limit: 3,
    });
    expect(String((fetchMock.mock.calls[0][1] as RequestInit).body)).not.toContain("keyword");
    expect((fetchMock.mock.calls[0][1] as RequestInit).headers).toEqual({
      "Content-Type": "application/json",
    });
  });

  test("user intelligence dashboard API call stays read-only and public", async () => {
    const fetchMock = mockFetch({
      generated_at: "2026-07-02T12:00:00Z",
      dashboard_version: "30.1",
      summary: {
        headline: "Your current market intelligence",
        description: "Personalized recommendations, warnings, and next actions.",
        warning_count: 0,
        recommendation_count: 0,
      },
      recommended_regions: [],
      recommended_companies: [],
      recommended_opportunities: [],
      market_warnings: [],
      forecast_changes: [],
      saved_items: [],
      recommended_next_actions: [],
      trust_context: {
        uses_existing_metadata_only: true,
        layer_30_full_trust_engine_available: false,
        message: "Existing metadata only.",
      },
    });

    await getUserIntelligenceDashboard();

    expect(fetchMock.mock.calls[0][0]).toBe("/user-intelligence/dashboard");
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBeUndefined();
    expect((fetchMock.mock.calls[0][1] as RequestInit).headers).toEqual({
      "Content-Type": "application/json",
    });
  });

  test("trust explanation API call stays read-only and public", async () => {
    const fetchMock = mockFetch({
      subject_type: "opportunity",
      subject_id: "opp_1",
      trust_tier: "partner_submitted",
      trust_label: "Partner-submitted",
      trust_summary: "Backend-provided summary.",
      risk_level: "medium",
      risk_label: "Use with caution",
      risk_summary: "Backend-provided risk summary.",
      routing_outcome: "visible_with_warning",
      routing_label: "Visible with warning",
      routing_summary: "Backend-provided routing summary.",
      ranking_influence_allowed: false,
      ranking_influence_decision: "denied",
      ranking_influence_label: "Excluded from rankings",
      ranking_influence_reason: "Backend-provided ranking reason.",
      evidence_requirements_met: [],
      evidence_requirements_missing: [],
      evidence_requirements_failed: [],
      trust_warnings: [],
      user_facing_warnings: [],
      last_checked_at: null,
      decided_at: null,
      next_recheck_at: null,
      explanation_version: "30C",
    });

    await getTrustExplanation("opportunity", "opp_1");

    expect(fetchMock.mock.calls[0][0]).toBe(
      "/trust/explanation?subject_type=opportunity&subject_id=opp_1",
    );
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBeUndefined();
    expect((fetchMock.mock.calls[0][1] as RequestInit).headers).toEqual({
      "Content-Type": "application/json",
    });
  });

  test("user report API call submits append-only report signal", async () => {
    const fetchMock = mockFetch({
      report: { user_report_id: "report_1", status: "queued_for_recheck" },
      recheck_job: { automated_recheck_job_id: "recheck_1", status: "queued" },
      status: {
        subject_type: "opportunity",
        subject_id: "opp_1",
        latest_report_status: "queued_for_recheck",
        latest_report_type: "outdated",
        latest_report_severity: "medium",
        latest_reported_at: "2026-07-08T12:00:00Z",
        active_recheck_job_id: "recheck_1",
        recheck_status: "queued",
        recheck_priority: "medium",
        recheck_outcome: null,
        recheck_status_label: "Recheck queued",
        message: "Report received. Automated recheck is queued.",
      },
      message: "Report received.",
    });

    await submitUserReport({
      subject_type: "opportunity",
      subject_id: "opp_1",
      report_type: "outdated",
      severity: "medium",
      report_reason: "Looks stale.",
      source_surface: "test",
    });

    expect(fetchMock.mock.calls[0][0]).toBe("/user-reports");
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe("POST");
    expect(JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body))).toEqual({
      subject_type: "opportunity",
      subject_id: "opp_1",
      report_type: "outdated",
      severity: "medium",
      report_reason: "Looks stale.",
      source_surface: "test",
    });
  });

  test("career agent API call stays public and structured", async () => {
    const fetchMock = mockFetch({ recommendations: [], guardrails: { passed: true } });

    await getCareerAgentAnswer({
      question_type: "city_fit",
      target_region_ids: ["greater_boston"],
      target_role_families: ["software_engineering"],
      include_forecasts: true,
      preference_snapshot: {
        preferred_region_ids: ["greater_boston"],
        counts_as_evidence: false,
      },
      limit: 3,
    });

    expect(fetchMock.mock.calls[0][0]).toBe("/career-agent/answers");
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe("POST");
    expect(JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body))).toEqual({
      question_type: "city_fit",
      target_region_ids: ["greater_boston"],
      target_role_families: ["software_engineering"],
      include_forecasts: true,
      preference_snapshot: {
        preferred_region_ids: ["greater_boston"],
        counts_as_evidence: false,
      },
      limit: 3,
    });
    expect(String((fetchMock.mock.calls[0][1] as RequestInit).body)).not.toContain("prompt");
    expect((fetchMock.mock.calls[0][1] as RequestInit).headers).toEqual({
      "Content-Type": "application/json",
    });
  });

  test("career action plan API call stays public and structured", async () => {
    const fetchMock = mockFetch({ steps: [], guardrails: { passed: true } });

    await getCareerActionPlan({
      plan_type: "weekly_job_search_plan",
      career_goal: "Find a grounded weekly plan.",
      career_agent_request: {
        question_type: "what_should_i_do_this_month",
        target_region_ids: ["greater_boston"],
        target_role_families: ["software_engineering"],
        include_forecasts: false,
        limit: 3,
      },
      include_memory: false,
      limit: 3,
    });

    expect(fetchMock.mock.calls[0][0]).toBe("/career-agent/action-plans");
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe("POST");
    expect(JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body))).toEqual({
      plan_type: "weekly_job_search_plan",
      career_goal: "Find a grounded weekly plan.",
      career_agent_request: {
        question_type: "what_should_i_do_this_month",
        target_region_ids: ["greater_boston"],
        target_role_families: ["software_engineering"],
        include_forecasts: false,
        limit: 3,
      },
      include_memory: false,
      limit: 3,
    });
    expect(String((fetchMock.mock.calls[0][1] as RequestInit).body)).not.toContain("prompt");
    expect((fetchMock.mock.calls[0][1] as RequestInit).headers).toEqual({
      "Content-Type": "application/json",
    });
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

  test("Layer 24 policy requests stay public and route to backend policy payloads", async () => {
    const fetchMock = mockFetch({
      region_id: "greater_boston",
      report_id: "layer24_policy_report:test",
      title: "Layer 24 report",
    });

    await getPolicyWorkforceDashboard("greater_boston");
    await getPolicyEconomicDevelopment("greater_boston");
    await getPolicyEducationAlignment("greater_boston");
    await getPolicyPeerComparison("greater_boston");
    await getPolicyEarlyCareerReport("greater_boston");

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/policy/regions/greater_boston/workforce-dashboard",
      "/policy/regions/greater_boston/economic-development",
      "/policy/regions/greater_boston/education-alignment",
      "/policy/regions/greater_boston/peer-comparison",
      "/policy/regions/greater_boston/reports/early-career-opportunity",
    ]);
    for (const [, init] of fetchMock.mock.calls) {
      expect((init as RequestInit).headers).toEqual({ "Content-Type": "application/json" });
    }
  });

  test("predictive report request stays public and API-safe", async () => {
    const fetchMock = mockFetch({ report_id: "predictive_report:test", sections: [] });

    await getPredictiveReport(["greater_boston", "greater_atlanta"], ["comp_a"]);

    expect(fetchMock.mock.calls[0][0]).toBe(
      "/platform/predictive/reports?region_id=greater_boston&region_id=greater_atlanta&company_id=comp_a",
    );
    expect((fetchMock.mock.calls[0][1] as RequestInit).headers).toEqual({
      "Content-Type": "application/json",
    });
  });

  test("Layer 27 standards requests stay public and read-only", async () => {
    const fetchMock = mockFetch({ definitions: [], partners: [], labels: [], governance_records: [] });

    await getDataStandardDefinitions();
    await getDataStandardsPartnerSchema();
    await getDataStandardsPartners();
    await getDataStandardsQualityLabels();
    await getDataStandardsGovernanceFramework();

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/data-standards/definitions",
      "/data-standards/partner-schema",
      "/data-standards/partners",
      "/data-standards/quality-labels",
      "/data-standards/governance-framework",
    ]);
    for (const [, init] of fetchMock.mock.calls) {
      expect((init as RequestInit).headers).toEqual({ "Content-Type": "application/json" });
      expect((init as RequestInit).method).toBeUndefined();
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

  test("protected career memory and memory-backed plan requests attach bearer tokens", async () => {
    const fetchMock = mockFetch({ memory_enabled: false, steps: [] });
    const auth = { getAccessToken: async () => "career-token" };

    await getCareerMemory(auth);
    await updateCareerMemory(
      {
        explicit_user_permission: true,
        permissions: [
          {
            category: "saved_companies",
            enabled: true,
            personalize_allowed: true,
            visibility: "private",
          },
        ],
        entries: [{ category: "saved_companies", value: "comp_a" }],
        replace_categories: ["saved_companies"],
      },
      auth,
    );
    await deleteCareerMemory({ clear_all: true }, auth);
    await getCareerActionPlanWithMemory(
      {
        plan_type: "weekly_job_search_plan",
        career_agent_request: {
          question_type: "what_should_i_do_this_month",
          target_region_ids: ["greater_boston"],
        },
        include_memory: true,
      },
      auth,
    );

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/me/career-memory",
      "/me/career-memory",
      "/me/career-memory",
      "/me/career-agent/action-plans",
    ]);
    expect((fetchMock.mock.calls[1][1] as RequestInit).method).toBe("PUT");
    expect((fetchMock.mock.calls[2][1] as RequestInit).method).toBe("DELETE");
    expect((fetchMock.mock.calls[3][1] as RequestInit).method).toBe("POST");
    expect(JSON.parse(String((fetchMock.mock.calls[3][1] as RequestInit).body))).toMatchObject({
      include_memory: true,
    });
    for (const [, init] of fetchMock.mock.calls) {
      expect((init as RequestInit).headers).toMatchObject({
        "Authorization": "Bearer career-token",
        "Content-Type": "application/json",
      });
    }
  });

  test("protected career agent tool requests attach bearer tokens and structured bodies", async () => {
    const fetchMock = mockFetch({ tool_previews: [], tool_request_id: "tool_1" });
    const auth = { getAccessToken: async () => "tool-token" };
    const previewRequest = {
      tool_type: "reminder" as const,
      career_agent_request: {
        question_type: "what_should_i_do_this_month" as const,
        target_region_ids: ["greater_boston"],
      },
      requested_action: "preview" as const,
      include_memory: false,
      limit: 3,
    };

    await previewCareerAgentTool(previewRequest, auth);
    await listCareerAgentTools(auth);
    await getCareerAgentTool("tool_1", auth);
    await approveCareerAgentTool(
      { tool_request_id: "tool_1", explicit_user_approval: true },
      auth,
    );
    await rejectCareerAgentTool(
      { tool_request_id: "tool_1", explicit_user_approval: false },
      auth,
    );

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/me/career-agent/tools/preview",
      "/me/career-agent/tools",
      "/me/career-agent/tools/tool_1",
      "/me/career-agent/tools/approve",
      "/me/career-agent/tools/reject",
    ]);
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe("POST");
    expect(JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body))).toEqual(previewRequest);
    expect(JSON.parse(String((fetchMock.mock.calls[3][1] as RequestInit).body))).toEqual({
      tool_request_id: "tool_1",
      explicit_user_approval: true,
    });
    expect(JSON.parse(String((fetchMock.mock.calls[4][1] as RequestInit).body))).toEqual({
      tool_request_id: "tool_1",
      explicit_user_approval: false,
    });
    for (const [, init] of fetchMock.mock.calls) {
      expect((init as RequestInit).headers).toMatchObject({
        "Authorization": "Bearer tool-token",
        "Content-Type": "application/json",
      });
    }
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
