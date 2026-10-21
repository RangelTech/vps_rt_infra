#!/usr/bin/env bash
# Restaura um backup de backup-before-upgrade.sh. Dois modos:
#   restore.sh <dir> --teste     # restaura os dumps num Postgres DESCARTAVEL (container temporario) e confere tabelas. Nao toca producao.
#   restore.sh <dir> --aplicar   # SUBSTITUI os bancos e arquivos da pilha. Exige a pilha parada e a digitacao da confirmacao.
# Nada e apagado: antes de sobrescrever, o estado atual vai para <CANAIS_DATA>/quarentena/<timestamp>/.
set -euo pipefail
B="${1:?diretorio do backup}"; MODE="${2:?--teste | --aplicar}"
[ -d "$B" ] || { echo "backup inexistente: $B" >&2; exit 1; }
( cd "$B" && sha256sum -c SHA256SUMS )
D="${CANAIS_DATA:-/opt/platform/data/canais}"
case "$MODE" in
--teste)
  N="canais-restore-teste-$$"; trap 'docker rm -f "$N" >/dev/null 2>&1 || true' EXIT
  docker run -d --name "$N" -e POSTGRES_PASSWORD=descartavel --network none "${MATRIX_POSTGRES_IMAGE:-postgres:16}" >/dev/null
  for i in $(seq 1 30); do docker exec "$N" pg_isready -U postgres >/dev/null 2>&1 && break; sleep 1; done
  for f in "$B"/pg/*.dump; do
    db="$(basename "$f" .dump)"
    docker exec "$N" createdb -U postgres -T template0 -E UTF8 --lc-collate=C --lc-ctype=C "$db"
    docker exec -i "$N" pg_restore -U postgres -d "$db" --no-owner < "$f"
    t=$(docker exec "$N" psql -U postgres -d "$db" -Atc "select count(*) from pg_tables where schemaname='public'")
    [ "$t" -gt 0 ] || { echo "FALHA: $db sem tabelas apos restore" >&2; exit 3; }
    echo "ok  $db tabelas=$t"
  done
  tar -tzf "$B/arquivos.tgz" >/dev/null && echo "ok  arquivos.tgz legivel"
  echo "RESTORE DE TESTE OK (container descartavel removido)";;
--aplicar)
  [ "$(hostname)" = "vmi3468840" ] || { echo "host inesperado" >&2; exit 2; }
  [ -z "$(docker ps -q --filter 'name=^canais-' --filter 'health=healthy')" ] || [ -n "${RESTORE_PILHA_PARADA:-}" ] || { echo "pare a pilha antes (docker compose -p canais stop) e exporte RESTORE_PILHA_PARADA=1" >&2; exit 4; }
  read -r -p "Digite RESTAURAR para substituir os dados atuais por $B: " c; [ "$c" = RESTAURAR ] || exit 5
  Q="$D/quarentena/$(date +%Y%m%d-%H%M%S)"; mkdir -p "$Q"
  for d in synapse mautrix-meta mautrix-instagram mautrix-whatsapp tiktok-sessions; do [ -e "$D/$d" ] && mv "$D/$d" "$Q/$d"; done
  tar -C "$D" -xzf "$B/arquivos.tgz"
  docker start canais-matrix-postgres >/dev/null 2>&1 || true
  for f in "$B"/pg/*.dump; do
    db="$(basename "$f" .dump)"
    docker exec canais-matrix-postgres psql -U matrix_admin -d postgres -c "ALTER DATABASE $db RENAME TO ${db}_pre_restore_$(date +%s)" || true
    docker exec canais-matrix-postgres createdb -U matrix_admin -T template0 -E UTF8 --lc-collate=C --lc-ctype=C "$db"
    docker exec -i canais-matrix-postgres pg_restore -U matrix_admin -d "$db" --no-owner < "$f"
  done
  echo "restaurado. Estado anterior em $Q e bancos *_pre_restore_* (nao apagados). Suba a pilha por release e confira login preservado.";;
*) echo "modo invalido" >&2; exit 1;;
esac
