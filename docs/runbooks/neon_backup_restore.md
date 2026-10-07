# Neon Backup / Restore Runbook

## Purpose

This runbook defines how to recover the production Neon database after data
loss, a destructive or failed migration, accidental deletes, corruption, bad
imports/seeds, or a deploy that causes database side effects.

## Scope

Covered:

- Neon production database backup and restore procedure.
- Staging or restored-branch validation before production promotion.
- Alembic migration compatibility checks.
- Verification through `/ready`, `/health`, and app smoke checks.

Not covered:

- Full disaster recovery for every service.
- Frontend rollback.
- Authentication or user recovery.
- Multi-region high availability design.

## Backup Policy

- Production data should rely on Neon-managed backups and point-in-time restore
  (PITR) when available for the active Neon plan.
- Verify the active Neon plan retention window in Neon project settings. Do not
  assume restore coverage without checking the dashboard/project settings.
- Confirm PITR availability before production launch and before high-risk
  migrations.
- Review backup and restore-point coverage before any major schema migration.
- For major migrations, define a restore point/checkpoint strategy before the
  migration is applied.
- Existing production databases without Alembic history require a separate,
  explicit migration-adoption plan. Do not use local/demo schema stamping for
  production adoption.
- `alembic stamp` is not a general failed-migration recovery command. Use it
  only when schema equivalence has been independently established and the
  operator can explain why Alembic history, rather than schema structure, is the
  only missing state.
- Store `DATABASE_URL` and other secrets only in deployment platform secret
  storage. Do not commit connection strings, backup credentials, or exported
  data.
- CI validates migrations against SQLite only. CI does not validate Neon backup
  coverage or production restore readiness.

## Restore Triggers

Consider a restore when any of these occur:

- Destructive migration or migration rollback failure.
- Accidental production data deletion.
- Corrupted production data.
- Failed deploy with database side effects.
- Compromised data integrity.
- Bad seed/import into production.
- The app cannot pass `/ready` because the database is unavailable or
  inconsistent.

## Roles / Ownership

- Restore owner / incident lead: coordinates the incident, assigns roles, owns
  the restore decision, and communicates status.
- App operator / deploy owner: pauses or redirects app traffic where possible,
  updates deployment secrets, and performs deploy/smoke checks.
- Database owner: operates Neon restore/branching, verifies database target and
  Alembic state, and confirms backup coverage.
- Verifier: runs readiness, smoke, and data integrity checks before promotion
  and after restore.

Use role placeholders until named production owners are assigned.

## Pre-Restore Checklist

- Identify the incident start time, detection time, and likely safe restore
  target.
- Stop, pause, or reduce write traffic if possible.
- Preserve logs, request IDs, deploy IDs, and migration output.
- Capture the current production `DATABASE_URL` target identity without exposing
  the secret value.
- Confirm the latest successful deployment and expected Alembic revision.
- Confirm whether the database already has Alembic history. If it does not,
  stop and use a dedicated production migration-adoption procedure before
  attempting promotion. Do not stamp an arbitrary production schema to `head`.
- If the database is reachable, inspect the current Alembic revision:

  ```bash
  APP_ENV=prod DATABASE_URL=<production-url> python -m alembic current
  ```

- Decide whether to restore by point in time, backup snapshot, branch, or
  restored database.
- Communicate expected risk, possible data loss window, and validation plan.

## Restore Process

### A. Triage

1. Confirm the incident is database-related and identify the affected Neon
   project, branch, and database.
2. Confirm whether production writes should be paused before restore work
   continues.
3. Determine the latest acceptable recovery point using logs, deploy times,
   request IDs, and migration timestamps.

### B. Create Restore Target

1. In Neon, create a restore branch or restored database from the selected point
   in time or backup snapshot.
2. Verify the selected project, branch, database, and restore timestamp before
   using the restored target.
3. Keep production pointed at the current database until the restored target is
   validated.

### C. Validate Before Promotion

Point staging or a one-off validation environment at the restored database.
Never run destructive tests against production.

