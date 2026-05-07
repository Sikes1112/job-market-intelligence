Job Orchestration Matrix

Trigger, Inputs, Outputs, Dependencies, Invalidation Scope, and Cadence
This turns the workflow into an engineering-facing operations table.

⸻

1. Matrix Purpose
This matrix defines, for each job:
* what triggers it
* what it needs
* what it produces
* what it depends on
* what must be invalidated downstream
* how often it should run
* how heavy it is
This is the practical control layer for the app.

⸻

2. Job Inventory
Core jobs:
1. Geography Build Job
2. Company Universe Intake Job
3. Eligibility & Classification Job
4. Company-Region Presence Mapping Job
5. Hiring Refresh Job
6. Entry-Level Refresh Job
7. Region Score Recompute Job
8. Region Output Build Job
9. Company Output Build Job
10. Comparison Cache Build Job
11. Personal Overlay Query Job
12. Contextual Challenge Build Job
13. Audit Job

⸻

3. Full Matrix
Job 1 — Geography Build Job
Purpose
Create or update geography objects used everywhere else.
Trigger
* initial system build
* add new city/metro/state/custom region
* update region definitions
* expand labor-region grouping
Inputs
* geography definitions
* region hierarchy rules
* normalization profile inputs
Outputs
* geography_object
* updated region registry
Dependencies
* none
Downstream dependencies
* Company-Region Presence Mapping Job
* Region Output Build Job
* Comparison Cache Build Job
Invalidation scope
If a geography changes:
* invalidate affected region outputs
* invalidate affected comparisons
* invalidate affected normalization outputs
* possibly re-run presence mapping for affected region(s)
Cadence
* rare
* on expansion or geography-rule change
Cost
* low to medium

⸻

Job 2 — Company Universe Intake Job
Purpose
Build the broad candidate company pool.
Trigger
* initial build
* sector-scope update
* source expansion
* company-universe refresh
* admin request to expand company coverage
Inputs
* sector inclusion rules
* source lists
* existing company registry
* geography coverage targets
Outputs
* candidate_company_pool
Dependencies
* geography registry helpful but not always required
Downstream dependencies
* Eligibility & Classification Job
Invalidation scope
If intake logic changes:
* invalidate candidate pool
* rerun eligibility/classification
* possibly cascade into full rebuild of company-dependent layers
Cadence
* rare to occasional
* batch-oriented
Cost
* medium

⸻

Job 3 — Eligibility & Classification Job
Purpose
Convert candidate pool into accepted company universe and labels.
Trigger
* new candidate companies added
* eligibility rule change
* major-tech rubric update
* manual correction request
* override review
Inputs
* candidate_company_pool
* eligibility rules
* major-tech rubric
* Mag 7 list
* override policy
Outputs
* classified_company_universe
Dependencies
* Company Universe Intake Job
Downstream dependencies
* Company-Region Presence Mapping Job
* Company Output Build Job
* Region Score Recompute Job
* Audit Job
Invalidation scope
If eligibility or classification changes for a company:
* invalidate all company-region presence records for that company
* invalidate hiring and entry-level records for affected company-region pairs
* invalidate affected region scores
* invalidate company page
* invalidate comparisons touching affected regions
If global classification rules change:
* likely require large rebuild
Cadence
* rare
* event-driven
Cost
* medium to high

⸻

Job 4 — Company-Region Presence Mapping Job
Purpose
Determine where each classified company has meaningful regional presence.
Trigger
* full build
* region expansion
* company classification change
* geography definition change
* company presence update
* office/operations evidence update
Inputs
* classified_company_universe
* region registry
* presence rules
* office/operations/hiring evidence
Outputs
* company_region_presence_map
Dependencies
* Geography Build Job
* Eligibility & Classification Job
Downstream dependencies
* Hiring Refresh Job
* Region Output Build Job
* Company Output Build Job
* Region Score Recompute Job
Invalidation scope
If a presence record changes:
* invalidate downstream hiring and entry-level for that company-region pair
* invalidate affected region score(s)
* invalidate affected company output
* invalidate affected region output
* invalidate comparisons involving affected region(s)
Cadence
* occasional
* event-driven
* slower than hiring refresh
Cost
* medium to high

