# Layer 13: Refresh Quality Control Plane

Date: 2026-05-26

## Purpose

Layer 13 moves the system from manually curated snapshots toward
controlled, reviewable data-maintenance workflows. It adds read-only helpers
for identifying weak, stale, missing, or regressed data quality signals and
preparing human review handoffs.

This is a refresh-quality control plane. It is not a scraping layer and not an
automatic canonical mutation layer.

## Implemented Slices

- Slice 13.1 Refresh Candidates
- Slice 13.2 Source Refresh Queue
- Slice 13.3 Human-in-the-Loop Review
- Slice 13.4 Quality Regression Detection
- Slice 13.5 Refresh Dashboard

## Backend Package

The implementation lives in `backend/refresh_quality/`:

- `models.py`: Pydantic records and vocabularies for candidates, queue items,
  source posture, and regressions
- `candidate_detection.py`: pure detection over already-loaded fact metadata
- `source_queue.py`: conversion from candidates to reviewable source-refresh
  work items
- `observations.py`: candidate observation records from refresh work
- `validation.py`: validation results and recommended review decisions
- `review.py`: explicit human review decision records
- `approval.py`: approved canonical update handoff intent records
- `audit.py`: audit records for validation, review, and handoff actions
- `regression_detection.py`: quality regression checks over current-vs-prior
  quality metadata
- `dashboard.py`: read-only dashboard payload builder
- `quality_metrics.py`: bounded comparison helpers and thresholds

No database table, migration, repository, API route, frontend dashboard,
scheduler, worker, or queue adapter is added in Batches 1-2.

## Refresh Candidates

`RefreshCandidate` is diagnostic metadata only. It is not a `CanonicalFact`, not
a `CandidateObservation`, and not evidence that a new fact is true.

Required candidate reasons are represented as stable enum values:

- `stale_hiring_count`
- `expired_internship_data`
- `old_company_region_presence_data`
- `low_confidence_source_fact`
- `missing_source_fact`
- `stale_entry_level_signal`
- `coverage_gap`

Candidate records preserve a stable key, entity type/id, fact type, reason,
severity, status, explanation, evidence context, current value, timestamp,
confidence, and recommended source target where available.

## Source Refresh Queue

`SourceRefreshQueueItem` records reviewable research work linked to a refresh
candidate. It is not an executable scraping job.

Source target types are:

- `company_page`
- `company_careers_page`
- `public_job_board`
- `government_open_dataset`
- `university_coop_public_employer_list`
- `company_internship_page`
- `manual_research_required`

Legal/terms posture values are:

- `MANUAL_ONLY`
- `PUBLIC_DATASET_ALLOWED`
- `TERMS_REVIEW_REQUIRED`
- `DISALLOWED`
- `UNKNOWN`

Public job board queue items default to `TERMS_REVIEW_REQUIRED` and cannot be
treated as public datasets. Company pages and careers/internship pages default
to `UNKNOWN` posture so a reviewer must decide the allowed handling before any
future automation.

## Candidate Observations

`CandidateObservation` records proposed evidence from refresh work. It links to
a refresh candidate and/or queue item, preserves the target entity/fact,
previous/current value, proposed value, source evidence reference, source type,
legal posture, confidence, status, explanation, and observed timestamp when
available.

Observation statuses are:

- `PENDING_VALIDATION`
- `VALIDATED`
- `NEEDS_MORE_EVIDENCE`
- `REJECTED`
- `APPROVED_FOR_HANDOFF`

Candidate observations are proposed evidence only. They are not canonical
truth and do not update source observations, market facts, scores, rankings,
coverage, personalization, caches, or outputs.

## Validation

`ObservationValidationResult` records whether an observation is ready for human
review and which review decision is recommended. Validation states are:

- `PASSED`
- `PASSED_WITH_WARNINGS`
- `FAILED`

Recommended review decisions are:

- `APPROVE`
- `REJECT`
- `NEEDS_MORE_EVIDENCE`
- `POLICY_BLOCK`

Validation checks for required fields, source evidence, disallowed legal
posture, public-job-board policy risk, minimum confidence, suspicious numeric
change, missing prior value, stale evidence timestamp, contradiction with the
current value, low-confidence source posture, and source dominance risk when
provided.

