# Layer 14C: Deterministic Recommendation Ranking + Controlled Tradeoffs

Date: 2026-05-26

## Scope

Layer 14C adds deterministic ranking over structured recommendation inputs. It
consumes Layer 14A explanation contracts and Layer 14B goal-mode profiles, then
returns ranked region/company recommendation outputs with inspectable component
scores, missing-data handling, explicit penalties, proxy flags, generated
tradeoffs, and bound `RecommendationExplanation` objects.

This layer does not create market truth. Every ranking reason or tradeoff must
derive from structured app data, confidence, freshness, provenance, market
coverage, missing-data context, or an explicitly labeled heuristic proxy.

## Implemented

- `backend/recommendations/ranking.py`
  - region recommendation ranking
  - company recommendation ranking
  - canonical score-component resolution
  - weighted scoring from `goal_modes.py`
  - explicit missing components
  - explicit proxy/inferred components
  - explicit ranking penalties
  - stable tie-break behavior
  - explanation binding for ranking reasons, weaknesses, manual checks, and
    generated tradeoffs
- `backend/recommendations/tradeoffs.py`
  - controlled tradeoff generation from resolved component signals
  - no city, company, sector, or market narratives unless supported by inputs

## Score Component Resolution

Layer 14C resolves the canonical Layer 14B components:

- `entry_level_access`
- `internship_or_coop_access`
- `prestige_density`
- `ai_cloud_concentration`
- `company_density`
- `role_diversity`
- `lower_competition_proxy`
- `geographic_flexibility`
- `market_coverage`
- `confidence`
- `freshness`

Unavailable components are represented as missing and surfaced in ranking
warnings plus bound explanation weaknesses/manual-verification items. They are
not imputed.

Proxy components are carried as proxy/inferred where appropriate. Current known
proxy areas remain:

- lower competition
- geographic flexibility
- AI/cloud concentration where sector metadata is the only signal
- role diversity where role-family summaries are sparse
- coverage quality where coverage metadata itself is heuristic

## Weighted Ranking

Weights are loaded from Layer 14B `goal_mode_weight_profile()`. Ranking does
not duplicate profile weights locally.

Final score behavior:

- each available weighted component contributes `component_value * profile_weight`
- missing weighted components contribute no score and are surfaced explicitly
- profile penalty components are applied separately and reported in
  `penalties_applied`
- final scores are bounded to `[0, 1]`
- `normalized_score` currently equals the bounded final score

Penalty direction is deterministic and exposed as `application_mode`:

- high-value penalties apply when a high component value is the risk
- low-value penalties apply when a low component value is the risk
- always penalties apply when the profile says verification is required even
  if a proxy value exists

## Tie Breaks

Ranked outputs are sorted by:

1. `final_score` descending
2. display label ascending
3. stable target ID ascending

This keeps rankings deterministic when scores tie.

## Controlled Tradeoffs

Tradeoffs are generated only from resolved score components and existing
explanation metadata. Supported controlled patterns include:

- broad opportunity but competition risk
- AI/cloud concentration but narrower company universe
- underrated-market proxy but weaker prestige density
- lower competition proxy but fewer total roles
- high prestige but weaker entry-level access
- good fit but weak/stale/missing evidence quality
- good fit but manual verification remains

Layer 14C intentionally does not generate unsupported public-sector/cyber vs
consumer-tech narratives unless future structured data supports that
distinction.

## Non-Goals Preserved

- No market strategy generator.
- No application timing guidance.
- No fallback market strategy.
- No watchlist strategy.
- No API endpoints.
- No frontend UI.
- No AI summaries, LLM calls, or prompt logic.
- No live web/job scraping.
- No new market facts.
- No persistence or migrations.
- No changes to existing scoring, freshness, provenance, confidence, coverage,
  or refresh-quality ownership.

## Next Batch

The next expected batch can consume ranked recommendation outputs to build
deterministic strategy/watchlist generation. It should continue treating AI as
a summarizer of structured recommendation evidence, not as a source of
recommendation truth.
