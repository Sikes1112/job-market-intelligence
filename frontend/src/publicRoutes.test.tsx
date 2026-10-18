// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import App from "./App";
import { FrontendAuthProvider } from "./auth";
import { PUBLIC_SEO_PAGES } from "./publicSeoContent";
import { isProductPage, parseRoute } from "./urlState";

type MockPayload = {
  data: unknown;
  warnings?: unknown[];
  status?: number;
  error?: { code: string; message: string };
};

function envelope(data: unknown, warnings: unknown[] = []) {
  return {
    status: "success",
    data,
    metadata: { state: "test", source_versions: {}, warnings },
    error: null,
  };
}

function errorEnvelope(code: string, message: string) {
  return {
    status: "error",
    data: null,
    metadata: { state: "failed", source_versions: {}, warnings: [] },
    error: { code, message },
  };
}

function platformEmbedAccessPayload(slug: string) {
  const comparison = slug === "region-comparison";
  return {
    allowed: true,
    embed_product_id: comparison ? "region_comparison" : "market_score_card",
    payload: {
      embed_product_id: comparison ? "region_comparison" : "market_score_card",
      title: comparison ? "Regional market comparison" : "Market score card",
      attribution: "Powered by Job Market Intelligence. Verify important decisions independently.",
      freshness: {
        status: "partial",
        freshness_expires_at: null,
        last_updated_at: null,
      },
      confidence: {
        level: "medium",
        label: comparison ? "Directional public-safe comparison" : "Directional public-safe score",
      },
      source_summary: {
        data_basis: "public_safe_summary",
        source_count: comparison ? 2 : 1,
        source_categories: comparison
          ? ["region score summary", "company-region summaries"]
          : ["region score summary"],
        notes: ["No raw records or source ids are exposed."],
      },
      warnings: comparison
        ? [
            "Embed output is a summary view, not a raw export.",
            "Coverage and freshness vary by market.",
          ]
        : ["Score card is derived market intelligence, not comprehensive truth."],
      metrics: comparison
        ? [
            { label: "Greater Boston", opportunity: 0.81, early_career_access: 0.86 },
            { label: "Greater Atlanta", opportunity: 0.67, early_career_access: 0.58 },
          ]
        : [
            { label: "Opportunity", value: 0.81 },
            { label: "Early-career access", value: 0.86 },
            { label: "Live market", value: 0.68 },
          ],
    },
  };
}

const coverageLabels: Record<string, string> = {
  tier_1: "Tier 1 - fully covered market",
  tier_2: "Tier 2 - partial but useful market",
  tier_3: "Tier 3 - watchlist / emerging market",
  tier_4: "Tier 4 - placeholder only",
};

const coverageScores: Record<string, number> = {
  tier_1: 0.86,
  tier_2: 0.62,
  tier_3: 0.24,
  tier_4: 0,
};

const coverageDescriptions: Record<string, string> = {
  tier_1: "API fixture says this market is ready for confident comparison.",
  tier_2: "API fixture says this market is directionally useful but incomplete.",
  tier_3: "API fixture says this market is tracked but not ready for confident recommendations.",
  tier_4: "API fixture says this market is placeholder-only and not analyzed.",
};

const coverageLimitations: Record<string, string> = {
  tier_1: "",
  tier_2: "Coverage is partial; compare this market with caution.",
  tier_3: "Coverage is watchlist-level; do not treat it as a confident recommendation market.",
  tier_4: "Coverage is placeholder-only; do not treat it as analyzed market intelligence.",
};

function coverage(tier: "tier_1" | "tier_2" | "tier_3" | "tier_4") {
  const score = coverageScores[tier];
  return {
    tier,
    label: coverageLabels[tier],
    quality_score: score,
    components: {
      company_coverage: score,
      hiring_coverage: tier === "tier_4" ? 0 : Math.max(0.12, score - 0.08),
      entry_level_coverage: tier === "tier_1" ? 0.82 : tier === "tier_2" ? 0.52 : 0,
      freshness: tier === "tier_4" ? 0 : 0.72,
      source_diversity: tier === "tier_1" ? 0.78 : tier === "tier_2" ? 0.42 : 0.12,
      confidence: score,
    },
    coverage_tier: tier,
    coverage_label: coverageLabels[tier],
    coverage_description: coverageDescriptions[tier],
    coverage_quality_score: {
      overall_score: score * 100,
      components: {
        company_coverage: score * 100,
        hiring_coverage: tier === "tier_4" ? 0 : Math.max(12, (score - 0.08) * 100),
        entry_level_coverage: tier === "tier_1" ? 82 : tier === "tier_2" ? 52 : 0,
        freshness: tier === "tier_4" ? 0 : 72,
        source_diversity: tier === "tier_1" ? 78 : tier === "tier_2" ? 42 : 12,
        confidence: score * 100,
      },
    },
    coverage_limitations: coverageLimitations[tier] ? [coverageLimitations[tier]] : [],
    notes: [`Fixture ${coverageLabels[tier].toLowerCase()} coverage note.`],
    heuristic: true,
    safe_for_confident_market_comparison: tier === "tier_1",
    should_rank_as_confident_recommendation: tier === "tier_1",
  };
}

function priorityMarket() {
  return {
    rank: 10,
    market_id: "boston",
    display_name: "Boston",
  };
}

function sectorCoverage(tier: "tier_1" | "tier_2" | "tier_3" | "tier_4", coverage_level = "watchlist") {
  return {
    sector: "ai",
    label: "AI",
    coverage_level,
    coverage: coverage(tier),
  };
}

function freshnessSummary() {
  return {
    freshness_status: "fresh",
    data_basis: "real_imported",
    last_collected_at: null,
    source_count: 1,
    low_confidence_warning: null,
  };
}

function regionScores(score = 0.74) {
  return {
    structural_ecosystem_score: 0.7,
    live_market_score: 0.6,
    objective_opportunity_score: score,
    raw_total_score: 0.68,
    general_density_score: 0.5,
    tech_market_density_score: 0.55,
    early_career_accessibility_score: 0.66,
    score_ruleset_version: "marketscore_v1",
  };
}

function regionDetail(
  regionId: string,
  displayName: string,
  tier?: "tier_1" | "tier_2" | "tier_3" | "tier_4",
  sectorCoverage: Record<string, unknown> = {},
) {
  return {
    region_id: regionId,
    display_name: displayName,
    region_type: "greater_region",
    parent_region_id: null,
    labor_market_group: regionId.replace("greater_", ""),
    ...(tier ? { coverage: coverage(tier), sector_coverage: sectorCoverage } : {}),
    ...(regionId === "greater_boston" ? { priority_market: priorityMarket() } : {}),
    summary: { eligible_company_count: 1 },
    scores: regionScores(tier === "tier_4" ? 0.28 : 0.74),
    top_companies_present: [
      {
        company_id: "comp_a",
        company_name: "Acme AI",
        sector_primary: "ai",
        eligibility_status: "eligible",
        is_major_tech: false,
        is_mag7: false,
        prestige_score: 0.45,
      },
    ],
    top_companies_hiring: [],
    entry_level_summary: {},
    major_tech_summary: { count: 0, company_ids: [] },
    mag7_summary: { count: 0, company_ids: [] },
  };
}

function sourceExplanation(subjectId: string, subjectType: "company" | "region" = "region") {
  return {
    subject_type: subjectType,
    subject_id: subjectId,
    freshness: freshnessSummary(),
    sources: [],
  };
}

function coverageWarning(scopeRef: string) {
  return {
    warning_code: "region_coverage_not_confident",
    severity: "medium",
    message: `Region ${scopeRef} is not covered enough for confident recommendations.`,
    scope_type: "region",
    scope_ref: scopeRef,
  };
}

function evidenceRef(basis = "structured_score") {
  return {
    basis,
    strength: basis === "heuristic_inference" ? "inferred" : "moderate",
    label: `${basis} fixture evidence`,
    reference_type: "fixture",
    reference_id: `${basis}:fixture`,
  };
}

function recommendationGoalModes() {
  return {
    goal_modes: [
      {
        goal_mode: "maximize_entry_level_access",
        label: "Maximize entry-level access",
        description: "Favor markets and employers with stronger early-career access signals.",
        prioritization_summary: "Prioritizes entry-level and internship signals.",
        weighted_components: [
          {
            component: "entry_level_access",
            weight: 0.42,
            evidence_basis: ["structured_score"],
            is_proxy: false,
            requires_heuristic_inference: false,
            unavailable_behavior: "Show missing data.",
          },
        ],
        penalty_components: [],
        missing_data_behavior: "Do not impute missing entry-level inputs.",
        warnings: [],
      },
      {
        goal_mode: "maximize_ai_cloud_concentration",
        label: "Maximize AI/cloud concentration",
        description: "Favor targets with stronger AI and cloud concentration signals.",
        prioritization_summary: "Current AI/cloud concentration is a proxy component.",
        weighted_components: [
          {
            component: "ai_cloud_concentration",
            weight: 0.46,
            evidence_basis: ["company_metadata", "market_coverage"],
            is_proxy: true,
            requires_heuristic_inference: false,
            unavailable_behavior: "Show weak AI/cloud evidence.",
            warning: "Current AI/cloud concentration is derived from sector metadata proxies.",
          },
        ],
        penalty_components: [
          {
            component: "company_density",
            weight: 0.06,
            evidence_basis: ["region_metadata"],
            is_proxy: true,
            requires_heuristic_inference: false,
            unavailable_behavior: "Do not apply when missing.",
            penalty_explanation: "Narrow company universes can make concentration less actionable.",
          },
        ],
        missing_data_behavior: "Missing sector inputs must become weak evidence.",
        warnings: ["AI/cloud concentration is currently a proxy component."],
      },
    ],
  };
}

