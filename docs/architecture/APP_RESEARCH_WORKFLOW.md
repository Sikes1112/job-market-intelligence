App Research Workflow

Formal Operating Workflow for the Product

0. Workflow Purpose
This workflow governs how the app:
1. builds the company universe
2. maps companies to regions
3. evaluates hiring activity
4. extracts entry-level opportunity
5. scores objective opportunity by market
6. applies user-specific preference filters
7. produces discovery, map, region, company, and comparison outputs
This is the core operating logic of the app.

⸻

1. Workflow Modes
The app should support three workflow modes.
Mode A — Market Population Workflow
Used to initially build or expand the database.
Example:
* add Greater Boston
* add Bay Area
* add Seattle
* add Austin
Mode B — Market Refresh Workflow
Used to update existing market data.
Example:
* refresh which firms are hiring in Boston this week
* refresh entry-level roles in Bay Area
* refresh current postings for selected companies
Mode C — User Query Workflow
Used when a user interacts with the product.
Example:
* show best PM markets
* show AI companies hiring entry-level in Boston
* compare Greater Boston vs Greater SF
* show where Datadog is hiring across cities
These modes use the same core logic, but at different scopes.

⸻

2. Core Workflow Stages
The app workflow should be formalized into these stages:
1. Geography Definition
2. Company Universe Intake
3. Eligibility and Classification
4. Company-Region Presence Mapping
5. Hiring Activity Mapping
6. Entry-Level Opportunity Mapping
7. Objective Market Scoring
8. Personal Preference Overlay
9. Region/Company Output Assembly
10. Comparison Output Assembly
11. Refresh/Audit Logic

⸻

3. Stage 1 — Geography Definition
Purpose
Define the geographic unit the system is analyzing.
Inputs
Possible inputs:
* city
* metro
* greater region
* state
* custom grouped labor region
Output
geography_object
Required fields
* region_id
* region_name
* region_type
    * city
    * metro
    * greater_region
    * state
    * custom_region
* parent_region_id
* labor_market_group
* display_name
* normalization_profile_id
Operational role in app
This stage allows the app to support:
* Boston
* Greater Boston
* Cambridge
* SF
* Greater SF
* Silicon Valley
* Bay Area
* state-level views
* custom grouped regions later
Workflow note
This stage happens first because every downstream result is region-bound.

⸻

4. Stage 2 — Company Universe Intake
Purpose
Build the broad candidate company pool for the selected geography set or app-wide database.
Inputs
* geography_object
* sector scope rules
* existing company database
* candidate company sources
Process
Collect all plausibly relevant companies in-scope for the product.
This stage is broad and intentionally permissive.
Output
candidate_company_pool
Required fields
* company_name
* source_reference
* sector_guess
* candidate_region_links
* initial_candidate_notes
Operational role in app
This is how the app populates:
* companies visible on region pages
* companies appearing on maps
* company-region relationships later
Rule
Do not over-filter here.This stage is for intake, not final acceptance.

⸻

5. Stage 3 — Eligibility and Classification
Purpose
Turn the candidate pool into the app’s accepted company universe.
Inputs
* candidate_company_pool
Sub-stages
This stage has two internal outputs:
1. eligibility decision
2. company classification labels
5A — Eligibility
Determine whether the firm belongs in the app universe.
Possible outcomes:
* eligible
* ineligible
* override_included
5B — Classification
Assign labels such as:
* eligible tech company
* major tech
* Mag 7
* future premium tags if needed
Output
classified_company_universe
Required fields
* company_id
* company_name
* eligibility_status
* eligibility_score
* eligibility_override_flag
* eligibility_override_reason
* classification_confidence
* sector_primary
* sector_secondary
* is_major_tech
* major_tech_score
* is_mag7
Operational role in app
This stage controls:
* which companies the app shows at all
* how they are tagged
* which comparison filters are possible
* prestige-lens filters later
Workflow note
This is the foundational company truth layer.

⸻

