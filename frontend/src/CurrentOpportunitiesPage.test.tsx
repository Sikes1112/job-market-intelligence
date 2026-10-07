// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import CurrentOpportunitiesPage from "./CurrentOpportunitiesPage";
import type { FrontendAuthContextValue } from "./auth";
import type {
  ApiEnvelope,
  CurrentOpportunityCoveragePayload,
  CurrentOpportunityDiagnostic,
  CurrentOpportunityMatchPayload,
  CurrentOpportunityPayload,
  CurrentOpportunityRefreshRun,
} from "./types";
import { parseRoute } from "./urlState";
import {
  ApiError,
  getCurrentOpportunities,
  getCurrentOpportunity,
  getCurrentOpportunityCoverage,
  getCurrentOpportunityDiagnostics,
  getCurrentOpportunityMatches,
  getCurrentOpportunityRefreshRuns,
} from "./api";

vi.mock("./api", () => {
  class MockApiError extends Error {
    statusCode?: number;

    constructor(message: string, options?: { statusCode?: number }) {
      super(message);
      this.name = "ApiError";
      this.statusCode = options?.statusCode;
    }
  }

  return {
    ApiError: MockApiError,
    getCurrentOpportunities: vi.fn(),
    getCurrentOpportunity: vi.fn(),
    getCurrentOpportunityCoverage: vi.fn(),
    getCurrentOpportunityDiagnostics: vi.fn(),
    getCurrentOpportunityMatches: vi.fn(),
    getCurrentOpportunityRefreshRuns: vi.fn(),
  };
});

const auth: FrontendAuthContextValue = {
  isConfigured: true,
  isAuthenticated: true,
  isLoading: false,
  error: null,
  user: { email: "current@example.com", sub: "auth0|current" },
  login: async () => undefined,
  logout: () => undefined,
  getAccessTokenSilently: async () => "token",
};

