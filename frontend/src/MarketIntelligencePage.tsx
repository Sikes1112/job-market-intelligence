import { useEffect, useMemo, useState } from "react";

import {
  getMarketComparison,
  getMarketIntelligence,
  getMarketIntelligenceProfile,
} from "./api";
import {
  DEFAULT_MARKET_INTELLIGENCE_GOAL,
  comparisonOutcomeLabel,
  confidencePresentation,
  contributionLabel,
  decisionStatePresentation,
  evidenceBasisPresentation,
  evidenceSufficiencyPresentation,
  formatMetricValue,
  freshnessPresentation,
  goalLabel,
  humanizeKey,
  isKnownMarketIntelligenceGoal,
  metricLabel,
  safePublicText,
  scoreMarginLabel,
  scoreLabel,
  stabilityPresentation,
} from "./marketIntelligenceModel";
import type {
  ApiEnvelope,
  ExplainableRankingItem,
  ExplainableRankingReport,
  MarketContradictionFinding,
  MarketContradictionStatus,
  MarketComparisonReport,
  MarketEvidenceGrounding,
  MarketEvidenceSufficiency,
  MarketIntelligenceGoalDefinition,
  MarketIntelligenceInsight,
  MarketIntelligenceProfile,
  MarketIntelligenceSupportingMetrics,
  PlatformMarketIntelligencePayload,
} from "./types";
import type { MarketIntelligenceUrlState } from "./urlState";
import { marketIntelligenceUrl } from "./urlState";

type LoadState<T> = {
  loading: boolean;
  envelope: ApiEnvelope<T> | null;
  error: string | null;
};

const EMPTY_STATE = { loading: false, envelope: null, error: null };
const METRIC_KEYS = [
  "employer_count",
  "active_posting_total",
  "active_posting_unknown_rows",
  "active_posting_zero_rows",
  "product_active_postings",
  "product_activity_status",
  "ai_cloud_active_postings",
  "ai_cloud_activity_status",
  "cybersecurity_active_postings",
  "cybersecurity_activity_status",
  "internship_total",
  "coop_total",
  "unknown_fact_count",
  "observed_zero_fact_count",
  "ranking_excluded_fact_count",
] as const;

