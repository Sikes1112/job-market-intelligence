export type ApiEnvelope<T> = {
  status: "success" | "partial" | "error";
  data: T | null;
  metadata: {
    state: string;
    freshness?: {
      last_updated_at: string | null;
      freshness_expires_at: string | null;
      is_stale: boolean;
      freshness_status?: FreshnessStatus;
    };
    source_versions?: Record<string, unknown>;
    warnings?: WarningItem[];
  };
  error: { code?: string; type?: string; message: string; request_id?: string } | null;
};

export type FreshnessStatus = "fresh" | "stale" | "partial" | "unknown" | "seeded_demo";

export type DataBasis = "seeded_demo" | "real_imported" | "mixed" | "unknown";

export type FreshnessSourceSummary = {
  freshness_status: FreshnessStatus;
  data_basis: DataBasis;
  last_collected_at: string | null;
  source_count: number;
  low_confidence_warning: string | null;
};

export type WarningRecord = {
  warning_code?: unknown;
  code?: unknown;
  severity?: unknown;
  message?: unknown;
  scope_type?: unknown;
  scope_ref?: unknown;
  [key: string]: unknown;
};

export type WarningItem = string | WarningRecord;

export type CoverageTier = "tier_1" | "tier_2" | "tier_3" | "tier_4";

export type CoverageScoreComponent =
  | "company_coverage"
  | "hiring_coverage"
  | "entry_level_coverage"
  | "freshness"
  | "source_diversity"
  | "confidence";

export type CoverageComponents = Partial<Record<CoverageScoreComponent, number>> & Record<string, number | undefined>;

export type CoverageMetadata = {
  tier: CoverageTier | string;
  label?: string | null;
  quality_score?: number | null;
  components?: CoverageComponents;
  notes?: string[];
  heuristic?: boolean;
  safe_for_confident_market_comparison?: boolean;
  should_rank_as_confident_recommendation?: boolean;
};

export type SectorCoverageMetadata = {
  sector: string;
  label?: string | null;
  coverage: CoverageMetadata;
};

export type SectorCoverageMap = Record<string, SectorCoverageMetadata>;

export type RegionListItem = {
  region_id: string;
  display_name: string;
  region_type: string;
  parent_region_id: string | null;
  labor_market_group: string | null;
  state: string;
  version?: number;
  coverage?: CoverageMetadata;
  sector_coverage?: SectorCoverageMap;
};

export type RegionSearchResult = {
  region_id: string;
  name: string;
  region_name: string;
  region_type: string;
  parent_region_id: string | null;
  labor_market_group: string | null;
  opportunity_score: number | null;
  coverage?: CoverageMetadata;
  sector_coverage?: SectorCoverageMap;
  freshness: FreshnessSourceSummary;
  has_real_data: boolean;
};

export type RegionSearchResponse = {
  regions?: RegionSearchResult[];
  count?: number;
};

export type RegionScores = {
  structural_ecosystem_score: number | null;
  live_market_score: number | null;
  objective_opportunity_score: number | null;
  raw_total_score: number | null;
  general_density_score: number | null;
  tech_market_density_score: number | null;
  early_career_accessibility_score: number | null;
  score_ruleset_version?: string | null;
};

export type RegionCompany = {
  company_id: string;
  company_name: string;
  sector_primary: string | null;
  eligibility_status: string | null;
  is_major_tech: boolean;
  is_mag7: boolean;
  prestige_score: number | null;
};

export type HiringCompany = {
  company_id: string;
  company_name: string;
  currently_hiring_flag: boolean;
  active_posting_count_now: number | null;
  posting_count_30d: number | null;
  posting_count_90d: number | null;
};

export type RegionDetail = {
  region_id: string;
  display_name: string;
  region_type: string;
  parent_region_id: string | null;
  labor_market_group: string | null;
  coverage?: CoverageMetadata;
  sector_coverage?: SectorCoverageMap;
  summary?: Record<string, number>;
  scores: RegionScores | null;
  top_companies_present?: RegionCompany[];
  top_companies_hiring?: HiringCompany[];
  entry_level_summary?: Record<string, number | null>;
  major_tech_summary?: { count: number; company_ids: string[] };
  mag7_summary?: { count: number; company_ids: string[] };
};

