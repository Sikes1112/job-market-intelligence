# Layer 24 - Policy, Workforce, and Economic Intelligence

Layer 24 expands the product from individual career guidance into regional labor-market
infrastructure. It is an interpretation layer over existing opportunity, region,
company, hiring, entry-level, scoring, freshness, confidence, institutional, public
payload, and partner-governance signals. It must not create a disconnected policy
analytics data universe.

## Batch 24A Scope

Batch 24A implements the backend policy intelligence core only.

Implemented:

- Read-only regional policy profile generation.
- Regional workforce dashboard backend payloads.
- Deterministic policy metrics for:
  - opportunity concentration
  - early-career access
  - internship pipeline strength
  - employer dependency
  - sector diversity
  - talent export risk
- Evidence-informed policy findings.
- Freshness, confidence, warning, source-summary, and public-safety metadata.
- Public-safe API endpoints for policy dashboard reads.
- Tests for determinism, low-data behavior, normalization, policy language, API payload
  metadata, private-field redaction, and mutation safety.

Not implemented in 24A:

- Frontend surfaces.
- Public report pages.
- Education-to-workforce alignment.
- Company attraction strategy.
- Peer metro comparison.
- Economic-development strategy recommendations.
- Final false-integration closeout audit.

## Backend Modules Added

- `backend/policy/schemas.py` defines public-safe DTOs for policy metrics, findings,
  warnings, freshness, confidence, source summaries, public-safety metadata, regional
  profiles, workforce dashboard payloads, and 24B strategy payloads.
- `backend/policy/metrics.py` contains shared deterministic helpers over canonical
  region, company, presence, hiring, entry-level, and region-score rows.
- `backend/policy/regional_inequality.py` computes bounded 0-to-1 policy metrics.
- `backend/policy/confidence.py` computes conservative confidence metadata.
- `backend/policy/warnings.py` generates visible low-data, normalization, freshness,
  provenance, and public-interpretation warnings.
- `backend/policy/service.py` loads existing canonical records and assembles Layer 24A
  outputs without persistence or mutation.
- `backend/policy/workforce_dashboard.py` provides dashboard assembly helpers.
- `backend/policy/sector_gaps.py` detects structured sector gaps from employer demand,
  early-career, internship, and peer-demand signals.
- `backend/policy/peer_metros.py` selects deterministic peer comparisons from available
  Layer 24A metrics and emits limitations when coverage is thin.
- `backend/policy/company_attraction.py` builds company attraction fit candidates as
  strategy-analysis inputs, not expansion predictions or subsidy recommendations.
- `backend/policy/economic_development.py` assembles regional strategy intelligence from
  24A metrics, sector gaps, employer-base risk, peers, and company-fit candidates.
- `backend/policy/institution_mapping.py` maps public-safe institution organization
  records to aggregate regional demand context.
- `backend/policy/education_alignment.py` builds aggregate education-to-workforce
  alignment profiles from program-area mappings and regional employer-demand signals.
- `backend/api/policy.py` exposes read-only policy endpoints.

## API Endpoints Added

- `GET /policy/regions/{region_id}/workforce-dashboard`
- `GET /policy/regions/{region_id}/early-career-access`
- `GET /policy/regions/{region_id}/employer-concentration`
- `GET /policy/regions/{region_id}/economic-development`
- `GET /policy/regions/{region_id}/peer-comparison`
- `GET /policy/regions/{region_id}/education-alignment`

The routes follow the existing FastAPI router and response-envelope pattern. They are
thin readers over `PolicyIntelligenceService`.

## Batch 24B Scope

Batch 24B extends the 24A backend from policy diagnostics into regional strategy
intelligence. It remains backend-only and read-only.

Implemented:

- Economic development profiles with a 24A policy-profile reference, sector-gap
  findings, employer-base risk findings, peer comparisons, company attraction fit
  candidates, diversification strategy candidates, warnings, confidence, freshness,
  source summaries, limitations, and public-safety metadata.
- Sector gap detection for internship pathway gaps, early-career access gaps,
  full-time early-career demand without internship/co-op pathways, narrow sector mix,
  and peer-relative sector gaps.
- Employer-base risk interpretation over 24A concentration, dependency, sector
  diversity, internship, and early-career metrics.
- Peer metro comparison using deterministic similarity across available Layer 24A
  metrics, with low-coverage warnings when the peer set is limited.
