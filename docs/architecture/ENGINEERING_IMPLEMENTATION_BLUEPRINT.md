# Engineering Implementation Blueprint

> **Status: historical/deferred architecture plan.** This document predates the implemented local architecture and intentionally describes possible queues, workers, caches, and object storage. Those components are not required by the portfolio application. See [`../ENGINEERING_GUIDE.md`](../ENGINEERING_GUIDE.md) for the current runnable system.

Backend Components, Data Stores, Queues, Workers, Schedulers, Caches, and API Surfaces

This preserves the original workflow-system blueprint for historical context. It is not a statement that every component below is currently deployed.

⸻

1. System Goal
Build a backend system that can:
* maintain a company universe
* map companies to regions
* map hiring and entry-level opportunity by region
* compute market scores
* serve region pages, company pages, comparisons, and personalized views
* refresh selectively without rebuilding everything
* expose all of that through app-ready APIs
The core engineering principle remains:
truth is built in background pipelines; product views read prepared truth and adapt it quickly.

⸻

2. Top-Level System Components
The cleanest architecture is seven major backend components.
Component 1 — Primary Database
Stores canonical structured truth.
This is where the durable system state lives:
* regions
* companies
* classifications
* company-region presence
* hiring snapshots
* entry-level snapshots
* score objects
* output object metadata
* job records
* audit records
Component 2 — Object Store / Artifact Store
Stores heavier built payloads and versioned objects.
Good for:
* region output objects
* company output objects
* comparison output objects
* contextual challenge objects
* audit artifacts
* large serialized intermediate results
Component 3 — Queue / Job Broker
Moves work between orchestration and workers.
Good for:
* foundational jobs
* refresh jobs
* output build jobs
* interactive jobs
* audit jobs
Component 4 — Worker Fleet
Processes queued jobs.
Different worker groups for:
* foundational truth
* refresh
* output assembly
* interactive personalization
* audit/repair
Component 5 — Scheduler / Orchestrator
Decides what runs, when, and why.
Handles:
* scheduled refresh cadence
* event-trigger routing
* dependency checks
* invalidation logic
* retries
* dedupe/coalescing
Component 6 — Cache Layer
Serves fast reads to the app.
Good for:
* region output cache
* company output cache
* comparison cache
* personalized session cache
* hot ranking caches
Component 7 — API Layer
Exposes app-facing endpoints.
Handles:
* region data
* company data
* map data
* comparison data
* personalized discovery
* filter/search
* admin/ops endpoints

⸻

3. Recommended Infrastructure Shape
At a practical level, the architecture should probably look like this:
3.1 Relational DB
Use a relational database for canonical truth.
Best fit for:
* normalized entities
* joins across companies, regions, presence, hiring, scores
* auditability
* version tracking
* operational integrity
This should be the system of record.
3.2 Redis-like cache
Use a fast in-memory cache for:
* region outputs
* company outputs
* hot comparisons
* session personalization
* freshness markers
* job dedupe keys
3.3 Blob/object storage
Use object storage for:
* serialized output objects
* historical snapshots
* audit reports
* rebuild artifacts
* long comparison outputs
3.4 Queue broker
Use a real task queue / broker.
Needs:
* multiple queues
* priority support
* retries
* dead-letter behavior
* worker-group isolation

⸻

4. Canonical Backend Services
The backend should be split into logical services/modules, even if they start in one codebase.
Service A — Geography Service
Owns:
* region registry
* geography definitions
* region hierarchy
* labor market groupings
* normalization profile references
Service B — Company Universe Service
Owns:
* candidate company intake
* eligibility
* major-tech classification
* Mag 7 tagging
* override tracking
* classification confidence
Service C — Presence Service
Owns:
* company-region presence mapping
* office/operations/hiring evidence normalization
* presence confidence
* presence status transitions
Service D — Hiring Intelligence Service
Owns:
* hiring snapshots
* time-window aggregations
* role-family summaries
* hiring program counts
* freshness markers for hiring data
Service E — Early-Career Service
Owns:
* internship detection
* co-op detection
* entry-level FT detection
* formal early-career program signals
* recurrence detection
* entry-level access score inputs
Service F — Scoring Service
Owns:
* structural ecosystem score
* live market score
* objective opportunity score
* normalized region scores
* scoring ruleset versions
Service G — Output Assembly Service
Owns:
* region output objects
* company output objects
* comparison output objects
* contextual challenge objects
Service H — Personalization Service
Owns:
* role/industry preference interpretation
* personal overlay scores
* personalized rankings
* personalized company targets
Service I — Audit & Integrity Service
Owns:
* override balance checks
* double-counting detection
* personal-vs-objective integrity checks
* presence inflation checks
* audit report creation
Service J — Orchestration Service
Owns:
* job creation
* event routing
* dependency resolution
* queue placement
* invalidation
* retries
* coalescing

