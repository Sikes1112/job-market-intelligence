# Layer 28 Closeout

Layer 28 adds governed review and controlled canonical merge for Layer 27
partner submissions.

Implemented:

- Submission lifecycle states and guarded transitions separate from validation,
  candidates, and canonical truth.
- Validation-to-candidate creation guarded by stored validation and lifecycle
  state.
- Partner submission permission enforcement before candidate creation.
- Candidate facts carrying partner trust context and initial provenance.
- Audit-linked reviewer decision records for approve, reject, changes,
  duplicate, low-confidence, escalation, conflict resolution, and merge actions.
- Provenance completeness enforcement, including license/terms category and
  review decision binding.
- Merge preview with merge-blocking conflict detection and explicit resolution.
- Controlled merge service for supported canonical targets.
- Provenance binding into source refs, source observations, fact links, merge
  records, and admin audit logs.
- Existing invalidation hooks where supported by current event rules.
- Ranking/scoring exclusion for partner-origin merged facts while
  `ranking_influence_allowed=false`.
- Admin authorization on candidate creation, review, preview, and merge
  mutation paths.
- Public-demo protections for Layer 27/28 mutation routes.

Verified path:

`partner submission -> validation -> candidate creation -> reviewer decision -> provenance binding -> merge preview -> controlled merge service -> canonical write -> audit log -> ranking influence remains false`

Non-goals:

- No automatic promotion from validation to canonical truth.
- No public partner portal or frontend admin portal.
- No scoring, ranking, benchmark, recommendation, or predictive signal mutation
  from normal Layer 28 partner submissions.
- No hidden paid, trust-tier, or partner boost.
- No public-demo write access.

Lock caveat:

- The worktree still contains substantial unrelated staged and untracked layer
  work, including untracked data standards files. That is a repository hygiene
  and merge-confidence risk outside Layer 28 behavior.
