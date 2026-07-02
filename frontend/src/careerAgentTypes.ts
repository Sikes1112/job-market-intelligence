export type CareerAgentQuestionType =
  | "where_should_i_apply"
  | "city_fit"
  | "companies_to_watch"
  | "strongest_market_strategy"
  | "what_should_i_do_this_month";

export type CareerAgentFreshnessStatus =
  | "fresh"
  | "stale"
  | "partial"
  | "unknown"
  | "seeded_demo";

export type CareerAgentPreferenceSnapshot = {
  preferred_region_ids?: string[];
  preferred_company_ids?: string[];
  preferred_role_families?: string[];
  preferred_location_modes?: string[];
  preferred_program_types?: string[];
  constraints?: string[];
  preference_context?: string | null;
  counts_as_evidence?: false;
};

export type CareerAgentRequest = {
  question_type: CareerAgentQuestionType;
  user_goal?: string | null;
  target_region_ids?: string[];
  target_company_ids?: string[];
  target_role_families?: string[];
  preferred_program_types?: string[];
  preferred_location_modes?: string[];
  skills?: string[];
  background_tags?: string[];
  include_forecasts?: boolean;
  limit?: number;
  preference_snapshot?: CareerAgentPreferenceSnapshot | null;
};

export type CareerAgentFreshness = {
  freshness_status: CareerAgentFreshnessStatus;
  data_basis: string;
  last_updated_at: string | null;
  freshness_expires_at: string | null;
  source_count: number;
  warnings: string[];
};

export type CareerAgentUncertainty = {
  confidence_level: "high" | "medium" | "low" | "unknown";
  confidence_score: number | null;
  uncertainty_level: "low" | "medium" | "high";
  reasons: string[];
  limitations: string[];
  forecast_based: boolean;
  bounded: boolean;
};

export type CareerAgentEvidenceRef = {
  ref_id: string;
  evidence_type: string;
  entity_type: string;
  entity_id: string;
  label: string;
  summary: string;
  data_basis: string;
  freshness_status: CareerAgentFreshnessStatus;
  confidence_label: string | null;
  source_count: number;
  observed_at: string | null;
  public_url: string | null;
};

export type CareerAgentRecommendation = {
  recommendation_id: string;
  recommendation_type: string;
  rank: number;
  target_type: "region" | "company" | "opportunity" | "market_strategy" | "monthly_action";
  target_id: string;
  title: string;
  summary: string;
  score: number | null;
  action: string | null;
  evidence_refs: CareerAgentEvidenceRef[];
  freshness: CareerAgentFreshness;
  uncertainty: CareerAgentUncertainty;
  preference_alignment: string[];
  matched_opportunity_ids: string[];
  warnings: string[];
  limitations: string[];
};

export type CareerAgentGuardrailStatus = {
  passed: boolean;
  evidence_requirement_met: boolean;
  fabricated_openings_blocked: boolean;
  preferences_excluded_from_evidence: boolean;
  forecast_claims_bounded: boolean;
  private_fields_redacted: boolean;
  blocked_reasons: string[];
  warnings: string[];
};

export type CareerAgentAnswer = {
  answer_id: string;
  question_type: CareerAgentQuestionType;
  generated_at: string;
  summary: string;
  recommendations: CareerAgentRecommendation[];
  freshness: CareerAgentFreshness;
  source_freshness: CareerAgentFreshness[];
  uncertainty: CareerAgentUncertainty;
  preference_snapshot: CareerAgentPreferenceSnapshot | null;
  guardrails: CareerAgentGuardrailStatus;
  limitations: string[];
};

export type CareerPlanType =
  | "weekly_job_search_plan"
  | "regional_targeting_plan"
  | "company_research_plan"
  | "internship_application_calendar"
  | "networking_plan";

export type CareerPlanUserActionRequirement =
  | "user_action_required"
  | "system_suggested";

export type CareerPlanTimeWindow = {
  label: string;
  start_date: string;
  end_date: string;
};

export type CareerPlanMilestone = {
  milestone_id: string;
  summary: string;
  outcome: string;
  target_date: string | null;
};

export type CareerPlanRisk = {
  risk_id: string;
  severity: "low" | "medium" | "high";
  summary: string;
  mitigation: string;
  evidence_refs: CareerAgentEvidenceRef[];
};

export type CareerPlanEvidenceBinding = {
  binding_id: string;
  step_id: string;
  binding_type: "strategic_basis" | "verification_basis";
  evidence_refs: CareerAgentEvidenceRef[];
  note: string;
};

export type CareerPlanStep = {
  step_id: string;
  rank: number;
  title: string;
  description: string;
  action_owner: CareerPlanUserActionRequirement;
  strategic: boolean;
  milestone: CareerPlanMilestone;
  evidence_refs: CareerAgentEvidenceRef[];
  evidence_bindings: CareerPlanEvidenceBinding[];
  freshness: CareerAgentFreshness;
  uncertainty: CareerAgentUncertainty;
  risks: CareerPlanRisk[];
  matched_opportunity_ids: string[];
  warnings: string[];
};

export type CareerActionPlanRequest = {
  plan_type: CareerPlanType;
  career_agent_request: CareerAgentRequest;
  career_goal?: string | null;
  time_window?: CareerPlanTimeWindow | null;
  include_memory?: boolean;
  limit?: number;
};

