// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import App from "./App";
import { FrontendAuthProvider } from "./auth";

type MockPayload = {
  data: unknown;
  warnings?: unknown[];
};

function envelope(data: unknown, warnings: unknown[] = []) {
  return {
    status: "success",
    data,
    metadata: { state: "test", source_versions: {}, warnings },
    error: null,
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

function responsePayloadFor(input: RequestInfo | URL): MockPayload {
  const value = typeof input === "string" ? input : input.toString();

  if (value === "/health") return { data: { service: "test" } };
  if (value === "/regions") {
    return {
      data: {
        regions: [
          {
            region_id: "greater_boston",
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
            region_id: "greater_sf",
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
  if (value === "/regions/greater_boston") {
    return {
      data: regionDetail("greater_boston", "Greater Boston", "tier_2", {
        ai: sectorCoverage("tier_3"),
      }),
    };
  }
  if (value === "/regions/greater_sf") {
    return { data: regionDetail("greater_sf", "Greater SF", "tier_4") };
  }
  if (value === "/regions/legacy_market") {
    return { data: regionDetail("legacy_market", "Legacy Market") };
  }
  if (value.startsWith("/regions/greater_boston/sources")) {
    return { data: sourceExplanation("greater_boston") };
  }
  if (value.startsWith("/regions/greater_sf/sources")) {
    return { data: sourceExplanation("greater_sf") };
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
            region_id: "greater_sf",
            name: "Greater SF",
            region_name: "greater_sf",
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
            region_id: "greater_sf",
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
            region_id: "greater_sf",
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
        comparison_id: "greater_boston__greater_sf",
        region_a: {
          region_id: "greater_boston",
          display_name: "Greater Boston",
          scores: regionScores(0.74),
          coverage: coverage("tier_3"),
          sector_coverage: {},
          priority_market: priorityMarket(),
        },
        region_b: {
          region_id: "greater_sf",
          display_name: "Greater SF",
          scores: regionScores(0.28),
          coverage: coverage("tier_4"),
          sector_coverage: {},
        },
        category_winners: { objective_opportunity_score: "greater_boston" },
        notes: [],
      },
      warnings: [coverageWarning("greater_boston"), coverageWarning("greater_sf")],
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
            region_id: "greater_sf",
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
    return new Response(JSON.stringify(envelope(payload.data, payload.warnings)), {
      headers: { "Content-Type": "application/json" },
      status: 200,
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

describe("public demo routes", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    window.history.pushState(null, "", "/");
  });

  test("landing page route renders disclosure and public links", () => {
    renderAt("/");

    expect(screen.getByRole("heading", { name: "Job Market Intelligence" })).toBeTruthy();
    expect(screen.getByText("Public demo disclosure")).toBeTruthy();
    expect(screen.getAllByText(/Coverage is partial/i).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Enter demo" }).some((link) =>
      link.getAttribute("href") === "/markets"
    )).toBe(true);
    expect(screen.getAllByRole("link", { name: "Data limitations" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Privacy" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Terms and disclaimer" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Source explanation" }).length).toBeGreaterThan(0);
  });

  test("demo CTA routes into the existing markets experience", async () => {
    stubPublicFetch();
    renderAt("/");

    fireEvent.click(screen.getAllByRole("link", { name: "Enter demo" })[0]);

    expect(window.location.pathname).toBe("/markets");
    expect(await screen.findByRole("heading", { name: "Explore markets" })).toBeTruthy();
  });

  test("region page renders read-only visualization and unsupported precision states", async () => {
    stubPublicFetch();
    renderAt("/markets/region/greater_boston");

    expect(await screen.findByText("Canonical/default score breakdown")).toBeTruthy();
    expect(screen.getAllByText("Coverage: Tier 2 - partial but useful market").length).toBeGreaterThan(0);
    expect(screen.getByText("Heuristic coverage score: 62%")).toBeTruthy();
    expect(screen.getAllByText("Coverage is partial; compare this market with caution.").length).toBeGreaterThan(0);
    expect(screen.getByText("Sector coverage")).toBeTruthy();
    expect(screen.getAllByText("Sector level: Watchlist").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Coverage: Tier 3 - watchlist / emerging market").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Priority #10: Boston").length).toBeGreaterThan(0);
    expect((await screen.findAllByText("Real imported data")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Fresh").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Current snapshot").length).toBeGreaterThan(0);
    expect(screen.getByText("Unsupported visualization state")).toBeTruthy();
    expect(screen.getByText("Historical trend view")).toBeTruthy();
    expect(screen.getByText("Opportunity heatmap")).toBeTruthy();
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
    renderAt("/markets/compare?region_a=greater_boston&region_b=greater_sf");

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

  test("recommendations page loads goal modes and renders evidence-bound ranking cards", async () => {
    stubPublicFetch();
    renderAt("/markets/recommendations");

    expect(await screen.findByRole("heading", { name: "Recommendation decision support" })).toBeTruthy();
    expect((screen.getByLabelText("Recommendation goal mode") as HTMLSelectElement).value).toBe(
      "maximize_entry_level_access",
    );
    expect(screen.getAllByText("Maximize entry-level access").length).toBeGreaterThan(0);
    expect(await screen.findByRole("heading", { name: "Ranked region recommendations" })).toBeTruthy();
    expect(screen.getAllByText("Greater Boston").length).toBeGreaterThan(0);
    expect(screen.getByText("Final score")).toBeTruthy();
    expect(screen.getByText("Ranked by Maximize entry-level access")).toBeTruthy();
    expect(screen.getByText("High prestige but weaker entry-level accessibility")).toBeTruthy();
    expect(screen.getAllByText("Verify current job postings").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Proxy").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Inferred").length).toBeGreaterThan(0);
    expect(
      screen.getAllByText("Company rankings unavailable: no company outputs were available.").length,
    ).toBeGreaterThan(0);
    expect(screen.queryByRole("textbox", { name: /prompt/i })).toBeNull();
    expect(screen.queryByText(/AI summary/i)).toBeNull();
    expect(screen.getByText("Generate a full strategy report with Individual.")).toBeTruthy();
    expect(screen.getByText(/The ranked recommendation stays visible here/i)).toBeTruthy();
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

    await screen.findByRole("heading", { name: "Recommendation decision support" });
    fireEvent.change(screen.getByLabelText("Recommendation goal mode"), {
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

    expect(await screen.findByRole("heading", { name: "Market strategy plan" })).toBeTruthy();
    expect(screen.getByText("Primary regions")).toBeTruthy();
    expect(screen.getByText("Fallback regions")).toBeTruthy();
    expect(screen.getByText("Watchlist")).toBeTruthy();
    expect(screen.getByText("Timing guidance")).toBeTruthy();
    expect(screen.getByText("Role-family guidance")).toBeTruthy();
    expect(screen.getAllByText("Heuristic / inferred").length).toBeGreaterThan(0);
    expect(screen.getByText("Ranked target uses proxy-heavy evidence.")).toBeTruthy();
    expect(screen.getByText("Check current company/career pages before treating ranked targets as actionable.")).toBeTruthy();
    expect(screen.getByText("Lower competition is not directly measured.")).toBeTruthy();
  });

  test("company geography keeps coverage separate from freshness and sector coverage", async () => {
    stubPublicFetch();
    renderAt("/markets/company/comp_a");

    expect(await screen.findByRole("heading", { name: "Observed region signals" })).toBeTruthy();
    expect(screen.getAllByText("Coverage: Tier 2 - partial but useful market").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Coverage: Tier 4 - placeholder only").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Sector coverage").length).toBeGreaterThan(0);
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
    ["/data-limitations", "Data limitations", /Scores are derived signals/i],
    ["/privacy", "Privacy notice", /Public browsing/i],
    ["/terms", "Terms and disclaimer", /No guarantee/i],
    ["/sources", "Source explanation", /Imported or source data/i],
  ])("%s renders public legal content", (path, heading, marker) => {
    renderAt(path);

    expect(screen.getByRole("heading", { name: heading })).toBeTruthy();
    expect(screen.getByText(marker)).toBeTruthy();
  });
});
