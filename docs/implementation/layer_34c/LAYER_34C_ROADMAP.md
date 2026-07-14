# Layer 34C Executable Roadmap

Each step must be implemented and verified before the controller advances.

## 34C.1 — Calibration Report Foundation

### Goal

Create a deterministic internal calibration report covering every registered market and supported career goal.

### Required outputs

- market-goal result matrix
- score
- rank
- score margin
- confidence
- freshness
- evidence sufficiency
- direct evidence summary
- proxy evidence summary
- top drivers
- limitations
- tie or near-tie status
- stability placeholder
- contradiction placeholder

### Acceptance criteria

- all registered markets and goals are included
- output is deterministic
- stable tie handling exists
- no canonical writes occur
- report is machine-readable and test-covered

### Verification

- targeted calibration tests
- deterministic repeated-run test
- read-only database-count test
- public-safe serialization test

---

## 34C.2 — Goal-Specific Evidence Definitions

### Goal

Harden goal definitions so each career goal uses meaningfully different evidence.

### Required outputs

Each goal definition includes:

- direct evidence categories
- proxy evidence categories
- minimum direct evidence
- minimum total evidence
- proxy-only confidence cap
- unsupported conditions
- weighting rationale
- public-safe labels

### Acceptance criteria

- goal logic is outside routes
- no two goals are identical aliases
- generic company counts cannot dominate every goal
- data-science limitations are explicit
- tests prove goal differentiation

### Verification

- goal registry tests
- weight/definition uniqueness tests
- direct-vs-proxy classification tests
- data-science unsupported/limited tests

---

## 34C.3 — Evidence Sufficiency Gates and Abstention

### Goal

Add comparison_ready, limited_evidence, insufficient_evidence, and not_supported states.

### Required behavior

- normal rankings require sufficient evidence
- provisional results are labeled
- insufficient evidence causes abstention
- unsupported goals do not generate authoritative rankings
- pairwise comparisons may return no winner
- confidence is capped by sufficiency

### Acceptance criteria

- sufficiency is backend-derived
- frontend does not recompute it
- abstention is public-safe and explicit
- invalid combinations fail safely

### Verification

- all four sufficiency states
- confidence cap tests
- abstention tests
- pairwise no-winner tests
- API schema tests

---

## 34C.4 — Sensitivity and Robustness Engine

### Goal

Measure whether small evidence changes create unstable rankings.

### Required scenarios

- unknown to observed zero
- observed zero to unknown
- stale source
- low-confidence exclusion
- ranking exclusion
- missing internship
- missing co-op
- dominant employer
- sparse coverage
- direct evidence removed
- proxy-only evidence
- equal evidence tie

### Required outputs

- stable
- sensitive
- unstable
- indeterminate

Include:

- baseline result
- scenario result
- rank change
- winner change
- score delta
- confidence delta
- sufficiency delta
- public-safe explanation

### Acceptance criteria

- scenarios are deterministic
- no writes occur
- instability affects limitations and presentation
- missing data never improves confidence silently

### Verification

- scenario-specific tests
- repeated-run determinism
- mutation/read-only test
- regression tests

---

## 34C.5 — Market Differentiation Audit

### Goal

Detect profiles and rankings that are insufficiently differentiated.

### Required checks

- repeated strengths
- repeated weaknesses
- repeated overview language
- repeated drivers
- nearly identical goal orderings
- generic descriptions
- unsupported stereotypes
- missing market-specific evidence

### Required outputs

- differentiation score
- duplicated language findings
- repeated-driver findings
- cross-goal rank correlation summary
- required improvement recommendations

### Acceptance criteria

- deterministic
- public-safe
- does not fabricate distinctions
- distinguishes true similarity from templated output

### Verification

- duplicated-profile fixtures
- legitimately similar-market fixture
- repeated-driver test
- cross-goal similarity test

---

## 34C.6 — Explanation Quality Hardening

### Goal

Make explanations comparative, evidence-specific, and aligned with confidence and limitations.

### Required behavior

Explanations identify:

- why the market ranks here
- what evidence is direct
- what evidence is proxy
- strongest comparative advantage
- strongest comparative weakness
- missing evidence
- confidence limitation
- stability limitation

### Acceptance criteria

