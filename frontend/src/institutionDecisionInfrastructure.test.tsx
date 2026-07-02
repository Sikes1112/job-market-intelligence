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

function privacy() {
  return {
    aggregation_level: "mixed_aggregate",
    privacy_mode: "suppressed_small_cohort",
    minimum_cohort_size: 5,
    cohort_size: 4,
    suppression_applied: true,
    suppressed_fields: ["target_markets"],
    privacy_notes: [
      "Institutional outputs use aggregate, anonymized cohort-level or public market-level intelligence only.",
      "Raw student searches, saved jobs, applications, preferences, recommendations, identities, and private activity are not exposed.",
    ],
    student_level_data_exposed: false,
  };
}

function confidence(level = "medium") {
  return {
    level,
    score: level === "high" ? 0.82 : 0.58,
    factors: ["Evidence spans aggregate cohort and public market-level sources."],
  };
}

function evidence(level = "medium") {
  return {
    confidence: confidence(level),
    freshness: "unknown",
    provenance: [
      "Layer 16 aggregate institutional dashboard",
      "Company-region hiring, entry-level, and presence tables",
    ],
    source_basis: [
      "aggregate_cohort_dashboard",
      "public_market_level_company_region_signals",
    ],
    historical_depth: {
      market_signal_count: 12,
      visible_target_market_count: 0,
      cohort_size: 4,
      minimum_cohort_size: 5,
    },
  };
}

function metric(label: string, value: number) {
  return {
    metric_key: label.toLowerCase().replace(/\s+/g, "_"),
    label,
    value,
    unit: "0-100",
    decision_use: "Supports advising, curriculum, employer partnership, or workforce decisions.",
    evidence: evidence(),
  };
}

function section(key: string, title: string) {
  return {
    section_key: key,
    title,
    what_is_happening: `${title} has a bounded institutional signal.`,
    why_it_matters: `${title} informs advising and employer strategy.`,
    considerations: ["Use as decision support, not a guaranteed outcome."],
    metrics: [metric("Opportunity score", 72)],
    evidence: evidence(),
    warnings: [],
  };
}

function decisionDashboardPayload() {
  return {
    organization_id: "org_demo",
    organization_name: "Demo Career Center",
    generated_at: "2026-05-26T12:00:00Z",
    time_horizon: "next_12_months",
    summary: section("summary", "Institutional Decision Summary"),
    target_markets: [{
      ...section("target_markets_suppressed", "Student Target Markets"),
      what_is_happening: "Cohort target-market detail is suppressed because no category met the minimum group threshold.",
      warnings: ["Small-group target-market detail is withheld."],
    }],
    regional_trends: [section("regional_trend:cloud", "Emerging Cloud Hub")],
    program_alignment: [section("program_alignment:computer_science", "Computer Science")],
    employer_geography: [section("employer_geography:cloud", "Emerging Cloud Hub employer geography")],
    internship_access: [section("internship_access:cloud", "Emerging Cloud Hub internship access")],
    industry_demand: [section("industry_demand:cloud", "Cloud")],
    forecast_notes: [{
      forecast_label: "Growth signal forecast",
      forecast_type: "ai_role_market_growth_12m",
      affected_entity: "emerging_cloud_hub",
      time_horizon: "next_12_months",
      safe_display_summary: "Historical movement supports a bounded growth forecast with medium confidence.",
      confidence: { level: "medium", score: 0.6 },
      source_basis: { data_basis: "producer_owned_export", source_count: 8 },
      historical_depth: { observation_count: 8 },
      uncertainty: { level: "medium", known_uncertainties: ["Forecast is bounded."] },
      reasoning_trail: ["Historical observations support the directional signal."],
      supporting_signals: [{ signal_kind: "trend", signal_status: "rising" }],
    }],
    recommended_actions: [
      "Review employer relationship coverage in markets with hiring, internship, and presence signals.",
    ],
    confidence: confidence(),
    freshness: "unknown",
    provenance: ["Layer 16 aggregate institutional dashboard"],
    privacy: privacy(),
    limitations: ["Layer 22A does not predict individual student outcomes."],
    warnings: ["Cohort size is below the minimum threshold; cohort-derived detail is suppressed."],
  };
}

function curriculumPayload() {
  return {
    organization_id: "org_demo",
    organization_name: "Demo Career Center",
    generated_at: "2026-05-26T12:00:00Z",
    programs: [{
      program_name: "Computer Science",
      relevant_role_families: ["Software Engineering", "Cloud Infrastructure"],
      strongest_aligned_markets: [metric("Emerging Cloud Hub", 82)],
      emerging_markets: [metric("Emerging Cloud Hub", 82)],
      weak_or_saturated_markets: [],
      skills_with_rising_demand: ["cloud deployment", "machine learning foundations"],
      employer_relationship_targets: ["CloudScale"],
      advising_recommendations: ["Use Emerging Cloud Hub as a first advising comparison market."],
      confidence: confidence("high"),
      freshness: "unknown",
      provenance: ["Company-region hiring, entry-level, and presence tables"],
      sparse_data_warnings: ["Cohort-derived student attention is suppressed for privacy."],
      privacy: privacy(),
    }],
    confidence: confidence(),
    freshness: "unknown",
    provenance: ["Company-region hiring, entry-level, and presence tables"],
    privacy: privacy(),
    warnings: [],
    limitations: ["Sample curriculum mappings are structured placeholders."],
  };
}

