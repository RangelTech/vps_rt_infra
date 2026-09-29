"""Hermes Relay (SPEC_HERMES_INTEGRADO_RIA_ATENDIMENTO.md, Fase B / secao
8.1 e 12) -- slice 3: alem da presenca autenticada por ticket (slices 1-2),
agora avisa o dispositivo em tempo real quando um comando e criado, em vez
de o dispositivo depender so do seu proprio poll periodico.

O backend faz `SELECT pg_notify('hermes_commands', device_id)` na mesma
transacao que insere o comando (hermes_commands.py:create_command) --
Postgres so entrega a notificacao se a transacao de fato comitar. Cada
conexao WS aqui mantem uma segunda conexao Postgres so pra `LISTEN
hermes_commands` e, ao ver seu proprio device_id, manda um
`{"type": "command.available"}` pro cliente. O Relay continua sem gravar
estado de negocio: ele so LE hermes_ws_tickets/hermes_devices e escuta um
canal, o claim de verdade do comando continua sendo o
`GET /api/hermes/commands/pending` atomico do backend (FOR UPDATE SKIP
LOCKED) -- o push aqui e so o gatilho pra parar de esperar o proximo poll.

Fora do escopo desta fatia (fica para a proxima): publicar eventos de
sessao para o backend pelo proprio Relay (hoje a extensao ainda publica
isso via HTTP).
"""

import asyncio
import contextlib
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


async def _listen_for_commands(device_id: str, websocket: WebSocket) -> None:
    """Runs for the lifetime of one WS connection. A fresh async connection
    (not the threadpool one used for auth/presence) because LISTEN/notifies()
    blocks on that connection for as long as this task lives."""
    aconn = await psycopg.AsyncConnection.connect(**_PG_KWARGS, autocommit=True)
    try:
        await aconn.execute("LISTEN hermes_commands")
        async for notify in aconn.notifies():
            if notify.payload == device_id:
                await websocket.send_json({"type": "command.available"})
    except asyncio.CancelledError:
        raise
    except Exception:
        # Nunca derruba a conexao WS por isso -- o dispositivo so perde o
        # aviso em tempo real e volta a depender do proprio poll ate a
        # proxima conexao.
        log.exception("command listener failed for device_id=%s", device_id)
    finally:
        await aconn.close()


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
    listen_task = asyncio.create_task(_listen_for_commands(device["id"], websocket))
    try:
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        listen_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await listen_task
        log.info("device disconnected tenant_id=%s device_id=%s", device["tenant_id"], device["id"])
        await run_in_threadpool(_mark_disconnected, device["id"])
