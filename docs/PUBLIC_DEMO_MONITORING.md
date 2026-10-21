# Public Demo Monitoring

> **Historical operations reference.** This predates the deployed `public_guest_demo` topology. Use the [Engineering Guide](ENGINEERING_GUIDE.md#operations) for current readiness, session, data-lifecycle, and failure-investigation behavior.

Layer 10 public demo monitoring is intentionally provider-neutral. It gives a
maintainer enough visibility to know whether the public demo is reachable,
whether the API is ready, whether errors are occurring, and whether the key
demo routes are slow. It is not full production observability.

## Monitoring Targets

Use these public-demo-safe targets:

- Frontend uptime: `GET /`
- Frontend demo entry: `GET /markets`
- API liveness: `GET /health`
- API readiness: `GET /ready`
- API demo read path: `GET /regions`
- API search path: `GET /regions/search`

All of these checks are non-mutating. They are compatible with
`APP_ENV=public_demo`; `/health` and `/ready` are explicitly allowed by the
public demo API allowlist and exempt from the in-app rate limiter.

## Health And Readiness

`GET /health` is a lightweight liveness check. It returns service identity and
environment posture, but it does not touch the database and does not expose
connection strings, secrets, stack traces, or dependency internals.

`GET /ready` performs the currently supported readiness check: application
configuration plus a minimal database reachability query. It reports only
`ok`/`failed` dependency states. It does not require seeded demo data and does
not expose database URLs, SQL, credentials, or exception messages.

## API Error Monitoring

The API attaches a safe `X-Request-ID` header to normal and error responses.
If a safe inbound `X-Request-ID` is supplied, it is preserved; otherwise the
backend generates one.

API errors use safe envelopes. Validation, HTTP, database, unexpected, rate,
request-size, and public-demo read-only denials return status codes plus safe
error types/messages/request IDs. They do not expose stack traces, SQL text,
database URLs, provider credentials, or exception detail.

The request observability middleware emits one structured JSON log record per
HTTP request through the `backend.api.requests` logger with:

- `request_id`
- `method`
- `path`
- `status_code`
- `duration_ms`
- `error_type`

This is the provider-neutral extension point for Render logs, OpenTelemetry,
Sentry, Datadog, Honeycomb, CloudWatch, or another external sink. No vendor
credentials or SDK integration are required by this repo.

## Frontend Error Monitoring

The React app is wrapped in an error boundary. If rendering fails, the user sees
a safe fallback that does not display stack traces or internal exception detail.

Frontend API failures preserve safe backend request IDs when the backend
returns one. User-facing request failures can show that reference ID, and the
frontend reports provider-neutral events through `configureFrontendErrorReporter`
in `src/errorMonitoring.ts`.

The default frontend reporter is unset. A deployment may attach a provider
adapter that receives:

- `source`
- `name`
- `message`
- `route`
- `path`
- `statusCode`
- `requestId`

Do not commit provider credentials. Configure provider DSNs/API keys in the
hosting provider if a future deployment adds a real reporting sink.

## Smoke And Latency Check

The frontend package includes a non-mutating smoke script:

```bash
cd frontend
FRONTEND_BASE_URL="https://<frontend-host>" \
API_BASE_URL="https://<api-host>" \
npm run smoke:public-demo
```

For local development it defaults to:

- `FRONTEND_BASE_URL=http://127.0.0.1:5173`
- `API_BASE_URL=http://127.0.0.1:8000`

Optional timeout:

```bash
SMOKE_TIMEOUT_MS=3000 npm run smoke:public-demo
```

The script prints one line per check with outcome, status code, latency, method,
and URL. It exits non-zero when a route is unreachable or returns a non-2xx
status. It does not call admin, ingestion, refresh, user persistence, snapshot,
override, repair, or other mutation surfaces.

## What Remains External

Public demo monitoring still requires external setup for:

- scheduled uptime checks
- alert routing
- log retention
- dashboards
- frontend error provider integration, if desired
- latency thresholds/SLOs

This is enough for public demo readiness, not full production observability.
Production-grade monitoring would also need provider configuration, alert
ownership, retention policy, synthetic checks from multiple regions, metrics,
traces, and incident runbooks.

Public-demo abuse protection details, including rate limits, request-size
limits, CORS posture, and bot-protection recommendations, are documented in
`docs/PUBLIC_DEMO_ABUSE_PROTECTION.md`.
