#!/usr/bin/env bash
# Rollback de IMAGEM da pilha `canais`: volta o versions.env para o do ultimo backup e recria so os servicos de bridge.
# Rollback de DADOS (migracao de banco do bridge sem volta) = restore.sh <backup> --aplicar. Nao e automatico.
# Uso: rollback.sh [<dir-backup>]   (padrao: ultimo backup antes de atualizar)
set -euo pipefail
[ "$(hostname)" = "vmi3468840" ] || { echo "host inesperado" >&2; exit 2; }
D="${CANAIS_DATA:-/opt/platform/data/canais}"; HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
B="${1:-$D/backups/$(cat "$D/backups/ULTIMO_ANTES_DE_ATUALIZAR")}"
[ -f "$B/versions.env.anterior" ] || { echo "sem versions.env.anterior em $B" >&2; exit 1; }
cp "$HERE/versions.env" "$HERE/versions.env.$(date +%Y%m%d-%H%M%S).falhou"
cp "$B/versions.env.anterior" "$HERE/versions.env"
if grep -q DIGEST_A_PREENCHER "$HERE/versions.env"; then echo "versions.env anterior ainda tem marcador: abortando" >&2; exit 3; fi
cd "$HERE"
docker compose -p canais --env-file versions.env --env-file /opt/platform/secrets/canais.env -f compose.yml up -d --no-build --pull never mautrix-meta mautrix-instagram mautrix-whatsapp synapse
docker compose -p canais -f compose.yml ps
echo "imagens revertidas para $B/versions.env.anterior. Confira: docker ps (saudavel) e login preservado."