function recommendationTarget(targetId = "greater_boston", label = "Greater Boston", targetType = "region") {
  return {
    target_type: targetType,
    target_id: targetId,
    display_label: label,
    parent_target_id: null,
    related_target_ids: [],
  };
}

function recommendationExplanation(target = recommendationTarget()) {
  const refs = [evidenceRef("structured_score"), evidenceRef("market_coverage")];
  return {
    target,
    goal_mode: "maximize_entry_level_access",
    headline: `${target.display_label} recommendation evidence`,
    fit_reasons: [
      {
        reason_category: "goal_alignment",
        label: "Ranked by Maximize entry-level access",
        detail: "Used weighted components: entry_level_access, market_coverage.",
        evidence_strength: "moderate",
        evidence_basis: ["structured_score", "market_coverage"],
        support: "direct",
        evidence_refs: refs,
      },
    ],
    data_strengths: [
      {
        reason_category: "data_strength",
        label: "Coverage supports comparison",
        detail: "Coverage metadata was attached.",
        evidence_strength: "moderate",
        evidence_basis: ["market_coverage"],
        support: "direct",
        evidence_refs: [refs[1]],
      },
    ],
    tradeoffs: [
      {
        tradeoff_category: "prestige_vs_entry_level_access",
        label: "High prestige but weaker entry-level accessibility",
        positive_side: "Prestige density is represented in structured metadata.",
        negative_side: "Entry-level access must be verified before acting.",
        importance: "high",
        evidence_strength: "moderate",
        evidence_basis: ["structured_score"],
        support: "direct",
        evidence_refs: [refs[0]],
      },
    ],
    weaknesses: [
      {
        weakness_category: "heuristic_limitation",
        label: "Ranking uses proxy components",
        detail: "Proxy components used: lower_competition_proxy.",
        evidence_strength: "inferred",
        evidence_basis: ["heuristic_inference"],
        support: "inferred",
        evidence_refs: [],
      },
    ],
    manual_verification: [
      {
        verification_category: "current_job_postings",
        label: "Verify current job postings",
        question: "Are current postings available before acting?",
        rationale: "Recommendation output is not a live jobs feed.",
        importance: "high",
        evidence_strength: "missing",
        evidence_basis: ["missing_data"],
        support: "direct",
        evidence_refs: [],
      },
    ],
    evidence_refs: refs,
    confidence_summary: {
      confidence_status: "moderate",
      confidence_score: 0.66,
      confidence_ref: "coverage:greater_boston:confidence",
      warnings: [],
    },
    freshness_summary: {
      freshness_status: "fresh",
      data_basis: "real_imported",
      source_count: 2,
      freshness_ref: "freshness:greater_boston",
      warnings: [],
    },
    provenance_refs: [],
    coverage_warnings: ["region_coverage_not_confident"],
    data_quality_warnings: [],
  };
}

function rankedRecommendation(target = recommendationTarget(), rank = 1) {
  return {
    rank,
    target,
    goal_mode: "maximize_entry_level_access",
    final_score: 0.74,
    normalized_score: 0.74,
    score_components_used: [
      {
        component: "entry_level_access",
        value: 0.8,
        weight: 0.42,
        weighted_value: 0.336,
        evidence_basis: ["structured_score"],
        evidence_refs: [evidenceRef("structured_score")],
        source_fields: ["region.scores.early_career_accessibility_score"],
        is_proxy: false,
        inferred: false,
        warning: null,
      },
      {
        component: "lower_competition_proxy",
        value: 0.58,
        weight: 0.22,
        weighted_value: 0.128,
        evidence_basis: ["heuristic_inference"],
        evidence_refs: [],
        source_fields: ["proxy"],
        is_proxy: true,
        inferred: true,
        warning: "Competition is not directly measured; this component is heuristic.",
      },
    ],
    score_components_missing: [
      {
        component: "geographic_flexibility",
        weight: 0.34,
        unavailable_behavior: "Location-flexibility policy data is unavailable.",
        evidence_basis: ["missing_data"],
        warning: "Verify location requirements manually.",
      },
    ],
    score_components_proxy: [
      {
        component: "lower_competition_proxy",
        value: 0.58,
        weight: 0.22,
        weighted_value: 0.128,
        evidence_basis: ["heuristic_inference"],
        evidence_refs: [],
        source_fields: ["proxy"],
        is_proxy: true,
        inferred: true,
        warning: "Competition is not directly measured; this component is heuristic.",
      },
    ],
    penalties_applied: [
      {
        component: "prestige_density",
        value: 0.7,
        weight: 0.08,
        penalty_value: 0.056,
        application_mode: "high_value",
        explanation: "High prestige can indicate harder entry-level access.",
        evidence_basis: ["company_metadata", "heuristic_inference"],
        evidence_refs: [],
        is_proxy: true,
        inferred: true,
      },
    ],
    confidence_contribution: 0.04,
    freshness_contribution: 0.05,
    coverage_contribution: 0.08,
    explanation: recommendationExplanation(target),
    warnings: ["Proxy-heavy recommendation: verify inferred components."],
  };
}

function recommendationStrategyPayload(goalMode = "maximize_entry_level_access") {
  const regionTarget = recommendationTarget();
  const roleTarget = recommendationTarget("ai_product_operations", "AI product operations", "role_family");
  return {
    available_goal_modes: recommendationGoalModes().goal_modes,
    selected_goal_mode: recommendationGoalModes().goal_modes.find((goal) => goal.goal_mode === goalMode)
      ?? recommendationGoalModes().goal_modes[0],
    ranking_profile_version: "layer14c_deterministic_ranking_v1",
    ranking_tie_breaker: "Sort by final_score descending, then display label, then stable target id.",
    ranked_region_recommendations: [rankedRecommendation(regionTarget)],
    ranked_company_recommendations: [],
    market_strategy_plan: {
      goal_mode: goalMode,
      strategy_version: "layer14d_market_strategy_v1",
      source_recommendations: [
        {
          source_id: "region:greater_boston:rank:1",
          rank: 1,
          target: regionTarget,
          final_score: 0.74,
          warnings: [],
        },
      ],
      primary_region_targets: [
        {
          target: regionTarget,
          target_role: "primary",
          source_rank: 1,
          final_score: 0.74,
          rationale: "Top ranked actionable target",
          tradeoff_categories: ["prestige_vs_entry_level_access"],
          source_recommendation_ids: ["region:greater_boston:rank:1"],
          evidence_strength: "moderate",
          evidence_basis: ["structured_score"],
          support: "direct",
          evidence_refs: [evidenceRef("structured_score")],
        },
      ],
      secondary_region_targets: [],
      fallback_region_targets: [
        {
          target: recommendationTarget("raleigh_durham", "Raleigh-Durham"),
          target_role: "fallback",
          source_rank: 2,
          final_score: 0.51,
          rationale: "Fallback market from ranked outputs",
          tradeoff_categories: ["lower_competition_vs_role_volume"],
          source_recommendation_ids: ["region:greater_boston:rank:1"],
          evidence_strength: "inferred",
          evidence_basis: ["heuristic_inference"],
          support: "inferred",
          evidence_refs: [],
        },
      ],
      company_targets: [],
      company_category_targets: [],
      role_family_targets: [
        {
          target: roleTarget,
          rationale: "Heuristic role-family suggestion tied to the selected goal mode; it does not claim current openings.",
          source_recommendation_ids: ["region:greater_boston:rank:1"],
          evidence_strength: "inferred",
          evidence_basis: ["heuristic_inference"],
          support: "inferred",
          evidence_refs: [],
        },
      ],
      timing_guidance: [
        {
          timing_category: "verify_current_postings",
          label: "Verify current postings before acting",
          guidance: "Check current company/career pages before treating ranked targets as actionable.",
          importance: "high",
          source_recommendation_ids: ["region:greater_boston:rank:1"],
          evidence_strength: "missing",
          evidence_basis: ["missing_data"],
          support: "direct",
          evidence_refs: [],
        },
      ],
      watchlist_items: [
        {
          watchlist_category: "proxy_heavy",
          target: regionTarget,
          reason: "Ranked target uses proxy-heavy evidence.",
          upside: "Useful ranked upside remains visible.",
          what_to_verify: "Verify proxy and missing inputs before acting.",
          revisit_after_refresh: true,
          source_recommendation_ids: ["region:greater_boston:rank:1"],
          evidence_strength: "inferred",
          evidence_basis: ["heuristic_inference"],
          support: "inferred",
          evidence_refs: [],
        },
      ],
      manual_verification_checklist: {
        items: [
          {
            item: recommendationExplanation(regionTarget).manual_verification[0],
            source_recommendation_ids: ["region:greater_boston:rank:1"],
          },
        ],
      },
      evidence_warnings: [
        {
          warning_category: "proxy",
          label: "Proxy-heavy recommendation",
          detail: "Lower competition is not directly measured.",
          source_recommendation_ids: ["region:greater_boston:rank:1"],
          evidence_strength: "inferred",
          evidence_basis: ["heuristic_inference"],
          support: "inferred",
          evidence_refs: [],
        },
      ],
    },
    warnings: ["Company rankings unavailable: no company outputs were available."],
  };
}