function workforceReportPayload() {
  return {
    title: "Demo Career Center Regional Workforce Opportunity Report",
    report_type: "regional_workforce_opportunity",
    audience: "career centers and workforce boards",
    scope: "Demo Career Center aggregate cohort and public market intelligence",
    generated_at: "2026-05-26T12:00:00Z",
    summary: "Regional workforce opportunity generated from aggregate cohort and public market signals.",
    key_findings: ["Emerging Cloud Hub has the strongest observed opportunity score."],
    recommended_actions: ["Review Emerging Cloud Hub as a priority comparison market."],
    supporting_metrics: [metric("Emerging Cloud Hub", 82)],
    confidence: confidence(),
    freshness: "unknown",
    provenance: ["Company-region hiring, entry-level, and presence tables"],
    privacy_statement: "This report does not include raw individual student behavior.",
    privacy: privacy(),
    limitations: ["Forecast-based gaps should be treated as prompts for review."],
    warnings: [],
    export_ready: { structure: "sectioned_json" },
  };
}

function benchmarkPayload() {
  return {
    organization_id: "org_demo",
    organization_name: "Demo Career Center",
    generated_at: "2026-05-26T12:00:00Z",
    benchmarks: [{
      benchmark_subject: "Student target-market alignment",
      comparison_market_set: ["Emerging Cloud Hub", "Cyber Growth Region"],
      opportunity_score: 78,
      alignment_score: 20,
      gap_score: 80,
      emerging_region_gap: 100,
      employer_access_gap: 75,
      internship_access_gap: 100,
      recommendation_summary: "Review emerging-region advising coverage.",
      supporting_rationale: ["Outdated-hub gap score is 50."],
      warnings: ["No student target market met the minimum group threshold."],
    }],
    confidence: confidence(),
    freshness: "unknown",
    provenance: ["Layer 16 aggregate institutional dashboard"],
    privacy: privacy(),
    warnings: [],
    limitations: ["Benchmark scores are deterministic directional comparisons."],
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
  if (value === "/api/institutions/organizations/org_demo/decision-dashboard") {
    return decisionDashboardPayload();
  }
  if (value === "/api/institutions/organizations/org_demo/curriculum-market-map") {
    return curriculumPayload();
  }
  if (value === "/api/institutions/organizations/org_demo/workforce-reports/regional_workforce_opportunity") {
    return workforceReportPayload();
  }
  if (value === "/api/institutions/organizations/org_demo/benchmarks") {
    return benchmarkPayload();
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

describe("institutional decision infrastructure UI", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    window.history.pushState(null, "", "/");
  });

  test("decisions route renders dashboard, report, benchmark, privacy, and suppressed states", async () => {
    const fetchMock = stubFetch();
    window.history.pushState(null, "", "/markets/institution/decisions");

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Institutional Decisions" })).toBeTruthy();
    expect(await screen.findByText("Privacy-Safe Aggregation")).toBeTruthy();
    expect(screen.getByText("Suppressed data")).toBeTruthy();
    expect(screen.getByText("Target Markets")).toBeTruthy();
    expect(screen.getByText("Regional Trends")).toBeTruthy();
    expect(screen.getByText("Curriculum-To-Market Mapping")).toBeTruthy();
    expect(screen.getByText("Demo Career Center Regional Workforce Opportunity Report")).toBeTruthy();
    expect(screen.getByText("Institutional Benchmarks")).toBeTruthy();
    expect(screen.getByText("Growth signal forecast")).toBeTruthy();
    expect(screen.getByText("Layer 22A does not predict individual student outcomes.")).toBeTruthy();
    expect(screen.getByText("Cohort size is below the minimum threshold; cohort-derived detail is suppressed.")).toBeTruthy();
    expect(screen.getByText("Sample curriculum mappings are structured placeholders.")).toBeTruthy();
    expect(screen.getByText("Forecast-based gaps should be treated as prompts for review.")).toBeTruthy();
    expect(screen.getByText("Benchmark scores are deterministic directional comparisons.")).toBeTruthy();
    expect(screen.getByText("No student target market met the minimum group threshold.")).toBeTruthy();
    expect(screen.getAllByText(/Source basis/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Historical depth/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Provenance/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Raw student searches/i)).toBeTruthy();
    expect(document.body.textContent ?? "").not.toContain("student_user_id");
    expect(document.body.textContent ?? "").not.toContain("saved_artifact_id");

    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url]) =>
        url === "/api/institutions/organizations/org_demo/decision-dashboard"
      )).toBe(true);
      expect(fetchMock.mock.calls.some(([url]) =>
        url === "/api/institutions/organizations/org_demo/curriculum-market-map"
      )).toBe(true);
      expect(fetchMock.mock.calls.some(([url]) =>
        url === "/api/institutions/organizations/org_demo/workforce-reports/regional_workforce_opportunity"
      )).toBe(true);
      expect(fetchMock.mock.calls.some(([url]) =>
        url === "/api/institutions/organizations/org_demo/benchmarks"
      )).toBe(true);
    });
  });
});
