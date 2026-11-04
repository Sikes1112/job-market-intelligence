// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import App from "./App";
import { ApiError } from "./api";
import ExploreComparisonPage from "./ExploreComparisonPage";
import type { FrontendAuthContextValue } from "./auth";
import type { ApiEnvelope, ExploreComparisonResult, ExploreFitResult, ExplorePrioritization } from "./types";
import type { ExploreUrlState } from "./urlState";

const routedAuth = vi.hoisted(() => ({
  getAccessTokenSilently: vi.fn(async () => "token"),
  login: vi.fn(async () => undefined),
  logout: vi.fn(),
}));

const mocks = vi.hoisted(() => ({
  compare: vi.fn(),
  getSaved: vi.fn(),
  save: vi.fn(),
  prioritize: vi.fn(),
  event: vi.fn(),
  resolve: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => ({
  ...await importOriginal<typeof import("./api")>(),
  compareExploreMarkets: mocks.compare,
  getExploreComparison: mocks.getSaved,
  saveExploreComparison: mocks.save,
  prioritizeExploreComparison: mocks.prioritize,
  recordProductEvent: mocks.event,
  resolveGeography: mocks.resolve,
}));

vi.mock("./auth", async (importOriginal) => ({
  ...await importOriginal<typeof import("./auth")>(),
  useFrontendAuth: () => ({
    isConfigured: true,
    isAuthenticated: true,
    isLoading: false,
    error: null,
    user: { sub: "user" },
    login: routedAuth.login,
    logout: routedAuth.logout,
    getAccessTokenSilently: routedAuth.getAccessTokenSilently,
  }),
}));

function envelope<T>(data: T): ApiEnvelope<T> {
  return { status: "success", data, metadata: { state: "fresh" }, error: null };
}

function fit(id: string, slug: string, name: string, score: number): ExploreFitResult {
  return {
    market_key: slug,
    region: { region_id: id, public_slug: slug, display_name: name, region_type: "metro", state_codes: [], primary_city: name, centroid: null, focus_bounds: null, market_support_status: "supported" },
    state: "confident", fit_score: score, fit_band: "strong_fit", rank: 1, display_order: 1,
    tied_region_ids: [], near_tie_region_ids: [], primary_drivers: [{ code: "employer_strength", label: "Employer strength", contribution: score, evidence: `${name} employer evidence.` }],
    tradeoffs: [`${name} tradeoff.`], confidence: "high", evidence_sufficiency: "comparison_ready", freshness: "current",
    market_coverage: { authority: "layer_34_market_intelligence", summary: `${name} governed coverage.`, evidence_areas_used: ["employers"], evidence_areas_missing: [] },
    opportunity_coverage: { authority: "layer_38_current_opportunities", status: "limited", active_opportunity_count: id === "greater_boston" ? 3 : 0, ranking_eligible_opportunity_count: 1, fresh_opportunity_count: 2, rationale: null, limitations: ["Observed inventory is incomplete."], affects_explore_fit: false },
    material_limitations: [], abstention_reason: null, hard_constraint_reasons: [], contradiction_status: "clear", contradiction_findings: [], contradiction_blocking: false, contradiction_summary: null, evidence_hooks: {},
    versions: { algorithm_version: "explore_fit_v1", market_evidence_authority_version: "layer34", market_evidence_bundle: "sha256:evidence", calibration_version: "bands_v1", context_fingerprint: "context", career_identity_version: 2 },
  };
}

function comparison(): ExploreComparisonResult {
  const boston = fit("greater_boston", "boston", "Greater Boston", 0.8);
  const nyc = fit("greater_nyc", "new-york", "Greater New York", 0.795);
  return {
    comparison_identity: "sha256:comparison",
    compared_markets: [
      { fit: boston, comparison_rank: 1, key_advantages: ["Stronger AI employer concentration."], key_tradeoffs: ["Narrower employer breadth."], confidence_caveat: "High confidence from governed evidence.", missing_evidence: [], company_evidence: [{ company_id: "acme", company_name: "Acme AI", evidence_kind: "current_hiring", active_posting_count: 2, confidence: "high" }] },
      { fit: nyc, comparison_rank: 2, key_advantages: ["Broader employer breadth."], key_tradeoffs: ["Slightly weaker AI concentration."], confidence_caveat: "High confidence from governed evidence.", missing_evidence: [], company_evidence: [{ company_id: "presence", company_name: "Presence Co", evidence_kind: "presence", active_posting_count: null, confidence: "medium" }] },
    ],
    recommendation_state: "near_tie", recommendation_summary: "Boston and New York are effectively tied. Current jobs did not affect this result.", winner_region_ids: ["greater_boston", "greater_nyc"], tied_region_ids: [], near_tie_region_ids: ["greater_boston", "greater_nyc"], abstained: false, abstention_reason: null,
    differentiating_factors: [{ code: "ai_strength", label: "AI employer strength", summary: "Greater Boston has the strongest governed AI employer signal in this set.", region_ids: ["greater_boston"], evidence: [] }],
    shared_strengths: [{ code: "employers", label: "Employers", summary: "Both markets have strong employer presence.", region_ids: ["greater_boston", "greater_nyc"], evidence: [] }], shared_weaknesses: [], confidence: "high", contradiction_state: "clear", contradiction_findings: [], missing_evidence: {},
    market_coverage: { greater_boston: boston.market_coverage, greater_nyc: nyc.market_coverage }, opportunity_coverage: { greater_boston: boston.opportunity_coverage, greater_nyc: nyc.opportunity_coverage },
    context_fingerprint: "explore_context_v2:test", effective_context: { goal: "ai_ml", role_families: [], industries: [], opportunity_types: [], career_stage: null, work_arrangements: [], preferred_region_ids: [], included_region_ids: [], excluded_region_ids: [], timing: [] },
    algorithm_version: "explore_fit_v1", evidence_authority_version: "layer34", evidence_bundle: "sha256:evidence", calibration_version: "bands_v1", generated_at: "2026-10-09T12:00:00Z", authority: "explore_fit_n_way_comparison", limitations: ["Jobs do not affect Fit."],
  };
}

function prioritization(region = "greater_boston"): ExplorePrioritization {
  const title = region === "greater_boston" ? "Prioritize Greater Boston" : "Prioritize Greater New York";
  const timestamp = "2026-10-09T12:00:00Z";
  return {
    decision_id: "decision-pending", comparison_id: "cmp-1", selected_region_id: region,
    system_recommended_region_ids: ["greater_boston"], choice_matches_recommendation: region === "greater_boston", created: true,
    decision: {
      decision_id: "decision-pending", decision_type: "location_choice", status: "decided", title,
      description: null, decision_date: timestamp, target_date: null, planned_review_at: null,
      time_horizon: null, priorities: [], constraints: [], selected_option_id: "option-selected",
      career_identity_id: null, current_context_snapshot_id: null, current_recommendation_id: null,
      current_version: 1, context: null,
      options: [{option_id: "option-selected", decision_id: "decision-pending", title: title.replace("Prioritize ", ""),
        description: null, scenario: {region_id:region}, status: "selected", position: 0, created_at:timestamp, updated_at:timestamp}],
      recommendation: null, action_plan: null,
      applications: [], outcomes: [], created_at: timestamp, updated_at: timestamp,
    },
  };
}

const auth: FrontendAuthContextValue = { isConfigured: true, isAuthenticated: true, isLoading: false, error: null, user: { sub: "user" }, login: vi.fn(), logout: vi.fn(), getAccessTokenSilently: vi.fn(async () => "token") };
const state: ExploreUrlState = { view: "list", selected: ["boston", "new-york"], goal: "ai_ml", opportunityTypes: [], workArrangements: [], geographicScope: [], industries: [] };

describe("Layer 42B Explore comparison", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.resolve.mockImplementation(async (token: string) => {
      const identities: Record<string, { region_id: string; public_slug: string }> = {
        boston: { region_id: "greater_boston", public_slug: "boston" },
        greater_boston: { region_id: "greater_boston", public_slug: "boston" },
        nyc: { region_id: "greater_nyc", public_slug: "new-york" },
        greater_nyc: { region_id: "greater_nyc", public_slug: "new-york" },
        "new-york": { region_id: "greater_nyc", public_slug: "new-york" },
        greater_sf: { region_id: "sf_bay_area", public_slug: "san-francisco-bay-area" },
        "san-francisco-bay-area": { region_id: "sf_bay_area", public_slug: "san-francisco-bay-area" },
      };
      const identity = identities[token];
      if (!identity) throw new Error("unknown geography");
      return envelope(identity);
    });
    mocks.compare.mockResolvedValue(envelope(comparison()));
    mocks.event.mockResolvedValue(envelope({ event: {} }));
    mocks.save.mockResolvedValue(envelope({ comparison: { comparison_id: "cmp-1", result: comparison() } }));
    mocks.prioritize.mockResolvedValue(envelope({ prioritization: prioritization("greater_nyc") }));
    mocks.getSaved.mockResolvedValue(envelope({ comparison: { comparison_id: "cmp-1", result: comparison() } }));
  });
  afterEach(() => {
    cleanup();
    window.history.replaceState(null, "", "/");
  });

  test("routes a raw NYC alias URL through App before generating one canonical comparison", async () => {
    window.history.replaceState(null, "", "/markets/compare?selected=nyc,boston");
    expect(`${window.location.pathname}${window.location.search}`).toBe(
      "/markets/compare?selected=nyc,boston",
    );

    render(<App />);

    expect(await screen.findByRole("heading", { name: /effectively tied/i })).toBeInTheDocument();
    await waitFor(() => expect(new URLSearchParams(window.location.search).get("selected")).toBe(
      "new-york,boston",
    ));

    expect(mocks.resolve).toHaveBeenCalledWith("nyc");
    expect(mocks.resolve).toHaveBeenCalledWith("boston");
    expect(mocks.compare).toHaveBeenCalledTimes(1);
    expect(mocks.compare).toHaveBeenCalledWith(
      ["new-york", "boston"],
      expect.anything(),
      expect.anything(),
    );

    const marketHeadings = screen.getAllByRole("heading", { level: 3 });
    expect(marketHeadings).toHaveLength(2);
    expect(marketHeadings.map((heading) => heading.textContent)).toEqual([
      "Greater Boston",
      "Greater New York",
    ]);
    expect(screen.getByText("2 markets")).toBeInTheDocument();
  });

  test("leads with near-tie language and provides semantic cards plus a compact table", async () => {
    render(<ExploreComparisonPage auth={auth} onNavigate={vi.fn()} state={state} />);
    expect(await screen.findByRole("heading", { name: /effectively tied/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Biggest differentiators" })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: "Greater Boston" }).length).toBeGreaterThan(0);
    expect(screen.getByRole("table")).toHaveAccessibleName(/Fit, confidence, tradeoffs/i);
    expect(screen.getByText(/presence evidence, not active hiring/i)).toBeInTheDocument();
    expect(screen.getAllByText(/supporting evidence only/i)).toHaveLength(4);
    await waitFor(() => expect(mocks.event).toHaveBeenCalledWith(expect.objectContaining({ event_type: "comparison_recommendation_viewed" }), expect.anything()));
  });

  test("saves without prioritizing, then explicitly confirms a user override", async () => {
    const clear = comparison();
    clear.recommendation_state = "clear_recommendation";
    clear.winner_region_ids = ["greater_boston"];
    clear.near_tie_region_ids = [];
    clear.recommendation_summary = "Greater Boston is the best-supported choice.";
    mocks.compare.mockResolvedValue(envelope(clear));
    render(<ExploreComparisonPage auth={auth} onNavigate={vi.fn()} state={state} />);
    fireEvent.click(await screen.findByRole("button", { name: "Save comparison" }));
    await waitFor(() => expect(mocks.save).toHaveBeenCalledTimes(1));
    expect(mocks.prioritize).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Saved ✓" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Prioritize" }));
    const select = screen.getByLabelText("Market");
    expect(select).toHaveFocus();
    fireEvent.change(select, { target: { value: "greater_nyc" } });
    expect(screen.getByText(/differs from the system recommendation/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Prioritize Greater New York" }));
    await waitFor(() => expect(mocks.prioritize).toHaveBeenCalledWith(expect.objectContaining({ selected_market_ref: "greater_nyc" }), expect.anything()));
    expect(await screen.findByRole("heading", { name: "Added to My Search" })).toBeInTheDocument();
  });

  test("shows one visible quota alert, preserves comparison and supports retry and navigation", async () => {
    const quota = new ApiError("Guest demo saved_comparisons limit reached", {
      statusCode: 429,
      envelope: { status: "error", data: null, metadata: {state: "fresh"}, error: { type: "guest_quota_exceeded", message: "Guest demo saved_comparisons limit reached" } },
    });
    mocks.save.mockRejectedValue(quota);
    const navigate = vi.fn();
    const { container } = render(<ExploreComparisonPage auth={auth} onNavigate={navigate} state={state} />);
    const save = await screen.findByRole("button", { name: "Save comparison" });
    fireEvent.click(save);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/guest demo’s saved-comparison limit has been reached/);
    expect(alert).toHaveTextContent(/existing saved comparisons are still available/);
    // Visibility in jsdom alone would miss the original clipped sr-only region.
    expect(alert).toHaveClass("error-copy");
    expect(alert.closest(".sr-only, [hidden], [aria-hidden='true']")).toBeNull();
    expect(alert.closest(".comparison-hero")).not.toBeNull();
    expect(container.querySelector("[aria-live='polite']")).not.toHaveTextContent(/Could not save/);
    expect(screen.queryByRole("button", { name: "Saved ✓" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 3 }).map(el => el.textContent)).toEqual(["Greater Boston", "Greater New York"]);
    fireEvent.click(save);
    await waitFor(() => expect(mocks.save).toHaveBeenCalledTimes(2));
    expect(await screen.findByRole("alert")).toHaveTextContent(/saved-comparison limit/);
    expect(mocks.save).toHaveBeenLastCalledWith({market_refs: state.selected, session_overrides: expect.anything(), comparison_identity: comparison().comparison_identity}, expect.anything());
    expect(mocks.prioritize).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Prioritize" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/saved-comparison limit/);
    fireEvent.click(screen.getByRole("button", { name: /Back to Explore/ }));
    expect(navigate).toHaveBeenCalledWith(expect.stringContaining("/markets"));
  });

  test("keeps other 429 errors accurate and clears save errors when comparison context changes", async () => {
    mocks.save.mockRejectedValue(new ApiError("Too many requests; try again later", {statusCode: 429}));
    const navigate = vi.fn();
    const {rerender} = render(<ExploreComparisonPage auth={auth} onNavigate={navigate} state={state} />);
    fireEvent.click(await screen.findByRole("button", {name: "Save comparison"}));
    expect(await screen.findByRole("alert")).toHaveTextContent("Too many requests; try again later");
    expect(screen.getByRole("alert")).not.toHaveTextContent("saved-comparison limit");
    rerender(<ExploreComparisonPage auth={auth} onNavigate={navigate} state={{...state, selected: ["new-york", "boston"]}} />);
    await screen.findByRole("button", {name: "Save comparison"});
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  test("clears a previous save failure after successful retry and opens the saved snapshot", async () => {
    mocks.save.mockRejectedValueOnce(new Error("Temporary failure"));
    const navigate = vi.fn();
    render(<ExploreComparisonPage auth={auth} onNavigate={navigate} state={state} />);
    fireEvent.click(await screen.findByRole("button", {name: "Save comparison"}));
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not save comparison: Temporary failure");
    fireEvent.click(screen.getByRole("button", {name: "Save comparison"}));
    expect(await screen.findByRole("button", {name: "Saved ✓"})).toBeDisabled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText("Comparison saved. It is now available in My Search.")).toHaveAttribute("aria-live", "polite");
    fireEvent.click(screen.getByRole("button", {name: "Open saved snapshot"}));
    expect(navigate).toHaveBeenCalledWith("/markets/comparisons/cmp-1");
  });

  test("reopens an immutable saved snapshot and offers an explicit current rerun", async () => {
    const navigate = vi.fn();
    render(<ExploreComparisonPage auth={auth} onNavigate={navigate} savedComparisonId="cmp-1" state={{ ...state, selected: [] }} />);
    expect(await screen.findByText("Historical saved snapshot")).toBeInTheDocument();
    expect(mocks.getSaved).toHaveBeenCalledWith("cmp-1", expect.anything());
    expect(mocks.compare).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /Compare these markets again/i }));
    expect(navigate).toHaveBeenCalledWith(expect.stringContaining("/markets/compare?selected=boston%2Cnew-york"));
  });

  test("fails malformed direct comparison state honestly", async () => {
    render(<ExploreComparisonPage auth={auth} onNavigate={vi.fn()} state={{ ...state, selected: ["boston"] }} />);
    expect(await screen.findByRole("heading", { name: "Comparison unavailable" })).toBeInTheDocument();
    expect(screen.getByText(/Choose 2–4 unique markets/i)).toBeInTheDocument();
    expect(mocks.compare).not.toHaveBeenCalled();
  });

  test("resolves registry aliases before comparing and replaces the URL with public slugs", async () => {
    const navigate = vi.fn();
    const { rerender } = render(<ExploreComparisonPage
      auth={auth}
      onNavigate={navigate}
      state={{ ...state, selected: ["nyc", "boston"] }}
    />);

    await waitFor(() => expect(navigate).toHaveBeenCalledWith(
      "/markets/compare?selected=new-york%2Cboston&role=ai_ml",
      { replace: true },
    ));
    expect(mocks.compare).not.toHaveBeenCalled();
    rerender(<ExploreComparisonPage
      auth={auth}
      onNavigate={navigate}
      state={{ ...state, selected: ["new-york", "boston"] }}
    />);
    expect(await screen.findByRole("heading", { name: /effectively tied/i })).toBeInTheDocument();
    expect(mocks.compare).toHaveBeenCalledWith(
      ["new-york", "boston"],
      expect.anything(),
      expect.anything(),
    );
    expect(mocks.compare).toHaveBeenCalledTimes(1);
  });

  test.each([
    [["greater_nyc", "greater_boston"], ["new-york", "boston"]],
    [["new-york", "boston"], ["new-york", "boston"]],
    [["greater_sf", "boston"], ["san-francisco-bay-area", "boston"]],
    [["nyc", "new-york", "greater_nyc", "boston"], ["new-york", "boston"]],
    [["bad", "nyc", "boston"], ["new-york", "boston"]],
  ])("canonicalizes %j without dropping valid markets", async (selected, canonical) => {
    const navigate = vi.fn();
    const { rerender } = render(<ExploreComparisonPage auth={auth} onNavigate={navigate} state={{ ...state, selected }} />);

    if (selected.join(",") !== canonical.join(",")) {
      await waitFor(() => expect(navigate).toHaveBeenCalledWith(
        expect.stringContaining(`selected=${canonical.join("%2C")}`),
        { replace: true },
      ));
      rerender(<ExploreComparisonPage auth={auth} onNavigate={navigate} state={{ ...state, selected: canonical }} />);
    }

    expect(await screen.findByRole("heading", { name: /effectively tied/i })).toBeInTheDocument();
    expect(mocks.compare).toHaveBeenCalledWith(canonical, expect.anything(), expect.anything());
  });

  test("describes an abstention choice without inventing a recommendation and restores focus", async () => {
    const abstained = comparison();
    abstained.recommendation_state = "insufficient_evidence";
    abstained.winner_region_ids = [];
    abstained.near_tie_region_ids = [];
    abstained.abstained = true;
    abstained.abstention_reason = "The evidence is insufficient.";
    mocks.compare.mockResolvedValue(envelope(abstained));
    render(<ExploreComparisonPage auth={auth} onNavigate={vi.fn()} state={state} />);

    const trigger = await screen.findByRole("button", { name: "Prioritize" });
    fireEvent.click(trigger);
    fireEvent.change(screen.getByLabelText("Market"), { target: { value: "greater_boston" } });
    expect(screen.getByText(/did not recommend a single market/i)).toBeInTheDocument();
    expect(screen.queryByText(/differs from the system recommendation/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(trigger).toHaveFocus());
  });
  test("Escape mirrors Cancel and Tab stays inside the labeled confirmation", async () => {
    render(<ExploreComparisonPage auth={auth} onNavigate={vi.fn()} state={state} />);
    const trigger = await screen.findByRole("button", {name:"Prioritize"});
    fireEvent.click(trigger);
    const dialog = screen.getByRole("dialog",{name:"Choose a market to prioritize"});
    const market = screen.getByLabelText("Market");
    expect(market).toHaveFocus();
    fireEvent.keyDown(market,{key:"Tab",shiftKey:true});
    expect(screen.getByRole("button",{name:"Cancel"})).toHaveFocus();
    fireEvent.keyDown(screen.getByRole("button",{name:"Cancel"}),{key:"Tab"});
    expect(market).toHaveFocus();
    fireEvent.keyDown(dialog,{key:"Escape"});
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await waitFor(()=>expect(trigger).toHaveFocus());
    expect(mocks.prioritize).not.toHaveBeenCalled();
  });
  test("Escape dismisses a pending confirmation without cancelling its result", async () => {
    let finish!: (value: unknown) => void;
    mocks.prioritize.mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve;}));
    const navigate = vi.fn();
    render(<ExploreComparisonPage auth={auth} onNavigate={navigate} state={state} />);
    const trigger = await screen.findByRole("button",{name:"Prioritize"});
    fireEvent.click(trigger);
    fireEvent.change(screen.getByLabelText("Market"),{target:{value:"greater_boston"}});
    fireEvent.click(screen.getByRole("button",{name:"Prioritize Greater Boston"}));
    expect(mocks.prioritize).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(document.body,{key:"Escape"});
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await waitFor(()=>expect(trigger).toHaveFocus());
    finish(envelope({ prioritization: prioritization() }));
    expect(await screen.findByRole("heading",{name:"Added to My Search"})).toBeInTheDocument();
    expect(screen.getByText("Prioritize Greater Boston is now active in My Search.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText(/Could not prioritize market|TypeError/)).not.toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(mocks.prioritize).toHaveBeenCalledTimes(1);
    expect(mocks.prioritize.mock.calls[0][0]).toMatchObject({selected_market_ref:"greater_boston"});
    fireEvent.click(screen.getByRole("button", {name:"Open Decision"}));
    expect(navigate).toHaveBeenLastCalledWith("/markets/decisions?decision=decision-pending");
    fireEvent.click(screen.getByRole("button", {name:"Open My Search"}));
    expect(navigate).toHaveBeenLastCalledWith("/markets/my-search");
  });

  test("pending dismissal preserves failure feedback and permits a deliberate retry", async () => {
    let fail!: (reason: Error) => void;
    mocks.prioritize.mockImplementationOnce(() => new Promise((_, reject) => { fail = reject; }));
    render(<ExploreComparisonPage auth={auth} onNavigate={vi.fn()} state={state} />);
    const trigger = await screen.findByRole("button", { name: "Prioritize" });
    fireEvent.click(trigger);
    fireEvent.change(screen.getByLabelText("Market"), { target: { value: "greater_boston" } });
    fireEvent.click(screen.getByRole("button", { name: "Prioritize Greater Boston" }));
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(mocks.prioritize).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(trigger).toHaveFocus());
    fail(new Error("Synthetic save failure"));
    expect(await screen.findByText(/Could not prioritize market: Synthetic save failure/)).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    fireEvent.click(trigger);
    expect(screen.getByRole("button", { name: "Prioritize Greater Boston" })).toBeEnabled();
  });

  test.each(["open", "Escape", "Cancel"])("failure remains visible and recoverable after %s", async (dismissal) => {
    let fail!: (error: Error) => void;
    mocks.prioritize.mockImplementationOnce(() => new Promise((_, reject) => { fail = reject; }));
    mocks.prioritize.mockResolvedValueOnce(envelope({prioritization:prioritization()}));
    render(<ExploreComparisonPage auth={auth} onNavigate={vi.fn()} state={state} />);
    const trigger = await screen.findByRole("button", {name:"Prioritize"});
    fireEvent.click(trigger);
    fireEvent.change(screen.getByLabelText("Market"), {target:{value:"greater_boston"}});
    fireEvent.click(screen.getByRole("button", {name:"Prioritize Greater Boston"}));
    if (dismissal === "Escape") fireEvent.keyDown(document.body, {key:"Escape"});
    if (dismissal === "Cancel") fireEvent.click(screen.getByRole("button", {name:"Cancel"}));
    fail(new Error("Synthetic save failure"));
    const alert = await screen.findByRole("alert");
    expect(alert).toBeVisible();
    expect(alert).toHaveTextContent("Could not prioritize market: Synthetic save failure");
    expect(alert).toHaveTextContent(/try again/i);
    expect(alert).not.toHaveClass("sr-only");
    expect(screen.queryByRole("heading", {name:"Added to My Search"})).not.toBeInTheDocument();
    if (dismissal === "open") expect(screen.getByRole("dialog")).toContainElement(alert);
    else {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      await waitFor(() => expect(trigger).toHaveFocus());
      fireEvent.click(trigger);
    }
    expect(screen.getByLabelText("Market")).toHaveValue("greater_boston");
    fireEvent.click(screen.getByRole("button", {name:"Prioritize Greater Boston"}));
    expect(await screen.findByRole("heading", {name:"Added to My Search"})).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText(/Synthetic save failure/)).not.toBeInTheDocument();
    expect(mocks.prioritize).toHaveBeenCalledTimes(2);
  });

  test.each([{}, {prioritization:{decision_id:"pending",created:true}}])("malformed success %j cannot expose a successful destination", async (response) => {
    mocks.prioritize.mockResolvedValueOnce(envelope(response));
    render(<ExploreComparisonPage auth={auth} onNavigate={vi.fn()} state={state} />);
    fireEvent.click(await screen.findByRole("button", {name:"Prioritize"}));
    fireEvent.change(screen.getByLabelText("Market"), {target:{value:"greater_boston"}});
    fireEvent.click(screen.getByRole("button", {name:"Prioritize Greater Boston"}));
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not prioritize market:");
    expect(screen.queryByRole("heading", {name:"Added to My Search"})).not.toBeInTheDocument();
    expect(screen.queryByRole("button", {name:"Open Decision"})).not.toBeInTheDocument();
  });


});

 describe("contextual opportunity role handoff", () => {
  afterEach(cleanup);
  test("uses the saved comparison role, not today's live role", async () => {
    const saved = comparison();
    saved.effective_context.goal = "data_science";
    mocks.getSaved.mockResolvedValue(envelope({comparison: {comparison_id: "saved", result: saved}}));
    mocks.event.mockResolvedValue(envelope({event: {}}));
    const navigate = vi.fn();
    render(<ExploreComparisonPage auth={auth} state={state} savedComparisonId="saved" onNavigate={navigate} />);
    fireEvent.click(await screen.findByRole("button", {name: "View opportunities in Greater Boston"}));
    expect(navigate).toHaveBeenCalledWith(expect.stringMatching(/role=data_ai/));
    expect(navigate.mock.calls[0][0]).toContain("preferred_role=data_science");
  });
  test("unmapped preference requires an explicit actual category without replacement", async () => {
    const saved = comparison(); saved.effective_context.goal = "marine_ecologist";
    mocks.getSaved.mockResolvedValue(envelope({comparison: {comparison_id: "saved", result: saved}}));
    mocks.event.mockResolvedValue(envelope({event: {}}));
    const navigate = vi.fn();
    render(<ExploreComparisonPage auth={auth} state={state} savedComparisonId="saved" onNavigate={navigate} />);
    fireEvent.click(await screen.findByRole("button", {name: "View opportunities in Greater Boston"}));
    expect(navigate).not.toHaveBeenCalled();
    expect(screen.getByText(/marine_ecologist/)).toBeInTheDocument();
    expect(screen.getByRole("button",{name:"Open selected opportunities"})).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Opportunity search category"),{target:{value:"solutions_engineering"}});
    fireEvent.click(screen.getByRole("button",{name:"Open selected opportunities"}));
    expect(navigate.mock.calls[0][0]).toContain("role=solutions_engineering");
    expect(navigate.mock.calls[0][0]).toContain("preferred_role=marine_ecologist");
  });
 });