- no route-level explanation construction
- no unsupported city stereotypes
- no generic explanation where comparative evidence exists
- explanation order is deterministic
- explanations align with drivers and score margin

### Verification

- explanation specificity tests
- driver alignment tests
- confidence alignment tests
- limitation alignment tests
- generic-language rejection tests

---

## 34C.7 — Contradiction Detection

### Goal

Detect logical conflicts across ranking, profile, confidence, freshness, sufficiency, and explanation outputs.

### Required contradictions

- high confidence plus insufficient evidence
- strong internship plus missing internship evidence
- current freshness plus stale primary source
- winner with lower score
- opposite weakness and driver
- specific role recommendation without direct evidence
- comparison_ready without qualifying evidence
- no limitations despite critical gaps
- alphabetical tie displayed as winner

### Acceptance criteria

- blocking contradictions prevent normal recommendation
- warnings are public-safe
- contradiction codes are stable
- tests cover every required contradiction

### Verification

- one focused test per contradiction
- API serialization test
- frontend rendering test
- no internal object leakage

---

## 34C.8 — Public-Safe Evidence Grounding

### Goal

Expose defensible grounding without leaking internal provenance or trust/risk details.

### Required fields

- evidence areas used
- evidence areas missing
- direct evidence summary
- proxy evidence summary
- freshness
- coverage
- excluded-fact summary
- confidence constraints
- score margin
- stability status

### Acceptance criteria

- major outputs include grounding
- raw provenance remains hidden
- internal IDs remain hidden
- nested redaction tests pass

### Verification

- profile grounding tests
- ranking grounding tests
- comparison grounding tests
- nested redaction tests

---

## 34C.9 — Frontend Decision-Usefulness

### Goal

Turn hardening metadata into useful user decisions.

### Required states

- clear leader
- narrow lead
- tie
- provisional ranking
- insufficient evidence
- not supported

### Required sections

- Why this market
- Why not this market
- Evidence strongest here
- Evidence weakest here
- Direct vs proxy evidence
- What could change this ranking
- Stability
- Abstention explanation

### Acceptance criteria

- frontend consumes backend states
- no score/confidence/sufficiency recomputation
- limitations are visible
- abstention is visible
- unknown is distinct from zero
- accessible and responsive

### Verification

- focused frontend tests
- contract tests
- accessibility checks
- public-demo smoke coverage

---

## 34C.10 — Realistic Scenario Fixtures

### Goal

Add representative fixtures that stress the intelligence system.

### Required fixtures

- strong AI market with weak internships
- broad employer market with weak early-career access
- smaller market with strong co-op evidence
- stale but otherwise strong market
- market dominated by one employer
- market with many unknowns
- market with strong direct role evidence
- market relying mostly on proxies

### Acceptance criteria

- fixtures are synthetic and deterministic
- no external data is fetched
- each fixture supports at least one adversarial test
- fixtures do not alter production curated datasets

### Verification

- fixture validation
- scenario test coverage
- no production-data mutation

---

## 34C.11 — Product Quality Evaluation Report

### Goal

Produce the machine-readable artifact used for the final audit.

### Required report

For every market-goal result include:

- rank
- score
- score margin
- confidence
- sufficiency
- direct/proxy evidence
- top drivers
- limitations
- stability
- contradictions
- abstention
- explanation quality status
- differentiation findings

Include platform summaries:

- cross-goal ranking similarity
- score clustering
- dominant metrics
- unsupported goals
- provisional results
- abstentions
- unstable results
- contradictions

### Acceptance criteria

- deterministic
- public-safe
- all 40 expected combinations represented when registry/goals remain unchanged
- report generated through tested code
- artifact path documented

### Verification

- report schema test
- result-count test
- deterministic snapshot test
- redaction test

---

## 34C.12 — Full Verification Readiness

### Goal

Prepare the completed implementation for independent audit.

### Required work

- run all targeted tests
- run full backend suite
- run full frontend suite
- run lint
- run build
- run public-demo smoke
- run compile checks
- run git diff check
- verify no hard-boundary violations
- update Layer 34 docs
- do not self-declare PASS

### Acceptance criteria

- all required commands pass
- no blocking implementation issue remains
- final evaluation report exists
- implementation evidence is complete
- controller transitions to AUDITING
