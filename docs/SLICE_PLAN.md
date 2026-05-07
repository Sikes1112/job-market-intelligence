# SLICE_PLAN.md

## Purpose

This file defines the implementation order for MVP V1.

Claude Code must use this as the execution plan.  
Implement one slice at a time unless explicitly instructed otherwise.

Do not skip ahead.  
Do not merge unrelated slices.  
Do not broaden scope beyond `docs/MVP_SCOPE.md`.

---

## Global Slice Rules

### 1. One slice at a time
Each implementation prompt should target exactly one slice.

### 2. Preserve architecture boundaries
Do not collapse:
- canonical truth
- derived outputs
- personalization overlays
- orchestration/job control

### 3. Prefer foundation-first implementation
Build stable primitives before higher-level workflows.

### 4. Tests are expected
Each slice should include tests for the behavior it introduces.

### 5. Avoid speculative implementation
If a later slice needs a feature, do not build it early unless the current slice explicitly requires a minimal stub/interface.

### 6. Keep implementation boring
Prefer simple, explicit, modular code over clever abstractions.

### 7. Document only real source-of-truth changes
Do not rewrite docs casually.

---

# MVP Slice Order

## Slice 1 — Repo Foundation

### Purpose
Create the basic backend repository structure and shared foundation.

### Build
- project/module structure
- configuration loading
- environment handling
- app entrypoint
- basic health endpoint if API framework is present
- shared error/result primitives
- test setup
- lint/type/test scripts if relevant

### Suggested modules
- `shared/`
- `api/`
- `config/` or equivalent
- `tests/`

### Must not build
- business logic
- company logic
- scoring logic
- real orchestration logic
- frontend/UI

### Success criteria
- repo runs
- tests run
- basic health path or app initialization works
- shared primitives exist without domain overreach

---

## Slice 2 — Core Data Model / Canonical Schema

### Purpose
Create the canonical database/data model foundation for MVP truth objects.

### Build
Canonical support for:
- regions
- companies
- company-region presence
- company-region hiring
- company-region entry-level
- region market scores
- jobs
- output metadata records

### Required concepts
- stable IDs
- timestamps
- object state
- version fields
- confidence/freshness fields where appropriate

### Suggested modules
- `geography/`
- `companies/`
- `presence/`
- `hiring/`
- `entry_level/`
- `scoring/`
- `orchestration/jobs/`
- `outputs/`

### Must not build
- scoring formulas
- hiring scraping
- full job execution
- personalization
- API endpoints beyond minimal schema validation if needed

### Success criteria
- schema/models exist
- relationships are clear
- migrations or equivalent persistence setup exists
- tests verify model creation/validation/basic relationships

---

## Slice 3 — Object State and Versioning Layer

### Purpose
Implement lifecycle state primitives used across truth and output objects.

### Build
- object state enum/helpers
- version metadata helpers
- freshness metadata helpers
- confidence metadata helpers
- basic state transition validation
- common object metadata mixins/utilities if appropriate

### Required MVP states
- `new`
- `building`
- `fresh`
- `stale`
- `partial`
- `failed`
- `blocked`
- `rebuilding`

### Optional later states
Do not implement unless needed:
- `low_confidence`
- `verified`
- `deprecated`

### Suggested modules
- `shared/state.py`
- `shared/versioning.py`
- `orchestration/state_machine/`

### Must not build
- full audit system
- full object repair workflows
- UI behavior
- queue execution

### Success criteria
- states are reusable
- invalid transitions are rejected or clearly handled
- tests cover state transitions and freshness behavior

---

## Slice 4 — Job Envelope and Orchestration Skeleton

### Purpose
Implement the basic job contract system without full worker execution.

### Build
- job type enum
- job status enum
- request envelope
- response envelope
- standard error schema
- standard warning schema
- downstream trigger recommendation schema
- dedupe key/scope hash helpers
- basic dependency reference structure

### Suggested modules
- `orchestration/jobs/`
- `orchestration/events/`
- `orchestration/dependencies/`

### Must not build
- real background workers
- full queue broker
- all job implementations
- complex retry engine

### Success criteria
- job payloads can be created/validated
- responses support success/warning/failure
- downstream trigger recommendation objects exist
- tests cover envelope validation and error/warning shapes

---

## Slice 5 — Geography Service

### Purpose
Implement region/geography truth objects and basic region operations.

### Build
- create/update region objects
- region hierarchy validation
- labor market group support
- normalization profile reference support
- Geography Build job handler skeleton or service method

### Suggested modules
- `geography/models.py`
- `geography/service.py`
- `geography/repository.py`
- `orchestration/jobs/geography_build.py`

### Must not build
- custom user-created geographies
- nationwide expansion logic
- complex GIS/spatial calculations
- map frontend logic