⸻

5. Data Model Blueprint
This is the backend data model at a system level.
5.1 Core truth tables
regions
Stores canonical geography objects.
Core fields:
* region_id
* region_name
* display_name
* region_type
* parent_region_id
* labor_market_group
* normalization_profile_id
* state
* version
* timestamps
companies
Stores canonical company records.
Core fields:
* company_id
* company_name
* sector_primary
* sector_secondary
* public_or_private
* eligibility_status
* eligibility_score
* eligibility_override_flag
* eligibility_override_reason
* classification_confidence
* is_major_tech
* major_tech_score
* is_mag7
* state
* version
* timestamps
company_region_presence
Stores company-region presence truth.
Core fields:
* company_id
* region_id
* presence_status
* presence_basis
* office_evidence_flag
* operations_evidence_flag
* hiring_evidence_flag
* presence_confidence
* state
* version
* timestamps
company_region_hiring
Stores hiring truth by company-region.
Core fields:
* company_id
* region_id
* currently_hiring_flag
* active_posting_count_now
* posting_count_30d
* posting_count_90d
* annualized_trend_signal
* seasonal_student_hiring_signal
* hiring_program_count
* role_family_summary
* hiring_confidence
* state
* version
* timestamps
company_region_entry_level
Stores early-career truth.
Core fields:
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
* timestamps
region_market_scores
Stores region-level scoring results.
Core fields:
* region_id
* structural_ecosystem_score
* live_market_score
* objective_opportunity_score
* raw_total_score
* general_density_score
* tech_market_density_score
* early_career_accessibility_score
* score_ruleset_version
* state
* version
* timestamps

⸻

5.2 Output metadata tables
region_outputs
Stores metadata for region output artifacts.
Core fields:
* region_output_id
* region_id
* artifact_uri
* artifact_hash
* source_versions
* state
* freshness_expires_at
* timestamps
company_outputs
Stores metadata for company output artifacts.
comparison_outputs
Stores metadata for comparison artifacts.
contextual_challenge_outputs
Stores metadata for contextual challenge artifacts.
These point to object storage or cache, not necessarily hold the full object body.

⸻

5.3 Job and orchestration tables
jobs
Stores job envelopes and execution state.
Core fields:
* job_id
* job_type
* queue_name
* status
* priority
* scope_hash
* dedupe_key
* retry_count
* max_retries
* input_hash
* output_hash
* dependency_refs
* timestamps
* error fields
job_events
Tracks event-driven orchestration history.
job_dependencies
Explicit dependency edges if needed.
dead_letter_jobs
Stores failed jobs that exhausted retries.

⸻

5.4 Integrity and audit tables
audit_reports
override_ledger
confidence_events
repair_actions
These are useful both for trust and later admin tooling.

⸻

6. Object Storage Blueprint
Use object storage for fully assembled payloads and big serialized outputs.
Store these as versioned artifacts
* region output JSON
* company output JSON
* comparison output JSON
* contextual challenge JSON
* audit artifact JSON
* maybe historical score snapshots
Each artifact should have:
* artifact_uri
* artifact_hash
* source_version_bundle
* created_at
This lets the DB hold metadata while large objects live elsewhere.

⸻

7. Cache Blueprint
The cache layer should be explicit and multi-level.
7.1 Cache categories
Region cache
Keyed by:
* region_output::<region_id>::<version>
Company cache
Keyed by:
* company_output::<company_id>::<version>
Comparison cache
Keyed by:
* comparison::<regionA>::<regionB>::<version_bundle>
Personalization cache
Keyed by:
* personalized::<user_or_session>::<query_hash>
Hot rankings cache
Keyed by:
* rankings::<mode>::<region_scope>::<filters_hash>

