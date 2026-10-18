#!/usr/bin/env bash
# Deploy de UM servico a partir do releases/<servico>.lock (roda NA VPS, chamado pelo workflow deploy.yml por SSH).
#   1) baixa o artefato (docker-archive) da GitHub Release e VERIFICA sha256 e image id;
#   2) confere as variaveis de runtime exigidas (env_required) em /opt/platform/secrets/<servico>.env;
#   3) docker load + tag local imutavel;
#   4) pre-deploy opcional (one-shot do compose, ex.: migracao do Rails); falhou => aborta sem trocar nada;
#   5) docker compose up -d (sem build) SO dos servicos do lock; stacks com varias imagens mantem as outras variaveis no .release.env;
#   6) healthcheck real (status do HEALTHCHECK de cada container alvo, timeout por servico); falhou => ROLLBACK automatico.
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
TARGETS="$(rt_lock_get "$LOCK" compose_service)"; TARGETS="${TARGETS:-$SERVICE}"
PRE="$(rt_lock_get "$LOCK" pre_deploy_service)"
HC_TIMEOUT="$(rt_lock_get "$LOCK" healthcheck_timeout)"; HC_TIMEOUT="${HC_TIMEOUT:-90}"
ENV_REQ="$(rt_lock_get "$LOCK" env_required)"
VAR="$(echo "$SERVICE" | tr 'a-z-' 'A-Z_')_IMAGE"
STATE="$BASE/state"; ART="$BASE/data/artifacts"; mkdir -p "$STATE" "$ART"
COMPOSE="$BASE/stacks/$STACK/compose.yml"
ENVF="$BASE/stacks/$STACK/.release.env"
SECF="$BASE/secrets/$SERVICE.env"
SHORT="${IMG_ID#sha256:}"; SHORT="${SHORT:0:12}"
NEW_TAG="rt/$SERVICE:$SHORT"
PREV_TAG="$(cat "$STATE/$SERVICE.current" 2>/dev/null || true)"
IFS=',' read -r -a TARGET_LIST <<< "$TARGETS"

rt_log "deploy $SERVICE $VERSION ($SHORT) stack=$STACK alvos=$TARGETS anterior=${PREV_TAG:-nenhuma}"

# 1) artefato verificado
FILE="$ART/$SERVICE-$VERSION.tar.gz"
if [ ! -s "$FILE" ] || ! echo "$SHA  $FILE" | sha256sum -c - >/dev/null 2>&1; then
  curl -fsSL -o "$FILE.part" "$URL"
  echo "$SHA  $FILE.part" | sha256sum -c - || { echo "sha256 do artefato NAO confere - abortando" >&2; rm -f "$FILE.part"; exit 3; }
  mv "$FILE.part" "$FILE"
fi

# 2) variaveis de runtime exigidas (fail-fast: a variavel precisa existir no arquivo; valor vazio e permitido, ex.: S3_PUBLIC_BASE_URL)
if [ -n "$ENV_REQ" ]; then
  missing=""
  IFS=',' read -r -a REQ_LIST <<< "$ENV_REQ"
  for v in "${REQ_LIST[@]}"; do
    grep -Eq "^${v}=" "$SECF" 2>/dev/null || missing="$missing $v"
  done
  [ -z "$missing" ] || { echo "variaveis de runtime ausentes em $SECF:$missing - abortando" >&2; exit 4; }
fi

# 3) load + checagem do image id + tag imutavel local
GOT_ID="sha256:$(gunzip -c "$FILE" | tar -xO manifest.json | python3 -c "import sys,json,re;print(re.sub(r'^.*/','',json.load(sys.stdin)[0]['Config']).replace('.json',''))")"
[ "$GOT_ID" = "$IMG_ID" ] || { echo "image id (digest da config) divergente: esperado $IMG_ID, obtido $GOT_ID" >&2; exit 3; }
LOADED="$(gunzip -c "$FILE" | docker load | sed -n 's/^Loaded image: //p' | head -n1)"
[ -n "$LOADED" ] || { echo "docker load nao informou a imagem" >&2; exit 3; }
docker tag "$LOADED" "$NEW_TAG"

set_image() { # $1 = tag ; mantem as outras variaveis do .release.env (stacks multi-imagem)
  touch "$ENVF"
  grep -v "^${VAR}=" "$ENVF" > "$ENVF.tmp" || true
  printf '%s=%s\n' "$VAR" "$1" >> "$ENVF.tmp"
  mv "$ENVF.tmp" "$ENVF"
}
dc() { docker compose -p "$STACK" -f "$COMPOSE" --env-file "$ENVF" "$@"; }
up() { set_image "$1"; dc up -d --no-build --no-deps --pull never "${TARGET_LIST[@]}"; }

wait_healthy() { # espera o HEALTHCHECK de cada container alvo
  local t cname st run n=$(( HC_TIMEOUT / 2 ))
  for t in "${TARGET_LIST[@]}"; do
    cname="$(dc ps -q "$t" 2>/dev/null | head -n1)"
    [ -n "$cname" ] || return 1
    local ok=0
    for _ in $(seq 1 "$n"); do
      st="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cname")"
      run="$(docker inspect --format '{{.State.Running}}' "$cname")"
      [ "$run" = "true" ] || return 1
      [ "$st" = "none" ] && { echo "container $t sem HEALTHCHECK: reprovado por politica" >&2; return 1; }
      [ "$st" = "healthy" ] && { ok=1; break; }
      sleep 2
    done
    [ "$ok" = "1" ] || return 1
  done
  return 0
}

# 4) pre-deploy (one-shot): roda com a imagem NOVA, antes de trocar os containers
if [ -n "$PRE" ]; then
  set_image "$NEW_TAG"
  rt_log "pre-deploy: $PRE"
  if ! dc --profile oneshot run --rm --no-deps "$PRE"; then
    echo "pre-deploy ($PRE) falhou - nada foi trocado" >&2
    [ -n "$PREV_TAG" ] && set_image "$PREV_TAG"
    exit 5
  fi
fi

# 5) subir e 6) verificar
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
for t in "${TARGET_LIST[@]}"; do docker logs --tail 30 "$(dc ps -q "$t" | head -n1)" 2>&1 | tail -30 || true; done
if [ -n "$PREV_TAG" ] && docker image inspect "$PREV_TAG" >/dev/null 2>&1; then
  rt_log "ROLLBACK para $PREV_TAG"
  up "$PREV_TAG"
  if wait_healthy; then rt_log "rollback concluido e saudavel"; else rt_log "ATENCAO: rollback tambem nao ficou saudavel"; fi
else
  rt_log "sem versao anterior: parando os containers reprovados"
  dc stop "${TARGET_LIST[@]}" || true
fi
exit 1
