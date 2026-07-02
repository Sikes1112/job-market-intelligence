# Layer 22A Closeout - Institutional Decision Infrastructure Foundation

## Layer 22A Decision

LOCK_READY

Layer 22A implements the foundational institutional decision infrastructure
without creating a separate product or expanding Layer 22 ownership beyond
aggregate institutional decision payloads.

## Layer 22B Audit Decision

COMPLETE_WITH_NARROW_FIXES

The Layer 22B privacy and B2B lock-readiness audit found no architectural
redesign requirement, persistence need, scraping dependency, or individual-data
exposure. It did apply narrow fixes for institutional forecast labeling,
user-safe forecast reasoning display, suppression metadata consistency across
Layer 22 payloads, direct API permission regression coverage, and frontend
warning/limitation rendering.

## Implemented

- privacy-safe institutional decision dashboard
- curriculum-to-market mapping
- generated institutional workforce reports
- institutional market-opportunity benchmarking
- reusable server-side privacy metadata
- role-checked API endpoints
- frontend `/markets/institution/decisions` route
- backend and frontend tests

## Privacy Decision

Layer 22A is aggregate-first by design. Server responses include privacy
metadata and suppress cohort-derived detail below the minimum cohort threshold.

No Layer 22 payload exposes raw individual student searches, saved jobs,
applications, preferences, recommendation snapshots, identities, saved artifact
IDs, or private activity rows.

## Permission Decision

Layer 22A reuses existing institutional permissions:

- `VIEW_DASHBOARD` for decision dashboards, curriculum mapping, and benchmarks
- `VIEW_REPORTS` for generated workforce reports

Students, inactive memberships, and cross-organization users are denied
server-side. Audit events reuse existing enum values with Layer 22 target types.

## Boundary Decision

Layer 22 consumes aggregate dashboards, public/market-level company-region
signals, producer-owned Layer 21 exports, and API-safe contracts.

Layer 22 does not own:

- raw scraping
- employer authority
- geography authority
- recommendation authority
- public report authority
- institutional records
- individual student records
- persistence or scheduled storage
- external data fetching

## Validation

Validated behavior includes:

- decision dashboard sections for target markets, regional trends, program
  alignment, employer geography, internship access, industry demand, forecast
  notes, and recommended actions
- deterministic curriculum mapping with programs, role families, markets,
  skills, employer targets, recommendations, confidence, and warnings
- generated workforce reports with findings, actions, metrics, warnings,
  confidence, freshness, provenance, and privacy statement
- deterministic benchmark scores for emerging-region, employer-access,
  internship-access, and outdated-hub gaps
- small-cohort suppression and privacy metadata
- authorized role access and unauthorized role denial
- frontend rendering of decision, report, benchmark, confidence, source basis,
  historical depth, provenance, privacy, suppression states, warnings, and
  limitations

Layer 22B additionally validated:

- Layer 21 forecast notes remain labeled as forecasts on institutional surfaces
  and do not expose internal reasoning objects.
- suppression metadata stays consistent when low-sample dashboard detail is
  withheld and downstream mappings, reports, or benchmarks reuse that source
  dashboard.
- student-role and cross-organization direct API calls are denied across Layer
  22 endpoints.

## Deferred Non-Blocking Work

- real producer-owned curriculum ingestion
- persisted institutional decision/report snapshots
- scheduled refresh and distribution
- richer export packaging
- institution-specific predictive report packaging
- deeper benchmark comparison UX

These are intentionally out of scope for Layer 22A.

## Final Status

Layer 22 is lock-ready at the foundational institutional decision
infrastructure level after the Layer 22B narrow audit fixes.