⸻

Job 5 — Hiring Refresh Job
Purpose
Refresh active hiring signals for present company-region pairs.
Trigger
* scheduled refresh
* region-specific refresh
* company-specific refresh
* user-triggered refresh
* detected job activity change
Inputs
* company_region_presence_map
* hiring source data
* time-window rules
Outputs
* company_region_hiring_map
Dependencies
* Company-Region Presence Mapping Job
Downstream dependencies
* Entry-Level Refresh Job
* Region Score Recompute Job
* Region Output Build Job
* Company Output Build Job
* Comparison Cache Build Job
* Audit Job
Invalidation scope
If hiring changes:
* invalidate entry-level records for affected company-region pairs
* invalidate region scores for affected regions
* invalidate region outputs for affected regions
* invalidate company outputs for affected companies
* invalidate cached comparisons involving affected regions
Cadence
* frequent
Cost
* medium

⸻

Job 6 — Entry-Level Refresh Job
Purpose
Refresh early-career opportunity signals.
Trigger
* after Hiring Refresh Job
* scheduled early-career refresh
* seasonal hiring window change
* company-specific refresh
* region-specific refresh
Inputs
* company_region_hiring_map
* early-career extraction logic
Outputs
* company_region_entry_level_map
Dependencies
* Hiring Refresh Job
Downstream dependencies
* Region Score Recompute Job
* Region Output Build Job
* Company Output Build Job
* Comparison Cache Build Job
* Audit Job
Invalidation scope
If entry-level records change:
* invalidate region scores for affected regions
* invalidate region outputs
* invalidate company outputs
* invalidate comparisons involving affected regions
Cadence
* frequent to moderate
Cost
* medium

⸻

Job 7 — Region Score Recompute Job
Purpose
Recompute structural, live-market, and objective-opportunity scores for impacted regions.
Trigger
* hiring refresh
* entry-level refresh
* presence change
* company classification change
* normalization input update
Inputs
* classified_company_universe
* company_region_presence_map
* company_region_hiring_map
* company_region_entry_level_map
* normalization inputs
Outputs
* region_market_scores
* updated normalized region scores
Dependencies
* Eligibility & Classification Job
* Company-Region Presence Mapping Job
* Hiring Refresh Job
* Entry-Level Refresh Job
Downstream dependencies
* Region Output Build Job
* Comparison Cache Build Job
* Personalized query ranking
* Contextual Challenge Build Job
Invalidation scope
If region score changes:
* invalidate region output
* invalidate cached comparisons using region
* invalidate discovery rankings using region
* do not invalidate foundational company truth
Cadence
* moderate to frequent
* after dynamic data changes
Cost
* medium

⸻

Job 8 — Region Output Build Job
Purpose
Assemble app-facing region objects.
Trigger
* region score recompute
* region expansion
* region page rebuild
* refresh of affected region
Inputs
* region_market_scores
* company_region_presence_map
* company_region_hiring_map
* company_region_entry_level_map
* region metadata
Outputs
* region_output_object
Dependencies
* Region Score Recompute Job
* Geography Build Job
Downstream dependencies
* region page
* interactive map panel
* comparison assembly
* personalized discovery views
Invalidation scope
If rebuilt:
* replace cached region object
* invalidate comparisons using stale region output
* invalidate discovery views tied to stale region object
Cadence
* moderate to frequent
* after score or major region data changes
Cost
* low to medium

⸻

