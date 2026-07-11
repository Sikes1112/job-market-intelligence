import type { CountStatus } from "./types";

export function formatCountStatus(
  value: number | null | undefined,
  status?: CountStatus | null,
): string {
  if (
    status === "unknown"
    || status === "not_collected"
    || status === "not_applicable"
    || status === "stale"
    || status === "conflicting"
    || status === "low_confidence"
  ) {
    return formatCountStatusLabel(status);
  }
  if (status === "zero_observed") return "0 observed";
  if (status === "positive_observed") {
    return typeof value === "number" ? value.toLocaleString() : "Observed";
  }
  if (typeof value === "number") return value.toLocaleString();
  return "Unknown";
}

export function formatCountStatusLabel(status?: CountStatus | null): string {
  if (status === "unknown") return "Unknown";
  if (status === "not_collected") return "Not collected";
  if (status === "not_applicable") return "Not applicable";
  if (status === "stale") return "Stale";
  if (status === "conflicting") return "Conflicting";
  if (status === "low_confidence") return "Low confidence";
  if (status === "zero_observed") return "0 observed";
  if (status === "positive_observed") return "Positive observed";
  return "Unknown";
}

export function formatCountStatusDimension(
  status: CountStatus,
  count: number | null | undefined,
): string {
  const value = typeof count === "number" ? count.toLocaleString() : "Unknown";
  return `${formatCountStatusLabel(status)}: ${value}`;
}

export function freshnessDisplayLabel(label: string | null | undefined): string {
  if (!label) return "Freshness unknown";
  return label.toLocaleLowerCase().startsWith("freshness:")
    ? label
    : `Freshness: ${label.toLocaleLowerCase()}`;
}
