#!/usr/bin/env bash
# One-command local Homean stack for manual testing on this Mac.
#
#   scripts/local_stack.sh up      # Postgres + Redis + MinIO in Docker, migrations, API on :8197
#   scripts/local_stack.sh seed    # create the media bucket and a test account
#   scripts/local_stack.sh status  # /ready plus what is running
#   scripts/local_stack.sh down    # stop everything and delete the volumes
#
# Uses the production compose file with a separate project name and spare ports
# (55433 / 6381 / 9010) so it never collides with the dev compose on 55432 or with
# other projects on this machine. The API binds 0.0.0.0 so the Android emulator
# can reach it at http://10.0.2.2:8197 and an iOS simulator at http://127.0.0.1:8197.
#
# Test account after `seed`: drill@example.com / drill-password-1
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE="$ROOT/.local"
ENV_FILE="$STATE/stack.env"
API_LOG="$STATE/api.log"
API_PID="$STATE/api.pid"
PROJECT=homean-local
API_PORT=8197
DB_URL="postgresql+asyncpg://homean:local-pass@127.0.0.1:55433/homean"
export PATH="$HOME/.orbstack/bin:/opt/homebrew/bin:$PATH" DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib

compose() { docker compose -p "$PROJECT" --env-file "$ENV_FILE" -f "$ROOT/infra/macmini/compose.yml" "$@"; }
log() { printf '\033[1m%s\033[0m\n' "$*"; }

up() {
  mkdir -p "$STATE"
  cat > "$ENV_FILE" <<ENV
POSTGRES_PASSWORD=local-pass
S3_ACCESS_KEY=localaccess
S3_SECRET_KEY=local-secret-key-1234
ENV
  log "starting Postgres, Redis, MinIO ($PROJECT)"
  compose up -d --wait
  log "applying migrations"
  (cd "$ROOT/backend" && DATABASE_URL="$DB_URL" .venv/bin/alembic upgrade head | tail -1)
  if [[ -f "$API_PID" ]] && kill -0 "$(cat "$API_PID")" 2>/dev/null; then
    log "API already running (pid $(cat "$API_PID"))"
  else
    log "starting API on 0.0.0.0:$API_PORT (log: $API_LOG)"
    # Detach fully (new session, no inherited descriptors) so a caller that
    # pipes this script's output is never held open by the API process.
    (cd "$ROOT/backend" && .venv/bin/python - "$API_PORT" "$DB_URL" "$API_LOG" "$API_PID" <<'PY'
import os, subprocess, sys
port, db_url, log_path, pid_path = sys.argv[1:5]
env = {
    "PATH": os.environ["PATH"], "HOME": os.environ["HOME"],
    "DYLD_FALLBACK_LIBRARY_PATH": "/opt/homebrew/lib",
    "DATABASE_URL": db_url, "REDIS_URL": "redis://127.0.0.1:6381/0",
    "S3_ENDPOINT_URL": "http://10.0.2.2:9010", "S3_INTERNAL_ENDPOINT_URL": "http://127.0.0.1:9010",
    "S3_ACCESS_KEY": "localaccess", "S3_SECRET_KEY": "local-secret-key-1234", "S3_BUCKET": "homean-media",
    "JWT_SECRET": "local-only-secret", "EMAIL_PROVIDER": "console",
    "DASHBOARD_ORIGIN": "http://localhost:3000", "PUBLIC_BASE_URL": f"http://127.0.0.1:{port}",
}
with open(log_path, "ab") as log:
    process = subprocess.Popen(
        [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", port, "--no-access-log"],
        env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log, close_fds=True, start_new_session=True,
    )
open(pid_path, "w").write(str(process.pid))
PY
    )
  fi
  for _ in $(seq 1 30); do curl -sf -m 2 "http://127.0.0.1:$API_PORT/health" >/dev/null && break; sleep 1; done
  status
}

seed() {
  (cd "$ROOT/backend" && .venv/bin/python - <<'PY'
import boto3
s3 = boto3.client("s3", endpoint_url="http://127.0.0.1:9010", aws_access_key_id="localaccess",
                  aws_secret_access_key="local-secret-key-1234", region_name="us-east-1")
try:
    s3.create_bucket(Bucket="homean-media"); print("bucket homean-media created")
except s3.exceptions.BucketAlreadyOwnedByYou:
    print("bucket homean-media already exists")
PY
  )
  code=$(curl -s -m 10 -o /dev/null -w '%{http_code}' -X POST -H 'content-type: application/json' \
    -d '{"email":"drill@example.com","password":"drill-password-1"}' "http://127.0.0.1:$API_PORT/auth/signup" || true)
  case "$code" in
    201) echo "test account drill@example.com / drill-password-1 created" ;;
    409) echo "test account drill@example.com already exists" ;;
    *) echo "signup returned HTTP $code" >&2; exit 1 ;;
  esac
}

status() {
  compose ps --format '{{.Service}}: {{.Status}}' 2>/dev/null || true
  printf 'API /ready: '; curl -s -m 5 "http://127.0.0.1:$API_PORT/ready" || echo "not reachable"; echo
  echo "Android emulator URL: http://10.0.2.2:$API_PORT   iOS simulator / dashboard: http://127.0.0.1:$API_PORT"
}

down() {
  if [[ -f "$API_PID" ]]; then kill "$(cat "$API_PID")" 2>/dev/null || true; rm -f "$API_PID"; fi
  [[ -f "$ENV_FILE" ]] && compose down -v --remove-orphans
  log "stopped $PROJECT and removed its volumes"
}

case "${1:-}" in
  up) up ;; seed) seed ;; status) status ;; down) down ;;
  *) sed -n '2,15p' "$0"; exit 2 ;;
esac
