"""Load public PNCP tables from the verified Kaggle Parquet files into the public Postgres.

Each table is downloaded from its Kaggle dataset (the same files any visitor can fetch), checked
against the release manifest hash by the publisher, loaded with COPY, indexed, and deleted locally.
Columns of embedding vectors and raw JSON payloads are not loaded.

Run on the VPS with the exports venv:  python load_pncp_db.py [table ...]
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
import pyarrow.parquet as pq

OWNER = "lucasrangelss"
WORK = Path(os.environ.get("LOAD_WORK", "/opt/pncp-db/work"))
KAGGLE = [sys.executable, "-m", "kaggle"]

# name -> (kaggle dataset, parquet file in the dataset, dropped columns, full-text spec)
TABLES = {
    "obt_pncp_editais_semantico": ("pncp-procurement-search-semantic", "semantic__obt_pncp_editais_semantico.parquet",
                                   {"embedding", "modelo", "dim"}, "objeto_compra orgao_razao_social nome_municipio categoria_area"),
    "obt_pncp_contratos": ("pncp-contracts-semantic", "semantic__obt_pncp_contratos.parquet", set(), None),
    "obt_pncp_atas": ("pncp-price-registration-semantic", "semantic__obt_pncp_atas.parquet", set(), None),
    "obt_pncp_pca": ("pncp-annual-plans-semantic", "semantic__obt_pncp_pca.parquet", set(), None),
    "obt_pncp_pca_itens": ("pncp-annual-plans-semantic", "semantic__obt_pncp_pca_itens.parquet", set(), None),
    "obt_pncp_contratacoes": ("pncp-procurement-notices-semantic", "semantic__obt_pncp_contratacoes.parquet", set(),
                              "objeto_compra orgao_razao_social nome_municipio"),
    "pncp_orgaos": ("pncp-organizations-data", "trusted__pncp_orgaos.parquet", {"payload_json"}, None),
    "pncp_orgaos_unidades": ("pncp-organizations-data", "trusted__pncp_orgaos_unidades.parquet", {"payload_json"}, None),
}


def pg_type(t: pa.DataType) -> str | None:
    if pa.types.is_string(t) or pa.types.is_large_string(t):
        return "text"
    if pa.types.is_int64(t) or pa.types.is_uint32(t):
        return "bigint"
    if pa.types.is_integer(t):
        return "integer"
    if pa.types.is_floating(t):
        return "double precision"
    if pa.types.is_decimal(t):
        return "numeric"
    if pa.types.is_timestamp(t):
        return "timestamptz" if t.tz else "timestamp"
    if pa.types.is_date(t):
        return "date"
    if pa.types.is_boolean(t):
        return "boolean"
    return None  # lists, structs, binary: not loaded


def host() -> str:
    out = subprocess.run(["docker", "inspect", "-f", "{{(index .NetworkSettings.Networks \"pncpdb\").IPAddress}}", "pncp-db-db-1"],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


def password() -> str:
    for line in Path("/opt/pncp-db/.env").read_text().splitlines():
        if line.startswith("POSTGRES_PASSWORD="):
            return line.split("=", 1)[1]
    raise SystemExit("POSTGRES_PASSWORD missing")


def fetch(dataset: str, filename: str) -> Path:
    target = WORK / dataset
    target.mkdir(parents=True, exist_ok=True)
    path = target / filename
    if not path.exists():
        subprocess.run([*KAGGLE, "datasets", "download", f"{OWNER}/{dataset}", "-f", filename, "-p", str(target), "--unzip"],
                       check=True, capture_output=True)
    return path


def load(conn: psycopg.Connection, name: str, path: Path, dropped: set[str], fts: str | None) -> int:
    pf = pq.ParquetFile(path)
    columns, types = [], {}
    for field in pf.schema_arrow:
        ddl = pg_type(field.type)
        if field.name in dropped or ddl is None:
            continue
        columns.append(field.name)
        types[field.name] = ddl
    with conn.cursor() as cur:
        cur.execute(f'DROP TABLE IF EXISTS pncp."{name}" CASCADE')
        cur.execute(f'CREATE TABLE pncp."{name}" ({", ".join(f"{chr(34)}{c}{chr(34)} {types[c]}" for c in columns)})')
    total = 0
    with conn.cursor() as cur, cur.copy(f'COPY pncp."{name}" FROM STDIN WITH (FORMAT csv)') as copy:
        for batch in pf.iter_batches(batch_size=100_000, columns=columns):
            sink = io.BytesIO()
            pacsv.write_csv(pa.Table.from_batches([batch]), sink, write_options=pacsv.WriteOptions(include_header=False))
            copy.write(sink.getvalue())
            total += batch.num_rows
    with conn.cursor() as cur:
        if "numero_controle_pncp" in columns:
            cur.execute(f'CREATE INDEX ON pncp."{name}" (numero_controle_pncp)')
        if fts:
            expr = " || ' ' || ".join(f"coalesce({c}, '')" for c in fts.split())
            cur.execute(f'ALTER TABLE pncp."{name}" ADD COLUMN fts tsvector GENERATED ALWAYS AS (to_tsvector(\'portuguese\', {expr})) STORED')
            cur.execute(f'CREATE INDEX ON pncp."{name}" USING gin (fts)')
        cur.execute(f'ANALYZE pncp."{name}"')
    conn.commit()
    return total


def main() -> None:
    wanted = sys.argv[1:] or list(TABLES)
    WORK.mkdir(parents=True, exist_ok=True)
    conn = psycopg.connect(host=host(), dbname="pncp", user="pncp_owner", password=password(), autocommit=False)
    for name in wanted:
        dataset, filename, dropped, fts = TABLES[name]
        t0 = time.time()
        try:
            path = fetch(dataset, filename)
            rows = load(conn, name, path, dropped, fts)
            path.unlink(missing_ok=True)
            print(json.dumps({"table": name, "rows": rows, "seconds": int(time.time() - t0)}), flush=True)
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            print(json.dumps({"table": name, "error": repr(exc)[:300]}), flush=True)
    conn.close()


if __name__ == "__main__":
    main()
