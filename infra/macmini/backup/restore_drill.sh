#!/usr/bin/env bash
# Restore a Homean snapshot into an isolated Compose project and verify it.
#
#   restore_drill.sh [--snapshot <UTC stamp>] [--from-dir <local snapshot dir>] [--keep]
#
# Downloads the newest (or named) snapshot from BACKUP_REMOTE, decrypts it with
# BACKUP_AGE_IDENTITY, restores PostgreSQL and the media volume into the
# homean-restore-drill project, checks the schema is at the Alembic head, prints
# read-only row counts for the evidence chain, starts a throwaway API on
# 127.0.0.1:8198 and requires /ready to pass. Tears everything down unless --keep.
#
# The drill never connects to homean-production.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
CONFIG_FILE="${HOMEAN_BACKUP_CONFIG:-$SCRIPT_DIR/backup.env}"
DRILL_PROJECT=homean-restore-drill
DRILL_COMPOSE="$SCRIPT_DIR/restore-drill.compose.yml"
DRILL_API_PORT=8198

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { log "ERROR: $*" >&2; exit 1; }

SNAPSHOT=""
FROM_DIR=""
KEEP=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --snapshot) SNAPSHOT="$2"; shift 2 ;;
    --from-dir) FROM_DIR="$2"; shift 2 ;;
    --keep) KEEP=1; shift ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) die "unknown argument $1" ;;
  esac
done

if [[ -f "$CONFIG_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
  set +a
fi
: "${BACKUP_AGE_IDENTITY:?BACKUP_AGE_IDENTITY must point to the age private key file}"
[[ -f "$BACKUP_AGE_IDENTITY" ]] || die "age identity $BACKUP_AGE_IDENTITY not found"

export PATH="$HOME/.orbstack/bin:/opt/homebrew/bin:$HOME/.local/bin:$PATH"
for tool in docker age curl; do
  command -v "$tool" >/dev/null || die "$tool is not installed"
done
[[ -x "$BACKEND_DIR/.venv/bin/python" ]] || die "backend virtualenv missing; run 'uv sync --frozen' in backend/"

WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/homean-restore-drill.XXXXXX")"
chmod 700 "$WORK_DIR"
API_PID=""

drill() { docker compose -p "$DRILL_PROJECT" -f "$DRILL_COMPOSE" "$@"; }

cleanup() {
  [[ -n "$API_PID" ]] && kill "$API_PID" 2>/dev/null || true
  if [[ $KEEP -eq 1 ]]; then
    log "keeping $DRILL_PROJECT and $WORK_DIR (--keep); remove with: docker compose -p $DRILL_PROJECT down -v"
  else
    drill down -v --remove-orphans >/dev/null 2>&1 || true
    rm -rf "$WORK_DIR"
  fi
}
trap cleanup EXIT

# 1. Fetch the snapshot.
if [[ -n "$FROM_DIR" ]]; then
  [[ -d "$FROM_DIR" ]] || die "$FROM_DIR is not a directory"
  cp "$FROM_DIR"/{postgres.dump.age,media.tar.gz.age,manifest.json} "$WORK_DIR/"
  SNAPSHOT="$(basename "$FROM_DIR")"
else
  : "${BACKUP_REMOTE:?BACKUP_REMOTE is required unless --from-dir is used}"
  command -v rclone >/dev/null || die "rclone is not installed"
  if [[ -z "$SNAPSHOT" ]]; then
    SNAPSHOT="$(rclone lsf --dirs-only "$BACKUP_REMOTE" | sed 's#/$##' | sort | tail -n 1)"
    [[ -n "$SNAPSHOT" ]] || die "no snapshots found at $BACKUP_REMOTE"
  fi
  log "downloading snapshot $SNAPSHOT from $BACKUP_REMOTE"
  rclone copy "$BACKUP_REMOTE/$SNAPSHOT" "$WORK_DIR"
fi
for f in postgres.dump.age media.tar.gz.age manifest.json; do
  [[ -s "$WORK_DIR/$f" ]] || die "snapshot is missing $f"
done

# 2. Verify checksums against the manifest, then decrypt.
for f in postgres.dump.age media.tar.gz.age; do
  expected="$(sed -n "s/.*\"$f\": {\"bytes\": [0-9]*, \"sha256\": \"\([0-9a-f]*\)\"}.*/\1/p" "$WORK_DIR/manifest.json")"
  actual="$(shasum -a 256 "$WORK_DIR/$f" | cut -d' ' -f1)"
  [[ "$expected" == "$actual" ]] || die "sha256 mismatch for $f"
done
log "checksums match manifest; decrypting"
age --decrypt --identity "$BACKUP_AGE_IDENTITY" --output "$WORK_DIR/postgres.dump" "$WORK_DIR/postgres.dump.age"
age --decrypt --identity "$BACKUP_AGE_IDENTITY" --output "$WORK_DIR/media.tar.gz" "$WORK_DIR/media.tar.gz.age"

# 3. Bring up the isolated target and restore into it.
log "starting $DRILL_PROJECT"
drill down -v --remove-orphans >/dev/null 2>&1 || true
drill up -d --wait

log "restoring PostgreSQL"
drill exec -T postgres pg_restore -U homean -d homean --no-owner --no-privileges --exit-on-error < "$WORK_DIR/postgres.dump"

log "restoring media volume"
docker run --rm --interactive --volume "${DRILL_PROJECT}_media-data:/data" alpine:3 \
  tar --extract --gzip --file - --directory /data < "$WORK_DIR/media.tar.gz"
drill restart minio >/dev/null
drill up -d --wait minio

# 4. Schema and read-only verification.
DRILL_DATABASE_URL="postgresql+asyncpg://homean:drill-only@127.0.0.1:55498/homean"
log "checking Alembic revision"
CURRENT="$(cd "$BACKEND_DIR" && DATABASE_URL="$DRILL_DATABASE_URL" .venv/bin/alembic current 2>/dev/null | grep -o '^[0-9a-z_]*' | head -n 1)"
HEAD="$(cd "$BACKEND_DIR" && DATABASE_URL="$DRILL_DATABASE_URL" .venv/bin/alembic heads 2>/dev/null | grep -o '^[0-9a-z_]*' | head -n 1)"
[[ -n "$CURRENT" && "$CURRENT" == "$HEAD" ]] || die "restored schema is at '$CURRENT', repository head is '$HEAD'"

log "read-only row counts"
COUNTS="$(drill exec -T postgres psql -U homean -d homean -v ON_ERROR_STOP=1 --tuples-only --no-align --field-separator=' ' <<'SQL'
select 'workspaces', count(*) from workspaces
union all select 'users', count(*) from users
union all select 'visits', count(*) from visits
union all select 'raw_media', count(*) from raw_media
union all select 'transcript_segments', count(*) from transcript_segments
union all select 'observations', count(*) from observations
union all select 'observations_with_evidence', count(*) from observations where source_transcript_segment_id is not null or source_media_id is not null
union all select 'reports', count(*) from reports
union all select 'report_share_links', count(*) from report_share_links
union all select 'report_sends', count(*) from report_sends
union all select 'pipeline_runs', count(*) from pipeline_runs;
SQL
)" || die "read-only verification query failed"
MEDIA_OBJECTS="$(docker run --rm --volume "${DRILL_PROJECT}_media-data:/data:ro" alpine:3 \
  sh -c "find /data -type f -name xl.meta -not -path '*/.minio.sys/*' | wc -l | tr -d ' '")"

