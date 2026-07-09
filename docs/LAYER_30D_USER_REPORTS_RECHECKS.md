# Layer 30D User Reports and Automated Rechecks

Layer 30D adds user reports and deterministic automated recheck jobs as
feedback inputs to the existing Layer 30 trust/risk foundation.

Scope:

- 30.8 Automated Recheck Workflow
- 30.10 User Reports and Feedback Loop

User reports are signals. They do not directly change canonical truth,
rankings, `ranking_influence_allowed`, trust tiers, risk levels, routing
outcomes, source records, opportunity records, company/region facts, or
recommendation scores.

## User Reports

`user_reports` is an additive report-signal table. `POST /user-reports` creates
one report row and, when appropriate, one automated recheck job.

Supported report types:

- outdated
- incorrect
- duplicate
- spam
- misleading
- expired_opportunity
- wrong_company
- wrong_region
- suspicious_ranking
- other

Reports may be low, medium, high, or critical severity. Report statuses are
user-facing workflow states such as `received`, `queued_for_recheck`,
`recheck_pending`, `resolved_by_system`, `dismissed_low_signal`,
`escalated_exception`, and `closed`.

Critical spam or misleading reports may be marked for future exception handling,
but this is not a normal approval queue.

## Automated Recheck Jobs

`automated_recheck_jobs` is an additive job table for deterministic
recomputation. Jobs can be queued from reports or other system triggers.

Recheck execution supports:

- opportunity subjects
- data-standard candidate/fact subjects

Unsupported subjects are skipped safely. Recheck execution does not perform AI
calls or live web/source calls. It loads existing local metadata, runs the 30A
trust/evidence service and 30B risk/routing/ranking service, and may persist new
`trust_assessments` and `risk_routing_decisions` snapshots.

Recheck execution does not mutate source facts, opportunity rows, company rows,
region rows, canonical data, or ranking inputs directly.

## API and UI Exposure

Safe report/recheck status appears as `report_recheck_status` on:

- opportunity payloads
- opportunity route matched items
- user intelligence dashboard items
- trust explanation payloads
- data-standard candidate payloads where applicable

The frontend `UserReportControl` submits reports and displays backend-returned
status. It must not infer that a report changed truth, trust, risk, rankings, or
ranking influence.

Public demo remains read-only. Report submission is blocked by the existing
public-demo protection middleware, and the frontend renders a disabled state.

## Layer 30E Handoff

Layer 30E should consume critical user reports, failed/skipped rechecks,
unresolved conflicts, blocked/quarantined outcomes, and suspicious-ranking
signals as exception inputs. It must remain an exception queue, not a normal
owner/admin approval queue for routine submissions.
