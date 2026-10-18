// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import App from "./App";

function envelope(data: unknown, status = "success") {
  return {
    status,
    data,
    metadata: {
      state: "test",
      source_versions: {},
      warnings: [],
      confidence: "confidence" in (data as Record<string, unknown>)
        ? (data as Record<string, unknown>).confidence
        : undefined,
      freshness: "freshness" in (data as Record<string, unknown>)
        ? (data as Record<string, unknown>).freshness
        : undefined,
      limitations: "limitations" in (data as Record<string, unknown>)
        ? (data as Record<string, unknown>).limitations
        : undefined,
      public_safe: true,
    },
    error: null,
  };
}

function regionsPayload() {
  return {
    regions: [
      {
        region_id: "greater_boston",
        display_name: "Greater Boston",
        region_type: "greater_region",
      },
      {
        region_id: "greater_atlanta",
        display_name: "Greater Atlanta",
        region_type: "greater_region",
      },
    ],
  };
}

function confidence(level = "medium") {
  return {
    level,
    score: level === "high" ? 0.82 : 0.58,
    label: `${level} confidence; local validation recommended`,
    factors: [],
  };
}

function freshness() {
  return {
    generated_at: "2026-06-27T12:00:00Z",
    freshness_status: "fresh",
    freshness_expires_at: "2099-01-01T12:00:00Z",
    stale: false,
    notes: ["Input freshness windows are currently fresh."],
  };
}

function sourceSummary() {
  return {
    data_basis: "canonical_market_truth",
    source_count: 9,
    source_categories: ["company_region_hiring", "company_region_entry_level"],
    evidence_summary: [
      "5 demonstrated present employers",
      "5 employer hiring signal rows",
      "5 employer early-career signal rows",
    ],
  };
}

function publicSafety() {
  return {
    public_safe: true,
    redacted_internal_fields: ["reviewer identities", "raw partner submission JSON"],
    student_level_data_exposed: false,
    partner_submission_internals_exposed: false,
    private_review_fields_exposed: false,
  };
}

function warning(code = "low_peer_comparison_coverage") {
  return {
    code,
    severity: "medium",
    message: "Few comparable regions had enough structured signals for peer comparison.",
    public_interpretation: "Peer comparisons are directional and should be validated with local regional context.",
  };
}

function metric(metric_id: string, label: string, score: number | null, band = "moderate") {
  return {
    metric_id,
    label,
    score,
    band: score === null ? "unknown" : band,
    polarity: metric_id.includes("risk") || metric_id.includes("dependency")
      ? "higher_is_risk"
      : "higher_is_better",
    interpretation_label: `${label} API interpretation`,
    explainable_inputs: { fixture: true },
    limitations: [`${label} limitation from API`],
    warning_codes: [],
  };
}

function workforceDashboard() {
  return {
    region_summary: {
      region_id: "greater_boston",
      region_name: "Greater Boston",
      region_type: "greater_region",
      present_company_count: 5,
      hiring_record_count: 5,
      entry_level_record_count: 5,
      score_available: true,
      normalization_basis: "demonstrated_present_companies",
    },
    core_metrics: {
      opportunity_concentration_score: metric("opportunity_concentration", "Opportunity concentration", 0.68, "high"),
      early_career_access_score: metric("early_career_access", "Early-career access", 0.42),
      internship_pipeline_score: metric("internship_pipeline", "Internship pipeline", 0.18, "low"),
      employer_dependency_score: metric("employer_dependency", "Employer dependency", 0.72, "high"),
      sector_diversity_score: metric("sector_diversity", "Sector diversity", 0.33, "low"),
      talent_export_risk_score: metric("talent_export_risk", "Talent export risk", 0.66, "high"),
    },
    policy_findings: [
      {
        finding_id: "finding_policy_api",
        finding_type: "internship_pipeline_weakness",
        severity: "medium",
        title: "API internship pathway finding",
        summary: "Available data suggests internships are less visible than full-time demand.",
        evidence_references: ["metric:internship_pipeline"],
        recommended_interpretation: "Further local validation is recommended.",
        recommended_actions: ["Validate employer pathways."],
        confidence: "medium",
        limitations: ["Finding limitation from API."],
      },
    ],
    warnings: [warning("bounded_public_interpretation")],
    confidence: confidence(),
    freshness: freshness(),
    source_summary: sourceSummary(),
    public_safe: true,
    public_safety: publicSafety(),
  };
}

function sectorGap() {
  return {
    sector: "software",
    gap_type: "internship_pathway_gap",
    severity: "medium",
    evidence_references: ["company_region_hiring", "company_region_entry_level"],
    interpretation: "Available signals suggest software has employer demand but limited internship evidence.",
    recommended_strategy_candidate: "This sector may benefit from further local validation of student-facing pathways.",
    confidence: "medium",
    limitations: ["Sector finding limitation from API."],
  };
}

