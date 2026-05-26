# Layer 14F Frontend Recommendations

Layer 14F makes the completed Layer 14 recommendation pipeline visible in the
frontend. It consumes the Layer 14E API and renders structured decision-support
objects without adding AI summaries, prompt boxes, scraping, or persistence.

## Implemented UI

Added a new product route:

- `/markets/recommendations`

The page includes:

- goal-mode selector
- goal-mode profile hints from `GET /recommendations/goal-modes`
- ranked region recommendation cards
- ranked company recommendation cards when the API returns companies
- missing-company empty state when company rankings are unavailable
- score components, missing components, proxy/inferred components, and penalties
- explanation sections for fit reasons, data strengths, tradeoffs, weaknesses,
  manual verification, and evidence references
- structured market strategy plan
- primary, secondary, fallback, and watchlist sections
- company target, company category, and role-family guidance sections
- timing guidance
- manual verification checklist
- strategy evidence warnings

## API Client

The frontend API client now supports:

- `getRecommendationGoalModes()`
- `getRecommendationStrategy(body)`

The strategy request shape matches Layer 14E and includes only structured
options such as `goal_mode`, region/company limits, and strategy section limits.
It does not accept free-form prompts.

## Evidence Display

Recommendation cards render the structured response directly:

- `score_components_used`
- `score_components_missing`
- `score_components_proxy`
- `penalties_applied`
- `explanation.fit_reasons`
- `explanation.data_strengths`
- `explanation.tradeoffs`
- `explanation.weaknesses`
- `explanation.manual_verification`
- `explanation.evidence_refs`
- confidence/freshness/provenance/coverage fields when present

Proxy and inferred signals are labeled visibly. Missing company recommendations
show backend warnings instead of invented company targets.

## Strategy Display

The market strategy section renders:

- primary regions
- secondary regions
- fallback regions
- watchlist items
- company targets and categories
- role-family guidance
- timing guidance
- manual verification checklist
- evidence warnings

Role-family guidance is visibly labeled as heuristic/inferred when the API marks
it that way. Watchlist items show their reason, upside, verification question,
and refresh revisit marker.

## Read-Only Boundary

The recommendation UI is read-only:

- no saved strategies
- no persisted goal-mode preferences
- no account mutations
- no backend data mutation
- no scraping or external retrieval

The public-demo smoke checks include the recommendations page and goal-mode API
endpoint using GET-only checks.

## Non-Goals

Not implemented:

- AI summaries
- LLM calls
- prompt box or free-form recommendation chat
- current job-opening claims
- current hiring-cycle claims
- invented companies
- invented market facts
- persistence or migrations
- backend ranking/strategy algorithm changes
- broad frontend redesign

## Known Limitations

- Company recommendations are empty when the backend has no readable company
  outputs.
- Role-family guidance remains heuristic until the backend carries direct
  role-family recommendation targets.
- Geographic flexibility, lower competition, and some AI/cloud signals remain
  proxy-heavy until richer structured data exists.
