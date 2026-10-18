import { useEffect, useMemo, useRef, useState } from "react";
import {
  ApiError,
  compareExploreMarkets,
  getExploreComparison,
  prioritizeExploreComparison,
  recordProductEvent,
  saveExploreComparison,
  type ProtectedRequestOptions,
} from "./api";
import type { FrontendAuthContextValue } from "./auth";
import { canonicalizeExploreGeography } from "./exploreGeography";
import type {
  ExploreComparisonMarket,
  ExploreComparisonResult,
  ExplorePrioritization,
  ExploreSessionOverrides,
} from "./types";
import {
  currentOpportunitiesUrl,
  decisionsUrl,
  exploreComparisonUrl,
  exploreUrl,
  mySearchUrl,
  savedExploreComparisonUrl,
  type ExploreUrlState,
} from "./urlState";

type Props = {
  auth: FrontendAuthContextValue;
  state: ExploreUrlState;
  savedComparisonId?: string;
  onNavigate: (url: string, options?: { replace?: boolean }) => void;
};

function errorMessage(error: unknown): string {
  return error instanceof ApiError || error instanceof Error
    ? error.message
    : "Comparison is unavailable.";
}

function pretty(value: string | null | undefined): string {
  return value
    ? value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase())
    : "Not available";
}

function readableSummary(value: string): string {
  return value
    .replace(" signal signal", " signal")
    .replace(/([^.!?]*(?:,| and )[^.!?]*) has the strongest/g, "$1 have the strongest")
    .replace(/\bgoverned\b/gi, "observed")
    .replace(/ is supported by canonical metric value [\d.]+/gi, " is supported by available evidence")
    .replace(/current jobs and company counts did not affect this result/gi, "Current opportunities are shown separately")
    .replace(/Unknown count facts/gi, "some market counts")
    .replace(/are missing some market counts evidence/gi, "have incomplete market-count evidence");
}

function sessionOverrides(state: ExploreUrlState): ExploreSessionOverrides {
  return {
    goal: state.goal,
    industries: state.industries.length ? state.industries : undefined,
    opportunity_types: state.opportunityTypes.length ? state.opportunityTypes : undefined,
    work_arrangements: state.workArrangements.length ? state.workArrangements : undefined,
    geographic_scope: state.geographicScope.length
      ? { region_refs: state.geographicScope }
      : undefined,
  };
}

function stateHeading(result: ExploreComparisonResult): string {
  const names = new Map(
    result.compared_markets.map((market) => [
      market.fit.region.region_id,
      market.fit.region.display_name,
    ]),
  );
  const winners = result.winner_region_ids.map((id) => names.get(id) ?? id);
  if (result.recommendation_state === "clear_recommendation") {
    return `${winners[0]} is the best-supported choice`;
  }
  if (result.recommendation_state === "near_tie") {
    return `${winners.join(" and ")} are effectively tied`;
  }
  if (result.recommendation_state === "exact_tie") {
    return `${winners.join(" and ")} are tied`;
  }
  if (result.recommendation_state === "blocking_contradiction") {
    return "Conflicting evidence blocks a recommendation";
  }
  if (result.recommendation_state === "unsupported_member") {
    return "One selected market is not supported";
  }
  if (result.recommendation_state === "outside_constraints") {
    return "One selected market is outside your search constraints";
  }
  return "There is not enough evidence to recommend one market";
}

function marketFitLabel(market: ExploreComparisonMarket): string {
  if (market.fit.fit_band) return pretty(market.fit.fit_band);
  return pretty(market.fit.state);
}

