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

## Layer 7 Addendum: Auth/User Foundation And User-Owned Personalization

Layer 7 Batch A adds internal account identity tables that are separate from
canonical market truth and personalization overlays.

Managed auth provider decision:
- Use Auth0 for the first managed auth path.
- Do not store passwords, credential recovery state, provider secrets, or
  hand-rolled token issuance in this app database.
- Use provider-verified OIDC identity claims as the auth boundary.

Internal user identity entities:
- `users`
- `external_auth_identities`
- `user_profiles`

The stable mapping key is:

```text
provider + issuer + subject
```

For the selected provider, `provider = auth0`, `issuer` is the Auth0 tenant
issuer, and `subject` is the OIDC `sub` claim. Email, display name, and avatar
URL are profile metadata only and must not be used as identity keys.

These Batch A identity tables must not store saved preferences, saved markets,
recommendation snapshots, privacy/export/delete workflow state, canonical
objective market truth, objective scores, source freshness, ingestion outputs,
company canonical state, or region canonical state.

### Entity: `users`

Purpose:
Stores the stable internal app user id.

Required fields:
- `user_id`
- `status`
- `admin_role`
- `created_at`
- `updated_at`

`admin_role` is nullable. Valid non-null Layer 9A values are `admin`,
`data_reviewer`, and `read_only_operator`.

### Entity: `external_auth_identities`

Purpose:
Maps a managed-provider identity to one internal app user.

Required fields:
- `external_identity_id`
- `user_id`
- `provider`
- `issuer`
- `subject`
- `email`
- `email_verified`
- `last_seen_at`
- `created_at`
- `updated_at`

Required constraints:
- unique (`provider`, `issuer`, `subject`)
- foreign key `user_id` → `users.user_id`

### Entity: `user_profiles`

Purpose:
Stores non-preference profile metadata sourced from the managed provider.

Required fields:
- `user_id`
- `display_name`
- `email`
- `avatar_url`
- `created_at`
- `updated_at`

Required constraints:
- foreign key `user_id` → `users.user_id`

### Entity: `user_preference_profiles`

Purpose:
Stores durable user-owned personalization inputs. These inputs may be used by
personalization overlays, but they must not update objective market truth.

Required fields:
- `user_id`
- `role_interests`
- `industry_interests`
- `preferred_regions`
- `prestige_weighting`
- `brand_weighting`
- `career_stage`
- `remote_hybrid_preference`
- `scoring_weights`
- `created_at`
- `updated_at`

Required constraints:
- foreign key `user_id` → `users.user_id`
- one preference profile per user

### Layer 11A Addendum: Retention Foundation

Batch 11A keeps retention data in the existing user-owned personalization
tables. It does not introduce a new market-truth table or a second scoring
source of truth.

`user_preference_profiles.scoring_weights` stores transparent user-adjustable
overlay weights for entry-level access, hiring density, prestige, industry fit,
and role fit. These weights are user-owned inputs. They may be used to preview
personalized scores, but they must not update `region_market_scores`, output
metadata, canonical companies, canonical regions, source freshness, provenance,
or ingestion records.

### Entity: `saved_market_artifacts`

Purpose:
Stores user-owned saved references or lightweight snapshots for objective
market artifacts. Saved snapshots are display/user context only and must not be
promoted into canonical region, company, score, source, or ingestion records.
For Batch 11A watchlists, rows should reference canonical identifiers through
`artifact_ref`; they must not duplicate canonical scores, company facts, region
facts, freshness facts, or scoring results into user-owned rows.
The API enforces this boundary by accepting only narrow reference/configuration
metadata in `snapshot`; copied scores, freshness/provenance/source summaries,
evidence, company/region detail payloads, hiring facts, entry-level signals,
and assembled market outputs are rejected.

Required fields:
- `saved_artifact_id`
- `user_id`
- `artifact_type`
- `artifact_ref`
- `label`
- `notes`
- `snapshot`
- `created_at`
- `updated_at`

Allowed `artifact_type` values:
- `region`
- `company`
- `role_family`
- `comparison`
- `discovery_result`

