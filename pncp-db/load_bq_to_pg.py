"""Load structured public tables from the source lake straight into the public Postgres.

Used for analytical (semantic) tables that an SQL agent and dashboards query directly, for example
the SIOPE education-finance tables. Column and table descriptions from the source become Postgres
COMMENTs, so the database documents itself (the agent reads them to write correct SQL).

Usage (exports venv):  python load_bq_to_pg.py <pg_schema> <zone>.<table> [<zone>.<table> ...]
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psycopg
import pyarrow as pa
import pyarrow.csv as pacsv

HERE = Path(__file__).resolve().parent
sys.path.insert(0, os.path.expanduser("~/exports"))
import release_table  # noqa: E402
from google.cloud import bigquery, bigquery_storage  # noqa: E402
from psycopg import sql  # noqa: E402

PROJECT = os.environ.get("EXPORT_PROJECT", "mi-prd-lake")
DROP = {"dt_ingestao_lake", "data_carga", "dt_carga"}


def pg_type(field: bigquery.SchemaField) -> str | None:
    if field.mode == "REPEATED":
        return None
    return {"STRING": "text", "INTEGER": "bigint", "INT64": "bigint", "FLOAT": "double precision", "FLOAT64": "double precision",
            "NUMERIC": "numeric", "BIGNUMERIC": "numeric", "BOOLEAN": "boolean", "BOOL": "boolean", "DATE": "date",
            "TIMESTAMP": "timestamptz", "DATETIME": "timestamp"}.get(field.field_type.upper())


def host() -> str:
    out = subprocess.run(["docker", "inspect", "-f", "{{(index .NetworkSettings.Networks \"pncpdb\").IPAddress}}", "pncp-db-db-1"],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


def password() -> str:
    for line in Path("/opt/pncp-db/.env").read_text().splitlines():
        if line.startswith("POSTGRES_PASSWORD="):
            return line.split("=", 1)[1]
    raise SystemExit("POSTGRES_PASSWORD missing")


def load_table(conn: psycopg.Connection, bq: bigquery.Client, schema: str, ref: str) -> int:
    zone, name = ref.split(".")
    table = bq.get_table(f"{PROJECT}.{zone}.{name}")
    fields = [f for f in table.schema if f.name not in DROP and pg_type(f)]
    with conn.cursor() as cur:
        cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
        cur.execute(f'DROP TABLE IF EXISTS "{schema}"."{name}" CASCADE')
        cur.execute(f'CREATE TABLE "{schema}"."{name}" ({", ".join(f"{chr(34)}{f.name}{chr(34)} {pg_type(f)}" for f in fields)})')
    total = 0
    cols = [f.name for f in fields]
    with conn.cursor() as cur, cur.copy(f'COPY "{schema}"."{name}" FROM STDIN WITH (FORMAT csv)') as copy:
        for batch in release_table._storage_batches(PROJECT, zone, name, cols):
            sink = io.BytesIO()
            pacsv.write_csv(pa.Table.from_batches([batch]).select(cols), sink, write_options=pacsv.WriteOptions(include_header=False))
            copy.write(sink.getvalue())
            total += batch.num_rows
    conn.commit()  # keep the loaded rows even if a comment fails
    with conn.cursor() as cur:
        if table.description:
            cur.execute(sql.SQL("COMMENT ON TABLE {}.{} IS {}").format(sql.Identifier(schema), sql.Identifier(name), sql.Literal(table.description[:1000])))
        for f in fields:
            if f.description:
                cur.execute(sql.SQL("COMMENT ON COLUMN {}.{}.{} IS {}").format(
                    sql.Identifier(schema), sql.Identifier(name), sql.Identifier(f.name), sql.Literal(f.description[:500])))
        cur.execute(sql.SQL("ANALYZE {}.{}").format(sql.Identifier(schema), sql.Identifier(name)))
    conn.commit()
    return total


def main() -> None:
    schema, refs = sys.argv[1], sys.argv[2:]
    release_table.BQSTORAGE_CLIENT = bigquery_storage.BigQueryReadClient()
    bq = bigquery.Client(project=PROJECT)
    conn = psycopg.connect(host=host(), dbname="pncp", user="pncp_owner", password=password())
    for ref in refs:
        t0 = time.time()
        try:
            rows = load_table(conn, bq, schema, ref)
            print(json.dumps({"table": f"{schema}.{ref.split('.')[1]}", "rows": rows, "seconds": int(time.time() - t0)}), flush=True)
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            print(json.dumps({"table": ref, "error": repr(exc)[:300]}), flush=True)
    conn.close()


if __name__ == "__main__":
    main()
