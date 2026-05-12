# DATA_MODEL.md

## Purpose

This file defines the canonical data model for MVP V1 of the job-market intelligence platform backend.

It exists to prevent schema drift during implementation.

Claude Code must treat this file as the source of truth for the MVP data model unless a later prompt explicitly updates it.

---

## Core Data Modeling Principle

The backend separates three categories of data:

1. **Canonical market truth**
   - structured, queryable records that define the actual market model

2. **Derived output objects**
   - assembled region/company/comparison payloads built from canonical truth

3. **User-specific personalization**
   - overlays and rankings computed from user preferences without mutating canonical truth

Do not collapse these layers.

---

# 1. Canonical Truth Entities

MVP V1 must support these canonical entities:

- `regions`
- `companies`
- `company_region_presence`
- `company_region_hiring`
- `company_region_entry_level`
- `region_market_scores`
- `jobs`

These are the minimum required truth-layer entities.

Optional but useful:
- `output_metadata`
- `audit_reports`
- `override_ledger`
- `confidence_events`
- `repair_actions`

---

# 2. Shared Field Conventions

Most canonical records should support some or all of the following shared fields.

## Identity fields

- `id`
- stable internal identifier
- should not be reused

## Version fields

- `version`
- `source_version_bundle` where appropriate
- `source_job_id` where appropriate

## State fields

- `state`
- object lifecycle state

MVP states:
- `new`
- `building`
- `fresh`
- `stale`
- `partial`
- `failed`
- `blocked`
- `rebuilding`

Later states:
- `low_confidence`
- `verified`
- `deprecated`

## Confidence fields

- `confidence_level`
- `confidence_notes`

Recommended confidence enum:
- `high`
- `medium`
- `low`
- `unknown`

## Freshness fields

- `freshness_expires_at`
- `last_successful_build_at`
- `last_attempted_build_at`

## Timestamp fields

- `created_at`
- `updated_at`

## Audit/source fields

- `source_refs`
- `notes`
- `warnings`

---

# 3. Entity: `regions`

## Purpose

Stores geography objects used by the app.

Regions are not just strict city boundaries. They may represent labor-market regions such as:

- Greater Boston
- Greater San Francisco / Silicon Valley
- Greater NYC
- Seattle
- Austin

## Required fields

- `region_id`
- `region_name`
- `display_name`
- `region_type`
- `parent_region_id`
- `labor_market_group`
- `normalization_profile_id`
- `state`
- `version`
- `created_at`
- `updated_at`

## Region type enum

- `city`
- `metro`
- `greater_region`
- `state`
- `custom_region`

For MVP, avoid arbitrary user-created custom regions unless explicitly requested.

## Notes

`labor_market_group` is important because the product compares opportunity by realistic work regions, not only municipal boundaries.

---

# 4. Entity: `companies`

## Purpose

Stores canonical company records, eligibility status, and classification labels.

This table answers:

- does this company belong in the product universe?
- is it eligible?
- is it override-included?
- is it major tech?
- is it Magnificent 7?

## Required fields

- `company_id`
- `company_name`
- `normalized_company_name`
- `sector_primary`
- `sector_secondary`
- `public_or_private`
- `eligibility_status`
- `eligibility_score`
- `eligibility_override_flag`
- `eligibility_override_reason`
- `classification_confidence`
- `is_major_tech`
- `major_tech_score`
- `is_mag7`
- `prestige_score`
- `state`
- `version`
- `created_at`
- `updated_at`

## Eligibility status enum

- `eligible`
- `ineligible`
- `override_included`

## Public/private enum

- `public`
- `private`
- `subsidiary`
- `unknown`

## Classification confidence enum

- `high_confidence`
- `moderate_confidence`
- `override_edge_case`
- `unknown`

## Sector scope

MVP included sector types may include:

- `software`
- `internet`
- `ai`
- `cloud`
- `data`
- `hardware`
- `cybersecurity`

Excluded by default:

- biotech-specific
- martech-specific
- very early/noisy startups
- irrelevant sectors

## Notes

`companies` stores classification truth only.  
It should not store region-specific hiring counts.  
Those belong in company-region tables.

---

# 5. Entity: `company_region_presence`

## Purpose

Stores whether a company has meaningful presence in a specific region.

This table powers the map and region/company geography logic.

## Required fields