export type CompanyDetail = {
  company_id: string;
  company_name: string;
  normalized_company_name: string;
  sector_primary: string | null;
  sector_secondary: string | null;
  eligibility_status: string;
  eligibility_override_flag: boolean;
  classification_confidence: string | null;
  is_major_tech: boolean;
  is_mag7: boolean;
  prestige_score: number | null;
  regions_present?: Array<{
    region_id: string;
    region_display_name: string;
    presence_status: string;
    presence_basis: string | null;
    presence_confidence: string | null;
    coverage?: CoverageMetadata;
    sector_coverage?: SectorCoverageMap;
  }>;
  regions_hiring?: Array<{
    region_id: string;
    region_display_name: string;
    currently_hiring_flag: boolean;
    active_posting_count_now: number | null;
    posting_count_30d: number | null;
    posting_count_90d: number | null;
    coverage?: CoverageMetadata;
    sector_coverage?: SectorCoverageMap;
  }>;
  entry_level_regions?: Array<{
    region_id: string;
    region_display_name: string;
    internship_count: number | null;
    coop_count: number | null;
    entry_level_full_time_count: number | null;
    formal_early_career_program_flag: boolean;
    entry_level_access_score: number | null;
    entry_level_confidence: string | null;
    coverage?: CoverageMetadata;
    sector_coverage?: SectorCoverageMap;
  }>;
};

export type CompanySearchResult = {
  company_id: string;
  name: string;
  sector: string | null;
  industry: string | null;
  role_families?: string[];
  matched_region_ids?: string[];
  matched_region_coverage?: Record<string, CoverageMetadata>;
  current_hiring: boolean;
  has_entry_level_access: boolean;
  presence_status: string | null;
  freshness: FreshnessSourceSummary;
  has_real_data: boolean;
};

export type CompanySearchResponse = {
  companies?: CompanySearchResult[];
  count?: number;
};

export type CompanyGeographyResult = {
  region_id: string;
  region_name: string;
  presence_status: string | null;
  current_hiring: boolean;
  has_entry_level_access: boolean;
  coverage?: CoverageMetadata;
  sector_coverage?: SectorCoverageMap;
  freshness: FreshnessSourceSummary;
  has_real_data: boolean;
};

export type CompanyGeographyResponse = {
  company_id: string;
  company_name: string;
  regions?: CompanyGeographyResult[];
  count?: number;
};

export type SourceDetail = {
  source_id: string;
  source_type: string;
  source_name: string;
  url: string | null;
  collected_at: string | null;
  freshness_status: FreshnessStatus;
  data_basis: DataBasis;
};

export type SourceExplanation = {
  subject_type: "company" | "region";
  subject_id: string;
  freshness: FreshnessSourceSummary;
  sources?: SourceDetail[];
  warnings?: string[];
};

export type ComparisonDetail = {
  comparison_id: string;
  region_a?: {
    region_id: string;
    display_name: string;
    scores: RegionScores | null;
    coverage?: CoverageMetadata;
    sector_coverage?: SectorCoverageMap;
  };
  region_b?: {
    region_id: string;
    display_name: string;
    scores: RegionScores | null;
    coverage?: CoverageMetadata;
    sector_coverage?: SectorCoverageMap;
  };
  category_winners?: Record<string, string | null>;
  notes?: string[];
};

export type PersonalizedRequest = {
  role_targets: string[];
  industry_preferences: string[];
  career_stage: string;
  prestige_preference: string;
  brand_preference: string;
  region_ids: string[];
  limit: number;
};

