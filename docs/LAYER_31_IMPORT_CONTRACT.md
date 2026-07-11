# Layer 31A Import Contract

Layer 31A defines deterministic curated-file imports for market data. It does
not scrape, crawl, call live APIs, write canonical database records, recompute
scores, rebuild outputs, or update frontend display.

## Dataset Location

The first fixture dataset is Greater NYC:

```text
data/imports/nyc/
```

Required files:

```text
regions.json
companies.csv
presence.csv
hiring.csv
entry_level.csv
source_refs.csv
```

## Files And Fields

`regions.json` is a JSON array. Required fields:

- `region_id`
- `region_name`
- `region_type`
- `country`
- `state_codes`
- `primary_city`
- `source_ref`

`companies.csv` required fields:

- `company_id`
- `company_name`
- `sector`
- `public_or_private`
- `website_domain`
- `source_ref`

`presence.csv` required fields:

- `company_id`
- `region_id`
- `presence_status`
- `presence_basis`
- `office_location_summary`
- `source_ref`

`hiring.csv` required fields:

- `company_id`
- `region_id`
- `role_family`
- `active_posting_count`
- `active_posting_count_status`
- `annualized_trend_signal`
- `seasonal_student_hiring_signal`
- `source_ref`

`entry_level.csv` required fields:

- `company_id`
- `region_id`
- `internship_count`
- `internship_count_status`
- `coop_count`
- `coop_count_status`
- `entry_level_full_time_count`
- `entry_level_full_time_count_status`
- `formal_early_career_program_flag`
- `student_season_recurrence_signal`
- `source_ref`

`source_refs.csv` required fields:

- `source_ref`
- `source_name`
- `source_type`
- `source_url_or_reference`
- `collected_at`
- `observed_at`
- `confidence`
- `license_or_terms_category`
- `freshness_status`

## Provenance Rules

Every fact-bearing record must carry a `source_ref` that resolves to a valid
row in `source_refs.csv`.

Hard rule:

```text
No source, no canonical fact.
```

For Layer 31A, validation rejects rows without source refs, rows with unknown
source refs, and rows whose source refs exist but fail provenance validation.

Required provenance metadata:

- `source_type`
- `collected_at`
- `observed_at`
- `confidence`
- `license_or_terms_category`
- `freshness_status`

Dates use date-only ISO format: `YYYY-MM-DD`.

## Source Types

Layer 31A uses the existing shared provenance vocabulary and allows this
curated-import subset:

- `company_official`
- `ats_job_board`
- `government_public_data`
- `regional_economic_dataset`
- `reputable_third_party_aggregator`
- `manual_research`

Unsupported source types, including unknown or generated source types, fail
validation.

## License And Terms Categories

Layer 31A allows this subset of the existing shared license vocabulary:

- `public`
- `permissive`
- `restricted`

`unknown` and `prohibited` do not satisfy the curated import contract.

## Freshness

Layer 31A uses a deterministic staleness threshold:

```text
observed_at older than 365 days is stale
```

The validator accepts a fixed `as_of` date for tests and batch runs. Source refs
with invalid freshness states, declared `stale` freshness, or `observed_at`
older than the threshold fail validation.

## Unknown-vs-Zero Semantics

Missing is not zero. Unknown is not zero. Blank is not zero. Only sourced,
observed zero is zero.

Count fields are represented as a value column plus a status column:

- value blank + status `unknown`
- value blank + status `not_collected`
- value blank + status `not_applicable`
- value `0` + status `zero_observed`
- positive integer + status `positive_observed`

Examples:

```csv
internship_count,internship_count_status
,unknown
0,zero_observed
4,positive_observed
```

Invalid examples:

```csv
internship_count,internship_count_status
unknown,unknown
0,unknown
,zero_observed
```

Observed counts are allowed only when the row has a valid source ref whose
provenance includes an observed date.

## Validation Behavior

`backend.imports.validation.validate_import_dataset()` returns a structured
result with:

- `ok`
- `errors`
- `warnings`
- `summary`

Errors include:

- `file`
- `row_number`
- `record_id`
- `field`
- `code`
- `message`

The validator detects missing files, missing fields, invalid IDs, invalid
source refs, missing provenance metadata, duplicate records/facts, invalid
dates, invalid confidence values, stale source dates, unsupported source types,
unsupported license categories, invalid freshness states, ambiguous count
encoding, and invalid unknown encodings.

Layer 31A stops at contract and validation. Canonical writes, import services,
score recompute, output rebuild, frontend display, scheduled imports, scraping,
API ingestion, and approval workflows are out of scope.

## Layer 31B Canonical Import Behavior

Layer 31B adds a deterministic canonical write path for validated curated
datasets.

The canonical flow is:

```text
load curated dataset
run full Layer 31A validation
if validation fails, write nothing
if validation passes, idempotently upsert canonical records
return structured import result
```

