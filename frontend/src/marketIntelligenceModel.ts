import type {
  MarketComparisonOutcome,
  MarketEvidenceBasis,
  MarketEvidenceSufficiency,
  MarketIntelligenceConfidence,
  MarketIntelligenceFreshness,
  MarketIntelligenceGoal,
  MarketIntelligenceGoalDefinition,
  MarketRankingStabilityStatus,
} from "./types";

export const DEFAULT_MARKET_INTELLIGENCE_GOAL: MarketIntelligenceGoal = "software_engineering";

export const KNOWN_MARKET_INTELLIGENCE_GOALS: MarketIntelligenceGoal[] = [
  "software_engineering",
  "product_management",
  "ai_ml",
  "cybersecurity",
  "data_science",
];

const FALLBACK_GOAL_LABELS: Record<string, string> = {
  software_engineering: "Software Engineering",
  product_management: "Product Management",
  ai_ml: "AI / Machine Learning",
  cybersecurity: "Cybersecurity",
  data_science: "Data Science",
};

const CONFIDENCE_PRESENTATION: Record<string, { label: string; help: string; className: string }> = {
  high: {
    label: "High confidence",
    help: "The current recommendation is well supported by available curated evidence.",
    className: "badge badge-real",
  },
  moderate: {
    label: "Moderate confidence",
    help: "The result is useful, but some coverage or evidence dimensions remain limited.",
    className: "badge badge-warning",
  },
  low: {
    label: "Low confidence",
    help: "Use this as directional intelligence because important evidence is limited.",
    className: "badge badge-error",
  },
  limited: {
    label: "Limited confidence",
    help: "The backend reports insufficient support for a firm conclusion.",
    className: "badge badge-unknown",
  },
};

const FRESHNESS_PRESENTATION: Record<string, { label: string; help: string; className: string }> = {
  current: {
    label: "Current freshness",
    help: "Based on the latest curated dataset currently available.",
    className: "badge badge-real",
  },
  aging: {
    label: "Aging evidence",
    help: "Some source references are getting old and may limit confidence.",
    className: "badge badge-warning",
  },
  stale: {
    label: "Stale evidence",
    help: "Stale evidence should be treated cautiously and can lower confidence.",
    className: "badge badge-error",
  },
  unknown: {
    label: "Unknown freshness",
    help: "Freshness is not available for part of this intelligence payload.",
    className: "badge badge-unknown",
  },
};

const EVIDENCE_SUFFICIENCY_PRESENTATION: Record<string, { label: string; help: string; className: string }> = {
  comparison_ready: {
    label: "Comparison ready",
    help: "The backend reports enough qualifying evidence for a normal comparison.",
    className: "badge badge-real",
  },
  limited_evidence: {
    label: "Limited evidence",
    help: "The backend allows only a provisional ranking because evidence coverage is limited.",
    className: "badge badge-warning",
  },
  insufficient_evidence: {
    label: "Insufficient evidence",
    help: "The backend is abstaining from a normal recommendation because qualifying evidence is insufficient.",
    className: "badge badge-error",
  },
  not_supported: {
    label: "Not supported",
    help: "The backend reports that the current canonical data model does not support this result.",
    className: "badge badge-error",
  },
};

const EVIDENCE_BASIS_PRESENTATION: Record<string, { label: string; help: string }> = {
  direct: {
    label: "Direct evidence",
    help: "The backend reports direct career-goal evidence as the basis for this result.",
  },
  proxy: {
    label: "Proxy evidence",
    help: "The backend reports proxy evidence as the basis for this result.",
  },
  direct_and_proxy: {
    label: "Direct and proxy evidence",
    help: "The backend reports a mix of direct and proxy evidence.",
  },
  no_qualifying_evidence: {
    label: "No qualifying evidence",
    help: "The backend did not find qualifying direct or proxy evidence for this result.",
  },
};

const STABILITY_PRESENTATION: Record<string, { label: string; help: string; className: string }> = {
  stable: {
    label: "Stable",
    help: "The backend stability analysis reports that small evidence changes did not change the ranking state.",
    className: "badge badge-real",
  },
  sensitive: {
    label: "Sensitive",
    help: "The backend stability analysis reports that small evidence changes can affect the ranking.",
    className: "badge badge-warning",
  },
  unstable: {
    label: "Unstable",
    help: "The backend stability analysis reports that scenario changes can materially alter the ranking.",
    className: "badge badge-error",
  },
  indeterminate: {
    label: "Indeterminate stability",
    help: "The backend has not established a stable ranking outcome for this surface.",
    className: "badge badge-unknown",
  },
};

export type MarketDecisionState =
  | "clear_leader"
  | "narrow_lead"
  | "tie"
  | "provisional_ranking"
  | "insufficient_evidence"
  | "not_supported"
  | "unknown";

