# Mac mini deployment

Homean runs on `macmini` from `/Users/hepang/Git/homean/backend`, following
Mainpay's native uv + supervisord + Cloudflare Tunnel deployment pattern.
Dependencies use a separate `homean-production` Docker Compose project.

| Service | Loopback address |
| --- | --- |
| API (`homean_api`) | 127.0.0.1:8120 |
| PostgreSQL | 127.0.0.1:55433 |
| Redis (`homean_worker` queue) | 127.0.0.1:6381 |
| Private MinIO S3 API | 127.0.0.1:9010 |

Production secrets live only in `backend/.env` on the Mac mini (mode 0600).
Use unique random PostgreSQL, S3, and JWT credentials. Set `POSTGRES_PASSWORD`,
`DATABASE_URL`, `REDIS_URL`, all `S3_*` values, and `JWT_SECRET`. Configure
`APP_ENV=production`, `DASHBOARD_ORIGIN=https://app.homean.com`,
`PUBLIC_BASE_URL=https://api.homean.com`, and
`S3_ENDPOINT_URL=https://media.homean.com`. The S3 endpoint must be reachable by
browsers and phones because it is used in signed URLs. Buckets remain private;
never add an anonymous read policy or publish the MinIO console.

Add the following ingress rules before the shared tunnel's catch-all:

```yaml
- hostname: api.homean.com
  service: http://localhost:8120
- hostname: media.homean.com
  service: http://localhost:9010
```

Both proxied CNAME records in the **homean.com zone** target
`f38865bf-4451-4202-bb4f-c520b0f8d452.cfargotunnel.com`.
Do not use the Mac mini's old zone-specific tunnel certificate for DNS: it
appends its original zone to Homean hostnames. Validate the tunnel configuration
before restarting `cloudflared_tunnels`; that restart briefly affects shared
services.

```bash
ssh macmini 'export PATH="$HOME/.orbstack/bin:/opt/homebrew/bin:$HOME/.local/bin:$PATH"
  cd ~/Git/homean
  git pull --ff-only origin main
  docker compose --env-file backend/.env -f infra/macmini/compose.yml up -d --wait
  cd backend
  uv sync --frozen
  uv run --env-file .env alembic upgrade head
  supervisorctl restart homean_api homean_worker'
```

First installation also creates private bucket `homean-media`, copies the
supervisor definitions into `/opt/homebrew/etc/supervisor.d/`, and runs
`supervisorctl reread` plus `supervisorctl update homean_api homean_worker`.
Use `uv run --env-file .env` for migrations: Alembic otherwise loads only the
repository-root `.env` and can select the development database.

Require all `/ready` checks to pass, verify signed uploads/downloads and CORS,
then deploy the dashboard with:

```bash
cd dashboard
HOMEAN_API_URL=https://api.homean.com npm run cf:deploy
```

Configure Deepgram and Anthropic credentials before real AI processing. SMTP
and Stripe are separate optional integrations; console email does not deliver
mail. No credentials are inherited from Kawu or Mainpay. Existing Kawu data and
uncommitted source remain untouched. Establish encrypted off-host database and
media backups before accepting customer data; Docker volumes alone are not a
backup.
