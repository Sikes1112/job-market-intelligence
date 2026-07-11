# Layer 32 Multi-Market Curated Import

Layer 32A generalizes the Layer 31 curated import path from a Greater NYC
dataset path into a registry-backed, market-keyed import system. It keeps the
Layer 31 contract intact: curated local files are validated before canonical
writes, validation failure writes nothing, facts must be source-backed,
provenance is preserved, imports are idempotent, and unknown count states are
not coerced to zero.

## Market Registry

Curated markets are registered in:

```text
data/imports/markets.json
```

Each record declares:

- `market_key`
- `region_id`
- `display_name`
- `dataset_path`
- `coverage_status`
- `import_status`
- `last_curated_at`
- `peer_group`
- optional `notes` / `warnings`

Layer 32A registers:

- `nyc` -> `greater_nyc` -> `data/imports/nyc`
- `seattle` -> `greater_seattle` -> `data/imports/seattle`

Registry validation rejects missing registry files, duplicate market keys,
duplicate region IDs, missing required fields, unsupported coverage/import
statuses, invalid dates, invalid dataset paths, registry/dataset region
mismatches, and market-key/dataset-path mismatches.

## Market-Keyed Validation

Direct dataset validation remains available for existing Layer 31 fixture
tests:

```python
validate_import_dataset(path)
```

Registry-aware validation is available by market key:

```python
validate_curated_market_dataset("nyc")
validate_curated_market_dataset("seattle")
```

The market-keyed validator loads the registry, resolves the dataset path,
runs the Layer 31 file contract, then applies registry-specific checks:

- dataset region IDs must match the registered market region
- fact rows must use the registered market region
- source refs must be local to the registered market prefix
- fact rows cannot pass validation by pointing at another market's source refs

## Generic Canonical Import

The generic canonical entry point accepts a registered market key:

```python
import_curated_market_dataset(session, "nyc")
import_curated_market_dataset(session, "seattle")
```

Direct paths are still supported for fixture tests. For market keys, the import
flow is:

```text
load registry
resolve market_key
resolve dataset_path
validate registry entry
validate dataset using Layer 31 validation
if validation fails, write nothing
if validation passes, write canonical facts idempotently
return structured import result
```

The NYC wrapper remains for compatibility and delegates to the generic path:

```python
import_nyc_dataset(session) -> import_curated_market_dataset(session, "nyc")
```

Seattle uses the same importer. There is no Seattle-specific importer module or
market branch.

## Seattle Dataset

Seattle is checked in under:

```text
data/imports/seattle/
```

The files use the exact Layer 31 contract:

- `regions.json`
- `companies.csv`
- `presence.csv`
- `hiring.csv`
- `entry_level.csv`
- `source_refs.csv`

The fixture includes region, company, presence, hiring, entry-level, and
source-ref coverage. It includes positive observed counts, observed zero
counts, unknown counts, and one company shared with NYC
(`cmp_hudson_applied_ai`) to prove canonical company reuse while preserving
market-specific presence/hiring/entry facts.

## Post-Import Refresh

The generic post-import entry point accepts a registered market key:

```python
run_curated_market_post_import(session, "nyc")
run_curated_market_post_import(session, "seattle")
```

The NYC wrapper delegates to the generic path. Refresh remains idempotent and
market scoped: trust/risk/ranking decisions are attached to the canonical facts
resolved from the selected market dataset, region score recompute is scoped to
that market's region, and output rebuild covers the selected region and its
companies.

## Ranking-Safe Scoring and Outputs

Layer 32A keeps Layer 30/31 protections:

- ranking-ineligible imported facts are excluded from score math and output top
  lists
- stale/risky Seattle facts do not alter NYC score math
- Seattle score/output rebuild uses the same output assembly path as NYC
- comparison output can include NYC and Seattle after both market outputs are
  refreshed
- unknown/not-collected/not-applicable counts remain non-numeric unknown states
- observed zero remains numeric zero and renders distinctly

Public payload import metadata remains label/boolean-only. It does not expose
internal trust IDs, risk-routing IDs, reports, exceptions, or reviewer fields.

## Explicit Non-Goals

Layer 32A does not add scraping, crawling, browser automation, live API calls,
scheduled imports, manual approval workflows, new markets beyond NYC/Seattle,
or the final frontend multi-market discovery UI.

## Layer 32B Expansion

Layer 32B keeps the same registry and six-file dataset contract, then expands
the checked-in import-ready market set to:

- `nyc` -> `greater_nyc`
- `seattle` -> `greater_seattle`
- `san_francisco_bay_area` -> `sf_bay_area`
- `boston` -> `greater_boston`
- `washington_dc` -> `washington_dc`
- `austin` -> `austin`
- `atlanta` -> `atlanta`
- `chicago` -> `chicago`

The six 32B market fixture directories each contain:

- `regions.json`
- `companies.csv`
- `presence.csv`
- `hiring.csv`
- `entry_level.csv`
- `source_refs.csv`

The additional fixtures are intentionally small. They are curated local
fixtures, not exhaustive market coverage. Each includes positive observed
counts, observed zero counts, unknown/not-collected/not-applicable states,
source refs, presence facts, hiring facts, and entry-level facts.

## Shared Companies

Layer 32B intentionally repeats canonical company IDs across markets to prove
reuse:

- `cmp_google` appears across Bay Area, Boston, Austin, and Chicago.
- `cmp_microsoft` appears across Washington DC, Atlanta, and Chicago.
- `cmp_cisco` appears across Bay Area, Washington DC, and Atlanta.
- `cmp_jpmorgan_chase` appears across Atlanta and Chicago.
- `cmp_deloitte` appears across Washington DC and Austin.

