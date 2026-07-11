# Layer 32 Closeout

## 1. Layer Decision

LOCK_READY

## 2. Confidence Level

High. Layer 32A, 32B, and 32C behaviors are implemented and verified across
backend import, validation, refresh, scoring, output, public payload, frontend,
lint, build, migration, and schema checks.

## 3. Executive Summary

Layer 32 converts the Layer 31 Greater NYC curated import path into a
registry-backed multi-market curated import system. Eight markets are now
registered, validated, imported, refreshed, scored, rebuilt into outputs, and
displayed through a generic frontend multi-market coverage panel.

The system keeps Layer 31 guarantees: validation runs before writes, failed
validation writes nothing, facts are source-backed, provenance is preserved,
imports and refreshes are idempotent, unknown values are not coerced to zero,
observed zero remains numeric zero, and public payloads expose labels/counts
rather than internal trust/risk/report/exception records.

No scraping, crawling, browser automation, live API calls, scheduled imports,
manual approval workflows, broad ranking refactors, or broad frontend redesigns
were added.

## 4. Files Inspected

- `backend/imports/registry.py`
- `backend/imports/validation.py`
- `backend/imports/service.py`
- `backend/imports/post_import.py`
- `backend/imports/bulk.py`
- `backend/imports/coverage.py`
- `backend/api/routes.py`
- `backend/outputs/*`
- `data/imports/markets.json`
- `data/imports/*`
- `frontend/src/App.tsx`
- `frontend/src/api.ts`
- `frontend/src/types.ts`
- `frontend/src/ImportedMarketDisplay.tsx`
- `frontend/src/importedMarketFormat.ts`
- `frontend/src/dataQuality.ts`
- `frontend/src/styles.css`
- Layer 31, 32A, 32B, 32C backend and frontend tests

## 5. Files Changed

- `backend/api/routes.py`
- `backend/imports/*`
- `data/imports/markets.json`
- `data/imports/nyc/*`
- `data/imports/seattle/*`
- `data/imports/san_francisco_bay_area/*`
- `data/imports/boston/*`
- `data/imports/washington_dc/*`
- `data/imports/austin/*`
- `data/imports/atlanta/*`
- `data/imports/chicago/*`
- `docs/LAYER_31_IMPORT_CONTRACT.md`
- `docs/LAYER_31_CLOSEOUT.md`
- `docs/LAYER_32_MULTI_MARKET_IMPORT.md`
- `docs/LAYER_32_CLOSEOUT.md`
- `frontend/src/App.tsx`
- `frontend/src/api.ts`
- `frontend/src/api.test.ts`
- `frontend/src/types.ts`
- `frontend/src/ImportedMarketDisplay.tsx`
- `frontend/src/ImportedMarketDisplay.test.tsx`
- `frontend/src/importedMarketFormat.ts`
- `frontend/src/importedMarketFormat.test.ts`
- `frontend/src/styles.css`
- Layer 31, 32A, 32B, and 32C import/output/coverage/frontend tests

## 6. 32.1 Market Registry Generalization Findings

`data/imports/markets.json` is the formal curated market registry. It registers:

- `nyc`
- `seattle`
- `san_francisco_bay_area`
- `boston`
- `washington_dc`
- `austin`
- `atlanta`
- `chicago`

Registry validation rejects missing files, duplicate market keys, invalid
duplicate region IDs, missing required fields, unsupported statuses, invalid
dates, invalid dataset paths, registry/dataset region mismatches, and
market-key/dataset-path mismatches.

## 7. 32.2 Generic Import Path Findings

`import_curated_market_dataset(session, market_key)` loads the registry,
resolves the dataset path, validates the registered dataset, and writes
canonical facts only after successful validation. `import_nyc_dataset()` remains
a thin compatibility wrapper around the generic NYC path.

Seattle and all 32B markets use the same generic importer. No
market-specific importer branches were added.

## 8. 32.3 Multi-Market Validation Findings

Registry-aware validation works for all eight markets. It enforces the six-file
contract, region scope, market-local source refs, company IDs, duplicate fact
guards, source-backed facts, freshness checks, and unknown-vs-zero semantics.

## 9. 32.4 Seattle Dataset Findings

Seattle is a second real curated market fixture under `data/imports/seattle/`.
It uses the Layer 31 contract and imports region, company, presence, hiring,
entry-level, source refs, positive counts, unknown counts, and observed zero
counts through the generic path.

## 10. 32.5 Additional Market Fixture Findings

Layer 32B adds six additional curated market fixture directories:

- San Francisco Bay Area
- Boston / Greater Boston
- Washington DC
- Austin
- Atlanta
- Chicago

Each uses the same required six-file contract and includes enough curated local
data to prove validation, canonical import, provenance, refresh, scoring,
outputs, comparison, coverage summaries, shared-company reuse, unknown counts,
and observed-zero counts.

## 11. 32.6 Multi-Market Canonical Import Findings

All eight markets import into the same canonical database. Shared companies
remain single canonical company rows, while company-region presence, hiring,
and entry-level facts stay region-specific. Repeated imports are idempotent.
Validation failure in one market does not corrupt successfully imported markets.

## 12. 32.7 Multi-Market Trust/Risk/Ranking Findings