```bash
APP_ENV=staging DATABASE_URL=<restored-non-prod-url> python -m alembic current
APP_ENV=staging DATABASE_URL=<restored-non-prod-url> python -m alembic upgrade head
```

The `upgrade head` check verifies that the restored database is compatible with
the current migration set. If it would apply unexpected migrations, stop and
confirm the intended application version and Alembic revision.

### D. Verify App Readiness

Run the backend against the restored non-production database and verify:

```bash
curl -fsS <staging-backend-url>/health
curl -fsS <staging-backend-url>/ready
```

`/health` confirms the HTTP process is alive. `/ready` confirms configuration
validity and database reachability. `/ready` must not require seeded demo data.

### E. Run Smoke Checks

Use non-destructive smoke checks against the staging/restored target:

```bash
curl -fsS <staging-backend-url>/regions
curl -fsS <staging-backend-url>/regions/greater_boston
curl -fsS "<staging-backend-url>/compare?region_a=greater_boston&region_b=greater_sf"
```

If appropriate, run backend tests against only the restored non-production
target:

```bash
APP_ENV=test DATABASE_URL=<restored-non-prod-url> python -m pytest
```

Do not run tests that mutate or destroy data against production.

### F. Promote or Swap Production

Only after validation passes:

1. Record the chosen restore target, restore timestamp, and expected data loss
   window.
2. Update the production deployment platform `DATABASE_URL` secret to the
   validated restored target, or promote/swap the Neon branch according to the
   selected Neon workflow.
3. Redeploy or restart the backend if needed so it picks up the new secret.
4. Verify production `/health` and `/ready`.
5. Run production smoke checks that do not mutate data.
6. Monitor logs and request IDs for elevated errors.

## Restore Validation Checklist

- `python -m alembic current` reports the expected revision.
- `python -m alembic upgrade head` succeeds or has an explained no-op result.
- `/health` returns 200.
- `/ready` returns ready and does not expose `DATABASE_URL` or secrets.
- Smoke endpoints return expected safe responses.
- Logs show normal request behavior with request IDs.
- No stack traces, SQL internals, or secrets are exposed to users.

## Rollback / Abort Criteria

Do not promote the restored database if any of these are true:

- Alembic revision mismatch cannot be explained.
- `/ready` fails.
- Smoke checks fail.
- The restored database is older than the acceptable recovery point.
- Data integrity checks fail.
- The wrong Neon project, branch, database, or timestamp was selected.
- Validation would require destructive testing on production.

## Post-Restore Checklist

- Confirm production `/ready` passes after promotion.
- Confirm app smoke endpoints work.
- Confirm logs show normal request behavior and include request IDs.
- Confirm no `DATABASE_URL`, credentials, or secrets leaked in logs or responses.
- Document the incident timeline.
- Document the chosen restore point and promotion time.
- Document the data loss window, if any.
- Create follow-up remediation items.
- Rotate secrets if compromise is suspected.
- Record the restore in the restore drill/incident history.

## Testing Cadence

- Test restore before major production launch.
- Before production launch, perform an isolated Neon/PostgreSQL restore into a
  separate branch/database and verify application compatibility against that
  restored target.
- Test restore before high-risk migrations.
- Periodically test restore using a staging environment or restored Neon branch.
- Record the last successful restore drill date, operator, restore source, and
  validation result.

Last successful restore drill:

- Date: `2026-09-02`
- Operator: `Layer 39B local verification`
- Restore target: `isolated SQLite backup/restore target under pytest tmp_path`
- Result: `partial production-equivalence proof; representative Layer 35-39A
  records, FK integrity, Alembic revision, and app readiness verified locally.
  Neon/PostgreSQL restored-branch proof remains required before external
  production launch.`

## Layer 2 Slice 2.8 Completion

This runbook satisfies Layer 2 Slice 2.8 by documenting:

- Backup policy.
- Restore process.
- Restore test process.
- Restore ownership and responsibilities.
