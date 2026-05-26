# Public Demo Environment

Layer 10 public demo mode is for externally viewable demos. It is safer than
the private/internal demo posture, but it is not production readiness.

## Environment Modes

- `local`: developer/local demo mode. May use the local SQLite default. Durable
  mutation workflows are available when their normal auth/role checks pass.
- `private_demo`: restricted demo mode against an explicitly configured
  database. Authenticated user/admin mutation workflows may be exercised.
- `staging`: production-like infrastructure validation mode. Requires an
  explicit non-SQLite database plus enabled protection flags.
- `public_demo`: externally viewable demo mode. Requires an explicit database
  URL, exact CORS origin, enabled in-app abuse protections, and a fail-closed
  public API allowlist.
- `production`: external production mode. Requires an explicit non-SQLite
  database plus enabled protection flags. Public demo mode must not be treated
  as production.

Legacy `dev` and `prod` strings remain accepted for compatibility. `prod`
has the same strict infrastructure defaults as `production`.

## public_demo Allowlist

In `APP_ENV=public_demo`, the backend exposes only these HTTP surfaces:

- `GET /health`
- `GET /ready`
- `GET /regions`
- `GET /regions/search`
- `GET /regions/{region_id}`
- `GET /regions/{region_id}/sources`
- `GET /companies/search`
- `GET /companies/{company_id}`
- `GET /companies/{company_id}/regions`
- `GET /companies/{company_id}/sources`
- `GET /compare`
- `POST /discover/personalized`
- `OPTIONS *` for preflight handling

`POST /discover/personalized` is allowed because it is request-scoped and does
not persist preferences, snapshots, output metadata, scores, or canonical facts.

## public_demo Denials

All non-allowlisted routes receive `403` with error type
`public_demo_read_only`. This includes unknown future routes, so new mutation
surfaces fail closed until they are explicitly reviewed.

Denied mutation surfaces:

- Admin review lifecycle mutations:
  `POST /admin/review/audit-finding-transitions`
- Override mutations:
  `POST /admin/overrides`,
  `POST /admin/overrides/{override_id}/activate`,
  `POST /admin/overrides/{override_id}/revoke`
- Repair mutations:
  `POST /admin/repair-actions`,
  `POST /admin/repair-actions/{repair_action_id}/execute`
- User-owned writes:
  `PUT /me/preferences`,
  `DELETE /me/preferences`,
  `POST /me/scoring-preview`,
  `POST /me/saved-market-artifacts`,
  `DELETE /me/saved-market-artifacts/{saved_artifact_id}`,
  `GET /me/alerts`,
  `POST /me/alerts/{user_alert_id}/read`,
  `POST /me/alerts/{user_alert_id}/dismiss`,
  `POST /me/explanations/{entity_type}`,
  `POST /me/recommendation-snapshots`,
  `DELETE /me`
- Canonical write-shaped requests such as `POST`, `PUT`, `PATCH`, or `DELETE`
  under public market paths.

Protected `GET /me` and `GET /admin/*` routes are also denied in public demo.
Although they are GET routes, the current auth boundary can create or update
internal user identity/profile rows while resolving the caller. Public demo
therefore treats them as non-public durable state surfaces.

## Ingestion And Refresh

There are currently no registered public API routers for ingestion or refresh
execution/enqueueing. The backend does contain ingestion services, refresh
queue/runtime services, and local/demo scripts. Those are not mounted in the
FastAPI app.

Local/demo database scripts are blocked when `APP_ENV=public_demo`, `staging`,
`production`, or legacy `prod`. Initial public-demo data should be prepared
before running the backend in public demo mode.

## Ambiguous Surfaces

- Non-persistent POST: `POST /discover/personalized` and
  `POST /recommendations/strategy` are explicitly allowed and covered by tests
  asserting they do not persist output metadata or canonical market truth.
- Protected reads: denied unless a future route proves it has no durable auth
  side effects.
- Unknown routes: denied in public demo before FastAPI can resolve them.

## Why public_demo Is Not Production

Public demo mode provides read-only API posture and visible demo limitations.
It does not complete production readiness. Public-demo monitoring posture is
documented in `docs/PUBLIC_DEMO_MONITORING.md`. Public-demo abuse protection
posture is documented in `docs/PUBLIC_DEMO_ABUSE_PROTECTION.md`. Provider
operations and final launch audit remain separate Layer 10 work.

## Why public_demo Is Stricter Than private_demo/staging

`private_demo` and `staging` may need authenticated mutation workflows for
review, QA, admin repair, and persistence testing. `public_demo` is intended
for strangers to view safely, so it blocks all durable mutation and all
protected state surfaces by default.
