# API Surfaces

> **Historical cumulative inventory.** This layer-oriented narrative is not the current route authority and predates the public guest policy. Use the FastAPI route modules, [guest route policy](../backend/public_guest/policy.py), and [Engineering Guide](ENGINEERING_GUIDE.md) for the current application.

This file documents the MVP API surface that is currently implemented. It is intentionally narrow: the local demo reads seeded backend data and exposes Auth0-backed frontend sign-in/account workflows for protected `/me` routes plus governed Layer 9 admin review, override, and repair APIs, but it does not expose scraping, broad admin mutation tooling, maps, or production deployment controls. Current status is an internal-production baseline for local/single-process operation, not external-production readiness.

## Layer 38A Current Opportunities

Layer 38A adds authenticated backend APIs for production-current opportunity
records. These APIs are backed by governed source acquisition, raw observation
storage, normalization, canonical identity resolution, freshness/provenance,
coverage contracts, and strategic matching.

User-facing routes:

- `GET /current-opportunities`
- `GET /current-opportunities/{opportunity_id}`
- `GET /current-opportunities/matches`
- `GET /current-opportunities/coverage`

Operator/data-review routes:

- `GET /current-opportunities/diagnostics`
- `GET /current-opportunities/refresh-runs`

List/detail responses include normalized company/title/role/location/work
arrangement/compensation/application fields, freshness, provenance summaries,
ranking eligibility, coverage status, and limitations. Strategic match
responses add score, relevance label, contributing factors, warnings, and
limitations based on existing Layer 35 Career Identity, Layer 36 decisions, and
Layer 37 strategic review records.

The API deliberately omits raw provider payloads, source credentials, internal
license text, and private operational internals. External application URLs are
validated as untrusted source data and only `http`/`https` routes with a host
are accepted.

No real external opportunity provider is configured by default in this batch.
The deterministic adapter is test/curated infrastructure only, so API coverage
must not be represented as exhaustive production market coverage unless
explicit source and coverage contracts are later configured.

Layer 38B frontend routes consuming this API family:

- `/markets/current-opportunities`
- `/markets/current-opportunities/{opportunity_id}`
- `/markets/current-opportunities/operations`

The operations route is a frontend surface for the existing diagnostics and
refresh-run endpoints; backend data-review authorization remains authoritative.

## Response Envelope

Most successful responses use:

```json
{
  "status": "success",
  "data": {},
  "metadata": {
    "state": "fresh",
    "freshness": {
      "last_updated_at": "ISO-8601 timestamp or null",
      "freshness_expires_at": "ISO-8601 timestamp or null",
      "is_stale": false,
      "freshness_status": "fresh | stale | unknown"
    },
    "source_versions": {},
    "warnings": []
  },
  "error": null
}
```

Lightweight endpoints may omit `freshness` and `source_versions` from `metadata`. When `freshness_expires_at` is `null`, `freshness_status` is `unknown`; do not interpret `is_stale: false` by itself as proof of tracked freshness.

Errors use:

```json
{
  "status": "error",
  "data": null,
  "metadata": {
    "state": "failed",
    "warnings": []
  },
  "error": {
    "code": "NOT_FOUND",
    "message": "Region not found."
  }
}
```

Warnings are structured objects when available:

```json
{
  "warning_code": "region_score_missing",
  "severity": "medium",
  "message": "no region_market_scores row for 'greater_boston'",
  "scope_type": "region",
  "scope_ref": "greater_boston"
}
```

## Auth And User Foundation

Layer 7 Batch A selects Auth0 as the managed auth provider and records the
internal identity boundary in `docs/AUTH_USER_FOUNDATION.md`. The app does not
hand-roll credential handling: login/signup, password reset, MFA, token
issuance, and token verification remain managed-provider responsibilities.

The backend has internal tables for protected user-owned and admin-foundation
workflows:

- `users`
- `external_auth_identities`
- `user_profiles`
- `user_preference_profiles`
- `saved_market_artifacts`
- `personalized_recommendation_snapshots`
- `alert_events`
- `user_alerts`
- `region_expansion_workflows`
- `admin_event_logs`
- `audit_finding_reviews`
- `admin_overrides`
- `admin_repair_actions`

Provider identity maps to internal user identity by `provider + issuer +
subject`; email/display/avatar claims are profile metadata only.

`users.admin_role` is nullable. When present, valid Layer 9A admin roles are
`admin`, `data_reviewer`, and `read_only_operator`. Backend dependencies, not
frontend checks, authorize admin surfaces.

Protected Layer 7.5 user routes use the existing already-verified OIDC claims
boundary. Production Auth0/JWKS middleware verifies Bearer JWT signature,
issuer, audience, expiration, and supported token/header shape before attaching
claims to `request.state.verified_oidc_claims`. The backend still does not
issue sessions, store passwords, or call Auth0 Management API. Local/test route
coverage may use `X-Verified-OIDC-Claims` with the same already-verified claim
mapping; this is a test/local boundary stub, not provider token validation, and
is rejected outside local/test.

Protected-route Auth0 settings:

- `AUTH0_ISSUER`
- `AUTH0_AUDIENCE`
- `AUTH0_JWKS_URL`, optional when issuer can derive
  `${AUTH0_ISSUER}.well-known/jwks.json`
- `AUTH0_JWKS_CACHE_SECONDS`, default `300`

