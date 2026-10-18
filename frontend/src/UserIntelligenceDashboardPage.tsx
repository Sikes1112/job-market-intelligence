import { useEffect, useState, type ReactNode } from "react";
import { getUserIntelligenceDashboard } from "./api";
import { TrustExplanationPanel } from "./TrustExplanation";
import UserReportControl from "./UserReportControl";
import type {
  ApiEnvelope,
  UserDashboardForecastChange,
  UserDashboardMarketWarning,
  UserDashboardNextAction,
  UserDashboardRecommendedCompany,
  UserDashboardRecommendedOpportunity,
  UserDashboardRecommendedRegion,
  UserDashboardSavedItem,
  UserDashboardWarningSeverity,
  UserIntelligenceDashboardPayload,
} from "./types";

type DashboardLoadState = {
  loading: boolean;
  envelope: ApiEnvelope<UserIntelligenceDashboardPayload> | null;
  error: string | null;
};

const emptyDashboardState: DashboardLoadState = {
  loading: false,
  envelope: null,
  error: null,
};

export default function UserIntelligenceDashboardPage() {
  const [state, setState] = useState<DashboardLoadState>(emptyDashboardState);

  useEffect(() => {
    let cancelled = false;
    async function loadDashboard() {
      setState((current) => ({ ...current, loading: true, error: null }));
      try {
        const envelope = await getUserIntelligenceDashboard();
        if (!cancelled) {
          setState({ loading: false, envelope, error: null });
        }
      } catch (error) {
        if (!cancelled) {
          setState({
            loading: false,
            envelope: null,
            error: error instanceof Error ? error.message : "Dashboard is unavailable",
          });
        }
      }
    }

    void loadDashboard();
    return () => {
      cancelled = true;
    };
  }, []);

  const dashboard = state.envelope?.data ?? null;

  return (
    <div className="view-grid user-intelligence-dashboard">
      <section className="card dashboard-hero-card">
        <div className="card-header">
          <div>
            <p className="card-eyebrow">User intelligence dashboard</p>
            <h2>{dashboard?.summary.headline ?? "Your current market intelligence"}</h2>
          </div>
          <div className="badge-stack">
            {state.loading ? <span className="badge badge-partial">Loading</span> : null}
            {dashboard ? <span className="badge">Layer {dashboard.dashboard_version}</span> : null}
            {dashboard ? <span className="badge badge-unknown">Generated {formatDateTime(dashboard.generated_at)}</span> : null}
          </div>
        </div>
        <p className="lead-copy">
          {dashboard?.summary.description
            ?? "Personalized recommendations, warnings, and next actions based on available data."}
        </p>
        {dashboard ? (
          <div className="dashboard-summary-grid">
            <SummaryMetric label="Recommendations" value={dashboard.summary.recommendation_count} />
            <SummaryMetric label="Warnings" value={dashboard.summary.warning_count} />
            <SummaryMetric
              label="Saved items"
              value={dashboard.saved_items.length}
            />
          </div>
        ) : null}
        {dashboard ? (
          <section className="notice-state dashboard-trust-context">
            <strong>Trust and confidence context</strong>
            <p>{dashboard.trust_context.message}</p>
            <div className="badge-stack">
              <span className="badge badge-success">
                Existing metadata only: {String(dashboard.trust_context.uses_existing_metadata_only)}
              </span>
              <span className="badge badge-unknown">
                Full trust engine available: {String(dashboard.trust_context.layer_30_full_trust_engine_available)}
              </span>
            </div>
          </section>
        ) : null}
      </section>

      {state.error ? (
        <section className="error-state">
          <strong>Dashboard unavailable</strong>
          <p>{state.error}</p>
        </section>
      ) : null}

      {dashboard ? (
        <>
          <DashboardModuleCard
            title="Recommended Regions"
            count={dashboard.recommended_regions.length}
            emptyTitle="No recommended regions"
            emptyBody="No scored market recommendations are available."
          >
            <div className="dashboard-module-grid">
              {dashboard.recommended_regions.map((region) => (
                <RecommendedRegionCard key={region.region_id} region={region} />
              ))}
            </div>
          </DashboardModuleCard>

          <DashboardModuleCard
            title="Recommended Companies"
            count={dashboard.recommended_companies.length}
            emptyTitle="No recommended companies"
            emptyBody="No employer recommendations with current hiring or early-career signals are available."
          >
            <div className="dashboard-module-grid">
              {dashboard.recommended_companies.map((company) => (
                <RecommendedCompanyCard key={company.company_id} company={company} />
              ))}
            </div>
          </DashboardModuleCard>

          <DashboardModuleCard
            title="Recommended Opportunities"
            count={dashboard.recommended_opportunities.length}
            emptyTitle="No recommended opportunities"
            emptyBody="No active opportunity records were returned for dashboard display."
          >
            <div className="dashboard-module-grid">
              {dashboard.recommended_opportunities.map((opportunity) => (
                <RecommendedOpportunityCard
                  key={opportunity.opportunity_id}
                  opportunity={opportunity}
                />
              ))}
            </div>
          </DashboardModuleCard>

          <DashboardModuleCard
            id="warnings"
            title="Market Warnings"
            count={dashboard.market_warnings.length}
            emptyTitle="No market warnings"
            emptyBody="No warning, stale freshness, weak confidence, partner-submitted, or forecast limitation metadata was returned."
          >
            <div className="dashboard-warning-list">
              {dashboard.market_warnings.map((warning) => (
                <MarketWarningCard key={`${warning.subject_type}:${warning.subject_id}:${warning.warning_code}`} warning={warning} />
              ))}
            </div>
          </DashboardModuleCard>

          <DashboardModuleCard
            title="Forecast Changes or Market Movement"
            count={dashboard.forecast_changes.length}
            emptyTitle="No forecast changes"
            emptyBody="No movement signals are available for the recommended subjects."
          >
            <div className="dashboard-module-grid">
              {dashboard.forecast_changes.map((forecast) => (
                <ForecastChangeCard key={`${forecast.subject_type}:${forecast.subject_id}:${forecast.title}`} forecast={forecast} />
              ))}
            </div>
          </DashboardModuleCard>

          <DashboardModuleCard
            title="Saved or Relevant Items"
            count={dashboard.saved_items.length}
            emptyTitle="No saved items in this dashboard"
            emptyBody="No saved items yet."
          >
            <div className="dashboard-module-grid">
              {dashboard.saved_items.map((item) => (
                <SavedItemCard key={item.item_id} item={item} />
              ))}
            </div>
          </DashboardModuleCard>

          <DashboardModuleCard
            title="Recommended Next Actions"
            count={dashboard.recommended_next_actions.length}
            emptyTitle="No next actions"
            emptyBody="There is not enough information to suggest a next action."
          >
            <div className="dashboard-action-grid">
              {dashboard.recommended_next_actions.map((action) => (
                <NextActionCard key={action.action_code} action={action} />
              ))}
            </div>
          </DashboardModuleCard>
        </>
      ) : null}
    </div>
  );
}

