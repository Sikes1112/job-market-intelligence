import { useCallback, useEffect, useMemo, useState, type MouseEvent, type ReactNode } from "react";
import {
  ApiError,
  getCurrentOpportunities,
  getCurrentOpportunity,
  getCurrentOpportunityCoverage,
  getCurrentOpportunityDiagnostics,
  getCurrentOpportunityMatches,
  getCurrentOpportunityRefreshRuns,
  type ProtectedRequestOptions,
} from "./api";
import type { FrontendAuthContextValue } from "./auth";
import { publicSafeText, sanitizePublicValue } from "./ImportedMarketOperationsModel";
import type {
  CurrentOpportunityCoveragePayload,
  CurrentOpportunityDiagnostic,
  CurrentOpportunityMatchPayload,
  CurrentOpportunityPayload,
  CurrentOpportunityRefreshRun,
} from "./types";
import {
  careerIdentityUrl,
  currentOpportunityDetailUrl,
  decisionsUrl,
  recommendationsUrl,
  type CurrentOpportunityUrlState,
} from "./urlState";

type LoadState<T> = {
  loading: boolean;
  data: T | null;
  error: string | null;
  statusCode?: number;
};

type OpportunityFilters = {
  market: string;
  roleFamily: string;
  opportunityType: string;
  workArrangement: string;
  freshness: string;
  relevance: string;
  limit: number;
};

type CurrentOpportunitiesPageProps = {
  auth: FrontendAuthContextValue;
  opportunityId?: string;
  operations?: boolean;
  onNavigate?: (url: string) => void;
  initialState?: CurrentOpportunityUrlState;
};

const DEFAULT_FILTERS: OpportunityFilters = {
  market: "greater_boston",
  roleFamily: "software_engineering",
  opportunityType: "job",
  workArrangement: "",
  freshness: "",
  relevance: "",
  limit: 20,
};

const WORK_ARRANGEMENTS = ["", "remote", "hybrid", "onsite", "mixed", "unknown"];
const FRESHNESS_STATES = ["", "fresh", "aging", "stale", "unknown"];
const RELEVANCE_STATES = ["", "direct_fit", "adjacent_fit", "limited_or_ineligible"];
const MARKET_OPTIONS = [
  ["greater_boston", "Greater Boston"],
  ["greater_nyc", "New York City"],
  ["sf_bay_area", "San Francisco Bay Area"],
  ["greater_seattle", "Seattle"],
  ["washington_dc", "Washington, DC"],
  ["austin", "Austin"],
  ["atlanta", "Atlanta"],
  ["chicago", "Chicago"],
] as const;
const ROLE_OPTIONS = [
  ["software_engineering", "Software engineering"],
  ["applied_ai", "Applied AI"],
  ["data_ai", "Data and AI"],
  ["product_management", "Technical product management"],
  ["solutions_engineering", "Solutions engineering"],
] as const;
const OPPORTUNITY_TYPES = [["job", "Jobs"], ["internship", "Internships"]] as const;

function emptyLoad<T>(): LoadState<T> {
  return { loading: false, data: null, error: null };
}