- Company attraction fit candidates for companies visible in other tracked regions and
  directionally aligned with identified sector gaps.
- Aggregate-only education-to-workforce alignment using public-safe institution
  organization records, program-area mappings, sector demand snapshots, internship
  alignment gaps, local employer absorption, talent export pressure, and explicit
  student-interest limitations.

Not implemented in 24B:

- Frontend surfaces.
- Public report pages.
- Political, causal, tax-incentive, or prescriptive policy recommendations.
- Individual student outcomes or student-level education alignment.
- Live external data calls or new ingestion pipelines.

## Batch 24C Scope

Batch 24C exposes Layer 24 through product UI surfaces and one representative
backend-generated public report surface. It does not perform the final Layer 24
integration audit.

Implemented:

- Policy/workforce intelligence product landing route.
- Regional policy dashboard UI that consumes the 24A workforce dashboard endpoint.
- Economic development dashboard UI that consumes the 24B economic-development endpoint.
- Education-to-workforce alignment dashboard UI that consumes the 24B education
  alignment endpoint.
- Peer metro comparison UI that consumes the 24B peer comparison endpoint.
- Frontend API methods and TypeScript types for Layer 24 payloads.
- Representative Layer 24 report endpoint and UI route for `The Geography of
  Early-Career Tech Opportunity`.
- Frontend states for loading, errors, missing regions, empty findings, empty peers,
  empty company candidates, and empty education alignment sections.

Not implemented in 24C:

- Full public report registry expansion for every recommended Layer 24 report template.
- Public marketing/report pages outside the product shell.
- New report scoring, ranking, or frontend-authored metric interpretations.
- 24D final false-integration audit.

## 24C Routes Added

Frontend routes:

- `/markets/policy`
- `/markets/policy/regions/{region_id}/workforce`
- `/markets/policy/regions/{region_id}/economic-development`
- `/markets/policy/regions/{region_id}/education-alignment`
- `/markets/policy/regions/{region_id}/peer-comparison`
- `/markets/policy/reports/{region_id}/early-career-opportunity`

Backend report route:

- `GET /policy/regions/{region_id}/reports/early-career-opportunity`

The existing 24A and 24B API routes remain the source of dashboard data.

## 24C Surfaces Added

The frontend adds a dedicated `PolicyIntelligencePage` component. It reads Layer 24
payloads via `frontend/src/api.ts` and renders backend-provided metrics, findings,
warnings, limitations, confidence, freshness, source summaries, and public-safe
metadata.

Visible surfaces include:

- workforce dashboard metric cards
- policy finding cards
- economic development sector-gap panels
- employer-base risk panels
- company attraction fit cards labeled as strategy-analysis candidates
- diversification candidate panels
- peer metro comparison tables
- education alignment metric cards
- aggregate institution pipeline summaries
- program alignment cards
- internship alignment gap panels
- representative policy report detail

The landing page contains static explanatory copy for intended public-sector and
institutional users, but it does not render fake metrics.

## API Payloads Consumed

24C consumes:

- `WorkforceDashboardPayload`
- `EconomicDevelopmentProfile`
- `PeerComparisonProfile`
- `EducationWorkforceAlignmentProfile`
- `PublicReportPayload` for the representative Layer 24 report

Frontend types mirror the backend DTO shape closely enough for rendering and tests:
policy metrics, findings, warnings, confidence, freshness, source summaries, sector
gaps, employer-base risks, peer comparisons, company attraction fits, institution
pipelines, program alignments, and limitations.

## 24C Public Report Behavior

24C adds one representative real Layer 24 report:

- `The Geography of Early-Career Tech Opportunity`

The report is generated from the backend workforce dashboard payload for the requested
region. It reuses existing `backend/public_reports` schema contracts and therefore
includes title, summary, region scope, methodology, findings, warnings, limitations,
freshness, confidence, source provenance, citation, share summary, and public authority
metadata.

Deferred templates:

- `Where AI Jobs Are Actually Concentrating`
- `The Internship Access Gap`
- `Talent-Producing Regions vs Opportunity-Producing Regions`
- `Employer Concentration and Regional Risk`
- `The Education-to-Workforce Alignment Index`

These remain deferred because adding them without real backend payload assembly would
create placeholder report logic.

## 24C UI Guardrails

Methodology, warnings, confidence, freshness, and limitations are visible on policy
surfaces. Low peer coverage warnings are rendered instead of hidden. Empty states are
explicit and do not suppress warnings or limitations when the backend returns them.

