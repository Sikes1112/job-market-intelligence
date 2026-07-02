# Layer 17 API Access

Batch 17C adds controlled external API access for governed read/access workflows.
External APIs are not public open data feeds and are not resale surfaces.

## API Client Model

API access is represented by:

- `ApiClient`
- `ApiKey`
- `ApiScope`
- `ApiAccessPolicy`
- `ApiUsageRecord`
- `ApiRateLimitDecision`
- `ApiResponseEnvelope`
- `ApiAccessAuditEvent`

Raw API keys are generated only at creation time. The database stores key hash,
safe prefix, and display key only.

## Supported Scopes

- `region:read`
- `company_geography:read`
- `market_signal:read`
- `institution_dashboard:read`
- `exports:create`
- `imports:create`

No ATS, applicant, student profile, resume submission, recruiter outreach, CRM,
or application pipeline scopes are defined.

## External Routes

- `GET /api/external/v1/regions`
- `GET /api/external/v1/regions/{region_id}/intelligence`
- `GET /api/external/v1/companies/{company_id}/geography`
- `GET /api/external/v1/market-signals`
- `GET /api/external/v1/institutions/{organization_id}/dashboard`

All external routes require an API key in `X-API-Key` and a scope check.
Institution dashboard access additionally requires the API client to be bound to
the exact requested institution. The app `Authorization` header remains reserved
for verified user JWTs.

## Admin Routes

- `POST /api/integrations/api-clients`
- `GET /api/integrations/api-clients`
- `PATCH /api/integrations/api-clients/{api_client_id}`
- `POST /api/integrations/api-clients/{api_client_id}/keys`
- `POST /api/integrations/api-keys/{api_key_id}/revoke`
- `GET /api/integrations/api-clients/{api_client_id}/usage`

These routes use existing admin dependencies. Raw keys are not returned by list
or usage routes.

## Response Envelope

External API responses use:

- `data`
- `meta.generated_at`
- `meta.coverage_tier`
- `meta.freshness_status`
- `meta.confidence`
- `meta.source_governance`
- `meta.governance_warnings`
- `meta.partner_contributed_evidence`
- `meta.rate_limit.limit`
- `meta.rate_limit.remaining`
- `meta.rate_limit.reset_at`

Internal-only scoring/source fields are stripped before responses leave the
service.

## Rate Limiting

Each API client carries a request limit and reset window. Allowed, denied,
revoked, missing-scope, and rate-limited decisions are recorded in usage/audit
tables. Exhausted clients receive a safe 429 response with rate-limit metadata.