# 5. Start a throwaway API against the restored data and require /ready.
log "starting throwaway API on 127.0.0.1:$DRILL_API_PORT"
(
  cd "$BACKEND_DIR"
  env -i PATH="$PATH" HOME="$HOME" DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib PYTHONUNBUFFERED=1 \
    DATABASE_URL="$DRILL_DATABASE_URL" \
    REDIS_URL="redis://127.0.0.1:6398/0" \
    S3_ENDPOINT_URL="http://127.0.0.1:9098" \
    S3_ACCESS_KEY=drill S3_SECRET_KEY=drill-only-secret S3_BUCKET=homean-media \
    JWT_SECRET=restore-drill-only APP_ENV=restore_drill EMAIL_PROVIDER=console \
    .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$DRILL_API_PORT" --no-access-log \
    > "$WORK_DIR/api.log" 2>&1
) &
API_PID=$!
READY=""
for _ in $(seq 1 30); do
  READY="$(curl -s -m 3 "http://127.0.0.1:$DRILL_API_PORT/ready" || true)"
  [[ "$READY" == *'"status":"ok"'* ]] && break
  sleep 1
done
[[ "$READY" == *'"status":"ok"'* ]] || { cat "$WORK_DIR/api.log" >&2; die "/ready did not pass: $READY"; }

cat <<SUMMARY

=== Homean restore drill: PASS ===
snapshot:            $SNAPSHOT
manifest:            $(tr -d '\n' < "$WORK_DIR/manifest.json" | sed 's/  */ /g')
alembic revision:    $CURRENT (matches head)
media objects:       $MEDIA_OBJECTS
/ready:              $READY
row counts:
$(printf '%s\n' "$COUNTS" | sed 's/^/  /')
drill target:        $DRILL_PROJECT (isolated; production untouched)
completed (UTC):     $(date -u +%Y-%m-%dT%H:%M:%SZ)
SUMMARY
