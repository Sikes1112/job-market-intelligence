# Frontend

The user interface is a React 19 and TypeScript application built with Vite. For the complete backend, database, seed, and frontend procedure, follow [`docs/LOCAL_SETUP.md`](../docs/LOCAL_SETUP.md).

## Development

With the local API running on `http://127.0.0.1:8000`:

```bash
npm ci
VITE_LOCAL_AUTH=true npm run dev
```

Open <http://127.0.0.1:5173/markets>. When `VITE_API_BASE_URL` is unset, the Vite development proxy forwards application API routes to port 8000. Set `VITE_DEV_API_TARGET` to use a different local API origin.

`VITE_LOCAL_AUTH=true` is restricted to development and activates the explicit local demonstration identity. Configured beta and production deployments reject it. Auth0 is optional for the local portfolio walkthrough.

## Configuration

Hosted Auth0 usage is configured with `VITE_AUTH0_DOMAIN`, `VITE_AUTH0_CLIENT_ID`, `VITE_AUTH0_AUDIENCE`, and optionally `VITE_AUTH0_REDIRECT_URI`. Hosted builds additionally enforce deployment-specific configuration in [`vite.config.ts`](vite.config.ts). These variables are not needed for local setup.

## Checks

```bash
npm run lint
npm test
npm run build
```

The frontend renders backend-owned evidence, coverage, ranking, and eligibility contracts. Recommendation scoring and authorization decisions are not reimplemented in the browser.