`run_curated_market_post_import(session, market_key)` and
`run_all_curated_market_post_imports(session)` apply trust/risk/ranking checks
per market and per fact. Stale/risky/ranking-denied facts are scoped to their
market and do not affect other markets. Repeated refreshes are idempotent.

## 13. 32.8 Multi-Market Score/Output Rebuild Findings

`rebuild_all_curated_market_outputs(session)` rebuilds region outputs, company
outputs, and supported comparison outputs for all registered import-ready
markets. All eight region outputs, shared company outputs, and pairwise
comparison outputs are supported by the existing output assembly path.

Ranking-ineligible facts remain excluded from score and top-list influence.

## 14. 32.9 Frontend Multi-Market Display Findings

The frontend now loads `GET /markets/imported` and renders a generic imported
market coverage panel on Explore Markets. The panel displays all eight markets,
source-backed labels, coverage labels, freshness labels, trust/risk labels,
ranking-safe/ranking-excluded labels, comparison availability, counts, unknown
dimensions, and observed-zero dimensions.

Existing region, company, and comparison views still render their Layer 31
import metadata.

## 15. 32.10 Market Coverage Status Findings

`build_market_coverage_summary()` and
`build_all_market_coverage_summaries()` produce backend public-safe coverage
summaries. `GET /markets/imported` exposes those summaries through the standard
API envelope with no raw internal trust/risk/provenance IDs.

## 16. 32.11 Tests and Closeout Findings

New Layer 32C tests cover backend multi-market frontend payload safety,
frontend multi-market rendering, imported market formatting, API client request
behavior, unknown-vs-zero display, ranking-excluded labels, and public payload
field safety.

This closeout document records final Layer 32 implementation and verification.

## 17. Shared-Company Findings

Shared company IDs such as Google, Microsoft, Cisco, JPMorgan Chase, Deloitte,
and the Layer 32A shared NYC/Seattle fixture company remain canonical. Reuse
does not duplicate company rows incorrectly. Market facts remain separated by
region-specific presence, hiring, and entry-level records.

## 18. Unknown-vs-Zero Findings

Unknown, not-collected, and not-applicable states remain nonnumeric. Observed
zero remains numeric `0` and renders as `0 observed`. Frontend formatters and
backend output payloads preserve these states across all markets.

## 19. Ranking Protection Findings

Ranking-ineligible facts do not affect score math or output top lists. Stale
or risky facts are denied ranking influence per fact and per market. A stale
Atlanta fact does not affect Seattle, and a ranking-denied Austin fact does not
affect NYC.

## 20. Public Payload Safety Findings

Public payloads expose labels, booleans, aggregate counts, and safe status
fields. They do not expose internal trust assessment IDs, risk routing IDs,
freeform report text, reporter identifiers, exception internals, private
provenance internals, fact-source link IDs, or reviewer/admin fields.

## 21. Tests Run With Exact Commands And Results

```bash
python -m pytest tests/test_import_dataset_validation.py tests/test_curated_market_import.py tests/test_curated_market_post_import.py tests/test_layer31_frontend_payload.py
# 45 passed in 2.20s
```

```bash
python -m pytest tests/test_market_registry.py tests/test_multi_market_import.py tests/test_multi_market_post_import.py
# 37 passed in 1.89s
```

```bash
python -m pytest tests/test_multi_market_bulk_import.py tests/test_market_coverage.py tests/test_multi_market_outputs.py
# 37 passed in 12.96s
```

```bash
python -m pytest tests/test_multi_market_frontend_payload.py
# 2 passed in 2.19s
```

```bash
python -m pytest tests/test_outputs_service.py tests/test_output_handlers.py
# 49 passed in 1.87s
```

```bash
python -m pytest tests/test_*trust*.py tests/test_*ranking*.py tests/test_provenance.py tests/test_provenance_freshness.py
# 48 passed in 0.60s
```

```bash
python -m pytest tests/test_*scoring*.py
# 103 passed in 0.88s
```

```bash
python -m pytest tests/test_migrations.py tests/test_schema_completeness.py
# 22 passed in 1.58s
```

```bash
npm test
# frontend workdir; 26 test files passed, 133 tests passed in 3.86s
```

```bash
npm run lint
# frontend workdir; passed
```

```bash
npm run build
# frontend workdir; passed; Vite reported an existing chunk-size warning
```

```bash
python -m ruff check backend/imports backend/outputs tests/test_import_dataset_validation.py tests/test_curated_market_import.py tests/test_curated_market_post_import.py tests/test_layer31_frontend_payload.py tests/test_market_registry.py tests/test_multi_market_import.py tests/test_multi_market_post_import.py tests/test_multi_market_bulk_import.py tests/test_market_coverage.py tests/test_multi_market_outputs.py tests/test_multi_market_frontend_payload.py
# All checks passed
```

```bash
git diff --check
# passed with no output
```

```bash
git status --short
# dirty worktree with Layer 31/32 tracked edits and new Layer 31/32 files
```

## 22. Known Limitations

- Coverage is intentionally curated and partial, not exhaustive.
- No live refresh, scraping, crawling, scheduled import, or manual approval
  workflow exists.
- Frontend multi-market display is a discovery/coverage panel, not a broad new
  product area.
- The frontend build still reports the existing Vite chunk-size warning.

## 23. Final Lock Recommendation

LOCK_READY