6. Stage 4 — Company-Region Presence Mapping
Purpose
Determine where each accepted company meaningfully exists.
Inputs
* classified_company_universe
* geography_object set
Process
For each company-region pair, determine whether meaningful presence exists.
Presence qualifies if:
* real office + real operationsor
* real office + actual hiring tied to region
If hiring evidence exists, prefer it.If none exists, satellite office can still suffice.
Output
company_region_presence_map
Required fields
* company_id
* region_id
* presence_status
* presence_basis
* office_evidence_flag
* operations_evidence_flag
* hiring_evidence_flag
* presence_confidence
* presence_notes
Operational role in app
This stage powers:
* company dots on regions/maps
* region company lists
* “company present here” filters
* company geography pages
Workflow note
This is the backbone of the map experience.

⸻

7. Stage 5 — Hiring Activity Mapping
Purpose
Determine where regionally present companies are actively hiring.
Inputs
* company_region_presence_map
Process
For each company-region pair marked present, assess hiring activity across supported time windows.
Supported time windows
* now
* 30d
* 90d
* annualized trend
* seasonal student window
Output
company_region_hiring_map
Required fields
* company_id
* region_id
* currently_hiring_flag
* active_posting_count_now
* posting_count_30d
* posting_count_90d
* annualized_trend_signal
* seasonal_student_hiring_signal
* hiring_program_count
* hiring_confidence
* role_family_summary
Operational role in app
This stage powers:
* “hiring now” filters
* region hiring dashboards
* market heat maps
* company hiring geography pages
* comparison activity counts
Workflow note
This is where the app shifts from static company geography into live opportunity geography.

⸻

8. Stage 6 — Entry-Level Opportunity Mapping
Purpose
Extract and score early-career opportunity within company-region hiring data.
Inputs
* company_region_hiring_map
Process
For each company-region pair, identify:
* internships
* co-ops
* entry-level full-time
* formal early-career programs
* recurrence patterns
Output
company_region_entry_level_map
Required fields
* company_id
* region_id
* internship_count
* coop_count
* entry_level_full_time_count
* formal_early_career_program_flag
* student_season_recurrence_signal
* entry_level_access_score
* entry_level_confidence
Operational role in app
This stage powers:
* early-career mode
* internship/co-op filters
* entry-level market ranking
* entry-level comparison
* early-career map overlays
Workflow note
This is one of the most important product layers.

⸻

9. Stage 7 — Objective Market Scoring
Purpose
Turn company-region opportunity data into market-relevant scores.
Inputs
* classified_company_universe
* company_region_presence_map
* company_region_hiring_map
* company_region_entry_level_map
Sub-layers
This stage should produce multiple score layers.
7A — Structural ecosystem score
Measures:
* eligible company density
* major tech density
* Mag 7 concentration
* presence footprint
7B — Live market score
Measures:
* actively hiring companies
* postings
* program counts
* time-window consistency
7C — Objective opportunity score
Measures mainly:
* entry-level access
* current hiring volume
* prestige
Output
region_market_scores
Required fields
* region_id
* structural_ecosystem_score
* live_market_score
* objective_opportunity_score
* score_notes
Operational role in app
This stage powers:
* market rankings
* region pages
* best-market discovery
* comparison engine
* “best places for X” outputs
Workflow note
This is the main engine of region-level intelligence.

⸻

10. Stage 8 — Personal Preference Overlay
Purpose
Customize outputs to the specific user.
Inputs
* region_market_scores
* company_region_entry_level_map
* company_region_hiring_map
* user preference profile
User preference inputs
* role targets
* industry preferences
* career stage
* prestige preference
* brand preference
* region preference
* relocation flexibility
Process
Apply user-specific scoring overlay.
Main components:
* role fit
* industry fit
* prestige preference
* brand appeal
Role fit and industry should weigh more than prestige and brand appeal.
Output
personalized_market_scoresandpersonalized_company_target_scores
Required fields
* user_id
* region_id
* personal_market_score
* company_id
* personal_company_score
* preference_match_notes
Operational role in app
This powers:
* personalized rankings
* “best cities for me”
* “best companies for me”
* tailored comparison results
Workflow note
This must remain an overlay, not the base market truth.

⸻