function monetizationFeatures() {
  const freeRationale = "Free users receive useful basic guidance and a visible basic recommendation result.";
  const paidRationale = "Paid plans add durable workflow value, maintained coverage depth, reports, and exports.";
  return {
    features: [
      {
        feature_key: "basic_region_exploration",
        boundary: "free",
        display_name: "Basic region exploration",
        description: "Browse core region context.",
        boundary_rationale: freeRationale,
        trust_constraint: "Free exploration must remain useful.",
        exposes_core_recommendation_conclusion: false,
        recommendation_influence: "none",
      },
      {
        feature_key: "limited_comparisons",
        boundary: "free",
        display_name: "Limited comparisons",
        description: "Compare a small number of regions.",
        boundary_rationale: freeRationale,
        trust_constraint: "Comparison limits must not hide the basic recommendation conclusion.",
        exposes_core_recommendation_conclusion: false,
        recommendation_influence: "none",
      },
      {
        feature_key: "basic_recommendation_preview",
        boundary: "free",
        display_name: "Basic recommendation preview",
        description: "Show the basic recommendation result.",
        boundary_rationale: "The core recommendation conclusion is free and visible.",
        trust_constraint: "The core recommendation conclusion must not become paid-only.",
        exposes_core_recommendation_conclusion: true,
        recommendation_influence: "none",
      },
      {
        feature_key: "saved_watchlists",
        boundary: "paid",
        display_name: "Saved watchlists",
        description: "Persist markets and targets.",
        boundary_rationale: paidRationale,
        trust_constraint: "Saving a watchlist must not feed back into ranking.",
        exposes_core_recommendation_conclusion: false,
        recommendation_influence: "none",
      },
      {
        feature_key: "alerts",
        boundary: "paid",
        display_name: "Alerts",
        description: "Monitor saved targets.",
        boundary_rationale: paidRationale,
        trust_constraint: "Alerts must report data changes without changing ranking.",
        exposes_core_recommendation_conclusion: false,
        recommendation_influence: "none",
      },
      {
        feature_key: "full_market_coverage",
        boundary: "paid",
        display_name: "Full market coverage",
        description: "Access the full maintained market catalog.",
        boundary_rationale: paidRationale,
        trust_constraint: "Coverage access must not change rankings.",
        exposes_core_recommendation_conclusion: false,
        recommendation_influence: "none",
      },
      {
        feature_key: "deeper_company_geography",
        boundary: "paid",
        display_name: "Deeper company geography",
        description: "Explore deeper company-region context.",
        boundary_rationale: paidRationale,
        trust_constraint: "Company geography access must not bias recommendations.",
        exposes_core_recommendation_conclusion: false,
        recommendation_influence: "none",
      },
      {
        feature_key: "saved_comparison_history",
        boundary: "paid",
        display_name: "Saved comparison history",
        description: "Persist comparison runs.",
        boundary_rationale: paidRationale,
        trust_constraint: "Saved history must not become a ranking input.",
        exposes_core_recommendation_conclusion: false,
        recommendation_influence: "none",
      },
      {
        feature_key: "full_report_generation",
        boundary: "paid",
        display_name: "Full report generation",
        description: "Generate complete report products.",
        boundary_rationale: paidRationale,
        trust_constraint: "Reports must preserve free previews.",
        exposes_core_recommendation_conclusion: false,
        recommendation_influence: "none",
      },
      {
        feature_key: "exportable_strategy_plans",
        boundary: "paid",
        display_name: "Exportable strategy plans",
        description: "Export structured market strategy plans.",
        boundary_rationale: paidRationale,
        trust_constraint: "Exports must preserve evidence and caveats.",
        exposes_core_recommendation_conclusion: false,
        recommendation_influence: "none",
      },
      {
        feature_key: "advanced_recommendation_reports",
        boundary: "paid",
        display_name: "Advanced recommendation reports",
        description: "Package deeper explanations and action planning.",
        boundary_rationale: paidRationale,
        trust_constraint: "Reports explain recommendations but do not own ranking.",
        exposes_core_recommendation_conclusion: false,
        recommendation_influence: "none",
      },
      {
        feature_key: "institutional_license_management",
        boundary: "paid",
        display_name: "Institutional license management",
        description: "Manage seats and organization access.",
        boundary_rationale: paidRationale,
        trust_constraint: "License metadata must not access private recommendation internals.",
        exposes_core_recommendation_conclusion: false,
        recommendation_influence: "none",
      },
      {
        feature_key: "cohort_guidance_templates",
        boundary: "paid",
        display_name: "Cohort guidance templates",
        description: "Reusable advisor templates.",
        boundary_rationale: paidRationale,
        trust_constraint: "Templates must remain guidance surfaces.",
        exposes_core_recommendation_conclusion: false,
        recommendation_influence: "none",
      },
      {
        feature_key: "privacy_preserving_program_insights",
        boundary: "paid",
        display_name: "Privacy-preserving program insights",
        description: "Aggregate licensed-program views.",
        boundary_rationale: paidRationale,
        trust_constraint: "Program insights must be aggregate.",
        exposes_core_recommendation_conclusion: false,
        recommendation_influence: "none",
      },
    ],
  };
}

function monetizationPlans() {
  const baseFeatures = [
    "basic_region_exploration",
    "limited_comparisons",
    "basic_recommendation_preview",
  ];
  const paidFeatures = [
    "saved_watchlists",
    "alerts",
    "advanced_recommendation_reports",
    "full_market_coverage",
    "exportable_strategy_plans",
    "deeper_company_geography",
    "saved_comparison_history",
    "full_report_generation",
  ];
  const institutionalFeatures = [
    "institutional_license_management",
    "cohort_guidance_templates",
    "privacy_preserving_program_insights",
  ];
  const plan = (
    plan_key: string,
    display_name: string,
    buyer_kind: string,
    billing_interval: string,
    intended_audience: string[],
    included_feature_keys: string[],
    buyer_segment: string | null = null,
    placeholder_amount_cents: number | null = null,
  ) => ({
    plan_key,
    display_name,
    buyer_kind,
    buyer_segment,
    billing_interval,
    intended_audience,
    included_feature_keys,
    usage_limits: plan_key === "free"
      ? [{
          feature_key: "limited_comparisons",
          limit: 3,
          unit: "per_month",
          description: "Free users can run a small number of comparisons each month.",
        }]
      : [{
          feature_key: "full_report_generation",
          limit: buyer_kind === "institutional" ? 100 : 3,
          unit: "per_month",
          description: "Report generation placeholder limit.",
        }],
    upgrade_plan_keys: plan_key === "free" ? ["individual_monthly", "individual_annual", "student_annual"] : [],
    price: {
      price_config_key: placeholder_amount_cents === null ? null : `TEST_${plan_key.toUpperCase()}`,
      placeholder_amount_cents,
      currency: "USD",
      final_price: false,
      note: placeholder_amount_cents === null ? "Configurable quote metadata." : "Placeholder test value.",
    },
  });
  return {
    plans: [
      plan("free", "Free", "individual", "free", ["students", "early_career_job_seekers"], baseFeatures, null, 0),
      plan("individual_monthly", "Individual Monthly", "individual", "monthly", ["early_career_job_seekers"], [...baseFeatures, ...paidFeatures], null, 1900),
      plan("individual_annual", "Individual Annual", "individual", "annual", ["early_career_job_seekers"], [...baseFeatures, ...paidFeatures], null, 14900),
      plan("student_annual", "Student Annual", "individual", "annual", ["students"], [...baseFeatures, ...paidFeatures], null, 7900),
      plan("career_center_license", "Career Center License", "institutional", "license_term", ["students"], [...baseFeatures, ...paidFeatures, ...institutionalFeatures], "career_centers"),
      plan("bootcamp_license", "Bootcamp License", "institutional", "license_term", ["students", "early_career_job_seekers"], [...baseFeatures, ...paidFeatures, ...institutionalFeatures], "bootcamps"),
      plan("university_license", "University License", "institutional", "license_term", ["students"], [...baseFeatures, ...paidFeatures, ...institutionalFeatures], "universities"),
      plan("workforce_board_license", "Workforce Board License", "institutional", "license_term", ["early_career_job_seekers"], [...baseFeatures, ...paidFeatures, ...institutionalFeatures], "workforce_boards"),
    ],
  };
}

function monetizationReports() {
  return {
    reports: [
      {
        report_key: "personalized_market_strategy_report",
        display_name: "Personalized Market Strategy Report",
        intended_segments: ["students", "early_career_job_seekers"],
        free_preview_available: true,
        preview_feature_key: "basic_recommendation_preview",
        paid_full_report_required: true,
        paid_full_report_feature_keys: ["advanced_recommendation_reports", "full_report_generation"],
        included_sections: ["recommendation conclusion", "primary market targets"],
        exportable: true,
        export_feature_key: "exportable_strategy_plans",
      },
      {
        report_key: "region_comparison_report",
        display_name: "Region Comparison Report",
        intended_segments: ["relocation_candidates"],
        free_preview_available: true,
        preview_feature_key: "limited_comparisons",
        paid_full_report_required: true,
        paid_full_report_feature_keys: ["saved_comparison_history", "full_report_generation"],
        included_sections: ["comparison summary", "decision checklist"],
        exportable: true,
        export_feature_key: "exportable_strategy_plans",
      },
      {
        report_key: "company_geography_report",
        display_name: "Company Geography Report",
        intended_segments: ["early_career_job_seekers"],
        free_preview_available: true,
        preview_feature_key: "basic_region_exploration",
        paid_full_report_required: true,
        paid_full_report_feature_keys: ["deeper_company_geography", "full_report_generation"],
        included_sections: ["company-region footprint", "presence evidence summary"],
        exportable: true,
        export_feature_key: "exportable_strategy_plans",
      },
      {
        report_key: "early_career_opportunity_report",
        display_name: "Early-Career Opportunity Report",
        intended_segments: ["students", "parents_advisors"],
        free_preview_available: true,
        preview_feature_key: "basic_recommendation_preview",
        paid_full_report_required: true,
        paid_full_report_feature_keys: ["advanced_recommendation_reports", "full_report_generation"],
        included_sections: ["early-career fit summary", "next-step plan"],
        exportable: true,
        export_feature_key: "exportable_strategy_plans",
      },
    ],
  };
}