function peerComparison() {
  return {
    peer_region_id: "greater_atlanta",
    peer_region_name: "Greater Atlanta",
    similarity_score: 0.74,
    similarity_rationale: "Peer selected by similarity across available policy metrics.",
    metrics_compared: [
      {
        metric_id: "early_career_access",
        target_value: 0.42,
        peer_value: 0.64,
        comparison: "target_weaker",
      },
    ],
    target_region_stronger: ["employer_dependency"],
    target_region_weaker: ["early_career_access"],
    confidence: "medium",
    limitations: ["Peer limitation from API."],
  };
}

function economicProfile() {
  return {
    region_id: "greater_boston",
    region_name: "Greater Boston",
    analysis_window: { label: "current_available_market_signals", generated_at: "2026-06-27T12:00:00Z", freshness_expires_at: null },
    regional_policy_profile: {},
    sector_gap_findings: [sectorGap()],
    employer_base_risk_findings: [
      {
        risk_type: "employer_dependency",
        severity: "medium",
        interpretation: "Available signals suggest the regional employer base may be sensitive to a concentrated set of employers.",
        evidence_references: ["metric:employer_dependency"],
        strategy_candidate: "Compare adjacent employer categories that could broaden opportunity access.",
        confidence: "medium",
        limitations: ["Risk finding limitation from API."],
      },
    ],
    peer_metro_comparisons: [peerComparison()],
    company_attraction_candidates: [
      {
        company_id: "candidate_api",
        company_name: "API Candidate Systems",
        sector: "software",
        fit_score: 0.72,
        fit_band: "high",
        fit_rationale: "This company appears directionally aligned with an identified sector gap.",
        regional_gap_addressed: "sector:software",
        early_career_or_internship_relevance: "Early-career relevance is visible in other tracked regions.",
        diversification_impact: "This employer type may be useful for regional diversification analysis.",
        confidence: "medium",
        limitations: ["This is a strategy candidate, not an expansion prediction."],
      },
    ],
    diversification_recommendations: [
      {
        candidate_type: "sector_gap_validation",
        title: "Software gap validation",
        rationale: "This sector may benefit from local validation.",
        evidence_references: ["company_region_hiring"],
        confidence: "medium",
        limitations: ["Diversification limitation from API."],
      },
    ],
    warnings: [warning()],
    confidence: confidence(),
    freshness: freshness(),
    source_summary: sourceSummary(),
    limitations: ["Economic development limitation from API."],
    public_safe: true,
    public_safety: publicSafety(),
  };
}

function educationProfile() {
  return {
    region_id: "greater_boston",
    region_name: "Greater Boston",
    analysis_window: { label: "current_available_market_signals", generated_at: "2026-06-27T12:00:00Z", freshness_expires_at: null },
    institution_pipeline_summaries: [
      {
        institution_id: "policy_state_university",
        institution_name: "Policy State University",
        region_id: "greater_boston",
        program_areas_available: [],
        related_demand_sectors: ["software", "ai"],
        nearby_early_career_demand_summary: "3 companies with early-career signals across 5 hiring-company sector observations.",
        internship_access_summary: "2 internship or co-op signals are visible in aggregate.",
        alignment_confidence: "medium",
        limitations: ["Institution pipeline limitation from API."],
      },
    ],
    program_alignment_findings: [
      {
        program_area: "Computer Science",
        nearby_employer_demand: metric("program_demand_computer_science", "Computer Science nearby employer demand", 0.62),
        internship_pipeline_strength: metric("program_internship_computer_science", "Computer Science internship pipeline strength", 0.28, "low"),
        early_career_access: metric("program_access_computer_science", "Computer Science early-career access", 0.46),
        alignment_score: 0.45,
        alignment_band: "moderate",
        finding: "Computer Science has mixed alignment with available local employer and internship signals.",
        confidence: "medium",
        limitations: ["No individual student outcomes are inferred."],
      },
    ],
    internship_alignment_gaps: [sectorGap()],
    local_employer_absorption_score: metric("local_employer_absorption", "Local employer absorption", 0.44),
    talent_export_pressure_score: metric("talent_export_risk", "Talent export risk", 0.66, "high"),
    student_interest_market_fit: metric("student_interest_market_fit", "Student interest market fit", null),
    warnings: [warning("aggregate_only_education_alignment")],
    confidence: confidence(),
    freshness: freshness(),
    source_summary: sourceSummary(),
    limitations: ["Education alignment is aggregate-only and public-safe."],
    public_safe: true,
    public_safety: publicSafety(),
  };
}

