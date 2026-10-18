import type { ReactNode } from "react";

import type {
  ApiEnvelope,
  CareerIdentityPersonalizationMetadata,
  PersonalizedResult,
  RecommendationGoalMode,
  RecommendationGoalModeProfilePayload,
  RecommendationGoalModesPayload,
  RecommendationRankingItem,
  RecommendationStrategyPayload,
  StrategyEvidenceWarning,
  StrategyRegionTarget,
  StrategyWatchlistItem,
} from "./types";
import {
  careerIdentityUrl,
  currentOpportunitiesUrl,
  decisionsUrl,
  exploreUrl,
  type RecommendationView,
} from "./urlState";

export type RecommendationLoadState<T> = {
  loading: boolean;
  envelope: ApiEnvelope<T> | null;
  error: string | null;
};

type Props = {
  activeView: RecommendationView;
  authenticated: boolean;
  goalModesState: RecommendationLoadState<RecommendationGoalModesPayload>;
  onNavigate: (url: string, options?: { replace?: boolean }) => void;
  onRetryPersonalized: () => void;
  onSelectGoalMode: (goalMode: RecommendationGoalMode) => void;
  onSelectView: (view: RecommendationView) => void;
  personalizedState: RecommendationLoadState<PersonalizedResult>;
  selectedGoalMode: RecommendationGoalMode;
  strategyState: RecommendationLoadState<RecommendationStrategyPayload>;
};

const DEFAULT_GOAL: RecommendationGoalMode = "maximize_entry_level_access";

