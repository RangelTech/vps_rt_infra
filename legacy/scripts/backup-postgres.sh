#!/usr/bin/env bash
# Daily/weekly Postgres backup using pg_dump + restic (external repository).
# Runs on the VPS via cron (installed by install-backup-cron.sh).

set -euo pipefail

BASE_DIR="/opt/platform"
ENV_FILE="${BASE_DIR}/compose/.env"
DUMP_DIR="${BASE_DIR}/data/backups/postgres"
DATE_TAG=$(date +%Y%m%d-%H%M%S)

# Le o .env linha a linha em vez de `source` -- achado real (21/08/2026):
# `source` avalia o valor como bash, e senhas com parenteses/aspas (ex.:
# POSTGRES_ADMIN_PASSWORD) quebram com "syntax error near unexpected
# token". O backup falhou silenciosamente (log cheio de erro, cron
# reportou sucesso porque o erro de source nao para o script com
# `set -e` em subshell de source) desde que o cron foi instalado.
while IFS='=' read -r key value; do
  [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
  export "$key=$value"
done < <(grep -v '^\s*#' "${ENV_FILE}" | grep '=')

mkdir -p "${DUMP_DIR}"

echo "==> Dumping Postgres database ${POSTGRES_DB}"
docker exec postgres pg_dump -U "${POSTGRES_ADMIN_USER}" -Fc "${POSTGRES_DB}" \
  > "${DUMP_DIR}/${POSTGRES_DB}-${DATE_TAG}.dump"

if [ -n "${RESTIC_REPOSITORY:-}" ] && [ -n "${RESTIC_PASSWORD:-}" ]; then
  echo "==> Sending backup to restic repository"
  export RESTIC_REPOSITORY RESTIC_PASSWORD
  restic snapshots >/dev/null 2>&1 || restic init
  restic backup "${DUMP_DIR}/${POSTGRES_DB}-${DATE_TAG}.dump" --tag postgres
  restic forget --tag postgres \
    --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune
else
  echo "==> RESTIC_REPOSITORY/RESTIC_PASSWORD not set, skipping offsite upload" >&2
fi

# Keep at most 7 local dump files as a fallback if restic is not configured yet
find "${DUMP_DIR}" -name "${POSTGRES_DB}-*.dump" -type f -printf '%T@ %p\n' \
  | sort -rn | tail -n +8 | cut -d' ' -f2- | xargs -r rm -f

echo "==> Postgres backup finished: ${DUMP_DIR}/${POSTGRES_DB}-${DATE_TAG}.dump"
