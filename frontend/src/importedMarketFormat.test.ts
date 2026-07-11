import { describe, expect, test } from "vitest";

import {
  formatCountStatus,
  formatCountStatusDimension,
  formatCountStatusLabel,
  freshnessDisplayLabel,
} from "./importedMarketFormat";

describe("imported market format helpers", () => {
  test("preserves unknown, not-collected, and not-applicable as non-zero labels", () => {
    expect(formatCountStatus(null, "unknown")).toBe("Unknown");
    expect(formatCountStatus(null, "not_collected")).toBe("Not collected");
    expect(formatCountStatus(null, "not_applicable")).toBe("Not applicable");
    expect(formatCountStatus(null, null)).toBe("Unknown");
  });

  test("renders observed zero and positive observed values distinctly", () => {
    expect(formatCountStatus(0, "zero_observed")).toBe("0 observed");
    expect(formatCountStatus(4, "positive_observed")).toBe("4");
    expect(formatCountStatusLabel("zero_observed")).toBe("0 observed");
    expect(formatCountStatusLabel("positive_observed")).toBe("Positive observed");
  });

  test("formats aggregate count-status dimensions without implying zero", () => {
    expect(formatCountStatusDimension("unknown", 3)).toBe("Unknown: 3");
    expect(formatCountStatusDimension("not_collected", 2)).toBe("Not collected: 2");
    expect(formatCountStatusDimension("not_applicable", 1)).toBe("Not applicable: 1");
    expect(formatCountStatusDimension("zero_observed", 5)).toBe("0 observed: 5");
  });

  test("normalizes freshness labels for frontend badges", () => {
    expect(freshnessDisplayLabel("Current")).toBe("Freshness: current");
    expect(freshnessDisplayLabel("Needs refresh")).toBe("Freshness: needs refresh");
    expect(freshnessDisplayLabel("Freshness: stale")).toBe("Freshness: stale");
    expect(freshnessDisplayLabel(null)).toBe("Freshness unknown");
  });
});