function peerProfile() {
  return {
    region_id: "greater_boston",
    region_name: "Greater Boston",
    analysis_window: { label: "current_available_market_signals", generated_at: "2026-06-27T12:00:00Z", freshness_expires_at: null },
    peer_metro_comparisons: [peerComparison()],
    warnings: [warning()],
    confidence: confidence(),
    freshness: freshness(),
    source_summary: sourceSummary(),
    limitations: ["The peer set is limited because not enough regions have comparable data."],
    public_safe: true,
    public_safety: publicSafety(),
  };
}

function policyReport() {
  return {
    report_id: "layer24_policy_report:greater_boston",
    slug: "layer-24-early-career-opportunity-greater-boston",
    title: "The Geography of Early-Career Tech Opportunity",
    category: "policy-workforce-intelligence",
    report_period: "2026-06-27",
    summary: "Available Layer 24 signals for Greater Boston summarize early-career access.",
    markets_covered: [{ market_id: "greater_boston", market_label: "Greater Boston", coverage_note: "Coverage follows Layer 24 warnings." }],
    market_results: [{
      result_type: "featured",
      rank: null,
      market_id: "greater_boston",
      market_label: "Greater Boston",
      headline: "API report headline from backend payload",
      rationale: "Available data suggests this region has a bounded early-career opportunity profile.",
      evidence_signals: ["early-career access", "internship pipeline"],
      freshness_date: "2026-06-27",
      confidence: "medium",
      warnings: ["Report warning from API."],
      source_provenance_summary: {
        data_basis: "public_safe_summary",
        source_count: 9,
        source_categories: ["company_region_hiring"],
        provenance_notes: ["No raw source references are exposed."],
      },
    }],
    methodology_summary: "This Layer 24 report is generated from the backend workforce dashboard payload.",
    limitations: ["Report limitation from API."],
    freshness_date: "2026-06-27",
    freshness_status: "fresh",
    confidence: "medium",
    warnings: ["Report warning from API."],
    source_provenance_summary: {
      data_basis: "public_safe_summary",
      source_count: 9,
      source_categories: ["company_region_hiring"],
      provenance_notes: ["No raw source references are exposed."],
    },
    related_links: [],
    suggested_citation: {
      source_name: "Job Market Intelligence",
      title: "The Geography of Early-Career Tech Opportunity",
      period: "2026-06-27",
      product_attribution: "Layer 24",
      public_path: "/reports/layer-24-early-career-opportunity-greater-boston",
      accessed_or_freshness_date: "2026-06-27",
    },
    share_summary: {
      title: "The Geography of Early-Career Tech Opportunity",
      category_claim: "Regional early-career opportunity",
      confidence_label: "Medium confidence",
      freshness_label: "Fresh",
      takeaway: "API report headline from backend payload",
      public_path: "/reports/layer-24-early-career-opportunity-greater-boston",
      warning: "Layer 24 report uses bounded policy intelligence.",
    },
    source_authority: { labels: ["Layer 24"], summary: "Backend-generated Layer 24 report." },
    institutional_cta: {
      label: "Use this report for aggregate workforce planning",
      body: "Use as a starting point for local validation.",
      href: "/markets/policy/regions/greater_boston/workforce",
      link_type: "public_page",
    },
  };
}

