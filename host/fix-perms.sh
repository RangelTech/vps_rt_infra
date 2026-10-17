#!/usr/bin/env bash
# Garante dono/modo dos arquivos que os containers exigem. Idempotente. Roda como root a cada deploy da base.
# Causa raiz do incidente de 29/09 e de 16-17/10: o deploy (rsync/terraform) devolvia server.key ao usuario deploy.
set -euo pipefail
TLS=/opt/platform/configs/postgres-tls
if [ -f "$TLS/server.key" ]; then
  chown root:999 "$TLS/server.key"; chmod 0640 "$TLS/server.key"   # Postgres aceita dono root com modo <= 0640 (grupo 999 le)
  chown deploy:deploy "$TLS/server.crt" 2>/dev/null || true; chmod 0644 "$TLS/server.crt" 2>/dev/null || true
fi
# Synapse: /data pertence ao uid 991 (imagem oficial)
[ -d /opt/platform/data/synapse ] && chown -R 991:991 /opt/platform/data/synapse || true
