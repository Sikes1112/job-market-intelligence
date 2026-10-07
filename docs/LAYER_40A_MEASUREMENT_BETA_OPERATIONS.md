# Layer 40A Measurement, Beta Operations, Trust, and Commercial Infrastructure

Layer 40A makes the product measurable and operable for real beta users. It does not claim production readiness or validated recommendation effectiveness.

## Reused Foundations

- Career Identity sufficiency comes from the Layer 35 `career_identity` evaluator.
- Decisions, recommendations, actions, applications, outcomes, journals, and weekly reviews come from Layer 36/37 `career_decisions`.
- Confidence, evidence sufficiency, recommendation status, limitations, challenges, and provenance remain the decision/recommendation trust primitives.
- Current opportunity coverage and unsupported-state language remain under `current_opportunities`.
- Admin authorization uses the existing privileged dependency boundary and admin event log.
- Monetization plan and feature primitives remain provider-agnostic; Layer 40A adds entitlement grants and feature gates without adding payment vendor code.

## Canonical Event Taxonomy

Events are persisted in `product_analytics_events` with `schema_version`, `event_type`, `event_source`, `occurred_at`, user/session reference, stable domain IDs, cohort/experiment metadata, confidence/coverage buckets, recommendation state, and a small structured payload.

Canonical event types:

- `onboarding_started`
- `onboarding_completed`
- `career_identity_sufficient`
- `decision_created`
- `decision_considered`
- `recommendation_generated`
- `recommendation_viewed`
- `recommendation_feedback_submitted`
- `recommendation_changed_decision`
- `decision_saved`
- `action_created`
- `user_acted`
- `action_succeeded`
- `application_recorded`
- `outcome_recorded`
- `outcome_updated`
- `reflection_recorded`
- `strategy_changed`
- `user_returned`
- `coverage_limitation_viewed`
- `trust_explanation_viewed`
- `commercial_offer_exposed`
- `commercial_offer_interest_recorded`
- `commercial_conversion_recorded`
- `support_case_created`
- `support_case_status_changed`

Generic analytics payloads must not contain raw resume text, journal text, recommendation narratives, support-message bodies, application materials, private notes, or reflection text. User-authored comments are stored only in the relevant first-party record such as feedback, support case, or reflection.

## Funnel Definition

The beta funnel is measured from durable state transitions where possible:

- Onboard: `onboarding_started`, then `onboarding_completed`.
- Identity sufficient: `career_identity_sufficient` emitted when the sufficiency evaluator returns sufficient.
- Decision: `decision_created` and `decision_considered`.
- Action: `action_created`, `application_recorded`, or `user_acted`.
- Outcome: `outcome_recorded` or `outcome_updated`.
- Return: `user_returned`; emitted only for a genuine later authenticated product visit as defined below.

Stage conversion can be read by cohort from the admin beta analytics endpoint. Counts are observational product-usage evidence, not KPI targets.

## Return Definition

An authenticated product visit starts when the backend successfully resolves a user on `GET /me`, the protected account bootstrap route used by the frontend after authentication.

`user_returned` is emitted when all of these are true:

- the user has a prior recorded authenticated product visit,
- the prior visit has been inactive for at least 30 minutes based on `product_user_visits.last_seen_at`,
- the current `GET /me` begins a new visit after that inactivity boundary.

The first authenticated visit creates a `product_user_visits` baseline and does not count as a return. Repeated `/me` calls, route changes, React rerenders, or other activity inside the 30-minute visit window update `last_seen_at` and do not emit another return. The return event is attributed to the authenticated `user_id` and inherits active cohort metadata from the measurement service when available.

Telemetry failures during visit observation are isolated from the account bootstrap response.

## Batch 40B Observation Classes

Automatically observed from actual product paths:

- `onboarding_started`
- `onboarding_completed`
- `career_identity_sufficient`
- `decision_created`
- `decision_considered`
- `recommendation_generated`
- `recommendation_viewed`
- `coverage_limitation_viewed` when a viewed recommendation has limitations, insufficient/limited evidence, or low/unknown confidence
- `trust_explanation_viewed`
- `decision_saved`
- `action_created`
- `user_acted`
- `application_recorded`
- `action_succeeded` when an action is completed or an application reaches a legitimately successful progression linked to an action
- `outcome_recorded`
- `outcome_updated`
- `user_returned`
- commercial exposure/interest/conversion signals only when the actual product records that signal
- support case lifecycle events

