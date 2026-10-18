// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import type { ComponentProps } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import RecommendationExperience from "./RecommendationExperience";
import type { ApiEnvelope, PersonalizedResult, RecommendationGoalModesPayload, RecommendationStrategyPayload } from "./types";

afterEach(cleanup);

function envelope<T>(data: T): ApiEnvelope<T> {
  return { data, error: null, metadata: {} } as ApiEnvelope<T>;
}

const ranking = {
  rank: 1,
  target: { target_id: "sf_bay_area", target_type: "region", display_label: "San Francisco Bay Area" },
  goal_mode: "maximize_entry_level_access",
  final_score: 0.58,
  normalized_score: 0.76,
  confidence_contribution: 0.2,
  freshness_contribution: 0.2,
  coverage_contribution: 0.2,
  warnings: ["Coverage is intentionally bounded."],
  score_components_used: [{ component: "entry_level_access", value: 0.8, weight: 0.3, weighted_value: 0.24, is_proxy: false, inferred: false, evidence_basis: ["observed"] }],
  score_components_proxy: [],
  score_components_missing: [],
  penalties_applied: [],
  explanation: {
    fit_reasons: [{ label: "Entry-level access", detail: "More supported entry-level evidence.", evidence_strength: "moderate", evidence_basis: ["observed"], support: "direct" }],
    data_strengths: [], weaknesses: [],
    tradeoffs: [{ tradeoff_category: "coverage", label: "Bounded coverage", positive_side: "Useful supported evidence", negative_side: "Not a nationwide census", evidence_strength: "moderate", evidence_basis: ["coverage"], support: "direct" }],
    manual_verification: [], evidence_refs: [{ basis: "market_signal", strength: "moderate", reference_id: "ref-1" }], provenance_refs: ["ref-1"], coverage_warnings: ["Limited coverage"],
  },
} as unknown as RecommendationStrategyPayload["ranked_region_recommendations"][number];

const strategy = {
  available_goal_modes: [{ goal_mode: "maximize_entry_level_access", label: "Maximize entry-level access", description: "Favor early-career access.", prioritization_summary: "Entry-level evidence leads.", weighted_components: [], penalty_components: [], missing_data_behavior: "Missing stays unknown.", warnings: [] }],
  ranked_region_recommendations: [ranking],
  ranked_company_recommendations: [],
  warnings: ["Synthetic scenario evidence is not live hiring verification."],
  market_strategy_plan: {
    goal_mode: "maximize_entry_level_access", strategy_version: "v1", source_recommendations: ["sf_bay_area"],
    primary_region_targets: [{ target_role: "primary", target: ranking.target, source_rank: 1, final_score: 0.58, rationale: "Strongest supported entry-level result.", tradeoff_categories: ["coverage"], evidence_strength: "moderate", evidence_basis: ["market_signal"], support: "direct" }],
    secondary_region_targets: [], fallback_region_targets: [], watchlist_items: [], company_targets: [], company_category_targets: [], role_family_targets: [], timing_guidance: [],
    manual_verification_checklist: { items: [] }, evidence_warnings: [{ warning_category: "coverage", label: "Coverage is bounded", detail: "Eight illustrative markets.", evidence_strength: "moderate", evidence_basis: ["coverage"], support: "direct" }],
  },
} as unknown as RecommendationStrategyPayload;

const emptyPersonalizedState = { loading: false, error: null, envelope: null };

function renderExperience(overrides: Partial<ComponentProps<typeof RecommendationExperience>> = {}) {
  return render(<RecommendationExperience
    activeView="by-goal"
    authenticated
    goalModesState={{ loading: false, error: null, envelope: envelope({ goal_modes: strategy.available_goal_modes } as RecommendationGoalModesPayload) }}
    onNavigate={vi.fn()}
    onRetryPersonalized={vi.fn()}
    onSelectGoalMode={vi.fn()}
    onSelectView={vi.fn()}
    personalizedState={emptyPersonalizedState}
    selectedGoalMode="maximize_entry_level_access"
    strategyState={{ loading: false, error: null, envelope: envelope(strategy) }}
    {...overrides}
  />);
}

