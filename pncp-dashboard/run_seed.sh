#!/usr/bin/env bash
# Runs on the VPS. Connects Metabase to the public Postgres network and seeds the two public dashboards.
set -euo pipefail
docker network connect pncpdb public-demo-metabase-1 2>/dev/null || true
set -a; . /opt/demo/runtime-lab/deploy/public-demo/.env; . /opt/pncp-db/.env; set +a
docker run --rm --network public-demo_app \
  -e MB_URL=http://public-demo-metabase-1:3000 -e METABASE_ADMIN_EMAIL -e METABASE_ADMIN_PASSWORD \
  -e PG_HOST=pncp-db-db-1 -e PG_DB=pncp -e PG_USER=bi_reader -e PG_PASSWORD="$BI_PW" \
  -v /opt/pncp-dashboard/seed:/seed:ro python:3.12-slim python /seed/seed_dashboards.py
