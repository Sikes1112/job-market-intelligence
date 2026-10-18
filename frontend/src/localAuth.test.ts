// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, describe, expect, test, vi } from "vitest";

describe("local portfolio authentication", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  test("protected frontend requests use the existing local-only claims bridge", async () => {
    vi.stubEnv("VITE_LOCAL_AUTH", "true");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          data: { opportunities: [] },
          error: null,
          meta: { request_id: "req-local-auth", generated_at: "2026-10-16T00:00:00Z" },
        }),
        { headers: { "Content-Type": "application/json" }, status: 200 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const { getCurrentOpportunities } = await import("./api");

    await getCurrentOpportunities(
      { market: "greater_boston" },
      { getAccessToken: async () => null },
    );

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
    expect(JSON.parse(headers["X-Verified-OIDC-Claims"])).toMatchObject({
      iss: "https://local.job-market-intelligence.test/",
      sub: "local|explorer",
    });
  });

  test("local authentication is treated as configured by protected product surfaces", async () => {
    vi.stubEnv("VITE_LOCAL_AUTH", "true");
    const { FrontendAuthProvider, useFrontendAuth } = await import("./auth");
    function Probe() {
      const auth = useFrontendAuth();
      return createElement("span", null, `${auth.isConfigured}:${auth.isAuthenticated}`);
    }

    render(createElement(FrontendAuthProvider, null, createElement(Probe)));

    expect(screen.getByText("true:true")).toBeTruthy();
  });

  test("unconfigured sign-in controls route to the account explanation", async () => {
    vi.stubEnv("VITE_LOCAL_AUTH", "false");
    window.history.replaceState({}, "", "/markets/current-opportunities");
    const { FrontendAuthProvider, useFrontendAuth } = await import("./auth");
    function Probe() {
      const auth = useFrontendAuth();
      return createElement("button", { onClick: () => void auth.login() }, "Sign in");
    }

    render(createElement(FrontendAuthProvider, null, createElement(Probe)));
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(window.location.pathname).toBe("/markets/account");
  });
});
