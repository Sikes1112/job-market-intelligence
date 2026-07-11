# Layer 31 Closeout

## 1. Layer Decision

Layer 31 is complete for the curated Greater NYC import path.

Decision: `LOCK_READY`

## 2. Confidence Level

High.

## 3. Executive Summary

Layer 31 establishes a deterministic curated-file import lifecycle for Greater
NYC. It validates fixture files, enforces provenance, preserves unknown-vs-zero
count semantics, writes source-backed canonical records idempotently, runs
post-import trust/risk/ranking evaluation, recomputes ranking-safe scores,
rebuilds backend outputs, and exposes public-safe imported-data labels in the
frontend.

No scraping, crawling, live API ingestion, scheduled imports, browser
automation, or manual approval workflow was added.

## 4. Files Inspected

- `backend/imports/*`
- `backend/outputs/payloads.py`
- `backend/outputs/region_output.py`
- `backend/outputs/company_output.py`
- `backend/outputs/comparison_output.py`
- `backend/outputs/service.py`
- `backend/api/routes.py`
- `backend/shared/provenance.py`
- `backend/shared/value_semantics.py`
- `backend/data_standards/ranking_gate.py`
- `backend/trust/explanations.py`
- `frontend/src/App.tsx`
- `frontend/src/types.ts`
- `frontend/src/dataQuality.ts`
- `frontend/src/styles.css`
- `frontend/package.json`
- Layer 31 validation/import/post-import/output/frontend tests

## 5. Files Changed

- `data/imports/nyc/regions.json`
- `data/imports/nyc/companies.csv`
- `data/imports/nyc/presence.csv`
- `data/imports/nyc/hiring.csv`
- `data/imports/nyc/entry_level.csv`
- `data/imports/nyc/source_refs.csv`
- `backend/imports/__init__.py`
- `backend/imports/contracts.py`
- `backend/imports/provenance.py`
- `backend/imports/validation.py`
- `backend/imports/result.py`
- `backend/imports/service.py`
- `backend/imports/nyc.py`
- `backend/imports/post_import.py`
- `alembic/versions/0035_curated_import_metadata.py`
- canonical model/service/provenance/trust/output files needed for additive
  import metadata and count-status preservation
- `frontend/src/App.tsx`
- `frontend/src/types.ts`
- `frontend/src/styles.css`
- `frontend/src/ImportedMarketDisplay.tsx`
- `frontend/src/importedMarketFormat.ts`
- `frontend/src/ImportedMarketDisplay.test.tsx`
- `tests/test_import_dataset_validation.py`
- `tests/test_curated_market_import.py`
- `tests/test_curated_market_post_import.py`
- `tests/test_layer31_frontend_payload.py`
- `docs/LAYER_31_IMPORT_CONTRACT.md`
- `docs/LAYER_31_CLOSEOUT.md`

## 6. 31.1 Import Dataset Contract Findings

The Greater NYC curated import contract is file-based and deterministic. It
defines region, company, presence, hiring, entry-level, and source-reference
records under `data/imports/nyc/`.

## 7. 31.2 Validation Findings

Validation enforces required files, required fields, IDs, source refs,
provenance fields, dates, confidence, freshness, duplicate facts, stale source
dates, supported source types, supported license categories, and count-status
encoding.

## 8. 31.3 Provenance Enforcement Findings

Every fact-bearing row must resolve to a valid source reference. Missing,
invalid, stale, unsupported, or incomplete provenance fails validation before
canonical writes.

Hard rule preserved: `No source, no canonical fact.`

## 9. 31.4 Company Import Findings

Companies import idempotently into canonical company records while preserving
company ID, name, classification, sector, eligibility, major-tech flags, source
links, and import provenance.

## 10. 31.5 Region + Presence Import Findings

Greater NYC imports as a canonical region. Company-region presence facts import
idempotently with presence basis, evidence flags, confidence, source refs, and
fact-source links.

## 11. 31.6 Hiring + Entry-Level Import Findings

Hiring and entry-level facts import idempotently with canonical count-status
columns. Unknown, not-collected, and not-applicable counts remain null with
explicit status values. Observed zero remains numeric `0` with
`zero_observed`.

## 12. 31.7 Trust Workflow Findings

Post-import refresh evaluates imported facts through existing Layer 30 trust
and risk services. It persists deterministic trust assessments and routing
decisions without adding manual approval queues.

## 13. 31.8 Score Recompute Findings

NYC scores are recomputed from ranking-eligible facts only. Stale or
insufficient-provenance facts are denied ranking influence and excluded from
score math.

## 14. 31.9 Output Rebuild Findings

NYC region, company, and supported comparison outputs rebuild through the
existing output service. Output top lists and summaries consume ranking-gated
facts.

## 15. 31.10 Frontend Display Findings

The frontend now displays public-safe imported-data metadata in existing
region, company, and comparison surfaces:

- `Real imported data`
- `Source-backed`
- `Partially covered`
- `Freshness: current/stale/unknown`
- `Trust: ...`
- `Risk: ...`
- `Ranking-safe` / `Ranking excluded`

Count rendering uses explicit count-status formatting.

## 16. Unknown-vs-Zero Findings

Unknown is not displayed or scored as zero. Not-collected and not-applicable
remain distinct from zero. Observed zero displays as `0 observed` and remains a
real sourced zero.

## 17. Ranking Protection Findings

Ranking-ineligible imported facts do not affect score math, output top lists,
recommendation inputs, or comparison inputs. They can remain labeled/explained
where safe, but are excluded from ranking influence.

## 18. Public Payload Safety Findings

Public payloads expose labels and booleans only. They do not expose trust
assessment IDs, risk routing IDs, reviewer notes, reporter identifiers,
freeform report text, exception internals, raw risk objects, or private
provenance internals.

## 19. Tests Run With Exact Commands And Results

- `python -m pytest tests/test_import_dataset_validation.py tests/test_curated_market_import.py tests/test_curated_market_post_import.py tests/test_layer31_frontend_payload.py`
  Result: 45 passed.
- `python -m pytest tests/test_outputs_service.py tests/test_output_handlers.py`
  Result: 49 passed.
- `python -m pytest tests/test_*trust*.py tests/test_*ranking*.py tests/test_provenance.py tests/test_provenance_freshness.py`
  Result: 48 passed.
- `python -m pytest tests/test_*scoring*.py`
  Result: 103 passed.
- `python -m ruff check backend/imports backend/outputs tests/test_import_dataset_validation.py tests/test_curated_market_import.py tests/test_curated_market_post_import.py tests/test_layer31_frontend_payload.py`
  Result: all checks passed.
- `cd frontend && npm test`
  Result: 25 test files passed, 126 tests passed.
- `cd frontend && npm run lint`
  Result: passed.
- `cd frontend && npm run build`
  Result: passed; Vite reported the existing large-chunk warning.
- `git diff --check`
  Result: passed.

## 20. Known Limitations

- Layer 31 covers curated Greater NYC fixtures only.
- It does not add scraping, crawling, live APIs, scheduled imports, or browser
  automation.
- It does not add manual approval workflows.
- Frontend display consumes current backend output surfaces; no broad redesign
  or new frontend route family was added.
- Vite build still reports a chunk-size warning, but the production build
  succeeds.

## 21. Final Lock Recommendation

`LOCK_READY`
