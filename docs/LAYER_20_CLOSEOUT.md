# Layer 20 Closeout - Platform API

Layer 20 is now packaged as a secured external Platform API foundation.

## 20A Summary

Batch 20A created the versioned public read surface under `/api/v1/platform`.
It added external DTOs, stable product ids, public-safe mapping adapters, and
read-only endpoints for region scores, company geography, early-career access,
hiring concentration, and market comparisons.

## 20B Summary

Batch 20B secured those data endpoints with backend-owned API keys, hashed key
storage, key status, environment, tiers, product scopes, entitlements, rate
limits, monthly usage checks, usage events, audit logs, and migration `0024`.
Non-platform routes and main app auth remained unchanged.

## 20C Summary

Batch 20C added platform packaging:

- Developer docs registry and frontend developer documentation pages.
- OpenAPI and Postman export routes for the secured Layer 20 endpoints.
- Versioning and deprecation governance.
- Usage analytics summary helpers.
- Iframe partner embed policy, backend-owned domain enforcement, safe denial
  states, usage tracking hooks, and frontend renderers.
- Conservative derived-dataset licensing registry and public licensing page.

## Completion Posture

Layer 20 is externally usable as a controlled, versioned, read-only market
intelligence API. Data access requires `X-API-Key`; docs/spec exports are public
metadata. Payloads preserve the public-safe envelope with freshness, confidence,
source summary, and warnings.

The final 20C narrow fix wires `/embed/region-comparison` and
`/embed/market-score-card` through the backend embed policy endpoint before
rendering. Approved domains render the iframe widget. Blocked, unapproved, or
missing origins receive the safe `EMBED_DOMAIN_NOT_ALLOWED` denial state, and
allowed plus denied attempts are tracked without raw keys, request payloads, or
internal data.

Boundary protections remain in force: no raw scrape/job records, scoring
internals, private user data, institution-only data, billing records, ingestion
metadata, source ids, raw keys, or raw licensed third-party data are exposed.

## Future Work

- SDKs.
- Full billing-provider integration.
- Enterprise self-serve portal and customer-facing analytics.
- Advanced embed customization.
- Contract-specific dataset export automation.
