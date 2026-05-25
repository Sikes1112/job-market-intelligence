# API Surfaces

This file documents the MVP API surface that is currently implemented. It is intentionally narrow: the local demo reads seeded backend data and exposes Auth0-backed frontend sign-in/account workflows for protected `/me` routes plus governed Layer 9 admin review, override, and repair APIs, but it does not expose scraping, broad admin mutation tooling, maps, or production deployment controls. Current status is an internal-production baseline for local/single-process operation, not external-production readiness.

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

Frontend Auth0 SPA settings:

- `VITE_AUTH0_DOMAIN`
- `VITE_AUTH0_CLIENT_ID`
- `VITE_AUTH0_AUDIENCE`
- `VITE_AUTH0_REDIRECT_URI`, optional; defaults to `/markets` on the current
  browser origin

When frontend Auth0 settings are absent, the Vite app runs in local/demo mode:
public market exploration remains available and account controls are disabled.
The frontend attaches Bearer tokens only to protected `/me` requests.

Public market exploration routes remain unauthenticated.

## Public Demo Runtime Posture

`APP_ENV=public_demo` is an externally viewable, read-only demo posture. It is
not production. In public demo mode, the backend fails closed to an explicit
allowlist of public read/search/source endpoints plus the non-persistent
`POST /discover/personalized` request-scoped calculation. Protected `/me` and
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

Exports app-owned Layer 7 user data for the current user: user/profile metadata,
external auth identity mappings, saved preferences, saved market artifacts, and
personalized recommendation snapshots.

### `DELETE /me`

Deactivates the current app-level user account. This deletes the current user's
profile, external auth identity mappings, preferences, saved artifacts, and
recommendation snapshots, then leaves the internal `users` row as a
`deactivated` tombstone. Auth0 provider-side account deletion and session
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

Layer 11B adds backend workflow metadata for planned region expansion across
NYC, Seattle, Austin, DC/NoVA, Boston, SF, Atlanta, Chicago, and LA. The
workflow states are `candidate`, `intake_started`, `normalized`,
`provenance_attached`, `review_ready`, `approved`, `published`, and
`refresh_enabled`.

The workflow checklist tracks region identity, source coverage,
company-region presence, hiring-signal support, entry-level-signal support,
scoring readiness, freshness readiness, provenance attachment, admin approval,
and output-refresh readiness. Workflow rows reference existing ingestion,
provenance, admin review, and refresh/output contracts; they do not create
canonical regions, run ingestion, scrape sources, publish outputs, or bypass
admin/provenance/freshness controls.

No public or frontend route is exposed for this workflow in Batch 11B.

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
      "state": "fresh",
      "version": 1
    }
  ]
}
```

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
      "opportunity_score": 0.74,
      "freshness": {
        "freshness_status": "fresh | stale | partial | unknown | seeded_demo",
        "data_basis": "seeded_demo | real_imported | mixed | unknown",
        "last_collected_at": "ISO-8601 timestamp or null",
        "source_count": 1,
        "low_confidence_warning": null
      },
      "has_real_data": true
    }
  ],
  "count": 1
}
```

`GET /companies/search` supports optional `query`, `sector`, `industry`,
`role_family`, `region_id`, `current_hiring`, `has_entry_level_access`, and
`presence_status` filters. Company matches come from canonical company,
presence, hiring, and entry-level rows, not region-output payload text.

`GET /companies/{company_id}/regions` returns canonical region links for a
company, including `presence_status`, `current_hiring`,
`has_entry_level_access`, per-row freshness/source metadata, and `count`.

`GET /regions/{region_id}/sources` and `GET /companies/{company_id}/sources`
return source explanations for the subject. Source details are built from
explicit `FactSourceLink` evidence when present. Missing source evidence is
represented honestly as an empty `sources` list with `source_count: 0` and
unknown freshness/source basis.

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
    "scores": {}
  },
  "region_b": {
    "region_id": "greater_sf",
    "display_name": "Greater San Francisco / Silicon Valley",
    "scores": {}
  },
  "category_winners": {
    "structural_ecosystem_score": "greater_sf",
    "early_career_accessibility_score": "greater_boston",
    "objective_opportunity_score": "greater_boston"
  },
  "notes": []
}
```

`category_winners` maps score field name to winning `region_id`. A value of `null` means an honest tie. Categories with missing score values are omitted.

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
      "personal_market_score": 0.78,
      "objective_opportunity_score": 0.74,
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

## Deferred Endpoints

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

## MVP Non-Goals

Do not implement unless explicitly requested:

- hand-rolled auth or credential storage
- provider account deletion/session revocation beyond frontend sign-out
- saved profiles or application tracking
- scraping or external APIs
- maps or advanced charts
- production deployment/security controls
- public mutation APIs for canonical truth
- persistent personalized outputs
