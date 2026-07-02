# Layer 27 Data Consortium / Standards Layer

Layer 27 defines standards metadata and bounded partner data intake. It does not
replace canonical market intelligence domains and does not merge external
submissions into company, region, hiring, opportunity, recommendation,
predictive, policy, career-agent, or market-score tables.

## Batch 27A Scope

Batch 27A added:

- Standard definitions for entry-level role, internship, co-op, early-career
  program, company-region presence, hiring activity, and market opportunity
  score.
- A partner submission schema for companies, regions, early-career programs,
  hiring signals, and company-region presence.
- Deterministic submission validation with structured errors.
- A bounded partner submission table:
  `data_standard_partner_submissions`.
- API routes for serving definitions, serving the partner schema, validating a
  submission, and creating a validated submission record.

## Batch 27B Scope

Batch 27B added:

- A deterministic verified partner registry served through the Layer 27 service
  and API.
- Partner type, verification status, and trust-tier vocabularies.
- Data quality certification labels served through the Layer 27 service and API.
- Conservative label-evaluation logic that uses partner verification, source
  refs, confidence, freshness, and label requirements.
- Tests proving partner verification and data certification remain separate and
  do not mutate canonical intelligence tables.

## Batch 27C Scope

Batch 27C added:

- Governance framework metadata for data ethics, labor-market fairness, source
  standards, institutional use, and bias review.
- A read-only governance framework API route.
- A public/institutional standards page at `/data-standards`.
- Frontend API client functions and types for Layer 27 definitions, partner
  schema, partner registry, quality labels, and governance framework records.
- Tests proving the frontend standards surface is connected to the Layer 27 API
  path and does not present verification, validation, certification, governance,
  or canonical acceptance as the same concept.

## Standards Contract

Each standard definition includes:

- `term`
- `canonical_name`
- `description`
- `inclusion_criteria`
- `exclusion_criteria`
- `examples`
- `related_terms`
- `version`
- `status`

Definitions are standards metadata only. They are not canonical company, region,
hiring, opportunity, recommendation, predictive, policy, career-agent, or
market-score records.

## Partner Submission Contract

Partner submissions use schema version `partner_submission_v1` and include:

- `submission_id`
- `partner_id`
- `submitted_at`
- `schema_version`
- `submitter_type`
- `records`
- `source_refs`
- `freshness`
- `confidence`
- `warnings`
- `validation_status`

Supported record types:

- `company`
- `region`
- `early_career_program`
- `hiring_signal`
- `company_region_presence`

Supported validation statuses:

- `received`
- `validated`
- `rejected`
- `needs_review`
- `certified`
- `archived`

## Verified Partner Network

Supported partner types:

- `university`
- `workforce_board`
- `bootcamp`
- `regional_economic_group`
- `career_platform`
- `employer`
- `research_group`
- `public_agency`

Supported verification statuses:

- `unverified`
- `pending_review`
- `verified`
- `suspended`
- `revoked`

Supported trust tiers:

- `tier_1_verified_institutional`
- `tier_2_verified_regional`
- `tier_3_verified_platform`
- `tier_4_limited_partner`
- `untrusted`

Each partner registry record includes:

- `partner_id`
- `name`
- `partner_type`
- `region_scope`
- `verification_status`
- `allowed_submission_types`
- `trust_tier`
- `public_contact_metadata`
- `created_at`
- `updated_at`

Partner contact metadata is public-safe only. Layer 27 partner registry payloads
must not expose private reviewer notes, private email addresses, internal
contact details, sensitive partner metadata, or private reviewer identity.

Partner verification is not data certification. A verified partner may submit
data, but submitted records still require submission validation, source refs,
freshness, confidence, and quality-label evaluation before any Layer 27
certification eligibility can be represented.

## Data Quality Labels

Supported quality labels:

- `verified_partner_data`
- `audited_source_data`
- `self_reported_employer_data`
- `public_source_verified`
- `low_confidence_signal`

Each label includes:

- `label`
- `display_name`
- `description`
- `allowed_sources`
- `minimum_confidence`
- `requires_source_refs`
- `requires_partner_verification`
- `ranking_influence_allowed`
- `public_display_allowed`
- `warning_copy`

Default safety posture: `ranking_influence_allowed=false` for every label in
Batch 27B. No Layer 27 label currently changes rankings, recommendations,
forecasts, policy outputs, career-agent outputs, public reports, or market
scores.

## Certification Eligibility Rules

Layer 27 certification evaluation is deterministic and conservative:

- `verified_partner_data` requires a verified partner, accepted source refs, and
  at least medium confidence.
- `audited_source_data` requires source refs, at least medium confidence, and a
  review-safe audit marker.
