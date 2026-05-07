Queue and Worker Model

Concurrency Limits, Retry Backoff, and Dependency-Aware Scheduling
This turns the event system into a runnable orchestration design.
 
⸻
 
1. Purpose
The app now has:
* jobs
* contracts
* triggers
* dependency rules
What it still needs is the execution model:
* which queues jobs go into
* which workers process them
* how many can run at once
* how retries behave
* how downstream jobs wait on upstream jobs
* how to avoid overload, duplicate work, and dependency thrashing
This is that layer.
 
⸻
 
2. Core Execution Principle
The system should run on this rule:
heavy truth-building jobs run in controlled background queues; lightweight adaptive jobs run in fast-response queues.
That means not all jobs are equal.
Some are:
* expensive
* slow
* foundational
* dangerous to rerun carelessly
Others are:
* cheap
* user-facing
* safe to compute live
So the queue model should reflect that.
 
⸻
 
3. Queue Classes
The cleanest structure is to use six queue classes.
Queue 1 — Foundational Build Queue
For slow, structural jobs that define market truth.
Job types
* Geography Build Job
* Company Universe Intake Job
* Eligibility & Classification Job
* large-scope Company-Region Presence Mapping Job
Characteristics
* low concurrency
* high caution
* strong dependency enforcement
* usually batch or admin triggered
Why separate
These jobs can invalidate lots of downstream state and should not compete with user-facing work.
 
⸻
 
Queue 2 — Market Refresh Queue
For dynamic but non-user-blocking market updates.
Job types
* Hiring Refresh Job
* Entry-Level Refresh Job
* Region Score Recompute Job
* medium-scope Presence Mapping updates
Characteristics
* medium concurrency
* recurring
* region/company scoped
* feeds most freshness improvements
Why separate
This is the operational heartbeat of the app after launch.
 
⸻
 
Queue 3 — Output Build Queue
For assembling cached app-facing objects.
Job types
* Region Output Build Job
* Company Output Build Job
* Comparison Cache Build Job
Characteristics
* moderate concurrency
* mostly deterministic
* rebuilds cached views
* often triggered by upstream changes
Why separate
These are cheaper than truth-building jobs and should not wait behind full rebuild logic.
 
⸻
 
Queue 4 — Fast Interactive Queue
For low-latency user-facing adaptive work.
Job types
* Personal Overlay Query Job
* live comparison assembly
* lightweight ranking/sorting/filtering
* Contextual Challenge Build Job when on-demand
Characteristics
* high priority
* low latency
* high concurrency
* should be isolated from slower background jobs
Why separate
User interactions should stay responsive even when background refreshes are happening.
 
⸻
 
Queue 5 — Audit and Repair Queue
For integrity checks and targeted repairs.
Job types
* Audit Job
* targeted repair workflows
* low-confidence rebuilds
* manual review follow-up jobs
Characteristics
* moderate concurrency
* may spike after failures
* should not starve product-facing queues
Why separate
Integrity work matters, but it should not choke the user experience.
 
⸻
 
Queue 6 — Scheduled Precompute Queue
For non-urgent optimization and cache warming.
Job types
* popular comparison precompute
* popular region ranking cache build
* long-tail company output rebuild
* low-priority refresh batches
Characteristics
* low priority
* opportunistic
* can be paused under load
Why separate
This is where nice-to-have work lives.
 
⸻
 
4. Worker Types
Each queue should have dedicated worker types.
Worker Type A — Foundational Workers
Handle:
* geography
* company intake
* classification
* broad presence mapping
Needs
* strong dependency checking
* idempotent writes
* version-safe output commits
Behavior
* few workers
* cautious scheduling
* no aggressive parallel fan-out unless scope is partitioned safely
 
⸻
 
Worker Type B — Market Refresh Workers
Handle:
* hiring refresh
* entry-level refresh
* score recompute
Needs
* good throughput
* region/company partition awareness
* downstream invalidation hooks
Behavior
* medium worker pool
* can parallelize by region or company-region pair
 
