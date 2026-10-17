#!/usr/bin/env bash
# Aplica uma stack versionada em stacks/<nome>/ na VPS (camada B: manual, com backup recente).
# Uso (como root na VPS, apos copiar stacks/<nome>/ para /opt/platform/stacks/<nome>/):
#   apply-stack.sh <nome> [servico...]
# Nunca usa --remove-orphans, down, nem prune. Valida o compose antes de aplicar.
set -euo pipefail
NAME="${1:?stack}"; shift || true
DIR="/opt/platform/stacks/$NAME"
[ "$(hostname)" = "vmi3468840" ] || { echo "host inesperado" >&2; exit 2; }
[ -f "$DIR/compose.yml" ] || { echo "sem $DIR/compose.yml" >&2; exit 1; }

# backup recente (<24h) e obrigatorio
last="/opt/platform/data/backups/last_ok.json"
if [ -f "$last" ]; then
  age=$(( $(date +%s) - $(date -d "$(python3 -c 'import json;print(json.load(open("'$last'"))["finished_at"])')" +%s) ))
  [ "$age" -lt 86400 ] || { echo "ultimo backup tem mais de 24h: rode backup.sh antes" >&2; exit 3; }
fi

cd "$DIR"
docker compose -p "$NAME" -f compose.yml config -q
docker compose -p "$NAME" -f compose.yml up -d --no-build --pull never "$@"
docker compose -p "$NAME" -f compose.yml ps
