# Job Market Intelligence Platform

Local MVP demo for a job-market intelligence platform.

The product maps companies, hiring activity, entry-level opportunity, and market strength across cities, metros, and labor regions.

Comparison is a feature, not the product core.

## What Is Implemented

- Backend API for health, region outputs, company outputs, Boston vs SF comparison, request-scoped personalized discovery, protected user-owned watchlists/scoring previews/alerts, and deterministic structured explanation endpoints.
- Deterministic seeded demo data for Greater Boston and Greater San Francisco / Silicon Valley.
- Vite + React + TypeScript frontend demo under `frontend/`, including Auth0 sign-in/sign-out and app-account UX for protected `/me` routes.
- Local SQLite demo workflow via `scripts/seed_demo.py`.

Current status: internal-production baseline for a local, single-process architecture. It is suitable for local demo/presentation and internal reliability exercises, but it is not external-production ready. It has an Auth0/JWKS-protected user API foundation and frontend account workflows, but does not expose scraping, external APIs, maps, admin tooling, provider-side account deletion/session revocation, or full production deployment configuration.

## Run The Local Demo

From the repo root, seed the demo database:

```bash
python -m scripts.seed_demo --database-url "sqlite:///./demo.db"
```

Run the backend against the same database:

```bash
DATABASE_URL="sqlite:///./demo.db" uvicorn backend.api.app:app --reload
```

In another shell, run the frontend:

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL printed by `npm run dev`, typically `http://localhost:5173`.

For the local demo, prefer the Vite dev proxy by leaving `VITE_API_BASE_URL` unset. The proxy forwards the implemented API paths to `http://127.0.0.1:8000` without requiring backend CORS changes.

Useful backend endpoints:

- `GET http://127.0.0.1:8000/health`
- `GET http://127.0.0.1:8000/ready`
- `GET http://127.0.0.1:8000/regions`
- `GET http://127.0.0.1:8000/regions/greater_boston`
- `GET http://127.0.0.1:8000/regions/greater_sf`
- `GET http://127.0.0.1:8000/compare?region_a=greater_boston&region_b=greater_sf`
- `POST http://127.0.0.1:8000/discover/personalized`
- `POST http://127.0.0.1:8000/me/scoring-preview` with Auth0 Bearer auth

## Private Cloud Demo Deployment Notes

This repo is prepared only for a private seeded Vercel + Render + Neon cloud
demo. It is not external-production ready, and the seeded cloud data must not
be presented as production or factual market data.

Vercel frontend settings:

- Root directory: `frontend/`
- Install command: `npm ci`
- Build command: `npm run build`
- Output directory: `dist`
- Environment: `VITE_API_BASE_URL=https://<render-service>.onrender.com`, `VITE_AUTH0_DOMAIN`, `VITE_AUTH0_CLIENT_ID`, `VITE_AUTH0_AUDIENCE`, optional `VITE_AUTH0_REDIRECT_URI`

Render backend settings:

- Service type: Python Web Service from the repo root
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn backend.api.app:app --host 0.0.0.0 --port $PORT`
- Environment: `APP_ENV=prod`, `DATABASE_URL`, `LOG_LEVEL=INFO`, `SERVICE_NAME=jmi-backend`, `CORS_ALLOWED_ORIGINS`, `RATE_LIMIT_ENABLED`, `SECURITY_HEADERS_ENABLED`, `MAX_REQUEST_BODY_BYTES`, `RATE_LIMIT_REQUESTS`, `RATE_LIMIT_WINDOW_SECONDS`, `AUTH0_ISSUER`, `AUTH0_AUDIENCE`, `AUTH0_JWKS_URL` if the issuer default is not sufficient, `AUTH0_JWKS_CACHE_SECONDS`, `PYTHON_VERSION=3.11.11`
- `APP_ENV=prod` rejects SQLite database URLs and requires rate limiting and security headers to remain enabled.
- Final CORS lockdown: `CORS_ALLOWED_ORIGINS=https://<vercel-app>.vercel.app`
- Do not use wildcard CORS. For local dev, leave `CORS_ALLOWED_ORIGINS` empty and use the Vite proxy, or set exact local origins explicitly.

Neon database notes:

