import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import {
  API_TARGET_LABEL,
  discoverPersonalized,
  getCompany,
  getComparison,
  getHealth,
  getRegion,
  getRegions,
} from "./api";
import type {
  ApiEnvelope,
  CompanyDetail,
  ComparisonDetail,
  PersonalizedResult,
  RegionDetail,
  RegionListItem,
  RegionScores,
  WarningItem,
} from "./types";

const DEFAULT_REGION_A = "greater_boston";
const DEFAULT_REGION_B = "greater_sf";

const ROLE_TARGETS = ["product", "ai_cloud_adjacent", "cybersecurity"];
const INDUSTRY_OPTIONS = ["software", "ai", "cloud", "data", "cybersecurity"];
const PREFERENCE_LEVELS = ["low", "medium", "high"];

const SCORE_FIELDS: Array<{ key: keyof RegionScores; label: string; short: string }> = [
  {
    key: "structural_ecosystem_score",
    label: "Structural ecosystem",
    short: "Ecosystem",
  },
  { key: "live_market_score", label: "Live market", short: "Live market" },
  {
    key: "objective_opportunity_score",
    label: "Objective opportunity",
    short: "Opportunity",
  },
  { key: "raw_total_score", label: "Raw total", short: "Total" },
  { key: "general_density_score", label: "General density", short: "Density" },
  {
    key: "tech_market_density_score",
    label: "Tech market density",
    short: "Tech density",
  },
  {
    key: "early_career_accessibility_score",
    label: "Early-career accessibility",
    short: "Early career",
  },
];

type ViewId = "overview" | "regions" | "companies" | "comparison" | "discovery";
type LoadState<T> = {
  loading: boolean;
  envelope: ApiEnvelope<T> | null;
  error: string | null;
};
type CompanyOption = {
  company_id: string;
  company_name: string;
  sector_primary?: string | null;
  source_regions: string[];
};

const VIEW_ITEMS: Array<{ id: ViewId; label: string; kicker: string }> = [
  { id: "overview", label: "Overview", kicker: "System snapshot" },
  { id: "regions", label: "Region Explorer", kicker: "Market output" },
  { id: "companies", label: "Company Explorer", kicker: "Geography output" },
  { id: "comparison", label: "Boston vs SF", kicker: "Score comparison" },
  { id: "discovery", label: "Discovery", kicker: "Personal overlay" },
];

function emptyLoadState<T>(): LoadState<T> {
  return { loading: false, envelope: null, error: null };
}