function DashboardModuleCard({
  children,
  count,
  emptyBody,
  emptyTitle,
  id,
  title,
}: {
  children: ReactNode;
  count: number;
  emptyBody: string;
  emptyTitle: string;
  id?: string;
  title: string;
}) {
  return (
    <section className="card dashboard-module-card" id={id}>
      <div className="card-header">
        <div>
          <p className="card-eyebrow">Command center module</p>
          <h2>{title}</h2>
        </div>
        <span className="badge">{count}</span>
      </div>
      {count > 0 ? children : (
        <div className="empty-state">
          <strong>{emptyTitle}</strong>
          <p>{emptyBody}</p>
        </div>
      )}
    </section>
  );
}

function RecommendedRegionCard({ region }: { region: UserDashboardRecommendedRegion }) {
  return (
    <article className="dashboard-item-card">
      <div>
        <p className="card-eyebrow">Region</p>
        <h3>{region.region_name}</h3>
      </div>
      <p>{region.why_recommended}</p>
      <ConfidenceSummary
        confidence={region.confidence}
        freshness={region.freshness}
        rankingInfluenceAllowed={region.ranking_influence_allowed}
      />
      <div className="badge-stack">
        <span className="badge">Score {scoreLabel(region.score)}</span>
        <OptionalBadge label="Trust tier" value={region.trust_tier} />
        <OptionalBadge label="Risk" value={region.risk_level} />
        <OptionalBadge label="Routing" value={region.routing_outcome} />
      </div>
      <WarningList warnings={region.warnings} />
    </article>
  );
}