export default function CurrentOpportunitiesPage({
  auth,
  initialState,
  opportunityId,
  operations = false,
  onNavigate,
}: CurrentOpportunitiesPageProps) {
  const [filters, setFilters] = useState<OpportunityFilters>(() => filtersFromUrl(initialState));
  const [matchesState, setMatchesState] = useState<LoadState<CurrentOpportunityMatchPayload[]>>(emptyLoad);
  const [opportunitiesState, setOpportunitiesState] = useState<LoadState<CurrentOpportunityPayload[]>>(emptyLoad);
  const [coverageState, setCoverageState] = useState<LoadState<CurrentOpportunityCoveragePayload>>(emptyLoad);
  const [detailState, setDetailState] = useState<LoadState<CurrentOpportunityPayload>>(emptyLoad);
  const [diagnosticsState, setDiagnosticsState] = useState<LoadState<CurrentOpportunityDiagnostic[]>>(emptyLoad);
  const [runsState, setRunsState] = useState<LoadState<CurrentOpportunityRefreshRun[]>>(emptyLoad);

  const protectedOptions = useMemo<ProtectedRequestOptions>(() => ({
    getAccessToken: auth.getAccessTokenSilently,
  }), [auth.getAccessTokenSilently]);

  const navigate = useCallback((event: MouseEvent<HTMLAnchorElement>, url: string) => {
    if (!onNavigate || event.button !== 0 || event.metaKey || event.altKey || event.ctrlKey || event.shiftKey) return;
    event.preventDefault();
    onNavigate(url);
  }, [onNavigate]);

  useEffect(() => {
    if (operations) return;
    setFilters(filtersFromUrl(initialState));
  }, [initialState, operations]);

  useEffect(() => {
    if (operations || auth.isLoading || !auth.isAuthenticated) return;
    let active = true;
    setMatchesState((current) => ({ ...current, loading: true, error: null }));
    setOpportunitiesState((current) => ({ ...current, loading: true, error: null }));
    setCoverageState((current) => ({ ...current, loading: true, error: null }));
    Promise.allSettled([
      getCurrentOpportunityMatches({ include_ineligible: true, limit: filters.limit }, protectedOptions),
      getCurrentOpportunities({
        market: filters.market,
        role_family: filters.roleFamily,
        opportunity_type: filters.opportunityType,
        work_arrangement: filters.workArrangement || null,
        include_ineligible: true,
        limit: 100,
      }, protectedOptions),
      getCurrentOpportunityCoverage({
        market_key: filters.market,
        role_family: filters.roleFamily,
        opportunity_type: filters.opportunityType,
      }, protectedOptions),
    ]).then(([matches, opportunities, coverage]) => {
      if (!active) return;
      if (matches.status === "fulfilled") {
        setMatchesState({ loading: false, data: matches.value.data?.matches ?? [], error: null });
      } else {
        setMatchesState(errorLoad(matches.reason, "Current opportunity matches are unavailable."));
      }
      if (opportunities.status === "fulfilled") {
        setOpportunitiesState({ loading: false, data: opportunities.value.data?.opportunities ?? [], error: null });
      } else {
        setOpportunitiesState(errorLoad(opportunities.reason, "Current opportunity inventory is unavailable."));
      }
      if (coverage.status === "fulfilled") {
        setCoverageState({ loading: false, data: coverage.value.data, error: null });
      } else {
        setCoverageState(errorLoad(coverage.reason, "Coverage status is unavailable."));
      }
    });
    return () => {
      active = false;
    };
  }, [auth.isAuthenticated, auth.isLoading, filters, operations, protectedOptions]);

  useEffect(() => {
    if (operations || auth.isLoading || !auth.isAuthenticated || !opportunityId) {
      setDetailState(emptyLoad);
      return;
    }
    let active = true;
    setDetailState((current) => ({ ...current, loading: true, error: null }));
    getCurrentOpportunity(opportunityId, protectedOptions)
      .then((envelope) => {
        if (active) setDetailState({ loading: false, data: envelope.data, error: null });
      })
      .catch((error) => {
        if (active) setDetailState(errorLoad(error, "Opportunity detail is unavailable."));
      });
    return () => {
      active = false;
    };
  }, [auth.isAuthenticated, auth.isLoading, operations, opportunityId, protectedOptions]);

  useEffect(() => {
    if (!opportunityId || !detailState.data) return;
    const opportunity = detailState.data;
    setFilters((current) => {
      const next = {
        ...current,
        market: initialState?.market ?? opportunity.market_id ?? current.market,
        roleFamily: initialState?.roleFamily ?? opportunity.role_family,
        opportunityType: initialState?.opportunityType ?? opportunity.opportunity_type,
        workArrangement: initialState?.workArrangement ?? current.workArrangement,
      };
      return current.market === next.market
        && current.roleFamily === next.roleFamily
        && current.opportunityType === next.opportunityType
        && current.workArrangement === next.workArrangement
        ? current
        : next;
    });
  }, [detailState.data, initialState, opportunityId]);

  useEffect(() => {
    if (!operations || auth.isLoading || !auth.isAuthenticated) return;
    let active = true;
    setDiagnosticsState((current) => ({ ...current, loading: true, error: null }));
    setRunsState((current) => ({ ...current, loading: true, error: null }));
    setCoverageState((current) => ({ ...current, loading: true, error: null }));
    Promise.allSettled([
      getCurrentOpportunityDiagnostics(protectedOptions),
      getCurrentOpportunityRefreshRuns({ limit: 25 }, protectedOptions),
      getCurrentOpportunityCoverage({
        market_key: filters.market,
        role_family: filters.roleFamily,
        opportunity_type: filters.opportunityType,
      }, protectedOptions),
    ]).then(([diagnostics, runs, coverage]) => {
      if (!active) return;
      if (diagnostics.status === "fulfilled") {
        setDiagnosticsState({ loading: false, data: diagnostics.value.data?.diagnostics ?? [], error: null });
      } else {
        setDiagnosticsState(errorLoad(diagnostics.reason, "Current opportunity diagnostics are unavailable."));
      }
      if (runs.status === "fulfilled") {
        setRunsState({ loading: false, data: runs.value.data?.runs ?? [], error: null });
      } else {
        setRunsState(errorLoad(runs.reason, "Refresh run history is unavailable."));
      }
      if (coverage.status === "fulfilled") {
        setCoverageState({ loading: false, data: coverage.value.data, error: null });
      } else {
        setCoverageState(errorLoad(coverage.reason, "Coverage status is unavailable."));
      }
    });
    return () => {
      active = false;
    };
  }, [auth.isAuthenticated, auth.isLoading, filters.market, filters.opportunityType, filters.roleFamily, operations, protectedOptions]);

  if (auth.isLoading) {
    return <PageFrame><LoadingBlock label="Checking account session" /></PageFrame>;
  }

  if (!auth.isAuthenticated) {
    return (
      <PageFrame>
        <section className="empty-state current-opportunity-state">
          <strong>Sign in to view current opportunities</strong>
          <p>Sign in to see opportunity matches informed by your Career Identity and saved decisions.</p>
          <button className="primary-button" type="button" onClick={() => void auth.login()}>
            Sign in
          </button>
        </section>
      </PageFrame>
    );
  }

  if (operations) {
    return (
      <OperationsView
        coverage={coverageState}
        diagnostics={diagnosticsState}
        filters={filters}
        onFilterChange={setFilters}
        runs={runsState}
      />
    );
  }

  const matches = matchesState.data ?? [];
  const filteredMatches = filterMatches(matches, filters);
  const opportunities = opportunitiesState.data ?? [];
  const coverage = coverageState.data;
  const hasDegradedData = Boolean(
    coverage && coverage.effective_status !== "production_ready"
    || filteredMatches.some((match) =>
      match.opportunity.freshness_state === "stale"
      || match.opportunity.freshness_state === "unknown"
      || match.limitations.length
      || match.warnings.length
    )
  );

  return (
    <PageFrame>
      <section className="card current-opportunity-hero">
        <div className="card-header">
          <div>
            <p className="card-eyebrow">Opportunity search</p>
            <h1>Current opportunities</h1>
          </div>
          <span className="opportunity-result-count">{filteredMatches.length}<small>matching results</small></span>
        </div>
        <p className="lead-copy">
          Search 24 illustrative opportunities across eight markets.
        </p>
        <p className="demo-data-note"><strong>Demo opportunities:</strong> synthetic, simulated freshness, and not live listings.</p>
        <div className="opportunity-link-row">
          {initialState?.returnTo ? <a href={initialState.returnTo} onClick={(event) => navigate(event, initialState.returnTo!)}>← Back to Explore context</a> : null}
          <a href={recommendationsUrl()} onClick={(event) => navigate(event, recommendationsUrl())}>View recommendations</a>
          <a href={careerIdentityUrl()} onClick={(event) => navigate(event, careerIdentityUrl())}>Career Identity</a>
          <a href={decisionsUrl()} onClick={(event) => navigate(event, decisionsUrl())}>Decision Workspace</a>
        </div>
      </section>

      <OpportunityFiltersPanel filters={filters} onChange={setFilters} />
      <CoveragePanel coverage={coverage} loading={coverageState.loading} error={coverageState.error} />

      {hasDegradedData ? <DegradedNotice matches={filteredMatches} /> : null}
      {matchesState.loading || opportunitiesState.loading ? <LoadingBlock label="Loading current opportunity matches" /> : null}
      {matchesState.error ? <ErrorBlock title="Matches unavailable" message={matchesState.error} /> : null}
      {opportunitiesState.error ? <ErrorBlock title="Opportunity inventory unavailable" message={opportunitiesState.error} /> : null}

      {!matchesState.loading && !matchesState.error ? (
        <OpportunityEmptyState
          coverage={coverage}
          filteredMatches={filteredMatches}
          matches={matches}
          opportunities={opportunities}
        />
      ) : null}

      <section className="current-opportunity-list" aria-label="Strategic current opportunity matches">
        {filteredMatches.map((match) => (
          <OpportunityMatchCard key={match.opportunity.opportunity_id} match={match} navigate={navigate} />
        ))}
      </section>

      {opportunityId ? (
        <OpportunityDetailPanel
          detail={detailState}
          match={matches.find((item) => item.opportunity.opportunity_id === opportunityId) ?? null}
        />
      ) : null}
    </PageFrame>
  );
}