function monetizationAccessPreview(value: string) {
  const [, query = ""] = value.split("?");
  const params = new URLSearchParams(query);
  const featureKey = params.get("feature_key") ?? "basic_recommendation_preview";
  const used = params.has("used") ? Number(params.get("used")) : null;
  const allowed = featureKey === "basic_recommendation_preview"
    || featureKey === "limited_comparisons" && (used ?? 0) < 3;
  return {
    decision: {
      allowed,
      plan_key: "free",
      feature_key: featureKey,
      reason: allowed
        ? `${featureKey} is included in free.`
        : `${featureKey} is not included in free.`,
      upgrade_plan_keys: allowed ? [] : ["individual_monthly", "individual_annual"],
      usage_limit: featureKey === "limited_comparisons"
        ? {
            feature_key: "limited_comparisons",
            limit: 3,
            unit: "per_month",
            description: "Free users can run a small number of comparisons each month.",
          }
        : null,
      remaining_usage: featureKey === "limited_comparisons" ? Math.max(3 - (used ?? 0), 0) : null,
    },
  };
}

const PUBLIC_REPORT_SLUGS = [
  "best-cities-early-career-ai-careers",
  "top-product-management-markets",
  "hidden-tech-hubs-new-graduates",
];

const PUBLIC_BENCHMARK_SLUGS = [
  "early-career-tech-access-index",
  "ai-career-geography-index",
  "product-career-market-index",
];

function publicReport(slug: string) {
  const titles: Record<string, string> = {
    "best-cities-early-career-ai-careers": "Best Cities for Early-Career AI Careers",
    "top-product-management-markets": "Top Product Management Markets",
    "hidden-tech-hubs-new-graduates": "Hidden Tech Hubs for New Graduates",
  };
  const markets = slug === "top-product-management-markets"
    ? [["nyc", "NYC"], ["austin", "Austin"]]
    : slug === "hidden-tech-hubs-new-graduates"
      ? [["raleigh_durham", "Raleigh-Durham"], ["pittsburgh", "Pittsburgh"]]
      : [["boston", "Boston"], ["sf_bay_area", "SF Bay Area"]];
  return {
    report_id: `public_report:${slug}`,
    slug,
    title: titles[slug] ?? "Unknown Report",
    category: slug.replaceAll("-", "_"),
    report_period: "2026 methodology preview",
    summary: "Fixture public career market intelligence report summary.",
    markets_covered: markets.map(([market_id, market_label]) => ({
      market_id,
      market_label,
      coverage_note: "Coverage must be checked before use.",
    })),
    market_results: markets.map(([market_id, market_label]) => ({
      result_type: "featured",
      rank: null,
      market_id,
      market_label,
      headline: `${market_label} fixture headline`,
      rationale: `${market_label} fixture rationale with current coverage caveat.`,
      evidence_signals: ["company-region presence", "early-career access"],
      freshness_date: "2026-06-18",
      confidence: "low",
      warnings: [
        "Featured-market example only; not a computed ranking.",
        "Current coverage, freshness, and source evidence must be checked before use.",
      ],
      source_provenance_summary: publicReportProvenance(),
    })),
    methodology_summary:
      "This fixture methodology explains public report evidence without benchmark scoring or recommendation ranking.",
    limitations: [
      "No benchmark/index scoring is performed in Layer 19B.",
      "Featured order is editorial/template order, not a computed ranking.",
    ],
    freshness_date: "2026-06-18",
    freshness_status: "unknown",
    confidence: "low",
    warnings: [
      "Layer 19B public reports are demo-safe templates.",
    ],
    source_provenance_summary: publicReportProvenance(),
    related_links: [
      { label: "Methodology", href: "/methodology", link_type: "public_page" },
      { label: "Category glossary", href: "/glossary", link_type: "public_page" },
    ],
    suggested_citation: {
      source_name: "Job Market Intelligence",
      title: titles[slug] ?? "Unknown Report",
      period: "2026 methodology preview",
      product_attribution: "Opportunity Geography Intelligence / Career Market Intelligence",
      public_path: `/reports/${slug}`,
      accessed_or_freshness_date: "2026-06-18",
    },
    share_summary: {
      title: titles[slug] ?? "Unknown Report",
      category_claim: "Public career market intelligence report",
      confidence_label: "Low confidence",
      freshness_label: "Freshness unknown - 2026-06-18",
      takeaway: "Fixture public career market intelligence report summary.",
      public_path: `/reports/${slug}`,
      warning: "Demo-safe public report; not production ranking truth.",
    },
    source_authority: {
      labels: [
        "demo-safe",
        "low-confidence",
        "methodology-backed",
        "not production ranking truth",
      ],
      summary:
        "This report is a public Layer 19 display artifact without production rankings or hidden scoring.",
    },
    institutional_cta: {
      label: "Use this report for career-center planning",
      body: "Apply the report as directional career-market intelligence for advising.",
      href: "/career-market-guides",
      link_type: "public_page",
    },
  };
}

function publicReportProvenance() {
  return {
    data_basis: "demo_template",
    source_count: 3,
    source_categories: ["Layer 19 category language", "public priority-market vocabulary"],
    provenance_notes: ["No raw source references are exposed."],
  };
}

function publicReports() {
  return {
    reports: PUBLIC_REPORT_SLUGS.map((slug) => {
      const report = publicReport(slug);
      return {
        report_id: report.report_id,
        slug: report.slug,
        title: report.title,
        category: report.category,
        report_period: report.report_period,
        summary: report.summary,
        freshness_date: report.freshness_date,
        confidence: report.confidence,
        warnings: report.warnings,
      };
    }),
  };
}

function publicBenchmark(slug: string) {
  const names: Record<string, string> = {
    "early-career-tech-access-index": "Early-Career Tech Access Index",
    "ai-career-geography-index": "AI Career Geography Index",
    "product-career-market-index": "Product Career Market Index",
  };
  const markets = slug === "ai-career-geography-index"
    ? [["sf_bay_area", "SF Bay Area", 72], ["seattle", "Seattle", 66]]
    : slug === "product-career-market-index"
      ? [["nyc", "NYC", 69], ["austin", "Austin", 60]]
      : [["boston", "Boston", 68], ["raleigh_durham", "Raleigh-Durham", 61]];
  return {
    benchmark_id: `public_benchmark:${slug}`,
    slug,
    name: names[slug] ?? "Unknown Benchmark",
    category: slug.replaceAll("-", "_"),
    period: "2026 methodology preview",
    summary: "Fixture public benchmark summary with demo-safe display data.",
    methodology_summary:
      "This fixture methodology explains benchmark display without production scoring or recommendation ranking.",
    limitations: [
      "No production benchmark/index scoring is performed in Layer 19C.",
      "Demo display values are static examples, not production-grade truth.",
    ],
    freshness_date: "2026-06-18",
    freshness_status: "unknown",
    confidence: "low",
    warnings: [
      "Layer 19C public benchmarks are demo-safe display templates and not production benchmark scores.",
    ],
    market_results: markets.map(([market_id, market_label, value]) => ({
      result_type: "featured",
      rank: null,
      market_id,
      market_label,
      score_display: {
        label: "Demo display score",
        value,
        display_value: `${value} / 100 demo-safe display`,
        score_basis: "demo_static",
        caveat: "Demo display value only; not production benchmark scoring.",
      },
      subscores: [
        {
          key: "early_career_access",
          label: "Early-career access",
          value: Number(value) - 2,
          display_value: `${Number(value) - 2} / 100 demo-safe display`,
          explanation: "Static fixture subscore for public rendering.",
        },
        {
          key: "coverage_readiness",
          label: "Coverage readiness",
          value: Number(value) - 6,
          display_value: `${Number(value) - 6} / 100 demo-safe display`,
          explanation: "Static fixture subscore for coverage caveats.",
        },
      ],
      explanation: `${market_label} fixture explanation; not production benchmark scoring.`,
      warnings: [
        "Demo-safe benchmark display only; not production-grade truth.",
      ],
      freshness_date: "2026-06-18",
      confidence: "low",
      source_provenance_summary: publicBenchmarkProvenance(),
    })),
    source_provenance_summary: publicBenchmarkProvenance(),
    related_links: [
      { label: "Benchmark methodology", href: "/methodology", link_type: "public_page" },
      { label: "Market intelligence reports", href: "/reports", link_type: "public_page" },
    ],
    suggested_citation: {
      source_name: "Job Market Intelligence",
      title: names[slug] ?? "Unknown Benchmark",
      period: "2026 methodology preview",
      product_attribution: "Opportunity Geography Intelligence / Career Market Intelligence",
      public_path: `/benchmarks/${slug}`,
      accessed_or_freshness_date: "2026-06-18",
    },
    share_summary: {
      title: names[slug] ?? "Unknown Benchmark",
      category_claim: "Public career market intelligence benchmark",
      confidence_label: "Low confidence",
      freshness_label: "Freshness unknown - 2026-06-18",
      takeaway: "Fixture public benchmark summary with demo-safe display data.",
      public_path: `/benchmarks/${slug}`,
      warning: "Demo-safe public benchmark; not production benchmark truth.",
    },
    source_authority: {
      labels: [
        "demo-safe",
        "low-confidence",
        "methodology-backed",
        "not production benchmark truth",
      ],
      summary:
        "This benchmark is a public Layer 19 display artifact without production scoring authority.",
    },
    institutional_cta: {
      label: "Compare markets for student placement strategy",
      body: "Use this index as directional career-market intelligence for planning.",
      href: "/career-market-guides",
      link_type: "public_page",
    },
  };
}