⸻

7.2 Cache rules
Use cache for
* app reads
* frequent comparisons
* map panels
* top regions/companies
* session personalization
Never treat cache as source of truth
Truth remains in:
* relational DB
* versioned artifacts
Cache invalidation comes from orchestrator events
Not ad hoc UI logic.

⸻

8. Queue Blueprint
You already defined the queue model. Here is how it should be implemented.
8.1 MVP queues
q_foundational
For:
* geography
* intake
* classification
* large presence mapping
q_refresh
For:
* hiring refresh
* entry-level refresh
* region score recompute
q_output
For:
* region output build
* company output build
* comparison cache build
q_interactive
For:
* personal overlay
* on-demand comparison assembly
* contextual challenge
Later:
* q_audit
* q_precompute
That is enough for MVP.

⸻

8.2 Queue messages
Each queued job should include:
* request envelope
* dedupe key
* dependency refs
* freshness deadline
* priority
* retry count

⸻

9. Worker Blueprint
9.1 Foundational workers
Read/write:
* DB heavily
* object storage sometimes
* cache minimally
Should:
* validate dependencies
* compute truth
* commit atomically
* emit downstream events only after commit
9.2 Refresh workers
Read:
* DB truth
* sourcesWrite:
* DB snapshots
* region score updates
* cache invalidation events
9.3 Output workers
Read:
* DB truth
* score objectsWrite:
* object storage artifacts
* output metadata
* cache entries
9.4 Interactive workers
Read:
* cache first
* DB fallbackWrite:
* session cache only
* maybe ephemeral comparison artifacts
Should not:
* mutate foundational truth
9.5 Audit workers
Read broadly across truth and outputs.Write:
* audit reports
* warnings
* repair recommendations

⸻

10. Scheduler / Orchestrator Blueprint
This is the brain.
It should have five responsibilities.
10.1 Event intake
Consume events like:
* REGION_ADDED
* HIRING_DATA_UPDATED
* COMPARISON_REQUESTED
10.2 Routing
Map events to jobs.
10.3 Dependency resolution
Check:
* dependency exists
* dependency state valid
* version compatibility
* stale/superseded conditions
10.4 Dedupe/coalescing
Prevent duplicate jobs.Merge equivalent scopes when safe.
10.5 Invalidation and downstream fan-out
When a job succeeds:
* invalidate relevant caches/outputs
* enqueue next jobs
* suppress unnecessary fan-out if no meaningful change
This service is central enough that it should be a clearly isolated subsystem.

⸻

11. API Blueprint
The API layer should be thin and read-oriented.
11.1 Public/user-facing endpoints
Region endpoints
* GET /regions
* GET /regions/{region_id}
* GET /regions/{region_id}/companies
* GET /regions/{region_id}/hiring
* GET /regions/{region_id}/entry-level
Company endpoints
* GET /companies/{company_id}
* GET /companies/{company_id}/regions
* GET /companies/{company_id}/hiring
Comparison endpoints
* GET /compare?region_a=...&region_b=...
* GET /compare/contextual?comparison_id=...
Discovery/search endpoints
* GET /search/companies
* GET /search/regions
* POST /discover/personalized
Map endpoints
* GET /map/regions
* GET /map/region-summary
* GET /map/heat

⸻

11.2 Admin/ops endpoints
Refresh/control
* POST /admin/jobs/run
* POST /admin/regions/add
* POST /admin/refresh/region
* POST /admin/refresh/company
Audit/repair
* GET /admin/audits
* POST /admin/audits/run
* POST /admin/repair/company/{id}
Override management
* GET /admin/overrides
* POST /admin/overrides/review
These are critical later, even if hidden at MVP.

⸻

12. Read Path Blueprint
How a normal app read should work.
Example: region page
1. API receives GET /regions/{id}
2. check cache for region output
3. if fresh, return immediately
4. if stale but acceptable, return with freshness metadata and optionally enqueue refresh
5. if missing, check output metadata/object storage
6. if still unavailable, enqueue output build / upstream recompute as needed
7. return loading/degraded response if full object unavailable
Example: comparison
1. check comparison cache
2. if missing, use cached region outputs to assemble live
3. if region outputs stale, use stale-with-warning or enqueue rebuild
4. optionally create cached comparison artifact after response
This is the right user-serving pattern.

