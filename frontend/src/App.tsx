import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type MouseEvent, type ReactNode } from "react";
import {
  API_TARGET_LABEL,
  discoverPersonalized,
  getCompany,
  getCompanyGeography,
  getCompanySources,
  getComparison,
  getHealth,
  getRegion,
  getRegionSources,
  getRegions,
  searchCompanies,
  searchRegions,
} from "./api";
import {
  dataBasisLabel,
  envelopeFreshnessStatus,
  freshnessLabel,
  isSeedDemoFreshness,
  qualityBadges,
  qualityNotices,
} from "./dataQuality";
import type {
  ApiEnvelope,
  CompanyGeographyResponse,
  CompanyDetail,
  CompanySearchResponse,
  ComparisonDetail,
  FreshnessSourceSummary,
  FreshnessStatus,
  PersonalizedResult,
  RegionDetail,
  RegionListItem,
  RegionSearchResult,
  RegionSearchResponse,
  RegionScores,
  SourceExplanation,
  WarningItem,
} from "./types";
import {
  DEFAULT_REGION_A,
  DEFAULT_REGION_B,
  CAREER_STAGE_OPTIONS,
  INDUSTRY_OPTIONS,
  PREFERENCE_LEVELS,
  ROLE_TARGETS,
  companyGeographyUrl,
  compareMarketsUrl,
  exploreUrl,
  parseRoute,
  personalizedDiscoveryUrl,
  regionDetailUrl,
  type DiscoveryFilters,
  type ProductPage,
  type RouteState,
} from "./urlState";

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
type OpportunityFilter = "any" | "0.70" | "0.50" | "missing";
type CareerStageFilter = "any" | "entry_level_reported" | "entry_level_unknown";
type FreshnessFilter = "any" | FreshnessStatus;

const NAV_ITEMS: Array<{ id: ProductPage; label: string; kicker: string }> = [
  { id: "explore", label: "Explore Markets", kicker: "Market map" },
  { id: "region", label: "Region Detail", kicker: "Regional output" },
  { id: "company", label: "Company Geography", kicker: "Presence and hiring" },
  { id: "compare", label: "Compare Markets", kicker: "Score comparison" },
  { id: "discovery", label: "Personalized Discovery", kicker: "Personal overlay" },
];

function emptyLoadState<T>(): LoadState<T> {
  return { loading: false, envelope: null, error: null };
}

function readCurrentRoute(): RouteState {
  return parseRoute(window.location.pathname, window.location.search);
}

function currentUrl(): string {
  return `${window.location.pathname}${window.location.search}`;
}

function isPlainLeftClick(event: MouseEvent<HTMLAnchorElement>): boolean {
  return event.button === 0 && !event.metaKey && !event.altKey && !event.ctrlKey && !event.shiftKey;
}

function getDefaultRegionId(regions: RegionListItem[]): string {
  if (regions.some((region) => region.region_id === DEFAULT_REGION_A)) return DEFAULT_REGION_A;
  return regions[0]?.region_id ?? DEFAULT_REGION_A;
}

function getFallbackComparisonRegion(regions: RegionListItem[], regionA: string): string {
  if (regionA !== DEFAULT_REGION_B && regions.some((region) => region.region_id === DEFAULT_REGION_B)) {
    return DEFAULT_REGION_B;
  }

  return regions.find((region) => region.region_id !== regionA)?.region_id ?? DEFAULT_REGION_B;
}

function isKnownRegion(regionId: string, regions: RegionListItem[], loaded: boolean): boolean {
  return !loaded || regions.some((region) => region.region_id === regionId);
}

