# Layer 22 - Institutional Decision Infrastructure

Layer 22 extends the existing institutional product so universities, career
centers, bootcamps, workforce boards, economic development agencies,
foundations, policy researchers, and chambers of commerce can make
privacy-safe workforce, advising, curriculum, employer, and regional strategy
decisions.

Layer 22A is a foundational implementation. It does not create a separate
institutional product and does not add persistence, scraping, external data
fetching, migrations, or nondeterministic model calls.

## Users

Implemented institutional surfaces support:

- career services and advisors
- program directors and curriculum committees
- employer partnership teams
- workforce and economic development planners
- institutional report viewers
- policy and foundation users who need aggregate market intelligence

## Architecture

Layer 22A extends the existing Layer 16 institutional architecture:

- `backend/institutions/privacy.py` defines reusable server-side privacy
  metadata.
- `backend/institutions/decision_infrastructure.py` builds generated
  institutional decision payloads.
- `backend/institutions/service.py` exposes permission-checked service methods.
- `backend/api/institutions.py` exposes new organization-scoped endpoints.
- `frontend/src/App.tsx`, `frontend/src/api.ts`, `frontend/src/types.ts`, and
  `frontend/src/urlState.ts` expose the institutional decisions route.

Layer 22 consumes:

- Layer 16 aggregate institutional dashboards
- public/market-level company-region hiring, entry-level, and presence signals
- Layer 21 producer-owned predictive exports when historical forecast evidence
  exists
- neutral API-safe payload contracts

Layer 22 does not own raw scraping, employer authority, geography authority,
recommendation authority, public report authority, institutional records,
student records, or persistence/storage authority.

## API Surfaces

New organization-scoped endpoints:

- `GET /api/institutions/organizations/{organization_id}/decision-dashboard`
- `GET /api/institutions/organizations/{organization_id}/curriculum-market-map`
- `GET /api/institutions/organizations/{organization_id}/workforce-reports/{report_type}`
- `GET /api/institutions/organizations/{organization_id}/benchmarks`

Supported generated workforce report types:

- `regional_workforce_opportunity`
- `early_career_market_access`
- `tech_sector_growth`
- `student_placement_strategy`
- `employer_geography`
- `program_alignment`

These endpoints are generated on demand and reuse existing institutional
authorization. They do not write report rows or create new database authority.

## Frontend Surface

The frontend adds `/markets/institution/decisions`.

The route renders:

- an institutional decision dashboard
- privacy-safe aggregation notice
- suppressed-data state
- target-market, regional-trend, program-alignment, employer-geography,
  internship-access, and industry-demand sections
- forecast notes when Layer 21 evidence exists
- curriculum-to-market mapping
- workforce report summary
- institutional benchmark scores and gaps
- warnings and limitations for dashboard, curriculum, workforce report, and
  benchmark payloads

The UI expects aggregate and market-level fields only. It does not require
student-level search, application, preference, saved-job, or identity fields.

## Privacy-Safe Aggregation

Layer 22A enforces privacy server-side. Every Layer 22 payload includes:

- `aggregation_level`
- `privacy_mode`
- `minimum_cohort_size`
- `cohort_size`
- `suppression_applied`
- `suppressed_fields`
- `privacy_notes`
- `student_level_data_exposed: false`

The minimum cohort threshold comes from the existing institutional dashboard
minimum group rules. If the cohort is too small, cohort-derived insights are
suppressed before the API response is built. Public market-level context may
still appear, but it is not treated as individual student behavior.

Layer 22 payloads do not expose raw individual student searches, saved jobs,
applications, preferences, recommendations, identities, saved artifact IDs,
recommendation snapshot IDs, or private activity rows.

## Permission Model

Layer 22A reuses existing institutional roles and actions:

- decision dashboard, curriculum mapping, and benchmarks use
  `VIEW_DASHBOARD`
- generated workforce reports use `VIEW_REPORTS`

Authorized organization surface roles can view dashboard-style decision
infrastructure. Report viewers can view generated workforce reports.
Students, inactive memberships, and cross-organization users are denied
server-side.

