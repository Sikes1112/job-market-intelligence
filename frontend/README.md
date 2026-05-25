# Job Market Intelligence Frontend Demo

Polished Vite + React + TypeScript demo UI for the existing backend API.

## Run

From the repo root:

```bash
python -m scripts.seed_demo --database-url "sqlite:///./demo.db"
DATABASE_URL="sqlite:///./demo.db" uvicorn backend.api.app:app --reload
```

In another shell:

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL printed by `npm run dev`.

## API Base URL

The frontend reads `VITE_API_BASE_URL` when provided:

```bash
VITE_API_BASE_URL="http://127.0.0.1:8000" npm run dev
```

When `VITE_API_BASE_URL` is not set, local development uses Vite's dev proxy for:

- `GET /health`
- `GET /regions`
- `GET /regions/{region_id}`
- `GET /companies/{company_id}`
- `GET /compare?region_a=...&region_b=...`
- `POST /discover/personalized`
- protected `/me` account routes
- protected `POST /me/scoring-preview`
- protected `/me/alerts` in-app alert feed routes
- protected `/me/explanations/*` deterministic structured guidance routes

The proxy targets `http://127.0.0.1:8000` and avoids requiring backend CORS changes for the local demo.

## Auth0 Account UX

The frontend uses Auth0's React SPA SDK for sign-in/sign-out when these variables are present:

```bash
VITE_AUTH0_DOMAIN="<tenant>.us.auth0.com"
VITE_AUTH0_CLIENT_ID="<spa-client-id>"
VITE_AUTH0_AUDIENCE="https://api.job-market-intelligence.local"
VITE_AUTH0_REDIRECT_URI="http://127.0.0.1:5173/markets"
```

Tokens are requested through Auth0 SDK memory cache and attached only to protected `/me` requests. Public market exploration works with the Auth0 variables unset.

The account screen exposes app-owned Layer 7/11A/11B data only: current user/profile, saved preferences, scoring weights, watchlists, in-app alerts, recommendation snapshots, export, and app-level account deactivation. Watchlists store references; scoring previews label canonical/default scores separately from personalized overlay scores. Deactivation does not delete the Auth0 provider account.

Layer 11C visualizations are read-only frontend views over existing API fields.
Score, comparison, and alert charts do not create new scoring logic. Trend,
map, heatmap, and network views stay disabled unless supported structured data
exists. Explanation panels call protected deterministic guidance endpoints and
render only supplied evidence-packet facts, limitations, and missing-data
flags.

## Market Coverage Disclosure

Layer 12 coverage metadata is rendered as an API-supplied readiness label, not
as source truth. Region-facing views show:

- `Coverage: Fully covered` for Tier 1 markets with enough validated data for
  confident comparison.
- `Coverage: Partial but useful` for Tier 2 markets that are directionally
  useful but incomplete.
- `Coverage: Watchlist / emerging` for Tier 3 markets tracked for expansion
  but not ready for confident recommendations.
- `Coverage: Placeholder only` for Tier 4 markets that should not be treated as
  analyzed.

When a numeric coverage score appears, the UI labels it as a heuristic coverage
score or estimate. The frontend does not infer coverage client-side. It renders
the backend `coverage` object when present and falls back to "Coverage
unavailable" for older responses.

Coverage, freshness, and provenance are separate disclosures. Freshness/source
badges remain visible beside coverage badges, and sector-specific coverage is
shown under a separate "Sector coverage" section instead of replacing overall
region coverage. Comparison and personalized discovery surfaces render
`region_coverage_not_confident` warnings when the backend returns them for Tier
3 or Tier 4 regions.

## Checks

```bash
npm run lint
npm run test
npm run build
```

Public demo smoke checks can probe a deployed frontend/API pair without
mutating backend state:

```bash
FRONTEND_BASE_URL="https://<frontend-host>" API_BASE_URL="https://<api-host>" npm run smoke:public-demo
```