function getNavigationUrl(
  page: ProductPage,
  selectedRegionId: string,
  selectedCompanyId: string,
  comparisonA: string,
  comparisonB: string,
  discoveryFilters: DiscoveryFilters,
): string {
  if (page === "region") return regionDetailUrl(selectedRegionId);
  if (page === "company") return companyGeographyUrl(selectedCompanyId);
  if (page === "compare") return compareMarketsUrl(comparisonA, comparisonB);
  if (page === "discovery") return personalizedDiscoveryUrl(discoveryFilters);
  return exploreUrl();
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
  if (status === "partial") return `Partial freshness · Expires: ${expires}`;
  if (status === "seeded_demo" || isSeedDemoFreshness(freshness.freshness_expires_at)) {
    return `Seeded demo freshness · Expires: ${expires}`;
  }
  if (status === "stale") return `Stale · Expires: ${expires}`;
  return `Fresh · Expires: ${expires}`;
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

    [...(region.top_companies_present ?? []), ...(region.top_companies_hiring ?? [])].forEach((company) => {
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

function qualityBadgeClass(tone: string): string {
  return `badge badge-${tone}`;
}

function QualityBadgeRow({
  envelope,
  source,
}: {
  envelope?: ApiEnvelope<unknown> | null;
  source?: SourceExplanation | FreshnessSourceSummary | null;
}) {
  return (
    <div className="metadata-row">
      {qualityBadges(envelope, source).map((badge) => (
        <span className={qualityBadgeClass(badge.tone)} key={`${badge.label}-${badge.tone}`}>
          {badge.label}
        </span>
      ))}
    </div>
  );
}

function getSourceSummary(
  source?: SourceExplanation | FreshnessSourceSummary | null,
): FreshnessSourceSummary | null {
  if (!source) return null;
  return "freshness" in source ? source.freshness : source;
}

function getRegionSearchMap(search?: ApiEnvelope<RegionSearchResponse> | null): Map<string, RegionSearchResult> {
  return new Map((search?.data?.regions ?? []).map((region) => [region.region_id, region]));
}

function regionOpportunityScore(
  regionId: string,
  searchMap: Map<string, RegionSearchResult>,
  regionDetails: Record<string, ApiEnvelope<RegionDetail>>,
): number | null {
  return searchMap.get(regionId)?.opportunity_score
    ?? regionDetails[regionId]?.data?.scores?.objective_opportunity_score
    ?? null;
}

function entryLevelSignalState(region?: RegionDetail | null): "reported" | "unknown" {
  const summary = region?.entry_level_summary;
  if (!summary) return "unknown";
  const values = Object.values(summary);
  return values.some((value) => typeof value === "number" && value > 0) ? "reported" : "unknown";
}

function hasEntryLevelAccess(row: NonNullable<CompanyDetail["entry_level_regions"]>[number]): boolean {
  return Boolean(
    (row.entry_level_access_score !== null && row.entry_level_access_score !== undefined && row.entry_level_access_score > 0)
      || (row.internship_count !== null && row.internship_count !== undefined && row.internship_count > 0)
      || (row.coop_count !== null && row.coop_count !== undefined && row.coop_count > 0)
      || (row.entry_level_full_time_count !== null && row.entry_level_full_time_count !== undefined && row.entry_level_full_time_count > 0)
      || row.formal_early_career_program_flag,
  );
}

function roleFamilyCounts(response?: CompanySearchResponse | null): Array<{ role: string; count: number }> {
  const counts = new Map<string, number>();
  for (const company of response?.companies ?? []) {
    for (const role of company.role_families ?? []) {
      counts.set(role, (counts.get(role) ?? 0) + 1);
    }
  }
  return Array.from(counts.entries())
    .map(([role, count]) => ({ role, count }))
    .sort((left, right) => right.count - left.count || left.role.localeCompare(right.role));
}

function comparisonSideLabel(
  side: ComparisonDetail["region_a"] | undefined,
  fallbackRegionId: string,
  regions: RegionListItem[],
): string {
  return side?.display_name
    ?? regions.find((region) => region.region_id === fallbackRegionId)?.display_name
    ?? fallbackRegionId
    ?? "Unknown region";
}

function objectiveComparison(
  comparison: ComparisonDetail | null | undefined,
): {
  winnerId: string | null;
  winnerLabel: string;
  message: string;
  delta: number | null;
} {
  const aValue = comparison?.region_a?.scores?.objective_opportunity_score;
  const bValue = comparison?.region_b?.scores?.objective_opportunity_score;
  const aName = comparison?.region_a?.display_name ?? "Region A";
  const bName = comparison?.region_b?.display_name ?? "Region B";

  if (typeof aValue !== "number" || typeof bValue !== "number") {
    return {
      winnerId: null,
      winnerLabel: "No objective winner",
      message: "Objective opportunity cannot be compared because one or both regions are missing that score.",
      delta: null,
    };
  }

  if (aValue === bValue) {
    return {
      winnerId: null,
      winnerLabel: "Tie on objective opportunity",
      message: "Both regions have the same objective opportunity score in the returned comparison.",
      delta: 0,
    };
  }

  const winnerIsA = aValue > bValue;
  const delta = Math.abs(aValue - bValue);
  return {
    winnerId: winnerIsA ? comparison?.region_a?.region_id ?? null : comparison?.region_b?.region_id ?? null,
    winnerLabel: winnerIsA ? aName : bName,
    message: `${winnerIsA ? aName : bName} has the higher objective opportunity score by ${(delta * 100).toFixed(0)} percentage point(s).`,
    delta,
  };
}

function comparisonDataLimitations(
  comparison: ComparisonDetail | null | undefined,
  envelope?: ApiEnvelope<unknown> | null,
  sourceA?: SourceExplanation | null,
  sourceB?: SourceExplanation | null,
): string[] {
  const notices = new Set<string>();
  const missingCategories = SCORE_FIELDS.filter((score) => {
    const aValue = comparison?.region_a?.scores?.[score.key];
    const bValue = comparison?.region_b?.scores?.[score.key];
    return typeof aValue !== "number" || typeof bValue !== "number";
  }).map((score) => score.label);

  if (!comparison?.region_a || !comparison.region_b) {
    notices.add("The comparison response is missing one or both region sides.");
  }
  if (missingCategories.length) {
    notices.add(`Missing comparable score data for: ${missingCategories.join(", ")}.`);
  }
  for (const notice of qualityNotices(envelope)) notices.add(notice);
  for (const notice of qualityNotices(undefined, sourceA)) notices.add(`Region A: ${notice}`);
  for (const notice of qualityNotices(undefined, sourceB)) notices.add(`Region B: ${notice}`);
  return Array.from(notices);
}

function recommendationNotes(notes: string[] | undefined): string[] {
  return notes?.length ? notes : ["The API did not return detailed match notes for this recommendation."];
}

function preferenceInfluencesForCompany(
  company: NonNullable<PersonalizedResult["ranked_companies"]>[number],
): Array<{ label: string; value: number }> {
  return [
    { label: "Role preference", value: company.role_fit },
    { label: "Industry preference", value: company.industry_fit },
    { label: "Prestige preference", value: company.prestige_fit },
    { label: "Brand preference", value: company.brand_fit },
  ].filter((item) => typeof item.value === "number");
}

function sourceForRegion(
  regionId: string,
  sourceStates: Record<string, LoadState<SourceExplanation>>,
): SourceExplanation | null {
  return sourceStates[regionId]?.envelope?.data ?? null;
}

function strongestCompanyRegions(
  company: CompanyDetail,
  geography?: CompanyGeographyResponse | null,
): Array<{
  regionId: string;
  regionName: string;
  signalCount: number;
  signals: string[];
  entryScore: number | null;
  activePostings: number | null;
  freshness?: FreshnessSourceSummary;
}> {
  const regions = new Map<string, {
    regionId: string;
    regionName: string;
    signals: Set<string>;
    entryScore: number | null;
    activePostings: number | null;
    freshness?: FreshnessSourceSummary;
  }>();

  function ensure(regionId: string, regionName: string) {
    const current = regions.get(regionId);
    if (current) return current;
    const next: {
      regionId: string;
      regionName: string;
      signals: Set<string>;
      entryScore: number | null;
      activePostings: number | null;
      freshness?: FreshnessSourceSummary;
    } = {
      regionId,
      regionName,
      signals: new Set<string>(),
      entryScore: null,
      activePostings: null,
    };
    regions.set(regionId, next);
    return next;
  }

  for (const row of company.regions_present ?? []) {
    if (row.presence_status === "present") {
      ensure(row.region_id, row.region_display_name).signals.add("Presence");
    }
  }

  for (const row of company.regions_hiring ?? []) {
    const item = ensure(row.region_id, row.region_display_name);
    item.activePostings = row.active_posting_count_now;
    if (row.currently_hiring_flag || (row.active_posting_count_now ?? 0) > 0) {
      item.signals.add("Hiring activity");
    }
  }

  for (const row of company.entry_level_regions ?? []) {
    const item = ensure(row.region_id, row.region_display_name);
    item.entryScore = row.entry_level_access_score;
    if (hasEntryLevelAccess(row)) {
      item.signals.add("Entry-level access");
    }
  }

  for (const row of geography?.regions ?? []) {
    const item = ensure(row.region_id, row.region_name);
    item.freshness = row.freshness;
    if (row.presence_status === "present") item.signals.add("Presence");
    if (row.current_hiring) item.signals.add("Hiring activity");
    if (row.has_entry_level_access) item.signals.add("Entry-level access");
  }

  return Array.from(regions.values())
    .map((item) => ({
      regionId: item.regionId,
      regionName: item.regionName,
      signalCount: item.signals.size,
      signals: Array.from(item.signals).sort(),
      entryScore: item.entryScore,
      activePostings: item.activePostings,
      freshness: item.freshness,
    }))
    .filter((item) => item.signalCount > 0)
    .sort((left, right) =>
      right.signalCount - left.signalCount
      || (right.entryScore ?? -1) - (left.entryScore ?? -1)
      || (right.activePostings ?? -1) - (left.activePostings ?? -1)
      || left.regionName.localeCompare(right.regionName),
    );
}

function confidenceTone(value: string | null | undefined): "fresh" | "warning" | "unknown" {
  if (!value) return "unknown";
  if (value.includes("high")) return "fresh";
  if (value.includes("low") || value.includes("unknown")) return "warning";
  return "unknown";
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

function MetadataPanel({
  envelope,
  source,
}: {
  envelope?: ApiEnvelope<unknown> | null;
  source?: SourceExplanation | FreshnessSourceSummary | null;
}) {
  const freshness = envelope?.metadata.freshness;
  const warnings = pickEnvelopeWarnings(envelope);
  const sourceSummary = getSourceSummary(source);
  const sourceDetails = source && "sources" in source ? source.sources ?? [] : [];
  const notices = qualityNotices(envelope, source);

  return (
    <div className="metadata-panel">
      <QualityBadgeRow envelope={envelope} source={source} />
      <div className="metadata-row metadata-row-secondary">
        <StateBadge envelope={envelope} />
        {warnings.length ? <span className="badge badge-warning">{warnings.length} warning(s)</span> : null}
        {sourceSummary ? <span className="badge badge-unknown">{sourceSummary.source_count} source(s)</span> : null}
      </div>
      {freshness ? (
        <div className="freshness-copy">
          <p>{freshnessText(freshness)}</p>
          <small>Updated: {formatDateTime(freshness.last_updated_at)}</small>
        </div>
      ) : null}
      {sourceSummary ? (
        <div className="freshness-copy">
          <p>
            {dataBasisLabel(sourceSummary.data_basis)} · {freshnessLabel(sourceSummary.freshness_status)}
          </p>
          <small>
            Last source collection: {formatDateTime(sourceSummary.last_collected_at)}
          </small>
        </div>
      ) : null}
      {sourceDetails.length ? (
        <details className="source-details">
          <summary>Source evidence</summary>
          <div className="source-list">
            {sourceDetails.map((item) => (
              <div className="source-row" key={item.source_id}>
                <strong>{item.source_name}</strong>
                <span>
                  {prettyKey(item.source_type)} · {dataBasisLabel(item.data_basis)} ·{" "}
                  {freshnessLabel(item.freshness_status)}
                </span>
                <small>{item.url ?? "No source URL/provider returned"}</small>
              </div>
            ))}
          </div>
        </details>
      ) : null}
      {notices.length || warnings.length ? (
        <div className="warning-list">
          {notices.map((notice) => (
            <div className="warning-item" key={notice}>
              <div className="warning-header">
                <span className="warning-code">Data quality note</span>
              </div>
              <p>{notice}</p>
            </div>
          ))}
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
        <p className="meta-copy">No metadata warnings or source caveats were returned.</p>
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
  companies: NonNullable<RegionDetail["top_companies_present"]> | NonNullable<RegionDetail["top_companies_hiring"]>;
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

function ExploreMarkets({
  health,
  regions,
  regionSearch,
  regionDetails,
  onOpenCompare,
  onOpenRegionDetail,
  onSelectRegion,
}: {
  health: LoadState<{ service: string }>;
  regions: LoadState<{ regions: RegionListItem[] }>;
  regionSearch: LoadState<RegionSearchResponse>;
  regionDetails: Record<string, ApiEnvelope<RegionDetail>>;
  onOpenCompare: () => void;
  onOpenRegionDetail: () => void;
  onSelectRegion: (regionId: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [opportunityFilter, setOpportunityFilter] = useState<OpportunityFilter>("any");
  const [careerFilter, setCareerFilter] = useState<CareerStageFilter>("any");
  const [freshnessFilter, setFreshnessFilter] = useState<FreshnessFilter>("any");
  const regionList = useMemo(() => regions.envelope?.data?.regions ?? [], [regions.envelope]);
  const searchMap = getRegionSearchMap(regionSearch.envelope);
  const normalizedQuery = query.toLocaleLowerCase().trim();
  const filteredRegions = regionList.filter((region) => {
    const searchItem = searchMap.get(region.region_id);
    const detail = regionDetails[region.region_id]?.data;
    const searchableValues = [
      region.display_name,
      region.region_id,
      region.region_type,
      region.labor_market_group,
      searchItem?.name,
      searchItem?.region_name,
    ];
    const matchesQuery =
      !normalizedQuery
      || searchableValues.some((value) => value?.toLocaleLowerCase().includes(normalizedQuery));
    if (!matchesQuery) return false;

    const opportunityScore = regionOpportunityScore(region.region_id, searchMap, regionDetails);
    if (opportunityFilter === "missing" && typeof opportunityScore === "number") return false;
    if (opportunityFilter !== "any" && opportunityFilter !== "missing") {
      if (typeof opportunityScore !== "number" || opportunityScore < Number(opportunityFilter)) return false;
    }

    const careerState = entryLevelSignalState(detail);
    if (careerFilter === "entry_level_reported" && careerState !== "reported") return false;
    if (careerFilter === "entry_level_unknown" && careerState !== "unknown") return false;

    const freshnessStatus = searchItem?.freshness.freshness_status
      ?? envelopeFreshnessStatus(regionDetails[region.region_id]);
    if (freshnessFilter !== "any" && freshnessStatus !== freshnessFilter) return false;

    return true;
  });
  const detailCount = regionList.filter((region) => regionDetails[region.region_id]?.data).length;
  const realImportedCount = regionList.filter(
    (region) => searchMap.get(region.region_id)?.freshness.data_basis === "real_imported",
  ).length;
  const seededCount = regionList.filter(
    (region) => searchMap.get(region.region_id)?.freshness.data_basis === "seeded_demo"
      || envelopeFreshnessStatus(regionDetails[region.region_id]) === "seeded_demo",
  ).length;

  return (
    <div className="view-grid">
      <ShellCard
        title="Explore markets"
        eyebrow="Explore markets"
        action={<StateBadge envelope={health.envelope} loading={health.loading} error={health.error} />}
      >
        <p className="lead-copy">
          Compare prepared regional market outputs for early-career tech decisions. Scores
          are derived signals, source labels show whether evidence is seeded demo, real
          imported, mixed, partial, stale, or unknown.
        </p>
        <div className="hero-actions">
          <button type="button" onClick={onOpenRegionDetail}>
            Open region detail
          </button>
          <button className="secondary-button" type="button" onClick={onOpenCompare}>
            Compare markets
          </button>
        </div>
      </ShellCard>

      <ShellCard title="Market filters" eyebrow="Search and narrow">
        <div className="market-filter-grid">
          <label>
            Region search
            <input
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search name, id, labor market"
              type="search"
              value={query}
            />
          </label>
          <label>
            Opportunity score
            <select
              onChange={(event) => setOpportunityFilter(event.target.value as OpportunityFilter)}
              value={opportunityFilter}
            >
              <option value="any">Any score</option>
              <option value="0.70">At least 70%</option>
              <option value="0.50">At least 50%</option>
              <option value="missing">Missing score</option>
            </select>
          </label>
          <label>
            Career stage
            <select
              onChange={(event) => setCareerFilter(event.target.value as CareerStageFilter)}
              value={careerFilter}
            >
              <option value="any">Any available stage signal</option>
              <option value="entry_level_reported">Entry-level access reported</option>
              <option value="entry_level_unknown">Entry-level unknown or missing</option>
            </select>
          </label>
          <label>
            Data freshness
            <select
              onChange={(event) => setFreshnessFilter(event.target.value as FreshnessFilter)}
              value={freshnessFilter}
            >
              <option value="any">Any freshness state</option>
              <option value="fresh">Fresh real/imported evidence</option>
              <option value="seeded_demo">Seeded demo</option>
              <option value="partial">Partial</option>
              <option value="stale">Stale</option>
              <option value="unknown">Unknown freshness</option>
            </select>
          </label>
        </div>
        <div className="market-summary-strip">
          <div>
            <strong>{filteredRegions.length}</strong>
            <span>matching region(s)</span>
          </div>
          <div>
            <strong>{detailCount}/{regionList.length}</strong>
            <span>detail outputs loaded</span>
          </div>
          <div>
            <strong>{realImportedCount}</strong>
            <span>real imported evidence</span>
          </div>
          <div>
            <strong>{seededCount}</strong>
            <span>seed/demo evidence</span>
          </div>
        </div>
        {regionSearch.error ? (
          <ErrorState message={`Region source search unavailable: ${regionSearch.error}`} />
        ) : null}
        <p className="meta-copy">
          Unknown freshness is intentionally kept separate from fresh. Missing scores and
          missing entry-level values are not converted into zeroes.
        </p>
      </ShellCard>

      <ShellCard title="Markets" eyebrow="Filtered region outputs">
        {regions.loading ? <LoadingBlock label="Loading regions" /> : null}
        {regions.error ? <ErrorState message={regions.error} /> : null}
        {regionSearch.loading ? <LoadingBlock label="Loading source and freshness labels" /> : null}
        {!regions.loading && !filteredRegions.length ? (
          <EmptyState
            title="No markets match these filters"
            body="Try clearing search, allowing unknown freshness, or including missing opportunity scores."
          />
        ) : null}
        {filteredRegions.length ? (
          <div className="market-card-grid">
            {filteredRegions.map((region) => {
              const searchItem = searchMap.get(region.region_id);
              const detailEnvelope = regionDetails[region.region_id] ?? null;
              const detail = detailEnvelope?.data;
              const opportunityScore = regionOpportunityScore(region.region_id, searchMap, regionDetails);
              const careerState = entryLevelSignalState(detail);
              return (
                <button
                  className="market-card"
                  key={region.region_id}
                  type="button"
                  onClick={() => onSelectRegion(region.region_id)}
                >
                  <div className="market-card-topline">
                    <span>{prettyKey(region.region_type)}</span>
                    <QualityBadgeRow envelope={detailEnvelope} source={searchItem?.freshness} />
                  </div>
                  <strong>{region.display_name}</strong>
                  <small>
                    {region.region_id} · {region.labor_market_group ?? "unknown labor market"}
                  </small>
                  <div className="market-card-metrics">
                    <ScoreCard compact label="Opportunity" value={opportunityScore} />
                    <div className="stat-card">
                      <span>Career-stage signal</span>
                      <strong>
                        {careerState === "reported" ? "Entry-level reported" : "Entry-level unknown"}
                      </strong>
                    </div>
                    <div className="stat-card">
                      <span>Source count</span>
                      <strong>{searchItem?.freshness.source_count ?? "Unknown"}</strong>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        ) : null}
      </ShellCard>

      <div className="quick-region-grid">
        {filteredRegions.slice(0, 2).map((region) => {
          const detail = regionDetails[region.region_id]?.data;
          return detail ? (
            <button
              className="quick-region-card"
              key={detail.region_id}
              type="button"
              onClick={() => {
                onSelectRegion(detail.region_id);
              }}
            >
              <span>{detail.region_type}</span>
              <strong>{detail.display_name}</strong>
              <div className="quick-score-row">
                <ScoreCard compact label="Total score" value={detail.scores?.raw_total_score} />
                <ScoreCard
                  compact
                  label="Early career"
                  value={detail.scores?.early_career_accessibility_score}
                />
              </div>
            </button>
          ) : (
            <div className="quick-region-card quick-region-placeholder" key={region.region_id}>
              <LoadingBlock label={`Loading ${region.display_name}`} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

function RegionExplorer({
  regions,
  selectedRegionId,
  regionState,
  sourceState,
  roleFamilyState,
  onSelectRegion,
  onSelectCompany,
  onCompareRegion,
}: {
  regions: RegionListItem[];
  selectedRegionId: string;
  regionState: LoadState<RegionDetail>;
  sourceState: LoadState<SourceExplanation>;
  roleFamilyState: LoadState<CompanySearchResponse>;
  onSelectRegion: (regionId: string) => void;
  onSelectCompany: (companyId: string) => void;
  onCompareRegion: (regionId: string) => void;
}) {
  const region = regionState.envelope?.data;
  const hasSelectedRegion = regions.some((item) => item.region_id === selectedRegionId);
  const source = sourceState.envelope?.data;
  const roleCounts = roleFamilyCounts(roleFamilyState.envelope?.data);
  const entrySummary = region?.entry_level_summary ?? {};

  return (
    <div className="view-grid">
      <ShellCard
        title="Region detail"
        eyebrow="Market output"
        action={<QualityBadgeRow envelope={regionState.envelope} source={source} />}
      >
        <div className="toolbar">
          <label>
            Select region
            <select value={selectedRegionId} onChange={(event) => onSelectRegion(event.target.value)}>
              {selectedRegionId && !hasSelectedRegion ? (
                <option value={selectedRegionId}>
                  {regions.length ? `Unknown region: ${selectedRegionId}` : selectedRegionId}
                </option>
              ) : null}
              {regions.map((item) => (
                <option key={item.region_id} value={item.region_id}>
                  {item.display_name}
                </option>
              ))}
            </select>
          </label>
          <button
            className="secondary-button toolbar-button"
            disabled={!region}
            onClick={() => onCompareRegion(selectedRegionId)}
            type="button"
          >
            Compare this market
          </button>
        </div>

        {regionState.loading ? <LoadingBlock label="Loading region output" /> : null}
        {regionState.error ? <ErrorState message={regionState.error} /> : null}
        {sourceState.error ? <ErrorState message={`Source explanation unavailable: ${sourceState.error}`} /> : null}
        {!regionState.loading && !regionState.error && !region ? (
          <EmptyState title="No region selected" body="Choose a region from the dropdown." />
        ) : null}
      </ShellCard>

      {region ? (
        <>
          <ShellCard title={region.display_name} eyebrow="Factual regional output">
            <div className="detail-hero">
              <div>
                <p className="meta-copy">
                  {region.region_id} · {region.labor_market_group ?? "unknown labor market"}
                </p>
                <h3>What this output contains</h3>
                <p className="meta-copy">
                  Counts are returned facts from the prepared output. Missing fields are shown
                  as unknown rather than converted to zero.
                </p>
              </div>
              <MetadataPanel envelope={regionState.envelope} source={source} />
            </div>
            <StatGrid values={region.summary ?? {}} />
          </ShellCard>

          <ShellCard title="Derived market scores" eyebrow="Interpretation">
            <p className="meta-copy">
              These scores are derived from stored scoring fields. They are not a claim of
              complete market coverage or real-time hiring certainty.
            </p>
            <RegionScoreGrid scores={region.scores} />
          </ShellCard>

          <div className="split-grid">
            <ShellCard title="Top companies present" eyebrow="Presence facts">
              <p className="meta-copy">
                Presence means the backend has a company-region presence record. It does not
                imply current hiring.
              </p>
              <CompanyList
                companies={region.top_companies_present ?? []}
                mode="present"
                onSelectCompany={onSelectCompany}
              />
            </ShellCard>

            <ShellCard title="Hiring activity" eyebrow="Hiring snapshot">
              <p className="meta-copy">
                Hiring counts are snapshots from prepared records. Unknown posting counts stay unknown.
              </p>
              <CompanyList
                companies={region.top_companies_hiring ?? []}
                mode="hiring"
                onSelectCompany={onSelectCompany}
              />
            </ShellCard>
          </div>

          <div className="split-grid">
            <ShellCard title="Entry-level access" eyebrow="Early-career facts">
              <p className="meta-copy">
                Internship, co-op, full-time, and formal program signals are separate inputs.
                Unknown totals are not treated as zero.
              </p>
              <StatGrid values={entrySummary} />
            </ShellCard>

            <ShellCard title="Role-family concentration" eyebrow="Derived from company search rows">
              <p className="meta-copy">
                This summarizes role families visible in company search rows for this region.
                Absence here does not prove there are no jobs in a family.
              </p>
              {roleFamilyState.loading ? <LoadingBlock label="Loading role-family signals" /> : null}
              {roleFamilyState.error ? <ErrorState message={roleFamilyState.error} /> : null}
              {roleCounts.length ? (
                <div className="signal-list">
                  {roleCounts.map((item) => (
                    <div className="signal-row" key={item.role}>
                      <span>{prettyKey(item.role)}</span>
                      <strong>{item.count} company signal(s)</strong>
                    </div>
                  ))}
                </div>
              ) : !roleFamilyState.loading ? (
                <EmptyState
                  title="No role-family signals"
                  body="No company search rows returned role-family summaries for this region."
                />
              ) : null}
            </ShellCard>
          </div>

          <ShellCard title="Classification context" eyebrow="Factual tags">
            <StatGrid
              values={{
                major_tech_count: region.major_tech_summary?.count,
                major_tech_companies: region.major_tech_summary?.company_ids,
                mag7_count: region.mag7_summary?.count,
                mag7_companies: region.mag7_summary?.company_ids,
              }}
            />
          </ShellCard>
        </>
      ) : null}
    </div>
  );
}

function CompanyExplorer({
  companyOptions,
  selectedCompanyId,
  companyState,
  geographyState,
  sourceState,
  onSelectCompany,
}: {
  companyOptions: CompanyOption[];
  selectedCompanyId: string;
  companyState: LoadState<CompanyDetail>;
  geographyState: LoadState<CompanyGeographyResponse>;
  sourceState: LoadState<SourceExplanation>;
  onSelectCompany: (companyId: string) => void;
}) {
  const company = companyState.envelope?.data;
  const hasSelectedCompany = companyOptions.some((item) => item.company_id === selectedCompanyId);
  const source = sourceState.envelope?.data;
  const geography = geographyState.envelope?.data;
  const strongestRegions = company ? strongestCompanyRegions(company, geography).slice(0, 5) : [];

  return (
    <div className="view-grid">
      <ShellCard
        title="Company geography"
        eyebrow="Presence, hiring, and entry-level access by region"
        action={<QualityBadgeRow envelope={companyState.envelope} source={source} />}
      >
        <div className="toolbar">
          <label>
            Select company
            <select
              value={selectedCompanyId}
              onChange={(event) => onSelectCompany(event.target.value)}
              disabled={!companyOptions.length}
            >
              {selectedCompanyId && !hasSelectedCompany ? (
                <option value={selectedCompanyId}>{selectedCompanyId} from URL</option>
              ) : null}
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
            body="Company choices are derived from loaded region outputs. Deep links still load by company ID."
          />
        ) : null}
        {companyState.loading ? <LoadingBlock label="Loading company output" /> : null}
        {companyState.error ? <ErrorState message={companyState.error} /> : null}
        {sourceState.error ? <ErrorState message={`Source explanation unavailable: ${sourceState.error}`} /> : null}
        {geographyState.error ? <ErrorState message={`Company geography summary unavailable: ${geographyState.error}`} /> : null}
      </ShellCard>

      {company ? (
        <>
          <ShellCard title={company.company_name} eyebrow="Company facts and source quality">
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
                <span className={qualityBadgeClass(confidenceTone(company.classification_confidence))}>
                  Classification confidence: {formatValue(company.classification_confidence)}
                </span>
              </div>
            </div>
            <MetadataPanel envelope={companyState.envelope} source={source} />
          </ShellCard>

          <ShellCard title="Strongest observed region signals" eyebrow="Derived from visible geography rows">
            <p className="meta-copy">
              This section counts distinct observed signals: presence, hiring activity, and
              entry-level access. It is not a comprehensive ranking of all possible markets.
            </p>
            {geographyState.loading ? <LoadingBlock label="Loading geography source summaries" /> : null}
            {strongestRegions.length ? (
              <div className="market-card-grid">
                {strongestRegions.map((region) => (
                  <div className="market-card market-card-static" key={region.regionId}>
                    <div className="market-card-topline">
                      <span>{region.signalCount} observed signal(s)</span>
                      {region.freshness ? <QualityBadgeRow source={region.freshness} /> : null}
                    </div>
                    <strong>{region.regionName}</strong>
                    <small>{region.regionId}</small>
                    <div className="chip-row">
                      {region.signals.map((signal) => (
                        <span className="badge" key={signal}>{signal}</span>
                      ))}
                    </div>
                    <div className="market-card-metrics">
                      <ScoreCard compact label="Entry access" value={region.entryScore} />
                      <div className="stat-card">
                        <span>Active postings</span>
                        <strong>{formatValue(region.activePostings)}</strong>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : !geographyState.loading ? (
              <EmptyState
                title="No strongest-region signal"
                body="The company output did not include enough presence, hiring, or entry-level rows to identify stronger observed regions."
              />
            ) : null}
          </ShellCard>

          <div className="split-grid">
            <ShellCard title="Where the company is present" eyebrow="Presence only">
              <p className="meta-copy">
                Presence is a company-region relationship. It does not imply active hiring
                or entry-level access in that region.
              </p>
              {(company.regions_present ?? []).length ? (
                <div className="stack-list">
                  {(company.regions_present ?? []).map((region) => (
                    <div className="stack-row" key={region.region_id}>
                      <strong>{region.region_display_name}</strong>
                      <span>
                        {formatValue(region.presence_basis)} · {formatValue(region.presence_confidence)}
                      </span>
                      <span className={qualityBadgeClass(confidenceTone(region.presence_confidence))}>
                        Confidence: {formatValue(region.presence_confidence)}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="No presence rows" body="No region presence was returned." />
              )}
            </ShellCard>

            <ShellCard title="Where the company is hiring" eyebrow="Hiring snapshot">
              <p className="meta-copy">
                Hiring rows are separate from presence rows. A present region can have no
                returned hiring signal.
              </p>
              {(company.regions_hiring ?? []).length ? (
                <div className="stack-list">
                  {(company.regions_hiring ?? []).map((region) => (
                    <div className="stack-row" key={region.region_id}>
                      <strong>{region.region_display_name}</strong>
                      <span>
                        {formatValue(region.active_posting_count_now)} active ·{" "}
                        {formatValue(region.posting_count_90d)} in 90d
                      </span>
                      <span className={region.currently_hiring_flag ? "badge badge-fresh" : "badge badge-unknown"}>
                        Currently hiring: {formatValue(region.currently_hiring_flag)}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="No hiring rows" body="No active hiring rows were returned." />
              )}
            </ShellCard>
          </div>

          <ShellCard title="Where entry-level access exists" eyebrow="Early-career access">
            <p className="meta-copy">
              Entry-level access combines internships, co-ops, full-time entry-level roles,
              and formal program signals when those fields are present.
            </p>
            {(company.entry_level_regions ?? []).length ? (
              <div className="entry-grid">
                {(company.entry_level_regions ?? []).map((region) => (
                  <div className="entry-card" key={region.region_id}>
                    <h3>{region.region_display_name}</h3>
                    <span className={qualityBadgeClass(confidenceTone(region.entry_level_confidence))}>
                      Confidence: {formatValue(region.entry_level_confidence)}
                    </span>
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
  sourceAState,
  sourceBState,
  validationError,
  onRegionA,
  onRegionB,
}: {
  regions: RegionListItem[];
  regionA: string;
  regionB: string;
  comparisonState: LoadState<ComparisonDetail>;
  sourceAState: LoadState<SourceExplanation>;
  sourceBState: LoadState<SourceExplanation>;
  validationError?: string | null;
  onRegionA: (regionId: string) => void;
  onRegionB: (regionId: string) => void;
}) {
  const comparison = validationError ? null : comparisonState.envelope?.data;
  const hasRegionA = regions.some((region) => region.region_id === regionA);
  const hasRegionB = regions.some((region) => region.region_id === regionB);
  const regionALabel = comparisonSideLabel(comparison?.region_a, regionA, regions);
  const regionBLabel = comparisonSideLabel(comparison?.region_b, regionB, regions);
  const categoryWinners = comparison?.category_winners ?? {};
  const notes = comparison?.notes ?? [];
  const objective = objectiveComparison(comparison);
  const sourceA = sourceAState.envelope?.data ?? null;
  const sourceB = sourceBState.envelope?.data ?? null;
  const limitations = comparisonDataLimitations(comparison, comparisonState.envelope, sourceA, sourceB);
  const earlyCareerA = comparison?.region_a?.scores?.early_career_accessibility_score;
  const earlyCareerB = comparison?.region_b?.scores?.early_career_accessibility_score;

  return (
    <div className="view-grid">
      <ShellCard
        title="Compare markets"
        eyebrow="Objective and category tradeoffs"
        action={<QualityBadgeRow envelope={comparisonState.envelope} />}
      >
        <div className="comparison-controls">
          <label>
            Region A
            <select value={regionA} onChange={(event) => onRegionA(event.target.value)}>
              {regionA && !hasRegionA ? (
                <option value={regionA}>{regions.length ? `Unknown region: ${regionA}` : regionA}</option>
              ) : null}
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
              {regionB && !hasRegionB ? (
                <option value={regionB}>{regions.length ? `Unknown region: ${regionB}` : regionB}</option>
              ) : null}
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
        {validationError && regionA !== regionB ? <ErrorState message={validationError} /> : null}
        {comparisonState.loading ? <LoadingBlock label="Loading comparison output" /> : null}
        {comparisonState.error ? <ErrorState message={comparisonState.error} /> : null}
        <p className="meta-copy">
          The comparison uses returned score fields only. Missing values are shown as
          unavailable and are not treated as zero.
        </p>
      </ShellCard>

      {comparison ? (
        <>
          <ShellCard title="Objective winner" eyebrow="Overall comparison signal">
            <div className="objective-winner-panel">
              <div>
                <span className="badge badge-real">Objective opportunity score</span>
                <h2>{objective.winnerLabel}</h2>
                <p className="lead-copy">{objective.message}</p>
                <p className="meta-copy">
                  This is a narrow objective-score winner, not a guarantee that the region
                  is best for every role, company, or career-stage preference.
                </p>
              </div>
              <div className="objective-score-grid">
                <ScoreCard compact label={regionALabel} value={comparison.region_a?.scores?.objective_opportunity_score} />
                <ScoreCard compact label={regionBLabel} value={comparison.region_b?.scores?.objective_opportunity_score} />
              </div>
            </div>
          </ShellCard>

          <ShellCard title={`${regionALabel} vs ${regionBLabel}`} eyebrow="Category-level score fields">
            <div className="comparison-score-table">
              <div className="comparison-table-head">
                <span>Category</span>
                <strong>{regionALabel}</strong>
                <strong>{regionBLabel}</strong>
                <strong>Winner</strong>
              </div>
              {SCORE_FIELDS.map((score) => {
                const aValue = comparison.region_a?.scores?.[score.key] as number | null | undefined;
                const bValue = comparison.region_b?.scores?.[score.key] as number | null | undefined;
                const hasWinner = Object.prototype.hasOwnProperty.call(categoryWinners, score.key);
                const winner = categoryWinners[score.key];
                const missing = typeof aValue !== "number" || typeof bValue !== "number";
                return (
                  <div className="comparison-table-row" key={score.key}>
                    <span>{score.label}</span>
                    <ScoreCard compact label={score.short} value={aValue} />
                    <ScoreCard compact label={score.short} value={bValue} />
                    <strong>{missing ? "Missing data" : hasWinner ? winnerLabel(winner, regions, comparison) : "Not available"}</strong>
                  </div>
                );
              })}
            </div>
          </ShellCard>

          <div className="split-grid">
            <ShellCard title="Category winners" eyebrow="Separate from objective winner">
              {Object.keys(categoryWinners).length ? (
                <div className="winner-grid">
                  {Object.entries(categoryWinners).map(([category, winner]) => (
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

            <ShellCard title="Early-career tradeoffs" eyebrow="Accessibility signal">
              {typeof earlyCareerA === "number" && typeof earlyCareerB === "number" ? (
                <div className="tradeoff-grid">
                  <ScoreCard compact label={regionALabel} value={earlyCareerA} />
                  <ScoreCard compact label={regionBLabel} value={earlyCareerB} />
                  <p className="meta-copy">
                    {earlyCareerA === earlyCareerB
                      ? "Both regions return the same early-career accessibility score."
                      : `${earlyCareerA > earlyCareerB ? regionALabel : regionBLabel} has the higher early-career accessibility score in this comparison.`}
                  </p>
                </div>
              ) : (
                <EmptyState
                  title="Early-career comparison unavailable"
                  body="One or both regions are missing the early-career accessibility score."
                />
              )}
            </ShellCard>
          </div>

          <div className="split-grid">
            <ShellCard title="Source and freshness differences" eyebrow="Comparison confidence">
              <div className="source-compare-grid">
                <div className="source-compare-card">
                  <strong>{regionALabel}</strong>
                  {sourceAState.loading ? <LoadingBlock label="Loading source details" /> : null}
                  {sourceAState.error ? <ErrorState message={sourceAState.error} /> : null}
                  <QualityBadgeRow envelope={comparisonState.envelope} source={sourceA} />
                  {sourceA ? <MetadataPanel source={sourceA} /> : null}
                </div>
                <div className="source-compare-card">
                  <strong>{regionBLabel}</strong>
                  {sourceBState.loading ? <LoadingBlock label="Loading source details" /> : null}
                  {sourceBState.error ? <ErrorState message={sourceBState.error} /> : null}
                  <QualityBadgeRow envelope={comparisonState.envelope} source={sourceB} />
                  {sourceB ? <MetadataPanel source={sourceB} /> : null}
                </div>
              </div>
            </ShellCard>

            <ShellCard title="Limits and warnings" eyebrow="Do not overread">
              {limitations.length ? (
                <div className="warning-list">
                  {limitations.map((notice) => (
                    <div className="warning-item" key={notice}>
                      <div className="warning-header">
                        <span className="warning-code">Comparison caveat</span>
                      </div>
                      <p>{notice}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="No caveats returned" body="No comparison caveats were detected from returned metadata." />
              )}
              {notes.length ? (
                <ul className="notes-list">
                  {notes.map((note) => (
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
  sourceStates,
  discoveryState,
  selectedRegions,
  roleTargets,
  industries,
  careerStage,
  prestigePreference,
  brandPreference,
  limit,
  onToggleRegion,
  onToggleRole,
  onToggleIndustry,
  onCareerStage,
  onPrestigePreference,
  onBrandPreference,
  onLimit,
  onSubmit,
}: {
  regions: RegionListItem[];
  sourceStates: Record<string, LoadState<SourceExplanation>>;
  discoveryState: LoadState<PersonalizedResult>;
  selectedRegions: string[];
  roleTargets: string[];
  industries: string[];
  careerStage: string;
  prestigePreference: string;
  brandPreference: string;
  limit: number;
  onToggleRegion: (regionId: string) => void;
  onToggleRole: (role: string) => void;
  onToggleIndustry: (industry: string) => void;
  onCareerStage: (stage: string) => void;
  onPrestigePreference: (level: string) => void;
  onBrandPreference: (level: string) => void;
  onLimit: (limit: number) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  const discovery = discoveryState.envelope?.data;
  const knownRegionIds = new Set(regions.map((region) => region.region_id));
  const unknownSelectedRegions = regions.length
    ? selectedRegions.filter((regionId) => !knownRegionIds.has(regionId))
    : [];
  const rankedRegions = discovery?.ranked_regions ?? [];
  const rankedCompanies = discovery?.ranked_companies ?? [];

  return (
    <div className="view-grid">
      <ShellCard
        title="Personalized discovery"
        eyebrow="Request-scoped exploration"
        action={<QualityBadgeRow envelope={discoveryState.envelope} />}
      >
        <p className="lead-copy">
          Discovery scores are exploratory overlays on the returned market data. Filters are
          shareable in the URL, but generated results are not saved or restored after reload.
        </p>
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
            {unknownSelectedRegions.map((regionId) => (
              <label className="checkbox-label" key={regionId}>
                <input checked onChange={() => onToggleRegion(regionId)} type="checkbox" />
                <span>{regionId} (unknown)</span>
              </label>
            ))}
          </fieldset>

          <fieldset>
            <legend>Role targets</legend>
            <p className="fieldset-copy">Role fit only uses role-family summaries returned by the API.</p>
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
            <p className="fieldset-copy">Industry fit comes from company sector fields, not inferred descriptions.</p>
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
              <select value={careerStage} onChange={(event) => onCareerStage(event.target.value)}>
                {CAREER_STAGE_OPTIONS.map((stage) => (
                  <option key={stage} value={stage}>
                    {prettyKey(stage)}
                  </option>
                ))}
              </select>
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

          <div className="preference-summary">
            <span className="badge">Roles: {roleTargets.length ? roleTargets.map(prettyKey).join(", ") : "neutral"}</span>
            <span className="badge">Industries: {industries.length ? industries.map(prettyKey).join(", ") : "neutral"}</span>
            <span className="badge">Prestige: {prestigePreference}</span>
            <span className="badge">Brand: {brandPreference}</span>
          </div>

          <button
            type="submit"
            disabled={!selectedRegions.length || Boolean(unknownSelectedRegions.length) || discoveryState.loading}
          >
            {discoveryState.loading ? "Running..." : "Run discovery"}
          </button>
        </form>
        {unknownSelectedRegions.length ? (
          <ErrorState message={`Discovery URL includes unknown region ID(s): ${unknownSelectedRegions.join(", ")}`} />
        ) : null}
        {discoveryState.error ? <ErrorState message={discoveryState.error} /> : null}
        <MetadataPanel envelope={discoveryState.envelope} />
      </ShellCard>

      {discovery ? (
        <div className="split-grid">
          <ShellCard title="Recommended regions" eyebrow="Exploratory market overlay">
            {rankedRegions.length ? (
              <div className="rank-list">
                {rankedRegions.map((region, index) => (
                  <div className="rank-row" key={region.region_id}>
                    <span className="rank-number">{index + 1}</span>
                    <div>
                      <strong>{region.display_name}</strong>
                      <small>
                        Objective score: {formatValue(region.objective_opportunity_score)}
                      </small>
                      <div className="chip-row">
                        <QualityBadgeRow source={sourceForRegion(region.region_id, sourceStates)} />
                      </div>
                      <ul className="notes-list recommendation-notes">
                        {recommendationNotes(region.match_notes).map((note) => (
                          <li key={note}>{prettyKey(note)}</li>
                        ))}
                      </ul>
                    </div>
                    <ScoreCard compact label="Personalized" value={region.personal_market_score} />
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No recommended regions"
                body="The personalization response returned no region recommendations for this request."
              />
            )}
          </ShellCard>

          <ShellCard title="Recommended company-region pairs" eyebrow="Preference fit components">
            {rankedCompanies.length ? (
              <div className="rank-list">
                {rankedCompanies.map((company, index) => (
                  <div className="rank-row rank-row-company" key={`${company.company_id}-${company.region_id}`}>
                    <span className="rank-number">{index + 1}</span>
                    <div>
                      <strong>{company.company_name}</strong>
                      <small>{company.region_display_name}</small>
                      <div className="chip-row">
                        <QualityBadgeRow source={sourceForRegion(company.region_id, sourceStates)} />
                      </div>
                      <ul className="notes-list recommendation-notes">
                        {recommendationNotes(company.match_notes).map((note) => (
                          <li key={note}>{prettyKey(note)}</li>
                        ))}
                      </ul>
                    </div>
                    <div className="fit-grid">
                      <ScoreCard compact label="Personal" value={company.personal_company_score} />
                      {preferenceInfluencesForCompany(company).map((item) => (
                        <ScoreCard compact key={item.label} label={item.label} value={item.value} />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No recommended companies"
                body="The personalization response returned no company-region recommendations for this request."
              />
            )}
          </ShellCard>
        </div>
      ) : (
        <EmptyState
          title="No discovery run yet"
          body="Choose URL-shareable filters and run the request-scoped personalization overlay."
        />
      )}
    </div>
  );
}

function App() {
  const [route, setRoute] = useState<RouteState>(() => readCurrentRoute());
  const [health, setHealth] = useState<LoadState<{ service: string }>>(emptyLoadState);
  const [regions, setRegions] = useState<LoadState<{ regions: RegionListItem[] }>>(emptyLoadState);
  const [regionDetails, setRegionDetails] = useState<Record<string, ApiEnvelope<RegionDetail>>>({});
  const [regionErrors, setRegionErrors] = useState<Record<string, string>>({});
  const [regionLoading, setRegionLoading] = useState<Record<string, boolean>>({});
  const [regionSearchState, setRegionSearchState] = useState<LoadState<RegionSearchResponse>>(emptyLoadState);
  const [regionSourceStates, setRegionSourceStates] = useState<Record<string, LoadState<SourceExplanation>>>({});
  const [regionCompanySearchStates, setRegionCompanySearchStates] = useState<Record<string, LoadState<CompanySearchResponse>>>({});
  const [companyState, setCompanyState] = useState<LoadState<CompanyDetail>>(emptyLoadState);
  const [companySourceStates, setCompanySourceStates] = useState<Record<string, LoadState<SourceExplanation>>>({});
  const [companyGeographyStates, setCompanyGeographyStates] = useState<Record<string, LoadState<CompanyGeographyResponse>>>({});
  const [comparisonState, setComparisonState] = useState<LoadState<ComparisonDetail>>(emptyLoadState);
  const [discoveryState, setDiscoveryState] = useState<LoadState<PersonalizedResult>>(emptyLoadState);
  const discoveryRequestKey = useRef(0);

  const regionList = useMemo(() => regions.envelope?.data?.regions ?? [], [regions.envelope]);
  const hasLoadedRegionList = Boolean(regions.envelope?.data?.regions);
  const companyOptions = getCompanyOptions(regionDetails);
  const defaultRegionId = getDefaultRegionId(regionList);
  const selectedRegionId = route.regionId ?? defaultRegionId;
  const selectedRegionIsKnown = isKnownRegion(selectedRegionId, regionList, hasLoadedRegionList);
  const selectedCompanyId = route.companyId ?? companyOptions[0]?.company_id ?? "";
  const comparisonA = route.comparison.regionA || defaultRegionId;
  const comparisonB = route.comparison.regionB || getFallbackComparisonRegion(regionList, comparisonA);
  const comparisonRegionAKnown = isKnownRegion(comparisonA, regionList, hasLoadedRegionList);
  const comparisonRegionBKnown = isKnownRegion(comparisonB, regionList, hasLoadedRegionList);
  const discoveryFilters = route.discovery;
  const discoveryUrl = personalizedDiscoveryUrl(discoveryFilters);
  const comparisonValidationError =
    comparisonA === comparisonB
      ? "Choose two distinct regions before running comparison."
      : !comparisonRegionAKnown || !comparisonRegionBKnown
        ? `Comparison URL includes unknown region ID(s): ${[
            comparisonRegionAKnown ? null : comparisonA,
            comparisonRegionBKnown ? null : comparisonB,
          ]
            .filter(Boolean)
            .join(", ")}`
        : null;
  const selectedRegionState: LoadState<RegionDetail> = {
    loading: selectedRegionIsKnown ? Boolean(regionLoading[selectedRegionId]) : false,
    envelope: selectedRegionIsKnown ? regionDetails[selectedRegionId] ?? null : null,
    error: selectedRegionIsKnown
      ? regionErrors[selectedRegionId] ?? null
      : `Unknown region ID: ${selectedRegionId}`,
  };
  const selectedRegionSourceState = regionSourceStates[selectedRegionId] ?? emptyLoadState<SourceExplanation>();
  const selectedRegionRoleFamilyState =
    regionCompanySearchStates[selectedRegionId] ?? emptyLoadState<CompanySearchResponse>();
  const selectedCompanySourceState = companySourceStates[selectedCompanyId] ?? emptyLoadState<SourceExplanation>();
  const selectedCompanyGeographyState =
    companyGeographyStates[selectedCompanyId] ?? emptyLoadState<CompanyGeographyResponse>();
  const regionSourceIdsNeeded = useMemo(() => {
    const ids: string[] = [];
    if (selectedRegionId && selectedRegionIsKnown) ids.push(selectedRegionId);
    if (route.page === "compare") {
      if (comparisonRegionAKnown) ids.push(comparisonA);
      if (comparisonRegionBKnown) ids.push(comparisonB);
    }
    if (route.page === "discovery") {
      for (const regionId of discoveryFilters.selectedRegions) {
        if (isKnownRegion(regionId, regionList, hasLoadedRegionList)) ids.push(regionId);
      }
    }
    return Array.from(new Set(ids));
  }, [
    comparisonA,
    comparisonB,
    comparisonRegionAKnown,
    comparisonRegionBKnown,
    discoveryFilters.selectedRegions,
    hasLoadedRegionList,
    regionList,
    route.page,
    selectedRegionId,
    selectedRegionIsKnown,
  ]);

  const navigateTo = useCallback((url: string, options?: { replace?: boolean }) => {
    if (url === currentUrl()) {
      setRoute(readCurrentRoute());
      return;
    }

    if (options?.replace) {
      window.history.replaceState(null, "", url);
    } else {
      window.history.pushState(null, "", url);
    }
    setRoute(readCurrentRoute());
  }, []);

  const loadRegion = useCallback(async (regionId: string) => {
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
  }, []);

  useEffect(() => {
    const handlePopState = () => setRoute(readCurrentRoute());
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

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
  }, [loadRegion]);

  useEffect(() => {
    async function loadRegionSearch() {
      setRegionSearchState((current) => ({ ...current, loading: true, error: null }));
      try {
        const envelope = await searchRegions();
        setRegionSearchState({ loading: false, envelope, error: null });
      } catch (error) {
        setRegionSearchState({
          loading: false,
          envelope: null,
          error: error instanceof Error ? error.message : "Failed to load region search",
        });
      }
    }

    void loadRegionSearch();
  }, []);

  useEffect(() => {
    if (
      !selectedRegionId
      || !selectedRegionIsKnown
      || regionDetails[selectedRegionId]
      || regionLoading[selectedRegionId]
    ) {
      return;
    }
    void loadRegion(selectedRegionId);
  }, [loadRegion, regionDetails, regionLoading, selectedRegionId, selectedRegionIsKnown]);

  useEffect(() => {
    if (route.page !== "explore") return;
    regionList.forEach((region) => {
      if (!regionDetails[region.region_id] && !regionLoading[region.region_id]) {
        void loadRegion(region.region_id);
      }
    });
  }, [loadRegion, regionDetails, regionList, regionLoading, route.page]);

  useEffect(() => {
    regionSourceIdsNeeded.forEach((regionId) => {
      const current = regionSourceStates[regionId];
      if (current?.loading || current?.envelope || current?.error) return;

      setRegionSourceStates((states) => ({
        ...states,
        [regionId]: { loading: true, envelope: null, error: null },
      }));
      getRegionSources(regionId)
        .then((envelope) => {
          setRegionSourceStates((states) => ({
            ...states,
            [regionId]: { loading: false, envelope, error: null },
          }));
        })
        .catch((error) => {
          setRegionSourceStates((states) => ({
            ...states,
            [regionId]: {
              loading: false,
              envelope: null,
              error: error instanceof Error ? error.message : "Failed to load region sources",
            },
          }));
        });
    });
  }, [regionSourceIdsNeeded, regionSourceStates]);

  useEffect(() => {
    if (route.page !== "compare") return;
    [comparisonA, comparisonB].forEach((regionId) => {
      if (!regionId || !isKnownRegion(regionId, regionList, hasLoadedRegionList)) return;
      if (!regionDetails[regionId] && !regionLoading[regionId]) {
        void loadRegion(regionId);
      }
    });
  }, [
    comparisonA,
    comparisonB,
    hasLoadedRegionList,
    loadRegion,
    regionDetails,
    regionList,
    regionLoading,
    route.page,
  ]);

  useEffect(() => {
    if (!selectedRegionId || !selectedRegionIsKnown) return;
    const current = regionCompanySearchStates[selectedRegionId];
    if (current?.loading || current?.envelope || current?.error) return;

    setRegionCompanySearchStates((states) => ({
      ...states,
      [selectedRegionId]: { loading: true, envelope: null, error: null },
    }));
    searchCompanies({ region_id: selectedRegionId })
      .then((envelope) => {
        setRegionCompanySearchStates((states) => ({
          ...states,
          [selectedRegionId]: { loading: false, envelope, error: null },
        }));
      })
      .catch((error) => {
        setRegionCompanySearchStates((states) => ({
          ...states,
          [selectedRegionId]: {
            loading: false,
            envelope: null,
            error: error instanceof Error ? error.message : "Failed to load company role-family search",
          },
        }));
      });
  }, [regionCompanySearchStates, selectedRegionId, selectedRegionIsKnown]);

  useEffect(() => {
    if (route.page === "region" && !route.regionId && selectedRegionId) {
      navigateTo(regionDetailUrl(selectedRegionId), { replace: true });
    }
  }, [navigateTo, route.page, route.regionId, selectedRegionId]);

  useEffect(() => {
    if (route.page === "company" && !route.companyId && selectedCompanyId) {
      navigateTo(companyGeographyUrl(selectedCompanyId), { replace: true });
    }
  }, [navigateTo, route.companyId, route.page, selectedCompanyId]);

  useEffect(() => {
    async function loadCompany() {
      if (!selectedCompanyId) {
        setCompanyState(emptyLoadState());
        return;
      }
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
    if (!selectedCompanyId) return;
    const current = companySourceStates[selectedCompanyId];
    if (current?.loading || current?.envelope || current?.error) return;

    setCompanySourceStates((states) => ({
      ...states,
      [selectedCompanyId]: { loading: true, envelope: null, error: null },
    }));
    getCompanySources(selectedCompanyId)
      .then((envelope) => {
        setCompanySourceStates((states) => ({
          ...states,
          [selectedCompanyId]: { loading: false, envelope, error: null },
        }));
      })
      .catch((error) => {
        setCompanySourceStates((states) => ({
          ...states,
          [selectedCompanyId]: {
            loading: false,
            envelope: null,
            error: error instanceof Error ? error.message : "Failed to load company sources",
          },
        }));
      });
  }, [companySourceStates, selectedCompanyId]);

  useEffect(() => {
    if (!selectedCompanyId) return;
    const current = companyGeographyStates[selectedCompanyId];
    if (current?.loading || current?.envelope || current?.error) return;

    setCompanyGeographyStates((states) => ({
      ...states,
      [selectedCompanyId]: { loading: true, envelope: null, error: null },
    }));
    getCompanyGeography(selectedCompanyId)
      .then((envelope) => {
        setCompanyGeographyStates((states) => ({
          ...states,
          [selectedCompanyId]: { loading: false, envelope, error: null },
        }));
      })
      .catch((error) => {
        setCompanyGeographyStates((states) => ({
          ...states,
          [selectedCompanyId]: {
            loading: false,
            envelope: null,
            error: error instanceof Error ? error.message : "Failed to load company geography",
          },
        }));
      });
  }, [companyGeographyStates, selectedCompanyId]);

  useEffect(() => {
    if (comparisonValidationError) {
      setComparisonState(emptyLoadState());
      return;
    }

    async function loadComparison() {
      if (!comparisonA || !comparisonB) return;
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
  }, [comparisonA, comparisonB, comparisonValidationError]);

  useEffect(() => {
    discoveryRequestKey.current += 1;
    setDiscoveryState(emptyLoadState());
  }, [discoveryUrl]);

  function handleRouteLink(event: MouseEvent<HTMLAnchorElement>, url: string) {
    if (!isPlainLeftClick(event)) return;
    event.preventDefault();
    navigateTo(url);
  }

  function selectRegion(regionId: string) {
    navigateTo(regionDetailUrl(regionId));
  }

  function selectCompany(companyId: string) {
    navigateTo(companyGeographyUrl(companyId));
  }

  function selectComparisonA(regionId: string) {
    navigateTo(compareMarketsUrl(regionId, comparisonB));
  }

  function selectComparisonB(regionId: string) {
    navigateTo(compareMarketsUrl(comparisonA, regionId));
  }

  function compareRegion(regionId: string) {
    const fallbackRegion = getFallbackComparisonRegion(regionList, regionId);
    const otherRegion = comparisonB && comparisonB !== regionId ? comparisonB : fallbackRegion;
    navigateTo(compareMarketsUrl(regionId, otherRegion));
  }

  function updateDiscoveryFilters(nextFilters: DiscoveryFilters) {
    navigateTo(personalizedDiscoveryUrl(nextFilters));
  }

  function toggleFilterValue(value: string, values: string[]): string[] {
    return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
  }

  async function handleDiscoverySubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const requestKey = discoveryRequestKey.current;
    setDiscoveryState((current) => ({ ...current, loading: true, error: null }));
    try {
      const envelope = await discoverPersonalized({
        region_ids: discoveryFilters.selectedRegions,
        role_targets: discoveryFilters.roleTargets,
        industry_preferences: discoveryFilters.industries,
        career_stage: discoveryFilters.careerStage,
        prestige_preference: discoveryFilters.prestigePreference,
        brand_preference: discoveryFilters.brandPreference,
        limit: discoveryFilters.limit,
      });
      if (requestKey === discoveryRequestKey.current) {
        setDiscoveryState({ loading: false, envelope, error: null });
      }
    } catch (error) {
      if (requestKey === discoveryRequestKey.current) {
        setDiscoveryState({
          loading: false,
          envelope: null,
          error: error instanceof Error ? error.message : "Failed to run personalized discovery",
        });
      }
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
          {NAV_ITEMS.map((item) => {
            const url = getNavigationUrl(
              item.id,
              selectedRegionId,
              selectedCompanyId,
              comparisonA,
              comparisonB,
              discoveryFilters,
            );
            return (
              <a
                className={route.page === item.id ? "nav-item nav-item-active" : "nav-item"}
                href={url}
                key={item.id}
                onClick={(event) => handleRouteLink(event, url)}
              >
                <span>{item.label}</span>
                <small>{item.kicker}</small>
              </a>
            );
          })}
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
            {route.unknownPath ? <p className="meta-copy">Unknown path redirected to Explore Markets.</p> : null}
          </div>
          <div className="topbar-badges">
            <StateBadge envelope={health.envelope} loading={health.loading} error={health.error} />
            <span className="badge">{regionList.length} regions</span>
            <span className="badge">{companyOptions.length} companies</span>
          </div>
        </header>

        {route.page === "explore" ? (
          <ExploreMarkets
            health={health}
            onOpenCompare={() => navigateTo(compareMarketsUrl(comparisonA, comparisonB))}
            onOpenRegionDetail={() => navigateTo(regionDetailUrl(selectedRegionId))}
            onSelectRegion={selectRegion}
            regionDetails={regionDetails}
            regionSearch={regionSearchState}
            regions={regions}
          />
        ) : null}

        {route.page === "region" ? (
          <RegionExplorer
            onCompareRegion={compareRegion}
            onSelectCompany={selectCompany}
            onSelectRegion={selectRegion}
            roleFamilyState={selectedRegionRoleFamilyState}
            regionState={selectedRegionState}
            regions={regionList}
            selectedRegionId={selectedRegionId}
            sourceState={selectedRegionSourceState}
          />
        ) : null}

        {route.page === "company" ? (
          <CompanyExplorer
            companyOptions={companyOptions}
            companyState={companyState}
            geographyState={selectedCompanyGeographyState}
            onSelectCompany={selectCompany}
            selectedCompanyId={selectedCompanyId}
            sourceState={selectedCompanySourceState}
          />
        ) : null}

        {route.page === "compare" ? (
          <ComparisonView
            comparisonState={comparisonState}
            onRegionA={selectComparisonA}
            onRegionB={selectComparisonB}
            regionA={comparisonA}
            regionB={comparisonB}
            regions={regionList}
            sourceAState={regionSourceStates[comparisonA] ?? emptyLoadState<SourceExplanation>()}
            sourceBState={regionSourceStates[comparisonB] ?? emptyLoadState<SourceExplanation>()}
            validationError={comparisonValidationError}
          />
        ) : null}

        {route.page === "discovery" ? (
          <PersonalizedDiscovery
            brandPreference={discoveryFilters.brandPreference}
            careerStage={discoveryFilters.careerStage}
            discoveryState={discoveryState}
            industries={discoveryFilters.industries}
            limit={discoveryFilters.limit}
            onBrandPreference={(brandPreference) =>
              updateDiscoveryFilters({ ...discoveryFilters, brandPreference })
            }
            onCareerStage={(careerStage) =>
              updateDiscoveryFilters({ ...discoveryFilters, careerStage })
            }
            onLimit={(nextLimit) =>
              updateDiscoveryFilters({
                ...discoveryFilters,
                limit: Math.max(1, Math.min(25, nextLimit || 1)),
              })
            }
            onPrestigePreference={(prestigePreference) =>
              updateDiscoveryFilters({ ...discoveryFilters, prestigePreference })
            }
            onSubmit={handleDiscoverySubmit}
            onToggleIndustry={(industry) =>
              updateDiscoveryFilters({
                ...discoveryFilters,
                industries: toggleFilterValue(industry, discoveryFilters.industries),
              })
            }
            onToggleRegion={(regionId) =>
              updateDiscoveryFilters({
                ...discoveryFilters,
                selectedRegions: toggleFilterValue(regionId, discoveryFilters.selectedRegions),
              })
            }
            onToggleRole={(role) =>
              updateDiscoveryFilters({
                ...discoveryFilters,
                roleTargets: toggleFilterValue(role, discoveryFilters.roleTargets),
              })
            }
            prestigePreference={discoveryFilters.prestigePreference}
            regions={regionList}
            roleTargets={discoveryFilters.roleTargets}
            selectedRegions={discoveryFilters.selectedRegions}
            sourceStates={regionSourceStates}
          />
        ) : null}
      </section>
    </main>
  );
}

export default App;