Required constraints:
- foreign key `user_id` → `users.user_id`
- unique (`user_id`, `artifact_type`, `artifact_ref`)

### Entity: `personalized_recommendation_snapshots`

Purpose:
Stores durable user-owned personalized recommendation outputs. These snapshots
are derived from user preferences and objective market outputs. They may record
which objective outputs were used, but they must not update canonical region,
company, score, source, freshness, or ingestion records.

Required fields:
- `recommendation_snapshot_id`
- `user_id`
- `preference_profile_id`
- `personalized_output`
- `recommendation_version`
- `source_version_bundle`
- `objective_output_refs`
- `recommendation_inputs_hash`
- `generated_at`
- `created_at`
- `updated_at`

Required constraints:
- foreign key `user_id` → `users.user_id`
- nullable foreign key `preference_profile_id` →
  `user_preference_profiles.user_id`
- retrieval must be scoped by internal `users.user_id`

### Layer 11B Addendum: Change/Expansion Engine

Batch 11B adds in-app alert metadata and a region-expansion workflow contract.
It does not create a new market-truth source, a second ingestion pipeline,
notification delivery infrastructure, advanced visualization, or AI
explanations.

### Entity: `alert_events`

Purpose:
Stores system-level detected change events derived from structured
refreshable/canonical/derived data or approved snapshot contracts. Alert
events are change metadata, not canonical market truth.

Supported event types:
- `new_hiring_activity`
- `entry_level_signal_changed`
- `company_expanded_in_region`
- `region_score_changed`
- `internship_window_opened`

Required fields:
- `alert_event_id`
- `event_type`
- `company_id`
- `region_id`
- `role_family`
- `previous_value`
- `new_value`
- `change_summary`
- `freshness_status`
- `freshness_observed_at`
- `freshness_expires_at`
- `source_refs`
- `change_basis_refs`
- `detection_basis`
- `created_at`

`previous_value`, `new_value`, and `change_summary` may contain only bounded
primitive change metadata. They must not store full company/region detail
payloads, source/provenance payloads, assembled market outputs, or copied
canonical rows.

### Entity: `user_alerts`

Purpose:
Stores user-specific in-app alert instances linked to one `alert_events` row.
The relevance reason is user-owned overlay metadata such as saved company,
saved region, saved comparison, saved role family, preferred region, or role
interest.

Required fields:
- `user_alert_id`
- `user_id`
- `alert_event_id`
- `relevance_reason`
- `relevance_artifact_id`
- `relevance_artifact_type`
- `relevance_artifact_ref`
- `is_read`
- `dismissed`
- `created_at`
- `updated_at`
- `read_at`
- `dismissed_at`

Required constraints:
- foreign key `user_id` -> `users.user_id`
- foreign key `alert_event_id` -> `alert_events.alert_event_id`
- unique (`user_id`, `alert_event_id`)

### Entity: `region_expansion_workflows`

Purpose:
Stores repeatable operator workflow/checklist state for region expansion. Rows
coordinate with existing ingestion, provenance, admin review, output, and
refresh systems by reference only. They do not create canonical region rows,
ingest data, publish output, or enable refresh by themselves.

Workflow states:
- `candidate`
- `intake_started`
- `normalized`
- `provenance_attached`
- `review_ready`
- `approved`
- `published`
- `refresh_enabled`

Region data modes:
- `seed_demo`
- `candidate`
- `real_refreshable`

Required checklist fields:
- `region_identity_check`
- `source_coverage_check`
- `company_region_presence_check`
- `hiring_signal_support_check`
- `entry_level_signal_support_check`
- `scoring_readiness_check`
- `freshness_readiness_check`
- `provenance_attached_check`
- `admin_approval_check`
- `output_refresh_readiness_check`

The initial planned target set is NYC, Seattle, Austin, DC/NoVA, Boston, SF,
Atlanta, Chicago, and LA. Target candidates are not automatically approved,
published, or refresh-enabled.

### Layer 11C Addendum: Product Surface And Explanation