Audit events reuse existing institutional audit action values with Layer 22
target types to avoid changing database check constraints.

## Dashboard Model

The decision dashboard answers:

- what is happening
- why it matters
- what the institution should consider doing

Sections include:

- summary
- target markets
- regional trends
- program alignment
- employer geography
- internship access
- industry demand
- forecast notes
- recommended actions
- confidence, freshness, and provenance
- privacy metadata
- limitations and warnings

Each major metric is tied to advising, curriculum, employer partnership, or
workforce decisions.

## Curriculum-To-Market Mapping

Layer 22A implements deterministic sample program structures until
producer-owned curriculum ingestion exists.

Mappings include:

- program name
- relevant role families
- strongest aligned markets
- emerging markets
- weak or saturated markets
- skills with rising demand
- employer relationship targets
- advising recommendations
- confidence, freshness, and provenance
- sparse-data warnings
- privacy metadata

The mapper is not a generic keyword matcher. It uses structured program
definitions and observed role-family, sector, employer, and market signals.

## Workforce Reports

Generated workforce reports include:

- title
- report type
- audience
- scope
- summary
- key findings
- recommended actions
- supporting metrics
- confidence, freshness, and provenance
- privacy statement and metadata
- limitations and warnings
- export-ready structure metadata

These reports are decision-ready JSON structures. Persistence and scheduled
distribution remain deferred.

## Benchmarking

Institutional benchmarks compare aggregate institutional focus against observed
market opportunity.

Benchmark outputs include:

- benchmark subject
- comparison market set
- opportunity score
- alignment score
- gap score
- emerging-region gap
- employer-access gap
- internship-access gap
- recommendation summary
- supporting rationale
- warnings for low sample sizes or forecast-based interpretation

Scores are deterministic and transparent. They are directional decision inputs,
not opaque model outputs.

## Layer Dependencies

Layer 22 builds on:

- Layer 16 institutional organizations, memberships, dashboards, permissions,
  reports, and audit patterns
- Layer 19 public reports and benchmarks as architecture precedent, without
  taking over public-report authority
- Layer 20 platform/API-safe payload conventions
- Layer 21 bounded forecast contracts and producer-owned predictive exports

Forecast notes remain labeled as bounded forecast signals. They are not
guarantees.

## Layer 22B Audit Addendum

The Layer 22B privacy and B2B lock-readiness audit found narrow issues and
fixed them without expanding scope:

- Layer 21 forecast notes used by Layer 22 are now forced to carry a forecast
  label on the institutional surface and serialize only user-safe reasoning
  summaries.
- Privacy metadata now reflects suppressed low-sample dashboard fields across
  dashboards, curriculum mappings, workforce reports, and benchmarks.
- Cross-organization endpoint denial and direct student-role denial are covered
  across Layer 22 decision surfaces.
- The frontend now renders Layer 22 warnings and limitations instead of relying
  on payload presence alone.

After these fixes, the Layer 22B audit considers Layer 22 foundationally
lock-ready for privacy-safe institutional decision infrastructure.

## Known Limitations

- Curriculum ingestion is represented by deterministic sample program
  structures.
- Workforce reports are generated on demand and are not persisted.
- Scheduled refresh, distribution, and richer export packaging are deferred.
- Forecast notes appear only when Layer 21 historical exports exist.
- Benchmark scores are deterministic directional comparisons and should be
  reviewed with local institutional context.

## Test Coverage

Layer 22A adds backend tests for:

- decision dashboard payload shape
- absence of individual student records
- deterministic curriculum mapping
- complete workforce report payloads
- benchmark gap detection
- small-cohort suppression
- server-side role enforcement

Frontend tests cover:

- `/markets/institution/decisions`
- dashboard/report/benchmark/card rendering
- privacy-safe aggregation notice
- suppressed-data state
- confidence, source basis, historical depth, and provenance display
- warning and limitation display across Layer 22 decision surfaces

## Status

Layer 22A is complete at the foundational level and ready for lock after the
targeted and adjacent test suites pass.
