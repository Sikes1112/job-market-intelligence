Job Contract Spec

Exact Request Payloads, Output Payloads, Error States, Retries, and Success Criteria
This turns the orchestration matrix into implementation-grade job contracts.

⸻

1. Contract Purpose
Each job needs a stable contract so the system knows:
* what request it accepts
* what output it must return
* what can fail
* when to retry
* what counts as success
* what downstream jobs should trigger next
This is the execution-facing spec.

⸻

2. Global Contract Rules
2.1 Every job should return
* job_id
* job_type
* status
* started_at
* completed_at
* input_hash
* output_hash
* error_code if failed
* warnings if partial
* downstream_trigger_recommendations
2.2 Standard job statuses
* queued
* running
* succeeded
* succeeded_with_warnings
* partial
* failed
* cancelled
2.3 Standard error classes
* INPUT_VALIDATION_ERROR
* DEPENDENCY_MISSING
* SOURCE_UNAVAILABLE
* RATE_LIMITED
* PARSE_FAILURE
* INTEGRITY_CHECK_FAILED
* TIMEOUT
* NO_MEANINGFUL_CHANGE
* INTERNAL_EXCEPTION
2.4 Retry classes
Retryable
* SOURCE_UNAVAILABLE
* RATE_LIMITED
* TIMEOUT
* some PARSE_FAILURE cases if transient
Not retryable without intervention
* INPUT_VALIDATION_ERROR
* DEPENDENCY_MISSING
* INTEGRITY_CHECK_FAILED
* deterministic PARSE_FAILURE
* INTERNAL_EXCEPTION if code bug suspected
2.5 Standard success criteria types
* output object created
* output object updated
* no-op accepted because no meaningful change
* partial success with confidence downgrade

⸻

3. Global Envelope Schema
Every job request should use a common envelope.
Request envelope
{
  "job_id": "string",
  "job_type": "string",
  "trigger_type": "scheduled | event_driven | manual | user_query",
  "requested_by": "system | admin | user:<id>",
  "priority": "low | normal | high | urgent",
  "request_time": "ISO-8601 timestamp",
  "scope": {},
  "inputs": {},
  "options": {},
  "dependency_refs": []
}
Response envelope
{
  "job_id": "string",
  "job_type": "string",
  "status": "queued | running | succeeded | succeeded_with_warnings | partial | failed | cancelled",
  "started_at": "ISO-8601 timestamp",
  "completed_at": "ISO-8601 timestamp",
  "input_hash": "string",
  "output_hash": "string",
  "scope": {},
  "metrics": {},
  "outputs": {},
  "warnings": [],
  "error_code": null,
  "error_message": null,
  "retry_recommended": false,
  "downstream_trigger_recommendations": []
}

⸻

4. Job 1 — Geography Build Job
Request
{
  "job_id": "job_geo_001",
  "job_type": "geography_build",
  "trigger_type": "manual",
  "requested_by": "admin",
  "priority": "high",
  "request_time": "2026-05-06T16:00:00Z",
  "scope": {
    "region_ids": ["greater_boston", "greater_sf"],
    "mode": "create_or_update"
  },
  "inputs": {
    "region_definitions": [
      {
        "region_id": "greater_boston",
        "display_name": "Greater Boston",
        "region_type": "greater_region",
        "parent_region_id": "massachusetts",
        "labor_market_group": "boston_labor_market"
      }
    ],
    "normalization_profiles": []
  },
  "options": {
    "validate_hierarchy": true,
    "rebuild_dependents": false
  },
  "dependency_refs": []
}
Output
{
  "outputs": {
    "geography_objects_created": ["greater_boston"],
    "geography_objects_updated": ["greater_sf"],
    "region_registry_version": "v12"
  },
  "metrics": {
    "created_count": 1,
    "updated_count": 1,
    "unchanged_count": 0
  }
}
Failure states
* invalid region hierarchy
* duplicate region id
* missing parent region
* bad normalization profile reference
Retry policy
* retry only for transient storage issues
* do not retry validation failures automatically
Success criteria
* all requested geography objects are created/updated
* hierarchy validation passes
* region registry version committed

⸻

