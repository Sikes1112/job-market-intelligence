// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import App from "./App";
import { isProductPage, parseRoute } from "./urlState";
import type { ApiEnvelope, CareerIdentity, CareerIdentityCompleteness } from "./types";

const authState = vi.hoisted(() => ({
  value: {
    isConfigured: true,
    isAuthenticated: true,
    isLoading: false,
    error: null,
    user: { email: "career@example.com", sub: "auth0|career-route" },
    login: vi.fn(async () => undefined),
    logout: vi.fn(),
    getAccessTokenSilently: vi.fn(async () => "route-token"),
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

function careerIdentity(): CareerIdentity {
  return {
    career_identity_id: "ci_route",
    user_id: "user_route",
    current_version: 1,
    completeness_state: "empty",
    sufficiency_state: "insufficient",
    privacy: {
      ingestion_consent_granted: false,
      inference_consent_granted: false,
      downstream_personalization_consent_granted: false,
      retain_import_metadata: true,
      privacy_visibility: "private",
    },
    completeness: careerEvaluation(),
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
    created_at: "2026-08-29T12:00:00Z",
    updated_at: "2026-08-29T12:00:00Z",
  };
}

function careerEvaluation(): CareerIdentityCompleteness {
  return {
    identity_version: 1,
    overall_score: 0,
    completeness_state: "empty",
    sufficiency_state: "insufficient",
    sufficient: false,
    strong_required_signal_count: 0,
    sections: [],
    missing_categories: ["skills", "goals", "role_preferences"],
    weak_categories: [],
    actionable_reason_codes: ["missing_skills", "missing_goals"],
  };
}

function stubAppFetch() {
  const identity = careerIdentity();
  const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(async (input) => {
    const path = input.toString();
    const data =
      path === "/health"
        ? { service: "test" }
        : path === "/regions"
          ? { regions: [] }
          : path === "/me/career-identity"
            ? identity
            : path === "/me/career-identity/evaluation"
              ? careerEvaluation()
              : path === "/me/career-identity/privacy"
                ? {
                    career_identity_id: identity.career_identity_id,
                    identity_version: identity.current_version,
                    privacy: identity.privacy,
                  }
                : null;
    return new Response(JSON.stringify(envelope(data)), {
      headers: { "Content-Type": "application/json" },
      status: 200,
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("Career Identity App route", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
    window.history.pushState(null, "", "/");
  });

  test("admits /markets/career-identity through the product route gate", async () => {
    const fetchMock = stubAppFetch();
    window.history.pushState(null, "", "/markets/career-identity");
    const route = parseRoute(window.location.pathname, window.location.search);

    expect(route.page).toBe("career-identity");
    expect(isProductPage(route.page)).toBe(true);

    render(<App />);

    expect(await screen.findByText("Private profile source of truth")).toBeInTheDocument();
    expect(screen.getByRole("tablist", { name: "Career Identity onboarding steps" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Terms and disclaimer" })).not.toBeInTheDocument();
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/me/career-identity",
        expect.objectContaining({
          headers: expect.objectContaining({ Authorization: "Bearer route-token" }),
        }),
      );
    });
  });
});