Company attraction display rule:

- Companies are labeled as `strategy-analysis candidates`.
- The UI does not describe candidates as expansion predictions or subsidy targets.

Education display rule:

- Education alignment is shown as aggregate regional/program-level intelligence.
- The UI states that no individual student outcomes are inferred.
- The UI states that short-term postings alone do not determine program value.

Public payload safety:

- Public-safe metadata is surfaced where relevant.
- Private Layer 23 review/submission fields, private institution internals, and
  student-level fields are not displayed.

## 24B Economic Development Profile Behavior

`EconomicDevelopmentProfile` is assembled downstream of `RegionalPolicyProfile`.
The profile carries the same analysis window, freshness metadata, source summary, and
public-safety metadata as the 24A profile, then adds strategy interpretation.

The output is deterministic for the same database state and `now` value. It never writes
to opportunity, company, institution, or partner-submission records.

Economic development profile limitations are explicit:

- Strategy outputs are not prescriptions.
- Company attraction fits are not expansion predictions.
- Local validation is required before public strategy decisions.

## Sector Gap Methodology

Sector snapshots are built from canonical present companies, company-region hiring
signals, and company-region entry-level records. Sectors are compared with bounded
scores for demand, internship pipeline strength, and early-career access.

Detected gap types include:

- `internship_pathway_gap` when employer demand is visible but internship/co-op
  evidence is weak.
- `early_career_access_gap` when demand is stronger than entry-level access.
- `full_time_without_internship_pathway` when full-time entry-level demand is visible
  without internship/co-op pathway evidence.
- `narrow_sector_mix` when 24A sector diversity is low.
- `peer_relative_sector_gap` when peer-region demand is stronger than the target
  region's available demand signal.

Findings use bounded language such as "available signals suggest", "appears
underdeveloped relative to available signals", and "could be a candidate for further
local validation."

## Peer Metro Comparison Methodology

Peers are selected from canonical regions that have comparable 24A policy profiles.
Similarity is computed over available 24A metrics:

- opportunity concentration
- early-career access
- internship pipeline
- employer dependency
- sector diversity
- talent export risk

Comparisons explain why a peer was selected, list the metrics compared, and identify
where the target is stronger or weaker. If too few comparable regions exist, the payload
emits a `low_peer_comparison_coverage` warning and a limitation stating that the peer set
is limited.

Known peer-comparison limits:

- Population, wages, commuting patterns, and complete industry inventories are not
  modeled in 24B.
- Similarity is a product-signal comparison, not a comprehensive economic benchmark.

## Company Attraction Fit Guardrails

Company attraction fits are candidates for regional analysis only. They are generated
when a public-safe company is not already present in the target region, is present in
other tracked regions, and aligns with an identified sector gap.

Allowed interpretation:

- The company appears directionally aligned with a sector gap.
- The employer type may be useful for diversification analysis.
- Further local validation is required.

Disallowed interpretation:

- Incentive recommendations.
- Expansion predictions.
- Claims that a company will solve a workforce gap.

## Education-To-Workforce Alignment Methodology

`EducationWorkforceAlignmentProfile` maps aggregate institution and program-area signals
to regional employer demand and opportunity gaps. It includes:

- public-safe institution pipeline summaries
- program demand alignment findings
- internship alignment gaps
- local employer absorption score
- talent export pressure score
- student interest market fit marked unknown when public-safe aggregate interest
  signals are not available
- warnings, confidence, freshness, source summary, limitations, and public-safety
  metadata

Program alignments use existing program-area definitions from institutional decision
infrastructure and compare them with regional sector demand snapshots. They are market
alignment signals, not program-quality ratings.

## Aggregate-Only Education Safety Rule

Education alignment is aggregate-only. It does not expose or infer:

- student identities
- student-level outcomes
- private student preferences
- individual placement probabilities
- private institution report payloads
- institutional audit-log internals

When student-interest-market-fit data is unavailable on a public-safe aggregate basis,
the metric is returned as `unknown` with explicit limitations rather than inferred.

## Scoring Philosophy

Layer 24A scores are deterministic, bounded, and explanatory. They are not causal
claims and are not precise economic measurements.

Normalization rules:

- Employer concentration uses employer hiring shares and normalized HHI rather than raw
  regional posting totals.