Batch 11C does not add canonical tables. Advanced visualization is a read-only
product surface over existing region/company/comparison outputs, scoring
breakdowns, alert metadata, freshness/source summaries, and explicit
unsupported states. Visualization code must not create hidden scoring formulas,
infer trends without historical snapshots, infer geography without stored
metadata, or imply heatmap/network precision that is not present in structured
data.

The explanation layer uses validated evidence packets and deterministic local
rendering. Evidence packets may carry canonical/default score fields,
personalized overlay fields, scoring factor evidence, freshness labels,
source/provenance refs or safe summaries, alert/change metadata, watchlist
context, missing-data flags, unsupported-data flags, and seeded/demo status.
They are request payloads only and are not persisted as canonical truth.

No external AI provider integration is configured in Batch 11C. Explanation
output is guidance text derived from supplied structured evidence only. It must
not be used as a data-ingestion path, stored as market truth, or used to mutate
regions, companies, scores, freshness, provenance, outputs, alerts, admin
records, or region-expansion workflows.

### Layer 7 Batch D Privacy Controls

App-level privacy controls operate only on Layer 7 user-owned data. They may:

- export the current user's `users`, `user_profiles`,
  `external_auth_identities`, `user_preference_profiles`,
  `saved_market_artifacts`, and `personalized_recommendation_snapshots` data
- delete the current user's saved preference profile
- delete the current user's saved market artifacts
- delete the current user's personalized recommendation snapshots
- deactivate the current app-level user account
- export and delete current-user `user_alerts` as app-owned user data

Privacy controls must not export, delete, or mutate canonical market truth:
`regions`, `companies`, `company_region_presence`, `company_region_hiring`,
`company_region_entry_level`, `region_market_scores`, `source_refs`,
`source_observations`, `fact_source_links`, `raw_ingestion_records`, or
objective output metadata.

App account deactivation is a soft-delete pattern for the internal `users`
row. It deletes profile, external auth identity mapping, preference, saved
artifact, and recommendation snapshot rows for the current user, then sets
`users.status = deactivated`. The internal `user_id` tombstone remains to avoid
identifier reuse and preserve the app-owned identity boundary.

Auth0/provider-side account deletion is outside Batch D and remains deferred
until a protected provider-management integration exists.

---

## Layer 9A Addendum: Admin Roles And Admin Event Log Foundation

Layer 9A adds governed admin authorization roles and an append-only admin event
log. It does not add raw database mutation endpoints.

Admin roles:

- `admin`: admin review access and future controlled admin mutation access.
- `data_reviewer`: review workflow access and future limited review actions.
- `read_only_operator`: read-only admin/review inspection.

Reusable backend authorization dependencies must enforce these roles for admin
surfaces. Frontend-only checks are not sufficient.

### Entity: `admin_event_logs`

Purpose:
Append-only record of governed admin/review actions.

Required fields:
- `admin_event_id`
- `actor`
- `actor_role`
- `action`
- `object_type`
- `object_id`
- `before_state`
- `after_state`
- `reason`
- `timestamp`
- `request_id`

Rows are append-only. Corrections or follow-up decisions must append a new
record instead of updating or deleting prior records.

---

## Layer 9B Addendum: Admin Data Review And Audit Finding Lifecycle

Layer 9B adds read-only admin review surfaces for production market/source
records and a controlled lifecycle for audit findings. It does not add
overrides, repairs, raw database update endpoints, or automatic production data
changes.

Reviewable object types:

- companies
- company-region presence facts
- company-region hiring facts
- company-region entry-level facts
- source refs
- audit findings

All admin roles may inspect review data. Only `admin` and `data_reviewer` may
perform audit finding lifecycle transitions. `read_only_operator` remains
read-only.

Audit finding lifecycle states:

- `open`
- `acknowledged`
- `resolved`
- `dismissed`
- `escalated`

Allowed transitions:

- `open` -> `acknowledged`, `escalated`, `dismissed`
- `acknowledged` -> `resolved`, `escalated`, `dismissed`
- `escalated` -> `acknowledged`, `resolved`, `dismissed`
- `resolved` -> `open`
- `dismissed` -> `open`

