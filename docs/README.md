# Documentation

The root [README](../README.md) is the product entrance. The guides below describe the current application; historical files remain available for implementation provenance, not as present-day operating instructions.

## Current guides

- [Decision Intelligence](DECISION_INTELLIGENCE.md) — By Goal versus For You, deterministic ranking, consent, evidence, uncertainty, and evaluation limits.
- [Engineering Guide](ENGINEERING_GUIDE.md) — architecture, source map, authentication and guest isolation, deployment, operations, testing, and trade-offs.
- [Local Setup](LOCAL_SETUP.md) — installation, SQLite migration and seed, startup, verification, and troubleshooting.
- [Portfolio Intelligence Evaluation](evaluation/PORTFOLIO_INTELLIGENCE_EVALUATION.md) — reproducible golden cases and the limits of that evidence.

## Specialist references

- [Data Model](DATA_MODEL.md) — implemented domain and persistence model.
- [Data Source Policy](DATA_SOURCE_POLICY.md) — source eligibility, provenance, freshness, missingness, and governance.
- [Canonical Geography](CANONICAL_GEOGRAPHY.md) and the [geography dataset notes](../data/geography/README.md) — identity rules, geometry source, and transformation.
- [Frontend notes](../frontend/README.md) — package-level development commands and Vite configuration.

Security, deployment, testing, and operations questions start in the [Engineering Guide](ENGINEERING_GUIDE.md), which links to the relevant implementation and tests.

## Historical material

Files named `LAYER_*`, closeout reports, implementation prompts, and material under [`implementation/`](implementation/) record completed development. Earlier architecture proposals, the original MVP and slice plans, cumulative API narratives, Auth0-only or controlled-beta topology, the old read-only `public_demo` design, and browser acceptance reports are also point-in-time references.

They are intentionally retained without being part of the current reading path. When a historical record conflicts with current source, tests, migrations, deployment configuration, or the current guides above, use the current evidence.