### Success criteria
- supported MVP regions can be represented
- parent/labor-market relationships validate
- geography build operation returns versioned outputs
- tests cover region creation and invalid hierarchy rejection

---

## Slice 6 — Company Universe and Classification Service

### Purpose
Implement company eligibility and classification logic.

### Build
- company record CRUD/repository basics
- eligibility status handling
- eligibility scoring placeholder/rule interface
- override-included path
- override rationale fields
- major-tech classification rubric interface
- Mag 7 tagging
- classification confidence

### Suggested modules
- `companies/models.py`
- `companies/service.py`
- `companies/classification.py`
- `companies/overrides.py`
- `orchestration/jobs/eligibility_classification.py`

### Must not build
- external company-source ingestion at scale
- complex ML classification
- real web research/scraping
- hiring logic

### Success criteria
- company can be marked eligible/ineligible/override-included
- major-tech and Mag 7 labels are assigned deterministically
- overrides are visible in company records
- tests cover normal eligibility, override inclusion, and major-tech tagging

---

## Slice 7 — Company-Region Presence Service

### Purpose
Implement meaningful regional presence mapping.

### Build
- company-region presence record logic
- presence status handling
- presence basis handling
- evidence flags:
  - office evidence
  - operations evidence
  - hiring evidence
- presence confidence
- presence mapping job/service skeleton

### Presence rule
A company is regionally present if:
- real office + real operations  
or
- real office + actual hiring tied to region

Hiring evidence is preferred when available.  
Satellite office may suffice when hiring evidence is unavailable.

### Suggested modules
- `presence/models.py`
- `presence/service.py`
- `presence/evidence.py`
- `orchestration/jobs/presence_mapping.py`

### Must not build
- live source fetching
- geospatial office validation
- hiring refresh logic
- scoring

### Success criteria
- company-region presence can be evaluated from provided evidence
- presence basis is explicit
- uncertain/insufficient evidence is handled honestly
- tests cover office+operations, office+hiring, satellite-only, and insufficient evidence cases

---

## Slice 8 — Hiring Activity Service

### Purpose
Implement hiring snapshot records and refresh logic over existing present company-region pairs.

### Build
- company-region hiring record model/service
- current hiring flag
- active posting count now
- 30-day count
- 90-day count
- annualized trend signal
- seasonal student hiring signal
- hiring program count
- role-family summary
- Hiring Refresh job skeleton

### Suggested modules
- `hiring/models.py`
- `hiring/service.py`
- `hiring/time_windows.py`
- `hiring/role_families.py`
- `orchestration/jobs/hiring_refresh.py`

### Must not build
- full job-board ingestion
- browser scraping
- AI parsing of real job descriptions
- entry-level extraction

### Success criteria
- hiring records can be created/refreshed from structured input
- time-window fields are stored and versioned
- refresh can return no meaningful change
- tests cover changed, unchanged, and invalid company-region pair cases

---

## Slice 9 — Entry-Level Opportunity Service

### Purpose
Implement early-career extraction and entry-level access scoring from structured hiring data.

### Build
- internship count
- co-op count
- entry-level full-time count
- formal early-career program flag
- student-season recurrence signal
- entry-level access score
- Entry-Level Refresh job skeleton

### Rule
Internships and co-ops are treated equally.

### Suggested modules
- `entry_level/models.py`
- `entry_level/service.py`
- `entry_level/scoring.py`
- `orchestration/jobs/entry_level_refresh.py`

### Must not build
- real NLP role extraction unless explicitly requested
- external job ingestion
- personalization
- full scoring engine

### Success criteria
- entry-level record can be built from structured hiring/role inputs
- internship/co-op parity is preserved
- missing/unknown role metadata does not become fake zero unless explicitly confirmed
- tests cover internship, co-op, entry-level FT, formal program, and partial metadata cases

---

## Slice 10 — Region Scoring Service

### Purpose
Implement MVP region-level market scoring from canonical truth records.

### Build
- structural ecosystem score
- live market score
- objective opportunity score
- raw total score
- general density score
- tech-market density score
- early-career accessibility score
- Region Score Recompute job skeleton

### Scoring hierarchy
Objective opportunity score should emphasize:
1. entry-level access
2. current hiring volume
3. prestige

Entry-level access leads, but only modestly.

### Suggested modules
- `scoring/models.py`
- `scoring/service.py`
- `scoring/rulesets.py`
- `scoring/normalization.py`
- `orchestration/jobs/region_score_recompute.py`

### Must not build
- complex ML ranking
- advanced normalization beyond MVP
- personalized scoring
- contextual challenge scoring

### Success criteria
- region scores can be computed deterministically from stored truth records
- normalized views are separate, not blended into one opaque denominator
- tests cover score computation and missing/partial input behavior

---

## Slice 11 — Output Assembly Service