function MarketComparisonCard({ market, onNavigate }: { market: ExploreComparisonMarket; onNavigate: Props["onNavigate"] }) {
  const jobs = market.fit.opportunity_coverage;
  return (
    <article className="comparison-market-card">
      <header>
        <div>
          <p className="eyebrow">
            {market.comparison_rank ? `Comparison rank ${market.comparison_rank}` : "No supported rank"}
          </p>
          <h3>{market.fit.region.display_name}</h3>
        </div>
        <span className={`fit-state fit-state-${market.fit.state}`}>
          <strong>{marketFitLabel(market)}</strong>
          <small>{pretty(market.fit.confidence)} confidence</small>
        </span>
      </header>
      <section>
        <h4>Strongest reason to choose it</h4>
        <p>{market.key_advantages[0] ? readableSummary(market.key_advantages[0]) : "No distinct advantage is supported."}</p>
      </section>
      <section>
        <h4>Biggest tradeoff</h4>
        <p>{readableSummary(market.key_tradeoffs[0])}</p>
      </section>
      <p className="comparison-caveat">{readableSummary(market.confidence_caveat)}</p>
      <button
        className="secondary-button comparison-opportunity-action"
        onClick={() => onNavigate(currentOpportunitiesUrl({ market: market.fit.region.region_id }))}
        type="button"
      >
        {`View opportunities in ${market.fit.region.primary_city ?? market.fit.region.display_name}`}
      </button>
      <details>
        <summary>Evidence and coverage</summary>
        <p>{market.fit.market_coverage.summary}</p>
        {market.missing_evidence.length ? (
          <p>Missing: {market.missing_evidence.map(pretty).join(", ")}.</p>
        ) : (
          <p>No evidence areas were marked missing.</p>
        )}
        <h4>Current opportunities — supporting evidence only</h4>
        <p>
          {jobs.active_opportunity_count} observed active · {jobs.ranking_eligible_opportunity_count} matching · {pretty(jobs.status)} coverage · {jobs.fresh_opportunity_count} fresh
        </p>
        <h4>Company evidence — supporting evidence only</h4>
        {market.company_evidence.length ? (
          <ul>
            {market.company_evidence.map((company) => (
              <li key={company.company_id}>
                {company.company_name} — {company.evidence_kind === "current_hiring" ? "current hiring evidence" : "presence evidence, not active hiring"}
              </li>
            ))}
          </ul>
        ) : (
          <p>No company evidence is available.</p>
        )}
      </details>
    </article>
  );
}

