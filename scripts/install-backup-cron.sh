#!/usr/bin/env bash
# Installs the cron jobs for daily backups. Runs on the VPS (called from
# Terraform's remote-exec after the stack is deployed). Idempotent.

set -euo pipefail

BASE_DIR="/opt/platform"
CRON_FILE="/etc/cron.d/platform-backups"

cat > "${CRON_FILE}" <<EOF
# Managed by vps_rt_infra. Do not edit manually — re-run terraform apply instead.
15 2 * * * root ${BASE_DIR}/scripts/backup-postgres.sh >> /var/log/platform-backup-postgres.log 2>&1
45 2 * * * root ${BASE_DIR}/scripts/backup-minio.sh >> /var/log/platform-backup-minio.log 2>&1
EOF

chmod 644 "${CRON_FILE}"
echo "==> Backup cron installed at ${CRON_FILE}"
