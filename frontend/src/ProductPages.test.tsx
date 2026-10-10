// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { MySearchPage, ProfileSummaryPage } from "./ProductPages";
import type { FrontendAuthContextValue } from "./auth";
import type { ApiEnvelope, CareerIdentity, MySearchWorkspace } from "./types";

const mocks = vi.hoisted(() => ({ getIdentity: vi.fn(), initialize: vi.fn(), createFact: vi.fn(), updateFact: vi.fn(), deleteFact: vi.fn(), privacy: vi.fn(), workspace: vi.fn() }));
vi.mock("./api", async (importOriginal) => ({
  ...await importOriginal<typeof import("./api")>(),
  getCareerIdentity: mocks.getIdentity,
  initializeCareerIdentity: mocks.initialize,
  createCareerIdentityFact: mocks.createFact,
  updateCareerIdentityFact: mocks.updateFact,
  deleteCareerIdentityFact: mocks.deleteFact,
  updateCareerIdentityPrivacy: mocks.privacy,
  getMySearchWorkspace: mocks.workspace,
}));

function envelope<T>(data: T): ApiEnvelope<T> { return { status: "success", data, metadata: { state: "fresh" }, error: null }; }
function identity(): CareerIdentity {
  return {
    career_identity_id: "raw-id-not-default", user_id: "user", current_version: 2, completeness_state: "minimal", sufficiency_state: "sufficient",
    privacy: { ingestion_consent_granted: true, inference_consent_granted: true, downstream_personalization_consent_granted: true, retain_import_metadata: true, privacy_visibility: "private" }, completeness: null,
    facts: {
      education: [], experience: [], skill: [{ career_identity_fact_id: "fact-skill", fact_type: "skill", normalized_key: "python", state: "explicit", payload: { name: "Python" }, provenance: {}, source_import_id: null, source_label: null, confirmed_at: null, created_at: "", updated_at: "" }], project: [], credential: [],
      career_goal: [{ career_identity_fact_id: "fact-goal", fact_type: "career_goal", normalized_key: "ai-product", state: "explicit", payload: { description: "AI product management" }, provenance: {}, source_import_id: null, source_label: null, confirmed_at: null, created_at: "", updated_at: "" }],
      role_preference: [{ career_identity_fact_id: "fact-role", fact_type: "role_preference", normalized_key: "ai-product-intern", state: "explicit", payload: { role_title: "AI product manager", employment_type: "internship", seniority: "entry_level" }, provenance: {}, source_import_id: null, source_label: null, confirmed_at: null, created_at: "", updated_at: "" }],
      industry_preference: [], geographic_constraint: [], compensation_constraint: [], timing_preference: [],
      work_arrangement_preference: [{ career_identity_fact_id: "fact-work", fact_type: "work_arrangement_preference", normalized_key: "hybrid", state: "explicit", payload: { arrangement: "hybrid" }, provenance: {}, source_import_id: null, source_label: null, confirmed_at: null, created_at: "", updated_at: "" }],
    }, created_at: "", updated_at: "",
  };
}

function searchWorkspace(): MySearchWorkspace {
  return {
    active_pursuits: [], applications: [], saved_comparisons: [],
    saved_items: [{ saved_artifact_id: "saved-1", artifact_type: "region", artifact_ref: "greater_boston", label: "Greater Boston", notes: null, region_id: "greater_boston", public_slug: "boston", display_name: "Greater Boston", created_at: "2026-10-09T12:00:00Z" }],
    history: [], generated_at: "2026-10-09T12:00:00Z",
  };
}

const auth: FrontendAuthContextValue = { isConfigured: true, isAuthenticated: true, isLoading: false, error: null, user: { sub: "user" }, login: vi.fn(), logout: vi.fn(), getAccessTokenSilently: vi.fn(async () => "token") };

