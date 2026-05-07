Event Trigger Map

If X Changes, Enqueue Jobs A/B/C; If Y Fails, Block Jobs D/E; Cached Path First, Fallback Path Second

This connects the job contracts into an actual orchestration engine.

⸻

1. Purpose
The event trigger map defines:
* what events the system listens for
* which jobs those events enqueue
* which downstream jobs are blocked if an upstream dependency fails
* when the app should use cached outputs
* when it should fall back to live rebuild/recompute
This is the control logic between product behavior and the job system.

⸻

2. Core Trigger Types
The app should recognize five trigger classes:
A. Foundational data triggers
Examples:
* region added
* region definition changed
* sector scope changed
* eligibility rules changed
* major-tech rubric changed
B. Company-level triggers
Examples:
* company added
* company reclassified
* company office/presence updated
* company hiring changed
C. Market-activity triggers
Examples:
* new hiring batch
* current postings changed
* entry-level signals changed
* seasonal hiring signal updated
D. User-interaction triggers
Examples:
* region page opened
* search/filter updated
* personalized ranking requested
* comparison requested
* contextual challenge requested
E. Integrity/control triggers
Examples:
* audit failed
* object marked stale
* dependency missing
* repeated refresh failure
* override imbalance detected

⸻

3. Trigger-to-Job Routing Rules
Trigger 1 — New Region Added
Event
REGION_ADDED
Enqueue
1. Geography Build Job
2. Company-Region Presence Mapping Job
3. Hiring Refresh Job
4. Entry-Level Refresh Job
5. Region Score Recompute Job
6. Region Output Build Job
7. Company Output Build Job for newly linked companies
8. Audit Job
Block conditions
Do not run:
* Presence Mappingunless Geography Build succeeds
Do not run:
* Hiring Refreshunless Presence Mapping succeeds
Notes
This is the standard region expansion workflow.

⸻

Trigger 2 — Region Definition Changed
Event
REGION_DEFINITION_CHANGED
Enqueue
1. Geography Build Job
2. Company-Region Presence Mapping Job for affected region(s)
3. Hiring Refresh Job for affected company-region pairs
4. Entry-Level Refresh Job
5. Region Score Recompute Job
6. Region Output Build Job
7. Comparison Cache Build Job for affected comparisons
8. Audit Job
Block conditions
If geography update fails:
* block all downstream region-dependent jobs
Invalidate
* affected region outputs
* affected comparison caches
* affected normalization outputs

⸻

Trigger 3 — Sector Scope Changed
Event
SECTOR_SCOPE_CHANGED
Enqueue
1. Company Universe Intake Job
2. Eligibility & Classification Job
3. Company-Region Presence Mapping Job
4. Hiring Refresh Job
5. Entry-Level Refresh Job
6. Region Score Recompute Job
7. Region Output Build Job
8. Company Output Build Job
9. Comparison Cache Build Job
10. Audit Job
Block conditions
If Intake or Classification fails:
* block all downstream company-truth rebuild steps
Notes
This is near-full rebuild territory.

⸻

Trigger 4 — Eligibility Rules Changed
Event
ELIGIBILITY_RULES_CHANGED
Enqueue
1. Eligibility & Classification Job
2. Company-Region Presence Mapping Job for affected companies
3. Hiring Refresh Job for affected pairs
4. Entry-Level Refresh Job
5. Region Score Recompute Job
6. Region Output Build Job
7. Company Output Build Job
8. Comparison Cache Build Job
9. Audit Job
Block conditions
If Classification fails:
* block presence, hiring, entry-level, score, and outputs for affected scope
Notes
This is a structural market-truth change.

⸻

Trigger 5 — Major-Tech Rubric Changed
Event
MAJOR_TECH_RUBRIC_CHANGED
Enqueue
1. Eligibility & Classification Job
2. Region Score Recompute Job
3. Region Output Build Job
4. Company Output Build Job
5. Comparison Cache Build Job
6. Audit Job
Conditional routing
If only major-tech labeling changed and eligibility did not:
* do not rerun presence/hiring/entry-level unless scoring depends on the changed class outputs
Notes
This is lighter than an eligibility change.

