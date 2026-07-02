# Layer 17 - Ecosystem And Integrations

Layer 17 lets users and institutions move product-owned market intelligence into adjacent workflows without letting external tools become the source of truth.

Batch 17A implements the shared integration foundation, export artifacts, and ICS reminder files. Batch 17B adds partner data imports and import governance. Batch 17C adds controlled API access and safe manual career-platform workflows.

## Implemented In Batch 17A

- Shared integration vocabulary:
  - `IntegrationDestination`
  - `IntegrationCapability`
  - `IntegrationRiskPosture`
  - `IntegrationPermissionDecision`
  - `IntegrationProvenance`
  - `IntegrationReceipt`
- User-owned integration records:
  - `integration_exports`
  - `integration_reminders`
- Protected API routes:
  - `POST /api/integrations/exports`
  - `GET /api/integrations/exports/{export_id}`
  - `GET /api/integrations/exports/{export_id}/download`
  - `POST /api/integrations/reminders`
  - `GET /api/integrations/reminders/{reminder_id}`
  - `GET /api/integrations/reminders/{reminder_id}/ics`
- Frontend controls on existing market, recommendation, and institutional surfaces.

## Implemented In Batch 17B

- Partner import vocabulary:
  - `PartnerImportBatch`
  - `PartnerImportRecord`
  - `PartnerImportSourceType`
  - `PartnerImportStatus`
  - `PartnerImportValidationResult`
  - `PartnerImportReceipt`
  - `PartnerImportGovernanceWarning`
  - `PartnerImportDecision`
  - `PartnerDataConfidence`
  - `PartnerContributedEvidence`
- Institution-scoped import records:
  - `partner_import_batches`
  - `partner_import_records`
- Supported import types:
  - local employer lists
  - internship partner lists
  - regional workforce data
  - aggregated career-center outcome data
- Supported formats:
  - CSV
  - JSON
- Protected API routes:
  - `POST /api/integrations/partner-imports`
  - `GET /api/integrations/partner-imports?organization_id=...`
  - `GET /api/integrations/partner-imports/{import_batch_id}`
  - `POST /api/integrations/partner-imports/{import_batch_id}/validate`
  - `POST /api/integrations/partner-imports/{import_batch_id}/accept`
  - `POST /api/integrations/partner-imports/{import_batch_id}/reject`
  - `POST /api/integrations/partner-imports/{import_batch_id}/archive`
  - `GET /api/integrations/partner-imports/{import_batch_id}/receipt`
- Institution-facing import center for upload, validation preview, warnings, quarantine/rejection visibility, action controls, and receipt review.

## Implemented In Batch 17C

- API access vocabulary:
  - `ApiClient`
  - `ApiKey`
  - `ApiScope`
  - `ApiAccessPolicy`
  - `ApiUsageRecord`
  - `ApiRateLimitDecision`
  - `ApiResponseEnvelope`
  - `ApiAccessAuditEvent`
- API access records:
  - `api_clients`
  - `api_keys`
  - `api_usage_records`
  - `api_access_audit_events`
- External API routes:
  - `GET /api/external/v1/regions`
  - `GET /api/external/v1/regions/{region_id}/intelligence`
  - `GET /api/external/v1/companies/{company_id}/geography`
  - `GET /api/external/v1/market-signals`
  - `GET /api/external/v1/institutions/{organization_id}/dashboard`
- API management routes:
  - `POST /api/integrations/api-clients`
  - `GET /api/integrations/api-clients`
  - `PATCH /api/integrations/api-clients/{api_client_id}`
  - `POST /api/integrations/api-clients/{api_client_id}/keys`
  - `POST /api/integrations/api-keys/{api_key_id}/revoke`
  - `GET /api/integrations/api-clients/{api_client_id}/usage`
- Career platform vocabulary:
  - `CareerPlatform`
  - `CareerPlatformReference`
  - `CareerPlatformExport`
  - `CareerPlatformRiskPosture`
  - `ExternalCareerLink`
- Career platform records:
  - `career_platform_references`
  - `career_platform_exports`
- Career platform routes:
  - `GET /api/integrations/career-platforms`
  - `GET /api/integrations/career-platforms/companies/{company_id}/links`
  - `POST /api/integrations/career-platform-references`
  - `GET /api/integrations/career-platform-references`
  - `POST /api/integrations/career-platform-exports`
- Frontend Account controls for API access and platform registry.
- Company controls for manual LinkedIn and Handshake exports.

## Product Authority Boundary

Layer 17A integrations are outbound artifacts only. They do not:

- perform OAuth
- write directly to Google Sheets, Notion, Airtable, Google Calendar, or Outlook
- create live sync or two-way sync
- allow external destinations to define product semantics
- expose internal-only scoring/source fields
- create applicant tracking system state

Receipts explicitly mark:

- `external_write_performed: false`
- `live_sync_enabled: false`
- `oauth_performed: false`
- `two_way_sync_enabled: false`
- `product_authority_retained: true`

Partner import receipts additionally mark:

- `partner_contributed_evidence: true`
- `canonical_truth: false`
- `canonical_identity_overwrite_performed: false`
- `canonical_region_overwrite_performed: false`
- `product_scoring_override_performed: false`
- `governance_warnings_removed: false`
- `internal_only_fields_exposed: false`

External API responses preserve:

- freshness metadata
- confidence metadata
- coverage metadata
- source governance warnings
- partner-contributed evidence labels
- rate-limit metadata

API keys are hashed at rest and raw keys are returned only during creation.
Institution-scoped API clients cannot access other institutions.

Career platform exports mark:

- `manual_only: true`
- `automation_performed: false`
- `ats_state_created: false`
- `application_status_created: false`
- `recruiter_outreach_created: false`

## Permission Model

Exports and reminders are owned by the authenticated internal user. Retrieval/download requires the same owner. Institutional exports/reminders additionally require an active organization membership with the appropriate report/dashboard permission.

Partner imports are institution-scoped. Organization admins and advisors may upload and validate imports. Organization admins may accept, reject, or archive import batches. Active report viewers may view import history. Students and non-members cannot create, view, or mutate import batches.

## Partner Data Boundary

Partner data is contributed evidence, not canonical truth. Accepted records are labeled as partner-contributed evidence with source attribution, freshness, confidence, and validation warnings. They do not overwrite canonical company identity, canonical region intelligence, product scoring, or existing source governance.

Privacy-sensitive or individual-level records are rejected or quarantined. Student-level PII, individual salary/outcome records, sensitive demographic/protected-class fields, application status semantics, and internal-only fields are not accepted as downstream evidence.

## Deferred To Later Batches

- Batch 17D: final audit, docs hardening, broad regression pass, and closeout.
