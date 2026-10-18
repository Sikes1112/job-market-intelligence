// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import App from "./App";
import { isProductPage, parseRoute } from "./urlState";
import type { ApiEnvelope, CareerDecision, CareerIdentity, WeeklyCareerReview } from "./types";

const authState = vi.hoisted(() => ({
  value: {
    isConfigured: true,
    isAuthenticated: true,
    isLoading: false,
    error: null,
    user: { email: "decisions@example.com", sub: "auth0|decisions-route" },
    login: vi.fn(async () => undefined),
    logout: vi.fn(),
    getAccessTokenSilently: vi.fn(async () => "decisions-route-token"),
  },
}));

vi.mock("./auth", () => ({
  useFrontendAuth: () => authState.value,
}));

function envelope<T>(data: T): ApiEnvelope<T> {
  return {
    status: "success",
    data,
    metadata: { state: "fresh", source_versions: {}, warnings: [] },
    error: null,
  };
}

function identity(): CareerIdentity {
  return {
    career_identity_id: "ci_route_decisions",
    user_id: "user_route_decisions",
    current_version: 2,
    completeness_state: "partial",
    sufficiency_state: "sufficient",
    privacy: {
      ingestion_consent_granted: true,
      inference_consent_granted: true,
      downstream_personalization_consent_granted: true,
      retain_import_metadata: true,
      privacy_visibility: "private",
    },
    completeness: {
      identity_version: 2,
      overall_score: 72,
      completeness_state: "partial",
      sufficiency_state: "sufficient",
      sufficient: true,
      strong_required_signal_count: 4,
      sections: [],
      missing_categories: [],
      weak_categories: [],
      actionable_reason_codes: [],
    },
    facts: {
      education: [],
      experience: [],
      skill: [],
      project: [],
      credential: [],
      career_goal: [],
      role_preference: [],
      industry_preference: [],
      geographic_constraint: [],
      compensation_constraint: [],
      timing_preference: [],
      work_arrangement_preference: [],
    },
    created_at: "2026-09-01T12:00:00Z",
    updated_at: "2026-09-01T12:00:00Z",
  };
}

function quietReview(): WeeklyCareerReview {
  return {
    window_start: "2026-08-25T00:00:00Z",
    window_end: "2026-09-01T00:00:00Z",
    happened: [],
    changed: [],
    worked: [],
    did_not_work: [],
    stalled: [],
    invalidated_assumptions: [],
    reconsider: [],
    next_actions: [],
    reminders: [],
  };
}

function structuredEvidenceDecision(): CareerDecision {
  const createdAt = "2026-09-01T12:00:00Z";
  return {
    decision_id: "decision-structured-evidence",
    decision_type: "location_choice",
    status: "evaluating",
    title: "Choose a launch market",
    description: "Synthetic decision fixture.",
    decision_date: null,
    target_date: null,
    planned_review_at: null,
    time_horizon: "graduation",
    priorities: [],
    constraints: [],
    selected_option_id: null,
    career_identity_id: "ci_route_decisions",
    current_context_snapshot_id: "context-1",
    current_recommendation_id: "recommendation-1",
    current_version: 1,
    context: null,
    options: [{
      option_id: "option-sf",
      decision_id: "decision-structured-evidence",
      title: "San Francisco Bay Area",
      description: null,
      scenario: { region_ids: ["sf_bay_area"] },
      status: "active",
      position: 0,
      created_at: createdAt,
      updated_at: createdAt,
    }],
    recommendation: {
      recommendation_id: "recommendation-1",
      decision_id: "decision-structured-evidence",
      context_snapshot_id: "context-1",
      recommended_option_id: "option-sf",
      recommendation_status: "ready",
      evidence_sufficiency: "limited_evidence",
      confidence: "low",
      summary: "A bounded comparison is available.",
      fit: {
        options: [{
          option_id: "option-sf",
          title: "San Francisco Bay Area",
          assessment: "plausible",
          advantages: [],
          tradeoffs: [],
          important_unknowns: [{
            kind: "unavailable",
            reference_type: "compensation",
            reference_id: "option-sf",
            note: "Illustrative compensation does not establish a city-wide outcome.",
          }],
        }],
      },
      comparison: {},
      evidence: {
        supporting: [],
        contrary: [],
        unavailable: [{
          kind: "unavailable",
          reference_type: "market",
          reference_id: "option-sf",
          note: "External competition evidence is unavailable.",
        }],
      },
      challenges: [],
      limitations: ["Synthetic evidence remains bounded."],
      generated_at: createdAt,
    },
    explore_comparison_provenance: null,
    action_plan: null,
    applications: [],
    outcomes: [],
    created_at: createdAt,
    updated_at: createdAt,
  };
}

function stubAppFetch(decision?: CareerDecision) {
  const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(async (input) => {
    const path = input.toString();
    const data =
      path === "/health"
        ? { service: "test" }
        : path === "/regions"
          ? { regions: [] }
          : path === "/me/career-identity"
            ? identity()
            : path === "/me/decisions"
              ? { decisions: decision ? [decision] : [] }
              : path === `/me/decisions/${decision?.decision_id}`
                ? { decision }
                : path === `/me/decisions/${decision?.decision_id}/journal`
                  ? { journal: [] }
                  : path === `/me/decisions/${decision?.decision_id}/deep-analysis`
                    ? { analysis: null }
                    : path.startsWith("/me/strategic-career-reviews")
                      ? { strategic_reviews: [] }
                      : path === "/me/beta-access"
                        ? { cohorts: [], feature_gates: [] }
                        : path === "/me/feature-access/decision_feedback"
                          ? { decision: { feature_key: "decision_feedback", allowed: false, reason: "test", cohort_keys: [], access_mode: null, entitlement_source: null, configuration: {} } }
              : path === "/me/reviews/weekly"
                ? { review: quietReview() }
                : {};
    return new Response(JSON.stringify(envelope(data)), {
      headers: { "Content-Type": "application/json" },
      status: 200,
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("Decision Workspace App route", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
    window.history.pushState(null, "", "/");
  });

  test("admits /markets/decisions through the product route gate", async () => {
    const fetchMock = stubAppFetch();
    window.history.pushState(null, "", "/markets/decisions");
    const route = parseRoute(window.location.pathname, window.location.search);

    expect(route.page).toBe("decisions");
    expect(isProductPage(route.page)).toBe(true);

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Compare a real career choice" })).toBeInTheDocument();
    expect(screen.getByText("No career decisions yet")).toBeInTheDocument();
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/me/decisions",
        expect.objectContaining({
          headers: expect.objectContaining({ Authorization: "Bearer decisions-route-token" }),
        }),
      );
    });
  });

  test("renders structured decision unknowns and evidence notes without raw-object failures", async () => {
    const decision = structuredEvidenceDecision();
    stubAppFetch(decision);
    window.history.pushState(null, "", "/markets/decisions");

    render(<App />);

    expect(await screen.findByText(
      "Illustrative compensation does not establish a city-wide outcome.",
    )).toBeInTheDocument();
    expect(screen.getByText("External competition evidence is unavailable.")).toBeInTheDocument();
  });
});
