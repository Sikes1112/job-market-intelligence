# Auth And User Foundation

> **Historical/conditional reference.** This records the repository's Auth0 path for configured OIDC environments. The live portfolio uses isolated backend-issued guest sessions and does not require Auth0. See the current [Engineering Guide](ENGINEERING_GUIDE.md#authentication-and-isolation).

## Decision

Use Auth0 as the managed auth provider for the first production auth path.
The frontend should use Auth0-hosted login with Authorization Code Flow with
PKCE for the Vite/React SPA. The backend should accept only provider-issued
Bearer access tokens that have been validated by provider SDK/JWKS middleware.

Rationale:

- Auth0 provides managed login, signup, password reset, email verification,
  MFA, hosted identity UI, and OIDC/OAuth2 primitives.
- The repo avoids owning passwords, credential recovery, token issuance, and
  primary credential storage.
- The provider boundary is standards-shaped enough to leave a future provider
  migration possible.

References:

- Auth0 PKCE flow for single-page apps:
  https://auth0.com/docs/get-started/authentication-and-authorization-flow/authorization-code-flow-with-pkce/call-your-api-using-the-authorization-code-flow-with-pkce
- Auth0 access-token validation guidance:
  https://auth0.com/docs/secure/tokens/access-tokens/validate-access-tokens
- Auth0 JWKS signing-key distribution:
  https://auth0.com/docs/get-started/tenant-settings/signing-keys/customer-signing-keys

## Boundary

The stable external identity boundary is:

```text
provider + issuer + subject
```

For the selected provider, `provider` is `auth0`, `issuer` is the Auth0 tenant
issuer, and `subject` is the OIDC `sub` claim. Email, display name, and avatar
URL are profile metadata only. They must not be used as identity keys.

The code in `backend.auth.boundary` intentionally accepts already-validated
claims. It does not decode JWTs, issue tokens, implement login, or store
credentials. Layer 7.5 Batch B adds Auth0/JWKS middleware that validates Bearer
JWT signature, issuer, audience, expiration, and supported token/header shape
before attaching verified OIDC claims to the request.

Required protected-route runtime configuration:

- `AUTH0_ISSUER`: exact Auth0 tenant issuer, including trailing slash.
- `AUTH0_AUDIENCE`: API audience configured in Auth0.
- `AUTH0_JWKS_URL`: optional JWKS URL; defaults to
  `${AUTH0_ISSUER}.well-known/jwks.json` when omitted.
- `AUTH0_JWKS_CACHE_SECONDS`: JWKS cache TTL, default `300`.

Required frontend Auth0 SPA configuration for account UX:

- `VITE_AUTH0_DOMAIN`: Auth0 tenant domain.
- `VITE_AUTH0_CLIENT_ID`: Auth0 single-page application client id.
- `VITE_AUTH0_AUDIENCE`: API audience matching backend `AUTH0_AUDIENCE`.
- `VITE_AUTH0_REDIRECT_URI`: optional redirect URI; local demos commonly use
  `http://127.0.0.1:5173/markets`.

The Vite frontend uses Auth0's React SPA SDK with in-memory token caching.
Bearer tokens are requested through the SDK and attached only to protected
`/me` API calls. When these frontend variables are absent, the app remains in
signed-out local/demo mode and public market exploration stays usable.

Layer 7.5 protected API routes resolve the current internal user from this
already-verified claims boundary. Local/test route coverage may still pass the
same already-verified claim mapping through `X-Verified-OIDC-Claims`; that
header is a test/local boundary stub and is rejected outside local/test.

## Internal User Model

Layer 7 Batch A adds these internal user-account tables:

- `users`: internal app identity keyed by `user_id`.
- `external_auth_identities`: mapping from `provider + issuer + subject` to
  `user_id`.
- `user_profiles`: provider-sourced profile metadata for display/contact use.

Layer 7 Batch B adds durable user-owned personalization tables:

- `user_preference_profiles`: saved preference inputs such as role interests,
  industry interests, preferred regions, prestige/brand weighting, career
  stage, remote/hybrid preference, and Batch 11A scoring overlay weights.
- `saved_market_artifacts`: saved references or user-owned snapshots for
  regions, companies, role families, comparisons, and discovery results.

Layer 7 Batch C adds durable user-owned recommendation output snapshots:

