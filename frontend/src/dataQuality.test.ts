import { describe, expect, test } from "vitest";
import {
  coverageComponentEntries,
  coverageDescription,
  coverageDisplayLabel,
  coverageIsWeak,
  coverageScoreText,
  coverageTone,
  isCoverageTier,
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
});
