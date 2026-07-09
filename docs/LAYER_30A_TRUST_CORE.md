# Layer 30A Trust Core + Evidence Requirements

Layer 30A implements the deterministic backend foundation for:

- 30.2 Automated Trust Tiers
- 30.4 Evidence Requirements Engine

It does not implement autonomous risk routing, ranking influence automation,
exception queues, automated rechecks, user reports, or the full trust
explanation API.

## Contracts

The shared trust contracts live in `backend/trust/schemas.py`:

- `TrustTier`
- `EvidenceRequirementStatus`
- `EvidenceRequirementCode`
- `TrustAssessmentSubjectType`
- `EvidenceRequirementResult`
- `TrustWarning`
- `TrustAssessmentResult`

The assessment version is `30A.1` and the assessment source is
`deterministic_layer_30a`.

## Evidence Requirements

`EvidenceRequirementsEngine` evaluates existing metadata only. It performs no
AI calls, no live source checks, no writes, and no canonical truth changes.

Supported requirement codes include source presence, source policy, freshness,
confidence, duplicate/conflict checks, independent verification, partner trust,
self-promotional signals, corroboration, claim type policy, and existing ranking
evidence metadata.

## Trust Tiers

`TrustAssessmentService` assigns trust tiers deterministically from the evidence
result and subject metadata. The current precedence is:

`blocked > quarantined > conflicting > stale > partner_submitted >
low_confidence > verified > trusted > unverified_visible >
ranking_ineligible > not_assessed`

This preserves the Layer 30 rule that partner-submitted opportunities remain
partner-submitted unless a stronger blocked, quarantined, conflicting, or stale
signal applies.

## Persistence

`trust_assessments` is an additive snapshot table. The assessment service itself
does not persist or mutate anything. Callers must explicitly use
`TrustAssessmentRepository` when an audit snapshot is needed.

## Safety Boundaries

- `visible_to_users` does not imply `ranking_influence_allowed`.
- This batch grants no new ranking influence.
- Existing `ranking_influence_allowed=false` values remain false.
- Trust decisions are deterministic and backend-owned.
- The frontend may render backend-provided `trust_tier` and safe evidence
  counts, but must not infer trust from older labels or source text.
- Layer 30A is not an admin approval queue or moderation workflow.
