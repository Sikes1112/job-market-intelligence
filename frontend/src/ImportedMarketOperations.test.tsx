// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import { ImportedMarketOperationsPanel } from "./ImportedMarketOperations";
import {
  IMPORTED_DIFF_RISKS,
  IMPORTED_MARKET_HEALTH_STATUSES,
  IMPORTED_REFRESH_READINESS_STATUSES,
  IMPORTED_SOURCE_FRESHNESS_STATUSES,
  operationStatusPresentation,
  publicSafeText,
  sanitizePublicValue,
} from "./ImportedMarketOperationsModel";
import type {
  ImportedCoverageGap,
  ImportedDatasetHealthReport,
  ImportedDiffPreview,
  ImportedMarketOperationDetails,
  ImportedMarketOperationsViewPayload,
  ImportedRefreshReadinessStatus,
  ImportedSourceAgingReport,
} from "./types";

afterEach(() => {
  cleanup();
});

const HEALTH_LABELS = [
  "Healthy",
  "Needs refresh",
  "Limited coverage",
  "Stale sources",
  "Validation failed",
  "Ranking limited",
] as const;

const READINESS_LABELS = [
  "Ready",
  "Source refresh needed",
  "Coverage expansion needed",
  "Validation fix needed",
  "Ranking check needed",
  "Not ready",
] as const;

function health(
  marketKey: string,
  marketName: string,
  healthStatus: ImportedDatasetHealthReport["health_status"],
): ImportedDatasetHealthReport {
  return {
    market_key: marketKey,
    market_name: marketName,
    validation_ok: healthStatus !== "validation_failed",
    missing_required_files: healthStatus === "validation_failed" ? ["companies.csv"] : [],
    counts: {
      company_count: 3,
      source_count: 5,
      presence_fact_count: 3,
      hiring_fact_count: 3,
      entry_level_fact_count: 3,
      total_fact_count: 13,
      unknown_fact_count: 3,
      observed_zero_fact_count: 2,
      ranking_eligible_fact_count: healthStatus === "ranking_limited" ? 8 : 13,
      ranking_excluded_fact_count: healthStatus === "ranking_limited" ? 5 : 0,
      stale_fact_count: 0,
      stale_source_count: healthStatus === "stale_sources" ? 1 : 0,
    },
    oldest_source_age_days: 42,
    newest_source_age_days: 8,
    coverage_summary: "Coverage summary is public safe.",
    freshness_summary: "Freshness summary is current.",
    health_status: healthStatus,
    reasons: [],
    recommended_next_action: "Add missing short-window hiring coverage.",
  };
}

function sourceReport(overrides: Partial<ImportedSourceAgingReport> = {}): ImportedSourceAgingReport {
  return {
    market_key: "atlanta",
    source_count: 4,
    stale_source_count: 1,
    aging_source_count: 1,
    expired_source_count: 1,
    oldest_source_age_days: 250,
    newest_source_age_days: 12,
    oldest_sources: [
      source("src_current", "Current hiring source", "current", 12),
      source("src_aging", "Aging internship source", "aging", 80),
      source("src_stale", "Stale co-op source", "stale", 150),
      source("src_expired", "Expired source", "expired", 250),
    ],
    greatest_fact_impact_sources: [],
    important_stale_sources: [
      source("src_stale", "Stale co-op source", "stale", 150),
      source("src_expired", "Expired source", "expired", 250),
    ],
    sources: [],
    ...overrides,
  };
}

function source(
  sourceId: string,
  sourceLabel: string,
  freshnessStatus: ImportedSourceAgingReport["sources"][number]["freshness_status"],
  ageDays: number,
): ImportedSourceAgingReport["sources"][number] {
  return {
    source_id: sourceId,
    source_label: sourceLabel,
    source_type: "curated_csv",
    observed_date: "2026-06-01",
    collected_date: "2026-06-02",
    age_days: ageDays,
    freshness_status: freshnessStatus,
    is_stale: freshnessStatus === "stale" || freshnessStatus === "expired",
    license_or_terms_category: "public_reference",
    fact_usage_count: freshnessStatus === "stale" ? 4 : 1,
    affected_areas: ["hiring"],
    affects_ranking_eligibility: freshnessStatus !== "current",
    impact: "Public-safe source impact explanation.",
  };
}