⸻

Trigger 6 — New Company Candidate Added
Event
NEW_COMPANY_CANDIDATE_ADDED
Enqueue
1. Eligibility & Classification Job
2. Company-Region Presence Mapping Job if eligible
3. Hiring Refresh Job if present anywhere
4. Entry-Level Refresh Job
5. Region Score Recompute Job for affected regions
6. Company Output Build Job
7. Region Output Build Job for affected regions
8. Audit Job
Block conditions
If company becomes ineligible:
* stop after Classification
* do not enqueue presence/hiring downstream

⸻

Trigger 7 — Company Classification Corrected
Event
COMPANY_CLASSIFICATION_CORRECTED
Enqueue
1. Eligibility & Classification Job for company
2. Company-Region Presence Mapping Job for company
3. Hiring Refresh Job for affected pairs
4. Entry-Level Refresh Job
5. Region Score Recompute Job for affected regions
6. Company Output Build Job
7. Region Output Build Job
8. Comparison Cache Build Job
9. Audit Job
Notes
This is a company-scoped structural rebuild.

⸻

Trigger 8 — Company Presence Updated
Event
COMPANY_PRESENCE_UPDATED
Enqueue
1. Company-Region Presence Mapping Job
2. Hiring Refresh Job for newly present or removed pairs
3. Entry-Level Refresh Job
4. Region Score Recompute Job
5. Company Output Build Job
6. Region Output Build Job
7. Comparison Cache Build Job
8. Audit Job
Block conditions
If presence mapping fails:
* block downstream hiring/entry-level/score jobs for those pairs

⸻

Trigger 9 — Hiring Data Updated
Event
HIRING_DATA_UPDATED
Enqueue
1. Hiring Refresh Job
2. Entry-Level Refresh Job
3. Region Score Recompute Job
4. Region Output Build Job
5. Company Output Build Job
6. Comparison Cache Build Job
7. Audit Job
Notes
This is the main recurring dynamic trigger.
Block conditions
If Hiring Refresh fails:
* block Entry-Level Refresh
* block Region Score Recompute for affected scope

⸻

Trigger 10 — Entry-Level Signal Updated
Event
ENTRY_LEVEL_SIGNAL_UPDATED
Enqueue
1. Entry-Level Refresh Job
2. Region Score Recompute Job
3. Region Output Build Job
4. Company Output Build Job
5. Comparison Cache Build Job
6. Audit Job
Notes
No need to rerun Hiring Refresh unless upstream hiring data changed.

⸻

Trigger 11 — Normalization Inputs Updated
Event
NORMALIZATION_INPUTS_UPDATED
Enqueue
1. Region Score Recompute Job
2. Region Output Build Job
3. Comparison Cache Build Job
4. Audit Job
Notes
No need to rerun company truth or hiring layers.

⸻

Trigger 12 — Region Page Requested
Event
REGION_VIEW_REQUESTED
Cached path
1. load Region Output Object from cache
2. load freshness metadata
3. render page
4. optionally apply Personal Overlay Query live
Fallback path
If region output missing or stale beyond threshold:
1. enqueue Region Output Build Job
2. if region scores stale, enqueue Region Score Recompute Job first
3. serve stale object with freshness warning if available
4. replace when fresh output returns
Block conditions
If no region score exists:
* cannot build final region output
* show partial region shell + loading/error state

⸻

Trigger 13 — Company Page Requested
Event
COMPANY_VIEW_REQUESTED
Cached path
1. load Company Output Object
2. render company page
Fallback path
If company output missing/stale:
1. enqueue Company Output Build Job
2. if upstream company data stale, enqueue needed repair jobs
3. serve cached stale object if safe
Block conditions
If company classification missing:
* block company output build
* show unavailable/error state

⸻