export type PersonalizedResult = {
  ranked_regions?: Array<{
    region_id: string;
    display_name: string;
    personal_market_score: number;
    objective_opportunity_score: number | null;
    coverage?: CoverageMetadata;
    match_notes: string[];
  }>;
  ranked_companies?: Array<{
    company_id: string;
    company_name: string;
    region_id: string;
    region_display_name: string;
    personal_company_score: number;
    role_fit: number;
    industry_fit: number;
    prestige_fit: number;
    brand_fit: number;
    match_notes: string[];
  }>;
};

export type UserAccount = {
  user_id: string;
  status: string;
  created_at: string | null;
  updated_at: string | null;
};

export type UserProfile = {
  user_id: string;
  display_name: string | null;
  email: string | null;
  avatar_url: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type CurrentUserProfile = {
  user: UserAccount;
  profile: UserProfile;
};

export type PreferenceLevel = "low" | "medium" | "high";
export type CareerStage = "entry_level";
export type RemoteHybridPreference = "remote" | "hybrid" | "onsite" | "flexible";

export type ScoringWeights = {
  entry_level_access: number;
  hiring_density: number;
  prestige: number;
  industry_fit: number;
  role_fit: number;
};

export type UserPreferenceProfileInput = {
  role_interests?: string[];
  industry_interests?: string[];
  preferred_regions?: string[];
  prestige_weighting?: PreferenceLevel | null;
  brand_weighting?: PreferenceLevel | null;
  career_stage?: CareerStage | null;
  remote_hybrid_preference?: RemoteHybridPreference | null;
  scoring_weights?: ScoringWeights | null;
};

export type UserPreferenceProfile = Required<Omit<UserPreferenceProfileInput, "scoring_weights">> & {
  user_id: string;
  persisted: boolean;
  scoring_weights: ScoringWeights;
};

export type SavedMarketArtifactType = "region" | "company" | "role_family" | "comparison" | "discovery_result";

export type SavedMarketArtifactInput = {
  artifact_type: SavedMarketArtifactType;
  artifact_ref: string;
  label?: string | null;
  notes?: string | null;
  snapshot?: Record<string, unknown> | unknown[] | null;
};

export type SavedMarketArtifact = SavedMarketArtifactInput & {
  saved_artifact_id: string;
  user_id: string;
  created_at: string | null;
  updated_at: string | null;
};

export type SavedMarketArtifactList = {
  saved_market_artifacts: SavedMarketArtifact[];
};

export type PersonalizedRecommendationSnapshotInput = {
  preference_profile_id?: string | null;
  personalized_output: Record<string, unknown> | unknown[];
  recommendation_version: string;
  source_version_bundle: Record<string, unknown> | unknown[];
  objective_output_refs: Array<Record<string, unknown> | string>;
  recommendation_inputs_hash: string;
  generated_at: string;
};

export type PersonalizedRecommendationSnapshot = PersonalizedRecommendationSnapshotInput & {
  recommendation_snapshot_id: string;
  user_id: string;
  preference_profile_id: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type RecommendationSnapshotList = {
  personalized_recommendation_snapshots: PersonalizedRecommendationSnapshot[];
};

export type ScoringPreviewRequest = {
  region_ids: string[];
  role_interests?: string[] | null;
  industry_interests?: string[] | null;
  scoring_weights?: ScoringWeights | null;
};

export type ScoringPreviewComponent = {
  value: number | null;
  raw_weight: number;
  effective_weight: number;
  status: "used" | "missing" | string;
  evidence: string[];
};

export type ScoringPreviewRegion = {
  region_id: string;
  display_name: string;
  canonical_default_scores: {
    objective_opportunity_score: number | null;
    raw_total_score: number | null;
    early_career_accessibility_score: number | null;
    live_market_score: number | null;
    score_ruleset_version: string | null;
  };
  coverage?: CoverageMetadata;
  personalized_overlay_score: number | null;
  components: Record<keyof ScoringWeights, ScoringPreviewComponent>;
  omitted_components: Array<keyof ScoringWeights>;
};

export type ScoringPreviewResult = {
  scoring_weights: ScoringWeights;
  normalized_weights: ScoringWeights;
  regions: ScoringPreviewRegion[];
};

export type AlertEventType =
  | "new_hiring_activity"
  | "entry_level_signal_changed"
  | "company_expanded_in_region"
  | "region_score_changed"
  | "internship_window_opened";

export type UserAlertRelevance = {
  reason:
    | "saved_company"
    | "saved_region"
    | "saved_comparison"
    | "saved_role_family"
    | "preferred_region"
    | "role_interest"
    | string;
  artifact_id: string | null;
  artifact_type: SavedMarketArtifactType | string | null;
  artifact_ref: string | null;
};

export type AlertEvent = {
  alert_event_id: string;
  event_type: AlertEventType | string;
  company_id: string | null;
  region_id: string | null;
  role_family: string | null;
  previous_value: Record<string, unknown> | unknown[] | null;
  new_value: Record<string, unknown> | unknown[] | null;
  change_summary: Record<string, unknown> | unknown[] | null;
  freshness_status: string | null;
  freshness_observed_at: string | null;
  freshness_expires_at: string | null;
  source_refs: string[];
  change_basis_refs: string[];
  detection_basis: string;
  created_at: string | null;
};

export type UserAlert = {
  user_alert_id: string;
  user_id: string;
  alert_event_id: string;
  is_read: boolean;
  dismissed: boolean;
  read_at: string | null;
  dismissed_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  relevance: UserAlertRelevance;
  event: AlertEvent;
};

export type UserAlertList = {
  alerts: UserAlert[];
};

export type ExplanationEntityType = "region" | "company" | "comparison" | "alert";

export type ExplanationFreshnessEvidence = {
  freshness_status?: string | null;
  data_basis?: string | null;
  last_updated_at?: string | null;
  freshness_expires_at?: string | null;
  source_count?: number | null;
};

export type ExplanationScoringFactor = {
  factor: string;
  label?: string | null;
  value?: number | null;
  weight?: number | null;
  status?: string | null;
};

export type ExplanationEvidencePacket = {
  entity_type: ExplanationEntityType;
  subject_refs?: Record<string, string>;
  display_label?: string | null;
  canonical_scores?: Record<string, number | null>;
  personalized_overlay?: Record<string, number | null>;
  scoring_factors?: ExplanationScoringFactor[];
  freshness?: ExplanationFreshnessEvidence | null;
  source_refs?: string[];
  alert?: {
    event_type: string;
    relevance_reason?: string | null;
    changed_fields?: string[];
    detection_basis?: string | null;
  } | null;
  watchlist_context?: string[];
  missing_data?: string[];
  unsupported_data?: string[];
  demo_or_seeded?: boolean;
  notes?: string[];
};

export type ExplanationRequest = {
  evidence: ExplanationEvidencePacket;
};

export type ExplanationResult = {
  provider_mode: "deterministic_structured_guidance" | string;
  status: "ok" | "constrained" | "refused" | string;
  entity_type: ExplanationEntityType;
  subject_refs: Record<string, string>;
  sections: Array<{
    section_type:
      | "structured_fact"
      | "score_interpretation"
      | "freshness_limitation"
      | "missing_unsupported_data"
      | "personalized_overlay"
      | string;
    title: string;
    statements: string[];
  }>;
  limitations: string[];
  evidence_refs: string[];
};

export type UserDataExport = {
  export_schema_version: string;
  user: UserAccount;
  profile: UserProfile | null;
  external_auth_identities: Array<Record<string, unknown>>;
  preference_profile: (Omit<UserPreferenceProfile, "persisted"> & {
    created_at: string | null;
    updated_at: string | null;
  }) | null;
  saved_market_artifacts: SavedMarketArtifact[];
  personalized_recommendation_snapshots: PersonalizedRecommendationSnapshot[];
  user_alerts?: Array<Record<string, unknown>>;
};

export type AccountDeactivationResult = {
  user_id: string;
  user_status: string;
  deleted_preference_profiles: number;
  deleted_saved_market_artifacts: number;
  deleted_recommendation_snapshots: number;
  deleted_user_alerts?: number;
  deleted_profiles: number;
  deleted_external_auth_identities: number;
};
