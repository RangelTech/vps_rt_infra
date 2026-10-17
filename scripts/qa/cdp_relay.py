"""Relay CDP: UMA conexao websocket ao Chrome (pede aprovacao 1x) e HTTP local 127.0.0.1:9333.
POST /cmd  {"method":..., "params":{...}, "sessionId":...} -> resposta CDP
GET  /events?clear=1  -> eventos recentes (Page.*, Browser.download*, etc.)
GET  /ping
"""
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import websocket

port_file = os.path.join(os.environ["LOCALAPPDATA"], "Google", "Chrome", "User Data", "DevToolsActivePort")
lines = open(port_file).read().split("\n")
WS_URL = f"ws://127.0.0.1:{lines[0].strip()}{lines[1].strip()}"
print("conectando em", WS_URL.split("/devtools")[0], "(aguardando aprovacao no Chrome)", flush=True)

ws = websocket.create_connection(WS_URL, suppress_origin=True, timeout=120)
print("CONECTADO", flush=True)
ws.settimeout(None)

lock = threading.Lock()
pending = {}
events = []
_id = [0]


def reader():
    while True:
        try:
            raw = ws.recv()
        except Exception as e:
            print("ws fechou:", e, flush=True)
            os._exit(1)
        m = json.loads(raw)
        if "id" in m and m["id"] in pending:
            pending[m["id"]]["res"] = m
            pending[m["id"]]["ev"].set()
        else:
            events.append(m)
            if len(events) > 2000:
                del events[:1000]


threading.Thread(target=reader, daemon=True).start()


def send(method, params=None, session=None, timeout=60):
    with lock:
        _id[0] += 1
        i = _id[0]
    slot = {"ev": threading.Event(), "res": None}
    pending[i] = slot
    msg = {"id": i, "method": method, "params": params or {}}
    if session:
        msg["sessionId"] = session
    ws.send(json.dumps(msg))
    if not slot["ev"].wait(timeout):
        pending.pop(i, None)
        return {"error": "timeout"}
    pending.pop(i, None)
    return slot["res"]


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/events"):
            out = list(events)
            if "clear=1" in self.path:
                events.clear()
            return self._json(out)
        self._json({"ok": True, "t": time.time()})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        self._json(send(body["method"], body.get("params"), body.get("sessionId"), body.get("timeout", 60)))


ThreadingHTTPServer(("127.0.0.1", 9333), H).serve_forever()
