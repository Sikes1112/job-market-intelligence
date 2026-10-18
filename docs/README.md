# Documentation

The root [README](../README.md) is the project overview. Use the current guides below for setup and technical investigation; the remaining documents preserve specialized operations detail or development history.

## Start here

- [`LOCAL_SETUP.md`](LOCAL_SETUP.md) — complete local installation, migration, seed, startup, verification, and troubleshooting procedure.
- [`ENGINEERING_GUIDE.md`](ENGINEERING_GUIDE.md) — implemented architecture, subsystem boundaries, representative request paths, trade-offs, source, and tests.
- [`DECISION_INTELLIGENCE.md`](DECISION_INTELLIGENCE.md) — goal-based ranking, authenticated Career Identity discovery, evidence semantics, and evaluation limits.

## Supporting evidence and specialized references

- [`evaluation/PORTFOLIO_INTELLIGENCE_EVALUATION.md`](evaluation/PORTFOLIO_INTELLIGENCE_EVALUATION.md) — executable golden behaviors and the limits of those checks.
- [`BROWSER_ACCEPTANCE_REPORT.md`](BROWSER_ACCEPTANCE_REPORT.md) — completed browser-based portfolio acceptance evidence.
- [`WALKTHROUGH_CAPTURE.md`](WALKTHROUGH_CAPTURE.md) — optional sequence for recording the running local application; no recording is bundled.
- [`API_SURFACES.md`](API_SURFACES.md) — comprehensive API inventory.
- [`DATA_SOURCE_POLICY.md`](DATA_SOURCE_POLICY.md) and [`CANONICAL_GEOGRAPHY.md`](CANONICAL_GEOGRAPHY.md) — source-governance and geographic-identity references.
- [`PUBLIC_DEMO_ENVIRONMENT.md`](PUBLIC_DEMO_ENVIRONMENT.md) — hosted public-demo restrictions; not required for local use.

## Historical implementation records

Files named `LAYER_*`, closeout reports, and material under [`implementation/`](implementation/) document the system's development and individual subsystem deliveries. They are retained for auditability, but they are not the recommended description of the current application.

The following are specifically historical or superseded:

- [`PRODUCT_OVERVIEW.md`](PRODUCT_OVERVIEW.md) — early product framing, superseded by the root README.
- [`MVP_SCOPE.md`](MVP_SCOPE.md) — original MVP scope.
- [`architecture/ENGINEERING_IMPLEMENTATION_BLUEPRINT.md`](architecture/ENGINEERING_IMPLEMENTATION_BLUEPRINT.md) — a pre-implementation distributed-infrastructure blueprint. Its queues, workers, caches, and object storage are not required by the local application.
- Other documents under [`architecture/`](architecture/) are design-stage orchestration proposals unless a current guide explicitly cites an implemented path.

When historical documentation conflicts with current source, tests, migrations, or the three start-here guides, the current implementation is authoritative.
