import { describe, expect, test } from "vitest";
import {
  PUBLIC_SEO_PAGES,
  REQUIRED_PUBLIC_SEO_SLUGS,
  getPublicSeoPageBySlug,
} from "./publicSeoContent";

const KNOWN_REPORT_SLUGS = new Set([
  "best-cities-early-career-ai-careers",
  "top-product-management-markets",
  "hidden-tech-hubs-new-graduates",
]);

const KNOWN_BENCHMARK_SLUGS = new Set([
  "early-career-tech-access-index",
  "ai-career-geography-index",
  "product-career-market-index",
]);

describe("public SEO content registry", () => {
  test("includes all required Layer 19D pages", () => {
    const slugs = new Set(PUBLIC_SEO_PAGES.map((page) => page.slug));

    for (const slug of REQUIRED_PUBLIC_SEO_SLUGS) {
      expect(slugs.has(slug)).toBe(true);
      expect(getPublicSeoPageBySlug(slug)?.id).toBe(`public_seo:${slug}`);
    }
  });

  test("every page carries public methodology, limitations, freshness, confidence, warnings, and SEO metadata", () => {
    for (const page of PUBLIC_SEO_PAGES) {
      expect(page.title.length).toBeGreaterThan(0);
      expect(page.summary.length).toBeGreaterThan(0);
      expect(page.intendedSearchIntent.length).toBeGreaterThan(0);
      expect(page.contentPeriod.length).toBeGreaterThan(0);
      expect(page.freshnessDate).toBe("2026-06-18");
      expect(page.confidence).toBe("low");
      expect(page.methodologySummary.length).toBeGreaterThan(0);
      expect(page.methodologyLink.href).toBe("/methodology");
      expect(page.limitations.length).toBeGreaterThan(0);
      expect(page.warnings.length).toBeGreaterThan(0);
      expect(page.warnings.join(" ")).toMatch(/demo-safe/i);
      expect(page.warnings.join(" ")).toMatch(/not a production ranking/i);
      expect(page.primarySections.length).toBeGreaterThan(0);
      expect(page.relatedReports.length).toBeGreaterThan(0);
      expect(page.relatedBenchmarks.length).toBeGreaterThan(0);
      expect(page.suggestedCitation.sourceName).toBe("Job Market Intelligence");
      expect(page.suggestedCitation.publicPath).toBe(page.routePath);
      expect(page.suggestedCitation.accessedOrFreshnessDate).toBe("2026-06-18");
      expect(page.shareSummary.publicPath).toBe(page.routePath);
      expect(page.shareSummary.confidenceLabel).toBe("Low confidence");
      expect(page.shareSummary.warning).toMatch(/demo-safe/i);
      expect(page.sourceAuthority.labels).toContain("demo-safe");
      expect(page.sourceAuthority.labels).toContain("low-confidence");
      expect(page.sourceAuthority.labels).toContain("methodology-backed");
      expect(page.institutionalCta.href).toBe("/career-market-guides");
      expect(page.seo.title.length).toBeGreaterThan(0);
      expect(page.seo.description.length).toBeGreaterThan(0);
      expect(page.seo.canonicalPath).toBe(page.routePath);
      expect(page.seo.topicTags.length).toBeGreaterThan(0);
      expect(page.canonicalCategoryLanguage).toContain("opportunity geography");
      expect(page.canonicalCategoryLanguage).toContain("career market intelligence");
      expect(page.canonicalCategoryLanguage).toContain("early-career access");
    }
  });

  test("related reports and benchmarks target known Layer 19 routes", () => {
    for (const page of PUBLIC_SEO_PAGES) {
      for (const report of page.relatedReports) {
        expect(report.linkType).toBe("report");
        expect(KNOWN_REPORT_SLUGS.has(report.slug ?? "")).toBe(true);
        expect(report.href).toBe(`/reports/${report.slug}`);
      }
      for (const benchmark of page.relatedBenchmarks) {
        expect(benchmark.linkType).toBe("benchmark");
        expect(KNOWN_BENCHMARK_SLUGS.has(benchmark.slug ?? "")).toBe(true);
        expect(benchmark.href).toBe(`/benchmarks/${benchmark.slug}`);
      }
    }
  });
});