- `presence_id`
- `company_id`
- `region_id`
- `presence_status`
- `presence_basis`
- `office_evidence_flag`
- `operations_evidence_flag`
- `hiring_evidence_flag`
- `presence_confidence`
- `state`
- `version`
- `source_refs`
- `created_at`
- `updated_at`

## Presence status enum

- `present`
- `not_present`
- `uncertain`

## Presence basis enum

- `office_plus_operations`
- `office_plus_hiring`
- `satellite_office_only`
- `insufficient_evidence`

## Presence rule

A company counts as regionally present if it has:

1. real office plus real operations  
   **or**
2. real office plus actual hiring tied to that region

Hiring evidence is preferred when available.

If hiring evidence is unavailable, a real satellite office may still suffice.

## Important constraint

Presence is primarily a scaffold/descriptive layer.  
It must not overpower hiring or entry-level access in final scoring.

---

# 6. Entity: `company_region_hiring`

## Purpose

Stores hiring activity for a company in a specific region.

This is dynamic market truth and should be refreshed more often than company classifications or geography.

## Required fields

- `hiring_id`
- `company_id`
- `region_id`
- `currently_hiring_flag`
- `active_posting_count_now`
- `posting_count_30d`
- `posting_count_90d`
- `annualized_trend_signal`
- `seasonal_student_hiring_signal`
- `hiring_program_count`
- `role_family_summary`
- `hiring_confidence`
- `state`
- `version`
- `freshness_expires_at`
- `source_refs`
- `created_at`
- `updated_at`

## Annualized trend signal enum

- `positive`
- `neutral`
- `negative`
- `unknown`

## Seasonal student hiring signal enum

- `strong`
- `moderate`
- `weak`
- `none`
- `unknown`

## Role family summary

This can be represented as structured JSON in MVP.

Example:

