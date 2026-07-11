# Layer 33 Import Operations and Dataset Maintenance

Layer 33 adds read-only operational intelligence and lightweight frontend
visibility for registered curated import markets. It does not import, refresh,
scrape, schedule, approve, or mutate canonical records. Write behavior remains
limited to the explicit Layer 31/32 import and post-import functions.

## Backend Architecture

- `backend/imports/schemas.py` defines stable public-safe enums and DTOs for
  health, source aging, fact health, coverage gaps, ranking exclusions, refresh
  readiness, and diff previews.
- `backend/imports/operations.py` builds one normalized market operational
  snapshot. The snapshot reads the registry, validation result, canonical rows,
  source references, fact-source links, source-file rows, and actual ranking-gate
  outcomes once per market.
- `backend/imports/diagnostics.py` builds the individual reports from the shared
  snapshot.
- `backend/imports/diff.py` compares the current canonical imported state with
  the current curated source files. It performs no writes and uses in-memory
  Layer 30 trust/risk evaluation to preview proposed ranking influence changes.
- `backend/api/routes.py` exposes narrow public-safe read routes under
  `/markets/imported`.
- `frontend/src/ImportedMarketOperations.tsx` renders the Layer 33 operational
  overview, per-market diagnostics, refresh-readiness distinction, and diff
  preview in the existing imported-market Explore surface.
- `frontend/src/api.ts` exposes typed public GET helpers for each Layer 33 route
  plus a client-side bundle helper that calls only those read-only routes.
- `frontend/src/types.ts` mirrors the public backend schemas using the backend's
  snake_case field names to avoid a parallel frontend data model.

## Report Types

- Dataset health: market-level validation, counts, freshness, ranking, and next
  action.
- Source aging: source-level current/aging/stale/expired/needs-review status,
  age, fact usage, affected areas, and ranking impact.
- Fact health: fact-level and aggregate unknown, observed-zero, stale,
  low-confidence, weak-source, and ranking status.
- Coverage gaps: deterministic gaps with severity, counts, and specific
  recommended actions.
- Ranking diagnostics: public reason categories derived from actual Layer 30B
  routing/gate outcomes.
- Refresh readiness: readiness status, blockers, warnings, actions, expected
  impact, and deterministic maintenance priority.
- Diff preview: source-file versus canonical diff with semantic-risk warnings.

## Health Rules

Top-level health uses explicit precedence:

1. `validation_failed`
2. `stale_sources`
3. `ranking_limited`
4. `limited_coverage`
5. `needs_refresh`
6. `healthy`

Validation failures are never hidden by lower-priority coverage or ranking
warnings.

## Freshness Rules

Layer 33 reuses Layer 31 import staleness (`365` days) and canonical
`fresh/stale/unknown` freshness labels. Operational source aging adds public
maintenance labels:

- `current`: observed within the normal window.
- `aging`: at or beyond 75% of the import staleness window.
- `stale`: older than the import staleness window or explicitly stale.
- `expired`: older than twice the import staleness window.
- `needs_review`: missing/unknown freshness metadata.

Tests pass a fixed `as_of` date so age output is deterministic.

## Coverage Gap Rules

Layer 33 uses explicit constants matching the current Layer 32 seed standard:

- at least 3 companies
- at least 5 source references
- at least 3 presence facts
- at least 3 hiring facts
- at least 3 entry-level facts

It also detects missing internship/co-op data, missing 30-day and 90-day hiring
counts, high unknown ratios, excessive ranking exclusions, no comparison-ready
facts, no strong early-career signal, and concentrated dependency on weak or
stale sources.

## Ranking Diagnostic Safety

Ranking diagnostics call the actual ranking gate and read persisted Layer 30B
routing decisions. They do not approximate ranking eligibility in report paths.
Internal IDs, reviewer details, reporter IDs, raw risk objects, trust rows, and
private provenance internals are not serialized. Internal reason codes are
translated into stable public categories such as `stale_source`,
`low_confidence`, `insufficient_evidence`, `source_not_allowed`, and
`trust_or_risk_limited`.

## Refresh Readiness

Readiness consumes health, source aging, fact health, coverage gaps, and ranking
diagnostics. It does not recompute a contradictory rule set. Status values are:

- `ready`
- `needs_source_refresh`
- `needs_coverage_expansion`
- `needs_validation_fix`
- `needs_ranking_review`
- `not_ready`

Validation failures classify as `needs_validation_fix`. Multiple non-validation
blocker classes classify as `not_ready`. Maintenance priority is scored
deterministically and ties sort by market key.

Health and refresh readiness are distinct. Health describes current dataset
quality and coverage. Refresh readiness describes whether current curated files
can be safely re-imported. A market can therefore be `limited_coverage` and
`ready` at the same time.

## Diff Semantics

Diff preview compares canonical imported rows with current source files for:

- companies
- regions and market identity
- source references
- presence facts
- hiring facts
- entry-level facts

