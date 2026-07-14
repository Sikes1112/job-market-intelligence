// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { MarketIntelligencePage } from "./MarketIntelligencePage";
import {
  safePublicText,
} from "./marketIntelligenceModel";
import {
  getMarketComparison,
  getMarketIntelligence,
  getMarketIntelligenceProfile,
} from "./api";
import type {
  ApiEnvelope,
  ExplainableRankingItem,
  ExplainableRankingReport,
  MarketEvidenceGrounding,
  MarketComparisonReport,
  MarketIntelligenceGoal,
  MarketIntelligenceProfile,
  PlatformMarketIntelligencePayload,
} from "./types";

vi.mock("./api", () => ({
  getMarketComparison: vi.fn(),
  getMarketIntelligence: vi.fn(),
  getMarketIntelligenceProfile: vi.fn(),
}));

const mockedGetMarketIntelligence = vi.mocked(getMarketIntelligence);
const mockedGetMarketIntelligenceProfile = vi.mocked(getMarketIntelligenceProfile);
const mockedGetMarketComparison = vi.mocked(getMarketComparison);

afterEach(() => {
  cleanup();
});

beforeEach(() => {
  vi.clearAllMocks();
  mockedGetMarketIntelligence.mockResolvedValue(envelope(platformFixture()));
  mockedGetMarketIntelligenceProfile.mockResolvedValue(envelope(profileFixture("atlanta")));
  mockedGetMarketComparison.mockResolvedValue(envelope(comparisonFixture("market_a")));
});

