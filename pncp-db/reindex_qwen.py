"""Builds the Qwen3-Embedding vectors of the notice texts into pncp.editais_embeddings_qwen (resume-safe).

Texts are the same `texto_base` the Vertex vectors were built from, read from the lake through the BigQuery
Storage API. Documents go to the embedding endpoint without an instruction prefix (Qwen3-Embedding uses the
instruction on the query side only), truncated to 768 dimensions (Matryoshka) so they fit halfvec(768).

Run on the VPS with the exports venv:
  python reindex_qwen.py            # resumes: ids already in the table are skipped
  LIMIT=2000 python reindex_qwen.py # small trial
Environment: EMBED_BASE_URL (default: the public edge name, ends in /v1); QWEN_API_KEY is read from /opt/rag-chat/.env.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import psycopg
from google.cloud import bigquery_storage
from pgvector import HalfVector
from pgvector.psycopg import register_vector

sys.path.insert(0, os.path.expanduser("~/exports"))
import release_table  # noqa: E402

PROJECT = os.environ.get("EXPORT_PROJECT", "mi-prd-lake")
ZONE, TABLE = "trusted_zone", "pncp_editais_embeddings"
BATCH = int(os.environ.get("BATCH", "64"))
WORKERS = int(os.environ.get("WORKERS", "8"))
LIMIT = int(os.environ.get("LIMIT", "0"))
MAX_CHARS = 800
DIM = 768


def read_env(path: str) -> dict[str, str]:
    out = {}
    for line in Path(path).read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def db_host() -> str:
    out = subprocess.run(["docker", "inspect", "-f", "{{(index .NetworkSettings.Networks \"pncpdb\").IPAddress}}", "pncp-db-db-1"],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


def embed_batch(url: str, key: str, texts: list[str]) -> list[list[float]]:
    body = json.dumps({"model": "qwen-embedding", "input": texts, "dimensions": DIM}).encode()
    last = ""
    for attempt in range(8):
        try:
            request = urllib.request.Request(url + "/embeddings", body, {"Authorization": "Bearer " + key, "Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=300) as response:
                data = json.load(response)["data"]
            vectors = [item["embedding"] for item in sorted(data, key=lambda item: item["index"])]
            if len(vectors) != len(texts) or any(len(v) != DIM for v in vectors):
                raise ValueError("unexpected embedding shape")
            return vectors
        except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as exc:
            last = repr(exc)[:100]
            time.sleep(min(5 * (attempt + 1), 60))
    raise SystemExit(f"embedding endpoint kept failing: {last}")


def main() -> None:
    env = read_env("/opt/rag-chat/.env")
    # The chat talks to the model on its direct route; embeddings are served behind the public edge name.
    url, key = os.environ.get("EMBED_BASE_URL", "https://qwen.rangeltech.net/v1").rstrip("/"), env["QWEN_API_KEY"]
    dbpw = read_env("/opt/pncp-db/.env")["POSTGRES_PASSWORD"]
    conn = psycopg.connect(host=db_host(), dbname="pncp", user="pncp_owner", password=dbpw, autocommit=True)
    register_vector(conn)
    done = {r[0] for r in conn.execute("SELECT numero_controle_pncp FROM pncp.editais_embeddings_qwen")}
    print(f"resuming with {len(done)} ids already embedded", flush=True)
    release_table.BQSTORAGE_CLIENT = bigquery_storage.BigQueryReadClient()

    work: queue.Queue = queue.Queue(maxsize=WORKERS * 2)
    results: queue.Queue = queue.Queue(maxsize=WORKERS * 2)
    stats = {"embedded": 0, "started": time.time()}

    def producer() -> None:
        seen = set(done)
        ids: list[str] = []
        texts: list[str] = []
        total = 0
        for batch in release_table._storage_batches(PROJECT, ZONE, TABLE, ["numero_controle_pncp", "texto_base"]):
            for key_id, text in zip(batch.column(0).to_pylist(), batch.column(1).to_pylist()):
                if not key_id or not text or key_id in seen:
                    continue
                seen.add(key_id)
                ids.append(key_id)
                texts.append(text[:MAX_CHARS])
                if len(ids) == BATCH:
                    work.put((ids, texts))
                    ids, texts, total = [], [], total + BATCH
                    if LIMIT and total >= LIMIT:
                        break
            if LIMIT and total >= LIMIT:
                break
        if ids:
            work.put((ids, texts))
        for _ in range(WORKERS):
            work.put(None)

    def worker() -> None:
        while (item := work.get()) is not None:
            ids, texts = item
            results.put((ids, embed_batch(url, key, texts)))
        results.put(None)

    def writer() -> None:
        finished = 0
        last_print = time.time()
        with conn.cursor() as cur:
            while finished < WORKERS:
                item = results.get()
                if item is None:
                    finished += 1
                    continue
                ids, vectors = item
                with cur.copy("COPY pncp.editais_embeddings_qwen (numero_controle_pncp, embedding) FROM STDIN WITH (FORMAT BINARY)") as copy:
                    copy.set_types(["text", "halfvec"])
                    for key_id, vec in zip(ids, np.asarray(vectors, dtype=np.float32)):
                        copy.write_row((key_id, HalfVector(vec)))
                stats["embedded"] += len(ids)
                if time.time() - last_print > 60:
                    rate = stats["embedded"] / (time.time() - stats["started"])
                    print(f"embedded {stats['embedded']} this run, {rate:.1f} texts/s", flush=True)
                    last_print = time.time()

    threads = [threading.Thread(target=producer, daemon=True)] + [threading.Thread(target=worker, daemon=True) for _ in range(WORKERS)]
    w = threading.Thread(target=writer)
    for t in threads:
        t.start()
    w.start()
    w.join()
    total = conn.execute("SELECT count(*) FROM pncp.editais_embeddings_qwen").fetchone()[0]
    print(f"REINDEX_PASS_DONE embedded {stats['embedded']} this run, {total} in the table", flush=True)


if __name__ == "__main__":
    main()
