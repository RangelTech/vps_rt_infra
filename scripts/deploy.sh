#!/usr/bin/env bash
# Deploy de UM servico a partir do releases/<servico>.lock (roda NA VPS, chamado pelo workflow deploy.yml por SSH).
#   1) baixa o artefato (docker-archive) da GitHub Release e VERIFICA sha256 e image id;
#   2) docker load + tag local imutavel;
#   3) docker compose up -d (sem build);
#   4) healthcheck real (status do HEALTHCHECK do container); falhou => ROLLBACK automatico para a imagem anterior.
# Nunca: build na VPS, tag movel, `|| true` no healthcheck, --remove-orphans, down -v.
set -euo pipefail
. "$(dirname "$0")/lib.sh"
rt_guard_host

SERVICE="${1:?uso: deploy.sh <servico>}"
BASE=/opt/platform
LOCK="$BASE/releases/$SERVICE.lock"
[ -f "$LOCK" ] || { echo "lock nao encontrado: $LOCK" >&2; exit 2; }

STACK="$(rt_lock_get "$LOCK" stack)"
URL="$(rt_lock_get "$LOCK" artifact_url)"
SHA="$(rt_lock_get "$LOCK" artifact_sha256)"
IMG_ID="$(rt_lock_get "$LOCK" image_id)"
VERSION="$(rt_lock_get "$LOCK" version)"
VAR="$(echo "$SERVICE" | tr 'a-z-' 'A-Z_')_IMAGE"
STATE="$BASE/state"; ART="$BASE/data/artifacts"; mkdir -p "$STATE" "$ART"
COMPOSE="$BASE/stacks/$STACK/compose.yml"
ENVF="$BASE/stacks/$STACK/.release.env"
SHORT="${IMG_ID#sha256:}"; SHORT="${SHORT:0:12}"
NEW_TAG="rt/$SERVICE:$SHORT"
PREV_TAG="$(cat "$STATE/$SERVICE.current" 2>/dev/null || true)"

rt_log "deploy $SERVICE $VERSION ($SHORT) stack=$STACK anterior=${PREV_TAG:-nenhuma}"

# 1) artefato verificado
FILE="$ART/$SERVICE-$VERSION.tar.gz"
if [ ! -s "$FILE" ] || ! echo "$SHA  $FILE" | sha256sum -c - >/dev/null 2>&1; then
  curl -fsSL -o "$FILE.part" "$URL"
  echo "$SHA  $FILE.part" | sha256sum -c - || { echo "sha256 do artefato NAO confere - abortando" >&2; rm -f "$FILE.part"; exit 3; }
  mv "$FILE.part" "$FILE"
fi

# 2) load + checagem do image id + tag imutavel local
LOADED="$(gunzip -c "$FILE" | docker load | sed -n 's/^Loaded image: //p' | head -n1)"
GOT_ID="$(docker image inspect --format '{{.Id}}' "$LOADED")"
[ "$GOT_ID" = "$IMG_ID" ] || { echo "image id divergente: esperado $IMG_ID, obtido $GOT_ID" >&2; exit 3; }
docker tag "$LOADED" "$NEW_TAG"

up() { # $1 = tag
  printf '%s=%s\n' "$VAR" "$1" > "$ENVF"
  docker compose -p "$STACK" -f "$COMPOSE" --env-file "$ENVF" up -d --no-build --no-deps --pull never
}

wait_healthy() { # espera o HEALTHCHECK do container (ate 90s)
  local cname; cname="$(docker compose -p "$STACK" -f "$COMPOSE" --env-file "$ENVF" ps -q "$SERVICE_CONTAINER" 2>/dev/null | head -n1)"
  [ -n "$cname" ] || return 1
  for _ in $(seq 1 45); do
    st="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cname")"
    run="$(docker inspect --format '{{.State.Running}}' "$cname")"
    [ "$run" = "true" ] || return 1
    [ "$st" = "healthy" ] && return 0
    [ "$st" = "none" ] && { echo "container sem HEALTHCHECK: reprovado por politica" >&2; return 1; }
    sleep 2
  done
  return 1
}
SERVICE_CONTAINER="$(rt_lock_get "$LOCK" compose_service)"; SERVICE_CONTAINER="${SERVICE_CONTAINER:-$SERVICE}"

up "$NEW_TAG"
if wait_healthy; then
  echo "$NEW_TAG" > "$STATE/$SERVICE.current"
  printf '{"service":"%s","version":"%s","image":"%s","deployed_at":"%s"}\n' "$SERVICE" "$VERSION" "$NEW_TAG" "$(date -Is)" > "$STATE/$SERVICE.last_deploy.json"
  # mantem so as 2 imagens mais recentes do servico
  docker images --format '{{.Repository}}:{{.Tag}} {{.CreatedAt}}' "rt/$SERVICE" | sort -k2 -r | awk 'NR>2{print $1}' | xargs -r docker rmi >/dev/null 2>&1 || true
  rt_log "OK $SERVICE $VERSION saudavel"
  exit 0
fi

rt_log "FALHA no healthcheck de $SERVICE $VERSION"
docker logs --tail 30 "$SERVICE_CONTAINER" 2>&1 | tail -30 || true
if [ -n "$PREV_TAG" ] && docker image inspect "$PREV_TAG" >/dev/null 2>&1; then
  rt_log "ROLLBACK para $PREV_TAG"
  up "$PREV_TAG"
  if wait_healthy; then rt_log "rollback concluido e saudavel"; else rt_log "ATENCAO: rollback tambem nao ficou saudavel"; fi
else
  rt_log "sem versao anterior: parando o container reprovado"
  docker compose -p "$STACK" -f "$COMPOSE" --env-file "$ENVF" stop "$SERVICE_CONTAINER" || true
fi
exit 1
