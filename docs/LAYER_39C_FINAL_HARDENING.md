# Layer 39C Performance, Accessibility, Responsive, and Failure Audit

Date: 2026-09-02

Layer 39C closes repository-side production hardening for the Job Market
Intelligence application. It builds on the Layer 39A security/privacy controls
and Layer 39B reliability/operations controls without changing the deployment
architecture.

## Performance Audit

### Backend

Audited user-owned and high-use read paths across Career Identity, Career
Decisions, Deep Decisions, Career Agent memory/tools, user export/privacy,
Current Opportunities, and operator health.

The main demonstrated issue was in `CurrentOpportunityService.list_opportunities`.
The endpoint selected up to 10,000 opportunities, then repeatedly queried source
links, sources, and coverage contracts for each candidate row while checking
display eligibility and serializing payloads. That created an avoidable N+1
pattern on a high-value list endpoint.

Layer 39C adds repository batch reads for source links and data sources, and the
service now resolves coverage contracts from one bounded in-memory index for
the list path. Detail reads keep the existing simple single-record behavior.
The closeout audit separately verified that low query count was not hiding large
candidate materialization: the list path now scans SQL-filtered, SQL-ordered
candidate windows and stops once the requested display-eligible page is filled,
while preserving the prior 10,000-candidate maximum only as a worst-case scan
ceiling for sparse display-eligible data.

Representative SQLite query-count coverage now verifies that a list request over
12 canonical opportunities returns 5 payloads with no per-row SELECT fan-out.
The scale regression seeds 2,000 canonical opportunities and verifies a
`limit=20` request materializes only the first bounded candidate window rather
than thousands of `CurrentOpportunity` ORM rows.
SQLite query-plan coverage verifies that the existing Current Opportunities
filter path uses an index; no new database index was added because current
indexes already cover the audited predicates well enough for this scale.

### Pagination and Payloads

High-cardinality product list endpoints already expose bounded limits:

- Current Opportunities API caps opportunity lists at 500 and match lists at 100.
- Career Decisions, actions, applications, outcomes, deep-decision reviews, and
  findings use bounded service/repository limits for interactive reads.
- User data export intentionally remains unpaginated because its purpose is a
  complete authenticated export; it is rate-limited and user-scoped by Layer 39A.

### Caching Decision

No cache was added. The measured backend issue was repeated database lookups
inside one request, which is correctly solved with prefetching. There was no
evidence that cross-request caching is necessary, and caching user-specific
career or decision data would introduce invalidation and privacy risk without a
demonstrated production bottleneck.

## Frontend Performance

The production Vite build showed one large initial chunk. The root cause is the
large single `App.tsx` shell plus statically imported major route pages.

Layer 39C lazy-loads the largest route pages:

- Career Identity
- Decisions
- Current Opportunities
- Career Agent
- Market Intelligence
- Policy Intelligence
- Opportunity Routes
- Data Standards
- User Intelligence Dashboard

Measured build result in this environment:

- Baseline initial JS chunk: `948.65 kB` raw, `240.14 kB` gzip.
- After route splitting: `737.16 kB` raw, `193.58 kB` gzip.

The Vite large-chunk warning remains because much of the product UI is still
implemented inside `App.tsx`. Moving that monolith into route modules would be a
larger product/frontend architecture refactor and is deferred outside Layer 39C.

## Accessibility Audit

Audited app shell, public routes, Career Identity, Decisions, Current
Opportunities, Career Agent, account/privacy controls, policy pages, institution
surfaces, shared cards/states, and route loading behavior.

Layer 39C remediations:

- Added a keyboard-visible skip link to the authenticated app shell.
- Converted the authenticated shell from an outer `<main>` containing sidebar
  navigation into an app wrapper with a dedicated `<main id="main-content">`.
- Added a global `:focus-visible` baseline for interactive controls.
- Added a polite route-loading status for lazy-loaded routes.

Existing surfaces already rely mostly on native buttons, links, labels,
fieldsets, tables/role-table structures, landmarks, and named sections. This is
not a formal WCAG certification; the application is audited and remediated
against applicable WCAG-aligned criteria within tested surfaces.

## Responsive Audit

Audited primary navigation, app shell, dense grids, tables, forms, decision
workspaces, Current Opportunities operations tables, policy tabs, account
settings, Career Identity panels, and long generated/user content.

Existing responsive CSS already collapses the authenticated shell at 1040px and
major form/grid layouts at 820px, 760px, 720px, 900px, and route-specific
breakpoints. Existing table-heavy surfaces use intentional horizontal scrolling
or grid collapse. Layer 39C adds test coverage for the app shell responsive and
keyboard-focus CSS contracts but does not redesign the UI.

## Failure Drills

Layer 39C exercises the mechanisms built in Layer 39B:

- DB unavailable: readiness reports `not_ready`, database check is `failed`,
  liveness remains a separate public process check, and safe payloads avoid
  exception/connection detail leakage.
- Source unavailable: a Current Opportunities source failure creates a failed
  run, preserves previously promoted opportunities, keeps last successful
  refresh visible, and redacts raw failure detail from operator summaries.
- Failed migration: the Layer 39B controlled Alembic failure proof remains the
  repository mechanism. It begins from a known revision, injects a failing
  upgrade in a disposable SQLite Alembic environment, verifies readiness rejects
  incompatible state, retries safely when revision was not advanced, and reaches
  the expected revision after recovery. SQLite DDL is not claimed to equal
  PostgreSQL transactional DDL.
- Broken refresh: existing Current Opportunities tests cover processing/write
  exceptions causing failed runs without falsely reporting success or deleting
  prior valid data.
- Auth outage: Auth0/JWKS fetch failure fails protected routes closed with a
  safe `auth_error`; public liveness remains available.
- Bad deployment: strict readiness rejects an unversioned schema and includes a
  safe release identifier so operators can identify the unhealthy build.

## Final Security and Reliability Audit

No new Critical or High repository-side Layer 39 findings remain after 39C.

Medium residual:

- The frontend initial chunk remains larger than Vite's 500 kB warning threshold
  because `App.tsx` still owns many embedded product surfaces. Route-level
  splitting materially reduces the chunk but a deeper split is deferred to a
  future frontend architecture/performance pass.

Low residual:

- Query-plan verification is SQLite-local. It verifies index use in the
  repository test environment but is not a Neon/PostgreSQL production plan.

External production-launch prerequisite:

- `PRODUCTION_NEON_RESTORE_VALIDATION_REQUIRED` remains from Layer 39B. Before
  production launch, perform an isolated Neon/PostgreSQL restore into a separate
  branch/database and verify Alembic revision, readiness, and representative
  application reads against that restored target.