function RecommendedCompanyCard({ company }: { company: UserDashboardRecommendedCompany }) {
  return (
    <article className="dashboard-item-card">
      <div>
        <p className="card-eyebrow">Company</p>
        <h3>{company.company_name}</h3>
      </div>
      <p>{company.why_recommended}</p>
      <ConfidenceSummary
        confidence={company.confidence}
        freshness={company.freshness}
        rankingInfluenceAllowed={company.ranking_influence_allowed}
      />
      <div className="badge-stack">
        <span className="badge">Score {scoreLabel(company.score)}</span>
        <OptionalBadge label="Trust tier" value={company.trust_tier} />
        <OptionalBadge label="Risk" value={company.risk_level} />
        <OptionalBadge label="Routing" value={company.routing_outcome} />
      </div>
      <WarningList warnings={company.warnings} />
    </article>
  );
}

function RecommendedOpportunityCard({
  opportunity,
}: {
  opportunity: UserDashboardRecommendedOpportunity;
}) {
  return (
    <article className="dashboard-item-card">
      <div>
        <p className="card-eyebrow">Opportunity</p>
        <h3>{opportunity.title}</h3>
      </div>
      <p>
        {opportunity.company_name}
        {opportunity.region_name ? ` | ${opportunity.region_name}` : ""}
      </p>
      <p>{opportunity.why_recommended}</p>
      <div className="badge-stack">
        {opportunity.trust_label ? <span className="badge">Trust label: {displayLabel(opportunity.trust_label)}</span> : null}
        {opportunity.review_status ? <span className="badge">Review status: {displayLabel(opportunity.review_status)}</span> : null}
        {opportunity.expiration_state ? <span className="badge">Expiration: {displayLabel(opportunity.expiration_state)}</span> : null}
        {opportunity.source_type ? <span className="badge">Source: {displayLabel(opportunity.source_type)}</span> : null}
        {opportunity.partner_submitted ? <span className="badge badge-warning">Partner submitted</span> : null}
        <span className={opportunity.ranking_influence_allowed ? "badge badge-success" : "badge badge-warning"}>
          Ranking influence: {opportunity.ranking_influence_allowed ? "allowed" : "not allowed"}
        </span>
        <OptionalBadge label="Trust tier" value={opportunity.trust_tier} />
        <OptionalBadge label="Risk" value={opportunity.risk_level} />
        <OptionalBadge label="Routing" value={opportunity.routing_outcome} />
        <OptionalBadge label="Ranking decision" value={opportunity.ranking_influence_decision} />
      </div>
      {opportunity.ranking_influence_reason ? (
        <small>Ranking reason: {opportunity.ranking_influence_reason}</small>
      ) : null}
      {opportunity.ranking_influence_reason_codes?.length ? (
        <small>
          Ranking reason codes:{" "}
          {opportunity.ranking_influence_reason_codes.map(displayLabel).join(", ")}
        </small>
      ) : null}
      {opportunity.evidence_summary ? (
        <small>
          Evidence met {opportunity.evidence_summary.met_count ?? 0} | missing{" "}
          {opportunity.evidence_summary.missing_count ?? 0} | failed{" "}
          {opportunity.evidence_summary.failed_count ?? 0}
        </small>
      ) : null}
      <TrustExplanationPanel
        compact
        explanation={opportunity.trust_explanation ?? null}
      />
      <UserReportControl
        exceptionStatus={opportunity.exception_status ?? null}
        initialStatus={opportunity.report_recheck_status ?? null}
        sourceSurface="user_intelligence_dashboard"
        subjectId={opportunity.opportunity_id}
        subjectType="opportunity"
      />
      <WarningList warnings={opportunity.warnings} />
    </article>
  );
}

