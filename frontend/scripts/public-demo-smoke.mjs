#!/usr/bin/env node

const DEFAULT_FRONTEND_BASE_URL = "http://127.0.0.1:5173";
const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";
const DEFAULT_TIMEOUT_MS = 5000;

export function buildPublicDemoSmokeChecks({
  frontendBaseUrl = DEFAULT_FRONTEND_BASE_URL,
  apiBaseUrl = DEFAULT_API_BASE_URL,
} = {}) {
  const frontend = trimTrailingSlash(frontendBaseUrl);
  const api = trimTrailingSlash(apiBaseUrl);
  return [
    { name: "frontend landing", method: "GET", url: `${frontend}/` },
    { name: "frontend demo entry", method: "GET", url: `${frontend}/markets` },
    { name: "frontend recommendations", method: "GET", url: `${frontend}/markets/recommendations` },
    { name: "api health", method: "GET", url: `${api}/health` },
    { name: "api readiness", method: "GET", url: `${api}/ready` },
    { name: "api regions list", method: "GET", url: `${api}/regions` },
    { name: "api region search", method: "GET", url: `${api}/regions/search` },
    { name: "api recommendation goal modes", method: "GET", url: `${api}/recommendations/goal-modes` },
  ];
}

export async function runSmokeChecks({
  checks,
  fetchImpl = globalThis.fetch,
  timeoutMs = DEFAULT_TIMEOUT_MS,
} = {}) {
  if (typeof fetchImpl !== "function") {
    throw new Error("fetch is required to run public demo smoke checks");
  }

  const results = [];
  for (const check of checks ?? buildPublicDemoSmokeChecks()) {
    results.push(await runSmokeCheck(check, fetchImpl, timeoutMs));
  }
  return results;
}

export function hasSmokeFailures(results) {
  return results.some((result) => !result.ok);
}

export function formatSmokeResults(results) {
  return results
    .map((result) => {
      const status = result.status === null ? "ERR" : String(result.status);
      const latency = result.latencyMs === null ? "n/a" : `${result.latencyMs.toFixed(1)}ms`;
      const outcome = result.ok ? "ok" : "failed";
      const detail = result.error ? ` ${result.error}` : "";
      return `${outcome.padEnd(7)} ${status.padEnd(3)} ${latency.padStart(9)} ${result.method} ${safeUrlLabel(result.url)}${detail}`;
    })
    .join("\n");
}

async function runSmokeCheck(check, fetchImpl, timeoutMs) {
  const startedAt = performance.now();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetchImpl(check.url, {
      method: check.method,
      signal: controller.signal,
    });
    const latencyMs = performance.now() - startedAt;
    return {
      ...check,
      status: response.status,
      latencyMs,
      ok: response.status >= 200 && response.status < 300,
      error: null,
    };
  } catch (error) {
    const latencyMs = performance.now() - startedAt;
    return {
      ...check,
      status: null,
      latencyMs,
      ok: false,
      error: error instanceof Error ? error.message : "request failed",
    };
  } finally {
    clearTimeout(timeout);
  }
}

function trimTrailingSlash(value) {
  return String(value).replace(/\/$/, "");
}

function safeUrlLabel(value) {
  try {
    const url = new URL(value);
    url.username = url.username ? "<redacted>" : "";
    url.password = url.password ? "<redacted>" : "";
    return url.toString();
  } catch {
    return String(value);
  }
}

async function main() {
  const frontendBaseUrl = process.env.FRONTEND_BASE_URL ?? DEFAULT_FRONTEND_BASE_URL;
  const apiBaseUrl = process.env.API_BASE_URL ?? process.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL;
  const timeoutMs = Number.parseInt(process.env.SMOKE_TIMEOUT_MS ?? `${DEFAULT_TIMEOUT_MS}`, 10);
  const checks = buildPublicDemoSmokeChecks({ frontendBaseUrl, apiBaseUrl });
  const results = await runSmokeChecks({ checks, timeoutMs });
  console.log(formatSmokeResults(results));
  if (hasSmokeFailures(results)) {
    process.exitCode = 1;
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  await main();
}
