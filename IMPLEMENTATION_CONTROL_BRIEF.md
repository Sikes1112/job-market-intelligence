# IMPLEMENTATION_CONTROL_BRIEF.md

A compact control artifact for Claude Code implementation sessions.

This brief is a navigation aid. It does **not** override `CLAUDE.md`, `docs/MVP_SCOPE.md`, `docs/SLICE_PLAN.md`, or any architecture doc. When a slice prompt fires, Claude should still read the slice-relevant source-of-truth docs listed in section 5; this brief just keeps the rereading minimal.

---

## 1. Product Summary

### What this backend is for
A **job-market intelligence platform** that maps where opportunity is strongest across selected U.S. labor regions. The backend supports four product flows:
1. Region exploration (region pages with companies, hiring, entry-level, scores)
2. Company geography exploration (where a company is present / hiring / offering early-career)
3. Region comparison (side-by-side; secondary contextual challenge view)
4. Personalized discovery (best regions/companies given user preferences)

### What this backend is NOT
- Not a job board / not a national listings aggregator
- Not a comparison engine (comparison is one feature, not the core)
- Not a frontend application
- Not an applicant tracking, resume, employer, or messaging system
- Not a real-data ingestion / scraping layer in MVP

---

## 2. MVP V1 Scope Summary

Source: `docs/MVP_SCOPE.md`. Treat this section as a quick index, not a substitute.

### In scope for MVP V1
- Geography-aware market modeling (city / metro / greater-region / state, parent-child, labor-market grouping)
- Company universe + classification (eligibility, override-included, major-tech, Mag 7, classification confidence)
- Company-region presence mapping (office/operations/hiring evidence; presence basis + confidence; versioned)
- Hiring activity mapping (currently_hiring, now/30d/90d counts, annualized trend, seasonal student signal, hiring program count, role_family_summary)
- Entry-level opportunity (internships, co-ops, entry-level FT, formal early-career programs, recurrence signal, entry-level access score)
- Region scoring (structural ecosystem, live market, objective opportunity, raw total, general density, tech-market density, early-career accessibility)
- Derived outputs (region, company, comparison; contextual challenge stub OK)
- Personalization overlays (role/industry/career-stage/prestige/brand prefs → personalized region & company rankings; session-scoped)
- Read APIs for region / company / comparison / personalized discovery
- Background orchestration (jobs, queues, dependency checks, retries, object states, invalidation, refresh)

### Geography scope
Initial supported set may include Greater Boston, Greater SF / Silicon Valley, Greater NYC, Seattle, Austin, DC/NoVA. **Narrowest MVP: Greater Boston + Greater SF / Silicon Valley.** No arbitrary user-created custom regions.

### Role-family scope
Narrowest MVP: product + AI/cloud-adjacent non-pure-engineering roles. Optional add: cybersecurity. Do not require full SWE / design / ops / analytics / legal taxonomies.

### Career-stage scope
Early-career weighted: internships, co-ops, entry-level FT, formal early-career programs.

### Explicitly out of scope unless requested
- Frontend / UI of any kind
- Real external data ingestion / scraping (job boards, company sources)
- Permanent user accounts, resume ingestion, application tracking, messaging, employer accounts
- Microservice decomposition, distributed workflow engines, event-bus complexity beyond the documented orchestration model
- Nationwide region coverage, GIS boundaries, custom user regions
- Rich admin dashboards, advanced moderation/repair UI, raw job-posting CRUD
- Advanced ML classification, semantic search, NL search

---

## 3. Architecture Invariants

These rules cross every slice. Violating them is a redesign, not an implementation choice.

### 3.1 Three layers, never collapsed
1. **Canonical market truth** — `regions`, `companies`, `company_region_presence`, `company_region_hiring`, `company_region_entry_level`, `region_market_scores`, `jobs`. Structured, queryable, versioned.
2. **Derived output objects** — region / company / comparison / contextual-challenge outputs. Built asynchronously from truth. Metadata in DB; payload may live in object storage / cache.
3. **Personalization overlays** — user-specific scores and rankings. **Must not** mutate canonical truth. Usually session-scoped; durable user profiles are out of scope unless explicitly requested.

### 3.2 Truth is built in background; reads serve prepared objects
- User-facing endpoints **must not** trigger heavy foundational rebuilds (Company Universe Intake, global Eligibility & Classification, broad Presence Mapping) synchronously.
- Allowed at request time: filtering, sorting, ranking, personal overlay, lightweight comparison assembly, contextual challenge generation.
- Read path: cache → stale-with-warning cache → output metadata / object storage → degraded fallback. Enqueue rebuild rather than block on it.

