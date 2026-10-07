# Layer 36A Decision And Outcome Backend

Layer 36A adds the backend contract for the personalized career decision
lifecycle. It is user-owned app data and does not mutate canonical market,
company, region, score, source, or Career Identity truth.

## Domain

`career_decisions` is the aggregate root. A decision has a type, status, title,
context, priorities, constraints, scenario options, a selected option, a current
recommendation snapshot, and versioned journal entries.

Supported decision types are `role_choice`, `company_choice`, `location_choice`,
`career_strategy`, `job_search_strategy`, `education_skill_investment`,
`offer_comparison`, and `career_path`. Supported decision states are `draft`,
`evaluating`, `decided`, `reconsidering`, `completed`, and `abandoned`.

`decision_options` model complete scenarios. A scenario can combine roles,
regions, companies, industries, work arrangement, compensation, relocation, or
other structured fields in JSON. One option is not required to equal one job or
one company.

## Career Identity Boundary

`decision_context_snapshots` is the canonical adapter boundary from Career
Identity into decision/recommendation logic. The service creates a snapshot with
the Career Identity id, version, completeness/sufficiency states, safe fact
references, and decision-facing context fields.

Recommendation logic consumes this snapshot instead of independently reading and
interpreting raw Career Identity facts. If downstream personalization consent is
not granted, the snapshot records that reason and does not expose fact refs or
fact payloads to the decision recommendation path. Historical recommendations
continue to point at the context snapshot used when they were generated.

## Fit And Evidence

`decision_recommendations` persists deterministic fit and comparison output:

- per-option fit assessments for role, market, company, and strategy where data
  exists
- direct, proxy, weak, contrary/conflicting, and unavailable evidence buckets
- hard constraint satisfaction and violations
- structured advantages, disadvantages, tradeoffs, and important unknowns
- confidence and evidence sufficiency
- abstention when evidence is insufficient or viable options are blocked

Layer 36A intentionally avoids fake precision. Unknown data is not treated as
zero. Scores are qualitative assessments backed by explicit evidence and
limitations. Company fit is omitted or weak when company metadata is absent or
low-confidence. Market fit references existing `region_market_scores` when
available and falls back only to proxy evidence when a region exists without a
score.

Structured challenge codes include hard constraint violations, compensation
minimum violations, weak company evidence, inferred identity dependency,
incomplete identity, and insufficient evidence. These codes are canonical; prose
is explanatory only.

## History

`decision_versions` is the decision journal. It stores append-only snapshots of
decision state, options, selected option, context snapshot, current
recommendation, user notes, and timestamps. Updating, selecting, reopening, plan
creation, and outcome recording append new versions instead of overwriting prior
reasoning.

## Execution Loop

`career_action_plans` and `career_actions` represent execution of a career
decision. Action categories are bounded to career use cases: research,
application, skill work, company targeting, networking/follow-up, preparation,
timing checkpoint, review task, and other.

`career_applications` is a personal application tracker. It supports the user
lifecycle `considering`, `preparing`, `applied`, `response`, `interview`,
`final_round`, `rejected`, `withdrawn`, `offer`, `accepted`, and `declined`.
`career_application_transitions` preserves transition history. Direct
`applied -> rejected` is valid; terminal states do not transition further.

`career_outcomes` captures observed outcomes from applications, actions,
decisions, skill work, research, networking, education, and strategy changes. An
outcome may link to a decision, action, application, option, and recommendation,
but not every outcome must originate from an application.

## Reviews And Reminders

Layer 36A does not create a second scheduler. Weekly review read models are
deterministically aggregated from stored decisions, actions, applications,
transitions, outcomes, due dates, follow-up dates, and planned review dates.

The review contract answers what happened, what changed, what worked, what did
not work, stalled items, invalidated assumptions, decisions to reconsider, next
actions, and upcoming reminders.

## APIs

Protected routes are mounted under `/me` and use the existing authenticated
internal `users.user_id` boundary:

- `GET /me/decisions`
- `POST /me/decisions`
- `GET /me/decisions/{decision_id}`
- `PATCH /me/decisions/{decision_id}`
- `POST /me/decisions/{decision_id}/options`
- `POST /me/decisions/{decision_id}/compare`
- `GET /me/decisions/{decision_id}/journal`
- `POST /me/decisions/{decision_id}/select`
- `POST /me/decisions/{decision_id}/reopen`
- `POST /me/decisions/{decision_id}/plan`
- `GET /me/actions`
- `PATCH /me/actions/{action_id}`
- `POST /me/applications`
- `PATCH /me/applications/{application_id}/transition`
- `POST /me/outcomes`
- `GET /me/reviews/weekly`

Read models return a decision graph with context, options, current
recommendation, latest action plan, applications, outcomes, and journal entries
where appropriate so Layer 36B does not need to reconstruct the lifecycle
client-side.

## Ownership And Privacy

Every Layer 36A row carries `user_id` and service methods enforce owner-only
read/mutation. Cross-user reads return not-found at the API layer. Linked
objects are validated before writes so selected options, action options,
applications, recommendations, and outcomes cannot cross user or decision
boundaries.

Private Career Identity facts flow through `decision_context_snapshots` only for
the authenticated owner and only when downstream personalization consent is
granted. Snapshots store safe provenance fields and fact refs, not raw imported
documents or uploaded text.

## Non-Goals

Layer 36A does not implement UI, employer ATS functionality, recruiter
workflows, autonomous application submission, email automation, a generalized
project management system, a new scheduler, a new market ingestion system, or
LLM-dependent recommendation correctness.
