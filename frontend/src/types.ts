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

export type PlatformEmbedProductId = "region_comparison" | "market_score_card";

export type PlatformEmbedPayload = {
  embed_product_id: PlatformEmbedProductId;
  title: string;
  attribution: string;
  freshness: {
    status: string;
    freshness_expires_at: string | null;
    last_updated_at: string | null;
  };
  confidence: {
    level: string;
    label: string;
  };
  source_summary: {
    data_basis: string;
    source_count: number;
    source_categories: string[];
    notes: string[];
  };
  warnings: string[];
  metrics: Array<Record<string, string | number | boolean | null>>;
};

export type PlatformEmbedAccessPayload = {
  allowed: true;
  embed_product_id: PlatformEmbedProductId;
  payload: PlatformEmbedPayload;
};

export type AudienceSegmentKey =
  | "students"
  | "early_career_job_seekers"
  | "relocation_candidates"
  | "parents_advisors";

export type BuyerSegmentKey =
  | "career_centers"
  | "bootcamps"
  | "universities"
  | "workforce_boards";

export type MonetizationFeatureBoundary = "free" | "paid";

export type MonetizationFeatureKey =
  | "basic_region_exploration"
  | "public_demo_markets"
  | "limited_comparisons"
  | "limited_personalized_discovery"
  | "basic_recommendation_preview"
  | "saved_watchlists"
  | "alerts"
  | "advanced_recommendation_reports"
  | "full_market_coverage"
  | "exportable_strategy_plans"
  | "deeper_company_geography"
  | "saved_comparison_history"
  | "full_report_generation"
  | "institutional_license_management"
  | "cohort_guidance_templates"
  | "privacy_preserving_program_insights";

export type MonetizationFeature = {
  feature_key: MonetizationFeatureKey;
  boundary: MonetizationFeatureBoundary;
  display_name: string;
  description: string;
  boundary_rationale: string;
  trust_constraint: string;
  exposes_core_recommendation_conclusion: boolean;
  recommendation_influence: string;
};

export type MonetizationFeaturesPayload = {
  features: MonetizationFeature[];
};

export type MonetizationPlanKey =
  | "free"
  | "individual_monthly"
  | "individual_annual"
  | "student_annual"
  | "career_center_license"
  | "bootcamp_license"
  | "university_license"
  | "workforce_board_license";

export type MonetizationBuyerKind = "individual" | "institutional";
export type MonetizationBillingInterval = "free" | "monthly" | "annual" | "license_term";
export type MonetizationUsageLimitUnit = "per_month" | "active_items" | "seats";

export type MonetizationUsageLimit = {
  feature_key: MonetizationFeatureKey;
  limit: number;
  unit: MonetizationUsageLimitUnit;
  description: string;
};

export type MonetizationPriceConfiguration = {
  price_config_key: string | null;
  placeholder_amount_cents: number | null;
  currency: string;
  final_price: boolean;
  note: string;
};

export type MonetizationPlan = {
  plan_key: MonetizationPlanKey;
  display_name: string;
  buyer_kind: MonetizationBuyerKind;
  buyer_segment: BuyerSegmentKey | null;
  billing_interval: MonetizationBillingInterval;
  intended_audience: AudienceSegmentKey[];
  included_feature_keys: MonetizationFeatureKey[];
  usage_limits: MonetizationUsageLimit[];
  upgrade_plan_keys: MonetizationPlanKey[];
  price: MonetizationPriceConfiguration;
};

export type MonetizationPlansPayload = {
  plans: MonetizationPlan[];
};

export type MonetizationReportProductKey =
  | "personalized_market_strategy_report"
  | "region_comparison_report"
  | "company_geography_report"
  | "early_career_opportunity_report";

export type MonetizationReportProduct = {
  report_key: MonetizationReportProductKey;
  display_name: string;
  intended_segments: AudienceSegmentKey[];
  free_preview_available: boolean;
  preview_feature_key: MonetizationFeatureKey | null;
  paid_full_report_required: boolean;
  paid_full_report_feature_keys: MonetizationFeatureKey[];
  included_sections: string[];
  exportable: boolean;
  export_feature_key: MonetizationFeatureKey | null;
};

export type MonetizationReportsPayload = {
  reports: MonetizationReportProduct[];
};

export type MonetizationAccessDecision = {
  allowed: boolean;
  plan_key: MonetizationPlanKey;
  feature_key: MonetizationFeatureKey;
  reason: string;
  upgrade_plan_keys: MonetizationPlanKey[];
  usage_limit: MonetizationUsageLimit | null;
  remaining_usage: number | null;
  account_status?: string | null;
};

export type MonetizationAccessPreviewPayload = {
  decision: MonetizationAccessDecision;
};

export type MonetizationAccountType =
  | "individual"
  | "student"
  | "institutional"
  | "public_demo"
  | "internal_test";

export type MonetizationEntitlementSnapshot = {
  user_id: string | null;
  monetization_account_id: string | null;
  account_type: MonetizationAccountType;
  account_status: string;
  plan_key: MonetizationPlanKey;
  included_feature_keys: MonetizationFeatureKey[];
  usage_limits: MonetizationUsageLimit[];
  assignment_source: string | null;
  effective_at: string | null;
  expires_at: string | null;
  seat_limit: number | null;
  assigned_seats_count: number | null;
  safe_metadata: Record<string, unknown>;
};

export type MonetizationAccountSummary = {
  monetization_account_id: string | null;
  user_id: string | null;
  account_type: MonetizationAccountType;
  account_status: string;
  assigned_seats_count: number | null;
  seat_limit: number | null;
  safe_metadata: Record<string, unknown>;
};

