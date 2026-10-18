# Layer 44A Beta Operations and Release Runbook

## Production Architecture

The repository now defines one intended controlled-beta topology:

- Vercel serves the Vite SPA from `frontend/` using `frontend/vercel.json`.
- Render runs the FastAPI backend from the repository root using `render.yaml`.
- Neon PostgreSQL is the production database. SQLite is local/test/private-demo only.
- Auth0 supplies SPA login and backend JWT/JWKS verification.
- Repository-controlled static assets are emitted by Vite from `frontend/public/`.
- The eight curated market datasets under `data/imports/` supply beta market intelligence.
- No production-quality Current Opportunity provider is configured in the repository. The beta is therefore a market-intelligence product with explicitly unavailable or partial current-job coverage.
- Render and Vercel environment stores own secrets. No secret belongs in Git.

Auth0 must allow the exact Vercel origin, callback path, logout origin, and web origin. `CORS_ALLOWED_ORIGINS` must be that same exact HTTPS frontend origin. Wildcards are rejected.

## Required Environment Contract

Backend production/staging startup fails unless these are valid:

- `APP_ENV=production` (or `staging`)
- `DATABASE_URL` using PostgreSQL, normally Neon with TLS parameters
- `CORS_ALLOWED_ORIGINS` containing exact HTTPS origins
- `AUTH0_ISSUER` and `AUTH0_AUDIENCE`
- `RELEASE_ID` (Render uses `RENDER_GIT_COMMIT` in `render.yaml`)
- `RATE_LIMIT_ENABLED=true`
- `SECURITY_HEADERS_ENABLED=true`
- `API_DOCS_ENABLED=false`

`BETA_ACCESS_REQUIRED` defaults true in staging/production. `ERROR_MONITORING_DSN` and Stripe settings are optional integrations; absence is reported as `not_configured` and does not disable the core workflow. Local verified-claims auth and `VITE_LOCAL_AUTH` are accepted only by local/test development code paths.

Deployed frontend builds set `VITE_DEPLOYMENT_MODE=beta` and fail at module startup if API URL, Auth0 domain/client/audience, or `VITE_RELEASE_ID` is absent. Use the same Git SHA for frontend `VITE_RELEASE_ID` and backend `RELEASE_ID`.

## Data Modes and Supported Scope

Production bootstrap imports only curated reference/evidence data. It never invokes `scripts.seed_demo`, and never creates demo users, entitlements, decisions, applications, or fake jobs.

The governed universe remains exactly Boston, New York, San Francisco Bay Area, Seattle, Washington DC, Austin, Atlanta, and Chicago. A national map is navigation context, not nationwide evidence coverage.

Run the gate before deployment:

```bash
python -m scripts.beta_reference_data validate
python -m scripts.beta_reference_data bootstrap
python -m scripts.beta_reference_data report
```

All operations are rerunnable. Bootstrap validates every repository dataset before opening its transaction, then performs canonical import and post-import trust/output refresh. A non-current schema or failed market validation exits nonzero. The 2026-10-10 quality run classifies all eight June 2026 datasets as current under the repository's governed freshness policy; operators must rerun the gate at every release and refresh rather than override it when it later expires.

Current Opportunity reporting records real-provider and synthetic-demo source counts,
observed record count, and one of `real_provider`, `synthetic_demo`, `mixed`, or
`coverage_unavailable`. Never describe it as exhaustive, complete, or real-time.

## Beta Access and Invitation

The existing Layer 40 cohort model is the single beta-access authority. Core Profile, Explore, Compare/Prioritize, Decision/Action/Application, and My Search routes require an active cohort membership in production. Local/test defaults keep the gate off.

1. The invited person signs in once. `GET /me` creates/resolves the internal user but does not grant beta access.
2. An existing admin creates the cohort once:

   ```http
   POST /admin/beta/cohorts
   {"cohort_key":"controlled_beta_1","name":"Controlled beta 1","status":"active"}
   ```

3. The admin grants access without direct database mutation:

   ```http
   POST /admin/beta/memberships
   {"user_id":"<internal-user-id>","cohort_key":"controlled_beta_1","status":"active"}
   ```

4. Verify `GET /me/beta-access`, then `GET /me/explore/context` returns 200. A nonmember receives a safe 403.

Core redesigned beta routes do not require a paid plan. Legacy monetized features retain their existing plan/feature enforcement and are not part of the beta acceptance gate.

## Health, Errors, and Observability

- `GET /health` is liveness only: service, environment, and release ID.
- `GET /ready` verifies database connectivity and, in staging/production, that Alembic is at the single repository head. Optional providers do not fail readiness.
- `/admin/operations/health` and `/admin/operations/metrics` are admin-only.
- production OpenAPI, Swagger, and ReDoc are disabled.
- every response carries `X-Request-ID` and `X-Release-ID`; both are exposed to the browser through CORS.
- structured request logs include UTC timestamp, severity, route, request ID, release, status, latency, exception class/type, and a one-way pseudonymous principal reference when verified claims exist.
- request logs never include request bodies, tokens, Profile facts, résumé text, application notes, or raw user identifiers.
- uncaught and database exceptions use the provider-neutral error-monitor adapter, with safe response bodies and no stack trace.
- frontend rendering errors have a recoverable boundary; API requests time out after 15 seconds and are not automatically retried. Mutations therefore cannot be silently repeated.

## Release Procedure

### Before

