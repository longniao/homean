# Homean dashboard

The dashboard is the browser workspace for reviewing, editing, confirming, and
delivering Homean showing reports. It is a Next.js 15 App Router application; capture
is handled by the Expo app in [`../mobile/README.md`](../mobile/README.md).

## Local setup

Install the dashboard dependencies and configure the backend origin:

```sh
cd dashboard
npm ci
cp .env.example .env.local
```

`.env.local` contains `NEXT_PUBLIC_API_URL`, the backend origin used by the server-side
proxy. The checked-in example points at `http://127.0.0.1:8000`; change it when the API
is running on another host or port. Do not put API keys or other provider credentials in
the dashboard environment.

Start the backend using the root setup instructions, then run the dashboard:

```sh
npm run dev
```

Open <http://localhost:3000>.

## API proxy and authentication

Browser API calls go through the same-origin `/api/backend/*` route. That route forwards
requests to `NEXT_PUBLIC_API_URL`, attaches the httpOnly access-token cookie as a bearer
token, and refreshes the access token through `/auth/refresh` when the backend returns
`401`. Login and signup use `/api/auth/login` and `/api/auth/signup`; logout is handled
by `/api/auth/logout`. The browser therefore does not need direct backend CORS access or
exposure to JWT values.

For a container or hosted dashboard, set `NEXT_PUBLIC_API_URL` to the reachable API
origin in the dashboard service environment. The API must allow the deployed dashboard
origin through its `DASHBOARD_ORIGIN` setting; see the
[infra release runbook](../infra/README.md) for the private-upload CORS check and other
release requirements.

## Local validation

Run these checks from `dashboard/` before opening a PR:

```sh
npm test
npm run typecheck
npm run lint
npm run build
```

The Docker image uses the same `npm run build` path and produces a standalone Next.js
server. The repository-level release preflight also builds the API, worker, and dashboard
images without credentials:

```sh
cd ..
bash scripts/release_preflight.sh
```

## End-to-end tests

The Playwright smoke flow uses the real API with fake storage, email, and pipeline
providers. It requires:

- Python 3.12, `uv`, and a backend environment installed with `cd ../backend && uv sync`;
- PostgreSQL reachable at `127.0.0.1:55432` (the local Compose PostgreSQL service);
- Docker Compose infrastructure running as described in the
  [infra runbook](../infra/README.md), if using the repository local environment;
- Playwright Chromium, installed with `npx playwright install chromium`.

From `dashboard/`, run:

```sh
npm run test:e2e
```

The E2E runner creates and removes an isolated database, starts the fake-provider API,
builds the dashboard, and runs the Playwright suite on port 3001. It does not call
Deepgram, Anthropic, Stripe, or an email provider.

## Related runbooks

- [Root local-development guide](../README.md)
- [Infrastructure and release runbook](../infra/README.md)
- [Mobile capture and airplane-mode runbook](../mobile/README.md)