function publicBenchmarkProvenance() {
  return {
    data_basis: "demo_template",
    source_count: 3,
    source_categories: ["Layer 19 benchmark methodology", "public priority-market vocabulary"],
    provenance_notes: ["No raw source references are exposed."],
  };
}

function publicBenchmarks() {
  return {
    benchmarks: PUBLIC_BENCHMARK_SLUGS.map((slug) => {
      const benchmark = publicBenchmark(slug);
      return {
        benchmark_id: benchmark.benchmark_id,
        slug: benchmark.slug,
        name: benchmark.name,
        category: benchmark.category,
        period: benchmark.period,
        summary: benchmark.summary,
        freshness_date: benchmark.freshness_date,
        confidence: benchmark.confidence,
        warnings: benchmark.warnings,
      };
    }),
  };
}

function responsePayloadFor(input: RequestInfo | URL): MockPayload {
  const value = typeof input === "string" ? input : input.toString();

  if (value.startsWith("/api/v1/platform/embeds/")) {
    const url = new URL(value, "https://app.local");
    const slug = url.pathname.split("/").at(-1) ?? "";
    const origin = url.searchParams.get("origin");
    if (!origin || origin.includes("blocked.example") || origin.includes("unknown.example")) {
      return {
        data: null,
        status: 403,
        error: {
          code: "EMBED_DOMAIN_NOT_ALLOWED",
          message: "This embed is not approved for the requesting domain.",
        },
      };
    }
    return { data: platformEmbedAccessPayload(slug) };
  }
  if (value === "/health") return { data: { service: "test" } };
  if (value === "/public/benchmarks") return { data: publicBenchmarks() };
  if (value.startsWith("/public/benchmarks/")) {
    const slug = decodeURIComponent(value.slice("/public/benchmarks/".length));
    return { data: PUBLIC_BENCHMARK_SLUGS.includes(slug) ? publicBenchmark(slug) : null };
  }
  if (value === "/public/reports") return { data: publicReports() };
  if (value.startsWith("/public/reports/")) {
    const slug = decodeURIComponent(value.slice("/public/reports/".length));
    return { data: PUBLIC_REPORT_SLUGS.includes(slug) ? publicReport(slug) : null };
  }
  if (value === "/regions") {
    return {
      data: {
        regions: [
          {
            region_id: "greater_boston",
            public_slug: "boston",
            display_name: "Greater Boston",
            region_type: "greater_region",
            parent_region_id: null,
            labor_market_group: "boston",
            state: "fresh",
            coverage: coverage("tier_2"),
            sector_coverage: {},
            priority_market: priorityMarket(),
          },
          {
            region_id: "sf_bay_area",
            public_slug: "san-francisco-bay-area",
            display_name: "Greater SF",
            region_type: "greater_region",
            parent_region_id: null,
            labor_market_group: "sf",
            state: "fresh",
            coverage: coverage("tier_4"),
            sector_coverage: {},
          },
          {
            region_id: "legacy_market",
            display_name: "Legacy Market",
            region_type: "placeholder",
            parent_region_id: null,
            labor_market_group: null,
            state: "unknown",
          },
        ],
      },
    };
  }
  if (value === "/regions/greater_boston" || value === "/regions/boston") {
    return {
      data: {
        ...regionDetail("greater_boston", "Greater Boston", "tier_2", {
          ai: sectorCoverage("tier_3"),
        }),
        public_slug: "boston",
      },
    };
  }
  if (
    value === "/regions/sf_bay_area"
    || value === "/regions/san-francisco-bay-area"
    || value === "/regions/greater_sf"
  ) {
    return {
      data: {
        ...regionDetail("sf_bay_area", "Greater SF", "tier_4"),
        public_slug: "san-francisco-bay-area",
      },
    };
  }
  if (value === "/regions/not-a-real-market") {
    return {
      data: null,
      status: 404,
      error: { code: "NOT_FOUND", message: "Region not found." },
    };
  }
  if (value === "/regions/ambiguous-market") {
    return {
      data: null,
      status: 409,
      error: { code: "GEOGRAPHIC_INPUT_AMBIGUOUS", message: "Region is ambiguous." },
    };
  }
  if (value === "/regions/legacy_market") {
    return { data: regionDetail("legacy_market", "Legacy Market") };
  }
  if (value.startsWith("/regions/greater_boston/sources")) {
    return { data: sourceExplanation("greater_boston") };
  }
  if (value.startsWith("/regions/sf_bay_area/sources")) {
    return { data: sourceExplanation("sf_bay_area") };
  }
  if (value.startsWith("/regions/legacy_market/sources")) {
    return { data: sourceExplanation("legacy_market") };
  }
  if (value.startsWith("/regions/search")) {
    return {
      data: {
        regions: [
          {
            region_id: "greater_boston",
            name: "Greater Boston",
            region_name: "greater_boston",
            region_type: "greater_region",
            parent_region_id: null,
            labor_market_group: "boston",
            opportunity_score: 0.74,
            coverage: coverage("tier_1"),
            sector_coverage: {},
            priority_market: priorityMarket(),
            freshness: freshnessSummary(),
            has_real_data: true,
          },
          {
            region_id: "sf_bay_area",
            name: "Greater SF",
            region_name: "sf_bay_area",
            region_type: "greater_region",
            parent_region_id: null,
            labor_market_group: "sf",
            opportunity_score: 0.28,
            coverage: coverage("tier_4"),
            sector_coverage: {},
            freshness: freshnessSummary(),
            has_real_data: true,
          },
        ],
      },
    };
  }
  if (value.startsWith("/companies/search")) {
    return {
      data: {
        companies: [
          {
            company_id: "comp_a",
            name: "Acme AI",
            sector: "ai",
            industry: "software",
            role_families: ["product"],
            matched_region_ids: ["greater_boston"],
            matched_region_coverage: { greater_boston: coverage("tier_2") },
            current_hiring: true,
            has_entry_level_access: true,
            presence_status: "present",
            freshness: freshnessSummary(),
            has_real_data: true,
          },
        ],
      },
    };
  }
  if (value === "/companies/comp_a") {
    return {
      data: {
        company_id: "comp_a",
        company_name: "Acme AI",
        normalized_company_name: "acme ai",
        sector_primary: "ai",
        sector_secondary: null,
        eligibility_status: "eligible",
        eligibility_override_flag: false,
        classification_confidence: "high",
        is_major_tech: false,
        is_mag7: false,
        prestige_score: 0.45,
        regions_present: [
          {
            region_id: "greater_boston",
            region_display_name: "Greater Boston",
            presence_status: "present",
            presence_basis: "office",
            presence_confidence: "high",
            coverage: coverage("tier_2"),
            sector_coverage: { ai: sectorCoverage("tier_3") },
            priority_market: priorityMarket(),
          },
        ],
        regions_hiring: [
          {
            region_id: "sf_bay_area",
            region_display_name: "Greater SF",
            currently_hiring_flag: true,
            active_posting_count_now: 3,
            posting_count_30d: 5,
            posting_count_90d: 8,
            coverage: coverage("tier_4"),
            sector_coverage: {},
          },
        ],
        entry_level_regions: [
          {
            region_id: "greater_boston",
            region_display_name: "Greater Boston",
            internship_count: 1,
            coop_count: 0,
            entry_level_full_time_count: 1,
            formal_early_career_program_flag: true,
            entry_level_access_score: 0.62,
            entry_level_confidence: "high",
            coverage: coverage("tier_2"),
            sector_coverage: {},
            priority_market: priorityMarket(),
          },
        ],
      },
    };
  }
  if (value.startsWith("/companies/comp_a/sources")) {
    return { data: sourceExplanation("comp_a", "company") };
  }
  if (value.startsWith("/companies/comp_a/regions")) {
    return {
      data: {
        company_id: "comp_a",
        company_name: "Acme AI",
        regions: [
          {
            region_id: "greater_boston",
            region_name: "Greater Boston",
            presence_status: "present",
            current_hiring: true,
            has_entry_level_access: true,
            coverage: coverage("tier_2"),
            sector_coverage: { ai: sectorCoverage("tier_3") },
            priority_market: priorityMarket(),
            freshness: freshnessSummary(),
            has_real_data: true,
          },
          {
            region_id: "sf_bay_area",
            region_name: "Greater SF",
            presence_status: "present",
            current_hiring: true,
            has_entry_level_access: false,
            coverage: coverage("tier_4"),
            sector_coverage: {},
            freshness: freshnessSummary(),
            has_real_data: true,
          },
        ],
      },
    };
  }
  if (value.startsWith("/compare")) {
    return {
      data: {
        comparison_id: "greater_boston__sf_bay_area",
        region_a: {
          region_id: "greater_boston",
          display_name: "Greater Boston",
          scores: regionScores(0.74),
          coverage: coverage("tier_3"),
          sector_coverage: {},
          priority_market: priorityMarket(),
        },
        region_b: {
          region_id: "sf_bay_area",
          display_name: "Greater SF",
          scores: regionScores(0.28),
          coverage: coverage("tier_4"),
          sector_coverage: {},
        },
        category_winners: { objective_opportunity_score: "greater_boston" },
        notes: [],
      },
      warnings: [coverageWarning("greater_boston"), coverageWarning("sf_bay_area")],
    };
  }
  if (value === "/discover/personalized") {
    return {
      data: {
        ranked_regions: [
          {
            region_id: "greater_boston",
            display_name: "Greater Boston",
            personal_market_score: 0.78,
            objective_opportunity_score: 0.74,
            coverage: coverage("tier_3"),
            priority_market: priorityMarket(),
            match_notes: ["region_coverage_not_confident"],
          },
          {
            region_id: "sf_bay_area",
            display_name: "Greater SF",
            personal_market_score: 0.44,
            objective_opportunity_score: 0.28,
            coverage: coverage("tier_4"),
            match_notes: ["region_coverage_not_confident"],
          },
        ],
        ranked_companies: [
          {
            company_id: "comp_a",
            company_name: "Acme AI",
            region_id: "greater_boston",
            region_display_name: "Greater Boston",
            personal_company_score: 0.72,
            role_fit: 0.7,
            industry_fit: 0.8,
            prestige_fit: 0.5,
            brand_fit: 0.4,
            match_notes: ["region_coverage_not_confident"],
          },
        ],
      },
      warnings: [coverageWarning("greater_boston")],
    };
  }
  if (value === "/recommendations/goal-modes") {
    return { data: recommendationGoalModes() };
  }
  if (value === "/recommendations/strategy") {
    return { data: recommendationStrategyPayload() };
  }
  if (value === "/monetization/plans") return { data: monetizationPlans() };
  if (value === "/monetization/features") return { data: monetizationFeatures() };
  if (value === "/monetization/reports") return { data: monetizationReports() };
  if (value === "/billing/status") {
    return {
      data: {
        provider: null,
        checkout_available: false,
        portal_available: false,
        checkout_plan_keys: [],
        disabled_reason: "Stripe secret key is not configured.",
      },
    };
  }
  if (value.startsWith("/monetization/access-preview")) {
    return { data: monetizationAccessPreview(value) };
  }
  return { data: null };
}