- Early-career access and internship pipeline scores normalize by demonstrated present
  employers where that denominator exists.
- Sector diversity uses normalized entropy over primary sector labels.
- Talent export risk is a proxy assembled from pathway weakness, sector diversity, and
  employer dependency. It is capped by interpretive confidence.

Missing data is not treated as zero. Low-data and missing-denominator cases emit
warnings and lower confidence.

## Policy Language Guardrails

Findings use bounded language such as:

- "Available data suggests..."
- "This region shows signs of..."
- "This may indicate..."
- "Further local validation is recommended."

Findings must not claim that policy caused an outcome, describe a city as failing,
recommend tax incentives, or promise definite future outcomes.

These guardrails apply to 24B strategy payloads as well as 24A diagnostics.

## Privacy And Public Payload Guardrails

Layer 24A and 24B do not expose:

- private review notes
- reviewer identities
- raw partner-submission internals
- submitter contacts
- raw source references
- source version bundles
- private institution fields
- student-level or individual-level data
- unpublished internal records

Layer 24A and 24B do not query Layer 23 submission/review internals for policy scoring
or strategy interpretation. When partner-submitted opportunity records exist in the same
database, policy outputs remain aggregate and public-safe.

## Tests Added

- `tests/test_policy_regional_inequality.py`
- `tests/test_policy_workforce_dashboards.py`
- `tests/test_policy_payload_safety.py`
- `tests/test_policy_economic_development.py`
- `tests/test_policy_peer_metros.py`
- `tests/test_policy_education_alignment.py`
- `tests/test_policy_strategy_payload_safety.py`
- `tests/test_policy_public_reports.py`
- `frontend/src/policyRoutes.test.tsx`

Coverage includes:

- deterministic regional policy profiles
- stable repeated metric outputs
- low-data warnings and reduced confidence
- mitigation of raw big-city count bias through normalization
- finding generation from structured metrics
- policy-language guardrails
- dashboard API metadata requirements
- Layer 23 private field non-leakage
- public payload forbidden-field checks
- no mutation of opportunity or partner-submission records
- deterministic economic development profiles
- sector gaps generated from structured evidence
- employer-base risk tied back to 24A metrics
- explainable peer metro comparisons
- low-data peer warning and limitation behavior
- company attraction candidates framed as analysis candidates, not guarantees
- aggregate-only education-to-workforce alignment
- student-level inference prevention
- 24B API metadata and limitations coverage
- no mutation of company, institution, opportunity, or submission records by 24B reads
- Layer 24 frontend route rendering
- dashboard rendering from API-backed Layer 24 payloads
- economic development candidate framing as strategy-analysis candidates
- aggregate-only education alignment UI notice
- peer warning and limitation rendering
- representative policy report rendering from backend report payload
- frontend API methods for Layer 24 policy endpoints
- public report payload generation from backend workforce dashboard data
- public report private-field and unsafe-language non-leakage

## Known Limitations

- Layer 24A uses currently available canonical records. It does not collect new sources
  or infer missing denominators.
- Talent export risk is a proxy, not observed migration or graduate-retention data.
- Sector diversity depends on existing company sector labels.
- Source summaries report categories and counts, not public citations.
- Confidence is intentionally conservative for interpretive policy outputs.
- 24B peer comparisons do not model population, wages, commuting patterns, full
  industry inventories, or fiscal policy.
- Institution pipeline summaries use available organization records and aggregate
  demand context. Institution-specific program catalogs are not connected in this
  batch.
- Company attraction fits depend on companies already represented in tracked regions.
  They are not an external prospecting database.
- 24C adds one representative Layer 24 public report. Additional report templates are
  intentionally deferred until each can be backed by real Layer 24 backend assembly.
- Policy UI routes live under the existing product shell at `/markets/policy...` rather
  than replacing the existing public `/reports` registry.

## Closeout Status

24C - Public and Institutional Surfaces:

- implemented

24D - Integration, Safety, and False-Integration Closeout Audit:

- completed on 2026-06-28
- public-contract audit completed
- privacy and redaction audit completed
- false-integration checks completed
- final Layer 24 readiness determination recorded in `docs/LAYER_24_CLOSEOUT.md`

Batch 24A, Batch 24B, Batch 24C, and Batch 24D are complete. Layer 24 is ready for
lock under the closeout decision recorded in `docs/LAYER_24_CLOSEOUT.md`.