⸻

13. Write Path Blueprint
How a background update should work.
Example: hiring refresh
1. scheduler emits HIRING_DATA_UPDATED
2. orchestrator enqueues Hiring Refresh Job in q_refresh
3. worker fetches current presence-valid company-region pairs
4. worker refreshes hiring snapshot
5. writes new version atomically to DB
6. emits downstream event
7. orchestrator enqueues:
    * Entry-Level Refresh
    * Region Score Recompute
    * later output rebuilds
8. cache invalidation scoped to affected regions/companies/comparisons
This is the canonical update flow.

⸻

14. Versioning Blueprint
Everything important should be versioned.
Version at minimum
* region registry
* company universe
* presence map
* hiring map
* entry-level map
* region scores
* output objects
* scoring rulesets
* eligibility rulesets
* presence rulesets
Why
This lets you:
* trace provenance
* support idempotency
* avoid stale downstream reads
* compare outputs across rebuilds
* debug unexpected behavior
This is not optional for this kind of system.

⸻

15. State Handling Blueprint
Each stored object should include:
* state
* confidence
* freshness expiry
* source job id
* source version bundle
This allows:
* orchestrator decisions
* UI behavior
* audit behavior
* safe fallback behavior
The state model should be enforced in storage and in read logic.

⸻

16. Freshness Blueprint
The backend should define freshness by object type.
Examples
Company-region hiring
Short freshness window
Entry-level
Short to medium freshness window
Region scores
Medium freshness window
Region outputs
Derived freshness from underlying score/hiring freshness
Geography and classification
Long freshness window
The freshness service can be simple at first, but it should exist conceptually.

⸻

17. Security / Access Blueprint
Even if this starts small, separate these concerns now.
Public read layer
Safe app-facing read endpoints only.
Admin mutation layer
Protected endpoints for:
* forcing rebuilds
* reviewing overrides
* editing regions
* marking objects stale
* triggering audits
Internal job credentials
Workers should have internal service access, not user-facing tokens.
This matters later when the app grows.

⸻

18. Observability Blueprint
You need visibility into the system or it becomes impossible to trust.
Track at minimum
* queue depth
* job success/failure rates
* retry rates
* region freshness
* comparison freshness
* cache hit rate
* average API latency
* object state distribution
* audit failure counts
Log structured events for
* job start
* job success
* job partial success
* job failure
* object state transitions
* cache invalidations
* downstream enqueue decisions
This is essential.

⸻

19. Suggested MVP Implementation Stack Shape
Without naming specific vendors, the MVP should conceptually be:
* one backend application codebase with modular services
* one relational DB
* one queue broker
* one cache store
* one object store
* one scheduler/orchestrator process
* a few worker processes by queue type
* one API server
Do not prematurely split into many separate deployable services unless needed.Start modular, not fragmented.

⸻

20. Suggested Internal Module Layout
Inside one backend repo, I would structure it roughly like:
* geography/
* companies/
* presence/
* hiring/
* entry_level/
* scoring/
* outputs/
* personalization/
* audit/
* orchestration/
* api/
* shared/
And inside orchestration:
* events/
* jobs/
* queues/
* workers/
* scheduler/
* state_machine/
* invalidation/
That keeps it sane.

⸻

21. MVP Buildable Slice
If you were building the first real version, I would keep V1 to this:
Must-have backend features
* region registry
* company universe + classification
* company-region presence
* hiring refresh
* entry-level extraction
* region score recompute
* region output build
* company output build
* live personalized overlay
* comparison endpoint
Can defer
* full audit sophistication
* contextual challenge artifact caching
* advanced repair workflows
* long-tail precompute queue
* complicated admin tooling
* broad nationwide geography at first
That is the realistic cut.

⸻

22. Strongest Engineering Rule
If I had to reduce the entire blueprint to one implementation rule:
store canonical truth in structured versioned records, build derived outputs asynchronously, and let the app read cached assembled views instead of recomputing truth in request time.
That is the backbone of the product.
