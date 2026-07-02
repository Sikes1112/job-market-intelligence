# Layer 21 Closeout - Predictive Labor-Market Intelligence

Layer 21 is lock-ready after the final validation audit.

## Decision

LOCK_READY

Layer 21A provides deterministic predictive contracts, confidence scoring,
historical trend modeling, emerging-market detection, and early-warning signal
detection. Layer 21B exposes those outputs through predictive report payloads,
an API-safe read endpoint, and public frontend rendering.

## Responsibility

Forecasts are labeled as forecasts and described as bounded directional signals
from historical evidence. Forecast copy avoids certainty language, warning copy
uses non-alarmist language, and underpriced opportunity markets are framed as
opportunity signals with capped confidence.

Weak or insufficient evidence produces low-confidence or insufficient-data
messaging. Forecasts do not promise hiring, compensation, market outcomes, or
applicant outcomes.

## Evidence And Confidence

Predictive outputs are derived from neutral historical observations,
producer-owned exports, and Layer 21A trend, emerging-market, or warning
signals. Every emitted predictive forecast preserves:

- structured confidence level and score
- confidence factors
- source basis
- historical depth
- known uncertainty
- reasoning trail
- supporting signals

Confidence degrades for thin, stale, contradictory, narrow, concentrated, low
input-confidence, unknown-basis, and interpretation-bounded evidence.

## Surfaces

- Backend report builder: `backend/predictive/reports.py`
- Producer-owned export adapter:
  `backend/platform_intelligence/predictive_exports.py`
- API endpoint: `GET /platform/predictive/reports`
- Frontend route: `/forecasts`

The API returns public-safe payloads only. The frontend renders forecast label,
confidence level and score, time horizon, historical depth, source basis,
uncertainty, reasoning trail, and supporting signals.

## Boundary Decision

Layer 21 consumes neutral contracts, Layer 21A outputs, producer-owned exports,
and API-safe payloads. It does not own raw scraping, employer authority,
geography authority, recommendation authority, public report authority,
institution authority, persistence, scheduled refresh, or external data
fetching.

The predictive package remains isolated from route handlers, storage internals,
raw sources, public report authority, recommendation systems, external clients,
and nondeterministic ML libraries.

## Validation

The final audit validated:

- predictive report generation from Layer 21A outputs
- public/API-safe payload shape
- confidence, source basis, historical depth, uncertainty, and reasoning
  preservation
- insufficient-data and low-confidence behavior
- deterministic repeated filter handling
- public frontend forecast rendering
- warning copy safety
- layer isolation
- adjacent public, platform, and institutional report regressions

## Deferred Non-Blocking Work

- persisted predictive report snapshots
- scheduled predictive report refresh
- institutional predictive report packaging beyond current API-safe payloads
- recurring review and distribution workflow
- richer forecast filtering, comparison, and saved-view UX

These items are intentionally out of scope for Layer 21 lock readiness.

## Final Status

Layer 21 is complete and lock-ready.
