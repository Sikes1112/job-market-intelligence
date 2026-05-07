# MVP_SCOPE.md

## Purpose

This file freezes the build scope for **MVP V1** of the job-market intelligence platform backend.

Its purpose is to prevent implementation drift.

If a feature, workflow, geography, role family, or system layer is not explicitly included here, treat it as **out of scope for MVP V1** unless the implementation prompt says otherwise.

This file is a build constraint, not a brainstorming document.

---

## Product Summary

MVP V1 is a backend system for a job-market intelligence platform that helps users understand **where opportunity is strongest** across selected labor regions.

The MVP is **not** a full national labor-market platform, a generic job board, or a complete frontend product.

The MVP backend must support:

- a structured company universe
- regional company presence mapping
- hiring activity mapping by region
- entry-level opportunity mapping
- region-level scoring
- company and region outputs
- comparison as a feature
- lightweight personalization overlays

The system must preserve the separation between:

1. **canonical market truth**
2. **derived output objects**
3. **user-specific personalization**

---

## MVP V1 Goal

Build a backend that can support this product behavior for a limited, high-value slice:

- selected major U.S. tech labor markets
- selected role families
- early-career emphasis
- region pages
- company geography pages
- region comparisons
- personalized discovery overlays

The backend should be implementation-ready and slice-friendly for Claude Code.

---

## In-Scope Product Capabilities

MVP V1 includes the following capabilities.

### 1. Geography-aware market modeling
The system must support region objects such as:
- city-like labor region
- greater region / metro-like region
- state only if explicitly included in the initial geography list

The backend must be able to represent:
- region identifiers
- display names
- parent-child geography relationships
- labor market grouping
- normalization profile references

### 2. Company universe and classification
The backend must support:
- candidate company intake
- eligibility decisions
- override-included companies
- major-tech labeling
- Magnificent 7 labeling
- classification confidence

### 3. Company-region presence mapping
The backend must support:
- meaningful regional presence records
- office/operations/hiring evidence basis
- presence confidence
- versioned presence truth

### 4. Hiring activity mapping
The backend must support:
- current hiring flags
- current posting counts
- 30-day and 90-day counts
- annualized trend signal
- seasonal student hiring signal
- hiring program count
- role-family summary

### 5. Entry-level opportunity mapping
The backend must support:
- internship counts
- co-op counts
- entry-level full-time counts
- formal early-career program flag
- recurrence signal
- entry-level access score

### 6. Region-level scoring
The backend must support:
- structural ecosystem score
- live market score
- objective opportunity score
- raw total score
- general density score
- tech-market density score
- early-career accessibility score

### 7. Derived output objects
The backend must support:
- region output objects
- company output objects
- comparison output objects
- contextual challenge objects can exist as a minimal stub or lightweight implementation if required by the slice

### 8. Personalization overlay
The backend must support:
- user role targets
- user industry preferences
- user career-stage preference
- prestige preference
- brand preference
- personalized region ranking
- personalized company ranking

### 9. API support for MVP reads
The backend must support app-facing read APIs for:
- region view
- company view
- comparison view
- personalized discovery/query

### 10. Background orchestration
The backend must support:
- jobs
- queue routing
- dependency checking
- retries
- object states
- invalidation logic
- refresh workflows

---

## MVP V1 Core User Flows

The backend must be able to support these flows.

### Flow 1 — Region exploration
A user can request a region and get:
- region summary
- major companies present
- top companies hiring
- entry-level summary
- market scores

### Flow 2 — Company geography exploration
A user can request a company and get:
- where it is present
- where it is hiring
- where it has entry-level opportunities

### Flow 3 — Comparison
A user can compare two supported regions and get:
- side-by-side summary
- category comparisons
- score comparisons
- optional contextual challenge view

### Flow 4 — Personalized discovery
A user can submit preferences and get:
- best regions for them
- best companies for them
- filtered and ranked outputs based on their preferences

### Flow 5 — Background freshness
The system can refresh hiring and entry-level layers without rebuilding the entire truth layer.

---

## MVP V1 Geography Scope

MVP V1 should start with a **small, deliberate geography set**.

The backend should be designed to expand, but should not try to implement nationwide breadth immediately.

### Initial recommended geography set
MVP V1 should support a small set such as:
- Greater Boston
- Greater San Francisco / Silicon Valley
- New York City / Greater NYC
- Seattle
- Austin
- Washington, DC / Northern Virginia region if included explicitly

For the absolute narrowest MVP, start with:
- Greater Boston
- Greater San Francisco / Silicon Valley

Additional regions can be added later through region expansion workflows.

### Geography rule
Do not implement arbitrary custom geography creation in MVP unless explicitly requested.
Use structured predefined region objects.

---

## MVP V1 Role Family Scope

MVP V1 should **not** attempt every possible job function.

Start with a small, useful role-family set.

### In-scope role families
Recommended MVP set:
- product
- AI-adjacent technical business roles
- cloud / solutions / technical account-style roles
- cybersecurity only if explicitly included in the initial build scope

For the narrowest MVP, start with:
- product
- AI/cloud-adjacent non-pure-engineering roles

### Out of scope by default
Do not make MVP depend on full support for:
- all software engineering role taxonomy
- every design role taxonomy
- every operations taxonomy
- every analytics taxonomy
- every legal/policy role taxonomy

These can be added later.

