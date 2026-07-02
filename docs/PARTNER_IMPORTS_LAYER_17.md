# Layer 17 Partner Imports

Batch 17B lets institutions provide structured partner data while keeping product-owned market intelligence authoritative.

## Core Rule

Partner data is contributed evidence, not canonical truth. Imported records must not overwrite canonical company identity, canonical region intelligence, product scoring, freshness/confidence posture, or existing governance warnings.

## Supported Import Types

- `local_employer_list`
- `internship_partner_list`
- `regional_workforce_data`
- `aggregated_career_center_outcome_data`

## Supported Formats

- CSV
- JSON

XLSX is not implemented in Batch 17B.

## Lifecycle

Import batches can move through:

- `uploaded`
- `validated`
- `needs_review`
- `accepted`
- `partially_accepted`
- `rejected`
- `archived`
- `quarantined`

Acceptance creates `partner_import_records` only. It does not write to canonical company, region, scoring, application, CRM, or student profile tables.

## Validation Coverage

Validation checks for:

- required fields
- unsupported fields
- duplicate employers
- ambiguous employer names
- region normalization issues
- company identity conflicts
- stale dates
- missing source attribution
- unsupported data categories
- unverified outcome claims
- student-level PII
- individual salary or outcome records
- sensitive demographic/protected-class attributes
- ATS/application status semantics
- internal-only scoring/source fields

## Privacy Handling

Student-level PII, individual outcome records, individual salary records, and sensitive demographic/protected-class attributes are rejected or quarantined. Career-center outcome imports must be aggregate records.

Accepted records carry:

- `partner_contributed: true`
- `canonical_truth: false`
- source attribution
- confidence
- freshness status
- validation warnings
- no canonical identity overwrite
- no canonical region overwrite
- no product scoring override

## Permissions

Partner imports are institution-scoped:

- org admins and advisors may upload and validate
- org admins may accept, reject, or archive
- active report viewers may view import history
- students and non-members cannot create, view, or mutate import batches

Imported data does not leak across institutions.

## Downstream Posture

When accepted partner evidence is surfaced in institution exports, it is labeled as `partner_contributed_evidence` and includes source attribution, freshness/confidence status, and governance warnings. It is not invisibly merged into canonical product intelligence.
