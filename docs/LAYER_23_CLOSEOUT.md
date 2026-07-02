# Layer 23 Closeout - Opportunity Infrastructure, Submission, Review, And Routing

## Layer 23A Decision

COMPLETE_FOUNDATION

Layer 23A implements backend opportunity infrastructure without launching a
job board, employer marketplace, sponsored ranking system, or user routing
engine.

## Layer 23B Decision

COMPLETE_SUBMISSION_REVIEW_FOUNDATION

Layer 23B implements employer and partner submission intake plus internal
review actions without allowing employer participation to become objective
scoring authority.

## Layer 23C Decision

COMPLETE_ROUTE_FIRST_OPPORTUNITY_ROUTING

Layer 23C implements intelligence-driven opportunity routing that connects user
intent to market, region, company-type, role-family, verified/source-checked
opportunity, and next-step guidance without becoming a generic job board.

## Implemented

Layer 23A implemented:

- structured opportunity SQL tables
- employer program records
- source evidence records
- region and role-family bindings
- employer influence metadata
- trust-label and review-status contracts
- expiration helpers and active/expired filtering
- read-only opportunity API routes
- governance constants and scoring anti-corruption checks
- Alembic migration and schema registration
- pytest coverage for models, service behavior, governance, and API payloads

Layer 23B adds:

- structured employer/partner submission request contracts
- append-only `opportunity_submissions`
- append-only `opportunity_review_actions`
- command-style submission and review service
- submission API routes
- review API route
- effective trust-label and review-status derivation from latest review action
- tests for submission defaults, validation, review actions, API behavior, and
  scoring anti-corruption

Layer 23C adds:

- API-safe route request, route, matched-opportunity, source-summary, and
  response contracts
- deterministic opportunity matching logic
- route generation service
- `POST /opportunities/routes`
- route-first frontend workspace at `/markets/opportunity-routes`
- frontend route contracts and API helper
- tests for route grouping, trust filtering, paid/partner disclosure, score
  separation, frontend rendering, and anti-job-board behavior

## Governance Decision

Opportunity records and review records are additive-only. They can describe
trusted early-career routes, but they cannot mutate or influence objective
market intelligence.

Partner-submitted and paid-partner metadata is preserved and visible, while
`ranking_influence_allowed` defaults to `false` and is rejected if enabled.
Review actions also persist `ranking_influence_allowed: false`.

Employer submission does not mean verified. New submissions are
`partner_submitted` and `pending_review` until an internal review action derives
an effective trusted state.

Layer 23C route and opportunity fit scores are Layer 23 outputs only. They do
not mutate objective market scores, region scores, company scores, role-family
scores, predictive signals, institutional scores, benchmark rankings, public
rankings, or canonical intelligence rows.

## Review Decision

Supported review actions:

- `approve_as_verified`
- `approve_as_source_checked`
- `mark_unverified`
- `mark_expired`
- `reject`
- `request_correction`

Approvals are only available through the review service/API. Internal review
notes and reviewer identity are stored in audit rows and excluded from public
opportunity payloads.

## Routing Decision

The route endpoint returns grouped strategic route objects. Matched
opportunities are subordinate route evidence. If no verified/source-checked
program is available, the endpoint still returns route guidance with caveats and
an empty matched-opportunity list.

Default route matching includes active verified and source-checked records.
Unverified and pending partner-submitted records are excluded unless
`include_unverified=true`, and then they remain visibly labeled. Expired and
rejected opportunities are excluded from active route recommendations.

Paid partner status is disclosed and is not a scoring input.

## Boundary Decision

Layer 23 does not implement:

- scraping
- generic job search
- application tracking
- referral or messaging workflows
- ATS integrations
- employer payments
- sponsored ranking
- generic listing feeds
- employer-controlled editing of verified records

## Validation

Tests prove:

- opportunities can be created, stored, and serialized
- employer submissions default to pending, partner-submitted, non-ranking state
- submitters cannot self-verify or mark source-checked/approved
- submitters cannot set ranking influence
- trust labels and review statuses serialize as API-safe values
- expired opportunities are marked and filtered correctly
- active verified views exclude expired opportunities
- partner-submitted and paid-partner metadata is preserved
- review actions can derive verified, source-checked, rejected, expired, and
  needs-correction states
- review actions preserve `ranking_influence_allowed: false`
- internal review notes are not exposed in public API payloads
- `ranking_influence_allowed` remains false
- opportunity submissions and reviews do not mutate score, output, predictive,
  index, or public benchmark ranking authority rows
- route recommendations can be generated from a profile/intent request
- route responses are grouped strategic objects, not flat listings
- verified and source-checked opportunities attach to routes
- unverified opportunities are excluded by default
- `include_unverified=true` labels unverified records clearly
- expired and rejected opportunities are excluded from active route matches
- partner-submitted and paid-partner metadata is preserved and disclosed
- paid-partner status does not increase fit score
- route and opportunity fit scores do not mutate objective intelligence rows
- employer submission/review notes do not leak into route payloads
- the frontend renders route cards, explanations, trust labels, warnings, next
  steps, and disclosure without generic listing controls

## Deferred Work

Still deferred:

- richer company-type and role-family intelligence inputs
- saved route artifacts
- authenticated route history
- frontend submission/review UI
- scraping
- application tracking
- referrals
- candidate-employer messaging
- ATS integrations
- payments
- sponsored ranking