export type MarketDecisionPresentation = {
  state: MarketDecisionState;
  label: string;
  help: string;
  className: string;
};

const DECISION_PRESENTATION: Record<MarketDecisionState, Omit<MarketDecisionPresentation, "state">> = {
  clear_leader: {
    label: "Clear leader",
    help: "The backend reports comparison-ready evidence with a non-narrow score margin.",
    className: "badge badge-real",
  },
  narrow_lead: {
    label: "Narrow lead",
    help: "The backend score margin is within the Layer 34C near-tie display threshold.",
    className: "badge badge-warning",
  },
  tie: {
    label: "Tie",
    help: "The backend reports an exact tie or zero score margin.",
    className: "badge badge-unknown",
  },
  provisional_ranking: {
    label: "Provisional ranking",
    help: "The backend reports limited evidence, so the ordering should be treated as provisional.",
    className: "badge badge-warning",
  },
  insufficient_evidence: {
    label: "Insufficient evidence",
    help: "The backend is abstaining from a normal ranking or winner.",
    className: "badge badge-error",
  },
  not_supported: {
    label: "Not supported",
    help: "The backend reports that this goal or comparison is not supported by the current canonical data model.",
    className: "badge badge-error",
  },
  unknown: {
    label: "Decision state unavailable",
    help: "The backend returned a state this frontend does not recognize.",
    className: "badge badge-unknown",
  },
};

export const NARROW_LEAD_SCORE_MARGIN = 0.01;

const COMPARISON_OUTCOME_LABELS: Record<string, string> = {
  market_a: "Market A ranks ahead",
  market_b: "Market B ranks ahead",
  tie: "Currently tied",
  no_winner: "No winner named",
};

const METRIC_LABELS: Record<string, string> = {
  employer_count: "Employers",
  sector_count: "Sectors",
  major_tech_count: "Major-tech employers",
  ai_cloud_employer_count: "AI/cloud employers",
  cybersecurity_employer_count: "Cybersecurity employers",
  active_posting_total: "Observed active postings",
  active_posting_unknown_rows: "Unknown hiring rows",
  active_posting_zero_rows: "Observed-zero hiring rows",
  product_active_postings: "Product postings",
  product_activity_status: "Product posting status",
  product_activity_unknown_rows: "Unknown product rows",
  ai_cloud_active_postings: "AI/cloud postings",
  ai_cloud_activity_status: "AI/cloud posting status",
  ai_cloud_activity_unknown_rows: "Unknown AI/cloud rows",
  cybersecurity_active_postings: "Cybersecurity postings",
  cybersecurity_activity_status: "Cybersecurity posting status",
  cybersecurity_activity_unknown_rows: "Unknown cybersecurity rows",
  internship_total: "Observed internships",
  internship_unknown_rows: "Unknown internship rows",
  coop_total: "Observed co-op count",
  coop_unknown_rows: "Unknown co-op rows",
  formal_program_count: "Formal early-career programs",
  unknown_fact_count: "Unknown facts",
  observed_zero_fact_count: "Observed-zero facts",
  ranking_eligible_fact_count: "Ranking-eligible facts",
  ranking_excluded_fact_count: "Ranking-excluded facts",
  unknown_fact_ratio: "Unknown fact ratio",
  ranking_eligible_ratio: "Ranking-eligible ratio",
  confidence_score: "Confidence score",
  freshness: "Freshness",
};

const FORBIDDEN_PUBLIC_TEXT = [
  "trust_assessment_id",
  "risk_routing_decision_id",
  "internal_policy_id",
  "reviewer_notes",
  "reviewer_id",
  "reporter_id",
  "reporter_user_id",
  "reporter_session_id",
  "freeform_report",
  "report_reason",
  "raw_risk",
  "raw_internal_risk",
  "raw_provenance",
  "provenance_internal",
  "private_provenance",
  "source_ref_id",
  "fact_source_link_id",
  "stack trace",
  "traceback",
  "/users/",
  "\\users\\",
];

export function goalLabel(
  goal: MarketIntelligenceGoal | string,
  definitions: MarketIntelligenceGoalDefinition[] = [],
): string {
  const found = definitions.find((definition) => definition.goal === goal);
  if (found?.label) return safePublicText(found.label);
  return FALLBACK_GOAL_LABELS[goal] ?? "Unsupported goal";
}

export function isKnownMarketIntelligenceGoal(value: string): value is MarketIntelligenceGoal {
  return KNOWN_MARKET_INTELLIGENCE_GOALS.includes(value as MarketIntelligenceGoal);
}

export function confidencePresentation(confidence: MarketIntelligenceConfidence | string) {
  return CONFIDENCE_PRESENTATION[confidence] ?? {
    label: "Unknown confidence",
    help: "The backend returned a confidence value this frontend does not recognize.",
    className: "badge badge-unknown",
  };
}

