# Repository Maintenance Guide

## Current baseline

Job Market Intelligence is a completed React/TypeScript and FastAPI/Python application. Treat the current code, migrations, tests, and deployment configuration as the baseline; do not restart the historical MVP or layer roadmap.

Read the root [README](README.md) for product scope, then use:

- [Decision Intelligence](docs/DECISION_INTELLIGENCE.md) for recommendation and personalization semantics;
- [Engineering Guide](docs/ENGINEERING_GUIDE.md) for architecture, security, deployment, operations, and testing;
- [Local Setup](docs/LOCAL_SETUP.md) for a reproducible local environment;
- [Documentation Index](docs/README.md) to distinguish current references from development history.

Historical `LAYER_*`, architecture, orchestration, and implementation files explain how the repository evolved. They are not current instructions when they conflict with implementation or the guides above.

## Preserve these boundaries

- Keep canonical evidence, governed outputs, and user-specific personalization separate. Missing data is not observed zero; weak or stale evidence must remain visible.
- Keep the seven **By Goal** strategies deterministic and independent from **For You** Career Identity personalization.
- Apply Career Identity only with the existing consent and supported-field rules. Preserve version checks and user ownership for identity, decisions, actions, and applications.
- Do not describe illustrative portfolio records as a live employment feed or recommendation logic as a trained predictive model.
- Do not treat optional institutional, billing, integration, or provider-ingestion modules as guest-demo capabilities.

## Authentication and environments

- `local` and `test` may use the explicit verified-claims development bridge. Never enable it in a deployed mode.
- `public_guest_demo` is the live portfolio topology: backend-issued guest sessions, same-origin secure cookies, CSRF and Origin checks, isolated internal users, exact route allowlisting, quotas, ephemeral SQLite, and no Auth0 requirement.
- `public_demo` is a separate older read-only mode.
- Other configured environments may use OIDC/Auth0 and PostgreSQL. Preserve their validation without applying those requirements to public guest or local setup.

Changes that touch authentication, authorization, ownership, public route policy, session lifecycle, migrations, or seed behavior require focused regression coverage. Do not weaken deny-by-default behavior to make a test or demo flow pass.

## Change discipline

- Implement only the requested scope and preserve unrelated work.
- Prefer direct, understandable modules and deterministic behavior over speculative abstractions.
- Keep API routes thin and ownership enforcement server-side.
- Run the focused backend and frontend tests for changed behavior; include migration and repeat-seed checks when schema or seed logic changes. CI configuration is in [`.github/workflows/ci.yml`](.github/workflows/ci.yml).
- Keep local reproduction free of required paid services. Never commit secrets or generated runtime data.
- Do not assume permission to add commercial scope, live data acquisition, external services, new deployment resources, or broad administrative capabilities.

Update documentation only when the current contract changes. Prefer correcting an existing primary guide to creating another Markdown file, keep historical chronology out of current explanations, and use source links instead of duplicating code or endpoint inventories.
