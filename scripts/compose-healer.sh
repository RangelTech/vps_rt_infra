#!/usr/bin/env bash
# Reconciles the RT Docker Compose stack when one or more services are stopped.
# This intentionally covers clean stops that Docker's restart policy will not
# undo, such as an accidental `docker compose stop`.

set -euo pipefail

COMPOSE_DIR="${RT_COMPOSE_DIR:-/opt/platform/compose}"
LOCK_FILE="${RT_COMPOSE_HEALER_LOCK:-/run/rt-compose-healer.lock}"
DISABLE_FILE="${RT_COMPOSE_HEALER_DISABLE_FILE:-/opt/platform/.maintenance}"
LOG_TAG="${RT_COMPOSE_HEALER_LOG_TAG:-rt-compose-healer}"

log() {
  echo "[$LOG_TAG] $*"
  logger -t "$LOG_TAG" -- "$*" 2>/dev/null || true
}

if [ -f "$DISABLE_FILE" ]; then
  log "disabled because $DISABLE_FILE exists"
  exit 0
fi

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  log "another healer run is already active"
  exit 0
fi

if [ ! -f "$COMPOSE_DIR/docker-compose.yml" ]; then
  log "missing compose file at $COMPOSE_DIR/docker-compose.yml"
  exit 1
fi

cd "$COMPOSE_DIR"

mapfile -t services < <(docker compose config --services)
if [ "${#services[@]}" -eq 0 ]; then
  log "docker compose config returned no services"
  exit 1
fi

needs_heal=()
for service in "${services[@]}"; do
  cid="$(docker compose ps -a -q "$service" 2>/dev/null | head -n 1 || true)"
  if [ -z "$cid" ]; then
    needs_heal+=("$service:no-container")
    continue
  fi

  state="$(docker inspect --format '{{.State.Status}}' "$cid" 2>/dev/null || echo "missing")"
  if [ "$state" != "running" ]; then
    needs_heal+=("$service:$state")
  fi
done

if [ "${#needs_heal[@]}" -eq 0 ]; then
  log "stack healthy: ${#services[@]} services running"
  exit 0
fi

log "healing stack; non-running services: ${needs_heal[*]}"
docker compose up -d --remove-orphans
log "compose up -d finished"
