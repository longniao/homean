#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

run_backend_script() {
  local script_name="$1"
  if [[ -x "$ROOT_DIR/backend/.venv/bin/python" ]]; then
    "$ROOT_DIR/backend/.venv/bin/python" \
      "$ROOT_DIR/backend/scripts/$script_name"
  else
    (
      cd "$ROOT_DIR/backend"
      uv run --frozen python "scripts/$script_name"
    )
  fi
}

echo "==> Checking Alembic migration graph"
if [[ -x "$ROOT_DIR/backend/.venv/bin/python" ]]; then
  "$ROOT_DIR/backend/.venv/bin/python" \
    "$ROOT_DIR/backend/scripts/assert_migration_head.py"
else
  (
    cd "$ROOT_DIR/backend"
    uv run --frozen python scripts/assert_migration_head.py
  )
fi

echo "==> Validating Render Blueprint structure and Docker paths"
run_backend_script validate_render_blueprint.py

echo "==> Validating Docker Compose configuration"
docker compose \
  --env-file "$ROOT_DIR/.env.example" \
  --file "$ROOT_DIR/infra/docker-compose.yml" \
  config -q

echo "==> Building API release image"
docker build \
  --file "$ROOT_DIR/backend/Dockerfile.api" \
  --tag kawu-api:preflight \
  "$ROOT_DIR/backend"

echo "==> Building worker release image"
docker build \
  --file "$ROOT_DIR/backend/Dockerfile.worker" \
  --tag kawu-worker:preflight \
  "$ROOT_DIR/backend"

echo "==> Building dashboard release image"
docker build \
  --file "$ROOT_DIR/dashboard/Dockerfile" \
  --tag kawu-dashboard:preflight \
  "$ROOT_DIR/dashboard"

echo "Release preflight passed. No provider credentials or deployment calls were used."
