export type StatusKind = "health" | "readiness" | "source" | "diff" | "severity" | "priority";
export type StatusTone = "success" | "warning" | "error" | "muted" | "real" | "unknown";

export type StatusPresentation = {
  label: string;
  explanation: string;
  tone: StatusTone;
};

export const IMPORTED_MARKET_HEALTH_STATUSES = [
  "healthy",
  "needs_refresh",
  "limited_coverage",
  "stale_sources",
  "validation_failed",
  "ranking_limited",
] as const;

export const IMPORTED_REFRESH_READINESS_STATUSES = [
  "ready",
  "needs_source_refresh",
  "needs_coverage_expansion",
  "needs_validation_fix",
  "needs_ranking_review",
  "not_ready",
] as const;

export const IMPORTED_SOURCE_FRESHNESS_STATUSES = [
  "current",
  "aging",
  "stale",
  "expired",
  "needs_review",
] as const;

export const IMPORTED_DIFF_RISKS = ["none", "low", "medium", "high", "blocking"] as const;

const FORBIDDEN_PUBLIC_DISPLAY_FRAGMENTS = [
  "trust_assessment_id",
  "risk_routing_decision_id",
  "related_trust_assessment_id",
  "related_risk_routing_decision_id",
  "internal_policy_id",
  "reviewer_note",
  "reviewer_notes",
  "reporter_id",
  "reporter_user_id",
  "reporter_session_id",
  "report_reason",
  "freeform_report",
  "raw_internal_risk",
  "raw_risk",
  "private_provenance",
  "fact_source_link_id",
  "traceback",
  "stack trace",
  "/users/",
  "/private/",
  "c:\\",
];

export function operationStatusPresentation(
  kind: StatusKind,
  value: string | null | undefined,
): StatusPresentation {
  if (kind === "health") return healthStatusPresentation(value);
  if (kind === "readiness") return readinessStatusPresentation(value);
  if (kind === "source") return sourceStatusPresentation(value);
  if (kind === "diff") return diffRiskPresentation(value);
  if (kind === "severity") return severityPresentation(value);
  return priorityPresentation(value);
}

export function publicSafeText(
  value: unknown,
  fallback = "Public-safe detail unavailable.",
): string {
  if (typeof value !== "string") return fallback;
  const text = value.trim();
  if (!text) return fallback;
  const folded = text.toLocaleLowerCase();
  if (FORBIDDEN_PUBLIC_DISPLAY_FRAGMENTS.some((fragment) => folded.includes(fragment))) {
    return fallback;
  }
  return text;
}

export function sanitizePublicValue(value: unknown): unknown {
  if (typeof value === "string") return publicSafeText(value, "Redacted public-safe value");
  if (typeof value === "number" || typeof value === "boolean" || value === null) return value;
  if (Array.isArray(value)) return value.map((item) => sanitizePublicValue(item));
  if (isRecordValue(value)) {
    return Object.fromEntries(
      Object.entries(value)
        .filter(([key]) => isPublicSafeDisplayToken(key))
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, item]) => [key, sanitizePublicValue(item)]),
    );
  }
  return null;
}

export function isPublicSafeDisplayToken(value: string): boolean {
  const folded = value.toLocaleLowerCase();
  return !FORBIDDEN_PUBLIC_DISPLAY_FRAGMENTS.some((fragment) => folded.includes(fragment));
}

function healthStatusPresentation(value: string | null | undefined): StatusPresentation {
  if (value === "healthy") {
    return {
      label: "Healthy",
      explanation: "The imported dataset has no current operational warnings.",
      tone: "success",
    };
  }
  if (value === "needs_refresh") {
    return {
      label: "Needs refresh",
      explanation: "The imported dataset should be refreshed to keep outputs current.",
      tone: "warning",
    };
  }
  if (value === "limited_coverage") {
    return {
      label: "Limited coverage",
      explanation: "The imported dataset is structurally usable but has weak coverage dimensions.",
      tone: "warning",
    };
  }
  if (value === "stale_sources") {
    return {
      label: "Stale sources",
      explanation: "One or more source references are stale or expired.",
      tone: "error",
    };
  }
  if (value === "validation_failed") {
    return {
      label: "Validation failed",
      explanation: "Curated source files do not pass required import validation.",
      tone: "error",
    };
  }
  if (value === "ranking_limited") {
    return {
      label: "Ranking limited",
      explanation: "Too many facts are excluded from ranking outputs.",
      tone: "warning",
    };
  }
  return unknownStatus(value, "Unknown health status");
}

