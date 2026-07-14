# Layer 34 - Market Intelligence Engine and Frontend Experience

Layer 34 adds a read-only market intelligence layer over the curated market
system completed in Layers 31-33. It transforms imported facts, existing region
scores, ranking eligibility, freshness, confidence, and Layer 33 diagnostics into
public-safe market profiles, comparisons, goal-aware rankings, explanations, and
a user-facing frontend experience.

Batch 34A implemented the backend intelligence engine and public GET APIs. Batch
34B wires those contracts into the frontend without adding writes, scraping,
approval workflows, or client-side scoring. Batch 34C hardens the intelligence
quality layer with calibration, evidence sufficiency, robustness, contradiction,
grounding, differentiation, explanation-quality, and product-evaluation outputs
for independent audit.

## Backend Architecture

The implementation lives in `backend/market_intelligence/`:

- `schemas.py` defines stable public DTOs and enums.
- `goals.py` defines supported career goals and deterministic component weights.
- `scoring.py` derives confidence-aware metrics from Layer 33 operational
  snapshots and stored `RegionMarketScore` rows.
- `profiles.py` builds multi-dimensional market intelligence profiles.
- `comparisons.py` builds pairwise comparison reports over explainable rankings.
- `calibration.py` builds deterministic market-goal calibration matrices.
- `sufficiency.py` derives comparison-ready, limited, insufficient, and
  unsupported evidence states.
- `robustness.py` evaluates deterministic sensitivity scenarios over ranked
  results.
- `differentiation.py` detects templated or insufficiently differentiated
  profile and ranking language.
- `explanations.py` builds comparative, evidence-specific explanation text.
- `contradictions.py` detects blocking conflicts across ranking, sufficiency,
  confidence, freshness, and explanation outputs.
- `grounding.py` exposes public-safe direct/proxy evidence grounding.
- `adversarial_fixtures.py` provides synthetic, non-production fixtures for
  quality stress tests.
- `evaluation.py` composes the Layer 34C product-quality evaluation report.
- `service.py` orchestrates snapshots, profiles, rankings, comparisons, and
  career-goal recommendations.

The API router lives in `backend/api/market_intelligence.py` and is included by
`backend/api/app.py`.

## Frontend Architecture

The frontend experience is implemented in:

- `frontend/src/MarketIntelligencePage.tsx`, a focused user-facing route for
  goal rankings, market profiles, and pairwise comparisons.
- `frontend/src/marketIntelligenceModel.ts`, the single frontend presentation
  mapping for career goals, confidence, freshness, comparison outcomes, metric
  labels, safe text handling, and unknown-enum fallbacks.
- `frontend/src/api.ts`, which exposes narrow typed helpers for the Layer 34 GET
  routes.
- `frontend/src/types.ts`, which mirrors the public backend response contracts.
- `frontend/src/urlState.ts`, which adds shareable `/markets/intelligence`
  route state for selected goal, selected market, and comparison markets.

The frontend displays backend-provided rankings, confidence, freshness,
limitations, and ranking drivers. It does not recompute scores, confidence, or
ranking order in the browser.

## Source Systems Consumed

Layer 34A consumes existing systems rather than replacing them:

- Layer 31 canonical company, region, source, presence, hiring, and entry-level
  rows.
- Layer 32 registry-backed multi-market snapshots for all ready markets.
- Layer 33 operational snapshots, dataset health, coverage gaps, source aging,
  fact health, ranking diagnostics, and refresh-readiness signals.
- Existing stored region market scores from `RegionMarketScore`.
- Existing ranking eligibility, trust/risk routing outcomes, freshness, and
  confidence semantics exposed through Layer 33 public-safe snapshots.

No new canonical table, cache, migration, or denormalized source of truth is
introduced.

## Market Profiles

Each market profile includes:

- Overview text.
- Strength insights with public-safe evidence.
- Weakness insights with public-safe evidence.
- Hiring summary.
- Employer summary.
- Internship summary.
- Co-op summary.
- Early-career summary.
- Opportunity environment summary.
- Confidence label and confidence score.
- Freshness label.
- Coverage summary.
- Public limitations.
- Supporting metrics.

Profiles only use canonical facts and diagnostics. Missing values remain
unknown or not collected. Unknown is never treated as observed zero.

The frontend renders profiles as structured sections: market overview, key
strengths, known weaknesses, opportunity environment, supporting evidence,
confidence/freshness, and visible limitations. Strengths and weaknesses are only
rendered when returned by the backend.

## Comparison Engine

The comparison engine builds explainable rankings, then compares markets using
the ranked items. Every comparison includes:

- Career goal.
- Market A and Market B summaries.
- Winner or tie outcome.
- Public explanation.
- Confidence.
- Supporting metrics.
- Limitations.

Tie handling is deterministic. Equal scores return `tie`; ranking lists sort by
confidence-adjusted score descending and then market key.