export function freshnessPresentation(freshness: MarketIntelligenceFreshness | string) {
  return FRESHNESS_PRESENTATION[freshness] ?? {
    label: "Unknown freshness",
    help: "The backend returned a freshness value this frontend does not recognize.",
    className: "badge badge-unknown",
  };
}

export function evidenceSufficiencyPresentation(sufficiency: MarketEvidenceSufficiency | string) {
  return EVIDENCE_SUFFICIENCY_PRESENTATION[sufficiency] ?? {
    label: "Unknown evidence sufficiency",
    help: "The backend returned an evidence-sufficiency value this frontend does not recognize.",
    className: "badge badge-unknown",
  };
}

export function evidenceBasisPresentation(basis: MarketEvidenceBasis | string | null | undefined) {
  if (!basis) {
    return {
      label: "Evidence basis unavailable",
      help: "The backend did not return a direct/proxy evidence basis for this surface.",
    };
  }
  return EVIDENCE_BASIS_PRESENTATION[basis] ?? {
    label: "Unknown evidence basis",
    help: "The backend returned an evidence-basis value this frontend does not recognize.",
  };
}

export function stabilityPresentation(stability: MarketRankingStabilityStatus | string | null | undefined) {
  if (!stability) {
    return STABILITY_PRESENTATION.indeterminate;
  }
  return STABILITY_PRESENTATION[stability] ?? {
    label: "Unknown stability",
    help: "The backend returned a stability value this frontend does not recognize.",
    className: "badge badge-unknown",
  };
}

export function decisionStatePresentation({
  evidenceSufficiency,
  isProvisional,
  scoreMargin,
  comparisonOutcome,
}: {
  evidenceSufficiency: MarketEvidenceSufficiency | string;
  isProvisional: boolean;
  scoreMargin: number | null | undefined;
  comparisonOutcome?: MarketComparisonOutcome | string | null;
}): MarketDecisionPresentation {
  let state: MarketDecisionState = "unknown";
  if (evidenceSufficiency === "not_supported") {
    state = "not_supported";
  } else if (evidenceSufficiency === "insufficient_evidence") {
    state = "insufficient_evidence";
  } else if (comparisonOutcome === "tie" || scoreMargin === 0) {
    state = "tie";
  } else if (isProvisional || evidenceSufficiency === "limited_evidence") {
    state = "provisional_ranking";
  } else if (
    typeof scoreMargin === "number"
    && Number.isFinite(scoreMargin)
    && scoreMargin > 0
    && scoreMargin <= NARROW_LEAD_SCORE_MARGIN
  ) {
    state = "narrow_lead";
  } else if (evidenceSufficiency === "comparison_ready") {
    state = "clear_leader";
  }
  const presentation = DECISION_PRESENTATION[state];
  return { state, ...presentation };
}

export function comparisonOutcomeLabel(outcome: MarketComparisonOutcome | string): string {
  return COMPARISON_OUTCOME_LABELS[outcome] ?? "Comparison outcome unavailable";
}

export function metricLabel(key: string): string {
  return METRIC_LABELS[key] ?? humanizeKey(key);
}

export function formatMetricValue(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "Unavailable";
  if (typeof value === "number") {
    if (value === 0) return "Observed zero";
    if (Math.abs(value) < 1 && value > 0) return `${Math.round(value * 100)}%`;
    if (!Number.isInteger(value)) return value.toFixed(2);
    return value.toLocaleString();
  }
  return safePublicText(value);
}

export function scoreLabel(score: number | null | undefined): string {
  if (typeof score !== "number" || Number.isNaN(score)) return "Score unavailable";
  return `${Math.round(score * 100)} comparative score`;
}

export function contributionLabel(contribution: number | null | undefined): string {
  if (typeof contribution !== "number" || Number.isNaN(contribution)) {
    return "Contribution unavailable";
  }
  return `${Math.round(contribution * 100)} relative contribution`;
}

export function scoreMarginLabel(scoreMargin: number | null | undefined): string {
  if (typeof scoreMargin !== "number" || Number.isNaN(scoreMargin)) {
    return "Backend score margin is unavailable.";
  }
  if (scoreMargin === 0) {
    return "Backend score margin is 0.0000, so this is an exact peer match.";
  }
  return `Backend score margin to nearest peer is ${scoreMargin.toFixed(4)}.`;
}

export function safePublicText(value: unknown, fallback = "Not available"): string {
  if (typeof value !== "string") return fallback;
  const trimmed = value.trim();
  if (!trimmed) return fallback;
  const normalized = trimmed.toLocaleLowerCase();
  if (FORBIDDEN_PUBLIC_TEXT.some((token) => normalized.includes(token))) {
    return fallback;
  }
  return trimmed;
}

export function humanizeKey(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
