#!/usr/bin/env bash
# Applies services.json: starts services whose flag is true (via Docker
# Compose profiles), stops the ones whose flag is false. Compose profiles
# only decide what `up -d` INCLUDES — they don't stop an already-running
# container on their own, so the explicit `stop` loop below is required.
#
# Known dependency: grafana's compose service depends_on prometheus+loki.
# If grafana=true but prometheus/loki=false in services.json, `up` fails
# (depends_on target not part of the active profile set). This script
# enforces that dependency automatically — see below.

set -euo pipefail

COMPOSE_DIR="${RT_COMPOSE_DIR:-/opt/platform/compose}"
SERVICES_JSON="${RT_SERVICES_JSON:-/opt/platform/services.json}"
LOG_TAG="${RT_APPLY_SERVICES_LOG_TAG:-rt-apply-services}"

log() {
  echo "[$LOG_TAG] $*"
  logger -t "$LOG_TAG" -- "$*" 2>/dev/null || true
}

if [ ! -f "$SERVICES_JSON" ]; then
  log "missing $SERVICES_JSON — nothing to apply"
  exit 1
fi

if [ ! -f "$COMPOSE_DIR/docker-compose.yml" ]; then
  log "missing compose file at $COMPOSE_DIR/docker-compose.yml"
  exit 1
fi

cd "$COMPOSE_DIR"

# grafana implies prometheus+loki (compose depends_on requires them in the
# active profile set, or `up` fails outright).
enabled_json="$(jq 'if .grafana == true then .prometheus = true | .loki = true else . end' "$SERVICES_JSON")"

mapfile -t enabled < <(echo "$enabled_json" | jq -r 'to_entries[] | select(.value==true) | .key')
mapfile -t disabled < <(echo "$enabled_json" | jq -r 'to_entries[] | select(.value==false) | .key')

profiles_csv="$(IFS=,; echo "${enabled[*]:-}")"

log "enabled: ${enabled[*]:-none} | disabled: ${disabled[*]:-none}"

if [ -n "$profiles_csv" ]; then
  COMPOSE_PROFILES="$profiles_csv" docker compose up -d
else
  log "no optional profile enabled, skipping profiled up (essential services keep running via their own restart policy / healer)"
fi

for svc in "${disabled[@]:-}"; do
  [ -z "$svc" ] && continue
  # `docker compose stop <svc>` fails ("no such service: X") when the
  # service's depends_on points at another profile-gated service that isn't
  # in the current invocation's profile set (e.g. grafana -> prometheus/loki)
  # — Compose tries to resolve the whole dependency graph even for a single
  # service, not just the one being stopped. Using `docker stop`/`docker
  # inspect` directly bypasses that resolution entirely; safe here because
  # every service in this compose file sets `container_name` equal to its
  # service key, so the container name IS the service name.
  if docker inspect "$svc" >/dev/null 2>&1; then
    log "stopping disabled service: $svc"
    docker stop "$svc" >/dev/null || true
  fi
done

log "apply-services finished"