Every lifecycle transition requires a reason, actor, role, and timestamp, and
must append an `admin_event_logs` record carrying before and after lifecycle
state. Lifecycle state changes do not mutate canonical market/source records.

### Entity: `audit_finding_reviews`

Purpose:
Stores persistent review lifecycle state for deterministic audit findings.

Required fields:
- `finding_id`
- `review_state`
- `category`
- `severity`
- `scope_type`
- `scope_ref`
- `message`
- `evidence_refs`
- `recommendation`
- `created_at`
- `updated_at`
- `last_transitioned_at`
- `last_transition_actor`
- `last_transition_role`
- `last_transition_reason`

Required constraints:
- primary key `finding_id`
- `review_state` must be one of `open`, `acknowledged`, `resolved`,
  `dismissed`, `escalated`

---

## Layer 9C Addendum: Controlled Overrides And Safe Repair Actions

Layer 9C adds governed override and repair workflow records. Overrides are
separate overlay records: canonical company, presence, and source rows remain
visible and recoverable, and creating or activating an override does not
silently rewrite canonical truth.

Supported override types:

- `company_eligibility` on `company`
- `company_classification` on `company`
- `presence_status` on `presence_fact`
- `source_confidence` on `source_ref`

Override statuses:

- `proposed`
- `active`
- `expired`
- `revoked`
- `superseded`

Only non-expired records with `active` status behave as active overlays in
admin review responses.

All override mutations require actor, role, reason, source/evidence, and either
an expiration timestamp or review timestamp. `admin` and `data_reviewer` may
propose overrides. Only `admin` may activate or revoke overrides.
`read_only_operator` may inspect override records only.

### Entity: `admin_overrides`

Purpose:
Stores visible override overlays for governed review workflows.

Required fields:
- `override_id`
- `target_type`
- `target_id`
- `override_type`
- `previous_value`
- `override_value`
- `reason`
- `reviewer_actor`
- `reviewer_role`
- `source_evidence`
- `expires_at`
- `review_at`
- `status`
- `created_at`
- `updated_at`
- `activated_at`
- `activated_by`
- `activated_role`
- `revoked_at`
- `revoked_by`
- `revoked_role`
- `revocation_reason`

Repair actions are explicit workflow records. Audit findings may reference or
motivate repair records, but audit finding lifecycle transitions do not
auto-repair production data.

Supported repair action types:

- `recompute_score`
- `rebuild_output`
- `mark_source_stale`
- `request_review`
- `deactivate_bad_fact`

`recompute_score` uses the existing scoring service path. `rebuild_output` uses
the existing output assembly/cache path. Source stale and bad-fact deactivation
preserve source/provenance history; facts and sources are not deleted.

### Entity: `admin_repair_actions`

Purpose:
Stores requested and executed safe repair workflow actions.

Required fields:
- `repair_action_id`
- `action_type`
- `target_type`
- `target_id`
- `status`
- `reason`
- `requested_by`
- `requested_role`
- `requested_at`
- `executed_by`
- `executed_role`
- `executed_at`
- `audit_finding_id`
- `parameters`
- `result`
- `created_at`
- `updated_at`

All override and repair mutations append an `admin_event_logs` record carrying
actor, role, action, object, before/after state, reason, timestamp, and request
id when available.

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
- `source_refs`
- `source_observations`
- `fact_source_links`

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

## Layer 3B Addendum: Provenance Schema

Layer 3B adds structural provenance tables so facts can be bound to source
observations before real data import exists. These tables do not imply scraping,
ingestion, external API calls, audit enforcement, or source quality scoring.

### Entity: `source_refs`

Stores a source or provider that observations may reference.

Required fields:
* source_id
* source_type
* source_name
* url_or_provider
* collected_at
* observed_at
* license_or_terms_category
* confidence
* data_origin
* notes
* state
* version
* created_at
* updated_at

### Entity: `source_observations`

