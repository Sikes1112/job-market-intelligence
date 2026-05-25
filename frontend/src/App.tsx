import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type MouseEvent, type ReactNode } from "react";
import {
  API_TARGET_LABEL,
  createRecommendationSnapshot,
  createSavedMarketArtifact,
  deactivateAccount,
  dismissAlert,
  deletePreferences,
  deleteSavedMarketArtifact,
  discoverPersonalized,
  explainAlert,
  explainComparison,
  explainCompany,
  explainRegion,
  exportUserData,
  getCompany,
  getCompanyGeography,
  getCompanySources,
  getComparison,
  getCurrentUser,
  getHealth,
  getPreferences,
  getRegion,
  getRegionSources,
  getRegions,
  listAlerts,
  listRecommendationSnapshots,
  listSavedMarketArtifacts,
  markAlertRead,
  previewScoringOverlay,
  searchCompanies,
  searchRegions,
  updatePreferences,
  type ProtectedRequestOptions,
} from "./api";
import { useFrontendAuth, type FrontendAuthContextValue } from "./auth";
import {
  coverageComponentEntries,
  coverageDescription,
  coverageDisplayLabel,
  coverageIsWeak,
  coverageScoreText,
  coverageTone,
  dataBasisLabel,
  envelopeFreshnessStatus,
  freshnessLabel,
  isSeedDemoFreshness,
  qualityBadges,
  qualityNotices,
} from "./dataQuality";
import type {
  ApiEnvelope,
  AccountDeactivationResult,
  CompanyGeographyResponse,
  CompanyDetail,
  CompanySearchResponse,
  ComparisonDetail,
  CoverageMetadata,
  SectorCoverageMap,
  CurrentUserProfile,
  ExplanationEvidencePacket,
  ExplanationResult,
  FreshnessSourceSummary,
  FreshnessStatus,
  PersonalizedRecommendationSnapshot,
  PersonalizedRecommendationSnapshotInput,
  PersonalizedResult,
  PreferenceLevel,
  RegionDetail,
  RegionListItem,
  RegionSearchResult,
  RegionSearchResponse,
  RegionScores,
  RemoteHybridPreference,
  SavedMarketArtifact,
  SavedMarketArtifactInput,
  ScoringPreviewResult,
  ScoringWeights,
  SourceExplanation,
  UserAlert,
  UserAlertList,
  UserDataExport,
  UserPreferenceProfile,
  UserPreferenceProfileInput,
  WarningItem,
} from "./types";
import {
  DEFAULT_REGION_A,
  DEFAULT_REGION_B,
  CAREER_STAGE_OPTIONS,
  INDUSTRY_OPTIONS,
  PREFERENCE_LEVELS,
  ROLE_TARGETS,
  accountUrl,
  companyGeographyUrl,
  compareMarketsUrl,
  exploreUrl,
  isProductPage,
  landingUrl,
  parseRoute,
  personalizedDiscoveryUrl,
  publicPageUrl,
  regionDetailUrl,
  type DiscoveryFilters,
  type ProductPage,
  type PublicPage,
  type RouteState,
} from "./urlState";
import {
  DEMO_DISCLOSURE_COPY,
  LANDING_COPY,
  LEGAL_PAGE_COPY,
  PUBLIC_INFO_LINKS,
  type LegalPublicPage,
} from "./publicContent";

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
const SCORING_WEIGHT_FIELDS: Array<{ key: keyof ScoringWeights; label: string }> = [
  { key: "entry_level_access", label: "Entry-level access" },
  { key: "hiring_density", label: "Hiring density" },
  { key: "prestige", label: "Prestige" },
  { key: "industry_fit", label: "Industry fit" },
  { key: "role_fit", label: "Role fit" },
];
const DEFAULT_SCORING_WEIGHTS: ScoringWeights = {
  entry_level_access: 0.30,
  hiring_density: 0.25,
  prestige: 0.15,
  industry_fit: 0.15,
  role_fit: 0.15,
};

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
type PreferenceDraft = {
  roleInterests: string;
  industryInterests: string;
  preferredRegions: string;
  prestigeWeighting: "" | PreferenceLevel;
  brandWeighting: "" | PreferenceLevel;
  careerStage: "" | "entry_level";
  remoteHybridPreference: "" | RemoteHybridPreference;
  scoringWeights: ScoringWeights;
};
type AccountActionState = {
  loading: boolean;
  message: string | null;
  error: string | null;
};

const NAV_ITEMS: Array<{ id: ProductPage; label: string; kicker: string }> = [
  { id: "explore", label: "Explore Markets", kicker: "Market map" },
  { id: "region", label: "Region Detail", kicker: "Regional output" },
  { id: "company", label: "Company Geography", kicker: "Presence and hiring" },
  { id: "compare", label: "Compare Markets", kicker: "Score comparison" },
  { id: "discovery", label: "Personalized Discovery", kicker: "Personal overlay" },
  { id: "account", label: "Account", kicker: "Saved overlays" },
];

const REMOTE_HYBRID_OPTIONS: RemoteHybridPreference[] = ["remote", "hybrid", "onsite", "flexible"];

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
  if (page === "account") return accountUrl();
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

function emptyPreferenceDraft(): PreferenceDraft {
  return {
    roleInterests: "",
    industryInterests: "",
    preferredRegions: "",
    prestigeWeighting: "",
    brandWeighting: "",
    careerStage: "",
    remoteHybridPreference: "",
    scoringWeights: { ...DEFAULT_SCORING_WEIGHTS },
  };
}

function splitDraftList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function joinDraftList(values?: string[]): string {
  return values?.join(", ") ?? "";
}

function preferenceDraftFromProfile(profile?: UserPreferenceProfile | null): PreferenceDraft {
  if (!profile) return emptyPreferenceDraft();
  return {
    roleInterests: joinDraftList(profile.role_interests),
    industryInterests: joinDraftList(profile.industry_interests),
    preferredRegions: joinDraftList(profile.preferred_regions),
    prestigeWeighting: profile.prestige_weighting ?? "",
    brandWeighting: profile.brand_weighting ?? "",
    careerStage: profile.career_stage ?? "",
    remoteHybridPreference: profile.remote_hybrid_preference ?? "",
    scoringWeights: normalizeScoringWeights(profile.scoring_weights),
  };
}

function preferenceInputFromDraft(draft: PreferenceDraft): UserPreferenceProfileInput {
  return {
    role_interests: splitDraftList(draft.roleInterests),
    industry_interests: splitDraftList(draft.industryInterests),
    preferred_regions: splitDraftList(draft.preferredRegions),
    prestige_weighting: draft.prestigeWeighting || null,
    brand_weighting: draft.brandWeighting || null,
    career_stage: draft.careerStage || null,
    remote_hybrid_preference: draft.remoteHybridPreference || null,
    scoring_weights: normalizeScoringWeights(draft.scoringWeights),
  };
}

function savedArtifactKey(type: SavedMarketArtifactInput["artifact_type"], ref: string): string {
  return `${type}:${ref}`;
}

function watchlistGroupLabel(type: SavedMarketArtifact["artifact_type"]): string {
  if (type === "region") return "Regions";
  if (type === "company") return "Companies";
  if (type === "role_family") return "Role families";
  if (type === "comparison") return "Comparison sets";
  return "Discovery results";
}

function watchlistGroups(artifacts: SavedMarketArtifact[]): Array<{
  type: SavedMarketArtifact["artifact_type"];
  label: string;
  items: SavedMarketArtifact[];
}> {
  const order: SavedMarketArtifact["artifact_type"][] = [
    "region",
    "company",
    "role_family",
    "comparison",
    "discovery_result",
  ];
  return order
    .map((type) => ({
      type,
      label: watchlistGroupLabel(type),
      items: artifacts.filter((artifact) => artifact.artifact_type === type),
    }))
    .filter((group) => group.items.length);
}

function normalizeScoringWeights(weights?: Partial<ScoringWeights> | null): ScoringWeights {
  return {
    entry_level_access: clampWeight(weights?.entry_level_access ?? DEFAULT_SCORING_WEIGHTS.entry_level_access),
    hiring_density: clampWeight(weights?.hiring_density ?? DEFAULT_SCORING_WEIGHTS.hiring_density),
    prestige: clampWeight(weights?.prestige ?? DEFAULT_SCORING_WEIGHTS.prestige),
    industry_fit: clampWeight(weights?.industry_fit ?? DEFAULT_SCORING_WEIGHTS.industry_fit),
    role_fit: clampWeight(weights?.role_fit ?? DEFAULT_SCORING_WEIGHTS.role_fit),
  };
}

function clampWeight(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(1, value));
}

function updateScoringWeight(
  weights: ScoringWeights,
  key: keyof ScoringWeights,
  percentValue: number,
): ScoringWeights {
  return normalizeScoringWeights({
    ...weights,
    [key]: percentValue / 100,
  });
}

function canonicalComparisonRef(regionA: string, regionB: string): string {
  return [regionA, regionB].filter(Boolean).sort().join("__");
}

