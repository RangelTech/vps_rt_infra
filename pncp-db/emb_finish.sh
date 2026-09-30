#!/usr/bin/env bash
# Finishes the embeddings load: dedupe, unique index, HNSW index. Serial (no parallel workers) because the
# database container has a 512 MB /dev/shm, which parallel builds overflow.
LOG=/opt/pncp-db-infra/emb2.log
psql_db() { docker exec pncp-db-db-1 psql -U pncp_owner -d pncp -v ON_ERROR_STOP=1 "$@"; }
: > "$LOG"
psql_db -c "SET max_parallel_workers_per_gather=0" -c "SELECT count(*) FROM pncp.editais_embeddings" >> "$LOG" 2>&1
psql_db -c "SET max_parallel_workers_per_gather=0" \
  -c "DELETE FROM pncp.editais_embeddings a USING pncp.editais_embeddings b WHERE a.numero_controle_pncp = b.numero_controle_pncp AND a.ctid < b.ctid" >> "$LOG" 2>&1
echo "dedup rc=$? $(date +%T)" >> "$LOG"
psql_db -c "SET max_parallel_maintenance_workers=0" -c "SET maintenance_work_mem='1GB'" \
  -c "CREATE UNIQUE INDEX IF NOT EXISTS editais_embeddings_id ON pncp.editais_embeddings (numero_controle_pncp)" >> "$LOG" 2>&1
echo "unique rc=$? $(date +%T)" >> "$LOG"
psql_db -c "SET max_parallel_maintenance_workers=0" -c "SET maintenance_work_mem='1GB'" \
  -c "CREATE INDEX IF NOT EXISTS editais_embeddings_hnsw ON pncp.editais_embeddings USING hnsw (embedding halfvec_cosine_ops) WITH (m = 16, ef_construction = 64)" >> "$LOG" 2>&1
echo "hnsw rc=$? $(date +%T)" >> "$LOG"
psql_db -c "GRANT SELECT ON pncp.editais_embeddings TO rag_reader, bi_reader, public_reader" -c "ANALYZE pncp.editais_embeddings" >> "$LOG" 2>&1
echo "EMBEDDINGS_DONE $(date +%T)" >> "$LOG"
