# Layer 14D: Deterministic Market Strategy + Watchlist Planning

Date: 2026-05-26

## Scope

Layer 14D turns Layer 14C ranked recommendations into structured job-search
strategy plans. It consumes ranked region/company outputs and produces primary
targets, secondary targets, fallback regions, watchlist items, company targets,
company-category guidance, heuristic role-family guidance, timing guidance,
manual-verification checklists, and strategy-level evidence warnings.

Layer 14D does not rank from scratch. It does not own raw market data, scoring,
coverage, confidence, freshness, provenance, refresh quality, API presentation,
frontend presentation, or AI explanation truth.

## Implemented

- `backend/recommendations/strategy.py`
  - `MarketStrategyPlan`
  - region target strategy objects
  - company target strategy objects
  - company category strategy objects
  - role-family strategy objects
  - timing guidance objects
  - watchlist objects
  - manual-verification checklist wrappers
  - evidence-warning objects
  - `generate_market_strategy_plan()`

Every strategy item references one or more ranked recommendation source IDs.
Structured strategy claims require evidence references. Heuristic strategy
claims must be explicitly inferred.

## Selection Rules

Region selections are deterministic:

1. Primary regions are the highest-ranked non-watchlist targets above the
   primary score threshold.
2. Fallback regions are lower-ranked viable targets with useful tradeoffs or,
   for lower-competition and underrated-market goals, favorable lower-
   competition proxy values.
3. Secondary regions are remaining viable non-watchlist targets after primary
   and fallback selection.
4. Watchlist regions are ranked targets with useful upside but weak freshness,
   confidence, coverage, missing components, missing provenance, or data-quality
   tradeoffs.

Tie order is inherited from Layer 14C rankings. Strategy does not re-sort or
re-score independently.

## Company And Category Rules

Company targets are included only when company rankings are supplied. The
strategy generator does not invent company targets.

Company-category guidance is generated only from supplied ranked company
outputs:

- AI/cloud-oriented companies from AI/cloud component evidence
- high-prestige companies from prestige component evidence
- entry-level-signal companies from entry-level component evidence

Proxy-derived categories are marked inferred and carry heuristic evidence
basis.

## Role-Family Rules

The current ranked outputs do not carry direct role-family names. Layer 14D may
therefore emit goal-mode-aligned role-family guidance only as heuristic,
inferred guidance. These items do not claim current openings and always add
manual verification for role-family fit.

## Timing Guidance

Timing guidance is conservative:

- apply first to high-fit targets with usable evidence context
- verify current postings before acting
- monitor watchlist targets until evidence improves
- revisit stale or weak-evidence targets after refresh
- verify internship/co-op availability for internship/co-op mode
- verify location or hybrid requirements for geographic-flexibility mode

No current hiring cycle, deadline, or live-opening claim is generated.

## Manual Verification

The plan aggregates manual-verification items from ranked explanations and adds
strategy-level checks for current postings, company-specific hiring pages,
internship/co-op eligibility, location requirements, and heuristic role-family
fit when relevant.

## Evidence Traceability

Each strategy object carries:

- source ranked recommendation IDs
- evidence basis
- evidence strength
- support type
- evidence refs when structured evidence is used

Strategy validation rejects free-floating structured advice, heuristic advice
not marked inferred, and strategy items that do not reference ranked
recommendations.

## Non-Goals Preserved

- No API endpoints.
- No frontend UI.
- No AI summaries, LLM calls, or prompt logic.
- No live web/job scraping.
- No current hiring-cycle claims.
- No current job-opening claims.
- No invented company targets.
- No invented market facts.
- No persistence or migrations.
- No changes to scoring, freshness, provenance, confidence, coverage, or
  refresh-quality ownership.

## Next Batch

The next batch can expose these strategy plans through API/frontend surfaces or
add controlled AI summaries that strictly summarize the structured plan. AI
must remain a summarizer of evidence-bound strategy objects, not a source of
recommendation truth.