Stores a dated observation made against a source reference. Observation rows
snapshot source metadata so later source-reference edits do not erase the
context used for a specific fact.

Required fields:
* observation_id
* source_id
* source_type
* source_name
* url_or_provider
* collected_at
* observed_at
* license_or_terms_category
* confidence
* data_origin
* observation_status
* notes
* state
* version
* created_at
* updated_at

### Entity: `fact_source_links`

Stores a structural binding between a fact and a source observation. The link
is polymorphic by `fact_type` and `fact_id` so it can bind provenance to:

* company facts
* region facts
* company-region presence facts
* hiring facts
* entry-level / internship / co-op / early-career facts
* score input facts

Required fields:
* link_id
* observation_id
* source_id
* fact_type
* fact_id
* fact_field
* source_type
* source_name
* url_or_provider
* collected_at
* observed_at
* license_or_terms_category
* confidence
* data_origin
* observation_status
* notes
* state
* version
* created_at
* updated_at

Seed/demo links must remain labeled as `demo_seed` /
`synthetic_or_curated_demo` and must not be presented as factual public market
coverage. `real_observed` links require a bound `source_observation`.

### Layer 3C value semantics

Count-like market fields must preserve unknown/zero distinctions:

* missing values remain `unknown` or `not_collected`
* explicit `0` is `zero_observed` only with an observed basis
* stale values remain distinguishable from current observed zero
* output summaries may use `null` rather than `0` when totals cannot be
  computed from current observed counts
* scoring input preparation may omit unknown components, but must not convert
  them to zero

Provenance freshness is evaluated from `observed_at` plus the Layer 3A
freshness window for the underlying fact category. `score_input` bindings must
declare the source fact category used for freshness evaluation.

### Layer 3D provenance audit findings

Provenance audit findings are structured in-memory diagnostics. They are not
stored in a new table in Layer 3D and do not enforce write paths.

Each finding includes:

* code
* severity (`info`, `warning`, `error`, `critical`)
* affected fact type / fact id when available
* source id / observation id when available
* explanation
* remediation
* whether it blocks real-data trust

The checks detect missing provenance, stale source observations,
single-source overreliance, low-confidence concentration, seed/real provenance
mixtures, and unknown values prepared as observed zero.

### Layer 4A raw ingestion intake records

Layer 4A introduces raw ingestion structure only. It does not scrape, schedule,
call external APIs, run background workers, or write trusted canonical facts.

The intended pipeline boundary is:

1. raw intake artifact
2. normalization result
3. provenance attachment
4. canonical fact proposal
5. later canonical fact creation
6. downstream scoring/output rebuild

`raw_ingestion_records` store externally observed payloads before
canonicalization. They carry provider/source identity, external entity id, raw
payload, checksum, collected/observed timestamps, ingestion status,
normalization status, optional normalized payload, parsing notes/errors, schema
version, intended canonical fact type, and optional Layer 3 `source_id` /
`observation_id` references.

Raw intake is not factual public market truth. A raw record may be stored,
parsed, normalized, rejected, marked conflicting, or routed for manual review
without creating or modifying canonical company, region, presence, hiring,
entry-level, or score rows.

Canonical fact proposals are allowed only after the intake record is normalized
and linked to provenance-compatible Layer 3 records. The proposal remains a
contract object; Layer 4A does not persist trusted facts from it.

### Layer 4B source adapter boundary

Source adapters are deterministic input-preparation boundaries. They accept
explicit inputs and return adapter results containing raw-intake definitions,
diagnostics, source metadata, and run metadata.

Layer 4B adds a manual research adapter for operator-supplied observations.
The adapter validates Layer 3 source vocabulary, records confidence and
license/terms metadata in the adapter result, flags source types that require
manual review, rejects disallowed factual evidence such as `llm_generated`,
and emits `RawIntakeDefinition` objects only.

Adapter output may be stored as `raw_ingestion_records` through the ingestion
service. This is still raw intake. It does not create `SourceRef`,
`SourceObservation`, `FactSourceLink`, company, region, presence, hiring,
entry-level, score, output, or audit rows. Provenance attachment,
normalization, canonical fact proposal, and canonical fact creation remain
separate stages.

