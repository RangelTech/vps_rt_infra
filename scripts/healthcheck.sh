#!/usr/bin/env bash
# Quick manual healthcheck for all stack endpoints. Also usable as a base for
# an Uptime Kuma "push" style monitor if desired later.

set -euo pipefail

BASE_DIR="/opt/platform"
ENV_FILE="${BASE_DIR}/compose/.env"

# shellcheck disable=SC1090
set -a; source "${ENV_FILE}"; set +a

check() {
  local name="$1" url="$2"
  if curl -fsS -o /dev/null -m 5 "${url}"; then
    echo "OK   ${name} (${url})"
  else
    echo "FAIL ${name} (${url})"
  fi
}

check "9route"            "https://9route.${ROOT_DOMAIN}"
check "Grafana"            "https://grafana.${ROOT_DOMAIN}/api/health"
check "MinIO"              "https://storage.${ROOT_DOMAIN}/minio/health/live"
check "pgAdmin"            "https://pgadmin.${ROOT_DOMAIN}/misc/ping"
check "Uptime Kuma"        "https://uptime.${ROOT_DOMAIN}"
check "Traefik dashboard"  "https://traefik.${ROOT_DOMAIN}"
check "VS Code Server"     "https://code.${ROOT_DOMAIN}"
check "Prometheus"         "https://prometheus.${ROOT_DOMAIN}/-/healthy"
check "Loki"               "https://logs.${ROOT_DOMAIN}/ready"
