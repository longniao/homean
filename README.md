# Kawu

Kawu is an AI showing-report tool for real-estate buyer's agents. This repository contains the FastAPI backend, Next.js dashboard, Expo mobile capture app, and local development infrastructure.

## Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Node.js 22 and npm
- Docker with Docker Compose

PDF rendering uses WeasyPrint. The backend container includes its native libraries. On
macOS, install the local native dependencies with `brew install pango`; if Homebrew is
under `/opt/homebrew`, export `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` when running
the API or renderer tests locally.

## Local setup

Create the local environment file:

```sh
cp .env.example .env
```

For host-based API development, start PostgreSQL, Redis, MinIO, the one-time `kawu-media`
bucket initializer, and the Celery pipeline worker:

```sh
docker compose --env-file .env -f infra/docker-compose.yml up -d \
  postgres redis minio minio-bucket-init worker
```

Alternatively, run the infrastructure, worker, and API entirely in containers:

```sh
docker compose --env-file .env -f infra/docker-compose.yml up -d --build
```

The containerized API binds port 8000, so do not also start the host-based Uvicorn command
below when using this option.

MinIO is available at `http://localhost:9000`; its console is at `http://localhost:9001`.

## Backend

```sh
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

The API runs at `http://localhost:8000`; its health endpoint is `http://localhost:8000/health`.

To run the Celery worker directly instead of through Docker Compose, open another
terminal with the same environment and run:

```sh
cd backend
uv run celery -A app.pipeline.celery_app:celery_app worker --loglevel=info
```

Run backend checks with:

```sh
uv run ruff check .
uv run pytest
```

## Dashboard

In a second terminal:

```sh
cd dashboard
npm ci
npm run dev
```

The dashboard runs at `http://localhost:3000`.

Run dashboard checks with:

```sh
npm test
npm run typecheck
npm run lint
npm run build
npm run test:e2e
```

The end-to-end test requires the local PostgreSQL service and a Playwright Chromium
installation (`npx playwright install chromium`).

## Mobile capture app

In a third terminal:

```sh
cd mobile
cp .env.example .env
npm ci
npm start
```

Set `EXPO_PUBLIC_API_URL` in `mobile/.env` to an API URL reachable from the device. See
`mobile/README.md` for development-build requirements and the physical-device airplane-mode
acceptance test.

Run mobile checks with:

```sh
npm test
npm run typecheck
npm run lint
```
