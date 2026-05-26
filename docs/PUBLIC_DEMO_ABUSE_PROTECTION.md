# Public Demo Abuse Protection

Layer 10 public demo abuse protection is designed for casual public exposure.
It is intentionally lightweight and provider-neutral. It does not claim
commercial-grade anti-abuse coverage.

## In-App Protection

`APP_ENV=public_demo` uses the same fail-closed read-only API allowlist
documented in `docs/PUBLIC_DEMO_ENVIRONMENT.md`. Abuse protection is layered on
top of that posture and does not make mutation routes available.

### Rate Limiting

The backend includes an in-memory per-client rate limiter in
`backend/api/protection.py`.

Public demo defaults:

- `RATE_LIMIT_ENABLED=true`
- `RATE_LIMIT_REQUESTS=60`
- `RATE_LIMIT_WINDOW_SECONDS=60`

Local/test/private demo defaults keep rate limiting disabled unless explicitly
enabled. Staging/production-style environments also default rate limiting on.

The limiter returns a safe `429` response with error type `rate_limited`,
`Retry-After`, and `X-Request-ID`. It does not expose internal state. `/health`,
`/ready`, and CORS preflight `OPTIONS` requests are exempt so uptime/readiness
checks remain usable.

This limiter is process-local. It is sufficient for local public-demo posture
and casual misuse, but it is not a distributed production rate limiter.

### Request Size Limits

Request body size is enforced by the same middleware before route handlers read
the body.

Public demo default:

- `MAX_REQUEST_BODY_BYTES=65536`

Local/test/private demo default:

- `MAX_REQUEST_BODY_BYTES=1048576`

Oversized bodies return a safe `413` response with error type
`request_too_large` and `X-Request-ID`. The response does not echo request body
content, stack traces, SQL, credentials, or implementation details.

### CORS

`APP_ENV=public_demo` requires an explicit `CORS_ALLOWED_ORIGINS` value. Use the
exact public frontend origin:

```bash
APP_ENV=public_demo
CORS_ALLOWED_ORIGINS=https://<public-demo-frontend-host>
```

Wildcards are rejected globally. Origins must be exact HTTP(S) origins without
paths, query strings, fragments, or credentials. If the frontend and API are
served from the same origin, use the exact shared origin or route API traffic
through the frontend host.

### Security Headers

`SECURITY_HEADERS_ENABLED` defaults to `true` in public demo mode. Responses
include basic browser safety headers when enabled. This is an in-app baseline,
not a replacement for edge/provider security controls.

## Bot Protection Posture

The app does not include a CAPTCHA, proof-of-work challenge, managed bot score,
or provider SDK. Do not commit provider credentials.

Recommended deployment-layer controls for a public demo:

- scheduled uptime checks separate from user traffic
- edge/provider request throttling in front of the API
- bot/challenge rules for repeated high-volume traffic
- WAF rules for obvious scanner paths and hostile methods
- CDN or platform caching for static frontend assets
- log/alert rules for repeated `429`, `413`, and `403 public_demo_read_only`
  responses

These controls should live in the deployment or edge provider. The application
keeps provider-neutral hooks and safe responses so those systems can monitor by
status code, route, request ID, and latency.

## Environment Differences

- `local`: developer-friendly; SQLite default allowed; rate/security flags
  default off; CORS can be empty for the Vite proxy.
- `private_demo`: explicit database required; authenticated mutation workflows
  may be exercised; rate/security flags default off unless configured.
- `staging`: non-SQLite database required; rate/security flags required on;
  mutations may be exercised for QA behind normal auth/role gates.
- `public_demo`: explicit database and exact CORS origin required; rate/security
  flags required on; public API is fail-closed read-only.
- `production`: non-SQLite database required; rate/security flags required on;
  separate production observability/security controls are still needed.

## Read-Only Alignment

The public demo allowlist remains:

- `GET /health`
- `GET /ready`
- public market/search/source GET routes used by `/markets`
- `POST /discover/personalized`, explicitly allowed because it is
  request-scoped and non-persistent
- `GET /recommendations/goal-modes`
- `POST /recommendations/strategy`, explicitly allowed because it is
  request-scoped, non-persistent, and uses existing app-owned outputs
- `OPTIONS *` for CORS preflight

Admin routes, user persistence, overrides, repairs, canonical writes, refresh
execution, ingestion execution, and unknown future routes remain denied.

## External Setup Still Required

Before exposing a deployed public demo, configure:

- exact `CORS_ALLOWED_ORIGINS`
- deployment/edge request throttling if available
- provider bot/challenge rules if available
- log retention and alert routing
- frontend/API uptime checks

This document covers public-demo abuse protection, not full production security
or commercial anti-abuse infrastructure.