5. Job 2 — Company Universe Intake Job
Request
{
  "job_id": "job_intake_001",
  "job_type": "company_universe_intake",
  "trigger_type": "scheduled",
  "requested_by": "system",
  "priority": "normal",
  "request_time": "2026-05-06T16:00:00Z",
  "scope": {
    "region_ids": ["greater_boston", "greater_sf"],
    "sector_scope": ["software", "ai", "cloud", "data", "hardware", "cybersecurity"]
  },
  "inputs": {
    "source_configs": ["source_set_default_v1"],
    "existing_company_registry_version": "v44"
  },
  "options": {
    "allow_new_candidates": true,
    "dedupe_against_registry": true
  },
  "dependency_refs": ["region_registry:v12"]
}
Output
{
  "outputs": {
    "candidate_company_pool_id": "candidate_pool_v45",
    "new_candidate_company_ids": ["cand_101", "cand_102"],
    "updated_candidate_company_ids": ["cand_055"]
  },
  "metrics": {
    "candidate_count_total": 824,
    "new_candidate_count": 2,
    "updated_candidate_count": 1,
    "deduped_count": 44
  }
}
Failure states
* no candidate sources available
* source schema mismatch
* dedupe failure
* malformed company records
Retry policy
* retry transient source failures
* do not retry malformed payload failures until source parser fixed
Success criteria
* candidate pool built
* dedupe pass completed
* output linked to registry version

⸻

6. Job 3 — Eligibility & Classification Job
Request
{
  "job_id": "job_classify_001",
  "job_type": "eligibility_classification",
  "trigger_type": "event_driven",
  "requested_by": "system",
  "priority": "high",
  "request_time": "2026-05-06T16:00:00Z",
  "scope": {
    "candidate_pool_id": "candidate_pool_v45",
    "company_ids": ["cand_101", "cand_102", "cand_055"]
  },
  "inputs": {
    "eligibility_ruleset_version": "eligibility_v7",
    "major_tech_rubric_version": "majortech_v4",
    "mag7_list_version": "mag7_v2",
    "override_policy_version": "override_v3"
  },
  "options": {
    "allow_override": true,
    "emit_confidence_labels": true
  },
  "dependency_refs": ["candidate_pool_v45"]
}
Output
{
  "outputs": {
    "classified_company_universe_version": "company_universe_v45",
    "company_results": [
      {
        "company_id": "comp_101",
        "company_name": "Example AI",
        "eligibility_status": "eligible",
        "eligibility_score": 0.82,
        "eligibility_override_flag": false,
        "classification_confidence": "high_confidence",
        "is_major_tech": true,
        "major_tech_score": 0.76,
        "is_mag7": false
      }
    ]
  },
  "metrics": {
    "eligible_count": 2,
    "ineligible_count": 1,
    "override_included_count": 0,
    "major_tech_count": 1
  }
}
Failure states
* missing ruleset
* missing candidate pool
* override policy violation
* company record incomplete
* integrity mismatch between scoring and labels
Retry policy
* retry only on transient storage or service issues
* do not retry rule/config failures
Success criteria
* all targeted candidate companies resolved
* eligibility/classification fields emitted
* no unresolved company remains in ambiguous state without explicit status

⸻

7. Job 4 — Company-Region Presence Mapping Job
Request
{
  "job_id": "job_presence_001",
  "job_type": "presence_mapping",
  "trigger_type": "event_driven",
  "requested_by": "system",
  "priority": "normal",
  "request_time": "2026-05-06T16:00:00Z",
  "scope": {
    "company_ids": ["comp_101", "comp_202"],
    "region_ids": ["greater_boston", "greater_sf"]
  },
  "inputs": {
    "classified_company_universe_version": "company_universe_v45",
    "region_registry_version": "v12",
    "presence_ruleset_version": "presence_v3",
    "presence_evidence_sources": ["office_data_v2", "ops_data_v1", "hiring_data_v20"]
  },
  "options": {
    "prefer_hiring_evidence": true,
    "allow_satellite_office_presence": true
  },
  "dependency_refs": ["company_universe_v45", "region_registry:v12"]
}
Output
{
  "outputs": {
    "presence_map_version": "presence_v33",
    "presence_results": [
      {
        "company_id": "comp_101",
        "region_id": "greater_boston",
        "presence_status": "present",
        "presence_basis": "office_plus_hiring",
        "office_evidence_flag": true,
        "operations_evidence_flag": false,
        "hiring_evidence_flag": true,
        "presence_confidence": "high_confidence"
      }
    ]
  },
  "metrics": {
    "pairs_evaluated": 4,
    "present_count": 3,
    "not_present_count": 1,
    "uncertain_count": 0
  }
}
Failure states
* missing classified company universe
* missing region registry
* evidence-source fetch failure
* conflicting evidence unresolved
Retry policy
* retry transient source failures
* unresolved evidence conflicts return partial if safe
Success criteria
* each requested company-region pair resolved to present/not_present/uncertain
* basis emitted for every non-failed pair

