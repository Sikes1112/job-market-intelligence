# Layer 15 Business Model and Monetization Layer

Layer 15 defines the internal monetization foundation. It decides product
access boundaries, plan metadata, entitlement decisions, report product catalog
entries, and the billing-adapter boundary.

## Scope

Implemented in Batch 1:

- `backend/monetization/segments.py` separates audience segments from buyer
  segments.
- `backend/monetization/features.py` defines canonical free and paid feature
  keys with rationale and trust constraints.
- `backend/monetization/plans.py` defines subscription and institutional
  license plans with configurable placeholder prices.
- `backend/monetization/entitlements.py` centralizes access decisions.
- `backend/monetization/reports.py` defines the report product catalog and
  feature requirements.
- `backend/api/monetization.py` exposes read-only catalog and access-preview
  endpoints.
- `frontend/src/App.tsx`, `frontend/src/api.ts`, and `frontend/src/types.ts`
  expose a read-only frontend monetization surface.

Implemented in Batch 3:

- `backend/monetization/accounts.py` defines provider-agnostic account type,
  plan status, assignment source, and safe metadata contracts.
- `backend/monetization/models.py` and
  `alembic/versions/0013_monetization_account_state.py` add internal
  monetization account, plan assignment, and usage counter tables.
- `backend/monetization/resolver.py` resolves effective account entitlements,
  defaulting unknown/public users to Free.
- `backend/monetization/enforcement.py` centralizes account-aware access and
  usage-limit decisions.
- `backend/api/monetization.py` adds read-only account entitlement and usage
  endpoints.

Implemented in Batch 4:

- `backend/api/monetization_access.py` centralizes API blocked-entitlement
  responses.
- Existing paid workflow routes now use account-aware enforcement for saved
  watchlist creation and alert feed actions.
- Authenticated comparison and personalized-discovery requests increment free
  usage counters only after successful responses.
- `POST /monetization/reports/{report_key}/generate` and
  `POST /monetization/reports/{report_key}/export` provide narrow structured
  JSON stubs guarded by report/export entitlements.
- `/markets/plans` renders effective account plan, account status, included
  features, usage counters, and account-aware access-preview decisions.

Implemented in Batch 5:

- `backend/billing/provider.py` defines provider-neutral billing contracts.
- `backend/billing/stripe_adapter.py` implements Stripe Checkout, Billing
  Portal session creation, and webhook signature verification as an adapter.
- `backend/billing/service.py` maps verified provider events into internal
  monetization plan assignments.
- `backend/billing/models.py` and
  `alembic/versions/0014_billing_provider_refs.py` store isolated provider
  customer/subscription refs and webhook idempotency records.
- `backend/api/billing.py` exposes billing status, checkout session, portal
  session, and Stripe webhook endpoints.
- `/markets/plans` can start backend-created checkout for configured
  self-serve plans and open billing management when a customer ref exists.

Not implemented:

- real PDF/file export rendering
- institutional self-serve checkout
- tax/VAT, dunning, invoice customization, and reconciliation jobs
- changes to recommendation ranking

## Segments

Audience segments are the people receiving guidance:

- students
- early-career job seekers
- relocation candidates
- parents and advisors

Buyer segments are institutional purchasers:

- career centers
- bootcamps
- universities
- workforce boards

These are separate by design. An institution may buy access for students, but
the buyer segment does not become a ranking signal or a proxy for private
recommendation state.

## Free vs Paid Boundary

Free features include:

- basic region exploration
- public demo markets
- limited comparisons
- limited personalized discovery
- basic recommendation preview

The basic recommendation preview explicitly keeps the core recommendation
conclusion visible to free users. Paid access must not hide that conclusion or
change the recommendation ranking.

Paid features include:

- saved watchlists
- alerts
- advanced recommendation reports
- full market coverage
- exportable strategy plans
- deeper company geography
- saved comparison history
- full report generation
- institutional license management and advising workflows

The paid boundary is tied to durable workflow value, deeper maintained coverage,
institutional administration, report packaging, monitoring, and exportability.
It is not tied to manipulating or withholding the core recommendation result.

## Plan Model

Canonical plan keys:

- `free`
- `individual_monthly`
- `individual_annual`
- `student_annual`
- `career_center_license`
- `bootcamp_license`
- `university_license`
- `workforce_board_license`

Each plan defines:

- display name
- buyer kind and buyer segment where relevant
- billing interval
- intended audience
- included feature keys
- usage limits where relevant
- upgrade targets where relevant
- configurable price metadata

Prices are placeholder/test metadata. Final pricing should live in deployment or
billing configuration and later payment-provider adapters.

## Entitlement Model

