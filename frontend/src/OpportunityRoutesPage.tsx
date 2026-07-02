import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  DEFAULT_OPPORTUNITY_ROUTE_REQUEST,
  LOCATION_MODE_OPTIONS,
  PROGRAM_TYPE_OPTIONS,
  commaList,
  requestOpportunityRoutes,
  toggleValue,
} from "./opportunityRoutes";
import { isPublicDemoMode } from "./demoMode";
import type {
  OpportunityLocationMode,
  OpportunityProgramType,
  OpportunityRoute,
  OpportunityRouteRequest,
  OpportunityRouteResponse,
  OpportunitySeniorityLevel,
} from "./opportunityTypes";
import type { ApiEnvelope } from "./types";

type RouteLoadState = {
  loading: boolean;
  envelope: ApiEnvelope<OpportunityRouteResponse> | null;
  error: string | null;
};

type RouteFormState = {
  intentSummary: string;
  regions: string;
  roleFamilies: string;
  programTypes: OpportunityProgramType[];
  locationModes: OpportunityLocationMode[];
  experienceLevel: OpportunitySeniorityLevel;
  skills: string;
  backgroundTags: string;
  constraints: string;
  includeUnverified: boolean;
  limit: number;
};

const EXPERIENCE_OPTIONS: OpportunitySeniorityLevel[] = [
  "internship",
  "new-grad",
  "early-career",
  "apprentice",
  "unknown",
];

function initialFormState(): RouteFormState {
  return {
    intentSummary: DEFAULT_OPPORTUNITY_ROUTE_REQUEST.user_intent_summary ?? "",
    regions: DEFAULT_OPPORTUNITY_ROUTE_REQUEST.target_regions.join(", "),
    roleFamilies: DEFAULT_OPPORTUNITY_ROUTE_REQUEST.target_role_families.join(", "),
    programTypes: [...(DEFAULT_OPPORTUNITY_ROUTE_REQUEST.preferred_program_types ?? [])],
    locationModes: [...(DEFAULT_OPPORTUNITY_ROUTE_REQUEST.preferred_location_modes ?? [])],
    experienceLevel: DEFAULT_OPPORTUNITY_ROUTE_REQUEST.experience_level,
    skills: (DEFAULT_OPPORTUNITY_ROUTE_REQUEST.skills ?? []).join(", "),
    backgroundTags: (DEFAULT_OPPORTUNITY_ROUTE_REQUEST.background_tags ?? []).join(", "),
    constraints: (DEFAULT_OPPORTUNITY_ROUTE_REQUEST.constraints ?? []).join(", "),
    includeUnverified: Boolean(DEFAULT_OPPORTUNITY_ROUTE_REQUEST.include_unverified),
    limit: DEFAULT_OPPORTUNITY_ROUTE_REQUEST.limit ?? 5,
  };
}

function formToRequest(form: RouteFormState): OpportunityRouteRequest {
  return {
    user_intent_summary: form.intentSummary,
    target_regions: commaList(form.regions),
    target_role_families: commaList(form.roleFamilies),
    preferred_program_types: form.programTypes,
    preferred_location_modes: form.locationModes,
    experience_level: form.experienceLevel,
    skills: commaList(form.skills),
    background_tags: commaList(form.backgroundTags),
    constraints: commaList(form.constraints),
    include_unverified: form.includeUnverified,
    limit: form.limit,
  };
}

