# Layer 21 - Predictive Labor-Market Intelligence

Layer 21 moves the product from current-state labor-market explanation toward
bounded, evidence-backed forecasting.

Batch 21A implements the core deterministic predictive foundation. Batch 21B
adds predictive report assembly, an API-safe read surface, public frontend
rendering, and Layer 21 closeout. Forecasts remain bounded directional signals
from historical producer exports and public-safe payloads.

## 21A Scope

Implemented:

- neutral predictive observation contracts in `backend/predictive/contracts.py`
- deterministic historical trend modeling
- emerging-market signal classification
- early-warning signal detection
- reusable structured forecast confidence
- public-safe reasoning trails, source basis, historical depth, and uncertainty
- focused tests for trend, emerging, warning, confidence, and isolation behavior

Not implemented in 21A:

- public predictive report generation
- frontend predictive report rendering
- new database tables or migrations
- live external data fetching
- raw scraping or raw job-record ingestion
- recommendation ranking changes
- market coverage authority changes
- geography, employer, source, institution, or public-report authority changes

## 21B Scope

Implemented:

- predictive report contracts in `backend/predictive/contracts.py`
- deterministic report builder logic in `backend/predictive/reports.py`
- a producer-owned export adapter in
  `backend/platform_intelligence/predictive_exports.py`
- API-safe report route at `GET /platform/predictive/reports`
- public demo access for the predictive report route
- frontend predictive report types in `frontend/src/types.ts`
- frontend API client helper in `frontend/src/api.ts`
- public `/forecasts` route and forecast card rendering in `frontend/src/App.tsx`
- frontend and backend tests for payload safety, metadata preservation,
  insufficient evidence, API behavior, rendering, and layer isolation

21B does not add persistence, migrations, scheduled generation, live external
fetching, nondeterministic model calls, or ownership over employer, geography,
recommendation, institution, scraping, public report, or raw historical storage
authority.

## Input Boundary

Layer 21A consumes `HistoricalMetricObservation` rows. These are neutral,
producer-safe observations that may be built from:

- append-only historical exports
- API-safe historical payloads
- public-safe payloads
- governed fixtures in tests
- future producer-owned export adapters

The contract carries source categories, source counts, confidence scores,
freshness states, coverage tiers, observed dates, and metric values. It does not
carry raw source identifiers, raw scrape records, internal formula weights,
admin metadata, private user data, or source-version internals.

The 21B platform-intelligence adapter is producer-owned by the historical
intelligence layer. It exports only neutral `HistoricalMetricObservation`
payloads from market, sector-region, and company-region snapshots. Layer 21
does not query raw source records and does not become the storage owner.

## Historical Trend Modeling

Implemented trend types:

- company expansion
- hiring growth
- hiring contraction
- internship seasonality
- regional score movement
- sector-specific growth

Trend modeling is deterministic. For each entity and metric, the service orders
historical observations by observed date, calculates interval movement, net
change, magnitude, amplitude, positive intervals, negative intervals, and flat
intervals.

Trend outputs include:

- direction
- magnitude
- time window
- historical depth
- supporting evidence
- source basis
- structured confidence
- known uncertainty
- public-safe reasoning trail

Insufficient trend evidence is not upgraded into a confident claim. A single
observation produces no trend; two or three observations may produce an
insufficient-data trend with degraded confidence.

## Emerging Market Detection

Implemented emerging-market signal types:

- rising AI market
- new cloud hub
- cybersecurity growth region
- product role expansion region
- underpriced opportunity market

Emerging labels are applied only when the observed metric movement supports a
rising classification. Stable, weakening, noisy, and insufficient-data cases
remain classified without receiving an emerging label.

Underpriced opportunity markets are framed as opportunity signals. They are not
presented as certain outcomes, and their confidence is capped because the label
is interpretive.

## Early Warning Signals

Implemented warning types:

- company hiring slowdown
- regional market weakening
- internship pipeline contraction
- sector cooling
- overheated market

Warning statuses:

- confirmed weakening
- possible weakening
- overheating
- insufficient evidence

