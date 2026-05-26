# Layer 14A: Recommendation Domain Contracts

Date: 2026-05-26

## Scope

Layer 14A establishes the backend/domain contract layer for explainable,
confidence-aware recommendations. It defines stable recommendation goal modes,
target types, explanation objects, evidence references, tradeoffs, weaknesses,
manual-verification prompts, and validation rules.

This layer is representation only. AI may later summarize these structures,
but AI does not own recommendation truth.

## Implemented

- `backend/recommendations/` package for recommendation-facing contracts.
- Stable `RecommendationGoalMode` values and user-facing metadata.
- Stable `RecommendationTargetType` values for regions, companies, company
  categories, role families, market strategies, and watchlist items.
- Evidence strength and basis vocabularies.
- Structured explanation models for fit reasons, data strengths, tradeoffs,
  weaknesses, manual verification, confidence, freshness, and provenance refs.
- Validation that rejects unsupported structured claims, blank explanations,
  invalid enum values, and heuristic claims that are not explicitly marked as
  inferred.

## Boundary Rule

Every recommendation claim must be traceable to structured app data,
confidence, freshness, provenance, market coverage, data-quality warnings, user
preferences, or explicitly labeled heuristic / missing-data context.

Layer 14A does not redefine freshness, confidence, provenance, coverage, or
refresh-quality rules. It carries references and summaries produced by those
layers.

## Non-Goals Preserved

- No recommendation ranking.
- No goal-mode scoring weights.
- No tradeoff generation logic.
- No market strategy generation.
- No API endpoints.
- No frontend UI.
- No AI summaries or external AI provider calls.
- No live web or job scraping.
- No invented market facts.
- No changes to scoring, refresh, provenance, confidence, coverage, or
  data-quality ownership.
- No persistence or database migration.

## Future Batches

Expected follow-on work can consume these contracts to add ranking, goal-mode
scoring, generated tradeoff selection, strategy/watchlist generation, API
surfaces, frontend presentation, and AI summaries. Those batches should keep
the same boundary: generated text explains app-owned evidence; it does not
create market truth.
