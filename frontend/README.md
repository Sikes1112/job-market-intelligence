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

The account screen exposes app-owned Layer 7 data only: current user/profile, saved preferences, saved market artifacts, recommendation snapshots, export, and app-level account deactivation. Deactivation does not delete the Auth0 provider account.

## Checks

```bash
npm run lint
npm run test
npm run build
```