Default warning detection does not emit warnings when evidence is too thin. The
service can include insufficient-evidence assessments for diagnostic/test use,
but API/report surfaces should keep those separate from actual warnings unless
there is a specific disclosure requirement.

Warning summaries use bounded language such as "possible weakening" and
"historical observations show". They avoid alarmist claims.

## Forecast Confidence

Every emitted predictive payload includes:

- `confidence`: structured level, score, and degradation factors
- `source_basis`: data basis, source categories, source count, observed metrics,
  coverage tiers, freshness states, and notes
- `historical_depth`: observation count, period count, evidence window, and
  latest observation date
- `uncertainty`: known uncertainties, limitations, uncertainty level, and
  boundedness
- `reasoning_trail`: public-safe reasoning steps

Confidence degrades when evidence is:

- thin
- shallow in time
- stale
- contradictory
- narrow
- overly concentrated
- missing input confidence
- low confidence at the input layer
- unknown in data basis
- interpretation-bounded

Confidence is deterministic and does not use nondeterministic ML behavior.

## Predictive Reports

Layer 21B report payloads reuse 21A trend, emerging-market, warning,
confidence, source-basis, historical-depth, uncertainty, and reasoning
contracts.

Implemented predictive report sections:

- AI role market growth forecasts
- entry-level tech access weakening forecasts
- company early-career hiring expansion forecasts
- sector cooling and overheated condition forecasts
- underpriced opportunity market forecasts

Every forecast includes:

- forecast title and label
- forecast type
- affected entity or market
- time horizon
- structured confidence
- source basis
- historical depth
- uncertainty
- public-safe reasoning trail
- supporting signal summaries
- safe display summary
- explanation for why the forecast exists

Weak evidence is rendered as low-confidence or insufficient-data messaging.
Warning copy distinguishes confirmed weakening, possible weakening,
overheating, and insufficient evidence without alarmist wording. Underpriced
markets are framed as opportunity signals with capped confidence.

## API And Frontend Surfaces

The API surface is:

- `GET /platform/predictive/reports`

The endpoint accepts optional repeated `region_id` and `company_id` query
parameters and returns a lightweight success envelope containing
`PredictiveReportPayload`. The endpoint builds the report on demand from
producer-owned history exports and does not persist report snapshots.

The frontend surface is:

- `/forecasts`

The public forecast route renders report metadata, forecast cards, confidence
level and score, time horizon, historical depth, source basis, uncertainty,
reasoning trail, and supporting signals. Cards explicitly label forecasts and
avoid certainty language.

## Boundary Rules

Layer 21A may:

- define neutral predictive contracts
- consume neutral historical observations
- compute deterministic trend/emerging/warning outputs
- explain confidence and uncertainty in public-safe language
- expose service outputs to future API/report layers through explicit adapters

Layer 21A must not:

- own raw scraping or raw job collection
- own employer authority
- own geography or market coverage authority
- own recommendation ranking
- own public report publication
- mutate canonical regions, companies, scores, recommendations, reports, or
  platform API records
- import domain-owned service internals
- introduce hidden global state, external fetching, or nondeterministic ML

Layer 21B may:

- assemble predictive reports from 21A outputs
- expose API-safe read payloads through existing route patterns
- render public-safe forecast cards
- use producer-owned historical export adapters
- preserve confidence, uncertainty, source basis, historical depth, and
  reasoning trail across report boundaries

Layer 21B must not:

- weaken or remove confidence and uncertainty fields
- expose internal-only or raw source fields
- own public report publication authority
- own employer, geography, recommendation, institution, scraping, or raw history
  authority
- create hidden global state, live scraping, or nondeterministic model behavior

## Deferred Work

Deferred beyond Layer 21 closeout:

- scheduling or refresh integration through existing orchestration boundaries
- persisted predictive report snapshots, if a producer-owned storage pattern is
  later approved
- institutional predictive report packaging beyond the current API-safe payload
- recurring distribution and review workflow
- broader product-specific forecast filters and comparison views

Future work must not relax Layer 21 confidence, uncertainty, or source-safety
rules.