Stripe billing adapter settings:

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_SUCCESS_URL`
- `STRIPE_CANCEL_URL`
- `STRIPE_BILLING_PORTAL_RETURN_URL`
- `STRIPE_PRICE_INDIVIDUAL_MONTHLY`
- `STRIPE_PRICE_INDIVIDUAL_ANNUAL`
- `STRIPE_PRICE_STUDENT_ANNUAL`
- optional institutional `STRIPE_PRICE_*` values, currently not used for
  self-serve checkout

Missing Stripe settings disable checkout and portal behavior without failing
app startup. These values are backend-only secrets/references and must not be
exposed to the frontend.

Frontend Auth0 SPA settings:

- `VITE_AUTH0_DOMAIN`
- `VITE_AUTH0_CLIENT_ID`
- `VITE_AUTH0_AUDIENCE`
- `VITE_AUTH0_REDIRECT_URI`, optional; defaults to `/markets` on the current
  browser origin

When frontend Auth0 settings are absent, the Vite app runs in local/demo mode:
public market exploration remains available and account controls are disabled.
The frontend attaches Bearer tokens only to protected `/me`, `/monetization`,
`/billing`, and future institutional account/workflow requests.

Public market exploration routes remain unauthenticated.

## Institutional Endpoints

Layer 16 adds institutional APIs under `/api/institutions`. These routes are
protected by the existing backend auth boundary and authorize against persisted
organization memberships. Frontend role state is not trusted for security
decisions.

Implemented routes:

- `GET /api/institutions/organizations/current`
- `GET /api/institutions/organizations/{organization_id}`
- `GET /api/institutions/organizations/{organization_id}/dashboard`
- `GET /api/institutions/organizations/{organization_id}/members`
- `POST /api/institutions/organizations/{organization_id}/members`
- `PATCH /api/institutions/organizations/{organization_id}/members/{membership_id}`
- `POST /api/institutions/organizations/{organization_id}/advisor/compare-regions`
- `POST /api/institutions/organizations/{organization_id}/advisor/compare-industries`
- `POST /api/institutions/organizations/{organization_id}/advisor/compare-companies`
- `POST /api/institutions/organizations/{organization_id}/advisor/compare-career-stages`
- `POST /api/institutions/organizations/{organization_id}/advisor/application-timing`
- `POST /api/institutions/organizations/{organization_id}/reports`
- `GET /api/institutions/organizations/{organization_id}/reports`
- `GET /api/institutions/organizations/{organization_id}/reports/{report_id}`
- `POST /api/institutions/organizations/{organization_id}/data-requests`
- `GET /api/institutions/organizations/{organization_id}/data-requests`

`/organizations/current` returns the caller's own active organization
memberships. Organization detail requires an active `ORG_ADMIN`, `ADVISOR`, or
`REPORT_VIEWER` membership. The dashboard route requires an active `ORG_ADMIN`,
`ADVISOR`, or `REPORT_VIEWER` membership in the requested organization. Member
list and member mutation routes require an active `ORG_ADMIN` membership in the
requested organization.

Advisor comparison routes require an active `ORG_ADMIN` or `ADVISOR`
membership in the requested organization. `REPORT_VIEWER` can view aggregate
dashboard/report-oriented surfaces but cannot use advisor tools in this batch.
`STUDENT` and inactive memberships are denied. Cross-organization requests are
denied by persisted backend membership checks.

Institutional report routes require an active `ORG_ADMIN`, `ADVISOR`, or
`REPORT_VIEWER` membership in the requested organization. `STUDENT` members do
not access institutional reports by default. Reports are persisted
aggregate-first payloads with low-sample suppression, coverage warnings,
limitations, recommended actions, privacy notes, data freshness, and deferred
export options.

Data request routes create/list auditable request records only. `ORG_ADMIN`
can create/list organization-level export/deletion request records for its own
organization. `STUDENT` can create/list their own student export/deletion
request records. `ADVISOR` and `REPORT_VIEWER` cannot create student
export/deletion requests by default. Cross-organization requests are denied.
The API does not execute destructive deletion or generate full export packages
in this batch.

The dashboard response is aggregate-first:

- `organization_id`, `organization_name`, `generated_at`
- `minimum_group_size`, default `5`, with request overrides bounded to `5` through `50`
- `cohort_size` and safe visible cohort summary counts
- `popular_target_markets`
- `role_interest_summary`
- `saved_company_summary`
- `market_demand_trends`
- `coverage_gaps`
- `suppressed_categories`
- `privacy_notes`, `coverage_warnings`, and `data_freshness`

Low-sample aggregate categories are suppressed before response serialization.
Suppressed labels and exact hidden low-sample counts are not returned. Market
demand and coverage-gap sections are derived only from target-market categories
that already met the configured minimum group threshold. The dashboard payload
does not include student ids, raw saved-market rows, search rows, recommendation
snapshots, or student-level activity.

Membership responses contain organization/member ids, user ids, roles, statuses,
and timestamps only. They do not expose profile email, saved companies,
recommendation snapshots, searches, alerts, personal activity, or student-level
private data.

Institutional audit rows are recorded for organization detail access,
dashboard access, member list access, member additions, and member updates.
Advisor tool usage records action names for region, industry, company,
career-stage, and application-timing comparisons. Audit metadata stores
organization scope, actor, actor role, comparison type, report/request type,
and non-sensitive request summaries only. There is no audit dashboard, PDF/CSV
export execution, destructive deletion execution, SSO, invite flow, or
student-specific advising endpoint in this batch.

Advisor tool responses are guidance-oriented:

- `organization_id`, `generated_at`, and `comparison_type`
- `compared_items` with market demand signals, explanation summaries, coverage
  metadata, item warnings, and non-sensitive metadata
- `guidance`
- `tradeoffs`
- `coverage_warnings`
- `data_freshness`
- `limitations`
- `privacy_notes`

Advisor routes reuse existing market/search/coverage systems and do not create
a separate recommendation engine. They do not include student ids, raw
per-student saved/search rows, recommendation snapshots, personal activity, or
individual student histories.

Report generation responses use:

- `report.report_id`, `organization_id`, `report_type`, `title`, `generated_at`
- `generated_by_user_id`
- `minimum_group_size` and `cohort_size`
- structured `sections`
- `privacy_suppressions`
- `coverage_warnings`
- `data_freshness`
- `limitations`
- `recommended_actions`
- `export_status` and deferred `export_options`

Report payloads do not include student ids, raw per-student saved/search rows,
recommendation snapshots, personal activity, or individual student histories.
PDF, CSV, PowerPoint, email delivery, and scheduled reports are not
implemented.

Report generation rejects `minimum_group_size` values below `5`; report
payloads are assembled only after the privacy-aware dashboard aggregation has
already applied suppression.

Data request create responses use:

- `data_request_id`
- `organization_id`
- `requester_user_id`
- `request_type`
- `subject_type`
- `subject_user_id`, only for the requester-owned student request case
- `status`
- `reason`
- timestamps and an execution note

Data request records are auditable workflow records only. They do not imply
approval, completion, deletion execution, or export package creation.

The Layer 16 foundation is education-privacy-aware and FERPA-conscious in
design, but this implementation does not claim legal FERPA compliance. It
minimizes unnecessary student-level exposure through role checks, organization
scoping, and aggregate-only dashboard design.

## Monetization Endpoints

Layer 15 exposes the internal monetization model and a narrow billing adapter.
Public catalog endpoints are read-only:

- `GET /monetization/plans`
- `GET /monetization/features`
- `GET /monetization/reports`
- `GET /monetization/access-preview`

`/monetization/access-preview` accepts a `feature_key`, optional explicit
`plan_key`, and optional `used` count for static plan previews. If no
`plan_key` is supplied and a current user can be resolved, it uses the
account-aware entitlement resolver. The endpoint does not create checkout
sessions or mutate recommendation ranking.

Protected account entitlement endpoints:

- `GET /monetization/me`
- `GET /monetization/entitlements`
- `GET /monetization/usage`
- `POST /monetization/reports/{report_key}/generate`
- `POST /monetization/reports/{report_key}/export`

These routes return internal account type, effective plan key, account status,
included feature keys, usage limits, safe license context, and usage counters.
They do not expose payment-provider identifiers, billing-provider state,
private recommendation inputs, or recommendation internals.

Report generate/export routes return structured JSON placeholders only. They
do not generate PDFs, start downloads, create checkout sessions, or call a
billing provider. Blocked monetization responses use HTTP 403 and include
`data.decision` with `allowed`, `feature_key`, `plan_key`, `reason`,
`upgrade_plan_keys`, and usage fields when relevant.

Batch 4 workflow enforcement points:

- `POST /me/saved-market-artifacts` requires `saved_watchlists`
- `GET /me/alerts` and alert read/dismiss routes require `alerts`
- authenticated `GET /compare` increments `limited_comparisons` only after a
  successful comparison response
- authenticated `POST /discover/personalized` increments
  `limited_personalized_discovery` only after a successful discovery response
- report generation increments `full_report_generation` only after a
  successful JSON report-stub response
- report export increments `exportable_strategy_plans` only after a successful
  JSON export-stub response

Billing adapter endpoints:

- `GET /billing/status`
- `POST /billing/checkout-session`
- `POST /billing/portal-session`
- `POST /billing/stripe/webhook`

`GET /billing/status` is public and exposes only availability plus
checkout-eligible internal plan keys. It never returns Stripe secrets or price
IDs. Checkout and portal routes require the current-user auth dependency.
Checkout validates the internal `plan_key`, rejects `free`, rejects unknown or
unmapped plans, and returns a backend-created provider URL. It does not update
entitlements. The Stripe webhook verifies the raw request body and
`Stripe-Signature` header before mapping provider lifecycle events into
internal monetization plan assignments.

## Public Demo Runtime Posture

`APP_ENV=public_demo` is an externally viewable, read-only demo posture. It is
not production. In public demo mode, the backend fails closed to an explicit
allowlist of public read/search/source endpoints plus the non-persistent
`POST /discover/personalized` and `POST /recommendations/strategy`
request-scoped calculations. Protected `/me` and
`/admin` routes, canonical write-shaped requests, override/repair/audit
mutations, and future unknown routes are denied before route handlers can
mutate durable state.

See `docs/PUBLIC_DEMO_ENVIRONMENT.md` for the mutation-surface inventory and
the exact public demo allowlist.

## Protected User Endpoints

All endpoints in this section require the current-user auth dependency. They
operate only on Layer 7 user-owned data for the resolved internal `users.user_id`.
They do not mutate canonical market truth, source freshness/provenance rows,
raw ingestion records, objective scores, output metadata, company canonical
state, or region canonical state.

### `GET /me`

Returns the current app user and provider-sourced profile metadata.

### `GET /me/preferences`

Returns the current user's saved preference profile. If no profile exists,
`persisted` is `false` and preference arrays are empty.

### `PUT /me/preferences`

Creates or updates the current user's saved preference profile.
Batch 11A adds `scoring_weights` for user-owned overlay controls covering
entry-level access, hiring density, prestige, industry fit, and role fit. These
weights are not canonical scoring rules and do not update objective scores.

### `DELETE /me/preferences`

Deletes only the current user's saved preference profile. Existing historical
recommendation snapshots are retained with their nullable preference link
cleared.

### `POST /me/scoring-preview`

Returns a non-persistent personalized scoring preview for requested regions
using saved preferences unless preview-only overrides are supplied in the
request. The response labels `canonical_default_scores` separately from
`personalized_overlay_score`, includes component weights/evidence, and surfaces
missing structured inputs as warnings. It does not create output metadata,
recommendation snapshots, canonical scores, source records, or ingestion rows.
Layer 12 Run 2 includes heuristic region `coverage` on each preview region so
personalized scoring previews do not hide watchlist or placeholder markets.

### `POST /me/saved-market-artifacts`

Creates a saved market artifact for the current user. Valid `artifact_type`
values are `region`, `company`, `role_family`, `comparison`, and
`discovery_result`. Batch 11A uses this table as the watchlist store; watchlist
rows reference canonical ids through `artifact_ref` and must not copy canonical
facts into user-owned storage.

Server-side validation rejects `snapshot` fields outside narrow reference and
configuration metadata. Unsafe snapshot fields such as copied scores, freshness,
provenance/source summaries, evidence, company/region detail payloads, hiring
facts, entry-level signals, or assembled market outputs are rejected with a
validation response rather than persisted.

### `GET /me/saved-market-artifacts`

Lists the current user's saved market artifacts. An optional `artifact_type`
query parameter narrows the list.

### `GET /me/saved-market-artifacts/{saved_artifact_id}`

Returns one saved artifact owned by the current user. Artifacts owned by other
users are not returned.

### `DELETE /me/saved-market-artifacts/{saved_artifact_id}`

Deletes one saved artifact owned by the current user.

### `GET /me/alerts`

Returns the current user's in-app alert feed. Alerts are generated from
structured change events and materialized for the user based on saved
watchlists or saved preference relevance. The response includes the
system-level event type, canonical entity references, safe previous/new change
metadata, freshness labels, source/change-basis refs, and the user-specific
relevance reason.

Alert records do not store full company, region, source/provenance, score, or
assembled market-output payloads.

Optional query parameters:

- `include_dismissed`: default `false`
- `limit`: default `100`, maximum `500`

### `POST /me/alerts/{user_alert_id}/read`

Marks one current-user alert as read. It does not mutate the system-level alert
event or any canonical market record.

### `POST /me/alerts/{user_alert_id}/dismiss`

Dismisses one current-user alert and marks it read. Dismissed alerts are hidden
from `GET /me/alerts` unless `include_dismissed=true`.

### `POST /me/explanations/region`

Renders deterministic structured guidance for a region evidence packet. The
endpoint is protected because it may include user-specific overlay context, but
it is read-only and does not persist explanation text. The request must include
`evidence.entity_type = "region"` and may include canonical/default score
fields, personalized overlay fields, scoring factors, freshness labels, safe
source refs, missing-data flags, unsupported-data flags, and seeded/demo
status.

The response labels its provider mode as
`deterministic_structured_guidance`. It is an explanation of supplied structured
evidence only, not source data or canonical market truth.

### `POST /me/explanations/company`

Renders deterministic structured guidance for a company evidence packet. The
endpoint expects `evidence.entity_type = "company"` and does not infer
unobserved region presence, hiring, prestige, or market claims.

### `POST /me/explanations/comparison`

Renders deterministic structured guidance for a comparison evidence packet.
The endpoint expects `evidence.entity_type = "comparison"` and summarizes only
returned comparison score fields, freshness/source labels, and missing-data
flags. It does not create a new comparison formula.

### `POST /me/explanations/alert`

Renders deterministic structured guidance for an in-app alert evidence packet.
The endpoint expects `evidence.entity_type = "alert"` and summarizes alert
event type, bounded changed fields, freshness labels, relevance context, and
source/change-basis refs. It does not generate additional alert events.

### `POST /me/recommendation-snapshots`

Persists a user-owned personalized recommendation snapshot supplied by the
caller. This route does not generate recommendations or recompute market data.

### `GET /me/recommendation-snapshots`

Lists the current user's personalized recommendation snapshots.

### `GET /me/recommendation-snapshots/{recommendation_snapshot_id}`

Returns one recommendation snapshot owned by the current user. Snapshots owned
by other users are not returned.

### `GET /me/export`

Exports app-owned user data for the current user: user/profile metadata,
external auth identity mappings, saved preferences, saved market artifacts,
personalized recommendation snapshots, user alerts, Career Identity facts/import
metadata, Career Decisions, application/outcome records, decision journals, and
Deep Decision Intelligence outputs. It also exports sanitized Career Agent
memory permissions/entries and Career Agent tool previews/audit summaries. It
does not export secrets, bearer tokens, password hashes, provider access tokens,
API key raw values, internal audit row ids, raw secret-shaped values, or other
users' data.

### `DELETE /me`

Deactivates the current app-level user account. This deletes the current user's
profile, preferences, saved artifacts, recommendation snapshots, user alerts,
Career Identity, Career Decisions, Deep Decision Intelligence, Career Agent
memory, and Career Agent tool records, then leaves the internal `users` row as a
`deactivated` tombstone. External auth identity mappings are retained as
scrubbed provider/issuer/subject tombstones so a still-valid upstream token
cannot recreate the app user. Auth0 provider-side account deletion and session
revocation are not implemented.

## Protected Admin Foundation Endpoints

Layer 9 admin routes require the same current-user auth boundary as `/me` plus
an internal admin role. They do not expose raw database mutation endpoints or
direct edits to production market/source records.

Role capabilities:

- `admin`: can access admin review workflows and perform future controlled
  admin mutations, including override activation/revocation and repair
  execution.
- `data_reviewer`: can access review workflows and perform future limited
  controlled review actions, including override proposals and review-request
  repair records.
- `read_only_operator`: can inspect admin/review data but cannot mutate it.

### `GET /admin/me`

Returns the current admin role and computed capabilities. Any valid admin role
can call this endpoint.

### `GET /admin/event-log`

Lists append-only admin event log records for inspection. Any valid admin role
can read the log. Layer 9 does not expose a public endpoint to create arbitrary
admin event records; controlled workflows append records through the admin event
log service.

## Protected Admin Review Endpoints

Layer 9B adds read-only review surfaces for canonical market/source rows and a
controlled audit-finding lifecycle. Review endpoints use the standard
lightweight response envelope.

Any valid admin role (`admin`, `data_reviewer`, `read_only_operator`) may view:

- `GET /admin/review/companies`
- `GET /admin/review/companies/{company_id}`
- `GET /admin/review/presence`
- `GET /admin/review/presence/{presence_id}`
- `GET /admin/review/hiring`
- `GET /admin/review/hiring/{hiring_id}`
- `GET /admin/review/entry-level`
- `GET /admin/review/entry-level/{entry_level_id}`
- `GET /admin/review/source-refs`
- `GET /admin/review/source-refs/{source_id}`
- `GET /admin/review/audit-findings`
- `GET /admin/review/audit-findings/{finding_id}`

These endpoints inspect rows only. They do not update companies, presence,
hiring, entry-level, source refs, scores, outputs, cache records, or provenance
records.

Audit finding lifecycle states:

- `open`
- `acknowledged`
- `resolved`
- `dismissed`
- `escalated`

Controlled lifecycle endpoint:

- `POST /admin/review/audit-finding-transitions`

Request:

```json
{
  "finding_id": "override_balance::comp_a::missing_reason",
  "target_state": "acknowledged",
  "reason": "Reviewed by data quality team."
}
```

Only `admin` and `data_reviewer` may transition audit findings.
`read_only_operator` may inspect findings but receives `403` on lifecycle
mutation attempts. Every transition requires a non-empty reason and writes an
append-only `admin_event_logs` record with actor, role, action, object,
before/after state, reason, timestamp, and request id when available.

Transition map:

- `open` -> `acknowledged`, `escalated`, `dismissed`
- `acknowledged` -> `resolved`, `escalated`, `dismissed`
- `escalated` -> `acknowledged`, `resolved`, `dismissed`
- `resolved` -> `open`
- `dismissed` -> `open`

## Protected Admin Override And Repair Endpoints

Layer 9C adds controlled workflow endpoints for governed overrides and safe
repair actions. These routes use the standard lightweight response envelope and
do not expose raw SQL or direct arbitrary table updates.

Override records are first-class overlays. Creating or activating an override
does not overwrite the canonical company, presence, or source row. Active
overrides are included as `active_overrides` on relevant admin review detail
and list responses for companies, presence facts, and source refs.
Expired, revoked, and superseded overrides are not reported as active overlays.

Any valid admin role may inspect override and repair workflow records:

- `GET /admin/overrides`
- `GET /admin/overrides/{override_id}`
- `GET /admin/repair-actions`
- `GET /admin/repair-actions/{repair_action_id}`

Only `admin` and `data_reviewer` may propose overrides:

- `POST /admin/overrides`

Request:

```json
{
  "target_type": "company",
  "target_id": "comp_a",
  "override_type": "company_eligibility",
  "override_value": {"eligibility_status": "eligible"},
  "reason": "Official source confirms in-scope technology business.",
  "source_evidence": {"source_ids": ["source_123"]},
  "review_at": "2026-06-25T16:00:00+00:00"
}
```

Supported override types are:

- `company_eligibility` on `company`
- `company_classification` on `company`
- `presence_status` on `presence_fact`
- `source_confidence` on `source_ref`

Only `admin` may activate or revoke overrides:

- `POST /admin/overrides/{override_id}/activate`
- `POST /admin/overrides/{override_id}/revoke`

Only `admin` may execute repair actions. `data_reviewer` may create
`request_review` repair records; other repair requests and all execution are
admin-only. `read_only_operator` can inspect but receives `403` for mutation
attempts.

- `POST /admin/repair-actions`
- `POST /admin/repair-actions/{repair_action_id}/execute`

Supported repair actions:

- `recompute_score`: recomputes a region score through `RegionScoringService`
- `rebuild_output`: rebuilds an existing output through `OutputAssemblyService`
- `mark_source_stale`: moves a source ref through the existing object state
  model without deleting observations or fact links
- `request_review`: creates visible workflow state without canonical mutation
- `deactivate_bad_fact`: moves a fact row to `blocked` through the existing
  state model while preserving source/provenance history

Every override and repair mutation requires a non-empty reason and appends an
`admin_event_logs` record with actor, role, action, object, before/after state,
reason, timestamp, and request id when available. Audit findings may be linked
to repair records, but audit finding lifecycle transitions do not auto-repair
production data.

Frontend admin UI remains deferred. The current frontend has no admin
navigation or role-aware admin shell; adding one cleanly belongs with a later
UI batch rather than broadening this API-focused review foundation.

## Region Expansion Workflow Contract

Layer 11B adds backend workflow metadata for planned region expansion. Layer 12
derives the target candidate plan from the canonical priority market registry in
`backend/geography/market_coverage.py`: NYC, Seattle, Austin, DC / NoVA,
Atlanta, Chicago, Los Angeles, Raleigh-Durham, Denver / Boulder, Boston, SF Bay
Area, Dallas, Miami, Pittsburgh, and Minneapolis.

The workflow states are `candidate`, `intake_started`, `normalized`,
`provenance_attached`, `review_ready`, `approved`, `published`, and
`refresh_enabled`.

The workflow checklist tracks region identity, source coverage,
company-region presence, hiring-signal support, entry-level-signal support,
scoring readiness, freshness readiness, provenance attachment, admin approval,
and output-refresh readiness. Workflow rows reference existing ingestion,
provenance, admin review, and refresh/output contracts; they do not create
canonical regions, run ingestion, scrape sources, publish outputs, or bypass
admin/provenance/freshness controls.

Layer 12 also defines backend-only coverage tier, sector coverage, and
heuristic coverage-quality metadata. These structures do not expose a broad API
surface in Run 1 and must not be interpreted as a claim that every priority
market is fully covered.

No public or frontend route is exposed for this workflow in Batch 11B or Layer
12 Run 1.

Layer 12 Run 2 exposes coverage metadata additively on backend read models where
region intelligence appears. The object shape is:

```json
{
  "coverage": {
    "tier": "tier_2",
    "label": "Tier 2 - partial but useful market",
    "quality_score": 58.0,
    "components": {
      "company_coverage": 72.0,
      "hiring_coverage": 58.0,
      "entry_level_coverage": 58.0,
      "freshness": 80.0,
      "source_diversity": 35.0,
      "confidence": 58.0
    },
    "coverage_tier": "tier_2",
    "coverage_label": "Tier 2 - partial but useful market",
    "coverage_description": "This market is directionally useful, but one or more coverage signals are incomplete and must be treated as partial.",
    "coverage_quality_score": {
      "overall_score": 58.0,
      "components": {
        "company_coverage": 72.0,
        "hiring_coverage": 58.0,
        "entry_level_coverage": 58.0,
        "freshness": 80.0,
        "source_diversity": 35.0,
        "confidence": 58.0
      }
    },
    "coverage_limitations": [
      "Coverage scoring is heuristic and should be read together with freshness and source metadata.",
      "Coverage is partial; at least one signal class is incomplete."
    ],
    "notes": ["Coverage is heuristic and source evidence may be incomplete."],
    "heuristic": true,
    "safe_for_confident_market_comparison": false,
    "should_rank_as_confident_recommendation": false
  },
  "sector_coverage": {}
}
```

Coverage scores are bounded heuristic completeness indicators in `[0, 100]`.
They do not replace source/provenance/freshness metadata and must not be read as
objective opportunity scores. Tier 3 and Tier 4 markets are not confident
recommendation markets. `sector_coverage` is separate from overall region
coverage. Lightweight list/search surfaces may keep `sector_coverage` empty to
avoid payload bloat; detail/output surfaces expose unknown sector coverage
defaults when sector-specific validation is not available.

`GET /metadata/coverage` returns the canonical coverage vocabulary: coverage
tiers and semantics, sector coverage categories and levels, priority markets,
component names, and quality score bounds.

## Layer 11C Product Surface And Explanation

Layer 11C adds read-only product-surface visualizations and deterministic
structured guidance. The frontend renders score breakdown bars, comparison
score bars, and alert summary bars from existing API responses. Trend views,
maps, heatmaps, and network graphs are disabled or labelled unsupported unless
historical snapshots, geographic precision, heatmap cells, or graph-layout
data are explicitly present.

The explanation endpoints under `/me/explanations/*` accept structured
evidence packets only. They do not call an external AI provider, browse, scrape,
persist explanation output, mutate canonical scores, or update source,
provenance, alert, output, admin, or region-expansion records. External AI
provider integration remains deferred until a safe provider abstraction exists.

## Public Demo Monitoring Posture

Public-demo monitoring targets and provider-neutral frontend/backend error
posture are documented in `docs/PUBLIC_DEMO_MONITORING.md`. The monitoring
surface is intentionally read-only and compatible with the `public_demo`
allowlist documented in `docs/PUBLIC_DEMO_ENVIRONMENT.md`.

## Public Demo Abuse Protection Posture

Public-demo rate limiting, request-size limits, exact-origin CORS requirements,
and bot-protection deployment posture are documented in
`docs/PUBLIC_DEMO_ABUSE_PROTECTION.md`. These controls are layered on top of the
read-only public demo allowlist and do not expose mutation routes.

## Implemented Public Endpoints

For the local MVP, full output endpoints assemble response payloads on read through the output assembly service without creating or updating `OutputMetadata` cache metadata. They do not run foundational ingestion, external refreshes, scraping, or scoring recomputation during request handling.

### `GET /health`

Basic health check. It does not touch the database.

Response `data`:

```json
{
  "service": "ok"
}
```

### `GET /regions`

Lightweight region list. This reads region identity rows only and does not return full region output sections.

Response `data`:

```json
{
  "regions": [
    {
      "region_id": "greater_boston",
      "display_name": "Greater Boston",
      "region_type": "greater_region",
      "parent_region_id": null,
      "labor_market_group": "boston_labor_market",
      "priority_market": null,
      "state": "fresh",
      "version": 1,
      "coverage": {
        "tier": "tier_4",
        "label": "Tier 4 - placeholder only",
        "quality_score": 0.0,
        "components": {
          "company_coverage": 0.0,
          "hiring_coverage": 0.0,
          "entry_level_coverage": 0.0,
          "freshness": 0.0,
          "source_diversity": 0.0,
          "confidence": 0.0
        },
        "coverage_tier": "tier_4",
        "coverage_label": "Tier 4 - placeholder only",
        "coverage_description": "This market is placeholder only and should not be treated as analyzed market intelligence.",
        "coverage_quality_score": {
          "overall_score": 0.0,
          "components": {
            "company_coverage": 0.0,
            "hiring_coverage": 0.0,
            "entry_level_coverage": 0.0,
            "freshness": 0.0,
            "source_diversity": 0.0,
            "confidence": 0.0
          }
        },
        "coverage_limitations": [
          "Coverage scoring is heuristic and should be read together with freshness and source metadata.",
          "Coverage is placeholder-only and must not be presented as analyzed.",
          "No coverage evidence is available on this surface."
        ],
        "notes": ["No coverage evidence is available on this surface."],
        "heuristic": true,
        "safe_for_confident_market_comparison": false,
        "should_rank_as_confident_recommendation": false
      },
      "sector_coverage": {}
    }
  ]
}
```

`coverage` and `sector_coverage` are included per region. Lightweight list
coverage is computed from already-loaded backend rows and remains heuristic; it
does not promote identity-only regions into analyzed markets. `priority_market`
is populated only when the region id exactly matches a canonical priority
market id.

### `GET /regions/{region_id}`

Returns the assembled region output in a flattened `data` body. The response does not wrap the body in a `region` key.

Response `data`:

```json
{
  "region_id": "greater_boston",
  "display_name": "Greater Boston",
  "region_type": "greater_region",
  "parent_region_id": null,
  "labor_market_group": "boston_labor_market",
  "priority_market": null,
  "coverage": {
    "tier": "tier_2",
    "label": "Tier 2 - partial but useful market",
    "quality_score": 58.0,
    "components": {
      "company_coverage": 72.0,
      "hiring_coverage": 58.0,
      "entry_level_coverage": 58.0,
      "freshness": 80.0,
      "source_diversity": 35.0,
      "confidence": 58.0
    },
    "coverage_tier": "tier_2",
    "coverage_label": "Tier 2 - partial but useful market",
    "coverage_description": "This market is directionally useful, but one or more coverage signals are incomplete and must be treated as partial.",
    "coverage_quality_score": {
      "overall_score": 58.0,
      "components": {
        "company_coverage": 72.0,
        "hiring_coverage": 58.0,
        "entry_level_coverage": 58.0,
        "freshness": 80.0,
        "source_diversity": 35.0,
        "confidence": 58.0
      }
    },
    "coverage_limitations": [
      "Coverage scoring is heuristic and should be read together with freshness and source metadata.",
      "Coverage is partial; at least one signal class is incomplete."
    ],
    "notes": ["Coverage is heuristic and source evidence may be incomplete."],
    "heuristic": true,
    "safe_for_confident_market_comparison": false,
    "should_rank_as_confident_recommendation": false
  },
  "sector_coverage": {
    "ai": {
      "sector": "ai",
      "label": "AI",
      "coverage_level": "unknown",
      "coverage": {
        "tier": "tier_4",
        "label": "Tier 4 - placeholder only",
        "quality_score": 0.0,
        "components": {
          "company_coverage": 0.0,
          "hiring_coverage": 0.0,
          "entry_level_coverage": 0.0,
          "freshness": 0.0,
          "source_diversity": 0.0,
          "confidence": 0.0
        },
        "coverage_tier": "tier_4",
        "coverage_label": "Tier 4 - placeholder only",
        "coverage_description": "This market is placeholder only and should not be treated as analyzed market intelligence.",
        "coverage_quality_score": {
          "overall_score": 0.0,
          "components": {
            "company_coverage": 0.0,
            "hiring_coverage": 0.0,
            "entry_level_coverage": 0.0,
            "freshness": 0.0,
            "source_diversity": 0.0,
            "confidence": 0.0
          }
        },
        "coverage_limitations": [
          "Coverage scoring is heuristic and should be read together with freshness and source metadata.",
          "Coverage is placeholder-only and must not be presented as analyzed."
        ],
        "notes": [],
        "heuristic": true,
        "safe_for_confident_market_comparison": false,
        "should_rank_as_confident_recommendation": false
      }
    }
  },
  "summary": {
    "eligible_company_count": 6,
    "major_tech_count": 2,
    "mag7_count": 2,
    "present_company_count": 5,
    "currently_hiring_company_count": 4
  },
  "scores": {
    "structural_ecosystem_score": 0.72,
    "live_market_score": 0.68,
    "objective_opportunity_score": 0.74,
    "raw_total_score": 0.71,
    "general_density_score": 0.76,
    "tech_market_density_score": 0.73,
    "early_career_accessibility_score": 0.79,
    "score_ruleset_version": "marketscore_v1"
  },
  "top_companies_present": [],
  "top_companies_hiring": [],
  "entry_level_summary": {
    "internship_count_total": 25,
    "coop_count_total": 15,
    "entry_level_full_time_count_total": 28,
    "formal_early_career_program_count": 2,
    "average_entry_level_access_score": 0.71,
    "pairs_with_entry_level_access": 5
  },
  "major_tech_summary": {
    "count": 2,
    "company_ids": ["comp_alphabet", "comp_microsoft"]
  },
  "mag7_summary": {
    "count": 2,
    "company_ids": ["comp_alphabet", "comp_microsoft"]
  }
}
```

Full region output carries coverage metadata beside the region identity and
keeps `sector_coverage` separate from the overall region tier. When no
sector-specific validation exists, sector entries are explicitly `unknown` and
must not be treated as strong sector coverage.

### `GET /companies/{company_id}`

Returns the assembled company output in a flattened `data` body. The response does not wrap the body in a `company` key.

Response `data`:

```json
{
  "company_id": "comp_alphabet",
  "company_name": "Alphabet",
  "normalized_company_name": "alphabet",
  "sector_primary": "ai",
  "sector_secondary": "cloud",
  "eligibility_status": "eligible",
  "eligibility_override_flag": false,
  "classification_confidence": "high_confidence",
  "is_major_tech": true,
  "is_mag7": true,
  "prestige_score": 0.95,
  "regions_present": [],
  "regions_hiring": [],
  "entry_level_regions": []
}
```

### Layer 5 search, geography, and source explanation endpoints

These read-only endpoints expose canonical/demo/imported rows through stable API
contracts. They do not scrape, ingest, recompute scores, update output cache
metadata, or infer source truth from output payload prose.

`GET /regions/search` supports optional `query`, `region_type`,
`has_real_data`, `freshness_status`, and `min_opportunity_score` filters.
Results are ordered deterministically and include `freshness` metadata:

```json
{
  "regions": [
    {
      "region_id": "greater_boston",
      "name": "Greater Boston",
      "region_name": "greater_boston",
      "region_type": "greater_region",
      "parent_region_id": null,
      "labor_market_group": "boston_labor_market",
      "priority_market": null,
      "opportunity_score": 0.74,
      "freshness": {
        "freshness_status": "fresh | stale | partial | unknown | seeded_demo",
        "data_basis": "seeded_demo | real_imported | mixed | unknown",
        "last_collected_at": "ISO-8601 timestamp or null",
        "source_count": 1,
        "low_confidence_warning": null
      },
      "coverage": {
        "tier": "tier_2",
        "label": "Tier 2 - partial but useful market",
        "quality_score": 58.0,
        "components": {
          "company_coverage": 72.0,
          "hiring_coverage": 58.0,
          "entry_level_coverage": 58.0,
          "freshness": 80.0,
          "source_diversity": 35.0,
          "confidence": 58.0
        },
        "coverage_tier": "tier_2",
        "coverage_label": "Tier 2 - partial but useful market",
        "coverage_description": "This market is directionally useful, but one or more coverage signals are incomplete and must be treated as partial.",
        "coverage_quality_score": {
          "overall_score": 58.0,
          "components": {
            "company_coverage": 72.0,
            "hiring_coverage": 58.0,
            "entry_level_coverage": 58.0,
            "freshness": 80.0,
            "source_diversity": 35.0,
            "confidence": 58.0
          }
        },
        "coverage_limitations": [
          "Coverage scoring is heuristic and should be read together with freshness and source metadata.",
          "Coverage is partial; at least one signal class is incomplete."
        ],
        "notes": [],
        "heuristic": true,
        "safe_for_confident_market_comparison": false,
        "should_rank_as_confident_recommendation": false
      },
      "sector_coverage": {},
      "has_real_data": true
    }
  ],
  "count": 1
}
```

`GET /companies/search` supports optional `query`, `sector`, `industry`,
`role_family`, `region_id`, `current_hiring`, `has_entry_level_access`, and
`presence_status` filters. Company matches come from canonical company,
presence, hiring, and entry-level rows, not region-output payload text. When a
company result includes matched regions, `matched_region_coverage` maps each
matched region id to that region's coverage metadata. Search results include
the compact coverage object and may leave `sector_coverage` empty to avoid
expanding every canonical sector on lightweight cards.

`GET /companies/{company_id}/regions` returns canonical region links for a
company, including `presence_status`, `current_hiring`,
`has_entry_level_access`, per-row freshness/source metadata, overall region
`coverage`, `priority_market`, distinct `sector_coverage`, and `count`.

`GET /regions/{region_id}/sources` and `GET /companies/{company_id}/sources`
return source explanations for the subject. Source details are built from
explicit `FactSourceLink` evidence when present. Missing source evidence is
represented honestly as an empty `sources` list with `source_count: 0` and
unknown freshness/source basis.

Source explanation endpoints are not coverage-bearing. They expose provenance
and freshness evidence only; coverage metadata appears on region/search/output
read models and must not replace these source summaries.

### `GET /compare`

Query parameters:

- `region_a`: required region id
- `region_b`: required region id

Returns the comparison output in a flattened `data` body. The backend canonicalizes comparison ordering by region id, so `region_a` and `region_b` in the response may be sorted rather than matching request order.

Response `data`:

```json
{
  "comparison_id": "greater_boston__greater_sf",
  "region_a": {
    "region_id": "greater_boston",
    "display_name": "Greater Boston",
    "priority_market": null,
    "scores": {},
    "coverage": {
      "tier": "tier_2",
      "label": "Tier 2 - partial but useful market",
      "quality_score": 58.0,
      "components": {
        "company_coverage": 72.0,
        "hiring_coverage": 58.0,
        "entry_level_coverage": 58.0,
        "freshness": 80.0,
        "source_diversity": 0.0,
        "confidence": 58.0
      },
      "coverage_tier": "tier_2",
      "coverage_label": "Tier 2 - partial but useful market",
      "coverage_description": "This market is directionally useful, but one or more coverage signals are incomplete and must be treated as partial.",
      "coverage_quality_score": {
        "overall_score": 58.0,
        "components": {
          "company_coverage": 72.0,
          "hiring_coverage": 58.0,
          "entry_level_coverage": 58.0,
          "freshness": 80.0,
          "source_diversity": 0.0,
          "confidence": 58.0
        }
      },
      "coverage_limitations": [
        "Coverage scoring is heuristic and should be read together with freshness and source metadata.",
        "Coverage is partial; at least one signal class is incomplete."
      ],
      "notes": [],
      "heuristic": true,
      "safe_for_confident_market_comparison": false,
      "should_rank_as_confident_recommendation": false
    },
    "sector_coverage": {}
  },
  "region_b": {
    "region_id": "greater_sf",
    "display_name": "Greater San Francisco / Silicon Valley",
    "priority_market": null,
    "scores": {},
    "coverage": {
      "tier": "tier_4",
      "label": "Tier 4 - placeholder only",
      "quality_score": 0.0,
      "components": {
        "company_coverage": 0.0,
        "hiring_coverage": 0.0,
        "entry_level_coverage": 0.0,
        "freshness": 0.0,
        "source_diversity": 0.0,
        "confidence": 0.0
      },
      "coverage_tier": "tier_4",
      "coverage_label": "Tier 4 - placeholder only",
      "coverage_description": "This market is placeholder only and should not be treated as analyzed market intelligence.",
      "coverage_quality_score": {
        "overall_score": 0.0,
        "components": {
          "company_coverage": 0.0,
          "hiring_coverage": 0.0,
          "entry_level_coverage": 0.0,
          "freshness": 0.0,
          "source_diversity": 0.0,
          "confidence": 0.0
        }
      },
      "coverage_limitations": [
        "Coverage scoring is heuristic and should be read together with freshness and source metadata.",
        "Coverage is placeholder-only and must not be presented as analyzed.",
        "No coverage evidence is available on this surface."
      ],
      "notes": ["No coverage evidence is available on this surface."],
      "heuristic": true,
      "safe_for_confident_market_comparison": false,
      "should_rank_as_confident_recommendation": false
    },
    "sector_coverage": {}
  },
  "category_winners": {
    "structural_ecosystem_score": "greater_sf",
    "early_career_accessibility_score": "greater_boston",
    "objective_opportunity_score": "greater_boston"
  },
  "notes": []
}
```

`category_winners` maps score field name to winning `region_id`. A value of
`null` means an honest tie. Categories with missing score values are omitted.
Comparison payload metadata includes a `region_coverage_not_confident` warning
when either side is Tier 3 or Tier 4.

### `POST /discover/personalized`

Request body:

```json
{
  "role_targets": ["product", "ai_cloud_adjacent"],
  "industry_preferences": ["ai", "cloud"],
  "career_stage": "entry_level",
  "prestige_preference": "medium",
  "brand_preference": "medium",
  "region_ids": ["greater_boston", "greater_sf"],
  "limit": 25
}
```

Returns the implemented personalized payload in a flattened `data` body. The response does not wrap the body in a `personalized` key. Preferences are request-scoped and are not persisted.

Response `data`:

```json
{
  "ranked_regions": [
    {
      "region_id": "greater_boston",
      "display_name": "Greater Boston",
      "priority_market": null,
      "personal_market_score": 0.78,
      "objective_opportunity_score": 0.74,
      "coverage": {
        "tier": "tier_2",
        "label": "Tier 2 - partial but useful market",
        "quality_score": 58.0,
        "components": {
          "company_coverage": 72.0,
          "hiring_coverage": 58.0,
          "entry_level_coverage": 58.0,
          "freshness": 80.0,
          "source_diversity": 0.0,
          "confidence": 58.0
        },
        "coverage_tier": "tier_2",
        "coverage_label": "Tier 2 - partial but useful market",
        "coverage_description": "This market is directionally useful, but one or more coverage signals are incomplete and must be treated as partial.",
        "coverage_quality_score": {
          "overall_score": 58.0,
          "components": {
            "company_coverage": 72.0,
            "hiring_coverage": 58.0,
            "entry_level_coverage": 58.0,
            "freshness": 80.0,
            "source_diversity": 0.0,
            "confidence": 58.0
          }
        },
        "coverage_limitations": [
          "Coverage scoring is heuristic and should be read together with freshness and source metadata.",
          "Coverage is partial; at least one signal class is incomplete."
        ],
        "notes": [],
        "heuristic": true,
        "safe_for_confident_market_comparison": false,
        "should_rank_as_confident_recommendation": false
      },
      "match_notes": []
    }
  ],
  "ranked_companies": [
    {
      "company_id": "comp_alphabet",
      "company_name": "Alphabet",
      "region_id": "greater_boston",
      "region_display_name": "Greater Boston",
      "personal_company_score": 0.84,
      "role_fit": 0.75,
      "industry_fit": 1.0,
      "prestige_fit": 0.9,
      "brand_fit": 1.0,
      "match_notes": []
    }
  ]
}
```

Personalized discovery keeps ranking behavior request-scoped and additive, but
Tier 3 and Tier 4 ranked regions receive a `region_coverage_not_confident`
warning and should not be treated as confident recommendations.

### `GET /recommendations/goal-modes`

Returns the canonical Layer 14 recommendation goal modes and API-safe profile
metadata. Each item includes:

- stable `goal_mode`
- user-facing `label` and `description`
- `prioritization_summary`
- weighted score components
- explicit penalty components
- missing-data behavior
- proxy/heuristic warnings

This endpoint exposes configuration only. It does not rank, generate strategy,
call AI, or persist anything.

### `POST /recommendations/strategy`

Produces deterministic Layer 14 ranked recommendations and a structured market
strategy plan from existing app-owned region/company output payloads.

Request body:

```json
{
  "goal_mode": "maximize_entry_level_access",
  "include_company_recommendations": true,
  "region_limit": 25,
  "company_limit": 25,
  "max_primary_regions": 3,
  "max_secondary_regions": 3,
  "max_fallback_regions": 3,
  "max_watchlist_items": 6,
  "max_company_targets": 5
}
```

Response `data` includes:

- `available_goal_modes`
- `selected_goal_mode`
- `ranking_profile_version`
- `ranking_tie_breaker`
- `ranked_region_recommendations`
- `ranked_company_recommendations`
- `market_strategy_plan`
- `warnings`

Ranked recommendation entries preserve targets, scores, score components,
missing/proxy/inferred components, penalties, warnings, explanations,
tradeoffs, weaknesses, manual verification, and evidence references. The
strategy plan preserves source recommendation references, primary/secondary/
fallback/watchlist targets, company/category/role-family guidance, timing
guidance, manual verification, and evidence warnings.

Unknown goal modes, invalid limits, and extra request fields are rejected. The
endpoint does not accept prompt fields, call AI, scrape jobs, invent companies,
or claim current openings.

## Layer 18 Historical Intelligence

Layer 18A adds read-only historical intelligence endpoints. They expose
append-only summaries of historical market/company observations; they do not
create snapshots, recalculate scores, mutate canonical market records, or expose
raw source references.

### `GET /platform/history/regions/{region_id}`

Returns a safe region history summary:

- `region_id`
- ordered `market_snapshots`
- ordered `sector_snapshots`
- historical `observations`
- latest `coverage_context` with coverage tier, freshness state, and confidence

Snapshot entries include observed score fields where available, coverage tier,
freshness state, confidence score, warning metadata, snapshot date/type, and
created time. Raw provenance/source internals are not exposed.

### `GET /platform/history/companies/{company_id}`

Returns safe company-region history:

- `company_id`
- ordered `region_snapshots`
- historical `observations`

Company-region snapshots include presence, hiring, entry-level, internship, and
coverage/freshness/confidence context where available. The endpoint is
read-only and does not change canonical company, hiring, entry-level, ranking,
or scoring records.

### `GET /platform/signals/regions/{region_id}`

Returns active, unexpired predictive signals for a region. The endpoint returns
signal language only: signal type, target, strength, confidence level, evidence
window, snapshot count, minimum-evidence status, summary, warnings, status, and
expiration where present.

Candidate, rejected, expired, and superseded signals are not returned as active.
Signal inputs remain internal audit records and are not exposed.

### `GET /platform/indices`

Returns public-safe proprietary market index metadata:

- index id/key/name/description
- status
- latest active version label
- public methodology summary
- created time

Internal formula weights and source/input records are not exposed.

### `GET /platform/indices/{index_key}/scores`

Returns public-safe score summaries for a proprietary index. Entries include
region id, score, rank where available, confidence, freshness, evidence
summary, public methodology summary, calculated time, and created time.

Index score inputs and internal weight configs remain internal audit records.
Index scores are derived intelligence and do not override canonical rankings,
official region scores, or recommendation outputs.

### `GET /platform/reports`

Returns public-safe summaries for published benchmark reports only. Draft,
review-ready, archived, and superseded reports are not returned as current
public reports.

Each summary includes report id, report key, title, report period, report type,
published status, summary, data window, and publication time. The endpoint does
not expose review notes, internal formula weights, raw index inputs, private
source internals, or admin-only metadata.

### `GET /platform/reports/{report_key}`

Returns the latest published public-safe benchmark report for a report key.
The detail payload includes:

- report key, title, report period, report type, and safe status
- summary and methodology summary
- data window
- freshness notes, confidence notes, coverage notes, and limitations
- ranked regions with score, rank, explanation, warnings, confidence, and
  freshness state
- report sections
- public-safe evidence summaries

Missing, draft, review-ready, archived, and superseded reports return `404` on
the public route. Benchmark report APIs are read-only and do not mutate
canonical rankings, official region scores, index scores, predictive signals,
recommendation outputs, or contribution data.

### `POST /platform/contributions`

Accepts authenticated, governed market-intelligence contributions. Basic
authenticated users may submit corrections, source suggestions, outdated-data
reports, role-access feedback, market-quality feedback, and company-presence
updates. Institution-scoped submissions require an active institution
membership with existing advisor/upload-style roles.

Accepted contribution types are:

- `verified_correction`
- `company_presence_update`
- `regional_employer_list`
- `career_center_intelligence`
- `internship_program_information`
- `role_access_feedback`
- `source_suggestion`
- `market_quality_feedback`
- `outdated_data_report`

The safe submission response includes contribution id, status, contribution
type, summary, created time, and a next-step message. It does not expose
internal reviewer notes, admin-only metadata, private institution data, source
validation internals, or canonical candidate internals.

Evidence URLs must be public `http`/`https` URLs without embedded credentials
or credential-like query fields. File paths, private references, and unsafe
uploaded-reference identifiers are rejected.

Submitted contributions create review queue records only. They do not mutate
canonical rankings, company rankings, official scores, index scores, predictive
signals, benchmark reports, recommendations, historical snapshots, public
confidence scores, public warnings, or published outputs.

### `GET /platform/contributions/review`

Returns the internal contribution review queue. This route requires existing
admin/data-reviewer access. It returns contribution metadata, structured
payload, evidence summaries, status, and timestamps for review. It is not a
public endpoint and is denied to ordinary authenticated users.

### `POST /platform/contributions/{contribution_id}/review`

Records an append-only contribution review and advances the contribution
lifecycle to `needs_review`, `verified`, `rejected`, `merged`, or `superseded`.
This route requires existing admin/data-reviewer access.

The safe review response includes contribution id, review decision, resulting
status, governed follow-up flags, and created time. It strips internal review
notes. Verified or merged reviews may record governed follow-up candidate/task
flags or refs, but review does not directly change canonical data, derived
indices/signals, benchmark reports, recommendations, historical snapshots, or
published outputs.

## Deferred Endpoints

## Layer 36A Career Decision Lifecycle APIs

Layer 36A adds protected user-owned APIs for the first complete personalized
career decision loop. All routes use the existing `/me` authentication boundary
and return the standard lightweight envelope.

Layer 36B consumes these routes from the authenticated frontend Decision
Workspace at `/markets/decisions`. The frontend uses centralized TypeScript API
client functions; it does not expose separate top-level resources for actions,
applications, outcomes, or reviews.

Implemented routes:

- `GET /me/decisions`
- `POST /me/decisions`
- `GET /me/decisions/{decision_id}`
- `PATCH /me/decisions/{decision_id}`
- `POST /me/decisions/{decision_id}/options`
- `POST /me/decisions/{decision_id}/compare`
- `GET /me/decisions/{decision_id}/journal`
- `POST /me/decisions/{decision_id}/select`
- `POST /me/decisions/{decision_id}/reopen`
- `POST /me/decisions/{decision_id}/plan`
- `GET /me/actions`
- `PATCH /me/actions/{action_id}`
- `POST /me/applications`
- `PATCH /me/applications/{application_id}/transition`
- `POST /me/outcomes`
- `GET /me/reviews/weekly`

`POST /me/decisions` creates a decision, an immutable decision-context snapshot
from Career Identity, and optional scenario options in one transaction-safe
service call. Scenario options can combine roles, regions, companies,
industries, work arrangement, compensation, and other structured fields.

`POST /me/decisions/{decision_id}/compare` creates a new context snapshot and a
persisted recommendation snapshot. The response exposes option fit, ranked
comparison, evidence buckets, structured challenges, limitations, confidence,
and evidence sufficiency. It may return `recommendation_status = "abstained"`
when evidence is insufficient or viable options are blocked by hard
constraints.

`GET /me/decisions/{decision_id}` returns the read model needed by the future
Decision Workspace UI: decision metadata, current context, options, current
recommendation, latest plan, applications, outcomes, and timestamps.

`GET /me/decisions/{decision_id}/journal` returns append-only decision versions
so historical reasoning and selections remain reconstructable after updates,
reconsideration, new recommendations, plan creation, or outcome recording.

`POST /me/decisions/{decision_id}/plan` creates a career action plan and
bounded career actions. The default plan includes research, preparation, and
review actions; callers can provide explicit actions with career-specific
action categories.

`POST /me/applications` and
`PATCH /me/applications/{application_id}/transition` track personal application
state only. Valid states are `considering`, `preparing`, `applied`, `response`,
`interview`, `final_round`, `rejected`, `withdrawn`, `offer`, `accepted`, and
`declined`. Transition history is append-only. This is not an employer ATS or
recruiter workflow surface.

`POST /me/outcomes` records observed outcomes from decisions, actions,
applications, skill work, research, networking, education, strategy changes, or
other career actions. Outcomes retain links to the original decision,
recommendation, option, action, and application where supplied or inferable.

`GET /me/reviews/weekly` deterministically aggregates stored state into
`happened`, `changed`, `worked`, `did_not_work`, `stalled`,
`invalidated_assumptions`, `reconsider`, `next_actions`, and `reminders`.
Reminder data is derived from decision review dates, action due dates, and
application follow-up dates; Layer 36A does not add a scheduler or live calendar
sync.

Cross-user access to decisions, options, actions, applications, outcomes,
journal entries, and review data is rejected at the service boundary and mapped
to not-found responses by the API.

## Layer 37A Deep Decision Intelligence APIs

Layer 37A extends the Layer 36 decision API family with deeper backend
intelligence. These routes are protected by the existing `/me` authentication
boundary and attach analysis to canonical Layer 36 decisions instead of
creating separate company, compensation, education, relocation, skill-gap, or
timing engines.

Implemented routes:

- `POST /me/decisions/{decision_id}/deep-analysis`
- `GET /me/decisions/{decision_id}/deep-analysis`
- `GET /me/strategic-reviews`

`POST /me/decisions/{decision_id}/deep-analysis` generates shared decision
factors, a bounded longitudinal context snapshot, recommendation evolution,
typed advisory findings, and a persisted strategic career review. The optional
request fields are `include_domains`, `window_start`, and `window_end`.
Supported domains are `company`, `compensation`, `skill_gap`, `education_roi`,
`relocation`, and `timing_pivot`.

The response includes `factors`, `longitudinal_context`,
`recommendation_evolution`, `advisory_findings`, and `strategic_review`.
Evidence kinds distinguish direct, derived, inferred, proxy, unavailable, and
conflicting evidence. Missing data remains unavailable evidence, not poor fit.

`GET /me/decisions/{decision_id}/deep-analysis` returns the latest generated
analysis for the authenticated owner. `GET /me/strategic-reviews` returns
persisted strategic review snapshots and can be filtered by `decision_id`.

Cross-user access returns not found. Unsupported domains return validation
errors. Layer 37A does not expose public personal decision analysis routes.

These endpoints may appear in older planning docs, but they are not currently implemented as public API routes:

- `GET /regions/{region_id}/companies`
- `GET /regions/{region_id}/hiring`
- `GET /regions/{region_id}/entry-level`
- `GET /companies/{company_id}/hiring`
- `GET /compare/contextual`
- `GET /search/companies`
- `GET /search/regions`
- `POST /admin/jobs/run`
- `POST /admin/refresh/region`
- `POST /admin/refresh/company`

The contextual challenge builder and seed path exist in backend code, but there is no public `GET /compare/contextual` endpoint in the current MVP.

## Runtime And Orchestration Boundaries

- Full output GET endpoints assemble response payloads in read-only mode. They do not create or update `OutputMetadata`; seed flows and output-build job handlers are responsible for cache metadata writes.
- Event invalidation returns directives/recommendations and can apply a narrow stale-marking pass for existing `OutputMetadata` rows affected by region/company/comparison output directives. Stale marking requires the DB-session-backed dispatch path; dispatch without a session reports stale marking as skipped. It does not delete rows, rebuild outputs, enqueue jobs beyond existing routing behavior, or run workers.
- Scheduler-generated `dependency_refs` are still opaque by default. The runtime also supports optional DB-backed refs in the form `kind:object_id@vN` through an injected database dependency resolver; there is no full source-version dependency graph.
- Queue dedupe uses an application-level check plus a partial unique index for active `dedupe_key` rows on SQLite/PostgreSQL. This is DB-level protection for supported databases, not a replacement for a production broker, distributed lock, or multi-worker orchestration.
- Audit and contextual challenge handlers/services exist for backend use, but they are not registered in the default worker registry and are not exposed as public API routes.

External-production work remains deferred: deployment hardening, provider-side account deletion/session revocation, broader security hardening, observability, distributed queue/broker integration, artifact storage/cache serving, and multi-worker stress testing.

## Canonical Geography

Region responses expose `region_id`, stable `public_slug`, display name, type,
primary city, state memberships, optional centroid/focus bounds, and explicit
market support status. Existing Region IDs remain valid route inputs.

- `GET /regions` returns canonical Region summaries.
- `GET /regions/{region_or_alias}` accepts a canonical ID, public slug, or
  unambiguous registered compatibility alias and returns canonical output.
- `GET /regions/resolve?input=...` exposes the routing/adapter resolution
  boundary. A resolved response includes the canonical identity and resolution
  source; unknown input is 404 and ambiguous input is 409.

Public API consumers should persist `region_id` and use `public_slug` for URL
presentation. Raw import keys and human labels are inputs, not canonical
geography. Alias registry internals are not exposed. Full policy and the
static-map data boundary are documented in `docs/CANONICAL_GEOGRAPHY.md`.

## MVP Non-Goals

Do not implement unless explicitly requested:

- hand-rolled auth or credential storage
- provider account deletion/session revocation beyond frontend sign-out
- saved profiles or application tracking outside protected user-owned Layer 35
  Career Identity and Layer 36 Decision Workspace workflows
- scraping or external APIs
- maps or advanced charts
- production deployment/security controls
- public mutation APIs for canonical truth
- public or anonymous persistent personalized outputs outside protected user-owned workflows
