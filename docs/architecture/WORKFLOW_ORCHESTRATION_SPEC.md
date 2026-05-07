Workflow Orchestration Spec

How the App Actually Runs End-to-End

This defines:

* what runs on full build
* what runs on partial refresh
* what runs on user query
* stage dependencies
* cache/update behavior
* what should be precomputed vs computed live

This is the operating system for the product.

⸻

1. Orchestration Purpose

The app needs to do three things reliably:

1. build market intelligence data
2. refresh changing data without rebuilding everything
3. serve user requests fast enough to feel like a product, not a research script

So the orchestration layer should separate:

* slow foundational workflows
* medium-frequency refresh workflows
* fast user-facing query workflows

That is the main principle.

⸻

2. System Run Types

The app should support five run types.

Run Type A — Full Build

Used when:

* bootstrapping the product
* adding many new regions
* changing the core company-universe logic
* changing major-tech classification rules
* changing scoring logic significantly

This is the heaviest workflow.

Run Type B — Region Expansion Build

Used when:

* adding one new city / metro / labor region
* adding one new state view
* expanding from existing region set to new geography coverage

This is lighter than full build.

Run Type C — Market Refresh

Used when:

* updating hiring activity
* updating entry-level opportunities
* updating seasonal openings
* updating region market scores

This should happen frequently.

Run Type D — Company Refresh

Used when:

* one company changes hiring behavior
* one company expands or shrinks regional presence
* one company page needs repair or re-evaluation

This is narrower and targeted.

Run Type E — User Query Execution

Used when:

* a user opens a region
* runs a search
* applies filters
* asks for personalized ranking
* runs a comparison

This should be fast and mostly use precomputed data.

⸻

3. Stage Dependency Graph

Not every stage needs to re-run every time.

Here is the dependency structure.

Foundational stages

These are the most expensive and stable:

1. Geography Definition
2. Company Universe Intake
3. Eligibility and Classification
4. Company-Region Presence Mapping

Dynamic market stages

These change more often:

5. Hiring Activity Mapping
6. Entry-Level Opportunity Mapping
7. Objective Market Scoring

User-facing adaptive stages

These can often run on demand:

8. Personal Preference Overlay
9. Region Output Assembly
10. Company Output Assembly
11. Comparison Output Assembly
12. Contextual Challenge Output

Audit/control stage

Runs after important updates:

13. Refresh and Audit Logic

⸻

4. Full Build Orchestration

Purpose

Create or rebuild the whole system from scratch.

Trigger conditions

Use Full Build when:

* initial product build
* major change to eligibility rules
* major change to classification logic
* major change to presence logic
* major change to core scoring architecture
* large geography expansion

Full Build sequence

Step 1

Run Geography Definition for all supported regions.

Step 2

Run Company Universe Intake across all target sectors and all supported regions.

Step 3

Run Eligibility and Classification for all candidate companies.

Step 4

Run Company-Region Presence Mapping for all eligible companies across all supported regions.

Step 5

Run Hiring Activity Mapping for all present company-region pairs.

Step 6

Run Entry-Level Opportunity Mapping for all hiring company-region pairs.

Step 7

Run Objective Market Scoring for all regions.

Step 8

Precompute Region Output Objects.

Step 9

Precompute Company Output Objects.

Step 10

Run systemwide Audit and Consistency Check.

Full Build outputs

* region registry
* company registry
* company-region presence map
* company-region hiring map
* company-region entry-level map
* region market scores
* prebuilt region pages
* prebuilt company pages
* audit report

Full Build notes

This should be treated like a batch pipeline, not a live user flow.

⸻

5. Region Expansion Build Orchestration

Purpose

Add one new region or a small set of new regions without rebuilding everything.

Trigger conditions

Use when:

* adding Seattle
* adding Austin
* adding DC
* adding a state-level view
* adding Greater Chicago, etc.

Region Expansion sequence

Step 1

Create new Geography Object(s).

Step 2

Reuse existing company universe where possible.

Step 3

Run Company-Region Presence Mapping only for:

* eligible companies
* newly added region(s)

Step 4

Run Hiring Activity Mapping only for present company-region pairs in new region(s).

Step 5

Run Entry-Level Opportunity Mapping for those pairs.

Step 6

Run Objective Market Scoring for the new region(s).

Step 7

Build Region Output Object(s) for the new region(s).

Step 8

Update relevant Company Output Objects for companies now linked to the new region(s).

Step 9

Run local Audit and Consistency Check for the newly added region set.

Region Expansion notes

This avoids rerunning global eligibility unless the universe logic changed.

⸻

6. Market Refresh Orchestration

Purpose

Update changing labor-market signals without redoing stable company-universe work.

Trigger conditions

Use when:

* current postings changed
* 30/90-day counts need updating
* seasonal student window changed
* early-career availability changed
* region opportunity scores need refreshing

Refresh frequency logic

