# Layer 34C Specification — Market Intelligence Quality, Calibration, and Decision-Usefulness Hardening

## Status

Approved implementation specification.

This file is the immutable product and architecture contract for Layer 34C. Implementation, audit, and remediation agents may not weaken or rewrite it to make the implementation pass.

## Starting Point

Layer 34A implemented a read-only backend market-intelligence engine.

Layer 34B implemented the user-facing market-intelligence experience.

Those batches proved that the platform can generate and display:

- market profiles
- career-goal rankings
- pairwise comparisons
- ranking drivers
- confidence
- freshness
- limitations
- public-safe explanations

Layer 34C must prove that the intelligence is sufficiently calibrated, differentiated, evidence-aware, stable, and useful to deserve user trust.

## Core Product Question

Layer 34C must answer:

> Are the platform's rankings, comparisons, profiles, confidence labels, and explanations genuinely defensible and useful, or do they merely produce technically valid output from incomplete data?

## Primary Outcomes

The completed layer must provide:

1. deterministic calibration analysis across all 40 current market-goal combinations
2. goal-specific evidence definitions that meaningfully differ by career goal
3. evidence-sufficiency states and abstention behavior
4. robustness testing against sparse, stale, low-confidence, and semantically changed data
5. profile and ranking differentiation checks
6. explanation-quality requirements
7. contradiction detection
8. public-safe evidence grounding
9. decision-usefulness improvements in the frontend
10. realistic adversarial scenario fixtures
11. a machine-readable product-quality evaluation report
12. an independent adversarial audit that supports the final decision

## Supported Markets

Use the registry as the source of truth. The current expected markets are:

- atlanta
- austin
- boston
- chicago
- nyc
- san_francisco_bay_area
- seattle
- washington_dc

Do not hardcode the market list into intelligence logic when the existing registry can supply it.

## Supported Career Goals

The current expected goals are:

- software_engineering
- product_management
- ai_ml
- cybersecurity
- data_science

Goal definitions must remain registry-backed or configuration-backed rather than embedded in route code.

## Evidence Sufficiency Contract

Every market-goal result must expose one of:

- comparison_ready
- limited_evidence
- insufficient_evidence
- not_supported

Definitions:

### comparison_ready

Enough direct or strongly relevant evidence exists to support a normal comparative ranking.

### limited_evidence

A provisional ordering may be shown, but limitations must be prominent and confidence capped.

### insufficient_evidence

The platform must abstain from declaring a normal winner or firm recommendation.

### not_supported

The current canonical data model does not support a defensible result for that goal or comparison.

The system must not produce a normal authoritative-looking ranking merely because a numeric score can be calculated.

## Direct and Proxy Evidence

Every goal definition must identify:

- direct evidence categories
- proxy evidence categories
- minimum direct-evidence requirement
- minimum total-evidence requirement
- confidence caps when only proxy evidence exists
- explicit unsupported conditions

The platform must disclose whether a result relies on direct evidence, proxy evidence, or both.

## Goal-Specific Quality Requirements

### Software Engineering

May use:

- technical employer presence
- engineering-related hiring evidence
- technical internship evidence
- entry-level technical pathways
- employer diversity
- ranking-eligible technical facts

### Product Management

May use:

- product-oriented employer ecosystem
- product hiring evidence
- product internship or rotational-program evidence
- company-stage or employer diversity where canonically supported
- early-career accessibility

Generic employer count alone must not dominate.

### AI/ML

May use:

- AI employer presence
- AI-related hiring evidence
- AI internship or early-career evidence
- advanced-technology ecosystem evidence where canonical
- confidence penalties where direct AI evidence is absent

### Cybersecurity

May use:

- cybersecurity employer presence
- security-related hiring evidence
- security internship pathways
- government, defense, or regulated-industry ecosystem only where canonically supported
- employer diversity

### Data Science

Direct data-science role-family evidence is currently limited.

