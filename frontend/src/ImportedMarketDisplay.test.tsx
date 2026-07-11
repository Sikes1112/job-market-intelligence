// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import {
  CountStatusValue,
  ImportedMarketBadges,
  ImportedMarketCoveragePanel,
} from "./ImportedMarketDisplay";
import { formatCountStatus } from "./importedMarketFormat";
import type { ImportDisplayMetadata, MarketCoverageSummary } from "./types";

const NYC_METADATA: ImportDisplayMetadata = {
  data_basis: "real_imported",
  imported_data: true,
  imported_data_label: "Real imported data",
  source_backed: true,
  source_label: "Source-backed",
  coverage_label: "Partially covered",
  freshness_status: "current",
  freshness_label: "Freshness: current",
  trust_label: "Verified",
  risk_label: "Low risk",
  ranking_influence_allowed: true,
  ranking_label: "Ranking-safe",
};

const MARKET_NAMES = [
  ["nyc", "greater_nyc", "Greater NYC"],
  ["seattle", "greater_seattle", "Greater Seattle"],
  ["san_francisco_bay_area", "sf_bay_area", "San Francisco Bay Area"],
  ["boston", "greater_boston", "Greater Boston"],
  ["washington_dc", "washington_dc", "Washington DC"],
  ["austin", "austin", "Austin"],
  ["atlanta", "atlanta", "Atlanta"],
  ["chicago", "chicago", "Chicago"],
] as const;

const MARKETS: MarketCoverageSummary[] = MARKET_NAMES.map(
  ([marketKey, regionId, displayName], index) => ({
    market_key: marketKey,
    region_id: regionId,
    display_name: displayName,
    coverage_status: index < 2 ? "curated" : "partial_curated",
    import_status: "ready",
    company_count: 3,
    presence_fact_count: 3,
    hiring_fact_count: 3,
    entry_level_fact_count: 3,
    source_count: 5,
    freshness_status: marketKey === "atlanta" ? "stale" : "fresh",
    ranking_eligible_fact_count: 12,
    ranking_excluded_fact_count: marketKey === "atlanta" ? 1 : 0,
    unknown_count_dimensions: 3,
    observed_zero_count_dimensions: 2,
    count_status_breakdown: {
      unknown: 3,
      not_collected: 1,
      not_applicable: 1,
      zero_observed: 2,
      positive_observed: 4,
    },
    last_curated_at: "2026-07-09",
    last_import_status: "imported",
    last_refresh_status: "refreshed",
    imported_data_label: "Real imported data",
    coverage_label: index < 2 ? "Seed coverage" : "Partial coverage",
    freshness_label: marketKey === "atlanta" ? "Needs refresh" : "Current",
    source_label: "Source-backed",
    trust_label: "Source-backed",
    risk_label: marketKey === "atlanta" ? "Use with caution" : "Low risk",
    ranking_label: marketKey === "atlanta"
      ? "Some data ranking-excluded"
      : "Ranking-safe",
    comparison_available: true,
    comparison_label: "Comparison available",
  }),
);

afterEach(() => {
  cleanup();
});

describe("imported market display", () => {
  test("renders NYC imported-data, source, trust, freshness, and ranking labels", () => {
    render(<ImportedMarketBadges metadata={NYC_METADATA} />);

    expect(screen.getByText("Real imported data")).toBeTruthy();
    expect(screen.getByText("Source-backed")).toBeTruthy();
    expect(screen.getByText("Partially covered")).toBeTruthy();
    expect(screen.getByText("Freshness: current")).toBeTruthy();
    expect(screen.getByText("Trust: Verified")).toBeTruthy();
    expect(screen.getByText("Risk: Low risk")).toBeTruthy();
    expect(screen.getByText("Ranking-safe")).toBeTruthy();
  });

  test("formats unknown and non-observed counts without coercing them to zero", () => {
    expect(formatCountStatus(null, "unknown")).toBe("Unknown");
    expect(formatCountStatus(null, "not_collected")).toBe("Not collected");
    expect(formatCountStatus(null, "not_applicable")).toBe("Not applicable");
    expect(formatCountStatus(undefined, null)).toBe("Unknown");

    render(<CountStatusValue value={null} status="unknown" />);
    expect(screen.getByText("Unknown")).toBeTruthy();
    expect(screen.queryByText("0")).toBeNull();
  });

  test("formats observed zero and positive observed counts distinctly", () => {
    expect(formatCountStatus(0, "zero_observed")).toBe("0 observed");
    expect(formatCountStatus(4, "positive_observed")).toBe("4");

    render(<CountStatusValue value={0} status="zero_observed" />);
    expect(screen.getByText("0 observed")).toBeTruthy();
  });

  test("renders a generic multi-market imported coverage panel", () => {
    render(<ImportedMarketCoveragePanel markets={MARKETS} />);

    for (const [, , displayName] of MARKET_NAMES) {
      expect(screen.getByText(displayName)).toBeTruthy();
    }
    expect(screen.getByText("8")).toBeTruthy();
    expect(screen.getAllByText("Real imported data").length).toBeGreaterThan(1);
    expect(screen.getAllByText("Source-backed").length).toBeGreaterThan(1);
    expect(screen.getAllByText("Partial coverage").length).toBeGreaterThan(1);
    expect(screen.getAllByText("Freshness: current").length).toBeGreaterThan(1);
    expect(screen.getByText("Freshness: needs refresh")).toBeTruthy();
    expect(screen.getAllByText("Trust: Source-backed").length).toBeGreaterThan(1);
    expect(screen.getByText("Risk: Use with caution")).toBeTruthy();
    expect(screen.getAllByText("Ranking-safe").length).toBeGreaterThan(1);
    expect(screen.getByText("Some data ranking-excluded")).toBeTruthy();
    expect(screen.getAllByText("Comparison available").length).toBeGreaterThan(1);
  });

  test("renders aggregate unknown and observed-zero dimensions without raw internal fields", () => {
    render(<ImportedMarketCoveragePanel markets={MARKETS.slice(0, 1)} />);

    expect(screen.getAllByText("Unknown: 3").length).toBeGreaterThan(0);
    expect(screen.getByText("Not collected: 1")).toBeTruthy();
    expect(screen.getByText("Not applicable: 1")).toBeTruthy();
    expect(screen.getAllByText("0 observed: 2").length).toBeGreaterThan(0);
    expect(screen.queryByText("trust_assessment_id")).toBeNull();
    expect(screen.queryByText("risk_routing_decision_id")).toBeNull();
    expect(screen.queryByText("report_reason")).toBeNull();
    expect(screen.queryByText("exception_case_id")).toBeNull();
  });
});
