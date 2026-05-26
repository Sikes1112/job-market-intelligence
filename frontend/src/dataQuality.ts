import type {
  ApiEnvelope,
  CoverageComponents,
  CoverageMetadata,
  CoverageScoreComponent,
  CoverageTier,
  DataBasis,
  FreshnessSourceSummary,
  FreshnessStatus,
  SectorCoverageLevel,
  SourceExplanation,
} from "./types";

export type QualityTone = "fresh" | "demo" | "real" | "warning" | "error" | "unknown";

export type QualityBadge = {
  label: string;
  tone: QualityTone;
};

const FAR_FUTURE_SEED_YEAR = 2090;
const FRESHNESS_STATUSES: FreshnessStatus[] = [
  "fresh",
  "stale",
  "partial",
  "unknown",
  "seeded_demo",
];
const DATA_BASES: DataBasis[] = ["seeded_demo", "real_imported", "mixed", "unknown"];
const COVERAGE_TIERS: CoverageTier[] = ["tier_1", "tier_2", "tier_3", "tier_4"];
const SECTOR_COVERAGE_LEVELS: SectorCoverageLevel[] = ["unknown", "limited", "watchlist", "partial", "strong"];
const COVERAGE_COMPONENT_LABELS: Record<CoverageScoreComponent, string> = {
  company_coverage: "Company coverage",
  hiring_coverage: "Hiring coverage",
  entry_level_coverage: "Entry-level coverage",
  freshness: "Freshness",
  source_diversity: "Source diversity",
  confidence: "Confidence",
};
const COVERAGE_COMPONENT_ORDER = Object.keys(COVERAGE_COMPONENT_LABELS) as CoverageScoreComponent[];

export function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export function isFreshnessStatus(value: unknown): value is FreshnessStatus {
  return typeof value === "string" && FRESHNESS_STATUSES.includes(value as FreshnessStatus);
}

export function isDataBasis(value: unknown): value is DataBasis {
  return typeof value === "string" && DATA_BASES.includes(value as DataBasis);
}

export function isCoverageTier(value: unknown): value is CoverageTier {
  return typeof value === "string" && COVERAGE_TIERS.includes(value as CoverageTier);
}

export function isSectorCoverageLevel(value: unknown): value is SectorCoverageLevel {
  return typeof value === "string" && SECTOR_COVERAGE_LEVELS.includes(value as SectorCoverageLevel);
}

export function isSeedDemoFreshness(value: string | null | undefined): boolean {
  if (!value) return false;
  const date = new Date(value);
  return !Number.isNaN(date.getTime()) && date.getUTCFullYear() >= FAR_FUTURE_SEED_YEAR;
}

export function envelopeFreshnessStatus(envelope?: ApiEnvelope<unknown> | null): FreshnessStatus {
  const freshness = envelope?.metadata?.freshness;
  if (!freshness) return "unknown";
  if (isSeedDemoFreshness(freshness.freshness_expires_at)) return "seeded_demo";
  if (isFreshnessStatus(freshness.freshness_status)) return freshness.freshness_status;
  if (freshness.freshness_expires_at) return freshness.is_stale ? "stale" : "fresh";
  return "unknown";
}

export function freshnessStatusFromSummary(
  summary?: FreshnessSourceSummary | null,
  envelope?: ApiEnvelope<unknown> | null,
): FreshnessStatus {
  if (summary?.freshness_status) return summary.freshness_status;
  return envelopeFreshnessStatus(envelope);
}

export function dataBasisFromSummary(
  summary?: FreshnessSourceSummary | null,
  envelope?: ApiEnvelope<unknown> | null,
): DataBasis {
  if (summary?.data_basis) return summary.data_basis;
  return envelopeFreshnessStatus(envelope) === "seeded_demo" ? "seeded_demo" : "unknown";
}

export function freshnessLabel(status: FreshnessStatus): string {
  if (status === "seeded_demo") return "Seeded demo";
  if (status === "fresh") return "Fresh";
  if (status === "stale") return "Stale";
  if (status === "partial") return "Partial";
  return "Unknown freshness";
}

export function dataBasisLabel(basis: DataBasis): string {
  if (basis === "seeded_demo") return "Seeded demo data";
  if (basis === "real_imported") return "Real imported data";
  if (basis === "mixed") return "Mixed data basis";
  return "Unknown data basis";
}