Job 9 — Company Output Build Job
Purpose
Assemble app-facing company objects.
Trigger
* company classification change
* company presence change
* company hiring change
* entry-level change
* company page rebuild
Inputs
* classified_company_universe
* company_region_presence_map
* company_region_hiring_map
* company_region_entry_level_map
Outputs
* company_output_object
Dependencies
* Eligibility & Classification Job
* Company-Region Presence Mapping Job
* Hiring Refresh Job
* Entry-Level Refresh Job
Downstream dependencies
* company page
* company geography view
* region-company lists
Invalidation scope
If rebuilt:
* replace cached company object
* invalidate region views that rely on company summaries if needed
* invalidate comparison fragments if company-level top lists changed meaningfully
Cadence
* moderate
* event-driven
Cost
* low to medium

⸻

Job 10 — Comparison Cache Build Job
Purpose
Precompute common comparison objects so comparisons load quickly.
Trigger
* region output change
* scheduled precompute for popular comparisons
* admin-selected comparison pairs
* new region addition
Inputs
* region_output_object
* normalized scores
* comparison templates
Outputs
* cached comparison_output_object
Dependencies
* Region Output Build Job
* Region Score Recompute Job
Downstream dependencies
* comparison page
* compare widget
* popular comparison suggestions
Invalidation scope
If one region in a cached comparison changes:
* invalidate only comparisons containing that region
* leave unrelated comparisons intact
Cadence
* moderate
* after region rebuilds
* also scheduled for popular pairs
Cost
* low to medium

⸻

Job 11 — Personal Overlay Query Job
Purpose
Apply user-specific preferences live or near-live.
Trigger
* user updates filters/preferences
* user runs personalized search
* user opens personalized comparison
* user changes role/industry selection
Inputs
* user preference profile
* region_market_scores
* company_region_hiring_map
* company_region_entry_level_map
* company_output_object
* region_output_object
Outputs
* personalized_market_scores
* personalized_company_target_scores
* personalized rankings/rendered results
Dependencies
* Region Score Recompute Job
* Region Output Build Job
* Company Output Build Job
Downstream dependencies
* personalized discovery page
* personalized comparison page
* recommended targets
Invalidation scope
If preferences change:
* invalidate only user/session-level outputs
* do not invalidate market truth or caches
Cadence
* live/on demand
Cost
* low

⸻

Job 12 — Contextual Challenge Build Job
Purpose
Generate the secondary challenge output for comparisons.
Trigger
* user requests advanced comparison
* popular comparison cache build
* region score change affecting cached advanced comparisons
Inputs
* comparison_output_object
* broader contextual logic
* secondary geography interpretation rules
Outputs
* contextual_challenge_object
Dependencies
* Comparison Cache Build Job or live comparison assembly
Downstream dependencies
* advanced comparison UI
* expert mode analysis
Invalidation scope
If base comparison changes:
* invalidate contextual challenge built from that comparison
Cadence
* on demand or cached for popular comparisons
Cost
* low

⸻

Job 13 — Audit Job
Purpose
Check integrity of the system after meaningful updates.
Trigger
* full build complete
* region expansion complete
* major classification change
* large hiring refresh batch
* scheduled integrity run
* admin review
Inputs
* all relevant workflow outputs
* prior audit baselines
* integrity rules
Outputs
* audit_report
Dependencies
* can run after any major pipeline stage
* most useful after rebuilds/refreshes
Downstream dependencies
* admin dashboard
* integrity warnings
* rebuild decisions
* trust/confidence indicators
Invalidation scope
Does not invalidate user outputs by itself unless critical failure detected.
If critical issues found:
* mark affected objects stale or low-confidence
* optionally queue repair jobs
Cadence
* after major jobs
* scheduled periodic integrity checks
Cost
* low to medium

⸻