Validation does not approve or mutate data. Public job board observations are
never automatically recommended for approval.

## Human Review

`HumanReviewRecord` records an explicit human/admin decision over an
observation and optional validation result. Review decisions are:

- `APPROVED`
- `REJECTED`
- `NEEDS_MORE_EVIDENCE`
- `DUPLICATE`
- `OUT_OF_SCOPE`
- `POLICY_BLOCKED`

A review decision is auditable metadata only. It does not mutate canonical
truth by itself. Approval requires a non-failed validation result.

## Approved Handoff

`ApprovedCanonicalUpdateHandoff` is produced only from an `APPROVED` review.
It preserves the approved observation, review decision, target entity/fact,
old/current/proposed values, source evidence reference, validation summary,
reviewer identifier, audit metadata, output-rebuild-needed flag, and status.

Handoff statuses are:

- `PREPARED`
- `WAITING_CANONICAL_APPLY`
- `APPLIED_EXTERNALLY`
- `REJECTED_BEFORE_APPLY`
- `SUPERSEDED`

The handoff is an intent/request object. It does not directly apply canonical
updates, mutate scores, invalidate caches, rebuild outputs, or bypass any
existing canonical write boundary.

## Audit Records

`RefreshQualityAuditRecord` captures validation, review, and handoff actions.
Audit action types are:

- `OBSERVATION_VALIDATED`
- `REVIEW_DECISION_RECORDED`
- `APPROVED_HANDOFF_PREPARED`
- `REVIEW_REJECTED`
- `POLICY_BLOCKED`
- `NEEDS_MORE_EVIDENCE`

Audit records preserve original/current/proposed facts, source evidence
references, validation summaries, reviewer decisions, affected company/region
identifiers when available, timestamp, and output rebuild handoff status when
applicable.

## Quality Regressions

`QualityRegressionRecord` flags risk when quality becomes worse. It explains
the regression and recommends human review. It must not repair data, rewrite
scores, change rankings, or rebuild outputs.

Regression types are:

- `source_disappeared`
- `suspicious_hiring_count_drop`
- `company_region_presence_contradicted`
- `entry_level_signal_became_stale`
- `single_source_dominates_market_score`
- `market_score_relies_too_heavily_on_low_confidence_facts`
- `coverage_gap_worsened`
- `repeated_refresh_failure`

## Dashboard

`RefreshDashboardPayload` is a backend read-model payload assembled from
supplied Layer 13 records. It summarizes:

- stale regions
- stale companies
- failed refresh jobs or repeated refresh failures
- low-confidence facts
- coverage gaps
- audit warnings
- refresh queue items
- pending review items
- approved update handoffs
- rejected observations
- policy-blocked observations
- quality regressions

No API route or frontend/admin UI is wired in Batch 2. The existing admin API
has governed patterns, but without durable refresh-quality storage this batch
keeps dashboard work as a payload builder. Route wiring and UI are deferred.

## Boundary Protections

Batches 1-2 do not:

- scrape websites
- call external HTTP APIs
- call public job boards
- call company pages or careers pages
- call government or university datasets
- write canonical market truth
- create source observations
- update canonical scores
- change rankings
- rebuild outputs
- invalidate caches
- execute refresh jobs
- add a frontend dashboard
- move Layer 12 market coverage logic into Layer 13
- persist refresh-quality review records
- expose API routes
- add frontend/admin UI
- record review decisions into the DB
- execute approved handoffs
- call ingestion services
- call canonical repositories
- call scoring, output, cache, scheduler, worker, or queue execution services

Layer 13 may read already-supplied metadata, produce candidates, produce
reviewable queue item records, validate candidate observations, record
in-memory human review decisions, prepare explicit approved handoff intents,
emit audit records, and build read-only dashboard payloads.

## Deferred

Future batches can add durable storage, admin API routes, operator UI, admin
event-log integration, and a governed canonical-apply workflow if the schema and
authorization boundaries are explicitly approved. Any execution, ingestion,
scraping, canonical write, score mutation, ranking mutation, output rebuild, or
cache invalidation remains outside this Batch 2 contract.
