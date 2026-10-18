#!/usr/bin/env python3
"""QA de ponta a ponta da plataforma (spec 03 §8) pelo Chrome real via CDP (relay em 127.0.0.1:9333).

Uso: python run_qa.py [--out DIR] [q1 q2 q3 ...]   (sem argumentos roda tudo que estiver implementado)
Credenciais: cofre pessoal (personal-skills/secrets/rt-platform-qa/ia-master.json), nunca no repo.
Saida: screenshots numerados + qa-report.md em DIR. Cada teste devolve PASS/FAIL com evidencia.
"""
import datetime
import json
import os
import re
import socket
import ssl
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cdp  # noqa: E402  (helper do relay CDP)

VAULT = os.environ.get("QA_VAULT", r"C:\Users\lucas.rangel\Desktop\new_ragente\repos\personal-skills\secrets\rt-platform-qa\ia-master.json")
OUT = None
RESULTS = []
SHOTN = [0]


def shot(sess, label):
    SHOTN[0] += 1
    path = os.path.join(OUT, f"{SHOTN[0]:02d}_{label}.png")
    cdp.shot(sess, path)
    return os.path.basename(path)


def record(qid, title, ok, evidence):
    RESULTS.append((qid, title, ok, evidence))
    print(f"[{'PASS' if ok else 'FAIL'}] {qid} {title} :: {evidence}", flush=True)


def tls_days_left(host):
    ctx = ssl.create_default_context()
    with socket.create_connection((host, 443), timeout=10) as s:
        with ctx.wrap_socket(s, server_hostname=host) as ss:
            exp = ss.getpeercert()["notAfter"]
    return (datetime.datetime.strptime(exp, "%b %d %H:%M:%S %Y %Z") - datetime.datetime.utcnow()).days


def q1_urls():
    expect = {
        "ia.rangeltech.net": (200, "/health/ready"), "chat.rangeltech.net": (200, "/health"), "bridge.rangeltech.net": (200, "/health"),
        "storage.rangeltech.net": (403, "/"), "lucas.rangeltech.net": (200, "/"), "rag.rangeltech.net": (200, "/"),
        "bi.rangeltech.net": (200, "/api/health"), "infisical.rangeltech.net": (200, "/api/status"),
        "airflow.rangeltech.net": (200, "/health"), "uptime.rangeltech.net": (200, "/"),
    }
    bad = []
    for host, (code, path) in expect.items():
        try:
            r = urllib.request.Request(f"https://{host}{path}", headers={"User-Agent": "rt-qa"})
            try:
                got = urllib.request.urlopen(r, timeout=20).status
            except urllib.error.HTTPError as e:
                got = e.code
            days = tls_days_left(host)
            ok = (got == code) and days > 5
            if not ok:
                bad.append(f"{host} {got} (esperado {code}) tls={days}d")
        except Exception as e:  # noqa: BLE001
            bad.append(f"{host} ERRO {e}")
    record("Q1", "matriz de URLs com TLS valido", not bad, "todas ok" if not bad else "; ".join(bad))


def login_ui(sess, email, password, label):
    cdp.goto(sess, "https://ia.rangeltech.net/", 3)
    cdp.ev(sess, "localStorage.clear(); sessionStorage.clear();")
    cdp.goto(sess, "https://ia.rangeltech.net/", 3)
    inputs = [x for x in cdp.ui(sess) if x[0] == "input"]
    if len(inputs) < 2:
        return False, "campos de login nao encontrados"
    for (x, y), text in ((inputs[0][2:4], email), (inputs[1][2:4], password)):
        cdp.click(sess, x, y)
        cdp.select_all(sess)
        cdp.typ(sess, text)
    shot(sess, f"{label}_login_preenchido")
    btn = [x for x in cdp.ui(sess) if x[0] == "button"][0]
    cdp.click(sess, btn[2], btn[3])
    time.sleep(4)
    url = cdp.ev(sess, "location.href")
    tok = cdp.ev(sess, "(localStorage.getItem('token')||localStorage.getItem('auth_token')||Object.keys(localStorage).join(','))")
    shot(sess, f"{label}_apos_login")
    return True, f"url={url} storage={str(tok)[:60]}"