function prettyKey(value: string) {
  return value.replaceAll("_", " ");
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "n/a";
  if (typeof value === "number") {
    return Number.isInteger(value) ? `${value}` : value.toFixed(2);
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "None";
  return String(value);
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "n/a";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function scorePercent(value: number | null | undefined) {
  if (typeof value !== "number") return 0;
  return Math.max(0, Math.min(100, value * 100));
}

function warningCode(warning: WarningItem): string {
  if (typeof warning === "string") return warning;
  const code = warning.warning_code ?? warning.code;
  return typeof code === "string" && code.trim() ? code : "warning";
}

function warningMessage(warning: WarningItem): string {
  if (typeof warning === "string") return warning;
  return typeof warning.message === "string" && warning.message.trim()
    ? warning.message
    : "No warning message provided.";
}

function warningSeverity(warning: WarningItem): string | null {
  if (typeof warning === "string") return null;
  return typeof warning.severity === "string" && warning.severity.trim()
    ? warning.severity
    : null;
}

function warningScope(warning: WarningItem): string | null {
  if (typeof warning === "string") return null;
  const scopeType = typeof warning.scope_type === "string" ? warning.scope_type : "";
  const scopeRef = typeof warning.scope_ref === "string" ? warning.scope_ref : "";
  if (!scopeType && !scopeRef) return null;
  return [scopeType, scopeRef].filter(Boolean).join(": ");
}

function hasStructuredWarningDetails(warning: WarningItem): boolean {
  return typeof warning !== "string";
}

function isSeedDemoFreshness(value: string | null | undefined): boolean {
  if (!value) return false;
  const date = new Date(value);
  return !Number.isNaN(date.getTime()) && date.getUTCFullYear() >= 2090;
}

function freshnessText(freshness: ApiEnvelope<unknown>["metadata"]["freshness"]): string {
  if (!freshness) return "";
  const status =
    freshness.freshness_status
    ?? (freshness.freshness_expires_at
      ? freshness.is_stale
        ? "stale"
        : "fresh"
      : "unknown");
  if (status === "unknown") return "Freshness not tracked";
  const expires = formatDateTime(freshness.freshness_expires_at);
  const label = status === "stale" ? "Stale" : "Fresh";
  if (isSeedDemoFreshness(freshness.freshness_expires_at)) {
    return `${label} · Seed demo freshness · Expires: ${expires}`;
  }
  return `${label} · Expires: ${expires}`;
}

function winnerLabel(regionId: string | null | undefined, regions: RegionListItem[], comparison?: ComparisonDetail | null) {
  if (!regionId) return "Tie";
  const fromComparison = [comparison?.region_a, comparison?.region_b].find(
    (region) => region?.region_id === regionId,
  );
  if (fromComparison?.display_name) return fromComparison.display_name;
  return regions.find((region) => region.region_id === regionId)?.display_name ?? regionId;
}

function getCompanyOptions(regionDetails: Record<string, ApiEnvelope<RegionDetail>>): CompanyOption[] {
  const companies = new Map<string, CompanyOption>();

  Object.values(regionDetails).forEach((envelope) => {
    const region = envelope.data;
    if (!region) return;

    [...region.top_companies_present, ...region.top_companies_hiring].forEach((company) => {
      const current = companies.get(company.company_id);
      if (current) {
        current.source_regions = Array.from(
          new Set([...current.source_regions, region.display_name]),
        );
        return;
      }

      companies.set(company.company_id, {
        company_id: company.company_id,
        company_name: company.company_name,
        sector_primary: "sector_primary" in company ? company.sector_primary : null,
        source_regions: [region.display_name],
      });
    });
  });

  return Array.from(companies.values()).sort((left, right) =>
    left.company_name.localeCompare(right.company_name),
  );
}

function pickEnvelopeWarnings(envelope?: ApiEnvelope<unknown> | null) {
  return envelope?.metadata?.warnings ?? [];
}

function StateBadge({
  envelope,
  loading,
  error,
}: {
  envelope?: ApiEnvelope<unknown> | null;
  loading?: boolean;
  error?: string | null;
}) {
  const state = error ? "error" : loading ? "loading" : envelope?.metadata.state ?? "unknown";
  const className = `badge badge-${state}`;
  return <span className={className}>{state}</span>;
}

function MetadataPanel({ envelope }: { envelope?: ApiEnvelope<unknown> | null }) {
  const freshness = envelope?.metadata.freshness;
  const warnings = pickEnvelopeWarnings(envelope);
  const seedDemoFreshness = isSeedDemoFreshness(freshness?.freshness_expires_at);
  const freshnessStatus =
    freshness?.freshness_status
    ?? (freshness?.freshness_expires_at
      ? freshness.is_stale
        ? "stale"
        : "fresh"
      : "unknown");

  return (
    <div className="metadata-panel">
      <div className="metadata-row">
        <StateBadge envelope={envelope} />
        {freshness && freshnessStatus === "fresh" ? <span className="badge badge-fresh">Fresh</span> : null}
        {freshnessStatus === "stale" ? <span className="badge badge-stale">stale</span> : null}
        {freshness && freshnessStatus === "unknown" ? <span className="badge">Freshness unknown</span> : null}
        {seedDemoFreshness ? <span className="badge badge-demo">Seed demo freshness</span> : null}
        {warnings.length ? <span className="badge badge-warning">{warnings.length} warning(s)</span> : null}
      </div>
      {freshness ? (
        <div className="freshness-copy">
          <p>{freshnessText(freshness)}</p>
          <small>Updated: {formatDateTime(freshness.last_updated_at)}</small>
        </div>
      ) : null}
      {warnings.length ? (
        <div className="warning-list">
          {warnings.map((warning, index) => (
            <div className="warning-item" key={index}>
              <div className="warning-header">
                <span className="warning-code">{prettyKey(warningCode(warning))}</span>
                {warningSeverity(warning) ? (
                  <span className="badge badge-warning">{warningSeverity(warning)}</span>
                ) : null}
              </div>
              <p>{warningMessage(warning)}</p>
              {warningScope(warning) ? <small>{warningScope(warning)}</small> : null}
              {hasStructuredWarningDetails(warning) ? (
                <details className="warning-debug">
                  <summary>Details</summary>
                  <pre>{JSON.stringify(warning, null, 2)}</pre>
                </details>
              ) : null}
            </div>
          ))}
        </div>
      ) : (
        <p className="meta-copy">No metadata warnings.</p>
      )}
    </div>
  );
}

function ShellCard({
  title,
  eyebrow,
  action,
  children,
}: {
  title: string;
  eyebrow?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="card">
      <div className="card-header">
        <div>
          {eyebrow ? <p className="card-eyebrow">{eyebrow}</p> : null}
          <h2>{title}</h2>
        </div>
        {action ? <div className="card-action">{action}</div> : null}
      </div>
      {children}
    </section>
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

function ErrorState({ message }: { message: string }) {
  return (
    <div className="error-state">
      <strong>Request failed</strong>
      <p>{message}</p>
    </div>
  );
}

function LoadingBlock({ label = "Loading data" }: { label?: string }) {
  return (
    <div className="loading-block">
      <span />
      {label}
    </div>
  );
}

function ScoreCard({
  label,
  value,
  compact = false,
}: {
  label: string;
  value: number | null | undefined;
  compact?: boolean;
}) {
  return (
    <div className={compact ? "score-card score-card-compact" : "score-card"}>
      <div className="score-topline">
        <span>{label}</span>
        <strong>{formatValue(value)}</strong>
      </div>
      <div className="score-track" aria-hidden="true">
        <span style={{ width: `${scorePercent(value)}%` }} />
      </div>
    </div>
  );
}

function StatGrid({ values }: { values: Record<string, unknown> }) {
  const entries = Object.entries(values);
  if (!entries.length) {
    return <EmptyState title="No values" body="This output did not include summary metrics." />;
  }

  return (
    <div className="stat-grid">
      {entries.map(([key, value]) => (
        <div className="stat-card" key={key}>
          <span>{prettyKey(key)}</span>
          <strong>{formatValue(value)}</strong>
        </div>
      ))}
    </div>
  );
}

function RegionScoreGrid({ scores }: { scores: RegionScores | null | undefined }) {
  if (!scores) {
    return <EmptyState title="Scores unavailable" body="No score object was returned for this region." />;
  }

  return (
    <div className="score-grid">
      {SCORE_FIELDS.map((score) => (
        <ScoreCard key={score.key} label={score.label} value={scores[score.key] as number | null} />
      ))}
    </div>
  );
}

function CompanyList({
  companies,
  mode,
  onSelectCompany,
}: {
  companies: RegionDetail["top_companies_present"] | RegionDetail["top_companies_hiring"];
  mode: "present" | "hiring";
  onSelectCompany: (companyId: string) => void;
}) {
  if (!companies.length) {
    return <EmptyState title="No companies" body="This section is empty for the selected output." />;
  }

  return (
    <div className="company-list">
      {companies.map((company) => (
        <button
          className="company-row"
          key={company.company_id}
          type="button"
          onClick={() => onSelectCompany(company.company_id)}
        >
          <span>
            <strong>{company.company_name}</strong>
            <small>
              {mode === "present"
                ? `${formatValue("sector_primary" in company ? company.sector_primary : null)} · ${formatValue(
                    "eligibility_status" in company ? company.eligibility_status : null,
                  )}`
                : `${formatValue("active_posting_count_now" in company ? company.active_posting_count_now : null)} active · ${formatValue(
                    "posting_count_90d" in company ? company.posting_count_90d : null,
                  )} in 90d`}
            </small>
          </span>
          <span className="row-arrow">View</span>
        </button>
      ))}
    </div>
  );
}

function Overview({
  health,
  regions,
  regionDetails,
  onNavigate,
  onSelectRegion,
}: {
  health: LoadState<{ service: string }>;
  regions: LoadState<{ regions: RegionListItem[] }>;
  regionDetails: Record<string, ApiEnvelope<RegionDetail>>;
  onNavigate: (view: ViewId) => void;
  onSelectRegion: (regionId: string) => void;
}) {
  const regionList = regions.envelope?.data?.regions ?? [];
  const boston = regionDetails[DEFAULT_REGION_A]?.data;
  const sf = regionDetails[DEFAULT_REGION_B]?.data;

  return (
    <div className="view-grid">
      <ShellCard
        title="Opportunity market intelligence for early-career tech paths"
        eyebrow="Product overview"
        action={<StateBadge envelope={health.envelope} loading={health.loading} error={health.error} />}
      >
        <p className="lead-copy">
          Job Market Intelligence turns prepared backend market truth into practical region,
          company, comparison, and personalized discovery views. This demo uses the seeded
          Greater Boston and Greater San Francisco / Silicon Valley dataset.
        </p>
        <div className="hero-actions">
          <button type="button" onClick={() => onNavigate("regions")}>
            Explore regions
          </button>
          <button className="secondary-button" type="button" onClick={() => onNavigate("comparison")}>
            Compare Boston vs SF
          </button>
        </div>
      </ShellCard>

      <div className="overview-grid">
        <ShellCard title="Backend status" eyebrow="GET /health">
          {health.loading ? <LoadingBlock /> : null}
          {health.error ? <ErrorState message={health.error} /> : null}
          {health.envelope ? (
            <div className="health-card">
              <span className="health-dot" />
              <div>
                <strong>{health.envelope.data?.service ?? "unknown"}</strong>
                <p>Envelope status: {health.envelope.status}</p>
              </div>
            </div>
          ) : null}
        </ShellCard>

        <ShellCard title="Available regions" eyebrow="GET /regions">
          {regions.loading ? <LoadingBlock /> : null}
          {regions.error ? <ErrorState message={regions.error} /> : null}
          {regionList.length ? (
            <div className="region-chip-list">
              {regionList.map((region) => (
                <button
                  className="region-chip"
                  key={region.region_id}
                  type="button"
                  onClick={() => {
                    onSelectRegion(region.region_id);
                    onNavigate("regions");
                  }}
                >
                  <strong>{region.display_name}</strong>
                  <span>{region.region_id}</span>
                </button>
              ))}
            </div>
          ) : !regions.loading ? (
            <EmptyState title="No regions loaded" body="Seed the demo database and refresh." />
          ) : null}
        </ShellCard>
      </div>

      <div className="quick-region-grid">
        {[
          { fallbackKey: DEFAULT_REGION_A, region: boston },
          { fallbackKey: DEFAULT_REGION_B, region: sf },
        ].map(({ fallbackKey, region }) =>
          region ? (
            <button
              className="quick-region-card"
              key={region.region_id}
              type="button"
              onClick={() => {
                onSelectRegion(region.region_id);
                onNavigate("regions");
              }}
            >
              <span>{region.region_type}</span>
              <strong>{region.display_name}</strong>
              <div className="quick-score-row">
                <ScoreCard compact label="Total score" value={region.scores?.raw_total_score} />
                <ScoreCard
                  compact
                  label="Early career"
                  value={region.scores?.early_career_accessibility_score}
                />
              </div>
            </button>
          ) : (
            <div className="quick-region-card quick-region-placeholder" key={fallbackKey}>
              <LoadingBlock label="Loading seeded region" />
            </div>
          ),
        )}
      </div>
    </div>
  );
}

function RegionExplorer({
  regions,
  selectedRegionId,
  regionState,
  onSelectRegion,
  onSelectCompany,
}: {
  regions: RegionListItem[];
  selectedRegionId: string;
  regionState: LoadState<RegionDetail>;
  onSelectRegion: (regionId: string) => void;
  onSelectCompany: (companyId: string) => void;
}) {
  const region = regionState.envelope?.data;

  return (
    <div className="view-grid">
      <ShellCard
        title="Region explorer"
        eyebrow="GET /regions/{region_id}"
        action={<StateBadge envelope={regionState.envelope} loading={regionState.loading} error={regionState.error} />}
      >
        <div className="toolbar">
          <label>
            Select region
            <select value={selectedRegionId} onChange={(event) => onSelectRegion(event.target.value)}>
              {regions.map((item) => (
                <option key={item.region_id} value={item.region_id}>
                  {item.display_name}
                </option>
              ))}
            </select>
          </label>
        </div>

        {regionState.loading ? <LoadingBlock label="Loading region output" /> : null}
        {regionState.error ? <ErrorState message={regionState.error} /> : null}
        {!regionState.loading && !regionState.error && !region ? (
          <EmptyState title="No region selected" body="Choose a region from the dropdown." />
        ) : null}
      </ShellCard>

      {region ? (
        <>
          <ShellCard title={region.display_name} eyebrow="Region detail">
            <div className="detail-hero">
              <div>
                <p className="meta-copy">
                  {region.region_id} · {region.labor_market_group ?? "unknown labor market"}
                </p>
                <h3>Market summary</h3>
              </div>
              <MetadataPanel envelope={regionState.envelope} />
            </div>
            <StatGrid values={region.summary} />
          </ShellCard>

          <ShellCard title="Stored scores" eyebrow="Region score fields">
            <RegionScoreGrid scores={region.scores} />
          </ShellCard>

          <div className="split-grid">
            <ShellCard title="Top companies present" eyebrow="Presence output">
              <CompanyList companies={region.top_companies_present} mode="present" onSelectCompany={onSelectCompany} />
            </ShellCard>

            <ShellCard title="Companies hiring" eyebrow="Hiring output">
              <CompanyList companies={region.top_companies_hiring} mode="hiring" onSelectCompany={onSelectCompany} />
            </ShellCard>
          </div>

          <div className="split-grid">
            <ShellCard title="Entry-level summary" eyebrow="Early-career signals">
              <StatGrid values={region.entry_level_summary} />
            </ShellCard>

            <ShellCard title="Major-tech and Mag 7" eyebrow="Classification summary">
              <StatGrid
                values={{
                  major_tech_count: region.major_tech_summary.count,
                  major_tech_companies: region.major_tech_summary.company_ids,
                  mag7_count: region.mag7_summary.count,
                  mag7_companies: region.mag7_summary.company_ids,
                }}
              />
            </ShellCard>
          </div>
        </>
      ) : null}
    </div>
  );
}

function CompanyExplorer({
  companyOptions,
  selectedCompanyId,
  companyState,
  onSelectCompany,
}: {
  companyOptions: CompanyOption[];
  selectedCompanyId: string;
  companyState: LoadState<CompanyDetail>;
  onSelectCompany: (companyId: string) => void;
}) {
  const company = companyState.envelope?.data;

  return (
    <div className="view-grid">
      <ShellCard
        title="Company explorer"
        eyebrow="GET /companies/{company_id}"
        action={<StateBadge envelope={companyState.envelope} loading={companyState.loading} error={companyState.error} />}
      >
        <div className="toolbar">
          <label>
            Select company
            <select
              value={selectedCompanyId}
              onChange={(event) => onSelectCompany(event.target.value)}
              disabled={!companyOptions.length}
            >
              {companyOptions.map((item) => (
                <option key={item.company_id} value={item.company_id}>
                  {item.company_name}
                </option>
              ))}
            </select>
          </label>
        </div>
        {!companyOptions.length ? (
          <EmptyState
            title="No company list endpoint"
            body="Companies are derived from loaded region outputs. Load a region first."
          />
        ) : null}
        {companyState.loading ? <LoadingBlock label="Loading company output" /> : null}
        {companyState.error ? <ErrorState message={companyState.error} /> : null}
      </ShellCard>

      {company ? (
        <>
          <ShellCard title={company.company_name} eyebrow="Classification">
            <div className="classification-layout">
              <StatGrid
                values={{
                  eligibility_status: company.eligibility_status,
                  classification_confidence: company.classification_confidence,
                  sector_primary: company.sector_primary,
                  sector_secondary: company.sector_secondary,
                  eligibility_override: company.eligibility_override_flag,
                  prestige_score: company.prestige_score,
                }}
              />
              <div className="badge-stack">
                <span className={company.is_major_tech ? "badge badge-fresh" : "badge"}>Major tech: {formatValue(company.is_major_tech)}</span>
                <span className={company.is_mag7 ? "badge badge-fresh" : "badge"}>Mag 7: {formatValue(company.is_mag7)}</span>
              </div>
            </div>
            <MetadataPanel envelope={companyState.envelope} />
          </ShellCard>

          <div className="split-grid">
            <ShellCard title="Regions present" eyebrow="Presence">
              {company.regions_present.length ? (
                <div className="stack-list">
                  {company.regions_present.map((region) => (
                    <div className="stack-row" key={region.region_id}>
                      <strong>{region.region_display_name}</strong>
                      <span>
                        {formatValue(region.presence_basis)} · {formatValue(region.presence_confidence)}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="No presence rows" body="No region presence was returned." />
              )}
            </ShellCard>

            <ShellCard title="Regions hiring" eyebrow="Hiring">
              {company.regions_hiring.length ? (
                <div className="stack-list">
                  {company.regions_hiring.map((region) => (
                    <div className="stack-row" key={region.region_id}>
                      <strong>{region.region_display_name}</strong>
                      <span>
                        {formatValue(region.active_posting_count_now)} active ·{" "}
                        {formatValue(region.posting_count_90d)} in 90d
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="No hiring rows" body="No active hiring rows were returned." />
              )}
            </ShellCard>
          </div>

          <ShellCard title="Entry-level regions" eyebrow="Internship, co-op, full-time">
            {company.entry_level_regions.length ? (
              <div className="entry-grid">
                {company.entry_level_regions.map((region) => (
                  <div className="entry-card" key={region.region_id}>
                    <h3>{region.region_display_name}</h3>
                    <ScoreCard label="Access score" value={region.entry_level_access_score} />
                    <StatGrid
                      values={{
                        internships: region.internship_count,
                        coops: region.coop_count,
                        entry_level_full_time: region.entry_level_full_time_count,
                        formal_program: region.formal_early_career_program_flag,
                        confidence: region.entry_level_confidence,
                      }}
                    />
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No entry-level rows" body="No early-career output was returned." />
            )}
          </ShellCard>
        </>
      ) : null}
    </div>
  );
}

function ComparisonView({
  regions,
  regionA,
  regionB,
  comparisonState,
  onRegionA,
  onRegionB,
}: {
  regions: RegionListItem[];
  regionA: string;
  regionB: string;
  comparisonState: LoadState<ComparisonDetail>;
  onRegionA: (regionId: string) => void;
  onRegionB: (regionId: string) => void;
}) {
  const comparison = comparisonState.envelope?.data;

  return (
    <div className="view-grid">
      <ShellCard
        title="Region comparison"
        eyebrow="GET /compare"
        action={<StateBadge envelope={comparisonState.envelope} loading={comparisonState.loading} error={comparisonState.error} />}
      >
        <div className="comparison-controls">
          <label>
            Region A
            <select value={regionA} onChange={(event) => onRegionA(event.target.value)}>
              {regions.map((region) => (
                <option key={region.region_id} value={region.region_id}>
                  {region.display_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Region B
            <select value={regionB} onChange={(event) => onRegionB(event.target.value)}>
              {regions.map((region) => (
                <option key={region.region_id} value={region.region_id}>
                  {region.display_name}
                </option>
              ))}
            </select>
          </label>
        </div>

        {regionA === regionB ? (
          <ErrorState message="Choose two distinct regions before running comparison." />
        ) : null}
        {comparisonState.loading ? <LoadingBlock label="Loading comparison output" /> : null}
        {comparisonState.error ? <ErrorState message={comparisonState.error} /> : null}
      </ShellCard>

      {comparison ? (
        <>
          <ShellCard title={`${comparison.region_a.display_name} vs ${comparison.region_b.display_name}`} eyebrow="Stored score values">
            <div className="comparison-score-table">
              <div className="comparison-table-head">
                <span>Category</span>
                <strong>{comparison.region_a.display_name}</strong>
                <strong>{comparison.region_b.display_name}</strong>
                <strong>Winner</strong>
              </div>
              {SCORE_FIELDS.map((score) => {
                const aValue = comparison.region_a.scores?.[score.key] as number | null | undefined;
                const bValue = comparison.region_b.scores?.[score.key] as number | null | undefined;
                const hasWinner = Object.prototype.hasOwnProperty.call(comparison.category_winners, score.key);
                const winner = comparison.category_winners[score.key];
                return (
                  <div className="comparison-table-row" key={score.key}>
                    <span>{score.label}</span>
                    <ScoreCard compact label={score.short} value={aValue} />
                    <ScoreCard compact label={score.short} value={bValue} />
                    <strong>{hasWinner ? winnerLabel(winner, regions, comparison) : "Not available"}</strong>
                  </div>
                );
              })}
            </div>
          </ShellCard>

          <div className="split-grid">
            <ShellCard title="Category winners" eyebrow="Comparison output">
              {Object.keys(comparison.category_winners).length ? (
                <div className="winner-grid">
                  {Object.entries(comparison.category_winners).map(([category, winner]) => (
                    <div className="winner-card" key={category}>
                      <span>{prettyKey(category)}</span>
                      <strong>{winnerLabel(winner, regions, comparison)}</strong>
                      {winner ? <small>{winner}</small> : null}
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState
                  title="No resolved winners"
                  body="One or both regions may be missing comparable score values."
                />
              )}
            </ShellCard>

            <ShellCard title="Notes and warnings" eyebrow="Metadata">
              {comparison.notes.length ? (
                <ul className="notes-list">
                  {comparison.notes.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              ) : (
                <EmptyState title="No notes" body="The comparison output did not include notes." />
              )}
              <MetadataPanel envelope={comparisonState.envelope} />
            </ShellCard>
          </div>
        </>
      ) : null}
    </div>
  );
}

function PersonalizedDiscovery({
  regions,
  discoveryState,
  selectedRegions,
  roleTargets,
  industries,
  prestigePreference,
  brandPreference,
  limit,
  onToggleRegion,
  onToggleRole,
  onToggleIndustry,
  onPrestigePreference,
  onBrandPreference,
  onLimit,
  onSubmit,
}: {
  regions: RegionListItem[];
  discoveryState: LoadState<PersonalizedResult>;
  selectedRegions: string[];
  roleTargets: string[];
  industries: string[];
  prestigePreference: string;
  brandPreference: string;
  limit: number;
  onToggleRegion: (regionId: string) => void;
  onToggleRole: (role: string) => void;
  onToggleIndustry: (industry: string) => void;
  onPrestigePreference: (level: string) => void;
  onBrandPreference: (level: string) => void;
  onLimit: (limit: number) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  const discovery = discoveryState.envelope?.data;

  return (
    <div className="view-grid">
      <ShellCard
        title="Personalized discovery"
        eyebrow="POST /discover/personalized"
        action={<StateBadge envelope={discoveryState.envelope} loading={discoveryState.loading} error={discoveryState.error} />}
      >
        <form className="discovery-form" onSubmit={onSubmit}>
          <fieldset>
            <legend>Regions</legend>
            {regions.map((region) => (
              <label className="checkbox-label" key={region.region_id}>
                <input
                  checked={selectedRegions.includes(region.region_id)}
                  onChange={() => onToggleRegion(region.region_id)}
                  type="checkbox"
                />
                <span>{region.display_name}</span>
              </label>
            ))}
          </fieldset>

          <fieldset>
            <legend>Role targets</legend>
            {ROLE_TARGETS.map((role) => (
              <label className="checkbox-label" key={role}>
                <input
                  checked={roleTargets.includes(role)}
                  onChange={() => onToggleRole(role)}
                  type="checkbox"
                />
                <span>{prettyKey(role)}</span>
              </label>
            ))}
          </fieldset>

          <fieldset>
            <legend>Industries</legend>
            {INDUSTRY_OPTIONS.map((industry) => (
              <label className="checkbox-label" key={industry}>
                <input
                  checked={industries.includes(industry)}
                  onChange={() => onToggleIndustry(industry)}
                  type="checkbox"
                />
                <span>{prettyKey(industry)}</span>
              </label>
            ))}
          </fieldset>

          <div className="form-row">
            <label>
              Career stage
              <input readOnly value="entry_level" />
            </label>
            <label>
              Limit
              <input
                max={25}
                min={1}
                onChange={(event) => onLimit(Number(event.target.value))}
                type="number"
                value={limit}
              />
            </label>
          </div>

          <div className="form-row">
            <label>
              Prestige preference
              <select value={prestigePreference} onChange={(event) => onPrestigePreference(event.target.value)}>
                {PREFERENCE_LEVELS.map((level) => (
                  <option key={level} value={level}>
                    {level}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Brand preference
              <select value={brandPreference} onChange={(event) => onBrandPreference(event.target.value)}>
                {PREFERENCE_LEVELS.map((level) => (
                  <option key={level} value={level}>
                    {level}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <button type="submit" disabled={!selectedRegions.length || discoveryState.loading}>
            {discoveryState.loading ? "Running..." : "Run discovery"}
          </button>
        </form>
        {discoveryState.error ? <ErrorState message={discoveryState.error} /> : null}
      </ShellCard>

      {discovery ? (
        <div className="split-grid">
          <ShellCard title="Ranked regions" eyebrow="Personal market score">
            {discovery.ranked_regions.length ? (
              <div className="rank-list">
                {discovery.ranked_regions.map((region, index) => (
                  <div className="rank-row" key={region.region_id}>
                    <span className="rank-number">{index + 1}</span>
                    <div>
                      <strong>{region.display_name}</strong>
                      <small>
                        Objective score: {formatValue(region.objective_opportunity_score)}
                      </small>
                    </div>
                    <ScoreCard compact label="Personalized" value={region.personal_market_score} />
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No ranked regions" body="The personalization response was empty." />
            )}
          </ShellCard>

          <ShellCard title="Ranked companies" eyebrow="Company-region matches">
            {discovery.ranked_companies.length ? (
              <div className="rank-list">
                {discovery.ranked_companies.map((company, index) => (
                  <div className="rank-row rank-row-company" key={`${company.company_id}-${company.region_id}`}>
                    <span className="rank-number">{index + 1}</span>
                    <div>
                      <strong>{company.company_name}</strong>
                      <small>{company.region_display_name}</small>
                    </div>
                    <div className="fit-grid">
                      <ScoreCard compact label="Personal" value={company.personal_company_score} />
                      <ScoreCard compact label="Role" value={company.role_fit} />
                      <ScoreCard compact label="Industry" value={company.industry_fit} />
                      <ScoreCard compact label="Prestige" value={company.prestige_fit} />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No ranked companies" body="The personalization response was empty." />
            )}
          </ShellCard>
        </div>
      ) : (
        <EmptyState
          title="No discovery run yet"
          body="Choose preferences and run the personalization overlay."
        />
      )}
    </div>
  );
}

function App() {
  const [activeView, setActiveView] = useState<ViewId>("overview");
  const [health, setHealth] = useState<LoadState<{ service: string }>>(emptyLoadState);
  const [regions, setRegions] = useState<LoadState<{ regions: RegionListItem[] }>>(emptyLoadState);
  const [regionDetails, setRegionDetails] = useState<Record<string, ApiEnvelope<RegionDetail>>>({});
  const [regionErrors, setRegionErrors] = useState<Record<string, string>>({});
  const [regionLoading, setRegionLoading] = useState<Record<string, boolean>>({});
  const [selectedRegionId, setSelectedRegionId] = useState(DEFAULT_REGION_A);
  const [selectedCompanyId, setSelectedCompanyId] = useState("");
  const [companyState, setCompanyState] = useState<LoadState<CompanyDetail>>(emptyLoadState);
  const [comparisonA, setComparisonA] = useState(DEFAULT_REGION_A);
  const [comparisonB, setComparisonB] = useState(DEFAULT_REGION_B);
  const [comparisonState, setComparisonState] = useState<LoadState<ComparisonDetail>>(emptyLoadState);
  const [discoveryState, setDiscoveryState] = useState<LoadState<PersonalizedResult>>(emptyLoadState);
  const [selectedDiscoveryRegions, setSelectedDiscoveryRegions] = useState<string[]>([
    DEFAULT_REGION_A,
    DEFAULT_REGION_B,
  ]);
  const [roleTargets, setRoleTargets] = useState<string[]>(ROLE_TARGETS);
  const [industries, setIndustries] = useState<string[]>(["software", "ai", "cloud"]);
  const [prestigePreference, setPrestigePreference] = useState("medium");
  const [brandPreference, setBrandPreference] = useState("medium");
  const [limit, setLimit] = useState(10);

  const regionList = regions.envelope?.data?.regions ?? [];
  const companyOptions = getCompanyOptions(regionDetails);
  const selectedRegionState: LoadState<RegionDetail> = {
    loading: Boolean(regionLoading[selectedRegionId]),
    envelope: regionDetails[selectedRegionId] ?? null,
    error: regionErrors[selectedRegionId] ?? null,
  };

  async function loadRegion(regionId: string) {
    if (!regionId) return;
    setRegionLoading((current) => ({ ...current, [regionId]: true }));
    setRegionErrors((current) => ({ ...current, [regionId]: "" }));
    try {
      const envelope = await getRegion(regionId);
      setRegionDetails((current) => ({ ...current, [regionId]: envelope }));
    } catch (error) {
      setRegionErrors((current) => ({
        ...current,
        [regionId]: error instanceof Error ? error.message : "Failed to load region",
      }));
    } finally {
      setRegionLoading((current) => ({ ...current, [regionId]: false }));
    }
  }

  useEffect(() => {
    async function loadInitialData() {
      setHealth((current) => ({ ...current, loading: true, error: null }));
      setRegions((current) => ({ ...current, loading: true, error: null }));

      const [healthResult, regionsResult] = await Promise.allSettled([getHealth(), getRegions()]);

      if (healthResult.status === "fulfilled") {
        setHealth({ loading: false, envelope: healthResult.value, error: null });
      } else {
        setHealth({
          loading: false,
          envelope: null,
          error: healthResult.reason instanceof Error ? healthResult.reason.message : "Failed to load health",
        });
      }

      if (regionsResult.status === "fulfilled") {
        setRegions({ loading: false, envelope: regionsResult.value, error: null });
        const regionIds = regionsResult.value.data?.regions.map((region) => region.region_id) ?? [];
        const defaults = [DEFAULT_REGION_A, DEFAULT_REGION_B].filter((regionId) =>
          regionIds.includes(regionId),
        );
        await Promise.all(defaults.map((regionId) => loadRegion(regionId)));
      } else {
        setRegions({
          loading: false,
          envelope: null,
          error: regionsResult.reason instanceof Error ? regionsResult.reason.message : "Failed to load regions",
        });
      }
    }

    void loadInitialData();
  }, []);

  useEffect(() => {
    if (!selectedRegionId || regionDetails[selectedRegionId] || regionLoading[selectedRegionId]) {
      return;
    }
    void loadRegion(selectedRegionId);
  }, [selectedRegionId, regionDetails, regionLoading]);

  useEffect(() => {
    if (selectedCompanyId || !companyOptions.length) return;
    setSelectedCompanyId(companyOptions[0].company_id);
  }, [companyOptions, selectedCompanyId]);

  useEffect(() => {
    async function loadCompany() {
      if (!selectedCompanyId) return;
      setCompanyState((current) => ({ loading: true, envelope: current.envelope, error: null }));
      try {
        const envelope = await getCompany(selectedCompanyId);
        setCompanyState({ loading: false, envelope, error: null });
      } catch (error) {
        setCompanyState({
          loading: false,
          envelope: null,
          error: error instanceof Error ? error.message : "Failed to load company",
        });
      }
    }

    void loadCompany();
  }, [selectedCompanyId]);

  useEffect(() => {
    async function loadComparison() {
      if (!comparisonA || !comparisonB || comparisonA === comparisonB) return;
      setComparisonState((current) => ({ loading: true, envelope: current.envelope, error: null }));
      try {
        const envelope = await getComparison(comparisonA, comparisonB);
        setComparisonState({ loading: false, envelope, error: null });
      } catch (error) {
        setComparisonState({
          loading: false,
          envelope: null,
          error: error instanceof Error ? error.message : "Failed to load comparison",
        });
      }
    }

    void loadComparison();
  }, [comparisonA, comparisonB]);

  function selectRegion(regionId: string) {
    setSelectedRegionId(regionId);
  }

  function selectCompany(companyId: string) {
    setSelectedCompanyId(companyId);
    setActiveView("companies");
  }

  function toggleValue(value: string, values: string[], setter: (next: string[]) => void) {
    setter(values.includes(value) ? values.filter((item) => item !== value) : [...values, value]);
  }

  async function handleDiscoverySubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setDiscoveryState((current) => ({ ...current, loading: true, error: null }));
    try {
      const envelope = await discoverPersonalized({
        region_ids: selectedDiscoveryRegions,
        role_targets: roleTargets,
        industry_preferences: industries,
        career_stage: "entry_level",
        prestige_preference: prestigePreference,
        brand_preference: brandPreference,
        limit,
      });
      setDiscoveryState({ loading: false, envelope, error: null });
    } catch (error) {
      setDiscoveryState({
        loading: false,
        envelope: null,
        error: error instanceof Error ? error.message : "Failed to run personalized discovery",
      });
    }
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <span className="brand-mark">JM</span>
          <div>
            <strong>Job Market Intelligence</strong>
            <small>MVP demo</small>
          </div>
        </div>
        <nav className="nav-list" aria-label="Main navigation">
          {VIEW_ITEMS.map((item) => (
            <button
              className={activeView === item.id ? "nav-item nav-item-active" : "nav-item"}
              key={item.id}
              onClick={() => setActiveView(item.id)}
              type="button"
            >
              <span>{item.label}</span>
              <small>{item.kicker}</small>
            </button>
          ))}
        </nav>
        <div className="api-target">
          <span>API target</span>
          <code>{API_TARGET_LABEL}</code>
        </div>
      </aside>

      <section className="content-shell">
        <header className="topbar">
          <div>
            <p className="eyebrow">Prepared market truth · derived outputs · personal overlays</p>
            <h1>Job Market Intelligence</h1>
          </div>
          <div className="topbar-badges">
            <StateBadge envelope={health.envelope} loading={health.loading} error={health.error} />
            <span className="badge">{regionList.length} regions</span>
            <span className="badge">{companyOptions.length} companies</span>
          </div>
        </header>

        {activeView === "overview" ? (
          <Overview
            health={health}
            onNavigate={setActiveView}
            onSelectRegion={selectRegion}
            regionDetails={regionDetails}
            regions={regions}
          />
        ) : null}

        {activeView === "regions" ? (
          <RegionExplorer
            onSelectCompany={selectCompany}
            onSelectRegion={selectRegion}
            regionState={selectedRegionState}
            regions={regionList}
            selectedRegionId={selectedRegionId}
          />
        ) : null}

        {activeView === "companies" ? (
          <CompanyExplorer
            companyOptions={companyOptions}
            companyState={companyState}
            onSelectCompany={(companyId) => setSelectedCompanyId(companyId)}
            selectedCompanyId={selectedCompanyId}
          />
        ) : null}

        {activeView === "comparison" ? (
          <ComparisonView
            comparisonState={comparisonState}
            onRegionA={setComparisonA}
            onRegionB={setComparisonB}
            regionA={comparisonA}
            regionB={comparisonB}
            regions={regionList}
          />
        ) : null}

        {activeView === "discovery" ? (
          <PersonalizedDiscovery
            brandPreference={brandPreference}
            discoveryState={discoveryState}
            industries={industries}
            limit={limit}
            onBrandPreference={setBrandPreference}
            onLimit={(nextLimit) => setLimit(Math.max(1, Math.min(25, nextLimit || 1)))}
            onPrestigePreference={setPrestigePreference}
            onSubmit={handleDiscoverySubmit}
            onToggleIndustry={(industry) => toggleValue(industry, industries, setIndustries)}
            onToggleRegion={(regionId) =>
              toggleValue(regionId, selectedDiscoveryRegions, setSelectedDiscoveryRegions)
            }
            onToggleRole={(role) => toggleValue(role, roleTargets, setRoleTargets)}
            prestigePreference={prestigePreference}
            regions={regionList}
            roleTargets={roleTargets}
            selectedRegions={selectedDiscoveryRegions}
          />
        ) : null}
      </section>
    </main>
  );
}

export default App;
