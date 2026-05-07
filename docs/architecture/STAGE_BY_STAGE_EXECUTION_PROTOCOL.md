Stage-by-Stage Execution Protocol

Boston vs. San Francisco/Silicon Valley Tech Opportunity Comparison System
This document turns the pipeline into an executable workflow.

⸻

1. Execution Goal
Produce a repeatable research workflow that compares Boston and San Francisco/Silicon Valley across:
* eligible tech company universe
* major tech concentration
* Magnificent 7 presence
* meaningful regional presence
* active hiring
* entry-level access
* objective target attractiveness
* personal target attractiveness
* normalized views
* primary and contextual final outputs
This workflow is designed so each stage:
* has a clear input
* produces a structured output
* feeds the next stage
* preserves auditability
* prevents category drift

⸻

2. Global System Rules
2.1 Region set
Primary regions:
* Boston labor region
* San Francisco/Silicon Valley labor region
Secondary contextual challenge geography:
* broader practical super-region interpretation, especially for Bay ecosystem scale
2.2 Region-first presentation rule
All primary tables should be organized:
1. Boston
2. San Francisco/Silicon Valley
Then compared side by side.
2.3 Classification discipline rule
Never collapse these into one variable:
* eligible company
* major tech company
* Mag 7 company
* regionally present company
* actively hiring company
* objective attractive target
* personally attractive target
2.4 Override rule
Override is allowed only for ambiguous but credible firms.Every override must be visible in the main table.
2.5 Evidence priority rule
When stronger evidence exists, use it over weaker evidence.
Priority examples:
* direct company hiring page > third-party repost
* direct regional office evidence > vague location references
* current posting evidence > generalized employer reputation
2.6 Remote rule
Remote roles do not enter the main score unless they are clearly tied to a regional office or regional hiring base.Even then, they should be placed in a separate remote-adjacent layer, not the core local-market score.

⸻

3. Master Workflow
The full workflow runs in this order:
1. Stage A — Candidate Company Intake
2. Stage B — Eligibility Screening
3. Stage C — Company Classification
4. Stage D — Regional Presence Assessment
5. Stage E — Active Hiring Assessment
6. Stage F — Entry-Level Access Assessment
7. Stage G — Objective Target Scoring
8. Stage H — Personal Overlay Scoring
9. Stage I — Normalization
10. Stage J — Final Output Assembly
11. Stage K — Contextual Challenge Output
12. Stage L — Audit and Consistency Check

⸻

4. Data Objects
These are the core objects the workflow should use.
4.1 Company Record
One record per company.
Suggested fields:
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
* classification_notes
4.2 Region Presence Record
One record per company-region pair.
Suggested fields:
* company_id
* region_id
* presence_status
* presence_basis
* office_evidence_flag
* operations_evidence_flag
* hiring_evidence_flag
* presence_confidence
* presence_notes
4.3 Hiring Record
One record per company-region pair for hiring analysis.
Suggested fields:
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
* hiring_notes
4.4 Entry-Level Record
One record per company-region pair for early-career access.
Suggested fields:
* company_id
* region_id
* internship_count
* coop_count
* entry_level_full_time_count
* formal_early_career_program_flag
* student_season_recurrence_signal
* entry_level_access_score
* entry_level_confidence
* entry_level_notes
4.5 Objective Target Record
One record per company-region pair.
Suggested fields:
* company_id
* region_id
* entry_level_access_component
* current_hiring_volume_component
* prestige_component
* objective_target_score
* objective_target_status
* objective_notes
4.6 Personal Overlay Record
One record per company-region pair.
Suggested fields:
* company_id
* region_id
* role_fit_component
* industry_component
* prestige_preference_component
* brand_appeal_component
* personal_overlay_score
* personal_target_status
* personal_notes

⸻

5. Stage A — Candidate Company Intake
Purpose
Build the broad initial candidate list before screening.
Input
Unfiltered candidate company pool from relevant sources.
Process
Collect firms that appear plausibly in-scope for:
* software
* internet
* AI
* cloud
* data
* hardware
* cybersecurity
* other serious tech categories
Do not filter too hard yet.
Output
candidate_company_list
Minimum output fields
* company_name
* sector_guess
* source_reference
* initial_notes
Rule
This stage is intentionally broad.Noise is allowed here because the next stage removes it.

⸻