The frontend pairwise comparison UI lets users choose two distinct markets. It
renders the backend outcome directly, including neutral tie language. It prevents
same-market comparisons from calling the comparison API.

## Career Goal Intelligence

Supported goals are:

- `software_engineering`
- `product_management`
- `ai_ml`
- `cybersecurity`
- `data_science`

Goal definitions live in `goals.py`, separate from route code. Each goal has a
public label, description, direct signals, and deterministic component weights.
The data-science goal explicitly reports that direct data-science role-family
facts are not collected in the current curated datasets.

The frontend uses backend goal definitions where available and a single fallback
mapping for the five current goals. Unknown future goals display a neutral
unsupported-goal fallback and do not crash the route.

## Layer 34C Quality Hardening

Layer 34C adds registry-backed, goal-specific evidence definitions and four
evidence sufficiency states: `comparison_ready`, `limited_evidence`,
`insufficient_evidence`, and `not_supported`. Normal recommendations require
backend-derived sufficiency; provisional and abstaining states are displayed as
such in the frontend.

The quality layer evaluates all registered market-goal combinations for
calibration, score margins, ties and near ties, stability, public-safe
direct/proxy grounding, limitations, contradiction status, explanation quality,
and differentiation findings. Data science remains explicitly unsupported for
authoritative recommendations until direct data-science role-family evidence is
available in canonical data.

The machine-readable product-quality evaluation artifact for audit lives at
`docs/implementation/layer_34c/artifacts/product_quality_evaluation_report.json`.
It is generated from the read-only `MarketIntelligenceService` report object
over seeded curated market data and contains the expected 40 market-goal
results for the current eight markets and five goals.

## Opportunity Environment

Opportunity summaries describe:

- Hiring activity.
- Employer diversity.
- Internship ecosystem.
- Co-op ecosystem.
- Early-career support.
- Hiring momentum.
- Overall environment.

The engine does not infer unsupported trends. Hiring momentum is only described
from observed canonical activity; no trend is fabricated from missing or unknown
counts.

## Explainable Rankings

Rankings include driver objects with:

- Stable code.
- Label.
- Contribution.
- Evidence.

Drivers are sorted by contribution descending and then code. Ranking items also
include strengths, weaknesses, confidence, freshness, limitations, and supporting
metrics. Raw trust/risk/provenance objects are never returned.

The frontend preserves backend driver ordering. Contributions are labeled as
relative comparative contributions, not probabilities, and raw JSON is never used
as the primary UI.

## Confidence Model

Confidence is derived from Layer 33 diagnostics:

- Validation failures reduce confidence.
- Stale or expired sources reduce confidence.
- Aging sources reduce confidence.
- Unknown fact ratios reduce confidence.
- Ranking-limited facts reduce confidence.
- High and medium coverage gaps reduce confidence.
- Low-confidence facts reduce confidence.

Confidence labels are:

- `high`
- `moderate`
- `low`
- `limited`

Recommendations are confidence-aware: the final score applies confidence,
freshness, and ranking-eligibility factors to the goal score.

The frontend presents confidence as first-class status text with concise public
meaning and visible limiting factors. Low or limited confidence is not hidden and
is not conveyed by color alone.

## Freshness Model

Freshness labels are:

- `current`
- `aging`
- `stale`
- `unknown`

Freshness is derived on the backend from Layer 33 source-aging diagnostics and
supporting fact state. The frontend renders freshness as explanatory status text
and never fetches, validates, or refreshes external sources from the browser.

## Limitations and Coverage

Every intelligence surface has a visible limitations area. Typical limitations
include missing direct role-family evidence, limited co-op or internship
coverage, unknown fact ratios, stale sources, ranking exclusions, and
insufficient comparison-ready evidence. Limitations are backend-derived and are
not hidden behind hover-only UI.

## Public APIs

Layer 34 exposes read-only GET routes:

- `GET /market-intelligence`
- `GET /market-intelligence/{market_key}`
- `GET /market-comparisons`
- `GET /market-comparisons/{market_a}/{market_b}`
- `GET /career-goal-comparisons`
- `GET /career-goal-comparisons/{goal}`

All responses use the existing lightweight success/error envelope conventions.
Invalid markets return a project-standard not-found envelope. Invalid goals
return a validation-error envelope.

The public-demo route allowlist permits these GET routes only. No write routes
are introduced.

## Frontend Routes

The market intelligence experience is available at:

- `/markets/intelligence`

The route supports shareable URL state:

- `goal`
- `market`
- `compare_a`
- `compare_b`

The existing product navigation includes a compact Market Intelligence entry in
the market exploration area. No broad admin console or duplicate navigation
system is introduced.

## Public Safety

Layer 34A responses do not expose:

