# Layer 14B: Structured Recommendation Assembly + Goal-Mode Profiles

Date: 2026-05-26

## Scope

Layer 14B adds the bridge from existing structured app read models into the
Layer 14A recommendation explanation contracts. It also adds inert,
inspectable goal-mode weight profiles for the later deterministic ranking
batch.

The assembly layer does not decide which target is best. It only converts
already-owned app data into traceable `RecommendationExplanation` objects.

## Assembly Ownership

`backend/recommendations/assembly.py` maps:

- region score fields to `structured_score` evidence
- region/company metadata to `region_metadata` / `company_metadata` evidence
- coverage payloads to `market_coverage` evidence
- output/source freshness summaries to `freshness` evidence
- confidence metadata or coverage confidence components to `confidence` evidence
- source explanation source IDs to `provenance` references
- missing fields, partial outputs, stale/unknown freshness, weak coverage, and
  absent source refs to weaknesses or manual verification items

The assembly layer accepts existing Pydantic read models or similarly shaped
objects. It uses structural field access so it does not import API routes,
repositories, services, scraping code, or AI providers.

## Goal-Mode Profiles

`backend/recommendations/goal_modes.py` defines one profile for each canonical
Layer 14A goal mode. Profiles include weighted components, explicit penalty
components, missing-data behavior, and warnings for proxy or inferred
components.

Current canonical components include:

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

`lower_competition_proxy`, `underrated markets`, geographic flexibility, and
some AI/cloud concentration inputs are explicitly proxy/inferred components
until direct structured data exists.

## Validation

Profiles validate that every weighted bundle sums to `1.0`, uses canonical
components, keeps penalties explicit, marks heuristic components as proxy, and
documents missing-data behavior.

Assembly output continues to rely on Layer 14A validation: structured claims
must carry evidence refs, heuristic claims must be marked inferred, and
free-text-only explanations are rejected.

## Non-Goals Preserved

- No recommendation ranking engine.
- No execution of goal-mode weights.
- No automatic tradeoff generation.
- No market strategy/watchlist generation.
- No API endpoints.
- No frontend UI.
- No AI summaries or external AI calls.
- No scraping or new market facts.
- No persistence or migrations.
- No changes to scoring, coverage, freshness, confidence, provenance, or
  refresh-quality ownership.

## Next Batch

The next expected batch is deterministic recommendation ranking and controlled
tradeoff generation that consumes these assembly outputs and goal-mode profile
definitions without creating recommendation truth outside structured evidence.
