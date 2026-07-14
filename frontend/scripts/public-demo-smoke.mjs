#!/usr/bin/env node

import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const DEFAULT_FRONTEND_BASE_URL = "http://127.0.0.1:5173";
const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";
const DEFAULT_TIMEOUT_MS = 5000;
const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = resolve(SCRIPT_DIR, "..");
const REPO_ROOT = resolve(FRONTEND_ROOT, "..");

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
    { name: "frontend market intelligence", method: "GET", url: `${frontend}/markets/intelligence` },
    { name: "api health", method: "GET", url: `${api}/health` },
    { name: "api readiness", method: "GET", url: `${api}/ready` },
    { name: "api regions list", method: "GET", url: `${api}/regions` },
    { name: "api region search", method: "GET", url: `${api}/regions/search` },
    { name: "api recommendation goal modes", method: "GET", url: `${api}/recommendations/goal-modes` },
    { name: "api market intelligence", method: "GET", url: `${api}/market-intelligence` },
    { name: "api market comparison ranking", method: "GET", url: `${api}/market-comparisons` },
    { name: "api career goal comparisons", method: "GET", url: `${api}/career-goal-comparisons` },
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

export function shouldUseInProcessFallback(results) {
  return (
    results.length > 0 &&
    results.every((result) => {
      const message = String(result.error ?? "").toLowerCase();
      return (
        !result.ok &&
        result.status === null &&
        (message.includes("fetch failed") ||
          message.includes("econnrefused") ||
          message.includes("operation not permitted"))
      );
    })
  );
}

export function runInProcessSmokeFallback({
  checks,
  frontendRoot = FRONTEND_ROOT,
  repoRoot = REPO_ROOT,
  spawnSyncImpl = spawnSync,
} = {}) {
  const selectedChecks = checks ?? buildPublicDemoSmokeChecks();
  const frontendChecks = selectedChecks.filter((check) => isFrontendCheck(check));
  const apiChecks = selectedChecks.filter((check) => !isFrontendCheck(check));
  return [
    ...frontendChecks.map((check) => frontendFallbackResult(check, frontendRoot)),
    ...apiFallbackResults(apiChecks, repoRoot, spawnSyncImpl),
  ];
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

function isFrontendCheck(check) {
  const path = new URL(check.url).pathname;
  return new Set(["/", "/markets", "/markets/recommendations", "/markets/intelligence"]).has(path);
}

function frontendFallbackResult(check, frontendRoot) {
  const builtIndex = resolve(frontendRoot, "dist", "index.html");
  const sourceIndex = resolve(frontendRoot, "index.html");
  const available = existsSync(builtIndex) || existsSync(sourceIndex);
  return {
    ...check,
    status: available ? 200 : null,
    latencyMs: 0,
    ok: available,
    error: available ? null : "frontend index.html is unavailable",
  };
}

function apiFallbackResults(checks, repoRoot, spawnSyncImpl) {
  if (checks.length === 0) {
    return [];
  }

  const byPath = new Map(checks.map((check) => [new URL(check.url).pathname, check]));
  const processResult = spawnSyncImpl(pythonExecutable(repoRoot), ["scripts/public_demo_smoke_backend.py"], {
    cwd: repoRoot,
    env: {
      ...process.env,
      PUBLIC_DEMO_SMOKE_API_PATHS: JSON.stringify([...byPath.keys()]),
    },
    encoding: "utf8",
  });

  if (processResult.status !== 0) {
    return checks.map((check) => ({
      ...check,
      status: null,
      latencyMs: 0,
      ok: false,
      error: processResult.stderr || processResult.stdout || "in-process API smoke failed",
    }));
  }

  const payloadLine = processResult.stdout
    .split(/\r?\n/)
    .map((line) => line.trim())
    .findLast((line) => line.startsWith("["));
  if (!payloadLine) {
    return checks.map((check) => ({
      ...check,
      status: null,
      latencyMs: 0,
      ok: false,
      error: processResult.stdout || "in-process API smoke returned no JSON payload",
    }));
  }

  const statuses = new Map(
    JSON.parse(payloadLine).map((item) => [item.path, item.status]),
  );
  return checks.map((check) => {
    const status = statuses.get(new URL(check.url).pathname) ?? null;
    return {
      ...check,
      status,
      latencyMs: 0,
      ok: status !== null && status >= 200 && status < 300,
      error: null,
    };
  });
}

function pythonExecutable(repoRoot) {
  if (process.env.PYTHON) {
    return process.env.PYTHON;
  }
  const venvPython = resolve(repoRoot, ".venv", "bin", "python3");
  return existsSync(venvPython) ? venvPython : "python3";
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
  if (
    hasSmokeFailures(results) &&
    shouldUseInProcessFallback(results) &&
    process.env.PUBLIC_DEMO_SMOKE_DISABLE_FALLBACK !== "1"
  ) {
    const fallbackResults = runInProcessSmokeFallback({ checks });
    console.log("network smoke unavailable; ran in-process fallback");
    console.log(formatSmokeResults(fallbackResults));
    if (hasSmokeFailures(fallbackResults)) {
      process.exitCode = 1;
    }
    return;
  }
  if (hasSmokeFailures(results)) {
    process.exitCode = 1;
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  await main();
}