function stubPublicFetch() {
  const fetchMock = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(async (input) => {
    const payload = responsePayloadFor(input);
    const status = payload.status ?? 200;
    const responseBody = payload.error
      ? errorEnvelope(payload.error.code, payload.error.message)
      : envelope(payload.data, payload.warnings);
    return new Response(JSON.stringify(responseBody), {
      headers: { "Content-Type": "application/json" },
      status,
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderAt(path: string) {
  window.history.pushState(null, "", path);
  return render(
    <FrontendAuthProvider>
      <App />
    </FrontendAuthProvider>,
  );
}

function setDocumentReferrer(value: string) {
  Object.defineProperty(document, "referrer", {
    configurable: true,
    value,
  });
}

describe("public demo routes", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    setDocumentReferrer("");
    window.history.pushState(null, "", "/");
  });

  test("landing page route renders disclosure and public links", async () => {
    renderAt("/");

    expect(await screen.findByRole("heading", { name: "Compare career markets. Choose your next move." })).toBeTruthy();
    expect(screen.getByText("Illustrative portfolio data")).toBeTruthy();
    expect(screen.getAllByText(/Coverage is partial/i).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Explore markets" }).some((link) =>
      link.getAttribute("href") === "/markets"
    )).toBe(true);
    expect(screen.getAllByRole("link", { name: "Guides" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Glossary" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Methodology" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Data limitations" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Privacy" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Terms and disclaimer" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Source explanation" }).length).toBeGreaterThan(0);
  });

  test("demo CTA routes into the existing markets experience", async () => {
    stubPublicFetch();
    renderAt("/");

    fireEvent.click((await screen.findAllByRole("link", { name: "Explore markets" }))[0]);

    expect(window.location.pathname).toBe("/markets");
  });

  test("developer portal and docs routes render API packaging content", async () => {
    renderAt("/developers");

    expect(await screen.findByRole("heading", { name: "Platform API developer portal" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "OpenAPI JSON" }).getAttribute("href"))
      .toBe("/api/v1/platform/docs/openapi.json");
    expect(screen.getByRole("link", { name: "Postman JSON" }).getAttribute("href"))
      .toBe("/api/v1/platform/docs/postman.json");

    cleanup();
    renderAt("/developers/docs/authentication");

    expect(await screen.findByRole("heading", { name: "Authentication" })).toBeTruthy();
    expect(screen.getAllByText(/X-API-Key/i).length).toBeGreaterThan(0);

    cleanup();
    renderAt("/developers/docs/errors");

    expect(await screen.findByRole("heading", { name: "Errors" })).toBeTruthy();
    expect(screen.getByText(/UNSUPPORTED_QUERY/i)).toBeTruthy();
    expect(screen.getByText(/RATE_LIMIT_EXCEEDED/i)).toBeTruthy();
  });

  test("data licensing route renders source-safe dataset cards", async () => {
    renderAt("/data-licensing");

    expect(await screen.findByRole("heading", { name: "Derived market intelligence datasets" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Regional market intelligence" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Early-career access scores" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Company-region presence" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Historical hiring signal snapshots" })).toBeTruthy();
    expect(screen.getAllByText(/Raw scrape records/i).length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Contact sales for enterprise licensing" })).toBeTruthy();
  });

  test("approved iframe embed routes render attribution freshness and source summary", async () => {
    const fetchMock = stubPublicFetch();
    setDocumentReferrer("https://careers.example.edu/page");
    renderAt("/embed/region-comparison");

    expect(await screen.findByRole("heading", { name: "Regional market comparison" })).toBeTruthy();
    expect(screen.getByText(/Powered by Job Market Intelligence/i)).toBeTruthy();
    expect(screen.getByText("Freshness")).toBeTruthy();
    expect(screen.getByText("Source summary")).toBeTruthy();
    expect(screen.getByText(/not a raw export/i)).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/platform/embeds/region-comparison?origin=https%3A%2F%2Fcareers.example.edu%2Fpage",
      expect.anything(),
    );

    cleanup();
    setDocumentReferrer("https://partners.example.org/page");
    renderAt("/embed/market-score-card");

    expect(await screen.findByRole("heading", { name: "Market score card" })).toBeTruthy();
    expect(screen.getByText("Confidence")).toBeTruthy();
    expect(screen.getByText(/no raw records or source ids/i)).toBeTruthy();
  });

  test("blocked and unapproved iframe embed routes render safe denial states", async () => {
    stubPublicFetch();
    setDocumentReferrer("https://blocked.example/frame");
    renderAt("/embed/region-comparison");

    expect(await screen.findByRole("heading", { name: "Embed unavailable" })).toBeTruthy();
    expect(screen.getByText("EMBED_DOMAIN_NOT_ALLOWED")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Regional market comparison" })).toBeNull();
    expect(document.body.textContent ?? "").not.toMatch(/raw_job|raw_scrape|billing|ingestion/i);

    cleanup();
    setDocumentReferrer("https://blocked.example/frame");
    renderAt("/embed/market-score-card");

    expect(await screen.findByRole("heading", { name: "Embed unavailable" })).toBeTruthy();
    expect(screen.getByText("EMBED_DOMAIN_NOT_ALLOWED")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Market score card" })).toBeNull();
    expect(document.body.textContent ?? "").not.toMatch(/raw_job|raw_scrape|billing|ingestion/i);

    cleanup();
    setDocumentReferrer("");
    renderAt("/embed/region-comparison");

    expect(await screen.findByRole("heading", { name: "Embed unavailable" })).toBeTruthy();
    expect(screen.getByText("EMBED_DOMAIN_NOT_ALLOWED")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Regional market comparison" })).toBeNull();

    cleanup();
    setDocumentReferrer("https://unknown.example/frame");
    renderAt("/embed/market-score-card");

    expect(await screen.findByRole("heading", { name: "Embed unavailable" })).toBeTruthy();
    expect(screen.getByText("EMBED_DOMAIN_NOT_ALLOWED")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Market score card" })).toBeNull();
  });

  test("/career-market-guides renders public SEO content cards", () => {
    renderAt("/career-market-guides");

    expect(screen.getByRole("heading", { name: "Opportunity geography guides" })).toBeTruthy();
    for (const page of PUBLIC_SEO_PAGES) {
      expect(screen.getByRole("heading", { name: page.title })).toBeTruthy();
    }
    expect(screen.getAllByRole("link", { name: "Read guide" }).length).toBe(PUBLIC_SEO_PAGES.length);
    expect(screen.getAllByText(/Confidence: Low/i).length).toBeGreaterThan(0);
  });

  test.each(PUBLIC_SEO_PAGES.map((page) => [page.slug, page.routePath, page.title]))(
    "%s renders public SEO page requirements",
    (slug, routePath, title) => {
      renderAt(routePath);

      expect(screen.getByRole("heading", { name: title })).toBeTruthy();
      expect(screen.getAllByText(/Confidence: Low/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/Freshness date/i).length).toBeGreaterThan(0);
      expect(screen.getByRole("heading", { name: "Methodology" })).toBeTruthy();
      expect(screen.getByRole("heading", { name: "Limitations" })).toBeTruthy();
      expect(screen.getByRole("heading", { name: "Warnings" })).toBeTruthy();
      expect(screen.getByRole("heading", { name: "Category language" })).toBeTruthy();
      expect(screen.getByRole("heading", { name: "Related reports" })).toBeTruthy();
      expect(screen.getByRole("heading", { name: "Related benchmarks" })).toBeTruthy();
      expect(screen.getByRole("heading", { name: "Source authority" })).toBeTruthy();
      expect(screen.getByRole("heading", { name: "Share summary" })).toBeTruthy();
      expect(screen.getByRole("heading", { name: "Suggested citation" })).toBeTruthy();
      expect(screen.getByRole("heading", { name: "Institutional use" })).toBeTruthy();
      expect(screen.getByRole("link", { name: "Explore institutional market intelligence" })).toBeTruthy();
      expect(screen.getAllByText(/demo-safe/i).length).toBeGreaterThan(0);
      expect(screen.getAllByRole("link", { name: "Methodology" }).length).toBeGreaterThan(0);
      expect(document.title).toBe(PUBLIC_SEO_PAGES.find((page) => page.slug === slug)?.seo.title);
    },
  );

  test("best cities SEO page renders featured cities and related assets", () => {
    renderAt("/best-cities/best-cities-product-managers");

    expect(screen.getByRole("heading", { name: "Featured cities" })).toBeTruthy();
    expect(screen.getByText(/what this page is measuring/i)).toBeTruthy();
    expect(screen.getAllByText("NYC").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Austin").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Top Product Management Markets" }).getAttribute("href"))
      .toBe("/reports/top-product-management-markets");
    expect(screen.getByRole("link", { name: "Product Career Market Index" }).getAttribute("href"))
      .toBe("/benchmarks/product-career-market-index");
  });

  test("comparison SEO page renders summary, markets, best-for guidance, and tradeoffs", () => {
    renderAt("/compare/nyc-vs-seattle-tech-careers");

    expect(screen.getByRole("heading", { name: "Comparison summary" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Market-by-market sections" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Best-for guidance" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Tradeoffs" })).toBeTruthy();
    expect(screen.getAllByText("NYC").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Seattle").length).toBeGreaterThan(0);
  });

  test("city market SEO page renders market overview and career-market signals", () => {
    renderAt("/career-markets/seattle-ai-careers-market");

    expect(screen.getByRole("heading", { name: "Market overview" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Career-market signals" })).toBeTruthy();
    expect(screen.getAllByText(/company-region presence/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/early-career access/i).length).toBeGreaterThan(0);
  });

  test("role market SEO page renders overview, examples, and early-career access", () => {
    renderAt("/roles/cybersecurity-entry-level-markets");

    expect(screen.getByRole("heading", { name: "Role market overview" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Market examples" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Early-career access" })).toBeTruthy();
    expect(screen.getAllByText(/cybersecurity/i).length).toBeGreaterThan(0);
  });

  test("unknown public SEO slug renders graceful not-found state", () => {
    renderAt("/best-cities/missing-guide");

    expect(screen.getByRole("heading", { name: "Guide not found" })).toBeTruthy();
    expect(screen.getByText(/No public career market guide is registered for missing-guide/i)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Back to guides" })).toBeTruthy();
  });

  test("/reports renders public report cards", async () => {
    stubPublicFetch();
    renderAt("/reports");

    expect(await screen.findByRole("heading", { name: "Market intelligence reports" })).toBeTruthy();
    expect(screen.getAllByText("Best Cities for Early-Career AI Careers").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Top Product Management Markets").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Hidden Tech Hubs for New Graduates").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Confidence: Low/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/warning/i).length).toBeGreaterThan(0);
  });

  test("/benchmarks renders public benchmark cards", async () => {
    stubPublicFetch();
    renderAt("/benchmarks");

    expect(await screen.findByRole("heading", { name: "Career market indices" })).toBeTruthy();
    expect(screen.getAllByText("Early-Career Tech Access Index").length).toBeGreaterThan(0);
    expect(screen.getAllByText("AI Career Geography Index").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Product Career Market Index").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Confidence: Low/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/warning/i).length).toBeGreaterThan(0);
  });

  test.each(PUBLIC_REPORT_SLUGS)("/reports/%s renders report detail", async (slug) => {
    stubPublicFetch();
    renderAt(`/reports/${slug}`);
    const report = publicReport(slug);

    expect(await screen.findByRole("heading", { name: report.title })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Methodology" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Limitations" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Warnings" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Source and provenance summary" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Source authority" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Share summary" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Suggested citation" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Institutional use" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Use this report for career-center planning" })).toBeTruthy();
    expect(screen.getAllByText(/Freshness/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Confidence: Low/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Featured-market example only/i).length).toBeGreaterThan(0);
    expect(screen.getByText("No benchmark or index score is presented here.")).toBeTruthy();
  });

  test.each(PUBLIC_BENCHMARK_SLUGS)("/benchmarks/%s renders benchmark detail", async (slug) => {
    stubPublicFetch();
    renderAt(`/benchmarks/${slug}`);
    const benchmark = publicBenchmark(slug);

    expect(await screen.findByRole("heading", { name: benchmark.name })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Methodology" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Score display" })).toBeTruthy();
    expect(screen.getAllByRole("heading", { name: "Subscores" }).length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "Limitations" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Warnings" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Source and provenance summary" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Related links" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Source authority" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Share summary" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Suggested citation" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Institutional use" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Benchmark methodology" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Market intelligence reports" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Compare markets for student placement strategy" })).toBeTruthy();
    expect(screen.getAllByText(/Freshness/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Confidence: Low/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/demo-safe display/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/not a supported benchmark/i).length).toBeGreaterThan(0);
    expect(screen.getByText("No benchmark or index score is presented here.")).toBeTruthy();
  });

  test("unknown public report slug renders graceful not-found state", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const value = typeof input === "string" ? input : input.toString();
      if (value === "/public/reports") {
        return new Response(JSON.stringify(envelope(publicReports())), {
          headers: { "Content-Type": "application/json" },
          status: 200,
        });
      }
      return new Response(JSON.stringify({
        status: "error",
        data: null,
        metadata: { state: "failed", warnings: [] },
        error: { code: "NOT_FOUND", message: "Public report not found: 'missing-report'" },
      }), {
        headers: { "Content-Type": "application/json" },
        status: 404,
      });
    }));

    renderAt("/reports/missing-report");

    expect(await screen.findByRole("heading", { name: "Report not found" })).toBeTruthy();
    expect(screen.getByText(/No public report is registered for missing-report/i)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Back to reports" })).toBeTruthy();
  });

  test("unknown public benchmark slug renders graceful not-found state", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const value = typeof input === "string" ? input : input.toString();
      if (value === "/public/benchmarks") {
        return new Response(JSON.stringify(envelope(publicBenchmarks())), {
          headers: { "Content-Type": "application/json" },
          status: 200,
        });
      }
      return new Response(JSON.stringify({
        status: "error",
        data: null,
        metadata: { state: "failed", warnings: [] },
        error: { code: "NOT_FOUND", message: "Public benchmark not found: 'missing-index'" },
      }), {
        headers: { "Content-Type": "application/json" },
        status: 404,
      });
    }));

    renderAt("/benchmarks/missing-index");

    expect(await screen.findByRole("heading", { name: "Benchmark not found" })).toBeTruthy();
    expect(screen.getByText(/No public benchmark is registered for missing-index/i)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Back to benchmarks" })).toBeTruthy();
  });

  test("region page renders read-only visualization and unsupported precision states", async () => {
    stubPublicFetch();
    renderAt("/markets/region/greater_boston");

    expect(await screen.findByText("Canonical/default score breakdown")).toBeTruthy();
    expect(screen.getAllByText("Coverage: Tier 2 - partial but useful market").length).toBeGreaterThan(0);
    expect(screen.getByText("Heuristic coverage score: 62%")).toBeTruthy();
    expect(screen.getAllByText("Coverage is partial; compare this market with caution.").length).toBeGreaterThan(0);
    expect(screen.getByText(/Sector coverage ·/)).toBeTruthy();
    expect(screen.getAllByText("Sector level: Watchlist").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Coverage: Tier 3 - watchlist / emerging market").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Priority #10: Boston").length).toBeGreaterThan(0);
    expect((await screen.findAllByText("Real imported data")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Fresh").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Current snapshot").length).toBeGreaterThan(0);
    expect(screen.queryByText("Unsupported visualization state")).toBeNull();
  });

  test("canonical slug cold navigation loads the canonical Region", async () => {
    const fetchMock = stubPublicFetch();
    renderAt("/markets/region/boston");

    expect(await screen.findByRole("heading", { name: "Greater Boston" })).toBeTruthy();
    expect(
      fetchMock.mock.calls.some(([url]) =>
        ["/regions/boston", "/regions/greater_boston"].includes(String(url)),
      ),
    ).toBe(true);
    expect(screen.queryByText(/Unknown region ID/i)).toBeNull();
  });

  test("in-app Region navigation prefers the published canonical slug", async () => {
    stubPublicFetch();
    renderAt("/markets");
    await screen.findByRole("heading", { name: "Explore markets" });

    fireEvent.click(screen.getByRole("button", { name: "Open region detail" }));

    await waitFor(() => {
      expect(window.location.pathname).toBe("/markets/region/boston");
    });
    expect(await screen.findByRole("heading", { name: "Greater Boston" })).toBeTruthy();
  });

  test("legacy Region token reaches backend resolution and normalizes the URL", async () => {
    const fetchMock = stubPublicFetch();
    renderAt("/markets/region/greater_sf");

    expect(await screen.findByRole("heading", { name: "Greater SF" })).toBeTruthy();
    await waitFor(() => {
      expect(window.location.pathname).toBe(
        "/markets/region/san-francisco-bay-area",
      );
    });
    expect(
      fetchMock.mock.calls.some(([url]) => String(url) === "/regions/greater_sf"),
    ).toBe(true);
  });

  test("unknown Region token reaches resolution and fails cleanly", async () => {
    const fetchMock = stubPublicFetch();
    renderAt("/markets/region/not-a-real-market");

    expect(await screen.findByText("Region not found.")).toBeTruthy();
    expect(screen.queryByText(/Unknown region ID/i)).toBeNull();
    await new Promise((resolve) => window.setTimeout(resolve, 50));
    expect(
      fetchMock.mock.calls.filter(
        ([url]) => String(url) === "/regions/not-a-real-market",
      ),
    ).toHaveLength(1);
  });

  test("ambiguous Region resolution is terminal and request-bounded", async () => {
    const fetchMock = stubPublicFetch();
    renderAt("/markets/region/ambiguous-market");

    expect(await screen.findByText("Region is ambiguous.")).toBeTruthy();
    await new Promise((resolve) => window.setTimeout(resolve, 50));
    expect(
      fetchMock.mock.calls.filter(
        ([url]) => String(url) === "/regions/ambiguous-market",
      ),
    ).toHaveLength(1);
  });

  test("Region route recovers after invalid token changes to a valid slug", async () => {
    const fetchMock = stubPublicFetch();
    renderAt("/markets/region/not-a-real-market");
    expect(await screen.findByText("Region not found.")).toBeTruthy();

    window.history.pushState(null, "", "/markets/region/boston");
    window.dispatchEvent(new PopStateEvent("popstate"));

    expect(await screen.findByRole("heading", { name: "Greater Boston" })).toBeTruthy();
    expect(
      fetchMock.mock.calls.filter(
        ([url]) => String(url) === "/regions/not-a-real-market",
      ),
    ).toHaveLength(1);
    expect(
      fetchMock.mock.calls.filter(([url]) =>
        ["/regions/boston", "/regions/greater_boston"].includes(String(url)),
      ),
    ).toHaveLength(1);
  });

  test("explore markets renders coverage labels for fully covered and placeholder markets", async () => {
    stubPublicFetch();
    renderAt("/markets");

    expect((await screen.findAllByText("Coverage: Tier 1 - fully covered market")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Coverage: Tier 4 - placeholder only").length).toBeGreaterThan(0);
    expect(screen.getByText(/Coverage labels separately show/i)).toBeTruthy();
  });

  test("comparison renders weak coverage warnings beside region results", async () => {
    stubPublicFetch();
    renderAt("/markets/compare?region_a=greater_boston&region_b=sf_bay_area");

    expect(await screen.findByRole("heading", { name: "Coverage context" })).toBeTruthy();
    expect(screen.getAllByText("Coverage: Tier 3 - watchlist / emerging market").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Coverage: Tier 4 - placeholder only").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/not covered enough for confident recommendations/i).length).toBeGreaterThan(0);
  });

  test("personalized discovery renders coverage warnings and cautious ranked labels", async () => {
    stubPublicFetch();
    renderAt("/markets/discovery");

    fireEvent.click(await screen.findByRole("button", { name: "Run discovery" }));

    expect(await screen.findByRole("heading", { name: "Ranked regions" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Ranked company-region pairs" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Recommended regions" })).toBeNull();
    expect(screen.getAllByText("Coverage: Tier 3 - watchlist / emerging market").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Coverage: Tier 4 - placeholder only").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/not covered enough for confident recommendations/i).length).toBeGreaterThan(0);
  });

  test("career identity route is admitted through the product app shell", async () => {
    stubPublicFetch();
    const route = parseRoute("/markets/career-identity", "");

    expect(route.page).toBe("career-identity");
    expect(isProductPage(route.page)).toBe(true);

    renderAt("/markets/career-identity");

    expect(await screen.findByText("Sign in to manage Career Identity")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Terms and disclaimer" })).toBeNull();
  });

  test("recommendations page loads goal modes and renders evidence-bound ranking cards", async () => {
    stubPublicFetch();
    renderAt("/markets/recommendations");

    expect(await screen.findByRole("heading", { name: /Greater Boston is the strongest actionable market/i })).toBeTruthy();
    expect((screen.getByLabelText("What should the ranking optimize?") as HTMLSelectElement).value).toBe(
      "maximize_entry_level_access",
    );
    expect(screen.getAllByText("Maximize entry-level access").length).toBeGreaterThan(0);
    expect(await screen.findByRole("heading", { name: "Ranked markets" })).toBeTruthy();
    expect(screen.getAllByText("Greater Boston").length).toBeGreaterThan(0);
    expect(screen.getByText("relative fit")).toBeTruthy();
    expect(screen.getByText("High prestige but weaker entry-level accessibility")).toBeTruthy();
    expect(screen.getByText("Inspect scoring, trade-offs, and evidence")).toBeTruthy();
    expect(
      screen.getAllByText("Company rankings unavailable: no company outputs were available.").length,
    ).toBeGreaterThan(0);
    expect(screen.queryByRole("textbox", { name: /prompt/i })).toBeNull();
    expect(screen.queryByText(/AI summary/i)).toBeNull();
    expect(screen.queryByText("Generate a full strategy report with Individual.")).toBeNull();
    expect(screen.getByRole("link", { name: "Open Decision Workspace" })).toBeTruthy();
  });

  test("plans page renders plan catalog reports and trust-safe access previews", async () => {
    stubPublicFetch();
    renderAt("/markets/plans");

    expect(await screen.findByRole("heading", { name: "Plans and access model" })).toBeTruthy();
    for (const planName of [
      "Free",
      "Individual Monthly",
      "Individual Annual",
      "Student Annual",
      "Career Center License",
      "Bootcamp License",
      "University License",
      "Workforce Board License",
    ]) {
      expect(screen.getByRole("heading", { name: planName })).toBeTruthy();
    }

    expect(screen.getByText(/Free users still receive useful market exploration/i)).toBeTruthy();
    expect(screen.getAllByText("Basic recommendation result remains visible").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "Personalized Market Strategy Report" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Region Comparison Report" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Company Geography Report" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Early-Career Opportunity Report" })).toBeTruthy();
    expect(await screen.findAllByText(/View plans for Individual Monthly/i)).toBeTruthy();

    const pageText = document.body.textContent ?? "";
    expect(pageText).not.toMatch(/Buy now/i);
    expect(pageText).not.toMatch(/payment success/i);
    expect(pageText).not.toMatch(/Unlock the truth/i);
    expect(pageText).not.toMatch(/Pay to see your best market/i);
    expect(pageText).not.toMatch(/recommendation is hidden/i);
  });

  test("recommendations selector reloads strategy for selected goal mode", async () => {
    const fetchMock = stubPublicFetch();
    renderAt("/markets/recommendations");

    await screen.findByRole("heading", { name: /Greater Boston is the strongest actionable market/i });
    fireEvent.change(screen.getByLabelText("What should the ranking optimize?"), {
      target: { value: "maximize_ai_cloud_concentration" },
    });

    expect(window.location.pathname).toBe("/markets/recommendations");
    expect(window.location.search).toContain("maximize_ai_cloud_concentration");
    await waitFor(() => {
      const strategyCalls = fetchMock.mock.calls.filter(([url]) => url === "/recommendations/strategy");
      expect(strategyCalls.length).toBeGreaterThanOrEqual(2);
      expect(String((strategyCalls.at(-1)?.[1] as RequestInit).body)).toContain(
        "maximize_ai_cloud_concentration",
      );
    });
  });

  test("recommendations strategy renders fallback watchlist timing and heuristic role guidance", async () => {
    stubPublicFetch();
    renderAt("/markets/recommendations");

    expect(await screen.findByRole("heading", { name: "Where the evidence supports action" })).toBeTruthy();
    expect(screen.getAllByText(/Primary target|Fallback target/).length).toBeGreaterThan(0);
    expect(screen.getByText(/market.*to monitor/i)).toBeTruthy();
    expect(screen.getByText("Method and supporting evidence")).toBeTruthy();
    expect(screen.getByText("Ranked target uses proxy-heavy evidence.")).toBeTruthy();
    expect(screen.getAllByText(/Lower competition is not directly measured/).length).toBeGreaterThan(0);
  });

  test("company geography keeps coverage separate from freshness and sector coverage", async () => {
    stubPublicFetch();
    renderAt("/markets/company/comp_a");

    expect(await screen.findByRole("heading", { name: "Acme AI" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Strongest market signals" })).toBeTruthy();
    expect(screen.getAllByText("Coverage: Tier 2 - partial but useful market").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Coverage: Tier 4 - placeholder only").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Sector coverage ·/).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Real imported data").length).toBeGreaterThan(0);
  });

  test("older region responses without coverage render fallback without sector noise", async () => {
    stubPublicFetch();
    renderAt("/markets/region/legacy_market");

    expect(await screen.findByRole("heading", { name: "Legacy Market" })).toBeTruthy();
    expect(screen.getByText("Coverage unavailable")).toBeTruthy();
    expect(screen.getByText("Coverage metadata is unavailable for this response.")).toBeTruthy();
    expect(screen.queryByText("Sector coverage")).toBeNull();
  });

  test.each([
    ["/glossary", "Category glossary", /Opportunity geography/i],
    ["/methodology", "How market intelligence works", /interpret market comparisons/i],
    ["/data-limitations", "Data limitations", /Scores are derived signals/i],
    ["/privacy", "Privacy notice", /Public browsing/i],
    ["/terms", "Terms and disclaimer", /No guarantee/i],
    ["/sources", "Source explanation", /Imported or source data/i],
  ])("%s renders public document content", (path, heading, marker) => {
    renderAt(path);

    expect(screen.getByRole("heading", { name: heading })).toBeTruthy();
    expect(screen.getAllByText(marker).length).toBeGreaterThan(0);
  });
});
