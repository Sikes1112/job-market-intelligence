# Layer 18 Closeout - Long-Term Platform / Data Moat Layer

## 1. Audit Decision

`COMPLETE_WITH_NARROW_FIXES`

Layer 18 satisfies the requested architecture after one narrow audit fix:
contribution evidence URL validation now rejects private, loopback, link-local,
reserved, multicast, and unspecified IP hosts, and public-demo tests explicitly
cover contribution review-queue denial.

## 2. Confidence Level

High.

The Layer 18 targeted suite, migration/schema checks, API protection tests,
public-demo tests, smoke imports, ruff, and `git diff --check` passed. The
broader backend suite has unrelated failures outside Layer 18, documented
below.

## 3. Files Inspected

- `backend/platform_intelligence/models.py`
- `backend/platform_intelligence/history_repository.py`
- `backend/platform_intelligence/schemas.py`
- `backend/platform_intelligence/snapshots.py`
- `backend/platform_intelligence/delta_detection.py`
- `backend/platform_intelligence/observations.py`
- `backend/platform_intelligence/predictive_signals.py`
- `backend/platform_intelligence/indices.py`
- `backend/platform_intelligence/reports.py`
- `backend/platform_intelligence/contributions.py`
- `backend/platform_intelligence/permissions.py`
- `backend/platform_intelligence/review_workflows.py`
- `backend/api/platform_intelligence.py`
- `backend/api/protection.py`
- `backend/api/app.py`
- `backend/shared/db.py`
- `alembic/versions/0020_historical_intelligence_foundation.py`
- `alembic/versions/0021_predictive_signals_market_indices.py`
- `alembic/versions/0022_benchmark_reports.py`
- `alembic/versions/0023_contribution_governance.py`
- `tests/test_platform_intelligence_history.py`
- `tests/test_platform_intelligence_signals_indices.py`
- `tests/test_platform_intelligence_reports.py`
- `tests/test_platform_intelligence_contributions.py`
- `tests/test_migrations.py`
- `tests/test_schema_completeness.py`
- `tests/test_smoke_imports.py`
- `tests/test_api_protection.py`
- `tests/test_api_read_layer.py`
- `tests/test_public_demo_environment.py`
- `docs/DATA_MODEL.md`
- `docs/API_SURFACES.md`
- `docs/LAYER_18_PLATFORM_INTELLIGENCE.md`
- `docs/PUBLIC_DEMO_ENVIRONMENT.md`

## 4. Files Changed During Audit

- `backend/platform_intelligence/schemas.py`
- `tests/test_platform_intelligence_contributions.py`
- `docs/LAYER_18_CLOSEOUT.md`

## 5. Layer 18A Historical Intelligence Findings

- `market_snapshots`, `company_region_snapshots`, `sector_region_snapshots`,
  `market_score_history`, and `historical_observations` are modeled as
  point-in-time Layer 18 records with `created_at` and no canonical
  `updated_at`, `state`, or `version` fields.
- Append-only ORM guards prevent update/delete of historical snapshot, score
  history, and observation rows.
- Snapshot creation writes new historical rows, creates market score history
  where applicable, and derives observations from adjacent snapshots only.
- Delta detection uses conservative thresholds: `0.05` for score changes and
  `2` for count changes.
- Snapshot and delta services do not mutate canonical region, company, sector,
  score, ranking, output, or recommendation records.
- History APIs return safe summaries with freshness, confidence, coverage, and
  warnings, while raw provenance/source internals remain internal.

## 6. Layer 18B Predictive Signal And Index Findings

- Predictive signals use required signal types and preserve evidence windows,
  snapshot counts, minimum-evidence flags, warnings, status, and expiry.
- Active signal generation requires at least 3 snapshots. Below-threshold
  evidence can create candidate rows but is not returned by the active signal
  API.
- Weak/moderate/strong signal strength rules are explicit at 3, 6, and 12
  snapshot evidence levels.
- Signal inputs reference source snapshots and historical observations.
- Expired, rejected, and superseded signals are excluded from active region
  summaries.
- Signal wording is conservative and does not claim certainty.
- The five required proprietary indices are registered:
  `early_career_tech_access`, `ai_opportunity_geography`,
  `internship_density`, `company_presence_quality`, and
  `hidden_market_opportunity`.
- Index versions, scores, and score inputs are preserved for auditability.
  Scores reference the version used at calculation time.
- Public index APIs expose methodology summaries and public-safe score context,
  not internal formula weights or input weights.
- Signal and index generation do not mutate canonical rankings, official
  scores, output metadata, or recommendations.

## 7. Layer 18C Benchmark Report Findings

- The four required report types are implemented:
  `best_cities_early_career_ai_roles`, `top_emerging_tech_markets`,
  `best_markets_product_careers`, and `best_regions_internship_access`.
- Report statuses are enforced: `draft`, `review_ready`, `published`,
  `archived`, and `superseded`.
- Reports can be generated as draft or review-ready. Publishing is explicit
  and only allowed from `review_ready`.
- Public APIs return only currently published reports. Draft, review-ready,
  archived, and superseded reports are not exposed as public current reports.
- Report generation uses Layer 18A snapshots/observations and Layer 18B
  indices/signals. It does not use unverified contribution data.