function filtersFromUrl(state?: CurrentOpportunityUrlState): OpportunityFilters {
  return {
    ...DEFAULT_FILTERS,
    market: state?.market ?? DEFAULT_FILTERS.market,
    roleFamily: state?.roleFamily ?? DEFAULT_FILTERS.roleFamily,
    opportunityType: state?.opportunityType ?? DEFAULT_FILTERS.opportunityType,
    workArrangement: state?.workArrangement ?? DEFAULT_FILTERS.workArrangement,
  };
}

function OperationsView({
  coverage,
  diagnostics,
  filters,
  onFilterChange,
  runs,
}: {
  coverage: LoadState<CurrentOpportunityCoveragePayload>;
  diagnostics: LoadState<CurrentOpportunityDiagnostic[]>;
  filters: OpportunityFilters;
  onFilterChange: (filters: OpportunityFilters) => void;
  runs: LoadState<CurrentOpportunityRefreshRun[]>;
}) {
  if (diagnostics.statusCode === 401 || diagnostics.statusCode === 403) {
    return (
      <PageFrame>
        <section className="error-state current-opportunity-state">
          <strong>Operator access required</strong>
          <p>Current opportunity diagnostics are restricted to users with data review access.</p>
        </section>
      </PageFrame>
    );
  }

  const diagnosticItems = diagnostics.data ?? [];
  const runItems = runs.data ?? [];
  const failedRuns = runItems.filter((run) => run.failure_count > 0 || run.status.includes("failure") || run.status === "failed");

  return (
    <PageFrame>
      <section className="card current-opportunity-hero">
        <div className="card-header">
          <div>
            <p className="card-eyebrow">Opportunity data operations</p>
            <h2>Current Opportunity Health</h2>
          </div>
          <span className={`badge ${failedRuns.length ? "badge-warning" : "badge-success"}`}>
            {failedRuns.length ? "Degraded" : "No failed recent runs"}
          </span>
        </div>
        <p className="lead-copy">
          This advanced view renders governed source diagnostics and refresh receipts. It does not recompute source health in the frontend.
        </p>
      </section>

      <OpportunityFiltersPanel filters={filters} onChange={onFilterChange} compact />
      <CoveragePanel coverage={coverage.data} loading={coverage.loading} error={coverage.error} operator />

      {(diagnostics.loading || runs.loading) ? <LoadingBlock label="Loading opportunity operations" /> : null}
      {diagnostics.error ? <ErrorBlock title="Diagnostics unavailable" message={diagnostics.error} /> : null}
      {runs.error ? <ErrorBlock title="Refresh runs unavailable" message={runs.error} /> : null}

      <section className="current-opportunity-ops-grid">
        <div className="card">
          <div className="card-header compact-header">
            <div>
              <p className="card-eyebrow">Diagnostics</p>
              <h3>Source and ranking health</h3>
            </div>
            <span className="badge">{diagnosticItems.length} findings</span>
          </div>
          {diagnosticItems.length ? (
            <ul className="current-diagnostic-list">
              {diagnosticItems.map((diagnostic, index) => (
                <li key={`${diagnostic.code}:${index}`}>
                  <span className={`status-dot status-${diagnostic.severity}`} aria-hidden="true" />
                  <div>
                    <strong>{labelFor(diagnostic.code)}</strong>
                    <p>{publicSafeText(diagnostic.message, "Diagnostic detail unavailable.")}</p>
                    <small>{safeStructuredSummary({ scope: diagnostic.scope, evidence: diagnostic.evidence })}</small>
                  </div>
                </li>
              ))}
            </ul>
          ) : diagnostics.loading ? null : (
            <div className="empty-state compact-empty">
              <strong>No diagnostics returned</strong>
              <p>The backend did not return source, coverage, or ranking degradation findings.</p>
            </div>
          )}
        </div>

        <div className="card">
          <div className="card-header compact-header">
            <div>
              <p className="card-eyebrow">Refresh runtime</p>
              <h3>Recent refresh runs</h3>
            </div>
            <span className="badge">{runItems.length} runs</span>
          </div>
          {runItems.length ? (
            <div className="refresh-run-table" role="table" aria-label="Current opportunity refresh runs">
              <div role="row" className="refresh-run-header">
                <span role="columnheader">Source</span>
                <span role="columnheader">Status</span>
                <span role="columnheader">Counts</span>
                <span role="columnheader">Failure</span>
              </div>
              {runItems.map((run) => (
                <div role="row" className="refresh-run-row" key={run.run_id}>
                  <span role="cell">
                    <strong>{run.source_id}</strong>
                    <small>{dateTimeLabel(run.completed_at ?? run.started_at)}</small>
                  </span>
                  <span role="cell">{labelFor(run.status)}</span>
                  <span role="cell">
                    {run.acquired_count} acquired, {run.normalized_count} normalized, {run.promoted_count} promoted, {run.duplicate_count} duplicate, {run.rejected_count} rejected
                  </span>
                  <span role="cell">
                    {run.failure_count ? publicSafeText(safeStructuredSummary(run.failure_details), "Failure detail unavailable.") : "None"}
                  </span>
                </div>
              ))}
            </div>
          ) : runs.loading ? null : (
            <div className="empty-state compact-empty">
              <strong>No refresh runs returned</strong>
              <p>No current-opportunity refresh receipts were available from the backend.</p>
            </div>
          )}
        </div>
      </section>
    </PageFrame>
  );
}