Shared companies remain single canonical `companies` rows. Market-specific
presence, hiring, and entry-level facts remain keyed by company plus region and
therefore stay separate.

## Bulk Operations

Layer 32B adds bulk helpers for registered import-ready markets:

```python
validate_all_registered_market_datasets(...)
import_all_curated_market_datasets(...)
run_all_curated_market_post_imports(...)
rebuild_all_curated_market_outputs(...)
```

Each helper loads the market registry and iterates `import_status == "ready"`
markets. Bulk import uses the same single-market validation-before-write path
per market. A validation failure in one market is reported in the batch result
and does not write canonical rows for that failed market. Other valid markets
can still import successfully.

Bulk results include:

- `markets_processed`
- `markets_succeeded`
- `markets_failed`
- `per_market_results`
- `total_created`
- `total_updated`
- `total_unchanged`
- `total_skipped`
- `total_failed`
- `total_ranking_allowed`
- `total_ranking_denied`
- `warnings`
- `errors`

Bulk output rebuild currently reuses the post-import refresh path because that
path already recomputes trust/risk/ranking, entry-level scores, region scores,
region outputs, company outputs, and supported comparison outputs.

## Coverage Summaries

Layer 32B adds backend market coverage summaries:

```python
build_market_coverage_summary(session, market_key)
build_all_market_coverage_summaries(session)
```

Coverage summaries are public-safe and frontend-consumable. They include:

- market key, region ID, display name
- registry coverage/import status
- company, presence, hiring, entry-level, and source counts
- freshness status and label
- ranking-eligible and ranking-excluded fact counts
- unknown count dimensions
- observed-zero count dimensions
- count-status breakdown
- last curated date
- import/refresh status labels
- source, coverage, freshness, and ranking labels

They do not expose raw trust assessment IDs, risk routing IDs, fact-source link
IDs, private report fields, exception fields, or reviewer internals.

## 32B Safety Rules

Layer 32B keeps the Layer 30/31/32A safety boundaries:

- validation still runs before canonical writes
- failed market validation writes nothing for that market
- fact-source links remain source-prefixed and market-scoped for
  region-specific facts
- stale/risky facts are ranking-denied per fact and per market
- a stale Atlanta fact does not affect Seattle
- a ranking-denied Austin fact does not affect NYC
- unknown/not-collected/not-applicable values remain nonnumeric unknown states
- observed zero remains numeric zero
- public payloads and coverage summaries expose only public-safe labels/counts

Layer 32B still does not add frontend multi-market discovery UI, final Layer 32
closeout, scraping, crawling, browser automation, live API calls, scheduled
imports, or manual approval workflows.

## Layer 32C Frontend Display

Layer 32C exposes the curated multi-market system through the existing frontend
market exploration surface. The UI is generic across registered markets and is
not hardcoded to Greater NYC or Seattle.

The frontend now loads:

```text
GET /markets/imported
```

The route returns a standard public envelope with:

- `markets`
- `market_count`

Each market summary is built from `build_all_market_coverage_summaries()` and
contains only frontend-safe fields:

- market key, region ID, display name
- coverage/import status
- company, source, presence, hiring, and entry-level fact counts
- freshness status and public label
- ranking-eligible and ranking-excluded fact counts
- unknown count dimensions
- observed-zero count dimensions
- count-status breakdown
- last curated date
- import/refresh status labels
- imported-data, source, coverage, freshness, trust, risk, ranking, and
  comparison labels

The route does not expose raw trust assessment IDs, risk routing IDs, report
text, reporter identifiers, exception internals, fact-source link IDs, private
provenance internals, or reviewer/admin fields.

## Frontend Rendering Rules

`frontend/src/ImportedMarketDisplay.tsx` now includes a generic imported market
coverage panel used by `frontend/src/App.tsx` on the Explore Markets screen.
It displays all registered imported markets from the backend payload, including:

- Greater NYC
- Greater Seattle
- San Francisco Bay Area
- Greater Boston
- Washington DC
- Austin
- Atlanta
- Chicago

The panel renders public-safe labels such as:

- Real imported data
- Source-backed
- Seed coverage / Partial coverage
- Freshness: current
- Freshness: needs refresh
- Trust: Source-backed
- Risk: Low risk / Risk: Use with caution
- Ranking-safe
- Some data ranking-excluded
- Comparison available

Layer 32C does not introduce a broad new frontend area. Region, company, and
comparison surfaces continue to render their existing imported fact metadata.

## Unknown-vs-Zero Display

The frontend formatting helpers preserve Layer 31/32 semantics:

```text
unknown != zero
not_collected != zero
not_applicable != zero
zero_observed == real sourced zero
```

Display examples:

- `unknown` + null count -> `Unknown`
- `not_collected` + null count -> `Not collected`
- `not_applicable` + null count -> `Not applicable`
- `zero_observed` + `0` -> `0 observed`
- `positive_observed` + `4` -> `4`

Aggregate coverage summaries show unknown and observed-zero dimensions as
explicit labeled dimensions. They do not coerce missing or null values to `0`.

## Layer 32C Safety Rules

Layer 32C keeps the Layer 30/31/32A/32B boundaries:

- frontend market discovery is backed by public-safe backend summaries
- trust/freshness/risk/ranking display uses labels, not internal records
- comparison availability is displayed as a label and does not create new
  ranking behavior
- existing region/company/comparison payloads remain public-safe
- no scraping, crawling, browser automation, live API calls, scheduled imports,
  or manual approval workflows were added

Layer 32C also creates the final Layer 32 closeout document.