describe("Layer 42A Profile and My Search", () => {
  let currentIdentity: CareerIdentity;
  beforeEach(() => {
    currentIdentity = identity();
    mocks.getIdentity.mockImplementation(async () => envelope(currentIdentity));
    mocks.updateFact.mockImplementation(async (factId: string, body: { payload: Record<string, unknown> }) => {
      const next = structuredClone(currentIdentity);
      for (const factGroup of Object.values(next.facts)) {
        const fact = factGroup.find((item) => item.career_identity_fact_id === factId);
        if (fact) fact.payload = body.payload;
      }
      next.current_version += 1;
      currentIdentity = next;
      return envelope(next);
    });
    mocks.deleteFact.mockResolvedValue(envelope({ deleted_career_identity_facts: 1 }));
    mocks.privacy.mockImplementation(async (body: { downstream_personalization_consent_granted?: boolean }) => {
      const next = structuredClone(currentIdentity);
      next.privacy.downstream_personalization_consent_granted = Boolean(body.downstream_personalization_consent_granted);
      next.current_version += 1;
      currentIdentity = next;
      return envelope(next);
    });
    mocks.workspace.mockResolvedValue(envelope(searchWorkspace()));
  });
  afterEach(() => { cleanup(); vi.clearAllMocks(); });

  test("presents Career Identity as a concise user-facing summary without dominant internals", async () => {
    render(<ProfileSummaryPage auth={auth} onNavigate={vi.fn()} />);
    expect(await screen.findByRole("heading", { name: "Profile" })).toBeInTheDocument();
    expect(screen.getByText(/seeking AI product manager/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Roles & goals" })).toBeInTheDocument();
    expect(screen.queryByText("raw-id-not-default")).not.toBeInTheDocument();
    expect(screen.getByText("Python")).toBeInTheDocument();
  });

  test("keeps My Search useful with canonical saved state and a clear empty decision state", async () => {
    const navigate = vi.fn();
    render(<MySearchPage auth={auth} onNavigate={navigate} />);
    expect(await screen.findByRole("heading", { name: "My Search" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Greater Boston/i }));
    expect(navigate).toHaveBeenCalledWith(expect.stringContaining("focus=boston"));
    expect(screen.getByText(/No active priorities/i)).toBeInTheDocument();
  });

  test("keeps saved comparison history distinct from an active prioritized Decision", async () => {
    const workspace = searchWorkspace();
    workspace.saved_comparisons = [{ comparison_id: "cmp-42", market_names: ["Greater Boston", "Greater New York"], context_summary: "AI / ML", recommendation_state: "near_tie", recommendation_summary: "Effectively tied.", winner_region_ids: ["greater_boston", "greater_nyc"], generated_at: "2026-10-09T12:00:00Z", saved_at: "2026-10-09T12:01:00Z" }];
    workspace.active_pursuits = [{ decision_id: "decision-42", decision_type: "location_choice", status: "decided", title: "Prioritize Greater Boston", selected_priority: { option_id: "option-boston", title: "Greater Boston", region_id: "greater_boston", public_slug: "boston" }, alternatives: [{ option_id: "option-nyc", title: "Greater New York", region_id: "greater_nyc", public_slug: "new-york" }], target_context: "AI Product · Internship", prioritized_at: "2026-10-09T12:00:00Z", next_action: null, open_action_count: 0, completed_action_count: 0, applications: [], active_application_count: 0, applications_needing_attention: 0, source_comparison: { comparison_id: "cmp-42", compared_markets: ["Greater Boston", "Greater New York"], system_recommendation: ["Greater New York"], original_user_choice: "Greater Boston", original_choice_matches_recommendation: false, current_user_choice: "Greater Boston", current_choice_matches_recommendation: false, recommendation_state: "near_tie", recommendation_summary: "Effectively tied.", generated_at: "2026-10-09T12:00:00Z" }, current_opportunities: { market_id: "greater_boston", coverage_status: "unsupported", coverage_rationale: "No coverage.", coverage_limitations: [], observed_active_count: 0, ranking_eligible_count: 0, fresh_count: 0, latest_observed_at: null, top_opportunities: [] }, latest_meaningful_update_at: "2026-10-09T12:00:00Z" }];
    mocks.workspace.mockResolvedValue(envelope(workspace));
    const navigate = vi.fn();
    render(<MySearchPage auth={auth} onNavigate={navigate} />);
    fireEvent.click(await screen.findByRole("button", { name: /Greater Boston vs Greater New York/i }));
    expect(navigate).toHaveBeenCalledWith("/markets/comparisons/cmp-42");
    fireEvent.click(screen.getByRole("button", { name: "Open pursuit" }));
    expect(navigate).toHaveBeenCalledWith("/markets/my-search/pursuits/decision-42");
  });

  test("lightweight essentials editor populates and replaces Layer 35 facts", async () => {
    render(<ProfileSummaryPage auth={auth} onNavigate={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Edit search essentials" }));
    expect(screen.getByLabelText("Target role or goal")).toHaveValue("AI product manager");
    fireEvent.change(screen.getByLabelText("Target role or goal"), { target: { value: "data science" } });
    fireEvent.click(screen.getByRole("button", { name: "Save to Profile" }));
    await waitFor(() => expect(mocks.updateFact).toHaveBeenCalledWith("fact-goal", expect.objectContaining({ payload: { goal_type: "near_term_objective", description: "data science" } }), expect.anything()));
    expect(mocks.createFact).not.toHaveBeenCalled();
    expect(await screen.findByText(/seeking Data Science/i)).toBeInTheDocument();
  });

  test("revokes downstream personalization consent without deleting facts", async () => {
    render(<ProfileSummaryPage auth={auth} onNavigate={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Edit search essentials" }));
    fireEvent.click(screen.getByLabelText("Use these facts to personalize Explore"));
    fireEvent.click(screen.getByRole("button", { name: "Save to Profile" }));
    await waitFor(() => expect(mocks.privacy).toHaveBeenCalledWith(expect.objectContaining({ downstream_personalization_consent_granted: false }), expect.anything()));
    expect(await screen.findByText("Personalization consent is off")).toBeInTheDocument();
    expect(currentIdentity.facts.role_preference).toHaveLength(1);
  });
});
