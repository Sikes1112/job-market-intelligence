# Layer 18 - Platform Intelligence

Layer 18 turns historical app-owned observations into a durable labor-market
intelligence foundation. Batch 18A implements the historical foundation, Batch
18B adds derived predictive signals and proprietary indices, Batch 18C adds
reviewable benchmark reports, and Batch 18D adds governed contribution intake.

## Batch 18A Scope

Implemented:

- append-only `market_snapshots`
- append-only `company_region_snapshots`
- append-only `sector_region_snapshots`
- append-only `market_score_history`
- append-only `historical_observations`
- conservative delta detection between adjacent snapshots
- safe read APIs for region and company history

Not implemented in 18A:

- predictive signals
- proprietary indices
- benchmark report generation
- partner contribution workflows
- public snapshot creation APIs

## Boundary Rules

Historical rows record what the platform observed or believed at a point in
time. Creating snapshots or observations must not mutate canonical `regions`,
`companies`, `region_market_scores`, hiring, presence, entry-level, output, or
ranking records.

Corrections are represented as later historical rows. Existing historical rows
are append-only and carry `created_at` rather than canonical `updated_at`,
`state`, or `version` metadata.

## Delta Detection

Delta detection is conservative:

- score changes below `0.05` are ignored
- count changes below `2` are ignored
- observations include previous/current snapshot IDs, signed delta, direction,
  severity, confidence, and a safe evidence summary

Observation types include regional score changes, entry-level access changes,
company presence changes, hiring activity changes, sector growth/decline, and
internship-density changes.

## API Surface

- `GET /platform/history/regions/{region_id}`
- `GET /platform/history/companies/{company_id}`

Responses expose safe summary fields only. Raw source refs, source version
bundles, admin metadata, and internal provenance payloads remain internal.

## Batch 18B Scope

Implemented:

- derived predictive signals in `predictive_signals`
- signal evidence rows in `signal_inputs`
- versioned market index registry in `market_indices`
- append-only index formula versions in `market_index_versions`
- derived index scores in `market_index_scores`
- auditable score inputs in `market_index_inputs`

Required predictive signal types:

- `emerging_market`
- `declining_market`
- `seasonal_hiring_window`
- `company_expansion_signal`
- `entry_level_access_trend`

Required proprietary indices:

- `early_career_tech_access`
- `ai_opportunity_geography`
- `internship_density`
- `company_presence_quality`
- `hidden_market_opportunity`

## 18B Boundaries

Predictive signals and market indices are derived intelligence. They do not
mutate canonical regions, companies, current region scores, rankings,
recommendation outputs, or reports.

Signals require evidence windows and snapshot counts. Fewer than 3 snapshots can
create candidate rows, but those candidates are not returned as active signals.
Signals use conservative wording such as "signal", "trend", "candidate", and
"watchlist item".

Index formulas are versioned. Public APIs expose methodology summaries and
scores, but internal weight configs and raw input references remain private.
Formula changes create new version rows; old score rows keep their original
version references for auditability.

Additional API surface:

- `GET /platform/signals/regions/{region_id}`
- `GET /platform/indices`
- `GET /platform/indices/{index_key}/scores`

## Batch 18C Scope

Implemented:

- benchmark report records in `benchmark_reports`
- ordered report sections in `benchmark_report_sections`
- report-specific ranked regions in `benchmark_report_rankings`
- auditable report evidence in `benchmark_report_evidence`
- draft, review-ready, publish, archive, and supersede service lifecycle
- safe public read APIs for published reports

Required report keys:

- `best_cities_early_career_ai_roles`
- `top_emerging_tech_markets`
- `best_markets_product_careers`
- `best_regions_internship_access`

Report statuses:

- `draft`
- `review_ready`
- `published`
- `archived`
- `superseded`

Reports are generated from Layer 18A snapshots/observations and Layer 18B
indices/signals. They include methodology summaries, data windows, freshness
notes, confidence notes, coverage notes, limitations, rankings, sections, and
public-safe evidence summaries.

## 18C Boundaries

Benchmark reports are public-facing intelligence products. They do not mutate
canonical regions, companies, current scores, canonical rankings, index scores,
predictive signals, recommendation outputs, or contribution data.

Draft and review-ready reports are not public. Publishing is explicit and
supersedes the previous published report for the same key rather than silently
rewriting it. Archived and superseded reports are excluded from the public
current-report APIs.

Public report payloads do not expose internal formula weights, raw index input
weights, private source internals, review notes, admin-only metadata, or
unpublished draft sections.

Additional API surface:

- `GET /platform/reports`
- `GET /platform/reports/{report_key}`

## Batch 18D Scope

Implemented:

- governed contribution intake in `data_contributions`
- append-only evidence rows in `contribution_evidence`
- append-only review rows in `contribution_reviews`
- authenticated basic-user contribution submission
- institution-scoped contribution submission using existing institution roles
- admin/data-reviewer review queue and review lifecycle actions
- public-demo denial for all contribution mutations

Required contribution types:

- `verified_correction`
- `company_presence_update`
- `regional_employer_list`
- `career_center_intelligence`
- `internship_program_information`
- `role_access_feedback`
- `source_suggestion`
- `market_quality_feedback`
- `outdated_data_report`

Contribution statuses:

- `submitted`
- `needs_review`
- `verified`
- `rejected`
- `merged`
- `superseded`

## 18D Boundaries

Contributions are governed intake records. They do not create external
authority over canonical product intelligence.

Submitted and unverified contributions can create review queue records,
stale-data suggestions, source suggestions, internal-only intelligence records,
and future research inputs. They do not mutate canonical rankings, official
scores, index scores, predictive signals, benchmark reports, recommendation
outputs, historical snapshots, public confidence scores, public warnings, or
published outputs.

Verified and merged reviews may record governed follow-up candidate/task flags
or refs, but canonical changes must still pass existing source, review,
refresh, and scoring boundaries. Review never rewrites historical snapshots;
history corrections must be represented by later safe correction records or
future governed refresh flows.

Institution-scoped contribution types require active institution membership
with existing advisor/upload-style roles. Review routes require existing
admin/data-reviewer access.

Additional API surface:

- `POST /platform/contributions`
- `GET /platform/contributions/review`
- `POST /platform/contributions/{contribution_id}/review`
