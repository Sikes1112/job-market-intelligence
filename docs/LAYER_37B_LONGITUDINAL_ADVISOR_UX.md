# Layer 37B Longitudinal Advisor UX And Hardening

Layer 37B extends the authenticated Decision Workspace with the deep decision
intelligence delivered by Layer 37A. It does not add separate products for
company, compensation, skills, education, relocation, or timing. Those domains
remain scenario factors inside the Layer 36 decision workspace.

## Decision Workspace Integration

The existing `/markets/decisions` workspace now loads and generates Layer 37
deep analysis for the selected decision. The workspace still follows the same
loop:

```text
Career Identity
-> decision
-> scenarios
-> recommendation
-> deep advisor analysis
-> choice
-> action/application
-> outcome
-> weekly and strategic review
```

After comparison, option selection, application changes, and outcome recording,
the workspace regenerates deep analysis so factors, advisor findings,
recommendation evolution, and strategic reviews stay aligned with the current
decision state.

## Shared Factor UX

Layer 37 factors are rendered through shared factor/evidence components. The UI
shows:

* domain
* factor category
* direction
* evidence kind
* evidence strength
* confidence
* uncertainty
* stale evidence state
* caveats
* concise structured values where available

The UI does not turn unknown into zero or weak evidence into strong evidence.
It avoids unsupported percentage scoring.

## Domain Presentation

The deep advisor groups factors by:

* company evidence
* compensation / offers
* skill strategy
* education scenarios
* relocation
* timing / pivot

Company factors only present evidence supplied by canonical company,
company-region, hiring, entry-level, and market records. The UI does not make
employee-review or culture claims.

Compensation factors distinguish user-entered data, estimates/proxy evidence,
missing benefits, and conflicting compensation values. The UI states that
compensation is one factor rather than the full recommendation.

Skill factors use wording such as likely gap and not confirmed absence. Absence
from Career Identity is not rendered as proof that the user lacks a skill.

Education factors show cost, time, claimed skill-gap reduction, and uncertainty
without framing credentials as inherently beneficial.

Relocation factors show opportunity evidence, remote/relocation friction, COL
inputs, and sparse-evidence caveats.

Timing factors show application sample size and outcome evidence with explicit
caveats against fatalistic pivot rules.

## Recommendation Evolution

The workspace renders previous and current recommendation snapshot IDs,
confidence before/after, change type, meaningful changes, and the evidence
basis that prior recommendations are not independent evidence.

This keeps user-driven, market/evidence-driven, and confidence-driven changes
visible without recomputing change history on the client.

## Advisor Findings

Advisor findings are rendered as non-modal strategy challenges. Each finding
shows severity, support status, confidence, uncertainty, supporting evidence,
counter-evidence, affected goal, explanation, and suggested reconsideration.

The UI explicitly frames findings as strategy observations, not personality
judgments. It does not include language such as irrational, obsessed,
indecisive, or afraid to pivot.

## Longitudinal Context

The longitudinal context panel separates:

* stated intent
* observed behavior
* prior decisions
* recommendation snapshots
* outcomes
* decision history

The safety text from the backend is displayed so observed behavior remains
evidence and does not overwrite explicit intent.

## Strategic Reviews

Strategic reviews are displayed as generated historical snapshots. Each review
shows period, generated date, confidence, uncertainty, application summary,
outcome summary, active risks, blind spots, recommendation changes, and
suggested adjustments.

Historical reviews are not reconstructed from current data on the client.

## Hardening Coverage

Layer 37B tests cover:

* deep analysis load/generation
* shared factor rendering
* unknown/unavailable evidence
* proxy evidence
* stale evidence
* conflicting compensation evidence
* company/compensation/skill/education/relocation/timing factor groups
* no fake winner during abstention
* constraint challenge visibility
* user selection against recommendation
* reopen/history preservation
* sparse longitudinal context
* no blind-spot empty state
* intent versus behavior separation
* non-psychological advisor wording
* invalid application transition error handling
* quiet weekly review behavior

Additional backend hardening tests cover contradictory outcomes and temporal
dominance, verifying mixed outcomes preserve uncertainty and many old behavior
records do not overwrite current explicit intent.

## Non-Goals

Layer 37B does not add Layer 38 intelligence, employer ATS workflows, separate
domain-specific pages, dashboards, a new scheduler, autonomous decisions, or
LLM-authored canonical advice.
