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
    career_identity_personalization?: CareerIdentityPersonalizationMetadata;
  };
  error: { code?: string; type?: string; message: string; request_id?: string } | null;
};

export type FreshnessStatus = "fresh" | "stale" | "partial" | "unknown" | "seeded_demo";

export type TrustExplanationWarning = {
  warning_code: string;
  severity: "info" | "warning" | "critical";
  title: string;
  message: string;
};

export type EvidenceRequirementResult = {
  code: string;
  status: "met" | "missing" | "failed" | "not_applicable" | string;
  message: string;
  source: string;
};

export type TrustWarning = {
  warning_code: string;
  severity: "info" | "warning" | "critical";
  message: string;
  source: string;
  evidence_requirement_code: string | null;
};

export type ReportRecheckStatus = {
  subject_type: string;
  subject_id: string;
  latest_report_status: string | null;
  latest_report_type: string | null;
  latest_report_severity: string | null;
  latest_reported_at: string | null;
  active_recheck_job_id: string | null;
  recheck_status: string | null;
  recheck_priority: string | null;
  recheck_outcome: string | null;
  recheck_status_label: string | null;
  exception_status?: ExceptionSubjectStatus | null;
  message: string;
};

export type ExceptionSubjectStatus = {
  subject_type: string;
  subject_id: string;
  has_open_exception: boolean;
  exception_case_id: string | null;
  exception_type: string | null;
  status: string | null;
  severity: string | null;
  public_safe_status: string;
  label: string;
  message: string;
  updated_at: string | null;
  resolved_at: string | null;
};

export type TrustExplanation = {
  subject_type: string;
  subject_id: string;
  trust_tier: string;
  trust_label: string;
  trust_summary: string;
  risk_level: string | null;
  risk_label: string | null;
  risk_summary: string | null;
  routing_outcome: string | null;
  routing_label: string | null;
  routing_summary: string | null;
  ranking_influence_allowed: boolean;
  ranking_influence_decision: string;
  ranking_influence_label: string;
  ranking_influence_reason: string;
  evidence_requirements_met: EvidenceRequirementResult[];
  evidence_requirements_missing: EvidenceRequirementResult[];
  evidence_requirements_failed: EvidenceRequirementResult[];
  trust_warnings: TrustWarning[];
  user_facing_warnings: TrustExplanationWarning[];
  last_checked_at: string | null;
  decided_at: string | null;
  next_recheck_at: string | null;
  report_recheck_status?: ReportRecheckStatus | null;
  exception_status?: ExceptionSubjectStatus | null;
  explanation_version: "30C" | string;
};

export type UserReportType =
  | "outdated"
  | "incorrect"
  | "duplicate"
  | "spam"
  | "misleading"
  | "expired_opportunity"
  | "wrong_company"
  | "wrong_region"
  | "suspicious_ranking"
  | "other";

export type UserReportSeverity = "low" | "medium" | "high" | "critical";

export type UserReportCreateRequest = {
  subject_type: string;
  subject_id: string;
  report_type: UserReportType;
  report_reason?: string | null;
  severity?: UserReportSeverity;
  reporter_session_id?: string | null;
  source_surface?: string | null;
};

export type UserReportPayload = {
  user_report_id: string;
  subject_type: string;
  subject_id: string;
  report_type: string;
  report_reason?: string | null;
  reporter_user_id?: string | null;
  reporter_session_id?: string | null;
  severity: string;
  status: string;
  source_surface: string | null;
  related_trust_assessment_id: string | null;
  related_risk_routing_decision_id: string | null;
  created_recheck_job_id: string | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
};

export type AutomatedRecheckJobPayload = {
  automated_recheck_job_id: string;
  subject_type: string;
  subject_id: string;
  trigger_type: string;
  trigger_source: string;
  status: string;
  priority: string;
  reason_codes: string[];
  related_user_report_id: string | null;
  related_trust_assessment_id: string | null;
  related_risk_routing_decision_id: string | null;
  scheduled_for: string | null;
  started_at: string | null;
  completed_at: string | null;
  outcome: string | null;
  outcome_reason: string | null;
  attempts: number;
  max_attempts: number;
  last_error: string | null;
  created_at: string;
  updated_at: string;
};

export type UserReportSubmissionResult = {
  report: UserReportPayload;
  recheck_job: AutomatedRecheckJobPayload | null;
  status: ReportRecheckStatus;
  message: string;
};

export type DataStandardDefinition = {
  term: string;
  canonical_name: string;
  description: string;
  inclusion_criteria: string[];
  exclusion_criteria: string[];
  examples: string[];
  related_terms: string[];
  version: string;
  status: "active" | "draft" | "deprecated" | string;
};

export type DataStandardDefinitionListPayload = {
  version: string;
  definitions: DataStandardDefinition[];
};

export type PartnerSubmissionSchemaPayload = {
  schema_version: string;
  supported_submitter_types: string[];
  supported_record_types: string[];
  validation_statuses: string[];
  required_submission_fields: string[];
  required_fields_by_record_type: Record<string, string[]>;
  source_refs_required_for_record_types: string[];
  freshness_required: boolean;
  confidence_required: boolean;
};

export type PartnerRegistryRecord = {
  partner_id: string;
  name: string;
  partner_type: string;
  region_scope: string[];
  verification_status: string;
  allowed_submission_types: string[];
  trust_tier: string;
  public_contact_metadata: {
    website_url: string | null;
    contact_page_url: string | null;
    public_contact_label: string | null;
    public_notes: string | null;
  };
  created_at: string;
  updated_at: string;
};

export type PartnerRegistryPayload = {
  version: string;
  supported_partner_types: string[];
  verification_statuses: string[];
  trust_tiers: string[];
  partners: PartnerRegistryRecord[];
};

export type DataQualityLabel = {
  label: string;
  display_name: string;
  description: string;
  allowed_sources: string[];
  minimum_confidence: "high" | "medium" | "low" | "unknown" | string;
  requires_source_refs: boolean;
  requires_partner_verification: boolean;
  ranking_influence_allowed: boolean;
  public_display_allowed: boolean;
  warning_copy: string;
  trust_explanation?: TrustExplanation | null;
  report_recheck_status?: ReportRecheckStatus | null;
  exception_status?: ExceptionSubjectStatus | null;
};

export type DataQualityLabelListPayload = {
  version: string;
  labels: DataQualityLabel[];
};

export type DataQualityCertificationResult = {
  label: DataQualityLabel;
  eligible: boolean;
  certification_status: "eligible" | "not_eligible";
  reasons: string[];
  warnings: string[];
  partner_id: string | null;
  partner_verification_status: string | null;
  partner_trust_tier: string | null;
  source_ref_count: number;
  freshness: Record<string, unknown> | null;
  confidence: Record<string, unknown> | null;
  ranking_influence_allowed: boolean;
  public_display_allowed: boolean;
};

export type GovernanceFrameworkRecord = {
  area: string;
  display_name: string;
  description: string;
  review_questions: string[];
  risk_flags: string[];
  recommended_controls: string[];
  status: "framework_defined" | string;
  version: string;
  public_summary: string;
};

export type GovernanceFrameworkPayload = {
  version: string;
  status: "framework_defined" | string;
  governance_records: GovernanceFrameworkRecord[];
};

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

export type ForecastConfidenceLevel = "high" | "medium" | "low" | "unknown";

export type ForecastConfidenceFactor = {
  code: string;
  severity: "info" | "low" | "medium" | "high";
  explanation: string;
};

export type ForecastConfidence = {
  level: ForecastConfidenceLevel;
  score: number;
  factors: ForecastConfidenceFactor[];
};

export type ForecastSourceBasis = {
  data_basis: string;
  source_categories: string[];
  source_count: number;
  observed_metrics: string[];
  coverage_tiers: string[];
  freshness_states: string[];
  notes: string[];
};

export type ForecastHistoricalDepth = {
  observation_count: number;
  period_count: number;
  window_start: string | null;
  window_end: string | null;
  window_days: number;
  latest_observed_at: string | null;
};

export type ForecastUncertainty = {
  level: "low" | "medium" | "high";
  known_uncertainties: string[];
  limitations: string[];
  bounded: boolean;
};

export type ForecastReasoningStep = {
  code: string;
  summary: string;
};

export type PredictiveAffectedEntity = {
  entity_type: "region" | "company_region" | "sector_region" | string;
  entity_id: string;
  region_id: string | null;
  company_id: string | null;
  sector_id: string | null;
};

export type PredictiveSupportingSignal = {
  signal_key: string;
  signal_kind: "trend" | "emerging_market" | "early_warning" | string;
  signal_type: string;
  signal_status: string;
  summary: string;
};

export type PredictiveReportForecast = {
  forecast_id: string;
  forecast_title: string;
  forecast_label: string;
  forecast_type: string;
  affected_entity: PredictiveAffectedEntity;
  time_horizon: string;
  confidence: ForecastConfidence;
  source_basis: ForecastSourceBasis;
  historical_depth: ForecastHistoricalDepth;
  uncertainty: ForecastUncertainty;
  reasoning_trail: ForecastReasoningStep[];
  supporting_signals: PredictiveSupportingSignal[];
  safe_display_summary: string;
  why_this_forecast_exists: string;
};

export type PredictiveReportSection = {
  section_key: string;
  title: string;
  summary: string;
  why_this_section_exists: string;
  forecasts: PredictiveReportForecast[];
};