export default function OpportunityRoutesPage() {
  const publicDemoMode = isPublicDemoMode();
  const [form, setForm] = useState<RouteFormState>(() => initialFormState());
  const [state, setState] = useState<RouteLoadState>({
    loading: false,
    envelope: null,
    error: null,
  });

  const routePayload = state.envelope?.data ?? null;
  const routes = routePayload?.routes ?? [];

  const submitRouteRequest = useCallback(async (request: OpportunityRouteRequest) => {
    if (publicDemoMode) return;
    setState((current) => ({ ...current, loading: true, error: null }));
    try {
      const envelope = await requestOpportunityRoutes(request);
      setState({ loading: false, envelope, error: null });
    } catch (error) {
      setState({
        loading: false,
        envelope: null,
        error: error instanceof Error ? error.message : "Opportunity routes are unavailable",
      });
    }
  }, [publicDemoMode]);

  useEffect(() => {
    if (publicDemoMode) return;
    void submitRouteRequest(DEFAULT_OPPORTUNITY_ROUTE_REQUEST);
  }, [publicDemoMode, submitRouteRequest]);

  const requestPreview = useMemo(() => formToRequest(form), [form]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (publicDemoMode) return;
    void submitRouteRequest(requestPreview);
  }

  if (publicDemoMode) {
    return (
      <div className="view-grid opportunity-route-view">
        <section className="notice-state">
          <strong>Opportunity routes are not available in public demo</strong>
          <p>
            The public-demo backend intentionally blocks opportunity routing and
            opportunity submission routes. Use market exploration, public reports,
            forecasts, data standards metadata, or career-agent public answers instead.
          </p>
        </section>
      </div>
    );
  }

  return (
    <div className="view-grid opportunity-route-view">
      <section className="card opportunity-route-control">
        <div className="card-header">
          <div>
            <p className="card-eyebrow">Opportunity routing</p>
            <h2>Recommended Opportunity Routes</h2>
          </div>
          <span className="badge badge-success">Route first</span>
        </div>

        <form className="route-form-grid" onSubmit={handleSubmit}>
          <label className="wide-field">
            Profile intent
            <textarea
              value={form.intentSummary}
              onChange={(event) =>
                setForm((current) => ({ ...current, intentSummary: event.target.value }))
              }
            />
          </label>
          <label>
            Target regions
            <input
              value={form.regions}
              onChange={(event) =>
                setForm((current) => ({ ...current, regions: event.target.value }))
              }
            />
          </label>
          <label>
            Role families
            <input
              value={form.roleFamilies}
              onChange={(event) =>
                setForm((current) => ({ ...current, roleFamilies: event.target.value }))
              }
            />
          </label>
          <label>
            Experience level
            <select
              value={form.experienceLevel}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  experienceLevel: event.target.value as OpportunitySeniorityLevel,
                }))
              }
            >
              {EXPERIENCE_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {displayLabel(option)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Route limit
            <input
              min={1}
              max={25}
              type="number"
              value={form.limit}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  limit: Math.max(1, Math.min(25, Number(event.target.value) || 1)),
                }))
              }
            />
          </label>
          <label>
            Skills
            <input
              value={form.skills}
              onChange={(event) =>
                setForm((current) => ({ ...current, skills: event.target.value }))
              }
            />
          </label>
          <label>
            Background tags
            <input
              value={form.backgroundTags}
              onChange={(event) =>
                setForm((current) => ({ ...current, backgroundTags: event.target.value }))
              }
            />
          </label>
          <fieldset>
            <legend>Program types</legend>
            <div className="route-toggle-grid">
              {PROGRAM_TYPE_OPTIONS.map((option) => (
                <label className="route-check" key={option}>
                  <input
                    checked={form.programTypes.includes(option)}
                    type="checkbox"
                    onChange={() =>
                      setForm((current) => ({
                        ...current,
                        programTypes: toggleValue(current.programTypes, option),
                      }))
                    }
                  />
                  <span>{displayLabel(option)}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <fieldset>
            <legend>Location modes</legend>
            <div className="route-toggle-grid">
              {LOCATION_MODE_OPTIONS.map((option) => (
                <label className="route-check" key={option}>
                  <input
                    checked={form.locationModes.includes(option)}
                    type="checkbox"
                    onChange={() =>
                      setForm((current) => ({
                        ...current,
                        locationModes: toggleValue(current.locationModes, option),
                      }))
                    }
                  />
                  <span>{displayLabel(option)}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <label className="wide-field">
            Constraints
            <input
              value={form.constraints}
              onChange={(event) =>
                setForm((current) => ({ ...current, constraints: event.target.value }))
              }
            />
          </label>
          <label className="route-check wide-field route-check-inline">
            <input
              checked={form.includeUnverified}
              type="checkbox"
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  includeUnverified: event.target.checked,
                }))
              }
            />
            <span>Include unverified with labels</span>
          </label>
          <button className="primary-button route-submit" disabled={state.loading} type="submit">
            {state.loading ? "Generating routes" : "Generate routes"}
          </button>
        </form>
      </section>

      {state.error ? (
        <section className="error-state">
          <strong>Routes unavailable</strong>
          <p>{state.error}</p>
        </section>
      ) : null}

      {routePayload ? (
        <section className="notice-state route-governance-note">
          <strong>{routePayload.route_count} route recommendations</strong>
          <p>{routePayload.route_generation_note}</p>
          <div className="badge-stack">
            {routePayload.non_goal_disclosures.map((disclosure) => (
              <span className="badge badge-unknown" key={disclosure}>
                {disclosure}
              </span>
            ))}
          </div>
        </section>
      ) : null}

      <section className="route-card-list" aria-label="Recommended Opportunity Routes">
        {routes.map((route) => (
          <OpportunityRouteCard key={route.route_id} route={route} />
        ))}
        {!state.loading && routePayload && routes.length === 0 ? (
          <div className="empty-state">
            <strong>No routes returned</strong>
            <p>The route endpoint returned an empty grouped route set.</p>
          </div>
        ) : null}
      </section>
    </div>
  );
}