### Purpose
Build derived app-facing output objects from canonical truth and scores.

### Build
- region output object builder
- company output object builder
- output metadata records
- artifact/cache-ready payload shape
- basic comparison output builder
- region-first comparison structure

### Suggested modules
- `outputs/models.py`
- `outputs/region_output.py`
- `outputs/company_output.py`
- `outputs/comparison_output.py`
- `outputs/repository.py`
- `orchestration/jobs/region_output_build.py`
- `orchestration/jobs/company_output_build.py`
- `orchestration/jobs/comparison_cache_build.py`

### Must not build
- frontend components
- advanced contextual challenge logic
- rich chart rendering
- personalization overlay

### Success criteria
- region output can be assembled from canonical truth
- company output can be assembled from canonical truth
- comparison output can compare two region outputs
- outputs include state/freshness/source version metadata
- tests cover output assembly and partial/stale input handling

---

## Slice 12 — API Read Layer

### Purpose
Expose MVP read APIs for app use.

### Build
Read endpoints for:
- region view
- company view
- comparison view
- basic search/filter if supported by existing objects

### Suggested endpoints
- `GET /regions`
- `GET /regions/{region_id}`
- `GET /companies/{company_id}`
- `GET /compare?region_a=...&region_b=...`
- `GET /health`

### API rules
- endpoints should be thin
- read prepared outputs where possible
- expose state/freshness metadata where useful
- do not run heavy truth-building synchronously

### Must not build
- full admin panel
- public mutation APIs
- frontend
- user accounts unless explicitly requested

### Success criteria
- endpoints return expected output objects
- missing/stale/partial objects are handled explicitly
- tests cover successful reads and unavailable object behavior

---

## Slice 13 — Personalization Overlay Service

### Purpose
Implement user preference scoring as an overlay, not canonical truth.

### Build
- user preference payload model
- role target handling
- industry preference handling
- career stage handling
- prestige preference handling
- brand preference handling
- personalized market score
- personalized company score
- personalized discovery endpoint or service method

### Weighting rule
Personal overlay should prioritize:
1. role fit
2. industry
3. prestige
4. brand appeal

Role fit and industry weigh more than prestige and brand appeal.

### Suggested modules
- `personalization/models.py`
- `personalization/service.py`
- `personalization/scoring.py`
- `api/personalized.py`

### Must not build
- permanent user account system unless explicitly requested
- resume/profile ingestion
- application tracking
- canonical truth mutation

### Success criteria
- personalization reads existing market truth/output data
- personalization does not write canonical truth
- tests cover preference scoring and layer separation

---

## Slice 14 — Basic Queue and Worker Runtime

### Purpose
Implement the MVP queue/worker execution system.

### Build
- queue abstraction
- worker registration
- job dispatch
- retry handling
- dependency checks
- dedupe key handling
- basic downstream trigger processing

### MVP queues
- foundational
- refresh
- output
- interactive

### Suggested modules
- `orchestration/queues/`
- `orchestration/workers/`
- `orchestration/scheduler/`
- `orchestration/invalidation/`

### Must not build
- complex distributed workflow engine
- advanced precompute queue
- full audit/repair system
- multi-service deployment

### Success criteria
- jobs can be enqueued and processed by type
- duplicate jobs can be suppressed by dedupe key
- dependency-missing jobs block/defer cleanly
- retryable errors retry under policy
- tests cover dispatch, dedupe, dependency blocking, and retry behavior

---

## Slice 15 — Event Trigger and Invalidation Logic

### Purpose
Connect events to job routing and scoped invalidation.

### Build
- event model
- event-to-job router
- scoped invalidation rules
- downstream enqueue recommendations
- suppression when no meaningful change occurs

### Required events
- `REGION_ADDED`
- `REGION_DEFINITION_CHANGED`
- `NEW_COMPANY_CANDIDATE_ADDED`
- `COMPANY_CLASSIFICATION_CORRECTED`
- `COMPANY_PRESENCE_UPDATED`
- `HIRING_DATA_UPDATED`
- `ENTRY_LEVEL_SIGNAL_UPDATED`
- `NORMALIZATION_INPUTS_UPDATED`
- `COMPARISON_REQUESTED`

### Suggested modules
- `orchestration/events/`
- `orchestration/invalidation/`
- `orchestration/scheduler/router.py`

### Must not build
- every future admin event
- full repair escalation UI
- broad manual review workflow

### Success criteria
- events enqueue correct jobs
- invalidation is scoped
- foundational jobs are not triggered by dynamic hiring events
- tests cover major trigger paths and suppression rules

---

## Slice 16 — Basic Audit Layer

### Purpose
Implement minimal integrity checks for MVP.

### Build
- audit report model
- override balance check
- double-counting check placeholder/basic implementation
- presence inflation check placeholder/basic implementation
- personal/objective separation check
- Audit Job skeleton

