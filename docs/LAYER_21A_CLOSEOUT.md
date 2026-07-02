# Layer 21A Closeout - Core Predictive Labor-Market Intelligence

Layer 21A is implemented as a neutral deterministic backend foundation.

## Implemented

- `backend/predictive/contracts.py`
- `backend/predictive/confidence.py`
- `backend/predictive/signals.py`
- `backend/predictive/service.py`
- `backend/predictive/__init__.py`

The batch covers:

- Slice 21.1 historical trend modeling
- Slice 21.2 emerging market detection
- Slice 21.3 early warning signals
- Slice 21.4 forecast confidence

## Architecture Decision

Layer 21A does not create persistence, routes, public reports, or frontend UI.
It consumes neutral `HistoricalMetricObservation` payloads and produces
API-safe predictive payloads. This keeps predictive logic separate from raw
scraping, canonical employer/geography/scoring authority, recommendation
authority, institutional reports, public reports, and the Layer 20 Platform API.

## Confidence And Uncertainty

Forecast confidence is structured, reusable, and deterministic. It includes a
bounded qualitative level, numeric score, and factor list. It degrades for thin,
stale, contradictory, narrow, concentrated, unknown, or low-confidence evidence.

Every trend, emerging-market signal, and warning carries confidence, source
basis, historical depth, known uncertainty, and a public-safe reasoning trail.

## Boundary Audit

Layer 21A modules import only neutral/shared dependencies and their own package.
The isolation regression test blocks imports from API routes, domain-owned
services/models, platform-intelligence storage internals, public reports,
recommendations, ingestion, refresh/orchestration runtime, external clients,
scraping tools, and ML libraries.

No route handlers, worker registration, external network calls, hidden global
state, or raw source/private payload fields are introduced.

## Validation

Targeted validation is covered by:

- `tests/test_predictive_confidence.py`
- `tests/test_predictive_intelligence_service.py`
- `tests/test_layer_isolation_slice21.py`
- updated `tests/test_smoke_imports.py`

The tests cover sufficient-evidence trend modeling, insufficient trend
evidence, rising/stable/weakening/noisy/insufficient emerging cases,
underpriced opportunity confidence caps, weakening warnings, overheated market
warnings, warning suppression for thin evidence, confidence degradation, common
forecast metadata, and layer isolation.

## Deferred To Layer 21B

- predictive reports
- public/institutional report integration
- broad frontend integration
- API endpoint wiring
- persistence or scheduled generation
- adapters from Layer 18 storage exports into Layer 21A neutral observations
- distribution and review workflows

## Closeout Decision

Layer 21A is ready to validate as the core predictive intelligence foundation.
It should remain locked behind neutral contracts until Layer 21B adds explicit
safe adapters and report/API surfaces.
