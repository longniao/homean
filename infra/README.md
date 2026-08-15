# Homean production operations

Render is the documented single-region deployment target. The Blueprint in
`infra/render.yaml` runs the API, Celery worker, Next.js dashboard, Postgres, and Redis.
Set S3/MinIO, SMTP, and Stripe secrets in the Render environment; no credentials belong
in the repository. The Blueprint derives the API and dashboard public URLs from Render's
own `RENDER_EXTERNAL_URL` values, pins PostgreSQL 16, blocks public database connections,
and waits for repository checks to pass before automatically deploying a commit.

Release sequence:

1. Deploy the API image.
2. Run `uv run alembic upgrade head` as the release migration step.
3. Start or roll the worker and dashboard after the migration succeeds.

## Repository preflight

Before a release, run the credential-free repository preflight from the repository
root:

```sh
cd /path/to/homean
(cd backend && uv sync --frozen)
bash scripts/release_preflight.sh
```

It checks that the Alembic graph has exactly one expected head, validates the Render
Blueprint structure and every Docker service's local context/Dockerfile path, validates
the local Compose file, and builds the API, worker, and dashboard images without
pushing or calling Render or any application provider. The dashboard context check
also ensures `.env` and `.env.*` files stay out of the image build context while the
safe `.env.example` remains available. The preflight is run by the
`release-preflight` GitHub Actions job.

The API and worker use the canonical Dockerfiles in `backend/` with `backend/` as the
build context. Keep those paths aligned in `infra/docker-compose.yml` and
`infra/render.yaml`; there are no release Dockerfiles under `infra/`.

## Staging acceptance gate

Do not promote staging to production until every item below has an owner and recorded
result. Use the executable [pilot acceptance checklist](../docs/Homean_Pilot_Acceptance_Checklist.md)
to record the result, evidence, and approval for each gate:

1. Confirm CI is green for backend, dashboard, mobile, dependency audit, and Playwright.
2. Validate the Blueprint, provision secrets, deploy, and confirm both `/health` and
   `/ready` return `200`; `/ready` must report database, Redis, and S3 as `ok`.
3. Sign up a new workspace and verify the 14-day trial, Checkout redirect, signed Stripe
   webhook activation, duplicate-event idempotency, and customer-portal redirect.
4. Upload one real English showing recording, confirm Deepgram and Anthropic processing,
   and review the evidence links. From the repository root, replace the visibly invalid
   placeholder with the staging Visit UUID, then run:
   ```sh
   cd backend
   VISIT_ID='REPLACE_WITH_STAGING_VISIT_UUID'
   uv run python scripts/ai_cost_report.py --visit-id "$VISIT_ID"
   ```
   Require the output to identify that same Visit UUID and contain its recorded token
   usage and estimated cost result.
5. Edit and explicitly confirm the report, send it by email, open the private share link,
   verify PDF rendering, revoke the link, and confirm the revoked URL returns `404`.
6. Apply the private-bucket CORS policy below and verify uploads from the dashboard origin
   succeed while an unrelated origin is rejected.
7. Complete the physical-device airplane-mode script in `mobile/README.md` and attach its
   result to the release record.
8. Obtain counsel approval for the recording-consent disclosure before enabling capture
   for trial users.
9. Enable database backups, name the restore owner, and complete a restore drill before
   storing real customer data.

Before syncing the Blueprint, run the current Render validator (Render CLI 2.7.0+)
against `infra/render.yaml`:

```sh
render blueprints validate infra/render.yaml
```

This performs Render's schema, plan, and semantic Blueprint checks (the live schema is
also published at <https://render.com/schema/render.yaml.json>). The API validation
endpoint is `POST https://api.render.com/v1/blueprints/validate` for an authenticated
workspace when conflict checking against existing resources is required.

Postgres backups are a daily operational requirement. Enable Render's daily backup/
point-in-time recovery for the production database and verify a restore drill at least
monthly. Keep backup retention and the restore owner documented in the service runbook.

Configure Stripe's webhook endpoint as `https://<api-host>/billing/webhook` for
`checkout.session.completed`, `customer.subscription.updated`, and
`customer.subscription.deleted`. Store the signing secret and solo-monthly price ID in
Render's secret environment variables.

Readiness is exposed at `/ready` and checks Postgres, Redis, and object storage. Liveness
is `/health`. The API image starts Uvicorn with access logging disabled; the structured
request logger is the canonical access log and redacts public share tokens. The Celery
worker leaves the Homean root logger in place and applies the same sanitized JSON formatter
to worker and task logs. Uvicorn is
configured with `--forwarded-allow-ips=*` because the API container is reachable only
through Render's forwarding ingress; this is what makes the trusted client address
available to rate limiting. Do not expose the container port directly or reuse this
trust setting outside that Render proxy boundary. Sentry is configured without default
PII and applies the same URL/request sanitization.

## Private object-storage CORS

The media and branding buckets remain private; browser uploads use presigned URLs.
Copy `infra/storage-cors.example.json`, replace the example origin with the exact
configured `DASHBOARD_ORIGIN` (including scheme and port), and apply it to the bucket:

```sh
aws s3api put-bucket-cors \
  --bucket "$S3_BUCKET" \
  --cors-configuration file://infra/storage-cors.example.json
```

The policy is intentionally limited to the dashboard origin, `PUT` for presigned
uploads, `GET`/`HEAD` for browser retrieval where needed, and the `Content-Type`
request header. It does not make the bucket public. For Cloudflare R2, apply the same
origin/method/header values in the bucket CORS settings (or the R2 S3-compatible API).

Verify the release configuration with a preflight request before enabling uploads:

```sh
curl -i -X OPTIONS "${PRESIGNED_URL}" \
  -H "Origin: ${DASHBOARD_ORIGIN}" \
  -H "Access-Control-Request-Method: PUT" \
  -H "Access-Control-Request-Headers: content-type"
```

The response must include the exact dashboard origin in
`Access-Control-Allow-Origin`, `PUT` in `Access-Control-Allow-Methods`, and
`Content-Type` in `Access-Control-Allow-Headers`. A request from any other origin
must not receive an allow-origin response. Include this preflight check in the release
runbook alongside the Alembic migration and `/ready` check.

## Tenant-query audit

Authenticated resource repositories require the current workspace ID on reads and
mutations (or join through a workspace-scoped Visit). The intentionally global reads
are limited to authentication email lookup, the real-estate vertical configuration,
and Stripe webhook subscription lookup by Stripe subscription ID; webhook events are
validated against workspace metadata before they update a subscription.
