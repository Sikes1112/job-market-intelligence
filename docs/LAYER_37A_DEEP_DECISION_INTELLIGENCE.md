# Layer 37A Deep Decision Intelligence Backend

Layer 37A extends the Layer 36 decision lifecycle with deeper, typed decision
intelligence. Layer 36 remains the canonical decision, scenario,
recommendation, journal, action, application, outcome, and review architecture.

## Canonical Boundary

Deep intelligence is generated for existing user-owned career decisions. It
does not create separate company, compensation, education, relocation, skill
gap, or timing decision engines.

The implemented flow is:

```text
Career Identity snapshot
-> Layer 36 decision and options
-> Layer 36 recommendation snapshot
-> shared Layer 37 factors
-> longitudinal context snapshot
-> recommendation evolution
-> advisory findings
-> strategic career review
```

Career Identity remains the source of user career facts. Layer 37 reads the
immutable decision-context snapshot already attached to the Layer 36 decision
and recommendation. Observed behavior, such as applications or ignored
recommendations, is advisory evidence only; it does not rewrite explicit goals,
preferences, constraints, or Career Identity facts.

## Factor Framework

`decision_factors` stores reusable factor records for all deep-decision
domains. Supported factor categories include benefit, cost, risk, time,
confidence, uncertainty, user importance, evidence strength, and reversibility.

Each factor preserves:

* decision, option, recommendation, and context linkage where applicable
* domain and factor key
* normalized value where comparison is valid
* raw value where source detail matters
* directionality
* importance
* confidence and uncertainty
* evidence strength
* direct, derived, inferred, proxy, unavailable, or conflicting evidence kind
* source/provenance
* explanation, caveats, and freshness status

Unknown remains unknown. Missing compensation, company, geography, or skill
data is not converted into negative evidence.

## Domain Intelligence

Company intelligence uses canonical company, company-region presence,
company-region hiring, entry-level, and region evidence. Canonical company
existence without company-region data is proxy evidence. Hiring and
early-career rows can lower freshness when their freshness window has expired.
No employer sentiment or workplace-quality claims are generated.

Compensation and offer intelligence evaluates user-entered or estimated base
salary, total compensation, targets, benefits, and conflicts between supplied
values. Estimated compensation is proxy evidence, not fact. Compensation is one
factor, not the whole recommendation.

Skill-gap intelligence compares the decision-context Career Identity skills
against scenario target skills. Visible overlap becomes transferable-skill
evidence. Missing target skills are treated as likely or weakly evidenced gaps,
not confirmed lack.

Education ROI intelligence evaluates scenario credential cost, time, and
claimed skill-gap reduction. High-cost credentials are surfaced as a caveat
when upside is not otherwise supported.

Relocation intelligence evaluates scenario region evidence, regional market
scores, relocation friction, remote work, and cost-of-living inputs where
available. Sparse geographic evidence lowers confidence.

Timing and pivot intelligence uses application and outcome history as cautious
evidence. It reports sample size and recent outcomes but does not apply a
universal rejection threshold as a deterministic pivot rule.

## Longitudinal Context

`longitudinal_context_snapshots` stores bounded, generated-at-time views of:

* explicit intent from the decision and Career Identity context
* observed behavior from applications and selected options
* prior system recommendations
* outcomes
* decision journal summaries
* scenarios considered

The payload records limits and the rule that behavior is evidence, not intent.
The implementation intentionally bounds history to avoid dumping unlimited user
history into one advisory object.

## Recommendation Evolution

`decision_recommendation_evolutions` compares the current Layer 36
recommendation with the previous persisted recommendation where available. It
can surface recommendation changes, context changes, confidence-only changes,
stale evidence, and user choices that differ from the recommendation.

Prior recommendations are not treated as independent evidence and cannot
recursively amplify confidence.

## Advisory Findings

`decision_advisory_findings` stores typed, evidence-backed findings. Current
deterministic findings include:

* stated goal versus observed application behavior mismatch
* repeated rejection pattern with sample-size caveat
* selected option differs from system recommendation
* weak compensation and relocation evidence combination
* low-diversity application strategy

Findings carry severity, support status, confidence, uncertainty, supporting
evidence, counter-evidence, explanation, and suggested action. Sparse evidence
can produce no finding. The advisor does not infer personality traits.

## Strategic Reviews

`strategic_career_reviews` stores generated strategic reviews linked to the
bounded longitudinal context. Reviews include current goals, strategy
performance, application and outcome summaries, identity/recommendation/market
change signals, active risks, blind spots, suggested next actions, confidence,
and uncertainty.

Strategic reviews are persisted snapshots. Regenerating a review creates new
records instead of rewriting old reviews.

## API

Layer 37A adds protected routes under the existing `/me` boundary:

* `POST /me/decisions/{decision_id}/deep-analysis`
* `GET /me/decisions/{decision_id}/deep-analysis`
* `GET /me/strategic-reviews`

The POST endpoint accepts optional `include_domains`, `window_start`, and
`window_end`. Supported domains are `company`, `compensation`, `skill_gap`,
`education_roi`, `relocation`, and `timing_pivot`.

The response returns one coherent analysis object containing factors,
longitudinal context, recommendation evolution, advisory findings, and the
strategic review. Cross-user access maps to not found. Missing or unsupported
domains fail validation without partial writes.

## Non-Goals

Layer 37A does not implement Layer 37B UX, employer ATS workflows, separate
domain-specific recommendation engines, employee-review sentiment, speculative
ML infrastructure, or LLM-authored canonical decision truth.
