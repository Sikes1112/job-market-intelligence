# Layer 34C Loop Protocol

## Purpose

This protocol controls the autonomous implementation, verification, audit, remediation, and finalization loop.

## State Machine

Allowed states:

- NOT_STARTED
- IMPLEMENTING_STEP
- VERIFYING_STEP
- STEP_COMPLETE
- IMPLEMENTATION_COMPLETE
- AUDITING
- REMEDIATION_REQUIRED
- REMEDIATING
- REVERIFYING
- PASS
- COMPLETE_PENDING_COMMIT
- LOCKED
- HUMAN_ESCALATION
- FAILED

## Core Rules

1. The specification is immutable.
2. The roadmap is executable but may not be weakened.
3. Only one roadmap step is implemented per fresh Codex invocation.
4. The controller, not Codex prose, advances state.
5. Deterministic commands must verify claims.
6. Audit runs use a fresh context and read-only sandbox.
7. Remediation runs use audit findings but may not mark the audit passed.
8. Maximum remediation cycles are defined by the completion contract.
9. A malformed structured response is a failed run.
10. Tests may not be deleted, weakened, skipped, or converted to xfail merely to pass.
11. Product behavior changes outside the specification require HUMAN_ESCALATION.
12. The final commit occurs only after PASS.
13. Post-commit verification is mandatory before LOCKED.
14. The loop stops after LOCKED and writes a next-layer handoff; it does not invent Layer 35.

## Implementation Transition

NOT_STARTED or STEP_COMPLETE
→ IMPLEMENTING_STEP
→ VERIFYING_STEP
→ STEP_COMPLETE

When every required step is complete:

STEP_COMPLETE
→ IMPLEMENTATION_COMPLETE
→ AUDITING

## Audit Transition

AUDITING → PASS when:

- no blocking findings
- no major findings
- all required verification passed
- specification is satisfied

AUDITING → REMEDIATION_REQUIRED when:

- findings are within Layer 34C scope
- remediation is bounded and implementable

AUDITING → HUMAN_ESCALATION when:

- specification is ambiguous
- a required product decision is missing
- remediation would change approved scope
- repository damage or unsafe state is detected
- retry limit is exceeded

## Remediation Transition

REMEDIATION_REQUIRED
→ REMEDIATING
→ REVERIFYING
→ AUDITING

Every remediation cycle must use a fresh audit invocation afterward.

## Finalization Transition

PASS
→ COMPLETE_PENDING_COMMIT
→ final inventory
→ stage intended Layer 34 files
→ staged diff audit
→ commit
→ post-commit verification
→ clean worktree
→ LOCKED

## Git Rules

- Record starting HEAD.
- Preserve unrelated changes.
- Do not stage during implementation steps.
- Capture changed-file inventory after every step.
- Do not use blind `git add .` during finalization.
- Exclude generated artifacts, caches, local databases, secrets, and environment files.
- Do not push or open a pull request.
- Final status must be clean after post-commit verification.

## Retry Rules

- A failed Codex invocation may be retried once for transport or malformed-output failure.
- A failed verification does not advance the step.
- Maximum audit/remediation cycles come from the completion contract.
- Exceeding the limit produces HUMAN_ESCALATION.

## Evidence Rules

Each implementation step must produce:

- changed files
- acceptance-criteria results
- commands run
- test results
- blocking issues
- remaining risks

Each audit must produce:

- decision
- confidence
- blocking findings
- major findings
- minor findings
- required remediations
- verification gaps
- lock recommendation

## Prohibited Loop Behavior

- changing the spec to match implementation
- changing tests solely to match broken output
- hiding failed commands
- accepting self-audit as independent audit
- repeatedly broad-refactoring after narrow findings
- automatic external data collection
- bypassing sandbox in the normal local loop
