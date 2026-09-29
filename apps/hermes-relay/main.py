"""Hermes Relay (SPEC_HERMES_INTEGRADO_RIA_ATENDIMENTO.md, Fase B / secao
8.1 e 12) -- slice 2: conexao WSS persistente autenticada por TICKET de
curta duracao (nao mais a credencial de longa duracao do dispositivo).

A extensao chama `POST /api/hermes/devices/ws-ticket` no backend (autenticada
com sua credencial de longa duracao, hermes_device_credentials), recebe um
ticket descartavel (hermes_ws_tickets, migration 0042) e usa SO o ticket na
query string do WS -- a credencial de longa duracao nunca aparece ali, e
portanto nunca aparece em log de acesso do Traefik. O Relay marca o ticket
como usado no mesmo UPDATE que valida (uso unico: replay do mesmo ticket
falha sempre) e confere a expiracao no banco, nao no relogio local.

Fora do escopo desta fatia (fica para a proxima): despachar comandos,
publicar eventos de sessao para o backend. O Relay nao grava estado de
negocio no Postgres -- aqui ele LE hermes_ws_tickets/hermes_devices e
atualiza presenca (last_seen_at/status), que ja e o dado que o backend HTTP
tambem escreve hoje.
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

# Consome hermes_ws_tickets (backend/migrations/0042) num UPDATE atomico:
# so aceita ticket nao usado e ainda nao expirado, e ja marca used_at no
# mesmo statement -- duas conexoes concorrentes com o mesmo ticket nunca
# autenticam as duas (a segunda pega 0 linhas, exatamente como o claim
# atomico de comandos pendentes no backend, FOR UPDATE SKIP LOCKED).
_CONSUME_TICKET = """
UPDATE hermes_ws_tickets
   SET used_at = now()
 WHERE token_hash = %s AND used_at IS NULL AND expires_at > now()
RETURNING device_id, tenant_id
"""

_DEVICE_STATUS_QUERY = "SELECT name, status FROM hermes_devices WHERE id = %s"


def hash_token(token: str) -> str:
    """Mesmo hash do backend (app/security.py:hash_token) -- sha256 hex."""
    return hashlib.sha256(token.encode()).hexdigest()


def _authenticate_device(ticket: str) -> dict | None:
    """Sync (psycopg normal), rodado via threadpool -- mesma tecnica que o
    backend usa nas suas proprias rotas sincronas."""
    with _connect(row_factory=dict_row) as conn:
        claim = conn.execute(_CONSUME_TICKET, (hash_token(ticket),)).fetchone()
        if claim is None:
            conn.commit()  # nada a desfazer, mas fecha a transacao aberta pela leitura
            return None
        device = conn.execute(_DEVICE_STATUS_QUERY, (claim["device_id"],)).fetchone()
        if device is None or device["status"] == "revoked":
            conn.rollback()  # nao consome um ticket bom pra um device ja revogado
            return None
        now = datetime.now(UTC)
        conn.execute(
            """UPDATE hermes_devices
                  SET last_seen_at = %s,
                      status = CASE WHEN status = 'disconnected' THEN 'connected' ELSE status END
                WHERE id = %s""",
            (now, claim["device_id"]),
        )
        conn.commit()
        return {
            "id": str(claim["device_id"]),
            "tenant_id": str(claim["tenant_id"]),
            "name": device["name"],
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
    ticket = websocket.query_params.get("ticket")
    if not ticket:
        await websocket.close(code=4401, reason="missing ticket")
        return
    device = await run_in_threadpool(_authenticate_device, ticket)
    if device is None:
        await websocket.close(code=4401, reason="invalid, expired, used or revoked ticket")
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
