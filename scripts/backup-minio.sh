#!/usr/bin/env bash
# Syncs MinIO data to the external restic repository (object-level backup).
# Runs on the VPS via cron (installed by install-backup-cron.sh).

set -euo pipefail

BASE_DIR="/opt/platform"
ENV_FILE="${BASE_DIR}/compose/.env"
MINIO_DATA_DIR="${BASE_DIR}/data/minio"

# shellcheck disable=SC1090
set -a; source "${ENV_FILE}"; set +a

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