⸻

8. Job 5 — Hiring Refresh Job
Request
{
  "job_id": "job_hiring_001",
  "job_type": "hiring_refresh",
  "trigger_type": "scheduled",
  "requested_by": "system",
  "priority": "high",
  "request_time": "2026-05-06T16:00:00Z",
  "scope": {
    "company_region_pairs": [
      {"company_id": "comp_101", "region_id": "greater_boston"},
      {"company_id": "comp_101", "region_id": "greater_sf"}
    ]
  },
  "inputs": {
    "presence_map_version": "presence_v33",
    "hiring_sources": ["jobs_feed_v10"],
    "time_window_config_version": "timewindows_v2"
  },
  "options": {
    "refresh_now_counts": true,
    "refresh_30d_counts": true,
    "refresh_90d_counts": true,
    "refresh_annualized_signal": true,
    "refresh_student_signal": true
  },
  "dependency_refs": ["presence_v33"]
}
Output
{
  "outputs": {
    "hiring_map_version": "hiring_v71",
    "hiring_results": [
      {
        "company_id": "comp_101",
        "region_id": "greater_boston",
        "currently_hiring_flag": true,
        "active_posting_count_now": 12,
        "posting_count_30d": 24,
        "posting_count_90d": 55,
        "annualized_trend_signal": "positive",
        "seasonal_student_hiring_signal": "moderate",
        "hiring_program_count": 2,
        "hiring_confidence": "high_confidence"
      }
    ]
  },
  "metrics": {
    "pairs_refreshed": 2,
    "pairs_changed": 1,
    "pairs_unchanged": 1
  }
}
Failure states
* hiring source unavailable
* parsing failure on postings
* time-window aggregation failure
* pair not present in presence map
Retry policy
* retry source and timeout failures
* do not retry invalid pair errors automatically
Success criteria
* requested pairs refreshed or explicitly marked unchanged
* current hiring fields and window fields emitted

⸻

9. Job 6 — Entry-Level Refresh Job
Request
{
  "job_id": "job_entry_001",
  "job_type": "entry_level_refresh",
  "trigger_type": "event_driven",
  "requested_by": "system",
  "priority": "high",
  "request_time": "2026-05-06T16:00:00Z",
  "scope": {
    "company_region_pairs": [
      {"company_id": "comp_101", "region_id": "greater_boston"}
    ]
  },
  "inputs": {
    "hiring_map_version": "hiring_v71",
    "entry_level_ruleset_version": "entrylevel_v4"
  },
  "options": {
    "count_internships": true,
    "count_coops": true,
    "count_entry_full_time": true,
    "emit_recurrence_signal": true
  },
  "dependency_refs": ["hiring_v71"]
}
Output
{
  "outputs": {
    "entry_level_map_version": "entry_v29",
    "entry_level_results": [
      {
        "company_id": "comp_101",
        "region_id": "greater_boston",
        "internship_count": 3,
        "coop_count": 2,
        "entry_level_full_time_count": 4,
        "formal_early_career_program_flag": true,
        "student_season_recurrence_signal": "strong",
        "entry_level_access_score": 0.81,
        "entry_level_confidence": "high_confidence"
      }
    ]
  },
  "metrics": {
    "pairs_evaluated": 1,
    "pairs_with_entry_level_access": 1
  }
}
Failure states
* missing hiring map dependency
* extraction logic failure
* ambiguous role-level parsing
* incomplete role metadata
Retry policy
* retry transient source issues upstream
* partial success allowed with downgraded confidence
Success criteria
* each requested pair emits entry-level counts or explicit zero/unknown treatment
* score emitted with confidence

⸻