function OpportunityRouteCard({ route }: { route: OpportunityRoute }) {
  return (
    <article className="card opportunity-route-card">
      <div className="card-header">
        <div>
          <p className="card-eyebrow">Best region / role-family path</p>
          <h2>{route.route_title}</h2>
        </div>
        <div className="route-score-pill">
          <span>{formatPercent(route.overall_route_fit_score)}</span>
          <small>{route.confidence} confidence</small>
        </div>
      </div>

      <p className="lead-copy">{route.explanation}</p>

      <div className="route-score-grid">
        <ScoreTile label="Market fit" value={route.market_fit_score} />
        <ScoreTile label="Region fit" value={route.region_fit_score} />
        <ScoreTile label="Company-type fit" value={route.company_type_fit_score} />
        <ScoreTile label="Role-family fit" value={route.role_family_fit_score} />
        <ScoreTile label="Opportunity fit" value={route.opportunity_fit_score} />
      </div>

      <section className="route-section">
        <h3>Recommended company types</h3>
        <div className="badge-stack">
          {route.recommended_company_types.map((companyType) => (
            <span className="badge" key={companyType}>
              {companyType}
            </span>
          ))}
        </div>
      </section>

      <section className="route-section">
        <h3>Matched verified programs</h3>
        <div className="route-program-list">
          {route.matched_opportunities.map((opportunity) => (
            <div className="route-program-row" key={opportunity.opportunity_id}>
              <div>
                <strong>{opportunity.program_name}</strong>
                <span>
                  {opportunity.employer_name} · {opportunity.region}
                  {opportunity.metro ? ` · ${opportunity.metro}` : ""}
                </span>
                <p>{opportunity.fit_explanation}</p>
                <div className="badge-stack">
                  <span className={`badge badge-${trustTone(opportunity.trust_label)}`}>
                    {displayLabel(opportunity.trust_label)}
                  </span>
                  <span className="badge">{displayLabel(opportunity.program_type)}</span>
                  <span className="badge">{displayLabel(opportunity.location_mode)}</span>
                  {opportunity.partner_submitted ? (
                    <span className="badge badge-warning">Partner submitted</span>
                  ) : null}
                  {opportunity.paid_partner ? (
                    <span className="badge badge-warning">Paid partner disclosed</span>
                  ) : null}
                </div>
                {opportunity.warnings.length ? (
                  <ul className="warning-list route-warning-list">
                    {opportunity.warnings.map((warning) => (
                      <li className="warning-item" key={warning}>
                        {warning}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
              <div className="route-program-actions">
                <span>{formatPercent(opportunity.fit_score)} fit</span>
                <a href={opportunity.source_url}>Source</a>
                <a href={opportunity.application_url}>Program page</a>
              </div>
            </div>
          ))}
          {route.matched_opportunities.length === 0 ? (
            <div className="empty-state">
              <strong>No trusted program attached</strong>
              <p>This route remains usable as strategic market guidance.</p>
            </div>
          ) : null}
        </div>
      </section>

      {route.sponsored_or_partner_disclosure ? (
        <section className="notice-state route-disclosure">
          <strong>Partner / paid disclosure</strong>
          <p>{route.sponsored_or_partner_disclosure}</p>
        </section>
      ) : null}

      {route.warnings.length ? (
        <section className="route-section">
          <h3>Warnings / caveats</h3>
          <ul className="warning-list">
            {route.warnings.map((warning) => (
              <li className="warning-item" key={warning}>
                {warning}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="route-section">
        <h3>Suggested next steps</h3>
        <ol className="route-next-steps">
          {route.next_steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </section>

      <section className="route-section route-source-summary">
        <h3>Source summary</h3>
        <p>
          {displayLabel(route.source_summary.data_basis)} · {route.source_summary.source_count} source
          {route.source_summary.source_count === 1 ? "" : "s"}
        </p>
        <div className="badge-stack">
          {route.source_summary.source_categories.map((category) => (
            <span className="badge badge-unknown" key={category}>
              {displayLabel(category)}
            </span>
          ))}
        </div>
      </section>
    </article>
  );
}

function ScoreTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="score-card score-card-compact">
      <span>{label}</span>
      <strong>{formatPercent(value)}</strong>
    </div>
  );
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function displayLabel(value: string): string {
  return value.replaceAll("_", " ").replaceAll("-", " ");
}

function trustTone(trustLabel: string): string {
  if (trustLabel === "verified" || trustLabel === "source_checked") return "success";
  if (trustLabel === "rejected" || trustLabel === "expired") return "error";
  return "warning";
}
