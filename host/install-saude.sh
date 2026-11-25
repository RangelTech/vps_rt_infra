#!/usr/bin/env bash
# Instala o coletor de saude (spec 57 6.10.5). Rodar como root a partir de vps_rt_infra/host. Idempotente.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
install -d /opt/platform/scripts/saude /opt/platform/scripts/infisical
install -m 0644 "$HERE"/../scripts/saude/coletor.py /opt/platform/scripts/saude/
install -m 0644 "$HERE"/../scripts/infisical/infisical_projetos.json /opt/platform/scripts/infisical/
install -m 0644 "$HERE"/rt-saude.service "$HERE"/rt-saude.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now rt-saude.timer
systemctl list-timers rt-saude.timer --no-pager