- Reports include methodology summaries, data windows, freshness notes,
  confidence notes, coverage notes, limitations, rankings, warnings, sections,
  and public-safe evidence summaries.
- Public report payloads omit internal formula weights, index input weights,
  source IDs, review notes, and admin-only metadata.
- Report generation does not mutate canonical rankings, official scores, index
  scores, predictive signals, recommendation outputs, or contribution data.

## 8. Layer 18D Contribution Governance Findings

- All required contribution types and statuses are enforced by schemas and
  database constraints.
- Contributions can attach evidence rows; review rows are append-only.
- Authenticated users can submit basic corrections, source suggestions,
  outdated-data reports, role-access feedback, market-quality feedback, and
  company-presence updates.
- Institution-scoped contribution types require active institution membership
  through the existing institution role helper.
- Review queue and review actions require existing admin/data-reviewer access.
- Review actions support verify, reject, merge, supersede, and needs-review
  lifecycle outcomes.
- Rejected contributions remain persisted for auditability.
- Submission and review responses are safe: public/user-facing payloads do not
  expose internal review notes, admin metadata, canonical candidate internals,
  or private review fields.
- Narrow audit fix: evidence URL validation now rejects private/local IP hosts
  and `.local`/localhost names in addition to non-http(s), embedded
  credentials, credential-like query keys, and filesystem-style references.
- Contributions and reviews do not mutate canonical rankings, official scores,
  index scores, predictive signals, benchmark reports, recommendation outputs,
  historical snapshots, public confidence scores, public warnings, or published
  outputs.
- Verified or merged reviews can record governed follow-up flags/refs only;
  they do not directly rewrite canonical or historical records.

## 9. Cross-Layer Authority Findings

- Layer 18 creates historical records, derived signals, derived index scores,
  benchmark reports, and governed intake workflows only.
- It does not become hidden canonical authority for rankings, scores,
  recommendations, output metadata, or public report contents.
- Existing provenance, freshness, confidence, coverage, refresh quality,
  admin-review, institution-permission, recommendation-explanation,
  public-demo, and integration/export boundaries remain intact.
- Model registration is explicit through `backend.shared.db.import_all_models`.
- No dependency on unrelated Layer 17 or frontend worktree changes was required
  for Layer 18 validation.

## 10. Public/Private Payload Findings

- `GET /platform/history/regions/{region_id}` and
  `GET /platform/history/companies/{company_id}` omit raw provenance/source
  internals.
- `GET /platform/signals/regions/{region_id}` omits signal input internals and
  returns active, unexpired signals only.
- `GET /platform/indices` and `GET /platform/indices/{index_key}/scores` omit
  internal formula weights and input weights.
- `GET /platform/reports` and `GET /platform/reports/{report_key}` return only
  published public-safe summaries/details and strip source IDs, internal input
  weights, review notes, and admin metadata.
- `POST /platform/contributions` returns only safe submission status and next
  steps.
- `GET /platform/contributions/review` and
  `POST /platform/contributions/{contribution_id}/review` are permissioned
  review/admin surfaces.

## 11. Public-Demo Findings

- Public-demo allowlist includes safe Layer 18 GET routes for history,
  signals, indices, and reports.
- Public-demo denies contribution submission, contribution review queue access,
  and contribution review writes.
- Public-demo does not expose Layer 18 mutation paths for reports, signals,
  indices, history, or contributions.
- Public-demo posture remains fail-closed for unknown/non-allowlisted routes.

## 12. Migration/Schema Findings

- Migrations are ordered:
  `0020_historical_intelligence_foundation` ->
  `0021_predictive_signals_market_indices` ->
  `0022_benchmark_reports` ->
  `0023_contribution_governance`.
- Migration tests confirm Alembic head creates the same schema as registered
  SQLAlchemy metadata and stamps existing create-all schemas at
  `0023_contribution_governance`.
- Schema completeness tests cover all Layer 18 tables and required columns.
- There were no Layer 18 migration conflicts observed.

## 13. Validation Results

- Targeted Layer 18/API/schema/public-demo validation:
  `315 passed in 9.20s`.
- Ruff:
  `python3 -m ruff check ...` passed for Layer 18 modules, API/protection
  files, migrations, and targeted tests.
- `git diff --check`: passed.
- Broader backend suite:
  `1936 passed, 7 failed in 58.19s`.
  The failures were outside Layer 18:
  - five date-sensitive freshness expectations in `tests/test_api_search.py`
  - one Layer 11 isolation assertion for `backend/outputs/payloads.py`
  - one monetization usage assertion in
    `tests/test_monetization_effective_entitlements.py`

## 14. Deferred Production Items

- Production seeding/backfill of historical snapshots.
- Operational schedule for snapshot capture and index/report refresh jobs.
- Admin UI for contribution review, report review, and governed follow-up task
  handling.
- Future Layer 18 extensions may add benchmark distribution and contribution
  ingestion integrations, but those should continue to respect canonical
  authority and public/private payload boundaries.

## 15. Final Lock Recommendation

Layer 18 is complete with narrow fixes applied and is ready to lock from a
Layer 18 safety and architecture standpoint. Canonical rankings remain
protected from historical records, derived intelligence, benchmark reports,
and external submissions.
