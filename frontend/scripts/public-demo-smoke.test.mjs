import { describe, expect, test } from "vitest";
import {
  buildPublicDemoSmokeChecks,
  formatSmokeResults,
  hasSmokeFailures,
  runSmokeChecks,
} from "./public-demo-smoke.mjs";

describe("public demo smoke checks", () => {
  test("builds non-mutating frontend and API monitoring checks", () => {
    const checks = buildPublicDemoSmokeChecks({
      frontendBaseUrl: "https://demo.example/",
      apiBaseUrl: "https://api.example/",
    });

    expect(checks.map((check) => check.method)).toEqual(["GET", "GET", "GET", "GET", "GET", "GET", "GET", "GET"]);
    expect(checks.map((check) => check.url)).toEqual([
      "https://demo.example/",
      "https://demo.example/markets",
      "https://demo.example/markets/recommendations",
      "https://api.example/health",
      "https://api.example/ready",
      "https://api.example/regions",
      "https://api.example/regions/search",
      "https://api.example/recommendations/goal-modes",
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

    expect(results).toHaveLength(8);
    expect(results.every((result) => result.method === "GET")).toBe(true);
    expect(results.every((result) => typeof result.latencyMs === "number")).toBe(true);
    expect(hasSmokeFailures(results)).toBe(true);
    expect(formatSmokeResults(results)).toContain("api.example/ready");
  });
});