### 3.3 Versioning is mandatory for major objects
Region registry, company universe, presence map, hiring map, entry-level map, region scores, output objects, scoring rulesets, eligibility rulesets, presence rulesets — all version-aware. Source-version-bundle metadata must travel with derived outputs.

### 3.4 Object lifecycle states are load-bearing
MVP states: `new`, `building`, `fresh`, `stale`, `partial`, `failed`, `blocked`, `rebuilding`. Later (defer): `low_confidence`, `verified`, `deprecated`. Never pretend `failed`/`blocked`/`partial` is complete. Never silently treat unknown as zero.

### 3.5 Atomic, idempotent writes
Build new result → validate → atomic commit. Same scope + inputs + dependency_refs must reproduce the same output_hash or return `NO_MEANINGFUL_CHANGE`.

### 3.6 Dependency-aware, dedupe-aware orchestration
Downstream jobs may not start unless dependency refs are in valid state. Scope dependency waiting to the minimum (company / region / company-region pair / comparison pair). Newer upstream versions supersede stale queued downstream jobs. Use scope-aware dedupe keys. Fan out only after upstream commit succeeds.

### 3.7 Foundation-first build order
Schema → orchestration skeleton → truth services → derived outputs → personalization → workers → events/invalidation → audit → contextual challenge → seed/demo. Do not invert.

### 3.8 Single repo, modular layout
One backend codebase, one DB, one queue broker, one cache store, one object store, one scheduler, a few worker processes, one API server. **Do not split into deployable services for MVP.**

### 3.9 API thinness
Endpoints are thin readers. Business logic in services. Expose state/freshness/source_versions where useful. Public APIs are read-oriented; mutations live behind admin-only paths.

---

## 4. Current Repo Structure

### Present at repo root
- `CLAUDE.md` — implementation rules (load every session)
- `README.md` — short pointer index
- `docs/` — see section 5
- `backend/` — skeleton package tree (only empty `__init__.py` files; no logic yet)
- `tests/` — empty directory
- `scripts/` — empty directory
- `seeds/` — empty directory
- `.env.example` — empty
- `.gitignore`
- `pyproject.toml` — empty
- `requirements.txt` — empty
- `requirements-dev.txt` — empty

### `backend/` package skeleton (all are `__init__.py`-only at the moment)
```
backend/
├── __init__.py
├── api/
├── audit/
├── companies/
├── config/
├── entry_level/
├── geography/
├── hiring/
├── orchestration/
│   ├── events/
│   ├── invalidation/
│   ├── jobs/
│   ├── queues/
│   ├── scheduler/
│   ├── state_machine/
│   └── workers/
├── outputs/
├── personalization/
├── presence/
├── scoring/
└── shared/
```

### Notable gaps vs. the docs (do **not** create these speculatively; flagged so future slices know what to add **only when their slice requires it**)
- `backend/orchestration/dependencies/` — referenced by Slice 4; not yet present.
- `backend/shared/` is empty — Slice 1 will fill in shared primitives; Slice 3 adds `state.py` / `versioning.py`.
- `backend/config/` is empty — Slice 1 fills in config loading.
- `backend/api/` is empty — Slice 1 adds health endpoint and app entrypoint scaffold.
- `pyproject.toml`, `requirements.txt`, `requirements-dev.txt` are all empty — Slice 1 fills the minimum.
- `tests/` is empty — Slice 1 adds test setup.
- `seeds/`, `scripts/` are empty — used in Slice 18.
- `docs/orchestration/` and `docs/specs/` directories exist but are empty (the actual orchestration source-of-truth lives in `docs/architecture/`). Do not move or duplicate content.

---

## 5. Source-of-Truth Docs Inventory

### Always-load (every slice)
- `CLAUDE.md` — implementation rules and hard constraints
- `docs/MVP_SCOPE.md` — what's in / out of MVP V1
- `docs/SLICE_PLAN.md` — slice order and per-slice scope/non-scope
- `IMPLEMENTATION_CONTROL_BRIEF.md` — this file

### Top-level product / scope docs (`docs/`)
- `docs/PRODUCT_OVERVIEW.md` — the product framing; useful narrative context
- `docs/MVP_SCOPE.md` — frozen MVP V1 scope
- `docs/SLICE_PLAN.md` — slice plan with success criteria per slice
- `docs/DATA_MODEL.md` — canonical data model; source of truth for schema/fields/enums/indexes
- `docs/API_SURFACES.md` — MVP API surface, response envelope, error codes, freshness exposure