Trigger 14 — Search/Filter Query Requested
Event
SEARCH_FILTER_QUERY_REQUESTED
Cached/live path
1. query prebuilt region/company/hiring/entry-level maps
2. apply filters live
3. sort/rank live
4. render results
Fallback path
If filtered scope depends on stale hiring/entry-level data:
1. use cached results if within freshness tolerance
2. otherwise enqueue targeted Hiring Refresh / Entry-Level Refresh
3. render with freshness notice
Notes
Should not trigger foundational jobs.

⸻

Trigger 15 — Personalized Discovery Requested
Event
PERSONALIZED_DISCOVERY_REQUESTED
Cached/live path
1. load region market scores
2. load region/company outputs
3. run Personal Overlay Query live
4. rank and return
Fallback path
If region scores stale:
1. enqueue Region Score Recompute for affected regions
2. use latest cached score if safe
3. mark freshness state
Block conditions
If user profile invalid:
* block Personal Overlay Query
* return validation error

⸻

Trigger 16 — Comparison Requested
Event
COMPARISON_REQUESTED
Cached path
1. load cached Comparison Output Object if exists and fresh
2. render comparison
3. optionally apply Personal Overlay Query live
Fallback path
If comparison cache missing/stale:
1. load Region Output Objects
2. assemble comparison live
3. optionally cache it
4. if one or more region outputs stale, enqueue Region Output Build Job or Region Score Recompute Job as needed
Block conditions
If either region output unavailable and cannot be rebuilt:
* block full comparison
* offer partial comparison or unavailable state

⸻

Trigger 17 — Contextual Challenge Requested
Event
CONTEXTUAL_CHALLENGE_REQUESTED
Cached/live path
1. load base comparison
2. if cached contextual object exists and fresh, render it
3. else run Contextual Challenge Build Job
4. render output
Block conditions
If base comparison unavailable:
* block contextual challenge generation

⸻

Trigger 18 — Audit Failure Detected
Event
AUDIT_FAILURE_DETECTED
Enqueue
Depends on failure type.
If override imbalance
1. enqueue Eligibility & Classification review job or manual review workflow
2. mark affected outputs warning-state
If presence inflation
1. enqueue Presence Mapping Job for flagged scope
2. enqueue downstream score/output rebuilds
If personal/objective contamination
1. block Personal Overlay outputs from being merged into core score
2. enqueue Region Score Recompute or output repair
If double-counting detected
1. enqueue Region Score Recompute with corrected rules
2. invalidate affected comparisons
Notes
Audit failures are control events, not just reports.

⸻

Trigger 19 — Repeated Job Failure
Event
JOB_FAILURE_THRESHOLD_REACHED
Enqueue
1. Audit Job
2. mark dependent outputs stale or degraded
3. optionally enqueue manual review workflow
4. suppress repeated downstream retries until fixed
Block conditions
If critical upstream object cannot be built:
* block dependent jobs rather than thrashing retries

⸻

4. Cached Path vs Fallback Path Rules
This is one of the most important control surfaces.
Rule 1 — Use cache first for all user-facing reads
For:
* region pages
* company pages
* comparisons
* personalized discovery
Always try:
1. fresh cache
2. stale-but-acceptable cache
3. rebuild/recompute fallback
Rule 2 — Never run heavy foundational jobs synchronously for a user request
Do not run live:
* Company Universe Intake
* global Eligibility & Classification
* global Presence Mapping
These belong to background/admin/batch workflows.
Rule 3 — Only allow live recompute for lightweight adaptive layers
Allowed live or near-live:
* Personal Overlay Query
* comparison assembly
* contextual challenge build
* filtered search ranking
Rule 4 — Use stale-with-warning before hard failure when safe
If latest trusted object is slightly stale:
* serve it
* show last updated time / freshness state
* enqueue refresh in background
This is much better UX than blank failure.

⸻