describe("RecommendationExperience", () => {
  test("presents the conclusion and action before technical evidence", () => {
    renderExperience();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("San Francisco Bay Area is the strongest actionable market");
    expect(screen.getByText("Strongest supported entry-level result.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Explore San Francisco Bay Area" })).toHaveAttribute("href", "/markets?focus=sf_bay_area");
    expect(screen.getByText(/Career Identity does not change these rankings/i)).toBeInTheDocument();
    expect(screen.getByText("Coverage is bounded")).toBeInTheDocument();
    expect(screen.getByText("Score components")).not.toBeVisible();
  });

  test("switches recommendation goals through the stable callback", () => {
    const onSelect = vi.fn();
    const goals = [...strategy.available_goal_modes, { ...strategy.available_goal_modes[0], goal_mode: "prefer_ai_cloud_hubs", label: "Prefer AI and cloud hubs" }];
    renderExperience({ goalModesState: { loading: false, error: null, envelope: envelope({ goal_modes: goals } as RecommendationGoalModesPayload) }, onSelectGoalMode: onSelect });
    fireEvent.change(screen.getByLabelText("What should the ranking optimize?"), { target: { value: "prefer_ai_cloud_hubs" } });
    expect(onSelect).toHaveBeenCalledWith("prefer_ai_cloud_hubs");
  });

  test("distinguishes a numerical watchlist leader from the actionable fallback", () => {
    const austin = { ...ranking, target: { ...ranking.target, target_id: "austin", display_label: "Austin" } };
    const boston = { ...ranking, rank: 2, target: { ...ranking.target, target_id: "greater_boston", display_label: "Greater Boston" } };
    const lowerCompetition = {
      ...strategy,
      ranked_region_recommendations: [austin, boston],
      market_strategy_plan: {
        ...strategy.market_strategy_plan,
        primary_region_targets: [],
        fallback_region_targets: [{ ...strategy.market_strategy_plan.primary_region_targets[0], target_role: "fallback", target: boston.target, source_rank: 2 }],
        watchlist_items: [{ target: austin.target, watchlist_category: "weak_evidence", reason: "The leading score depends on limited evidence.", upside: "Lower competition proxy.", what_to_verify: "Verify current role volume.", revisit_after_refresh: true, source_recommendation_ids: ["austin"], evidence_strength: "weak", evidence_basis: ["coverage"], support: "inferred", evidence_refs: [] }],
      },
    } as unknown as RecommendationStrategyPayload;
    renderExperience({ selectedGoalMode: "maximize_lower_competition", strategyState: { loading: false, error: null, envelope: envelope(lowerCompetition) } });
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Greater Boston is the actionable fallback");
    expect(screen.getByText(/Austin has the highest numerical score but is not an actionable target/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Explore Greater Boston" })).toHaveAttribute("href", "/markets?focus=greater_boston");
    expect(screen.getByText("Verify: current role volume.")).toBeInTheDocument();
    expect(screen.queryByText(/Verify:\s*Verify:/i)).not.toBeInTheDocument();
  });

  test("renders authenticated Career Identity results and preserves market and supported role context", () => {
    const personalized = envelope<PersonalizedResult>({
      ranked_regions: [{ region_id: "sf_bay_area", display_name: "San Francisco Bay Area", personal_market_score: 0.84, objective_opportunity_score: 0.71, match_notes: ["role:applied_ai"] }],
      ranked_companies: [],
    });
    personalized.metadata.career_identity_personalization = {
      source: "career_identity",
      career_identity_applied: true,
      role_targets: ["applied_ai"],
      industry_preferences: ["ai"],
      region_ids: ["sf_bay_area"],
    };
    renderExperience({ activeView: "for-you", personalizedState: { loading: false, error: null, envelope: personalized } });
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("San Francisco Bay Area best matches your stated preferences");
    expect(screen.getByRole("link", { name: "Explore relevant opportunities" })).toHaveAttribute("href", "/markets/current-opportunities?market=sf_bay_area&role=applied_ai&opportunity_type=job");
  });

  test("uses market exploration when Career Identity has no supported opportunity role", () => {
    const personalized = envelope<PersonalizedResult>({
      ranked_regions: [{ region_id: "sf_bay_area", display_name: "San Francisco Bay Area", personal_market_score: 0.84, objective_opportunity_score: 0.71, match_notes: [] }],
      ranked_companies: [],
    });
    personalized.metadata.career_identity_personalization = {
      source: "career_identity",
      career_identity_applied: true,
      role_targets: ["research_strategy"],
      industry_preferences: ["ai"],
      region_ids: ["sf_bay_area"],
    };
    renderExperience({ activeView: "for-you", personalizedState: { loading: false, error: null, envelope: personalized } });
    expect(screen.getByRole("link", { name: "Explore San Francisco Bay Area" })).toHaveAttribute("href", "/markets?focus=sf_bay_area");
    expect(screen.queryByRole("link", { name: "Explore relevant opportunities" })).not.toBeInTheDocument();
  });

  test("does not present request fallbacks as Career Identity personalization", () => {
    const response = envelope<PersonalizedResult>({ ranked_regions: [], ranked_companies: [] });
    response.metadata.career_identity_personalization = { source: "request", career_identity_applied: false, reason: "downstream_personalization_consent_not_granted" };
    renderExperience({ activeView: "for-you", personalizedState: { loading: false, error: null, envelope: response } });
    expect(screen.getByText("Personalization consent is off.")).toBeInTheDocument();
    expect(screen.queryByText(/best matches your stated preferences/i)).not.toBeInTheDocument();
  });

  test("offers an intentional retry from a personalized-discovery error", () => {
    const onRetry = vi.fn();
    renderExperience({
      activeView: "for-you",
      onRetryPersonalized: onRetry,
      personalizedState: { loading: false, error: "The service could not be reached.", envelope: null },
    });

    expect(screen.getByRole("alert")).toHaveTextContent("The service could not be reached.");
    fireEvent.click(screen.getByRole("button", { name: "Retry For You" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
