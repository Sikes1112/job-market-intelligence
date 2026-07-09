# Layer 30C Trust Explanations

Layer 30C adds user-facing explanations and labels on top of the deterministic
Layer 30A trust/evidence results and Layer 30B risk/routing/ranking decisions.

Scope:

- 30.9 Trust Explanation API
- 30.5 User-Facing Trust Labels

The frontend renders backend-provided explanation payloads. It does not infer
trust tier, risk level, routing outcome, or ranking influence from legacy
confidence, source, partner, warning, or trust-label fields.

## Backend Contracts

`TrustExplanationService` converts existing 30A/30B results into safe user
copy:

- trust tier label and summary
- risk label and summary
- routing label and summary
- ranking influence label and reason
- evidence requirements met, missing, and failed
- user-facing warnings
- last checked / decided timestamps when available

The copy is deterministic. No AI calls, live source calls, admin approval
workflow, review queue, or canonical truth mutation is involved.

The read-only endpoint is:

```text
GET /trust/explanation?subject_type=...&subject_id=...
```

Missing subjects return a safe `not_assessed` explanation. Embedded explanation
blocks are also exposed additively on opportunity payloads, data-standard
candidate/quality-label payloads, and user intelligence dashboard opportunity
items.

## User-Facing Labels

Trust labels include:

- trusted -> Trusted source
- verified -> Verified
- partner_submitted -> Partner-submitted
- unverified_visible -> Not independently verified
- low_confidence -> Low confidence
- conflicting -> Conflicting source detected
- stale -> Stale source
- quarantined -> Quarantined
- ranking_ineligible -> Excluded from rankings
- blocked -> Blocked
- not_assessed -> Not assessed

Risk, routing, and ranking labels are derived from the 30B enum values and
reason codes. Ranking copy must never say an item is used in rankings unless the
backend explanation has `ranking_influence_allowed=true`.

## Safety Rules

- `visible_to_users` does not imply `ranking_influence_allowed`.
- Layer 30C grants no new ranking influence.
- Public-demo responses can show safe trust labels and ranking-excluded copy.
- Public-demo responses must not expose internal review notes, reviewer
  identity, admin-only fields, or exception internals.
- Explanation payloads are read-only and do not mutate submissions, canonical
  facts, review status, rankings, or routing decisions.

## Frontend Rendering

Reusable components in `frontend/src/TrustExplanation.tsx` render only the
backend-provided explanation object:

- `TrustBadge`
- `RiskBadge`
- `RankingInfluenceBadge`
- `RiskWarningCard`
- `EvidenceExplanationPanel`
- `TrustExplanationPanel`

Null or missing explanations render honest unavailable states. They do not map
old fields into new trust/risk/ranking decisions.

## Layer 30D Handoff

Automated recheck jobs and user reports should consume the same 30A/30B/30C
fields. Reports may increase risk or trigger recheck in 30D, but must not
directly mutate canonical truth or ranking influence.
