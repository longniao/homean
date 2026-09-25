# Mac mini deployment

Homean runs on `macmini` from `/Users/hepang/Git/homean/backend`, following
Mainpay's native uv + supervisord + Cloudflare Tunnel deployment pattern.
Dependencies use a separate `homean-production` Docker Compose project.
MinIO images are pulled from `quay.io/minio`; Docker Hub stopped serving
`minio/minio`, so a fresh pull of the old reference fails.

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
`PUBLIC_BASE_URL=https://api.homean.com`, and the `S3_*` values for Cloudflare R2
described under **Media storage on R2** below. The S3 endpoint must be reachable by
browsers and phones because it is used in signed URLs. Buckets remain private;
never add a public bucket policy.

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

Choose the transcription and report providers and configure their credentials
before real AI processing; see [AI provider switches](../../docs/Homean_AI_Providers.md).
OpenAI transcription requires `/opt/homebrew/bin/ffmpeg` on the native worker.
Resend
is the selected email provider; see [Resend setup](../../docs/Homean_Resend_Setup.md).
Stripe is a separate optional integration; console email does not deliver
mail. No credentials are inherited from Kawu or Mainpay. Existing Kawu data and
uncommitted source remain untouched. Establish encrypted off-host database and
media backups before accepting customer data; Docker volumes alone are not a
backup. The tooling for that lives in `backup/` and is described below.

## Backups and restore drill

`backup/backup.sh` takes an encrypted snapshot of PostgreSQL (`pg_dump` custom
format) and the MinIO media volume, uploads it with rclone to an off-host
remote, and prunes old snapshots. `backup/restore_drill.sh` restores the newest
snapshot into the isolated `homean-restore-drill` Compose project, checks the
Alembic revision, prints evidence-chain row counts, boots a throwaway API and
requires `/ready` to pass. Neither script connects to production for the drill.

Setup on the Mac mini, once:

```bash
brew install age rclone
age-keygen -o ~/homean-backup-identity.txt   # keep the private key OFF the Mac mini too
rclone config                                # create the off-host remote
cp infra/macmini/backup/backup.env.example infra/macmini/backup/backup.env
chmod 600 infra/macmini/backup/backup.env    # fill in BACKUP_REMOTE and BACKUP_AGE_RECIPIENT
bash infra/macmini/backup/backup.sh          # first snapshot
BACKUP_AGE_IDENTITY=~/homean-backup-identity.txt bash infra/macmini/backup/restore_drill.sh
cp infra/macmini/backup/com.homean.backup.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.homean.backup.plist
```

The launchd job runs daily at 03:30 local time and logs to
`~/git/logs/homean_backup.*.log`. Repeat the restore drill after every
migration that changes the evidence chain, and record the drill summary as
evidence for checklist gate 4. Redis is intentionally not backed up: it holds
only the transient Celery queue.

## Media storage on R2

Media (audio, photos, video, PDFs, logos) lives in the Cloudflare R2 bucket
`homean-media` (account `9cb6c5c344477c40e7b141a668789813`, location hint WNAM).
Its CORS rule is versioned in `r2/cors.json` and applied with
`npx wrangler r2 bucket cors set homean-media --file infra/macmini/r2/cors.json`
from `dashboard/`. Phones and browsers talk to R2 directly through presigned
URLs, so the Mac mini no longer serves media and `media.homean.com` is not needed.

Cut-over from the Mac mini's MinIO, in order:

1. In the Cloudflare dashboard, R2 → Manage API tokens → create a token with
   **Object Read & Write** scoped to `homean-media`. Note the Access Key ID, the
   Secret Access Key and the S3 endpoint `https://<account-id>.r2.cloudflarestorage.com`.
2. Copy every existing object while MinIO is still live (re-runnable, never deletes):
   ```bash
   cd ~/Git/homean
   R2_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com \
   R2_ACCESS_KEY=<key id> R2_SECRET_KEY=<secret> \
   bash infra/macmini/r2/migrate_media_to_r2.sh
   ```
3. In `backend/.env` set `S3_ENDPOINT_URL` to the R2 endpoint, `S3_ACCESS_KEY` /
   `S3_SECRET_KEY` to the token values, `S3_BUCKET=homean-media`, `S3_REGION=auto`,
   and remove `S3_INTERNAL_ENDPOINT_URL`. Then `supervisorctl restart homean_api homean_worker`.
4. Verify: `curl https://api.homean.com/ready` reports `s3: ok`; upload one photo
   from the dashboard and open it back; run step 2 once more so anything captured
   during the switch is copied.
5. Retire MinIO on the Mac mini: remove the `media.homean.com` ingress rule from the
   tunnel, then `docker compose -p homean-production stop minio`. Keep the volume
   for 30 days before `docker compose -p homean-production rm -v minio`.

The backup script's media step archives the MinIO volume and becomes redundant
after step 5; the PostgreSQL step still matters. R2 itself is one provider, so a
second bucket or another provider remains the encrypted backup target.
