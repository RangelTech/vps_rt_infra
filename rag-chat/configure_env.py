"""Runs on the VPS. Adds the Postgres, embedding and SQL-base settings to /opt/rag-chat/.env (idempotent).

Passwords come from /opt/pncp-db/.env and are written only into the .env file (mode 600), never printed.
"""
import json
import os

def read_env(path):
    out = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k] = v
    return out

db = read_env("/opt/pncp-db/.env")
env = read_env("/opt/rag-chat/.env")
host = "pncp-db-db-1"
extra = [
    {"id": "pncp-sql", "type": "sql", "label": "PNCP contracts and price registrations (SQL)",
     "tables": ["pncp.obt_pncp_contratos", "pncp.obt_pncp_atas"], "dataset_slug": "lucasrangelss/pncp-contracts-semantic",
     "release": "v1", "cutoff": "2026-07-31"},
    {"id": "siope", "type": "sql", "label": "SIOPE education spending (SQL)",
     "tables": ["siope.obt_fnde_siope_indicador_municipio_ano", "siope.obt_fnde_siope_dados_gerais_municipio_ano",
                "siope.obt_fnde_siope_despesa_funcao_municipio_ano", "siope.obt_fnde_fundeb_indicadores_siope_municipio_ano",
                "ibge.obt_ibge_municipio", "ibge.obt_ibge_uf"],
     "dataset_slug": "lucasrangelss/siope-analytics", "release": "v1", "cutoff": "n/a"},
]
env.update({
    "RAG_DATABASE_URL": f"postgresql://rag_reader:{db['RAG_PW']}@{host}:5432/pncp",
    "RAG_SQL_DATABASE_URL": f"postgresql://sql_agent:{db['AGENT_PW']}@{host}:5432/pncp",
    "EMBED_URL": "http://embed:8090",
    "RAG_BASE_ID": "pncp",
    "RAG_PROFILE": "PNCP procurement notices (text + vector search)",
    "RAG_EXTRA_CORPORA": json.dumps(extra, separators=(",", ":")),
})
with open("/opt/rag-chat/.env", "w", encoding="utf-8") as f:
    for k, v in env.items():
        f.write(f"{k}={v}\n")
os.chmod("/opt/rag-chat/.env", 0o600)
print("keys:", ", ".join(sorted(env)))
