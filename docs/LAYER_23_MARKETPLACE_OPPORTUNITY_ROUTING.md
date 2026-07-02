# Layer 23 - Marketplace / Opportunity Routing

Layer 23 is the marketplace and opportunity routing layer. Its purpose is to
help users move from trusted market intelligence into actionable opportunity
routes while preserving the objectivity of the intelligence layer.

Layer 23 is not a generic job board. Opportunity records are structured,
trusted, early-career opportunity objects that can later attach to market,
company, region, and role-family intelligence. They do not replace or reshape
the objective intelligence itself.

## Layer 23A Scope

Layer 23A implements the backend foundation for structured early-career
opportunity records:

- internships
- co-ops
- rotational programs
- new-grad roles
- apprenticeships
- employer early-career programs

Implemented backend components:

- `backend/opportunities/models.py`
- `backend/opportunities/repository.py`
- `backend/opportunities/service.py`
- `backend/opportunities/schemas.py`
- `backend/opportunities/verification.py`
- `backend/opportunities/governance.py`
- `backend/api/opportunities.py`
- Alembic revision `0025_opportunity_infrastructure`

## Layer 23B Scope

Layer 23B adds safe employer and partner submission intake plus internal review
workflow. It does not add routing, recommendations, scraping, application
tracking, referrals, messaging, ATS integrations, payments, sponsored ranking,
or frontend marketplace UI.

Implemented additions:

- employer/partner submission payloads and validation
- append-only `opportunity_submissions`
- append-only `opportunity_review_actions`
- `backend/opportunities/submissions.py`
- submission and review API routes
- effective trust/review-state derivation for read payloads
- Alembic revision `0026_opportunity_submission_review`

## Layer 23C Scope

Layer 23C connects trusted market intelligence to user-facing opportunity
routes. The output is an opportunity route, not a job listing feed:

user profile / intent -> market fit -> region fit -> company-type fit ->
role-family fit -> verified or source-checked opportunity fit -> next-step
guidance.

Implemented additions:

- `backend/opportunities/route_schemas.py`
- `backend/opportunities/matching.py`
- `backend/opportunities/routing.py`
- `POST /opportunities/routes`
- route-first frontend workspace at `/markets/opportunity-routes`
- frontend route contracts and API helper in `frontend/src/opportunityTypes.ts`
  and `frontend/src/opportunityRoutes.ts`

Layer 23C is deliberately route-first. The route payload groups matched
programs under strategic route objects with explanations, warnings, source
summaries, confidence, and next steps. It does not expose all-opportunity
search, newest sorting, infinite listings, one-click apply, application status,
messaging, referrals, ATS synchronization, payments, or sponsored ranking.

## Opportunity Records

An opportunity record carries structured fields for employer/program identity,
program type, role-family bindings, region or metro bindings, location mode,
seniority level, eligibility, application/source URLs, dates, expiration,
compensation disclosure, trust label, review status, and employer influence
metadata.

Trust labels include:

- `verified`
- `source_checked`
- `partner_submitted`
- `unverified`
- `expired`
- `rejected`

Review statuses include:

- `pending_review`
- `approved`
- `source_checked`
- `rejected`
- `expired`
- `needs_correction`

Expiration is derived at read time. Opportunities past their application
deadline or explicit expiration timestamp are marked expired in API payloads
and excluded from active verified opportunity views.

## Employer Submission Flow

Employers and partner organizations submit structured early-career opportunities
through `POST /opportunities/submissions`.

Submitted opportunities default to:

- `trust_label: partner_submitted`
- `review_status: pending_review`
- `partner_submitted: true`
- `paid_partner: false` unless explicitly provided with visible metadata
- `ranking_influence_allowed: false`

Submissions cannot provide `trust_label`, `review_status`,
`ranking_influence_allowed`, `verified`, or `source_checked` overrides. Extra
fields are rejected by the submission contract.

Every submission creates an immutable opportunity snapshot plus append-only
submission metadata. Submitted does not mean verified.

Submission read routes:

- `GET /opportunities/submissions`
- `GET /opportunities/submissions/{submission_id}`

## Review Flow

Review actions are command-style and append-only:

- `approve_as_verified`
- `approve_as_source_checked`
- `mark_unverified`
- `mark_expired`
- `reject`
- `request_correction`

`POST /opportunities/submissions/{submission_id}/review` records the review
action. The original opportunity snapshot remains additive-only; public
opportunity payloads derive their effective trust label and review status from
the latest review action.

Trust transitions:

- `approve_as_verified` -> `trust_label: verified`, `review_status: approved`
- `approve_as_source_checked` -> `trust_label: source_checked`,
  `review_status: source_checked`
- `mark_unverified` -> `trust_label: unverified`,
  `review_status: pending_review`