export default function ExploreComparisonPage({
  auth,
  state,
  savedComparisonId,
  onNavigate,
}: Props) {
  const [result, setResult] = useState<ExploreComparisonResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadNonce, setReloadNonce] = useState(0);
  const [savedId, setSavedId] = useState<string | null>(savedComparisonId ?? null);
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [priorityTarget, setPriorityTarget] = useState("");
  const [prioritizing, setPrioritizing] = useState(false);
  const [prioritization, setPrioritization] = useState<ExplorePrioritization | null>(null);
  const [canonicalLiveState, setCanonicalLiveState] = useState<ExploreUrlState | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const viewed = useRef(new Set<string>());
  const prioritizeButtonRef = useRef<HTMLButtonElement>(null);
  const successHeadingRef = useRef<HTMLHeadingElement>(null);
  const authOptions = useMemo<ProtectedRequestOptions>(
    () => ({ getAccessToken: auth.getAccessTokenSilently }),
    [auth.getAccessTokenSilently],
  );
  const liveState = canonicalLiveState ?? state;
  const overrides = useMemo(() => sessionOverrides(liveState), [liveState]);
  const requestKey = JSON.stringify([savedComparisonId, state.selected, overrides]);

  useEffect(() => {
    if (auth.isLoading) return;
    if (!auth.isAuthenticated) {
      setLoading(false);
      setError("Sign in to compare markets.");
      return;
    }
    let active = true;
    let normalizing = false;
    setLoading(true);
    setError(null);
    const request = savedComparisonId
      ? getExploreComparison(savedComparisonId, authOptions).then((envelope) => envelope.data?.comparison.result)
      : canonicalizeExploreGeography(state).then((canonical) => {
          if (!active) return null;
          setCanonicalLiveState(canonical);
          if (canonical.selected.join(",") !== state.selected.join(",")) {
            normalizing = true;
            onNavigate(exploreComparisonUrl(canonical), { replace: true });
            return null;
          }
          if (canonical.selected.length < 2 || canonical.selected.length > 4) {
            throw new Error("Choose 2–4 unique markets in Explore before comparing.");
          }
          return compareExploreMarkets(
            canonical.selected,
            sessionOverrides(canonical),
            authOptions,
          ).then((envelope) => envelope.data);
        });
    request
      .then((comparison) => {
        if (!active) return;
        if (normalizing) return;
        if (!comparison) throw new Error("Comparison returned no result.");
        setResult(comparison);
        const defaultTarget = comparison.recommendation_state === "clear_recommendation"
          ? comparison.winner_region_ids[0] ?? ""
          : "";
        setPriorityTarget(defaultTarget);
        setAnnouncement(stateHeading(comparison));
      })
      .catch((reason) => active && setError(errorMessage(reason)))
      .finally(() => active && !normalizing && setLoading(false));
    return () => { active = false; };
  // requestKey captures the canonical selected/context state.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.isAuthenticated, auth.isLoading, authOptions, reloadNonce, requestKey, savedComparisonId]);

  useEffect(() => {
    if (prioritization) successHeadingRef.current?.focus();
  }, [prioritization]);

  useEffect(() => {
    if (!result) return;
    const event = result.abstained
      ? "comparison_abstained_viewed" as const
      : "comparison_recommendation_viewed" as const;
    const key = `${event}:${result.comparison_identity}`;
    if (viewed.current.has(key)) return;
    viewed.current.add(key);
    void recordProductEvent({
      event_type: event,
      event_source: "frontend",
      product_surface: "explore_comparison",
      confidence_bucket: result.confidence,
      recommendation_state: result.recommendation_state,
      payload: {
        comparison_identity: result.comparison_identity,
        context_fingerprint: result.context_fingerprint,
        market_count: result.compared_markets.length,
      },
    }, authOptions).catch(() => undefined);
  }, [authOptions, result]);

  async function save() {
    if (!result || saving || savedId) return;
    setSaving(true);
    try {
      const envelope = await saveExploreComparison({
        market_refs: liveState.selected,
        session_overrides: overrides,
        comparison_identity: result.comparison_identity,
      }, authOptions);
      const id = envelope.data?.comparison.comparison_id;
      if (!id) throw new Error("Saved comparison returned no ID.");
      setSavedId(id);
      setAnnouncement("Comparison saved. It is now available in My Search.");
    } catch (reason) {
      setAnnouncement(`Could not save comparison: ${errorMessage(reason)}`);
    } finally {
      setSaving(false);
    }
  }

  async function prioritize() {
    if (!result || !priorityTarget || prioritizing) return;
    setPrioritizing(true);
    try {
      const envelope = await prioritizeExploreComparison(
        savedComparisonId
          ? { selected_market_ref: priorityTarget, comparison_id: savedComparisonId }
          : {
              selected_market_ref: priorityTarget,
              comparison_identity: result.comparison_identity,
              market_refs: liveState.selected,
              session_overrides: overrides,
            },
        authOptions,
      );
      const next = envelope.data?.prioritization;
      if (!next) throw new Error("Prioritize returned no Decision.");
      setPrioritization(next);
      setConfirming(false);
      setAnnouncement(`${next.decision.title} is now active in My Search.`);
    } catch (reason) {
      setAnnouncement(`Could not prioritize market: ${errorMessage(reason)}`);
    } finally {
      setPrioritizing(false);
    }
  }

  if (loading) return <div className="product-empty" role="status">Comparing selected markets…</div>;
  if (error || !result) {
    return <div className="product-empty" role="alert"><h1>Comparison unavailable</h1><p>{error ?? "No comparison result was returned."}</p>{auth.isAuthenticated ? <button onClick={() => setReloadNonce((value) => value + 1)} type="button">Try again</button> : null}<button onClick={() => onNavigate(exploreUrl(state))} type="button">Return to Explore</button></div>;
  }

  const chosen = result.compared_markets.find((market) => market.fit.region.region_id === priorityTarget);
  const recommendationMatches = priorityTarget && result.winner_region_ids.length
    ? result.winner_region_ids.includes(priorityTarget)
    : null;
  const closeConfirmation = () => {
    setConfirming(false);
    window.setTimeout(() => prioritizeButtonRef.current?.focus(), 0);
  };
  return (
    <div className="explore-comparison-page">
      <div aria-atomic="true" aria-live="polite" className="sr-only">{announcement}</div>
      <nav aria-label="Comparison context" className="comparison-back-row">
        <button className="text-button" onClick={() => onNavigate(exploreUrl({ ...state, selected: result.compared_markets.map((market) => market.fit.region.public_slug ?? market.fit.region.region_id) }))} type="button">← Back to Explore</button>
        {savedComparisonId ? <span>Historical saved snapshot</span> : <span>Current comparison</span>}
      </nav>

      <section aria-labelledby="comparison-title" className={`comparison-hero comparison-state-${result.recommendation_state}`}>
        <p className="eyebrow">{savedComparisonId ? "Saved comparison" : "Explore comparison"}</p>
        <h1 id="comparison-title">{stateHeading(result)}</h1>
        <p>{readableSummary(result.abstention_reason ?? result.recommendation_summary)}</p>
        <div className="comparison-summary-meta">
          <span>{pretty(result.confidence)} confidence</span>
          <span>{result.compared_markets.length} markets</span>
          <span>Generated {new Date(result.generated_at).toLocaleString()}</span>
        </div>
        <div className="comparison-primary-actions">
          {!savedComparisonId ? <button disabled={Boolean(savedId) || saving} onClick={() => void save()} type="button">{savedId ? "Saved ✓" : saving ? "Saving…" : "Save comparison"}</button> : null}
          <button className="secondary-button" onClick={() => setConfirming(true)} ref={prioritizeButtonRef} type="button">Prioritize</button>
          {savedComparisonId ? <button className="secondary-button" onClick={() => onNavigate(exploreComparisonUrl({ selected: result.compared_markets.map((market) => market.fit.region.public_slug ?? market.fit.region.region_id), view: "list" }))} type="button">Compare these markets again with current data</button> : null}
          {savedId && !savedComparisonId ? <button className="text-button" onClick={() => onNavigate(savedExploreComparisonUrl(savedId))} type="button">Open saved snapshot</button> : null}
        </div>
      </section>

      {result.differentiating_factors.length ? <section aria-labelledby="difference-title" className="comparison-factors">
        <div><p className="eyebrow">Key differences</p><h2 id="difference-title">Biggest differentiators</h2></div>
        <ul>{result.differentiating_factors.slice(0, 4).map((factor) => <li key={factor.code}><strong>{factor.label}</strong><span>{readableSummary(factor.summary)}</span></li>)}</ul>
      </section> : null}

      {result.shared_strengths.length || result.shared_weaknesses.length ? (
        <section className="comparison-shared" aria-labelledby="shared-title">
          <h2 id="shared-title">Where the markets are similar</h2>
          <ul>{[...result.shared_strengths, ...result.shared_weaknesses].map((factor) => <li key={factor.code}>{readableSummary(factor.summary)}</li>)}</ul>
        </section>
      ) : null}

      <section aria-labelledby="market-cards-title">
        <h2 id="market-cards-title">Market tradeoffs</h2>
        <div className="comparison-market-cards">{result.compared_markets.map((market) => <MarketComparisonCard key={market.fit.region.region_id} market={market} onNavigate={onNavigate} />)}</div>
      </section>

      <section className="comparison-table-section" aria-labelledby="compact-title">
        <h2 id="compact-title">At a glance</h2>
        <div className="comparison-table-wrap">
          <table>
            <caption className="sr-only">Fit, confidence, tradeoffs, and current-opportunity coverage for selected markets.</caption>
            <thead><tr><th scope="col">Market</th><th scope="col">Fit</th><th scope="col">Confidence</th><th scope="col">Key driver</th><th scope="col">Tradeoff</th><th scope="col">Current-job coverage</th></tr></thead>
            <tbody>{result.compared_markets.map((market) => <tr key={market.fit.region.region_id}><th scope="row">{market.fit.region.display_name}</th><td>{marketFitLabel(market)}</td><td>{pretty(market.fit.confidence)}</td><td>{market.key_advantages[0] ? readableSummary(market.key_advantages[0]) : "No distinct advantage"}</td><td>{readableSummary(market.key_tradeoffs[0])}</td><td>{pretty(market.fit.opportunity_coverage.status)} · {market.fit.opportunity_coverage.active_opportunity_count} observed</td></tr>)}</tbody>
          </table>
        </div>
      </section>

      {confirming ? (
        <section aria-labelledby="prioritize-title" aria-modal="true" className="prioritize-confirmation" role="dialog">
          <h2 id="prioritize-title">Choose a market to prioritize</h2>
          <p>Add one market to My Search. The comparison result will remain unchanged.</p>
          <label>Market<select autoFocus onChange={(event) => setPriorityTarget(event.target.value)} value={priorityTarget}><option value="">Select a market</option>{result.compared_markets.filter((market) => market.fit.state !== "hard_constraint_excluded").map((market) => <option key={market.fit.region.region_id} value={market.fit.region.region_id}>{market.fit.region.display_name}</option>)}</select></label>
          {chosen ? <p><strong>Prioritize {chosen.fit.region.display_name}?</strong> This will add it to My Search as an active decision.{result.winner_region_ids.length === 0 ? ` You’re choosing ${chosen.fit.region.display_name} even though the comparison did not recommend a single market.` : recommendationMatches === false ? " Your choice differs from the system recommendation and both will be preserved." : ""}</p> : <p>Select the market you want to pursue.</p>}
          <div><button disabled={!priorityTarget || prioritizing} onClick={() => void prioritize()} type="button">{prioritizing ? "Prioritizing…" : chosen ? `Prioritize ${chosen.fit.region.display_name}` : "Prioritize"}</button><button className="secondary-button" onClick={closeConfirmation} type="button">Cancel</button></div>
        </section>
      ) : null}

      {prioritization ? <section className="comparison-success" role="status"><h2 ref={successHeadingRef} tabIndex={-1}>Added to My Search</h2><p>{prioritization.created ? "A durable active decision was created." : "Your existing equivalent active decision was reused."}</p><div><button onClick={() => onNavigate(mySearchUrl())} type="button">Open My Search</button><button className="secondary-button" onClick={() => onNavigate(decisionsUrl(prioritization.decision_id))} type="button">Open Decision</button></div></section> : null}

      <details className="comparison-methodology"><summary>Method and evidence</summary><p>Fit, rank, ties, and abstention use market evidence. Current opportunities and employer evidence are shown separately.</p><dl><dt>Context fingerprint</dt><dd>{result.context_fingerprint}</dd><dt>Fit algorithm</dt><dd>{result.algorithm_version}</dd><dt>Evidence authority</dt><dd>{result.evidence_authority_version}</dd><dt>Calibration</dt><dd>{result.calibration_version}</dd></dl></details>
    </div>
  );
}