export type CareerActionPlan = {
  plan_id: string;
  plan_type: CareerPlanType;
  generated_at: string;
  source_answer_id: string;
  summary: string;
  career_goal: string | null;
  time_window: CareerPlanTimeWindow;
  steps: CareerPlanStep[];
  evidence_refs: CareerAgentEvidenceRef[];
  freshness: CareerAgentFreshness;
  source_freshness: CareerAgentFreshness[];
  uncertainty: CareerAgentUncertainty;
  risks: CareerPlanRisk[];
  warnings: string[];
  limitations: string[];
  memory_personalization: string[];
  guardrails: CareerAgentGuardrailStatus;
};

export type CareerMemoryCategory =
  | "saved_companies"
  | "target_regions"
  | "applied_roles"
  | "preferred_industries"
  | "rejected_markets"
  | "career_constraints"
  | "preferred_role_types";

export type CareerMemoryVisibility = "private";

export type CareerMemoryPermission = {
  category: CareerMemoryCategory;
  enabled: boolean;
  personalize_allowed: boolean;
  visibility?: CareerMemoryVisibility;
};

export type CareerMemoryEntryInput = {
  category: CareerMemoryCategory;
  value: string;
  label?: string | null;
  notes?: string | null;
};

export type CareerMemoryEntry = CareerMemoryEntryInput & {
  memory_entry_id: string;
  visibility: CareerMemoryVisibility;
  source: "user_provided";
  counts_as_evidence: false;
  created_at: string | null;
  updated_at: string | null;
};

export type CareerMemoryAuditEvent = {
  event_type: "permission_updated" | "entry_saved" | "entry_deleted" | "memory_cleared";
  category: CareerMemoryCategory | null;
  memory_entry_id: string | null;
  occurred_at: string;
  summary: string;
};

export type CareerMemoryProfile = {
  user_id: string;
  memory_enabled: boolean;
  permissions: CareerMemoryPermission[];
  entries: CareerMemoryEntry[];
  entries_by_category: Record<CareerMemoryCategory, CareerMemoryEntry[]>;
  audit_events: CareerMemoryAuditEvent[];
};

export type CareerMemoryUpdateRequest = {
  explicit_user_permission: boolean;
  permissions?: CareerMemoryPermission[];
  entries?: CareerMemoryEntryInput[];
  replace_categories?: CareerMemoryCategory[];
};

export type CareerMemoryDeleteRequest = {
  clear_all?: boolean;
  categories?: CareerMemoryCategory[];
  memory_entry_ids?: string[];
  disable_permissions?: boolean;
};

export type CareerAgentToolType =
  | "reminder"
  | "career_report_export"
  | "watchlist_update_suggestion"
  | "notification_preference"
  | "outreach_message_draft"
  | "application_prep_checklist"
  | "job_application_submission";

export type CareerAgentToolStatus =
  | "suggested"
  | "drafted"
  | "preview_ready"
  | "awaiting_user_approval"
  | "approved"
  | "executed"
  | "rejected"
  | "expired"
  | "blocked";

export type CareerAgentActionBoundary =
  | "read_only_preview"
  | "user_state_change"
  | "reminder_creation"
  | "user_data_export"
  | "watchlist_mutation"
  | "notification_change"
  | "external_contact"
  | "application_submission";

export type CareerAgentToolPrivacy =
  | "public_safe"
  | "user_private"
  | "external_contact"
  | "blocked";

export type CareerAgentRequestedToolAction =
  | "preview"
  | "draft"
  | "approval_only"
  | "send"
  | "submit_application";

export type CareerAgentApprovalRequirement = {
  approval_required: boolean;
  explicit_user_approval_required: boolean;
  reason: string;
  boundary: CareerAgentActionBoundary;
  approval_button_label: string | null;
  runtime_execution_available: boolean;
};

export type CareerAgentToolAuditEvent = {
  event_type: "preview_created" | "approval_recorded" | "rejection_recorded" | "blocked";
  occurred_at: string;
  summary: string;
};

export type CareerAgentToolRequest = {
  tool_type: CareerAgentToolType;
  career_agent_request?: CareerAgentRequest | null;
  action_plan_request?: CareerActionPlanRequest | null;
  requested_action?: CareerAgentRequestedToolAction;
  include_memory?: boolean;
  include_private_memory_in_export?: boolean;
  target_opportunity_ids?: string[];
  user_context_claims?: string[];
  draft_recipient_role?: string | null;
  limit?: number;
};

export type CareerAgentToolPreview = {
  tool_request_id: string;
  tool_type: CareerAgentToolType;
  proposed_action_summary: string;
  user_visible_preview: Record<string, unknown>;
  evidence_refs: CareerAgentEvidenceRef[];
  freshness: CareerAgentFreshness;
  uncertainty: CareerAgentUncertainty;
  warnings: string[];
  approval_requirement: CareerAgentApprovalRequirement;
  action_boundary: CareerAgentActionBoundary;
  status: CareerAgentToolStatus;
  privacy_classification: CareerAgentToolPrivacy;
  source_answer_id: string | null;
  source_plan_id: string | null;
  user_id: string | null;
  runtime_execution_performed: boolean;
  created_at: string;
  updated_at: string;
  audit_events: CareerAgentToolAuditEvent[];
};

export type CareerAgentToolApproval = {
  tool_request_id: string;
  explicit_user_approval?: boolean;
  approval_note?: string | null;
};

export type CareerAgentToolExecution = {
  tool_request_id: string;
  status: CareerAgentToolStatus;
  runtime_execution_performed: boolean;
  executed_at: string | null;
  summary: string;
  warnings: string[];
  tool_preview: CareerAgentToolPreview;
};

export type CareerAgentToolList = {
  tool_previews: CareerAgentToolPreview[];
};
