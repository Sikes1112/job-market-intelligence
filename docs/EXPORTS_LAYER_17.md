# Layer 17 Exports

Batch 17A supports local and prepared-manual exports.

## Supported Export Formats

- CSV local download
- PDF local download
- prepared Google Sheets payload
- prepared Notion payload
- prepared Airtable payload

Prepared payloads are not live integrations. They are structured manual-copy artifacts with `sync_mode: none`.

## Export Provenance

Each export includes provenance metadata:

- product object type and id
- product object label
- generating user
- optional organization scope
- freshness status
- confidence label
- evidence basis
- limitations
- governance warnings

CSV exports include provenance, freshness, and confidence rows before data rows. PDF exports include limitations and governance warnings in the generated file body and in the receipt.

## Data Governance

Export serialization strips internal-only fields such as:

- `raw_total_score`
- `score_ruleset_version`
- source version bundles
- source refs and source observation ids
- internal/token/provider fields

Public product fields may be exported, but source-governance internals and implementation-only scoring/source details are withheld.

Accepted partner import evidence may appear in institutional exports only as labeled `partner_contributed_evidence`. These rows retain source attribution, freshness/confidence status, and governance warnings, and they do not become canonical company, region, or scoring data.

## External Destination Boundary

Google Sheets, Notion, and Airtable exports are prepared payloads only. The backend does not call external APIs, does not create provider records, and does not treat destination schemas as product semantics.
