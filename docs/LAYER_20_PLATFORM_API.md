# Layer 20 - Platform API

Layer 20 defines the versioned Platform API product surface for external
consumers. Batch 20A added public-safe read endpoints. Batch 20B added
backend-owned API key access control, product entitlements, usage metering,
tier-based limits, and audit logs for those Layer 20 routes only. Batch 20C
packages the secured API into a developer-facing platform with docs, governance,
spec exports, analytics helpers, iframe embed policy, and conservative licensing
registry.

Layer 20 does not add write APIs, raw source feeds, Stripe integration, billing
record exposure, private user data, or institution-specific data access.

## Batch 20A Implementation

Batch 20A creates the public API foundation under `/api/v1/platform`:

- `GET /api/v1/platform/regions/{region_id}/scores`
- `GET /api/v1/platform/companies/{company_id}/geography`
- `GET /api/v1/platform/regions/{region_id}/early-career-access`
- `GET /api/v1/platform/markets/hiring-concentration`
- `GET /api/v1/platform/markets/compare`

The stable product identifiers are:

- `region_scores`
- `company_geography`
- `early_career_access`
- `hiring_concentration`
- `market_comparisons`

Responses use the Layer 20 envelope:

- `status`: `success`, `partial`, or `error`
- `data`: endpoint-specific public DTO
- `meta.api_version`: currently `v1`
- `meta.schema_version`: currently `2026-06-20a`
- `meta.product_id`: one stable product identifier
- `meta.freshness`: public freshness status and timestamps
- `meta.confidence`: qualitative confidence label and basis
- `meta.source_summary`: public-safe count/category summary only
- `meta.warnings`: public-safe warning codes/messages
- `error`: safe error object for failed responses

## Boundary Rules

Batch 20A maps from existing product-safe outputs and aggregate rows into
external DTOs. It does not expose internal output DTOs directly.

The public DTO guard rejects forbidden field names such as raw score totals,
score ruleset versions, source version bundles, source identifiers, raw scrape
records, private/admin metadata, user ids, billing records, and ingestion
metadata. Source summaries are reduced to counts, categories, and public notes.

The new endpoints are read-only and do not create `OutputMetadata` cache rows.
Public demo mode allowlists only the five `GET` routes and remains fail-closed
for writes and unrelated paths. The route handlers still require a valid
Platform API key, so public-demo allowlisting does not bypass Layer 20 access
control.

## Batch 20B Access Control

All `/api/v1/platform` requests require `X-API-Key`. The enforcement path is
route-local to `backend/api/platform_public.py`; existing app auth, public
reports, benchmarks, search, read, metadata, monetization, billing, and
non-platform routes are unchanged.

API keys are created by `backend/platform/api_keys.py`:

- Raw keys use the `jmi_platform_{environment}_...` format.
- Raw keys are returned only in the creation result.
- Storage uses `key_hash`, `key_prefix`, and `display_key`; there is no raw key,
  token, or secret column.
- Key status is `active` or `revoked`.
- Key environment is `test` or `live`.
- Keys carry a backend-stored tier and product scope list.

Tier policy is defined in `backend/platform/entitlements.py`:

- `trial`: `region_scores`
- `starter`: `region_scores`, `company_geography`, `early_career_access`
- `growth`: starter products plus `hiring_concentration`
- `enterprise`: all Layer 20 products, including `market_comparisons`

An endpoint is allowed only when both checks pass:

- The key tier includes the endpoint product id.
- The key's stored product scopes include the endpoint product id.

Denials return the public Layer 20 error envelope with safe codes such as
`MISSING_API_KEY`, `INVALID_API_KEY`, `REVOKED_API_KEY`,
`MISSING_PRODUCT_SCOPE`, `ENTITLEMENT_DENIED`, `RATE_LIMIT_EXCEEDED`, and
`USAGE_LIMIT_EXCEEDED`.

Usage and audit behavior:

- Successful requests record one allowed usage unit.
- Denied requests record a denied usage event with zero billable request units.
- Rate limits are tier-based request windows.
- Monthly limits are derived from allowed usage rows for deterministic test-safe
  behavior.
