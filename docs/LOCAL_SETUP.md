# Local Setup

This is the authoritative procedure for running the complete portfolio application locally. It uses SQLite and bundled demonstration data; Auth0, PostgreSQL, paid APIs, external AI services, and network data providers are optional and not required.

## Requirements

- Python 3.11 (`.python-version`)
- Node.js 22 (`.nvmrc`)
- npm 10 or newer

Run all backend commands from the repository root. On macOS or Linux, the commands below use a POSIX shell.

## 1. Install dependencies

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt -c requirements.lock

cd frontend
npm ci
cd ..
```

`requirements.lock` and `frontend/package-lock.json` contain the verified dependency versions. `requirements-dev.txt` includes the runtime dependencies plus pytest, HTTPX, and Ruff.

## 2. Initialize SQLite and seed the portfolio fixture

```bash
APP_ENV=local DATABASE_URL="sqlite:///./demo.db" \
  python -m alembic upgrade head

APP_ENV=local python -m scripts.seed_demo \
  --database-url "sqlite:///./demo.db" \
  --portfolio --demo-as-of 2026-10-17
```

The explicit date reproduces the checked-in screenshot and evaluation context. Opportunities are still labeled with simulated demonstration freshness rather than live-employer freshness. The seed is idempotent and applies migrations internally as a safety check, so rerunning it does not create duplicate logical records.

## 3. Start the backend

```bash
APP_ENV=local DATABASE_URL="sqlite:///./demo.db" \
  .venv/bin/uvicorn backend.api.app:app --reload
```

The API runs at <http://127.0.0.1:8000>. Useful readiness checks are <http://127.0.0.1:8000/health> and <http://127.0.0.1:8000/ready>.

## 4. Start the frontend

In a second terminal:

```bash
cd frontend
VITE_LOCAL_AUTH=true npm run dev
```

Open <http://127.0.0.1:5173/markets>. Leave `VITE_API_BASE_URL` unset for local development; Vite proxies API requests to `http://127.0.0.1:8000`.

`VITE_LOCAL_AUTH=true` enables the explicit `local|explorer` development identity used by the portfolio seed. This makes the synthetic Career Identity and saved decision available for the walkthrough. The frontend enables this mode only during development, configured beta and production deployments reject it, and the backend accepts its verified claims only in `local` or `test` environments.

## Suggested walkthrough

1. Open **Explore** to search markets and inspect employer evidence.
2. Use **Compare** to evaluate selected geographic alternatives.
3. Filter **Opportunities** by market, role, type, and work arrangement.
4. In **Recommendations**, compare the authenticated **For You** view with the public **By Goal** strategies.
5. Open **Career Identity** and **Decisions** to inspect the seeded profile, alternatives, and next actions.

All bundled market and opportunity records are illustrative. The UI preserves the relevant synthetic-data, confidence, and coverage disclosures.

## Verification

Backend lint and tests:

```bash
source .venv/bin/activate
python -m ruff check alembic backend scripts tests
APP_ENV=test python -m pytest -q
```

Frontend lint, tests, and production build:

```bash
cd frontend
npm run lint
npm test
npm run build
```

High-signal portfolio behavior:

```bash
APP_ENV=test .venv/bin/pytest -q \
  tests/integration/test_portfolio_demo_batch1.py
```

Fresh migration and repeat-seed smoke check:

```bash
APP_ENV=local DATABASE_URL="sqlite:////tmp/jmi-portfolio-smoke.db" \
  .venv/bin/alembic upgrade head

APP_ENV=local DATABASE_URL="sqlite:////tmp/jmi-portfolio-smoke.db" \
  .venv/bin/python -m scripts.seed_demo \
  --portfolio --demo-as-of 2026-10-17 --quiet

APP_ENV=local DATABASE_URL="sqlite:////tmp/jmi-portfolio-smoke.db" \
  .venv/bin/python -m scripts.seed_demo \
  --portfolio --demo-as-of 2026-10-17 --quiet
```

The GitHub Actions workflow runs the same backend lint/tests, frontend lint/tests/build, migration, and repeat-seed checks.

## Troubleshooting

- **`python3.11` is unavailable:** install Python 3.11 or use a version manager that honors `.python-version`.
- **The frontend cannot reach the API:** confirm FastAPI is listening on port 8000 and that `VITE_API_BASE_URL` is unset. To use another backend port, set `VITE_DEV_API_TARGET` when starting Vite.
- **Personalized pages appear empty:** confirm the seed used `--portfolio` and Vite was started with `VITE_LOCAL_AUTH=true`.
- **The schema is behind:** rerun `APP_ENV=local DATABASE_URL="sqlite:///./demo.db" .venv/bin/alembic upgrade head`, then rerun the idempotent portfolio seed.
- **Ports 5173 or 8000 are occupied:** stop the conflicting local process or pass an explicit port to Vite or Uvicorn; if Vite changes ports, use the URL it prints.

Auth0 and PostgreSQL configuration is intentionally outside the local portfolio path. Deployment-oriented material remains in the specialized operations documentation indexed from [`docs/README.md`](README.md).
