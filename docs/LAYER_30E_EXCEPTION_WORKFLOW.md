# Layer 30E - Exception Workflow + Dashboard Finalization

Layer 30E adds rare exception handling on top of the deterministic Layer 30A-D
trust, risk, explanation, report, and recheck foundation.

## Scope

Implemented slices:

- 30.7 Exception Queue, Not Approval Queue
- Final User Intelligence Dashboard integration cleanup

This is not an owner/admin approval workflow. Normal submissions, partner
submissions, low-confidence items, stale items, and ordinary reports continue
through automated validation, trust assessment, risk routing, ranking influence
policy, explanations, and automated recheck where needed.

## Exception Cases

`exception_cases` are additive records for rare unresolved risk conditions. They
do not mutate canonical facts, opportunity records, source records, trust tiers,
risk levels, routing outcomes, or ranking influence.

Exception cases may be created from deterministic signals such as:

- critical spam, abuse-like, legal-like, or suspicious-ranking reports
- repeated serious spam or misleading reports
- failed or skipped high-priority rechecks
- unresolved conflicts after high-priority recheck
- critical risk decisions
- blocked, quarantined, or explicit exception routing outcomes

Exception cases are not created for:

- normal partner submissions
- ordinary low-confidence items
- stale items that can be rechecked
- ordinary user reports
- visible-with-warning items
- auto-recheck or needs-more-evidence outcomes by default
- unverified visible items

Duplicate open exception cases for the same subject and exception type are
suppressed by `ExceptionWorkflowService`.

## Public-Safe Status

Public/user-facing surfaces receive `ExceptionSubjectStatus`, which includes
only safe fields:

- public-safe status
- label
- message
- severity
- exception type
- timestamps

Public status does not expose internal notes, assigned owner, abuse details,
legal details, reviewer identity, or source dispute internals.

Protected internal endpoints can list/update exception cases using existing
data-review access controls. These endpoints are not exposed in public demo.

## Dashboard Integration

The User Intelligence Dashboard now consumes:

- trust/evidence fields from 30A
- risk/routing/ranking decisions from 30B
- trust explanations from 30C
- report/recheck status from 30D
- safe exception status from 30E

Dashboard next actions can direct users away from quarantined or blocked items,
but the dashboard does not become an approval queue and does not fabricate
intelligence.

## Safety Invariants

- Exceptions are rare unresolved risk cases, not normal approvals.
- Normal data flow remains automated.
- No new ranking influence is granted.
- `visible_to_users` still does not imply `ranking_influence_allowed`.
- Frontend renders backend-provided exception status only.
- No canonical truth mutation is performed by exception creation.
- No AI-authoritative decision path is introduced.
- Public demo can read safe status but cannot mutate exception records.