6. Stage B — Eligibility Screening
Purpose
Determine which firms belong in the study universe.
Input
candidate_company_list
Process
Apply weighted eligibility rule.
6.1 Eligibility criteria
Evaluate each company against weighted signals such as:
* sector fit
* seriousness/maturity
* recognized market presence
* official organizational legitimacy
* scale
* evidence of being beyond noisy startup stage
6.2 Exclusion triggers
Mark ineligible if clearly:
* biotech-specific
* martech-specific
* too early-stage
* too unstable
* not meaningfully in-scope for this comparison
6.3 Override path
If a company is ambiguous but clearly credible, allow override inclusion.
Output
eligible_company_universe
Required output fields
* company_id
* company_name
* eligibility_status
    * eligible
    * ineligible
    * override_included
* eligibility_score
* eligibility_override_flag
* eligibility_override_reason
* classification_confidence
* sector_primary
* sector_secondary
Decision rule
Only eligible and override_included firms proceed.

⸻

7. Stage C — Company Classification
Purpose
Assign broad company-class labels to eligible firms.
Input
eligible_company_universe
Process
For each eligible company, classify:
* is it an eligible tech company
* is it major tech
* is it Mag 7
7.1 Major tech rubric
Use a balanced rubric based on:
* scale
* recognition/prestige
* seriousness/maturity
* labor-market significance
Do not heavily use current hiring intensity here.
7.2 Mag 7 rule
Binary classification:
* yes
* no
Output
classified_company_universe
Required output fields
* company_id
* company_name
* is_major_tech
* major_tech_score
* is_mag7
* classification_notes
Rule
These are parallel labels, not additive buckets.

⸻

8. Stage D — Regional Presence Assessment
Purpose
Determine whether each classified company has meaningful presence in each region.
Input
* classified_company_universe
* region list:
    * Boston
    * San Francisco/Silicon Valley
Process
For each company-region pair, assess presence.
8.1 Presence qualifies if either is true
* real office + real operations
* real office + actual hiring tied to region
8.2 Preference rule
If hiring evidence exists, prefer it.If not, a real satellite office can still suffice.
8.3 Presence status options
* present
* not_present
* uncertain
Output
regional_presence_table
Required output fields
* company_id
* region_id
* presence_status
* presence_basis
    * office_plus_operations
    * office_plus_hiring
    * satellite_office_only
    * insufficient_evidence
* office_evidence_flag
* operations_evidence_flag
* hiring_evidence_flag
* presence_confidence
Rule
Only present firms continue into region-specific hiring assessment.

⸻

9. Stage E — Active Hiring Assessment
Purpose
Measure current hiring activity for regionally present firms.
Input
regional_presence_table filtered to present
Process
Assess live hiring across time windows.
9.1 Core metrics
* active postings now
* active postings in last 30 days
* active postings in last 90 days
* annualized trend signal
* seasonal student hiring signal
* hiring program count
9.2 Time reliability rule
Treat as core evidence:
* now
* 30d
* 90d
Treat as contextual:
* annualized trend
* seasonal student hiring
Output
regional_hiring_table
Required output fields
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

⸻

10. Stage F — Entry-Level Access Assessment
Purpose
Measure early-career access within each company-region pair.
Input
regional_hiring_table
Process
Count and classify:
* internships
* co-ops
* entry-level full-time roles
* formal early-career programs
* recurring student-season hiring
10.1 Equal treatment rule
Internships and co-ops are weighted equally.
Output
entry_level_access_table
Required output fields
* company_id
* region_id
* internship_count
* coop_count
* entry_level_full_time_count
* formal_early_career_program_flag
* student_season_recurrence_signal
* entry_level_access_score
* entry_level_confidence

⸻

11. Stage G — Objective Target Scoring
Purpose
Identify objectively strong hiring targets.
Input
* classified_company_universe
* regional_hiring_table
* entry_level_access_table
Process
Score each company-region pair using three main components:
1. entry-level access
2. current hiring volume
3. prestige
11.1 Weighting rule
Entry-level access should be the highest-weighted factor, but only modestly above the others.
11.2 Output status
Assign:
* high_objective_target
* medium_objective_target
* low_objective_target
Output
objective_target_table
Required output fields
* company_id
* region_id
* entry_level_access_component
* current_hiring_volume_component
* prestige_component
* objective_target_score
* objective_target_status

⸻

12. Stage H — Personal Overlay Scoring
Purpose
Apply user-specific preference logic after objective scoring is complete.
Input
objective_target_table
Process
Score each company-region pair on:
1. role fit
2. industry
3. prestige
4. brand appeal
12.1 Weighting rule
Role fit and industry are weighted above prestige and brand appeal.
Output
personal_overlay_table
Required output fields
* company_id
* region_id
* role_fit_component
* industry_component
* prestige_preference_component
* brand_appeal_component
* personal_overlay_score
* personal_target_status

