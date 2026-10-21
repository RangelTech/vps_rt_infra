#!/usr/bin/env bash
# Smoke LOCAL da pilha canais: Synapse + Postgres + 3 bridges mautrix com os mesmos templates da VPS.
# Uso: smoke-local/up.sh <dir-de-dados> [up|down|reset]
# Segredos aleatorios em <dir>/canais.env (fora do git). Gateway roda no host (porta 8000).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
D="${1:?dir de dados}"; CMD="${2:-up}"; mkdir -p "$D"; D="$(cd "$D" && pwd)"
export CANAIS_DATA="$D" COMPOSE_PROJECT_NAME=canais-smoke
C=(docker compose --env-file "$HERE/versions.env" --env-file "$D/canais.env" -f "$HERE/compose.yml" -f "$HERE/smoke-local/override.yml")
case "$CMD" in
  down) "${C[@]}" down; exit 0;;
  reset) "${C[@]}" down -v 2>/dev/null || true; rm -rf "$D"/{rendered,synapse,mautrix-*}; rm -f "$D/canais.env";;
esac
if [ ! -f "$D/canais.env" ]; then
  r() { openssl rand -hex 24; }
  cat > "$D/canais.env" <<ENV
MATRIX_SERVER_NAME=matrix.internal
TIMEZONE=UTC
CANAIS_DATA=$D
MATRIX_POSTGRES_PASSWORD=$(r)
SYNAPSE_REGISTRATION_SHARED_SECRET=$(r)
SYNAPSE_MACAROON_SECRET_KEY=$(r)
SYNAPSE_FORM_SECRET=$(r)
GATEWAY_AS_ID=luar-gateway
GATEWAY_AS_URL=http://host.docker.internal:8000
GATEWAY_AS_TOKEN=$(r)
GATEWAY_HS_TOKEN=$(r)
GATEWAY_SENDER_LOCALPART=luar_gateway
META_AS_TOKEN=$(r)
META_HS_TOKEN=$(r)
INSTAGRAM_AS_TOKEN=$(r)
INSTAGRAM_HS_TOKEN=$(r)
WHATSAPP_AS_TOKEN=$(r)
WHATSAPP_HS_TOKEN=$(r)
BRIDGE_PROVISIONING_SECRET=$(r)
BRIDGE_ADMIN_MXID=@luar_admin:matrix.internal
BACKFILL_DAYS=60
ENV
  chmod 600 "$D/canais.env"
fi
bash "$HERE/scripts/render-configs.sh" --env "$D/canais.env" --out "$D/rendered" >/dev/null
mkdir -p "$D"/synapse "$D"/mautrix-meta "$D"/mautrix-instagram "$D"/mautrix-whatsapp
"${C[@]}" up -d