It flags dangerous semantic changes including unknown-to-zero, zero-to-unknown,
removed sources still used by canonical facts, company identity mismatch, region
or market-key mismatch, cross-market source leakage, ranking eligibility flips,
freshness degradation, material source coverage loss, and validation failure.
The preview does not require approval and does not mutate records.

## Unknown-Vs-Zero Protection

Unknown, not-collected, not-applicable, observed-zero, and positive-observed
statuses remain distinct. Reports never infer zero from absence. Diff preview
explicitly warns when unknown-like statuses become observed zero or observed zero
becomes unknown-like.

## Determinism

Layer 33 output uses stable sorting, stable enum values, explicit tie-breaking,
fixed test clocks, no random IDs, and no filesystem traversal ordering. Repeated
calls with identical canonical and source inputs return identical serialized
payloads.

## Read-Only Guarantees

Operational reports and diff previews do not write database rows, curated files,
registries, trust/risk state, ranking state, provenance state, source refs, or
audit/user-report records. Tests assert repeated calls leave table counts and
source files unchanged.

## API Routes

- `GET /markets/imported`
- `GET /markets/imported/health`
- `GET /markets/imported/{market_key}/health`
- `GET /markets/imported/{market_key}/sources`
- `GET /markets/imported/{market_key}/facts`
- `GET /markets/imported/{market_key}/gaps`
- `GET /markets/imported/{market_key}/ranking-diagnostics`
- `GET /markets/imported/{market_key}/refresh-readiness`
- `GET /markets/imported/{market_key}/diff-preview`

The all-market health route includes a compact platform summary with registered
market count, healthy count, limited-coverage count, markets needing refresh,
stale-source totals, ranking-excluded totals, highest-priority maintenance
market, next action, and aggregate health status.

All Layer 33 maintenance routes are public-demo approved GET routes. Public-demo
protection still denies POST/write-shaped variants and unknown maintenance
actions.

## Frontend Visibility

The frontend extends the existing Explore Markets imported coverage card. It
does not add a broad admin console or approval workflow.

The operations panel renders:

- platform-level imported-data health counts and highest-priority market
- per-market health, freshness, counts, unknown facts, observed-zero facts,
  ranking-excluded count, coverage-gap count, maintenance priority, and next
  action
- source aging counts and important stale/aging source explanations
- fact-health counts for ranking eligibility, unknown, observed zero,
  low-confidence, stale, and weak source coverage
- coverage gaps by public message, severity, affected area, metrics, impact, and
  recommended action
- ranking-exclusion zero state or public reason categories and affected areas
- refresh readiness with blockers, warnings, ordered actions, expected impact,
  and priority
- diff preview with visible "Preview only. No imported data has been changed."
  language, risk, narrative summary, blockers, warnings, summary counts, and
  deterministic detailed changes

Status labels use deterministic mappings for every known backend health,
readiness, source-aging, diff-risk, severity, and priority value. Unknown future
enum values render a neutral fallback instead of crashing.

## Public Redaction

Responses avoid raw paths, stack traces, internal trust/risk IDs, reviewer notes,
reporter IDs, freeform user reports, raw risk objects, and private provenance
internals. Invalid market keys return the project-standard not-found envelope.

The frontend does not dump raw operational JSON. It renders only explicit public
fields and filters unsafe nested keys or strings before displaying supporting
metrics, diff before/after values, warnings, and error text.

## Hard Boundaries

Layer 33A introduces no scraping, web crawling, browser automation, live external
API integration, scheduler, background import worker, automatic source refresh,
manual approval queue, reviewer assignment, owner approval workflow, or write-mode
maintenance action.

## Tests Added

`tests/test_import_operations_layer33.py` covers:

- all eight market health reports
- source aging classifications
- fact health counts and unknown/zero semantics
- coverage gaps and recommended actions
- ranking diagnostics and public reason categories
- refresh readiness statuses and deterministic priority ordering
- diff-preview dangerous semantic changes
- repeated diff/report read-only behavior
- API route shape and nested redaction
- hard-boundary checks for no network/scraping/scheduler/approval workflow

Batch 33B adds:

- `frontend/src/ImportedMarketOperations.test.tsx` for overview rendering,
  every supported enum mapping, health/readiness distinction, source aging,
  coverage gaps, ranking diagnostics, diff preview, loading/error/empty/partial
  states, unknown enum fallback, and nested payload redaction
- `frontend/src/api.test.ts` coverage for every Layer 33 public GET helper and
  the client-side operations bundle
- `tests/integration/test_frontend_api_contract.py` coverage for backend fields
  rendered by the frontend and route-contract stability
- `tests/test_public_demo_environment.py` coverage for read-only public-demo
  allowlisting of Layer 33 routes

## Known Limitations

Layer 33 is diagnostic visibility only. It does not refresh external sources,
collect live data, schedule imports, apply diff previews, approve imports,
override ranking, or persist preview trust/risk assessments. Diff preview
predicts proposed ranking influence using in-memory Layer 30 trust/risk services
but does not persist preview assessments. The frontend is intentionally compact
and lives inside the existing imported-market surface rather than a broad admin
application.
