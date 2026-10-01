#!/usr/bin/env bash
# Builds the vector index over the Qwen embeddings once the reindex has finished (serial, 1 GB maintenance memory).
LOG=/opt/pncp-db-infra/ivf_qwen.log
psql_db() { docker exec pncp-db-db-1 psql -U pncp_owner -d pncp -v ON_ERROR_STOP=1 "$@"; }
: > "$LOG"
psql_db -c "SET max_parallel_maintenance_workers=0" -c "SET maintenance_work_mem='1GB'" \
  -c "CREATE UNIQUE INDEX IF NOT EXISTS editais_embeddings_qwen_id ON pncp.editais_embeddings_qwen (numero_controle_pncp)" >> "$LOG" 2>&1
echo "unique rc=$? $(date +%T)" >> "$LOG"
psql_db -c "SET max_parallel_maintenance_workers=0" -c "SET maintenance_work_mem='1GB'" \
  -c "CREATE INDEX IF NOT EXISTS editais_embeddings_qwen_ivf ON pncp.editais_embeddings_qwen USING ivfflat (embedding halfvec_cosine_ops) WITH (lists = 1100)" \
  -c "GRANT SELECT ON pncp.editais_embeddings_qwen TO rag_reader, bi_reader, public_reader" -c "ANALYZE pncp.editais_embeddings_qwen" >> "$LOG" 2>&1
echo "IVF_QWEN_DONE rc=$? $(date +%T)" >> "$LOG"