describe("MarketIntelligencePage", () => {
  test("renders overview, all markets, deterministic ranking, confidence, freshness, drivers, and limitations", async () => {
    renderPage();

    expect(await screen.findByText("Career-goal market rankings")).toBeInTheDocument();
    expect(screen.getByLabelText("Career goal")).toHaveValue("software_engineering");
    expect(screen.getAllByText("Atlanta").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Greater Boston").length).toBeGreaterThan(0);
    expect(screen.getByText("Rank #1")).toBeInTheDocument();
    expect(screen.getAllByText("High confidence").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Current freshness").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Observed hiring activity").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Some count facts are unknown and are not treated as zero.").length).toBeGreaterThan(0);
  });

  test("renders decision-usefulness sections from backend hardening metadata", async () => {
    renderPage();

    expect(await screen.findByRole("region", { name: "Decision guidance" })).toBeInTheDocument();
    for (const heading of [
      "Why this market",
      "Why not this market",
      "Evidence strongest here",
      "Evidence weakest here",
      "Direct vs proxy evidence",
      "What could change this ranking",
      "Stability",
      "Abstention explanation",
    ]) {
      expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
    }
    expect(screen.getByText("Direct and proxy evidence: The backend reports a mix of direct and proxy evidence.")).toBeInTheDocument();
    expect(screen.getAllByText(/Backend score margin to nearest peer is 0.1200/).length).toBeGreaterThan(0);
    expect(screen.getByText("The backend is not abstaining for this ranking.")).toBeInTheDocument();
  });

  test("renders unstable stability scenario summaries from backend grounding", async () => {
    const scenarioGrounding = groundingFixture(0.004, "unstable", [
      stabilityScenarioFixture(
        "missing_internship",
        "unstable",
        "Missing internship evidence changes Atlanta from rank 1 to rank 3.",
      ),
    ]);
    mockedGetMarketIntelligence.mockResolvedValue(envelope(platformWithDecisionState(
      {
        grounding: scenarioGrounding,
        limitations: [
          "Sensitivity analysis found unstable ranking behavior; use scenario details before treating this rank as durable.",
        ],
      },
      {
        grounding: scenarioGrounding,
        limitations: [
          "Sensitivity analysis found unstable ranking behavior; use scenario details before treating this rank as durable.",
        ],
      },
    )));
    mockedGetMarketComparison.mockResolvedValue(envelope({
      ...comparisonFixture("market_a"),
      grounding: scenarioGrounding,
      limitations: [
        "Sensitivity analysis found unstable ranking behavior; use scenario details before treating this rank as durable.",
      ],
    }));

    renderPage();

    expect((await screen.findAllByText("Unstable")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Unstable Missing Internship:/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Sensitivity analysis found unstable ranking behavior/).length).toBeGreaterThan(0);
  });

  test("keeps source concentration visible when later material scenarios are truncated", async () => {
    const scenarioGrounding = groundingFixture(0.004, "sensitive", [
      stabilityScenarioFixture(
        "missing_internship",
        "sensitive",
        "Missing internship evidence changes Atlanta from rank 1 to rank 2.",
      ),
      stabilityScenarioFixture(
        "missing_coop",
        "sensitive",
        "Missing co-op evidence changes Atlanta from rank 1 to rank 2.",
      ),
      stabilityScenarioFixture(
        "ranking_exclusion",
        "sensitive",
        "A ranking-eligible fact exclusion changes Atlanta from rank 1 to rank 2.",
      ),
      stabilityScenarioFixture(
        "source_concentration",
        "sensitive",
        "Source concentration risk leaves Atlanta dependent on one public source.",
      ),
    ]);
    mockedGetMarketIntelligence.mockResolvedValue(envelope(platformWithDecisionState(
      { grounding: scenarioGrounding },
      { grounding: scenarioGrounding },
    )));

    renderPage();

    expect(await screen.findByText(/Sensitive Source Concentration:/)).toBeInTheDocument();
    expect(screen.getByText(/dependent on one public source/)).toBeInTheDocument();
  });

  test("redacts backend-private text case-insensitively before rendering", () => {
    const fallback = "Public fallback";
    for (const unsafe of [
      "raw_provenance",
      "source_ref_id",
      "fact_source_link_id",
      "traceback",
      "Stack Trace",
      "/users/private/path",
      "C:\\Users\\private\\path",
    ]) {
      expect(safePublicText(`Unsafe ${unsafe} payload`, fallback)).toBe(fallback);
    }
  });

  test("renders repeated limitations without duplicate React key warnings", async () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);

    try {
      renderPage();

      await screen.findByRole("region", { name: "Decision guidance" });
      expect(screen.getAllByText("Some count facts are unknown and are not treated as zero.").length).toBeGreaterThan(1);
      expect(
        consoleError.mock.calls.filter(([message]) => (
          String(message).includes("Encountered two children with the same key")
        )),
      ).toEqual([]);
    } finally {
      consoleError.mockRestore();
    }
  });

  test.each([
    {
      label: "Clear leader",
      item: {
        evidence_sufficiency: "comparison_ready",
        is_provisional: false,
        abstention_reason: null,
        grounding: groundingFixture(0.12),
      },
      ranking: {
        evidence_sufficiency: "comparison_ready",
        is_provisional: false,
        abstention_reason: null,
        grounding: groundingFixture(0.12),
      },
    },
    {
      label: "Narrow lead",
      item: {
        evidence_sufficiency: "comparison_ready",
        is_provisional: false,
        abstention_reason: null,
        grounding: groundingFixture(0.006),
      },
      ranking: {
        evidence_sufficiency: "comparison_ready",
        is_provisional: false,
        abstention_reason: null,
        grounding: groundingFixture(0.006),
      },
    },
    {
      label: "Tie",
      item: {
        evidence_sufficiency: "comparison_ready",
        is_provisional: false,
        abstention_reason: null,
        grounding: groundingFixture(0),
      },
      ranking: {
        evidence_sufficiency: "comparison_ready",
        is_provisional: false,
        abstention_reason: null,
        grounding: groundingFixture(0),
      },
    },
    {
      label: "Provisional ranking",
      item: {
        evidence_sufficiency: "limited_evidence",
        is_provisional: true,
        abstention_reason: null,
        grounding: groundingFixture(0.12),
      },
      ranking: {
        evidence_sufficiency: "limited_evidence",
        is_provisional: true,
        abstention_reason: null,
        grounding: groundingFixture(0.12),
      },
    },
    {
      label: "Insufficient evidence",
      item: {
        evidence_sufficiency: "insufficient_evidence",
        is_provisional: false,
        abstention_reason: "there is not enough qualifying ranking evidence",
        grounding: groundingFixture(0.12),
      },
      ranking: {
        evidence_sufficiency: "insufficient_evidence",
        is_provisional: false,
        abstention_reason: "there is not enough qualifying ranking evidence",
        grounding: groundingFixture(0.12),
      },
    },
    {
      label: "Not supported",
      item: {
        evidence_sufficiency: "not_supported",
        is_provisional: false,
        abstention_reason: "the canonical data model does not support this goal",
        grounding: groundingFixture(0.12),
      },
      ranking: {
        evidence_sufficiency: "not_supported",
        is_provisional: false,
        abstention_reason: "the canonical data model does not support this goal",
        grounding: groundingFixture(0.12),
      },
    },
  ] satisfies Array<{
    label: string;
    item: Partial<ExplainableRankingItem>;
    ranking: Partial<ExplainableRankingReport>;
  }>)("renders the $label decision state from backend fields", async ({ label, item, ranking }) => {
    mockedGetMarketIntelligence.mockResolvedValue(envelope(platformWithDecisionState(item, ranking)));

    renderPage();

    expect((await screen.findAllByText(label)).length).toBeGreaterThan(0);
  });

  test("does not recompute sufficiency from strong-looking metrics or high scores", async () => {
    mockedGetMarketIntelligence.mockResolvedValue(envelope(platformWithDecisionState(
      {
        score: 0.99,
        raw_score: 0.99,
        confidence: "high",
        evidence_sufficiency: "not_supported",
        is_provisional: false,
        abstention_reason: "direct role-family evidence is not supported",
        supporting_metrics: {
          employer_count: 500,
          active_posting_total: 900,
          internship_total: 200,
          unknown_fact_count: 0,
          observed_zero_fact_count: 0,
          ranking_excluded_fact_count: 0,
        },
      },
      {
        evidence_sufficiency: "not_supported",
        is_provisional: false,
        abstention_reason: "direct role-family evidence is not supported",
      },
    )));

    renderPage();

    expect((await screen.findAllByText("Not supported")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("direct role-family evidence is not supported").length).toBeGreaterThan(0);
  });

  test("presents unsupported data-science ranking as abstention before diagnostic ordering", async () => {
    mockedGetMarketIntelligence.mockResolvedValue(envelope(unsupportedDataSciencePlatform()));
    mockedGetMarketComparison.mockResolvedValue(envelope(dataScienceUnsupportedComparison("no_winner")));

    renderPage({ goal: "data_science" });

    expect(await screen.findByRole("region", { name: "Decision guidance" })).toBeInTheDocument();
    expect(screen.getAllByText("Not supported").length).toBeGreaterThan(0);
    expect(screen.getByText("No decision market selected")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Why the backend abstains" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Diagnostic ordering constraints" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Why this market" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Diagnostic market ordering")).toBeInTheDocument();
    expect(screen.getByText("Diagnostic #1")).toBeInTheDocument();
    expect(screen.queryByText("Rank #1")).not.toBeInTheDocument();
    expect(screen.queryByText(/Atlanta is rank #1/)).not.toBeInTheDocument();
    expect(screen.getAllByText(/diagnostic ordering/).length).toBeGreaterThan(0);
  });

  test("does not render unsupported data-science comparison as a normal winner", async () => {
    mockedGetMarketIntelligence.mockResolvedValue(envelope(unsupportedDataSciencePlatform()));
    mockedGetMarketComparison.mockResolvedValue(envelope(dataScienceUnsupportedComparison("market_a")));

    renderPage({ goal: "data_science", compareA: "atlanta", compareB: "boston" });

    expect(await screen.findByText("No supported winner")).toBeInTheDocument();
    expect(screen.getByText(/abstains from naming a normal winner/)).toBeInTheDocument();
    expect(screen.queryByText("Market A ranks ahead")).not.toBeInTheDocument();
    expect(screen.queryByText(/stronger fit based on current data/)).not.toBeInTheDocument();
  });

  test("renders every supported career goal and requests the selected goal", async () => {
    renderPage();
    const selector = await screen.findByLabelText("Career goal");

    for (const label of [
      "Software Engineering",
      "Product Management",
      "AI / Machine Learning",
      "Cybersecurity",
      "Data Science",
    ]) {
      expect(screen.getByRole("option", { name: label })).toBeInTheDocument();
    }

    fireEvent.change(selector, { target: { value: "data_science" } });

    await waitFor(() => {
      expect(mockedGetMarketIntelligence).toHaveBeenCalledWith("data_science");
    });
  });

  test("preserves data-science coverage limitation", async () => {
    mockedGetMarketIntelligence.mockResolvedValue(envelope(platformFixture("data_science")));

    renderPage({ goal: "data_science" });

    expect(
      (await screen.findAllByText(/Direct data-science role-family facts are not collected/)).length,
    ).toBeGreaterThan(0);
  });

  test("renders market profile sections and unknown-vs-zero semantics", async () => {
    mockedGetMarketIntelligenceProfile.mockResolvedValue(envelope(profileFixture("atlanta", {
      supporting_metrics: {
        employer_count: 3,
        active_posting_total: 0,
        active_posting_unknown_rows: 2,
        internship_total: null,
        coop_total: null,
        unknown_fact_count: 4,
        observed_zero_fact_count: 0,
        ranking_excluded_fact_count: 0,
      },
    })));

    renderPage({ marketKey: "atlanta" });

    expect(await screen.findByText("Market profile")).toBeInTheDocument();
    expect(screen.getByText("Employer environment")).toBeInTheDocument();
    expect(screen.getByText("Hiring environment")).toBeInTheDocument();
    expect(screen.getByText("Internship ecosystem")).toBeInTheDocument();
    expect(screen.getByText("Co-op ecosystem")).toBeInTheDocument();
    expect(screen.getByText("Early-career environment")).toBeInTheDocument();
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Observed zero").length).toBeGreaterThan(0);
    expect(screen.getByText(/Unknown facts and observed-zero facts are displayed separately/)).toBeInTheDocument();
  });

  test("renders pairwise winner, strengths, weaknesses, metrics, confidence, and limitations", async () => {
    renderPage({ compareA: "atlanta", compareB: "boston" });

    expect(await screen.findByText("Market A ranks ahead")).toBeInTheDocument();
    expect(screen.getByText(/Atlanta is the stronger fit based on current data/)).toBeInTheDocument();
    expect(screen.getAllByText("Atlanta strength").length).toBeGreaterThan(0);
    expect(screen.getByText("Boston weakness")).toBeInTheDocument();
    expect(screen.getAllByText("Moderate confidence").length).toBeGreaterThan(0);
    expect(screen.getByText("Comparison limitation.")).toBeInTheDocument();
  });

  test("renders tie language without forcing a winner", async () => {
    mockedGetMarketComparison.mockResolvedValue(envelope(comparisonFixture("tie")));

    renderPage({ compareA: "atlanta", compareB: "boston" });

    expect(await screen.findByText("Currently tied")).toBeInTheDocument();
    expect(screen.getByText(/currently tied for this goal/)).toBeInTheDocument();
  });

  test("renders backend no-winner language without computing a winner", async () => {
    mockedGetMarketComparison.mockResolvedValue(envelope(comparisonFixture("no_winner")));

    renderPage({ compareA: "atlanta", compareB: "boston" });

    expect((await screen.findAllByText("No supported winner")).length).toBeGreaterThan(0);
    expect(screen.getByText(/does not name a winner/)).toBeInTheDocument();
  });

  test("renders backend contradiction findings without recomputing them", async () => {
    mockedGetMarketIntelligence.mockResolvedValue(envelope({
      ...platformFixture(),
      default_ranking: {
        ...platformFixture().default_ranking,
        contradiction_status: "blocking",
        contradictions: [contradictionFixture("alphabetical_tie_displayed_as_winner")],
        ranked_markets: [
          {
            ...rankingItem("atlanta", "Atlanta", 1, "software_engineering"),
            contradiction_status: "blocking",
            contradictions: [contradictionFixture("opposite_weakness_and_driver")],
          },
        ],
      },
    }));
    mockedGetMarketComparison.mockResolvedValue(envelope({
      ...comparisonFixture("no_winner"),
      contradiction_status: "blocking",
      contradictions: [contradictionFixture("winner_with_lower_score")],
    }));

    renderPage({ compareA: "atlanta", compareB: "boston" });

    expect((await screen.findAllByLabelText("Contradiction review")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/alphabetical_tie_displayed_as_winner/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/opposite_weakness_and_driver/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/winner_with_lower_score/).length).toBeGreaterThan(0);
  });

  test("handles same-market comparison without calling comparison API", async () => {
    renderPage({ compareA: "atlanta", compareB: "atlanta" });

    expect(await screen.findByText(/Choose two distinct markets/)).toBeInTheDocument();
    expect(mockedGetMarketComparison).not.toHaveBeenCalled();
  });

  test("handles invalid market and API failure safely", async () => {
    mockedGetMarketIntelligenceProfile.mockRejectedValue(new Error("Market intelligence market not found."));

    renderPage({ marketKey: "not_registered" });

    expect(await screen.findByText("Request failed")).toBeInTheDocument();
    expect(screen.getByText("Market intelligence market not found.")).toBeInTheDocument();
  });

  test("handles empty ranking and unknown future enum values safely", async () => {
    mockedGetMarketIntelligence.mockResolvedValue(envelope({
      ...platformFixture(),
      default_ranking: {
        ...platformFixture().default_ranking,
        ranked_markets: [],
        top_market_key: null,
      },
      profiles: [],
    }));
    mockedGetMarketIntelligenceProfile.mockResolvedValue(envelope(profileFixture("atlanta", {
      confidence: "future_confidence",
      freshness: "future_freshness",
    })));

    renderPage({ goal: "future_goal", marketKey: "atlanta" });

    expect(await screen.findByText("No ranking available")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Unsupported goal" })).toBeInTheDocument();
  });

  test("does not expose prohibited internal payload text", async () => {
    mockedGetMarketIntelligenceProfile.mockResolvedValue(envelope(profileFixture("atlanta", {
      limitations: [
        "trust_assessment_id private",
        "Safe limitation.",
      ],
    })));

    const { container } = renderPage({ marketKey: "atlanta" });

    await screen.findByText("Safe limitation.");
    expect(container.textContent).not.toContain("trust_assessment_id");
    expect(container.textContent).not.toContain("risk_routing_decision_id");
    expect(container.textContent).not.toContain("Traceback");
  });
});

function renderPage(state: Partial<Parameters<typeof MarketIntelligencePage>[0]["state"]> = {}) {
  const onNavigate = vi.fn((url: string) => {
    const parsed = new URL(url, "http://localhost");
    const nextGoal = parsed.searchParams.get("goal");
    if (nextGoal) {
      mockedGetMarketIntelligence(nextGoal as MarketIntelligenceGoal);
    }
  });
  const result = render(
    <MarketIntelligencePage
      onNavigate={onNavigate}
      state={{
        goal: "software_engineering",
        ...state,
      }}
    />,
  );
  return { ...result, onNavigate };
}

function envelope<T>(data: T): ApiEnvelope<T> {
  return {
    status: "success",
    data,
    metadata: { state: "fresh", source_versions: {}, warnings: [] },
    error: null,
  };
}

function platformFixture(goal: MarketIntelligenceGoal = "software_engineering"): PlatformMarketIntelligencePayload {
  const atlanta = profileFixture("atlanta");
  const boston = profileFixture("boston");
  const dataScienceLimitation = "Direct data-science role-family facts are not collected in the current curated datasets.";
  const goalDefinition = goalDefinitionFixture(goal);
  return {
    market_count: 2,
    profile_count: 2,
    supported_goals: [
      goalDefinitionFixture("software_engineering"),
      goalDefinitionFixture("product_management"),
      goalDefinitionFixture("ai_ml"),
      goalDefinitionFixture("cybersecurity"),
      goalDefinitionFixture("data_science", [dataScienceLimitation]),
    ],
    profiles: [atlanta, boston],
    default_ranking: {
      goal,
      goal_definition: goalDefinition,
      ranked_markets: [
        rankingItem("atlanta", "Atlanta", 1, goal),
        rankingItem("boston", "Greater Boston", 2, goal),
      ],
      top_market_key: "atlanta",
      explanation: "Atlanta ranks first based on observed hiring activity.",
      limitations: goal === "data_science"
        ? [dataScienceLimitation, "Some count facts are unknown and are not treated as zero."]
        : ["Some count facts are unknown and are not treated as zero."],
      tie_breaker: "Sort by confidence-adjusted score descending, then market key.",
      evidence_sufficiency: goal === "data_science" ? "not_supported" : "limited_evidence",
      is_provisional: goal !== "data_science",
      abstention_reason: goal === "data_science"
        ? "the current canonical data model does not include direct evidence needed for this goal"
        : null,
      contradiction_status: "clear",
      contradictions: [],
      grounding: groundingFixture(0.12),
    },
    highest_confidence_market: "atlanta",
    public_summary: "Two imported market profiles are available.",
    limitations: goal === "data_science" ? [dataScienceLimitation] : [],
  };
}

function platformWithDecisionState(
  itemOverrides: Partial<ExplainableRankingItem>,
  rankingOverrides: Partial<ExplainableRankingReport> = {},
): PlatformMarketIntelligencePayload {
  const platform = platformFixture();
  const topItem = {
    ...platform.default_ranking.ranked_markets[0],
    ...itemOverrides,
  };
  const ranking = {
    ...platform.default_ranking,
    evidence_sufficiency: topItem.evidence_sufficiency,
    is_provisional: topItem.is_provisional,
    abstention_reason: topItem.abstention_reason,
    grounding: topItem.grounding,
    ...rankingOverrides,
    ranked_markets: [
      topItem,
      ...platform.default_ranking.ranked_markets.slice(1),
    ],
  };
  return {
    ...platform,
    default_ranking: ranking,
  };
}

function unsupportedDataSciencePlatform(): PlatformMarketIntelligencePayload {
  const platform = platformFixture("data_science");
  const abstentionReason = "the current canonical data model does not include direct evidence needed for this goal";
  const rankedMarkets = platform.default_ranking.ranked_markets.map((item) => {
    const grounding = item.grounding ?? groundingFixture(0.12);
    return {
      ...item,
      goal: "data_science" as const,
      confidence: "limited" as const,
      evidence_sufficiency: "not_supported" as const,
      evidence_basis: "proxy" as const,
      is_provisional: false,
      abstention_reason: abstentionReason,
      grounding: {
        ...grounding,
        direct_evidence_summary: [
          "No direct Data Science evidence appears among positive ranking drivers.",
        ],
        proxy_evidence_summary: [
          "Proxy-only adjacent evidence is available for diagnostic ordering.",
        ],
        confidence_constraints: [
          "Sufficiency is not_supported, so the ordering is diagnostic ordering only.",
        ],
      },
    };
  });
  return {
    ...platform,
    default_ranking: {
      ...platform.default_ranking,
      ranked_markets: rankedMarkets,
      top_market_key: null,
      explanation: (
        "Ranking position: the backend abstains from naming a top Data Science market "
        + `because ${abstentionReason}; Atlanta is listed at rank 1 of 2 for diagnostic ordering.`
      ),
      evidence_sufficiency: "not_supported",
      is_provisional: false,
      abstention_reason: abstentionReason,
      grounding: rankedMarkets[0].grounding,
    },
    public_summary: (
      "Two imported market profiles are available; the backend abstains from naming "
      + `a top Data Science market because ${abstentionReason}.`
    ),
  };
}

function goalDefinitionFixture(goal: MarketIntelligenceGoal, limitations: string[] = []) {
  const labels: Record<string, string> = {
    software_engineering: "Software Engineering",
    product_management: "Product Management",
    ai_ml: "AI / Machine Learning",
    cybersecurity: "Cybersecurity",
    data_science: "Data Science",
  };
  return {
    goal,
    label: labels[goal] ?? "Unknown goal",
    description: "Goal description.",
    direct_signals: ["company presence"],
    limitations,
  };
}

function profileFixture(
  marketKey: "atlanta" | "boston",
  overrides: Partial<MarketIntelligenceProfile> = {},
): MarketIntelligenceProfile {
  const marketName = marketKey === "atlanta" ? "Atlanta" : "Greater Boston";
  return {
    market_key: marketKey,
    market_name: marketName,
    region_id: marketKey,
    overview: `${marketName} has curated employer evidence.`,
    strengths: [
      {
        code: "strong_employer_presence",
        message: `${marketName} strength`,
        evidence: "3 curated employers are present.",
        impact: "Improves comparison breadth.",
      },
    ],
    weaknesses: [
      {
        code: "limited_coop_coverage",
        message: `${marketName} weakness`,
        evidence: "No observed co-op count is available.",
        impact: "Limits co-op comparison.",
      },
    ],
    hiring_summary: "5 observed active postings across 2 hiring facts. Unknown rows are not treated as zero.",
    employer_summary: "3 curated employers across 3 sectors.",
    internship_summary: "2 observed internship counts; 1 internship count is unknown.",
    coop_summary: "No observed co-op count is available; 1 co-op count is unknown.",
    early_career_summary: "1 observed entry-level full-time count; 1 formal program signal.",
    opportunity_environment: {
      hiring_activity: "Hiring activity summary.",
      employer_diversity: "Employer diversity summary.",
      internship_ecosystem: "Internship ecosystem summary.",
      coop_ecosystem: "Co-op ecosystem summary.",
      early_career_support: "Early-career support summary.",
      hiring_momentum: "Observed hiring activity is positive; no unsupported trend is inferred.",
      overall: "Overall opportunity environment summary.",
    },
    confidence: "high",
    confidence_score: 0.88,
    freshness: "current",
    coverage_summary: "Coverage summary.",
    limitations: ["Some count facts are unknown and are not treated as zero."],
    supporting_metrics: {
      employer_count: 3,
      active_posting_total: 5,
      active_posting_unknown_rows: 1,
      active_posting_zero_rows: 1,
      internship_total: 2,
      coop_total: null,
      unknown_fact_count: 3,
      observed_zero_fact_count: 1,
      ranking_excluded_fact_count: 0,
    },
    grounding: groundingFixture(null),
    ...overrides,
  };
}

function rankingItem(
  marketKey: "atlanta" | "boston",
  marketName: string,
  rank: number,
  goal: MarketIntelligenceGoal,
) {
  return {
    rank,
    market_key: marketKey,
    market_name: marketName,
    goal,
    score: rank === 1 ? 0.84 : 0.72,
    raw_score: rank === 1 ? 0.91 : 0.79,
    confidence: rank === 1 ? "high" : "moderate",
    freshness: "current",
    ranking_drivers: [
      {
        code: "hiring_activity",
        label: "Observed hiring activity",
        contribution: 0.42,
        evidence: "Observed hiring activity is supported by canonical metric value 5.",
      },
      {
        code: "employer_presence",
        label: "Employer presence",
        contribution: 0.25,
        evidence: "Employer presence is supported by canonical metric value 3.",
      },
    ],
    strengths: [`${marketName} strength`],
    weaknesses: [`${marketName} weakness`],
    limitations: ["Some count facts are unknown and are not treated as zero."],
    supporting_metrics: {
      employer_count: 3,
      active_posting_total: rank === 1 ? 5 : 2,
      unknown_fact_count: 3,
      observed_zero_fact_count: 1,
      ranking_excluded_fact_count: 0,
    },
    evidence_sufficiency: "limited_evidence",
    evidence_basis: "direct_and_proxy",
    is_provisional: true,
    abstention_reason: null,
    contradiction_status: "clear",
    contradictions: [],
    grounding: groundingFixture(rank === 1 ? 0.12 : 0.12),
  };
}

function comparisonFixture(outcome: "market_a" | "market_b" | "tie" | "no_winner"): MarketComparisonReport {
  return {
    goal: "software_engineering",
    market_a: {
      market_key: "atlanta",
      market_name: "Atlanta",
      score: 0.84,
      confidence: "moderate",
      strengths: ["Atlanta strength"],
      weaknesses: ["Atlanta weakness"],
      supporting_metrics: {
        employer_count: 3,
        active_posting_total: 5,
        unknown_fact_count: 3,
        observed_zero_fact_count: 1,
        ranking_excluded_fact_count: 0,
      },
      evidence_sufficiency: "limited_evidence",
      evidence_basis: "direct_and_proxy",
      grounding: groundingFixture(0.12),
    },
    market_b: {
      market_key: "boston",
      market_name: "Greater Boston",
      score: outcome === "tie" ? 0.84 : 0.72,
      confidence: "moderate",
      strengths: ["Boston strength"],
      weaknesses: ["Boston weakness"],
      supporting_metrics: {
        employer_count: 3,
        active_posting_total: 2,
        unknown_fact_count: 3,
        observed_zero_fact_count: 1,
        ranking_excluded_fact_count: 0,
      },
      evidence_sufficiency: "limited_evidence",
      evidence_basis: "direct_and_proxy",
      grounding: groundingFixture(0.12),
    },
    outcome,
    winner_market_key: outcome === "market_a" ? "atlanta" : outcome === "market_b" ? "boston" : null,
    explanation: outcome === "no_winner"
      ? "The backend does not name a winner because evidence is insufficient."
      : "Atlanta ranks ahead because its confidence-adjusted score is higher.",
    confidence: "moderate",
    supporting_metrics: {
      market_a_score: 0.84,
      market_b_score: outcome === "tie" ? 0.84 : 0.72,
      score_delta: outcome === "tie" ? 0 : 0.12,
      evidence_sufficiency: outcome === "no_winner" ? "insufficient_evidence" : "limited_evidence",
    },
    limitations: ["Comparison limitation."],
    evidence_sufficiency: outcome === "no_winner" ? "insufficient_evidence" : "limited_evidence",
    is_provisional: outcome !== "no_winner",
    abstention_reason: outcome === "no_winner" ? "evidence is insufficient" : null,
    contradiction_status: "clear",
    contradictions: [],
    grounding: groundingFixture(outcome === "tie" ? 0 : 0.12),
  };
}

function dataScienceUnsupportedComparison(outcome: "market_a" | "no_winner"): MarketComparisonReport {
  const abstentionReason = "the current canonical data model does not support this data-science comparison";
  const base = comparisonFixture(outcome);
  const grounding = base.grounding ?? groundingFixture(0.12);
  return {
    ...base,
    goal: "data_science",
    outcome,
    winner_market_key: outcome === "market_a" ? "atlanta" : null,
    explanation: "The backend does not name a winner because data-science evidence is not supported.",
    confidence: "limited",
    market_a: {
      ...base.market_a,
      confidence: "limited",
      evidence_sufficiency: "not_supported",
      evidence_basis: "proxy",
    },
    market_b: {
      ...base.market_b,
      confidence: "limited",
      evidence_sufficiency: "not_supported",
      evidence_basis: "proxy",
    },
    supporting_metrics: {
      ...base.supporting_metrics,
      evidence_sufficiency: "not_supported",
    },
    limitations: [
      "Pairwise comparison is not supported for an authoritative winner by the current canonical data model.",
    ],
    evidence_sufficiency: "not_supported",
    is_provisional: false,
    abstention_reason: abstentionReason,
    grounding: {
      ...grounding,
      confidence_constraints: [
        "Comparison confidence is limited; sufficiency is not_supported.",
      ],
    },
  };
}

function groundingFixture(
  scoreMargin: number | null,
  stabilityStatus: MarketEvidenceGrounding["stability_status"] = "indeterminate",
  stabilityScenarios: MarketEvidenceGrounding["stability_scenarios"] = [],
): MarketEvidenceGrounding {
  return {
    evidence_areas_used: ["Observed hiring activity"],
    evidence_areas_missing: ["Unknown count facts"],
    direct_evidence_summary: ["Observed hiring activity is supported by canonical metrics."],
    proxy_evidence_summary: ["Employer presence is used as a proxy."],
    freshness: "current",
    coverage: "3 ranking-eligible fact(s); 3 unknown count fact(s); 1 observed zero count fact(s).",
    excluded_fact_summary: "No ranking-excluded facts are used in the score.",
    confidence_constraints: [
      "Confidence is moderate.",
      "Unknown count facts constrain confidence and remain distinct from zero.",
    ],
    score_margin: scoreMargin,
    stability_status: stabilityStatus,
    stability_scenarios: stabilityScenarios,
  };
}

function stabilityScenarioFixture(
  scenario: string,
  status: MarketEvidenceGrounding["stability_status"],
  explanation: string,
) {
  return {
    scenario,
    label: scenario,
    status,
    baseline_result: {
      market_key: "atlanta",
      rank: 1,
      score: 0.84,
      confidence: "high",
      freshness: "current",
      evidence_sufficiency: "limited_evidence",
      top_market_key: "atlanta",
    },
    scenario_result: {
      market_key: "atlanta",
      rank: 3,
      score: 0.72,
      confidence: "moderate",
      freshness: "current",
      evidence_sufficiency: "limited_evidence",
      top_market_key: "boston",
    },
    rank_change: 2,
    winner_change: true,
    score_delta: -0.12,
    confidence_delta: -1,
    sufficiency_delta: "unchanged",
    explanation,
  } satisfies NonNullable<MarketEvidenceGrounding["stability_scenarios"]>[number];
}

function contradictionFixture(code: string) {
  return {
    code,
    severity: "blocking",
    message: code,
    evidence: `${code} evidence.`,
    blocks_recommendation: true,
  };
}