export type MonetizationMePayload = {
  account: MonetizationAccountSummary;
  entitlements: MonetizationEntitlementSnapshot;
};

export type MonetizationEntitlementsPayload = {
  entitlements: MonetizationEntitlementSnapshot;
};

export type MonetizationUsageCounter = {
  usage_counter_id: string | null;
  monetization_account_id: string | null;
  feature_key: MonetizationFeatureKey;
  period_start: string;
  period_end: string;
  used_count: number;
  limit_count: number;
  reset_policy: "monthly" | "static" | string;
  last_incremented_at: string | null;
};

export type MonetizationUsagePayload = {
  plan_key: MonetizationPlanKey;
  account_status: string;
  usage: MonetizationUsageCounter[];
};

export type MonetizationReportWorkflowPayload = {
  report_key: MonetizationReportProductKey;
  workflow: string;
  generated_at: string;
  access_decision: MonetizationAccessDecision;
  sections: Array<{
    section_key: string;
    title: string;
    body: string;
  }>;
  note: string;
};

export type MonetizationReportGenerationPayload = {
  report: MonetizationReportWorkflowPayload;
};

export type MonetizationReportExportPayload = {
  export: MonetizationReportWorkflowPayload;
};

export type BillingProvider = "stripe";

export type BillingStatusPayload = {
  provider: BillingProvider | null;
  checkout_available: boolean;
  portal_available: boolean;
  checkout_plan_keys: MonetizationPlanKey[];
  disabled_reason: string | null;
};

export type BillingCheckoutSessionPayload = {
  provider: BillingProvider;
  checkout_session_id: string;
  checkout_url: string;
  plan_key: MonetizationPlanKey;
  access_granted: false;
};

export type BillingPortalSessionPayload = {
  provider: BillingProvider;
  portal_session_id: string;
  portal_url: string;
};

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

export type PublicReportLink = {
  label: string;
  href: string;
  link_type: "report" | "public_page";
};

export type PublicSourceProvenanceSummary = {
  data_basis: "demo_template" | "public_safe_summary" | "mixed" | "unknown";
  source_count: number;
  source_categories: string[];
  provenance_notes: string[];
};

export type PublicCitation = {
  source_name: string;
  title: string;
  period: string;
  product_attribution: string;
  public_path: string;
  accessed_or_freshness_date: string;
};

export type PublicShareSummary = {
  title: string;
  category_claim: string;
  confidence_label: string;
  freshness_label: string;
  takeaway: string;
  public_path: string;
  warning: string;
};

export type PublicSourceAuthority = {
  labels: string[];
  summary: string;
};

export type PublicInstitutionalCta = {
  label: string;
  body: string;
  href: string;
  link_type: "public_page";
};

export type PublicReportMarket = {
  market_id: string;
  market_label: string;
  coverage_note: string;
};

export type PublicReportMarketResult = {
  result_type: "featured" | "ranked";
  rank: number | null;
  market_id: string;
  market_label: string;
  headline: string;
  rationale: string;
  evidence_signals: string[];
  freshness_date: string;
  confidence: "high" | "medium" | "low" | "unknown";
  warnings: string[];
  source_provenance_summary: PublicSourceProvenanceSummary;
};

export type PublicReport = {
  report_id: string;
  slug: string;
  title: string;
  category: string;
  report_period: string;
  summary: string;
  markets_covered: PublicReportMarket[];
  market_results: PublicReportMarketResult[];
  methodology_summary: string;
  limitations: string[];
  freshness_date: string;
  freshness_status: FreshnessStatus;
  confidence: "high" | "medium" | "low" | "unknown";
  warnings: string[];
  source_provenance_summary: PublicSourceProvenanceSummary;
  related_links: PublicReportLink[];
  suggested_citation: PublicCitation;
  share_summary: PublicShareSummary;
  source_authority: PublicSourceAuthority;
  institutional_cta: PublicInstitutionalCta;
};

export type PublicReportSummary = {
  report_id: string;
  slug: string;
  title: string;
  category: string;
  report_period: string;
  summary: string;
  freshness_date: string;
  confidence: "high" | "medium" | "low" | "unknown";
  warnings: string[];
};

export type PublicReportListPayload = {
  reports: PublicReportSummary[];
};

export type PublicBenchmarkLink = {
  label: string;
  href: string;
  link_type: "benchmark" | "report" | "public_page";
};

export type PublicBenchmarkSourceSummary = {
  data_basis: "demo_template" | "public_safe_summary" | "mixed" | "unknown";
  source_count: number;
  source_categories: string[];
  provenance_notes: string[];
};

export type PublicBenchmarkScoreDisplay = {
  label: string;
  value: number | null;
  display_value: string;
  score_basis: "demo_static" | "public_safe_summary" | "unavailable";
  caveat: string;
};

export type PublicBenchmarkSubscore = {
  key: string;
  label: string;
  value: number | null;
  display_value: string;
  explanation: string;
};

export type PublicBenchmarkMarketResult = {
  result_type: "featured" | "ranked";
  rank: number | null;
  market_id: string;
  market_label: string;
  score_display: PublicBenchmarkScoreDisplay;
  subscores: PublicBenchmarkSubscore[];
  explanation: string;
  warnings: string[];
  freshness_date: string;
  confidence: "high" | "medium" | "low" | "unknown";
  source_provenance_summary: PublicBenchmarkSourceSummary;
};

