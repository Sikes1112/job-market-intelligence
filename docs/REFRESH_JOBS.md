# Refresh Jobs Foundation

Layer 8 defines the refresh job vocabulary, cadence posture, queue decision,
process boundaries, and status/observability fields. It does not move routes,
make external network calls in tests, or change auth, user, scoring, ingestion,
output, or personalization behavior.

## Queue Decision

The selected production posture is **RQ + Redis**:

- Redis is the broker.
- RQ workers run as external worker processes.
- The current database-backed `QueueService` remains useful for local
  admission/dedupe semantics and tests, but it is not the production broker.
- The RQ adapter imports broker clients lazily. API import/startup and normal
  tests do not require `rq`, `redis`, or a live Redis broker.
- The Python `rq`/`redis` dependencies are deferred from the base install in
  this batch. Production runtime must install them before using the RQ adapter.

Kafka is explicitly rejected for this layer. Refresh jobs need named task
queues, retries, dedupe/admission metadata, and separate workers. Kafka would
add streaming-platform concerns such as topics, offsets, consumer groups, and
operational overhead before the product needs them.

## Job Types

- `company_universe_refresh`
- `presence_refresh`
- `hiring_refresh`
- `entry_level_refresh`
- `score_recompute`
- `output_rebuild`
- `audit_run`

These refresh names do not replace existing orchestration handler names. They
are the production refresh contract vocabulary that future queue adapters can
map onto existing authoritative handlers.

## Cadence Classes

- Hiring refresh: frequent.
- Entry-level refresh: seasonal, frequent during recruiting windows.
- Presence refresh: slower.
- Company universe refresh: medium.
- Score recompute: after canonical data changes.
- Output rebuild: after score or canonical data changes.
- Audit run: scheduled or manual, matching the existing audit posture.

The cadence map is deterministic metadata. It does not decide source freshness
or execute scheduling.

## Process Boundaries

Web/API process:

- serves request paths
- reads prepared output and metadata through the existing API/output services
- must not execute refresh handlers directly
- must not require Redis/RQ at import or startup

Scheduler process:

- builds deterministic cadence-driven refresh requests from `backend.refresh.cadence`
- enqueues planned jobs through the queue adapter
- must not call refresh handlers or perform heavy data refresh work

Worker process:

- claims queued refresh jobs
- dispatches through `backend.refresh.handlers`
- records start, finish, duration, status, failure reason, retry count, and
  source-version/source-bundle references where present
- may execute real handlers in later batches once each handler is safely wired

The local in-memory queue adapter is for tests and local smoke checks only. It
is not durable, distributed, or production-ready.

## Process Entrypoints

Run the production worker posture once RQ/Redis dependencies and Redis are
available:

```bash
REDIS_URL=redis://localhost:6379/0 python -m scripts.run_refresh_worker
```

Run the scheduler process once to enqueue cadence-driven jobs:

```bash
REDIS_URL=redis://localhost:6379/0 python -m scripts.run_refresh_scheduler
```

For local smoke checks that do not use Redis:

```bash
REFRESH_QUEUE_ADAPTER=local python -m scripts.run_refresh_scheduler
REFRESH_QUEUE_ADAPTER=local python -m scripts.run_refresh_worker --max-jobs 1
```

The local adapter has process-local memory, so it is not a substitute for the
production RQ/Redis broker.

## Observability Contract

Refresh job status records support:

- stable job key and optional broker/job id
- job type
- target scope and optional target id
- status
- enqueue, start, and finish timestamps
- duration
- failure reason
- retry count
- source version refs and source bundle reference
- stale output count
- summary helpers for last successful run and stale output count

Refresh contracts require source-version and source-bundle preservation for
jobs that write refreshed data, recompute derived scores, or rebuild outputs.
The refresh layer only records that requirement; existing ingestion,
provenance, scoring, and output writers remain authoritative for the actual
data and output semantics.

## Output Cache Storage

Layer 8 stores region, company, and comparison output payloads on the existing
`OutputMetadata` row in `cached_payload`. The row remains the queryable output
index and now also carries cache lifecycle fields:

- `cached_payload`
- `source_version_bundle`
- `source_version_refs`
- `source_bundle_ref`
- `invalidated_at`
- `rebuilt_at`
- `stale_reason`
- `rebuild_job_key`
- latest rebuild status/failure reason

This is a DB-backed JSON cache that works with local SQLite and maps cleanly to
Postgres JSON/JSONB. `artifact_uri` remains available for a future object-store
backend, but Layer 8 does not introduce object storage.

## Invalidation Lifecycle

Output invalidation marks fresh output cache rows `stale`, records the
staleness reason and invalidation time, preserves source-version refs and the
source-bundle ref, then enqueues an `output_rebuild` refresh job through the
Batch 2 queue abstraction.

Duplicate active rebuild jobs are suppressed by stable refresh job keys. Normal
tests use the local in-memory queue adapter; Redis/RQ remains the production
posture and is not required for API startup or test runs.

## Stale Repair Lifecycle

The `output_rebuild` handler can be wired with the existing
`OutputAssemblyService` and `OutputCacheRepository`. It rebuilds stale region,
company, and comparison outputs through the existing output builders, updates
`cached_payload`, clears stale repair fields on success, and records explicit
failure reasons on failure.

The web/API process never executes the rebuild handler. API read paths prefer a
cached payload when one exists, including stale cached payloads with stale
metadata/warnings. If no cached payload exists, the current live assembly path
remains as a fallback only and does not write cache rows from request handling.

## Deferred

Remaining work after Layer 8 includes durable refresh job status storage,
concrete source-version dependency resolution, retry/backoff runtime, broker
deployment settings, production dependency install for `rq`/`redis`, and any
future object-storage backend for large payloads.