The importer writes:

- source references, source observations, and fact-source links
- regions
- companies
- company-region presence
- company-region hiring
- company-region entry-level facts

Validation is the write gate. A validation failure returns
`status="validation_failed"`, includes the structured validation errors, and
does not create source refs or canonical domain rows.

Imports are idempotent. Running the same dataset again upserts to the same
final state and reports unchanged records instead of creating duplicates.

Provenance is preserved through canonical provenance tables and, where the
canonical table already has `source_refs`, through row-local source metadata.
The preserved metadata includes:

- `source_ref`
- `source_type`
- `collected_at`
- `observed_at`
- `confidence`
- `license_or_terms_category`
- `freshness_status`

Unknown-vs-zero semantics are preserved in canonical count-status columns.
Unknown, not-collected, and not-applicable counts remain `NULL` with explicit
status values. Sourced observed zero remains numeric `0` with
`zero_observed`.

Layer 31B does not recompute region scores, rebuild outputs, update frontend
display, run scheduled imports, scrape, crawl, call external APIs, or create
manual approval workflows. Entry-level import writes factual counts/statuses
and provenance only; broader scoring/rebuild behavior is deferred.

## Layer 31C Post-Import Refresh

Layer 31C adds a deterministic post-import refresh for already-imported
curated datasets.

The refresh flow is:

```text
load curated dataset identifiers
run full Layer 31A validation
confirm expected canonical records exist
evaluate imported facts through Layer 30 trust/risk/ranking services
persist idempotent trust assessments and risk routing decisions
recompute derived scores from ranking-eligible facts only
rebuild supported backend outputs
return structured refresh result
```

Validation remains the first gate. If validation fails, no trust/risk,
scoring, or output writes run. If the expected canonical records are missing,
the refresh returns `status="canonical_records_missing"` and does not create
partial trust or output rows.

Imported facts are evaluated through existing Layer 30 services. The refresh
derives:

- trust tier
- risk level and routing outcome
- ranking influence allow/deny decision
- user-facing trust label
- user-facing freshness label
- ranking influence label

The refresh does not create manual approval queues. Stale, weak, or
insufficiently sourced imported facts are labeled and denied ranking influence
by the existing deterministic trust/risk policy.

Ranking math uses the hard rule:

```text
Only ranking-eligible imported facts may affect score math.
```

The region scoring and output builders consume the existing ranking gate, so
explicit Layer 30 deny decisions remove imported facts from:

- region score inputs
- company-region score inputs
- early-career score inputs
- output top lists and summaries
- comparison output inputs

Unknown-vs-zero semantics are preserved during recompute. Unknown and
not-collected counts are not scored as hidden zeroes. `not_applicable` count
dimensions are omitted only where the local score component can be computed
from observed dimensions without treating the not-applicable value as zero.
Observed zero remains numeric `0` and may affect score math only when the
underlying fact is ranking-eligible.

Layer 31C rebuilds supported backend outputs for the imported NYC region and
companies, and can rebuild comparison outputs for supplied peer regions. Public
payloads remain redacted; they do not expose internal reviewer notes, reporter
identifiers, report text, exception internals, raw risk objects, or private
trust routing IDs.

Layer 31C still does not update frontend display, run scheduled imports,
scrape, crawl, call external APIs, or create manual approval workflows.

## Layer 31D Frontend Display And Public Payloads

Layer 31D exposes the imported NYC result through existing user-facing region,
company, and comparison surfaces.

Backend output payloads add public-safe `import_metadata` labels for supported
region/company/comparison objects and fact rows. These fields are display
metadata only:

- `imported_data_label`
- `source_label`
- `coverage_label`
- `freshness_label`
- `trust_label`
- `risk_label`
- `ranking_label`
- `ranking_influence_allowed`

The labels are derived from canonical source links and Layer 30 routing
decisions. They do not expose trust assessment IDs, risk routing IDs, reviewer
notes, reporter identifiers, freeform reports, exception internals, raw risk
objects, or private provenance internals.

Frontend display uses these labels to show:

- real imported data
- source-backed evidence
- partial coverage where output coverage is incomplete
- freshness state
- trust/risk label
- ranking-safe or ranking-excluded state

Count-like fields render through explicit count-status fields:

- `unknown` renders as `Unknown`
- `not_collected` renders as `Not collected`
- `not_applicable` renders as `Not applicable`
- `zero_observed` with value `0` renders as `0 observed`
- `positive_observed` renders as the positive count

Null, blank, unknown, not-collected, and not-applicable values are not displayed
as zero. Observed zero is displayed as a real sourced zero.

Layer 31D does not add scraping, crawling, external API calls, live ingestion,
scheduled imports, manual approval workflows, score recompute changes, or broad
frontend redesign. It completes the Layer 31 user-visible path for the
deterministic curated NYC import.