### Architecture docs (`docs/architecture/`)
- `ENGINEERING_IMPLEMENTATION_BLUEPRINT.md` — system components, infra shape, module layout, MVP cut
- `APP_RESEARCH_WORKFLOW.md` — the 13 logical workflow stages and the three layered hierarchy
- `STAGE_BY_STAGE_EXECUTION_PROTOCOL.md` — Stage A–L execution detail, region-first rule, weighting hierarchy
- `WORKFLOW_ORCHESTRATION_SPEC.md` — full build / region expansion / market refresh / company refresh / user-query orchestration; precompute vs live; cache strategy; invalidation
- `JOB_ORCHESTRATION_MATRIX.md` — per-job trigger/inputs/outputs/dependencies/invalidation/cadence matrix
- `JOB_CONTRACT_SPEC.md` — request/response envelopes, status enums, error/warning schemas, retry policy table, idempotency rule
- `EVENT_TRIGGER_MAP.md` — event types, trigger-to-job routing, block conditions, cached vs fallback paths, suppression rules
- `OBJECT_STATE_MODEL.md` — full state set, transitions, read/write rules per state, per-object-type state usage
- `QUEUE_AND_WORKER_MODEL.md` — queue classes, worker types, concurrency, retry backoff, timeouts, partitioning, MVP queue layout (4 queues)

### Minimum docs to read per slice (in addition to the always-load set)

| Slice | Additional docs to read |
|---|---|
| 1 — Repo Foundation | `ENGINEERING_IMPLEMENTATION_BLUEPRINT.md` (sections 19–20) |
| 2 — Core Data Model | `DATA_MODEL.md`, `OBJECT_STATE_MODEL.md` (state set + metadata fields) |
| 3 — State / Versioning | `OBJECT_STATE_MODEL.md`, `DATA_MODEL.md` (shared field conventions) |
| 4 — Job Envelope / Orchestration Skeleton | `JOB_CONTRACT_SPEC.md`, `JOB_ORCHESTRATION_MATRIX.md`, `EVENT_TRIGGER_MAP.md` (schemas only) |
| 5 — Geography Service | `DATA_MODEL.md` (regions), `APP_RESEARCH_WORKFLOW.md` Stage 1, `JOB_CONTRACT_SPEC.md` Job 1 |
| 6 — Company Universe / Classification | `DATA_MODEL.md` (companies), `APP_RESEARCH_WORKFLOW.md` Stages 2–3, `STAGE_BY_STAGE_EXECUTION_PROTOCOL.md` Stages A–C, `JOB_CONTRACT_SPEC.md` Jobs 2–3 |
| 7 — Presence | `DATA_MODEL.md` (presence), `APP_RESEARCH_WORKFLOW.md` Stage 4, `STAGE_BY_STAGE_EXECUTION_PROTOCOL.md` Stage D, `JOB_CONTRACT_SPEC.md` Job 4 |
| 8 — Hiring | `DATA_MODEL.md` (hiring), `APP_RESEARCH_WORKFLOW.md` Stage 5, `STAGE_BY_STAGE_EXECUTION_PROTOCOL.md` Stage E, `JOB_CONTRACT_SPEC.md` Job 5 |
| 9 — Entry-Level | `DATA_MODEL.md` (entry_level), `APP_RESEARCH_WORKFLOW.md` Stage 6, `STAGE_BY_STAGE_EXECUTION_PROTOCOL.md` Stage F, `JOB_CONTRACT_SPEC.md` Job 6 |
| 10 — Region Scoring | `DATA_MODEL.md` (region_market_scores), `APP_RESEARCH_WORKFLOW.md` Stage 7, `STAGE_BY_STAGE_EXECUTION_PROTOCOL.md` Stages G + I, `JOB_CONTRACT_SPEC.md` Job 7 |
| 11 — Output Assembly | `DATA_MODEL.md` (output_metadata + derived shapes §19), `APP_RESEARCH_WORKFLOW.md` Stages 9–11, `JOB_CONTRACT_SPEC.md` Jobs 8–10 |
| 12 — API Read Layer | `API_SURFACES.md` (full), `OBJECT_STATE_MODEL.md` §11 (UI behavior rules), `EVENT_TRIGGER_MAP.md` §4 (cached vs fallback) |
| 13 — Personalization Overlay | `DATA_MODEL.md` §20, `APP_RESEARCH_WORKFLOW.md` Stage 8, `STAGE_BY_STAGE_EXECUTION_PROTOCOL.md` Stage H, `JOB_CONTRACT_SPEC.md` Job 11, `API_SURFACES.md` §8 |
| 14 — Queue / Worker Runtime | `QUEUE_AND_WORKER_MODEL.md` (full), `JOB_CONTRACT_SPEC.md` (retry table) |
| 15 — Event Trigger / Invalidation | `EVENT_TRIGGER_MAP.md` (full), `JOB_ORCHESTRATION_MATRIX.md` §6 |
| 16 — Audit | `APP_RESEARCH_WORKFLOW.md` Stage 13, `STAGE_BY_STAGE_EXECUTION_PROTOCOL.md` Stage L, `JOB_CONTRACT_SPEC.md` Job 13, `DATA_MODEL.md` §12 |
| 17 — Contextual Challenge | `APP_RESEARCH_WORKFLOW.md` Stage 12, `STAGE_BY_STAGE_EXECUTION_PROTOCOL.md` Stage K, `JOB_CONTRACT_SPEC.md` Job 12, `API_SURFACES.md` §6 (contextual) |
| 18 — Seed Data / Demo | `MVP_SCOPE.md` geography section, `WORKFLOW_ORCHESTRATION_SPEC.md` §17 Scenario A |