function PageFrame({ children }: { children: ReactNode }) {
  return <div className="view-grid current-opportunities-view">{children}</div>;
}

function OpportunityFiltersPanel({
  compact = false,
  filters,
  onChange,
}: {
  compact?: boolean;
  filters: OpportunityFilters;
  onChange: (filters: OpportunityFilters) => void;
}) {
  return (
    <section className={`card current-opportunity-filters ${compact ? "current-opportunity-filters-compact" : ""}`}>
      <div className="card-header compact-header">
        <div>
          <p className="card-eyebrow">Scope</p>
          <h3>{compact ? "Coverage scope" : "Opportunity filters"}</h3>
        </div>
        {!compact ? <button className="text-button" onClick={() => onChange({ ...DEFAULT_FILTERS })} type="button">Reset filters</button> : null}
      </div>
      <div className="opportunity-filter-grid">
        <label>
          Market
          <select
            value={filters.market}
            onChange={(event) => onChange({ ...filters, market: event.target.value })}
          >{MARKET_OPTIONS.map(([value, text]) => <option key={value} value={value}>{text}</option>)}</select>
        </label>
        <label>
          Role family
          <select
            value={filters.roleFamily}
            onChange={(event) => onChange({ ...filters, roleFamily: event.target.value })}
          >{ROLE_OPTIONS.map(([value, text]) => <option key={value} value={value}>{text}</option>)}</select>
        </label>
        <label>
          Type
          <select
            value={filters.opportunityType}
            onChange={(event) => onChange({ ...filters, opportunityType: event.target.value })}
          >{OPPORTUNITY_TYPES.map(([value, text]) => <option key={value} value={value}>{text}</option>)}</select>
        </label>
        {!compact ? (
          <>
            <label>
              Work arrangement
              <select
                value={filters.workArrangement}
                onChange={(event) => onChange({ ...filters, workArrangement: event.target.value })}
              >
                {WORK_ARRANGEMENTS.map((option) => (
                  <option key={option || "all"} value={option}>{option ? labelFor(option) : "Any"}</option>
                ))}
              </select>
            </label>
            <label>
              Freshness
              <select
                value={filters.freshness}
                onChange={(event) => onChange({ ...filters, freshness: event.target.value })}
              >
                {FRESHNESS_STATES.map((option) => (
                  <option key={option || "all"} value={option}>{option ? labelFor(option) : "Any"}</option>
                ))}
              </select>
            </label>
            <label>
              Strategic relevance
              <select
                value={filters.relevance}
                onChange={(event) => onChange({ ...filters, relevance: event.target.value })}
              >
                {RELEVANCE_STATES.map((option) => (
                  <option key={option || "all"} value={option}>{option ? relevanceLabel(option) : "Any"}</option>
                ))}
              </select>
            </label>
          </>
        ) : null}
      </div>
    </section>
  );
}

