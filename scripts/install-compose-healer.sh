#!/usr/bin/env bash
# Installs a systemd timer that periodically reconciles the RT Compose stack.

set -euo pipefail

SOURCE_SCRIPT="${1:-/opt/platform/scripts/compose-healer.sh}"
TARGET_SCRIPT="/usr/local/sbin/rt-compose-healer"
SERVICE_FILE="/etc/systemd/system/rt-compose-healer.service"
TIMER_FILE="/etc/systemd/system/rt-compose-healer.timer"

if [ ! -f "$SOURCE_SCRIPT" ]; then
  echo "Missing healer script: $SOURCE_SCRIPT" >&2
  exit 1
fi

install -m 0755 "$SOURCE_SCRIPT" "$TARGET_SCRIPT"

cat > "$SERVICE_FILE" <<'EOF'
[Unit]
Description=RT Compose stack self-healer
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target
ConditionPathExists=/opt/platform/compose/docker-compose.yml

[Service]
Type=oneshot
Environment=RT_COMPOSE_DIR=/opt/platform/compose
ExecStart=/usr/local/sbin/rt-compose-healer
EOF

cat > "$TIMER_FILE" <<'EOF'
[Unit]
Description=Run RT Compose stack self-healer every minute

[Timer]
OnBootSec=2min
OnUnitActiveSec=1min
AccuracySec=15s
Persistent=true
Unit=rt-compose-healer.service

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now rt-compose-healer.timer
systemctl start rt-compose-healer.service || true
systemctl --no-pager --full status rt-compose-healer.timer