⸻

13. Stage I — Normalization
Purpose
Produce multiple normalized views without blending denominators into one opaque formula.
Input
Regional totals from prior stages.
Process
Create separate views:
13.1 Raw totals
No normalization.
13.2 General density view
Opportunity relative to metro/labor-region scale.
13.3 Tech-market density view
Opportunity relative to tech workforce/labor force.
13.4 Early-career accessibility view
Opportunity relative to relevant early-career pool and/or early-career sub-index.
Output
normalized_region_scores
Required output fields
* region_id
* raw_total_score
* general_density_score
* tech_market_density_score
* early_career_accessibility_score

⸻

14. Stage J — Final Output Assembly
Purpose
Assemble the main quantitative result.
Input
* classified_company_universe
* regional_presence_table
* regional_hiring_table
* entry_level_access_table
* objective_target_table
* personal_overlay_table
* normalized_region_scores
Process
Build the primary region-first comparison.
14.1 Main comparison components
Include:
* eligible company counts
* major tech counts
* Mag 7 counts
* meaningful presence counts
* active hiring counts
* entry-level counts
* objective target strength
* personal overlay comparison
* normalized views
Output
primary_quantitative_output
Required output sections
* region summary table
* score summary
* category winners
* explanatory notes
* visible override entries in main table

⸻

15. Stage K — Contextual Challenge Output
Purpose
Produce the secondary challenge comparison that tests whether broader practical regional reality changes the interpretation.
Input
All prior data, with broader contextual framing where appropriate.
Process
Build a second output that:
* challenges the main result
* shows whether broader ecosystem scale materially shifts interpretation
* remains subordinate to the primary result
Output
contextual_challenge_output
Required sections
* contextual score
* region-first comparison table
* narrative explanation of what changes and what does not
* explicit statement of whether the primary winner is challenged, reinforced, or unchanged

⸻

16. Stage L — Audit and Consistency Check
Purpose
Ensure the whole system stayed internally consistent.
Input
All stage outputs
Process
Check for:
* override overuse
* inconsistent classification logic across regions
* prestige leaking too heavily into non-prestige layers
* personal preference contaminating objective layers
* remote roles contaminating core local scores
* weak-presence inflation from satellite-office-only cases
* double-counting between descriptive lenses
Output
audit_report
Required audit fields
* override_count
* override_balance_by_region
* classification_consistency_flag
* presence_consistency_flag
* objective_layer_integrity_flag
* personal_layer_integrity_flag
* double_counting_flag
* audit_notes

⸻

17. Recommended Field Enums
Eligibility Status
* eligible
* ineligible
* override_included
Presence Status
* present
* not_present
* uncertain
Classification Confidence
* high_confidence
* moderate_confidence
* override_edge_case
Objective Target Status
* high_objective_target
* medium_objective_target
* low_objective_target
Personal Target Status
* high_personal_target
* medium_personal_target
* low_personal_target

⸻

18. Main Region-First Table Schema
Recommended top-level table structure:
Region Summary Table
Columns:
* region
* eligible_company_count
* major_tech_count
* mag7_count
* meaningful_presence_count
* actively_hiring_company_count
* active_posting_count_now
* posting_count_30d
* posting_count_90d
* entry_level_opportunity_count
* internship_count
* coop_count
* entry_level_full_time_count
* formal_early_career_program_count
* high_objective_target_count
* high_personal_target_count
* raw_total_score
* general_density_score
* tech_market_density_score
* early_career_accessibility_score
Main Company Detail Table
Columns:
* region
* company_name
* eligibility_status
* eligibility_override_flag
* eligibility_override_reason
* classification_confidence
* is_major_tech
* is_mag7
* presence_status
* presence_basis
* currently_hiring_flag
* entry_level_access_score
* objective_target_score
* personal_overlay_score

⸻

19. Suggested Weighting Hierarchy
Not exact numbers yet, but the ranking should be:
Objective opportunity score
1. entry-level access
2. current hiring volume
3. prestige
with 2 and 3 close behind 1.
Personal overlay score
1. role fit
2. industry
3. prestige
4. brand appeal
Descriptive/contextual layers
These should support interpretation, not dominate the final score:
* eligible universe breadth
* major tech density
* Mag 7 density
* presence footprint

⸻