# Integration Governance

Layer 17 integrations move data across workflow boundaries without moving product authority.

## Product Authority

External destinations and partner inputs do not define product semantics. Job Market Intelligence remains the authority for canonical company identity, region intelligence, scoring, source governance, freshness posture, and confidence posture.

## Outbound Controls

Exports and reminders are prepared artifacts:

- CSV and PDF are local downloads.
- Google Sheets, Notion, and Airtable payloads are manual prepared payloads.
- ICS reminders are local calendar files.

No Batch 17A route performs OAuth, live sync, two-way sync, or direct external writes.

## Controlled API Access

Batch 17C external APIs are authenticated, scoped, and rate-limited. They expose
controlled read/access surfaces, not public open feeds.

API access must not:

- expose raw API keys after creation
- store raw API keys
- allow missing-scope access
- allow revoked-key access
- cross institution boundaries
- expose internal-only scoring/source fields
- remove freshness, confidence, coverage, source governance, or warnings
- convert partner-contributed evidence into canonical truth

External API responses include governance metadata and rate-limit metadata.
Institution dashboard API clients must be bound to the exact requested
institution.

## Career Platform Controls

Career platforms are references and destinations, not dependencies. Batch 17C
supports manual/export/deep-link workflows only.

Blocked workflows include:

- LinkedIn scraping
- Handshake automation
- logged-in job-board crawling
- automated application submission
- automated resume upload
- automated recruiter messaging
- ATS pipeline state
- applicant/candidate/student profiles
- employer CRM behavior

## Inbound Controls

Partner imports are institution-scoped contributed evidence. They must include source attribution before they can become accepted evidence. Accepted rows are stored separately from canonical market tables.

Imports must not:

- overwrite canonical company identity
- overwrite canonical region intelligence
- override product scoring
- remove governance warnings
- create ATS/application status state
- create student/applicant profile records
- create employer CRM records
- expose internal-only scoring/source fields

## Privacy Controls

Batch 17B rejects or quarantines:

- student names
- student emails
- phone numbers
- addresses
- student/person IDs
- individual salaries
- individual application outcomes
- demographic/protected-class attributes
- disability status
- race/ethnicity
- religion
- citizenship or immigration status
- gender or sexuality
- other sensitive individual-level attributes

Aggregated career-center outcomes may be accepted when they pass validation and preserve source attribution.

## Receipts

Integration receipts are governance records. They expose whether a workflow retained product authority, whether external writes/sync occurred, and whether partner evidence remained noncanonical.

Import receipts explicitly mark:

- partner-contributed evidence
- canonical truth false
- no company identity overwrite
- no region overwrite
- no scoring override
- no governance warning removal
- no student-level PII import
- no individual outcome import
- no sensitive demographic import
- no internal-only field exposure

Career platform exports explicitly mark no automation, no ATS state, no
application status creation, and no recruiter outreach.