function label(value: string | null | undefined): string {
  return value
    ? value
      .replaceAll("_", " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase())
      .replace(/\bAi\b/g, "AI")
      .replace(/\bNyc\b/g, "NYC")
    : "Not available";
}

function humanText(value: string): string {
  return value
    .replace(/\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b/g, (token) => token.replaceAll("_", " "))
    .replace(/Missing component ([^:]+): Treat as unavailable and surface a missing-data weakness; do not impute\.?/i, (_, component: string) => `${component.replaceAll(" or ", " or ")} is unavailable for this market.`)
    .replace(/Coverage warning attached to ranked recommendation/i, "Some ranked results have limited coverage.")
    .replace(/Fallback target selected from ranked recommendations with useful tradeoffs\.?/i, "A supported alternative with different trade-offs.");
}

function percent(value: number | null | undefined): string {
  return typeof value === "number" ? `${Math.round(value * 100)}%` : "Not available";
}

function targetName(item: RecommendationRankingItem | StrategyRegionTarget): string {
  return item.target.display_label ?? label(item.target.target_id);
}

function LinkButton({ children, className = "secondary-button", onNavigate, url }: {
  children: ReactNode;
  className?: string;
  onNavigate: Props["onNavigate"];
  url: string;
}) {
  return (
    <a className={className} href={url} onClick={(event) => {
      if (event.button !== 0 || event.metaKey || event.altKey || event.ctrlKey || event.shiftKey) return;
      event.preventDefault();
      onNavigate(url);
    }}>
      {children}
    </a>
  );
}

function LoadingBlock({ label: loadingLabel = "Building recommendations…" }: { label?: string }) {
  return <div className="loading-block" role="status"><span />{loadingLabel}</div>;
}

function ErrorBlock({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="error-state" role="alert"><strong>Recommendations are unavailable</strong><p>{message}</p>{onRetry ? <button className="secondary-button" onClick={onRetry} type="button">Retry For You</button> : null}</div>;
}

function GoalSelector({ goals, loading, selected, onSelect }: {
  goals: RecommendationGoalModeProfilePayload[];
  loading: boolean;
  selected: RecommendationGoalMode;
  onSelect: Props["onSelectGoalMode"];
}) {
  const active = goals.find((goal) => goal.goal_mode === selected);
  const options = goals.length ? goals : [{
    goal_mode: DEFAULT_GOAL,
    label: "Maximize entry-level access",
    description: "Favor markets with stronger early-career access signals.",
  } as RecommendationGoalModeProfilePayload];
  return (
    <section className="recommendation-goal-panel">
      <label htmlFor="recommendation-goal-mode" id="recommendation-goal-title">What should the ranking optimize?</label>
      <select disabled={loading} id="recommendation-goal-mode" onChange={(event) => onSelect(event.target.value as RecommendationGoalMode)} value={selected}>
        {options.map((goal) => <option key={goal.goal_mode} value={goal.goal_mode}>{goal.label}</option>)}
      </select>
      <p>{active?.description ?? "Choose a goal to see a different ranking."}</p>
      {active?.weighted_components?.length ? (
        <details className="evidence-disclosure compact-disclosure">
          <summary>How this goal is weighted</summary>
          {active.prioritization_summary ? <p className="meta-copy">{active.prioritization_summary}</p> : null}
          <div className="component-chip-grid">
            {active.weighted_components.map((component) => (
              <span className={component.is_proxy ? "badge badge-warning" : "badge"} key={component.component}>
                {label(component.component)} · {Math.round(component.weight * 100)}%{component.is_proxy ? " · proxy" : ""}
              </span>
            ))}
          </div>
          {active.missing_data_behavior ? <p className="meta-copy">{active.missing_data_behavior}</p> : null}
        </details>
      ) : null}
    </section>
  );
}

function StrategyTarget({ item, tone }: { item: StrategyRegionTarget; tone: "primary" | "secondary" | "fallback" }) {
  return (
    <article className={`strategy-target strategy-target-${tone}`}>
      <div><span className="strategy-target-role">{label(tone)} target</span><h3>{targetName(item)}</h3><p>{humanText(item.rationale)}</p></div>
      <div className="strategy-target-score"><strong>{percent(item.final_score)}</strong><small>{label(item.evidence_strength)} evidence</small></div>
    </article>
  );
}

function WatchlistItem({ item }: { item: StrategyWatchlistItem }) {
  const verification = humanText(item.what_to_verify).replace(/^(?:verify\b\s*:?\s*)+/i, "");
  return (
    <article className="strategy-watch-item">
      <div><span className="badge badge-warning">Watchlist</span><strong>{item.target.display_label ?? label(item.target.target_id)}</strong></div>
      <p>{humanText(item.reason)}</p><small>Verify: {verification}</small>
    </article>
  );
}

function StrategySummary({ strategy }: { strategy: RecommendationStrategyPayload["market_strategy_plan"] }) {
  const targets = [
    ...strategy.primary_region_targets.map((item) => ({ item, tone: "primary" as const })),
    ...strategy.secondary_region_targets.map((item) => ({ item, tone: "secondary" as const })),
    ...strategy.fallback_region_targets.map((item) => ({ item, tone: "fallback" as const })),
  ];
  return (
    <section className="recommendation-strategy" aria-labelledby="strategy-title">
      <div className="section-title-row"><div><p className="eyebrow">Market strategy</p><h2 id="strategy-title">Where the evidence supports action</h2></div><span className="badge">{targets.length} actionable · {strategy.watchlist_items.length} watchlist</span></div>
      {targets.length ? <div className="strategy-targets">{targets.map(({ item, tone }) => <StrategyTarget item={item} key={`${tone}:${item.target.target_id}`} tone={tone} />)}</div> : <div className="recommendation-abstention"><strong>No market has enough support for action.</strong><p>Review the watchlist or choose another goal.</p></div>}
      {strategy.watchlist_items.length ? <details className="evidence-disclosure"><summary>{strategy.watchlist_items.length} market{strategy.watchlist_items.length === 1 ? "" : "s"} to monitor</summary><div className="strategy-watchlist-grid">{strategy.watchlist_items.map((item) => <WatchlistItem item={item} key={`${item.watchlist_category}:${item.target.target_id}`} />)}</div></details> : null}
    </section>
  );
}

function primaryReason(item: RecommendationRankingItem): string {
  const returned = item.explanation.fit_reasons[0]?.detail ?? item.explanation.fit_reasons[0]?.label ?? item.explanation.data_strengths[0]?.detail ?? item.explanation.data_strengths[0]?.label;
  if (returned && !returned.toLocaleLowerCase().startsWith("used weighted components")) return humanText(returned);
  const strongest = [...item.score_components_used].filter((component) => component.weighted_value > 0).sort((a, b) => b.weighted_value - a.weighted_value).slice(0, 2).map((component) => label(component.component).toLocaleLowerCase());
  return strongest.length ? `Strongest support comes from ${strongest.join(" and ")} under this goal.` : "This result is supported by the selected goal's available evidence.";
}

function isGenericCoverageQualification(value: string): boolean {
  const normalized = value.toLocaleLowerCase();
  return normalized.includes("coverage quality is heuristic") || normalized.includes("coverage scoring is heuristic") || normalized.includes("read with freshness/confidence") || normalized.includes("proxy components represent") || normalized.includes("geographic flexibility is a proxy") || normalized.includes("explicit ranking penalties were applied");
}

function RankingCard({ item }: { item: RecommendationRankingItem }) {
  const limitation = [...item.warnings, ...item.explanation.coverage_warnings, ...item.explanation.weaknesses.flatMap((weakness) => [weakness.detail, weakness.label])]
    .find((value): value is string => typeof value === "string" && Boolean(value) && !isGenericCoverageQualification(value));
  return (
    <article className="recommendation-result-card">
      <div className="recommendation-result-rank">#{item.rank}</div>
      <div className="recommendation-result-main">
        <div className="section-title-row"><div><p className="eyebrow">{label(item.target.target_type)}</p><h3>{targetName(item)}</h3></div><span className="recommendation-score"><strong>{percent(item.normalized_score)}</strong><small>relative fit</small></span></div>
        <p className="recommendation-rationale">{primaryReason(item)}</p>
        {limitation ? <p className="recommendation-key-limitation"><strong>Limitation:</strong> {humanText(limitation)}</p> : null}
        <details className="evidence-disclosure"><summary>Inspect scoring, trade-offs, and evidence</summary><div className="recommendation-evidence-grid">
          <section><h4>Why it fits</h4><ul>{item.explanation.fit_reasons.map((reason) => <li key={`${reason.label}:${reason.evidence_strength}`}><strong>{reason.label}</strong>{reason.detail ? ` — ${reason.detail}` : ""}</li>)}</ul></section>
          <section><h4>Trade-offs</h4>{item.explanation.tradeoffs.length ? <ul>{item.explanation.tradeoffs.map((tradeoff) => <li key={`${tradeoff.tradeoff_category}:${tradeoff.label}`}><strong>{tradeoff.label}</strong> — {tradeoff.negative_side}</li>)}</ul> : <p>No distinct trade-off was returned.</p>}</section>
          <section><h4>Score components</h4><ul>{item.score_components_used.slice(0, 8).map((component) => <li key={`${component.component}:${component.weighted_value}`}>{label(component.component)} · {Math.round(component.weight * 100)}% weight · {percent(component.weighted_value)} contribution{component.is_proxy ? " · proxy" : ""}</li>)}</ul></section>
          <section><h4>Evidence record</h4><p>{item.explanation.evidence_refs.length} references · {item.explanation.provenance_refs.length} provenance links · {item.explanation.coverage_warnings.length} coverage qualifications.</p><ul>{item.explanation.evidence_refs.slice(0, 8).map((ref, index) => <li key={`${ref.basis}:${ref.reference_id ?? index}`}>{label(ref.basis)}{ref.label ? ` · ${ref.label}` : ""} · {label(ref.strength)}</li>)}</ul></section>
        </div></details>
      </div>
    </article>
  );
}

function RankingSection({ items, title }: { items: RecommendationRankingItem[]; title: string }) {
  return <section className="recommendation-ranking" aria-label={title}><div className="section-title-row"><h2>{title}</h2><span>{items.length} ranked results</span></div>{items.length ? <div className="recommendation-result-list">{items.map((item) => <RankingCard item={item} key={`${item.target.target_type}:${item.target.target_id}`} />)}</div> : <div className="empty-state"><strong>No supported results</strong><p>There is not enough evidence to rank a target.</p></div>}</section>;
}

function WarningSummary({ strategy }: { strategy: RecommendationStrategyPayload }) {
  const evidenceWarnings = strategy.market_strategy_plan.evidence_warnings;
  const uniqueApiWarnings = Array.from(new Set(strategy.warnings));
  const material = evidenceWarnings.find((warning) => warning.warning_category.includes("coverage") || warning.warning_category.includes("freshness")) ?? evidenceWarnings[0];
  return <section className="recommendation-limitations" aria-label="Recommendation confidence and limitations"><div><p className="eyebrow">Confidence</p><h2>Evidence limitations</h2></div>{material ? <p><strong>{humanText(material.label)}</strong> Review coverage and freshness before acting.</p> : <p>No material evidence limitation was returned.</p>}{(evidenceWarnings.length || uniqueApiWarnings.length) ? <details className="evidence-disclosure"><summary>Review all {evidenceWarnings.length + uniqueApiWarnings.length} qualifications</summary><ul className="recommendation-warning-summary">{uniqueApiWarnings.map((warning) => <li key={warning}>{humanText(warning)}</li>)}{evidenceWarnings.map((warning: StrategyEvidenceWarning, index) => <li key={`${warning.warning_category}:${warning.label}:${index}`}><strong>{label(warning.warning_category)}:</strong> {warning.label}{warning.detail ? ` — ${humanText(warning.detail)}` : ""}</li>)}</ul></details> : null}</section>;
}

const OPPORTUNITY_ROLES = new Map<string, string>([
  ["applied_ai", "applied_ai"], ["applied_ai_engineer", "applied_ai"], ["ai_ml", "applied_ai"],
  ["data_ai", "data_ai"], ["data_science", "data_ai"], ["product", "product_management"],
  ["product_management", "product_management"], ["technical_product", "product_management"],
  ["solutions_engineer", "solutions_engineering"], ["solutions_engineering", "solutions_engineering"],
  ["software_engineer", "software_engineering"], ["software_engineering", "software_engineering"],
]);

function supportedOpportunityRole(metadata: CareerIdentityPersonalizationMetadata | undefined): string | undefined {
  for (const target of metadata?.role_targets ?? []) {
    const mapped = OPPORTUNITY_ROLES.get(target.trim().toLocaleLowerCase().replaceAll(" ", "_"));
    if (mapped) return mapped;
  }
  return undefined;
}

function personalizedMarketUrl(regionId: string, roleFamily: string | undefined): string {
  return roleFamily ? currentOpportunitiesUrl({ market: regionId, roleFamily, opportunityType: "job" }) : exploreUrl({ focus: regionId });
}

function RecommendationTabs({ active, onSelect }: { active: RecommendationView; onSelect: Props["onSelectView"] }) {
  return <nav className="recommendation-view-tabs" aria-label="Recommendation views"><button aria-pressed={active === "for-you"} onClick={() => onSelect("for-you")} type="button">For You</button><button aria-pressed={active === "by-goal"} onClick={() => onSelect("by-goal")} type="button">By Goal</button></nav>;
}

function ForYouView({ authenticated, onNavigate, onRetry, state }: { authenticated: boolean; onNavigate: Props["onNavigate"]; onRetry: Props["onRetryPersonalized"]; state: RecommendationLoadState<PersonalizedResult> }) {
  if (!authenticated) return <div className="empty-state recommendation-personalized-empty"><strong>Sign in to use Career Identity personalization.</strong><p>Goal-based market rankings remain available without an account.</p></div>;
  if (state.loading) return <LoadingBlock label="Building your Career Identity results…" />;
  if (state.error) return <ErrorBlock message={state.error} onRetry={onRetry} />;
  const metadata = state.envelope?.metadata.career_identity_personalization;
  if (!metadata?.career_identity_applied) {
    const noConsent = metadata?.reason === "downstream_personalization_consent_not_granted";
    return <div className="empty-state recommendation-personalized-empty"><strong>{noConsent ? "Personalization consent is off." : "Add Career Identity details for personalized discovery."}</strong><p>{noConsent ? "Request inputs are not presented as Career Identity-based results." : "Ordinary market exploration and By Goal rankings remain available."}</p><LinkButton onNavigate={onNavigate} url={careerIdentityUrl()}>Review Career Identity</LinkButton></div>;
  }
  const discovery = state.envelope?.data;
  const regions = discovery?.ranked_regions ?? [];
  const companies = discovery?.ranked_companies ?? [];
  const top = regions[0];
  const roleFamily = supportedOpportunityRole(metadata);
  return (
    <>
      <header className="recommendation-hero"><div><p className="eyebrow">For You · Career Identity</p><h1>{top ? `${top.display_name} best matches your stated preferences.` : "No personalized market is supported yet."}</h1><p>Authenticated discovery using the Career Identity facts and consent you control.</p></div><div className="recommendation-hero-actions">{top ? <LinkButton className="primary-button" onNavigate={onNavigate} url={personalizedMarketUrl(top.region_id, roleFamily)}>{roleFamily ? "Explore relevant opportunities" : `Explore ${top.display_name}`}</LinkButton> : null}<LinkButton onNavigate={onNavigate} url={careerIdentityUrl()}>Review Career Identity</LinkButton></div></header>
      <section className="recommendation-ranking" aria-label="Personalized markets"><div className="section-title-row"><div><p className="eyebrow">Preference fit</p><h2>Markets for your profile</h2></div><span>{regions.length} results</span></div>{regions.length ? <div className="personalized-market-grid">{regions.map((region, index) => <article className="strategy-target" key={region.region_id}><div><span className="strategy-target-role">#{index + 1} personalized</span><h3>{region.display_name}</h3><p>{region.match_notes.slice(0, 2).map(humanText).join(" · ") || "Supported by the available profile and market evidence."}</p></div><div className="strategy-target-score"><strong>{percent(region.personal_market_score)}</strong><small>personal fit</small></div><LinkButton onNavigate={onNavigate} url={personalizedMarketUrl(region.region_id, roleFamily)}>{roleFamily ? "View relevant opportunities" : "Explore market"}</LinkButton></article>)}</div> : <div className="empty-state"><strong>No personalized markets returned.</strong><p>Review your Career Identity or explore markets directly.</p></div>}</section>
      <details className="recommendation-company-disclosure evidence-disclosure"><summary>Employers aligned to this profile ({companies.length})</summary><div className="personalized-company-grid">{companies.map((company) => <article className="strategy-target" key={`${company.company_id}:${company.region_id}`}><div><span className="strategy-target-role">{company.region_display_name}</span><h3>{company.company_name}</h3><p>{company.match_notes.slice(0, 3).map(humanText).join(" · ")}</p></div><div className="strategy-target-score"><strong>{percent(company.personal_company_score)}</strong><small>personal fit</small></div></article>)}</div></details>
      <section className="recommendation-limitations" aria-label="Personalization basis"><div><p className="eyebrow">Basis and limits</p><h2>Profile inputs used</h2></div><p>{(metadata.role_targets ?? []).map(label).join(", ") || "No role targets"}{metadata.industry_preferences?.length ? ` · ${metadata.industry_preferences.map(label).join(", ")}` : ""}</p><p className="meta-copy">Deterministic preference matching over illustrative market evidence; not a prediction of hiring outcomes.</p></section>
    </>
  );
}

function firstActionableTarget(strategy: RecommendationStrategyPayload | undefined): { item: StrategyRegionTarget; tone: "primary" | "secondary" | "fallback" } | null {
  const plan = strategy?.market_strategy_plan;
  if (!plan) return null;
  if (plan.primary_region_targets[0]) return { item: plan.primary_region_targets[0], tone: "primary" };
  if (plan.secondary_region_targets[0]) return { item: plan.secondary_region_targets[0], tone: "secondary" };
  if (plan.fallback_region_targets[0]) return { item: plan.fallback_region_targets[0], tone: "fallback" };
  return null;
}

function ByGoalView({ goalModesState, onNavigate, onSelectGoalMode, selectedGoalMode, strategyState }: Pick<Props, "goalModesState" | "onNavigate" | "onSelectGoalMode" | "selectedGoalMode" | "strategyState">) {
  const strategy = strategyState.envelope?.data;
  const goals = goalModesState.envelope?.data?.goal_modes ?? strategy?.available_goal_modes ?? [];
  const numericLeader = strategy?.ranked_region_recommendations[0];
  const actionable = firstActionableTarget(strategy ?? undefined);
  const selectedGoalLabel = goals.find((goal) => goal.goal_mode === selectedGoalMode)?.label ?? label(selectedGoalMode);
  const selectedGoalSubject = selectedGoalLabel.replace(/^Maximize\s+/i, "").replace(/^Prioritize\s+/i, "");
  const headline = actionable ? `${targetName(actionable.item)} is the ${actionable.tone === "fallback" ? "actionable fallback" : actionable.tone === "secondary" ? "supported secondary option" : "strongest actionable market"} for ${selectedGoalSubject.toLocaleLowerCase()}.` : numericLeader ? `No market is actionable yet for ${selectedGoalSubject.toLocaleLowerCase()}.` : "Compare markets by a selected goal.";
  const leaderDiffers = Boolean(actionable && numericLeader && actionable.item.target.target_id !== numericLeader.target.target_id);
  const targetUrl = actionable ? exploreUrl({ focus: actionable.item.target.target_id }) : exploreUrl();
  return (
    <>
      <header className="recommendation-hero"><div><p className="eyebrow">By Goal · deterministic market comparison</p><h1>{headline}</h1><p>{leaderDiffers ? `${targetName(numericLeader!)} has the highest numerical score but is not an actionable target in this strategy.` : "Shared market evidence is ranked by the objective you select; Career Identity does not change these rankings."}</p></div><div className="recommendation-hero-actions"><LinkButton className="primary-button" onNavigate={onNavigate} url={targetUrl}>{actionable ? `Explore ${targetName(actionable.item)}` : "Explore markets"}</LinkButton></div></header>
      <GoalSelector goals={goals} loading={goalModesState.loading} onSelect={onSelectGoalMode} selected={selectedGoalMode} />
      {goalModesState.error ? <ErrorBlock message={goalModesState.error} /> : null}{strategyState.loading ? <LoadingBlock /> : null}{strategyState.error ? <ErrorBlock message={strategyState.error} /> : null}
      {strategy ? <><StrategySummary strategy={strategy.market_strategy_plan} /><div className="recommendation-next-actions"><div><p className="eyebrow">Next step</p><h2>Turn a ranked market into a decision.</h2><p>Compare alternatives or record the trade-off you want to revisit.</p></div><div><LinkButton className="primary-button" onNavigate={onNavigate} url={decisionsUrl()}>Open Decision Workspace</LinkButton><LinkButton onNavigate={onNavigate} url={exploreUrl()}>Compare markets</LinkButton></div></div><RankingSection items={strategy.ranked_region_recommendations} title="Ranked markets" /><details className="recommendation-company-disclosure evidence-disclosure"><summary>Ranked employers ({strategy.ranked_company_recommendations.length})</summary><RankingSection items={strategy.ranked_company_recommendations} title="Employer results" /></details><WarningSummary strategy={strategy} /><details className="recommendation-technical-summary evidence-disclosure"><summary>Method and supporting evidence</summary><dl><dt>Strategy version</dt><dd>{strategy.market_strategy_plan.strategy_version}</dd><dt>Source recommendations</dt><dd>{strategy.market_strategy_plan.source_recommendations.length}</dd><dt>Manual verification steps</dt><dd>{strategy.market_strategy_plan.manual_verification_checklist.items.length}</dd><dt>Timing guidance items</dt><dd>{strategy.market_strategy_plan.timing_guidance.length}</dd></dl><div className="recommendation-evidence-grid"><section><h3>Role-family guidance</h3>{strategy.market_strategy_plan.role_family_targets.length ? <ul>{strategy.market_strategy_plan.role_family_targets.map((item) => <li key={item.target.target_id}><strong>{item.target.display_label ?? label(item.target.target_id)}</strong> — {item.rationale}{item.support === "inferred" ? " (heuristic / inferred)" : ""}</li>)}</ul> : <p>No grounded role-family guidance returned.</p>}</section><section><h3>Timing guidance</h3>{strategy.market_strategy_plan.timing_guidance.length ? <ul>{strategy.market_strategy_plan.timing_guidance.map((item) => <li key={`${item.timing_category}:${item.label}`}><strong>{item.label}</strong> — {item.guidance}</li>)}</ul> : <p>No conservative timing guidance returned.</p>}</section><section><h3>Company and category targets</h3>{[...strategy.market_strategy_plan.company_targets, ...strategy.market_strategy_plan.company_category_targets].length ? <ul>{[...strategy.market_strategy_plan.company_targets, ...strategy.market_strategy_plan.company_category_targets].map((item) => <li key={`${item.target.target_type}:${item.target.target_id}`}><strong>{item.target.display_label ?? label(item.target.target_id)}</strong> — {item.rationale}</li>)}</ul> : <p>No grounded company targets returned.</p>}</section><section><h3>Manual verification checklist</h3>{strategy.market_strategy_plan.manual_verification_checklist.items.length ? <ul>{strategy.market_strategy_plan.manual_verification_checklist.items.map((entry, index) => <li key={`${entry.item.verification_category}:${entry.item.label}:${index}`}><strong>{entry.item.label}</strong> — {entry.item.question}</li>)}</ul> : <p>No manual verification steps returned.</p>}</section></div></details></> : !strategyState.loading && !strategyState.error ? <div className="empty-state"><strong>No recommendation strategy loaded</strong><p>Select a supported goal or retry when the recommendation service is available.</p></div> : null}
    </>
  );
}

export default function RecommendationExperience(props: Props) {
  return <div className="recommendation-experience"><RecommendationTabs active={props.activeView} onSelect={props.onSelectView} />{props.activeView === "for-you" ? <ForYouView authenticated={props.authenticated} onNavigate={props.onNavigate} onRetry={props.onRetryPersonalized} state={props.personalizedState} /> : <ByGoalView goalModesState={props.goalModesState} onNavigate={props.onNavigate} onSelectGoalMode={props.onSelectGoalMode} selectedGoalMode={props.selectedGoalMode} strategyState={props.strategyState} />}</div>;
}
