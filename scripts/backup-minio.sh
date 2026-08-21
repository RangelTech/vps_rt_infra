#!/usr/bin/env bash
# Syncs MinIO data to the external restic repository (object-level backup).
# Runs on the VPS via cron (installed by install-backup-cron.sh).

set -euo pipefail

BASE_DIR="/opt/platform"
ENV_FILE="${BASE_DIR}/compose/.env"
MINIO_DATA_DIR="${BASE_DIR}/data/minio"

# Le o .env linha a linha em vez de `source` -- mesmo achado do
# backup-postgres.sh (senha com parenteses quebra `source` em bash).
while IFS='=' read -r key value; do
  [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
  export "$key=$value"
done < <(grep -v '^\s*#' "${ENV_FILE}" | grep '=')

if [ -z "${RESTIC_REPOSITORY:-}" ] || [ -z "${RESTIC_PASSWORD:-}" ]; then
  echo "RESTIC_REPOSITORY/RESTIC_PASSWORD not set, skipping MinIO backup" >&2
  exit 0
fi

export RESTIC_REPOSITORY RESTIC_PASSWORD
restic snapshots >/dev/null 2>&1 || restic init

echo "==> Backing up MinIO data directory"
restic backup "${MINIO_DATA_DIR}" --tag minio

restic forget --tag minio \
  --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune

echo "==> MinIO backup finished"
