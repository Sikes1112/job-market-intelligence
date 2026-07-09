# Layer 30B Risk Routing + Ranking Influence Protection

Layer 30B implements:

- 30.3 Autonomous Risk Routing
- 30.6 Ranking Influence Automation

It builds on Layer 30A trust/evidence results. It does not add an admin
approval workflow, manual moderation queue, exception queue, automated recheck
jobs, user reports, frontend trust inference, or canonical truth mutation.

## Contracts

The shared contracts live in `backend/trust/schemas.py`:

- `RiskLevel`
- `RoutingOutcome`
- `RankingInfluenceDecision`
- `RankingInfluenceReasonCode`
- `RiskRoutingReasonCode`
- `RiskClassificationResult`
- `RankingInfluencePolicyResult`
- `RiskRoutingDecisionResult`

The routing decision version is `30B.1` and the decision source is
`deterministic_layer_30b`.

## Risk Routing

`RiskClassifier` and `RiskRoutingService` classify existing 30A assessments
deterministically:

- low risk remains visible and may still be non-ranking
- medium risk remains visible with warnings
- high risk requires more evidence, automated recheck, or quarantine markers
- critical risk is blocked or quarantined
- unknown risk is not routed

Risk decisions are labels and gates. They do not mutate submissions, canonical
truth, review status, rankings, or visibility state.

## Ranking Influence

`RankingInfluencePolicy` is default-deny. Ranking influence is allowed only for
trusted or verified assessments that pass deterministic evidence checks for
source presence, allowed source, freshness, confidence, no conflict, no duplicate
risk, non-self-promotional source, corroboration, and allowed claim type.

Automatic denial includes partner-submitted or partner-origin evidence, stale
sources, low confidence, conflicts, quarantine, blocked signals,
ranking-ineligible/not-assessed tiers, missing sources, source policy failures,
duplicate risk, self-promotional sources, missing evidence, public-demo
restrictions, and legacy unassessed data without an explicit allow path.

## Persistence

`risk_routing_decisions` is an additive snapshot table. Routing computation
itself remains pure/read-only; callers must explicitly persist a decision
through `TrustAssessmentRepository.add_routing_decision`.

## Ranking Gate Compatibility

`backend/data_standards/ranking_gate.py` now consults explicit Layer 30B routing
decisions when present. Existing platform-owned canonical facts with no Layer
28/30 record can remain eligible only through the documented
`allow_legacy_unassessed=True` compatibility flag. New submitted/imported/manual
canonical writes should either persist an explicit Layer 30B allow decision or
call the gate with `allow_legacy_unassessed=False`.

## Safety Boundaries

- `visible_to_users` does not imply `ranking_influence_allowed`.
- Partner-submitted items are visible-only unless later deterministic evidence
  rules explicitly change that through a safe backend decision.
- `include_unverified=True` affects visibility only and does not grant ranking
  advantage.
- Frontend code renders backend-provided risk/routing/ranking fields only.
- No admin approval queue or canonical truth mutation was added.