- Audit logs are written for allowed requests, denied requests, missing keys,
  invalid keys, revoked keys, entitlement denials, rate limits, and monthly
  usage-limit denials.
- Audit and usage rows store key ids/prefixes, product ids, route, method,
  outcome, status code, and safe decision metadata only.

## Remaining Work

## Batch 20C Platform Packaging

Developer documentation:

- `backend/platform/docs_registry.py` defines docs metadata for overview,
  authentication, key safety, tiers/scopes, rate limits, monthly usage limits,
  errors, envelope metadata, freshness, confidence, source summary, warnings,
  each Platform API product, and versioning/deprecation.
- Frontend public pages were added for `/developers`, `/developers/docs`, and
  product/topic doc subroutes.
- Docs pages explain `X-API-Key`, product ids, safe errors, freshness,
  confidence, source summaries, warnings, and public-safe response posture.

Spec exports:

- `GET /api/v1/platform/docs/openapi.json`
- `GET /api/v1/platform/docs/postman.json`

The exports are generated from stable builders and match the five secured data
endpoints, `X-API-Key` header authentication, current API version, schema
version, product ids, and documented safe error codes.

Governance:

- `backend/platform/versioning.py` defines current API version, schema version,
  supported versions, minimum deprecation notice, additive-change rules, and
  breaking-change rules.
- Breaking changes require a new versioned path. Supported versions receive at
  least 180 days deprecation notice before removal, except immediate security
  or leakage protections.

Usage analytics:

- `backend/platform/analytics.py` summarizes usage by product, usage by key id
  or prefix, denied request counts, rate-limit denials, monthly usage consumed,
  and monthly remaining units.
- Batch 20C keeps analytics as backend service helpers rather than public routes
  because no new customer/admin analytics auth surface was required.

Partner embeds:

- `backend/platform/embeds.py` defines iframe-first embed product ids, approved
  domains, blocked-domain denials, attribution requirements, freshness/source
  summary requirements, and a usage tracking hook.
- `GET /api/v1/platform/embeds/{embed_product_slug}` is the backend-owned
  enforcement path used by the iframe surfaces. It evaluates request `Origin`,
  request `Referer`, and the parent origin derived by the frontend from
  `ancestorOrigins` or `document.referrer`.
- The actual frontend iframe routes at `/embed/region-comparison` and
  `/embed/market-score-card` render the normal widget only after the backend
  policy returns an allowed decision.
- Blocked, unapproved, or missing origins receive a bounded denial state with
  `EMBED_DOMAIN_NOT_ALLOWED`; the denial state does not expose policy internals,
  raw data, source ids, scoring internals, keys, billing records, or ingestion
  metadata.
- Allowed and denied embed attempts are tracked through the backend embed usage
  hook using safe product id, normalized origin domain, outcome, event type, and
  timestamp fields.
- Embed renderers include attribution, freshness, confidence, source summary,
  and warnings. They do not expose raw exports or internal fields.

Data licensing:

- `backend/platform/licensing.py` defines conservative derived dataset entries:
  `regional_market_intelligence_v1`, `early_career_access_scores_v1`,
  `company_region_presence_v1`, and
  `historical_hiring_signal_snapshots_v1`.
- Entries include descriptions, sample fields, excluded fields, refresh cadence,
  allowed formats, minimum tier, restrictions, attribution rules, and
  source-safety notes.
- A public `/data-licensing` page presents derived dataset cards and explicitly
  excludes raw scrape/job records, source ids, private user data, billing
  records, ingestion metadata, and scoring formulas.

## Remaining Future Work

- Add production API governance hardening.
- Add SDKs only after customer API ergonomics stabilize.
- Add full billing-provider integration through a clean backend plan bridge.
- Add enterprise self-serve portal workflows for key management and analytics.
- Add advanced embed customization, contract-specific allowlists, and embed
  analytics views.
- Add export automation for licensed datasets after commercial and source
  restrictions are finalized.
- Connect commercial packaging to billing/Stripe only through a clean backend
  plan bridge; Layer 20 intentionally keeps billing-provider behavior unchanged.
