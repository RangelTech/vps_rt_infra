#!/usr/bin/env bash
# BACKUP obrigatorio ANTES de atualizar qualquer imagem da pilha `canais` (bridge, Synapse, ReLttk).
# Gera $CANAIS_DATA/backups/<timestamp>/ com: dumps dos 4 bancos, tar dos dados (Synapse, bridges, sessoes TikTok),
# versions.env vigente e os digests EM EXECUCAO (para rollback). Nao para nada; so le. Falha se algo vier vazio.
# Depois copie para fora da VPS (backup.sh diario inclui $CANAIS_DATA/backups pelas EXTRA_PATHS).
set -euo pipefail
[ "$(hostname)" = "vmi3468840" ] || { echo "host inesperado" >&2; exit 2; }
D="${CANAIS_DATA:-/opt/platform/data/canais}"; HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TS="$(date +%Y%m%d-%H%M%S)"; B="$D/backups/$TS"; umask 077; mkdir -p "$B/pg"
PG=canais-matrix-postgres
for db in synapse mautrix_meta mautrix_instagram mautrix_whatsapp; do
  docker exec "$PG" pg_dump -U matrix_admin -Fc "$db" > "$B/pg/$db.dump"
  sz=$(stat -c %s "$B/pg/$db.dump"); [ "$sz" -gt 2000 ] || { echo "FALHA: dump pequeno ($sz B): $db" >&2; exit 3; }
  echo "ok  $db ${sz}B"
done
# estado de arquivos (signing key do Synapse, media, dados dos bridges, sessoes dos workers TikTok) - leitura
tar -C "$D" -czf "$B/arquivos.tgz" synapse mautrix-meta mautrix-instagram mautrix-whatsapp tiktok-sessions
[ "$(stat -c %s "$B/arquivos.tgz")" -gt 100 ] || { echo "FALHA: tar vazio" >&2; exit 3; }
cp "$HERE/versions.env" "$B/versions.env.anterior"
docker ps --filter 'name=^canais-' --format '{{.Names}} {{.Image}}' | while read -r n img; do
  echo "$n $img $(docker inspect --format '{{.Image}}' "$n")"; done > "$B/em_execucao.txt"
( cd "$B" && sha256sum pg/* arquivos.tgz versions.env.anterior > SHA256SUMS )
echo "$TS" > "$D/backups/ULTIMO_ANTES_DE_ATUALIZAR"
echo "backup pronto: $B (restore: restore.sh $B)"