function CoveragePanel({
  coverage,
  error,
  loading,
  operator = false,
}: {
  coverage: CurrentOpportunityCoveragePayload | null;
  error: string | null;
  loading: boolean;
  operator?: boolean;
}) {
  if (loading && !coverage) return <LoadingBlock label="Loading coverage state" />;
  if (error && !coverage) return <ErrorBlock title="Coverage unavailable" message={error} />;
  if (!coverage) return null;
  const presentation = coveragePresentation(coverage.effective_status);
  return (
    <section className={`coverage-panel current-coverage-panel coverage-${presentation.tone}`}>
      <div className="card-header compact-header">
        <div>
          <p className="card-eyebrow">{operator ? "Coverage contract" : "Coverage"}</p>
          <h3>{presentation.label}</h3>
        </div>
        <span className={`badge badge-${presentation.tone}`}>{labelFor(coverage.effective_status)}</span>
      </div>
      <p>{presentation.copy}</p>
      <details className="evidence-disclosure compact-disclosure">
        <summary>Coverage details</summary>
        <p className="meta-copy">{publicSafeText(coverage.rationale, "Coverage rationale unavailable.")}</p>
        {coverage.limitations.length ? (
          <ul className="compact-list">
            {coverage.limitations.map((limitation) => (
              <li key={limitation}>{publicSafeText(limitation)}</li>
            ))}
          </ul>
        ) : null}
        <div className="metadata-row">
          <span>Scope: {coverage.market_key} / {coverage.role_family} / {coverage.opportunity_type}</span>
          <span>Expected sources: {coverage.minimum_expected_sources}</span>
          <span>Evaluated: {dateTimeLabel(coverage.last_evaluated_at)}</span>
        </div>
      </details>
    </section>
  );
}

function DegradedNotice({
  matches,
}: {
  matches: CurrentOpportunityMatchPayload[];
}) {
  const staleCount = matches.filter((match) => ["stale", "unknown"].includes(match.opportunity.freshness_state)).length;
  const ineligibleCount = matches.filter((match) => !match.ranking_eligible).length;
  if (!staleCount && !ineligibleCount) return null;
  return (
    <section className="notice-state current-opportunity-state">
      <strong>Some results need review</strong>
      <div className="badge-stack">
        {staleCount ? <span className="badge badge-warning">{staleCount} stale or unknown freshness</span> : null}
        {ineligibleCount ? <span className="badge badge-warning">{ineligibleCount} not ranking eligible</span> : null}
      </div>
    </section>
  );
}