10. Job 7 — Region Score Recompute Job
Request
{
  "job_id": "job_score_001",
  "job_type": "region_score_recompute",
  "trigger_type": "event_driven",
  "requested_by": "system",
  "priority": "high",
  "request_time": "2026-05-06T16:00:00Z",
  "scope": {
    "region_ids": ["greater_boston", "greater_sf"]
  },
  "inputs": {
    "classified_company_universe_version": "company_universe_v45",
    "presence_map_version": "presence_v33",
    "hiring_map_version": "hiring_v71",
    "entry_level_map_version": "entry_v29",
    "normalization_profile_version": "norm_v5",
    "scoring_ruleset_version": "marketscore_v6"
  },
  "options": {
    "recompute_structural_score": true,
    "recompute_live_market_score": true,
    "recompute_objective_opportunity_score": true,
    "recompute_normalized_views": true
  },
  "dependency_refs": ["company_universe_v45", "presence_v33", "hiring_v71", "entry_v29"]
}
Output
{
  "outputs": {
    "region_market_scores_version": "regionscore_v18",
    "region_scores": [
      {
        "region_id": "greater_boston",
        "structural_ecosystem_score": 0.72,
        "live_market_score": 0.68,
        "objective_opportunity_score": 0.74,
        "raw_total_score": 0.71,
        "general_density_score": 0.76,
        "tech_market_density_score": 0.73,
        "early_career_accessibility_score": 0.79
      }
    ]
  },
  "metrics": {
    "regions_recomputed": 2,
    "regions_changed": 2
  }
}
Failure states
* missing upstream maps
* scoring ruleset missing
* normalization inputs missing
* integrity mismatch across inputs
Retry policy
* retry transient storage reads
* do not retry broken scoring config automatically
Success criteria
* each requested region receives full score bundle
* normalized views emitted
* scores tied to exact versioned inputs

⸻

11. Job 8 — Region Output Build Job
Request
{
  "job_id": "job_region_output_001",
  "job_type": "region_output_build",
  "trigger_type": "event_driven",
  "requested_by": "system",
  "priority": "normal",
  "request_time": "2026-05-06T16:00:00Z",
  "scope": {
    "region_ids": ["greater_boston"]
  },
  "inputs": {
    "region_market_scores_version": "regionscore_v18",
    "presence_map_version": "presence_v33",
    "hiring_map_version": "hiring_v71",
    "entry_level_map_version": "entry_v29",
    "region_registry_version": "v12"
  },
  "options": {
    "include_top_companies_present": true,
    "include_top_companies_hiring": true,
    "include_entry_level_summary": true
  },
  "dependency_refs": ["regionscore_v18"]
}
Output
{
  "outputs": {
    "region_output_objects": [
      {
        "region_id": "greater_boston",
        "region_output_version": "regionout_v40",
        "summary_sections_built": [
          "region_summary",
          "top_companies_present",
          "top_companies_hiring",
          "entry_level_summary"
        ]
      }
    ]
  },
  "metrics": {
    "region_outputs_built": 1
  }
}
Failure states
* missing region score
* missing region metadata
* top-list assembly failure
* corrupted region object template
Retry policy
* retry template/storage failures
* do not retry if inputs missing until upstream fixed
Success criteria
* region output object built and cacheable
* required summary sections present

⸻

12. Job 9 — Company Output Build Job
Request
{
  "job_id": "job_company_output_001",
  "job_type": "company_output_build",
  "trigger_type": "event_driven",
  "requested_by": "system",
  "priority": "normal",
  "request_time": "2026-05-06T16:00:00Z",
  "scope": {
    "company_ids": ["comp_101"]
  },
  "inputs": {
    "classified_company_universe_version": "company_universe_v45",
    "presence_map_version": "presence_v33",
    "hiring_map_version": "hiring_v71",
    "entry_level_map_version": "entry_v29"
  },
  "options": {
    "include_region_presence_view": true,
    "include_hiring_geography_view": true,
    "include_entry_level_view": true
  },
  "dependency_refs": ["company_universe_v45", "presence_v33"]
}
Output
{
  "outputs": {
    "company_output_objects": [
      {
        "company_id": "comp_101",
        "company_output_version": "companyout_v19",
        "sections_built": [
          "company_summary",
          "regions_present",
          "regions_hiring",
          "entry_level_regions"
        ]
      }
    ]
  },
  "metrics": {
    "company_outputs_built": 1
  }
}
Failure states
* missing company classification record
* missing presence data
* company rendering template failure
Retry policy
* retry transient storage/template failures
* no retry for missing upstream truth until repaired
Success criteria
* company output object built
* region/hiring/entry-level sections present if data available

