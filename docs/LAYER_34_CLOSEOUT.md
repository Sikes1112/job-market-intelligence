# Layer 34 Closeout - Market Intelligence Engine and Comparison Platform

## Purpose

Layer 34 establishes that the platform can turn curated imported-market data into
useful, explainable, confidence-aware career intelligence for users. It builds on
Layers 31-33 without changing import behavior, canonical facts, trust/risk
policy, or ranking gates.

## Batch 34A Backend Architecture

Batch 34A added `backend/market_intelligence/`:

- `schemas.py` defines stable public DTOs and enums.
- `goals.py` defines supported career goals and public goal metadata.
- `scoring.py` derives confidence-aware metrics from canonical facts, region
  scores, ranking eligibility, freshness, and Layer 33 diagnostics.
- `profiles.py` builds multi-dimensional market profiles.
- `comparisons.py` builds explainable rankings and pairwise comparisons.
- `service.py` orchestrates platform summaries, profiles, rankings, pairwise
  comparisons, and career-goal recommendations.

The backend API router is `backend/api/market_intelligence.py`, registered from
`backend/api/app.py`.

## Batch 34B Frontend Architecture

Batch 34B added a focused user-facing intelligence route:

- `/markets/intelligence`

The frontend implementation lives in:

- `frontend/src/MarketIntelligencePage.tsx`
- `frontend/src/marketIntelligenceModel.ts`
- Layer 34 additions to `frontend/src/api.ts`
- Layer 34 additions to `frontend/src/types.ts`
- Layer 34 route state in `frontend/src/urlState.ts`
- Small product navigation integration in `frontend/src/App.tsx`

The route renders backend-provided rankings, profiles, comparisons, confidence,
freshness, limitations, and ranking drivers. It does not recompute rankings,
scores, confidence, or ranking-driver order in the browser.

## Batch 34C Quality Hardening

Batch 34C adds the quality and audit-readiness layer over the existing read-only
market intelligence system. It includes deterministic calibration across every
registered market and supported career goal, goal-specific direct/proxy evidence
definitions, evidence-sufficiency gates, robustness scenarios, differentiation
checks, explanation-quality checks, contradiction detection, and public-safe
evidence grounding.

The machine-readable product-quality evaluation report for the independent audit
is generated at:

- `docs/implementation/layer_34c/artifacts/product_quality_evaluation_report.json`

The report is built from `MarketIntelligenceService.product_quality_evaluation_report`
and includes the current 40 market-goal combinations, platform summaries,
stability findings, abstentions, contradictions, explanation-quality status, and
differentiation findings. The generation path uses seeded curated market data in
memory and does not write canonical tables, refresh external sources, or mutate
production datasets.

## Public API Routes

Layer 34 exposes GET-only public-safe routes:

- `GET /market-intelligence`
- `GET /market-intelligence/{market_key}`
- `GET /market-comparisons`
- `GET /market-comparisons/{market_a}/{market_b}`
- `GET /career-goal-comparisons`
- `GET /career-goal-comparisons/{goal}`

Invalid markets return the project-standard not-found envelope. Invalid goals
return a validation-error envelope. Public-demo route protection allows these GET
routes only.

## Market Profiles

Market profiles include:

- Overview.
- Strengths and weaknesses with public-safe evidence.
- Employer, hiring, internship, co-op, and early-career summaries.
- Opportunity-environment summary.
- Supporting metrics.
- Confidence and freshness.
- Coverage summary.
- Public limitations.

The frontend renders these as structured sections and only displays strengths or
weaknesses returned by the backend.

## Career-Goal Rankings

Supported goals are:

- `software_engineering`
- `product_management`
- `ai_ml`
- `cybersecurity`
- `data_science`

The frontend uses backend goal definitions when available and a single fallback
presentation map for known goals. Unknown future goals render a neutral fallback
and do not crash the route.

## Pairwise Comparisons

Users can compare two distinct markets for the selected career goal. The
frontend displays both sides, backend-provided strengths and weaknesses,
supporting metrics, limitations, and the backend outcome. Ties use neutral
language and do not force a winner. Same-market comparisons are handled locally
without calling the comparison API.

## Explainable Ranking Drivers

Ranking drivers include stable public code, label, relative contribution, and
evidence. The frontend preserves backend ordering and labels contributions as
comparative, not probabilistic.

## Confidence Model

Confidence levels are:

- `high`
- `moderate`
- `low`
- `limited`

Confidence is backend-derived from coverage, freshness, unknown ratios,
ranking-exclusion state, validation state, and Layer 33 diagnostics. The
frontend displays confidence as text, not color alone, and does not derive a
different value.

## Freshness Model

Freshness levels are:

- `current`
- `aging`
- `stale`
- `unknown`

Freshness is backend-derived from curated source and fact state. The frontend
does not fetch, validate, or refresh sources.

