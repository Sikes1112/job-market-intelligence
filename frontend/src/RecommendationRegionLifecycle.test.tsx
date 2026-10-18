// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { StrictMode } from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import App from "./App";
import type { ApiEnvelope } from "./types";

const authState = vi.hoisted(() => ({
  value: {
    isConfigured: true,
    isAuthenticated: true,
    isLoading: false,
    error: null,
    user: { email: "reviewer@example.test", name: "Local reviewer", sub: "local|reviewer" },
    login: vi.fn(async () => undefined),
    logout: vi.fn(),
    getAccessTokenSilently: vi.fn(async () => "review-token"),
  },
}));

vi.mock("./auth", () => ({
  useFrontendAuth: () => authState.value,
}));

function envelope<T>(data: T, metadata: Record<string, unknown> = {}): ApiEnvelope<T> {
  return {
    status: "success",
    data,
    metadata: { state: "fresh", source_versions: {}, warnings: [], ...metadata },
    error: null,
  } as ApiEnvelope<T>;
}

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}

function regionsFailure(): Response {
  return jsonResponse({
    status: "error",
    data: null,
    metadata: { state: "unavailable", source_versions: {}, warnings: [] },
    error: { code: "REGIONS_UNAVAILABLE", message: "Region service is temporarily unavailable." },
  }, 503);
}

function regionsSuccess(): Response {
  return jsonResponse(envelope({
    regions: [{
      region_id: "sf_bay_area",
      display_name: "San Francisco Bay Area",
      region_type: "metro",
      parent_region_id: null,
      labor_market_group: null,
    }],
  }));
}

function personalizedSuccess(): Response {
  return jsonResponse(envelope({
    ranked_regions: [{
      region_id: "sf_bay_area",
      display_name: "San Francisco Bay Area",
      personal_market_score: 0.84,
      objective_opportunity_score: 0.71,
      match_notes: ["role:applied_ai"],
    }],
    ranked_companies: [],
  }, {
    career_identity_personalization: {
      source: "career_identity",
      career_identity_applied: true,
      career_identity_version: 2,
      role_targets: ["applied_ai"],
      industry_preferences: ["ai"],
      region_ids: ["sf_bay_area"],
    },
  }));
}

function installFetch(regionResponse: () => Response) {
  const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(async (input) => {
    const path = input.toString();
    if (path === "/regions") return regionResponse();
    if (path === "/me/discover/personalized") return personalizedSuccess();
    return jsonResponse(envelope({}));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function regionRequestCount(fetchMock: ReturnType<typeof installFetch>): number {
  return fetchMock.mock.calls.filter(([input]) => input.toString() === "/regions").length;
}

function renderForYou() {
  return render(<StrictMode><App /></StrictMode>);
}

describe("For You region request lifecycle", () => {
  beforeEach(() => {
    window.history.pushState(null, "", "/markets/recommendations?mode=for-you");
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
    window.history.pushState(null, "", "/");
  });

  test("loads regions once in Strict Mode and continues to authenticated personalization", async () => {
    const fetchMock = installFetch(regionsSuccess);
    renderForYou();

    expect(await screen.findByRole("heading", { name: /San Francisco Bay Area best matches/i })).toBeInTheDocument();
    expect(regionRequestCount(fetchMock)).toBe(1);
    expect(fetchMock.mock.calls.filter(([input]) => input.toString() === "/me/discover/personalized")).toHaveLength(1);
  });

  test("bounds a persistent failure across rerenders and retries only on user intent", async () => {
    const fetchMock = installFetch(regionsFailure);
    const view = renderForYou();

    expect(await screen.findByRole("alert")).toHaveTextContent("Region service is temporarily unavailable.");
    expect(regionRequestCount(fetchMock)).toBe(1);

    view.rerender(<StrictMode><App /></StrictMode>);
    view.rerender(<StrictMode><App /></StrictMode>);
    await act(async () => Promise.resolve());
    expect(regionRequestCount(fetchMock)).toBe(1);

    fireEvent.click(screen.getByRole("button", { name: "Retry For You" }));
    await waitFor(() => expect(regionRequestCount(fetchMock)).toBe(2));
    expect(await screen.findByRole("alert")).toHaveTextContent("Region service is temporarily unavailable.");

    view.rerender(<StrictMode><App /></StrictMode>);
    await act(async () => Promise.resolve());
    expect(regionRequestCount(fetchMock)).toBe(2);
  });

  test("recovers after an explicit retry when the region service becomes available", async () => {
    let available = false;
    const fetchMock = installFetch(() => available ? regionsSuccess() : regionsFailure());
    renderForYou();

    expect(await screen.findByRole("alert")).toHaveTextContent("Region service is temporarily unavailable.");
    expect(regionRequestCount(fetchMock)).toBe(1);

    available = true;
    fireEvent.click(screen.getByRole("button", { name: "Retry For You" }));

    expect(await screen.findByRole("heading", { name: /San Francisco Bay Area best matches/i })).toBeInTheDocument();
    expect(regionRequestCount(fetchMock)).toBe(2);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