1. Record branch, HEAD, expected release SHA, and `git status`.
2. Run backend/frontend/full repository gates.
3. Confirm `alembic heads` returns only `0046_beta_production_hardening`.
4. Review the migration and check Neon PITR/restore retention in the provider console.
5. Run `python -m scripts.beta_reference_data validate`; resolve every blocker.
6. Confirm Auth0 callback/logout/origin values and exact CORS origin.
7. Confirm the designated smoke/acceptance user is active in the beta cohort.

### Deploy

1. Record a Neon restore point or verified PITR time.
2. Render pre-deploy runs `alembic upgrade head`, verifies one head through readiness, and bootstraps curated beta data.
3. Deploy/restart the backend. Require `/health` and `/ready` 200 with the expected release.
4. Deploy the Vercel frontend with the same release SHA.

### Verify

Run read-only production smoke:

```bash
BETA_SMOKE_BASE_URL=https://<backend> \
BETA_SMOKE_ACCESS_TOKEN=<designated-user-token> \
python -m scripts.release_smoke
```

The script checks health, readiness, current user, Profile read, Explore Context, Explore markets, and My Search. It performs no durable writes. Then confirm frontend sign-in, Explore navigation, error monitor intake, and release correlation.

## Full Acceptance Gate

Use a designated non-production or staging beta account. Do not use an arbitrary production user.

### Empty user

1. Sign in and verify Profile has no Career Identity.
2. Add essential role/opportunity/work-arrangement/geography facts and grant personalization consent.
3. Open Explore and confirm personalized evaluation or an explicit governed abstention.
4. Inspect two markets, select 2–4, and generate comparison.
5. Save and prioritize one market.
6. Open My Search, generate next steps, add/complete an action, and track an application.
7. Sign out; use a fresh browser context; sign in and verify restoration.

### Returning user

Verify Profile, saved comparison, active pursuit, next action, application, status history, and historical comparison version all return after a fresh session.

### Lifecycle/privacy

With foreign keys enabled, deactivate a test user containing Profile, comparison, Decision, actions, application, and telemetry. Verify the user can no longer authenticate and a second user is unchanged.

### Failure drills

- Disable the Current Opportunity provider: Explore, Compare, and My Search must still work with honest unavailable coverage.
- Break database connectivity in staging: `/ready` must return 503; APIs must return safe errors with request IDs.
- Expire an Auth0 session: the frontend must offer sign-in rather than losing local selection state.
- Stop the backend: Explore, comparison, and My Search must show recoverable retry states.

Record environment URL, release SHA, database engine, provider mode, request IDs for failures, and pass/fail evidence. Localhost is not production verification.

## Concurrency and Integrity Contract

- Saved comparison identity is DB-unique per user; same-user save/prioritize is serialized on the user row on PostgreSQL.
- Active action plans have a partial unique index per Decision; generation also locks the Decision row.
- tracked Current Opportunities have an explicit canonical ID and DB uniqueness across user + pursuit + opportunity. Duplicate races resolve to the existing application.
- application transitions lock the application row before validating the current state. Competing legal transitions serialize; the second request is evaluated against the committed winner and fails cleanly when no longer legal.
- equivalent active Prioritize requests serialize on the user row before the existing equivalence check.

SQLite covers functional and constraint tests but does not emulate PostgreSQL row locking. Run the focused concurrency tests against a staging Neon branch before cohort admission.

## Measurement and Feedback

The admin beta funnel now reconstructs:

`signed in → Profile sufficient → Explore viewed → market inspected → 2+ selected → comparison generated → saved/prioritized → My Search viewed → action completed → application tracking started → return`

Decision-useful metrics are activation (personalized Explore), exploration (market inspected/2+ selected), deliberation (comparison), commitment (prioritize), execution (completed action/application), and return after the existing 30-minute session boundary. These are learning signals, not optimization targets.

The authenticated shell exposes a small Beta feedback form. It creates an existing support case with optional user text plus route and release ID. It does not attach Profile facts. Operators use `/admin/support-cases`, `/admin/beta/analytics`, `/admin/product-events`, `/admin/beta/cohorts`, `/admin/feature-gates`, and `/admin/operations/*` for the narrow beta view.

## Small-Cohort Validation Plan

- Start with 5–10 invited early-career users considering geographic options.
- Ask them to describe their search, identify 2–3 markets, compare, prioritize one, find a next action, and track one application. Do not prescribe clicks.
- Observe comprehension of Fit versus job coverage, comparison confidence, Prioritize meaning, and My Search next action.
- Collect the funnel above plus the embedded feedback form and a short operator note outside analytics.
- Stop admission for any P0/P1.

Exit criteria: no open P0/P1; no systemic auth or data-loss issue; users distinguish market Fit from current-job coverage; comparison/Prioritize/My Search are understood; no fatal market quality contradiction; and production-like performance is acceptable. Tiny-cohort retention is not an exit criterion.

Severity:

- P0: security incident, data loss/cross-user exposure, or system unavailable.
- P1: core workflow impossible or materially misleading.
- P2: important friction with a workaround.
- P3: polish.

## Rollback

- Frontend: redeploy the prior Vercel artifact; confirm its backend API compatibility.
- Backend: redeploy the prior Render commit only if it supports the current schema.
- Database: do not assume Alembic downgrade is safe. `0045` and `0046` refuse downgrade when new analytics events exist. Prefer forward repair or Neon PITR/branch restore after writes are paused and the data-loss window is understood.
- After any rollback, run `/health`, `/ready`, read-only smoke, Auth0 sign-in, Explore, and My Search; record release IDs.

Use `docs/runbooks/neon_backup_restore.md` for restore steps. The database owner must verify the real Neon retention window and perform a non-production restore drill; repository code cannot prove provider backup coverage.
