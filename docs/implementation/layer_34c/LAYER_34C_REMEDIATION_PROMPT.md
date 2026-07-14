You are the remediation implementation agent for Layer 34C.

Read:

1. docs/implementation/layer_34c/LAYER_34C_SPEC.md
2. docs/implementation/layer_34c/LAYER_34C_ROADMAP.md
3. docs/implementation/layer_34c/LAYER_34C_LOOP_PROTOCOL.md
4. docs/implementation/layer_34c/LAYER_34C_COMPLETION_CONTRACT.json
5. docs/implementation/layer_34c/LAYER_34C_STATE.json
6. the audit report path supplied by the controller

## Mission

Validate and remediate the accepted audit findings with the narrowest correct changes.

## Required Process

1. Validate each finding against source code and behavior.
2. Accept a finding when evidence confirms it.
3. Reject a finding only with concrete source/test evidence.
4. Map each accepted finding to:
   - code change
   - test change
   - documentation change when required
   - verification command
5. Fix blocking findings first.
6. Avoid broad refactors.
7. Add a regression test for every accepted defect.
8. Run focused verification.
9. Run the controller-required regression commands.
10. Return control to a fresh independent audit.

## Prohibited Behavior

- do not modify the specification
- do not weaken or delete tests
- do not mark the audit passed
- do not stage or commit
- do not add unrelated functionality
- do not add writes, scraping, live APIs, schedulers, or approval workflows
- do not hide unresolved findings

## Final Output

Your final response must conform exactly to the controller-provided JSON schema.

Do not include markdown outside the JSON response.

## Human-Authorized Fourth-Cycle Requirements

A human has authorized one additional remediation cycle for the two major findings identified after cycle 3.

This authorization is narrow.

### Required Fix 1 — Product Management Evidence Classification

Generic `formal_early_career_program_flag` evidence must not count as direct Product Management evidence by itself.

Treat generic formal early-career programs as proxy evidence unless the canonical model contains clearly product-specific evidence such as:

- product-specific hiring activity
- product-specific internship evidence
- product-specific rotational-program evidence
- another explicitly product-oriented canonical field

Required effects include, where applicable:

- direct evidence count
- proxy evidence count
- evidence basis
- sufficiency
- confidence cap
- ranking contribution
- public-safe evidence summaries
- limitations
- evaluation-report output

Add a focused regression fixture where:

- `formal_program_count > 0`
- product-specific activity is unavailable or zero

The result must not claim direct Product Management evidence.

### Required Fix 2 — Abstention and Unsupported Ranking Presentation

When a result is `not_supported` or `insufficient_evidence`:

- do not select the first sorted market as the decision market
- do not display a normal winner
- do not display normal “Rank #1” recommendation language
- do not display normal “Why this market” decision guidance
- do not imply that a diagnostic ordering is a supported ranking
- make abstention or unsupported status the primary frontend state

If diagnostic ordering remains in backend or evaluation artifacts:

- label it explicitly as diagnostic
- prevent it from supplying winner semantics
- prevent it from becoming the frontend decision recommendation

Add focused backend, frontend, and contract tests proving this behavior for Data Science.

### Cycle Completion

Do not return REMEDIATION_COMPLETE unless:

- both major findings are fixed
- focused regression tests pass
- the evaluation report is regenerated or validated
- no normal winner semantics remain for unsupported results
- Product Management generic formal programs no longer count as direct evidence