`backend.monetization.entitlements.decide_access()` is the pure plan/feature
access decision function. It accepts:

- `plan_key`
- `feature_key`
- optional usage context

It returns:

- `allowed`
- `plan_key`
- `feature_key`
- `reason`
- `upgrade_plan_keys`
- `usage_limit`
- `remaining_usage`
- `account_status` when the account-aware enforcement layer supplies it

The entitlement layer is deterministic and testable without API, database,
frontend, Stripe, or recommendation dependencies. Route handlers and future
billing adapters should call this function instead of implementing local
feature checks.

Batch 3 adds `backend.monetization.resolver.resolve_account_entitlements()` and
`backend.monetization.enforcement.evaluate_account_access()` for account-aware
decisions. The resolver:

- defaults unknown and public users to `free`
- applies explicit internal plan assignments only when the assignment is
  effective and status is `active`, `trialing`, `test`, or `manual`
- falls back to `free` for expired, paused, canceled, or future-dated
  assignments
- returns included feature keys, usage limits, account type, account status,
  seat context, and safe metadata

All route-level paid workflow checks should flow through these helpers. Route
handlers must not inspect plan keys directly.

## Account Entitlement State

Batch 3 introduces provider-agnostic account state:

- `monetization_accounts`
- `monetization_plan_assignments`
- `monetization_usage_counters`

The account record stores internal account/license context:

- current app user link when applicable
- account type: individual, student, institutional, public demo, or internal
  test
- assigned seat count for institutional contexts
- safe metadata only

Plan assignments store:

- `plan_key`
- `plan_status`
- `assignment_source`
- `effective_at`
- optional `expires_at`
- optional `seat_limit`
- safe metadata only

Assignment sources are `manual`, `admin_seed`, `test_fixture`, and
`future_billing_provider`. This leaves room for Stripe or another provider to
update internal assignments later without making the provider the product
authority.

Safe metadata must not store payment-provider identifiers, checkout state,
private recommendation internals, recommendation preference details, or copied
market/recommendation payloads.

## Usage Counters

Usage counters are internal product counters, not billing-provider metering.
They track:

- account id
- feature key
- period start and end
- used count
- configured limit count
- reset policy
- last increment timestamp

They support limited comparisons, limited personalized discovery, full report
generation, exports, alerts, and watchlists as those workflow surfaces mature.
Access checks can include remaining usage, and exhausted limits return upgrade
targets through the central entitlement decision.

Usage increment rules:

- increment only after a request is allowed and the workflow succeeds
- do not increment on blocked entitlement decisions
- do not increment on validation errors or missing-object responses
- do not report counters to any billing provider
- keep counters keyed by feature and period, not private recommendation inputs

Batch 4 increments usage for authenticated limited comparisons, authenticated
limited personalized discovery, full report JSON stubs, and report export JSON
stubs. Anonymous public comparison/discovery remains available but is not yet
durably metered because there is no visitor/session account identity.

## Enforcement Boundary Map

Free workflows that remain allowed:

- basic region exploration: `GET /regions`, `GET /regions/{region_id}`,
  `GET /regions/search`, source explanations
- public demo markets and read-only market coverage displays
- anonymous/public comparisons through `GET /compare`; authenticated requests
  are metered against `limited_comparisons`
- anonymous/public personalized discovery through `POST /discover/personalized`;
  authenticated requests are metered against `limited_personalized_discovery`
- basic recommendation preview and strategy output through
  `POST /recommendations/strategy`
- report catalog/free preview metadata through `GET /monetization/reports`

Paid workflows enforced in Batch 4:

- saved watchlist creation: `POST /me/saved-market-artifacts` requires
  `saved_watchlists`
- alert feed actions: `GET /me/alerts`,
  `POST /me/alerts/{user_alert_id}/read`, and
  `POST /me/alerts/{user_alert_id}/dismiss` require `alerts`
- full report JSON stub:
  `POST /monetization/reports/{report_key}/generate` requires the report's
  configured full-report feature keys and increments `full_report_generation`
  after success
- export JSON stub:
  `POST /monetization/reports/{report_key}/export` requires and increments
  `exportable_strategy_plans` after success

Paid workflows documented as deferred because no route exists yet:

- saved comparison history as a distinct comparison-history product
- deeper company geography beyond the existing public company geography view
- full market coverage gating beyond public/demo catalog visibility
- institutional seat management, cohort templates, and aggregate program
  insights

Read/delete of existing saved artifacts remains available to the owning user so
account data is not trapped behind a plan boundary.

## Report Product Catalog

Batch 1 defines report product metadata only:

- personalized market strategy report
- region comparison report
- company geography report
- early-career opportunity report