```json
{
  "product": 3,
  "ai_cloud_adjacent": 5,
  "cybersecurity": 2
}
Notes
This table should not parse or store every job posting in detail for MVP unless explicitly requested.
It stores aggregated hiring intelligence by company-region pair.

⸻

7. Entity: 
company_region_entry_level
Purpose
Stores early-career opportunity signals for a company in a specific region.
This is one of the most important MVP layers because the product is early-career weighted.
Required fields
* entry_level_id
* company_id
* region_id
* internship_count
* coop_count
* entry_level_full_time_count
* formal_early_career_program_flag
* student_season_recurrence_signal
* entry_level_access_score
* entry_level_confidence
* state
* version
* freshness_expires_at
* source_refs
* created_at
* updated_at
Student season recurrence signal enum
* strong
* moderate
* weak
* none
* unknown
Rule
Internships and co-ops are weighted equally.
Important constraint
Unknown or incomplete entry-level metadata must not be silently treated as zero unless the system has confirmed absence.
Use:
* unknown
* partial
* lower confidence
rather than fake precision.

⸻

8. Entity: 
region_market_scores
Purpose
Stores region-level scores derived from canonical truth records.
This table powers region rankings, comparison, and discovery.
Required fields
* region_score_id
* region_id
* structural_ecosystem_score
* live_market_score
* objective_opportunity_score
* raw_total_score
* general_density_score
* tech_market_density_score
* early_career_accessibility_score
* score_ruleset_version
* normalization_profile_id
* state
* version
* source_version_bundle
* created_at
* updated_at
Score range
Scores should generally be normalized to a consistent range, preferably:
* 0.0 to 1.0
Do not mix incompatible score ranges without explicit conversion.
Scoring hierarchy
Objective opportunity score should emphasize:
1. entry-level access
2. current hiring volume
3. prestige
Entry-level access leads, but only modestly.
Normalization rule
Do not create one opaque blended denominator.
Keep separate:
* raw total score
* general density score
* tech-market density score
* early-career accessibility score

⸻

9. Entity: 
jobs
Purpose
Stores orchestration job records and execution state.
This table supports queueing, retries, dependency checks, dedupe, and auditability.
Required fields
* job_id
* job_type
* queue_name
* status
* priority
* trigger_type
* requested_by
* scope
* scope_hash
* dedupe_key
* inputs
* options
* dependency_refs (opaque strings by default; optionally `kind:object_id@vN` for DB-backed runtime checks)
* retry_count
* max_retries
* input_hash
* output_hash
* started_at
* completed_at
* created_at
* updated_at
* error_code
* error_message
* warnings
Job status enum
* queued
* running
* succeeded
* succeeded_with_warnings
* partial
* failed
* cancelled
Trigger type enum
* scheduled
* event_driven
* manual
* user_query
Priority enum
* low
* normal
* high
* urgent
Job type examples
* geography_build
* company_universe_intake
* eligibility_classification
* presence_mapping
* hiring_refresh
* entry_level_refresh
* region_score_recompute
* region_output_build
* company_output_build
* comparison_cache_build
* personal_overlay_query
* contextual_challenge_build
* audit

⸻

10. Entity: 
output_metadata
Purpose
Stores metadata for derived output artifacts.
Actual output payloads may live in object storage or cache.This table tracks where they are and what versions they were built from.
Required fields
* output_id
* output_type
* subject_id
* artifact_uri
* artifact_hash
* source_version_bundle
* state
* freshness_expires_at
* created_at
* updated_at
Output type enum
* region_output
* company_output
* comparison_output
* contextual_challenge_output
* personalized_output
Subject ID examples
For region output:
* greater_boston
For company output:
* comp_101
For comparison output:
* greater_boston__greater_sf
Notes
Derived outputs should not become canonical market truth.
They are downstream artifacts assembled from canonical records.

⸻

11. Optional Entity: 
override_ledger
Purpose
Stores visible override decisions for company eligibility/classification.
This supports transparency and consistency.
Suggested fields
* override_id
* company_id
* override_type
* override_reason
* decision
* decided_by
* source_refs
* created_at
* updated_at
Override type enum
* eligibility_override
* classification_override
* presence_override
Decision enum
* approved
* rejected
* needs_review
MVP note
If this is not implemented as a separate table in MVP, override fields must still be visible on companies.

⸻

12. Optional Entity: 
audit_reports
Purpose
Stores integrity check outputs.
Suggested fields
* audit_report_id
* audit_mode
* scope
* findings
* warnings_count
* failures_count
* created_at
MVP note
A minimal audit report object is enough for MVP.Full admin audit dashboards are out of scope.

⸻

13. Optional Entity: 
confidence_events
Purpose
Tracks confidence downgrades/upgrades over time.
Suggested fields
* confidence_event_id
* object_type
* object_id
* previous_confidence
* new_confidence
* reason
* source_job_id
* created_at
MVP note
This can be deferred unless confidence transitions become important early.

⸻

14. Optional Entity: 
repair_actions
Purpose
Tracks repair attempts for stale, partial, failed, or low-confidence objects.
Suggested fields
* repair_action_id
* object_type
* object_id
* repair_type
* status
* source_audit_report_id
* created_at
* updated_at
MVP note
Can be deferred until the audit/repair layer matures.

⸻

15. Relationships
Region relationships
A region may have:
* one parent region
* many child regions
* one labor market group
* one normalization profile
Company relationships
A company may have:
* many company-region presence records
* many company-region hiring records
* many company-region entry-level records
* many output artifacts over time
Presence relationships
A presence record belongs to:
* one company
* one region
Presence records feed:
* hiring records
* region score computation
* company output assembly
* region output assembly
Hiring relationships
A hiring record belongs to:
* one company
* one region
Hiring records feed:
* entry-level records
* live market score
* objective opportunity score
* region/company outputs
Entry-level relationships
An entry-level record belongs to:
* one company
* one region
Entry-level records feed:
* early-career accessibility score
* objective opportunity score
* personalized discovery
* region/company outputs
Region score relationships
A region market score belongs to:
* one region
It depends on:
* company classifications
* presence records
* hiring records
* entry-level records
* normalization inputs
Output metadata relationships
Output metadata records point to:
* region/company/comparison/contextual output payloads
* source version bundles used to create them

⸻

16. Unique Constraints
Recommended uniqueness constraints:
regions
* unique region_id
companies
* unique company_id
* unique normalized company name where practical
company_region_presence
* unique pair: company_id + region_id
company_region_hiring
* unique pair: company_id + region_id + current active version strategy
For MVP, one current record per company-region pair is acceptable.
company_region_entry_level
* unique pair: company_id + region_id + current active version strategy
For MVP, one current record per company-region pair is acceptable.
region_market_scores
* unique pair: region_id + current active version strategy
For MVP, one current score record per region is acceptable.
jobs
* unique job_id
* dedupe key index
* partial unique active dedupe key for queued/running jobs where the database supports it
output_metadata
* unique active output per output_type + subject_id if using current active version

⸻

17. Recommended Indexes
Indexes should support common access paths.
Regions
* region_id
* region_type
* parent_region_id
* labor_market_group
Companies
* company_id
* normalized_company_name
* eligibility_status
* is_major_tech
* is_mag7
* sector_primary
Company-region presence
* company_id
* region_id
* presence_status
* compound: region_id, presence_status
* compound: company_id, region_id
Company-region hiring
* company_id
* region_id
* currently_hiring_flag
* compound: region_id, currently_hiring_flag
* compound: region_id, active_posting_count_now
Company-region entry-level
* company_id
* region_id
* compound: region_id, entry_level_access_score
* compound: region_id, internship_count
* compound: region_id, coop_count
Region market scores
* region_id
* objective_opportunity_score
* early_career_accessibility_score
Jobs
* job_id
* job_type
* status
* queue_name
* dedupe_key
* priority
Output metadata
* output_type
* subject_id
* compound: output_type, subject_id
* state

⸻

18. JSON / Structured Fields
Some fields can be stored as JSON-like structured payloads in MVP.
Acceptable JSON fields:
* source_refs
* role_family_summary
* source_version_bundle
* scope
* inputs
* options
* dependency_refs
* warnings
* findings
Do not hide core queryable truth in JSON if it is central to MVP behavior.
For example:
Good JSON field:
* role_family_summary
Bad JSON-only modeling:
* storing all company-region hiring logic only inside one opaque blob

⸻

19. Derived Output Object Shape
Derived output objects should be assembled from canonical truth and may be stored as artifacts.
Region output object should include
* region metadata
* region market scores
* top companies present
* top companies hiring
* entry-level summary
* major-tech summary
* Mag 7 summary
* freshness/state metadata
Company output object should include
* company metadata
* regions present
* regions hiring
* entry-level regions
* classification labels
* freshness/state metadata
Comparison output object should include
* region A summary
* region B summary
* score comparison
* category winners
* freshness/state metadata
Contextual challenge object should include
* base comparison reference
* challenge status
* changed findings
* unchanged findings
* explanation fields

⸻

20. Personalization Data
MVP personalization does not require permanent user profiles unless explicitly requested.
A personalization request can be session/request scoped.
User preference payload
Suggested fields:
* role_targets
* industry_preferences
* career_stage
* prestige_preference
* brand_preference
* region_preferences
Personalization output
Suggested fields:
* personal_market_score
* personal_company_score
* preference_match_notes
* ranked_regions
* ranked_companies
Constraint
Personalization must not mutate canonical truth tables.

⸻

21. Data State Rules
Canonical truth objects
Should be stateful and versioned.
Includes:
* regions
* companies
* presence records
* hiring records
* entry-level records
* region scores
Derived output objects
Should include:
* artifact URI or body
* source version bundle
* state
* freshness metadata
Personalization outputs
May be ephemeral/session-scoped.
Do not require durable persistence unless explicitly requested.

⸻

22. MVP Schema Boundaries
Must support in MVP
* core canonical tables
* state/version/freshness fields
* output metadata
* job table
* basic indexes
* structured JSON fields where helpful
Can defer
* full historical snapshot model
* full audit/repair tables
* permanent user accounts
* complex source-ingestion tables
* raw job posting database
* full normalized role taxonomy tables
* full normalized industry taxonomy tables

⸻

23. Important Non-Goals
Do not build these into the MVP data model unless explicitly requested:
* full applicant tracking schema
* resume/profile database
* employer accounts
* messaging tables
* application submission pipeline
* full job-posting warehouse
* scraping-source management system
* complex GIS boundary model
* arbitrary user-defined region schema

⸻

24. Implementation Guidance
When implementing this data model:
1. Start with the required canonical entities.
2. Include state/version/freshness fields early.
3. Keep relationships explicit.
4. Add indexes for common region/company access paths.
5. Avoid over-normalizing role and industry taxonomy in MVP.
6. Do not hide important score or count fields inside opaque JSON.
7. Keep output artifacts downstream from canonical truth.

⸻

25. MVP Acceptance Criteria
The MVP data model is acceptable when it can support:
1. representing supported regions
2. storing eligible and classified companies
3. mapping companies to regions
4. storing hiring activity by company-region pair
5. storing entry-level opportunity by company-region pair
6. computing and storing region scores
7. storing/referencing derived output objects
8. tracking job execution
9. preserving state/version/freshness metadata
10. supporting read APIs for region, company, comparison, and personalization flows
That is the required data model baseline.