function coverageGap(overrides: Partial<ImportedCoverageGap> = {}): ImportedCoverageGap {
  return {
    gap_code: "missing_30_day_hiring_counts",
    severity: "low",
    market_key: "atlanta",
    affected_area: "hiring",
    message: "30-day hiring counts are not collected for this market.",
    supporting_counts: {
      observed_count: 0,
      total: 3,
      unknown_ratio: 0.42,
      trust_assessment_id: "trust_private",
    },
    recommended_action: "Add 30-day hiring count coverage during the next curated refresh.",
    estimated_impact: "hiring_quality",
    ...overrides,
  };
}

function diffPreview(overrides: Partial<ImportedDiffPreview> = {}): ImportedDiffPreview {
  return {
    market_key: "atlanta",
    validation_ok: true,
    overall_diff_risk: "high",
    risk_reasons: ["unknown_to_zero_changes"],
    blocking_issues: [
      {
        code: "region_id_mismatch",
        severity: "blocking",
        area: "region",
        record_id: "atlanta",
        message: "Proposed region IDs do not match the registered market region.",
      },
    ],
    warnings: [
      {
        code: "unknown_becoming_observed_zero",
        severity: "high",
        area: "hiring",
        record_id: "hiring_1",
        message: "A hiring fact would convert from unknown to observed zero.",
      },
      {
        code: "zero_becoming_unknown",
        severity: "high",
        area: "entry_level",
        record_id: "entry_1",
        message: "An entry-level fact would convert from observed zero to unknown.",
      },
      {
        code: "source_removed_still_used",
        severity: "high",
        area: "source",
        record_id: "src_old",
        message: "A source reference would be removed while canonical facts still depend on it.",
      },
      {
        code: "ranking_eligible_becoming_excluded",
        severity: "high",
        area: "presence",
        record_id: "presence_1",
        message: "A fact would become ranking-excluded.",
      },
      {
        code: "company_id_identity_mismatch",
        severity: "high",
        area: "company",
        record_id: "cmp_1",
        message: "Proposed company name matches an existing company with a different ID.",
      },
    ],
    summary_counts: {
      companies_added: 1,
      companies_changed: 1,
      source_references_added: 1,
      source_references_changed: 1,
      source_references_absent_from_files: 1,
      unknown_to_zero_changes: 1,
      zero_to_unknown_changes: 1,
      ranking_eligible_to_excluded: 1,
      ranking_excluded_to_eligible: 1,
      freshness_degradations: 1,
    },
    narrative_summary: "3 facts changed, 1 source reference is absent, and 1 fact would become ranking-excluded. Overall import risk: high.",
    changes: [
      {
        area: "hiring",
        change_type: "changed",
        record_id: "hiring_1",
        field: "posting_count_30d",
        before: "unknown",
        after: 0,
        message: "Hiring count would change from unknown to observed zero.",
      },
    ],
    ...overrides,
  };
}