def q2_login(sess, creds):
    ok, ev = login_ui(sess, creds["qa_admin_email"], creds["qa_admin_password"], "q2_admin")
    page = cdp.ev(sess, "document.body.innerText.slice(0,300)")
    logged = ok and "acessar plataforma" not in (page or "").lower()
    # negativo: senha errada
    cdp.ev(sess, "localStorage.clear(); sessionStorage.clear();")
    ok2, _ = login_ui(sess, creds["qa_admin_email"], "senha-errada-123", "q2_negativo")
    page2 = cdp.ev(sess, "document.body.innerText")
    rejected = "acessar plataforma" in (page2 or "").lower() and "inv" in (page2 or "").lower()
    record("Q2", "login digitado na tela (admin) + senha errada rejeitada", logged and rejected, f"{ev}; negativo_rejeitado={rejected}")
    # volta a logar para os proximos testes
    login_ui(sess, creds["qa_admin_email"], creds["qa_admin_password"], "q2_admin_relogin")


def q3_chat(sess):
    cdp.goto(sess, "https://ia.rangeltech.net/chat", 4)
    shot(sess, "q3_chat_vazio")
    box = [x for x in cdp.ui(sess, 80) if x[0] == "textarea"]
    send = [x for x in cdp.ui(sess, 80) if x[0] == "button" and "Enviar" in x[1]]
    if not box or not send:
        record("Q3", "chat: mensagem, resposta e historico", False, "textarea/botao Enviar nao encontrados")
        return
    pergunta = "Responda em uma frase: qual a capital do Brasil?"
    cdp.click(sess, box[0][2], box[0][3])
    cdp.typ(sess, pergunta)
    shot(sess, "q3_digitada")
    cdp.click(sess, send[0][2], send[0][3])
    answer = None
    t0 = time.time()
    for _ in range(45):
        time.sleep(2)
        txt = cdp.ev(sess, "document.body.innerText") or ""
        m = re.search(r"ASSISTENTE\s+[^\n]*\s+(A capital[^\n]*Bras[^\n]*)", txt, re.I)
        if m:
            answer = m.group(1)
            break
    lat = round(time.time() - t0, 1)
    shot(sess, "q3_resposta")
    # reload: o historico deve listar a conversa e reabri-la
    cdp.goto(sess, "https://ia.rangeltech.net/chat", 4)
    hist = cdp.ev(sess, "document.body.innerText") or ""
    persisted = "capital do Brasil" in hist
    shot(sess, "q3_pos_reload")
    record("Q3", "chat: mensagem digitada, resposta em streaming e historico apos reload", answer is not None and persisted,
           f"resposta={'sim' if answer else 'nao'} em {lat}s; historico={persisted}")


def wait_for(sess, js, timeout=40, step=2):
    t0 = time.time()
    while time.time() - t0 < timeout:
        v = cdp.ev(sess, js)
        if v:
            return v
        time.sleep(step)
    return None


def q12_portfolio(sess):
    evid = []
    ok = True
    # --- site (lucas.)
    cdp.goto(sess, "https://lucas.rangeltech.net/", 4)
    title = cdp.ev(sess, "document.title") or ""
    shot(sess, "q12_site")
    fb = cdp.ev(sess, "fetch('/api/feedback/health').then(r=>r.status)", True)
    site_ok = "Lucas Rangel" in title and fb == 200
    evid.append(f"site={'ok' if site_ok else 'FALHA'} (titulo={title[:30]}, feedback={fb})")
    ok &= site_ok
    # --- RAG chat (rag.): pergunta digitada e resposta
    cdp.goto(sess, "https://rag.rangeltech.net/", 5)
    box = wait_for(sess, "(()=>{const e=document.querySelector('textarea');if(!e)return null;const r=e.getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]})()", 20)
    if box:
        cdp.click(sess, box[0], box[1])
        cdp.typ(sess, "O que e o PNCP?")
        shot(sess, "q12_rag_digitada")
        cdp.key(sess, "Enter", "Enter", 13)
        ans = wait_for(sess, "(()=>{const t=document.body.innerText;return /Portal Nacional/i.test(t)?t.slice(-400):null})()", 90, 3)
        shot(sess, "q12_rag_resposta")
        rag_ok = ans is not None
    else:
        rag_ok = False
    evid.append(f"rag={'ok' if rag_ok else 'FALHA'}")
    ok &= rag_ok
    # --- Metabase (bi.): login digitado
    mb = json.load(open(VAULT.replace("ia-master.json", "metabase-admin.json"), encoding="utf-8"))
    cdp.goto(sess, "https://bi.rangeltech.net/auth/login", 3)
    wait_for(sess, "document.querySelectorAll('input').length>=2", 30)
    inputs = [x for x in cdp.ui(sess, 20) if x[0] == "input"]
    if len(inputs) >= 2:
        for (x, y), text in ((inputs[0][2:4], mb["email"]), (inputs[1][2:4], mb["password"])):
            cdp.click(sess, x, y)
            cdp.select_all(sess)
            cdp.typ(sess, text)
        shot(sess, "q12_bi_login")
        btn = [x for x in cdp.ui(sess, 30) if x[0] == "button" and ("sign" in x[1].lower() or "entrar" in x[1].lower() or "log" in x[1].lower())]
        if btn:
            cdp.click(sess, btn[0][2], btn[0][3])
        else:
            cdp.key(sess, "Enter", "Enter", 13)
        home = wait_for(sess, "(()=>{const u=location.pathname;return u.indexOf('/auth/login')<0?u:null})()", 40)
        shot(sess, "q12_bi_logado")
        bi_ok = home is not None
    else:
        bi_ok = False
    evid.append(f"bi_login={'ok' if bi_ok else 'FALHA'}")
    ok &= bi_ok
    record("Q12", "portfolio unificado (site, RAG chat, Metabase)", ok, "; ".join(evid))