function OpportunityEmptyState({
  coverage,
  filteredMatches,
  matches,
  opportunities,
}: {
  coverage: CurrentOpportunityCoveragePayload | null;
  filteredMatches: CurrentOpportunityMatchPayload[];
  matches: CurrentOpportunityMatchPayload[];
  opportunities: CurrentOpportunityPayload[];
}) {
  if (filteredMatches.length) return null;
  if (coverage?.effective_status === "unsupported") {
    return (
      <section className="empty-state current-opportunity-state">
        <strong>Current coverage is not supported for this scope</strong>
        <p>No complete current-opportunity view is available for these filters.</p>
      </section>
    );
  }
  if (coverage?.effective_status === "limited" || coverage?.effective_status === "experimental") {
    return (
      <section className="empty-state current-opportunity-state">
        <strong>No current matches in a partial view</strong>
        <p>{coveragePresentation(coverage.effective_status).copy}</p>
      </section>
    );
  }
  if (opportunities.length && !matches.length) {
    return (
      <section className="empty-state current-opportunity-state">
        <strong>Opportunities exist but none are eligible strategic matches</strong>
        <p>Visible opportunities are ineligible for ranking or do not match the current Career Identity and decision context.</p>
      </section>
    );
  }
  if (matches.length && !filteredMatches.length) {
    return (
      <section className="empty-state current-opportunity-state">
        <strong>No matches after filters</strong>
        <p>Reset or broaden the filters. The coverage label above shows whether this view is complete or partial.</p>
      </section>
    );
  }
  return (
    <section className="empty-state current-opportunity-state">
      <strong>No current strategic matches returned</strong>
      <p>No current opportunities matching these criteria were found in the available covered data.</p>
    </section>
  );
}

