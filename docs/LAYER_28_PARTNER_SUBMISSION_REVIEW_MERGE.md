# Layer 28 Partner Submission Review And Merge

Layer 28 turns validated Layer 27 partner submissions into controlled candidate
facts. Candidate facts are isolated review inputs until an internal reviewer
approves them and the controlled merge service accepts a clean or explicitly
resolved preview.

## Runtime Path

1. Partner submits a Layer 27 payload.
2. Validation checks schema, source refs, freshness, confidence, and partner
   submission permissions.
3. Stored submissions enter the separate Layer 28 lifecycle:
   `submitted`, `validation_failed`, `validation_passed`, `under_review`,
   `needs_changes`, `accepted_as_candidate`, `rejected`, `merged`,
   `superseded`, `withdrawn`.
4. Candidate creation requires stored `validation_status=validated` and
   `review_lifecycle_state=validation_passed`; it then transitions the
   submission to `accepted_as_candidate`.
5. Reviewer decisions append audit-linked records. Supported actions are
   `approve_candidate`, `reject_candidate`, `request_changes`,
   `mark_duplicate`, `mark_low_confidence`, `escalate`,
   `resolve_conflicts`, and `merge_to_canonical`.
6. Merge preview checks candidate state, submission lifecycle, provenance,
   conflicts, and duplicate merge records without mutating canonical tables.
7. Merge execution writes canonical rows only through
   `DataStandardsService.merge_candidate_fact`, binds provenance, creates an
   admin audit log, and emits invalidation directives where supported.

## Safety Controls

- Partner submissions, candidates, reviews, and merges remain separate from
  canonical truth until controlled merge.
- Partner permissions constrain accepted record types; trust tier does not
  bypass permissions, review, merge, or ranking gates.
- Review decisions require reviewer ID, timestamp, reason, notes, source basis,
  and before/after diff when the action changes or resolves state.
- Review decisions create admin audit events and merge records bind the latest
  review decision ID.
- Merge provenance binds partner submission ID, candidate ID, review decision
  ID, source refs, collected/observed timestamps, confidence, freshness, and
  license/terms category.
- License/terms category must come from source metadata or reviewer source
  basis; hardcoded merge defaults are not used.
- Conflicts cover duplicate keys, stale source, lower-trust source conflict,
  canonical value mismatch, missing dependencies, and numeric mismatch.
- Conflicts block merge until a reviewer records `resolved_conflict_codes`.
- `ranking_influence_allowed` remains false on Layer 28 rows. Scoring
  repositories exclude partner-origin merged canonical facts unless a future
  stricter layer explicitly allows ranking influence.
- Public-demo mode denies all Layer 27/28 mutation routes before auth.
- Non-demo candidate creation, review, and preview routes require data-review
  admin access; merge execution requires admin mutation access.

## API Surface

- Public metadata:
  - `GET /data-standards/definitions`
  - `GET /data-standards/partner-schema`
  - `GET /data-standards/partners`
  - `GET /data-standards/quality-labels`
  - `GET /data-standards/governance-framework`
- Internal/admin review:
  - `POST /data-standards/partner-submissions/{submission_id}/candidates`
  - `GET /data-standards/partner-submissions/{submission_id}/candidates`
  - `GET /data-standards/review/candidates`
  - `GET /data-standards/candidates/{candidate_fact_id}`
  - `POST /data-standards/candidates/{candidate_fact_id}/review`
  - `POST /data-standards/candidates/{candidate_fact_id}/merge-preview`
  - `POST /data-standards/candidates/{candidate_fact_id}/merge`

No frontend admin portal is claimed in this layer.

## Known Limitations

- Ranking influence is intentionally always false for normal Layer 28 partner
  submissions. Enabling it requires a future stricter review layer.
- The controlled merge service is authoritative for Layer 28 candidate-to-
  canonical writes, but other pre-existing canonical services can still write
  their own domains.
- The repository worktree still contains substantial unrelated staged and
  untracked layer work; lock review should account for that merge-risk boundary.