---

## 6. Slice Plan Summary

Source of truth: `docs/SLICE_PLAN.md`.

| # | Slice | Implements (one-line) |
|---|---|---|
| 1 | Repo Foundation | Project/module structure, config loading, env, app entrypoint, health route, shared error/result primitives, test setup, lint/type/test scripts |
| 2 | Core Data Model / Canonical Schema | Models + persistence for regions, companies, presence, hiring, entry-level, region_market_scores, jobs, output_metadata; stable IDs, timestamps, state, version, confidence/freshness fields |
| 3 | Object State and Versioning Layer | State enum/helpers, version metadata, freshness/confidence helpers, basic transition validation |
| 4 | Job Envelope and Orchestration Skeleton | Job-type/status enums, request/response envelopes, error/warning/downstream-trigger schemas, dedupe key/scope hash, dependency ref structure |
| 5 | Geography Service | Region create/update, hierarchy validation, labor-market group, normalization profile ref, Geography Build job handler skeleton |
| 6 | Company Universe & Classification | Company CRUD, eligibility status, eligibility scoring rule interface, overrides + rationale, major-tech rubric interface, Mag 7 tagging, classification confidence |
| 7 | Company-Region Presence | Presence record logic, status, basis, evidence flags (office/operations/hiring), confidence, presence mapping job/service skeleton |
| 8 | Hiring Activity | Hiring record model/service; current-hiring flag, now/30d/90d counts, annualized trend, seasonal student signal, hiring program count, role_family_summary; Hiring Refresh job skeleton |
| 9 | Entry-Level Opportunity | Internship/co-op/entry-level FT counts, formal early-career flag, recurrence signal, entry-level access score; Entry-Level Refresh job skeleton |
| 10 | Region Scoring | Structural / live-market / objective-opportunity / raw-total / density / early-career-accessibility scores; Region Score Recompute job skeleton |
| 11 | Output Assembly | Region / company / comparison output object builders; output metadata records; cache-ready payload shape; build jobs for region/company/comparison |
| 12 | API Read Layer | Read endpoints: regions list/detail, company detail, region companies, compare, health; thin handlers; freshness/state metadata |
| 13 | Personalization Overlay | Preference payload, per-component scoring, personalized region/company rankings, discovery service method; overlay-only (no truth mutation) |
| 14 | Queue & Worker Runtime | Queue abstraction (foundational/refresh/output/interactive), worker registration, dispatch, retries, dependency checks, dedupe, downstream trigger processing |
| 15 | Event Trigger & Invalidation | Event model, event-to-job router, scoped invalidation, downstream enqueue recommendations, suppression on no-meaningful-change |
| 16 | Basic Audit | Audit report model, override balance, double-counting, presence inflation, personal/objective separation; Audit Job skeleton |
| 17 | Contextual Challenge (Minimal) | Contextual challenge object, status enum (reinforced/challenged/unchanged/insufficient_data), changed/unchanged findings, lightweight explanation |
| 18 | Seed Data and MVP Demo Path | Seed Greater Boston + Greater SF, seed companies / presence / hiring / entry-level, seed scoring + output, integration test for end-to-end MVP path |

