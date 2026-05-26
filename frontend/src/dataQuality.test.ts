import { describe, expect, test } from "vitest";
import {
  coverageComponentEntries,
  coverageDescription,
  coverageDisplayLabel,
  coverageIsWeak,
  coverageLimitations,
  coverageScoreText,
  coverageTone,
  coverageTier,
  isCoverageTier,
  sectorCoverageLevelLabel,
  sectorCoverageTone,
} from "./dataQuality";
import type { CoverageMetadata } from "./types";

function coverage(tier: CoverageMetadata["tier"], qualityScore = 0.5): CoverageMetadata {
  return {
    tier,
    label: String(tier),
    quality_score: qualityScore,
    components: {
      company_coverage: qualityScore,
      hiring_coverage: 0.4,
      entry_level_coverage: 0.3,
      freshness: 0.7,
      source_diversity: 0.2,
      confidence: qualityScore,
    },
    heuristic: true,
  };
}

describe("coverage disclosure helpers", () => {
  test("recognizes canonical coverage tiers and renders stable labels", () => {
    expect(isCoverageTier("tier_1")).toBe(true);
    expect(isCoverageTier("tier_5")).toBe(false);
    expect(coverageDisplayLabel(coverage("tier_1"))).toBe("Coverage: Fully covered");
    expect(coverageDisplayLabel(coverage("tier_2"))).toBe("Coverage: Partial but useful");
    expect(coverageDisplayLabel(coverage("tier_3"))).toBe("Coverage: Watchlist / emerging");
    expect(coverageDisplayLabel(coverage("tier_4"))).toBe("Coverage: Placeholder only");
  });

  test("keeps weak and unavailable coverage distinct", () => {
    expect(coverageIsWeak(coverage("tier_2"))).toBe(true);
    expect(coverageIsWeak(coverage("tier_3"))).toBe(true);
    expect(coverageIsWeak(coverage("tier_4"))).toBe(true);
    expect(coverageIsWeak(coverage("tier_1"))).toBe(false);
    expect(coverageDisplayLabel(undefined)).toBe("Coverage unavailable");
    expect(coverageDescription(undefined)).toMatch(/unavailable/i);
    expect(coverageTone(undefined)).toBe("unknown");
  });

  test("formats heuristic coverage score and components without raw decimal precision", () => {
    const item = coverage("tier_2", 0.625);

    expect(coverageScoreText(item)).toBe("Heuristic coverage score: 63%");
    expect(coverageComponentEntries(item)).toEqual([
      { key: "company_coverage", label: "Company coverage", value: 63 },
      { key: "hiring_coverage", label: "Hiring coverage", value: 40 },
      { key: "entry_level_coverage", label: "Entry-level coverage", value: 30 },
      { key: "freshness", label: "Freshness", value: 70 },
      { key: "source_diversity", label: "Source diversity", value: 20 },
      { key: "confidence", label: "Confidence", value: 63 },
    ]);
  });

  test("prefers additive API coverage fields while preserving legacy aliases", () => {
    const item: CoverageMetadata = {
      ...coverage("tier_4", 0),
      coverage_tier: "tier_4",
      coverage_label: "Tier 4 - placeholder only",
      coverage_description: "API supplied placeholder description.",
      coverage_quality_score: {
        overall_score: 12,
        components: {
          company_coverage: 10,
          hiring_coverage: 20,
          entry_level_coverage: 0,
        },
      },
      coverage_limitations: ["API supplied placeholder limitation."],
    };

    expect(coverageTier(item)).toBe("tier_4");
    expect(coverageDisplayLabel(item)).toBe("Coverage: Tier 4 - placeholder only");
    expect(coverageDescription(item)).toBe("API supplied placeholder description.");
    expect(coverageLimitations(item)).toEqual(["API supplied placeholder limitation."]);
    expect(coverageScoreText(item)).toBe("Heuristic coverage score: 12%");
    expect(coverageComponentEntries(item).slice(0, 3)).toEqual([
      { key: "company_coverage", label: "Company coverage", value: 10 },
      { key: "hiring_coverage", label: "Hiring coverage", value: 20 },
      { key: "entry_level_coverage", label: "Entry-level coverage", value: 0 },
    ]);
  });

  test("labels sector coverage levels conservatively", () => {
    expect(sectorCoverageLevelLabel("strong")).toBe("Strong");
    expect(sectorCoverageLevelLabel("limited")).toBe("Limited");
    expect(sectorCoverageLevelLabel(undefined)).toBe("Unknown");
    expect(sectorCoverageTone("strong")).toBe("real");
    expect(sectorCoverageTone("unknown")).toBe("unknown");
  });
});
