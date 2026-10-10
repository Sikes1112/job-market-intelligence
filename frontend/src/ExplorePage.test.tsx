// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import ExplorePage from "./ExplorePage";
import type { FrontendAuthContextValue } from "./auth";
import type { ApiEnvelope, ExploreFitResult, ExploreMarketsResponse } from "./types";
import { parseRoute, type ExploreUrlState } from "./urlState";

const mocks = vi.hoisted(() => ({
  evaluate: vi.fn(),
  getRegion: vi.fn(),
  getOpportunities: vi.fn(),
  save: vi.fn(),
  listSaved: vi.fn(),
  event: vi.fn(),
  resolve: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => ({
  ...await importOriginal<typeof import("./api")>(),
  evaluateExploreMarkets: mocks.evaluate,
  getRegion: mocks.getRegion,
  getCurrentOpportunities: mocks.getOpportunities,
  createSavedMarketArtifact: mocks.save,
  listSavedMarketArtifacts: mocks.listSaved,
  recordProductEvent: mocks.event,
  resolveGeography: mocks.resolve,
}));

function envelope<T>(data: T): ApiEnvelope<T> {
  return { status: "success", data, metadata: { state: "fresh", source_versions: {}, warnings: [] }, error: null };
}

function market(regionId: string, slug: string, name: string, rank: number, state: ExploreFitResult["state"] = "confident"): ExploreFitResult {
  return {
    market_key: slug,
    region: { region_id: regionId, public_slug: slug, display_name: name, region_type: "metro", state_codes: [regionId === "greater_boston" ? "MA" : "NY"], primary_city: name, centroid: null, focus_bounds: null, market_support_status: "supported" },
    state,
    fit_score: state === "confident" ? 0.82 - rank / 100 : null,
    fit_band: state === "confident" ? "strong" : null,
    rank: state === "confident" ? rank : null,
    display_order: rank,
    tied_region_ids: [], near_tie_region_ids: [],
    primary_drivers: [{ label: "Strong early-career access" }],
    tradeoffs: ["Housing costs may be material."], confidence: "high", evidence_sufficiency: "comparison_ready", freshness: "current",
    market_coverage: { authority: "layer_34_market_intelligence", summary: "Grounded market evidence is available.", evidence_areas_used: ["hiring"], evidence_areas_missing: [] },
    opportunity_coverage: { authority: "layer_38_current_opportunities", status: "unsupported", active_opportunity_count: 0, ranking_eligible_opportunity_count: 0, fresh_opportunity_count: 0, rationale: null, limitations: ["No coverage contract."], affects_explore_fit: false },
    material_limitations: [], abstention_reason: null, hard_constraint_reasons: [], contradiction_status: "clear", contradiction_findings: [], contradiction_blocking: false, contradiction_summary: null, evidence_hooks: {}, versions: {},
  };
}

function payload(personalizationState: ExploreMarketsResponse["context"]["personalization_state"] = "personalized"): ExploreMarketsResponse {
  const markets = [
    market("greater_boston", "boston", "Greater Boston", 1),
    market("greater_nyc", "new-york", "Greater New York", 2),
    market("greater_seattle", "seattle", "Greater Seattle", 3),
    market("austin", "austin", "Austin", 4),
    market("chicago", "chicago", "Chicago", 5),
  ];
  return {
    context: {
      career_identity_id: "ci_42", career_identity_version: 3, personalization_consent: personalizationState !== "general_market_intelligence",
      profile_defaults: { goal: "ai_ml", role_families: [], industries: [], opportunity_types: ["internship"], career_stage: "entry_level", work_arrangements: ["hybrid"], preferred_region_ids: [], included_region_ids: [], excluded_region_ids: [], timing: [] },
      session_overrides: { goal: null, role_families: [], industries: [], opportunity_types: [], career_stage: null, work_arrangements: [], preferred_region_ids: [], included_region_ids: [], excluded_region_ids: [], timing: [] },
      effective_context: { goal: "ai_ml", role_families: [], industries: [], opportunity_types: ["internship"], career_stage: "entry_level", work_arrangements: ["hybrid"], preferred_region_ids: [], included_region_ids: [], excluded_region_ids: [], timing: [] },
      context_fingerprint: "test", fingerprint_version: "v2", personalization_state: personalizationState, supported_goal: "ai_ml", goal_mapping_state: "supported", applied_context: ["goal"], unapplied_context: [
        { code: "opportunity_types_market_evidence_unavailable", field: "opportunity_types", source: "effective_context", reason: "This input is preserved as unapplied and does not change Explore Fit." },
        { code: "work_arrangements_market_evidence_unavailable", field: "work_arrangements", source: "effective_context", reason: "This input is preserved as unapplied and does not change Explore Fit." },
        { code: "career_stage_market_evidence_unavailable", field: "career_stage", source: "effective_context", reason: "This input is preserved as unapplied and does not change Explore Fit." },
      ], unsupported_context: [], limitations: [],
    },
    ranking_universe: { kind: "curated", label: "8 supported markets", region_ids: markets.map((item) => item.region.region_id), market_count: 8, nationally_representative: false },
    markets, evaluated_at: "2026-10-08T12:00:00Z", authority: "explore_fit", authority_version: "41B", contradiction_status: "clear", contradiction_findings: [], contradiction_blocking: false, contradiction_summary: null, limitations: [],
  };
}

const auth: FrontendAuthContextValue = {
  isConfigured: true, isAuthenticated: true, isLoading: false, error: null,
  user: { sub: "auth0|42", email: "explorer@example.com" }, login: vi.fn(), logout: vi.fn(), getAccessTokenSilently: vi.fn(async () => "token"),
};

const state: ExploreUrlState = { view: "list", selected: [], opportunityTypes: [], workArrangements: [], geographicScope: [], industries: [] };

describe("Layer 42A Explore experience", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
    mocks.evaluate.mockResolvedValue(envelope(payload()));
    mocks.getRegion.mockResolvedValue(envelope({ region_id: "greater_boston", display_name: "Greater Boston", region_type: "metro", parent_region_id: null, labor_market_group: null, scores: null, top_companies_hiring: [{ company_id: "acme", company_name: "Acme AI", currently_hiring_flag: true, active_posting_count_now: 2, posting_count_30d: 4, posting_count_90d: 7 }] }));
    mocks.getOpportunities.mockResolvedValue(envelope({ opportunities: [] }));
    mocks.event.mockResolvedValue(envelope({ event: {} }));
    mocks.save.mockResolvedValue(envelope({}));
    mocks.listSaved.mockResolvedValue(envelope({ saved_market_artifacts: [] }));
    mocks.resolve.mockRejectedValue(new Error("unknown geography"));
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ type: "FeatureCollection", features: [] }), { status: 200 })));
  });

  afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  test("renders the same Fit universe in the accessible list and map, then opens honest detail", async () => {
    const navigate = vi.fn();
    const { rerender } = render(<ExplorePage auth={auth} onNavigate={navigate} state={state} />);
    expect(await screen.findByRole("heading", { name: "Ranked markets" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Greater Boston: Strong, High confidence/i })).toBeInTheDocument();
    const listButton = screen.getAllByText("Greater Boston").find((element) => element.tagName === "STRONG")?.closest("button");
    expect(listButton).toBeInTheDocument();
    fireEvent.click(listButton!);
    expect(navigate).toHaveBeenCalledWith(expect.stringContaining("focus=boston"), { replace: false });

    rerender(<ExplorePage auth={auth} onNavigate={navigate} state={{ ...state, focus: "boston" }} />);
    expect(await screen.findByRole("dialog", { name: "Greater Boston details" })).toBeInTheDocument();
    expect(screen.getByText(/Current job coverage is unsupported/i)).toBeInTheDocument();
    expect(await screen.findByText("Acme AI")).toBeInTheDocument();
    expect(screen.getByText(/Current opportunity counts do not change market Fit/i)).toBeInTheDocument();
    await waitFor(() => expect(mocks.event).toHaveBeenCalledWith(expect.objectContaining({ event_type: "coverage_limitation_viewed", coverage_status: "unsupported" }), expect.anything()));
    expect(mocks.event).not.toHaveBeenCalledWith(expect.objectContaining({ event_type: "recommendation_viewed" }), expect.anything());
  });

  test("uses session overrides without a Profile mutation and limits comparison groundwork to four", async () => {
    const navigate = vi.fn();
    render(<ExplorePage auth={auth} onNavigate={navigate} state={{ ...state, goal: "ai_ml", selected: ["boston", "seattle", "austin", "chicago"] }} />);
    await waitFor(() => expect(mocks.evaluate).toHaveBeenCalledWith(expect.objectContaining({ goal: "ai_ml" }), expect.anything()));
    expect(screen.getByText("Temporary Explore override")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Add Greater New York to comparison" }));
    expect(await screen.findByText("Comparison selection is limited to four markets.")).toBeInTheDocument();
    expect(navigate).not.toHaveBeenCalled();
  });

  test("labels unconsented results as general intelligence rather than personalized Fit", async () => {
    mocks.evaluate.mockResolvedValue(envelope(payload("general_market_intelligence")));
    render(<ExplorePage auth={auth} onNavigate={vi.fn()} state={state} />);
    expect(await screen.findByText("General market intelligence")).toBeInTheDocument();
    expect(screen.getByText(/Personalization is off/i)).toBeInTheDocument();
    expect(screen.getByText("General market intelligence", { selector: ".map-legend strong" })).toBeInTheDocument();
  });

  test("renders typed context classifications without inferring semantics from reason copy", async () => {
    const classified = payload();
    classified.context.unsupported_context = [{
      code: "compensation_not_modeled",
      field: "compensation",
      source: "career_identity",
      reason: "The word unapplied appears here but must not change classification.",
    }];
    mocks.evaluate.mockResolvedValue(envelope(classified));
    render(<ExplorePage auth={auth} onNavigate={vi.fn()} state={state} />);

    expect(await screen.findByText("Ai Ml")).toBeInTheDocument();
    expect(screen.getByText("Internship opportunities · Hybrid work · Entry Level")).toBeInTheDocument();
    expect(screen.getByText("Compensation")).toBeInTheDocument();
    expect(screen.getByText("Unsupported", { selector: ".context-summary span" })).toBeInTheDocument();
  });

  test("distinguishes missing Profile from consent-off and prioritizes contradiction abstention", async () => {
    const noProfile = payload("general_market_intelligence");
    noProfile.context.career_identity_id = null;
    noProfile.context.career_identity_version = null;
    mocks.evaluate.mockResolvedValue(envelope(noProfile));
    const { unmount } = render(<ExplorePage auth={auth} onNavigate={vi.fn()} state={state} />);
    expect(await screen.findByText(/Tell us what kind of role you're looking for/i)).toBeInTheDocument();
    unmount();

    const conflicted = payload();
    conflicted.markets[0] = { ...conflicted.markets[0], state: "abstained", rank: null, fit_band: null, contradiction_blocking: true, contradiction_summary: "Hiring and access evidence point in different directions.", abstention_reason: "Evidence conflicts, so we're not naming a confident result." };
    mocks.evaluate.mockResolvedValue(envelope(conflicted));
    render(<ExplorePage auth={auth} onNavigate={vi.fn()} state={{ ...state, focus: "boston" }} />);
    expect(await screen.findAllByText(/Evidence conflicts/i)).not.toHaveLength(0);
    expect(screen.getAllByText(/Hiring and access evidence point in different directions/i).length).toBeGreaterThan(0);
  });

  test("shows observed opportunity evidence separately when coverage exists", async () => {
    const available = payload();
    available.markets[0].opportunity_coverage = { ...available.markets[0].opportunity_coverage, status: "adequate", active_opportunity_count: 12, ranking_eligible_opportunity_count: 4, fresh_opportunity_count: 9, limitations: [] };
    mocks.evaluate.mockResolvedValue(envelope(available));
    mocks.getOpportunities.mockResolvedValue(envelope({ opportunities: [{ opportunity_id: "opp-1", company_id: "acme", company_name: "Acme AI", original_title: "Product Intern", normalized_title: "AI Product Intern", role_family: "ai_ml", seniority_level: "entry_level", market_id: "greater_boston", market_label: "Boston", location_text: "Boston", work_arrangement: "hybrid", compensation_min: null, compensation_max: null, compensation_currency: null, compensation_interval: "unknown", employment_type: "internship", opportunity_type: "internship", posting_date: null, closing_date: null, application_url: null, source_url: null, description_text: null, skills: [], requirements: [], status: "active", freshness_state: "fresh", freshness_age_hours: 3, first_observed_at: null, last_observed_at: null, last_collected_at: null, canonical_updated_at: "", normalization_confidence: "high", identity_confidence: "high", ranking_eligible: true, ranking_ineligible_reasons: [], coverage_status: "adequate", coverage_limitations: [], provenance: {}, warnings: [] }] }));
    render(<ExplorePage auth={auth} onNavigate={vi.fn()} state={{ ...state, focus: "boston", opportunityTypes: ["internship"] }} />);
    expect(await screen.findByText(/12 observed active · 4 matching/i)).toBeInTheDocument();
    expect(screen.getByText(/Coverage: Adequate · 9 fresh/i)).toBeInTheDocument();
    expect(await screen.findByText("AI Product Intern")).toBeInTheDocument();
    expect(screen.getByText(/Current opportunity counts do not change market Fit/i)).toBeInTheDocument();
    expect(mocks.getOpportunities).toHaveBeenCalledWith(expect.objectContaining({
      market: "greater_boston",
      role_family: "ai_ml",
      opportunity_type: "internship",
      work_arrangement: "hybrid",
    }), expect.anything());
  });

  test("saves canonical Region identity once and disables repeated Save", async () => {
    render(<ExplorePage auth={auth} onNavigate={vi.fn()} state={{ ...state, focus: "boston" }} />);
    const saveButton = await screen.findByRole("button", { name: "Save market" });
    fireEvent.click(saveButton);
    await waitFor(() => expect(mocks.save).toHaveBeenCalledWith({ artifact_type: "region", artifact_ref: "greater_boston", label: "Greater Boston" }, expect.anything()));
    expect(await screen.findByRole("button", { name: "Saved ✓" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Saved ✓" }));
    expect(mocks.save).toHaveBeenCalledTimes(1);
  });

  test("falls back from empty hiring evidence to honestly labeled company presence", async () => {
    mocks.getRegion.mockResolvedValue(envelope({ region_id: "greater_boston", display_name: "Greater Boston", region_type: "metro", parent_region_id: null, labor_market_group: null, scores: null, top_companies_hiring: [], top_companies_present: [{ company_id: "present-co", company_name: "Present Co" }] }));
    render(<ExplorePage auth={auth} onNavigate={vi.fn()} state={{ ...state, focus: "boston" }} />);
    expect(await screen.findByText("Company presence (not active hiring evidence)")).toBeInTheDocument();
    expect(screen.getByText("Present Co")).toBeInTheDocument();
  });

  test("keeps the List/Map control available in either mobile mode and activates Compare", async () => {
    const navigate = vi.fn();
    const { rerender } = render(<ExplorePage auth={auth} onNavigate={navigate} state={state} />);
    expect(await screen.findByRole("group", { name: "Explore view" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Map" }));
    expect(navigate).toHaveBeenCalledWith(expect.stringContaining("view=map"), { replace: false });
    rerender(<ExplorePage auth={auth} onNavigate={navigate} state={{ ...state, view: "map", selected: ["boston", "new-york"] }} />);
    expect(screen.getByRole("button", { name: "List" })).toBeInTheDocument();
    const compare = screen.getByRole("button", { name: "Compare 2" });
    expect(compare).toBeEnabled();
    fireEvent.click(compare);
    expect(navigate).toHaveBeenCalledWith(
      "/markets/compare?view=map&selected=boston%2Cnew-york",
    );
  });

  test("routes recognized role search into the role override instead of free-text filtering", async () => {
    const navigate = vi.fn();
    render(<ExplorePage auth={auth} onNavigate={navigate} state={state} />);
    const search = await screen.findByPlaceholderText("Try Boston or AI / machine learning");
    fireEvent.change(search, { target: { value: "AI / machine learning" } });
    fireEvent.keyDown(search, { key: "Enter" });
    expect(navigate).toHaveBeenCalledWith("/markets?role=ai_ml", { replace: false });
    expect(search).toHaveValue("");
    expect(screen.queryByText(/No markets match/)).not.toBeInTheDocument();
  });

  test("focuses a geography search without leaving a hidden transient filter", async () => {
    const navigate = vi.fn();
    render(<ExplorePage auth={auth} onNavigate={navigate} state={state} />);
    const search = await screen.findByPlaceholderText("Try Boston or AI / machine learning");
    fireEvent.change(search, { target: { value: "Boston" } });
    fireEvent.keyDown(search, { key: "Enter" });
    expect(navigate).toHaveBeenCalledWith("/markets?focus=boston", { replace: false });
    expect(search).toHaveValue("");
  });

  test("canonicalizes legacy and malformed geographic URL tokens before they count", async () => {
    mocks.resolve.mockImplementation(async (token: string) => {
      if (token === "greater_sf") return envelope({ region_id: "sf_bay_area", public_slug: "san-francisco-bay-area" });
      throw new Error("unknown geography");
    });
    const withSf = payload();
    withSf.markets.push(market("sf_bay_area", "san-francisco-bay-area", "San Francisco Bay Area", 6));
    mocks.evaluate.mockResolvedValue(envelope(withSf));
    const navigate = vi.fn();
    render(<ExplorePage auth={auth} onNavigate={navigate} state={{ ...state, focus: "greater_boston", selected: ["greater_sf", "bad-market", "boston"] }} />);
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/markets?focus=boston&selected=san-francisco-bay-area%2Cboston", { replace: true }));
  });

  test("normalizes the complete raw URL pipeline before applying the four-market cap", async () => {
    const rawSearch = "?focus=greater_boston&selected=bad,greater_boston,boston,greater_sf,greater_nyc,seattle,austin";
    const rawState = parseRoute("/markets", rawSearch).explore;
    expect(rawState.selected).toEqual([
      "bad", "greater_boston", "boston", "greater_sf", "greater_nyc", "seattle", "austin",
    ]);
    mocks.resolve.mockImplementation(async (token: string) => {
      if (token === "greater_sf") return envelope({ region_id: "sf_bay_area", public_slug: "san-francisco-bay-area" });
      throw new Error("unknown geography");
    });
    const withSf = payload();
    withSf.markets.push(market("sf_bay_area", "san-francisco-bay-area", "San Francisco Bay Area", 6));
    mocks.evaluate.mockResolvedValue(envelope(withSf));
    const navigate = vi.fn();
    const { container, rerender } = render(<ExplorePage auth={auth} onNavigate={navigate} state={rawState} />);
    const canonicalUrl = "/markets?focus=boston&selected=boston%2Csan-francisco-bay-area%2Cnew-york%2Cseattle";

    await waitFor(() => expect(navigate).toHaveBeenCalledWith(canonicalUrl, { replace: true }));
    const canonicalState = parseRoute("/markets", canonicalUrl.slice(canonicalUrl.indexOf("?"))).explore;
    rerender(<ExplorePage auth={auth} onNavigate={navigate} state={canonicalState} />);

    await waitFor(() => expect(container.querySelectorAll(".comparison-chips button")).toHaveLength(4));
    const chips = Array.from(container.querySelectorAll<HTMLButtonElement>(".comparison-chips button"));
    expect(chips.map((chip) => chip.textContent)).toEqual([
      "Greater Boston ×",
      "San Francisco Bay Area ×",
      "Greater New York ×",
      "Greater Seattle ×",
    ]);
    expect(screen.queryByRole("button", { name: "Remove Austin from comparison" })).not.toBeInTheDocument();
    expect(new Set(chips.map((chip) => chip.textContent)).size).toBe(4);

    const reloadState = parseRoute("/markets", canonicalUrl.slice(canonicalUrl.indexOf("?"))).explore;
    expect(reloadState.selected).toEqual(["boston", "san-francisco-bay-area", "new-york", "seattle"]);
  });

  test("replaces duplicate and trailing fifth selections even when the first four are canonical", async () => {
    const rawState = parseRoute(
      "/markets",
      "?selected=boston,boston,new-york,seattle,austin,chicago",
    ).explore;
    const navigate = vi.fn();
    render(<ExplorePage auth={auth} onNavigate={navigate} state={rawState} />);

    await waitFor(() => expect(navigate).toHaveBeenCalledWith(
      "/markets?selected=boston%2Cnew-york%2Cseattle%2Caustin",
      { replace: true },
    ));
  });

  test("emits stable coverage and trust views once per market context", async () => {
    const { rerender } = render(<ExplorePage auth={auth} onNavigate={vi.fn()} state={{ ...state, focus: "boston" }} />);
    await waitFor(() => expect(mocks.event).toHaveBeenCalledWith(expect.objectContaining({ event_type: "coverage_limitation_viewed" }), expect.anything()));
    fireEvent.click(screen.getByText("Why and evidence"));
    await waitFor(() => expect(mocks.event).toHaveBeenCalledWith(expect.objectContaining({ event_type: "trust_explanation_viewed" }), expect.anything()));
    rerender(<ExplorePage auth={auth} onNavigate={vi.fn()} state={{ ...state, focus: "boston", view: "map" }} />);
    await new Promise((resolve) => window.setTimeout(resolve, 0));
    expect(mocks.event.mock.calls.filter(([body]) => body.event_type === "coverage_limitation_viewed")).toHaveLength(1);
    expect(mocks.event.mock.calls.filter(([body]) => body.event_type === "trust_explanation_viewed")).toHaveLength(1);
  });
});