export type PredictiveReportPayload = {
  report_id: string;
  report_type: string;
  title: string;
  generated_at: string;
  time_horizon: string;
  forecast_disclaimer: string;
  methodology_summary: string;
  sections: PredictiveReportSection[];
  limitations: string[];
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

export type PolicySeverity = "info" | "low" | "medium" | "high";
export type PolicyConfidenceLevel = "high" | "medium" | "low" | "unknown";
export type PolicyScoreBand =
  | "very_low"
  | "low"
  | "moderate"
  | "high"
  | "very_high"
  | "unknown";

export type PolicyWarning = {
  code: string;
  severity: PolicySeverity;
  message: string;
  public_interpretation: string;
};

export type PolicyConfidenceFactor = {
  code: string;
  severity: PolicySeverity;
  explanation: string;
};

export type PolicyConfidenceMetadata = {
  level: PolicyConfidenceLevel;
  score: number;
  label: string;
  factors: PolicyConfidenceFactor[];
};

export type PolicyFreshnessMetadata = {
  generated_at: string;
  freshness_status: FreshnessStatus;
  freshness_expires_at: string | null;
  stale: boolean;
  notes: string[];
};

export type PolicySourceSummary = {
  data_basis: "canonical_market_truth" | "mixed" | "unknown";
  source_count: number;
  source_categories: string[];
  evidence_summary: string[];
};

export type PolicyPublicSafetyMetadata = {
  public_safe: true;
  redacted_internal_fields: string[];
  student_level_data_exposed: false;
  partner_submission_internals_exposed: false;
  private_review_fields_exposed: false;
};

export type PolicyMetric = {
  metric_id: string;
  label: string;
  score: number | null;
  band: PolicyScoreBand;
  polarity: "higher_is_better" | "higher_is_risk" | "contextual";
  interpretation_label: string;
  explainable_inputs: Record<string, unknown>;
  limitations: string[];
  warning_codes: string[];
};

export type PolicyFinding = {
  finding_id: string;
  finding_type: string;
  severity: PolicySeverity;
  title: string;
  summary: string;
  evidence_references: string[];
  recommended_interpretation: string;
  recommended_actions: string[];
  confidence: PolicyConfidenceLevel;
  limitations: string[];
};

export type PolicyRegionSummary = {
  region_id: string;
  region_name: string;
  region_type: string;
  present_company_count: number;
  hiring_record_count: number;
  entry_level_record_count: number;
  score_available: boolean;
  normalization_basis: string;
};

export type RegionalPolicyMetrics = {
  opportunity_concentration_score: PolicyMetric;
  early_career_access_score: PolicyMetric;
  internship_pipeline_score: PolicyMetric;
  employer_dependency_score: PolicyMetric;
  sector_diversity_score: PolicyMetric;
  talent_export_risk_score: PolicyMetric;
};

export type WorkforceDashboardPayload = {
  region_summary: PolicyRegionSummary;
  core_metrics: RegionalPolicyMetrics;
  policy_findings: PolicyFinding[];
  warnings: PolicyWarning[];
  confidence: PolicyConfidenceMetadata;
  freshness: PolicyFreshnessMetadata;
  source_summary: PolicySourceSummary;
  public_safe: true;
  public_safety: PolicyPublicSafetyMetadata;
};

export type SectorGapFinding = {
  sector: string;
  gap_type: string;
  severity: PolicySeverity;
  evidence_references: string[];
  interpretation: string;
  recommended_strategy_candidate: string;
  confidence: PolicyConfidenceLevel;
  limitations: string[];
};

export type EmployerBaseRiskFinding = {
  risk_type: string;
  severity: PolicySeverity;
  interpretation: string;
  evidence_references: string[];
  strategy_candidate: string;
  confidence: PolicyConfidenceLevel;
  limitations: string[];
};

export type PeerMetricComparison = {
  metric_id: string;
  target_value: number | null;
  peer_value: number | null;
  comparison: "target_stronger" | "target_weaker" | "similar" | "unknown";
};

export type PeerMetroComparison = {
  peer_region_id: string;
  peer_region_name: string;
  similarity_score: number | null;
  similarity_rationale: string;
  metrics_compared: PeerMetricComparison[];
  target_region_stronger: string[];
  target_region_weaker: string[];
  confidence: PolicyConfidenceLevel;
  limitations: string[];
};

export type CompanyAttractionFit = {
  company_id: string;
  company_name: string;
  sector: string | null;
  fit_score: number | null;
  fit_band: PolicyScoreBand;
  fit_rationale: string;
  regional_gap_addressed: string;
  early_career_or_internship_relevance: string;
  diversification_impact: string;
  confidence: PolicyConfidenceLevel;
  limitations: string[];
};

export type DiversificationStrategyCandidate = {
  candidate_type: string;
  title: string;
  rationale: string;
  evidence_references: string[];
  confidence: PolicyConfidenceLevel;
  limitations: string[];
};

export type EconomicDevelopmentProfile = {
  region_id: string;
  region_name: string;
  analysis_window: {
    label: string;
    generated_at: string;
    freshness_expires_at: string | null;
  };
  sector_gap_findings: SectorGapFinding[];
  employer_base_risk_findings: EmployerBaseRiskFinding[];
  peer_metro_comparisons: PeerMetroComparison[];
  company_attraction_candidates: CompanyAttractionFit[];
  diversification_recommendations: DiversificationStrategyCandidate[];
  warnings: PolicyWarning[];
  confidence: PolicyConfidenceMetadata;
  freshness: PolicyFreshnessMetadata;
  source_summary: PolicySourceSummary;
  limitations: string[];
  public_safe: true;
  public_safety: PolicyPublicSafetyMetadata;
};

export type PeerComparisonProfile = {
  region_id: string;
  region_name: string;
  analysis_window: {
    label: string;
    generated_at: string;
    freshness_expires_at: string | null;
  };
  peer_metro_comparisons: PeerMetroComparison[];
  warnings: PolicyWarning[];
  confidence: PolicyConfidenceMetadata;
  freshness: PolicyFreshnessMetadata;
  source_summary: PolicySourceSummary;
  limitations: string[];
  public_safe: true;
  public_safety: PolicyPublicSafetyMetadata;
};

export type InstitutionRegionalPipeline = {
  institution_id: string | null;
  institution_name: string;
  region_id: string;
  program_areas_available: string[];
  related_demand_sectors: string[];
  nearby_early_career_demand_summary: string;
  internship_access_summary: string;
  alignment_confidence: PolicyConfidenceLevel;
  limitations: string[];
};

export type ProgramDemandAlignment = {
  program_area: string;
  nearby_employer_demand: PolicyMetric;
  internship_pipeline_strength: PolicyMetric;
  early_career_access: PolicyMetric;
  alignment_score: number | null;
  alignment_band: PolicyScoreBand;
  finding: string;
  confidence: PolicyConfidenceLevel;
  limitations: string[];
};

export type EducationWorkforceAlignmentProfile = {
  region_id: string;
  region_name: string;
  analysis_window: {
    label: string;
    generated_at: string;
    freshness_expires_at: string | null;
  };
  institution_pipeline_summaries: InstitutionRegionalPipeline[];
  program_alignment_findings: ProgramDemandAlignment[];
  internship_alignment_gaps: SectorGapFinding[];
  local_employer_absorption_score: PolicyMetric;
  talent_export_pressure_score: PolicyMetric;
  student_interest_market_fit: PolicyMetric | null;
  warnings: PolicyWarning[];
  confidence: PolicyConfidenceMetadata;
  freshness: PolicyFreshnessMetadata;
  source_summary: PolicySourceSummary;
  limitations: string[];
  public_safe: true;
  public_safety: PolicyPublicSafetyMetadata;
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
  public_slug?: string | null;
  display_name: string;
  region_type: string;
  parent_region_id: string | null;
  labor_market_group: string | null;
  primary_city?: string | null;
  state_codes?: string[];
  centroid?: { latitude: number; longitude: number } | null;
  focus_bounds?: Record<string, number> | null;
  market_support_status?: "supported" | "unsupported" | "unknown" | string;
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

export type CountStatus =
  | "unknown"
  | "not_collected"
  | "not_applicable"
  | "zero_observed"
  | "positive_observed"
  | "stale"
  | "conflicting"
  | "low_confidence"
  | string;

export type ImportDisplayMetadata = {
  data_basis: "real_imported" | "mixed" | "unknown" | string;
  imported_data: boolean;
  imported_data_label: string;
  source_backed: boolean;
  source_label: string;
  coverage_label: string;
  freshness_status: "current" | "stale" | "unknown" | string;
  freshness_label: string;
  trust_label: string | null;
  risk_label: string | null;
  ranking_influence_allowed: boolean | null;
  ranking_label: string;
};

export type MarketCoverageSummary = {
  market_key: string;
  region_id: string;
  public_slug?: string | null;
  display_name: string;
  primary_city?: string | null;
  state_codes?: string[];
  coverage_status: string;
  import_status: string;
  company_count: number;
  presence_fact_count: number;
  hiring_fact_count: number;
  entry_level_fact_count: number;
  source_count: number;
  freshness_status: FreshnessStatus | string;
  ranking_eligible_fact_count: number;
  ranking_excluded_fact_count: number;
  unknown_count_dimensions: number;
  observed_zero_count_dimensions: number;
  count_status_breakdown: Partial<Record<CountStatus, number>>;
  last_curated_at: string;
  last_import_status: string;
  last_refresh_status: string;
  imported_data_label: string;
  coverage_label: string;
  freshness_label: string;
  source_label: string;
  trust_label: string;
  risk_label: string;
  ranking_label: string;
  comparison_available: boolean;
  comparison_label: string;
};

export type MarketCoverageListPayload = {
  markets: MarketCoverageSummary[];
  market_count: number;
};

export type ImportedMarketHealthStatus =
  | "healthy"
  | "needs_refresh"
  | "limited_coverage"
  | "stale_sources"
  | "validation_failed"
  | "ranking_limited"
  | (string & {});

export type ImportedSourceFreshnessStatus =
  | "current"
  | "aging"
  | "stale"
  | "expired"
  | "needs_review"
  | (string & {});

export type ImportedRefreshReadinessStatus =
  | "ready"
  | "needs_source_refresh"
  | "needs_coverage_expansion"
  | "needs_validation_fix"
  | "needs_ranking_review"
  | "not_ready"
  | (string & {});

export type ImportedGapSeverity =
  | "low"
  | "medium"
  | "high"
  | "critical"
  | (string & {});

export type ImportedDiffRisk =
  | "none"
  | "low"
  | "medium"
  | "high"
  | "blocking"
  | (string & {});

export type ImportedFactArea =
  | "market_identity"
  | "region"
  | "company"
  | "source"
  | "presence"
  | "hiring"
  | "entry_level"
  | (string & {});

export type ImportedMaintenancePriority =
  | "low"
  | "medium"
  | "high"
  | "critical"
  | (string & {});

export type ImportedRankingExclusionCategory =
  | "stale_source"
  | "low_confidence"
  | "insufficient_evidence"
  | "unsupported_freshness"
  | "source_not_allowed"
  | "missing_source"
  | "trust_or_risk_limited"
  | "unassessed"
  | "default_denied"
  | (string & {});

export type ImportedMarketOperationalCounts = {
  company_count: number;
  source_count: number;
  presence_fact_count: number;
  hiring_fact_count: number;
  entry_level_fact_count: number;
  total_fact_count: number;
  unknown_fact_count: number;
  observed_zero_fact_count: number;
  ranking_eligible_fact_count: number;
  ranking_excluded_fact_count: number;
  stale_fact_count: number;
  stale_source_count: number;
};

export type ImportedMarketPlatformSummary = {
  registered_market_count: number;
  healthy_market_count: number;
  markets_needing_refresh: number;
  markets_with_limited_coverage: number;
  markets_with_stale_sources: number;
  total_stale_source_count: number;
  total_ranking_excluded_fact_count: number;
  highest_priority_maintenance_market: string | null;
  recommended_next_maintenance_action: string;
  overall_health_status: ImportedMarketHealthStatus;
};

export type ImportedDatasetHealthReport = {
  market_key: string;
  market_name: string;
  validation_ok: boolean;
  missing_required_files: string[];
  counts: ImportedMarketOperationalCounts;
  oldest_source_age_days: number | null;
  newest_source_age_days: number | null;
  coverage_summary: string;
  freshness_summary: string;
  health_status: ImportedMarketHealthStatus;
  reasons: string[];
  recommended_next_action: string;
};

export type ImportedMarketHealthOverviewPayload = {
  summary: ImportedMarketPlatformSummary;
  markets: ImportedDatasetHealthReport[];
};

export type ImportedSourceDiagnostic = {
  source_id: string;
  source_label: string;
  source_type: string;
  data_origin?: string;
  observed_date: string | null;
  collected_date: string | null;
  age_days: number | null;
  freshness_status: ImportedSourceFreshnessStatus;
  is_stale: boolean;
  license_or_terms_category: string | null;
  fact_usage_count: number;
  affected_areas: string[];
  affects_ranking_eligibility: boolean;
  impact: string;
};

export type ImportedSourceAgingReport = {
  market_key: string;
  source_count: number;
  stale_source_count: number;
  aging_source_count: number;
  expired_source_count: number;
  oldest_source_age_days: number | null;
  newest_source_age_days: number | null;
  oldest_sources: ImportedSourceDiagnostic[];
  greatest_fact_impact_sources: ImportedSourceDiagnostic[];
  important_stale_sources: ImportedSourceDiagnostic[];
  sources: ImportedSourceDiagnostic[];
};

export type ImportedFactHealthFinding = {
  fact_type: string;
  fact_id: string;
  company_id: string | null;
  region_id: string | null;
  area: ImportedFactArea;
  ranking_eligible: boolean;
  ranking_excluded_reasons: string[];
  freshness_status: string;
  confidence: string;
  observation_status: string;
  source_count: number;
  public_message: string;
};

export type ImportedFactHealthReport = {
  market_key: string;
  total_facts: number;
  ranking_eligible_facts: number;
  ranking_excluded_facts: number;
  stale_facts: number;
  low_confidence_facts: number;
  unknown_facts: number;
  observed_zero_facts: number;
  missing_useful_dimension_facts: number;
  weak_source_coverage_facts: number;
  trust_or_risk_limited_facts: number;
  limiting_categories: string[];
  findings: ImportedFactHealthFinding[];
};

export type ImportedCoverageGap = {
  gap_code: string;
  severity: ImportedGapSeverity;
  market_key: string;
  affected_area: ImportedFactArea;
  message: string;
  supporting_counts: Record<string, number | string | null>;
  recommended_action: string;
  estimated_impact: string;
};

export type ImportedCoverageGapReport = {
  market_key: string;
  gap_count: number;
  highest_severity: ImportedGapSeverity | null;
  gaps: ImportedCoverageGap[];
};

export type ImportedRankingExclusionDiagnostic = {
  fact_type: string;
  fact_id: string;
  area: ImportedFactArea;
  reason_categories: ImportedRankingExclusionCategory[];
  explanation: string;
};

export type ImportedRankingExclusionReport = {
  market_key: string;
  excluded_fact_count: number;
  total_fact_count: number;
  ranking_limited_ratio: number;
  affected_areas: string[];
  reason_counts: Record<string, number>;
  stale_source_exclusion_count: number;
  low_confidence_exclusion_count: number;
  insufficient_evidence_exclusion_count: number;
  unsupported_freshness_exclusion_count: number;
  trust_or_risk_limitation_count: number;
  diagnostics: ImportedRankingExclusionDiagnostic[];
};

export type ImportedRefreshReadinessReport = {
  market_key: string;
  readiness_status: ImportedRefreshReadinessStatus;
  blocking_conditions: string[];
  warnings: string[];
  recommended_next_action: string;
  ordered_actions: string[];
  reasons: string[];
  expected_impact: string;
  maintenance_priority: ImportedMaintenancePriority;
  priority_score: number;
};

export type ImportedDiffChange = {
  area: ImportedFactArea;
  change_type: string;
  record_id: string;
  field: string | null;
  before: unknown;
  after: unknown;
  message: string;
};

export type ImportedDiffWarning = {
  code: string;
  severity: ImportedDiffRisk;
  area: ImportedFactArea;
  record_id: string | null;
  message: string;
};

export type ImportedDiffPreview = {
  market_key: string;
  validation_ok: boolean;
  overall_diff_risk: ImportedDiffRisk;
  risk_reasons: string[];
  blocking_issues: ImportedDiffWarning[];
  warnings: ImportedDiffWarning[];
  summary_counts: Record<string, number>;
  narrative_summary: string;
  changes: ImportedDiffChange[];
};

export type ImportedMarketOperationDetails = {
  sources: ImportedSourceAgingReport;
  facts: ImportedFactHealthReport;
  gaps: ImportedCoverageGapReport;
  ranking: ImportedRankingExclusionReport;
  readiness: ImportedRefreshReadinessReport;
  diff: ImportedDiffPreview;
};

export type ImportedMarketOperationsViewPayload = {
  overview: ImportedMarketHealthOverviewPayload;
  details_by_market: Record<string, ImportedMarketOperationDetails>;
};

export type MarketIntelligenceGoal =
  | "software_engineering"
  | "product_management"
  | "ai_ml"
  | "cybersecurity"
  | "data_science"
  | (string & {});

export type MarketIntelligenceConfidence =
  | "high"
  | "moderate"
  | "low"
  | "limited"
  | (string & {});

export type MarketIntelligenceFreshness =
  | "current"
  | "aging"
  | "stale"
  | "unknown"
  | (string & {});

export type MarketComparisonOutcome =
  | "market_a"
  | "market_b"
  | "tie"
  | "no_winner"
  | (string & {});

export type MarketEvidenceSufficiency =
  | "comparison_ready"
  | "limited_evidence"
  | "insufficient_evidence"
  | "not_supported"
  | (string & {});

export type MarketEvidenceBasis =
  | "direct"
  | "proxy"
  | "direct_and_proxy"
  | "no_qualifying_evidence"
  | (string & {});

export type MarketRankingStabilityStatus =
  | "stable"
  | "sensitive"
  | "unstable"
  | "indeterminate"
  | (string & {});

export type MarketContradictionStatus =
  | "clear"
  | "warnings"
  | "blocking"
  | (string & {});

export type MarketContradictionSeverity =
  | "warning"
  | "blocking"
  | (string & {});

export type MarketContradictionCode =
  | "high_confidence_insufficient_evidence"
  | "strong_internship_missing_evidence"
  | "current_freshness_stale_primary_source"
  | "winner_with_lower_score"
  | "opposite_weakness_and_driver"
  | "specific_role_recommendation_without_direct_evidence"
  | "comparison_ready_without_qualifying_evidence"
  | "no_limitations_despite_critical_gaps"
  | "alphabetical_tie_displayed_as_winner"
  | (string & {});

export type MarketContradictionFinding = {
  code: MarketContradictionCode;
  severity: MarketContradictionSeverity;
  message: string;
  evidence: string;
  blocks_recommendation: boolean;
};

export type MarketIntelligenceGoalDefinition = {
  goal: MarketIntelligenceGoal;
  label: string;
  description: string;
  direct_signals: string[];
  limitations: string[];
};

export type MarketIntelligenceInsight = {
  code: string;
  message: string;
  evidence: string;
  impact: string;
};

export type MarketOpportunityEnvironment = {
  hiring_activity: string;
  employer_diversity: string;
  internship_ecosystem: string;
  coop_ecosystem: string;
  early_career_support: string;
  hiring_momentum: string;
  overall: string;
};

export type MarketIntelligenceSupportingMetrics = Record<
  string,
  number | string | null | undefined
>;

export type MarketEvidenceGrounding = {
  evidence_areas_used: string[];
  evidence_areas_missing: string[];
  direct_evidence_summary: string[];
  proxy_evidence_summary: string[];
  freshness: MarketIntelligenceFreshness;
  coverage: string;
  excluded_fact_summary: string;
  confidence_constraints: string[];
  score_margin: number | null;
  stability_status: MarketRankingStabilityStatus;
  stability_scenarios?: MarketRobustnessScenarioResult[];
};

export type MarketRobustnessScenarioRankingResult = {
  market_key: string;
  rank: number;
  score: number;
  confidence: MarketIntelligenceConfidence;
  freshness: MarketIntelligenceFreshness;
  evidence_sufficiency: MarketEvidenceSufficiency;
  top_market_key: string | null;
};

export type MarketRobustnessScenarioResult = {
  scenario: string;
  label: string;
  status: MarketRankingStabilityStatus;
  baseline_result: MarketRobustnessScenarioRankingResult;
  scenario_result: MarketRobustnessScenarioRankingResult;
  rank_change: number;
  winner_change: boolean;
  score_delta: number;
  confidence_delta: number;
  sufficiency_delta: string;
  explanation: string;
};

export type MarketIntelligenceProfile = {
  market_key: string;
  market_name: string;
  region_id: string;
  overview: string;
  strengths: MarketIntelligenceInsight[];
  weaknesses: MarketIntelligenceInsight[];
  hiring_summary: string;
  employer_summary: string;
  internship_summary: string;
  coop_summary: string;
  early_career_summary: string;
  opportunity_environment: MarketOpportunityEnvironment;
  confidence: MarketIntelligenceConfidence;
  confidence_score: number;
  freshness: MarketIntelligenceFreshness;
  coverage_summary: string;
  limitations: string[];
  supporting_metrics: MarketIntelligenceSupportingMetrics;
  grounding: MarketEvidenceGrounding | null;
};

export type MarketRankingDriver = {
  code: string;
  label: string;
  contribution: number;
  evidence: string;
};

export type ExplainableRankingItem = {
  rank: number;
  market_key: string;
  market_name: string;
  goal: MarketIntelligenceGoal;
  score: number;
  raw_score: number;
  confidence: MarketIntelligenceConfidence;
  freshness: MarketIntelligenceFreshness;
  ranking_drivers: MarketRankingDriver[];
  strengths: string[];
  weaknesses: string[];
  limitations: string[];
  supporting_metrics: MarketIntelligenceSupportingMetrics;
  evidence_sufficiency: MarketEvidenceSufficiency;
  evidence_basis: MarketEvidenceBasis;
  is_provisional: boolean;
  abstention_reason: string | null;
  contradiction_status: MarketContradictionStatus;
  contradictions: MarketContradictionFinding[];
  grounding: MarketEvidenceGrounding | null;
};

export type ExplainableRankingReport = {
  goal: MarketIntelligenceGoal;
  goal_definition: MarketIntelligenceGoalDefinition;
  ranked_markets: ExplainableRankingItem[];
  top_market_key: string | null;
  explanation: string;
  limitations: string[];
  tie_breaker: string;
  evidence_sufficiency: MarketEvidenceSufficiency;
  is_provisional: boolean;
  abstention_reason: string | null;
  contradiction_status: MarketContradictionStatus;
  contradictions: MarketContradictionFinding[];
  grounding: MarketEvidenceGrounding | null;
};

export type MarketComparisonSide = {
  market_key: string;
  market_name: string;
  score: number;
  confidence: MarketIntelligenceConfidence;
  strengths: string[];
  weaknesses: string[];
  supporting_metrics: MarketIntelligenceSupportingMetrics;
  evidence_sufficiency: MarketEvidenceSufficiency;
  evidence_basis: MarketEvidenceBasis;
  grounding: MarketEvidenceGrounding | null;
};

export type MarketComparisonReport = {
  goal: MarketIntelligenceGoal;
  market_a: MarketComparisonSide;
  market_b: MarketComparisonSide;
  outcome: MarketComparisonOutcome;
  winner_market_key: string | null;
  explanation: string;
  confidence: MarketIntelligenceConfidence;
  supporting_metrics: MarketIntelligenceSupportingMetrics;
  limitations: string[];
  evidence_sufficiency: MarketEvidenceSufficiency;
  is_provisional: boolean;
  abstention_reason: string | null;
  contradiction_status: MarketContradictionStatus;
  contradictions: MarketContradictionFinding[];
  grounding: MarketEvidenceGrounding | null;
};

export type CareerGoalComparisonReport = {
  goal: MarketIntelligenceGoal;
  goal_definition: MarketIntelligenceGoalDefinition;
  ranking: ExplainableRankingReport;
  recommended_market_key: string | null;
  recommendation_summary: string;
  confidence: MarketIntelligenceConfidence;
  limitations: string[];
  evidence_sufficiency: MarketEvidenceSufficiency;
  is_provisional: boolean;
  abstention_reason: string | null;
  contradiction_status: MarketContradictionStatus;
  contradictions: MarketContradictionFinding[];
  grounding: MarketEvidenceGrounding | null;
};

export type PlatformMarketIntelligencePayload = {
  market_count: number;
  profile_count: number;
  supported_goals: MarketIntelligenceGoalDefinition[];
  profiles: MarketIntelligenceProfile[];
  default_ranking: ExplainableRankingReport;
  highest_confidence_market: string | null;
  public_summary: string;
  limitations: string[];
};

export type RegionCompany = {
  company_id: string;
  company_name: string;
  sector_primary: string | null;
  eligibility_status: string | null;
  is_major_tech: boolean;
  is_mag7: boolean;
  prestige_score: number | null;
  import_metadata?: ImportDisplayMetadata | null;
};

export type HiringCompany = {
  company_id: string;
  company_name: string;
  currently_hiring_flag: boolean;
  active_posting_count_now: number | null;
  active_posting_count_now_status?: CountStatus | null;
  posting_count_30d: number | null;
  posting_count_30d_status?: CountStatus | null;
  posting_count_90d: number | null;
  posting_count_90d_status?: CountStatus | null;
  import_metadata?: ImportDisplayMetadata | null;
};

export type EntryLevelSummary = {
  internship_count_total?: number | null;
  internship_count_total_status?: CountStatus | null;
  coop_count_total?: number | null;
  coop_count_total_status?: CountStatus | null;
  entry_level_full_time_count_total?: number | null;
  entry_level_full_time_count_total_status?: CountStatus | null;
  formal_early_career_program_count?: number | null;
  average_entry_level_access_score?: number | null;
  pairs_with_entry_level_access?: number | null;
};

export type RegionDetail = {
  region_id: string;
  public_slug?: string | null;
  display_name: string;
  region_type: string;
  parent_region_id: string | null;
  labor_market_group: string | null;
  primary_city?: string | null;
  state_codes?: string[];
  centroid?: { latitude: number; longitude: number } | null;
  focus_bounds?: Record<string, number> | null;
  market_support_status?: "supported" | "unsupported" | "unknown" | string;
  coverage?: CoverageMetadata;
  sector_coverage?: SectorCoverageMap;
  priority_market?: PriorityMarket | null;
  summary?: Record<string, number>;
  scores: RegionScores | null;
  import_metadata?: ImportDisplayMetadata | null;
  top_companies_present?: RegionCompany[];
  top_companies_hiring?: HiringCompany[];
  entry_level_summary?: EntryLevelSummary;
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
  import_metadata?: ImportDisplayMetadata | null;
  regions_present?: Array<{
    region_id: string;
    region_display_name: string;
    presence_status: string;
    presence_basis: string | null;
    presence_confidence: string | null;
    import_metadata?: ImportDisplayMetadata | null;
    coverage?: CoverageMetadata;
    sector_coverage?: SectorCoverageMap;
    priority_market?: PriorityMarket | null;
  }>;
  regions_hiring?: Array<{
    region_id: string;
    region_display_name: string;
    currently_hiring_flag: boolean;
    active_posting_count_now: number | null;
    active_posting_count_now_status?: CountStatus | null;
    posting_count_30d: number | null;
    posting_count_30d_status?: CountStatus | null;
    posting_count_90d: number | null;
    posting_count_90d_status?: CountStatus | null;
    import_metadata?: ImportDisplayMetadata | null;
    coverage?: CoverageMetadata;
    sector_coverage?: SectorCoverageMap;
    priority_market?: PriorityMarket | null;
  }>;
  entry_level_regions?: Array<{
    region_id: string;
    region_display_name: string;
    internship_count: number | null;
    internship_count_status?: CountStatus | null;
    coop_count: number | null;
    coop_count_status?: CountStatus | null;
    entry_level_full_time_count: number | null;
    entry_level_full_time_count_status?: CountStatus | null;
    formal_early_career_program_flag: boolean;
    entry_level_access_score: number | null;
    entry_level_confidence: string | null;
    import_metadata?: ImportDisplayMetadata | null;
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
    import_metadata?: ImportDisplayMetadata | null;
    coverage?: CoverageMetadata;
    sector_coverage?: SectorCoverageMap;
    priority_market?: PriorityMarket | null;
  };
  region_b?: {
    region_id: string;
    display_name: string;
    scores: RegionScores | null;
    import_metadata?: ImportDisplayMetadata | null;
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

export type CareerIdentityFactType =
  | "education"
  | "experience"
  | "skill"
  | "project"
  | "credential"
  | "career_goal"
  | "role_preference"
  | "industry_preference"
  | "geographic_constraint"
  | "compensation_constraint"
  | "timing_preference"
  | "work_arrangement_preference";

export type CareerIdentityFactState = "explicit" | "imported" | "inferred" | "confirmed";

export type CareerIdentityFact = {
  career_identity_fact_id: string;
  fact_type: CareerIdentityFactType;
  normalized_key: string;
  state: CareerIdentityFactState;
  payload: Record<string, unknown>;
  provenance: Record<string, unknown>;
  source_import_id: string | null;
  source_label: string | null;
  confirmed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type CareerIdentityPrivacy = {
  ingestion_consent_granted: boolean;
  inference_consent_granted: boolean;
  downstream_personalization_consent_granted: boolean;
  retain_import_metadata: boolean;
  privacy_visibility: "private" | string;
};

export type CareerIdentityCompletenessSection = {
  section: string;
  score: number;
  status: string;
  present_signals: string[];
  missing_signals: string[];
  weak_signals: string[];
  reason_codes: string[];
};

export type CareerIdentityCompleteness = {
  identity_version: number;
  overall_score: number;
  completeness_state: "empty" | "minimal" | "partial" | "complete" | string;
  sufficiency_state: "insufficient" | "sufficient" | string;
  sufficient: boolean;
  strong_required_signal_count: number;
  sections: CareerIdentityCompletenessSection[];
  missing_categories: string[];
  weak_categories: string[];
  actionable_reason_codes?: string[];
};

export type CareerIdentity = {
  career_identity_id: string;
  user_id: string;
  current_version: number;
  completeness_state: string;
  sufficiency_state: string;
  privacy: CareerIdentityPrivacy;
  completeness: CareerIdentityCompleteness | null;
  facts: Record<CareerIdentityFactType, CareerIdentityFact[]>;
  created_at: string;
  updated_at: string;
};

export type CareerIdentityFactInput = {
  fact_type: CareerIdentityFactType;
  payload: Record<string, unknown>;
  state?: CareerIdentityFactState;
  provenance?: {
    source_type?: string | null;
    source_label?: string | null;
    source_ref?: string | null;
    extraction_method?: string | null;
    confidence?: string | null;
    notes?: string | null;
  } | null;
  normalized_key?: string | null;
  expected_version?: number | null;
};

export type CareerIdentityFactUpdateInput = {
  payload?: Record<string, unknown> | null;
  state?: CareerIdentityFactState | null;
  provenance?: CareerIdentityFactInput["provenance"];
  normalized_key?: string | null;
  expected_version?: number | null;
};

export type CareerIdentityPrivacyInput = Partial<Omit<CareerIdentityPrivacy, "privacy_visibility">> & {
  expected_version?: number | null;
};

export type CareerIdentityIngestionRequest = {
  source_type: "resume_text" | "profile_text" | "structured_profile";
  source_label?: string | null;
  text?: string | null;
  structured_profile?: Record<string, unknown> | null;
  consent_granted: boolean;
  expected_version?: number | null;
};

export type CareerIdentityIngestionResult = {
  career_identity_import_id: string | null;
  identity_version: number;
  status: "completed" | "failed" | "duplicate";
  imported_fact_count: number;
  created_fact_count: number;
  updated_fact_count: number;
  protected_fact_count: number;
  duplicate_fact_count: number;
  diagnostics: Array<Record<string, unknown>>;
  completeness: CareerIdentityCompleteness;
};

export type CareerIdentityFactMutationResult = {
  career_identity_fact_id: string;
  outcome: string;
  version_changed: boolean;
  identity: CareerIdentity;
};

export type CareerIdentityPrivacyPayload = {
  career_identity_id: string;
  identity_version: number;
  privacy: CareerIdentityPrivacy;
};

export type CareerDecisionType =
  | "role_choice"
  | "company_choice"
  | "location_choice"
  | "career_strategy"
  | "job_search_strategy"
  | "education_skill_investment"
  | "offer_comparison"
  | "career_path";

export type CareerDecisionStatus =
  | "draft"
  | "evaluating"
  | "decided"
  | "reconsidering"
  | "completed"
  | "abandoned";

export type DecisionOptionStatus = "active" | "selected" | "rejected" | "archived";
export type DecisionRecommendationStatus = "ready" | "abstained";
export type EvidenceSufficiency =
  | "comparison_ready"
  | "limited_evidence"
  | "insufficient_evidence"
  | "not_supported";
export type CareerDecisionConfidence = "high" | "medium" | "low" | "unknown";
export type CareerActionStatus = "open" | "in_progress" | "completed" | "skipped" | "blocked";
export type CareerActionType =
  | "research"
  | "application"
  | "skill_work"
  | "company_targeting"
  | "networking_follow_up"
  | "preparation"
  | "timing_checkpoint"
  | "review_task"
  | "other";
export type CareerApplicationStatus =
  | "considering"
  | "preparing"
  | "applied"
  | "response"
  | "interview"
  | "final_round"
  | "rejected"
  | "withdrawn"
  | "offer"
  | "accepted"
  | "declined";
export type CareerOutcomeType =
  | "application_progress"
  | "offer"
  | "rejection"
  | "withdrawal"
  | "skill_development"
  | "research_completed"
  | "networking"
  | "strategy_change"
  | "education"
  | "decision_completed"
  | "other";
export type CareerOutcomeStatus = "observed" | "reflected" | "superseded";

export type CareerDecisionPriorityInput = {
  key: string;
  label?: string | null;
  weight?: number | null;
  hard?: boolean;
};

export type CareerDecisionConstraintInput = {
  key: string;
  field: string;
  operator?: string;
  value: unknown;
  hard?: boolean;
  label?: string | null;
};

export type CareerDecisionOptionInput = {
  title: string;
  description?: string | null;
  scenario?: Record<string, unknown>;
  position?: number;
};

export type CareerDecisionCreateInput = {
  decision_type: CareerDecisionType;
  title: string;
  description?: string | null;
  target_date?: string | null;
  planned_review_at?: string | null;
  time_horizon?: string | null;
  priorities?: CareerDecisionPriorityInput[];
  constraints?: CareerDecisionConstraintInput[];
  options?: CareerDecisionOptionInput[];
};

export type CareerDecisionUpdateInput = Partial<Omit<CareerDecisionCreateInput, "decision_type" | "options">> & {
  status?: CareerDecisionStatus | null;
  user_note?: string | null;
};

export type CareerDecisionContext = {
  context_snapshot_id: string;
  career_identity_id: string;
  career_identity_version: number;
  completeness_state: string;
  sufficiency_state: string;
  privacy_scope: string;
  context: Record<string, unknown>;
  fact_refs: Array<Record<string, unknown>>;
  created_at: string;
};

export type CareerDecisionOption = {
  option_id: string;
  decision_id: string;
  title: string;
  description: string | null;
  scenario: Record<string, unknown>;
  status: DecisionOptionStatus;
  position: number;
  created_at: string;
  updated_at: string;
};

export type DecisionChallenge = {
  code: string;
  severity: "info" | "warning" | "critical" | string;
  message: string;
  scope_type?: string | null;
  scope_id?: string | null;
  details?: Record<string, unknown>;
};

export type DecisionFitOption = {
  option_id: string;
  title?: string;
  assessment?: string;
  confidence?: CareerDecisionConfidence | string;
  dimensions?: Array<Record<string, unknown>>;
  constraints?: Array<Record<string, unknown>>;
  hard_violations?: Array<Record<string, unknown>>;
  advantages?: string[];
  disadvantages?: string[];
  tradeoffs?: string[];
  important_unknowns?: Array<string | Record<string, unknown>>;
  [key: string]: unknown;
};

export type DecisionRecommendation = {
  recommendation_id: string;
  decision_id: string;
  context_snapshot_id: string;
  recommended_option_id: string | null;
  recommendation_status: DecisionRecommendationStatus;
  evidence_sufficiency: EvidenceSufficiency;
  confidence: CareerDecisionConfidence;
  summary: string | null;
  fit: {
    options?: DecisionFitOption[];
    [key: string]: unknown;
  };
  comparison: Record<string, unknown>;
  evidence: {
    supporting?: Array<Record<string, unknown>>;
    contrary?: Array<Record<string, unknown>>;
    unavailable?: Array<Record<string, unknown>>;
    [key: string]: unknown;
  };
  challenges: DecisionChallenge[];
  limitations: string[];
  generated_at: string;
};

export type CareerAction = {
  action_id: string;
  action_plan_id: string | null;
  decision_id: string | null;
  option_id: string | null;
  action_type: CareerActionType;
  status: CareerActionStatus;
  title: string;
  description: string | null;
  due_at: string | null;
  priority: number | null;
  position: number;
  completed_at: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type CareerActionInput = {
  action_type: CareerActionType;
  title: string;
  description?: string | null;
  option_id?: string | null;
  due_at?: string | null;
  priority?: number | null;
  position?: number;
  metadata?: Record<string, unknown>;
};

export type CareerActionPlan = {
  action_plan_id: string;
  decision_id: string;
  selected_option_id: string | null;
  title: string;
  status: "active" | "completed" | "archived";
  plan: Record<string, unknown>;
  actions: CareerAction[];
  created_at: string;
  updated_at: string;
};

export type CareerApplicationTransition = {
  transition_id: string;
  application_id: string;
  from_status: CareerApplicationStatus | null;
  to_status: CareerApplicationStatus;
  reason: string | null;
  metadata: Record<string, unknown>;
  transitioned_at: string;
};

export type CareerApplication = {
  application_id: string;
  decision_id: string | null;
  action_id: string | null;
  option_id: string | null;
  company_id: string | null;
  region_id: string | null;
  role_title: string | null;
  status: CareerApplicationStatus;
  status_started_at: string;
  applied_at: string | null;
  follow_up_at: string | null;
  source_url: string | null;
  notes: string | null;
  metadata: Record<string, unknown>;
  transitions: CareerApplicationTransition[];
  created_at: string;
  updated_at: string;
};

export type CareerApplicationCreateInput = {
  decision_id?: string | null;
  action_id?: string | null;
  option_id?: string | null;
  company_id?: string | null;
  region_id?: string | null;
  role_title?: string | null;
  status?: CareerApplicationStatus;
  applied_at?: string | null;
  follow_up_at?: string | null;
  source_url?: string | null;
  notes?: string | null;
  metadata?: Record<string, unknown>;
};

export type MySearchPursuitOption = {
  option_id: string;
  title: string;
  region_id: string | null;
  public_slug: string | null;
};

export type MySearchAction = {
  action_id: string;
  action_type: CareerActionType;
  status: CareerActionStatus;
  title: string;
  description: string | null;
  due_at: string | null;
  priority: number | null;
  completed_at: string | null;
  updated_at: string;
};

export type MySearchApplication = {
  application_id: string;
  decision_id: string | null;
  company_id: string | null;
  company_name: string;
  region_id: string | null;
  market_name: string | null;
  role_title: string;
  status: CareerApplicationStatus;
  applied_at: string | null;
  follow_up_at: string | null;
  source_url: string | null;
  current_opportunity_id: string | null;
  needs_attention: boolean;
  attention_reason: string | null;
  created_at: string;
  updated_at: string;
};

export type MySearchSourceComparison = {
  comparison_id: string;
  compared_markets: string[];
  system_recommendation: string[];
  original_user_choice: string;
  original_choice_matches_recommendation: boolean | null;
  current_user_choice: string;
  current_choice_matches_recommendation: boolean | null;
  recommendation_state: string;
  recommendation_summary: string | null;
  generated_at: string | null;
};

export type MySearchOpportunitySummary = {
  market_id: string | null;
  coverage_status: string;
  coverage_rationale: string;
  coverage_limitations: string[];
  observed_active_count: number;
  ranking_eligible_count: number;
  fresh_count: number;
  latest_observed_at: string | null;
  top_opportunities: Array<{
    opportunity_id: string;
    company_name: string;
    role_title: string;
    freshness_state: string;
    ranking_eligible: boolean;
    application_url_available: boolean;
  }>;
};

export type MySearchPursuit = {
  decision_id: string;
  decision_type: CareerDecisionType;
  status: CareerDecisionStatus;
  title: string;
  selected_priority: MySearchPursuitOption;
  alternatives: MySearchPursuitOption[];
  target_context: string | null;
  prioritized_at: string | null;
  next_action: MySearchAction | null;
  open_action_count: number;
  completed_action_count: number;
  applications: MySearchApplication[];
  active_application_count: number;
  applications_needing_attention: number;
  source_comparison: MySearchSourceComparison | null;
  current_opportunities: MySearchOpportunitySummary;
  latest_meaningful_update_at: string;
};

export type MySearchSavedComparison = {
  comparison_id: string;
  market_names: string[];
  context_summary: string;
  recommendation_state: string;
  recommendation_summary: string;
  winner_region_ids: string[];
  generated_at: string;
  saved_at: string;
};

export type MySearchSavedItem = {
  saved_artifact_id: string;
  artifact_type: string;
  artifact_ref: string;
  label: string | null;
  notes: string | null;
  region_id: string | null;
  public_slug: string | null;
  display_name: string | null;
  created_at: string;
};

export type MySearchHistoryItem = {
  history_id: string;
  kind: string;
  title: string;
  detail: string | null;
  occurred_at: string;
  decision_id: string | null;
  application_id: string | null;
};

export type MySearchWorkspace = {
  active_pursuits: MySearchPursuit[];
  applications: MySearchApplication[];
  saved_comparisons: MySearchSavedComparison[];
  saved_items: MySearchSavedItem[];
  history: MySearchHistoryItem[];
  generated_at: string;
};

export type TrackOpportunityResult = {
  application: MySearchApplication;
  created: boolean;
  external_application_url: string | null;
};

export type CareerOutcome = {
  outcome_id: string;
  decision_id: string | null;
  action_id: string | null;
  application_id: string | null;
  option_id: string | null;
  recommendation_id: string | null;
  outcome_type: CareerOutcomeType;
  status: CareerOutcomeStatus;
  title: string;
  description: string | null;
  occurred_at: string;
  reflection: string | null;
  evidence: Record<string, unknown>;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type CareerOutcomeCreateInput = {
  outcome_type: CareerOutcomeType;
  title: string;
  status?: CareerOutcomeStatus;
  decision_id?: string | null;
  action_id?: string | null;
  application_id?: string | null;
  option_id?: string | null;
  recommendation_id?: string | null;
  description?: string | null;
  occurred_at?: string | null;
  reflection?: string | null;
  evidence?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
};

export type RecommendationFeedbackCreateInput = {
  decision_id: string;
  recommendation_id: string;
  useful: boolean;
  surprising: boolean;
  changed_decision: boolean;
  missing_alternative: boolean;
  missing_alternative_category?: string | null;
  confidence_calibration: "too_high" | "too_low" | "about_right" | "unsure";
  feedback_comment?: string | null;
  cohort_key?: string | null;
  experiment_key?: string | null;
  variant_key?: string | null;
};

export type RecommendationFeedback = RecommendationFeedbackCreateInput & {
  feedback_id: string;
  user_id: string;
  created_at: string;
  updated_at: string;
};

export type DecisionReflectionCreateInput = {
  decision_id: string;
  recommendation_id?: string | null;
  outcome_id?: string | null;
  would_make_same_decision: "yes" | "no" | "unsure" | "not_applicable";
  view_changed: boolean;
  satisfaction_rating?: number | null;
  regret_level?: "none" | "low" | "medium" | "high" | "unsure" | null;
  reflection_comment?: string | null;
};

export type DecisionReflection = DecisionReflectionCreateInput & {
  reflection_id: string;
  user_id: string;
  created_at: string;
  updated_at: string;
};

export type StrategyChangeCreateInput = {
  decision_id?: string | null;
  recommendation_id?: string | null;
  change_type: "target_role" | "geography" | "company_strategy" | "opportunity_type" | "application_strategy" | "other";
  previous_state?: Record<string, unknown> | null;
  new_state: Record<string, unknown>;
  reason_category?: string | null;
  note?: string | null;
};

export type StrategyChange = StrategyChangeCreateInput & {
  strategy_change_id: string;
  user_id: string;
  occurred_at: string;
  created_at: string;
  updated_at: string;
};

export type SupportCaseType =
  | "product_issue"
  | "bad_data"
  | "recommendation_issue"
  | "privacy_issue"
  | "account_access_issue"
  | "billing_issue"
  | "other";

export type SupportCaseCreateInput = {
  case_type: SupportCaseType;
  title: string;
  description?: string | null;
  subject_type?: string | null;
  subject_id?: string | null;
  decision_id?: string | null;
  recommendation_id?: string | null;
  current_opportunity_id?: string | null;
  privacy_request_type?: string | null;
  priority?: string;
};

export type SupportCase = SupportCaseCreateInput & {
  support_case_id: string;
  user_id: string;
  status: "open" | "investigating" | "awaiting_user" | "resolved" | "closed";
  assigned_operator_id: string | null;
  resolution: string | null;
  resolved_at: string | null;
  closed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type FeatureAccessDecision = {
  feature_key: string;
  allowed: boolean;
  reason: string;
  cohort_keys: string[];
  access_mode: string | null;
  entitlement_source: string | null;
  configuration: Record<string, unknown>;
};

export type BetaAccessPayload = {
  cohorts: Array<{
    cohort_key: string;
    name: string;
    status: string;
    membership_status: string;
    configuration: Record<string, unknown>;
  }>;
  feature_gates: Array<Record<string, unknown>>;
};

export type CommercialExperimentSignalCreateInput = {
  experiment_key: string;
  variant_key: string;
  offer_key: "one_time_decision_report" | "active_search_subscription" | "premium_scenarios" | "university_advisor_access";
  signal_type: "exposed" | "interested" | "not_interested" | "learn_more" | "converted" | "activated" | "canceled";
  product_surface?: string | null;
  conversion_ref?: string | null;
  qualitative_feedback?: string | null;
  metadata?: Record<string, unknown>;
};

export type ProductEventCreateInput = {
  event_type:
    | "recommendation_viewed"
    | "coverage_limitation_viewed"
    | "trust_explanation_viewed"
    | "comparison_recommendation_viewed"
    | "comparison_abstained_viewed"
    | "market_inspected"
    | "comparison_selection_ready"
    | "my_search_viewed";
  event_source: "frontend";
  schema_version?: number;
  anonymous_session_id?: string | null;
  product_surface?: string | null;
  decision_id?: string | null;
  recommendation_id?: string | null;
  current_opportunity_id?: string | null;
  career_identity_id?: string | null;
  career_identity_version?: number | null;
  cohort_key?: string | null;
  experiment_key?: string | null;
  variant_key?: string | null;
  confidence_bucket?: string | null;
  coverage_status?: string | null;
  recommendation_state?: string | null;
  payload?: Record<string, unknown>;
};

export type ExplorePersonalizationState =
  | "personalized"
  | "needs_input"
  | "general_market_intelligence"
  | "unsupported";

export type ExploreContextValues = {
  goal: string | null;
  role_families: string[];
  industries: string[];
  opportunity_types: string[];
  career_stage: string | null;
  work_arrangements: string[];
  preferred_region_ids: string[];
  included_region_ids: string[];
  excluded_region_ids: string[];
  timing: string[];
};

export type ExploreSessionOverrides = {
  goal?: string | null;
  role_families?: string[] | null;
  industries?: string[] | null;
  opportunity_types?: string[] | null;
  work_arrangements?: string[] | null;
  geographic_scope?: {
    region_refs?: string[];
    excluded_region_refs?: string[];
  } | null;
};

export type ExploreContext = {
  career_identity_id: string | null;
  career_identity_version: number | null;
  personalization_consent: boolean;
  profile_defaults: ExploreContextValues;
  session_overrides: ExploreContextValues;
  effective_context: ExploreContextValues;
  context_fingerprint: string;
  fingerprint_version: string;
  personalization_state: ExplorePersonalizationState;
  supported_goal: string | null;
  goal_mapping_state: "supported" | "missing" | "ambiguous" | "unsupported";
  applied_context: string[];
  unapplied_context: Array<{ code: string; field: string; source: string; reason: string }>;
  unsupported_context: Array<{ code: string; field: string; source: string; reason: string }>;
  limitations: string[];
};

export type ExploreFitState =
  | "confident"
  | "tentative"
  | "insufficient_evidence"
  | "unsupported"
  | "abstained"
  | "hard_constraint_excluded"
  | "general_market_intelligence";

export type ExploreRegion = {
  region_id: string;
  public_slug: string | null;
  display_name: string;
  region_type: string | null;
  state_codes: string[];
  primary_city: string | null;
  centroid: { latitude: number; longitude: number } | null;
  focus_bounds: Record<string, number> | null;
  market_support_status: string;
};

export type ExploreFitResult = {
  market_key: string;
  region: ExploreRegion;
  state: ExploreFitState;
  fit_score: number | null;
  fit_band: string | null;
  rank: number | null;
  display_order: number;
  tied_region_ids: string[];
  near_tie_region_ids: string[];
  primary_drivers: Array<Record<string, unknown>>;
  tradeoffs: string[];
  confidence: string;
  evidence_sufficiency: string;
  freshness: string;
  market_coverage: {
    authority: string;
    summary: string;
    evidence_areas_used: string[];
    evidence_areas_missing: string[];
  };
  opportunity_coverage: {
    authority: string;
    status: string;
    active_opportunity_count: number;
    ranking_eligible_opportunity_count: number;
    fresh_opportunity_count: number;
    rationale: string | null;
    limitations: string[];
    affects_explore_fit: false;
  };
  material_limitations: string[];
  abstention_reason: string | null;
  hard_constraint_reasons: string[];
  contradiction_status: string;
  contradiction_findings: Array<Record<string, unknown>>;
  contradiction_blocking: boolean;
  contradiction_summary: string | null;
  evidence_hooks: Record<string, unknown>;
  versions: Record<string, unknown>;
};

export type ExploreMarketsResponse = {
  context: ExploreContext;
  ranking_universe: {
    kind: string;
    label: string;
    region_ids: string[];
    market_count: number;
    nationally_representative: boolean;
  };
  markets: ExploreFitResult[];
  evaluated_at: string;
  authority: "explore_fit";
  authority_version: string;
  contradiction_status: string;
  contradiction_findings: Array<Record<string, unknown>>;
  contradiction_blocking: boolean;
  contradiction_summary: string | null;
  limitations: string[];
};

export type ExploreComparisonRecommendationState =
  | "clear_recommendation"
  | "near_tie"
  | "exact_tie"
  | "insufficient_evidence"
  | "blocking_contradiction"
  | "unsupported_member"
  | "outside_constraints";

export type ExploreComparisonFactor = {
  code: string;
  label: string;
  summary: string;
  region_ids: string[];
  evidence: string[];
};

export type ExploreComparisonMarket = {
  fit: ExploreFitResult;
  comparison_rank: number | null;
  key_advantages: string[];
  key_tradeoffs: string[];
  confidence_caveat: string;
  missing_evidence: string[];
  company_evidence: Array<{
    company_id: string;
    company_name: string;
    evidence_kind: "current_hiring" | "presence" | string;
    active_posting_count: number | null;
    confidence: string | null;
  }>;
};

export type ExploreComparisonResult = {
  comparison_identity: string;
  compared_markets: ExploreComparisonMarket[];
  recommendation_state: ExploreComparisonRecommendationState;
  recommendation_summary: string;
  winner_region_ids: string[];
  tied_region_ids: string[];
  near_tie_region_ids: string[];
  abstained: boolean;
  abstention_reason: string | null;
  differentiating_factors: ExploreComparisonFactor[];
  shared_strengths: ExploreComparisonFactor[];
  shared_weaknesses: ExploreComparisonFactor[];
  confidence: string;
  contradiction_state: string;
  contradiction_findings: Array<Record<string, unknown>>;
  missing_evidence: Record<string, string[]>;
  market_coverage: Record<string, ExploreFitResult["market_coverage"]>;
  opportunity_coverage: Record<string, ExploreFitResult["opportunity_coverage"]>;
  context_fingerprint: string;
  effective_context: ExploreContextValues;
  algorithm_version: string;
  evidence_authority_version: string;
  evidence_bundle: string;
  calibration_version: string;
  generated_at: string;
  authority: "explore_fit_n_way_comparison";
  limitations: string[];
};

export type SavedExploreComparisonSummary = {
  comparison_id: string;
  selected_region_ids: string[];
  selected_public_slugs: string[];
  market_names: string[];
  context_fingerprint: string;
  context_summary: string;
  recommendation_state: ExploreComparisonRecommendationState;
  recommendation_summary: string;
  winner_region_ids: string[];
  confidence: string;
  generated_at: string;
  saved_at: string | null;
};

export type SavedExploreComparison = SavedExploreComparisonSummary & {
  result: ExploreComparisonResult;
};

export type ExplorePrioritization = {
  decision_id: string;
  comparison_id: string;
  selected_region_id: string;
  system_recommended_region_ids: string[];
  choice_matches_recommendation: boolean | null;
  created: boolean;
  decision: CareerDecision;
};

export type CareerDecision = {
  decision_id: string;
  decision_type: CareerDecisionType;
  status: CareerDecisionStatus;
  title: string;
  description: string | null;
  decision_date: string | null;
  target_date: string | null;
  planned_review_at: string | null;
  time_horizon: string | null;
  priorities: Array<Record<string, unknown>>;
  constraints: Array<Record<string, unknown>>;
  selected_option_id: string | null;
  career_identity_id: string | null;
  current_context_snapshot_id: string | null;
  current_recommendation_id: string | null;
  current_version: number;
  context: CareerDecisionContext | null;
  options: CareerDecisionOption[];
  recommendation: DecisionRecommendation | null;
  explore_comparison_provenance?: {
    comparison_id: string;
    context_fingerprint: string;
    system_recommendation_state: string;
    system_recommended_region_ids: string[];
    user_selected_region_id: string;
    choice_matches_recommendation: boolean | null;
  } | null;
  action_plan: CareerActionPlan | null;
  applications: CareerApplication[];
  outcomes: CareerOutcome[];
  created_at: string;
  updated_at: string;
};

export type CareerDecisionVersion = {
  decision_version_id: string;
  version_number: number;
  version_reason: string;
  selected_option_id: string | null;
  context_snapshot_id: string | null;
  decision_snapshot: Record<string, unknown>;
  options_snapshot: Array<Record<string, unknown>>;
  recommendation_snapshot: Record<string, unknown> | null;
  user_note: string | null;
  created_at: string;
};

export type WeeklyCareerReview = {
  window_start: string;
  window_end: string;
  happened: Array<Record<string, unknown>>;
  changed: Array<Record<string, unknown>>;
  worked: Array<Record<string, unknown>>;
  did_not_work: Array<Record<string, unknown>>;
  stalled: Array<Record<string, unknown>>;
  invalidated_assumptions: Array<Record<string, unknown>>;
  reconsider: Array<Record<string, unknown>>;
  next_actions: Array<Record<string, unknown>>;
  reminders: Array<Record<string, unknown>>;
};

export type DecisionFactorCategory =
  | "benefit"
  | "cost"
  | "risk"
  | "time"
  | "confidence"
  | "uncertainty"
  | "user_importance"
  | "evidence_strength"
  | "reversibility";

export type DecisionFactorDirection = "positive" | "negative" | "neutral" | "mixed" | "unknown";

export type DecisionFactorEvidenceKind =
  | "direct"
  | "derived"
  | "inferred"
  | "proxy"
  | "unavailable"
  | "conflicting";

export type DecisionFactorFreshness = "fresh" | "stale" | "partial" | "unknown";

export type DecisionFactor = {
  factor_id: string;
  decision_id: string;
  option_id: string | null;
  recommendation_id: string | null;
  context_snapshot_id: string | null;
  domain: string;
  category: DecisionFactorCategory;
  factor_key: string;
  label: string;
  normalized_value: Record<string, unknown> | null;
  raw_value: Record<string, unknown> | null;
  direction: DecisionFactorDirection;
  importance: number | null;
  confidence: CareerDecisionConfidence;
  uncertainty: string;
  evidence_strength: string;
  evidence_kind: DecisionFactorEvidenceKind;
  source_type: string | null;
  source_id: string | null;
  provenance: Record<string, unknown>;
  explanation: string;
  caveats: string[];
  freshness_status: DecisionFactorFreshness;
  freshness_expires_at: string | null;
  generated_at: string;
};

export type LongitudinalContext = {
  longitudinal_context_id: string;
  decision_id: string | null;
  window_start: string | null;
  window_end: string;
  record_count: number;
  context: Record<string, unknown>;
  evidence: Record<string, unknown>;
  generated_at: string;
};

export type RecommendationEvolution = {
  evolution_id: string;
  decision_id: string;
  previous_recommendation_id: string | null;
  current_recommendation_id: string | null;
  change_type:
    | "none"
    | "user_changed"
    | "goal_changed"
    | "career_identity_changed"
    | "market_changed"
    | "evidence_changed"
    | "outcome_changed"
    | "confidence_changed"
    | "stale_prior"
    | "superseded";
  meaningful_changes: Array<Record<string, unknown>>;
  confidence_before: CareerDecisionConfidence | null;
  confidence_after: CareerDecisionConfidence | null;
  evidence_basis: Record<string, unknown>;
  uncertainty: string;
  explanation: string;
  generated_at: string;
};

export type AdvisoryFinding = {
  advisory_finding_id: string;
  decision_id: string | null;
  finding_type: string;
  severity: "info" | "watch" | "warning" | "blocking";
  support_status: "supported" | "weakly_supported" | "unresolved";
  confidence: CareerDecisionConfidence;
  uncertainty: string;
  window_start: string | null;
  window_end: string;
  affected_goal: string | null;
  supporting_evidence: Array<Record<string, unknown>>;
  counter_evidence: Array<Record<string, unknown>>;
  explanation: string;
  suggested_action: string | null;
  acknowledged_at: string | null;
  dismissed_at: string | null;
  generated_at: string;
};

export type StrategicCareerReview = {
  strategic_review_id: string;
  decision_id: string | null;
  longitudinal_context_id: string;
  status: string;
  window_start: string | null;
  window_end: string;
  goals: Record<string, unknown>;
  strategy_performance: Record<string, unknown>;
  application_summary: Record<string, unknown>;
  outcome_summary: Record<string, unknown>;
  identity_changes: Array<Record<string, unknown>>;
  market_changes: Array<Record<string, unknown>>;
  recommendation_changes: Array<Record<string, unknown>>;
  active_risks: Array<Record<string, unknown>>;
  blind_spots: Array<Record<string, unknown>>;
  suggested_next_actions: Array<Record<string, unknown>>;
  confidence: CareerDecisionConfidence;
  uncertainty: string;
  generated_at: string;
};

export type DeepDecisionAnalysisRequest = {
  include_domains?: string[];
  window_start?: string | null;
  window_end?: string | null;
};

export type DeepDecisionAnalysis = {
  decision_id: string;
  factors: DecisionFactor[];
  longitudinal_context: LongitudinalContext;
  recommendation_evolution: RecommendationEvolution | null;
  advisory_findings: AdvisoryFinding[];
  strategic_review: StrategicCareerReview;
};

export type CurrentOpportunityFreshnessState = "fresh" | "aging" | "stale" | "unknown" | string;
export type CurrentOpportunityCoverageStatus =
  | "production_ready"
  | "limited"
  | "experimental"
  | "unsupported"
  | string;
export type CurrentOpportunityConfidence = "high" | "medium" | "low" | "unknown" | string;
export type CurrentOpportunityWorkArrangement =
  | "remote"
  | "hybrid"
  | "onsite"
  | "mixed"
  | "unknown"
  | string;

export type CurrentOpportunityPayload = {
  opportunity_id: string;
  company_id: string | null;
  company_name: string;
  original_title: string;
  normalized_title: string;
  role_family: string;
  seniority_level: string;
  market_id: string | null;
  market_label: string | null;
  location_text: string | null;
  location_resolution_status?: "resolved" | "unresolved" | "ambiguous" | string;
  location_resolution_source?: string | null;
  work_arrangement: CurrentOpportunityWorkArrangement;
  compensation_min: number | null;
  compensation_max: number | null;
  compensation_currency: string | null;
  compensation_interval: string;
  employment_type: string;
  opportunity_type: string;
  posting_date: string | null;
  closing_date: string | null;
  application_url: string | null;
  source_url: string | null;
  description_text: string | null;
  skills: string[];
  requirements: string[];
  status: string;
  freshness_state: CurrentOpportunityFreshnessState;
  freshness_age_hours: number | null;
  first_observed_at: string | null;
  last_observed_at: string | null;
  last_collected_at: string | null;
  canonical_updated_at: string;
  normalization_confidence: CurrentOpportunityConfidence;
  identity_confidence: CurrentOpportunityConfidence;
  ranking_eligible: boolean;
  ranking_ineligible_reasons: string[];
  coverage_status: CurrentOpportunityCoverageStatus;
  coverage_limitations: string[];
  provenance: {
    source_count?: number;
    sources?: Array<{
      source_id: string;
      provider_record_id?: string;
      first_observed_at?: string | null;
      last_observed_at?: string | null;
      last_collected_at?: string | null;
      active?: boolean;
      source_name?: string | null;
      source_type?: string | null;
      provider?: string | null;
      data_origin?: string | null;
      synthetic?: boolean;
      source_trust?: string;
      display_use_allowed?: boolean;
      ranking_use_allowed?: boolean;
    }>;
    [key: string]: unknown;
  };
  warnings: string[];
};

export type CurrentOpportunityMatchPayload = {
  opportunity: CurrentOpportunityPayload;
  match_score: number;
  strategic_relevance: string;
  contributing_factors: string[];
  warnings: string[];
  limitations: string[];
  ranking_eligible: boolean;
};

export type CurrentOpportunityCoveragePayload = {
  market_key: string;
  role_family: string;
  opportunity_type: string;
  status: CurrentOpportunityCoverageStatus;
  effective_status: CurrentOpportunityCoverageStatus;
  rationale: string;
  limitations: string[];
  source_basis: Record<string, unknown>;
  minimum_expected_sources: number;
  freshness_max_age_hours: number | null;
  last_evaluated_at: string | null;
};

export type CurrentOpportunityDiagnostic = {
  code: string;
  severity: "info" | "warning" | "blocking" | string;
  message: string;
  scope: Record<string, unknown>;
  evidence: Record<string, unknown>;
};

export type CurrentOpportunityRefreshRun = {
  run_id: string;
  source_id: string;
  status: string;
  acquired_count: number;
  normalized_count: number;
  promoted_count: number;
  duplicate_count: number;
  rejected_count: number;
  warning_count: number;
  failure_count: number;
  started_at: string;
  completed_at: string | null;
  warnings: string[];
  failure_details: Record<string, unknown>;
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

export type CareerIdentityPersonalizationMetadata = {
  source: "request" | "career_identity" | string;
  career_identity_applied: boolean;
  career_identity_version?: number;
  reason?: string;
  role_targets?: string[];
  industry_preferences?: string[];
  region_ids?: string[];
  excluded_roles?: string[];
  excluded_industries?: string[];
  excluded_region_ids?: string[];
  geographic_resolutions?: Array<Record<string, unknown>>;
  skills_count?: number;
  experience_count?: number;
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
  original_artifact_ref?: string | null;
  region_identity?: {
    region_id: string;
    public_slug: string | null;
    display_name: string | null;
  } | null;
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

export type UserDashboardWarningSeverity = "info" | "warning" | "critical";
export type UserDashboardNextActionPriority = "low" | "medium" | "high";

export type UserDashboardSummary = {
  headline: string;
  description: string;
  warning_count: number;
  recommendation_count: number;
};

export type UserDashboardRecommendedRegion = {
  region_id: string;
  region_name: string;
  score: number | null;
  confidence: string | null;
  freshness: string | null;
  warnings: string[];
  why_recommended: string;
  ranking_influence_allowed: boolean | null;
  trust_tier?: string | null;
  risk_level?: string | null;
  routing_outcome?: string | null;
  ranking_influence_decision?: string | null;
  ranking_influence_reason?: string | null;
  ranking_influence_reason_codes?: string[];
  trust_explanation?: TrustExplanation | null;
  report_recheck_status?: ReportRecheckStatus | null;
  exception_status?: ExceptionSubjectStatus | null;
};

export type UserDashboardRecommendedCompany = {
  company_id: string;
  company_name: string;
  score: number | null;
  confidence: string | null;
  freshness: string | null;
  warnings: string[];
  why_recommended: string;
  ranking_influence_allowed: boolean | null;
  trust_tier?: string | null;
  risk_level?: string | null;
  routing_outcome?: string | null;
  ranking_influence_decision?: string | null;
  ranking_influence_reason?: string | null;
  ranking_influence_reason_codes?: string[];
  trust_explanation?: TrustExplanation | null;
  report_recheck_status?: ReportRecheckStatus | null;
  exception_status?: ExceptionSubjectStatus | null;
};

export type UserDashboardRecommendedOpportunity = {
  opportunity_id: string;
  title: string;
  company_name: string;
  region_name: string | null;
  trust_label: string | null;
  review_status: string | null;
  partner_submitted: boolean;
  ranking_influence_allowed: boolean;
  expiration_state: string | null;
  source_type: string | null;
  warnings: string[];
  why_recommended: string;
  trust_tier?: string | null;
  evidence_summary?: Record<string, string | number> | null;
  risk_level?: string | null;
  routing_outcome?: string | null;
  ranking_influence_decision?: string | null;
  ranking_influence_reason?: string | null;
  ranking_influence_reason_codes?: string[];
  trust_explanation?: TrustExplanation | null;
  report_recheck_status?: ReportRecheckStatus | null;
  exception_status?: ExceptionSubjectStatus | null;
};

export type UserDashboardMarketWarning = {
  warning_code: string;
  severity: UserDashboardWarningSeverity;
  title: string;
  message: string;
  subject_type: string;
  subject_id: string;
  source: string;
};

export type UserDashboardForecastChange = {
  subject_type: string;
  subject_id: string;
  title: string;
  summary: string;
  confidence: string | null;
  freshness: string | null;
  warnings: string[];
};

export type UserDashboardSavedItem = {
  item_id: string;
  item_type: string;
  label: string;
  target_route: string | null;
  metadata: Record<string, string | number | boolean | null>;
};

export type UserDashboardNextAction = {
  action_code: string;
  label: string;
  description: string;
  priority: UserDashboardNextActionPriority;
  target_route: string | null;
};

export type UserDashboardTrustContext = {
  uses_existing_metadata_only: boolean;
  layer_30_full_trust_engine_available: boolean;
  message: string;
};

export type UserIntelligenceDashboardPayload = {
  generated_at: string;
  dashboard_version: "30.1" | string;
  summary: UserDashboardSummary;
  recommended_regions: UserDashboardRecommendedRegion[];
  recommended_companies: UserDashboardRecommendedCompany[];
  recommended_opportunities: UserDashboardRecommendedOpportunity[];
  market_warnings: UserDashboardMarketWarning[];
  forecast_changes: UserDashboardForecastChange[];
  saved_items: UserDashboardSavedItem[];
  recommended_next_actions: UserDashboardNextAction[];
  trust_context: UserDashboardTrustContext;
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

export type InstitutionPrivacyMetadata = {
  aggregation_level: string;
  privacy_mode: string;
  minimum_cohort_size: number;
  cohort_size: number;
  suppression_applied: boolean;
  suppressed_fields: string[];
  privacy_notes: string[];
  student_level_data_exposed: false;
};

export type InstitutionDecisionConfidence = {
  level: string;
  score: number;
  factors: string[];
};

export type InstitutionDecisionEvidence = {
  confidence: InstitutionDecisionConfidence;
  freshness: string;
  provenance: string[];
  source_basis: string[];
  historical_depth: Record<string, unknown>;
};

export type InstitutionDecisionMetric = {
  metric_key: string;
  label: string;
  value: number | string | null;
  unit: string | null;
  decision_use: string;
  evidence: InstitutionDecisionEvidence;
};

export type InstitutionDecisionSection = {
  section_key: string;
  title: string;
  what_is_happening: string;
  why_it_matters: string;
  considerations: string[];
  metrics: InstitutionDecisionMetric[];
  evidence: InstitutionDecisionEvidence;
  warnings: string[];
};

export type InstitutionForecastNote = {
  forecast_label: string;
  forecast_type: string;
  affected_entity: string;
  time_horizon: string;
  safe_display_summary: string;
  confidence: Record<string, unknown>;
  source_basis: Record<string, unknown>;
  historical_depth: Record<string, unknown>;
  uncertainty: Record<string, unknown>;
  reasoning_trail: string[];
  supporting_signals: Array<Record<string, unknown>>;
};

export type InstitutionDecisionDashboardPayload = {
  organization_id: string;
  organization_name: string;
  generated_at: string;
  time_horizon: string;
  summary: InstitutionDecisionSection;
  target_markets: InstitutionDecisionSection[];
  regional_trends: InstitutionDecisionSection[];
  program_alignment: InstitutionDecisionSection[];
  employer_geography: InstitutionDecisionSection[];
  internship_access: InstitutionDecisionSection[];
  industry_demand: InstitutionDecisionSection[];
  forecast_notes: InstitutionForecastNote[];
  recommended_actions: string[];
  confidence: InstitutionDecisionConfidence;
  freshness: string;
  provenance: string[];
  privacy: InstitutionPrivacyMetadata;
  limitations: string[];
  warnings: string[];
};

export type CurriculumProgramMapping = {
  program_name: string;
  relevant_role_families: string[];
  strongest_aligned_markets: InstitutionDecisionMetric[];
  emerging_markets: InstitutionDecisionMetric[];
  weak_or_saturated_markets: InstitutionDecisionMetric[];
  skills_with_rising_demand: string[];
  employer_relationship_targets: string[];
  advising_recommendations: string[];
  confidence: InstitutionDecisionConfidence;
  freshness: string;
  provenance: string[];
  sparse_data_warnings: string[];
  privacy: InstitutionPrivacyMetadata;
};

export type CurriculumMarketMappingPayload = {
  organization_id: string;
  organization_name: string;
  generated_at: string;
  programs: CurriculumProgramMapping[];
  confidence: InstitutionDecisionConfidence;
  freshness: string;
  provenance: string[];
  privacy: InstitutionPrivacyMetadata;
  warnings: string[];
  limitations: string[];
};

export type InstitutionWorkforceReportType =
  | "regional_workforce_opportunity"
  | "early_career_market_access"
  | "tech_sector_growth"
  | "student_placement_strategy"
  | "employer_geography"
  | "program_alignment";

export type InstitutionWorkforceReportPayload = {
  title: string;
  report_type: InstitutionWorkforceReportType;
  audience: string;
  scope: string;
  generated_at: string;
  summary: string;
  key_findings: string[];
  recommended_actions: string[];
  supporting_metrics: InstitutionDecisionMetric[];
  confidence: InstitutionDecisionConfidence;
  freshness: string;
  provenance: string[];
  privacy_statement: string;
  privacy: InstitutionPrivacyMetadata;
  limitations: string[];
  warnings: string[];
  export_ready: Record<string, unknown>;
};

export type InstitutionBenchmarkItem = {
  benchmark_subject: string;
  comparison_market_set: string[];
  opportunity_score: number;
  alignment_score: number;
  gap_score: number;
  emerging_region_gap: number;
  employer_access_gap: number;
  internship_access_gap: number;
  recommendation_summary: string;
  supporting_rationale: string[];
  warnings: string[];
};

export type InstitutionBenchmarkPayload = {
  organization_id: string;
  organization_name: string;
  generated_at: string;
  benchmarks: InstitutionBenchmarkItem[];
  confidence: InstitutionDecisionConfidence;
  freshness: string;
  provenance: string[];
  privacy: InstitutionPrivacyMetadata;
  warnings: string[];
  limitations: string[];
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
