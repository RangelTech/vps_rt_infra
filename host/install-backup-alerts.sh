#!/usr/bin/env bash
# Instala o alerta de backup (30 min) e a prova de restauracao semanal. Idempotente. Roda como root.
# Opcional: /opt/platform/secrets/alert.env (modo 0600) com ALERT_WEBHOOK_URL e/ou ALERT_PUSH_URL.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; SCRIPTS="$(cd "$HERE/../scripts" && pwd)"
install -m 0755 "$SCRIPTS/backup-alert.sh" "$SCRIPTS/restore-verify.sh" /opt/platform/scripts/
install -m 0644 "$HERE"/rt-backup-alert.service "$HERE"/rt-backup-alert.timer "$HERE"/rt-restore-verify.service "$HERE"/rt-restore-verify.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now rt-backup-alert.timer rt-restore-verify.timer
systemctl list-timers rt-backup-alert.timer rt-restore-verify.timer --no-pager