export function qualityTone(statusOrBasis: FreshnessStatus | DataBasis): QualityTone {
  if (statusOrBasis === "fresh") return "fresh";
  if (statusOrBasis === "real_imported") return "real";
  if (statusOrBasis === "seeded_demo") return "demo";
  if (statusOrBasis === "stale" || statusOrBasis === "partial" || statusOrBasis === "mixed") return "warning";
  return "unknown";
}

export function coverageTierLabel(tier: CoverageTier | string | null | undefined): string {
  if (tier === "tier_1") return "Fully covered";
  if (tier === "tier_2") return "Partial but useful";
  if (tier === "tier_3") return "Watchlist / emerging";
  if (tier === "tier_4") return "Placeholder only";
  return "Coverage unavailable";
}

export function coverageTier(coverage?: CoverageMetadata | null): CoverageTier | null {
  const value = coverage?.coverage_tier ?? coverage?.tier;
  return isCoverageTier(value) ? value : null;
}

function isUsefulCoverageLabel(label: string | null | undefined): label is string {
  if (!label) return false;
  if (isCoverageTier(label)) return false;
  return label.trim().length > 0;
}

export function coverageDisplayLabel(coverage?: CoverageMetadata | null): string {
  const tier = coverageTier(coverage);
  const payloadLabel = coverage?.coverage_label;
  const legacyLabel = coverage?.label;
  const label = isUsefulCoverageLabel(payloadLabel)
    ? payloadLabel
    : isUsefulCoverageLabel(legacyLabel)
      ? legacyLabel
      : coverageTierLabel(tier);
  return tier
    ? `Coverage: ${label}`
    : "Coverage unavailable";
}

export function coverageDescription(coverage?: CoverageMetadata | null): string {
  if (coverage?.coverage_description) return coverage.coverage_description;
  const tier = coverageTier(coverage);
  if (tier === "tier_1") {
    return "This market has enough validated data for confident comparison.";
  }
  if (tier === "tier_2") {
    return "This market is directionally useful, but some signal categories are incomplete.";
  }
  if (tier === "tier_3") {
    return "This market is tracked for future expansion, but current data is not deep enough for confident recommendations.";
  }
  if (tier === "tier_4") {
    return "This market exists as a placeholder and should not be treated as analyzed.";
  }
  return "Coverage metadata is unavailable for this response.";
}

export function coverageLimitations(coverage?: CoverageMetadata | null): string[] {
  const explicit = coverage?.coverage_limitations?.filter((item) => item.trim().length > 0) ?? [];
  if (explicit.length) return explicit;
  const tier = coverageTier(coverage);
  if (tier === "tier_1") return [];
  return [coverageDescription(coverage)];
}

export function coverageTone(coverage?: CoverageMetadata | null): QualityTone {
  const tier = coverageTier(coverage);
  if (tier === "tier_1") return "real";
  if (tier === "tier_2") return "warning";
  if (tier === "tier_3") return "warning";
  if (tier === "tier_4") return "error";
  return "unknown";
}

export function coverageIsWeak(coverage?: CoverageMetadata | null): boolean {
  const tier = coverageTier(coverage);
  return tier === "tier_2" || tier === "tier_3" || tier === "tier_4" || !tier;
}

function normalizeCoverageScore(value: number): number {
  const clamped = Math.max(0, Math.min(1, value > 1 ? value / 100 : value));
  return Math.round(clamped * 100);
}

export function coverageScoreText(coverage?: CoverageMetadata | null): string | null {
  const scoreValue = typeof coverage?.coverage_quality_score?.overall_score === "number"
    ? coverage.coverage_quality_score.overall_score
    : coverage?.quality_score;
  if (typeof scoreValue !== "number" || Number.isNaN(scoreValue)) {
    return null;
  }
  const score = normalizeCoverageScore(scoreValue);
  return coverage?.heuristic
    ? `Heuristic coverage score: ${score}%`
    : `Coverage estimate: ${score}%`;
}