Layer 4B does not introduce live scraping, browser automation, external API
calls, background workers, scheduling, autonomous crawling, or canonical fact
writes.

### Layer 4C normalization boundary

Normalizers transform raw intake into structured normalized observations. They
operate after adapter output has been stored as raw intake and before any
provenance attachment or canonical fact proposal is trusted.

The Layer 4C boundary is:

1. `raw_ingestion_records.raw_payload`
2. normalizer result with diagnostics and normalized fields
3. stored normalization status / normalized payload on the raw intake record
4. explicit Layer 3 provenance attachment
5. canonical fact proposal
6. later canonical fact write path

Manual observation normalizers cover company, region, company-region presence,
hiring, internships/co-ops, early-career programs, and score-input intents.
They validate required fields, mark malformed payloads as rejected, mark
conflicting payloads as requiring manual review, and preserve Layer 3
observation statuses.

Count-like fields must keep unknown/zero semantics during normalization:

* absent counts remain `not_collected`
* `None` counts remain `unknown`
* stale counts remain `stale`
* `0` becomes `zero_observed` only when the manual payload explicitly supplies
  an observed basis

Normalization does not create `SourceRef`, `SourceObservation`,
`FactSourceLink`, canonical truth rows, scores, outputs, jobs, schedules, or
external-source activity.

### Layer 4D explicit provenance attachment

Layer 4D adds the explicit provenance-attachment stage between normalization
and canonical fact proposal:

1. raw intake record
2. normalized payload and normalization status
3. explicit provenance attachment
4. canonical fact proposal object
5. later canonical fact write path

Attachment creates or reuses Layer 3 `SourceRef` and `SourceObservation`
records from normalized-intake metadata, then stores their identifiers on the
raw intake record. It preserves source type, source name, provider/URL,
collected/observed timestamps, license/terms category, confidence, data
origin, observation status, and notes.

Attachment does not create `FactSourceLink` rows, canonical company/region/
presence/hiring/entry-level records, score inputs, outputs, jobs, schedules,
or external-source activity. Layer 3 audit checks remain diagnostic rather
than runtime-blocking enforcement.

`llm_generated` and other disallowed source types cannot attach as factual
market provenance. Inputs that require manual review may attach provenance
only with that review requirement preserved and reported; they are not treated
as fully trusted current facts.

Canonical fact proposals require explicit provenance attachment. A normalized
raw record without attached `source_id` and `observation_id` cannot produce a
proposal object, and a proposal object still does not write canonical truth.

### Layer 4E proposal review and source linking

Layer 4E adds an explicit review step after a canonical fact proposal exists:

1. provenance-attached normalized intake
2. canonical fact proposal object
3. operator/reviewer approval or rejection
4. `FactSourceLink` creation for approved proposals
5. later canonical fact write path

Proposal review status is distinct from normalization status and canonical
fact state. Supported review outcomes include `proposed`,
`approved_for_linking`, `rejected`, `requires_manual_review`,
`linked_to_source`, and `failed`.

An approved proposal may create or reuse a `FactSourceLink` that binds the
proposed fact id, fact binding type, and fact field to the existing
`SourceObservation`. This source-linked proposal is still not a canonical
company, region, presence, hiring, entry-level, score, or output row.

Rejected proposals create no source link. Proposals with manual-review markers
default to `requires_manual_review`; they can link only when an explicit
review override and reviewer note are supplied. Disallowed source types such
as `llm_generated` cannot be linked as factual market evidence.

Layer 4E does not write canonical domain facts, run scoring, rebuild outputs,
run audits as blocking enforcement, schedule workers, or collect external
data.

### Layer 4F canonical write plans

Layer 4F translates an approved source-linked proposal into a dry-run
canonical write plan:

1. approved source-linked proposal
2. canonical write plan
3. later explicit canonical write execution
4. later scoring/output refresh

