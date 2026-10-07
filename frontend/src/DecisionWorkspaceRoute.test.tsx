// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import App from "./App";
import { isProductPage, parseRoute } from "./urlState";
import type { ApiEnvelope, CareerIdentity, WeeklyCareerReview } from "./types";

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

function stubAppFetch() {
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
              ? { decisions: [] }
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

    expect(await screen.findByRole("heading", { name: "Decision Workspace" })).toBeInTheDocument();
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
});