⸻

13. Job 10 — Comparison Cache Build Job
Request
{
  "job_id": "job_compare_cache_001",
  "job_type": "comparison_cache_build",
  "trigger_type": "scheduled",
  "requested_by": "system",
  "priority": "normal",
  "request_time": "2026-05-06T16:00:00Z",
  "scope": {
    "comparison_pairs": [
      ["greater_boston", "greater_sf"]
    ]
  },
  "inputs": {
    "region_output_versions": {
      "greater_boston": "regionout_v40",
      "greater_sf": "regionout_v41"
    },
    "comparison_template_version": "comparetpl_v2"
  },
  "options": {
    "build_primary_comparison": true,
    "defer_contextual_challenge": true
  },
  "dependency_refs": ["regionout_v40", "regionout_v41"]
}
Output
{
  "outputs": {
    "comparison_cache_objects": [
      {
        "comparison_id": "greater_boston__greater_sf",
        "comparison_output_version": "compare_v12"
      }
    ]
  },
  "metrics": {
    "comparisons_built": 1
  }
}
Failure states
* missing region output object
* comparison template mismatch
* invalid region pair format
Retry policy
* retry missing cache reads if transient
* do not retry bad pair definition automatically
Success criteria
* cached comparison object built for each requested pair

⸻

14. Job 11 — Personal Overlay Query Job
Request
{
  "job_id": "job_personal_overlay_001",
  "job_type": "personal_overlay_query",
  "trigger_type": "user_query",
  "requested_by": "user:user_123",
  "priority": "high",
  "request_time": "2026-05-06T16:00:00Z",
  "scope": {
    "region_ids": ["greater_boston", "greater_sf"],
    "company_ids": [],
    "query_mode": "market_ranking"
  },
  "inputs": {
    "user_profile": {
      "role_targets": ["product_manager"],
      "industry_preferences": ["ai", "cloud"],
      "career_stage": "entry_level",
      "prestige_preference": "medium",
      "brand_preference": "medium"
    },
    "region_market_scores_version": "regionscore_v18",
    "region_output_versions": ["regionout_v40", "regionout_v41"]
  },
  "options": {
    "rank_regions": true,
    "rank_companies": true,
    "limit": 25
  },
  "dependency_refs": ["regionscore_v18"]
}
Output
{
  "outputs": {
    "personalized_market_scores": [
      {
        "region_id": "greater_boston",
        "personal_market_score": 0.78
      }
    ],
    "personalized_company_target_scores": [
      {
        "company_id": "comp_101",
        "region_id": "greater_boston",
        "personal_company_score": 0.84
      }
    ]
  },
  "metrics": {
    "regions_ranked": 2,
    "companies_ranked": 25
  }
}
Failure states
* malformed user preference payload
* missing region scores
* unsupported role target enum
Retry policy
* do not retry malformed user input automatically
* retry transient cache misses
Success criteria
* personalized market ranking produced
* company targets ranked if requested

⸻

15. Job 12 — Contextual Challenge Build Job
Request
{
  "job_id": "job_context_001",
  "job_type": "contextual_challenge_build",
  "trigger_type": "user_query",
  "requested_by": "user:user_123",
  "priority": "normal",
  "request_time": "2026-05-06T16:00:00Z",
  "scope": {
    "comparison_id": "greater_boston__greater_sf"
  },
  "inputs": {
    "comparison_output_version": "compare_v12",
    "contextual_ruleset_version": "context_v3"
  },
  "options": {
    "emit_changed_vs_unchanged_findings": true,
    "emit_challenge_narrative": true
  },
  "dependency_refs": ["compare_v12"]
}
Output
{
  "outputs": {
    "contextual_challenge_object": {
      "comparison_id": "greater_boston__greater_sf",
      "contextual_output_version": "contextout_v7",
      "primary_result_status": "challenged",
      "changed_findings": ["broader_bay_scale"],
      "unchanged_findings": ["entry_level_density_advantage_boston"]
    }
  },
  "metrics": {
    "challenge_generated": 1
  }
}
Failure states
* missing comparison object
* contextual ruleset missing
* narrative generation failure
Retry policy
* retry transient object-load failures
* partial success allowed without narrative if structured result produced
Success criteria
* contextual challenge object built
* changed/unchanged interpretation emitted

⸻