The plan describes intended operations only. Supported operation types include
`create`, `update`, `no_op`, `reject`, and `requires_manual_review`. Each plan
records the raw intake id, fact intent, target table/entity type, target
identifier, proposed field changes, provenance link id, confidence,
observation status, diagnostics, and `dry_run=true`.

The planner may inspect existing canonical rows to decide whether a future
write would be a create, update, no-op, unsupported mapping, or manual-review
case. It does not execute the write.

Unknown, not-collected, and stale count-like values remain null in the plan
and are not converted to zero. A zero count is planned only when the normalized
payload carries `zero_observed` status. Risky conflicts, such as a proposed
presence status disagreeing with an existing categorical presence status, are
returned as `requires_manual_review` diagnostics instead of overwrite plans.

Score-input proposals remain source-linked but are not mapped to canonical
score rows in Layer 4F; they return an unsupported/manual-review diagnostic
rather than guessing at a write target.

Layer 4F does not mutate company, region, presence, hiring, entry-level,
score, output, job, or audit tables; does not create additional provenance
links; and does not trigger scoring/output refreshes.

### Layer 4G manual canonical write execution

Layer 4G adds the first ingestion path that may mutate canonical domain rows,
but only through an explicit manual execution gate:

1. dry-run canonical write plan
2. manual execution decision with explicit approval
3. narrow canonical write execution
4. later scoring/output refresh

Execution decisions include the deterministic plan id, approval boolean,
operator note or rejection reason, and timestamp. A rejected or unapproved
decision produces no canonical write.

Executable plans must be dry-run plans with status `planned` or `no_op`, must
contain a supported operation, and must be backed by an existing
`FactSourceLink`. Plans marked `rejected`, `failed`, `unsupported`, or
`requires_manual_review` are blocked in Layer 4G.

Supported write targets are:

* `companies`
* `regions`
* `company_region_presence`
* `company_region_hiring`
* `company_region_entry_level`

`score_input` execution remains unsupported because there is no narrow
canonical score-input table in this layer. Scoring remains downstream.

Where canonical models carry `source_refs`, execution stores the
`fact_source_link_id`, `source_id`, and `observation_id` so the canonical row
remains traceable back to Layer 3 provenance. Company and region rows remain
traceable through the existing `FactSourceLink`.

Unknown, not-collected, and stale count-like values are allowed to execute
only as nulls. They must not execute as numeric zero. Numeric zero can execute
only when the plan marks the value as `zero_observed`.

Repeated execution of an already-applied plan returns `already_applied` and
does not duplicate rows or bump versions. `no_op` plans remain no-op.

Layer 4G does not add scraping, external APIs, workers, schedules, automatic
plan execution, scoring rewrites, output refresh triggers, or global runtime
audit blocking.

### Layer 4H post-write refresh plans

Layer 4H adds a dry-run planning stage after an approved canonical write
execution:

1. canonical write execution result
2. post-write refresh plan
3. later explicit score/output/audit refresh execution

The plan describes affected downstream artifacts only. It records the source
execution plan id, raw intake id, changed canonical entity type and id,
affected company ids, affected region ids, refresh targets, diagnostics, and
`dry_run=true`.

Supported target vocabulary includes:

* `region_score`
* `company_score`
* `region_output`
* `company_output`
* `comparison_output`
* `contextual_output`
* `provenance_audit`
* `unknown_or_unsupported`

Layer 4H maps canonical writes conservatively:

* company writes affect the company output and any region scores/outputs for
  regions where that company already has presence, hiring, or entry-level rows
* region writes affect that region's score and output
* company-region presence writes affect that region's score/output and that
  company's output
* hiring writes affect that region's score/output and that company's output
* internship, co-op, and early-career writes affect that region's score/output
  and that company's output

The planner may include a `provenance_audit` target, but it does not run the
audit. Comparison, contextual, and company-score dependency execution remains
deferred unless a concrete downstream mapping exists.

Layer 4H refuses rejected, blocked, failed, or unapproved write executions.
`no_op` and `already_applied` executions produce no-op refresh plans. Unsupported
execution target types return structured diagnostics rather than guessed
dependencies.

