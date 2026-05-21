import type {
  ApiEnvelope,
  DataBasis,
  FreshnessSourceSummary,
  FreshnessStatus,
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

export function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export function isFreshnessStatus(value: unknown): value is FreshnessStatus {
  return typeof value === "string" && FRESHNESS_STATUSES.includes(value as FreshnessStatus);
}

export function isDataBasis(value: unknown): value is DataBasis {
  return typeof value === "string" && DATA_BASES.includes(value as DataBasis);
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
