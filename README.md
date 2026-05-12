# Job Market Intelligence Platform

Local MVP demo for a job-market intelligence platform.

The product maps companies, hiring activity, entry-level opportunity, and market strength across cities, metros, and labor regions.

Comparison is a feature, not the product core.

## What Is Implemented

- Backend API for health, region outputs, company outputs, Boston vs SF comparison, and request-scoped personalized discovery.
- Deterministic seeded demo data for Greater Boston and Greater San Francisco / Silicon Valley.
- Vite + React + TypeScript frontend demo under `frontend/`.
- Local SQLite demo workflow via `scripts/seed_demo.py`.

Current status: internal-production baseline for a local, single-process architecture. It is suitable for local demo/presentation and internal reliability exercises, but it is not external-production ready. It does not include auth, accounts, saved profiles, scraping, external APIs, maps, admin tooling, or production security/deployment configuration.

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
- `GET http://127.0.0.1:8000/regions`
- `GET http://127.0.0.1:8000/regions/greater_boston`
- `GET http://127.0.0.1:8000/regions/greater_sf`
- `GET http://127.0.0.1:8000/compare?region_a=greater_boston&region_b=greater_sf`
- `POST http://127.0.0.1:8000/discover/personalized`

## MVP Runtime Notes

- Full output GET endpoints assemble payloads on read without creating or updating `OutputMetadata`. Seed flows and output-build job handlers still write cache metadata.
- Freshness metadata now reports `freshness_status` as `fresh`, `stale`, or `unknown`; `unknown` means the output had no tracked freshness window.
- Event invalidation has a narrow DB-session-backed apply path that marks existing fresh `OutputMetadata` rows stale for scoped region/company/comparison outputs. Dispatch callers must use the session-backed path to apply stale marking; otherwise routing/enqueue still happens and the dispatch result reports stale marking as skipped. It does not delete rows, rebuild outputs, enqueue jobs beyond existing routing behavior, or run workers.
- Opaque scheduler-generated `dependency_refs` remain structural, but the worker runtime now supports optional DB-backed refs such as `region:greater_boston@v1` when callers provide a database resolver.
- Queue dedupe has an application-level check plus a partial unique index for active `dedupe_key` rows on SQLite/PostgreSQL. This provides DB-level protection for supported databases, but it is still not an external broker, distributed queue, or distributed lock.
- SQLite seeding is the local demo path. Existing demo DBs should be recreated or migrated manually after schema changes; Alembic-style migrations and production deployment configuration remain out of scope.
- Contextual challenge and audit backend services/job handlers exist, but they are not public API endpoints and are not registered in the default runtime worker registry.

Remaining external-production work includes migrations, deployment configuration, auth/security, observability, distributed queue/broker integration, artifact storage/cache serving, and multi-worker stress testing.

## Core Layers

1. Canonical market truth
2. Derived output objects
3. User-specific personalization overlays

## Important Docs

- `CLAUDE.md`
- `docs/MVP_SCOPE.md`
- `docs/SLICE_PLAN.md`
- `docs/DATA_MODEL.md`
- `docs/API_SURFACES.md`
- `docs/architecture/ENGINEERING_IMPLEMENTATION_BLUEPRINT.md`
