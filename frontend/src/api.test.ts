import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import {
  ApiError,
  createSavedMarketArtifact,
  deleteSavedMarketArtifact,
  dismissAlert,
  explainAlert,
  explainComparison,
  explainCompany,
  explainRegion,
  getCurrentUser,
  getRecommendationGoalModes,
  getRecommendationStrategy,
  getRegions,
  listAlerts,
  listSavedMarketArtifacts,
  markAlertRead,
  previewScoringOverlay,
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