- `personalized_recommendation_snapshots`: derived personalized outputs keyed
  by internal `user_id`, with the recommendation version, source version
  bundle, objective output references, input-bundle hash, and generation time
  used to produce the snapshot.

Layer 11B adds in-app user alert instances:

- `alert_events`: system-level structured change metadata derived from
  refreshable/canonical/derived data or approved change snapshots.
- `user_alerts`: current-user alert feed rows linked to one alert event and a
  user-specific relevance reason.

Layer 7 Batch D adds app-level privacy controls for Layer 7 user-owned data.
Layer 39A extends those controls across the Layer 35-37 user-owned Career
Identity, Career Decisions, and Deep Decision Intelligence tables:

- export the current internal user's account/profile metadata, Auth0 identity
  mapping metadata, saved preferences, saved market artifacts, personalized
  recommendation snapshots, Career Identity state, decision history, application
  and outcome records, and deep decision analysis outputs
- delete the current user's saved preference profile
- delete the current user's saved market artifacts
- delete the current user's personalized recommendation snapshots
- deactivate the current app user account and delete user-owned personal,
  decision, memory, and derived analysis rows covered by the current schema

Layer 9A adds a nullable `users.admin_role` field for governed admin access.
Valid non-null values are `admin`, `data_reviewer`, and
`read_only_operator`. Backend authorization dependencies enforce these roles
for admin surfaces.

Layer 9C keeps the same role vocabulary for override and repair workflows:
`admin` may activate/revoke overrides and execute safe repairs,
`data_reviewer` may propose overrides and create review-request repair records,
and `read_only_operator` may inspect admin workflow records without mutating
them.

These are app-account/user-owned tables, not canonical market truth. They do
not store or mutate:

- privacy/export/delete workflows
- objective market facts, scores, freshness, ingestion output, company state,
  or region state

Saved market artifact types are constrained to:

- `region`
- `company`
- `role_family`
- `comparison`
- `discovery_result`

Batch 11A uses saved market artifacts as watchlist entries. Watchlist snapshots
may keep user-owned display context, but they must not copy canonical scores,
region facts, company facts, freshness state, or source/provenance facts into
the user-owned table. The protected API rejects unsafe snapshot fields instead
of persisting copied market truth.

The protected `POST /me/scoring-preview` endpoint reads structured facts and
stored scores to compute a personalized overlay from the current user's saved
or preview-only scoring weights. It returns the canonical/default score labels
separately from personalized overlay scores and does not persist the overlay or
mutate market truth.

Layer 11C protected `/me/explanations/*` endpoints render deterministic
structured guidance from caller-supplied evidence packets. They are read-only:
they do not call an external AI provider, browse, scrape, persist explanation
text, or mutate canonical regions, companies, scores, freshness, provenance,
outputs, alerts, admin records, or region-expansion workflow rows.

## Privacy Controls

Batch D privacy controls are implemented at the app service boundary. Every
operation is scoped to the current internal `users.user_id`; attempts to name a
different owner are blocked before reading or deleting data.

The export operation returns structured app-owned data only:

- `users` account metadata
- `user_profiles`
- `external_auth_identities`
- `user_preference_profiles`
- `saved_market_artifacts`
- `personalized_recommendation_snapshots`
- `user_alerts`
- `career_identities`
- `career_identity_facts`
- `career_identity_imports`
- Layer 36 Career Decisions tables: decisions, context snapshots, options,
  recommendations, versions/journals, action plans, actions, applications,
  application transitions, and outcomes
- Layer 37 Deep Decision Intelligence tables: factors, longitudinal contexts,
  recommendation evolutions, advisory findings, and strategic reviews
- Career Agent memory permissions/entries and Career Agent tool previews/audit
  summaries, exported in sanitized form
- created/update timestamps and snapshot `generated_at` timestamps

Export does not include canonical market truth, regions, companies, objective
scores, source freshness/provenance rows, raw ingestion records, or output
cache records. It also excludes local session credentials, bearer tokens,
password hashes, provider access tokens, API key raw values, internal audit row
ids, raw secret-shaped values, and other users' data. Alert exports include
alert ids, event refs, relevance refs, and read/dismiss state only; they do not
inline copied alert-event market payloads.

Deleting a preference profile removes only the current user's
`user_preference_profiles` row. Existing recommendation snapshots for that
user are preserved as historical user-owned outputs and have their nullable
`preference_profile_id` cleared before the preference row is removed.

