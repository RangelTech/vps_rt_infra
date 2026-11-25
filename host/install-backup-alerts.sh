#!/usr/bin/env bash
# Instala o backup diario (03:30), o alerta de backup (30 min) e a prova de restauracao semanal. Idempotente. Roda como root.
# (Achado 25/11: o backup diario nao tinha agendador; so o alerta existia.)
# Opcional: /opt/platform/secrets/alert.env (modo 0600) com ALERT_WEBHOOK_URL e/ou ALERT_PUSH_URL.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; SCRIPTS="$(cd "$HERE/../scripts" && pwd)"
install -m 0755 "$SCRIPTS/backup.sh" "$SCRIPTS/backup-alert.sh" "$SCRIPTS/restore-verify.sh" /opt/platform/scripts/
install -m 0644 "$HERE"/rt-backup.service "$HERE"/rt-backup.timer "$HERE"/rt-backup-alert.service "$HERE"/rt-backup-alert.timer "$HERE"/rt-restore-verify.service "$HERE"/rt-restore-verify.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now rt-backup.timer rt-backup-alert.timer rt-restore-verify.timer
systemctl list-timers rt-backup.timer rt-backup-alert.timer rt-restore-verify.timer --no-pager
