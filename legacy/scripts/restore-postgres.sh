#!/usr/bin/env bash
# Restores a Postgres dump into the running postgres container.
#
# Usage: restore-postgres.sh <path-to-dump-file>

set -euo pipefail

BASE_DIR="/opt/platform"
ENV_FILE="${BASE_DIR}/compose/.env"
DUMP_FILE="${1:?Usage: restore-postgres.sh <path-to-dump-file>}"

# shellcheck disable=SC1090
set -a; source "${ENV_FILE}"; set +a

if [ ! -f "${DUMP_FILE}" ]; then
  echo "Dump file not found: ${DUMP_FILE}" >&2
  exit 1
fi

echo "==> WARNING: this will overwrite database ${POSTGRES_DB}."
read -r -p "Type the database name to confirm: " CONFIRM
if [ "${CONFIRM}" != "${POSTGRES_DB}" ]; then
  echo "Confirmation mismatch, aborting." >&2
  exit 1
fi

echo "==> Dropping and recreating ${POSTGRES_DB}"
docker exec postgres dropdb -U "${POSTGRES_ADMIN_USER}" "${POSTGRES_DB}"
docker exec postgres createdb -U "${POSTGRES_ADMIN_USER}" "${POSTGRES_DB}"

echo "==> Restoring dump"
docker exec -i postgres pg_restore -U "${POSTGRES_ADMIN_USER}" -d "${POSTGRES_DB}" \
  < "${DUMP_FILE}"

echo "==> Restore finished"
