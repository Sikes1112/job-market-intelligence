# Layer 39A Security And Privacy Hardening

> **Historical delivery record.** This captures the OIDC/Auth0 security baseline before public guest sessions were added. See the [Engineering Guide](ENGINEERING_GUIDE.md#authentication-and-isolation) for current runtime distinctions and guest isolation.

## Repository-Grounded Architecture

The backend is a FastAPI application with SQLAlchemy models and Alembic
migrations. The frontend is a Vite/React SPA using Auth0's React SDK. The
database boundary is SQLAlchemy sessions created from runtime `DATABASE_URL`.
The application uses Auth0/OIDC bearer access tokens for protected backend
routes and does not store local web sessions or passwords.

Auth is enforced in backend middleware/dependencies:

- `Auth0JWTMiddleware` validates bearer JWT shape, algorithm, signature via
  JWKS, issuer, audience, `exp`, `nbf`, `iat`, and supported token use.
- `get_current_user` resolves verified provider claims to an internal `users`
  row using `provider + issuer + subject`.
- `X-Verified-OIDC-Claims` is a local/test-only already-verified claims stub
  and is rejected outside local/test.
- Protected `/me`, Career Identity, Career Decisions, Deep Decision
  Intelligence, Current Opportunities matches, and admin routes use backend
  current-user dependencies. Frontend route protection is not a security
  boundary.

Current Opportunities provider/source state is shared market data. Authenticated
opportunity matches are computed from the current user's Career Identity,
Decision, and Strategic Review data. Diagnostics and refresh runs are admin
gated.

## Assets

Sensitive assets in the current repository are account identity, external auth
identity mappings, bearer access tokens in transit, Auth0 settings, API keys,
Stripe secrets, database URLs, user profiles, preference profiles, saved market
artifacts, personalized recommendation snapshots, user alerts, Career Identity
facts/import metadata, imported resume/profile metadata, inferred facts,
compensation constraints, geographic constraints, decision history, decision
journal/version notes, action plans, applications, outcomes, deep decision
factors, longitudinal context, recommendation evolutions, advisory findings,
strategic reviews, Career Agent memory/tool records, provider/source
configuration, refresh/job records, logs, and export payloads.

## Trust Boundaries

- Browser to frontend: Auth0 SPA SDK obtains bearer tokens; public exploration
  works signed out.
- Frontend to backend: protected calls use `Authorization: Bearer ...`; CORS
  does not allow credentials.
- Unauthenticated to authenticated API: public market exploration is open;
  private `/me` and user-derived routes require verified claims.
- API to database: SQLAlchemy repositories/services enforce user ids on
  user-owned queries and mutations.
- API to Auth0 JWKS: backend validates provider-issued tokens.
- API to Stripe: runtime secrets stay server-side and are not exposed through
  APIs.
- Worker/job to database/provider: current repository jobs use configured
  provider/source state; user-owned opportunity matches are not persisted.
- Operator to production: settings come from runtime environment, not committed
  secret files.
- Runtime to logs: request logs are structured and redacted.

## Threat Classes And Controls

Critical findings: none left unresolved after this batch.

High findings remediated:

- Deleted-account replay: account deactivation previously deleted the external
  auth identity mapping. A still-valid Auth0 token could authenticate again and
  create a new active internal user. Layer 39A now retains a scrubbed
  provider/issuer/subject tombstone, blocks deactivated users during auth
  resolution, and avoids profile resync.
- Incomplete privacy export/delete for Layer 36/37: `/me/export` and `/me`
  deactivation omitted Career Decisions and Deep Decision Intelligence rows.
  Layer 39A exports those rows and deletes them transactionally before
  deactivating the user.

Medium findings remediated:

- Coarse rate limiting: the prior middleware used one client-IP bucket. Layer
  39A adds endpoint-class policies for anonymous reads, authenticated reads,
  mutations, and expensive routes. Authenticated limits key on verified
  issuer/subject when available.
- Structured log leakage: the previous JSON formatter could emit arbitrary
  sensitive `extra_fields` or exception text. Layer 39A redacts sensitive keys
  and secret-shaped strings recursively.

Low findings:

- Public market exploration remains unauthenticated by product design. It is
  read-oriented, request-scoped, and covered by request size/rate limits.
- Auth0 provider-side account deletion and token revocation are not implemented
  in this repository. App-level deactivation blocks reuse at the app boundary,
  but the user must manage provider sessions through Auth0 until a protected
  provider-management integration is added.

Informational findings:

- No local password, password-reset, CSRF-token, or cookie-authenticated session
  model exists. CORS has `allow_credentials=False`, so cookie-auth CSRF controls
  are not applicable to the current architecture.
- No separate embeddings/vector memory subsystem exists. The app's durable
  memory-equivalent data is Career Identity, inferred facts, decisions, deep
  decision outputs, Career Agent memory records, and Career Agent tool preview
  records; app-level deletion removes those where present.

## Authentication Model

Production protected routes require valid Auth0 bearer JWTs. Missing, malformed,
invalid, expired, or unsupported tokens fail closed with generic authentication
errors. The local/test claims header is explicitly gated by environment and
cannot silently operate in staging/production.

App deactivation sets `users.status = deactivated`. A later authentication
attempt for the same provider/issuer/subject fails with a generic 401 before
profile sync.

## Authorization And User Isolation

User ownership is represented by `user_id` columns on app-owned tables. The
Career Identity, Career Decisions, Deep Decision Intelligence, personalization,
alert, and Career Agent services query and mutate through the authenticated
current user's `user_id`. Parent/child resources are resolved through owned
aggregate lookups before mutation.

Shared market data such as regions, companies, scores, source observations,
raw ingestion records, output metadata, provider source registry state, and
Current Opportunities source state is not user-owned. User-specific derived
state is either computed request-scoped from the current user's data or stored
with `user_id`.

## Rate Limiting

The middleware keeps bounded in-process buckets:

- anonymous reads: `RATE_LIMIT_ANONYMOUS_REQUESTS` per
  `RATE_LIMIT_ANONYMOUS_WINDOW_SECONDS`
- authenticated reads: `RATE_LIMIT_AUTHENTICATED_REQUESTS` per
  `RATE_LIMIT_AUTHENTICATED_WINDOW_SECONDS`
- expensive routes: `RATE_LIMIT_EXPENSIVE_REQUESTS` per
  `RATE_LIMIT_EXPENSIVE_WINDOW_SECONDS`
- mutations: `RATE_LIMIT_MUTATION_REQUESTS` per
  `RATE_LIMIT_MUTATION_WINDOW_SECONDS`

Defaults derive from the existing global limit. Expensive routes default to 20
requests/window; mutation routes default to 60 requests/window. The limiter
keys authenticated requests by verified issuer/subject and anonymous requests
by the socket client host. It does not trust forwarded headers.

This strategy is suitable for a single process and useful as defense in depth.
Horizontally scaled production must add a shared upstream or distributed
limiter before treating these quotas as globally strict.

## Privacy Lifecycle

Consent is stored on Career Identity and controls import/inference/downstream
personalization behavior in that service. Revocation keeps the identity private
and prevents downstream use of revoked processing categories.

Export returns structured JSON for the current user only. It includes account,
profile, external identity metadata, preferences, saved artifacts,
recommendation snapshots, user alerts, Career Identity, Career Decisions, and
Deep Decision Intelligence data. It also includes a sanitized representation of
Career Agent memory permissions/entries and Career Agent tool previews/audit
summaries because those rows contain user-provided private memory and
user-visible tool state. It excludes secrets, tokens, API-key raw values, local
session credentials, password hashes, internal audit row ids, other users' data,
and canonical market truth.

Deletion is app-level deactivation. It deletes current-user profile,
preferences, saved artifacts, recommendation snapshots, alerts, Career Identity,
Career Decisions, Deep Decision Intelligence, Career Agent memory, and Career
Agent tool records, then sets the user tombstone to deactivated. External auth
identity mappings are scrubbed and retained for replay prevention.

Retention currently focuses on durable deletion of user-owned personal data and
in-process rate-limit bucket expiry. There are no temporary export artifacts
persisted by `/me/export`; exports are generated directly in the response.

Provider revocation is applicable to internal API keys and integration clients
where implemented by the integrations service. Current Auth0 and Stripe
credentials are configuration-wide runtime secrets, not user OAuth tokens.
Opportunity providers are registry/configuration state, not user credentials.

## Logging And Errors

Structured logs retain request id, route path, method, status, duration, safe
error type, logger, level, and operational identifiers where callers provide
them. Redaction removes sensitive keys and secret-shaped strings including
authorization headers, cookies, bearer tokens, API keys, credentials, raw keys,
database URLs, Stripe-like secrets, webhook secrets, and nested token/secret
fields.

Production error responses use safe error envelopes and do not expose Python
stack traces, SQL text, filesystem paths, database credentials, provider
secrets, or request bodies.

## Residual Risks

- In-process API rate limiting is not globally strict across multiple app
  workers or hosts.
- Auth0 provider-side session revocation/account deletion is deferred to a
  provider-management integration.
- Raw application logs outside this service boundary must still avoid dumping
  request bodies before they reach the shared formatter.