export function MarketIntelligencePage({
  state,
  onNavigate,
}: {
  state: MarketIntelligenceUrlState;
  onNavigate: (url: string) => void;
}) {
  const [platformState, setPlatformState] =
    useState<LoadState<PlatformMarketIntelligencePayload>>(EMPTY_STATE);
  const [profileState, setProfileState] =
    useState<LoadState<MarketIntelligenceProfile>>(EMPTY_STATE);
  const [comparisonState, setComparisonState] =
    useState<LoadState<MarketComparisonReport>>(EMPTY_STATE);

  const selectedGoal = state.goal || DEFAULT_MARKET_INTELLIGENCE_GOAL;
  const platform = platformState.envelope?.data ?? null;
  const ranking = platform?.default_ranking ?? null;
  const supportedGoals = useMemo(() => platform?.supported_goals ?? [], [platform]);
  const rankedMarkets = ranking?.ranked_markets ?? [];
  const hasDecisionMarket = Boolean(
    ranking?.top_market_key && !isAbstentionSufficiency(ranking?.evidence_sufficiency),
  );
  const selectedMarketKey = state.marketKey
    ?? (hasDecisionMarket ? ranking?.top_market_key : undefined)
    ?? platform?.profiles[0]?.market_key
    ?? "";
  const loadedProfile = profileState.envelope?.data ?? null;
  const selectedProfile = loadedProfile?.market_key === selectedMarketKey
    ? loadedProfile
    : platform?.profiles.find((profile) => profile.market_key === selectedMarketKey)
    ?? null;
  const comparisonA = state.compareA ?? selectedMarketKey;
  const comparisonB = state.compareB
    ?? rankedMarkets.find((item) => item.market_key !== comparisonA)?.market_key
    ?? "";
  const sameMarketComparison = Boolean(comparisonA && comparisonA === comparisonB);
  const invalidGoal = Boolean(selectedGoal && platform && !isKnownMarketIntelligenceGoal(selectedGoal)
    && !supportedGoals.some((goal) => goal.goal === selectedGoal));

  useEffect(() => {
    let cancelled = false;
    setPlatformState((current) => ({ ...current, loading: true, error: null }));
    getMarketIntelligence(selectedGoal)
      .then((envelope) => {
        if (!cancelled) setPlatformState({ loading: false, envelope, error: null });
      })
      .catch((error) => {
        if (!cancelled) {
          setPlatformState({
            loading: false,
            envelope: null,
            error: error instanceof Error ? error.message : "Market intelligence is unavailable.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedGoal]);

  useEffect(() => {
    if (!selectedMarketKey) {
      setProfileState(EMPTY_STATE);
      return;
    }
    let cancelled = false;
    setProfileState((current) => ({ ...current, loading: true, error: null }));
    getMarketIntelligenceProfile(selectedMarketKey)
      .then((envelope) => {
        if (!cancelled) setProfileState({ loading: false, envelope, error: null });
      })
      .catch((error) => {
        if (!cancelled) {
          setProfileState({
            loading: false,
            envelope: null,
            error: error instanceof Error ? error.message : "Market profile is unavailable.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedMarketKey]);

  useEffect(() => {
    if (!comparisonA || !comparisonB || sameMarketComparison) {
      setComparisonState(EMPTY_STATE);
      return;
    }
    let cancelled = false;
    setComparisonState((current) => ({ ...current, loading: true, error: null }));
    getMarketComparison(comparisonA, comparisonB, selectedGoal)
      .then((envelope) => {
        if (!cancelled) setComparisonState({ loading: false, envelope, error: null });
      })
      .catch((error) => {
        if (!cancelled) {
          setComparisonState({
            loading: false,
            envelope: null,
            error: error instanceof Error ? error.message : "Market comparison is unavailable.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [comparisonA, comparisonB, sameMarketComparison, selectedGoal]);

  const goalDefinitions = useMemo(
    () => mergeGoalDefinitions(supportedGoals, ranking?.goal_definition),
    [ranking?.goal_definition, supportedGoals],
  );

  function updateUrl(next: Partial<MarketIntelligenceUrlState>) {
    onNavigate(marketIntelligenceUrl({
      goal: selectedGoal,
      marketKey: state.marketKey,
      compareA: comparisonA,
      compareB: comparisonB,
      ...next,
    }));
  }

  return (
    <div className="view-grid market-intelligence-page">
      <section className="card market-intelligence-hero">
        <div className="card-header">
          <div>
            <p className="card-eyebrow">Market intelligence</p>
            <h2>Career-goal market rankings</h2>
          </div>
          {ranking ? (
            <span className="badge badge-real">
              {ranking.ranked_markets.length} ranked markets
            </span>
          ) : null}
        </div>
        <p className="lead-copy">Compare eight illustrative markets by career goal. Results are directional, not live market claims.</p>
        <label className="market-intelligence-goal">
          Career goal
          <select
            aria-label="Career goal"
            value={selectedGoal}
            onChange={(event) => updateUrl({ goal: event.target.value, marketKey: undefined })}
          >
            {goalDefinitions.map((definition) => (
              <option key={definition.goal} value={definition.goal}>
                {safePublicText(definition.label, goalLabel(definition.goal))}
              </option>
            ))}
            {selectedGoal && !goalDefinitions.some((definition) => definition.goal === selectedGoal) ? (
              <option value={selectedGoal}>Unsupported goal</option>
            ) : null}
          </select>
        </label>
        {platformState.loading ? <LoadingBlock label="Loading market intelligence" /> : null}
        {platformState.error ? <ErrorState message={platformState.error} /> : null}
        {invalidGoal ? (
          <ErrorState message="The selected career goal is not available." />
        ) : null}
        {platform ? (
          <div className="market-intelligence-summary">
            <p>{intelligenceText(platform.public_summary)}</p>
            <LimitationList limitations={platform.limitations} />
          </div>
        ) : null}
      </section>

      <section className="card">
        <div className="card-header">
          <div>
            <p className="card-eyebrow">Goal ranking</p>
            <h2>{goalLabel(selectedGoal, goalDefinitions)}</h2>
          </div>
          {ranking ? <span className="badge">Confidence-aware order</span> : null}
        </div>
        {ranking ? (
          <>
            <p className="meta-copy">{rankingSummary(ranking, goalLabel(selectedGoal, goalDefinitions))}</p>
            <ContradictionList
              findings={ranking.contradictions}
              status={ranking.contradiction_status}
            />
            <DecisionUsefulnessPanel
              item={topDecisionItem(ranking)}
              ranking={ranking}
            />
            {rankedMarkets.length ? (
              <div
                className="market-intelligence-ranking"
                aria-label={isAbstentionSufficiency(ranking.evidence_sufficiency)
                  ? "Evidence-only market ordering"
                  : "Ranked markets"}
              >
                {rankedMarkets.map((item) => (
                  <RankingCard
                    key={item.market_key}
                    item={item}
                    onCompare={() => updateUrl({
                      compareA: item.market_key,
                      compareB: rankedMarkets.find((candidate) => candidate.market_key !== item.market_key)?.market_key,
                      marketKey: item.market_key,
                    })}
                    onOpenProfile={() => updateUrl({ marketKey: item.market_key })}
                    selected={item.market_key === selectedMarketKey}
                  />
                ))}
              </div>
            ) : (
              <EmptyState
                body="No markets have enough evidence for this goal."
                title="No ranking available"
              />
            )}
            <LimitationList limitations={ranking.limitations} />
          </>
        ) : !platformState.loading && !platformState.error ? (
          <EmptyState
            body="No ranking is available for the selected career goal."
            title="No market ranking loaded"
          />
        ) : null}
      </section>

      <MarketProfileSection
        loading={profileState.loading}
        error={profileState.error}
        profile={selectedProfile}
      />

      <section className="card" aria-labelledby="market-intelligence-comparison-heading">
        <div className="card-header">
          <div>
            <p className="card-eyebrow">Pairwise comparison</p>
            <h2 id="market-intelligence-comparison-heading">Compare two markets</h2>
          </div>
        </div>
        <div className="comparison-controls">
          <label>
            Market A
            <select
              value={comparisonA}
              onChange={(event) => updateUrl({ compareA: event.target.value })}
            >
              {marketOptions(platform).map((market) => (
                <option key={market.market_key} value={market.market_key}>
                  {market.market_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Market B
            <select
              value={comparisonB}
              onChange={(event) => updateUrl({ compareB: event.target.value })}
            >
              {marketOptions(platform).map((market) => (
                <option key={market.market_key} value={market.market_key}>
                  {market.market_name}
                </option>
              ))}
            </select>
          </label>
        </div>
        {sameMarketComparison ? (
          <ErrorState message="Choose two distinct markets before running the intelligence comparison." />
        ) : null}
        {comparisonState.loading ? <LoadingBlock label="Loading market comparison" /> : null}
        {comparisonState.error ? <ErrorState message={comparisonState.error} /> : null}
        <ComparisonPanel comparison={comparisonState.envelope?.data ?? null} />
      </section>
    </div>
  );
}

function topDecisionItem(ranking: ExplainableRankingReport) {
  if (!ranking.top_market_key || isAbstentionSufficiency(ranking.evidence_sufficiency)) {
    return null;
  }
  return ranking.ranked_markets.find((item) => item.market_key === ranking.top_market_key)
    ?? null;
}

function DecisionUsefulnessPanel({
  item,
  ranking,
}: {
  item: ExplainableRankingItem | null;
  ranking: ExplainableRankingReport;
}) {
  const grounding = item?.grounding ?? ranking.grounding;
  const evidenceSufficiency = item?.evidence_sufficiency ?? ranking.evidence_sufficiency;
  const abstentionReason = item?.abstention_reason ?? ranking.abstention_reason;
  const decision = decisionStatePresentation({
    evidenceSufficiency,
    isProvisional: item?.is_provisional ?? ranking.is_provisional,
    scoreMargin: grounding?.score_margin,
  });
  const sufficiency = evidenceSufficiencyPresentation(evidenceSufficiency);
  const stability = stabilityPresentation(grounding?.stability_status);
  const evidenceBasis = evidenceBasisPresentation(item?.evidence_basis);
  const abstains = isAbstentionSufficiency(evidenceSufficiency);
  const marketName = item && !abstains
    ? safePublicText(item.market_name, item.market_key)
    : "No decision market selected";

  return (
    <section className="decision-usefulness-panel" aria-label="Decision guidance">
      <div className="decision-panel-header">
        <div>
          <p className="card-eyebrow">Decision guidance</p>
          <h3>{decision.label}</h3>
          <p className="meta-copy">{marketName}</p>
        </div>
        <div className="decision-state-row" aria-label="Decision states">
          <span className={decision.className}>{decision.label}</span>
          <span className={sufficiency.className}>{sufficiency.label}</span>
          <span className={stability.className}>{stability.label}</span>
        </div>
      </div>
      <p className="decision-state-help">{intelligenceText(decision.help)}</p>
      <details className="method-details intelligence-evidence-details">
        <summary>Evidence and stability</summary>
        <div className="decision-section-grid">
          <DecisionSection
            title={abstains ? "Why no recommendation" : "Why this market"}
            empty={abstains
              ? "No abstention reason is available."
              : "No market-specific reason is available."}
            items={whyThisMarket(ranking, item, abstains)}
          />
          <DecisionSection
            title={abstains ? "Decision limitations" : "Why not this market"}
            empty={abstains
              ? "No additional limitations are available."
              : "No additional trade-offs are available."}
            items={whyNotThisMarket(ranking, item)}
          />
          <DecisionSection
            title={abstains ? "Available evidence" : "Evidence strongest here"}
            empty="No strongest-evidence details are available."
            items={strongestEvidence(item, grounding)}
          />
          <DecisionSection
            title={abstains ? "Missing evidence" : "Evidence weakest here"}
            empty="No missing-evidence details are available."
            items={weakestEvidence(ranking, item, grounding)}
          />
          <DecisionSection
            title="Direct vs proxy evidence"
            empty="No direct/proxy evidence details are available."
            items={[
              `${evidenceBasis.label}: ${evidenceBasis.help}`,
              ...(grounding?.direct_evidence_summary ?? []),
              ...(grounding?.proxy_evidence_summary ?? []),
            ]}
          />
          <DecisionSection
            title={abstains ? "Ordering constraints" : "What could change this ranking"}
            empty="No ranking-change details are available."
            items={rankingChangeFactors(ranking, grounding)}
          />
          <DecisionSection
            title="Stability"
            empty="No stability details are available."
            items={[
              `${stability.label}: ${stability.help}`,
              scoreMarginLabel(grounding?.score_margin),
              ...stabilityScenarioItems(grounding),
            ]}
          />
          <DecisionSection
            title="Abstention explanation"
            empty="No additional abstention details are available."
            items={abstentionExplanation(evidenceSufficiency, abstentionReason)}
          />
        </div>
      </details>
    </section>
  );
}

function DecisionSection({
  empty,
  items,
  title,
}: {
  empty: string;
  items: Array<string | null | undefined>;
  title: string;
}) {
  const publicItems = items
    .map((item) => intelligenceText(item))
    .filter(Boolean)
    .slice(0, 5);
  return (
    <section className="decision-section">
      <h4>{title}</h4>
      {publicItems.length ? (
        <ul>
          {publicItems.map((item, index) => (
            <li key={`${title}-${index}-${item}`}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="meta-copy">{empty}</p>
      )}
    </section>
  );
}

function whyThisMarket(
  ranking: ExplainableRankingReport,
  item: ExplainableRankingItem | null,
  abstains: boolean,
) {
  if (abstains) {
    return [
      ranking.abstention_reason,
      ranking.explanation,
      ...ranking.limitations,
    ];
  }
  return [
    item ? `${safePublicText(item.market_name, item.market_key)} is rank #${item.rank}.` : null,
    ranking.explanation,
    ...(item?.strengths ?? []),
    item?.ranking_drivers[0]?.evidence,
  ];
}

function whyNotThisMarket(
  ranking: ExplainableRankingReport,
  item: ExplainableRankingItem | null,
) {
  return [
    ...(item?.limitations ?? []),
    ...(item?.weaknesses ?? []),
    ...ranking.limitations,
  ];
}

function strongestEvidence(
  item: ExplainableRankingItem | null,
  grounding: MarketEvidenceGrounding | null | undefined,
) {
  return [
    ...(item?.ranking_drivers.slice(0, 2).map((driver) => (
      `${safePublicText(driver.label, humanizeKey(driver.code))}: ${safePublicText(driver.evidence)}`
    )) ?? []),
    ...(grounding?.direct_evidence_summary ?? []),
  ];
}

function weakestEvidence(
  ranking: ExplainableRankingReport,
  item: ExplainableRankingItem | null,
  grounding: MarketEvidenceGrounding | null | undefined,
) {
  return [
    ...(grounding?.evidence_areas_missing ?? []),
    ...(item?.limitations ?? []),
    ...ranking.limitations,
    ...(grounding?.confidence_constraints ?? []),
  ];
}

function rankingChangeFactors(
  ranking: ExplainableRankingReport,
  grounding: MarketEvidenceGrounding | null | undefined,
) {
  return [
    scoreMarginLabel(grounding?.score_margin),
    grounding?.excluded_fact_summary,
    ...(grounding?.confidence_constraints ?? []),
    ...ranking.limitations,
  ];
}

function stabilityScenarioItems(
  grounding: MarketEvidenceGrounding | null | undefined,
) {
  const materialScenarios = (grounding?.stability_scenarios ?? [])
    .filter((scenario) => scenario.status === "unstable" || scenario.status === "sensitive");
  const sourceConcentrationScenarios = materialScenarios
    .filter((scenario) => scenario.scenario === "source_concentration");
  const otherMaterialScenarios = materialScenarios
    .filter((scenario) => scenario.scenario !== "source_concentration");

  return [...sourceConcentrationScenarios, ...otherMaterialScenarios]
    .slice(0, 3)
    .map((scenario) => (
      `${humanizeKey(scenario.status)} ${humanizeKey(scenario.scenario)}: ${scenario.explanation}`
    ));
}

function abstentionExplanation(
  sufficiency: MarketEvidenceSufficiency | string,
  abstentionReason: string | null | undefined,
) {
  if (abstentionReason) return [abstentionReason];
  if (sufficiency === "not_supported") {
    return ["This result is not supported; no separate reason is available."];
  }
  if (sufficiency === "insufficient_evidence") {
    return ["Evidence is insufficient; no separate reason is available."];
  }
  return ["This ranking includes a supported result."];
}

function RankingCard({
  item,
  onCompare,
  onOpenProfile,
  selected,
}: {
  item: ExplainableRankingItem;
  onCompare: () => void;
  onOpenProfile: () => void;
  selected: boolean;
}) {
  const confidence = confidencePresentation(item.confidence);
  const freshness = freshnessPresentation(item.freshness);
  const decision = decisionStatePresentation({
    evidenceSufficiency: item.evidence_sufficiency,
    isProvisional: item.is_provisional,
    scoreMargin: item.grounding?.score_margin,
  });
  const basis = evidenceBasisPresentation(item.evidence_basis);
  const abstains = isAbstentionSufficiency(item.evidence_sufficiency);
  return (
    <article className={selected ? "market-card market-card-static intelligence-rank-card selected-rank-card" : "market-card market-card-static intelligence-rank-card"}>
      <div className="market-card-topline">
        <span>{abstains ? "Evidence order" : "Rank"} #{item.rank}</span>
        <span className={decision.className}>{decision.label}</span>
        <span className={confidence.className}>{confidence.label}</span>
        <span className={freshness.className}>{freshness.label}</span>
      </div>
      <strong>{safePublicText(item.market_name, item.market_key)}</strong>
      <small>
        {scoreLabel(item.score)} · {basis.label} · {abstains
          ? "evidence order, not a recommendation"
          : "comparative, not a probability"}
      </small>
      <ContradictionList
        compact
        findings={item.contradictions}
        status={item.contradiction_status}
      />
      {item.ranking_drivers.length ? (
        <p className="meta-copy">
          Top signals: {item.ranking_drivers.slice(0, 2).map((driver) => (
            intelligenceText(driver.label || humanizeKey(driver.code))
          )).join(" · ")}
        </p>
      ) : null}
      <details className="method-details rank-evidence-details">
        <summary>Evidence details</summary>
        <DriverList drivers={item.ranking_drivers} />
        <InlineList title="Strengths" items={item.strengths} />
        <InlineList title="Caveats" items={item.limitations.length ? item.limitations : item.weaknesses} />
      </details>
      <div className="hero-actions">
        <button type="button" onClick={onOpenProfile}>Open profile</button>
        <button className="secondary-button" type="button" onClick={onCompare}>Compare</button>
      </div>
    </article>
  );
}

function MarketProfileSection({
  loading,
  error,
  profile,
}: {
  loading: boolean;
  error: string | null;
  profile: MarketIntelligenceProfile | null;
}) {
  if (loading && !profile) return <LoadingBlock label="Loading market profile" />;
  if (error && !profile) return <ErrorState message={error} />;
  if (!profile) {
    return (
      <EmptyState
        body="Choose a ranked market to inspect its profile."
        title="No market profile selected"
      />
    );
  }
  const confidence = confidencePresentation(profile.confidence);
  const freshness = freshnessPresentation(profile.freshness);
  return (
    <section className="card market-profile-card">
      <div className="card-header">
        <div>
          <p className="card-eyebrow">Market profile</p>
          <h2>{safePublicText(profile.market_name, profile.market_key)}</h2>
        </div>
        <div className="metadata-row">
          <span className={confidence.className}>{confidence.label}</span>
          <span className={freshness.className}>{freshness.label}</span>
        </div>
      </div>
      {error ? <ErrorState message={error} /> : null}
      <p className="lead-copy">{safePublicText(profile.overview)}</p>
      <div className="split-grid">
        <InsightSection title="Key strengths" insights={profile.strengths} empty="No distinct strengths are available." />
        <InsightSection title="Known weaknesses" insights={profile.weaknesses} empty="No distinct weaknesses are available." />
      </div>
      <section className="opportunity-environment" aria-label="Opportunity environment">
        <h3>Opportunity environment</h3>
        <div className="stack-list">
          <EnvironmentRow label="Employer environment" value={profile.employer_summary} />
          <EnvironmentRow label="Hiring environment" value={profile.hiring_summary} />
          <EnvironmentRow label="Internship ecosystem" value={profile.internship_summary} />
          <EnvironmentRow label="Co-op ecosystem" value={profile.coop_summary} />
          <EnvironmentRow label="Early-career environment" value={profile.early_career_summary} />
          <EnvironmentRow label="Hiring momentum" value={profile.opportunity_environment.hiring_momentum} />
        </div>
      </section>
      <p className="meta-copy">{confidence.help} {freshness.help}</p>
      <details className="method-details intelligence-evidence-details">
        <summary>Supporting evidence and coverage</summary>
        <MetricGrid metrics={profile.supporting_metrics} />
        <p className="meta-copy">
          Unknown and observed-zero facts remain distinct; unavailable evidence is not treated as zero.
        </p>
        <p>{intelligenceText(profile.coverage_summary)}</p>
        <LimitationList limitations={profile.limitations} />
      </details>
    </section>
  );
}

function ComparisonPanel({ comparison }: { comparison: MarketComparisonReport | null }) {
  if (!comparison) {
    return (
      <EmptyState
        body="Select two distinct markets to load a goal-specific comparison."
        title="No comparison loaded"
      />
    );
  }
  const confidence = confidencePresentation(comparison.confidence);
  const decision = decisionStatePresentation({
    evidenceSufficiency: comparison.evidence_sufficiency,
    isProvisional: comparison.is_provisional,
    scoreMargin: comparison.grounding?.score_margin,
    comparisonOutcome: comparison.outcome,
  });
  const sufficiency = evidenceSufficiencyPresentation(comparison.evidence_sufficiency);
  const stability = stabilityPresentation(comparison.grounding?.stability_status);
  const abstains = isAbstentionSufficiency(comparison.evidence_sufficiency);
  const outcome = abstains
    ? "There is not enough evidence to name a winner."
    : comparison.outcome === "tie"
    ? "These demonstration markets are tied for this goal based on the fixture evidence."
    : comparison.winner_market_key
      ? `${winnerName(comparison)} is the stronger fit within the demonstration dataset.`
      : comparisonOutcomeLabel(comparison.outcome);
  return (
    <div className="market-comparison-panel">
      <div className="objective-winner-panel">
        <div>
          <div className="decision-state-row" aria-label="Comparison decision states">
            <span className={decision.className}>{decision.label}</span>
            <span className={sufficiency.className}>{sufficiency.label}</span>
            <span className={confidence.className}>{confidence.label}</span>
            <span className={stability.className}>{stability.label}</span>
          </div>
          <h3>{abstains ? "No supported winner" : comparisonOutcomeLabel(comparison.outcome)}</h3>
          <p className="lead-copy">{outcome}</p>
          <p className="meta-copy">{intelligenceText(comparison.explanation)}</p>
          <AbstentionNotice
            abstentionReason={comparison.abstention_reason}
            sufficiency={comparison.evidence_sufficiency}
          />
          <ContradictionList
            findings={comparison.contradictions}
            status={comparison.contradiction_status}
          />
        </div>
        <div className="objective-score-grid">
          <MetricValue label={comparison.market_a.market_name} value={scoreLabel(comparison.market_a.score)} />
          <MetricValue label={comparison.market_b.market_name} value={scoreLabel(comparison.market_b.score)} />
        </div>
      </div>
      <details className="method-details intelligence-evidence-details">
        <summary>Comparison evidence</summary>
        <div className="split-grid">
          <ComparisonSide side={comparison.market_a} title="Market A" />
          <ComparisonSide side={comparison.market_b} title="Market B" />
        </div>
        <InlineList
          title="Stability scenarios"
          items={stabilityScenarioItems(comparison.grounding)}
        />
        <MetricGrid metrics={comparison.supporting_metrics} />
        <LimitationList limitations={comparison.limitations} />
      </details>
    </div>
  );
}

function AbstentionNotice({
  abstentionReason,
  sufficiency,
}: {
  abstentionReason: string | null | undefined;
  sufficiency: MarketEvidenceSufficiency | string;
}) {
  if (!abstentionReason && sufficiency !== "insufficient_evidence" && sufficiency !== "not_supported") {
    return null;
  }
  return (
    <section className="abstention-notice" aria-label="Abstention explanation">
      <h4>Abstention explanation</h4>
      <p>
        {safePublicText(
          abstentionReason,
          sufficiency === "not_supported"
            ? "This comparison is not supported."
            : "This comparison has insufficient evidence.",
        )}
      </p>
    </section>
  );
}

function ComparisonSide({
  side,
  title,
}: {
  side: MarketComparisonReport["market_a"];
  title: string;
}) {
  const basis = evidenceBasisPresentation(side.evidence_basis);
  const sufficiency = evidenceSufficiencyPresentation(side.evidence_sufficiency);
  return (
    <article className="source-compare-card">
      <h3>{title}</h3>
      <strong>{safePublicText(side.market_name, side.market_key)}</strong>
      <div className="decision-state-row">
        <span className={confidencePresentation(side.confidence).className}>
          {confidencePresentation(side.confidence).label}
        </span>
        <span className={sufficiency.className}>{sufficiency.label}</span>
      </div>
      <p className="meta-copy">{basis.label}</p>
      <InlineList title="Strengths" items={side.strengths} />
      <InlineList title="Weaknesses" items={side.weaknesses} />
      <MetricGrid metrics={side.supporting_metrics} compact />
    </article>
  );
}

function DriverList({ drivers }: { drivers: ExplainableRankingItem["ranking_drivers"] }) {
  if (!drivers.length) {
    return <p className="meta-copy">No ranking drivers were returned.</p>;
  }
  return (
    <ol className="driver-list" aria-label="Ranking drivers">
      {drivers.map((driver) => (
        <li key={`${driver.code}-${driver.label}`}>
          <strong>{safePublicText(driver.label, humanizeKey(driver.code))}</strong>
          <span>{contributionLabel(driver.contribution)}</span>
          <p>{intelligenceText(driver.evidence)}</p>
        </li>
      ))}
    </ol>
  );
}

function ContradictionList({
  findings,
  status,
  compact = false,
}: {
  findings: MarketContradictionFinding[];
  status: MarketContradictionStatus;
  compact?: boolean;
}) {
  if (!findings.length && status !== "blocking" && status !== "warnings") return null;
  const title = status === "blocking"
    ? "Contradiction review blocked recommendation"
    : "Contradiction review warnings";
  return (
    <section
      aria-label="Contradiction review"
      className={compact ? "contradiction-block compact-contradictions" : "contradiction-block"}
    >
      <h3>{title}</h3>
      {findings.length ? (
        <ul>
          {findings.map((finding) => (
            <li key={`${finding.code}-${finding.evidence}`}>
              <strong>{safePublicText(finding.message, humanizeKey(finding.code))}</strong>
              <span>{safePublicText(finding.evidence)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="meta-copy">Contradiction details are unavailable.</p>
      )}
    </section>
  );
}

function InsightSection({
  title,
  insights,
  empty,
}: {
  title: string;
  insights: MarketIntelligenceInsight[];
  empty: string;
}) {
  return (
    <section>
      <h3>{title}</h3>
      {insights.length ? (
        <div className="stack-list">
          {insights.map((insight) => (
            <div className="stack-row" key={insight.code}>
              <strong>{intelligenceText(insight.message)}</strong>
              {insight.impact && intelligenceText(insight.impact).toLowerCase() !== "coverage" ? (
                <small>{intelligenceText(insight.impact)}</small>
              ) : null}
            </div>
          ))}
        </div>
      ) : (
        <p className="meta-copy">{empty}</p>
      )}
    </section>
  );
}

function InlineList({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="inline-intel-list">
      <span>{title}</span>
      <ul>
        {items.slice(0, 3).map((item, index) => (
          <li key={`${title}-${index}-${item}`}>{intelligenceText(item)}</li>
        ))}
      </ul>
    </div>
  );
}

function LimitationList({ limitations }: { limitations: string[] }) {
  if (!limitations.length) {
    return null;
  }
  return (
    <details className="method-details limitations-block" aria-label="Important limitations">
      <summary>{limitations.length} evidence limitation{limitations.length === 1 ? "" : "s"}</summary>
      <ul>
        {limitations.map((limitation, index) => (
          <li key={`limitation-${index}-${limitation}`}>{intelligenceText(limitation)}</li>
        ))}
      </ul>
    </details>
  );
}

function MetricGrid({
  metrics,
  compact = false,
}: {
  metrics: MarketIntelligenceSupportingMetrics;
  compact?: boolean;
}) {
  const entries = METRIC_KEYS
    .filter((key) => key in metrics)
    .map((key) => [key, metrics[key]] as const);
  if (!entries.length) {
    return <p className="meta-copy">Supporting metrics are unavailable.</p>;
  }
  return (
    <div className={compact ? "market-card-metrics compact-metrics" : "market-card-metrics"}>
      {entries.map(([key, value]) => (
        <MetricValue key={key} label={metricLabel(key)} value={formatMetricValue(value)} />
      ))}
    </div>
  );
}

function MetricValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat-card">
      <span>{safePublicText(label)}</span>
      <strong>{safePublicText(value)}</strong>
    </div>
  );
}

function EnvironmentRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="stack-row">
      <strong>{label}</strong>
      <span>{safePublicText(value)}</span>
    </div>
  );
}

function LoadingBlock({ label }: { label: string }) {
  return (
    <div className="loading-block" role="status" aria-live="polite">
      <span />
      {label}
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="error-state" role="alert">
      <strong>Request failed</strong>
      <p>{safePublicText(message, "Market intelligence is unavailable.")}</p>
    </div>
  );
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <p>{body}</p>
    </div>
  );
}

function mergeGoalDefinitions(
  definitions: MarketIntelligenceGoalDefinition[],
  rankingDefinition?: MarketIntelligenceGoalDefinition,
) {
  const byGoal = new Map<string, MarketIntelligenceGoalDefinition>();
  for (const definition of definitions) byGoal.set(definition.goal, definition);
  if (rankingDefinition) byGoal.set(rankingDefinition.goal, rankingDefinition);
  if (!byGoal.size) {
    byGoal.set(DEFAULT_MARKET_INTELLIGENCE_GOAL, {
      goal: DEFAULT_MARKET_INTELLIGENCE_GOAL,
      label: goalLabel(DEFAULT_MARKET_INTELLIGENCE_GOAL),
      description: "Default market intelligence goal.",
      direct_signals: [],
      limitations: [],
    });
  }
  return [...byGoal.values()];
}

function marketOptions(platform: PlatformMarketIntelligencePayload | null) {
  const profiles = platform?.profiles ?? [];
  return profiles.map((profile) => ({
    market_key: profile.market_key,
    market_name: profile.market_name,
  }));
}

function winnerName(comparison: MarketComparisonReport): string {
  if (comparison.winner_market_key === comparison.market_a.market_key) {
    return comparison.market_a.market_name;
  }
  if (comparison.winner_market_key === comparison.market_b.market_key) {
    return comparison.market_b.market_name;
  }
  return "No market";
}

function rankingSummary(ranking: ExplainableRankingReport, goal: string): string {
  const top = topDecisionItem(ranking);
  if (!top) {
    return intelligenceText(
      ranking.abstention_reason || `There is not enough evidence for a ${goal} recommendation.`,
    );
  }
  const suffix = ranking.is_provisional
    ? " Confidence is limited, so treat the order as provisional."
    : "";
  return `${safePublicText(top.market_name, top.market_key)} currently leads for ${goal.toLowerCase()}.${suffix}`;
}

function intelligenceText(value: string | null | undefined): string {
  return safePublicText(value, "")
    .replace(/\bThe backend reports\b/gi, "Available evidence shows")
    .replace(/\bBackend score margin\b/gi, "Score margin")
    .replace(/\bbackend confidence\b/gi, "confidence")
    .replace(/\bis supported by canonical metric value\b/gi, "is based on an observed value of")
    .replace(/\bcanonical metric value\b/gi, "observed value")
    .replace(/\bbackend stability analysis\b/gi, "stability analysis");
}

function isAbstentionSufficiency(
  sufficiency: MarketEvidenceSufficiency | string | null | undefined,
) {
  return sufficiency === "insufficient_evidence" || sufficiency === "not_supported";
}
