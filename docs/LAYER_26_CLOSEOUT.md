# Layer 26 Closeout

Layer 26 now has a governed career-agent path across grounded answers, action
planning, opt-in progress memory, and approval-gated tool preparation.

## Completed Scope

Layer 26A:

- grounded strategic career answers
- evidence refs on every recommendation
- freshness metadata
- uncertainty metadata
- anti-fabrication checks
- public API and frontend rendering

Layer 26B:

- grounded action plans
- ordered steps and milestones
- user-action-required vs system-suggested labels
- opt-in progress memory
- user-scoped, category-scoped durable memory
- protected memory-backed plan generation

Layer 26C:

- protected career-agent tool previews
- durable tool approval/rejection records
- approval gates for high-impact actions
- blocked autonomous application action type
- safe outreach drafts without sending
- export-safe report previews
- reminder, watchlist, notification, and checklist preparation
- tool audit events
- frontend tool preview and approval UI
- guardrail and false-integration tests

## Final Contracts

Grounded answers and plans remain structured-data-first. User preferences and
memory may personalize outputs but do not count as evidence.

Tool previews inherit the same evidence, freshness, uncertainty, and privacy
rules. Tool records are protected under `/me/career-agent/tools` and scoped to
the authenticated user.

Any action that changes state, shares user data, contacts another party, creates
reminders, updates watchlists, enables notifications, exports reports, or could
affect a job search requires explicit user approval.

Autonomous job applications remain prohibited.

## Runtime Limitations

Layer 26C does not wire actual reminder scheduling, file generation,
notification delivery, watchlist mutation, outreach sending, profile sharing,
resume submission, or job application submission. Approval records show user
intent and preserve auditability, but runtime execution remains false unless a
future batch adds a real backend integration with its own guardrails.

## Public Demo

Public demo mode allows only stateless public answer and action-plan routes.
Protected memory and tool routes are denied because they are user-scoped durable
state surfaces.