Each report declares intended segments, free preview availability, paid
full-report feature requirements, included sections, and exportability. Full
report access maps to paid feature keys; previews map to free feature keys.

Real PDF generation and file export rendering are deferred until a clean
report/export abstraction exists. Batch 4 report/export routes return structured
JSON placeholders only and do not pretend that a file was generated.

## Read-Only API

The optional read-only API surface is registered because it matches the current
FastAPI pattern:

- `GET /monetization/plans`
- `GET /monetization/features`
- `GET /monetization/reports`
- `GET /monetization/access-preview`
- `GET /monetization/me`
- `GET /monetization/entitlements`
- `GET /monetization/usage`
- `POST /monetization/reports/{report_key}/generate`
- `POST /monetization/reports/{report_key}/export`

These endpoints serialize metadata and central entitlement decisions. They do
not require or reference a billing provider. Catalog endpoints remain public.
Account endpoints require the existing current-user auth dependency.
Report generate/export stubs are protected and return either structured
workflow payloads or a blocked entitlement decision.

`/monetization/access-preview` still supports explicit `plan_key` previews for
public UI education. When no `plan_key` is supplied and a current user is
available, it resolves the user's effective account entitlements.

## Billing Adapter API

Batch 5 adds a narrow billing API:

- `GET /billing/status`
- `POST /billing/checkout-session`
- `POST /billing/portal-session`
- `POST /billing/stripe/webhook`

`GET /billing/status` returns provider availability, checkout availability,
portal availability, and checkout-eligible internal plan keys. It never returns
Stripe secrets or price IDs.

Checkout is available only when Stripe is configured with a secret key,
success/cancel URLs, and a mapped paid individual/student plan. `free` can
never create checkout. Institutional licenses remain sales-assisted unless a
later batch explicitly designs institutional self-serve billing.

Creating a checkout session does not grant access. Paid access starts only
after a verified webhook updates an internal `monetization_plan_assignments`
row through the billing service.

The webhook endpoint verifies the `Stripe-Signature` header against
`STRIPE_WEBHOOK_SECRET`, normalizes relevant events, and records provider event
IDs for idempotency. It supports checkout completion, subscription
created/updated/deleted, and invoice payment events. Active/trialing
subscriptions grant internal assignments; canceled, expired, unpaid, paused,
or past-due states revoke or expire the provider-created assignment.

## Frontend Surface

Batch 2 adds `/markets/plans` in the frontend. Batch 4 makes it
account-aware. It renders:

- plan catalog metadata
- free vs paid feature boundary
- report product catalog
- access-preview decisions from the central backend entitlement endpoint using
  the current account when signed in
- effective plan, account status, included features, usage limits, and usage
  counters when authenticated
- light upgrade prompts on existing recommendation, comparison, market
  exploration, region, and company geography surfaces

Frontend prompts emphasize added workflow/report value: saving, alerts,
exports, deeper reports, broader maintained coverage, and institutional
workflows. They must not say or imply that the user's best market, the
recommendation truth, or the basic recommendation result is hidden behind a
payment boundary.

The frontend does not expose Stripe secrets or fake payment state. It calls the
backend checkout/portal endpoints only when billing status reports availability
and redirects only to the backend-returned provider URL. It still treats the
internal account entitlement endpoints as product access truth.

## Trust, Privacy, and Billing Constraints

Monetization must not compromise recommendation trust:

- billing state must not access private recommendation internals
- payment providers must be adapters, not product authority
- entitlements must not alter market recommendations
- paid workflow enforcement must not alter market recommendations
- recommendation ranking logic is not imported by monetization
- free users still receive useful exploration and the basic recommendation
  conclusion
- institutional insights must remain aggregate and privacy-preserving
- monetization account and usage state must not store private preference
  details or recommendation internals

## Stripe Adapter Boundary

Stripe is an adapter, not product authority. Stripe price IDs map to internal
plan keys, but product access flows only through the internal plan assignment,
resolver, entitlement, and enforcement layers. Product routes must not check
Stripe IDs or billing state directly.

Provider references live in `billing_customer_refs`,
`billing_subscription_refs`, and `billing_webhook_events`. Monetization account
state continues to avoid provider-specific IDs and recommendation internals.
Webhook metadata must remain limited to safe account/plan references and must
not contain private recommendation inputs or user preference details.

## Deferred Work

Later batches may add:

- admin tooling for institutional licenses
- report rendering/export generation
- seat assignment and organization membership enforcement
- privacy-preserving institutional analytics
- billing invoices, receipts, and renewal lifecycle views
- billing reconciliation jobs
- dunning/customer emails
- tax/VAT handling
- invoice customization

Those later layers should continue treating `backend/monetization` as product
authority for features, plans, and entitlement decisions.
