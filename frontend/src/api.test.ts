import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import {
  ApiError,
  createSavedMarketArtifact,
  deleteSavedMarketArtifact,
  getCurrentUser,
  getRegions,
  listSavedMarketArtifacts,
} from "./api";

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
    vi.unstubAllGlobals();
  });

  test("public market requests do not attach bearer tokens", async () => {
    const fetchMock = mockFetch({ regions: [] });

    await getRegions();

    const [, init] = fetchMock.mock.calls[0];
    expect(fetchMock.mock.calls[0][0]).toBe("/regions");
    expect((init as RequestInit).headers).toEqual({ "Content-Type": "application/json" });
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

  test("saved artifact calls stay under /me and use the bearer token", async () => {
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

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/me/saved-market-artifacts",
      "/me/saved-market-artifacts?artifact_type=region",
      "/me/saved-market-artifacts/saved_artifact_1",
    ]);
    for (const [, init] of fetchMock.mock.calls) {
      expect((init as RequestInit).headers).toMatchObject({ "Authorization": "Bearer token" });
    }
  });
});