⸻
 
Worker Type C — Output Builders
Handle:
* region outputs
* company outputs
* comparison caches
Needs
* fast read access to cached truth objects
* deterministic rendering logic
* low-cost recomputation
Behavior
* medium to high concurrency
* safe to scale horizontally
 
⸻
 
Worker Type D — Interactive Workers
Handle:
* personal overlay
* live ranking
* contextual challenge
* fast comparison assembly
Needs
* low latency
* access to precomputed objects
* aggressive timeouts
* session-aware caching
Behavior
* high concurrency
* strict latency budget
* should never run heavy foundational recompute
 
⸻
 
Worker Type E — Audit/Repair Workers
Handle:
* audits
* integrity scans
* targeted repair jobs
Needs
* broad read access
* rule evaluation
* escalation hooks
Behavior
* moderate concurrency
* can be deprioritized under heavy user load
 
⸻
 
5. Recommended Concurrency Model
These are conceptual limits, not exact infrastructure numbers.
Foundational Build Queue
Concurrency
Very low
Recommended behavior:
* 1 to 2 major jobs at once globally
* partition within job only when safe
Why
These jobs create truth and can cause cascading invalidation.
 
⸻
 
Market Refresh Queue
Concurrency
Moderate
Recommended behavior:
* parallelize by region
* parallelize by company-region shard
* cap concurrency to avoid hammering sources
Why
This queue needs throughput, but also must respect source/rate limits.
 
⸻
 
Output Build Queue
Concurrency
Moderate to high
Recommended behavior:
* region outputs can build in parallel
* company outputs can build in parallel
* comparison caches can fan out after region outputs stabilize
Why
These jobs are relatively safe and good candidates for horizontal scale.
 
⸻
 
Fast Interactive Queue
Concurrency
High
Recommended behavior:
* scale with traffic
* small per-job runtime budget
* reject or degrade rather than block
Why
This queue directly affects UX.
 
⸻
 
Audit and Repair Queue
Concurrency
Low to moderate
Recommended behavior:
* run continuously but politely
* yield to user-facing pressure when needed
Why
Important, but not allowed to interfere with responsiveness.
 
⸻
 
Scheduled Precompute Queue
Concurrency
Elastic but lowest priority
Recommended behavior:
* run when spare capacity exists
* throttle heavily under load
Why
Useful for speed, not critical for correctness.
 
⸻
 
6. Dependency-Aware Scheduling Rules
This is one of the most important sections.
Rule 1 — A job may not start unless required dependency refs are in a valid state
For example:
* Hiring Refresh cannot run without valid presence map refs
* Region Output Build cannot run without valid region score refs
So the scheduler must check:
* dependency exists
* dependency not failed
* dependency version compatible
* dependency not superseded by newer required version
 
⸻
 
Rule 2 — Downstream jobs should wait on the minimum necessary scope
Do not block all hiring refreshes because one unrelated region’s presence mapping failed.
Dependency waiting should be scoped to:
* company
* region
* company-region pair
* comparison pair
not entire global system unless truly necessary.
This is critical.
 
⸻
 
Rule 3 — Newer upstream versions should supersede stale queued downstream jobs
Example:
* Region Score Recompute for Greater Boston v17 is queued
* before it runs, Hiring Refresh emits v18-relevant data
* the queued recompute based on stale dependencies should be cancelled, upgraded, or merged
Otherwise you waste compute and emit stale outputs.
 
⸻
 
Rule 4 — Jobs should carry scope-aware dedupe keys
Examples:
* region_score_recompute::greater_boston::regionscore_inputs_hash
* company_output_build::comp_101::companyout_inputs_hash
If a semantically identical job is already queued or running, do not enqueue another one unnecessarily.
 
⸻
 
Rule 5 — Fan-out only after upstream commit succeeds
Example:
* Hiring Refresh finishes successfully
* then enqueue Entry-Level Refresh and Region Score Recompute
Do not fan out from a running or partial upstream job unless the system explicitly supports partial downstream operation.
 
