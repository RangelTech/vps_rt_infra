"""Load the notice embeddings into Postgres (pgvector) and index them.

Source: the trusted table `pncp_editais_embeddings` in the lake (768-dimension vectors from Vertex
`text-multilingual-embedding-002`), read through the BigQuery Storage API. Stored as halfvec(768) with an
HNSW cosine index, so semantic search runs inside Postgres next to the text search.

Run on the VPS with the exports venv:  python load_embeddings.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import psycopg
from pgvector import HalfVector
from pgvector.psycopg import register_vector

sys.path.insert(0, os.path.expanduser("~/exports"))
import release_table  # noqa: E402
from google.cloud import bigquery_storage  # noqa: E402

PROJECT = os.environ.get("EXPORT_PROJECT", "mi-prd-lake")
ZONE, TABLE = "trusted_zone", "pncp_editais_embeddings"


def host() -> str:
    out = subprocess.run(["docker", "inspect", "-f", "{{(index .NetworkSettings.Networks \"pncpdb\").IPAddress}}", "pncp-db-db-1"],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


def password() -> str:
    for line in Path("/opt/pncp-db/.env").read_text().splitlines():
        if line.startswith("POSTGRES_PASSWORD="):
            return line.split("=", 1)[1]
    raise SystemExit("POSTGRES_PASSWORD missing")


def main() -> None:
    release_table.BQSTORAGE_CLIENT = bigquery_storage.BigQueryReadClient()
    conn = psycopg.connect(host=host(), dbname="pncp", user="pncp_owner", password=password(), autocommit=True)
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    register_vector(conn)
    conn.execute("DROP TABLE IF EXISTS pncp.editais_embeddings")
    conn.execute("CREATE TABLE pncp.editais_embeddings (numero_controle_pncp text NOT NULL, embedding halfvec(768) NOT NULL)")
    t0, total = time.time(), 0
    with conn.cursor() as cur, cur.copy("COPY pncp.editais_embeddings (numero_controle_pncp, embedding) FROM STDIN WITH (FORMAT BINARY)") as copy:
        copy.set_types(["text", "halfvec"])
        for batch in release_table._storage_batches(PROJECT, ZONE, TABLE, ["numero_controle_pncp", "embedding"]):
            ids = batch.column(0).to_pylist()
            column = batch.column(1)
            flat = np.asarray(column.flatten().to_numpy(zero_copy_only=False), dtype=np.float32)
            if flat.size != len(ids) * 768:
                raise SystemExit(f"unexpected embedding size {flat.size} for {len(ids)} rows")
            values = flat.reshape(len(ids), 768)
            for key, vec in zip(ids, values):
                copy.write_row((key, HalfVector(vec)))
            total += len(ids)
            if total % 100_000 < len(ids):
                print(f"loaded {total} ({int(time.time() - t0)} s)", flush=True)
    print(f"loaded {total} rows in {int(time.time() - t0)} s; deduplicating", flush=True)
    conn.execute("DELETE FROM pncp.editais_embeddings a USING pncp.editais_embeddings b "
                 "WHERE a.numero_controle_pncp = b.numero_controle_pncp AND a.ctid < b.ctid")
    conn.execute("CREATE UNIQUE INDEX editais_embeddings_id ON pncp.editais_embeddings (numero_controle_pncp)")
    print("building the HNSW index", flush=True)
    conn.execute("SET maintenance_work_mem = '1GB'")
    conn.execute("CREATE INDEX editais_embeddings_hnsw ON pncp.editais_embeddings USING hnsw (embedding halfvec_cosine_ops) WITH (m = 16, ef_construction = 64)")
    conn.execute("GRANT SELECT ON pncp.editais_embeddings TO rag_reader, bi_reader, public_reader")
    conn.execute("ANALYZE pncp.editais_embeddings")
    print(f"EMBEDDINGS_DONE {int(time.time() - t0)} s", flush=True)


if __name__ == "__main__":
    main()