export type PublicBenchmark = {
  benchmark_id: string;
  slug: string;
  name: string;
  category: string;
  period: string;
  summary: string;
  methodology_summary: string;
  limitations: string[];
  freshness_date: string;
  freshness_status: FreshnessStatus;
  confidence: "high" | "medium" | "low" | "unknown";
  warnings: string[];
  market_results: PublicBenchmarkMarketResult[];
  source_provenance_summary: PublicBenchmarkSourceSummary;
  related_links: PublicBenchmarkLink[];
  suggested_citation: PublicCitation;
  share_summary: PublicShareSummary;
  source_authority: PublicSourceAuthority;
  institutional_cta: PublicInstitutionalCta;
};

export type PublicBenchmarkSummary = {
  benchmark_id: string;
  slug: string;
  name: string;
  category: string;
  period: string;
  summary: string;
  freshness_date: string;
  confidence: "high" | "medium" | "low" | "unknown";
  warnings: string[];
};

export type PublicBenchmarkListPayload = {
  benchmarks: PublicBenchmarkSummary[];
};

export type CoverageTier = "tier_1" | "tier_2" | "tier_3" | "tier_4";

export type CoverageScoreComponent =
  | "company_coverage"
  | "hiring_coverage"
  | "entry_level_coverage"
  | "freshness"
  | "source_diversity"
  | "confidence";

export type CoverageComponents = Partial<Record<CoverageScoreComponent, number>> & Record<string, number | undefined>;

export type CoverageQualityScore = {
  overall_score: number | null;
  components?: CoverageComponents;
};

export type CoverageMetadata = {
  tier: CoverageTier | string;
  label?: string | null;
  quality_score?: number | null;
  components?: CoverageComponents;
  coverage_tier?: CoverageTier | string | null;
  coverage_label?: string | null;
  coverage_description?: string | null;
  coverage_quality_score?: CoverageQualityScore | null;
  coverage_limitations?: string[];
  notes?: string[];
  heuristic?: boolean;
  safe_for_confident_market_comparison?: boolean;
  should_rank_as_confident_recommendation?: boolean;
};

export type SectorCoverageLevel = "unknown" | "limited" | "watchlist" | "partial" | "strong";

export type SectorCoverageMetadata = {
  sector: string;
  label?: string | null;
  coverage_level?: SectorCoverageLevel | string | null;
  coverage: CoverageMetadata;
};

export type SectorCoverageMap = Record<string, SectorCoverageMetadata>;