High-frequency refresh

* active postings now
* current hiring flags
* job count changes

Medium-frequency refresh

* 30-day and 90-day windows
* student-season recurrence signals
* hiring program counts

Lower-frequency refresh

* annualized trend signals
* major company-presence changes
* company-region operational changes

Market Refresh sequence

Step 1

Select affected region(s) and/or company-region pairs.

Step 2

Refresh Hiring Activity Mapping for those pairs.

Step 3

Refresh Entry-Level Opportunity Mapping for those pairs.

Step 4

Recompute Objective Market Scoring only for impacted regions.

Step 5

Rebuild impacted Region Output Objects.

Step 6

Rebuild impacted Company Output Objects.

Step 7

Invalidate and update cached comparison outputs involving affected regions.

Step 8

Run targeted Audit checks.

Market Refresh notes

This should be the most common background workflow after launch.

⸻

7. Company Refresh Orchestration

Purpose

Refresh one company or a small set of companies without touching everything else.

Trigger conditions

Use when:

* a company expands to a new city
* a company closes offices
* a company’s hiring spikes or disappears
* a company’s classification is corrected
* a company page needs repair

Company Refresh sequence

Case A — hiring-only change

If only hiring changed:

1. refresh company-region hiring records
2. refresh entry-level records
3. update impacted region scores
4. rebuild impacted company page
5. rebuild affected region outputs
6. invalidate affected comparisons

Case B — presence change

If presence changed:

1. refresh company-region presence map for that company
2. refresh hiring for newly present/removed pairs
3. refresh entry-level for affected pairs
4. update region scores
5. rebuild company page
6. rebuild affected region outputs
7. invalidate affected comparisons

Case C — classification change

If eligibility or major-tech label changed:

1. rerun company eligibility/classification
2. rerun all company-region presence links for that company
3. rerun hiring and entry-level for affected pairs
4. update all affected region scores
5. rebuild company page
6. rebuild affected region outputs
7. run stronger audit checks

Company Refresh notes

Classification changes are much more expensive than hiring changes.

⸻

8. User Query Orchestration

Purpose

Serve interactive app behavior quickly.

Rule

User queries should rely primarily on:

* precomputed truth objects
* cached region outputs
* cached company outputs
* lightweight live overlay logic

They should not trigger heavy foundational research unless absolutely necessary.

User query types

Query Type 1 — Region view

Example:

* show Greater Boston

Sequence:

1. load Region Output Object
2. apply current UI filters
3. apply optional user preference overlay
4. render map/dashboard/panels

Query Type 2 — Company view

Example:

* show Datadog across regions

Sequence:

1. load Company Output Object
2. apply filter mode
3. render company geography and hiring footprint

Query Type 3 — Search/filter query

Example:

* show AI companies hiring entry-level in Boston

Sequence:

1. query prebuilt company-region hiring map
2. query entry-level map
3. filter by sector/role/region
4. optionally rank with objective score
5. optionally personalize

Query Type 4 — Comparison query

Example:

* compare Greater Boston vs Greater SF

Sequence:

1. load both Region Output Objects
2. generate Comparison Output Assembly
3. optionally load Personal Preference Overlay
4. optionally load Contextual Challenge Output

Query Type 5 — Personalized market discovery

Example:

* best cities for PM + AI + early-career

Sequence:

1. query region market scores
2. apply user preference overlay
3. rank regions
4. load top region/company targets
5. render discovery output

⸻

9. Precompute vs Live Compute Rules

This is one of the most important orchestration decisions.

Must be precomputed

These are too expensive or too foundational to compute live every time:

* company universe
* eligibility
* major-tech classification
* Mag 7 tagging
* company-region presence map
* baseline region market scores
* company output objects
* region output objects

Should usually be precomputed and refreshed on schedule

* active hiring counts
* 30-day/90-day posting counts
* entry-level access scores
* objective opportunity scores

Can be computed live or near-live

* user filters
* personalized overlays
* comparison assembly
* contextual challenge narrative
* sort/rank views

Rule of thumb

Anything that defines market truth should be precomputed.
Anything that adapts truth to a user can be live.

⸻

10. Cache Strategy

Cache layers

Cache Layer 1 — Foundational truth cache

Stores:

* company registry
* classifications
* company-region presence
* base region identities

This should be long-lived.

Cache Layer 2 — Market activity cache

Stores:

* hiring maps
* entry-level maps
* region market scores

This should refresh regularly.

Cache Layer 3 — Output object cache

Stores:

* region output objects
* company output objects
* common comparison outputs

This supports fast UX.

Cache Layer 4 — Session/user cache

Stores:

* user preference overlays
* recent filters
* recent comparisons
* recent discovery views

This supports responsiveness.

⸻

11. Invalidation Rules

When one thing changes, not everything should be thrown away.

If hiring changes

Invalidate:

* affected company-region hiring records
* affected entry-level records
* affected region scores
* affected company output objects
* affected region output objects
* affected comparisons involving that region

Do not invalidate:

* company eligibility
* major-tech classification globally

If presence changes

Invalidate:

* affected company-region presence records
* downstream hiring/entry-level records for those pairs
* region outputs using those pairs
* company page
* comparisons involving impacted regions

If company classification changes

Invalidate:

* company classification record
* all company-region presence records for that company
* downstream hiring/entry-level records
* all region scores influenced by that company
* company page
* all relevant comparisons

If user preferences change

Invalidate:

* only user/session-level personalized outputs

Do not invalidate:

* market truth cache

That separation is critical.

⸻

12. Orchestration by Product Surface

Interactive Map

Depends on:

* geography definitions
* region output objects
* market scores
* optional personalized overlay

Usually should not trigger heavy recomputation.

Region Page

Depends on:

* region output object
* fresh enough market activity cache
* optional personalization

Company Page

Depends on:

* company output object
* recent hiring state
* entry-level layer

Comparison View

Depends on:

* cached region outputs
* lightweight comparison assembly
* optional contextual challenge build

Personalized Discovery View

Depends on:

* region market scores
* company-region opportunity data
* live preference overlay

⸻

13. Scheduled Orchestration Cadence

You asked earlier about multiple time windows. This needs cadence logic.

Frequent cadence

Refresh:

* currently hiring flags
* active posting counts
* new entry-level counts

Use for app freshness.

Moderate cadence

Refresh:

* 30-day and 90-day windows
* objective region scores
* common comparisons

Slower cadence

Refresh:

* annualized trend signals
* company-region operational presence
* region structural summaries

Rare cadence

Refresh:

* eligibility rules
* major-tech rubric
* entire company universe

These should change only when the product logic changes, not routinely.

⸻

14. Workflow Priorities by Cost

Most expensive

* Full Build
* global eligibility reclassification
* global presence remapping

Medium cost

* region expansion
* market refresh for many regions
* large comparison recompute batches

Lowest cost

* user filters
* personalization
* comparison rendering
* contextual narrative generation

This matters because the app should feel instant even though the underlying research is not.

⸻

15. Failure Handling / Fallback Behavior

The app needs rules for stale or incomplete data.

If hiring data is stale

Show:

* last refreshed timestamp
* use cached market truth
* mark freshness status visibly

If entry-level data is incomplete

Show:

* reduced-confidence entry-level score
* do not pretend absence equals zero unless confirmed

If company-region presence is uncertain

Show:

* uncertain presence status
* do not fully count it as strong presence in score-driving layers

If comparison data is uneven

Show:

* confidence note
* preserve main comparison but surface limitations

This matters a lot for trust.

⸻

16. Suggested Orchestration Jobs

The system likely needs distinct job types.

Job Type 1 — Region Build Job

Builds one region from presence through scoring.

Job Type 2 — Company Universe Job

Builds or refreshes the company universe and classification layer.

Job Type 3 — Hiring Refresh Job

Refreshes company-region hiring records.

Job Type 4 — Entry-Level Refresh Job

Refreshes early-career layer.

Job Type 5 — Region Score Recompute Job

Recomputes market scores for impacted regions.

Job Type 6 — Output Object Rebuild Job

Rebuilds region/company outputs.

Job Type 7 — Comparison Cache Job

Precomputes common comparisons.

Job Type 8 — Audit Job

Checks for drift, inconsistency, double-counting, and contamination.

⸻

17. Recommended Run Order by Scenario

Scenario A — First-time app build

Run:

1. Geography Definition
2. Company Universe Intake
3. Eligibility and Classification
4. Company-Region Presence Mapping
5. Hiring Activity Mapping
6. Entry-Level Opportunity Mapping
7. Objective Market Scoring
8. Region Output Assembly
9. Company Output Assembly
10. Audit

Scenario B — Add one new city/metro

Run:

1. Geography Definition for new region
2. Presence Mapping for eligible companies into new region
3. Hiring Mapping for present pairs
4. Entry-Level Mapping
5. Region Scoring
6. Region Output Assembly
7. Company Output updates
8. Audit

Scenario C — Weekly/regular refresh

Run:

1. Hiring Refresh
2. Entry-Level Refresh
3. Region Score Recompute
4. Region Output rebuild
5. Company Output rebuild
6. Comparison cache invalidation/rebuild
7. Audit

Scenario D — User compares Boston vs SF

Run:

1. Load region outputs
2. Apply filters
3. Assemble comparison
4. Apply personal overlay if needed
5. Generate contextual challenge if requested

⸻

18. The Core Orchestration Principle

The system should be designed around this rule:

Build slowly, refresh selectively, serve quickly.

That is the essence of the app workflow.

* foundational truth should be expensive but stable
* market activity should be refreshable
* user experiences should be fast and mostly assembled from prepared objects

⸻
