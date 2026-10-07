# Layer 36 Decision Workspace Closeout

Layer 36B adds the authenticated frontend product loop on top of the Layer 36A
decision/outcome backend. The user-facing route is `/markets/decisions`.

## Product Surface

The Decision Workspace presents the lifecycle as one workflow rather than as
separate backend resources:

1. create or select a career decision
2. add scenario-style options
3. compare options against the Career Identity decision context
4. inspect recommendation, tradeoffs, evidence, challenges, confidence, and
   evidence sufficiency
5. choose any option, including a non-recommended option
6. view append-only decision journal entries
7. reopen a decided decision for reconsideration
8. create a career-focused action plan
9. track personal application progress
10. record outcomes and optional reflection
11. review deterministic weekly activity and reminder signals

The workspace is intentionally not an ATS, recruiting CRM, generalized project
management system, autonomous application submitter, or chatbot replacement.

## Career Identity Integration

The workspace calls the existing Career Identity API and uses Layer 36A decision
context snapshots as the personalization boundary. It does not reinterpret raw
Career Identity facts in the frontend.

The bridge panel shows current Career Identity sufficiency/consent state and,
when a decision has been evaluated, the Career Identity version captured by the
decision context snapshot. If Career Identity changes later, the workspace can
show the current sufficiency/consent state while preserving the historical
decision context version used by earlier recommendations.

If downstream personalization consent is off, the workspace explains that
recommendations may abstain or rely on limited context. It does not surface raw
private facts or attempt to reconstruct facts hidden by consent.

## Recommendation UX

The recommendation surface distinguishes:

- recommendation available
- backend abstention
- confidence
- evidence sufficiency
- supporting evidence
- contrary evidence
- unavailable evidence
- limitations
- structured challenges
- per-option qualitative fit dimensions
- hard constraint violations
- important unknowns

Unknown or unavailable evidence is rendered as unavailable evidence, not as poor
fit or a zero score. The UI does not invent percentage scores.

Abstention is a first-class state. When `recommendation_status` is `abstained`,
the workspace does not display a system winner and instead shows the backend
summary, challenges, limitations, unavailable evidence, and unknowns that would
need to be clarified.

Challenge severity is visible in text and styling. Hard constraint violations
remain visible even when an option has favorable fit on another dimension.

## Decision Choice And History

The selection panel labels the recommendation as advisory. The user can choose
any option, including one that differs from the recommendation. Selection writes
through `POST /me/decisions/{decision_id}/select`; history is read from
`GET /me/decisions/{decision_id}/journal`.

The reopen button calls `POST /me/decisions/{decision_id}/reopen`. The existing
journal remains visible so prior recommendations, context snapshots, selected
options, and user notes are not overwritten.

## Action, Application, Outcome, Review

After an option is selected, the workspace can create a career action plan with
research, application, and review actions. Actions can be moved through the
backend statuses `open`, `in_progress`, `completed`, `blocked`, and `skipped`.

Application tracking is personal state only. The frontend transition menu is
aligned with the backend legal transitions:

- `considering -> preparing | applied | withdrawn`
- `preparing -> applied | withdrawn`
- `applied -> response | interview | rejected | withdrawn | offer`
- `response -> interview | rejected | withdrawn`
- `interview -> final_round | rejected | withdrawn | offer`
- `final_round -> offer | rejected | withdrawn`
- `offer -> accepted | declined | withdrawn`

Terminal states do not present further transitions. If the backend rejects a
transition, the UI preserves the prior state and shows the error.

Outcomes can link to the current decision, selected option, action,
application, and recommendation. Reflection is optional.

Weekly review uses `GET /me/reviews/weekly` and renders deterministic stored
state only: happened, changed, worked, did not work, stalled, reconsider, next
actions, and reminders. A quiet week is rendered explicitly without fabricated
insights.

## Frontend Contract

Layer 36B adds centralized TypeScript types and protected API client methods for
the Layer 36A API family. Components do not issue ad hoc `fetch()` calls.

The main decision detail uses the aggregate `GET /me/decisions/{decision_id}`
read model for context, options, recommendation, plan, actions, applications,
and outcomes. The journal remains a separate append-only read model.

## Instrumentation

The repository has platform/API usage analytics and career-agent audit events,
but no general authenticated product analytics/event mechanism for frontend
behavior. Layer 36B therefore does not add new product events; adding a separate
analytics stack here would exceed the Layer 36B boundary.

## Validation Coverage

Layer 36B frontend tests cover:

- full authenticated Career Identity -> Decision -> Options -> Recommendation
  -> Choice -> Action -> Application -> Outcome -> Review flow
- abstention with no fake winner
- hard constraint challenge visibility
- user choice that differs from the recommendation
- reopen without erasing historical selected-option journal entries
- application `applied -> rejected`
- outcome linkage to decision/application/action surfaces
- historical decision context display after current Career Identity changes
- privacy/no-consent messaging without raw private fact leakage
- backend transition rejection preserving UI state
- quiet weekly review
- `/markets/decisions` product route admission and protected `/me/decisions`
  request behavior