- `mark_expired` -> `trust_label: expired`, `review_status: expired`
- `reject` -> `trust_label: rejected`, `review_status: rejected`
- `request_correction` -> `trust_label: unverified`,
  `review_status: needs_correction`

All review actions preserve `ranking_influence_allowed: false`. Internal review
notes and reviewer identity are stored in review audit rows and are excluded
from public opportunity payloads.

## Trust And Influence Separation

Employer and partner metadata is visible on opportunity records:

- `partner_submitted`
- `paid_partner`
- `ranking_influence_allowed`

Layer 23A and 23B force `ranking_influence_allowed` to `false`. Paid or
partner-submitted metadata may describe the opportunity record, but it cannot
affect market scores, company scores, region scores, role-family scores,
predictive scores, institutional scores, public benchmark scores, or objective
rankings.

## API Surface

Layer 23 exposes read opportunity routes:

- `GET /opportunities`
- `GET /opportunities/{opportunity_id}`

Supported list filters:

- `trust_label`
- `region`
- `role_family`
- `program_type`
- `active`
- `expired`
- `limit`

Layer 23B adds command-style submission/review routes:

- `POST /opportunities/submissions`
- `GET /opportunities/submissions`
- `GET /opportunities/submissions/{submission_id}`
- `POST /opportunities/submissions/{submission_id}/review`

Layer 23C adds route generation:

- `POST /opportunities/routes`

The route request accepts profile or intent summary, target regions,
target role families, preferred program types, preferred location modes,
experience level, skills, background tags, constraints, trust preferences,
`include_unverified`, and a route limit.

The route response returns grouped `routes`, each with:

- route title and target region/role family
- market, region, company-type, role-family, opportunity, and overall route
  fit scores
- confidence
- route explanation
- recommended company types
- subordinate matched opportunities
- warnings and caveats
- next steps
- source summary
- partner/paid disclosure where applicable

There are no generic update or delete routes.

## Routing And Matching Logic

Route generation is deterministic. For each requested region and role-family
pair, Layer 23C reads stored objective region intelligence as context, then
scores eligible opportunities using transparent route-only criteria:

- region binding match
- role-family binding match
- preferred program type match
- preferred location mode match
- seniority match
- verified/source-checked/partner/unverified trust strength
- skills and background tag overlap

Route fit and opportunity fit are new Layer 23C outputs only. They are not
canonical market scores, region scores, company scores, role-family scores,
predictive scores, institutional scores, benchmark scores, or public rankings.

If no verified or source-checked opportunity is available, the endpoint still
returns strategic route guidance based on market, region, company-type, and
role-family context, with an empty matched opportunity list and caveats.

## Trust Behavior In Routes

Default routing is conservative:

- active `verified` opportunities may attach
- active `source_checked` opportunities may attach
- `unverified` and pending partner-submitted opportunities are excluded by
  default
- `include_unverified=true` can include unverified or partner-submitted records,
  but the payload labels them clearly
- expired opportunities are excluded
- rejected opportunities are excluded

Partner-submitted metadata is preserved in matched opportunities even after an
internal review makes the effective trust state verified or source-checked.

Paid partner metadata is disclosed at the matched-opportunity level and route
level. Paid status does not add score points and cannot move a route or program
above another record.

Internal review notes, reviewer identity, and submission audit details do not
appear in route payloads.

## Governance Boundary

Opportunity records and submission/review audit rows are additive-only. The
tables are protected with SQLAlchemy update/delete guards, and tests prove
opportunity submission and review actions do not mutate existing objective
intelligence outputs or scoring authorities.

Layer 23 does not own:

- generic job search
- live job scraping
- application tracking
- referral workflows
- employer payments
- sponsored ranking
- objective score mutation
- generic listing feeds
- messaging
- ATS integrations

## Frontend Route Experience

The user-facing route surface is `/markets/opportunity-routes`. It renders:

- route request controls for profile intent, target regions, role families,
  program/location preferences, seniority, skills, background tags, constraints,
  and unverified opt-in
- recommended opportunity route cards
- route fit explanation
- best region and role-family path
- score tiles for route-only fit dimensions
- matched verified/source-checked programs subordinate to the route
- trust labels
- partner-submitted and paid-partner disclosure
- warnings and caveats
- suggested next steps
- source summary

The UI avoids generic all-listing patterns. It does not provide keyword search,
newest sorting, infinite browsing, one-click apply, employer messaging, or
application tracking.

## Deferred To Later Layers

Deferred work remains:

- richer company-type intelligence
- deeper role-family intelligence inputs
- user-saved route artifacts
- authenticated route history
- employer admin frontend
- additional source review workflows
- integrations that remain manual/export/deep-link only
- any future marketplace monetization, if governed separately and kept out of
  scoring/ranking authority
