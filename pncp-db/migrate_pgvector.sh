#!/usr/bin/env bash
# One-off: move the public database from postgres:16-alpine to pgvector/pgvector:pg16 (dump, swap image, restore).
set -euo pipefail
cd /opt/pncp-db-infra
set -a; . /opt/pncp-db/.env; set +a
echo "dump $(date +%T)"
docker exec pncp-db-db-1 pg_dump -U pncp_owner -d pncp -Fc > /opt/pncp-db-infra/pncp.dump
ls -la /opt/pncp-db-infra/pncp.dump
docker compose down
sudo mv /opt/pncp-db/data /opt/pncp-db/data-old-alpine
sudo mkdir -p /opt/pncp-db/data && sudo chown 999:999 /opt/pncp-db/data
docker compose up -d
for i in $(seq 1 60); do docker exec pncp-db-db-1 pg_isready -U pncp_owner -d pncp >/dev/null 2>&1 && break; sleep 3; done
docker exec pncp-db-db-1 psql -U pncp_owner -d pncp -c "CREATE EXTENSION IF NOT EXISTS vector" -c "CREATE EXTENSION IF NOT EXISTS pg_prewarm"
docker exec -i pncp-db-db-1 psql -v ON_ERROR_STOP=1 -U pncp_owner -d pncp -v rag_pw="$RAG_PW" -v bi_pw="$BI_PW" -v public_pw="$PUBLIC_PW" < roles.sql
echo "restore $(date +%T)"
docker exec -i pncp-db-db-1 pg_restore -U pncp_owner -d pncp --no-owner -j 2 < /opt/pncp-db-infra/pncp.dump || true
docker exec pncp-db-db-1 psql -U pncp_owner -d pncp -c "GRANT SELECT ON ALL TABLES IN SCHEMA pncp TO rag_reader, bi_reader, public_reader" -c "\dt pncp.*"
echo "MIGRATED $(date +%T)"
