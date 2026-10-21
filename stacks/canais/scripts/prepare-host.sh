#!/usr/bin/env bash
# Prepara diretorios e donos NA VPS antes da 1a subida (root). Idempotente. NAO inicia container.
# Problemas conhecidos de producao (28/08/2026):
#   (1) config do Synapse fora de /data (resolvido no compose: /etc/synapse);
#   (2) bridges precisam de saida para a internet (resolvido: rede canais_egress);
#   (3) matrix-postgres exige diretorio de dados 999:999 -> chown abaixo.
set -euo pipefail
[ "$(hostname)" = "vmi3468840" ] || { echo "host inesperado: $(hostname)" >&2; exit 2; }
D="${CANAIS_DATA:-/opt/platform/data/canais}"
mkdir -p "$D"/{matrix-postgres,synapse,mautrix-meta,mautrix-instagram,mautrix-whatsapp,tiktok-sessions/_molde,rendered,backups}
chown 999:999   "$D/matrix-postgres"; chmod 0700 "$D/matrix-postgres"
chown 991:991   "$D/synapse"
# imagens dock.mau.dev rodam como 1337:1337 por padrao (conferir com `docker inspect` na CH-0)
chown 1337:1337 "$D/mautrix-meta" "$D/mautrix-instagram" "$D/mautrix-whatsapp"
chmod 0700 "$D/tiktok-sessions" "$D/rendered" "$D/backups"
echo "host preparado em $D"
