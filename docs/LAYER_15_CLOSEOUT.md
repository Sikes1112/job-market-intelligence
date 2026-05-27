# Layer 15 Closeout: Business Model and Monetization Layer

Date: 2026-05-27

## Final Decision

LOCK_READY_AFTER_NARROW_FIX

Confidence: High

## Purpose

Layer 15 defines the business model and monetization foundation for the
product. It establishes free and paid feature boundaries, account entitlements,
usage limits, paid workflow enforcement, and Stripe as a narrow billing adapter
without allowing monetization to affect recommendation trust.

## Batch Summary

### Batch 1: Monetization Domain and Catalog

- Added audience and buyer segmentation.
- Added canonical feature boundaries.
- Added subscription plan metadata.
- Added centralized pure entitlement decisions.
- Added report product catalog metadata.
- Added read-only monetization catalog APIs.

### Batch 2: Frontend Monetization UX

- Added `/markets/plans`.
- Added plan catalog UI.
- Added free/paid feature boundary UI.
- Added report product catalog UI.
- Added access-preview UI.
- Added trust-safe upgrade prompts.

### Batch 3: Account Entitlement State and Usage Limits

- Added provider-agnostic monetization accounts.
- Added internal plan assignments.
- Added usage counters.
- Added account-aware entitlement resolver.
- Added centralized enforcement helpers.
- Added `/monetization/me`, `/monetization/entitlements`, and
  `/monetization/usage`.

### Batch 4: Paid Workflow Enforcement and Account-Aware UX

- Enforced `saved_watchlists` for saved market artifact creation.
- Enforced `alerts` for alert workflows.
- Checked and incremented `limited_comparisons` for authenticated comparison
  requests.
- Checked and incremented `limited_personalized_discovery` for authenticated
  personalized discovery requests.
- Added JSON-only report generation and export stubs behind report/export
  entitlements.
- Made `/markets/plans` account-aware.

### Batch 5: Stripe Adapter, Checkout, and Billing Portal

- Added provider-neutral billing contracts.
- Added Stripe checkout session creation.
- Added Stripe billing portal session creation.
- Added Stripe webhook signature verification.
- Added Stripe event normalization.
- Added isolated provider reference tables.
- Updated internal plan assignment state from verified webhook events.
- Added billing status endpoint.
- Wired frontend checkout and portal actions through backend endpoints.

### Final Audit: Webhook Authority Fix

The final audit decision was `COMPLETE_WITH_NARROW_FIXES`. A verified
`checkout.session.completed` webhook could previously derive the internal plan
from Stripe metadata without re-checking backend checkout eligibility. This
was fixed so checkout metadata is ignored unless the internal plan is
configured as checkout-eligible. Regression coverage was added.

## Final Architecture

The locked authority path is:

```text
Stripe/payment provider
  -> billing adapter
  -> internal plan assignment
  -> entitlement resolver
  -> centralized enforcement
  -> product routes
```

Stripe price IDs, metadata, checkout sessions, and frontend callbacks must
never directly grant product access.

## Trust and Privacy Protections

- Free users keep useful basic exploration and recommendation preview.
- Paid features are tied to workflow and report value.
- Recommendation ranking is not affected by monetization.
- Billing state does not store recommendation internals.
- Secrets and provider refs are not exposed to the frontend.
- Public demo remains read-only for billing and monetization status.

## Final Validation Status

- `ruff check backend tests alembic`: passed
- `pytest tests/test_billing_stripe_adapter.py`: 10 passed
- Monetization, billing, API, schema, migration, public-demo, and smoke suite:
  350 passed
- Recommendation regression suite: 70 passed
- `cd frontend && npm run test`: 7 files passed, 36 tests passed
- `cd frontend && npm run lint`: passed
- `cd frontend && npm run build`: passed
- `git diff --check`: passed

## Deferred Acceptable Items

- Real PDF/file exports
- Institutional self-serve billing
- Institutional admin analytics
- Billing reconciliation jobs
- Dunning/customer emails
- Tax/VAT handling
- Invoice customization
- Deeper productized company geography gating

## Final Recommendation

Layer 15 is locked. Future work should not reopen Layer 15 core architecture
unless changing billing providers, entitlement authority, or monetization
policy.