- Use the Neon Postgres connection string for Render `DATABASE_URL`.
- The app uses SQLAlchemy with `psycopg`; `postgres://` and `postgresql://` URLs are normalized to `postgresql+psycopg://`.
- Initialize schema explicitly with `DATABASE_URL="<neon-url>" alembic upgrade head`.
- `python -m scripts.init_db` remains a local/demo wrapper that runs Alembic `upgrade head`; it is blocked for `APP_ENV=staging` and `APP_ENV=prod`.
- Seed demo data only for private demos. Non-SQLite seed targets require explicit confirmation, for example `APP_ENV=local JMI_ALLOW_NON_LOCAL_DEMO_DB=true DATABASE_URL="<neon-url>" python -m scripts.seed_demo`.
- Do not use cloud seed data as production or factual market data.

Layer 1 does not add auth, public launch readiness, or production data pipelines.

## Public Demo Runtime Notes

For externally viewable public demos, run the backend with `APP_ENV=public_demo`
and an explicit `DATABASE_URL` plus exact frontend CORS origin:

```bash
APP_ENV=public_demo
CORS_ALLOWED_ORIGINS=https://<public-demo-frontend-host>
```

`public_demo` keeps the public API read-only, enables in-app rate limiting and
security headers by default, uses a smaller default request body limit, and
continues to deny admin/user/canonical mutation routes. See
`docs/PUBLIC_DEMO_ENVIRONMENT.md`, `docs/PUBLIC_DEMO_MONITORING.md`, and
`docs/PUBLIC_DEMO_ABUSE_PROTECTION.md`.

## MVP Runtime Notes

- `/health` is liveness-only. `/ready` checks configuration validity and database reachability with a minimal query; it does not require seeded demo data.
- API errors use safe responses with `request_id`; `X-Request-ID` is returned on normal and error responses. Basic in-process rate limiting, request size limits, and security headers are infrastructure safeguards, not authentication. Current market exploration endpoints remain unauthenticated.
- Full output GET endpoints assemble payloads on read without creating or updating `OutputMetadata`. Seed flows and output-build job handlers still write cache metadata.
- Freshness metadata now reports `freshness_status` as `fresh`, `stale`, or `unknown`; `unknown` means the output had no tracked freshness window.
- Event invalidation has a narrow DB-session-backed apply path that marks existing fresh `OutputMetadata` rows stale for scoped region/company/comparison outputs. Dispatch callers must use the session-backed path to apply stale marking; otherwise routing/enqueue still happens and the dispatch result reports stale marking as skipped. It does not delete rows, rebuild outputs, enqueue jobs beyond existing routing behavior, or run workers.
- Opaque scheduler-generated `dependency_refs` remain structural, but the worker runtime now supports optional DB-backed refs such as `region:greater_boston@v1` when callers provide a database resolver.
- Queue dedupe has an application-level check plus a partial unique index for active `dedupe_key` rows on SQLite/PostgreSQL. This provides DB-level protection for supported databases, but it is still not an external broker, distributed queue, or distributed lock.
- SQLite seeding is the local demo path. Demo seed setup applies Alembic migrations before inserting data.
- Contextual challenge and audit backend services/job handlers exist, but they are not public API endpoints and are not registered in the default runtime worker registry.
- Layer 11A retention foundation reuses protected user-owned tables for watchlists and scoring controls. Watchlists store references only; scoring previews are personalized overlays and do not mutate canonical/default scores.
- Layer 11B adds in-app alert metadata and region-expansion workflow contracts without notification delivery or a second ingestion system.
- Layer 11C adds read-only visualization surfaces and deterministic evidence-packet guidance. External AI provider integration, maps/heatmaps without precise data, and generated market facts remain deferred.

Remaining external-production work includes deployment hardening, provider-side account deletion/session revocation, broader security hardening, observability, distributed queue/broker integration, artifact storage/cache serving, and multi-worker stress testing.

## CI Checks

The GitHub Actions workflow runs the same core checks locally available from
the repo root:

```bash
python -m pytest
python -m ruff check alembic backend scripts tests/
APP_ENV=local DATABASE_URL=sqlite:////private/tmp/jmi-ci-migrations.db python -m alembic upgrade head
cd frontend && npm run lint
cd frontend && npm run test
cd frontend && npm run build
```

## Core Layers

1. Canonical market truth
2. Derived output objects
3. User-specific personalization overlays

## Important Docs

- `CLAUDE.md`
- `docs/MVP_SCOPE.md`
- `docs/SLICE_PLAN.md`
- `docs/AUTH_USER_FOUNDATION.md`
- `docs/DATA_MODEL.md`
- `docs/API_SURFACES.md`
- `docs/architecture/ENGINEERING_IMPLEMENTATION_BLUEPRINT.md`
- `docs/runbooks/neon_backup_restore.md`
