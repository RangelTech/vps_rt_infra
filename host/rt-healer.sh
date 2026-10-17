#!/usr/bin/env bash
# rt-healer: recoloca de pe, por stack, containers que caíram (Exited) ou sumiram e TEM politica de restart.
# Regras: respeita /opt/platform/.maintenance; nunca usa --remove-orphans nem down; ignora airflow|capital|hermes-relay;
# no maximo 3 tentativas por container por hora. Logs vao para o journald (stdout/stderr do servico).
set -uo pipefail

BASE="${RT_BASE:-/opt/platform}"
STATE_DIR="${RT_HEALER_STATE:-/var/lib/rt-healer}"
MAX_ATTEMPTS=3
WINDOW=3600
SKIP_RE='airflow|capital|hermes-relay'
# projeto do compose principal (compose/docker-compose.yml na raiz de compose/)
MAIN_PROJECT="${RT_MAIN_PROJECT:-platform}"

log() { echo "rt-healer: $*"; }

[ -e "$BASE/.maintenance" ] && { log "modo manutencao ativo, nada a fazer"; exit 0; }
[ "$(hostname)" = "${RT_EXPECTED_HOST:-vmi3468840}" ] || { log "host inesperado: $(hostname)" >&2; exit 2; }

install -d -m 0700 "$STATE_DIR"
exec 9>"$STATE_DIR/lock"
flock -n 9 || { log "outra execucao em andamento"; exit 0; }

ATT="$STATE_DIR/attempts"
touch "$ATT"
now="$(date +%s)"
# descarta tentativas fora da janela
awk -v n="$now" -v w="$WINDOW" '$1 > n - w' "$ATT" > "$ATT.new" && mv "$ATT.new" "$ATT"

attempts_for() { awk -v k="$1" '$2 == k' "$ATT" | wc -l; }

# servicos com restart != no/vazio do compose (um por linha)
restartable_services() { # project file [envfile]
  docker compose -p "$1" -f "$2" ${3:+--env-file "$3"} config --format json 2>/dev/null | python3 -c '
import json, sys
try:
    cfg = json.load(sys.stdin)
except Exception:
    sys.exit(0)
for name, svc in (cfg.get("services") or {}).items():
    r = svc.get("restart") or ""
    if r and r != "no":
        print(name)
'
}

heal_stack() { # project file [envfile]
  local project="$1" file="$2" envf="${3:-}" svc cname state key n
  [[ "$project" =~ $SKIP_RE ]] && { log "stack $project ignorada"; return; }
  local targets=()
  while IFS= read -r svc; do
    [ -n "$svc" ] || continue
    [[ "$svc" =~ $SKIP_RE ]] && continue
    cname="$(docker ps -a --filter "label=com.docker.compose.project=$project" --filter "label=com.docker.compose.service=$svc" --format '{{.Names}}' | head -n1)"
    if [ -n "$cname" ]; then
      [[ "$cname" =~ $SKIP_RE ]] && continue
      state="$(docker inspect -f '{{.State.Status}}' "$cname" 2>/dev/null || echo unknown)"
      [ "$state" = "exited" ] || continue
    else
      cname="$project/$svc"   # ausente
    fi
    key="$project/$svc"
    n="$(attempts_for "$key")"
    if [ "$n" -ge "$MAX_ATTEMPTS" ]; then
      log "ALERTA $key: $n tentativas na ultima hora, desistindo ate a janela esvaziar"
      continue
    fi
    echo "$now $key" >> "$ATT"
    targets+=("$svc")
    log "$key ($cname) fora do ar, tentativa $((n + 1))/$MAX_ATTEMPTS"
  done < <(restartable_services "$project" "$file" "$envf")

  for svc in "${targets[@]}"; do
    if docker compose -p "$project" -f "$file" ${envf:+--env-file "$envf"} up -d --no-build --pull never --no-deps "$svc"; then
      log "$project/$svc: up -d ok"
    else
      log "$project/$svc: up -d FALHOU" >&2
    fi
  done
}

find_compose_file() { # dir
  local f
  for f in compose.yml compose.yaml docker-compose.yml docker-compose.yaml; do
    [ -f "$1/$f" ] && { echo "$1/$f"; return 0; }
  done
  return 1
}

if f="$(find_compose_file "$BASE/compose")"; then
  heal_stack "$MAIN_PROJECT" "$f"
fi
for d in "$BASE"/compose/*/; do
  [ -d "$d" ] || continue
  name="$(basename "$d")"
  f="$(find_compose_file "${d%/}")" || continue
  heal_stack "$name" "$f"
done

# stacks versionadas (/opt/platform/stacks/<nome>/compose.yml) com .release.env escrito pelo deploy.sh
for d in "$BASE"/stacks/*/; do
  [ -d "$d" ] || continue
  name="$(basename "$d")"
  f="${d}compose.yml"
  [ -f "$f" ] || continue
  e="${d}.release.env"
  [ -f "$e" ] || e=""
  heal_stack "$name" "$f" "$e"
done
exit 0