- Trust assessment IDs.
- Risk-routing IDs.
- Reviewer notes.
- Reporter IDs.
- Raw ranking objects.
- Raw trust or risk objects.
- Internal scoring objects.
- Internal explanation graphs.
- Private provenance internals.
- Filesystem paths.
- Stack traces.

Internal outcomes are translated into public-safe confidence, freshness,
limitation, driver, and explanation text.

The frontend also filters rendered API text through a narrow public-safety guard
for known forbidden internal tokens. It does not log full operational payloads in
production code and does not render raw API exceptions.

## Determinism

Layer 34A enforces deterministic output through:

- Stable enums.
- Sorted market snapshots and profiles.
- Stable metric and dictionary serialization.
- Explicit ranking tie-breaker by market key.
- Stable ranking-driver ordering.
- Fixed `as_of` dates in tests.
- No random IDs or timestamps in response DTOs.

Identical canonical inputs produce identical serialized responses.

Frontend determinism is preserved by rendering backend ranking and driver order,
using one goal/status presentation model, and keeping URL-state serialization
stable. The browser does not introduce random IDs, client-side ranking
tie-breakers, or timestamp fields.

## Read-Only Guarantees

The intelligence service:

- Builds Layer 33 operational snapshots.
- Reads stored region market score rows.
- Builds public DTOs in memory.

It does not mutate canonical facts, source references, trust records,
risk-routing records, ranking state, provenance state, audit state, import
registry state, or curated source files. Tests assert table counts are unchanged
after service and API calls.

The frontend exposes only GET helpers and no apply, approve, publish, override,
or refresh controls.

## Unknown-vs-Zero Protections

Observed zero and unknown remain separate throughout scoring and presentation:

- Observed count statuses are counted only when status is `zero_observed` or
  `positive_observed`.
- Unknown, not-collected, and not-applicable values do not become zero.
- Supporting metrics expose separate unknown and observed-zero fact counts.
- Summaries explicitly state that unknown hiring counts are not treated as zero.
- The frontend formats missing metrics as unavailable and true zero values as
  observed zero where relevant.

## Hard Boundaries

Layer 34 does not add:

- Scraping.
- Live APIs.
- Source fetching.
- Scheduled refresh.
- Background workers.
- Imports.
- Canonical writes.
- Database migrations.
- Ranking algorithm replacement.
- Trust algorithm changes.
- Approval workflow.
- Operator workflow.
- Broad frontend redesign.
- New authentication or authorization.

## Tests

Layer 34A added `tests/test_market_intelligence_layer34.py`, covering:

- Deterministic platform profiles.
- Market profile summaries.
- Opportunity environment text.
- Cross-market ranking and comparison behavior.
- Tie handling.
- All supported career goals.
- Confidence and freshness integration with Layer 33 diagnostics.
- Public-safe API routes.
- Invalid market and invalid goal handling.
- Public-demo GET-only allowlisting.
- Service and API read-only behavior.
- Boundary checks for scraping, schedulers, and approval workflows.

`tests/test_smoke_imports.py` now imports the new backend package modules.

Layer 34B adds frontend and contract coverage:

- `frontend/src/MarketIntelligencePage.test.tsx` covers overview rendering,
  career-goal selection, data-science limitations, profile sections, pairwise
  winner and tie displays, same-market handling, empty and unknown-enum states,
  unknown-vs-zero display, and public-safe rendering.
- `frontend/src/api.test.ts` covers Layer 34 frontend helper paths and GET-only
  request behavior.
- `frontend/src/urlState.test.ts` covers shareable market-intelligence URL
  parsing and serialization.
- `tests/integration/test_frontend_api_contract.py` covers frontend-consumed
  Layer 34 API shapes, supported goal alignment, invalid market/goal behavior,
  public-demo GET allowlisting, route method safety, public redaction, and
  unknown-vs-zero payload preservation.

Layer 34C extends the same focused test files with calibration, evidence
sufficiency, robustness, differentiation, explanation-quality, contradiction,
grounding, adversarial fixture, product-quality report, and frontend
decision-usefulness coverage. Verification readiness is established by running
the focused Layer 34C tests, full backend suite, full frontend suite, lint,
compile, build, public-demo smoke, and git diff checks before independent audit.

## Accessibility

The frontend uses semantic headings, associated form labels, text status labels,
keyboard-accessible selects and buttons, visible limitations, and status badges
with human-readable labels. No chart-only presentation or hover-only critical
information is introduced.

## Known Limitations

- The current curated datasets provide adjacent AI/cloud and product signals for
  data science, but not a direct data-science role family.
- Hiring momentum is descriptive only; the engine does not infer trends unless
  future canonical facts support them.
- The scoring model is intentionally conservative and explainable. It is an
  orchestration layer over existing canonical signals, not a replacement for
  ranking, trust, or import systems.
- The frontend currently uses structured cards and metric rows instead of charts
  because the existing product does not require new chart infrastructure for this
  layer.
