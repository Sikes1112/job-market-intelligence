export type ApiEnvelope<T> = {
  status: "success" | "partial" | "error";
  data: T | null;
  metadata: {
    state: string;
    freshness?: {
      last_updated_at: string | null;
      freshness_expires_at: string | null;
      is_stale: boolean;
      freshness_status?: "fresh" | "stale" | "unknown";
    };
    source_versions?: Record<string, unknown>;
    warnings: WarningItem[];
  };
  error: { code: string; message: string } | null;
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

export type RegionListItem = {
  region_id: string;
  display_name: string;
  region_type: string;
  parent_region_id: string | null;
  labor_market_group: string | null;
  state: string;
  version?: number;
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
  summary: Record<string, number>;
  scores: RegionScores | null;
  top_companies_present: RegionCompany[];
  top_companies_hiring: HiringCompany[];
  entry_level_summary: Record<string, number | null>;
  major_tech_summary: { count: number; company_ids: string[] };
  mag7_summary: { count: number; company_ids: string[] };
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
  regions_present: Array<{
    region_id: string;
    region_display_name: string;
    presence_status: string;
    presence_basis: string | null;
    presence_confidence: string | null;
  }>;
  regions_hiring: Array<{
    region_id: string;
    region_display_name: string;
    currently_hiring_flag: boolean;
    active_posting_count_now: number | null;
    posting_count_30d: number | null;
    posting_count_90d: number | null;
  }>;
  entry_level_regions: Array<{
    region_id: string;
    region_display_name: string;
    internship_count: number | null;
    coop_count: number | null;
    entry_level_full_time_count: number | null;
    formal_early_career_program_flag: boolean;
    entry_level_access_score: number | null;
    entry_level_confidence: string | null;
  }>;
};

export type ComparisonDetail = {
  comparison_id: string;
  region_a: {
    region_id: string;
    display_name: string;
    scores: RegionScores | null;
  };
  region_b: {
    region_id: string;
    display_name: string;
    scores: RegionScores | null;
  };
  category_winners: Record<string, string | null>;
  notes: string[];
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
  ranked_regions: Array<{
    region_id: string;
    display_name: string;
    personal_market_score: number;
    objective_opportunity_score: number | null;
    match_notes: string[];
  }>;
  ranked_companies: Array<{
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