function MarketWarningCard({ warning }: { warning: UserDashboardMarketWarning }) {
  return (
    <article className="dashboard-warning-card">
      <div className="card-header">
        <div>
          <p className="card-eyebrow">{displayLabel(warning.subject_type)}</p>
          <h3>{warning.title}</h3>
        </div>
        <span className={warningBadgeClass(warning.severity)}>{displayLabel(warning.severity)}</span>
      </div>
      <p>{warning.message}</p>
      <small>
        {warning.subject_id} | {displayLabel(warning.source)} | {warning.warning_code}
      </small>
    </article>
  );
}

function ForecastChangeCard({ forecast }: { forecast: UserDashboardForecastChange }) {
  return (
    <article className="dashboard-item-card">
      <div>
        <p className="card-eyebrow">{displayLabel(forecast.subject_type)}</p>
        <h3>{forecast.title}</h3>
      </div>
      <p>{forecast.summary}</p>
      <ConfidenceSummary
        confidence={forecast.confidence}
        freshness={forecast.freshness}
        rankingInfluenceAllowed={null}
      />
      <WarningList warnings={forecast.warnings} />
    </article>
  );
}

function SavedItemCard({ item }: { item: UserDashboardSavedItem }) {
  return (
    <article className="dashboard-item-card">
      <p className="card-eyebrow">{displayLabel(item.item_type)}</p>
      <h3>{item.label}</h3>
      {item.target_route ? <a href={item.target_route}>Open item</a> : null}
    </article>
  );
}

function NextActionCard({ action }: { action: UserDashboardNextAction }) {
  const body = (
    <>
      <div>
        <p className="card-eyebrow">Next action</p>
        <h3>{action.label}</h3>
      </div>
      <p>{action.description}</p>
      <span className={priorityBadgeClass(action.priority)}>
        Priority: {displayLabel(action.priority)}
      </span>
    </>
  );
  return action.target_route ? (
    <a className="dashboard-action-card" href={action.target_route}>
      {body}
    </a>
  ) : (
    <article className="dashboard-action-card">{body}</article>
  );
}

function SummaryMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="score-card score-card-compact">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ConfidenceSummary({
  confidence,
  freshness,
  rankingInfluenceAllowed,
}: {
  confidence: string | null;
  freshness: string | null;
  rankingInfluenceAllowed: boolean | null;
}) {
  return (
    <div className="badge-stack">
      <span className="badge">Confidence: {displayValue(confidence)}</span>
      <span className="badge">Freshness: {displayValue(freshness)}</span>
      {rankingInfluenceAllowed === null ? (
        <span className="badge badge-unknown">Ranking influence: unavailable</span>
      ) : (
        <span className={rankingInfluenceAllowed ? "badge badge-success" : "badge badge-warning"}>
          Ranking influence: {rankingInfluenceAllowed ? "allowed" : "not allowed"}
        </span>
      )}
    </div>
  );
}

function OptionalBadge({ label, value }: { label: string; value?: string | null }) {
  return value ? <span className="badge">{label}: {displayLabel(value)}</span> : null;
}

function WarningList({ warnings }: { warnings: string[] }) {
  if (!warnings.length) return null;
  return (
    <ul className="warning-list dashboard-warning-list-inline">
      {warnings.map((warning) => (
        <li className="warning-item" key={warning}>
          {warning}
        </li>
      ))}
    </ul>
  );
}

function displayLabel(value: string): string {
  return value.replaceAll("_", " ").replaceAll("-", " ");
}

function displayValue(value: string | null): string {
  return value ? displayLabel(value) : "unavailable";
}

function scoreLabel(value: number | null): string {
  return typeof value === "number" ? value.toFixed(2) : "unavailable";
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "n/a";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function warningBadgeClass(severity: UserDashboardWarningSeverity): string {
  if (severity === "critical") return "badge badge-error";
  if (severity === "warning") return "badge badge-warning";
  return "badge badge-unknown";
}

function priorityBadgeClass(priority: string): string {
  if (priority === "high") return "badge badge-warning";
  if (priority === "medium") return "badge badge-real";
  return "badge badge-unknown";
}