Deleting saved market artifacts removes only the current user's
`saved_market_artifacts` rows. Deleting recommendation snapshots removes only
the current user's `personalized_recommendation_snapshots` rows.

App-level account deactivation deletes the current user's profile row, saved
preference profile, saved market artifacts, personalized recommendation
snapshots, user alert rows, Career Identity rows, Layer 36 Career Decisions
rows, Layer 37 Deep Decision Intelligence rows, Career Agent memory rows, and
Career Agent tool records. It then marks the internal `users.status` as
`deactivated`.

External auth identity mappings are retained as scrubbed tombstones containing
the stable `provider + issuer + subject` boundary but not profile email or
email-verification metadata. Retaining that minimal mapping prevents a still
valid upstream Auth0 token from silently recreating a fresh internal account
after app-level deletion. Authentication resolution blocks deactivated users
before profile sync.

The internal user row remains as a minimal tombstone with `user_id`, status, and
timestamps so the app does not reuse the stable internal identifier and so
already-written internal references stay explainable. This tombstone is not
canonical market truth.

Auth0 provider account deletion is deferred. The current implementation does not call Auth0
Management API, delete Auth0 tenants/users, revoke provider sessions, or claim
provider-side erasure. Provider-side deletion must be implemented in a later
protected provider-integration slice with explicit Auth0 Management API
authorization and audit handling.

## Layer 39A Security And Privacy Addendum

Protected backend routes do not rely on frontend route protection. The backend
requires a verified bearer-token claims boundary for `/me`, Career Identity,
Career Decisions, Deep Decision Intelligence, Current Opportunities matches,
and admin routes. The local/test-only `X-Verified-OIDC-Claims` shortcut is
rejected outside local/test environments.

The app uses Auth0-managed bearer tokens and does not store local web sessions.
Logout is handled by the frontend Auth0 SDK/provider session. App-level account
deactivation prevents future use of the retained external identity mapping, but
does not revoke an Auth0 provider session.

Request abuse controls are in-process and endpoint-class based:

- anonymous and authenticated cheap reads use the configured read buckets
- mutation endpoints use the mutation bucket
- expensive exports, personalized recommendation/deep analysis, Career Agent,
  Current Opportunities match/diagnostic/refresh, billing mutation, and
  integration routes use the expensive bucket

Authenticated buckets key on stable issuer/subject where verified claims are
available. Anonymous buckets key on the socket client address and intentionally
do not trust forwarded headers. This is production-suitable for a single
process; horizontally scaled deployments need a shared limiter before relying
on strict global quotas.

Structured logging redacts sensitive keys and secret-shaped strings, including
authorization headers, cookies, bearer tokens, database URLs, Stripe-like
secrets, webhook secrets, API keys, credentials, and nested token/secret fields.
Request logs retain request id, method, path, status, duration, and safe error
type without dumping request bodies or auth headers.

## Public Exploration

All current market exploration endpoints remain unauthenticated:

- `GET /regions`
- `GET /regions/{region_id}`
- `GET /companies/{company_id}`
- `GET /companies/{company_id}/regions`
- `GET /companies/{company_id}/sources`
- `GET /companies/search`
- `GET /regions/{region_id}/sources`
- `GET /regions/search`
- `GET /compare`
- `POST /discover/personalized`

`POST /discover/personalized` remains request-scoped. It does not persist
preferences or personalized outputs. Batch C snapshot persistence is available
through the internal user personalization service only; no public market route
creates snapshots.

Batch D privacy controls are service-level only; public market exploration
endpoints remain unauthenticated and do not require app account state.

Layer 7.5 protected user endpoints are separate from public market exploration.
They cover current profile lookup, saved preferences, saved market artifacts,
recommendation snapshots, app-owned data export, and app-level account
deactivation. They remain scoped to the current internal `users.user_id` and do
not create, update, or delete canonical market records.

Layer 7.5 Batch C exposes those protected surfaces in the frontend account UI.
The UI labels saved preferences, saved artifacts, and recommendation snapshots
as user-owned overlays, and account deactivation is app-level only. Auth0
provider account deletion and Management API-driven session revocation remain
deferred; frontend sign-out uses the normal Auth0 SPA SDK logout path.
