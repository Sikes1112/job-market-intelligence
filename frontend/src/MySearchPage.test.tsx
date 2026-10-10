// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import MySearchPage from "./MySearchPage";
import type { FrontendAuthContextValue } from "./auth";
import type { ApiEnvelope, CareerDecision, CurrentOpportunityMatchPayload, MySearchWorkspace } from "./types";

const mocks = vi.hoisted(() => ({
  workspace: vi.fn(), decision: vi.fn(), journal: vi.fn(), matches: vi.fn(),
  action: vi.fn(), actionPlan: vi.fn(), updateAction: vi.fn(), application: vi.fn(),
  track: vi.fn(), transition: vi.fn(), updateDecision: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => ({
  ...await importOriginal<typeof import("./api")>(),
  getMySearchWorkspace: mocks.workspace,
  getCareerDecision: mocks.decision,
  getCareerDecisionJournal: mocks.journal,
  getCurrentOpportunityMatches: mocks.matches,
  createCareerAction: mocks.action,
  createCareerActionPlan: mocks.actionPlan,
  updateCareerAction: mocks.updateAction,
  createCareerApplication: mocks.application,
  trackCurrentOpportunity: mocks.track,
  transitionCareerApplication: mocks.transition,
  updateCareerDecision: mocks.updateDecision,
}));

function envelope<T>(data: T): ApiEnvelope<T> {
  return { status: "success", data, metadata: { state: "fresh" }, error: null };
}

const auth: FrontendAuthContextValue = {
  isConfigured: true, isAuthenticated: true, isLoading: false, error: null,
  user: { sub: "user" }, login: vi.fn(), logout: vi.fn(), getAccessTokenSilently: vi.fn(async () => "token"),
};

function workspace(nextAction = "Review Boston AI Product openings"): MySearchWorkspace {
  return {
    active_pursuits: [{
      decision_id: "decision-boston", decision_type: "location_choice", status: "decided", title: "Prioritize Greater Boston",
      selected_priority: { option_id: "option-boston", title: "Greater Boston", region_id: "greater_boston", public_slug: "boston" },
      alternatives: [{ option_id: "option-nyc", title: "Greater New York", region_id: "greater_nyc", public_slug: "new-york" }],
      target_context: "AI Product · Internship", prioritized_at: "2026-10-09T12:00:00Z",
      next_action: { action_id: nextAction.startsWith("Review") ? "action-1" : "action-2", action_type: "research", status: "open", title: nextAction, description: null, due_at: null, priority: 1, completed_at: null, updated_at: "2026-10-09T12:00:00Z" },
      open_action_count: 2, completed_action_count: 0,
      applications: [{ application_id: "application-1", decision_id: "decision-boston", company_id: "acme", company_name: "Acme AI", region_id: "greater_boston", market_name: "Greater Boston", role_title: "AI Product Intern", status: "preparing", applied_at: null, follow_up_at: null, source_url: "https://jobs.example/apply", current_opportunity_id: "opportunity-1", needs_attention: true, attention_reason: "Not submitted", created_at: "2026-10-09T12:00:00Z", updated_at: "2026-10-09T12:00:00Z" }],
      active_application_count: 1, applications_needing_attention: 1,
      source_comparison: { comparison_id: "comparison-1", compared_markets: ["Greater Boston", "Greater New York"], system_recommendation: ["Greater New York"], original_user_choice: "Greater Boston", original_choice_matches_recommendation: false, current_user_choice: "Greater Boston", current_choice_matches_recommendation: false, recommendation_state: "near_tie", recommendation_summary: "The comparison slightly favored New York.", generated_at: "2026-10-09T12:00:00Z" },
      current_opportunities: { market_id: "greater_boston", coverage_status: "production_ready", coverage_rationale: "Curated current coverage.", coverage_limitations: [], observed_active_count: 4, ranking_eligible_count: 4, fresh_count: 4, latest_observed_at: "2026-10-09T12:00:00Z", top_opportunities: [] },
      latest_meaningful_update_at: "2026-10-09T12:00:00Z",
    }],
    applications: [],
    saved_comparisons: [{ comparison_id: "saved-1", market_names: ["Boston", "New York"], context_summary: "AI / ML", recommendation_state: "near_tie", recommendation_summary: "Near tie.", winner_region_ids: ["greater_nyc"], generated_at: "2026-10-08T12:00:00Z", saved_at: "2026-10-08T12:00:00Z" }],
    saved_items: [{ saved_artifact_id: "saved-market", artifact_type: "region", artifact_ref: "greater_boston", label: "Boston", notes: null, region_id: "greater_boston", public_slug: "boston", display_name: "Greater Boston", created_at: "2026-10-08T12:00:00Z" }],
    history: [{ history_id: "history-1", kind: "option_selected", title: "Prioritized Greater Boston", detail: "Prioritize Boston", occurred_at: "2026-10-09T12:00:00Z", decision_id: "decision-boston", application_id: null }],
    generated_at: "2026-10-09T12:00:00Z",
  };
}

const decision = {
  decision_id: "decision-boston", decision_type: "location_choice", status: "decided", title: "Prioritize Greater Boston", description: null, decision_date: "2026-10-09T12:00:00Z", target_date: null, planned_review_at: null, time_horizon: null, priorities: [], constraints: [], selected_option_id: "option-boston", career_identity_id: null, current_context_snapshot_id: null, current_recommendation_id: null, current_version: 1, context: null,
  options: [{ option_id: "option-boston", decision_id: "decision-boston", title: "Greater Boston", description: null, scenario: { region_id: "greater_boston" }, status: "selected", position: 0, created_at: "", updated_at: "" }], recommendation: null, explore_comparison_provenance: null,
  action_plan: { action_plan_id: "plan-1", decision_id: "decision-boston", selected_option_id: "option-boston", title: "Plan", status: "active", plan: {}, actions: [{ action_id: "action-1", action_plan_id: "plan-1", decision_id: "decision-boston", option_id: "option-boston", action_type: "research", status: "open", title: "Review Boston AI Product openings", description: null, due_at: null, priority: 1, position: 0, completed_at: null, metadata: {}, created_at: "", updated_at: "" }], created_at: "", updated_at: "" },
  applications: [], outcomes: [], created_at: "", updated_at: "",
} as CareerDecision;

const match = {
  opportunity: { opportunity_id: "opportunity-1", company_id: "acme", company_name: "Acme AI", original_title: "Product Intern", normalized_title: "AI Product Intern", role_family: "product_management", seniority_level: "entry_level", market_id: "greater_boston", market_public_slug: "boston", original_market_id: null, market_label: "Greater Boston", location_text: "Boston", location_resolution_status: "resolved", location_resolution_source: "canonical", work_arrangement: "hybrid", compensation_min: null, compensation_max: null, compensation_currency: null, compensation_interval: "unknown", employment_type: "internship", opportunity_type: "internship", posting_date: null, closing_date: null, application_url: "https://jobs.example/apply", source_url: "https://jobs.example/job", description_text: null, skills: [], requirements: [], status: "active", freshness_state: "fresh", freshness_age_hours: 2, first_observed_at: null, last_observed_at: null, last_collected_at: null, canonical_updated_at: "2026-10-09T12:00:00Z", normalization_confidence: "high", identity_confidence: "high", ranking_eligible: true, ranking_ineligible_reasons: [], coverage_status: "production_ready", coverage_limitations: [], provenance: {}, warnings: [] },
  match_score: 0.8, strategic_relevance: "direct_fit", contributing_factors: ["role fit"], warnings: [], limitations: [], ranking_eligible: true,
} as CurrentOpportunityMatchPayload;

describe("Layer 43 My Search", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.workspace.mockResolvedValue(envelope(workspace()));
    mocks.decision.mockResolvedValue(envelope({ decision }));
    mocks.journal.mockResolvedValue(envelope({ journal: [] }));
    mocks.matches.mockResolvedValue(envelope({ matches: [match] }));
    mocks.updateAction.mockResolvedValue(envelope({ action: decision.action_plan!.actions[0] }));
    mocks.track.mockResolvedValue(envelope({ application: workspace().active_pursuits[0].applications[0], created: true, external_application_url: "https://jobs.example/apply" }));
    mocks.application.mockResolvedValue(envelope({ application: decision.applications[0] }));
    mocks.transition.mockResolvedValue(envelope({ application: decision.applications[0] }));
    mocks.action.mockResolvedValue(envelope({ action: decision.action_plan!.actions[0] }));
    mocks.actionPlan.mockResolvedValue(envelope({ action_plan: decision.action_plan }));
    mocks.updateDecision.mockResolvedValue(envelope({ decision: { ...decision, status: "completed" } }));
  });
  afterEach(cleanup);

  test("puts active priority and next action ahead of saved research and advances durably", async () => {
    mocks.workspace.mockResolvedValueOnce(envelope(workspace())).mockResolvedValue(envelope(workspace("Pick 10 target employers")));
    render(<MySearchPage auth={auth} onNavigate={vi.fn()} />);
    expect(await screen.findByRole("heading", { name: "Active priorities" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Greater Boston" })).toBeInTheDocument();
    expect(screen.getByText("Review Boston AI Product openings")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Saved for later" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox", { name: /Review Boston AI Product openings/i }));
    await waitFor(() => expect(mocks.updateAction).toHaveBeenCalledWith("action-1", { status: "completed" }, expect.anything()));
    expect(await screen.findByText("Pick 10 target employers")).toBeInTheDocument();
  });

  test("keeps Apply and track pre-submission and external navigation non-mutating", async () => {
    render(<MySearchPage auth={auth} onNavigate={vi.fn()} pursuitId="decision-boston" />);
    expect(await screen.findByRole("heading", { name: "Current opportunities" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Apply and track" }));
    await waitFor(() => expect(mocks.track).toHaveBeenCalledWith(expect.objectContaining({ initial_status: "preparing" }), expect.anything()));
    expect(mocks.transition).not.toHaveBeenCalled();
    const link = screen.getByRole("link", { name: /Open application site/i });
    expect(link).toHaveAttribute("target", "_blank");
    fireEvent.click(link);
    expect(mocks.transition).not.toHaveBeenCalled();
  });

  test("supports manual application input and only valid next statuses", async () => {
    render(<MySearchPage auth={auth} onNavigate={vi.fn()} pursuitId="decision-boston" />);
    fireEvent.click(await screen.findByRole("button", { name: "Add application" }));
    fireEvent.change(screen.getByLabelText("Company"), { target: { value: "Manual Labs" } });
    fireEvent.change(screen.getByLabelText("Role"), { target: { value: "APM Intern" } });
    fireEvent.click(screen.getByRole("button", { name: "Track application" }));
    await waitFor(() => expect(mocks.application).toHaveBeenCalledWith(expect.objectContaining({ status: "preparing", metadata: expect.objectContaining({ company_name: "Manual Labs" }) }), expect.anything()));

    const transition = screen.getByLabelText("Update Acme AI application status");
    expect(transition).toHaveTextContent("Applied");
    expect(transition).toHaveTextContent("Withdrawn");
    expect(transition).not.toHaveTextContent("Offer");
  });

  test("renders the recommendation and user choice separately", async () => {
    render(<MySearchPage auth={auth} onNavigate={vi.fn()} pursuitId="decision-boston" />);
    expect(await screen.findByText("Current priority")).toBeInTheDocument();
    expect(screen.getByText("Greater Boston", { selector: "dd" })).toBeInTheDocument();
    expect(screen.getByText("Greater New York", { selector: "dd" })).toBeInTheDocument();
    expect(screen.getByText(/not an error/i)).toBeInTheDocument();
  });

  test("describes a later reselection as current truth while retaining the original choice", async () => {
    const reselected = workspace();
    const pursuit = reselected.active_pursuits[0];
    pursuit.selected_priority = { option_id: "option-nyc", title: "Greater New York", region_id: "greater_nyc", public_slug: "new-york" };
    pursuit.source_comparison!.current_user_choice = "Greater New York";
    pursuit.source_comparison!.current_choice_matches_recommendation = true;
    mocks.workspace.mockResolvedValue(envelope(reselected));

    render(<MySearchPage auth={auth} onNavigate={vi.fn()} pursuitId="decision-boston" />);
    expect(await screen.findByText("Original priority")).toBeInTheDocument();
    expect(screen.getByText("Greater Boston", { selector: "dd" })).toBeInTheDocument();
    expect(screen.getByText(/current priority now matches/i)).toBeInTheDocument();
    expect(screen.getByText(/originally prioritized Greater Boston/i)).toBeInTheDocument();
  });
});
