#!/usr/bin/env bash
# Runs on the VPS once the pinned PNCP semantic notices and trusted items Parquet files exist.
# 1. aggregate to small CSVs  2. load them into the analytics DB as approved views
# 3. seed the Metabase dashboard and print its public UUID  4. (re)start the edge with that UUID
set -euo pipefail
SRC=/opt/pncp-dashboard/src          # copy of distributed-agent-runtime-lab/deploy/public-demo/pncp
CAND=${CAND:-$HOME/exports/candidates/catalogue-20260929}
NOTICES=${NOTICES:-$CAND/obt_pncp_contratacoes--semantic/obt_pncp_contratacoes.parquet}
ITEMS=${ITEMS:-$CAND/pncp_contratacoes_itens--trusted/pncp_contratacoes_itens.parquet}
OUT=/opt/pncp-dashboard/aggregates
DEMO_ENV=/opt/demo/runtime-lab/deploy/public-demo/.env

mkdir -p "$OUT"
[ -f "$OUT/derivative.json" ] || "$HOME/exports/.venv/bin/python" "$SRC/build_aggregates.py" --notices "$NOTICES" --items "$ITEMS" \
  --cutoff 2026-07-31 --release-version 1 --output "$OUT"

PNCP_DIR="$OUT" sh "$SRC/load_aggregates.sh"

set -a; . "$DEMO_ENV"; set +a
UUID=$(docker run --rm --network public-demo_app \
  -e MB_URL=http://public-demo-metabase-1:3000 -e METABASE_ADMIN_EMAIL -e METABASE_ADMIN_PASSWORD \
  -e PNCP_CUTOFF=2026-07-31 -e PNCP_RELEASE_VERSION=1 \
  -v "$SRC":/seed:ro python:3.12-slim python /seed/seed_pncp_dashboard.py | tee /dev/stderr | sed -n 's/^public_dashboard_uuid=//p')
[ -n "$UUID" ]
printf 'PUBLIC_DASHBOARD_UUID=%s\n' "$UUID" > /opt/pncp-dashboard/.env
chmod 600 /opt/pncp-dashboard/.env
cd /opt/pncp-dashboard && docker compose up -d --force-recreate
echo "dashboard ready for pncp.rangeltech.net"