11. Stage 9 — Region Output Assembly
Purpose
Turn the research objects into app-visible region outputs.
Inputs
* region_market_scores
* company_region_presence_map
* company_region_hiring_map
* company_region_entry_level_map
* personalized_market_scores if available
Process
Assemble the region page / map panel / market summary.
Output
region_output_object
Required sections
* region summary
* top companies present
* top companies hiring
* entry-level access summary
* major-tech distribution
* Mag 7 presence
* objective opportunity indicators
* personalized fit indicators if user mode is active
Operational role in app
This powers:
* map click panels
* region pages
* state/metro dashboards

⸻

12. Stage 10 — Company Output Assembly
Purpose
Turn the research objects into company-visible outputs.
Inputs
* classified_company_universe
* company_region_presence_map
* company_region_hiring_map
* company_region_entry_level_map
Process
Assemble company geography and market footprint views.
Output
company_output_object
Required sections
* company summary
* regions present
* regions hiring
* regions with entry-level access
* role-family distribution by region
* major-tech / Mag 7 tags if relevant
Operational role in app
This powers:
* company geography pages
* “apply to same company in multiple cities” use case
* company-region job exploration

⸻

13. Stage 11 — Comparison Output Assembly
Purpose
Generate side-by-side comparison views for regions.
Inputs
* two or more region_output_objects
* optionally personalized_market_scores
Process
Compare selected regions across:
* structural ecosystem
* live market activity
* entry-level access
* objective opportunity
* personal fit if active
Output
comparison_output_object
Required sections
* region-first summary table
* category winners
* score comparisons
* explanation notes
* optional personal-fit comparison
Operational role in app
This powers:
* compare Boston vs Greater SF
* compare Seattle vs Austin
* compare Boston vs NYC for PM roles
* compare regions under user profile filters
Workflow note
Comparison is now a feature, not the product core.

⸻

14. Stage 12 — Contextual Challenge Output
Purpose
Generate the secondary output that challenges or reframes the primary comparison.
Inputs
* comparison_output_object
* broader contextual geography logic
* broader ecosystem interpretation layer
Process
Ask whether the broader practical market context materially changes the interpretation of the primary result.
Output
contextual_challenge_object
Required sections
* contextual score
* broader interpretation summary
* changed vs unchanged findings
* challenge narrative
Operational role in app
This powers:
* advanced comparison mode
* expert-mode interpretation
* “strict vs broader reality” comparison framing

⸻

15. Stage 13 — Refresh and Audit Logic
Purpose
Keep the app’s data current and logically consistent.
Inputs
All workflow outputs.
Refresh types
Full refresh
Re-run broad market population and company-region mapping.
Partial refresh
Refresh:
* hiring activity
* entry-level access
* selected companies
* selected regions
User-triggered refresh
Refresh current selected comparison or region view.
Audit checks
Check for:
* override overuse
* inconsistent company eligibility
* inconsistent major-tech classification
* weak presence inflation
* remote contamination in local score
* prestige double-counting
* personal preference contamination of objective score
Output
refresh_logandaudit_report

⸻

16. How the App Actually Runs
App bootstrapping workflow
When building the product database:
1. define regions
2. intake candidate companies
3. screen and classify them
4. map company-region presence
5. map hiring
6. map entry-level opportunities
7. build market scores
8. publish region/company outputs
User interaction workflow
When a user opens the app and selects filters:
1. identify requested region(s)
2. load region/company/output objects
3. apply preference overlay if relevant
4. generate map/dashboard view
5. generate comparison if requested
6. generate contextual challenge output if requested
Market refresh workflow
When updating data:
1. refresh hiring activity
2. refresh entry-level signals
3. re-score affected regions
4. update affected company pages
5. update comparisons that depend on changed regions

⸻

17. The App’s Real Workflow Hierarchy
The workflow is best understood in three stacked layers.
Layer 1 — Market truth layer
This is objective data construction:
* company universe
* classification
* region presence
* hiring
* entry-level access
Layer 2 — Intelligence layer
This is analysis:
* market scores
* target strength
* region outputs
* company outputs
* comparison outputs
Layer 3 — Personalization layer
This is user-specific:
* preference overlay
* tailored rankings
* personal target lists
* customized comparison
That is the real operating model of the app.

⸻

18. The Most Important Rule
The most important rule for the app workflow is:
Never let personalized preference logic contaminate the market truth layer.
Meaning:
* first build objective company-region-market truth
* then score opportunity
* then personalize
That keeps the app trustworthy.