export function coverageComponentEntries(
  coverage?: CoverageMetadata | null,
): Array<{ key: string; label: string; value: number }> {
  const components = coverage?.coverage_quality_score?.components ?? coverage?.components;
  if (!components || !isRecord(components)) return [];
  const entries: Array<{ key: string; label: string; value: number }> = [];
  const seen = new Set<string>();

  function addEntry(key: string, value: unknown, label: string) {
    if (typeof value !== "number" || Number.isNaN(value)) return;
    seen.add(key);
    entries.push({ key, label, value: normalizeCoverageScore(value) });
  }

  for (const key of COVERAGE_COMPONENT_ORDER) {
    addEntry(key, (components as CoverageComponents)[key], COVERAGE_COMPONENT_LABELS[key]);
  }
  for (const [key, value] of Object.entries(components)) {
    if (!seen.has(key)) addEntry(key, value, prettyCoverageComponentKey(key));
  }
  return entries;
}

export function sectorCoverageLevelLabel(level: SectorCoverageLevel | string | null | undefined): string {
  if (level === "strong") return "Strong";
  if (level === "partial") return "Partial";
  if (level === "watchlist") return "Watchlist";
  if (level === "limited") return "Limited";
  return "Unknown";
}

export function sectorCoverageTone(level: SectorCoverageLevel | string | null | undefined): QualityTone {
  if (level === "strong") return "real";
  if (level === "partial") return "warning";
  if (level === "watchlist" || level === "limited") return "warning";
  return "unknown";
}

function prettyCoverageComponentKey(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/^\w/, (letter) => letter.toUpperCase());
}

export function qualityBadges(
  envelope?: ApiEnvelope<unknown> | null,
  source?: SourceExplanation | FreshnessSourceSummary | null,
): QualityBadge[] {
  const summary = "freshness" in (source ?? {}) ? (source as SourceExplanation).freshness : source as FreshnessSourceSummary | null | undefined;
  const basis = dataBasisFromSummary(summary, envelope);
  const freshness = freshnessStatusFromSummary(summary, envelope);
  const badges: QualityBadge[] = [
    { label: dataBasisLabel(basis), tone: qualityTone(basis) },
    { label: freshnessLabel(freshness), tone: qualityTone(freshness) },
  ];

  const state = envelope?.metadata?.state;
  if (state && state !== freshness && state !== "fresh") {
    badges.push({ label: `Output ${state}`, tone: state === "failed" ? "error" : "warning" });
  }

  return badges;
}

export function qualityNotices(
  envelope?: ApiEnvelope<unknown> | null,
  source?: SourceExplanation | FreshnessSourceSummary | null,
): string[] {
  const summary = "freshness" in (source ?? {}) ? (source as SourceExplanation).freshness : source as FreshnessSourceSummary | null | undefined;
  const notices = new Set<string>();
  const state = envelope?.metadata?.state;
  const freshness = freshnessStatusFromSummary(summary, envelope);
  const basis = dataBasisFromSummary(summary, envelope);

  if (!envelope && !summary) {
    notices.add("No response metadata is available yet.");
  } else if (!envelope?.metadata?.freshness) {
    notices.add("Freshness metadata is missing, so recency is unknown.");
  }

  if (state === "partial" || envelope?.status === "partial") {
    notices.add("This output is partial; missing values are not treated as zero.");
  }

  if (freshness === "stale") {
    notices.add("Freshness is stale; verify before treating these values as current.");
  } else if (freshness === "partial") {
    notices.add("Freshness/source evidence is partial.");
  } else if (freshness === "unknown") {
    notices.add("Freshness is unknown from the available metadata.");
  } else if (freshness === "seeded_demo" || basis === "seeded_demo") {
    notices.add("This is deterministic seeded demo data, not live market coverage.");
  }

  if (basis === "mixed") {
    notices.add("The data basis is mixed; review source details before relying on it.");
  } else if (basis === "unknown") {
    notices.add("Source evidence is unknown or incomplete.");
  }

  if (summary?.source_count === 0) {
    notices.add("No source evidence records were returned for this view.");
  }
  if (summary?.low_confidence_warning) {
    notices.add(summary.low_confidence_warning);
  }
  if ("warnings" in (source ?? {})) {
    for (const warning of (source as SourceExplanation).warnings ?? []) {
      notices.add(warning);
    }
  }

  return Array.from(notices);
}
