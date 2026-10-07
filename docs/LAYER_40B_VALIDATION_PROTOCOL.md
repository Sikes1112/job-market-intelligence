# Layer 40B Validation Protocol

Layer 40B must collect real-user beta evidence. This protocol defines the evidence that can be collected from Layer 40A infrastructure. It does not create beta participants, synthetic outcomes, fake purchases, or a launch decision.

## Participant Identifier Strategy

Use the product `user_id` as the internal participant key. Research notes may keep a separate study participant code, but analytics and product records should reference stable product IDs, cohort keys, decision IDs, recommendation IDs, action/application/outcome IDs, and support-case IDs rather than copying private free text into analytics.

## Cohort Assignment

Before a participant starts:

- assign the user to a beta cohort with `beta_cohort_memberships`,
- record cohort status and start/end if applicable,
- configure server-side feature gates,
- assign any experiment variant needed for commercial or product configuration tests,
- verify feature access through `/me/feature-access/{feature_key}`.

## Starting Product State

Record whether the participant begins with:

- Career Identity absent, insufficient, or sufficient,
- downstream personalization consent available,
- existing decisions/actions/outcomes,
- beta cohort and experiment assignment,
- relevant feature access or entitlement.

## Evidence Checklist

Automatically observed evidence from product instrumentation:

- onboarding started/completed,
- Career Identity sufficiency,
- decision created/considered,
- recommendation generated/viewed,
- recommendation confidence bucket,
- coverage/evidence sufficiency,
- recommendation state,
- decision saved,
- action plan/action created,
- application recorded and status transitions,
- outcome recorded/updated,
- user returned,
- coverage limitation/trust explanation viewed where instrumented,
- support/correction/dispute/privacy cases,
- commercial experiment exposure or interest signals when used,
- cohort and variant metadata.

Explicit user-reported evidence:

- recommendation useful or not useful,
- surprising or not surprising,
- whether it changed the decision,
- missing alternative indicator and category,
- confidence calibration feedback,
- later decision reflection,
- would make same decision again,
- view changed,
- satisfaction rating,
- regret level,
- strategy change and reason,
- support/correction/dispute/privacy descriptions.

Researcher/operator observations, if the study uses them:

- participant interview notes stored outside generic analytics,
- observed confusion or unsupported coverage not captured automatically,
- operational remediation notes on support cases,
- audit observations about product limitation communication.

Unavailable or not-yet-observed:

- outcomes requiring more elapsed time,
- employer responses not yet received,
- offer outcomes not applicable to the user's decision,
- retention not observable within the study window,
- commercial conversion when no real billing path exists.

Missing evidence is not negative evidence. It should be recorded as unavailable or not yet observed.

## Validation Questions

Layer 40B can evaluate:

- Did the user reach sufficient Career Identity?
- Did they create or consider a meaningful decision?
- What recommendation/version was generated and viewed?
- What confidence, coverage, evidence, and limitations accompanied it?
- Did the user find it useful?
- Was it surprising?
- Did it change their decision?
- Was an important alternative missing?
- Did the user save or act on the decision?
- What action/application/outcome followed?
- Did strategy change?
- Did the user return?
- Was the eventual outcome directionally consistent with the recommendation?
- What did the user think after seeing the outcome?
- Which cohort, feature configuration, entitlement, and experiment variant applied?
- Were there bad-data, recommendation, privacy, support, access, or billing incidents?
- Which limitations or unsupported states were encountered?

## Causal Boundary

Layer 40B may report observed associations from real usage. It must not claim that recommendations caused outcomes unless the study design supports causal inference.

## Completion Boundary

Do not mark this protocol complete until actual beta participants produce real evidence. Do not convert this protocol into a production launch classification.