Explicitly user reported:

- recommendation usefulness,
- surprise,
- changed-decision feedback,
- missing alternative/category,
- confidence calibration,
- decision reflection,
- satisfaction,
- regret,
- strategy change reason,
- support, correction, dispute, and privacy request details.

Derived from persisted domain state:

- decision/action/application/outcome counts,
- stage-to-stage funnel conversion by distinct user,
- cohort segmentation,
- recommendation feedback summaries,
- support/dispute/correction counts,
- commercial signal counts,
- confidence and coverage bucket summaries.

Unavailable or not currently observable:

- employer responses the user never records,
- outcomes that require more elapsed time,
- causal impact of recommendations on interviews/offers/outcomes,
- real payment conversion when no real billing path exists,
- limitations shown outside instrumented recommendation/current-opportunity surfaces unless those surfaces emit their own view event.

## Recommendation Feedback and Outcomes

`recommendation_feedback` stores user feedback tied to the exact `decision_id` and `recommendation_id` the user saw. It captures usefulness, surprise, whether the recommendation changed the user's decision, missing alternatives, confidence calibration, and optional comments. Historical feedback is append-only at the record level and does not rewrite recommendation output.

Outcome evaluation is supported by:

- existing applications and application transitions,
- existing decision outcomes,
- `strategy_changes`,
- `decision_reflections`,
- recommendation feedback joined by decision/recommendation,
- cohort and experiment metadata.

Supported analysis includes usefulness by confidence/coverage bucket, changed-decision rate, surprise rate, missing-alternative rate, application/interview/offer state where recorded, strategy changes, satisfaction, regret, and later reflections.

## Causal Limitation

Layer 40A records associations only. It can support statements such as users who saw recommendation X later reported outcome Y. It must not be used to claim that the recommendation caused an interview, offer, strategy change, or other outcome without a valid study design.

## Beta Operations

Beta access is represented by:

- `beta_cohorts`
- `beta_cohort_memberships`
- `product_feature_gates`
- `experiment_assignments`

Feature access is server-authoritative. Frontend hiding is not an access-control boundary. Unknown or disabled gates fail closed unless explicitly configured as open. Administrative changes use privileged admin routes and the admin event log.

## Support and Correction Workflows

`support_cases` and append-only `support_case_events` support beta operations for:

- product issues,
- bad-data reports,
- recommendation disputes,
- privacy issues,
- account/access issues,
- billing issues when billing exists,
- other recoverable incidents.

Bad-data reports and recommendation disputes do not mutate canonical source truth or rewrite historical recommendations. Operators must resolve cases through review, correction, or remediation workflows appropriate to the data source.

## Commercial Architecture

Layer 40A separates commercial state from recommendation intelligence:

- plans and feature definitions remain in `backend/monetization`,
- entitlement grants are in `product_entitlement_grants`,
- beta/cohort feature access is in `product_feature_gates`,
- commercial experiment signals are in `commercial_experiment_signals`,
- recommendation scoring/ranking stays in the recommendation and decision services.

No payment vendor was added because the repository did not show an explicit launch requirement for real charging. Commercial experiments can record exposure, interest, learn-more, activation, cancellation, or conversion only when those events actually happen. Interest is not a purchase. Fake purchases must not be recorded.

Payment, entitlement, cohort, sponsorship, or experiment state must not alter core recommendation ordering or scoring. Tests cover this boundary.

## Admin Read Model

Admin-only Layer 40A APIs expose:

- cohort and feature-gate inspection,
- cohort membership assignment,
- experiment assignment,
- entitlement grant creation,
- support case inspection and status updates,
- beta funnel/event summaries segmented by cohort.

Ordinary users can inspect their own beta access, submit feedback, submit support/correction/privacy cases, record strategy changes/reflections, and record commercial interest signals.
