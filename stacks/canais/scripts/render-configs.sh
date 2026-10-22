#!/usr/bin/env bash
# Renderiza templates/ -> arquivos de config finais (com segredos), em modo 0600, FORA do git.
#   render-configs.sh                      # usa /opt/platform/secrets/canais.env, grava em $CANAIS_DATA/rendered (guarda de host)
#   render-configs.sh --env F --out DIR    # modo seco/validacao (qualquer maquina), sem guarda de host
# Nao inicia nem altera container algum.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="/opt/platform/secrets/canais.env"; OUT=""; DRY=0
while [ $# -gt 0 ]; do case "$1" in --env) ENV_FILE="$2"; DRY=1; shift 2;; --out) OUT="$2"; DRY=1; shift 2;; *) echo "arg desconhecido: $1" >&2; exit 1;; esac; done
[ "$DRY" = 1 ] || { [ "$(hostname)" = "vmi3468840" ] || { echo "host inesperado" >&2; exit 2; }; }
[ -f "$ENV_FILE" ] || { echo "sem $ENV_FILE" >&2; exit 1; }
set -a; . "$ENV_FILE"; set +a
: "${MATRIX_SERVER_NAME:?}"; CANAIS_DATA="${CANAIS_DATA:-/opt/platform/data/canais}"
OUT="${OUT:-$CANAIS_DATA/rendered}"
# servidor com pontos escapados para uso em regex dos registros
export MATRIX_SERVER_NAME_RE="${MATRIX_SERVER_NAME//./\\.}"
VARS='${MATRIX_SERVER_NAME} ${MATRIX_SERVER_NAME_RE} ${MATRIX_POSTGRES_PASSWORD} ${SYNAPSE_REGISTRATION_SHARED_SECRET} ${SYNAPSE_MACAROON_SECRET_KEY} ${SYNAPSE_FORM_SECRET} ${GATEWAY_AS_ID} ${GATEWAY_AS_URL} ${GATEWAY_AS_TOKEN} ${GATEWAY_HS_TOKEN} ${GATEWAY_SENDER_LOCALPART} ${META_AS_TOKEN} ${META_HS_TOKEN} ${INSTAGRAM_AS_TOKEN} ${INSTAGRAM_HS_TOKEN} ${WHATSAPP_AS_TOKEN} ${WHATSAPP_HS_TOKEN} ${BRIDGE_PROVISIONING_SECRET} ${BRIDGE_ADMIN_MXID} ${BACKFILL_DAYS}'
command -v envsubst >/dev/null || { echo "envsubst ausente (pacote gettext-base)" >&2; exit 1; }
umask 077
mkdir -p "$OUT/synapse" "$OUT/registrations" "$OUT/bridges"
render() { envsubst "$VARS" < "$1" > "$2"; chmod 0600 "$2"; echo "ok  $2"; }
render "$HERE/templates/synapse/homeserver.yaml.tmpl" "$OUT/synapse/homeserver.yaml"
for r in gateway meta instagram whatsapp; do render "$HERE/templates/registrations/$r.yaml.tmpl" "$OUT/registrations/$r.yaml"; done
for b in meta instagram whatsapp; do render "$HERE/templates/bridges/$b.yaml.tmpl" "$OUT/bridges/$b.yaml"; done
# placeholders nao resolvidos viram erro (variavel faltando no .env)
if grep -rn '\${' "$OUT" >/dev/null 2>&1; then echo "ERRO: variavel nao resolvida em $OUT" >&2; grep -rn '\${' "$OUT" | sed -E 's/:.*//' | sort -u >&2; exit 3; fi
# Donos/modos para os containers sem root (Synapse 991, bridges 1337): achado no apply real de 21/10.
# Segredos so ficam legiveis ao dono do container; registrations (tokens dos dois lados) precisam ser lidos pelo Synapse
# e pelo bridge correspondente, entao 0644 dentro de um diretorio que so o host alcanca (rendered 0711, host unico).
if [ "$DRY" = 0 ]; then
  chmod 0711 "$OUT" "$OUT/synapse" "$OUT/registrations" "$OUT/bridges"
  chown 991:991 "$OUT/synapse/homeserver.yaml"; chmod 0400 "$OUT/synapse/homeserver.yaml"
  chown 1337:1337 "$OUT"/bridges/*.yaml; chmod 0400 "$OUT"/bridges/*.yaml
  chmod 0644 "$OUT"/registrations/*.yaml
fi
echo "render concluido em $OUT"