### Current next slice → **Slice 1: Repo Foundation**
Confirmed by current repo state: every `backend/**` package is empty (`__init__.py` only); root `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, `.env.example` are empty; `tests/` is empty. No prior implementation exists.

---

## 7. Claude Code Implementation Rules

These rules apply to **every** slice prompt. They are the operational projection of `CLAUDE.md` plus this brief.

1. **One slice at a time.** Implement only the slice the prompt names. Do not jump to later slices, even if a later slice would "make this easier."
2. **Do not broaden MVP scope.** If something isn't in `MVP_SCOPE.md` or the slice's "Build" list, treat as out of scope unless the prompt explicitly says otherwise.
3. **Preserve the three layers.** Never write personalization into canonical truth. Never put truth-building work in request handlers. Never collapse derived outputs into canonical tables.
4. **Add tests appropriate to the slice.** Schema/state/version/dependency/invalidation/stale-handling tests are the priority targets. Skip nothing foundational.
5. **Use atomic writes for canonical/derived objects.** Build → validate → commit. Version every major object.
6. **Honor object states.** `new`, `building`, `fresh`, `stale`, `partial`, `failed`, `blocked`, `rebuilding`. Don't fake completeness.
7. **Be explicit about degraded/unknown.** Never silently treat unknown as zero (especially for entry-level metadata).
8. **Keep code boring.** Simple modules, explicit data flow, no speculative abstractions, no premature framework indirection.
9. **Update docs only when source-of-truth behavior changes.** Do not casually rewrite architecture docs. If updating, edit the specific file with minimal scope.
10. **Summarize at the end of every slice prompt:** files created, files modified, what was implemented, tests added, what was intentionally not implemented.
11. **If ambiguous:** prefer MVP_SCOPE → SLICE_PLAN → simpler implementation → preserve layer separation → narrowest version consistent with docs. Stop short of inventing new architecture.

---

## 8. First Implementation Recommendation — Slice 1

### What Slice 1 should do
Create the runnable skeleton for the backend repo so later slices have somewhere to land:
- Choose and pin a Python version + framework choice (the doc layer assumes a Python relational app; any standard Python web framework consistent with the modular layout in `ENGINEERING_IMPLEMENTATION_BLUEPRINT.md` §19–20 is fine — pick one, commit to it, keep it boring).
- Populate `pyproject.toml` (or equivalent) and `requirements.txt` / `requirements-dev.txt` with the minimum runtime + test/lint dependencies. No DB driver heroics, no queue broker libraries yet.
- Add `backend/config/` loading: env-driven settings (read `.env.example` and document keys; do not invent secret-handling beyond "load from env"). Keep `.env.example` honest — only list keys actually used.
- Add an app entrypoint under `backend/api/` exposing `GET /health` returning the canonical envelope from `API_SURFACES.md` §3 (status/data/metadata/error). Health must not touch the DB or trigger jobs.
- Add `backend/shared/` primitives only as they are needed by the entrypoint and by tests: a result/error type and a structured-logging helper are reasonable; do not pre-stage state/version/job code (those belong to Slices 2–4).
- Add `tests/` setup: a runner config (pytest is the default expectation), at least one passing test that imports the app and hits `/health`, plus a smoke import test for every existing top-level package so empty packages don't break later slices.
- Add lint/type/test commands runnable from a single entrypoint (the prompt does not require a Makefile; a `pyproject.toml` `[tool.*]` config plus documented commands is fine).
- Do **not** create database models, migrations, services, or job code. Do **not** add framework choices for queues/cache/object-store yet.

### Docs the Slice 1 prompt should tell Claude Code to read
1. `CLAUDE.md`
2. `docs/MVP_SCOPE.md`
3. `docs/SLICE_PLAN.md` (Slice 1 section in particular)
4. `docs/architecture/ENGINEERING_IMPLEMENTATION_BLUEPRINT.md` (sections 19–20 for module layout and MVP shape; section 17 for security framing only at a conceptual level)
5. `docs/API_SURFACES.md` (section 3 for the health endpoint and section 2 for the response envelope)
6. `IMPLEMENTATION_CONTROL_BRIEF.md` (this file)

### What Slice 1 must NOT implement
- Any database model, migration, ORM mapping, or table definition (Slice 2)
- Any state machine, version helper, or freshness helper (Slice 3)
- Any job envelope, dedupe key logic, or dependency-ref structure (Slice 4)
- Any geography/company/presence/hiring/entry-level/scoring service, model, or rule (Slices 5–10)
- Any output object builders or output metadata logic (Slice 11)
- Any read endpoints beyond `/health` (Slice 12)
- Any personalization logic (Slice 13)
- Any queue, worker, scheduler, or invalidation logic (Slices 14–15)
- Any audit checks, contextual challenge logic, or seed/demo data (Slices 16–18)
- Any frontend, admin dashboard, or external data ingestion at any time
- Any speculative abstraction "for later slices" (e.g., a Job base class, a generic Repository, a plugin loader). If a later slice needs it, that slice will add it.

### Slice 1 success criteria (inherited from `SLICE_PLAN.md`)
- Repo runs.
- Tests run and pass.
- `/health` returns the documented envelope shape.
- Shared primitives exist without domain overreach.
- Empty package tree still imports cleanly.

---

## 9. Open Questions / Potential Conflicts

These are flagged for awareness; **do not resolve them by changing the architecture.** When a slice encounters one, fall back to the precedence in `CLAUDE.md` ("If Something Is Ambiguous").

1. **Trailing line in `SLICE_PLAN.md` (line 843):** _"Next, I'd create `docs/DATA_MODEL.md`, because Slice 2 will drift unless the canonical tables/entities are locked before Claude starts coding."_ — `DATA_MODEL.md` already exists. The line appears to be a stale planning note from before `DATA_MODEL.md` was authored. Treat `DATA_MODEL.md` as the existing source of truth for Slice 2; do not rewrite the slice plan or the data model.
2. **Slice 4 names `orchestration/dependencies/`** as a suggested module, but the existing `backend/orchestration/` skeleton has no `dependencies/` directory (it has events, invalidation, jobs, queues, scheduler, state_machine, workers). Slice 4 may either (a) create the directory or (b) fold dependency-ref structures into `orchestration/jobs/`. Either is consistent with the docs; pick the simpler option per Slice 4's prompt and keep it explicit in the summary.
3. **Queue naming.** `ENGINEERING_IMPLEMENTATION_BLUEPRINT.md` uses `q_foundational / q_refresh / q_output / q_interactive`; `QUEUE_AND_WORKER_MODEL.md` §20 uses `MVP Queue A/B/C/D` with the same four logical queues; `SLICE_PLAN.md` Slice 14 uses `foundational / refresh / output / interactive`. These are the same model under different labels — Slice 14 should pick one consistent set of identifiers and stick with it.
4. **Minor enum / state naming variants.** `DATA_MODEL.md` uses `succeeded_with_warnings` for jobs while `OBJECT_STATE_MODEL.md` describes object states (`fresh`, `verified`, etc.) separately. These are orthogonal (job status vs. object state) and consistent across docs; a slice prompt should never conflate them.
5. **Prestige score.** `DATA_MODEL.md` lists `prestige_score` as a `companies` field but no doc fully specifies how it is computed. Treat `prestige_score` as a stored field whose population rule is deferred — Slice 6 stores/accepts it; later slices (or post-MVP work) can refine the rule. Do not invent a formula in MVP unless a slice explicitly asks for one.
6. **Empty `docs/orchestration/` and `docs/specs/` directories.** Source-of-truth orchestration docs live in `docs/architecture/`. Do not migrate, duplicate, or "fill" the empty directories without an explicit prompt to do so.

None of these are architectural conflicts. They are documentation-state details that future slices should note in their own summaries when relevant.

---

## 10. Slice Prompt Template (use for every slice)

```
Read CLAUDE.md, docs/MVP_SCOPE.md, docs/SLICE_PLAN.md, IMPLEMENTATION_CONTROL_BRIEF.md,
and the slice-specific docs listed in IMPLEMENTATION_CONTROL_BRIEF.md §5.

Implement Slice <N> only: <slice name>.

Hard constraints:
- one slice only; do not implement later slices
- do not broaden MVP scope
- preserve canonical truth / derived output / personalization separation
- honor object states; never silently treat unknown as zero
- atomic writes for canonical/derived objects; version-aware
- add tests appropriate to this slice
- update docs only if this slice changes source-of-truth behavior

After implementation, summarize:
1. files created
2. files modified
3. what was implemented
4. tests added
5. what was intentionally not implemented (and which slice it belongs to)
```
