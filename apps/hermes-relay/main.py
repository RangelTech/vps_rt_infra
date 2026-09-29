"""Hermes Relay (SPEC_HERMES_INTEGRADO_RIA_ATENDIMENTO.md, Fase B / secao
8.1 e 12) -- slice 1: conexao WSS persistente autenticada por dispositivo.

Escopo desta fatia: provar que o transporte WSS + autenticacao de
dispositivo funcionam de verdade contra o mesmo banco (hermes_devices /
hermes_device_credentials) que o backend HTTP ja usa -- reaproveitando o
MESMO hash (sha256, ver backend/app/security.py:hash_token) e a MESMA
consulta de autenticacao (backend/app/device_auth.py:current_device), so
que sobre um socket de longa duracao em vez de um bearer por request.

Fora do escopo desta fatia (fica para a proxima): despachar comandos,
publicar eventos de sessao para o backend, emitir/validar tickets de curta
duracao para o RIA assistir uma sessao ao vivo. O Relay nao grava estado de
negocio no Postgres -- aqui ele so LE hermes_devices/hermes_device_credentials
para autenticar e atualiza presenca (last_seen_at/status), que ja e o dado
que o backend HTTP tambem escreve hoje.
"""

import hashlib
import logging
import os
from datetime import UTC, datetime

import psycopg
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from psycopg.rows import dict_row
from starlette.concurrency import run_in_threadpool

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("hermes-relay")

# Variaveis separadas, nao uma DSN montada por interpolacao: a senha real
# do Postgres contem caracteres que nao sao percent-encoded (%, #, (, ) --
# achado ao vivo, 29/09/2026, o mesmo tipo de armadilha ja documentada no
# bloco do Infisical acima sobre DB_CONNECTION_URI).
_PG_KWARGS = {
    "host": os.environ.get("PGHOST", "postgres"),
    "port": int(os.environ.get("PGPORT", "5432")),
    "dbname": os.environ["PGDATABASE"],
    "user": os.environ["PGUSER"],
    "password": os.environ["PGPASSWORD"],
    "connect_timeout": 5,
}


def _connect(**overrides):
    return psycopg.connect(**{**_PG_KWARGS, **overrides})

app = FastAPI(title="Hermes Relay")

# Espelha device_auth.py:_DEVICE_QUERY no backend -- qualquer mudanca de
# schema precisa ser replicada nos dois lugares ate existir um contrato
# OpenAPI/SQL compartilhado (spec secao 17, entregavel 2, ainda pendente).
_DEVICE_QUERY = """
SELECT d.id AS device_id, d.tenant_id, d.name, d.status,
       c.id AS credential_id, c.revoked_at AS credential_revoked_at
  FROM hermes_device_credentials c
  JOIN hermes_devices d ON d.id = c.device_id
 WHERE c.token_hash = %s
"""


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _authenticate_device(token: str) -> dict | None:
    """Sync (psycopg normal), rodado via threadpool -- mesma tecnica que o
    backend usa nas suas proprias rotas sincronas."""
    with _connect(row_factory=dict_row) as conn:
        row = conn.execute(_DEVICE_QUERY, (hash_token(token),)).fetchone()
        if row is None or row["credential_revoked_at"] is not None:
            return None
        if row["status"] == "revoked":
            return None
        now = datetime.now(UTC)
        conn.execute(
            "UPDATE hermes_device_credentials SET last_used_at = %s WHERE id = %s",
            (now, row["credential_id"]),
        )
        conn.execute(
            """UPDATE hermes_devices
                  SET last_seen_at = %s,
                      status = CASE WHEN status = 'disconnected' THEN 'connected' ELSE status END
                WHERE id = %s""",
            (now, row["device_id"]),
        )
        conn.commit()
        return {
            "id": str(row["device_id"]),
            "tenant_id": str(row["tenant_id"]),
            "name": row["name"],
        }


def _mark_disconnected(device_id: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE hermes_devices SET status = 'disconnected' WHERE id = %s AND status <> 'revoked'",
            (device_id,),
        )
        conn.commit()


@app.get("/healthz")
async def healthz():
    try:
        def _ping():
            with _connect(connect_timeout=3) as conn:
                conn.execute("SELECT 1")
        await run_in_threadpool(_ping)
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001 -- healthcheck reports any DB failure verbatim, sanitized (no credentials in the message)
        return JSONResponse(status_code=503, content={"status": "db_unreachable", "error": type(exc).__name__})


@app.websocket("/ws/device")
async def ws_device(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401, reason="missing token")
        return
    device = await run_in_threadpool(_authenticate_device, token)
    if device is None:
        await websocket.close(code=4401, reason="invalid or revoked credential")
        return

    await websocket.accept()
    log.info("device connected tenant_id=%s device_id=%s", device["tenant_id"], device["id"])
    await websocket.send_json({
        "type": "device.hello",
        "device_id": device["id"],
        "tenant_id": device["tenant_id"],
    })
    try:
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        log.info("device disconnected tenant_id=%s device_id=%s", device["tenant_id"], device["id"])
        await run_in_threadpool(_mark_disconnected, device["id"])