function readinessStatusPresentation(value: string | null | undefined): StatusPresentation {
  if (value === "ready") {
    return {
      label: "Ready",
      explanation: "The current curated files can be safely re-imported; this does not mean coverage is complete.",
      tone: "success",
    };
  }
  if (value === "needs_source_refresh") {
    return {
      label: "Source refresh needed",
      explanation: "Source freshness must improve before a useful refresh.",
      tone: "warning",
    };
  }
  if (value === "needs_coverage_expansion") {
    return {
      label: "Coverage expansion needed",
      explanation: "High-severity coverage gaps limit refresh usefulness.",
      tone: "warning",
    };
  }
  if (value === "needs_validation_fix") {
    return {
      label: "Validation fix needed",
      explanation: "Curated files need validation fixes before refresh.",
      tone: "error",
    };
  }
  if (value === "needs_ranking_review") {
    return {
      label: "Ranking check needed",
      explanation: "Ranking-limited facts need attention before refresh is useful.",
      tone: "warning",
    };
  }
  if (value === "not_ready") {
    return {
      label: "Not ready",
      explanation: "Multiple blockers prevent a safe or useful refresh.",
      tone: "error",
    };
  }
  return unknownStatus(value, "Unknown readiness status");
}

function sourceStatusPresentation(value: string | null | undefined): StatusPresentation {
  if (value === "current") {
    return {
      label: "Current",
      explanation: "The source is current under backend freshness rules.",
      tone: "success",
    };
  }
  if (value === "aging") {
    return {
      label: "Aging",
      explanation: "The source is approaching stale age.",
      tone: "warning",
    };
  }
  if (value === "stale") {
    return {
      label: "Stale",
      explanation: "The source is stale under backend freshness rules.",
      tone: "error",
    };
  }
  if (value === "expired") {
    return {
      label: "Expired",
      explanation: "The source is expired under backend freshness rules.",
      tone: "error",
    };
  }
  if (value === "needs_review") {
    return {
      label: "Needs attention",
      explanation: "The source freshness state needs operator attention.",
      tone: "warning",
    };
  }
  return unknownStatus(value, "Unknown source status");
}

function diffRiskPresentation(value: string | null | undefined): StatusPresentation {
  if (value === "none") {
    return {
      label: "No diff risk",
      explanation: "No risky import changes were detected.",
      tone: "success",
    };
  }
  if (value === "low") {
    return {
      label: "Low risk",
      explanation: "The preview contains low-risk changes.",
      tone: "real",
    };
  }
  if (value === "medium") {
    return {
      label: "Medium risk",
      explanation: "The preview contains material changes to inspect.",
      tone: "warning",
    };
  }
  if (value === "high") {
    return {
      label: "High risk",
      explanation: "The preview contains dangerous semantic changes.",
      tone: "error",
    };
  }
  if (value === "blocking") {
    return {
      label: "Blocking risk",
      explanation: "The preview has blocking validation or identity issues.",
      tone: "error",
    };
  }
  return unknownStatus(value, "Unknown diff risk");
}

function severityPresentation(value: string | null | undefined): StatusPresentation {
  if (value === "critical") return { label: "Critical", explanation: "Critical operational gap.", tone: "error" };
  if (value === "high") return { label: "High", explanation: "High-severity operational gap.", tone: "error" };
  if (value === "medium") return { label: "Medium", explanation: "Medium-severity operational gap.", tone: "warning" };
  if (value === "low") return { label: "Low", explanation: "Low-severity operational gap.", tone: "muted" };
  return unknownStatus(value, "Unknown severity");
}

function priorityPresentation(value: string | null | undefined): StatusPresentation {
  if (value === "critical") {
    return { label: "Critical priority", explanation: "Highest maintenance priority.", tone: "error" };
  }
  if (value === "high") {
    return { label: "High priority", explanation: "High maintenance priority.", tone: "error" };
  }
  if (value === "medium") {
    return { label: "Medium priority", explanation: "Medium maintenance priority.", tone: "warning" };
  }
  if (value === "low") {
    return { label: "Low priority", explanation: "Low maintenance priority.", tone: "muted" };
  }
  return unknownStatus(value, "Unknown priority");
}

function unknownStatus(value: string | null | undefined, label: string): StatusPresentation {
  const safeValue = publicSafeText(value, "unrecognized");
  return {
    label,
    explanation: `Backend returned ${safeValue}; this UI is using a neutral fallback.`,
    tone: "unknown",
  };
}

function isRecordValue(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