### Suggested modules
- `audit/models.py`
- `audit/service.py`
- `audit/checks.py`
- `orchestration/jobs/audit.py`

### Must not build
- full admin dashboard
- advanced repair automation
- broad manual review UI
- complex anomaly detection

### Success criteria
- audit job can run against stored truth/output objects
- findings are structured
- critical findings can mark affected scopes warning/degraded if implemented
- tests cover basic audit checks

---

## Slice 17 — Contextual Challenge Minimal Implementation

### Purpose
Implement the secondary contextual challenge output as a minimal derived feature.

### Build
- contextual challenge object
- simple challenge status:
  - `reinforced`
  - `challenged`
  - `unchanged`
  - `insufficient_data`
- changed vs unchanged findings
- lightweight narrative fields or structured explanation fields

### Suggested modules
- `outputs/contextual_challenge.py`
- `orchestration/jobs/contextual_challenge_build.py`
- `api/contextual.py` if needed

### Must not build
- complex AI narrative generation
- advanced regional simulation
- hidden scoring changes to the primary comparison

### Success criteria
- contextual challenge reads comparison outputs
- it does not replace primary quantitative result
- tests cover reinforced/challenged/unchanged paths

---

## Slice 18 — Seed Data and MVP Demo Path

### Purpose
Create a small seed/demo path so the backend can demonstrate the full workflow without external integrations.

### Build
- seed regions:
  - Greater Boston
  - Greater San Francisco / Silicon Valley
- seed companies
- seed presence records
- seed hiring records
- seed entry-level records
- seed scores/output generation command or script

### Suggested modules/files
- `seeds/`
- `scripts/`
- `tests/integration/`

### Must not build
- real data ingestion
- scraping
- nationwide seed data
- large fake dataset

### Success criteria
- developer can run seed/demo flow
- region output works
- company output works
- comparison works
- personalized discovery works if Slice 13 is implemented
- integration test verifies end-to-end MVP path

---

# Deferred / Post-MVP Slices

These are intentionally not part of the core MVP unless explicitly requested.

## Deferred A — Real External Data Ingestion
- job board integrations
- company source ingestion
- automated source parsing
- rate-limit handling for external providers

## Deferred B — Advanced Admin Tooling
- override review UI
- repair dashboards
- manual confidence adjustment
- admin analytics

## Deferred C — Advanced Geography
- arbitrary custom user regions
- nationwide region coverage
- GIS boundary support
- commute-time modeling

## Deferred D — Advanced Search
- semantic search
- natural language search
- advanced filtering DSL

## Deferred E — Advanced Personalization
- saved user profiles
- resume ingestion
- application tracking
- recommendation feedback loops

## Deferred F — Full Audit/Repair Automation
- repair workflows
- confidence upgrade pipelines
- automated anomaly resolution

---

# Recommended Claude Code Prompt Pattern

For each slice, use a prompt like:

```text
Read CLAUDE.md, docs/MVP_SCOPE.md, docs/SLICE_PLAN.md, and the relevant docs for this slice.

Implement Slice <N> only: <slice name>.

Do not implement later slices.
Do not add frontend code.
Do not broaden MVP scope.
Preserve the canonical truth / derived output / personalization separation.

After implementation, summarize:
1. files created
2. files modified
3. what was implemented
4. tests added
5. what was intentionally not implemented

⸻

Slice Acceptance Checklist
A slice is acceptable only if:
* it stays inside requested scope
* it preserves architecture boundaries
* tests pass
* new behavior is covered by tests
* no unrelated future slices are implemented
* no major docs are rewritten unnecessarily
* omissions are explicitly stated

⸻

Current Implementation Status
Update this section as slices are completed.
Slice status
* Slice 1 — Repo Foundation
* Slice 2 — Core Data Model / Canonical Schema
* Slice 3 — Object State and Versioning Layer
* Slice 4 — Job Envelope and Orchestration Skeleton
* Slice 5 — Geography Service
* Slice 6 — Company Universe and Classification Service
* Slice 7 — Company-Region Presence Service
* Slice 8 — Hiring Activity Service
* Slice 9 — Entry-Level Opportunity Service
* Slice 10 — Region Scoring Service
* Slice 11 — Output Assembly Service
* Slice 12 — API Read Layer
* Slice 13 — Personalization Overlay Service
* Slice 14 — Basic Queue and Worker Runtime
* Slice 15 — Event Trigger and Invalidation Logic
* Slice 16 — Basic Audit Layer
* Slice 17 — Contextual Challenge Minimal Implementation
* Slice 18 — Seed Data and MVP Demo Path
Next, I’d create `docs/DATA_MODEL.md`, because Slice 2 will drift unless the canonical tables/entities are locked before Claude starts coding.