function details(
  marketKey: string,
  readinessStatus: ImportedRefreshReadinessStatus = "ready",
  overrides: Partial<ImportedMarketOperationDetails> = {},
): ImportedMarketOperationDetails {
  return {
    sources: sourceReport({ market_key: marketKey }),
    facts: {
      market_key: marketKey,
      total_facts: 13,
      ranking_eligible_facts: 13,
      ranking_excluded_facts: 0,
      stale_facts: 0,
      low_confidence_facts: 0,
      unknown_facts: 3,
      observed_zero_facts: 2,
      missing_useful_dimension_facts: 3,
      weak_source_coverage_facts: 0,
      trust_or_risk_limited_facts: 0,
      limiting_categories: [],
      findings: [],
    },
    gaps: {
      market_key: marketKey,
      gap_count: 1,
      highest_severity: "low",
      gaps: [coverageGap({ market_key: marketKey })],
    },
    ranking: {
      market_key: marketKey,
      excluded_fact_count: 0,
      total_fact_count: 13,
      ranking_limited_ratio: 0,
      affected_areas: [],
      reason_counts: {},
      stale_source_exclusion_count: 0,
      low_confidence_exclusion_count: 0,
      insufficient_evidence_exclusion_count: 0,
      unsupported_freshness_exclusion_count: 0,
      trust_or_risk_limitation_count: 0,
      diagnostics: [],
    },
    readiness: {
      market_key: marketKey,
      readiness_status: readinessStatus,
      blocking_conditions: readinessStatus === "ready" ? [] : ["stale_or_expired_sources"],
      warnings: ["missing_30_day_hiring_counts"],
      recommended_next_action: "Add missing short-window hiring coverage.",
      ordered_actions: ["Add 30-day hiring count coverage during the next curated refresh."],
      reasons: ["missing_30_day_hiring_counts"],
      expected_impact: "hiring_quality",
      maintenance_priority: "medium",
      priority_score: marketKey === "atlanta" ? 13 : 2,
    },
    diff: diffPreview({ market_key: marketKey }),
    ...overrides,
  };
}

function payload(
  markets: ImportedDatasetHealthReport[] = [
    health("atlanta", "Atlanta", "limited_coverage"),
    health("boston", "Greater Boston", "healthy"),
  ],
  detailsByMarket: Record<string, ImportedMarketOperationDetails> = {
    atlanta: details("atlanta"),
    boston: details("boston", "ready", {
      sources: sourceReport({
        market_key: "boston",
        source_count: 5,
        stale_source_count: 0,
        aging_source_count: 0,
        expired_source_count: 0,
        oldest_sources: [],
        important_stale_sources: [],
      }),
      gaps: { market_key: "boston", gap_count: 0, highest_severity: null, gaps: [] },
      diff: diffPreview({
        market_key: "boston",
        overall_diff_risk: "none",
        blocking_issues: [],
        warnings: [],
        summary_counts: { companies_added: 0 },
        narrative_summary: "0 facts changed, 0 source references are absent, and 0 facts would become ranking-excluded. Overall import risk: none.",
        changes: [],
      }),
    }),
  },
): ImportedMarketOperationsViewPayload {
  return {
    overview: {
      summary: {
        registered_market_count: markets.length,
        healthy_market_count: markets.filter((market) => market.health_status === "healthy").length,
        markets_needing_refresh: markets.filter((market) => market.health_status === "needs_refresh").length,
        markets_with_limited_coverage: markets.filter((market) => market.health_status === "limited_coverage").length,
        markets_with_stale_sources: markets.filter((market) => market.health_status === "stale_sources").length,
        total_stale_source_count: markets.reduce((sum, market) => sum + market.counts.stale_source_count, 0),
        total_ranking_excluded_fact_count: markets.reduce(
          (sum, market) => sum + market.counts.ranking_excluded_fact_count,
          0,
        ),
        highest_priority_maintenance_market: "atlanta",
        recommended_next_maintenance_action: "Add missing short-window hiring coverage.",
        overall_health_status: markets.some((market) => market.health_status === "limited_coverage")
          ? "limited_coverage"
          : "healthy",
      },
      markets,
    },
    details_by_market: detailsByMarket,
  };
}

