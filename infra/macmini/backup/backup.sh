#!/usr/bin/env bash
# Encrypted off-host snapshot of the Homean PostgreSQL database and media volume.
#
# Produces <BACKUP_LOCAL_DIR>/<UTC timestamp>/ containing:
#   postgres.dump.age   pg_dump custom-format archive, age-encrypted
#   media.tar.gz.age    tar of the MinIO data volume, age-encrypted
#   manifest.json       sizes, sha256 of the encrypted files, git commit, host
# then copies the snapshot to BACKUP_REMOTE with rclone and prunes old ones.
#
# Redis is not backed up: it only holds the transient Celery queue.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
CONFIG_FILE="${HOMEAN_BACKUP_CONFIG:-$SCRIPT_DIR/backup.env}"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { log "ERROR: $*" >&2; exit 1; }

[[ -f "$CONFIG_FILE" ]] || die "missing $CONFIG_FILE; copy backup.env.example and fill it in"
set -a
# shellcheck disable=SC1090
source "$CONFIG_FILE"
set +a

: "${BACKUP_REMOTE:?BACKUP_REMOTE is required}"
: "${BACKUP_AGE_RECIPIENT:?BACKUP_AGE_RECIPIENT is required}"
: "${BACKUP_RETENTION_DAYS:=30}"
: "${BACKUP_LOCAL_KEEP:=3}"
: "${BACKUP_LOCAL_DIR:=$HOME/homean-backups}"
: "${COMPOSE_PROJECT:=homean-production}"
: "${COMPOSE_FILE:=$SCRIPT_DIR/../compose.yml}"
: "${COMPOSE_ENV_FILE:=$REPO_ROOT/backend/.env}"
: "${MEDIA_VOLUME:=${COMPOSE_PROJECT}_media-data}"

export PATH="$HOME/.orbstack/bin:/opt/homebrew/bin:$HOME/.local/bin:$PATH"
for tool in docker rclone age shasum; do
  command -v "$tool" >/dev/null || die "$tool is not installed (brew install age rclone)"
done
[[ "$BACKUP_AGE_RECIPIENT" == age1* ]] || die "BACKUP_AGE_RECIPIENT must be an age public key"
[[ -f "$COMPOSE_ENV_FILE" ]] || die "compose env file $COMPOSE_ENV_FILE not found"
rclone listremotes | grep -qx "${BACKUP_REMOTE%%:*}:" || die "rclone remote '${BACKUP_REMOTE%%:*}' is not configured"

compose() {
  docker compose -p "$COMPOSE_PROJECT" --env-file "$COMPOSE_ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

# One backup at a time. The lock directory is removed on exit.
LOCK_DIR="$BACKUP_LOCAL_DIR/.lock"
mkdir -p "$BACKUP_LOCAL_DIR"
mkdir "$LOCK_DIR" 2>/dev/null || die "another backup is running (lock: $LOCK_DIR)"
trap 'rm -rf "$LOCK_DIR"' EXIT

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
SNAPSHOT_DIR="$BACKUP_LOCAL_DIR/$STAMP"
mkdir -p "$SNAPSHOT_DIR"
chmod 700 "$BACKUP_LOCAL_DIR" "$SNAPSHOT_DIR"

log "snapshot $STAMP -> $SNAPSHOT_DIR"

compose ps --status running --services | grep -qx postgres || die "postgres is not running in $COMPOSE_PROJECT"
docker volume inspect "$MEDIA_VOLUME" >/dev/null 2>&1 || die "media volume $MEDIA_VOLUME not found"

log "dumping PostgreSQL"
compose exec -T postgres pg_dump -U homean -d homean --format=custom --no-owner --no-privileges \
  | age --recipient "$BACKUP_AGE_RECIPIENT" --output "$SNAPSHOT_DIR/postgres.dump.age"

log "archiving media volume $MEDIA_VOLUME"
docker run --rm --volume "$MEDIA_VOLUME:/data:ro" alpine:3 tar --create --gzip --file - --directory /data . \
  | age --recipient "$BACKUP_AGE_RECIPIENT" --output "$SNAPSHOT_DIR/media.tar.gz.age"

for f in postgres.dump.age media.tar.gz.age; do
  [[ -s "$SNAPSHOT_DIR/$f" ]] || die "$f is empty"
done

GIT_COMMIT="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
{
  echo '{'
  echo "  \"snapshot\": \"$STAMP\","
  echo "  \"host\": \"$(hostname)\","
  echo "  \"git_commit\": \"$GIT_COMMIT\","
  echo "  \"compose_project\": \"$COMPOSE_PROJECT\","
  echo "  \"media_volume\": \"$MEDIA_VOLUME\","
  echo "  \"age_recipient\": \"$BACKUP_AGE_RECIPIENT\","
  echo '  "files": {'
  first=1
  for f in postgres.dump.age media.tar.gz.age; do
    [[ $first -eq 1 ]] || echo ','
    first=0
    printf '    "%s": {"bytes": %s, "sha256": "%s"}' \
      "$f" "$(stat -f %z "$SNAPSHOT_DIR/$f")" "$(shasum -a 256 "$SNAPSHOT_DIR/$f" | cut -d' ' -f1)"
  done
  echo
  echo '  }'
  echo '}'
} > "$SNAPSHOT_DIR/manifest.json"

log "uploading to $BACKUP_REMOTE/$STAMP"
rclone copy --checksum "$SNAPSHOT_DIR" "$BACKUP_REMOTE/$STAMP"
rclone check --one-way "$SNAPSHOT_DIR" "$BACKUP_REMOTE/$STAMP"

log "pruning remote snapshots older than ${BACKUP_RETENTION_DAYS}d"
rclone delete --min-age "${BACKUP_RETENTION_DAYS}d" "$BACKUP_REMOTE"
rclone rmdirs --leave-root "$BACKUP_REMOTE"

log "keeping the newest $BACKUP_LOCAL_KEEP local snapshots"
# BSD head has no negative -n, so count explicitly (bash 3.2 compatible).
local_snapshots=()
while IFS= read -r dir; do local_snapshots+=("$dir"); done < <(ls -1d "$BACKUP_LOCAL_DIR"/*/ 2>/dev/null | sort)
excess=$(( ${#local_snapshots[@]} - BACKUP_LOCAL_KEEP ))
if (( excess > 0 )); then
  for old in "${local_snapshots[@]:0:excess}"; do
    rm -rf "$old"
  done
fi

log "done: $(du -sh "$SNAPSHOT_DIR" | cut -f1) in $STAMP"