The system must not present data-science rankings as equally grounded when direct evidence is absent. It must use limited_evidence, insufficient_evidence, or not_supported as appropriate.

## Calibration Requirements

Evaluate all current market-goal combinations.

The calibration report must detect:

- one market dominating nearly every goal
- nearly identical ranking order across goals
- score clustering
- unrealistic score spread
- generic metrics dominating goal-specific evidence
- confidence inconsistent with evidence sufficiency
- rankings inconsistent with explanations
- ties hidden by deterministic tie-breaking
- alphabetical ordering presented as substantive superiority
- limited evidence presented as a firm recommendation

## Robustness Requirements

The test suite must cover deterministic scenarios for:

- unknown to observed zero
- observed zero to unknown
- stale source
- expired source where supported
- low-confidence fact exclusion
- ranking-excluded fact
- missing internship evidence
- missing co-op evidence
- dominant single employer
- sparse market coverage
- direct evidence removed
- proxy-only evidence
- equal evidence tie
- small score perturbation
- source concentration
- contradictory inputs

The system must identify rankings that are unstable under small evidence changes.

## Explanation Requirements

Explanations must:

- identify the comparative evidence difference
- distinguish direct from proxy evidence
- state important missing evidence
- align with score drivers
- align with confidence
- align with sufficiency
- align with freshness
- avoid generic city stereotypes
- avoid unsupported trend language
- avoid repeating the same generic explanation across markets and goals

## Contradiction Requirements

Detect at least:

- high confidence with insufficient evidence
- strong internship claim with missing internship evidence
- current freshness with stale primary evidence
- declared winner with lower score
- weakness and driver making opposite claims
- highly specific recommendation without direct role evidence
- comparison_ready with no comparison-ready evidence
- zero limitations despite known critical gaps
- tie broken alphabetically but displayed as a winner

Blocking contradictions must prevent a normal recommendation.

## Public-Safe Grounding Requirements

Major intelligence outputs must expose public-safe grounding:

- evidence areas used
- evidence areas missing
- direct evidence count or summary
- proxy evidence count or summary
- freshness status
- coverage status
- ranking-excluded facts omitted
- confidence limitations
- score margin
- stability classification

Do not expose internal trust IDs, risk-routing IDs, raw provenance internals, reviewer data, raw ranking objects, file paths, or stack traces.

## Frontend Decision-Usefulness Requirements

The frontend must distinguish:

- clear leader
- narrow lead
- tie
- provisional ranking
- insufficient evidence
- not supported

The frontend must answer:

- Why this market?
- Why not this market?
- Where is evidence strongest?
- Where is evidence weakest?
- Is the result direct-evidence-based or proxy-based?
- What could change the ranking?
- How stable is the recommendation?
- Is the platform abstaining?

Limitations and abstentions must not be hidden behind hover-only UI.

## Read-Only Requirements

Layer 34C remains read-only.

Do not add:

- canonical writes
- source refresh
- imports
- scraping
- live external APIs
- browser automation
- scheduled jobs
- approval workflows
- operator overrides
- ranking overrides
- trust/risk policy changes

## Determinism Requirements

All rankings, reports, explanations, contradictions, scenarios, and serialized outputs must use:

- stable sorting
- explicit tie rules
- fixed clocks in tests
- deterministic fixtures
- no random IDs
- no uncontrolled filesystem ordering

## Completion Requirements

Layer 34C may pass only when:

- every roadmap implementation step is complete
- required deterministic verification passes
- all 40 current market-goal combinations are evaluated
- sufficiency and abstention behavior are implemented
- robustness scenarios pass
- contradictions are detected
- frontend decision states are visible
- public-safe grounding is visible
- Layer 31–34 regressions pass
- the independent audit returns PASS
- no blocking or major findings remain
- the final committed repository state passes post-commit verification

## Allowed Final Decisions

- PASS
- REMEDIATION_REQUIRED
- HUMAN_ESCALATION

Only PASS permits finalization.