function OpportunityMatchCard({
  match,
  navigate,
}: {
  match: CurrentOpportunityMatchPayload;
  navigate: (event: MouseEvent<HTMLAnchorElement>, url: string) => void;
}) {
  const opportunity = match.opportunity;
  const detailUrl = currentOpportunityDetailUrl(opportunity.opportunity_id);
  return (
    <article className={`card opportunity-match-card freshness-${opportunity.freshness_state}`}>
      <div className="card-header">
        <div>
          <p className="card-eyebrow">{relevanceLabel(match.strategic_relevance)}</p>
          <h3>{opportunity.normalized_title || opportunity.original_title}</h3>
          <p className="meta-copy">{opportunity.company_name} · {opportunity.location_text ?? opportunity.market_label ?? "Location unknown"}</p>
        </div>
        <div className="opportunity-score-pill">
          <strong>{scoreBand(match.match_score)}</strong>
          <small>Relevance signal</small>
        </div>
      </div>

      <div className="badge-stack">
        <span className={`badge freshness-badge freshness-${opportunity.freshness_state}`}>{freshnessLabel(opportunity)}</span>
        <span className={`badge badge-${coveragePresentation(opportunity.coverage_status).tone}`}>{coveragePresentation(opportunity.coverage_status).label}</span>
        <span className="badge">{labelFor(opportunity.work_arrangement)}</span>
        {!match.ranking_eligible ? <span className="badge badge-warning">Not ranking eligible</span> : null}
      </div>

      <p>{formatCompensation(opportunity)}</p>

      {match.contributing_factors.length ? (
        <section className="opportunity-section">
          <h4>Why this appears</h4>
          <ul className="compact-list">
            {match.contributing_factors.slice(0, 4).map((factor) => (
              <li key={factor}>{factorLabel(factor)}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <WarningList warnings={[...match.warnings, ...match.limitations]} />

      <div className="opportunity-actions">
        <a className="secondary-button" href={detailUrl} onClick={(event) => navigate(event, detailUrl)}>
          View detail
        </a>
        <ApplicationLink opportunity={opportunity} />
      </div>
    </article>
  );
}

function OpportunityDetailPanel({
  detail,
  match,
}: {
  detail: LoadState<CurrentOpportunityPayload>;
  match: CurrentOpportunityMatchPayload | null;
}) {
  if (detail.loading) return <LoadingBlock label="Loading opportunity detail" />;
  if (detail.error) return <ErrorBlock title="Opportunity detail unavailable" message={detail.error} />;
  if (!detail.data) return null;
  const opportunity = detail.data;
  return (
    <section className="card opportunity-detail-panel" aria-label="Current opportunity detail">
      <div className="card-header">
        <div>
          <p className="card-eyebrow">Opportunity detail</p>
          <h2>{opportunity.normalized_title || opportunity.original_title}</h2>
          <p className="meta-copy">{opportunity.company_name} · {opportunity.location_text ?? opportunity.market_label ?? "Location unknown"}</p>
        </div>
        <ApplicationLink opportunity={opportunity} />
      </div>
      <div className="opportunity-detail-grid">
        <DetailCell label="Freshness" value={freshnessLabel(opportunity)} />
        <DetailCell label="Coverage" value={coveragePresentation(opportunity.coverage_status).label} />
        <DetailCell label="Identity confidence" value={labelFor(opportunity.identity_confidence)} />
        <DetailCell label="Normalization confidence" value={labelFor(opportunity.normalization_confidence)} />
        <DetailCell label="Employment" value={`${labelFor(opportunity.employment_type)} / ${labelFor(opportunity.opportunity_type)}`} />
        <DetailCell label="Posted" value={dateLabel(opportunity.posting_date)} />
      </div>
      {opportunity.description_text ? <p>{publicSafeText(opportunity.description_text)}</p> : null}
      <TagSection title="Skills" values={opportunity.skills} empty="No normalized skills returned." />
      <TagSection title="Requirements" values={opportunity.requirements} empty="No normalized requirements returned." />
      {match?.contributing_factors.length ? (
        <section className="opportunity-section">
        <h3>Why it matches</h3>
          <ul className="compact-list">
            {match.contributing_factors.map((factor) => <li key={factor}>{factorLabel(factor)}</li>)}
          </ul>
        </section>
      ) : null}
      <ProvenanceSummary opportunity={opportunity} />
      <WarningList warnings={[...opportunity.warnings, ...opportunity.coverage_limitations, ...opportunity.ranking_ineligible_reasons]} />
    </section>
  );
}

function ProvenanceSummary({ opportunity }: { opportunity: CurrentOpportunityPayload }) {
  const sources = opportunity.provenance.sources ?? [];
  return (
    <section className="opportunity-section">
      <h3>Source summary</h3>
      <p className="meta-copy">
        {sources.length || opportunity.provenance.source_count || 0} source link(s) · Last observed {dateTimeLabel(opportunity.last_observed_at)}.
      </p>
      {sources.length ? (
        <ul className="compact-list">
          {sources.slice(0, 3).map((source) => (
            <li key={`${source.source_id}:${source.provider_record_id ?? "record"}`}>
              {source.source_name ?? source.source_id} · {labelFor(source.data_origin ?? "unknown origin")} · trust {labelFor(source.source_trust ?? "unknown")} · last collected {dateTimeLabel(source.last_collected_at ?? null)}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function ApplicationLink({ opportunity }: { opportunity: CurrentOpportunityPayload }) {
  if (isIllustrativeApplicationUrl(opportunity.application_url)) {
    return <span className="badge">Illustrative route only</span>;
  }
  const safeUrl = safeApplicationUrl(opportunity.application_url);
  if (!safeUrl) {
    return <span className="badge badge-warning">Application route unavailable</span>;
  }
  return (
    <a
      className="primary-button"
      href={safeUrl}
      rel="noopener noreferrer"
      target="_blank"
      aria-label={`Apply externally for ${opportunity.normalized_title || opportunity.original_title}`}
    >
      Apply externally
    </a>
  );
}

function WarningList({ warnings }: { warnings: string[] }) {
  const uniqueWarnings = Array.from(new Set(warnings.filter(Boolean))).slice(0, 5);
  if (!uniqueWarnings.length) return null;
  return (
    <details className="opportunity-warning-list evidence-disclosure" aria-label="Opportunity warnings and limitations">
      <summary>{uniqueWarnings.length} {uniqueWarnings.length === 1 ? "limitation" : "limitations"}</summary>
      <ul className="compact-list">{uniqueWarnings.map((warning) => (
        <li key={warning}>{publicSafeText(warning)}</li>
      ))}</ul>
    </details>
  );
}

function TagSection({ empty, title, values }: { empty: string; title: string; values: string[] }) {
  return (
    <section className="opportunity-section">
      <h3>{title}</h3>
      {values.length ? (
        <div className="badge-stack">
          {values.map((value) => <span className="badge" key={value}>{value}</span>)}
        </div>
      ) : (
        <p className="meta-copy">{empty}</p>
      )}
    </section>
  );
}

function DetailCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat-card">
      <span>{label}</span>
      <strong>{value}</strong>
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

function ErrorBlock({ title, message }: { title: string; message: string }) {
  return (
    <section className="error-state current-opportunity-state">
      <strong>{title}</strong>
      <p>{publicSafeText(message, "Request failed.")}</p>
    </section>
  );
}

function errorLoad<T>(error: unknown, fallback: string): LoadState<T> {
  return {
    loading: false,
    data: null,
    error: error instanceof Error ? error.message : fallback,
    statusCode: error instanceof ApiError ? error.statusCode : undefined,
  };
}

function filterMatches(matches: CurrentOpportunityMatchPayload[], filters: OpportunityFilters): CurrentOpportunityMatchPayload[] {
  return matches.filter((match) => {
    const opportunity = match.opportunity;
    if (filters.market && opportunity.market_id !== filters.market && opportunity.market_label !== filters.market) return false;
    if (filters.roleFamily && opportunity.role_family !== filters.roleFamily) return false;
    if (filters.opportunityType && opportunity.opportunity_type !== filters.opportunityType) return false;
    if (filters.workArrangement && opportunity.work_arrangement !== filters.workArrangement) return false;
    if (filters.freshness && opportunity.freshness_state !== filters.freshness) return false;
    if (filters.relevance) {
      if (filters.relevance === "limited_or_ineligible") return !match.ranking_eligible;
      return match.strategic_relevance === filters.relevance;
    }
    return true;
  });
}

function coveragePresentation(status: string) {
  if (status === "production_ready") {
    return {
      label: "Strong current view",
      copy: "Coverage is sufficient for a strong current view of these filters.",
      tone: "success",
    };
  }
  if (status === "limited") {
    return {
      label: "Limited coverage",
      copy: "The opportunity set may be incomplete; absence of a match is not evidence that no opportunity exists.",
      tone: "warning",
    };
  }
  if (status === "experimental") {
    return {
      label: "Experimental coverage",
      copy: "This scope is still being evaluated, so recommendations may be incomplete or lower confidence.",
      tone: "warning",
    };
  }
  if (status === "unsupported") {
    return {
      label: "Unsupported coverage",
      copy: "A complete current-opportunity view is not supported for these filters.",
      tone: "error",
    };
  }
  return {
    label: "Unknown coverage",
    copy: "Completeness is unknown for these filters.",
    tone: "unknown",
  };
}

function relevanceLabel(value: string): string {
  if (value === "direct_fit") return "Direct strategic fit";
  if (value === "adjacent_fit") return "Adjacent strategic route";
  if (value === "limited_or_ineligible") return "Limited or ineligible";
  if (value === "not_ranking_eligible") return "Visible but not ranking eligible";
  return labelFor(value || "strategic match");
}

function scoreBand(score: number): string {
  if (score >= 0.8) return "High";
  if (score >= 0.5) return "Medium";
  if (score > 0) return "Low";
  return "Diagnostic";
}

function freshnessLabel(opportunity: CurrentOpportunityPayload): string {
  const base = labelFor(opportunity.freshness_state);
  if (opportunity.freshness_age_hours === null) return `${base} freshness`;
  return `${base} · ${opportunity.freshness_age_hours}h observed age`;
}

function factorLabel(value: string): string {
  const normalized = value.replaceAll("_", " ").toLowerCase();
  if (normalized === "current and ranking eligible") {
    return "Current and eligible for ranking.";
  }
  if (normalized === "fresh source observation") {
    return "Fresh source observation.";
  }
  if (normalized === "limited coverage") {
    return "Coverage is limited.";
  }
  if (value === "career identity and decision term overlap") {
    return "Career Identity and active decision terms overlap with this opportunity.";
  }
  if (value === "strategy term overlap") {
    return "Your current recommendation strategy aligns with this opportunity.";
  }
  return publicSafeText(labelFor(value), "Match factor unavailable.");
}

function formatCompensation(opportunity: CurrentOpportunityPayload): string {
  if (opportunity.compensation_min === null && opportunity.compensation_max === null) return "Compensation unavailable";
  const currency = opportunity.compensation_currency ?? "USD";
  const interval = labelFor(opportunity.compensation_interval);
  if (opportunity.compensation_min !== null && opportunity.compensation_max !== null) {
    return `${currency} ${formatNumber(opportunity.compensation_min)}-${formatNumber(opportunity.compensation_max)} ${interval}`;
  }
  return `${currency} ${formatNumber(opportunity.compensation_min ?? opportunity.compensation_max ?? 0)} ${interval}`;
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
}

function labelFor(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function dateLabel(value: string | null): string {
  if (!value) return "Unknown";
  return value;
}

function dateTimeLabel(value: string | null): string {
  if (!value) return "Unknown";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown";
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function safeApplicationUrl(value: string | null): string | null {
  if (!value) return null;
  try {
    const parsed = new URL(value);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return null;
    const hostname = parsed.hostname.toLowerCase();
    if (hostname === "localhost" || hostname === "127.0.0.1" || hostname.startsWith("127.")) return null;
    if (hostname === "example" || hostname.endsWith(".example")) return null;
    return parsed.toString();
  } catch {
    return null;
  }
}

function isIllustrativeApplicationUrl(value: string | null): boolean {
  if (!value) return false;
  try {
    const hostname = new URL(value).hostname.toLowerCase();
    return hostname === "example" || hostname.endsWith(".example");
  } catch {
    return false;
  }
}

function safeStructuredSummary(value: unknown): string {
  try {
    return JSON.stringify(sanitizePublicValue(value));
  } catch {
    return "Structured detail unavailable.";
  }
}