4. Condensed Matrix View
Job	Main Trigger	Main Inputs	Main Outputs	Depends On	Invalidates	Cadence
Geography Build	new/changed region	region defs	geography objects	none	affected region outputs/comparisons	rare
Company Universe Intake	source/scope expansion	sector rules, sources	candidate pool	none	downstream eligibility if changed	occasional
Eligibility & Classification	rule/company update	candidate pool, rules	classified universe	intake	company-region and downstream for affected companies	rare
Presence Mapping	region/company presence update	classified universe, geography	presence map	geography, classification	hiring, entry-level, region outputs, comparisons	occasional
Hiring Refresh	scheduled/company/region refresh	presence map, hiring data	hiring map	presence	entry-level, region scores, outputs, comparisons	frequent
Entry-Level Refresh	after hiring refresh	hiring map	entry-level map	hiring	region scores, outputs, comparisons	frequent/moderate
Region Score Recompute	dynamic data changed	classified + presence + hiring + entry-level	region scores	classification, presence, hiring, entry-level	region outputs, comparisons, rankings	moderate/frequent
Region Output Build	region data changed	scores + maps	region output object	region scores	comparisons, discovery views	moderate/frequent
Company Output Build	company data changed	company + maps	company output object	classification/presence/hiring/entry	company views, some region fragments	moderate
Comparison Cache Build	region output changed	region outputs	comparison cache	region output	only affected comparisons	moderate
Personal Overlay Query	user filter change	user prefs + cached truth	personalized outputs	region/company outputs	user-session only	live
Contextual Challenge Build	advanced compare request	comparison output	challenge object	comparison	challenge only	on demand
Audit	major update/schedule	all outputs	audit report	post-job	none unless failures	periodic

⸻

5. Trigger Classes
Class 1 — Foundational triggers
These usually require deeper rebuilds:
* new region definition
* eligibility rule change
* major-tech rubric update
* geography logic change
Affected jobs:
* Geography Build
* Eligibility & Classification
* Presence Mapping
* downstream rebuilds
Class 2 — Market activity triggers
These are the normal operating triggers:
* new hiring data
* job counts changed
* seasonal shifts
* new early-career postings
Affected jobs:
* Hiring Refresh
* Entry-Level Refresh
* Region Score Recompute
* output rebuilds
Class 3 — Object-specific triggers
These affect only one company or region:
* company office update
* company hiring spike
* region-specific refresh request
Affected jobs:
* limited presence/hiring/entry-level/score/output jobs
Class 4 — User-interaction triggers
These should stay light:
* filter change
* compare request
* personalized ranking request
Affected jobs:
* Personal Overlay Query
* Comparison assembly
* Contextual Challenge build

⸻

6. Invalidation Tiers
Tier 1 — Session-only invalidation
Used for:
* changed filters
* changed role selection
* changed industry selection
* changed preference profile
Invalidate:
* personalized results only
Tier 2 — Output-object invalidation
Used for:
* region score change
* company hiring change
* entry-level change
Invalidate:
* region outputs
* company outputs
* affected comparisons
Tier 3 — Market-truth invalidation
Used for:
* company classification change
* presence mapping correction
* geography logic change
Invalidate:
* foundational downstream objects
* scores
* outputs
* affected comparisons
Tier 4 — Structural rebuild invalidation
Used for:
* core eligibility logic change
* sector-scope change
* large geography redesign
Invalidate:
* major portions of pipeline
* likely triggers full build or large partial rebuild

⸻

7. Cadence Guidance
Daily / near-daily
* Hiring Refresh
* Entry-Level Refresh for active regions/companies
* Region Score Recompute for impacted regions
* rebuild affected outputs
Weekly
* broader market refresh batch
* popular comparison cache rebuild
* scheduled audit run
Monthly / occasional
* presence review
* company-universe intake expansion
* manual override review
* normalization input refresh
Rare
* eligibility rule changes
* major-tech rubric changes
* geography model changes
* full build

⸻

8. Engineering Priority Guidance
If building in phases, prioritize these jobs first:
Phase 1 jobs
* Geography Build
* Eligibility & Classification
* Presence Mapping
* Hiring Refresh
* Entry-Level Refresh
* Region Score Recompute
* Region Output Build
* Personal Overlay Query
That gets you a working MVP.
Phase 2 jobs
* Company Output Build
* Comparison Cache Build
* Contextual Challenge Build
Phase 3 jobs
* richer Audit system
* smarter trigger automation
* broader precompute strategy

⸻