## Limitation Handling

Every intelligence surface has a visible limitations area. Limitations include
missing role-family evidence, limited co-op or internship coverage, high unknown
ratios, stale sources, ranking exclusions, and insufficient comparison-ready
evidence. The data-science goal visibly preserves the limitation that direct
data-science role-family facts are not currently collected.

## Unknown-vs-Zero Handling

Layer 34 preserves the Layer 31 unknown-vs-zero contract:

- Unknown, missing, not-collected, and unavailable metrics are not displayed as
  zero.
- True zero metrics are displayed as observed zero where relevant.
- Supporting metrics keep `unknown_fact_count` and `observed_zero_fact_count`
  separate.
- The frontend explicitly states that unknown facts and observed-zero facts are
  displayed separately.

## Accessibility

The frontend uses semantic headings, associated select labels, text status
labels, keyboard-accessible controls, visible limitations, and readable error
states. No chart-only presentation or hover-only critical information is
introduced.

## Determinism

Backend outputs are deterministic through stable enums, stable market ordering,
explicit tie-breaking, stable metric serialization, and fixed test clocks.
Frontend determinism is preserved by rendering backend order and using one
presentation mapping for goals, confidence, freshness, and comparison outcomes.

## Read-Only Guarantees

Layer 34 reads canonical data, Layer 33 diagnostics, stored region market scores,
and public-safe ranking/freshness/confidence signals. It does not mutate
canonical facts, source references, imports, trust records, risk-routing records,
ranking state, provenance state, curated files, or audit logs. The frontend
exposes no write controls.

## Public Safety

Layer 34 does not expose trust IDs, risk-routing IDs, reviewer notes, reporter
IDs, raw trust/risk objects, raw ranking objects, internal scoring objects,
private provenance internals, filesystem paths, or stack traces. Frontend tests
assert rendered text redacts prohibited internal tokens.

## Hard Boundaries

Layer 34 does not add scraping, live external APIs, source fetching, browser
automation, scheduled refresh, cron, background ingestion, canonical writes,
import mutation, ranking replacement, trust/risk policy changes, approval
workflow, reviewer workflow, operator override, new authentication, new
authorization, or database migrations.

## Tests

Backend coverage:

- `tests/test_market_intelligence_layer34.py`
- Layer 34 additions to `tests/test_smoke_imports.py`
- Layer 34 additions to `tests/integration/test_frontend_api_contract.py`

Frontend coverage:

- `frontend/src/MarketIntelligencePage.test.tsx`
- Layer 34 additions to `frontend/src/api.test.ts`
- Layer 34 additions to `frontend/src/urlState.test.ts`
- Layer 34 additions to `frontend/scripts/public-demo-smoke.test.mjs`

## Verification Results

Batch 34B verification results:

- Layer 34 frontend focused tests: 39 passed.
- Full frontend suite: 157 passed.
- Layer 34 backend plus frontend contract slice: 14 passed.
- Layer 31 regression slice: 45 passed.
- Layer 32 regression slice: 56 passed.
- Layer 33 operations and contract slice: 33 passed.
- Trust/risk/ranking/API safety slice: 60 passed.
- Migration/schema/API metadata slice: 31 passed.
- Full backend suite: 2,389 passed.
- Backend ruff: passed.
- Backend compileall: passed.
- Frontend lint: passed.
- Frontend build: passed, with the existing Vite bundle-size warning.
- Public-demo smoke: 12 checks passed.
- `git diff --check`: passed.

Batch 34C verification readiness is established by the Layer 34C implementation
loop before independent audit. Required evidence includes focused backend and
frontend tests, backend/frontend contracts, Layer 31-34 regression coverage,
full backend and frontend suites, backend and frontend lint, frontend build,
Python compile checks, public-demo smoke, git diff checks, and hard-boundary
inspection. Codex implementation output does not self-declare audit pass; the
controller advances to independent audit after deterministic verification.

## Known Limitations

- Current curated datasets do not include direct data-science role-family facts;
  data-science recommendations rely on adjacent canonical signals and display
  that limitation.
- Hiring momentum is descriptive only and does not infer unsupported trends.
- The frontend uses ranked cards and metric rows rather than new chart
  infrastructure.
- Layer 34 is read-only intelligence; it does not perform imports or data
  maintenance.

## Final Audit Findings

The implementation is coherent with Layers 31-33, public-safe, deterministic,
read-only, and contract-aligned. The frontend exposes market intelligence as a
normal user-facing exploration surface rather than an import-maintenance or
admin workflow.

## Final Recommendation

Layer 34 is `LOCK_READY` based on the final Batch 34B source audit, contract
checks, regression results, read-only posture, public-safety review, and clean
git diff checks. Do not begin Layer 35 from this closeout; commit durability is a
separate repository task.