- `self_reported_employer_data` requires employer partner context or employer
  submitter context, source refs, and warning copy.
- `public_source_verified` requires public source refs and at least medium
  confidence.
- `low_confidence_signal` may apply to weak, stale, incomplete, or low-confidence
  records, and it never permits ranking influence.

Certification eligibility is Layer 27 metadata only. It does not merge or mutate
canonical company, region, hiring, opportunity, recommendation, predictive,
policy, career-agent, public report, contribution, or market-score records.

## Governance Framework

Governance framework areas:

- `data_ethics`
- `labor_market_fairness`
- `source_standards`
- `institutional_use`
- `bias_review`

Each governance record includes:

- `area`
- `display_name`
- `description`
- `review_questions`
- `risk_flags`
- `recommended_controls`
- `status`
- `version`
- `public_summary`

The current governance status is `framework_defined`. This means the platform
has documented review questions, risk flags, and recommended controls for Layer
27 standards work. It does not mean an active governance board exists, that an
external board has approved the framework, or that partner submissions are
automatically reviewed or accepted.

Governance framework metadata is guidance only. It does not approve partner
submissions, certify submitted data, change quality labels automatically, alter
rankings, alter recommendations, alter forecasts, alter policy intelligence,
alter career-agent outputs, alter public reports, or alter market scores.

## Validation Contract

Validation checks that:

- the schema version is supported
- `partner_id` is present
- `submitter_type` is supported
- records are present
- each record type is supported
- required fields are present for each record type
- source refs are attached to records and declared at submission level
- freshness is declared
- confidence is declared
- private/internal metadata keys are rejected
- validation errors are structured and testable

Validation may accept partner warnings, but warnings are not evidence of
canonical truth. Partner-provided confidence and freshness survive serialization
as intake metadata.

## Authority Boundary

Partner submissions are intake state. Creating a partner submission:

- persists only to `data_standard_partner_submissions`
- does not create or update canonical company or region records
- does not create or update hiring activity, opportunity, recommendation,
  predictive, policy, career-agent, or market-score records
- does not certify the submitted facts as product-owned intelligence
- does not use partner verification as a shortcut for data certification
- does not let quality labels alter rankings or product intelligence by default

Future downstream consumers must define an explicit review/merge contract and
tests before partner intake can influence canonical intelligence.

## API Routes

- `GET /data-standards/definitions`
- `GET /data-standards/partner-schema`
- `GET /data-standards/partners`
- `GET /data-standards/partners/{partner_id}`
- `GET /data-standards/quality-labels`
- `GET /data-standards/governance-framework`
- `POST /data-standards/quality-labels/evaluate`
- `POST /data-standards/partner-submissions/validate`
- `POST /data-standards/partner-submissions`

The create route runs the same validation path as the validate route before
persisting a submission record.

## Frontend Standards Surface

The public `/data-standards` page consumes the Layer 27 API through the
frontend API client and types. It displays:

- Standard definitions
- Partner submission format
- Verified partner network
- Data quality labels
- Governance framework
- A bounded submission validation preview

The page states the public/institutional authority boundaries:

- Layer 27 defines standards and intake quality.
- Partner-submitted data is not automatically canonical.
- Verified partner status does not equal certified data.
- Data quality labels do not currently alter rankings, recommendations,
  forecasts, policy outputs, career-agent outputs, public reports, or market
  scores.
- Low-confidence and self-reported data require warnings.
- Governance is currently a framework, not an active governance board.

The validation preview is intentionally non-mutating. It may describe schema and
validation behavior, but it does not create submissions, certify data, accept
canonical records, or merge partner data into product-owned intelligence.

## Public Demo Behavior

Read-only Layer 27 standards metadata routes are public-demo allowlisted:

- `GET /data-standards/definitions`
- `GET /data-standards/partner-schema`
- `GET /data-standards/partners`
- `GET /data-standards/partners/{partner_id}`
- `GET /data-standards/quality-labels`
- `GET /data-standards/governance-framework`

Public demo mode remains fail-closed for Layer 27 mutation, evaluation, and
intake routes, including quality-label evaluation, partner submission
validation, and partner submission creation.

## Known Limitations

- Batch 27A does not implement partner certification workflows.
- Batch 27B exposes certification eligibility only; it does not implement a
  canonical merge or downstream activation pipeline.
- Batch 27B uses deterministic service-defined partner registry records rather
  than a mutable partner-management workflow.
- Batch 27C defines governance framework metadata, but it does not establish or
  claim an active governance board.
- The `/data-standards` frontend page is read-only and does not create real
  partner submissions.
- Layer 27 does not call external systems.
- Layer 27 does not expose partner authentication or rate limiting beyond the
  existing API protection layer.
