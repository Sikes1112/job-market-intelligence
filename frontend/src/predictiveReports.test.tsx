// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import App from "./App";
import { FrontendAuthProvider } from "./auth";

function envelope(data: unknown) {
  return {
    status: "success",
    data,
    metadata: { state: "test", source_versions: {}, warnings: [] },
    error: null,
  };
}

function forecast(overrides: Record<string, unknown>) {
  return {
    forecast_id: "forecast:high",
    forecast_title: "Rising AI market signal forecast for Greater Boston",
    forecast_label: "Rising AI market signal",
    forecast_type: "ai_role_market_growth_12m",
    affected_entity: {
      entity_type: "region",
      entity_id: "greater_boston",
      region_id: "greater_boston",
      company_id: null,
      sector_id: null,
    },
    time_horizon: "next_12_months",
    confidence: {
      level: "high",
      score: 0.86,
      factors: [],
    },
    source_basis: {
      data_basis: "producer_owned_export",
      source_categories: ["market_snapshot", "historical_export"],
      source_count: 8,
      observed_metrics: ["ai_opportunity"],
      coverage_tiers: ["tier_2"],
      freshness_states: ["fresh"],
      notes: ["Derived from historical observations only."],
    },
    historical_depth: {
      observation_count: 4,
      period_count: 4,
      window_start: "2026-01-01",
      window_end: "2026-04-01",
      window_days: 90,
      latest_observed_at: "2026-04-01",
    },
    uncertainty: {
      level: "low",
      known_uncertainties: ["Forecasts are bounded directional signals, not certain outcomes."],
      limitations: ["Read with the stated evidence window."],
      bounded: true,
    },
    reasoning_trail: [
      { code: "historical_window", summary: "Compared 4 historical observations." },
      { code: "confidence_bounds", summary: "Assigned high confidence after checks." },
    ],
    supporting_signals: [
      {
        signal_key: "emerging:ai",
        signal_kind: "emerging_market",
        signal_type: "rising_ai_market",
        signal_status: "rising",
        summary: "The label is based on observed historical movement and bounded confidence.",
      },
    ],
    safe_display_summary: "Rising AI market signal is supported by observed movement with high confidence.",
    why_this_forecast_exists: "The forecast exists because an emerging-market signal was classified from observable historical movement.",
    ...overrides,
  };
}