describe("CurrentOpportunitiesPage", () => {
  beforeEach(() => {
    vi.mocked(getCurrentOpportunityMatches).mockResolvedValue(envelope({ matches: [match("opp_direct"), match("opp_adjacent", {
      strategic_relevance: "adjacent_fit",
      match_score: 0.58,
      contributing_factors: ["strategy term overlap"],
      opportunity: opportunity("opp_adjacent", {
        normalized_title: "Platform Quality Engineer",
        application_url: "javascript:alert(1)",
        freshness_state: "stale",
        freshness_age_hours: 120,
        ranking_eligible: false,
        ranking_ineligible_reasons: ["freshness_stale"],
      }),
    })] }));
    vi.mocked(getCurrentOpportunities).mockResolvedValue(envelope({ opportunities: [opportunity("opp_direct"), opportunity("opp_adjacent")] }));
    vi.mocked(getCurrentOpportunityCoverage).mockResolvedValue(envelope(coverage("limited")));
    vi.mocked(getCurrentOpportunity).mockResolvedValue(envelope(opportunity("opp_direct")));
    vi.mocked(getCurrentOpportunityDiagnostics).mockResolvedValue(envelope({
      diagnostics: [
        diagnostic("stale_source", "warning", "Source src_static has stale or unknown observations."),
        diagnostic("ranking_degradation_no_eligible_opportunities", "blocking", "Canonical opportunities exist but none are ranking eligible."),
      ],
    }));
    vi.mocked(getCurrentOpportunityRefreshRuns).mockResolvedValue(envelope({
      runs: [
        refreshRun("run_ok", "completed"),
        refreshRun("run_failed", "failed", { failure_count: 1, failure_details: { reason: "upstream timeout" } }),
      ],
    }));
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  test("renders strategic matches without treating match score as probability", async () => {
    render(<CurrentOpportunitiesPage auth={auth} />);

    expect(await screen.findByText("Strategic Current Opportunities")).toBeInTheDocument();
    expect(screen.getByText("Backend Engineer")).toBeInTheDocument();
    expect(screen.getAllByText("Direct strategic fit").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Adjacent strategic route").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Limited coverage").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/opportunity set may be incomplete/i).length).toBeGreaterThan(0);
    expect(document.body.textContent).not.toContain("82%");
    expect(document.body.textContent).not.toMatch(/chance of success/i);
  });

  test("renders detail provenance and blocks unsafe application URLs", async () => {
    vi.mocked(getCurrentOpportunity).mockResolvedValue(envelope(opportunity("opp_adjacent", {
      normalized_title: "Platform Quality Engineer",
      application_url: "data:text/html,unsafe",
      coverage_limitations: ["Coverage is test-only and not exhaustive."],
    })));

    render(<CurrentOpportunitiesPage auth={auth} opportunityId="opp_adjacent" />);

    expect(await screen.findByText("Opportunity detail")).toBeInTheDocument();
    expect(screen.getByText(/Observed from 1 governed source link/i)).toBeInTheDocument();
    expect(screen.getAllByText("Application route unavailable").length).toBeGreaterThan(0);
    expect(document.body.innerHTML).not.toContain("data:text/html");
  });

  test("keeps backend and frontend application-route safety aligned for local hosts", async () => {
    vi.mocked(getCurrentOpportunity).mockResolvedValue(envelope(opportunity("opp_local", {
      application_url: "http://127.0.0.1/admin",
    })));

    render(<CurrentOpportunitiesPage auth={auth} opportunityId="opp_local" />);

    expect(await screen.findByText("Opportunity detail")).toBeInTheDocument();
    expect(screen.getAllByText("Application route unavailable").length).toBeGreaterThan(0);
    expect(document.body.innerHTML).not.toContain("127.0.0.1");
  });

  test("distinguishes unsupported coverage from no opportunities", async () => {
    vi.mocked(getCurrentOpportunityMatches).mockResolvedValue(envelope({ matches: [] }));
    vi.mocked(getCurrentOpportunities).mockResolvedValue(envelope({ opportunities: [] }));
    vi.mocked(getCurrentOpportunityCoverage).mockResolvedValue(envelope(coverage("unsupported")));

    render(<CurrentOpportunitiesPage auth={auth} />);

    expect(await screen.findByText("Current coverage is not supported for this scope")).toBeInTheDocument();
    expect(screen.getAllByText(/cannot make an exhaustive claim/i).length).toBeGreaterThan(0);
    expect(document.body.textContent).not.toMatch(/no jobs exist/i);
  });

  test("renders operator diagnostics and refresh run receipts", async () => {
    render(<CurrentOpportunitiesPage auth={auth} operations />);

    expect(await screen.findByText("Current Opportunity Health")).toBeInTheDocument();
    expect(screen.getByText("Stale Source")).toBeInTheDocument();
    expect(screen.getByText("Ranking Degradation No Eligible Opportunities")).toBeInTheDocument();
    expect(screen.getAllByText("src_static").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/1 acquired, 1 normalized, 1 promoted/i).length).toBeGreaterThan(0);
  });

  test("keeps operator diagnostics restricted when backend returns forbidden", async () => {
    vi.mocked(getCurrentOpportunityDiagnostics).mockRejectedValue(new ApiError("Forbidden", { statusCode: 403 }));

    render(<CurrentOpportunitiesPage auth={auth} operations />);

    await waitFor(() => expect(screen.getByText("Operator access required")).toBeInTheDocument());
    expect(document.body.textContent).not.toContain("Source src_static");
  });

  test("supports route parsing for list, detail, and operations", () => {
    expect(parseRoute("/markets/current-opportunities", "").page).toBe("current-opportunities");
    expect(parseRoute("/markets/current-opportunities/opp_1", "").opportunityId).toBe("opp_1");
    expect(parseRoute("/markets/current-opportunities/operations", "").page).toBe("current-opportunity-operations");
  });

  test("renders unauthenticated sign-in state", async () => {
    const login = vi.fn(async () => undefined);
    render(<CurrentOpportunitiesPage auth={{ ...auth, isAuthenticated: false, login }} />);

    fireEvent.click(await screen.findByRole("button", { name: "Sign in" }));
    expect(login).toHaveBeenCalled();
  });
});

function envelope<T>(data: T): ApiEnvelope<T> {
  return {
    status: "success",
    data,
    metadata: { state: "test", source_versions: {}, warnings: [] },
    error: null,
  };
}

