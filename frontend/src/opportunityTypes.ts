import type {
  ExceptionSubjectStatus,
  ReportRecheckStatus,
  TrustExplanation,
} from "./types";

export type OpportunityProgramType =
  | "internship"
  | "co-op"
  | "rotational_program"
  | "new_grad_role"
  | "apprenticeship"
  | "employer_program"
  | "fellowship"
  | "unknown";

export type OpportunityLocationMode = "onsite" | "hybrid" | "remote" | "mixed" | "unknown";

export type OpportunitySeniorityLevel =
  | "internship"
  | "co-op"
  | "apprentice"
  | "new-grad"
  | "early-career"
  | "unknown";

export type OpportunityTrustLabel =
  | "verified"
  | "source_checked"
  | "partner_submitted"
  | "unverified"
  | "expired"
  | "rejected";

export type OpportunityReviewStatus =
  | "pending_review"
  | "approved"
  | "source_checked"
  | "rejected"
  | "expired"
  | "needs_correction";

export type OpportunityExpirationState = "active" | "expired";
export type OpportunityRouteConfidence = "high" | "medium" | "low";

export type OpportunityRouteRequest = {
  user_intent_summary?: string | null;
  profile_summary?: string | null;
  target_regions: string[];
  target_role_families: string[];
  preferred_program_types?: OpportunityProgramType[];
  preferred_location_modes?: OpportunityLocationMode[];
  experience_level: OpportunitySeniorityLevel;
  skills?: string[];
  background_tags?: string[];
  constraints?: string[];
  opportunity_trust_preferences?: OpportunityTrustLabel[];
  include_unverified?: boolean;
  limit?: number;
};

export type OpportunityRouteSourceSummary = {
  data_basis: string;
  source_categories: string[];
  source_count: number;
  notes: string[];
};

export type MatchedOpportunity = {
  opportunity_id: string;
  employer_name: string;
  program_name: string;
  program_type: OpportunityProgramType;
  region: string;
  metro: string | null;
  role_family: string;
  location_mode: OpportunityLocationMode;
  trust_label: OpportunityTrustLabel;
  review_status: OpportunityReviewStatus;
  expiration_state: OpportunityExpirationState;
  partner_submitted: boolean;
  paid_partner: boolean;
  application_url: string;
  source_url: string;
  fit_score: number;
  fit_explanation: string;
  warnings: string[];
  trust_tier?: string | null;
  risk_level?: string | null;
  routing_outcome?: string | null;
  ranking_influence_allowed?: boolean;
  ranking_influence_decision?: string | null;
  ranking_influence_reason?: string | null;
  ranking_influence_reason_codes?: string[];
  trust_explanation?: TrustExplanation | null;
  report_recheck_status?: ReportRecheckStatus | null;
  exception_status?: ExceptionSubjectStatus | null;
};

export type OpportunityRoute = {
  route_id: string;
  route_title: string;
  target_region: string;
  target_role_family: string;
  recommended_company_types: string[];
  matched_opportunities: MatchedOpportunity[];
  market_fit_score: number;
  region_fit_score: number;
  company_type_fit_score: number;
  opportunity_fit_score: number;
  role_family_fit_score: number;
  overall_route_fit_score: number;
  confidence: OpportunityRouteConfidence;
  explanation: string;
  warnings: string[];
  next_steps: string[];
  source_summary: OpportunityRouteSourceSummary;
  sponsored_or_partner_disclosure: string | null;
};

export type OpportunityRouteResponse = {
  routes: OpportunityRoute[];
  route_count: number;
  route_generation_note: string;
  non_goal_disclosures: string[];
};
