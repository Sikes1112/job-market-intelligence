# CLAUDE.md

## Purpose

This repository contains the backend/system implementation for a job-market intelligence platform.

The product is **not** a generic job board.  
It is a structured system for:

- building a company universe
- mapping companies to labor regions
- mapping hiring activity by region
- extracting entry-level opportunity signals
- computing market/opportunity scores
- serving region, company, comparison, and personalized outputs

Comparison is a feature, not the product core.

---

## Read This First Before Any Implementation Work

Before implementing any slice, read these files in this order:

1. `docs/MVP_SCOPE.md`
2. `docs/SLICE_PLAN.md`
3. `docs/PRODUCT_OVERVIEW.md`
4. `docs/architecture/ENGINEERING_IMPLEMENTATION_BLUEPRINT.md`

Then read any slice-relevant source-of-truth docs from:

- `docs/architecture/`
- `docs/orchestration/`

Do **not** skip the MVP scope or slice plan.

---

## Implementation Philosophy

Build this system in a **foundation-first** order.

The most important rule is:

**store canonical truth in structured versioned records, build derived outputs asynchronously, and serve cached/assembled views instead of recomputing truth in request time.**

Truth-building happens in background workflows.  
User-facing reads should mostly consume prepared objects.

---

## Hard Rules

### 1. Build only the requested slice
When asked to implement a slice, implement **that slice only**.

Do not:
- jump ahead to future slices
- build adjacent systems “for convenience”
- add speculative abstractions for later features
- quietly broaden scope

### 2. Obey MVP scope
If an idea is not in `docs/MVP_SCOPE.md`, treat it as out of scope unless explicitly requested.

### 3. Do not redesign the architecture
Use the repo docs as source of truth.

Do not:
- replace the architecture with a different pattern
- turn the system into a microservice mesh unless explicitly requested
- collapse the truth/derived-output distinction
- move personalization into the canonical truth layer

### 4. Keep the code modular and boring
Prefer:
- simple modules
- explicit data flow
- clear boundaries
- deterministic behavior
- versioned objects
- straightforward database access

Avoid:
- clever abstractions
- unnecessary generics
- framework-heavy indirection
- over-engineering for hypothetical scale

### 5. Do not mix layers
Keep these layers separate:

#### Market truth layer
Canonical truth:
- companies
- classifications
- presence
- hiring
- entry-level
- region scores

#### Intelligence/output layer
Derived objects:
- region outputs
- company outputs
- comparison outputs
- contextual challenge outputs

#### Personalization layer
User-specific overlays:
- preference scoring
- personalized rankings
- personalized company targets

Do **not** let personalization contaminate canonical truth.

### 6. Do not compute foundational truth in user request paths
User-facing endpoints should not trigger heavy foundational rebuilds synchronously.

Allowed request-time work:
- filtering
- sorting
- ranking
- personal overlay
- lightweight comparison assembly
- contextual challenge generation

Not allowed request-time work unless explicitly requested:
- global company intake
- broad classification rebuild
- global presence remapping
- heavy market-truth recomputation

### 7. Respect object states
Object lifecycle states are source-of-truth behavior, not optional decoration.

At minimum, honor:
- `new`
- `building`
- `fresh`
- `stale`
- `partial`
- `failed`
- `blocked`
- `rebuilding`

Do not pretend failed, blocked, or partial objects are complete.

### 8. Respect versioning
Major truth and output objects must be version-aware.

Do not build features that assume mutable, unversioned truth.

### 9. Prefer atomic writes for truth objects
When updating canonical or derived outputs:
- build the new result
- validate it
- commit atomically

Do not partially overwrite canonical objects.

### 10. Be explicit about degraded behavior
If something is partial, stale, low-confidence, or blocked:
- model it explicitly
- expose it explicitly where appropriate
- do not silently treat unknown as zero

---

## Expected Repo Layering

Use and preserve this conceptual structure:

- `geography/`
- `companies/`
- `presence/`
- `hiring/`
- `entry_level/`
- `scoring/`
- `outputs/`
- `personalization/`
- `audit/`
- `orchestration/`
- `api/`
- `shared/`

Inside orchestration, preserve clear subdomains like:
- events
- jobs
- queues
- workers
- scheduler
- state machine
- invalidation

If the exact folder structure differs slightly, keep the same logical separation.

---

## What To Optimize For

Optimize for:

- correctness
- clarity
- maintainability
- auditable behavior
- strong boundaries
- easy future slice extension

Do **not** optimize first for:
- novelty
- premature scale tricks
- broad feature coverage
- premature UI completeness

---

## Database and Data Modeling Rules

When implementing schema/model logic:

- keep canonical truth normalized enough to stay auditable
- keep relationships explicit
- use stable identifiers
- include version/state/freshness/confidence where the architecture requires it
- do not bury essential truth in opaque blobs

Derived output payloads may live in object/artifact storage, but canonical truth should remain queryable and structured.

---

## Queue / Job / Worker Rules

When implementing orchestration:

- keep queue boundaries aligned with the documented queue model
- keep job contracts explicit
- keep retry behavior conservative for foundational jobs
- dedupe semantically identical queued jobs when appropriate
- do not allow downstream fan-out before upstream commit succeeds
- do not let stale upstream versions generate canonical downstream outputs

If job dependencies are not satisfied, block or defer cleanly rather than improvising.

---

## API Rules

For API implementation:

- keep endpoints thin
- prefer reading prepared output objects
- expose freshness/state metadata where useful
- do not stuff orchestration logic into controllers/routes
- do not let endpoints mutate canonical truth unless the endpoint is explicitly administrative/internal

Public endpoints should mostly be read-oriented.

---

## Testing Expectations

For each implementation slice, add or update tests appropriate to that slice.

Prefer tests that verify:

- schema/model correctness
- state transitions
- version handling
- dependency rules
- invalidation behavior
- correct separation of truth vs derived outputs
- correct handling of stale/partial/blocked conditions

Do not skip tests for foundational logic.

---

## Documentation Update Rules

Only update docs when the implemented slice changes source-of-truth behavior.

Do not casually rewrite the architecture docs.

If a slice adds implementation details without changing source-of-truth architecture:
- keep doc changes minimal

If you must update docs:
- update only the specific relevant file(s)
- preserve terminology and architectural boundaries already established

---

## Output Expectations for Each Slice

Unless told otherwise, when implementing a slice:

1. implement only the requested scope
2. add/update relevant tests
3. add minimal necessary wiring
4. update only strictly necessary docs
5. summarize:
   - files created
   - files modified
   - what was implemented
   - what was intentionally not implemented

Be explicit about omissions and boundaries.

---

## Non-Goals / Things To Avoid

Do not:

- build frontend/UI unless explicitly requested
- invent extra product features
- create broad admin systems unless explicitly requested
- add nationwide coverage assumptions to MVP code
- implement every future job/queue/state if the slice does not require it
- create speculative plugin systems
- replace simple repo modules with distributed services
- collapse multiple slices into one giant implementation

---

## If Something Is Ambiguous

When ambiguity appears:

1. prefer the documented MVP scope
2. prefer the slice plan
3. prefer simple implementations
4. preserve truth/output/personalization separation
5. avoid broadening scope

If a decision would materially change architecture, stop short of inventing a new architecture.  
Implement the narrowest version consistent with the docs.

---

## Practical Default

The default mode for this repo is:

**implement the smallest correct slice that fits the documented architecture, passes tests, preserves boundaries, and does not overbuild.**