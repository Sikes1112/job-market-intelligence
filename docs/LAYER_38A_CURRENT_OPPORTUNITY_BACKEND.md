# Layer 38A Current Opportunity Backend

Layer 38A adds the backend foundation for production-current external
opportunities. It does not configure a real provider by itself; the exercised
source today is a deterministic curated/test adapter used to prove the
governed path end to end.

## Data Flow

The current opportunity path is:

```text
governed source
-> acquisition adapter
-> raw source observation
-> validation and normalization
-> canonical identity resolution
-> safe diff and promotion
-> current_opportunities
-> freshness/provenance/coverage evaluation
-> strategic matching
-> authenticated current opportunity APIs
```

Raw source observations are stored in `opportunity_source_observations`.
Canonical product records live in `current_opportunities`. The service never
mutates raw observations into canonical truth in place.

## Governance

`opportunity_data_sources` records machine-enforceable source policy:

- source id, provider, display name, source type, acquisition method
- enabled and operational status
- allowed-use, license/terms, and trust classifications
- freshness SLA
- supported markets and opportunity types
- display and ranking permissions
- refresh config and provenance requirements

Unknown, prohibited, disabled, untrusted, or non-display/non-ranking states fail
closed for ranking eligibility.

## Adapters

Adapters implement `OpportunityAcquisitionAdapter`. They acquire raw records and
transport metadata only. They do not normalize, resolve identity, promote
canonical records, or decide ranking eligibility. Supported categories are API,
feed, licensed source, employer contribution, and approved curated input.

`StaticOpportunityAdapter` is the deterministic test/curated adapter. It is not
a scraping framework and does not imply any live provider coverage.

## Identity And Dedupe

Layer 38A distinguishes:

- provider record identity: source/provider record id
- observation identity: source/run/provider/payload hash
- canonical identity: normalized company, title, market, employment type, and
  application route

Exact source-record replays are idempotent. Cross-source duplicate groups link
to one canonical opportunity when company/title/market/employment match.
Potential duplicates with same company/market/role family but different title
are flagged as low-confidence and remain separate. Provider id reuse with a
different identity is flagged instead of silently merged.

## Freshness And Ranking

Freshness is based on source observation time and governed source SLA, not row
`updated_at`. States are `fresh`, `aging`, `stale`, and `unknown`.

Ranking eligibility requires:

- active canonical status
- fresh or aging source data
- explicit source ranking and display permission
- allowed source use and non-prohibited license terms
- trusted source classification
- medium/high normalization and identity confidence
- coverage status of `production_ready` or `limited`
- active source link

Duplicate observations do not create additional canonical opportunities and do
not independently boost rank.

## Coverage And Diagnostics

`opportunity_coverage_contracts` evaluates coverage by market, role family, and
opportunity type. Supported statuses are `production_ready`, `limited`,
`experimental`, and `unsupported`. Unknown combinations are treated as
`unsupported`, and unsupported coverage never means no opportunities exist.

Diagnostics are derived for stale sources, disabled sources, failed refreshes,
repeated failures, source concentration, stale canonical opportunities, low
coverage, unsupported scopes, and ranking degradation when canonical
opportunities exist but none are eligible.

## APIs

Authenticated user-facing APIs:

- `GET /current-opportunities`
- `GET /current-opportunities/{opportunity_id}`
- `GET /current-opportunities/matches`
- `GET /current-opportunities/coverage`

Data-review/operator APIs:

- `GET /current-opportunities/diagnostics`
- `GET /current-opportunities/refresh-runs`

Responses expose normalized opportunity fields, freshness, provenance summaries,
coverage limitations, application route, and strategic match explanations. They
do not expose raw payloads, secrets, internal license text, or source
credentials.

## Layer 35/36/37 Integration

Strategic matching reads existing Career Identity facts, Career Decision rows,
and Strategic Career Review rows. It does not duplicate those systems or create
a separate strategy engine. Matching combines semantic fit with current-data
quality gates, so stale or ineligible opportunities cannot outrank valid
current opportunities.

## Layer 38B UX And Operations

Layer 38B adds the frontend surfaces that consume the Layer 38A contracts:

- `/markets/current-opportunities` shows authenticated users backend-ranked
  strategic current opportunities.
- `/markets/current-opportunities/{opportunity_id}` adds a detail panel for a
  selected canonical opportunity.
- `/markets/current-opportunities/operations` renders the restricted
  data-review view for diagnostics, scoped coverage, and recent refresh runs.

The user-facing page does not rebuild matching in React. It renders backend
match score bands as relevance signals, not probabilities, and uses backend
factors to explain Career Identity, decision, and strategy alignment. Direct
fits and adjacent strategic routes are labeled separately.

Freshness uses backend states only. Stale and unknown opportunities are visually
qualified and carry warnings or ranking-ineligibility reasons when the backend
returns them.

Coverage remains part of the product semantics:

- `production_ready` is shown as a strong current view for the selected scope.
- `limited` explains that absence of a match is not exhaustive.
- `experimental` explains that the scope is still being evaluated.
- `unsupported` states that current coverage is not supported and cannot prove
  that no opportunities exist.

Application links are treated as untrusted external data in the frontend as
well as the backend. Only `http` and `https` URLs are rendered as external links
with `rel="noopener noreferrer"`; malformed, `javascript:`, and `data:` routes
are omitted.

The operations page renders diagnostics and refresh receipts from Layer 38A. It
does not recompute source health, coverage degradation, or ranking diagnostics
client-side, and it does not expose raw provider payloads, credentials, or
internal license text.

## Current Source Reality

No real external opportunity provider is configured in this repository state.
The deterministic `StaticOpportunityAdapter` and the
`greater_boston/software_engineering/job` coverage fixture are test-only proof
points for the governed pipeline. Infrastructure readiness is not the same as
real-source production coverage.