export type PriorityMarket = {
  rank: number;
  market_id: string;
  display_name: string;
};

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
  priority_market?: PriorityMarket | null;
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
  priority_market?: PriorityMarket | null;
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
  priority_market?: PriorityMarket | null;
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
    priority_market?: PriorityMarket | null;
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
    priority_market?: PriorityMarket | null;
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
    priority_market?: PriorityMarket | null;
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
  priority_market?: PriorityMarket | null;
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
    priority_market?: PriorityMarket | null;
  };
  region_b?: {
    region_id: string;
    display_name: string;
    scores: RegionScores | null;
    coverage?: CoverageMetadata;
    sector_coverage?: SectorCoverageMap;
    priority_market?: PriorityMarket | null;
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
    priority_market?: PriorityMarket | null;
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
  priority_market?: PriorityMarket | null;
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

export type RecommendationGoalMode =
  | "maximize_entry_level_access"
  | "maximize_prestige"
  | "maximize_ai_cloud_concentration"
  | "maximize_underrated_markets"
  | "maximize_internship_coop_access"
  | "maximize_lower_competition"
  | "maximize_geographic_flexibility";

export type RecommendationScoreComponentName =
  | "entry_level_access"
  | "internship_or_coop_access"
  | "prestige_density"
  | "ai_cloud_concentration"
  | "company_density"
  | "role_diversity"
  | "lower_competition_proxy"
  | "geographic_flexibility"
  | "market_coverage"
  | "confidence"
  | "freshness";

export type RecommendationEvidenceBasis =
  | "structured_score"
  | "market_coverage"
  | "company_metadata"
  | "region_metadata"
  | "provenance"
  | "freshness"
  | "confidence"
  | "data_quality_warning"
  | "heuristic_inference"
  | "user_preference"
  | "missing_data"
  | string;

export type RecommendationEvidenceStrength =
  | "strong"
  | "moderate"
  | "weak"
  | "missing"
  | "inferred"
  | string;

export type RecommendationClaimSupport = "direct" | "inferred" | string;
export type RecommendationImportance = "low" | "medium" | "high" | string;
export type RecommendationTargetType =
  | "region"
  | "company"
  | "company_category"
  | "role_family"
  | "market_strategy"
  | "watchlist_item"
  | string;

export type RecommendationTarget = {
  target_type: RecommendationTargetType;
  target_id: string;
  display_label?: string | null;
  parent_target_id?: string | null;
  related_target_ids?: string[];
};

export type RecommendationConfidenceSummary = {
  confidence_level?: string | null;
  confidence_score?: number | null;
  confidence_status?: string | null;
  confidence_ref?: string | null;
  warnings?: string[];
};

export type RecommendationFreshnessSummary = {
  freshness_status?: string | null;
  data_basis?: string | null;
  last_updated_at?: string | null;
  freshness_expires_at?: string | null;
  source_count?: number | null;
  freshness_ref?: string | null;
  warnings?: string[];
};

export type RecommendationProvenanceReference = {
  provenance_ref?: string | null;
  source_ref_id?: string | null;
  source_observation_id?: string | null;
  fact_source_link_id?: string | null;
  source_type?: string | null;
  origin?: string | null;
  source_refs?: string[];
};

export type RecommendationEvidenceReference = {
  basis: RecommendationEvidenceBasis;
  strength: RecommendationEvidenceStrength;
  label?: string | null;
  reference_type?: string | null;
  reference_id?: string | null;
  provenance?: RecommendationProvenanceReference | null;
  confidence?: RecommendationConfidenceSummary | null;
  freshness?: RecommendationFreshnessSummary | null;
  coverage_warning_refs?: string[];
  data_quality_warning_refs?: string[];
  note?: string | null;
};

export type RecommendationReason = {
  reason_category: string;
  label: string;
  detail?: string | null;
  evidence_strength: RecommendationEvidenceStrength;
  evidence_basis: RecommendationEvidenceBasis[];
  support: RecommendationClaimSupport;
  evidence_refs: RecommendationEvidenceReference[];
};

export type RecommendationTradeoff = {
  tradeoff_category: string;
  label: string;
  positive_side: string;
  negative_side: string;
  importance: RecommendationImportance;
  evidence_strength: RecommendationEvidenceStrength;
  evidence_basis: RecommendationEvidenceBasis[];
  support: RecommendationClaimSupport;
  evidence_refs: RecommendationEvidenceReference[];
};

export type RecommendationWeakness = {
  weakness_category: string;
  label: string;
  detail?: string | null;
  evidence_strength: RecommendationEvidenceStrength;
  evidence_basis: RecommendationEvidenceBasis[];
  support: RecommendationClaimSupport;
  evidence_refs: RecommendationEvidenceReference[];
};

export type RecommendationManualVerificationItem = {
  verification_category: string;
  label: string;
  question: string;
  rationale?: string | null;
  importance: RecommendationImportance;
  evidence_strength: RecommendationEvidenceStrength;
  evidence_basis: RecommendationEvidenceBasis[];
  support: RecommendationClaimSupport;
  evidence_refs: RecommendationEvidenceReference[];
};

export type RecommendationExplanation = {
  target: RecommendationTarget;
  goal_mode?: RecommendationGoalMode | null;
  headline?: string | null;
  fit_reasons: RecommendationReason[];
  data_strengths: RecommendationReason[];
  tradeoffs: RecommendationTradeoff[];
  weaknesses: RecommendationWeakness[];
  manual_verification: RecommendationManualVerificationItem[];
  evidence_refs: RecommendationEvidenceReference[];
  confidence_summary?: RecommendationConfidenceSummary | null;
  freshness_summary?: RecommendationFreshnessSummary | null;
  provenance_refs: RecommendationProvenanceReference[];
  coverage_warnings: string[];
  data_quality_warnings: string[];
};

export type RecommendationGoalModeComponentPayload = {
  component: RecommendationScoreComponentName;
  weight: number;
  evidence_basis: RecommendationEvidenceBasis[];
  is_proxy: boolean;
  requires_heuristic_inference: boolean;
  unavailable_behavior: string;
  warning?: string | null;
  penalty_explanation?: string | null;
};

export type RecommendationGoalModeProfilePayload = {
  goal_mode: RecommendationGoalMode;
  label: string;
  description: string;
  prioritization_summary: string;
  weighted_components: RecommendationGoalModeComponentPayload[];
  penalty_components: RecommendationGoalModeComponentPayload[];
  missing_data_behavior: string;
  warnings: string[];
};

export type RecommendationGoalModesPayload = {
  goal_modes: RecommendationGoalModeProfilePayload[];
};

export type RecommendationStrategyRequest = {
  goal_mode: RecommendationGoalMode;
  include_company_recommendations?: boolean;
  region_limit?: number;
  company_limit?: number;
  max_primary_regions?: number;
  max_secondary_regions?: number;
  max_fallback_regions?: number;
  max_watchlist_items?: number;
  max_company_targets?: number;
};

export type WeightedScoreComponent = {
  component: RecommendationScoreComponentName;
  value: number;
  weight: number;
  weighted_value: number;
  evidence_basis: RecommendationEvidenceBasis[];
  evidence_refs: RecommendationEvidenceReference[];
  source_fields: string[];
  is_proxy: boolean;
  inferred: boolean;
  warning?: string | null;
};

export type MissingScoreComponent = {
  component: RecommendationScoreComponentName;
  weight: number;
  unavailable_behavior: string;
  evidence_basis: RecommendationEvidenceBasis[];
  warning?: string | null;
};

export type AppliedRankingPenalty = {
  component: RecommendationScoreComponentName;
  value: number;
  weight: number;
  penalty_value: number;
  application_mode: string;
  explanation: string;
  evidence_basis: RecommendationEvidenceBasis[];
  evidence_refs: RecommendationEvidenceReference[];
  is_proxy: boolean;
  inferred: boolean;
};

export type RecommendationRankingItem = {
  rank: number;
  target: RecommendationTarget;
  goal_mode: RecommendationGoalMode;
  final_score: number;
  normalized_score: number;
  score_components_used: WeightedScoreComponent[];
  score_components_missing: MissingScoreComponent[];
  score_components_proxy: WeightedScoreComponent[];
  penalties_applied: AppliedRankingPenalty[];
  confidence_contribution?: number | null;
  freshness_contribution?: number | null;
  coverage_contribution?: number | null;
  explanation: RecommendationExplanation;
  warnings: string[];
};

export type StrategySourceRecommendation = {
  source_id: string;
  rank: number;
  target: RecommendationTarget;
  final_score: number;
  warnings: string[];
};

export type StrategyTraceableItem = {
  source_recommendation_ids: string[];
  evidence_strength: RecommendationEvidenceStrength;
  evidence_basis: RecommendationEvidenceBasis[];
  support: RecommendationClaimSupport;
  evidence_refs: RecommendationEvidenceReference[];
};

export type StrategyRegionTarget = StrategyTraceableItem & {
  target: RecommendationTarget;
  target_role: "primary" | "secondary" | "fallback" | string;
  source_rank: number;
  final_score: number;
  rationale: string;
  tradeoff_categories: string[];
};

export type StrategyCompanyTarget = StrategyTraceableItem & {
  target: RecommendationTarget;
  source_rank: number;
  final_score: number;
  rationale: string;
};

export type StrategyCompanyCategoryTarget = StrategyTraceableItem & {
  target: RecommendationTarget;
  rationale: string;
};

export type StrategyRoleFamilyTarget = StrategyTraceableItem & {
  target: RecommendationTarget;
  rationale: string;
};

export type StrategyTimingGuidance = StrategyTraceableItem & {
  timing_category: string;
  label: string;
  guidance: string;
  importance: RecommendationImportance;
};

export type StrategyWatchlistItem = StrategyTraceableItem & {
  watchlist_category: string;
  target: RecommendationTarget;
  reason: string;
  upside: string;
  what_to_verify: string;
  revisit_after_refresh: boolean;
};

export type StrategyManualVerificationEntry = {
  item: RecommendationManualVerificationItem;
  source_recommendation_ids: string[];
};

export type StrategyManualVerificationChecklist = {
  items: StrategyManualVerificationEntry[];
};

export type StrategyEvidenceWarning = StrategyTraceableItem & {
  warning_category: string;
  label: string;
  detail?: string | null;
};

export type MarketStrategyPlan = {
  goal_mode: RecommendationGoalMode;
  strategy_version: string;
  source_recommendations: StrategySourceRecommendation[];
  primary_region_targets: StrategyRegionTarget[];
  secondary_region_targets: StrategyRegionTarget[];
  fallback_region_targets: StrategyRegionTarget[];
  company_targets: StrategyCompanyTarget[];
  company_category_targets: StrategyCompanyCategoryTarget[];
  role_family_targets: StrategyRoleFamilyTarget[];
  timing_guidance: StrategyTimingGuidance[];
  watchlist_items: StrategyWatchlistItem[];
  manual_verification_checklist: StrategyManualVerificationChecklist;
  evidence_warnings: StrategyEvidenceWarning[];
};

export type RecommendationStrategyPayload = {
  available_goal_modes: RecommendationGoalModeProfilePayload[];
  selected_goal_mode: RecommendationGoalModeProfilePayload;
  ranking_profile_version: string;
  ranking_tie_breaker: string;
  ranked_region_recommendations: RecommendationRankingItem[];
  ranked_company_recommendations: RecommendationRankingItem[];
  market_strategy_plan: MarketStrategyPlan;
  warnings: string[];
};

export type OrganizationRole = "ORG_ADMIN" | "ADVISOR" | "STUDENT" | "REPORT_VIEWER";

export type InstitutionOrganization = {
  organization_id: string;
  name: string;
  organization_type: string;
  status: string;
  created_at: string | null;
  updated_at: string | null;
};

export type InstitutionMembership = {
  organization_membership_id: string;
  organization_id: string;
  user_id: string;
  role: OrganizationRole;
  status: string;
  created_at: string | null;
  updated_at: string | null;
};

export type InstitutionCurrentOrganizationsPayload = {
  organizations: Array<{
    organization: InstitutionOrganization;
    membership: InstitutionMembership;
  }>;
};

export type InstitutionAggregateItem = {
  label: string;
  count: number | null;
  percentage: number | null;
  category: string | null;
  suppressed: boolean;
  suppression_reason: string | null;
  source_count: number | null;
  coverage: Record<string, unknown> | null;
  confidence: string | null;
  metadata: Record<string, unknown>;
};

export type InstitutionSuppressedCategory = {
  section: string;
  suppressed_count: number;
  suppression_reason: string;
  minimum_group_size: number;
};

export type InstitutionDashboardPayload = {
  organization_id: string;
  organization_name: string;
  generated_at: string;
  minimum_group_size: number;
  cohort_size: number;
  visible_student_count: number;
  popular_target_markets: InstitutionAggregateItem[];
  role_interest_summary: InstitutionAggregateItem[];
  saved_company_summary: InstitutionAggregateItem[];
  market_demand_trends: InstitutionAggregateItem[];
  coverage_gaps: InstitutionAggregateItem[];
  suppressed_categories: InstitutionSuppressedCategory[];
  privacy_notes: string[];
  coverage_warnings: string[];
  data_freshness: Record<string, unknown>;
};

export type InstitutionAdvisorComparisonType =
  | "regions"
  | "industries"
  | "companies"
  | "career_stages"
  | "application_timing";

export type InstitutionAdvisorRegionRequest = {
  regions: string[];
  role_context?: string | null;
  industry_context?: string | null;
  career_stage?: string | null;
};

export type InstitutionAdvisorIndustryRequest = {
  industries: string[];
  region_context?: string[];
  career_stage?: string | null;
};

export type InstitutionAdvisorCompanyRequest = {
  companies: string[];
  region_context?: string[];
  industry_context?: string | null;
  career_stage?: string | null;
};

export type InstitutionAdvisorCareerStageRequest = {
  career_stages: string[];
  region_context?: string[];
  industry_context?: string | null;
  company_context?: string[];
};

export type InstitutionAdvisorApplicationTimingRequest = {
  target_regions?: string[];
  target_industries?: string[];
  target_companies?: string[];
  career_stage?: string | null;
  application_window?: string | null;
};

export type InstitutionAdvisorRequest =
  | InstitutionAdvisorRegionRequest
  | InstitutionAdvisorIndustryRequest
  | InstitutionAdvisorCompanyRequest
  | InstitutionAdvisorCareerStageRequest
  | InstitutionAdvisorApplicationTimingRequest;

export type InstitutionAdvisorComparedItem = {
  item_id: string;
  label: string;
  item_type: string;
  demand_signals: Record<string, unknown>;
  coverage: Record<string, unknown> | null;
  explanation_summary: string[];
  warnings: string[];
  metadata: Record<string, unknown>;
};

export type InstitutionAdvisorTradeoff = {
  category: string;
  summary: string;
  evidence_level: string;
};

export type InstitutionAdvisorToolResponse = {
  organization_id: string;
  generated_at: string;
  comparison_type: InstitutionAdvisorComparisonType;
  compared_items: InstitutionAdvisorComparedItem[];
  guidance: string[];
  tradeoffs: InstitutionAdvisorTradeoff[];
  coverage_warnings: string[];
  data_freshness: Record<string, unknown>;
  limitations: string[];
  privacy_notes: string[];
};

export type InstitutionReportType =
  | "career_services"
  | "program_director"
  | "workforce_planner"
  | "economic_development_partner";

export type InstitutionReportCreateRequest = {
  report_type: InstitutionReportType;
  minimum_group_size?: number;
  date_range?: Record<string, string | null> | null;
};

export type InstitutionReportSection = {
  section_id: string;
  title: string;
  summary: string;
  findings: string[];
  metrics: Record<string, unknown>;
  warnings: string[];
  suppressions: InstitutionSuppressedCategory[];
  limitations: string[];
  recommended_actions: string[];
};

export type InstitutionReportPayload = {
  report_id: string;
  organization_id: string;
  report_type: InstitutionReportType;
  title: string;
  generated_at: string;
  generated_by_user_id: string;
  date_range: Record<string, string | null> | null;
  minimum_group_size: number;
  cohort_size: number;
  sections: InstitutionReportSection[];
  privacy_suppressions: InstitutionSuppressedCategory[];
  coverage_warnings: string[];
  data_freshness: Record<string, unknown>;
  limitations: string[];
  recommended_actions: string[];
  export_status: string;
  export_options: Record<string, string>;
  privacy_notes: string[];
};

export type InstitutionReportSummary = {
  report_id: string;
  organization_id: string;
  report_type: InstitutionReportType;
  title: string;
  generated_at: string;
  generated_by_user_id: string;
  minimum_group_size: number;
  cohort_size: number;
  status: string;
  privacy_summary: Record<string, unknown>;
  coverage_summary: Record<string, unknown>;
};

export type InstitutionReportGeneratePayload = {
  report: InstitutionReportPayload;
};

export type InstitutionReportListPayload = {
  reports: InstitutionReportSummary[];
};

export type IntegrationDestination =
  | "csv"
  | "pdf"
  | "google_sheets"
  | "notion"
  | "airtable"
  | "ics_calendar";

export type IntegrationCapability =
  | "export_file"
  | "prepared_payload"
  | "calendar_file";

export type IntegrationRiskPosture =
  | "local_download_only"
  | "prepared_no_sync"
  | "calendar_file_no_sync"
  | "unsupported_deferred";

export type IntegrationExportFormat =
  | "csv"
  | "pdf"
  | "prepared_google_sheets"
  | "prepared_notion"
  | "prepared_airtable";

export type IntegrationProductObjectType =
  | "region"
  | "company"
  | "comparison"
  | "recommendation_strategy"
  | "institutional_dashboard"
  | "institutional_report";

export type IntegrationReminderType =
  | "application_window"
  | "internship_deadline"
  | "follow_up"
  | "market_refresh_alert"
  | "institutional_report_review"
  | "data_request_due";

export type IntegrationPermissionDecision = {
  allowed: boolean;
  reason: string;
  boundary: string;
  owner_user_id: string | null;
  organization_id: string | null;
};

export type IntegrationProvenance = {
  product_object_type: IntegrationProductObjectType;
  product_object_id: string;
  product_object_label: string | null;
  generated_at: string;
  generated_by_user_id: string;
  organization_id: string | null;
  freshness_status: string;
  freshness_as_of: string | null;
  confidence_label: string;
  evidence_basis: string[];
  source_object_version: string | null;
  limitations: string[];
  governance_warnings: string[];
};

export type IntegrationReceipt = {
  integration_id: string;
  destination: IntegrationDestination;
  capability: IntegrationCapability;
  risk_posture: IntegrationRiskPosture;
  status: string;
  permission_decision: IntegrationPermissionDecision;
  provenance: IntegrationProvenance;
  external_write_performed: boolean;
  live_sync_enabled: boolean;
  oauth_performed: boolean;
  two_way_sync_enabled: boolean;
  product_authority_retained: boolean;
  limitations: string[];
  governance_warnings: string[];
};

export type IntegrationExportCreateRequest = {
  product_object_type: IntegrationProductObjectType;
  product_object_id: string;
  export_format: IntegrationExportFormat;
  organization_id?: string | null;
  source_context?: Record<string, unknown>;
};

export type IntegrationExportPayload = {
  export_id: string;
  product_object_type: IntegrationProductObjectType;
  product_object_id: string;
  export_format: IntegrationExportFormat;
  destination: IntegrationDestination;
  capability: IntegrationCapability;
  risk_posture: IntegrationRiskPosture;
  status: string;
  filename: string | null;
  content_type: string | null;
  payload: Record<string, unknown>;
  receipt: IntegrationReceipt;
  created_at: string;
  updated_at: string;
};

export type IntegrationExportCreatePayload = {
  export: IntegrationExportPayload;
};

export type IntegrationReminderCreateRequest = {
  reminder_type: IntegrationReminderType;
  product_object_type: IntegrationProductObjectType;
  product_object_id: string;
  title: string;
  due_at: string;
  organization_id?: string | null;
  timezone?: string;
  description?: string | null;
  duration_minutes?: number;
};

export type IntegrationReminderPayload = {
  reminder_id: string;
  reminder_type: IntegrationReminderType;
  product_object_type: IntegrationProductObjectType;
  product_object_id: string;
  destination: IntegrationDestination;
  capability: IntegrationCapability;
  risk_posture: IntegrationRiskPosture;
  status: string;
  title: string;
  due_at: string;
  timezone: string;
  receipt: IntegrationReceipt;
  ics_filename: string;
  created_at: string;
  updated_at: string;
};

export type IntegrationReminderCreatePayload = {
  reminder: IntegrationReminderPayload;
};

export type PartnerImportSourceType =
  | "local_employer_list"
  | "internship_partner_list"
  | "regional_workforce_data"
  | "aggregated_career_center_outcome_data";

export type PartnerImportFormat = "csv" | "json";

export type PartnerImportStatus =
  | "uploaded"
  | "validated"
  | "needs_review"
  | "accepted"
  | "partially_accepted"
  | "rejected"
  | "archived"
  | "quarantined";

export type PartnerImportDecision =
  | "accept"
  | "needs_review"
  | "reject"
  | "quarantine";

export type PartnerDataConfidence =
  | "high"
  | "medium"
  | "low"
  | "unknown"
  | "unverified"
  | "blocked";

export type PartnerImportGovernanceWarning = {
  code: string;
  severity: string;
  message: string;
  record_index: number | null;
  field: string | null;
  action: PartnerImportDecision;
};

export type PartnerImportValidationResult = {
  status: PartnerImportStatus;
  record_count: number;
  accepted_record_count: number;
  quarantined_record_count: number;
  rejected_record_count: number;
  warning_count: number;
  warnings: PartnerImportGovernanceWarning[];
  required_fields_missing: string[];
  unsupported_fields: string[];
  has_blocking_privacy_issue: boolean;
  has_blocking_source_issue: boolean;
  can_accept: boolean;
};

export type PartnerContributedEvidence = {
  partner_contributed: boolean;
  canonical_truth: boolean;
  import_batch_id: string;
  import_record_id: string;
  organization_id: string;
  source_type: PartnerImportSourceType;
  source_attribution: string;
  confidence: PartnerDataConfidence;
  freshness_status: string;
  imported_at: string;
  governance_warnings: PartnerImportGovernanceWarning[];
  canonical_identity_overwrite_performed: boolean;
  canonical_region_overwrite_performed: boolean;
  product_scoring_override_performed: boolean;
};

export type PartnerImportReceipt = {
  import_batch_id: string;
  organization_id: string;
  uploaded_by_user_id: string;
  source_type: PartnerImportSourceType;
  status: PartnerImportStatus;
  source_attribution: string;
  validation_result: PartnerImportValidationResult;
  permission_decision: IntegrationPermissionDecision;
  partner_contributed_evidence: boolean;
  canonical_truth: boolean;
  canonical_identity_overwrite_performed: boolean;
  canonical_region_overwrite_performed: boolean;
  product_scoring_override_performed: boolean;
  governance_warnings_removed: boolean;
  student_level_pii_imported: boolean;
  individual_outcome_records_imported: boolean;
  sensitive_demographics_imported: boolean;
  internal_only_fields_exposed: boolean;
  limitations: string[];
  governance_warnings: PartnerImportGovernanceWarning[];
  created_at: string;
};

export type PartnerImportCreateRequest = {
  organization_id: string;
  source_type: PartnerImportSourceType;
  import_format: PartnerImportFormat;
  source_attribution?: string | null;
  content: string;
  original_filename?: string | null;
};

export type PartnerImportActionRequest = {
  reason?: string | null;
};

export type PartnerImportRecordPayload = {
  import_record_id: string;
  import_batch_id: string;
  organization_id: string;
  record_index: number;
  source_type: PartnerImportSourceType;
  record_status: string;
  decision: PartnerImportDecision;
  source_attribution: string;
  employer_name: string | null;
  region_label: string | null;
  confidence: PartnerDataConfidence;
  freshness_status: string;
  partner_payload: Record<string, unknown>;
  evidence: PartnerContributedEvidence;
  validation_warnings: PartnerImportGovernanceWarning[];
  created_at: string;
  updated_at: string;
};

export type PartnerImportBatchPayload = {
  import_batch_id: string;
  organization_id: string;
  uploaded_by_user_id: string;
  source_type: PartnerImportSourceType;
  status: PartnerImportStatus;
  import_format: PartnerImportFormat;
  source_attribution: string;
  original_filename: string | null;
  record_count: number;
  accepted_record_count: number;
  quarantined_record_count: number;
  rejected_record_count: number;
  validation_result: PartnerImportValidationResult;
  receipt: PartnerImportReceipt;
  governance_warnings: PartnerImportGovernanceWarning[];
  records: PartnerImportRecordPayload[];
  preview_records: Array<Record<string, unknown>>;
  created_at: string;
  updated_at: string;
};

export type PartnerImportCreatePayload = {
  partner_import: PartnerImportBatchPayload;
};

export type PartnerImportListPayload = {
  imports: PartnerImportBatchPayload[];
};

export type PartnerImportReceiptPayload = {
  receipt: PartnerImportReceipt;
};

export type ApiScope =
  | "region:read"
  | "company_geography:read"
  | "market_signal:read"
  | "institution_dashboard:read"
  | "exports:create"
  | "imports:create";

export type ApiClientStatus = "active" | "revoked";

export type ApiAccessPolicy = {
  scopes: ApiScope[];
  organization_id: string | null;
  rate_limit_count: number;
  rate_limit_window_seconds: number;
  allowed_origins: string[];
};

export type SafeApiKeyDisplay = {
  api_key_id: string;
  key_prefix: string;
  display_key: string;
  raw_key: string | null;
  revealed_once: boolean;
};

export type ApiClientPayload = {
  api_client_id: string;
  display_name: string;
  created_by_user_id: string;
  organization_id: string | null;
  status: ApiClientStatus;
  policy: ApiAccessPolicy;
  keys: SafeApiKeyDisplay[];
  created_at: string;
  updated_at: string;
};

export type ApiClientCreateRequest = {
  display_name: string;
  scopes: ApiScope[];
  organization_id?: string | null;
  rate_limit_count?: number;
  rate_limit_window_seconds?: number;
  allowed_origins?: string[];
};

export type ApiClientUpdateRequest = {
  scopes?: ApiScope[] | null;
  rate_limit_count?: number | null;
  rate_limit_window_seconds?: number | null;
  status?: ApiClientStatus | null;
};

export type ApiClientCreatePayload = {
  api_client: ApiClientPayload;
};

export type ApiClientListPayload = {
  api_clients: ApiClientPayload[];
};

export type ApiKeyCreatePayload = {
  api_key: SafeApiKeyDisplay;
};

export type ApiUsagePayload = {
  usage_record_id: string;
  api_client_id: string | null;
  api_key_id: string | null;
  route: string;
  method: string;
  scope: string | null;
  decision: string;
  status_code: number;
  rate_limit_limit: number | null;
  rate_limit_remaining: number | null;
  rate_limit_reset_at: string | null;
  occurred_at: string;
};

export type ApiUsageListPayload = {
  usage: ApiUsagePayload[];
};

export type CareerPlatform =
  | "linkedin"
  | "handshake"
  | "university_job_board"
  | "company_career_page"
  | "other_public_career_site";

export type CareerPlatformRiskPosture =
  | "safe_manual"
  | "export_only"
  | "deep_link_only"
  | "official_api_only"
  | "requires_review"
  | "blocked_hostile_tos"
  | "deferred";

export type CareerPlatformRegistryItem = {
  platform: CareerPlatform;
  display_name: string;
  risk_posture: CareerPlatformRiskPosture;
  allowed_capabilities: string[];
  blocked_capabilities: string[];
  notes: string[];
  manual_only: boolean;
  automation_performed: boolean;
  ats_state_created: boolean;
};

export type CareerPlatformRegistryPayload = {
  platforms: CareerPlatformRegistryItem[];
};

export type ExternalCareerLink = {
  url: string;
  label: string;
  platform: CareerPlatform;
  risk_posture: CareerPlatformRiskPosture;
  manual_only: boolean;
  automation_performed: boolean;
  ats_state_created: boolean;
};

export type CareerPlatformReference = {
  reference_id: string;
  platform: CareerPlatform;
  risk_posture: CareerPlatformRiskPosture;
  subject_type: string;
  subject_id: string;
  url: string;
  label: string;
  organization_id: string | null;
  submitted_by_user_id: string;
  manual_only: boolean;
  created_at: string;
};

export type CareerPlatformReferenceCreateRequest = {
  platform: CareerPlatform;
  subject_type: string;
  subject_id: string;
  url: string;
  label?: string | null;
  organization_id?: string | null;
};

export type CareerPlatformReferencePayload = {
  reference: CareerPlatformReference;
};

export type CareerPlatformReferenceListPayload = {
  references: CareerPlatformReference[];
};

export type CareerPlatformExportRequest = {
  platform: CareerPlatform;
  company_ids?: string[];
  employer_names?: string[];
  organization_id?: string | null;
};

export type CareerPlatformExportPayload = {
  export: {
    career_platform_export_id: string;
    platform: CareerPlatform;
    risk_posture: CareerPlatformRiskPosture;
    export_mode: string;
    rows: Array<Record<string, unknown>>;
    manual_only: boolean;
    automation_performed: boolean;
    ats_state_created: boolean;
    application_status_created: boolean;
    recruiter_outreach_created: boolean;
    created_at: string;
  };
};

export type InstitutionDataRequestType =
  | "organization_export"
  | "organization_deletion"
  | "student_export"
  | "student_deletion";

export type InstitutionDataRequestSubjectType = "organization" | "student";
export type InstitutionDataRequestStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "completed"
  | "canceled";

export type InstitutionDataRequestCreateRequest = {
  request_type: InstitutionDataRequestType;
  subject_type?: InstitutionDataRequestSubjectType | null;
  subject_user_id?: string | null;
  reason?: string | null;
  metadata?: Record<string, unknown> | null;
};

export type InstitutionDataRequestPayload = {
  data_request_id: string;
  organization_id: string;
  requester_user_id: string;
  request_type: InstitutionDataRequestType;
  subject_type: InstitutionDataRequestSubjectType;
  subject_user_id: string | null;
  status: InstitutionDataRequestStatus;
  reason: string | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  metadata: Record<string, unknown> | null;
  execution_note: string;
};

export type InstitutionDataRequestCreatePayload = {
  data_request: InstitutionDataRequestPayload;
};

export type InstitutionDataRequestListPayload = {
  data_requests: InstitutionDataRequestPayload[];
};