⸻
 
7. Queue Priority Order
When system pressure is high, prioritize in this order:
Priority Tier 1
Fast Interactive Queue
Because user-visible latency matters most.
Priority Tier 2
Market Refresh Queue for active/high-traffic regions
Because stale markets damage usefulness quickly.
Priority Tier 3
Output Build Queue for affected active regions/companies
Because refreshed truth must become visible.
Priority Tier 4
Audit and Repair Queue
Because trust matters, but not at the cost of killing UX.
Priority Tier 5
Scheduled Precompute Queue
This is easiest to defer.
Priority Tier 6
Large Foundational Build jobs not tied to immediate product needs
These are important but should be carefully scheduled.
 
⸻
 
8. Retry Backoff Rules
Retry behavior should differ by queue and failure type.
Foundational Build Queue
Retry policy
* very conservative
* retry only truly transient failures
* cap attempts low
* escalate quickly
Why
A bad foundational job should not thrash and create instability.
 
⸻
 
Market Refresh Queue
Retry policy
* moderate retry tolerance
* exponential backoff
* jitter
* scope-preserving reruns
Why
Refresh failures are often transient and worth retrying.
 
⸻
 
Output Build Queue
Retry policy
* retry transient read/template/cache failures
* low risk
* can often recover quickly
Why
These are cheap enough to retry a bit more.
 
⸻
 
Fast Interactive Queue
Retry policy
* minimal retry
* fail fast
* fall back to cached/stale output if possible
Why
User-facing requests care more about responsiveness than perfect recomputation.
 
⸻
 
Audit and Repair Queue
Retry policy
* moderate
* if repeated failure, escalate to manual/admin or repair backlog
 
⸻
 
9. Suggested Backoff Pattern
Conceptually:
Retry attempt 1
Immediate short retry for clear transient hiccup
Retry attempt 2
Exponential delay with jitter
Retry attempt 3
Longer exponential delay
Retry attempt 4+
Stop automatic retries for most jobs and escalate
This should especially be true for:
* foundational jobs
* repeated source failures
* dependency failures
You do not want retry storms.
 
⸻
 
10. Timeout Model
Each queue should have a different timeout budget.
Foundational Build Queue
Long timeout budget
Because these jobs are heavy.
Market Refresh Queue
Medium timeout budget
Because they process many scoped updates but should not hang forever.
Output Build Queue
Short to medium timeout budget
Because object builds should be fairly deterministic.
Fast Interactive Queue
Very short timeout budget
If it cannot finish quickly, return cached or degraded output.
Audit Queue
Medium timeout budget
Can run longer than user-facing work, but should still be bounded.
 
⸻
 
11. Cancellation Rules
Cancellation is important for efficiency.
Cancel queued jobs when
* their dependency version is obsolete
* their scope has been superseded by a newer broader job
* no meaningful change means downstream work is no longer needed
* user session no longer needs the interactive result
Examples:
* old region comparison cache build for stale region output
* personal overlay job for a user who changed filters again
* score recompute based on stale hiring version
 
⸻
 
Do not cancel running foundational jobs lightly
Unless:
* administrator intervention
* detected corruption
* version conflict requiring safe abort
* resource emergency
Because stopping truth-building halfway can be messy.
 
⸻
 
12. Coalescing Rules
To avoid queue spam, the scheduler should merge compatible jobs.
Good coalescing examples
* multiple Hiring Refresh events for same region close together → one merged refresh job
* multiple Region Score Recompute triggers for same region → one recompute
* multiple Company Output rebuilds for same company → one rebuild
Do not coalesce when
* scopes are logically incompatible
* priority mismatch is too large
* user-specific jobs belong to different sessions/users
 
⸻
 