def clear_site_cookies(sess, host):
    cdp.cmd("Network.enable", {}, sess)
    ck = cdp.cmd("Network.getCookies", {"urls": [f"https://{host}/"]}, sess)["result"]["cookies"]
    for c in ck:
        cdp.cmd("Network.deleteCookies", {"name": c["name"], "domain": c["domain"], "path": c["path"]}, sess)
    return len(ck)


def chatwoot_state(sess):
    """Devolve (logado, texto): logado quando /app mostra o dashboard e nao a tela de login."""
    cdp.goto(sess, "https://chat.rangeltech.net/app/", 6)
    url = cdp.ev(sess, "location.pathname") or ""
    txt = cdp.ev(sess, "document.body.innerText") or ""
    logged = ("/login" not in url) and ("sign in" not in txt.lower()[:400]) and ("entrar" not in txt.lower()[:300])
    return logged, url, txt[:200]


def q5_sso(sess, creds):
    evid = []
    # estado inicial: sem sessao do Chatwoot
    clear_site_cookies(sess, "chat.rangeltech.net")
    clear_site_cookies(sess, "ia.rangeltech.net")
    l0, u0, _ = chatwoot_state(sess)
    shot(sess, "q5_chat_antes")
    evid.append(f"antes_logado={l0}")
    # login digitado na plataforma (dispara a popup de SSO)
    login_ui(sess, creds["qa_sso_email"], creds["qa_sso_password"], "q5_ia")
    time.sleep(8)
    # confere a sessao do Chatwoot na MESMA sessao de navegador
    l1, u1, t1 = chatwoot_state(sess)
    shot(sess, "q5_chat_depois")
    evid.append(f"depois_logado={l1} url={u1}")
    # logout na plataforma derruba a sessao do Chatwoot
    cdp.goto(sess, "https://ia.rangeltech.net/dashboard", 4)
    sair = [x for x in cdp.ui(sess, 30) if x[0] == "button" and x[1].strip() == "Sair"]
    if sair:
        cdp.click(sess, sair[0][2], sair[0][3])
        time.sleep(6)
    l2, u2, _ = chatwoot_state(sess)
    shot(sess, "q5_chat_pos_logout")
    evid.append(f"pos_logout_logado={l2}")
    record("Q5", "login sincronizado plataforma<->Chatwoot (entrada e saida)", (not l0) and l1 and (not l2), "; ".join(evid))


def q6_chatwoot_login(sess, creds):
    clear_site_cookies(sess, "chat.rangeltech.net")
    cdp.goto(sess, "https://chat.rangeltech.net/app/login", 6)
    inputs = [x for x in cdp.ui(sess, 20) if x[0] == "input"]
    if len(inputs) < 2:
        record("Q6", "login direto no Chatwoot", False, "campos nao encontrados")
        return
    for (x, y), text in ((inputs[0][2:4], creds["chatwoot_email"]), (inputs[1][2:4], creds["chatwoot_password"])):
        cdp.click(sess, x, y)
        cdp.select_all(sess)
        cdp.typ(sess, text)
    shot(sess, "q6_login_preenchido")
    btn = [x for x in cdp.ui(sess, 30) if x[0] == "button"]
    cdp.click(sess, btn[-1][2], btn[-1][3]) if btn else cdp.key(sess, "Enter", "Enter", 13)
    ok = wait_for(sess, "location.pathname.indexOf('/login')<0 ? location.pathname : null", 40)
    time.sleep(3)
    shot(sess, "q6_logado")
    txt = cdp.ev(sess, "document.body.innerText") or ""
    record("Q6", "login direto no Chatwoot e caixa de entrada", ok is not None and "Conversations" in txt or "Conversas" in txt, f"path={ok}")


