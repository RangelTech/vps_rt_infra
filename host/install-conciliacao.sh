#!/usr/bin/env bash
# Instala a conciliacao diaria da Cakto (spec 57, 10A.2). Rodar como root a partir de vps_rt_infra/host.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
install -d /opt/platform/scripts/conciliacao /opt/platform/scripts/infisical
install -m 0644 "$HERE"/../scripts/conciliacao/conciliar.py "$HERE"/../scripts/conciliacao/teste_conciliar.py /opt/platform/scripts/conciliacao/
install -m 0644 "$HERE"/../scripts/infisical/infisical_projetos.json /opt/platform/scripts/infisical/
install -m 0644 "$HERE"/rt-conciliacao.service "$HERE"/rt-conciliacao.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now rt-conciliacao.timer
systemctl list-timers rt-conciliacao.timer --no-pager