16. Job 13 — Audit Job
Request
{
  "job_id": "job_audit_001",
  "job_type": "audit",
  "trigger_type": "scheduled",
  "requested_by": "system",
  "priority": "normal",
  "request_time": "2026-05-06T16:00:00Z",
  "scope": {
    "region_ids": ["greater_boston", "greater_sf"],
    "company_ids": [],
    "audit_mode": "targeted"
  },
  "inputs": {
    "classified_company_universe_version": "company_universe_v45",
    "presence_map_version": "presence_v33",
    "hiring_map_version": "hiring_v71",
    "entry_level_map_version": "entry_v29",
    "region_market_scores_version": "regionscore_v18",
    "audit_ruleset_version": "audit_v5"
  },
  "options": {
    "check_override_balance": true,
    "check_double_counting": true,
    "check_presence_inflation": true,
    "check_personal_layer_integrity": true
  },
  "dependency_refs": ["company_universe_v45", "presence_v33", "hiring_v71", "entry_v29", "regionscore_v18"]
}
Output
{
  "outputs": {
    "audit_report_id": "audit_v91",
    "findings": {
      "override_count": 4,
      "override_balance_by_region": {
        "greater_boston": 2,
        "greater_sf": 2
      },
      "classification_consistency_flag": true,
      "presence_consistency_flag": true,
      "objective_layer_integrity_flag": true,
      "personal_layer_integrity_flag": true,
      "double_counting_flag": false
    }
  },
  "metrics": {
    "checks_run": 8,
    "warnings_count": 1,
    "failures_count": 0
  }
}
Failure states
* missing required versions
* audit ruleset mismatch
* integrity-check execution failure
Retry policy
* retry transient read failures
* do not retry deterministic ruleset/config failures automatically
Success criteria
* audit report emitted
* all requested checks resolved pass/warn/fail

⸻

17. Standard Warning Schema
Warnings should be structured, not just text.
{
  "warning_code": "LOW_CONFIDENCE_ENTRY_LEVEL",
  "severity": "low | medium | high",
  "scope_type": "company | region | company_region_pair | comparison",
  "scope_ref": "comp_101::greater_boston",
  "message": "Entry-level classification confidence reduced due to incomplete role metadata."
}

⸻

18. Standard Error Schema
{
  "error_code": "DEPENDENCY_MISSING",
  "error_message": "presence_map_version presence_v33 not found",
  "error_details": {
    "missing_dependency": "presence_v33"
  }
}

⸻

19. Standard Downstream Trigger Recommendation Schema
{
  "downstream_trigger_recommendations": [
    {
      "job_type": "entry_level_refresh",
      "reason": "Hiring records changed for 4 company-region pairs",
      "scope": {
        "company_region_pairs": [
          {"company_id": "comp_101", "region_id": "greater_boston"}
        ]
      },
      "priority": "high"
    }
  ]
}

⸻

20. Retry Policy Table
Error Code	Retry?	Notes
INPUT_VALIDATION_ERROR	No	Fix payload/config first
DEPENDENCY_MISSING	No	Repair upstream job/object first
SOURCE_UNAVAILABLE	Yes	Backoff + retry
RATE_LIMITED	Yes	Exponential backoff
PARSE_FAILURE	Sometimes	Retry only if source instability suspected
INTEGRITY_CHECK_FAILED	No	Needs investigation
TIMEOUT	Yes	Retry with capped attempts
NO_MEANINGFUL_CHANGE	No	Treat as successful no-op
INTERNAL_EXCEPTION	Sometimes	Retry once, then escalate

⸻

21. Success Semantics
A job should count as successful under one of these conditions:
Full success
All requested scope processed and outputs emitted.
Successful no-op
No meaningful change detected, but job completed correctly.
Example:
* hiring refresh found no posting changes
Success with warnings
Outputs emitted, but some confidence is downgraded.
Example:
* entry-level counts produced, but recurrence signal uncertain
Partial success
Some requested scope succeeded, some failed safely.
Example:
* 8 of 10 company-region pairs refreshed, 2 source failures
This should not be treated the same as full success.

⸻

22. Minimal Idempotency Rule
Every job should be safe to rerun for the same:
* scope
* inputs
* dependency_refs
If rerun with identical inputs, it should either:
* reproduce the same output hashor
* return NO_MEANINGFUL_CHANGE
That will matter a lot for engineering reliability.

⸻