def http_json(url, method, body=None, headers=None, timeout=120):
    r = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                               headers=dict({"Content-Type": "application/json", "User-Agent": "rt-qa"}, **(headers or {})))
    try:
        return json.load(urllib.request.urlopen(r, timeout=timeout))
    except urllib.error.HTTPError as e:
        return {"_http": e.code, "_body": e.read().decode()[:300]}


def q7_inbox_ia(sess, creds):
    """Mensagem entra pelo inbox de API do Chatwoot -> Agent Bot -> bridge -> kernel -> resposta no Chatwoot (+ tela)."""
    cw = "https://chat.rangeltech.net"
    tok = creds["qa_cw_api_token"]
    ident = creds["qa_cw_inbox_identifier"]
    acc = creds["qa_cw_account"]
    ct = http_json(f"{cw}/public/api/v1/inboxes/{ident}/contacts", "POST", {"identifier": f"qa-{int(time.time())}", "name": "Cliente QA"})
    src = ct["source_id"]
    conv = http_json(f"{cw}/public/api/v1/inboxes/{ident}/contacts/{src}/conversations", "POST", {})["id"]
    pergunta = "Ola! Qual a capital do Brasil? Responda em uma frase."
    http_json(f"{cw}/public/api/v1/inboxes/{ident}/contacts/{src}/conversations/{conv}/messages", "POST", {"content": pergunta})
    t0 = time.time()
    reply = None
    while time.time() - t0 < 150 and not reply:
        time.sleep(4)
        msgs = http_json(f"{cw}/api/v1/accounts/{acc}/conversations/{conv}/messages", "GET", None, {"api_access_token": tok})
        for m in msgs.get("payload", []):
            if m.get("message_type") == 1 and m.get("content"):
                reply = m["content"]
    lat = round(time.time() - t0, 1)
    ok_reply = bool(reply) and "Bras" in reply
    # tela: login digitado no Chatwoot e abre a conversa
    clear_site_cookies(sess, "chat.rangeltech.net")
    cdp.goto(sess, "https://chat.rangeltech.net/app/login", 6)
    inputs = [x for x in cdp.ui(sess, 20) if x[0] == "input"]
    for (x, y), text in ((inputs[0][2:4], creds["chatwoot_email"]), (inputs[1][2:4], creds["chatwoot_password"])):
        cdp.click(sess, x, y)
        cdp.select_all(sess)
        cdp.typ(sess, text)
    btn = [x for x in cdp.ui(sess, 30) if x[0] == "button"]
    cdp.click(sess, btn[-1][2], btn[-1][3])
    time.sleep(6)
    cdp.goto(sess, f"https://chat.rangeltech.net/app/accounts/{acc}/conversations/{conv}", 8)
    txt = cdp.ev(sess, "document.body.innerText") or ""
    shot(sess, "q7_conversa_chatwoot")
    on_screen = "Bras" in txt and "capital do Brasil" in txt
    record("Q7", "mensagem pelo inbox do Chatwoot respondida pela IA (bot -> bridge -> kernel -> Chatwoot)", ok_reply and on_screen,
           f"resposta_api={ok_reply} em {lat}s; na_tela={on_screen}; conversa={conv}")


def main():
    global OUT
    args = [a for a in sys.argv[1:]]
    out = None
    if "--out" in args:
        i = args.index("--out")
        out = args[i + 1]
        del args[i:i + 2]
    OUT = out or os.path.join(os.getcwd(), "qa-" + datetime.date.today().isoformat())
    os.makedirs(OUT, exist_ok=True)
    creds = json.load(open(VAULT, encoding="utf-8"))
    todo = [a.lower() for a in args] or ["q1", "q2", "q3", "q5", "q6", "q7", "q12"]
    tab, sess = cdp.new_tab("about:blank")
    try:
        if "q1" in todo:
            q1_urls()
        if "q2" in todo:
            q2_login(sess, creds)
        if "q3" in todo:
            q3_chat(sess)
        if "q5" in todo:
            q5_sso(sess, creds)
        if "q6" in todo:
            q6_chatwoot_login(sess, creds)
        if "q7" in todo:
            q7_inbox_ia(sess, creds)
        if "q12" in todo:
            q12_portfolio(sess)
    finally:
        pass
    with open(os.path.join(OUT, "qa-report.md"), "w", encoding="utf-8") as fh:
        fh.write(f"# QA {datetime.datetime.now():%Y-%m-%d %H:%M}\n\n| Teste | Resultado | Evidencia |\n|---|---|---|\n")
        for qid, title, ok, ev in RESULTS:
            fh.write(f"| {qid} {title} | {'PASS' if ok else 'FAIL'} | {ev} |\n")
    print("relatorio:", os.path.join(OUT, "qa-report.md"))
    return 0 if all(r[2] for r in RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