Layer 4H does not recompute scores, rebuild outputs, run audits, enqueue jobs,
schedule workers, trigger external collection, or mutate refresh/task tables.

### Layer 4I post-write refresh execution

Layer 4I adds a manual-only synchronous execution gate for supported
post-write refresh plans:

1. dry-run post-write refresh plan
2. manual refresh execution decision with explicit approval
3. synchronous refresh of supported local artifacts

Refresh execution decisions include the deterministic refresh plan id,
approval boolean, operator note or rejection reason, timestamp, and optional
expected target count. Unapproved, rejected, failed, unsupported, or no-op
plans do not run refresh work.

Supported refresh target execution is intentionally narrow:

* `region_score` uses the existing region scoring recompute service
* `region_output` uses the existing region output assembly service
* `company_output` uses the existing company output assembly service

These executions are synchronous and bounded to the requested targets. They
reuse existing idempotent upsert behavior: repeated score or output refreshes
update the same deterministic rows, and unchanged rebuilds return no-op /
unchanged outcomes rather than duplicate artifacts.

Unsupported or deferred targets return structured diagnostics:

* `company_score` remains unsupported because no canonical company-score row
  exists
* `comparison_output` and `contextual_output` remain deferred until an exact
  affected-pair mapping is introduced
* `provenance_audit` is reported as deferred; Layer 4I does not run audits or
  make audit findings block already-executed canonical writes
* `unknown_or_unsupported` remains diagnostic only

Layer 4I does not scrape, call external APIs, add workers, enqueue jobs,
schedule refreshes, create ingestion records, create or mutate provenance
records, create `FactSourceLink` rows, rewrite scoring formulas, or globally
enforce provenance audits at runtime.

### Layer 4J manual ingestion orchestration

Layer 4J adds a bounded orchestration helper for the existing manual ingestion
flow. It composes existing Layer 4 steps; it does not introduce a broad ETL
framework, background workers, scheduling, crawling, scraping, or external API
collection.

The default mode is `dry_run_only`. A default run may store raw intake,
normalize it, attach Layer 3 provenance, and produce a canonical fact proposal,
but it stops before proposal review/linking. It does not execute canonical
writes or refreshes.

Supported run modes are:

* `dry_run_only`
* `link_only`
* `execute_write_with_approval`
* `execute_write_and_refresh_with_approval`

The orchestration result exposes each stage that ran:

* adapter result
* raw record ids stored or reused
* normalization result
* provenance attachment result
* canonical proposal
* proposal review/link result
* canonical write plan
* write execution result, only when explicitly approved
* post-write refresh plan, only after a successful write
* refresh execution result, only when separately approved
* diagnostics and final status

Trust boundaries remain explicit:

* proposal review/linking requires a supplied review decision
* canonical write execution requires a matching
  `CanonicalWriteExecutionDecision`
* refresh execution requires a separate
  `PostWriteRefreshExecutionDecision`
* manual-review-required states are surfaced and not silently overridden
* disallowed sources and malformed payloads stop safely with diagnostics
* unknown/not-collected/stale values remain distinct from observed zero

The orchestration helper reuses existing idempotent behavior where available.
Existing raw intake is reused by raw record id, provenance records and
`FactSourceLink` rows use existing upsert/idempotency paths, and repeated
link-only runs do not duplicate links.

Layer 4J does not auto-run destructive writes, auto-run refreshes, enqueue
jobs, create schedules, run workers, rewrite score/output formulas, make
provenance audits globally blocking, or fetch external data.

⸻

11. Optional Entity: 
override_ledger
Purpose
Stores visible override decisions for company eligibility/classification.
This supports transparency and consistency.
Layer 9C implements this capability as `admin_overrides` rather than the older
`override_ledger` sketch.
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
Implemented override workflow records are separate from canonical company and
fact rows; active overlays are surfaced on admin review responses.

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
Layer 9C implements this capability as `admin_repair_actions`.
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
Implemented as an explicit admin workflow record. Repair actions do not delete
facts, sources, observations, or provenance links.

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