5. Dependency Blocking Rules
If Geography Build fails
Block:
* Presence Mapping
* Region Output Build
* Comparison Cache Buildfor affected regions
If Eligibility & Classification fails
Block:
* Presence Mapping
* Company Output Build
* Region Score Recomputefor affected companies/scope
If Presence Mapping fails
Block:
* Hiring Refresh
* Entry-Level Refresh
* Region Score Recomputefor affected company-region pairs
If Hiring Refresh fails
Block:
* Entry-Level Refresh
* Region Score Recomputefor affected company-region pairs/regions unless safe cached data exists
If Entry-Level Refresh fails
Allow:
* Region Score Recompute only if rules permit downgraded-confidence scoreOtherwise block objective opportunity recompute for affected regions
If Region Score Recompute fails
Block:
* Region Output Build
* Comparison Cache Build
* Personalized market rankingfor affected regions
If Region Output Build fails
Block:
* cached comparison rebuild for affected regionsAllow:
* direct raw-data fallback only in internal/admin mode, not normal user mode
If Company Output Build fails
Block:
* company page rebuildAllow:
* minimal raw company fallback if classification/presence data exists

⸻

6. Event Priority Rules
Urgent priority
* user query blocking missing object
* job failure threshold reached
* critical audit failure
* active region data corruption
High priority
* hiring refresh for active regions
* entry-level refresh for active regions
* region score recompute after dynamic changes
* personalized user query jobs
Normal priority
* scheduled comparison cache builds
* company output rebuilds
* routine region output rebuilds
* contextual challenge builds
Low priority
* optional precomputes
* long-tail comparison cache builds
* broad candidate intake expansions
* non-critical audits

⸻

7. Trigger Chaining Rules
Each job response can recommend downstream jobs, but orchestration should enforce chain rules.
Valid chain example
HIRING_DATA_UPDATED→ Hiring Refresh→ Entry-Level Refresh→ Region Score Recompute→ Region Output Build→ Comparison Cache Build→ Audit
Invalid chain example
HIRING_DATA_UPDATED→ global Eligibility & Classification
That would be overreach.
Rule
Dynamic triggers should stay in the dynamic layers unless a real structural inconsistency is discovered.

⸻

8. Trigger Suppression Rules
Prevent unnecessary work.
Suppress downstream jobs when
* upstream job returns NO_MEANINGFUL_CHANGE
* changed scope does not affect dependent objects
* stale cache is still within allowed freshness window and no user-visible impact exists
Example
If Hiring Refresh returns unchanged for all pairs:
* suppress Entry-Level Refresh unless entry-level-specific trigger exists
* suppress Region Score Recompute
* suppress output rebuilds
This is important for cost control.

⸻

9. Repair Escalation Rules
When automatic workflows are not enough.
Escalate to manual/admin review when
* override imbalance persists across audits
* repeated classification conflicts occur
* presence evidence is persistently contradictory
* downstream jobs keep failing from the same upstream defect
* critical region outputs cannot be built after retry policy exhausted
Admin review outputs
* approve override
* reject override
* force reclassification
* mark region/company low confidence
* queue targeted rebuild

⸻

10. Minimal Event Payload Schema
Useful for engineering event bus design.
{
  "event_id": "string",
  "event_type": "string",
  "emitted_at": "ISO-8601 timestamp",
  "source": "system | scheduler | admin | user:<id> | audit_engine",
  "scope": {},
  "payload": {},
  "priority": "low | normal | high | urgent",
  "correlation_id": "string"
}
Example:
{
  "event_id": "evt_001",
  "event_type": "HIRING_DATA_UPDATED",
  "emitted_at": "2026-05-06T16:15:00Z",
  "source": "scheduler",
  "scope": {
    "region_ids": ["greater_boston"],
    "company_region_pairs": [
      {"company_id": "comp_101", "region_id": "greater_boston"}
    ]
  },
  "payload": {
    "hiring_map_version_old": "hiring_v70",
    "hiring_map_version_new": "hiring_v71"
  },
  "priority": "high",
  "correlation_id": "refresh_batch_2026_05_06_a"
}

⸻