13. Partitioning / Sharding Rules
For scalability, jobs should shard along the natural boundaries of the product.
Best shard keys
* region_id
* company_id
* company_region_pair
* comparison_pair
Recommended use
Presence Mapping
Shard by company-region pair or by region
Hiring Refresh
Shard by company-region pair or region batch
Entry-Level Refresh
Shard by company-region pair
Region Score Recompute
Shard by region
Output Build
Shard by region or company
This reduces cross-job contention.
 
⸻
 
14. Freshness-Sensitive Scheduling
Some jobs should get priority boosts when the object they affect is highly visible.
Boost priority when
* region is frequently viewed
* company is frequently viewed
* comparison is popular
* user is actively waiting on the result
* stale age crosses freshness threshold
This is a strong product optimization.
So not all stale regions are equally important:
* Greater Boston, Greater SF, NYC might deserve more frequent refresh
* long-tail regions may use slower cadences
 
⸻
 
15. Worker Safety Rules
Rule 1 — Write outputs atomically
A worker should not partially overwrite the canonical object. Use:
* build temp result
* validate
* commit atomically
Rule 2 — Version every major object
Workers must read and write versioned objects so downstream jobs can tell what they depend on.
Rule 3 — Emit downstream events only after successful commit
Otherwise downstream jobs may start from outputs that were never safely published.
Rule 4 — Respect idempotency keys
A retry should not duplicate writes or create conflicting objects.
Rule 5 — Record degraded confidence explicitly
If a job succeeds with warnings, the worker must mark that in the output metadata.
 
⸻
 
16. Queue Admission Rules
Not every requested job should be admitted immediately.
Admit immediately
* user interactive jobs
* critical refreshes for active regions
* dependency-repair jobs blocking user-facing outputs
Admit conditionally
* large foundational jobs during heavy traffic
* long-tail precomputes
* low-priority audits
Delay or reject
* duplicate jobs with same dedupe key
* jobs blocked by missing dependencies
* jobs for stale superseded versions
* jobs that exceed retry threshold without intervention
 
⸻
 
17. Queue Health Rules
The orchestrator should monitor:
* queue depth
* median wait time
* retry rate
* failure rate
* stale-output rate
* superseded-job rate
* cancellation rate
These are important because they tell you:
* whether the product feels fresh
* whether queues are overloaded
* whether job design is too noisy
* whether workers are thrashing on stale scopes
 
⸻
 
18. Failure Escalation Path
When a job repeatedly fails:
Step 1
Retry according to queue policy
Step 2
If failure threshold reached, mark affected object scope:
* stale
* degraded
* low confidence
* blocked
Step 3
Enqueue Audit/Repair workflow
Step 4
If still unresolved, escalate to manual/admin review queue
This keeps failures from silently poisoning outputs.
 
⸻
 
19. Minimal Queue Contract Fields
Each queued job should carry:
{
  "queue_name": "string",
  "worker_type": "string",
  "dedupe_key": "string",
  "priority": "low | normal | high | urgent",
  "scope_hash": "string",
  "dependency_refs": [],
  "retry_count": 0,
  "max_retries": 3,
  "enqueue_time": "ISO-8601 timestamp",
  "freshness_deadline": "ISO-8601 timestamp or null",
  "supersedes_job_id": null
}
These fields let the scheduler reason properly.
 
⸻
 
20. Recommended Queue Layout for MVP
For a realistic MVP, do not overcomplicate this.
You probably only need four real queues at first:
MVP Queue A — Foundational
* geography
* intake
* classification
* presence
MVP Queue B — Refresh
* hiring
* entry-level
* region score recompute
MVP Queue C — Output
* region output
* company output
* comparison cache
MVP Queue D — Interactive
* personal overlay
* live comparison
* contextual challenge
Then later add:
* audit/repair queue
* precompute queue
That is probably enough to start.
 
⸻
 
21. Strongest Engineering Principle
If I had to compress the whole queue model into one sentence:
truth jobs should be serialized more carefully than view jobs, and user-facing jobs should almost always read prepared truth rather than trying to create truth live.
That is the core of the system.
 
⸻