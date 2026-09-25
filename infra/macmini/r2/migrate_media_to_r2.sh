#!/usr/bin/env bash
# One-time copy of the media bucket from the Mac mini's MinIO to Cloudflare R2.
#
#   migrate_media_to_r2.sh            # sync, then verify with rclone check
#   migrate_media_to_r2.sh --dry-run  # show what would be copied
#
# Reads the MinIO side from backend/.env (S3_INTERNAL_ENDPOINT_URL, S3_ACCESS_KEY,
# S3_SECRET_KEY, S3_BUCKET) and the R2 side from R2_ENDPOINT_URL, R2_ACCESS_KEY,
# R2_SECRET_KEY and R2_BUCKET in the environment. Safe to re-run: rclone sync only
# copies what differs. It never deletes from MinIO.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
ENV_FILE="${HOMEAN_ENV_FILE:-$REPO_ROOT/backend/.env}"
DRY_RUN=""
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN="--dry-run"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { log "ERROR: $*" >&2; exit 1; }

export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"
command -v rclone >/dev/null || die "rclone is not installed (brew install rclone)"
[[ -f "$ENV_FILE" ]] || die "env file $ENV_FILE not found"

# MinIO side, from the current backend/.env.
minio_endpoint="$(grep -E '^S3_INTERNAL_ENDPOINT_URL=' "$ENV_FILE" | cut -d= -f2- || true)"
[[ -n "$minio_endpoint" ]] || minio_endpoint="$(grep -E '^S3_ENDPOINT_URL=' "$ENV_FILE" | cut -d= -f2-)"
minio_key="$(grep -E '^S3_ACCESS_KEY=' "$ENV_FILE" | cut -d= -f2-)"
minio_secret="$(grep -E '^S3_SECRET_KEY=' "$ENV_FILE" | cut -d= -f2-)"
minio_bucket="$(grep -E '^S3_BUCKET=' "$ENV_FILE" | cut -d= -f2-)"
[[ -n "$minio_endpoint" && -n "$minio_key" && -n "$minio_secret" && -n "$minio_bucket" ]] || die "MinIO S3_* values missing in $ENV_FILE"

: "${R2_ENDPOINT_URL:?e.g. https://<account-id>.r2.cloudflarestorage.com}"
: "${R2_ACCESS_KEY:?R2 access key id}"
: "${R2_SECRET_KEY:?R2 secret access key}"
: "${R2_BUCKET:=homean-media}"

# rclone remotes defined through the environment only; nothing is written to rclone.conf.
export RCLONE_CONFIG_SRC_TYPE=s3 RCLONE_CONFIG_SRC_PROVIDER=Minio \
  RCLONE_CONFIG_SRC_ENDPOINT="$minio_endpoint" \
  RCLONE_CONFIG_SRC_ACCESS_KEY_ID="$minio_key" RCLONE_CONFIG_SRC_SECRET_ACCESS_KEY="$minio_secret"
export RCLONE_CONFIG_DST_TYPE=s3 RCLONE_CONFIG_DST_PROVIDER=Cloudflare \
  RCLONE_CONFIG_DST_ENDPOINT="$R2_ENDPOINT_URL" \
  RCLONE_CONFIG_DST_ACCESS_KEY_ID="$R2_ACCESS_KEY" RCLONE_CONFIG_DST_SECRET_ACCESS_KEY="$R2_SECRET_KEY"

log "source objects: $(rclone size "src:$minio_bucket" --json | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["count"], "objects,", d["bytes"], "bytes")')"
log "syncing src:$minio_bucket -> dst:$R2_BUCKET ${DRY_RUN:+(dry run)}"
rclone sync "src:$minio_bucket" "dst:$R2_BUCKET" --checksum --transfers 8 --stats-one-line --stats 30s $DRY_RUN
[[ -n "$DRY_RUN" ]] && exit 0

log "verifying"
rclone check "src:$minio_bucket" "dst:$R2_BUCKET" --one-way --size-only
log "done: every MinIO object is present in R2. MinIO was not modified."
