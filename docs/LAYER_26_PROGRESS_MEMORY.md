# Layer 26B - Progress Memory

Career progress memory is optional, private, and user-scoped. It is off by
default and cannot be saved unless the user explicitly opts in for the relevant
category.

## Categories

- `saved_companies`
- `target_regions`
- `applied_roles`
- `preferred_industries`
- `rejected_markets`
- `career_constraints`
- `preferred_role_types`

Each category has its own permission record. Entries are stored separately from
permissions so a category can be enabled, personalized, edited, or cleared
without affecting unrelated categories.

## Permission Rules

- Memory is off when no category permission is enabled.
- Saving or enabling memory requires `explicit_user_permission: true`.
- Personalization requires both `enabled: true` and
  `personalize_allowed: true`.
- Disabling a category deletes entries for that category.
- `DELETE /me/career-memory` can clear all memory or delete selected
  categories/entries.

## Evidence Boundary

Career memory is always user-provided context:

- `source: user_provided`
- `visibility: private`
- `counts_as_evidence: false`

Memory may adjust plan prioritization only through the protected
`POST /me/career-agent/action-plans` endpoint. It never becomes an evidence ref
and never changes canonical region, company, opportunity, forecast, freshness,
or confidence records.

Rejected markets and applied roles affect plans only when those exact
categories are enabled for personalization. Without permission, the same
grounded plan request ignores those memory categories.

## Privacy Boundary

Memory routes are protected under `/me`. Career memory does not appear in:

- public career-agent answer payloads
- public action-plan payloads
- public reports
- public demo routes
- unrelated users' profiles
- the current user export payload

Account deactivation deletes career memory rows along with other user-owned
private data.

## Current Limitations

Layer 26B implements progress memory only. It does not implement reminders,
outreach sending, exports, notifications, watchlist mutation, autonomous job
applications, or progress-memory conversation history.