describe("imported market operations display", () => {
  test("renders platform overview counts and recommended action", () => {
    render(<ImportedMarketOperationsPanel payload={payload()} />);

    expect(screen.getByText("Operations overview")).toBeTruthy();
    expect(screen.getAllByText("2").length).toBeGreaterThan(0);
    expect(screen.getByText("healthy")).toBeTruthy();
    expect(screen.getByText("limited coverage")).toBeTruthy();
    expect(screen.getByText("stale sources")).toBeTruthy();
    expect(screen.getByText("ranking-excluded facts")).toBeTruthy();
    expect(screen.getAllByText("Atlanta").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Add missing short-window hiring coverage.").length).toBeGreaterThan(0);
  });

  test("handles empty, loading, and error states safely", () => {
    render(<ImportedMarketOperationsPanel loading />);
    expect(screen.getByRole("status")).toBeTruthy();
    cleanup();

    render(<ImportedMarketOperationsPanel error="Traceback /Users/private/app.py" />);
    expect(screen.getByText("Imported data operations are unavailable.")).toBeTruthy();
    expect(screen.queryByText(/Traceback/i)).toBeNull();
    cleanup();

    render(<ImportedMarketOperationsPanel payload={payload([], {})} />);
    expect(screen.getByText("No imported markets registered")).toBeTruthy();
  });

  test("renders every supported status with text and public-safe explanations", () => {
    IMPORTED_MARKET_HEALTH_STATUSES.forEach((status, index) => {
      expect(operationStatusPresentation("health", status).label).toBe(HEALTH_LABELS[index]);
    });
    IMPORTED_REFRESH_READINESS_STATUSES.forEach((status, index) => {
      expect(operationStatusPresentation("readiness", status).label).toBe(READINESS_LABELS[index]);
    });
    IMPORTED_SOURCE_FRESHNESS_STATUSES.forEach((status) => {
      expect(operationStatusPresentation("source", status).label).not.toContain("Unknown");
    });
    IMPORTED_DIFF_RISKS.forEach((risk) => {
      expect(operationStatusPresentation("diff", risk).label).not.toContain("Unknown");
    });

    render(<ImportedMarketOperationsPanel payload={payload()} />);
    expect(screen.getAllByLabelText(/Limited coverage:/).length).toBeGreaterThan(0);
    expect(screen.getAllByLabelText(/Ready:/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/approve|reject|publish|accept changes|override ranking/i)).toBeNull();
  });

  test("distinguishes health from refresh readiness", () => {
    render(<ImportedMarketOperationsPanel payload={payload()} />);

    expect(screen.getByText(/Health describes the current quality and coverage/i)).toBeTruthy();
    expect(screen.getByText(/Refresh readiness describes whether the current curated files/i)).toBeTruthy();
    expect(screen.getAllByText("Limited coverage").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Ready").length).toBeGreaterThan(0);
    expect(screen.getAllByLabelText(/Ready: The current curated files can be safely re-imported; this does not mean coverage is complete/i).length).toBeGreaterThan(0);
  });

  test("renders source aging, no-stale state, and missing optional fields", () => {
    render(<ImportedMarketOperationsPanel payload={payload()} />);

    expect(screen.getAllByText("Source aging").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Current").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Aging").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Stale").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Expired").length).toBeGreaterThan(0);
    expect(screen.getByText("No sources are currently aging, stale, or expired.")).toBeTruthy();
  });

  test("renders coverage gaps and filters unsafe supporting metrics", () => {
    render(<ImportedMarketOperationsPanel payload={payload()} />);

    expect(screen.getByText("30-day hiring counts are not collected for this market.")).toBeTruthy();
    expect(screen.getAllByText("Low").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Hiring quality/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Unknown ratio: 0.42/)).toBeTruthy();
    expect(screen.queryByText(/trust_assessment_id/i)).toBeNull();
    expect(screen.getByText("No coverage gaps were returned for this market.")).toBeTruthy();
  });

  test("renders ranking exclusions and zero-exclusion state without raw trust fields", () => {
    const rankedPayload = payload([health("atlanta", "Atlanta", "ranking_limited")], {
      atlanta: details("atlanta", "needs_ranking_review", {
        ranking: {
          market_key: "atlanta",
          excluded_fact_count: 2,
          total_fact_count: 13,
          ranking_limited_ratio: 0.1538,
          affected_areas: ["hiring"],
          reason_counts: { low_confidence: 1, stale_source: 1 },
          stale_source_exclusion_count: 1,
          low_confidence_exclusion_count: 1,
          insufficient_evidence_exclusion_count: 0,
          unsupported_freshness_exclusion_count: 0,
          trust_or_risk_limitation_count: 0,
          diagnostics: [
            {
              fact_type: "company_region_hiring",
              fact_id: "hiring_1",
              area: "hiring",
              reason_categories: ["low_confidence", "stale_source"],
              explanation: "Fact is excluded because source evidence is stale and confidence is low.",
            },
          ],
        },
      }),
    });

    render(<ImportedMarketOperationsPanel payload={rankedPayload} />);

    expect(screen.getByText("Fact is excluded because source evidence is stale and confidence is low.")).toBeTruthy();
    expect(screen.getByText(/Low confidence: 1/)).toBeTruthy();
    expect(screen.queryByText(/risk_routing_decision_id/i)).toBeNull();
    cleanup();

    render(<ImportedMarketOperationsPanel payload={payload()} />);
    expect(screen.getAllByText("No imported facts are currently excluded from ranking.").length).toBeGreaterThan(0);
  });

  test("renders diff preview warnings, counts, and preview-only no-write language", () => {
    render(<ImportedMarketOperationsPanel payload={payload()} />);

    expect(screen.getAllByText("Preview only. No imported data has been changed.").length).toBeGreaterThan(0);
    expect(screen.getByText(/would convert from unknown to observed zero/i)).toBeTruthy();
    expect(screen.getByText(/would convert from observed zero to unknown/i)).toBeTruthy();
    expect(screen.getByText(/source reference would be removed/i)).toBeTruthy();
    expect(screen.getAllByText(/would become ranking-excluded/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/different ID/i)).toBeTruthy();
    expect(screen.getByText(/region IDs do not match/i)).toBeTruthy();
    expect(screen.getByText(/Unknown to zero changes: 1/)).toBeTruthy();
    expect(screen.getByText("No detailed diff changes were returned.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /approve|apply|publish|accept/i })).toBeNull();
  });

  test("handles unknown enum and partial market details without crashing", () => {
    render(
      <ImportedMarketOperationsPanel
        payload={payload([health("new_market", "New Market", "unexpected_health")], {})}
      />,
    );

    expect(screen.getAllByText("Unknown health status").length).toBeGreaterThan(0);
    expect(screen.getByText("Detailed diagnostics unavailable")).toBeTruthy();
  });

  test("redacts prohibited nested payload text and values", () => {
    const unsafePayload = payload([health("atlanta", "Atlanta", "limited_coverage")], {
      atlanta: details("atlanta", "ready", {
        gaps: {
          market_key: "atlanta",
          gap_count: 1,
          highest_severity: "high",
          gaps: [
            coverageGap({
              severity: "high",
              message: "trust_assessment_id private detail",
              recommended_action: "reporter_user_id should not render",
            }),
          ],
        },
        ranking: {
          ...details("atlanta").ranking,
          excluded_fact_count: 1,
          diagnostics: [
            {
              fact_type: "company_region_hiring",
              fact_id: "hiring_unsafe",
              area: "hiring",
              reason_categories: ["trust_or_risk_limited"],
              explanation: "raw_internal_risk object leaked",
            },
          ],
        },
        diff: diffPreview({
          changes: [
            {
              area: "hiring",
              change_type: "changed",
              record_id: "hiring_unsafe",
              field: "value",
              before: { trust_assessment_id: "trust_private", safe_value: "unknown" },
              after: "Traceback in /Users/private/app.py",
              message: "private_provenance internals leaked",
            },
          ],
        }),
      }),
    });

    render(<ImportedMarketOperationsPanel payload={unsafePayload} />);

    const rendered = document.body.textContent ?? "";
    expect(rendered).not.toContain("trust_assessment_id");
    expect(rendered).not.toContain("reporter_user_id");
    expect(rendered).not.toContain("raw_internal_risk");
    expect(rendered).not.toContain("private_provenance");
    expect(rendered).not.toContain("Traceback");
    expect(rendered).not.toContain("/Users/private");
    expect(publicSafeText("risk_routing_decision_id")).toBe("Public-safe detail unavailable.");
    expect(sanitizePublicValue({ trust_assessment_id: "secret", safe_value: "ok" })).toEqual({
      safe_value: "ok",
    });
  });
});
