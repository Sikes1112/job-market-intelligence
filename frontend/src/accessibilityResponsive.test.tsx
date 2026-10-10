// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import App from "./App";
import type { ApiEnvelope, CareerIdentity, CareerIdentityCompleteness } from "./types";

const authState = vi.hoisted(() => ({
  value: {
    isConfigured: true,
    isAuthenticated: true,
    isLoading: false,
    error: null,
    user: { email: "accessibility@example.com", sub: "auth0|accessibility-route" },
    login: vi.fn(async () => undefined),
    logout: vi.fn(),
    getAccessTokenSilently: vi.fn(async () => "accessibility-token"),
  },
}));

vi.mock("./auth", () => ({
  useFrontendAuth: () => authState.value,
}));

vi.mock("./ExplorePage", () => ({ default: () => <div>Explore route content</div> }));

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
    career_identity_id: "ci_accessibility",
    user_id: "user_accessibility",
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
    created_at: "2026-09-02T12:00:00Z",
    updated_at: "2026-09-02T12:00:00Z",
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

function stubFetch() {
  const identity = careerIdentity();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const path = input.toString();
      const data =
        path === "/regions"
          ? { regions: [] }
          : path === "/companies"
            ? { companies: [] }
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
                  : {};
      return new Response(JSON.stringify(envelope(data)), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      });
    }),
  );
}

describe("Layer 39C accessibility and responsive shell contracts", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
    window.history.pushState(null, "", "/");
  });

  test("authenticated app shell exposes skip link, navigation, and main landmark", () => {
    stubFetch();
    window.history.pushState(null, "", "/markets/career-identity");

    const { container } = render(<App />);

    expect(screen.getByRole("link", { name: "Skip to main content" })).toHaveAttribute(
      "href",
      "#main-content",
    );
    expect(screen.getByRole("navigation", { name: "Main navigation" })).toBeInTheDocument();
    expect(screen.getByRole("main")).toHaveAttribute("id", "main-content");
    expect(screen.getByRole("status")).toHaveTextContent("Loading workspace");
    expect(container.querySelector(".app-shell")).toBeInTheDocument();
    expect(container.querySelector(".primary-product-nav")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Explore" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "My Search" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Profile" }).length).toBeGreaterThan(0);
    expect(screen.queryByRole("link", { name: "Institution" })).not.toBeInTheDocument();
    expect(container.querySelector(".skip-link")).toBeInTheDocument();
  });

  test("does not start legacy, account, or monetization requests on authenticated Explore", async () => {
    stubFetch();
    window.history.pushState(null, "", "/markets");
    render(<App />);
    expect(await screen.findByText("Explore route content")).toBeInTheDocument();
    expect(vi.mocked(fetch)).not.toHaveBeenCalled();
  });

  test("global role search writes the Explore role override rather than free-text q", async () => {
    stubFetch();
    window.history.pushState(null, "", "/markets");
    render(<App />);
    const search = screen.getByRole("searchbox", { name: "Search markets or roles" });
    fireEvent.change(search, { target: { value: "AI / machine learning" } });
    fireEvent.submit(search.closest("form")!);
    await waitFor(() => expect(window.location.search).toBe("?role=ai_ml"));
  });

  test.each([
    ["institution", "/markets/institution", "Institution workspace"],
    ["policy", "/markets/policy", "Policy intelligence"],
    ["operator", "/markets/current-opportunities/operations", "Opportunity data operations"],
  ])("keeps the %s route outside the individual shell", async (_family, path, heading) => {
    stubFetch();
    window.history.pushState(null, "", path);
    const { container } = render(<App />);
    expect(await screen.findByText(heading)).toBeInTheDocument();
    expect(container.querySelector(".secondary-context-shell")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Main navigation" })).not.toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Mobile navigation" })).not.toBeInTheDocument();
  });
});
