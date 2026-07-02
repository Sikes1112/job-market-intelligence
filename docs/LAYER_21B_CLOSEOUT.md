# Layer 21B Closeout - Predictive Reports And Surfaces

Layer 21B is implemented as an API-safe reporting and rendering layer on top of
the Layer 21A deterministic predictive foundation.

## Implemented

- `backend/predictive/contracts.py`
- `backend/predictive/reports.py`
- `backend/platform_intelligence/predictive_exports.py`
- `backend/api/platform_intelligence.py`
- `backend/api/protection.py`
- `frontend/src/types.ts`
- `frontend/src/api.ts`
- `frontend/src/urlState.ts`
- `frontend/src/publicContent.ts`
- `frontend/src/App.tsx`
- `frontend/src/styles.css`

The batch completes Slice 21.5 predictive reports.

## Architecture Decision

Layer 21B reuses Layer 21A trend, emerging-market, warning, confidence,
source-basis, historical-depth, uncertainty, and reasoning contracts. The report
builder consumes 21A outputs and emits a single public-safe
`PredictiveReportPayload`.

Historical input is supplied through a producer-owned platform-intelligence
adapter that converts market, sector-region, and company-region snapshots into
neutral `HistoricalMetricObservation` rows. Layer 21 does not own raw
collection, historical storage, employer authority, geography authority,
recommendation authority, institution authority, or public report authority.

## Surfaces

- API: `GET /platform/predictive/reports`
- Frontend: `/forecasts`

The API endpoint returns forecast title, forecast type, affected entity, time
horizon, confidence, source basis, historical depth, uncertainty, reasoning
trail, supporting signals, and safe display summary. The public frontend renders
the same metadata in forecast cards.

## Bounded Forecast Behavior

Forecasts are labeled as forecasts and described as directional signals from
historical evidence. Weak evidence produces low-confidence or insufficient-data
messaging. Warning cards use bounded language for confirmed weakening, possible
weakening, overheating, and insufficient evidence. Underpriced opportunity
markets are framed as opportunity signals with capped confidence.

Every predictive report forecast preserves:

- structured confidence level, score, and factors
- source basis
- historical depth
- uncertainty
- reasoning trail
- supporting signal summaries

## Boundary Audit

The predictive package remains isolated from API internals, raw scraping,
domain-owned storage internals, recommendation systems, geography authority,
employer authority, public-report authority, external clients, and ML libraries.

The API route imports the platform-intelligence export adapter and report
builder, then serializes the public-safe payload. Frontend code consumes only
the API payload shape and does not infer forecast certainty.

## Validation

Targeted validation is covered by:

- `tests/test_predictive_reports.py`
- `tests/test_predictive_confidence.py`
- `tests/test_predictive_intelligence_service.py`
- `tests/test_layer_isolation_slice21.py`
- updated `tests/test_smoke_imports.py`
- `frontend/src/api.test.ts`
- `frontend/src/predictiveReports.test.tsx`

Adjacent regression coverage was run for public reports, public benchmarks,
platform public APIs, platform-intelligence history/signals/reports, and
institutional report data requests.

## Deferred

- persisted predictive report snapshots
- scheduled predictive report refresh
- institutional predictive report packaging beyond the API-safe payload
- recurring review and distribution workflow
- broader forecast filtering, comparison, and saved-view UX

No live scraping, nondeterministic model calls, hidden global state, or new
persistence were added.

## Closeout Decision

Layer 21 is ready to validate as complete. Layer 21A provides the deterministic
forecasting foundation, and Layer 21B exposes bounded predictive intelligence
through API-safe reports and public frontend rendering while preserving
confidence, uncertainty, provenance, historical depth, and layer isolation.