function predictiveReportPayload() {
  return {
    report_id: "predictive_report:next_12_months",
    report_type: "labor_market_forecast",
    title: "Predictive labor-market intelligence",
    generated_at: "2026-06-20T12:00:00Z",
    time_horizon: "next_12_months",
    forecast_disclaimer: "Forecasts are bounded directional signals from historical evidence, not certain outcomes.",
    methodology_summary: "This report reuses deterministic trend, warning, confidence, uncertainty, source-basis, historical-depth, and reasoning contracts.",
    sections: [
      {
        section_key: "ai_role_market_growth",
        title: "AI role market growth forecasts",
        summary: "Markets appear here when AI opportunity observations support a classification.",
        why_this_section_exists: "This section exists to show whether historical AI opportunity movement supports a bounded growth forecast.",
        forecasts: [forecast({})],
      },
      {
        section_key: "entry_level_access_weakening",
        title: "Entry-level tech access weakening forecasts",
        summary: "Regions appear here when entry-level access movement weakens.",
        why_this_section_exists: "This section exists to avoid treating sparse evidence as a firm forecast.",
        forecasts: [
          forecast({
            forecast_id: "forecast:thin",
            forecast_title: "Insufficient-data forecast for Thin Region",
            forecast_label: "Insufficient-data forecast",
            forecast_type: "entry_level_access_weakening",
            confidence: {
              level: "low",
              score: 0.32,
              factors: [{
                code: "thin_historical_evidence",
                severity: "medium",
                explanation: "Historical evidence is below the preferred observation count.",
              }],
            },
            historical_depth: {
              observation_count: 2,
              period_count: 2,
              window_start: "2026-01-01",
              window_end: "2026-02-01",
              window_days: 31,
              latest_observed_at: "2026-02-01",
            },
            uncertainty: {
              level: "high",
              known_uncertainties: ["Historical evidence is below the preferred observation count."],
              limitations: ["Read with the stated evidence window."],
              bounded: true,
            },
            safe_display_summary: "Historical observations are too limited for a stronger directional forecast.",
            supporting_signals: [{
              signal_key: "trend:thin",
              signal_kind: "trend",
              signal_type: "regional_score_movement",
              signal_status: "insufficient_data",
              summary: "entry_level_access is insufficient_data across 2 historical observations.",
            }],
          }),
        ],
      },
      {
        section_key: "sector_cooling_overheating",
        title: "Sector cooling and overheated condition forecasts",
        summary: "Signals appear here when movement supports a cooling or overheating warning.",
        why_this_section_exists: "This section separates warning types in non-alarmist language.",
        forecasts: [
          forecast({
            forecast_id: "forecast:warning",
            forecast_title: "Possible weakening forecast for Cybersecurity / Austin",
            forecast_label: "Possible weakening forecast",
            forecast_type: "sector_condition_change",
            confidence: { level: "medium", score: 0.64, factors: [] },
            uncertainty: {
              level: "medium",
              known_uncertainties: ["Some historical intervals move against the net direction."],
              limitations: ["Read with the stated evidence window."],
              bounded: true,
            },
            safe_display_summary: "sector_cooling is classified as possible_weakening with medium confidence.",
            supporting_signals: [{
              signal_key: "warning:sector",
              signal_kind: "early_warning",
              signal_type: "sector_cooling",
              signal_status: "possible_weakening",
              summary: "Historical observations show possible weakening in this signal.",
            }],
          }),
        ],
      },
    ],
    limitations: [
      "Weak or limited evidence is shown as low-confidence or insufficient-data messaging.",
      "No live scraping or nondeterministic model calls are used.",
    ],
  };
}

function renderAt(path: string) {
  window.history.pushState(null, "", path);
  render(
    <FrontendAuthProvider>
      <App />
    </FrontendAuthProvider>,
  );
}

describe("predictive forecast reports UI", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  test("/forecasts renders forecast metadata and bounded warning copy", async () => {
    const fetchMock = vi.fn<(input: RequestInfo | URL) => Promise<Response>>(async (input) => {
      const value = String(input);
      if (value.startsWith("/platform/predictive/reports")) {
        return new Response(JSON.stringify(envelope(predictiveReportPayload())), {
          headers: { "Content-Type": "application/json" },
          status: 200,
        });
      }
      return new Response(JSON.stringify(envelope({})), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/forecasts");

    expect(await screen.findByRole("heading", { name: "Labor-market forecasts" })).toBeTruthy();
    expect(screen.getAllByText("Forecast").length).toBeGreaterThan(0);
    expect(screen.getByText(/Confidence: High \(86%\)/i)).toBeTruthy();
    expect(screen.getByText(/Confidence: Low \(32%\)/i)).toBeTruthy();
    expect(screen.getAllByText(/Time horizon: Next 12 Months/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Historical depth: 4 observation/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Source basis: 8 signal input/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Uncertainty: Low/i).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("heading", { name: "Reasoning trail" }).length).toBeGreaterThan(0);
    expect(screen.getByText(/emerging market/i)).toBeTruthy();
    expect(screen.getByText(/early warning/i)).toBeTruthy();
    expect(screen.getAllByText(/Insufficient-data forecast/i).length).toBeGreaterThan(0);

    const text = document.body.textContent?.toLowerCase() ?? "";
    expect(text).not.toContain("crash");
    expect(text).not.toContain("collapse");
    expect(text).not.toContain("guarantee");
    expect(text).not.toContain("guaranteed");
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
  });
});