function opportunity(
  opportunityId: string,
  overrides: Partial<CurrentOpportunityPayload> = {},
): CurrentOpportunityPayload {
  return {
    opportunity_id: opportunityId,
    company_id: "comp_acme",
    company_name: "Acme Robotics",
    original_title: "Software Engineer I",
    normalized_title: "Backend Engineer",
    role_family: "software_engineering",
    seniority_level: "entry_level",
    market_id: "greater_boston",
    market_label: "Greater Boston",
    location_text: "Greater Boston hybrid",
    work_arrangement: "hybrid",
    compensation_min: 100000,
    compensation_max: 120000,
    compensation_currency: "USD",
    compensation_interval: "annual",
    employment_type: "full_time",
    opportunity_type: "job",
    posting_date: "2026-09-01",
    closing_date: null,
    application_url: "https://jobs.acme.example/apply",
    source_url: "https://jobs.acme.example/job",
    description_text: "Build cloud systems with Python.",
    skills: ["Python", "Cloud"],
    requirements: ["Entry-level software experience"],
    status: "active",
    freshness_state: "fresh",
    freshness_age_hours: 24,
    first_observed_at: "2026-09-01T12:00:00Z",
    last_observed_at: "2026-09-02T12:00:00Z",
    last_collected_at: "2026-09-02T12:00:00Z",
    canonical_updated_at: "2026-09-02T12:00:00Z",
    normalization_confidence: "high",
    identity_confidence: "high",
    ranking_eligible: true,
    ranking_ineligible_reasons: [],
    coverage_status: "limited",
    coverage_limitations: ["Coverage is limited; do not treat absence as exhaustive."],
    provenance: {
      source_count: 1,
      sources: [
        {
          source_id: "src_static",
          provider_record_id: "job-1",
          active: true,
          source_trust: "high",
          display_use_allowed: true,
          ranking_use_allowed: true,
          last_collected_at: "2026-09-02T12:00:00Z",
        },
      ],
    },
    warnings: [],
    ...overrides,
  };
}

function match(
  opportunityId: string,
  overrides: Partial<CurrentOpportunityMatchPayload> = {},
): CurrentOpportunityMatchPayload {
  const baseOpportunity = overrides.opportunity ?? opportunity(opportunityId);
  return {
    opportunity: baseOpportunity,
    match_score: 0.82,
    strategic_relevance: "direct_fit",
    contributing_factors: ["career identity and decision term overlap"],
    warnings: [],
    limitations: baseOpportunity.coverage_limitations,
    ranking_eligible: baseOpportunity.ranking_eligible,
    ...overrides,
  };
}

function coverage(status: CurrentOpportunityCoveragePayload["effective_status"]): CurrentOpportunityCoveragePayload {
  return {
    market_key: "greater_boston",
    role_family: "software_engineering",
    opportunity_type: "job",
    status,
    effective_status: status,
    rationale: "Deterministic test-only coverage contract.",
    limitations: status === "production_ready" ? [] : ["Coverage is not exhaustive."],
    source_basis: { sources: ["src_static"] },
    minimum_expected_sources: 1,
    freshness_max_age_hours: 72,
    last_evaluated_at: "2026-09-02T12:00:00Z",
  };
}

function diagnostic(code: string, severity: string, message: string): CurrentOpportunityDiagnostic {
  return {
    code,
    severity,
    message,
    scope: { source_id: "src_static" },
    evidence: { age_hours: 120 },
  };
}

function refreshRun(
  runId: string,
  status: string,
  overrides: Partial<CurrentOpportunityRefreshRun> = {},
): CurrentOpportunityRefreshRun {
  return {
    run_id: runId,
    source_id: "src_static",
    status,
    acquired_count: 1,
    normalized_count: 1,
    promoted_count: 1,
    duplicate_count: 0,
    rejected_count: 0,
    warning_count: 0,
    failure_count: 0,
    started_at: "2026-09-02T12:00:00Z",
    completed_at: "2026-09-02T12:01:00Z",
    warnings: [],
    failure_details: {},
    ...overrides,
  };
}
