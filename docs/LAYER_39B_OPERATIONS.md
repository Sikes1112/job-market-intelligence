# Layer 39B Operations, Reliability, and Deployment

> **Historical delivery record.** The topology, migration head, and lack of a Render descriptor below predate the current single-service public guest deployment. See [Deployment architecture](ENGINEERING_GUIDE.md#deployment-architecture) and [Operations](ENGINEERING_GUIDE.md#operations).

This document records the Layer 39B operational baseline implemented against
the repository as it exists after Layer 35-39A. It is intentionally bounded:
the app remains a FastAPI backend, Vite/React frontend, SQLAlchemy/Alembic
database app, and deterministic local/CI workflow. It does not add Kubernetes,
a distributed metrics stack, a custom backup service, or a new admin console.

## Runtime Architecture

- Backend: FastAPI served by `uvicorn backend.api.app:app`.
- Database: SQLAlchemy with PostgreSQL for staging/production and SQLite for
  local/test/demo. `postgres://` and `postgresql://` URLs are normalized to the
  psycopg driver.
- Migrations: Alembic, current head `0039_current_opportunity_backend`.
- Frontend: Vite/React build under `frontend/`; local dev uses the Vite proxy
  when `VITE_API_BASE_URL` is unset.
- Deployment configuration: no committed Render, Vercel, Docker, or Procfile
  descriptors were present. README documents Vercel frontend, Render Python web
  service, and Neon PostgreSQL settings.
- Background work: durable `jobs` records plus refresh scripts under `scripts/`.
  The local worker uses the existing queue adapter; RQ can be used when a Redis
  URL is supplied by the runtime.
- External dependencies: Auth0/JWKS for protected user routes, Stripe when
  billing secrets are configured, governed Current Opportunities sources, and
  optional error monitoring through the application seam.

## Observability

### Logs

Requests emit structured JSON logs through `backend.shared.logging.JsonFormatter`.
The formatter applies Batch 39A redaction to all `extra_fields` and exception
text. Request logs include safe context:

- `request_id`
- `method`
- `path` without query string
- normalized `route`
- `status_code`
- `duration_ms`
- `error_type`

Logs must not include authorization headers, cookies, tokens, provider
credentials, raw request bodies, resume content, journal content, or private
decision payloads.

### Request IDs

`X-Request-ID` is accepted only when it is bounded and matches the safe request
ID character policy. Unsafe or overlong inbound IDs are replaced. Responses
include `x-request-id` for support correlation.

### Metrics

`backend.operations.metrics.InMemoryMetricsRegistry` records per-process HTTP
metrics:

- method
- normalized route
- status class
- request count
- 5xx error count
- average and max duration

Labels intentionally exclude raw user IDs, arbitrary URLs, query strings,
opportunity IDs, and exception messages. The registry is per process; platform
metrics remain the source of truth for infrastructure CPU/memory/restarts.

Detailed metrics are available only to admin-read operators:

```bash
GET /admin/operations/metrics
```

### Error Monitoring

`backend.operations.error_monitoring.ErrorMonitor` is a fail-open integration
seam. With no external provider configured, errors are still captured in safe
structured logs. Production may attach a provider adapter at
`app.state.error_monitor` or through a future initialization hook. Monitoring
failures are swallowed and must not fail user requests.

### Health

`GET /health` is liveness-only. It returns process/app identity and does not
touch the database.

`GET /ready` checks whether the instance can serve normal DB-backed traffic:

- database connectivity via `SELECT 1`;
- schema revision visibility;
- current Alembic compatibility when
  `READINESS_REQUIRE_MIGRATION_CURRENT=true`.

`READINESS_REQUIRE_MIGRATION_CURRENT` defaults to true for
`staging`/`production`/`prod` and false for local/test/demo environments.

Detailed operational health is admin-read protected:

```bash
GET /admin/operations/health
```

It returns readiness, safe metrics summary, database/schema status, generic job
summary, Current Opportunities refresh summary, environment, and release ID. It
does not return database URLs, secrets, provider tokens, raw payloads, stack
traces, or private user records.

### Release Identification

Set `RELEASE_ID` to the platform commit SHA or deployment ID. `/health`,
`/ready`, and `/admin/operations/health` expose only this safe release string.

## Production Rate-Limit Topology

The repository has no committed process manager or horizontal-scaling
descriptor. The documented Render start command is:

```bash
uvicorn backend.api.app:app --host 0.0.0.0 --port $PORT
```

That command starts one effective backend process per service instance unless
Render settings are changed outside the repository. Under that current
documented topology, the Batch 39A in-process limiter is suitable as the app's
current abuse-control layer. If production enables multiple worker processes,
multiple Render instances, or autoscaling, limits become per-memory-space
defense in depth and must be paired with platform-level limits or a bounded
shared limiter.

## Backup And Restore

Durable state lives primarily in the relational database:

- users, profiles, external identity tombstones;
- preferences, saved artifacts, alerts;
- Career Identity facts/import metadata/consent;
- Career Decisions, outcomes, journals, plans, applications;
- Deep Decision Intelligence;
- Career Agent memory/tool approval records;
- Current Opportunities sources/runs/observations/matches/state;
- orchestration jobs and admin event logs;
- billing/provider reference records.

No committed blob/file store or vector-memory store was found. Frontend build
artifacts are reproducible from source and are not primary durable data.

Production backup owner: Neon/database operator. Mechanism: Neon-managed backup
and point-in-time restore when enabled for the active plan. Access to restore
targets and database credentials must stay in platform/Neon secret storage.

Local proof performed in 39B:

- created an Alembic-upgraded SQLite source database;
- seeded representative Layer 35-39A state;
- produced a SQLite backup artifact with the SQLite backup API;
- restored into an isolated target database;
- verified representative records, FK integrity, Alembic revision, and app
  readiness against the restored target.

This is `BACKUP_RESTORE_PROOF_PARTIAL` for production because this environment
does not provide a PostgreSQL/Neon restore branch or credentials. A production
restore drill must use `docs/runbooks/neon_backup_restore.md`.

## Migration Operations

Normal production migration workflow:

```bash
APP_ENV=prod DATABASE_URL=<production-url> python -m alembic current
APP_ENV=prod DATABASE_URL=<production-url> python -m alembic upgrade head
```

`scripts/init_db.py` remains a local/demo wrapper and is blocked for
staging/prod environments. Production deployments must run Alembic explicitly
before routing traffic to a release that requires the new schema.

Readiness surfaces schema status:

- `current`: DB revision equals the repository Alembic head.
- `unversioned`: model tables may exist, but Alembic history is absent.
- `mismatch`: DB has an Alembic revision different from the expected head.
- `unavailable`: revision could not be read safely.

Staging/production readiness fails unless schema status is `current`.

Recovery guidance:

- Failed migration before any schema changes or revision advancement: fix the
  cause and retry `alembic upgrade head`.
- PostgreSQL migrations should run inside Alembic's PostgreSQL transactional
  DDL context for repository-style DDL. If the transaction rolls back cleanly
  and the revision remains unchanged, retry is normally safe after the root
  cause is fixed.
- SQLite reports non-transactional DDL. A migration failure can leave partially
  created tables/indexes while `alembic_version` remains at the prior revision.
  Automatic retry on that same database is unsafe unless an operator proves the
  partial schema has been corrected.
- Current unversioned local/demo schema: `upgrade_database(...,
  allow_existing_schema_stamp=True)` may stamp only SQLite when the schema
  exactly matches current metadata.
- Production unversioned schema: stop and create an explicit adoption plan; do
  not stamp production ad hoc. `alembic stamp` is not failed-migration recovery
  unless schema equivalence has been independently established.
- Non-transactional or partially applied migration: restore from a pre-migration
  backup/branch or apply a reviewed forward fix; do not assume retry or
  downgrade is safe.
- Backward-incompatible migration: prefer forward fix or database restore.
  Application rollback may be unsafe after an incompatible DB migration.

Layer 39B proof now covers both strict readiness rejecting an unversioned
current schema and a controlled failed upgrade from
`0038_deep_decision_intelligence` toward `0039_current_opportunity_backend`.
The failed SQLite upgrade left partial `0039` tables while `alembic_version`
remained at `0038`; strict readiness rejected it, retry on the same partial
database failed, and recovery succeeded from a pre-upgrade backup followed by a
normal upgrade to head.

## Deployment

Frontend:

- provider documented: Vercel;
- root: `frontend/`;
- install: `npm ci`;
- build: `npm run build`;
- output: `dist`;
- runtime env: only `VITE_*` public configuration, never backend secrets.

Backend:

- provider documented: Render Python web service;
- build: `pip install -r requirements.txt`;
- start: `uvicorn backend.api.app:app --host 0.0.0.0 --port $PORT`;
- runtime env: `APP_ENV=prod`, `DATABASE_URL`, exact
  `CORS_ALLOWED_ORIGINS`, Auth0 config, rate/security settings, optional Stripe
  secrets, and `RELEASE_ID`.

Release procedure:

1. Run backend tests, ruff, frontend lint/build/tests, and Alembic upgrade check.
2. Confirm production secrets and non-secret settings are present in the
   deployment platform.
3. Confirm `RELEASE_ID` is the release commit or deployment ID.
4. Check the current DB revision with `alembic current`.
5. Apply `alembic upgrade head` once, outside app startup workers.
6. Deploy backend and frontend.
7. Verify `/health`, `/ready`, and bounded smoke endpoints.
8. Inspect logs for request IDs, 5xx rates, and operational errors.

## Rollback

Frontend rollback follows Vercel's previous deployment promotion/rollback
workflow.

Backend rollback follows Render's previous deploy rollback/redeploy workflow.

Database compatibility governs whether app rollback is safe. Production
migrations should follow expand/contract compatibility: add backward-compatible
schema first, deploy compatible app code, migrate data, then remove old schema
in a later release. If a release applied a backward-incompatible migration, do
not roll application code back until the DB compatibility impact is understood.
Use forward fix or a validated Neon restore target when necessary.

## Failure Isolation

- Primary database unavailable: `/ready` returns not ready; DB-backed API
  requests fail with safe 503 envelopes; `/health` remains alive.
- Auth0/JWKS unavailable: protected access fails closed; request logs and error
  monitoring capture safe operational context. Public unauthenticated market
  routes are unaffected.
- Current Opportunities source unavailable: refresh runs record failed or
  partial state; prior durable opportunity data is not deleted solely because a
  refresh fails; operator health exposes safe refresh status.
- AI/expensive provider failure: no active external AI provider dependency was
  found in repository runtime paths. Existing deterministic services should fail
  specific operations rather than unrelated APIs.
- Stripe unavailable or unconfigured: billing operations fail or remain
  disabled; non-billing routes continue.
- Monitoring failure: fail-open and does not affect normal request handling.
- Failed/stale jobs: generic job and Current Opportunities summaries expose
  counts, recent failures, and stale running counts.

## Operator Tools

Added protected read-only surfaces:

- `GET /admin/operations/health`
- `GET /admin/operations/metrics`

Authorization reuses existing admin roles. `read_only_operator`,
`data_reviewer`, and `admin` can read operations diagnostics. Normal users and
anonymous callers are rejected.

No operator mutations were added in 39B. Retry/clear/force-refresh operations
remain deferred until the existing job runner exposes a bounded, audited command
surface that warrants it.

## Residual Operational Risks

- Application metrics are per process and are not globally strict in
  horizontally scaled deployments.
- Production restore proof remains partial until exercised against a Neon
  restored branch or equivalent PostgreSQL target.
- No committed Render/Vercel descriptors exist, so provider-side settings must
  be verified manually before production launch.
- Formal bad-deploy, failed-migration, provider-outage, and restore drills are
  deferred to Batch 39C.