async function sha256Label(value: unknown): Promise<string> {
  const serialized = JSON.stringify(value);
  if (window.crypto?.subtle) {
    const bytes = new TextEncoder().encode(serialized);
    const digest = await window.crypto.subtle.digest("SHA-256", bytes);
    const hex = Array.from(new Uint8Array(digest))
      .map((byte) => byte.toString(16).padStart(2, "0"))
      .join("");
    return `sha256:${hex}`;
  }

  let hash = 0;
  for (const char of serialized) {
    hash = Math.imul(31, hash) + char.charCodeAt(0);
  }
  return `sha256:fallback-${Math.abs(hash).toString(16)}`;
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

function CoverageBadge({ coverage }: { coverage?: CoverageMetadata | null }) {
  return (
    <span className={qualityBadgeClass(coverageTone(coverage))}>
      {coverageDisplayLabel(coverage)}
    </span>
  );
}

function CoverageInlineNote({ coverage }: { coverage?: CoverageMetadata | null }) {
  if (!coverageIsWeak(coverage) && coverage?.tier) return null;
  return <p className="meta-copy coverage-note">{coverageDescription(coverage)}</p>;
}

function CoverageWarningList({ warnings }: { warnings: WarningItem[] }) {
  const coverageWarnings = warnings.filter((warning) => warningCode(warning) === "region_coverage_not_confident");
  if (!coverageWarnings.length) return null;
  return (
    <div className="warning-list coverage-warning-list" aria-label="Coverage warnings">
      {coverageWarnings.map((warning, index) => (
        <div className="warning-item" key={index}>
          <div className="warning-header">
            <span className="warning-code">{prettyKey(warningCode(warning))}</span>
            {warningSeverity(warning) ? (
              <span className="badge badge-warning">{warningSeverity(warning)}</span>
            ) : null}
          </div>
          <p>{warningMessage(warning)}</p>
          {warningScope(warning) ? <small>{warningScope(warning)}</small> : null}
        </div>
      ))}
    </div>
  );
}

function SectorCoveragePanel({ sectorCoverage }: { sectorCoverage?: SectorCoverageMap | null }) {
  const sectors = Object.values(sectorCoverage ?? {}).filter((sector) => sector?.coverage);
  if (!sectors.length) return null;

  return (
    <div className="sector-coverage-panel">
      <div className="coverage-section-heading">
        <strong>Sector coverage</strong>
        <small>Separate from overall region coverage</small>
      </div>
      <div className="sector-coverage-list">
        {sectors.map((sector) => (
          <div className="sector-coverage-row" key={sector.sector}>
            <span>{sector.label ?? prettyKey(sector.sector)}</span>
            <CoverageBadge coverage={sector.coverage} />
          </div>
        ))}
      </div>
    </div>
  );
}

function CoveragePanel({
  coverage,
  sectorCoverage,
}: {
  coverage?: CoverageMetadata | null;
  sectorCoverage?: SectorCoverageMap | null;
}) {
  const scoreText = coverageScoreText(coverage);
  const components = coverageComponentEntries(coverage);
  const notes = coverage?.notes ?? [];

  return (
    <div className="coverage-panel">
      <div className="metadata-row">
        <CoverageBadge coverage={coverage} />
        {coverage?.heuristic ? <span className="badge badge-unknown">Heuristic</span> : null}
      </div>
      {scoreText ? <p className="coverage-score">{scoreText}</p> : null}
      <p className="meta-copy">{coverageDescription(coverage)}</p>
      {components.length ? (
        <div className="coverage-component-grid" aria-label="Coverage components">
          {components.map((component) => (
            <div className="coverage-component-row" key={component.key}>
              <span>{component.label}</span>
              <strong>{component.value}%</strong>
            </div>
          ))}
        </div>
      ) : null}
      {notes.length ? (
        <ul className="coverage-notes">
          {notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      ) : null}
      <SectorCoveragePanel sectorCoverage={sectorCoverage} />
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

function coverageForRegion(
  region: RegionListItem,
  searchItem?: RegionSearchResult,
  detail?: RegionDetail | null,
): { coverage?: CoverageMetadata; sectorCoverage?: SectorCoverageMap } {
  return {
    coverage: searchItem?.coverage ?? detail?.coverage ?? region.coverage,
    sectorCoverage: searchItem?.sector_coverage ?? detail?.sector_coverage ?? region.sector_coverage,
  };
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

function missingScoreLabels(scores?: RegionScores | null): string[] {
  if (!scores) return SCORE_FIELDS.map((score) => score.label);
  return SCORE_FIELDS
    .filter((score) => typeof scores[score.key] !== "number")
    .map((score) => score.label);
}

function sourceRefsFromExplanation(source?: SourceExplanation | null): string[] {
  return (source?.sources ?? []).map((item) => `${item.source_type}:${item.source_id}`);
}

function compactSubjectRefs(refs: Record<string, string | null | undefined>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(refs).filter((entry): entry is [string, string] =>
      typeof entry[1] === "string" && entry[1].trim().length > 0,
    ),
  );
}

function explanationFreshness(
  envelope?: ApiEnvelope<unknown> | null,
  source?: SourceExplanation | FreshnessSourceSummary | null,
) {
  const envelopeFreshness = envelope?.metadata.freshness;
  const summary = getSourceSummary(source);
  const freshnessStatus = summary?.freshness_status ?? envelopeFreshness?.freshness_status ?? null;
  const dataBasis = summary?.data_basis ?? null;
  if (!freshnessStatus && !dataBasis && !envelopeFreshness) return null;
  return {
    freshness_status: freshnessStatus,
    data_basis: dataBasis,
    last_updated_at: envelopeFreshness?.last_updated_at ?? summary?.last_collected_at ?? null,
    freshness_expires_at: envelopeFreshness?.freshness_expires_at ?? null,
    source_count: summary?.source_count ?? null,
  };
}

function regionExplanationEvidence(
  region: RegionDetail,
  envelope?: ApiEnvelope<RegionDetail> | null,
  source?: SourceExplanation | null,
): ExplanationEvidencePacket {
  const freshness = explanationFreshness(envelope, source);
  return {
    entity_type: "region",
    subject_refs: { region_id: region.region_id },
    display_label: region.display_name,
    canonical_scores: Object.fromEntries(
      SCORE_FIELDS.map((score) => {
        const value = region.scores?.[score.key];
        return [score.key, typeof value === "number" ? value : null];
      }),
    ) as Record<string, number | null>,
    freshness,
    source_refs: sourceRefsFromExplanation(source),
    missing_data: missingScoreLabels(region.scores),
    unsupported_data: [
      "historical trend",
      "map geometry",
      "opportunity heatmap density",
      "company-region network layout",
    ],
    demo_or_seeded: Boolean(
      freshness?.freshness_status === "seeded_demo"
        || freshness?.data_basis === "seeded_demo",
    ),
    notes: ["Current snapshot only"],
  };
}

function companyExplanationEvidence(
  company: CompanyDetail,
  envelope?: ApiEnvelope<CompanyDetail> | null,
  source?: SourceExplanation | null,
): ExplanationEvidencePacket {
  const freshness = explanationFreshness(envelope, source);
  const missingData = [
    company.prestige_score === null ? "prestige score" : null,
    (company.regions_present ?? []).length ? null : "presence rows",
    (company.regions_hiring ?? []).length ? null : "hiring rows",
    (company.entry_level_regions ?? []).length ? null : "entry-level rows",
  ].filter(Boolean) as string[];
  return {
    entity_type: "company",
    subject_refs: { company_id: company.company_id },
    display_label: company.company_name,
    canonical_scores: { prestige_score: company.prestige_score },
    freshness,
    source_refs: sourceRefsFromExplanation(source),
    missing_data: missingData,
    unsupported_data: ["market-wide company ranking", "unobserved region presence"],
    demo_or_seeded: Boolean(
      freshness?.freshness_status === "seeded_demo"
        || freshness?.data_basis === "seeded_demo",
    ),
    notes: [
      `Presence rows: ${(company.regions_present ?? []).length}`,
      `Hiring rows: ${(company.regions_hiring ?? []).length}`,
      `Entry-level rows: ${(company.entry_level_regions ?? []).length}`,
    ],
  };
}

function comparisonExplanationEvidence(
  comparison: ComparisonDetail,
  envelope?: ApiEnvelope<ComparisonDetail> | null,
  sourceA?: SourceExplanation | null,
  sourceB?: SourceExplanation | null,
): ExplanationEvidencePacket {
  const freshness = explanationFreshness(envelope, sourceA ?? sourceB);
  const missing = [
    ...missingScoreLabels(comparison.region_a?.scores).map((label) => `Region A ${label}`),
    ...missingScoreLabels(comparison.region_b?.scores).map((label) => `Region B ${label}`),
  ];
  return {
    entity_type: "comparison",
    subject_refs: compactSubjectRefs({
      comparison_id: comparison.comparison_id,
      region_a: comparison.region_a?.region_id ?? "",
      region_b: comparison.region_b?.region_id ?? "",
    }),
    display_label: `${comparison.region_a?.display_name ?? "Region A"} vs ${comparison.region_b?.display_name ?? "Region B"}`,
    canonical_scores: {
      region_a_objective_opportunity_score: comparison.region_a?.scores?.objective_opportunity_score ?? null,
      region_b_objective_opportunity_score: comparison.region_b?.scores?.objective_opportunity_score ?? null,
      region_a_early_career_accessibility_score: comparison.region_a?.scores?.early_career_accessibility_score ?? null,
      region_b_early_career_accessibility_score: comparison.region_b?.scores?.early_career_accessibility_score ?? null,
    },
    freshness,
    source_refs: [
      ...sourceRefsFromExplanation(sourceA),
      ...sourceRefsFromExplanation(sourceB),
    ],
    missing_data: missing,
    unsupported_data: ["historical trend", "geographic distance or commute comparison"],
    notes: comparison.notes ?? [],
  };
}

function alertExplanationEvidence(alert: UserAlert): ExplanationEvidencePacket {
  const summary = alert.event.change_summary;
  const changedFields = summary && !Array.isArray(summary) && Array.isArray(summary.changed_fields)
    ? summary.changed_fields.filter((item): item is string => typeof item === "string")
    : [];
  return {
    entity_type: "alert",
    subject_refs: compactSubjectRefs({
      user_alert_id: alert.user_alert_id,
      alert_event_id: alert.alert_event_id,
      company_id: alert.event.company_id ?? "",
      region_id: alert.event.region_id ?? "",
    }),
    display_label: alertEventLabel(alert),
    freshness: {
      freshness_status: alert.event.freshness_status,
      freshness_expires_at: alert.event.freshness_expires_at,
      last_updated_at: alert.event.freshness_observed_at,
      source_count: alert.event.source_refs.length,
    },
    source_refs: [...alert.event.source_refs, ...alert.event.change_basis_refs],
    alert: {
      event_type: alert.event.event_type,
      relevance_reason: alert.relevance.reason,
      changed_fields: changedFields,
      detection_basis: alert.event.detection_basis,
    },
    watchlist_context: [
      alert.relevance.reason,
      alert.relevance.artifact_type ?? "",
      alert.relevance.artifact_ref ?? "",
    ].filter(Boolean),
    missing_data: alert.event.freshness_status ? [] : ["freshness status"],
    unsupported_data: ["unobserved future hiring changes"],
  };
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
  coverage?: CoverageMetadata;
  sectorCoverage?: SectorCoverageMap;
}> {
  const regions = new Map<string, {
    regionId: string;
    regionName: string;
    signals: Set<string>;
    entryScore: number | null;
    activePostings: number | null;
    freshness?: FreshnessSourceSummary;
    coverage?: CoverageMetadata;
    sectorCoverage?: SectorCoverageMap;
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
      coverage?: CoverageMetadata;
      sectorCoverage?: SectorCoverageMap;
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
      const item = ensure(row.region_id, row.region_display_name);
      item.coverage ??= row.coverage;
      item.sectorCoverage ??= row.sector_coverage;
      item.signals.add("Presence");
    }
  }

  for (const row of company.regions_hiring ?? []) {
    const item = ensure(row.region_id, row.region_display_name);
    item.activePostings = row.active_posting_count_now;
    item.coverage ??= row.coverage;
    item.sectorCoverage ??= row.sector_coverage;
    if (row.currently_hiring_flag || (row.active_posting_count_now ?? 0) > 0) {
      item.signals.add("Hiring activity");
    }
  }

  for (const row of company.entry_level_regions ?? []) {
    const item = ensure(row.region_id, row.region_display_name);
    item.entryScore = row.entry_level_access_score;
    item.coverage ??= row.coverage;
    item.sectorCoverage ??= row.sector_coverage;
    if (hasEntryLevelAccess(row)) {
      item.signals.add("Entry-level access");
    }
  }

  for (const row of geography?.regions ?? []) {
    const item = ensure(row.region_id, row.region_name);
    item.freshness = row.freshness;
    item.coverage ??= row.coverage;
    item.sectorCoverage ??= row.sector_coverage;
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
      coverage: item.coverage,
      sectorCoverage: item.sectorCoverage,
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

function AuthStatusPanel({
  auth,
  onOpenAccount,
}: {
  auth: FrontendAuthContextValue;
  onOpenAccount: () => void;
}) {
  if (!auth.isConfigured) {
    return (
      <div className="auth-panel">
        <span className="badge badge-unknown">Local account mode</span>
        <p>Auth0 frontend config is not set. Public market exploration remains available.</p>
      </div>
    );
  }

  if (auth.isLoading) {
    return (
      <div className="auth-panel">
        <span className="badge badge-loading">Checking account</span>
      </div>
    );
  }

  if (!auth.isAuthenticated) {
    return (
      <div className="auth-panel">
        <span className="badge">Signed out</span>
        <p>Sign in to save personal overlays.</p>
        <button className="secondary-button" type="button" onClick={() => void auth.login()}>
          Sign in
        </button>
      </div>
    );
  }

  return (
    <div className="auth-panel">
      <span className="badge badge-success">Signed in</span>
      <strong>{auth.user?.name ?? auth.user?.email ?? "Auth0 user"}</strong>
      <div className="auth-actions">
        <button className="secondary-button" type="button" onClick={onOpenAccount}>
          Account
        </button>
        <button className="secondary-button" type="button" onClick={auth.logout}>
          Sign out
        </button>
      </div>
    </div>
  );
}

type LinkClickHandler = (event: MouseEvent<HTMLAnchorElement>, url: string) => void;

function DemoDisclosure({ compact = false }: { compact?: boolean }) {
  return (
    <aside className={compact ? "demo-disclosure demo-disclosure-compact" : "demo-disclosure"}>
      <div>
        <strong>{DEMO_DISCLOSURE_COPY.title}</strong>
        <p>{DEMO_DISCLOSURE_COPY.summary}</p>
      </div>
      {!compact ? (
        <ul>
          {DEMO_DISCLOSURE_COPY.bullets.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
    </aside>
  );
}

function PublicInfoLinks({
  activePage,
  onNavigate,
  variant,
  includeOverview = false,
}: {
  activePage: PublicPage | null;
  onNavigate: LinkClickHandler;
  variant: "sidebar" | "footer" | "top";
  includeOverview?: boolean;
}) {
  return (
    <nav className={`public-link-list public-link-list-${variant}`} aria-label="Public information">
      {includeOverview ? (
        <a
          className={activePage === "landing" ? "public-link-active" : ""}
          href={landingUrl()}
          onClick={(event) => onNavigate(event, landingUrl())}
        >
          Overview
        </a>
      ) : null}
      {PUBLIC_INFO_LINKS.map((item) => (
        <a
          className={activePage === item.page ? "public-link-active" : ""}
          href={item.href}
          key={item.page}
          onClick={(event) => onNavigate(event, item.href)}
        >
          {item.label}
        </a>
      ))}
    </nav>
  );
}

function PublicFooter({
  activePage,
  onNavigate,
}: {
  activePage: PublicPage | null;
  onNavigate: LinkClickHandler;
}) {
  return (
    <footer className="public-footer">
      <p>Public demo only. Verify important decisions independently.</p>
      <PublicInfoLinks activePage={activePage} includeOverview onNavigate={onNavigate} variant="footer" />
    </footer>
  );
}

function PublicShell({
  activePage,
  children,
  onNavigate,
}: {
  activePage: PublicPage;
  children: ReactNode;
  onNavigate: LinkClickHandler;
}) {
  return (
    <main className="public-shell">
      <header className="public-header">
        <a className="public-brand" href={landingUrl()} onClick={(event) => onNavigate(event, landingUrl())}>
          <span className="brand-mark">JM</span>
          <span>
            <strong>Job Market Intelligence</strong>
            <small>Public demo</small>
          </span>
        </a>
        <div className="public-header-actions">
          <PublicInfoLinks activePage={activePage} onNavigate={onNavigate} variant="top" />
          <a className="primary-button" href={exploreUrl()} onClick={(event) => onNavigate(event, exploreUrl())}>
            Enter demo
          </a>
        </div>
      </header>
      <section className="public-content">
        {children}
      </section>
      <PublicFooter activePage={activePage} onNavigate={onNavigate} />
    </main>
  );
}

function LandingPage({
  onNavigate,
  unknownPath,
}: {
  onNavigate: LinkClickHandler;
  unknownPath?: string;
}) {
  return (
    <div className="public-page">
      <section className="public-intro">
        <p className="eyebrow">{LANDING_COPY.eyebrow}</p>
        <h1>{LANDING_COPY.title}</h1>
        <p className="public-lead">{LANDING_COPY.intro}</p>
        {unknownPath ? (
          <p className="meta-copy">Unknown public path opened the overview: {unknownPath}</p>
        ) : null}
        <div className="hero-actions">
          <a className="primary-button" href={exploreUrl()} onClick={(event) => onNavigate(event, exploreUrl())}>
            {LANDING_COPY.ctaLabel}
          </a>
          <a
            className="secondary-button"
            href={publicPageUrl("data-limitations")}
            onClick={(event) => onNavigate(event, publicPageUrl("data-limitations"))}
          >
            {LANDING_COPY.secondaryCtaLabel}
          </a>
        </div>
      </section>

      <DemoDisclosure />

      <section className="public-section-grid" aria-label="Demo overview">
        {LANDING_COPY.sections.map((section) => (
          <article className="public-section" key={section.title}>
            <h2>{section.title}</h2>
            <p>{section.body}</p>
          </article>
        ))}
      </section>
    </div>
  );
}

function LegalPage({ page }: { page: LegalPublicPage }) {
  const copy = LEGAL_PAGE_COPY[page];
  return (
    <div className="public-page public-document">
      <section className="public-intro public-document-intro">
        <p className="eyebrow">{copy.eyebrow}</p>
        <h1>{copy.title}</h1>
        <p className="public-lead">{copy.intro}</p>
      </section>
      <DemoDisclosure compact />
      <section className="public-document-list" aria-label={copy.title}>
        {copy.sections.map((section) => (
          <article className="public-section" key={section.title}>
            <h2>{section.title}</h2>
            <p>{section.body}</p>
            {section.bullets?.length ? (
              <ul>
                {section.bullets.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : null}
          </article>
        ))}
      </section>
    </div>
  );
}

function PublicRouteView({
  route,
  onNavigate,
}: {
  route: RouteState;
  onNavigate: LinkClickHandler;
}) {
  const activePage = route.page as PublicPage;
  return (
    <PublicShell activePage={activePage} onNavigate={onNavigate}>
      {activePage === "landing" ? (
        <LandingPage onNavigate={onNavigate} unknownPath={route.unknownPath} />
      ) : (
        <LegalPage page={activePage as LegalPublicPage} />
      )}
    </PublicShell>
  );
}

function JsonBlock({ value }: { value: unknown }) {
  return <pre className="json-block">{JSON.stringify(value, null, 2)}</pre>;
}

function alertEventLabel(alert: UserAlert): string {
  return prettyKey(alert.event.event_type);
}

function alertFreshnessText(alert: UserAlert): string {
  const status = alert.event.freshness_status ? prettyKey(alert.event.freshness_status) : "Freshness unknown";
  const observed = formatDateTime(alert.event.freshness_observed_at);
  const expires = formatDateTime(alert.event.freshness_expires_at);
  if (alert.event.freshness_observed_at || alert.event.freshness_expires_at) {
    return `${status} · observed ${observed} · expires ${expires}`;
  }
  return status;
}

function alertScopeText(alert: UserAlert): string {
  const parts = [
    alert.event.company_id ? `Company ${alert.event.company_id}` : null,
    alert.event.region_id ? `Region ${alert.event.region_id}` : null,
    alert.event.role_family ? `Role ${alert.event.role_family}` : null,
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : "System event";
}

function alertChangeText(alert: UserAlert): string {
  const summary = alert.event.change_summary;
  if (!summary || Array.isArray(summary)) return "Structured change metadata only.";
  const changed = Array.isArray(summary.changed_fields)
    ? summary.changed_fields.join(", ")
    : null;
  return changed ? `Changed fields: ${changed}` : "Structured change metadata only.";
}

function AccountView({
  auth,
  currentUserState,
  preferenceState,
  preferenceDraft,
  artifactsState,
  alertsState,
  snapshotsState,
  scoringPreviewState,
  alertExplanationStates,
  exportState,
  deactivationResult,
  actionState,
  deactivateConfirmed,
  onLogin,
  onRefresh,
  onPreferenceDraft,
  onSavePreferences,
  onPreviewScoring,
  onDeletePreferences,
  onDeleteArtifact,
  onMarkAlertRead,
  onDismissAlert,
  onExplainAlert,
  onExport,
  onDeactivate,
  onDeactivateConfirmed,
}: {
  auth: FrontendAuthContextValue;
  currentUserState: LoadState<CurrentUserProfile>;
  preferenceState: LoadState<UserPreferenceProfile>;
  preferenceDraft: PreferenceDraft;
  artifactsState: LoadState<{ saved_market_artifacts: SavedMarketArtifact[] }>;
  alertsState: LoadState<UserAlertList>;
  snapshotsState: LoadState<{ personalized_recommendation_snapshots: PersonalizedRecommendationSnapshot[] }>;
  scoringPreviewState: LoadState<ScoringPreviewResult>;
  alertExplanationStates: Record<string, LoadState<ExplanationResult>>;
  exportState: LoadState<UserDataExport>;
  deactivationResult: AccountDeactivationResult | null;
  actionState: AccountActionState;
  deactivateConfirmed: boolean;
  onLogin: () => void;
  onRefresh: () => void;
  onPreferenceDraft: (draft: PreferenceDraft) => void;
  onSavePreferences: () => void;
  onPreviewScoring: () => void;
  onDeletePreferences: () => void;
  onDeleteArtifact: (savedArtifactId: string) => void;
  onMarkAlertRead: (userAlertId: string) => void;
  onDismissAlert: (userAlertId: string) => void;
  onExplainAlert: (alert: UserAlert) => void;
  onExport: () => void;
  onDeactivate: () => void;
  onDeactivateConfirmed: (confirmed: boolean) => void;
}) {
  const currentUser = currentUserState.envelope?.data;
  const preferences = preferenceState.envelope?.data;
  const artifacts = artifactsState.envelope?.data?.saved_market_artifacts ?? [];
  const alerts = alertsState.envelope?.data?.alerts ?? [];
  const groupedWatchlists = watchlistGroups(artifacts);
  const snapshots = snapshotsState.envelope?.data?.personalized_recommendation_snapshots ?? [];

  if (!auth.isConfigured) {
    return (
      <div className="view-grid">
        <ShellCard title="Account" eyebrow="Auth0 configuration required">
          <EmptyState
            title="Local demo mode"
            body="Auth0 frontend variables are not configured, so account workflows are disabled while public market exploration remains available."
          />
        </ShellCard>
      </div>
    );
  }

  if (!auth.isAuthenticated) {
    return (
      <div className="view-grid">
        <ShellCard title="Account" eyebrow="Signed out">
          <p className="lead-copy">
            Account and personalization workflows use protected /me routes. Public market
            exploration does not require sign-in.
          </p>
          <button className="primary-button" type="button" onClick={onLogin}>Sign in with Auth0</button>
        </ShellCard>
      </div>
    );
  }

  return (
    <div className="view-grid">
      {actionState.message ? (
        <div className="notice-state">
          <strong>Account update</strong>
          <p>{actionState.message}</p>
        </div>
      ) : null}
      {actionState.error ? <ErrorState message={actionState.error} /> : null}

      <div className="split-grid">
        <ShellCard
          title="Current user"
          eyebrow="Internal app account"
          action={<button className="secondary-button" type="button" onClick={onRefresh}>Refresh</button>}
        >
          {currentUserState.loading ? <LoadingBlock label="Loading account" /> : null}
          {currentUserState.error ? <ErrorState message={currentUserState.error} /> : null}
          {currentUser ? (
            <div className="account-summary">
              <div>
                <span>User ID</span>
                <strong>{currentUser.user.user_id}</strong>
              </div>
              <div>
                <span>Status</span>
                <strong>{currentUser.user.status}</strong>
              </div>
              <div>
                <span>Email</span>
                <strong>{currentUser.profile.email ?? "n/a"}</strong>
              </div>
              <div>
                <span>Display</span>
                <strong>{currentUser.profile.display_name ?? auth.user?.name ?? "n/a"}</strong>
              </div>
            </div>
          ) : null}
          <p className="meta-copy">
            Auth0 identity is mapped to this internal user. Saved overlays use the internal user id,
            not the Auth0 subject, as their durable owner.
          </p>
        </ShellCard>

        <ShellCard title="Privacy controls" eyebrow="App-owned data only">
          <p className="meta-copy">
            Export and deactivation operate on Layer 7 account data. They do not delete or change
            canonical regions, companies, objective scores, source freshness, ingestion records, or
            output metadata.
          </p>
          <div className="account-button-row">
            <button className="secondary-button" disabled={actionState.loading} type="button" onClick={onExport}>
              Export user data
            </button>
            <label className="checkbox-label">
              <input
                checked={deactivateConfirmed}
                onChange={(event) => onDeactivateConfirmed(event.target.checked)}
                type="checkbox"
              />
              <span>Confirm app account deactivation</span>
            </label>
            <button
              className="danger-button"
              disabled={!deactivateConfirmed || actionState.loading}
              type="button"
              onClick={onDeactivate}
            >
              Deactivate app account
            </button>
          </div>
          {deactivationResult ? <JsonBlock value={deactivationResult} /> : null}
        </ShellCard>
      </div>

      <ShellCard title="Alerts" eyebrow="In-app change feed">
        {alertsState.loading ? <LoadingBlock label="Loading alerts" /> : null}
        {alertsState.error ? <ErrorState message={alertsState.error} /> : null}
        <AlertSummaryVisualization alerts={alerts} />
        {alerts.length ? (
          <div className="account-list alert-feed">
            {alerts.map((alert) => (
              <div
                className={alert.is_read ? "account-list-row alert-row" : "account-list-row alert-row alert-row-unread"}
                key={alert.user_alert_id}
              >
                <div>
                  <div className="metadata-row">
                    <span className="badge">{alertEventLabel(alert)}</span>
                    <span className={alert.is_read ? "badge badge-unknown" : "badge badge-success"}>
                      {alert.is_read ? "Read" : "Unread"}
                    </span>
                    <span className="badge badge-unknown">{alertFreshnessText(alert)}</span>
                  </div>
                  <strong>{alertScopeText(alert)}</strong>
                  <small>
                    Relevance: {prettyKey(alert.relevance.reason)}
                    {alert.relevance.artifact_ref ? ` · ${alert.relevance.artifact_ref}` : ""}
                    {" · "}
                    created {formatDateTime(alert.created_at)}
                  </small>
                  <p className="meta-copy">{alertChangeText(alert)}</p>
                </div>
                <div className="alert-actions">
                  <button
                    className="secondary-button"
                    disabled={actionState.loading || alert.is_read}
                    type="button"
                    onClick={() => onMarkAlertRead(alert.user_alert_id)}
                  >
                    Mark read
                  </button>
                  <button
                    className="secondary-button"
                    disabled={actionState.loading || alert.dismissed}
                    type="button"
                    onClick={() => onDismissAlert(alert.user_alert_id)}
                  >
                    Dismiss
                  </button>
                  <button
                    className="secondary-button"
                    disabled={actionState.loading}
                    type="button"
                    onClick={() => onExplainAlert(alert)}
                  >
                    Explain
                  </button>
                </div>
                <ExplanationResultPanel
                  emptyCopy="Use Explain to render alert guidance from this alert event packet."
                  state={alertExplanationStates[alert.user_alert_id]}
                />
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No alerts"
            body="Alerts appear here when structured market changes match saved watchlists or preferences."
          />
        )}
      </ShellCard>

      <ShellCard title="Saved preferences" eyebrow="User-owned inputs">
        {preferenceState.loading ? <LoadingBlock label="Loading preferences" /> : null}
        {preferenceState.error ? <ErrorState message={preferenceState.error} /> : null}
        <p className="meta-copy">
          These inputs are personal preferences only. They do not alter objective market records.
          Current state: {preferences?.persisted ? "saved" : "empty/default"}.
        </p>
        <div className="account-form-grid">
          <label>
            Role interests
            <input
              onChange={(event) => onPreferenceDraft({ ...preferenceDraft, roleInterests: event.target.value })}
              placeholder="product, cybersecurity"
              value={preferenceDraft.roleInterests}
            />
          </label>
          <label>
            Industry interests
            <input
              onChange={(event) => onPreferenceDraft({ ...preferenceDraft, industryInterests: event.target.value })}
              placeholder="software, ai, cloud"
              value={preferenceDraft.industryInterests}
            />
          </label>
          <label>
            Preferred regions
            <input
              onChange={(event) => onPreferenceDraft({ ...preferenceDraft, preferredRegions: event.target.value })}
              placeholder="greater_boston, greater_sf"
              value={preferenceDraft.preferredRegions}
            />
          </label>
          <label>
            Prestige weighting
            <select
              value={preferenceDraft.prestigeWeighting}
              onChange={(event) =>
                onPreferenceDraft({
                  ...preferenceDraft,
                  prestigeWeighting: event.target.value as PreferenceDraft["prestigeWeighting"],
                })
              }
            >
              <option value="">No saved weighting</option>
              {PREFERENCE_LEVELS.map((level) => (
                <option key={level} value={level}>{level}</option>
              ))}
            </select>
          </label>
          <label>
            Brand weighting
            <select
              value={preferenceDraft.brandWeighting}
              onChange={(event) =>
                onPreferenceDraft({
                  ...preferenceDraft,
                  brandWeighting: event.target.value as PreferenceDraft["brandWeighting"],
                })
              }
            >
              <option value="">No saved weighting</option>
              {PREFERENCE_LEVELS.map((level) => (
                <option key={level} value={level}>{level}</option>
              ))}
            </select>
          </label>
          <label>
            Career stage
            <select
              value={preferenceDraft.careerStage}
              onChange={(event) =>
                onPreferenceDraft({
                  ...preferenceDraft,
                  careerStage: event.target.value as PreferenceDraft["careerStage"],
                })
              }
            >
              <option value="">No saved stage</option>
              {CAREER_STAGE_OPTIONS.map((stage) => (
                <option key={stage} value={stage}>{prettyKey(stage)}</option>
              ))}
            </select>
          </label>
          <label>
            Remote/hybrid preference
            <select
              value={preferenceDraft.remoteHybridPreference}
              onChange={(event) =>
                onPreferenceDraft({
                  ...preferenceDraft,
                  remoteHybridPreference: event.target.value as PreferenceDraft["remoteHybridPreference"],
                })
              }
            >
              <option value="">No saved preference</option>
              {REMOTE_HYBRID_OPTIONS.map((option) => (
                <option key={option} value={option}>{prettyKey(option)}</option>
              ))}
            </select>
          </label>
        </div>
        <div className="scoring-control-grid">
          {SCORING_WEIGHT_FIELDS.map((field) => (
            <label className="range-label" key={field.key}>
              <span>
                {field.label}
                <strong>{Math.round(preferenceDraft.scoringWeights[field.key] * 100)}%</strong>
              </span>
              <input
                max={100}
                min={0}
                onChange={(event) =>
                  onPreferenceDraft({
                    ...preferenceDraft,
                    scoringWeights: updateScoringWeight(
                      preferenceDraft.scoringWeights,
                      field.key,
                      Number(event.target.value),
                    ),
                  })
                }
                type="range"
                value={Math.round(preferenceDraft.scoringWeights[field.key] * 100)}
              />
            </label>
          ))}
        </div>
        <div className="account-button-row">
          <button disabled={actionState.loading} type="button" onClick={onSavePreferences}>
            Save preferences
          </button>
          <button
            className="secondary-button"
            disabled={actionState.loading || scoringPreviewState.loading}
            type="button"
            onClick={onPreviewScoring}
          >
            Preview scoring overlay
          </button>
          <button
            className="secondary-button"
            disabled={actionState.loading || !preferences?.persisted}
            type="button"
            onClick={onDeletePreferences}
          >
            Delete preferences
          </button>
        </div>
        {scoringPreviewState.loading ? <LoadingBlock label="Loading scoring preview" /> : null}
        {scoringPreviewState.error ? <ErrorState message={scoringPreviewState.error} /> : null}
        {scoringPreviewState.envelope?.data ? (
          <ScoringPreviewPanel preview={scoringPreviewState.envelope.data} />
        ) : null}
      </ShellCard>

      <ShellCard title="Watchlist" eyebrow="Saved references">
        {artifactsState.loading ? <LoadingBlock label="Loading saved artifacts" /> : null}
        {artifactsState.error ? <ErrorState message={artifactsState.error} /> : null}
        {groupedWatchlists.length ? (
          <div className="watchlist-dashboard">
            {groupedWatchlists.map((group) => (
              <section className="watchlist-group" key={group.type}>
                <div className="watchlist-group-header">
                  <strong>{group.label}</strong>
                  <span className="badge">{group.items.length}</span>
                </div>
                <div className="account-list">
                  {group.items.map((artifact) => (
                    <div className="account-list-row" key={artifact.saved_artifact_id}>
                      <div>
                        <strong>{artifact.label ?? artifact.artifact_ref}</strong>
                        <small>{artifact.artifact_ref} · saved {formatDateTime(artifact.created_at)}</small>
                        {artifact.notes ? <p className="meta-copy">{artifact.notes}</p> : null}
                      </div>
                      <button
                        className="secondary-button"
                        disabled={actionState.loading}
                        type="button"
                        onClick={() => onDeleteArtifact(artifact.saved_artifact_id)}
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                </div>
              </section>
            ))}
          </div>
        ) : (
          <EmptyState title="No watchlist items" body="Save a visible region, company, role family, or comparison set." />
        )}
      </ShellCard>

      <ShellCard title="Recommendation snapshots" eyebrow="Persisted derived overlays">
        {snapshotsState.loading ? <LoadingBlock label="Loading snapshots" /> : null}
        {snapshotsState.error ? <ErrorState message={snapshotsState.error} /> : null}
        {snapshots.length ? (
          <div className="account-list">
            {snapshots.map((snapshot) => (
              <details className="account-list-row account-details-row" key={snapshot.recommendation_snapshot_id}>
                <summary>
                  <span>
                    <strong>{snapshot.recommendation_version}</strong>
                    <small>{formatDateTime(snapshot.generated_at)}</small>
                  </span>
                </summary>
                <JsonBlock value={snapshot} />
              </details>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No recommendation snapshots"
            body="Run personalized discovery while signed in, then persist the visible output as a recommendation snapshot."
          />
        )}
      </ShellCard>

      {exportState.envelope?.data ? (
        <ShellCard title="Export preview" eyebrow="Current user-owned data">
          <JsonBlock value={exportState.envelope.data} />
        </ShellCard>
      ) : null}
      {exportState.error ? <ErrorState message={exportState.error} /> : null}
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

function ScoringPreviewPanel({ preview }: { preview: ScoringPreviewResult }) {
  if (!preview.regions.length) {
    return <EmptyState title="No preview regions" body="Choose at least one preferred region." />;
  }

  return (
    <div className="preview-panel">
      {preview.regions.map((region) => (
        <div className="preview-row" key={region.region_id}>
          <div>
            <span className="badge">Personalized overlay</span>
            <CoverageBadge coverage={region.coverage} />
            <strong>{region.display_name}</strong>
            <small>{region.region_id}</small>
            <CoverageInlineNote coverage={region.coverage} />
          </div>
          <ScoreCard
            compact
            label="Canonical/default objective"
            value={region.canonical_default_scores.objective_opportunity_score}
          />
          <ScoreCard
            compact
            label="Personalized overlay"
            value={region.personalized_overlay_score}
          />
          <div className="preview-component-list">
            {SCORING_WEIGHT_FIELDS.map((field) => {
              const component = region.components[field.key];
              return (
                <span className="badge" key={field.key}>
                  {field.label}: {formatValue(component?.value)} · weight{" "}
                  {Math.round((component?.effective_weight ?? 0) * 100)}%
                </span>
              );
            })}
          </div>
          <CoveragePanel coverage={region.coverage} />
        </div>
      ))}
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

function ScoreBreakdownChart({
  scores,
  title = "Canonical/default score breakdown",
}: {
  scores: RegionScores | null | undefined;
  title?: string;
}) {
  if (!scores) {
    return (
      <UnsupportedVisualizationPanel
        items={["Score breakdown chart"]}
        reason="No score object was returned for the current snapshot."
      />
    );
  }

  return (
    <div className="visualization-panel">
      <div className="visualization-header">
        <strong>{title}</strong>
        <span className="badge badge-unknown">Current snapshot</span>
      </div>
      <div className="visual-bar-list" aria-label={title}>
        {SCORE_FIELDS.map((score) => {
          const value = scores[score.key] as number | null;
          const missing = typeof value !== "number";
          return (
            <div className="visual-bar-row" key={score.key}>
              <span>{score.label}</span>
              <div className={missing ? "visual-bar visual-bar-missing" : "visual-bar"}>
                <span style={{ width: `${scorePercent(value)}%` }} />
              </div>
              <strong>{missing ? "Missing" : `${Math.round(value * 100)}%`}</strong>
            </div>
          );
        })}
      </div>
      <p className="meta-copy">
        This chart renders stored score fields only. Missing values are not
        converted to zero.
      </p>
    </div>
  );
}

function ComparisonScoreChart({
  comparison,
  regionALabel,
  regionBLabel,
}: {
  comparison: ComparisonDetail;
  regionALabel: string;
  regionBLabel: string;
}) {
  return (
    <div className="visualization-panel">
      <div className="visualization-header">
        <strong>Region comparison visualization</strong>
        <span className="badge badge-unknown">Current snapshot</span>
      </div>
      <div className="comparison-visual-list">
        {SCORE_FIELDS.map((score) => {
          const aValue = comparison.region_a?.scores?.[score.key] as number | null | undefined;
          const bValue = comparison.region_b?.scores?.[score.key] as number | null | undefined;
          return (
            <div className="comparison-visual-row" key={score.key}>
              <span>{score.label}</span>
              <div>
                <small>{regionALabel}</small>
                <div className={typeof aValue === "number" ? "visual-bar" : "visual-bar visual-bar-missing"}>
                  <span style={{ width: `${scorePercent(aValue)}%` }} />
                </div>
              </div>
              <div>
                <small>{regionBLabel}</small>
                <div className={typeof bValue === "number" ? "visual-bar" : "visual-bar visual-bar-missing"}>
                  <span style={{ width: `${scorePercent(bValue)}%` }} />
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <p className="meta-copy">
        Bars compare returned canonical/default score fields. This is not a new
        scoring model.
      </p>
    </div>
  );
}

function AlertSummaryVisualization({ alerts }: { alerts: UserAlert[] }) {
  if (!alerts.length) {
    return (
      <UnsupportedVisualizationPanel
        items={["Alert summary chart"]}
        reason="No current in-app alerts were returned for this account."
      />
    );
  }
  const counts = new Map<string, number>();
  for (const alert of alerts) {
    counts.set(alert.event.event_type, (counts.get(alert.event.event_type) ?? 0) + 1);
  }
  const maxCount = Math.max(...counts.values(), 1);
  return (
    <div className="visualization-panel">
      <div className="visualization-header">
        <strong>Alert change summary</strong>
        <span className="badge badge-unknown">Feed metadata</span>
      </div>
      <div className="visual-bar-list">
        {Array.from(counts.entries()).sort().map(([eventType, count]) => (
          <div className="visual-bar-row" key={eventType}>
            <span>{prettyKey(eventType)}</span>
            <div className="visual-bar">
              <span style={{ width: `${(count / maxCount) * 100}%` }} />
            </div>
            <strong>{count}</strong>
          </div>
        ))}
      </div>
      <p className="meta-copy">
        This summarizes alert feed metadata only. It does not infer additional
        market change events.
      </p>
    </div>
  );
}

function UnsupportedVisualizationPanel({
  items,
  reason,
}: {
  items: string[];
  reason: string;
}) {
  return (
    <div className="unsupported-visualization">
      <div className="visualization-header">
        <strong>Unsupported visualization state</strong>
        <span className="badge badge-warning">Disabled</span>
      </div>
      <p className="meta-copy">{reason}</p>
      <div className="chip-row">
        {items.map((item) => (
          <span className="badge badge-unknown" key={item}>{item}</span>
        ))}
      </div>
    </div>
  );
}

function ExplanationResultPanel({
  state,
  emptyCopy,
}: {
  state?: LoadState<ExplanationResult>;
  emptyCopy: string;
}) {
  if (state?.loading) return <LoadingBlock label="Rendering structured guidance" />;
  if (state?.error) return <ErrorState message={state.error} />;
  const explanation = state?.envelope?.data;
  if (!explanation) {
    return <EmptyState title="No explanation yet" body={emptyCopy} />;
  }
  return (
    <div className="explanation-panel">
      <div className="metadata-row">
        <span className="badge">Structured guidance</span>
        <span className={explanation.status === "ok" ? "badge badge-success" : "badge badge-warning"}>
          {prettyKey(explanation.status)}
        </span>
        <span className="badge badge-unknown">{prettyKey(explanation.provider_mode)}</span>
      </div>
      {explanation.sections.map((section) => (
        <div className="explanation-section" key={section.section_type}>
          <strong>{section.title}</strong>
          <ul className="notes-list">
            {section.statements.map((statement) => (
              <li key={statement}>{statement}</li>
            ))}
          </ul>
        </div>
      ))}
      {explanation.limitations.length ? (
        <div className="warning-list">
          {explanation.limitations.map((limitation) => (
            <div className="warning-item" key={limitation}>
              <div className="warning-header">
                <span className="warning-code">Explanation boundary</span>
              </div>
              <p>{limitation}</p>
            </div>
          ))}
        </div>
      ) : null}
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
          imported, mixed, partial, stale, or unknown. Coverage labels separately show
          whether each market is fully covered, partial, watchlist, or placeholder.
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
          missing entry-level values are not converted into zeroes. Coverage is a separate
          readiness estimate and does not replace source or freshness evidence.
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
              const { coverage } = coverageForRegion(region, searchItem, detail);
              return (
                <button
                  className="market-card"
                  key={region.region_id}
                  type="button"
                  onClick={() => onSelectRegion(region.region_id)}
                >
                  <div className="market-card-topline">
                    <span>{prettyKey(region.region_type)}</span>
                    <CoverageBadge coverage={coverage} />
                    <QualityBadgeRow envelope={detailEnvelope} source={searchItem?.freshness} />
                  </div>
                  <strong>{region.display_name}</strong>
                  <small>
                    {region.region_id} · {region.labor_market_group ?? "unknown labor market"}
                  </small>
                  <CoverageInlineNote coverage={coverage} />
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

      <ShellCard title="Region expansion status" eyebrow="Operator workflow">
        <UnsupportedVisualizationPanel
          items={["Expansion workflow status visualization"]}
          reason="Region expansion workflow rows are operator/checklist state and are not exposed through a public frontend API in this batch."
        />
      </ShellCard>

      <div className="quick-region-grid">
        {filteredRegions.slice(0, 2).map((region) => {
          const detail = regionDetails[region.region_id]?.data;
          const searchItem = searchMap.get(region.region_id);
          const { coverage } = coverageForRegion(region, searchItem, detail);
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
              <CoverageBadge coverage={coverage} />
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
  canSavePersonalOverlays,
  canExplainGuidance,
  savedArtifactsByKey,
  explanationState,
  onSelectRegion,
  onSelectCompany,
  onCompareRegion,
  onSaveRegion,
  onSaveRoleFamily,
  onRemoveSavedArtifact,
  onExplainRegion,
}: {
  regions: RegionListItem[];
  selectedRegionId: string;
  regionState: LoadState<RegionDetail>;
  sourceState: LoadState<SourceExplanation>;
  roleFamilyState: LoadState<CompanySearchResponse>;
  canSavePersonalOverlays: boolean;
  canExplainGuidance: boolean;
  savedArtifactsByKey: Map<string, SavedMarketArtifact>;
  explanationState?: LoadState<ExplanationResult>;
  onSelectRegion: (regionId: string) => void;
  onSelectCompany: (companyId: string) => void;
  onCompareRegion: (regionId: string) => void;
  onSaveRegion: (region: RegionDetail) => void;
  onSaveRoleFamily: (roleFamily: string) => void;
  onRemoveSavedArtifact: (savedArtifactId: string) => void;
  onExplainRegion: (region: RegionDetail) => void;
}) {
  const region = regionState.envelope?.data;
  const hasSelectedRegion = regions.some((item) => item.region_id === selectedRegionId);
  const source = sourceState.envelope?.data;
  const roleCounts = roleFamilyCounts(roleFamilyState.envelope?.data);
  const entrySummary = region?.entry_level_summary ?? {};
  const savedRegionArtifact = savedArtifactsByKey.get(savedArtifactKey("region", selectedRegionId));

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
          <div className="toolbar-actions">
            <button
              className="secondary-button toolbar-button"
              disabled={!region}
              onClick={() => onCompareRegion(selectedRegionId)}
              type="button"
            >
              Compare this market
            </button>
            <button
              className="secondary-button toolbar-button"
              disabled={!region || !canSavePersonalOverlays}
              onClick={() => {
                if (savedRegionArtifact) {
                  onRemoveSavedArtifact(savedRegionArtifact.saved_artifact_id);
                } else if (region) {
                  onSaveRegion(region);
                }
              }}
              type="button"
            >
              {savedRegionArtifact ? "Remove region" : canSavePersonalOverlays ? "Save region" : "Sign in to save"}
            </button>
            <button
              className="secondary-button toolbar-button"
              disabled={!region || !canExplainGuidance}
              onClick={() => {
                if (region) onExplainRegion(region);
              }}
              type="button"
            >
              {canExplainGuidance ? "Explain guidance" : "Sign in to explain"}
            </button>
          </div>
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
              <div className="detail-side-panels">
                <CoveragePanel coverage={region.coverage} sectorCoverage={region.sector_coverage} />
                <MetadataPanel envelope={regionState.envelope} source={source} />
              </div>
            </div>
            <StatGrid values={region.summary ?? {}} />
          </ShellCard>

          <ShellCard title="Derived market scores" eyebrow="Interpretation">
            <p className="meta-copy">
              These scores are derived from stored scoring fields. They are not a claim of
              complete market coverage or real-time hiring certainty.
            </p>
            <ScoreBreakdownChart scores={region.scores} />
            <RegionScoreGrid scores={region.scores} />
          </ShellCard>

          <ShellCard title="Structured guidance" eyebrow="Evidence packet explanation">
            <p className="meta-copy">
              Guidance is generated from returned structured fields only. It is not source
              data and is not stored as market truth.
            </p>
            <ExplanationResultPanel
              emptyCopy="Use Explain guidance to render a constrained explanation from this region output."
              state={explanationState}
            />
          </ShellCard>

          <ShellCard title="Deferred visualizations" eyebrow="No unsupported precision">
            <UnsupportedVisualizationPanel
              items={[
                "Historical trend view",
                "Map",
                "Opportunity heatmap",
                "Company-region network graph",
              ]}
              reason="The current region response does not include historical snapshots, map geometry, heatmap cells, or network layout coordinates."
            />
          </ShellCard>

          <div className="split-grid">
            <ShellCard title="Companies present" eyebrow="Presence facts">
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
                  {roleCounts.map((item) => {
                    const savedRoleArtifact = savedArtifactsByKey.get(
                      savedArtifactKey("role_family", item.role),
                    );
                    return (
                      <div className="signal-row" key={item.role}>
                        <span>{prettyKey(item.role)}</span>
                        <strong>{item.count} company signal(s)</strong>
                        <button
                          className="secondary-button"
                          disabled={!canSavePersonalOverlays}
                          type="button"
                          onClick={() => {
                            if (savedRoleArtifact) {
                              onRemoveSavedArtifact(savedRoleArtifact.saved_artifact_id);
                            } else {
                              onSaveRoleFamily(item.role);
                            }
                          }}
                        >
                          {savedRoleArtifact ? "Remove" : canSavePersonalOverlays ? "Save" : "Sign in"}
                        </button>
                      </div>
                    );
                  })}
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
  canSavePersonalOverlays,
  canExplainGuidance,
  savedCompanyArtifact,
  explanationState,
  onSelectCompany,
  onSaveCompany,
  onRemoveSavedArtifact,
  onExplainCompany,
}: {
  companyOptions: CompanyOption[];
  selectedCompanyId: string;
  companyState: LoadState<CompanyDetail>;
  geographyState: LoadState<CompanyGeographyResponse>;
  sourceState: LoadState<SourceExplanation>;
  canSavePersonalOverlays: boolean;
  canExplainGuidance: boolean;
  savedCompanyArtifact?: SavedMarketArtifact;
  explanationState?: LoadState<ExplanationResult>;
  onSelectCompany: (companyId: string) => void;
  onSaveCompany: (company: CompanyDetail) => void;
  onRemoveSavedArtifact: (savedArtifactId: string) => void;
  onExplainCompany: (company: CompanyDetail) => void;
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
          <div className="toolbar-actions">
            <button
              className="secondary-button toolbar-button"
              disabled={!company || !canSavePersonalOverlays}
              onClick={() => {
                if (savedCompanyArtifact) {
                  onRemoveSavedArtifact(savedCompanyArtifact.saved_artifact_id);
                } else if (company) {
                  onSaveCompany(company);
                }
              }}
              type="button"
            >
              {savedCompanyArtifact ? "Remove company" : canSavePersonalOverlays ? "Save company" : "Sign in to save"}
            </button>
            <button
              className="secondary-button toolbar-button"
              disabled={!company || !canExplainGuidance}
              onClick={() => {
                if (company) onExplainCompany(company);
              }}
              type="button"
            >
              {canExplainGuidance ? "Explain guidance" : "Sign in to explain"}
            </button>
          </div>
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

          <ShellCard title="Observed region signals" eyebrow="Derived from visible geography rows">
            <p className="meta-copy">
              This section counts distinct observed signals: presence, hiring activity, and
              entry-level access. It is not a comprehensive ranking of all possible markets.
              Coverage labels describe each region's readiness separately from source freshness.
            </p>
            {geographyState.loading ? <LoadingBlock label="Loading geography source summaries" /> : null}
            {strongestRegions.length ? (
              <div className="market-card-grid">
                {strongestRegions.map((region) => (
                  <div className="market-card market-card-static" key={region.regionId}>
                    <div className="market-card-topline">
                      <span>{region.signalCount} observed signal(s)</span>
                      <CoverageBadge coverage={region.coverage} />
                      {region.freshness ? <QualityBadgeRow source={region.freshness} /> : null}
                    </div>
                    <strong>{region.regionName}</strong>
                    <small>{region.regionId}</small>
                    <CoverageInlineNote coverage={region.coverage} />
                    <div className="chip-row">
                      {region.signals.map((signal) => (
                        <span className="badge" key={signal}>{signal}</span>
                      ))}
                    </div>
                    <SectorCoveragePanel sectorCoverage={region.sectorCoverage} />
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

          <ShellCard title="Structured guidance" eyebrow="Evidence packet explanation">
            <p className="meta-copy">
              Guidance summarizes returned company fields and source labels only. It does
              not infer unobserved presence or hiring.
            </p>
            <ExplanationResultPanel
              emptyCopy="Use Explain guidance to render a constrained explanation from this company output."
              state={explanationState}
            />
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
                      <CoverageBadge coverage={region.coverage} />
                      <CoverageInlineNote coverage={region.coverage} />
                      <span>
                        {formatValue(region.presence_basis)} · {formatValue(region.presence_confidence)}
                      </span>
                      <span className={qualityBadgeClass(confidenceTone(region.presence_confidence))}>
                        Confidence: {formatValue(region.presence_confidence)}
                      </span>
                      <SectorCoveragePanel sectorCoverage={region.sector_coverage} />
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
                      <CoverageBadge coverage={region.coverage} />
                      <CoverageInlineNote coverage={region.coverage} />
                      <span>
                        {formatValue(region.active_posting_count_now)} active ·{" "}
                        {formatValue(region.posting_count_90d)} in 90d
                      </span>
                      <span className={region.currently_hiring_flag ? "badge badge-fresh" : "badge badge-unknown"}>
                        Currently hiring: {formatValue(region.currently_hiring_flag)}
                      </span>
                      <SectorCoveragePanel sectorCoverage={region.sector_coverage} />
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
                    <CoverageBadge coverage={region.coverage} />
                    <CoverageInlineNote coverage={region.coverage} />
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
                    <SectorCoveragePanel sectorCoverage={region.sector_coverage} />
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
  canSavePersonalOverlays,
  canExplainGuidance,
  savedComparisonArtifact,
  explanationState,
  onRegionA,
  onRegionB,
  onSaveComparison,
  onRemoveSavedArtifact,
  onExplainComparison,
}: {
  regions: RegionListItem[];
  regionA: string;
  regionB: string;
  comparisonState: LoadState<ComparisonDetail>;
  sourceAState: LoadState<SourceExplanation>;
  sourceBState: LoadState<SourceExplanation>;
  validationError?: string | null;
  canSavePersonalOverlays: boolean;
  canExplainGuidance: boolean;
  savedComparisonArtifact?: SavedMarketArtifact;
  explanationState?: LoadState<ExplanationResult>;
  onRegionA: (regionId: string) => void;
  onRegionB: (regionId: string) => void;
  onSaveComparison: (comparison: ComparisonDetail, label: string) => void;
  onRemoveSavedArtifact: (savedArtifactId: string) => void;
  onExplainComparison: (comparison: ComparisonDetail) => void;
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
        <div className="account-inline-actions">
          <button
            className="secondary-button"
            disabled={!comparison || !canSavePersonalOverlays}
            onClick={() => {
              if (savedComparisonArtifact) {
                onRemoveSavedArtifact(savedComparisonArtifact.saved_artifact_id);
              } else if (comparison) {
                onSaveComparison(comparison, `${regionALabel} vs ${regionBLabel}`);
              }
            }}
            type="button"
          >
            {savedComparisonArtifact ? "Remove comparison" : canSavePersonalOverlays ? "Save comparison" : "Sign in to save"}
          </button>
          <button
            className="secondary-button"
            disabled={!comparison || !canExplainGuidance}
            onClick={() => {
              if (comparison) onExplainComparison(comparison);
            }}
            type="button"
          >
            {canExplainGuidance ? "Explain guidance" : "Sign in to explain"}
          </button>
        </div>

        {regionA === regionB ? (
          <ErrorState message="Choose two distinct regions before running comparison." />
        ) : null}
        {validationError && regionA !== regionB ? <ErrorState message={validationError} /> : null}
        {comparisonState.loading ? <LoadingBlock label="Loading comparison output" /> : null}
        {comparisonState.error ? <ErrorState message={comparisonState.error} /> : null}
        <p className="meta-copy">
          The comparison uses returned score fields only. Missing values are shown as
          unavailable and are not treated as zero. Coverage warnings identify markets
          that should not be treated as confident recommendations.
        </p>
        <CoverageWarningList warnings={pickEnvelopeWarnings(comparisonState.envelope)} />
      </ShellCard>

      {comparison ? (
        <>
          <ShellCard title="Coverage context" eyebrow="Comparison readiness">
            <div className="source-compare-grid">
              <div className="source-compare-card">
                <strong>{regionALabel}</strong>
                <CoveragePanel
                  coverage={comparison.region_a?.coverage}
                  sectorCoverage={comparison.region_a?.sector_coverage}
                />
              </div>
              <div className="source-compare-card">
                <strong>{regionBLabel}</strong>
                <CoveragePanel
                  coverage={comparison.region_b?.coverage}
                  sectorCoverage={comparison.region_b?.sector_coverage}
                />
              </div>
            </div>
          </ShellCard>

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
            <ComparisonScoreChart
              comparison={comparison}
              regionALabel={regionALabel}
              regionBLabel={regionBLabel}
            />
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

          <ShellCard title="Structured guidance" eyebrow="Evidence packet explanation">
            <p className="meta-copy">
              Guidance summarizes returned comparison fields only. Missing score values
              remain missing.
            </p>
            <ExplanationResultPanel
              emptyCopy="Use Explain guidance to render a constrained explanation from this comparison output."
              state={explanationState}
            />
          </ShellCard>

          <ShellCard title="Deferred visualizations" eyebrow="No unsupported precision">
            <UnsupportedVisualizationPanel
              items={["Trend view", "Map", "Heatmap"]}
              reason="The comparison response has current score fields only; it does not include historical snapshots or geographic precision."
            />
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
  canSavePersonalOverlays,
  onSaveDiscoveryResult,
  onSaveRecommendationSnapshot,
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
  canSavePersonalOverlays: boolean;
  onSaveDiscoveryResult: (discovery: PersonalizedResult) => void;
  onSaveRecommendationSnapshot: (discovery: PersonalizedResult) => void;
}) {
  const discovery = discoveryState.envelope?.data;
  const knownRegionIds = new Set(regions.map((region) => region.region_id));
  const unknownSelectedRegions = regions.length
    ? selectedRegions.filter((regionId) => !knownRegionIds.has(regionId))
    : [];
  const rankedRegions = discovery?.ranked_regions ?? [];
  const rankedCompanies = discovery?.ranked_companies ?? [];
  const rankedRegionCoverage = new Map(rankedRegions.map((region) => [region.region_id, region.coverage]));
  const regionListCoverage = new Map(regions.map((region) => [region.region_id, region.coverage]));

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
                <CoverageBadge coverage={region.coverage} />
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
        <CoverageWarningList warnings={pickEnvelopeWarnings(discoveryState.envelope)} />
        {discovery ? (
          <div className="account-inline-actions">
            <button
              className="secondary-button"
              disabled={!canSavePersonalOverlays}
              type="button"
              onClick={() => onSaveDiscoveryResult(discovery)}
            >
              {canSavePersonalOverlays ? "Save discovery result" : "Sign in to save result"}
            </button>
            <button
              className="secondary-button"
              disabled={!canSavePersonalOverlays}
              type="button"
              onClick={() => onSaveRecommendationSnapshot(discovery)}
            >
              {canSavePersonalOverlays ? "Save recommendation snapshot" : "Sign in to save snapshot"}
            </button>
          </div>
        ) : null}
      </ShellCard>

      {discovery ? (
        <div className="split-grid">
          <ShellCard title="Ranked regions" eyebrow="Exploratory market overlay">
            {rankedRegions.length ? (
              <div className="rank-list">
                {rankedRegions.map((region, index) => (
                  <div className="rank-row" key={region.region_id}>
                    <span className="rank-number">{index + 1}</span>
                    <div>
                      <strong>{region.display_name}</strong>
                      <CoverageBadge coverage={region.coverage} />
                      <CoverageInlineNote coverage={region.coverage} />
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
                title="No ranked regions"
                body="The personalization response returned no ranked region rows for this request."
              />
            )}
          </ShellCard>

          <ShellCard title="Ranked company-region pairs" eyebrow="Preference fit components">
            {rankedCompanies.length ? (
              <div className="rank-list">
                {rankedCompanies.map((company, index) => {
                  const coverage = rankedRegionCoverage.get(company.region_id) ?? regionListCoverage.get(company.region_id);
                  return (
                    <div className="rank-row rank-row-company" key={`${company.company_id}-${company.region_id}`}>
                      <span className="rank-number">{index + 1}</span>
                      <div>
                        <strong>{company.company_name}</strong>
                        <CoverageBadge coverage={coverage} />
                        <CoverageInlineNote coverage={coverage} />
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
                  );
                })}
              </div>
            ) : (
              <EmptyState
                title="No ranked companies"
                body="The personalization response returned no ranked company-region rows for this request."
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
  const auth = useFrontendAuth();
  const [route, setRoute] = useState<RouteState>(() => readCurrentRoute());
  const isProductRoute = isProductPage(route.page);
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
  const [currentUserState, setCurrentUserState] = useState<LoadState<CurrentUserProfile>>(emptyLoadState);
  const [preferenceState, setPreferenceState] = useState<LoadState<UserPreferenceProfile>>(emptyLoadState);
  const [preferenceDraft, setPreferenceDraft] = useState<PreferenceDraft>(() => emptyPreferenceDraft());
  const [artifactsState, setArtifactsState] = useState<LoadState<{ saved_market_artifacts: SavedMarketArtifact[] }>>(emptyLoadState);
  const [alertsState, setAlertsState] = useState<LoadState<UserAlertList>>(emptyLoadState);
  const [snapshotsState, setSnapshotsState] = useState<LoadState<{ personalized_recommendation_snapshots: PersonalizedRecommendationSnapshot[] }>>(emptyLoadState);
  const [scoringPreviewState, setScoringPreviewState] = useState<LoadState<ScoringPreviewResult>>(emptyLoadState);
  const [explanationStates, setExplanationStates] = useState<Record<string, LoadState<ExplanationResult>>>({});
  const [exportState, setExportState] = useState<LoadState<UserDataExport>>(emptyLoadState);
  const [deactivationResult, setDeactivationResult] = useState<AccountDeactivationResult | null>(null);
  const [accountAction, setAccountAction] = useState<AccountActionState>({ loading: false, message: null, error: null });
  const [deactivateConfirmed, setDeactivateConfirmed] = useState(false);
  const [accountDeactivated, setAccountDeactivated] = useState(false);
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
  const protectedOptions = useMemo<ProtectedRequestOptions>(
    () => ({ getAccessToken: auth.getAccessTokenSilently }),
    [auth.getAccessTokenSilently],
  );
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
  const savedArtifactRefs = useMemo(() => {
    const refs = new Set<string>();
    for (const artifact of artifactsState.envelope?.data?.saved_market_artifacts ?? []) {
      refs.add(savedArtifactKey(artifact.artifact_type, artifact.artifact_ref));
    }
    return refs;
  }, [artifactsState.envelope]);
  const savedArtifactByKey = useMemo(() => {
    const refs = new Map<string, SavedMarketArtifact>();
    for (const artifact of artifactsState.envelope?.data?.saved_market_artifacts ?? []) {
      refs.set(savedArtifactKey(artifact.artifact_type, artifact.artifact_ref), artifact);
    }
    return refs;
  }, [artifactsState.envelope]);
  const comparisonArtifactRef = comparisonState.envelope?.data?.comparison_id
    ?? canonicalComparisonRef(comparisonA, comparisonB);
  const canSavePersonalOverlays = auth.isConfigured && auth.isAuthenticated && !accountDeactivated;
  const canExplainGuidance = canSavePersonalOverlays;
  const regionSourceIdsNeeded = useMemo(() => {
    const ids: string[] = [];
    if (isProductRoute && selectedRegionId && selectedRegionIsKnown) ids.push(selectedRegionId);
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
    isProductRoute,
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

  const resetAccountState = useCallback(() => {
    setCurrentUserState(emptyLoadState());
    setPreferenceState(emptyLoadState());
    setPreferenceDraft(emptyPreferenceDraft());
    setArtifactsState(emptyLoadState());
    setAlertsState(emptyLoadState());
    setSnapshotsState(emptyLoadState());
    setScoringPreviewState(emptyLoadState());
    setExplanationStates({});
    setExportState(emptyLoadState());
    setDeactivationResult(null);
    setDeactivateConfirmed(false);
  }, []);

  const loadAccountData = useCallback(async () => {
    if (!auth.isAuthenticated || accountDeactivated) return;

    setCurrentUserState((current) => ({ ...current, loading: true, error: null }));
    setPreferenceState((current) => ({ ...current, loading: true, error: null }));
    setArtifactsState((current) => ({ ...current, loading: true, error: null }));
    setAlertsState((current) => ({ ...current, loading: true, error: null }));
    setSnapshotsState((current) => ({ ...current, loading: true, error: null }));

    const [userResult, preferenceResult, artifactResult, alertResult, snapshotResult] = await Promise.allSettled([
      getCurrentUser(protectedOptions),
      getPreferences(protectedOptions),
      listSavedMarketArtifacts(protectedOptions),
      listAlerts(protectedOptions),
      listRecommendationSnapshots(protectedOptions),
    ]);

    if (userResult.status === "fulfilled") {
      setCurrentUserState({ loading: false, envelope: userResult.value, error: null });
    } else {
      setCurrentUserState({
        loading: false,
        envelope: null,
        error: userResult.reason instanceof Error ? userResult.reason.message : "Failed to load account",
      });
    }

    if (preferenceResult.status === "fulfilled") {
      setPreferenceState({ loading: false, envelope: preferenceResult.value, error: null });
      setPreferenceDraft(preferenceDraftFromProfile(preferenceResult.value.data));
    } else {
      setPreferenceState({
        loading: false,
        envelope: null,
        error: preferenceResult.reason instanceof Error ? preferenceResult.reason.message : "Failed to load preferences",
      });
    }

    if (artifactResult.status === "fulfilled") {
      setArtifactsState({ loading: false, envelope: artifactResult.value, error: null });
    } else {
      setArtifactsState({
        loading: false,
        envelope: null,
        error: artifactResult.reason instanceof Error ? artifactResult.reason.message : "Failed to load saved artifacts",
      });
    }

    if (alertResult.status === "fulfilled") {
      setAlertsState({ loading: false, envelope: alertResult.value, error: null });
    } else {
      setAlertsState({
        loading: false,
        envelope: null,
        error: alertResult.reason instanceof Error ? alertResult.reason.message : "Failed to load alerts",
      });
    }

    if (snapshotResult.status === "fulfilled") {
      setSnapshotsState({ loading: false, envelope: snapshotResult.value, error: null });
    } else {
      setSnapshotsState({
        loading: false,
        envelope: null,
        error: snapshotResult.reason instanceof Error ? snapshotResult.reason.message : "Failed to load snapshots",
      });
    }
  }, [accountDeactivated, auth.isAuthenticated, protectedOptions]);

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
    if (!auth.isAuthenticated) {
      resetAccountState();
      setAccountDeactivated(false);
      return;
    }
    void loadAccountData();
  }, [auth.isAuthenticated, loadAccountData, resetAccountState]);

  useEffect(() => {
    if (!isProductRoute) return;

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
  }, [isProductRoute, loadRegion]);

  useEffect(() => {
    if (!isProductRoute) return;

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
  }, [isProductRoute]);

  useEffect(() => {
    if (!isProductRoute) return;
    if (
      !selectedRegionId
      || !selectedRegionIsKnown
      || regionDetails[selectedRegionId]
      || regionLoading[selectedRegionId]
    ) {
      return;
    }
    void loadRegion(selectedRegionId);
  }, [isProductRoute, loadRegion, regionDetails, regionLoading, selectedRegionId, selectedRegionIsKnown]);

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
    if (!isProductRoute) return;
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
  }, [isProductRoute, regionCompanySearchStates, selectedRegionId, selectedRegionIsKnown]);

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
    if (!isProductRoute) {
      setCompanyState(emptyLoadState());
      return;
    }

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
  }, [isProductRoute, selectedCompanyId]);

  useEffect(() => {
    if (!isProductRoute) return;
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
  }, [companySourceStates, isProductRoute, selectedCompanyId]);

  useEffect(() => {
    if (!isProductRoute) return;
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
  }, [companyGeographyStates, isProductRoute, selectedCompanyId]);

  useEffect(() => {
    if (!isProductRoute) return;
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
  }, [comparisonA, comparisonB, comparisonValidationError, isProductRoute]);

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

  async function handleSaveArtifact(input: SavedMarketArtifactInput, successMessage: string) {
    if (!canSavePersonalOverlays) {
      setAccountAction({ loading: false, message: "Sign in to save personal overlays.", error: null });
      return;
    }
    if (savedArtifactRefs.has(savedArtifactKey(input.artifact_type, input.artifact_ref))) {
      setAccountAction({ loading: false, message: "This artifact is already saved for your account.", error: null });
      return;
    }

    setAccountAction({ loading: true, message: null, error: null });
    try {
      await createSavedMarketArtifact(input, protectedOptions);
      await loadAccountData();
      setAccountAction({ loading: false, message: successMessage, error: null });
    } catch (error) {
      setAccountAction({
        loading: false,
        message: null,
        error: error instanceof Error ? error.message : "Failed to save artifact",
      });
    }
  }

  function handleSaveRegion(region: RegionDetail) {
    void handleSaveArtifact(
      {
        artifact_type: "region",
        artifact_ref: region.region_id,
        label: region.display_name,
        snapshot: {
          ref_kind: "canonical_region_id",
          saved_from: "region_detail",
        },
      },
      "Region saved to your watchlist.",
    );
  }

  function handleSaveCompany(company: CompanyDetail) {
    void handleSaveArtifact(
      {
        artifact_type: "company",
        artifact_ref: company.company_id,
        label: company.company_name,
        snapshot: {
          ref_kind: "canonical_company_id",
          saved_from: "company_geography",
        },
      },
      "Company saved to your watchlist.",
    );
  }

  function handleSaveRoleFamily(roleFamily: string) {
    void handleSaveArtifact(
      {
        artifact_type: "role_family",
        artifact_ref: roleFamily,
        label: prettyKey(roleFamily),
        snapshot: {
          ref_kind: "role_family_key",
          saved_from: "region_role_family",
        },
      },
      "Role family saved to your watchlist.",
    );
  }

  function handleSaveComparison(comparison: ComparisonDetail, label: string) {
    void handleSaveArtifact(
      {
        artifact_type: "comparison",
        artifact_ref: comparison.comparison_id ?? comparisonArtifactRef,
        label,
        snapshot: {
          ref_kind: "canonical_comparison_set",
          region_ids: [
            comparison.region_a?.region_id,
            comparison.region_b?.region_id,
          ].filter(Boolean),
          saved_from: "compare_markets",
        },
      },
      "Comparison set saved to your watchlist.",
    );
  }

  function discoveryObjectiveRefs(discovery: PersonalizedResult): Array<Record<string, unknown>> {
    return [
      ...(discovery.ranked_regions ?? []).map((region) => ({
        output_type: "region",
        subject_id: region.region_id,
      })),
      ...(discovery.ranked_companies ?? []).map((company) => ({
        output_type: "company_region",
        company_id: company.company_id,
        region_id: company.region_id,
      })),
    ];
  }

  function handleSaveDiscoveryResult(discovery: PersonalizedResult) {
    void (async () => {
      const refs = discoveryObjectiveRefs(discovery);
      const hash = await sha256Label({ discoveryFilters, refs });
      await handleSaveArtifact(
        {
          artifact_type: "discovery_result",
          artifact_ref: `discovery:${hash.slice(7, 39)}`,
          label: `Discovery result ${formatDateTime(new Date().toISOString())}`,
          snapshot: {
            filters: discoveryFilters,
            objective_output_refs: refs,
            saved_from: "personalized_discovery",
          },
        },
        "Discovery result saved to your account overlays.",
      );
    })();
  }

  function handleSaveRecommendationSnapshot(discovery: PersonalizedResult) {
    void (async () => {
      if (!canSavePersonalOverlays) {
        setAccountAction({ loading: false, message: "Sign in to save recommendation snapshots.", error: null });
        return;
      }
      const refs = discoveryObjectiveRefs(discovery);
      const sourceVersionBundle = discoveryState.envelope?.metadata.source_versions ?? {};
      const recommendationInputsHash = await sha256Label({
        discoveryFilters,
        refs,
        sourceVersionBundle,
      });
      const preferenceProfile = preferenceState.envelope?.data;
      const snapshot: PersonalizedRecommendationSnapshotInput = {
        preference_profile_id: preferenceProfile?.persisted ? preferenceProfile.user_id : null,
        personalized_output: { ...discovery } as Record<string, unknown>,
        recommendation_version: "frontend_discovery_snapshot_v1",
        source_version_bundle: sourceVersionBundle,
        objective_output_refs: refs,
        recommendation_inputs_hash: recommendationInputsHash,
        generated_at: new Date().toISOString(),
      };

      setAccountAction({ loading: true, message: null, error: null });
      try {
        await createRecommendationSnapshot(snapshot, protectedOptions);
        await loadAccountData();
        setAccountAction({ loading: false, message: "Recommendation snapshot saved.", error: null });
      } catch (error) {
        setAccountAction({
          loading: false,
          message: null,
          error: error instanceof Error ? error.message : "Failed to save recommendation snapshot",
        });
      }
    })();
  }

  function handleSavePreferences() {
    void (async () => {
      setAccountAction({ loading: true, message: null, error: null });
      try {
        const envelope = await updatePreferences(preferenceInputFromDraft(preferenceDraft), protectedOptions);
        setPreferenceState({ loading: false, envelope, error: null });
        setPreferenceDraft(preferenceDraftFromProfile(envelope.data));
        setAccountAction({ loading: false, message: "Preferences saved.", error: null });
      } catch (error) {
        setAccountAction({
          loading: false,
          message: null,
          error: error instanceof Error ? error.message : "Failed to save preferences",
        });
      }
    })();
  }

  function handlePreviewScoring() {
    void (async () => {
      if (!canSavePersonalOverlays) {
        setAccountAction({ loading: false, message: "Sign in to preview scoring overlays.", error: null });
        return;
      }
      const preferredRegionIds = splitDraftList(preferenceDraft.preferredRegions);
      const fallbackRegionIds = regionList.slice(0, 2).map((region) => region.region_id);
      const regionIds = preferredRegionIds.length
        ? preferredRegionIds
        : fallbackRegionIds.length
          ? fallbackRegionIds
          : [selectedRegionId].filter(Boolean);

      setScoringPreviewState((current) => ({ ...current, loading: true, error: null }));
      try {
        const envelope = await previewScoringOverlay(
          {
            region_ids: regionIds,
            role_interests: splitDraftList(preferenceDraft.roleInterests),
            industry_interests: splitDraftList(preferenceDraft.industryInterests),
            scoring_weights: normalizeScoringWeights(preferenceDraft.scoringWeights),
          },
          protectedOptions,
        );
        setScoringPreviewState({ loading: false, envelope, error: null });
        setAccountAction({ loading: false, message: "Scoring preview updated.", error: null });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to preview scoring overlay";
        setScoringPreviewState({ loading: false, envelope: null, error: message });
        setAccountAction({ loading: false, message: null, error: message });
      }
    })();
  }

  function handleDeletePreferences() {
    void (async () => {
      setAccountAction({ loading: true, message: null, error: null });
      try {
        await deletePreferences(protectedOptions);
        const envelope = await getPreferences(protectedOptions);
        setPreferenceState({ loading: false, envelope, error: null });
        setPreferenceDraft(preferenceDraftFromProfile(envelope.data));
        setAccountAction({ loading: false, message: "Preferences deleted.", error: null });
      } catch (error) {
        setAccountAction({
          loading: false,
          message: null,
          error: error instanceof Error ? error.message : "Failed to delete preferences",
        });
      }
    })();
  }

  function handleDeleteArtifact(savedArtifactId: string) {
    void (async () => {
      setAccountAction({ loading: true, message: null, error: null });
      try {
        await deleteSavedMarketArtifact(savedArtifactId, protectedOptions);
        await loadAccountData();
        setAccountAction({ loading: false, message: "Saved artifact deleted.", error: null });
      } catch (error) {
        setAccountAction({
          loading: false,
          message: null,
          error: error instanceof Error ? error.message : "Failed to delete saved artifact",
        });
      }
    })();
  }

  function handleMarkAlertRead(userAlertId: string) {
    void (async () => {
      setAccountAction({ loading: true, message: null, error: null });
      try {
        await markAlertRead(userAlertId, protectedOptions);
        const envelope = await listAlerts(protectedOptions);
        setAlertsState({ loading: false, envelope, error: null });
        setAccountAction({ loading: false, message: "Alert marked read.", error: null });
      } catch (error) {
        setAccountAction({
          loading: false,
          message: null,
          error: error instanceof Error ? error.message : "Failed to mark alert read",
        });
      }
    })();
  }

  function handleDismissAlert(userAlertId: string) {
    void (async () => {
      setAccountAction({ loading: true, message: null, error: null });
      try {
        await dismissAlert(userAlertId, protectedOptions);
        const envelope = await listAlerts(protectedOptions);
        setAlertsState({ loading: false, envelope, error: null });
        setAccountAction({ loading: false, message: "Alert dismissed.", error: null });
      } catch (error) {
        setAccountAction({
          loading: false,
          message: null,
          error: error instanceof Error ? error.message : "Failed to dismiss alert",
        });
      }
    })();
  }

  function runExplanation(
    key: string,
    request: { evidence: ExplanationEvidencePacket },
    endpoint: (
      body: { evidence: ExplanationEvidencePacket },
      authOptions: ProtectedRequestOptions,
    ) => Promise<ApiEnvelope<ExplanationResult>>,
  ) {
    void (async () => {
      if (!canExplainGuidance) {
        setAccountAction({ loading: false, message: "Sign in to render structured guidance.", error: null });
        return;
      }
      setExplanationStates((current) => ({
        ...current,
        [key]: { loading: true, envelope: current[key]?.envelope ?? null, error: null },
      }));
      try {
        const envelope = await endpoint(request, protectedOptions);
        setExplanationStates((current) => ({
          ...current,
          [key]: { loading: false, envelope, error: null },
        }));
        setAccountAction({ loading: false, message: "Structured guidance rendered.", error: null });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to render structured guidance";
        setExplanationStates((current) => ({
          ...current,
          [key]: { loading: false, envelope: null, error: message },
        }));
        setAccountAction({ loading: false, message: null, error: message });
      }
    })();
  }

  function handleExplainRegion(region: RegionDetail) {
    runExplanation(
      `region:${region.region_id}`,
      {
        evidence: regionExplanationEvidence(
          region,
          selectedRegionState.envelope,
          selectedRegionSourceState.envelope?.data ?? null,
        ),
      },
      explainRegion,
    );
  }

  function handleExplainCompany(company: CompanyDetail) {
    runExplanation(
      `company:${company.company_id}`,
      {
        evidence: companyExplanationEvidence(
          company,
          companyState.envelope,
          selectedCompanySourceState.envelope?.data ?? null,
        ),
      },
      explainCompany,
    );
  }

  function handleExplainComparison(comparison: ComparisonDetail) {
    runExplanation(
      `comparison:${comparison.comparison_id ?? comparisonArtifactRef}`,
      {
        evidence: comparisonExplanationEvidence(
          comparison,
          comparisonState.envelope,
          regionSourceStates[comparisonA]?.envelope?.data ?? null,
          regionSourceStates[comparisonB]?.envelope?.data ?? null,
        ),
      },
      explainComparison,
    );
  }

  function handleExplainAlert(alert: UserAlert) {
    runExplanation(
      `alert:${alert.user_alert_id}`,
      { evidence: alertExplanationEvidence(alert) },
      explainAlert,
    );
  }

  function handleExportUserData() {
    void (async () => {
      setExportState((current) => ({ ...current, loading: true, error: null }));
      setAccountAction({ loading: true, message: null, error: null });
      try {
        const envelope = await exportUserData(protectedOptions);
        setExportState({ loading: false, envelope, error: null });
        setAccountAction({ loading: false, message: "User-owned data export loaded.", error: null });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to export user data";
        setExportState({ loading: false, envelope: null, error: message });
        setAccountAction({ loading: false, message: null, error: message });
      }
    })();
  }

  function handleDeactivateAccount() {
    void (async () => {
      if (!deactivateConfirmed) return;
      setAccountAction({ loading: true, message: null, error: null });
      try {
        const envelope = await deactivateAccount(protectedOptions);
        setDeactivationResult(envelope.data);
        setAccountDeactivated(true);
        setCurrentUserState(emptyLoadState());
        setPreferenceState(emptyLoadState());
        setPreferenceDraft(emptyPreferenceDraft());
        setArtifactsState(emptyLoadState());
        setAlertsState(emptyLoadState());
        setSnapshotsState(emptyLoadState());
        setScoringPreviewState(emptyLoadState());
        setExplanationStates({});
        setExportState(emptyLoadState());
        setDeactivateConfirmed(false);
        setAccountAction({
          loading: false,
          message: "App account deactivated. Auth0 provider account deletion is not performed here.",
          error: null,
        });
      } catch (error) {
        setAccountAction({
          loading: false,
          message: null,
          error: error instanceof Error ? error.message : "Failed to deactivate account",
        });
      }
    })();
  }

  if (!isProductRoute) {
    return <PublicRouteView onNavigate={handleRouteLink} route={route} />;
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
        <AuthStatusPanel auth={auth} onOpenAccount={() => navigateTo(accountUrl())} />
        <PublicInfoLinks activePage={null} onNavigate={handleRouteLink} variant="sidebar" />
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

        <DemoDisclosure compact />

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
            canExplainGuidance={canExplainGuidance}
            canSavePersonalOverlays={canSavePersonalOverlays}
            explanationState={explanationStates[`region:${selectedRegionId}`]}
            onExplainRegion={handleExplainRegion}
            onCompareRegion={compareRegion}
            onRemoveSavedArtifact={handleDeleteArtifact}
            onSaveRegion={handleSaveRegion}
            onSaveRoleFamily={handleSaveRoleFamily}
            onSelectCompany={selectCompany}
            onSelectRegion={selectRegion}
            roleFamilyState={selectedRegionRoleFamilyState}
            regionState={selectedRegionState}
            regions={regionList}
            savedArtifactsByKey={savedArtifactByKey}
            selectedRegionId={selectedRegionId}
            sourceState={selectedRegionSourceState}
          />
        ) : null}

        {route.page === "company" ? (
          <CompanyExplorer
            canExplainGuidance={canExplainGuidance}
            canSavePersonalOverlays={canSavePersonalOverlays}
            companyOptions={companyOptions}
            companyState={companyState}
            explanationState={explanationStates[`company:${selectedCompanyId}`]}
            geographyState={selectedCompanyGeographyState}
            onExplainCompany={handleExplainCompany}
            onRemoveSavedArtifact={handleDeleteArtifact}
            onSaveCompany={handleSaveCompany}
            onSelectCompany={selectCompany}
            savedCompanyArtifact={savedArtifactByKey.get(savedArtifactKey("company", selectedCompanyId))}
            selectedCompanyId={selectedCompanyId}
            sourceState={selectedCompanySourceState}
          />
        ) : null}

        {route.page === "compare" ? (
          <ComparisonView
            canExplainGuidance={canExplainGuidance}
            canSavePersonalOverlays={canSavePersonalOverlays}
            comparisonState={comparisonState}
            explanationState={explanationStates[`comparison:${comparisonArtifactRef}`]}
            onExplainComparison={handleExplainComparison}
            savedComparisonArtifact={savedArtifactByKey.get(savedArtifactKey("comparison", comparisonArtifactRef))}
            onRemoveSavedArtifact={handleDeleteArtifact}
            onRegionA={selectComparisonA}
            onRegionB={selectComparisonB}
            onSaveComparison={handleSaveComparison}
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
            canSavePersonalOverlays={canSavePersonalOverlays}
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
            onSaveDiscoveryResult={handleSaveDiscoveryResult}
            onSaveRecommendationSnapshot={handleSaveRecommendationSnapshot}
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

        {route.page === "account" ? (
          <AccountView
            actionState={accountAction}
            alertExplanationStates={Object.fromEntries(
              Object.entries(explanationStates)
                .filter(([key]) => key.startsWith("alert:"))
                .map(([key, value]) => [key.slice("alert:".length), value]),
            )}
            alertsState={alertsState}
            artifactsState={artifactsState}
            auth={auth}
            currentUserState={currentUserState}
            deactivateConfirmed={deactivateConfirmed}
            deactivationResult={deactivationResult}
            exportState={exportState}
            onDeactivate={handleDeactivateAccount}
            onDeactivateConfirmed={setDeactivateConfirmed}
            onDeleteArtifact={handleDeleteArtifact}
            onDeletePreferences={handleDeletePreferences}
            onDismissAlert={handleDismissAlert}
            onExplainAlert={handleExplainAlert}
            onExport={handleExportUserData}
            onLogin={() => void auth.login()}
            onMarkAlertRead={handleMarkAlertRead}
            onPreferenceDraft={setPreferenceDraft}
            onPreviewScoring={handlePreviewScoring}
            onRefresh={() => void loadAccountData()}
            onSavePreferences={handleSavePreferences}
            preferenceDraft={preferenceDraft}
            preferenceState={preferenceState}
            scoringPreviewState={scoringPreviewState}
            snapshotsState={snapshotsState}
          />
        ) : null}

        <PublicFooter activePage={null} onNavigate={handleRouteLink} />
      </section>
    </main>
  );
}

export default App;