function payloadFor(input: RequestInfo | URL) {
  const value = typeof input === "string" ? input : input.toString();
  if (value === "/health") return { service: "test" };
  if (value === "/regions") return regionsPayload();
  if (value === "/regions/search") return { regions: [], count: 0 };
  if (value === "/policy/regions/greater_boston/workforce-dashboard") return workforceDashboard();
  if (value === "/policy/regions/greater_boston/economic-development") return economicProfile();
  if (value === "/policy/regions/greater_boston/education-alignment") return educationProfile();
  if (value === "/policy/regions/greater_boston/peer-comparison") return peerProfile();
  if (value === "/policy/regions/greater_boston/reports/early-career-opportunity") return policyReport();
  if (value === "/me") return { user: { user_id: "user_demo", status: "active" } };
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
  const fetchMock = vi.fn<(input: RequestInfo | URL) => Promise<Response>>(async (input) =>
    new Response(JSON.stringify(envelope(payloadFor(input))), {
      headers: { "Content-Type": "application/json" },
      status: 200,
    })
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("Layer 24 policy routes", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    window.history.pushState(null, "", "/");
  });

  test("policy landing renders audiences and links without fake metrics", async () => {
    stubFetch();
    window.history.pushState(null, "", "/markets/policy");

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Policy, workforce, and economic intelligence" })).toBeTruthy();
    expect(screen.getByText("Public-sector workforce planning")).toBeTruthy();
    expect(screen.getByText("University career office strategy")).toBeTruthy();
    expect(screen.queryByText("Opportunity concentration API interpretation")).toBeNull();
  });

  test("public-demo mode hides blocked nav items and renders policy unavailable state", async () => {
    vi.stubEnv("VITE_PUBLIC_DEMO", "true");
    const fetchMock = stubFetch();
    window.history.pushState(null, "", "/markets/policy/regions/greater_boston/workforce");

    render(<App />);

    expect(await screen.findByText("Policy intelligence is not available in public demo")).toBeTruthy();
    expect(screen.queryByRole("link", { name: /Opportunity Routes/i })).toBeNull();
    expect(screen.queryByRole("link", { name: /Policy/i })).toBeNull();
    expect(fetchMock.mock.calls.some(([url]) =>
      String(url).startsWith("/policy/")
    )).toBe(false);
  });

  test("regional policy dashboard consumes backend metrics and safety metadata", async () => {
    stubFetch();
    window.history.pushState(null, "", "/markets/policy/regions/greater_boston/workforce");

    render(<App />);

    expect(await screen.findByText("Opportunity concentration API interpretation")).toBeTruthy();
    expect(screen.getByText("API internship pathway finding")).toBeTruthy();
    expect(screen.getByText("Confidence, freshness, and sources")).toBeTruthy();
    expect(screen.getByText(/Aggregate data only; no student-level records/i)).toBeTruthy();
    expect(screen.getByText("Input freshness windows are currently fresh.")).toBeTruthy();
  });

  test("economic development route frames company candidates as strategy analysis", async () => {
    stubFetch();
    window.history.pushState(null, "", "/markets/policy/regions/greater_boston/economic-development");

    render(<App />);

    expect(await screen.findByText("Sector gap findings")).toBeTruthy();
    expect(screen.getByText("API Candidate Systems")).toBeTruthy();
    expect(screen.getByText("Strategy-analysis candidate")).toBeTruthy();
    expect(screen.getByText("This is a strategy candidate, not an expansion prediction.")).toBeTruthy();
    expect(screen.queryByText(/will expand/i)).toBeNull();
    expect(screen.queryByText(/tax incentives/i)).toBeNull();
  });

  test("education alignment route displays aggregate-only guardrails", async () => {
    stubFetch();
    window.history.pushState(null, "", "/markets/policy/regions/greater_boston/education-alignment");

    render(<App />);

    expect(await screen.findByText("Aggregate-only education alignment")).toBeTruthy();
    expect(screen.getByText("Policy State University")).toBeTruthy();
    expect(screen.getByText("Computer Science")).toBeTruthy();
    expect(screen.getAllByText(/No individual student outcomes are inferred/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/should close this program/i)).toBeNull();
  });

  test("peer comparison route renders warnings, limitations, and compared metrics", async () => {
    stubFetch();
    window.history.pushState(null, "", "/markets/policy/regions/greater_boston/peer-comparison");

    render(<App />);

    expect(await screen.findByText("Greater Atlanta")).toBeTruthy();
    expect(screen.getByText("Low Peer Comparison Coverage")).toBeTruthy();
    expect(screen.getByText("The peer set is limited because not enough regions have comparable data.")).toBeTruthy();
    expect(screen.getAllByText("Early Career Access").length).toBeGreaterThan(0);
  });

  test("representative policy report route renders backend report payload", async () => {
    stubFetch();
    window.history.pushState(null, "", "/markets/policy/reports/greater_boston/early-career-opportunity");

    render(<App />);

    expect(await screen.findByText("The Geography of Early-Career Tech Opportunity")).toBeTruthy();
    expect(screen.getAllByText("API report headline from backend payload").length).toBeGreaterThan(0);
    expect(screen.getByText("This Layer 24 report is generated from the backend workforce dashboard payload.")).toBeTruthy();
    expect(screen.getByText("Report limitation from API.")).toBeTruthy();
  });

  test("policy public surfaces avoid private and unsafe language", async () => {
    stubFetch();
    window.history.pushState(null, "", "/markets/policy/regions/greater_boston/economic-development");

    render(<App />);
    await screen.findByText("API Candidate Systems");

    const rendered = document.body.textContent?.toLowerCase() ?? "";
    for (const token of [
      "private_reviewer_id",
      "raw_submission_json",
      "reviewer_id",
      "this city is failing",
      "policy x caused",
      "the city should give tax incentives",
      "students from this school will leave",
    ]) {
      expect(rendered).not.toContain(token);
    }
  });
});
