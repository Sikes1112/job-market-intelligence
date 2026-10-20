// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import { createElement, StrictMode } from "react";
import { afterEach, describe, expect, test, vi } from "vitest";

function bootstrapResponse(csrfToken: string, created = true, replaced = false): Response {
  return new Response(JSON.stringify({
    data: {
      status: "active",
      csrf_token: csrfToken,
      expires_at: "2026-10-20T20:00:00+00:00",
      created,
      replaced,
    },
  }), { status: created ? 201 : 200, headers: { "Content-Type": "application/json" } });
}

function envelope(data: unknown, status = 200): Response {
  return new Response(JSON.stringify({
    status: status < 400 ? "success" : "error",
    data: status < 400 ? data : null,
    metadata: { state: "current", source_versions: {}, warnings: [] },
    error: status < 400 ? null : data,
  }), { status, headers: { "Content-Type": "application/json" } });
}

describe("public guest frontend session integration", () => {
  afterEach(async () => {
    const guest = await import("./guestSession");
    guest.resetGuestSessionMemoryForTests();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    vi.resetModules();
  });

  test("StrictMode initializes one guest session without exposing a login flow", async () => {
    vi.stubEnv("VITE_DEPLOYMENT_MODE", "public_guest_demo");
    const fetchMock = vi.fn().mockResolvedValue(bootstrapResponse("csrf-initial"));
    vi.stubGlobal("fetch", fetchMock);
    const { FrontendAuthProvider, useFrontendAuth } = await import("./auth");

    function Probe() {
      const auth = useFrontendAuth();
      return createElement("span", null, `${auth.isConfigured}:${auth.isAuthenticated}:${auth.isLoading}:${auth.user?.name ?? "none"}`);
    }

    render(createElement(StrictMode, null,
      createElement(FrontendAuthProvider, null, createElement(Probe)),
    ));

    await waitFor(() => expect(screen.getByText("true:true:false:Guest workspace")).toBeTruthy());
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/guest/session");
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      credentials: "same-origin",
      method: "POST",
    });
  });

  test("unsafe requests use the memory-only CSRF token and same-origin cookie credentials", async () => {
    vi.stubEnv("VITE_DEPLOYMENT_MODE", "public_guest_demo");
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(bootstrapResponse("csrf-memory-only"))
      .mockResolvedValueOnce(envelope({ persisted: true }));
    vi.stubGlobal("fetch", fetchMock);
    const storageSpy = vi.spyOn(Storage.prototype, "setItem");
    const { updatePreferences } = await import("./api");

    await updatePreferences({}, { getAccessToken: async () => null });

    const [url, init] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(url).toBe("/me/preferences");
    expect(init.credentials).toBe("same-origin");
    expect(init.method).toBe("PUT");
    expect((init.headers as Record<string, string>)["X-CSRF-Token"]).toBe("csrf-memory-only");
    expect(storageSpy).not.toHaveBeenCalled();
  });

  test("a stale cookie replacement is announced as a temporary workspace reset", async () => {
    vi.stubEnv("VITE_DEPLOYMENT_MODE", "public_guest_demo");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(bootstrapResponse("csrf-replaced", true, true)));
    const { FrontendAuthProvider, useFrontendAuth } = await import("./auth");

    function Probe() {
      const auth = useFrontendAuth();
      return createElement("span", null, auth.sessionMessage ?? "none");
    }

    render(createElement(FrontendAuthProvider, null, createElement(Probe)));

    await waitFor(() => expect(screen.getByText("Your temporary workspace reset. A new session is ready.")).toBeTruthy());
  });

  test("a typed pre-execution CSRF rejection recovers once and only then replays", async () => {
    vi.stubEnv("VITE_DEPLOYMENT_MODE", "public_guest_demo");
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(bootstrapResponse("csrf-old"))
      .mockResolvedValueOnce(envelope({ type: "guest_csrf_invalid", message: "Forbidden" }, 403))
      .mockResolvedValueOnce(bootstrapResponse("csrf-new", false))
      .mockResolvedValueOnce(envelope({ decision: { decision_id: "decision-1" } }));
    vi.stubGlobal("fetch", fetchMock);
    const { createCareerDecision } = await import("./api");

    await createCareerDecision(
      { title: "Choose a market", decision_type: "location_choice" },
      { getAccessToken: async () => null },
    );

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/guest/session",
      "/me/decisions",
      "/guest/session",
      "/me/decisions",
    ]);
    const retryHeaders = fetchMock.mock.calls[3]?.[1]?.headers as Record<string, string>;
    expect(retryHeaders["X-CSRF-Token"]).toBe("csrf-new");
  });

  test("uncertain server failures are not retried", async () => {
    vi.stubEnv("VITE_DEPLOYMENT_MODE", "public_guest_demo");
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(bootstrapResponse("csrf-stable"))
      .mockResolvedValueOnce(envelope({ type: "internal_error", message: "Internal server error" }, 500));
    vi.stubGlobal("fetch", fetchMock);
    const { createCareerDecision } = await import("./api");

    await expect(createCareerDecision(
      { title: "Do not duplicate", decision_type: "location_choice" },
      { getAccessToken: async () => null },
    )).rejects.toMatchObject({ statusCode: 500 });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
