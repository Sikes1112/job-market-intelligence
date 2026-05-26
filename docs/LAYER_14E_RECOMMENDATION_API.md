# Layer 14E Recommendation API

Layer 14E exposes the completed Layer 14A-D recommendation pipeline through
backend API and DTO surfaces. It serializes structured recommendation objects;
it does not turn recommendations into AI prose.

## Scope

Implemented:

- `backend/recommendations/payloads.py`
  - API-safe goal-mode profile DTOs.
  - `RecommendationStrategyRequest`.
  - `RecommendationStrategyPayload`.
- `backend/api/recommendations.py`
  - `GET /recommendations/goal-modes`.
  - `POST /recommendations/strategy`.
- Router registration in `backend/api/app.py`.

The strategy endpoint reads existing app-owned region/company output payloads
through `OutputAssemblyService`, attaches source summaries from existing API
search helpers when available, runs Layer 14C deterministic ranking, and passes
ranked outputs into the Layer 14D strategy generator.

## Endpoints

### `GET /recommendations/goal-modes`

Returns all canonical recommendation goal modes with user-facing labels,
descriptions, prioritization summaries, weighted components, penalty
components, missing-data behavior, and proxy/heuristic warnings.

The response does not expose ranking execution output. It is inspectable
configuration for frontend controls and later API consumers.

### `POST /recommendations/strategy`

Request fields:

- `goal_mode` - required canonical `RecommendationGoalMode`.
- `include_company_recommendations` - optional, defaults to `true`.
- `region_limit` - optional ranked-region limit, `1..100`, defaults to `25`.
- `company_limit` - optional ranked-company limit, `0..100`, defaults to `25`.
- `max_primary_regions` - optional strategy limit, `1..10`, defaults to `3`.
- `max_secondary_regions` - optional strategy limit, `0..10`, defaults to `3`.
- `max_fallback_regions` - optional strategy limit, `0..10`, defaults to `3`.
- `max_watchlist_items` - optional strategy limit, `0..25`, defaults to `6`.
- `max_company_targets` - optional strategy limit, `0..25`, defaults to `5`.

Unknown goal modes, invalid limits, and extra request fields are rejected by
Pydantic/FastAPI validation. The endpoint does not accept free-form prompts or
natural-language recommendation instructions.

Response fields:

- available goal-mode profile DTOs
- selected goal-mode profile DTO
- ranking profile version and documented tie-breaker
- ranked region recommendations
- ranked company recommendations when existing company outputs are available
- generated `MarketStrategyPlan`
- data-source warnings

Ranked recommendations preserve:

- target identity
- rank and bounded scores
- used score components
- missing score components
- proxy/inferred score components
- applied penalties
- explanation reasons, tradeoffs, weaknesses, and manual verification items
- confidence/freshness/provenance/coverage references and warnings

Strategy plans preserve:

- source ranked recommendation references
- primary, secondary, fallback, and watchlist targets
- company targets only from supplied ranked company outputs
- company-category guidance only from ranked company component evidence
- role-family guidance marked heuristic/inferred unless future ranked outputs
  carry direct role-family names
- timing guidance
- manual verification checklist
- evidence warnings

## Data Source Behavior

The API integrates with existing read surfaces only:

- regions are listed from `RegionRepository`
- region output payloads are assembled through `OutputAssemblyService.read_region`
- companies are enumerated through existing `search_companies`
- company output payloads are assembled through `OutputAssemblyService.read_company`
- source summaries come from existing `explain_region_sources` and
  `explain_company_sources`

If company data is absent, the response returns an empty company recommendation
section with a structured warning. It does not invent companies, company
categories, role openings, or market facts.

## Boundary Rule

Layer 14E is an API/DTO surface. It preserves recommendation traceability from
Layer 14A-D:

> AI does not own recommendation truth.

Recommendation claims remain tied to structured app data, confidence, freshness,
provenance, coverage, or explicitly labeled heuristic inference.

## Non-Goals

Not implemented in this batch:

- frontend UI
- frontend TypeScript contract changes
- AI summaries
- LLM calls or prompt logic
- live job scraping or external retrieval
- current job-opening claims
- current hiring-cycle claims
- invented company targets
- invented market facts
- database persistence or migrations
- scoring/freshness/provenance/confidence/coverage ownership changes

## Known Limitations

- Company recommendations are empty when the current backend has no readable
  company outputs.
- Role-family strategy remains heuristic/inferred until ranked outputs carry
  direct role-family target contracts.
- Geographic flexibility, lower competition, and some AI/cloud guidance remain
  proxy-bound until richer structured data exists.
