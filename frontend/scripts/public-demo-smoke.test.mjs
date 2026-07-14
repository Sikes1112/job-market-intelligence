import { describe, expect, test } from "vitest";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  buildPublicDemoSmokeChecks,
  formatSmokeResults,
  hasSmokeFailures,
  runInProcessSmokeFallback,
  runSmokeChecks,
  shouldUseInProcessFallback,
} from "./public-demo-smoke.mjs";

describe("public demo smoke checks", () => {
  test("builds non-mutating frontend and API monitoring checks", () => {
    const checks = buildPublicDemoSmokeChecks({
      frontendBaseUrl: "https://demo.example/",
      apiBaseUrl: "https://api.example/",
    });

    expect(checks.map((check) => check.method)).toEqual([
      "GET",
      "GET",
      "GET",
      "GET",
      "GET",
      "GET",
      "GET",
      "GET",
      "GET",
      "GET",
      "GET",
      "GET",
    ]);
    expect(checks.map((check) => check.url)).toEqual([
      "https://demo.example/",
      "https://demo.example/markets",
      "https://demo.example/markets/recommendations",
      "https://demo.example/markets/intelligence",
      "https://api.example/health",
      "https://api.example/ready",
      "https://api.example/regions",
      "https://api.example/regions/search",
      "https://api.example/recommendations/goal-modes",
      "https://api.example/market-intelligence",
      "https://api.example/market-comparisons",
      "https://api.example/career-goal-comparisons",
    ]);
  });

  test("reports status and latency failures without mutating state", async () => {
    const checks = buildPublicDemoSmokeChecks({
      frontendBaseUrl: "https://demo.example",
      apiBaseUrl: "https://api.example",
    });
    const fetchImpl = async (url) =>
      new Response("{}", {
        status: String(url).endsWith("/ready") ? 503 : 200,
      });

    const results = await runSmokeChecks({ checks, fetchImpl, timeoutMs: 100 });

    expect(results).toHaveLength(12);
    expect(results.every((result) => result.method === "GET")).toBe(true);
    expect(results.every((result) => typeof result.latencyMs === "number")).toBe(true);
    expect(hasSmokeFailures(results)).toBe(true);
    expect(formatSmokeResults(results)).toContain("api.example/ready");
  });

  test("falls back only when every network smoke check cannot reach a server", () => {
    expect(shouldUseInProcessFallback([
      {
        ok: false,
        status: null,
        error: "fetch failed",
      },
      {
        ok: false,
        status: null,
        error: "ECONNREFUSED",
      },
    ])).toBe(true);

    expect(shouldUseInProcessFallback([
      {
        ok: false,
        status: 503,
        error: null,
      },
    ])).toBe(false);
  });

  test("runs deterministic in-process fallback checks without network writes", () => {
    const tempRoot = mkdtempSync(join(tmpdir(), "public-demo-smoke-"));
    const frontendRoot = join(tempRoot, "frontend");
    mkdirSync(join(frontendRoot, "dist"), { recursive: true });
    writeFileSync(join(frontendRoot, "dist", "index.html"), "<!doctype html>");
    const checks = buildPublicDemoSmokeChecks({
      frontendBaseUrl: "http://127.0.0.1:5173",
      apiBaseUrl: "http://127.0.0.1:8000",
    });

    try {
      const results = runInProcessSmokeFallback({
        checks,
        frontendRoot,
        repoRoot: tempRoot,
        spawnSyncImpl: (_command, _args, options) => ({
          status: 0,
          stderr: "",
          stdout: [
            "{\"level\":\"INFO\",\"message\":\"request_completed\"}",
            JSON.stringify(
              JSON.parse(options.env.PUBLIC_DEMO_SMOKE_API_PATHS).map((path) => ({
                path,
                status: 200,
              })),
            ),
          ].join("\n"),
        }),
      });

      expect(results).toHaveLength(12);
      expect(results.every((result) => result.method === "GET")).toBe(true);
      expect(hasSmokeFailures(results)).toBe(false);
    } finally {
      rmSync(tempRoot, { recursive: true, force: true });
    }
  });
});