---

## MVP V1 Career Stage Scope

MVP V1 is explicitly **early-career weighted**.

### In scope
- internships
- co-ops
- entry-level full-time
- formal early-career programs

### Supported personalization input
- entry-level / early-career emphasis

### Important note
The system may still store broader hiring counts, but MVP scoring and usefulness should center heavily on early-career opportunity.

---

## MVP V1 Company Universe Scope

MVP V1 includes:
- serious tech companies in the supported sectors
- eligible companies
- major tech companies
- Mag 7 companies
- credible override-included edge cases

### Included sector types
- software
- internet
- AI
- cloud
- data
- hardware
- cybersecurity if in chosen MVP slice

### Excluded by default
- biotech-specific companies
- martech-specific companies
- obviously irrelevant sectors
- very early/noisy startups

### Important note
The company universe should remain broad enough to include serious mid-sized firms, not only giant companies.

---

## MVP V1 Backend Surfaces

The backend must support these surfaces.

### Required
- region output retrieval
- company output retrieval
- comparison retrieval
- personalized discovery retrieval

### Optional but minimal
- contextual challenge retrieval
- basic admin refresh triggers

### Not required for MVP
- rich admin dashboards
- advanced moderation tools
- manual review UI
- public write endpoints
- complex user accounts if not required by the slice

---

## MVP V1 Data and System Requirements

The MVP backend must include these implementation foundations.

### Required
- relational canonical truth store
- queue/job system
- versioned objects
- object states
- cache layer
- output object assembly
- orchestrated refresh behavior
- dependency-aware job execution

### Also required
- tests for foundational logic
- deterministic contracts where possible
- explicit stale/partial/failed handling

### Not required for MVP
- multi-service deployment
- advanced distributed coordination
- enterprise auth complexity
- heavy analytics/BI pipelines
- full observability platform sophistication beyond sensible structured logging and metrics

---

## MVP V1 Must-Have Tables / Canonical Entities

At minimum, MVP V1 should include canonical support for:

- `regions`
- `companies`
- `company_region_presence`
- `company_region_hiring`
- `company_region_entry_level`
- `region_market_scores`
- `jobs`
- output metadata records for region/company/comparison objects

Optional for MVP but useful if slice reaches it:
- audit reports
- override ledger
- confidence events
- repair actions

---

## MVP V1 Must-Have Job Types

At minimum, MVP V1 should include:

- Geography Build
- Eligibility & Classification
- Presence Mapping
- Hiring Refresh
- Entry-Level Refresh
- Region Score Recompute
- Region Output Build
- Company Output Build
- Personal Overlay Query

Recommended but can be lighter initially:
- Comparison Cache Build
- Contextual Challenge Build
- Audit Job

---

## MVP V1 Must-Have Object States

At minimum, MVP V1 should implement:

- `new`
- `building`
- `fresh`
- `stale`
- `partial`
- `failed`
- `blocked`
- `rebuilding`

These can be expanded later with:
- `low_confidence`
- `verified`
- `deprecated`

if the slice reaches them.

---

## Explicit Non-Goals for MVP V1

These are out of scope unless explicitly requested.

### Product non-goals
- becoming a full national job board
- ingesting every possible U.S. city immediately
- supporting every role family immediately
- building a full frontend application
- building user networking or messaging
- building resume tools
- building application tracking systems
- building employer-side tooling

### Architecture non-goals
- microservice decomposition
- speculative plugin frameworks
- broad event-bus complexity beyond what the job/orchestration system needs
- fully generalized workflow engines beyond the documented orchestration model
- overbuilt admin systems

### Data non-goals
- perfect labor-market completeness
- exhaustive remote-role modeling in MVP core logic
- full custom geography creation
- full national normalization sophistication beyond the documented MVP needs

### UX/API non-goals
- public mutation-heavy APIs
- real-time collaborative features
- advanced dashboarding for admins
- overbuilt search semantics beyond MVP needs

---

## Implementation Guardrails for MVP

Claude Code implementation should follow these constraints.

### 1. Foundation first
Build:
- canonical schema
- orchestration skeleton
- truth services
before:
- fancy outputs
- advanced comparisons
- nonessential personalization

### 2. Derived outputs remain downstream
Region/company/comparison outputs must remain derived from truth objects.

### 3. Personalization remains overlay-only
Do not place user preference logic into canonical truth.

### 4. Comparison remains a feature
Do not center the whole backend around comparison-only workflows.

### 5. Keep MVP small
Prefer:
- fewer regions
- fewer role families
- fewer endpoints
- stronger foundations

over:
- broad feature sprawl

---

## What Counts as MVP Success

MVP V1 is successful if the backend can reliably do the following for the supported region set:

1. store and classify a valid company universe  
2. map meaningful company presence by region  
3. map hiring activity by region  
4. map entry-level opportunity by region  
5. compute region-level scores  
6. build region and company output objects  
7. compare two supported regions  
8. personalize rankings based on simple user preferences  
9. refresh dynamic market data without full rebuild  
10. expose read APIs for product use

That is enough for MVP.

---

## What To Do If A Slice Suggests More

If an implementation slice naturally suggests:
- more regions
- more roles
- more services
- more infra
- more APIs
- more admin tooling

do **not** add them automatically.

Treat them as post-MVP unless explicitly requested.

This file is intended to stop scope creep.
