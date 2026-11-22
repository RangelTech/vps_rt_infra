#!/usr/bin/env python3
"""Caça-GPU v2 (pedido do Lucas, 22/11/2026): pesca 2x RTX 3090 cada vez mais baratas para o Qwen, sem nunca deixar o Qwen sem máquina.

Ciclo (cron de minuto em minuto, com flock para não sobrepor):
1. PROCURA sempre: 2x RTX 3090 (ou Ti), CUDA >= 13, aluguel fixo, disco >= 60 GB, internet >= 300 Mbps. Preço = aluguel + 50 GB.
   Se achar uma mais barata (por MARGEM) que a mais barata que já temos (fixa ou candidata viva), aluga na hora. Até MAX_CAND candidatas.
2. TESTA cada candidata sozinho (o "agente" de teste): quando liga, entra por SSH, baixa o modelo, sobe o vLLM igual à produção e
   faz 3 provas (saúde, resposta curta, chamada de ferramenta) e mede a velocidade. Falhou ou não ligou no prazo: destrói e põe na
   lista negra.
3. TROCA só de madrugada (00h às 06h de Brasília): candidata pronta e mais barata que a fixa vira a fixa (GPU_STATIC_INSTANCE_ID +
   recriar o llm-queue), confere uma conversa real pela fila e SÓ ENTÃO destrói a fixa antiga. Se a conversa não passar, volta para a
   anterior. A máquina antiga do Brasil (ANTIGA) nunca é destruída.
Avisa por e-mail cada aluguel, teste, troca e falha. Estado em ~/caca-gpu/estado.json, log em ~/caca-gpu/caca.log.
"""
from __future__ import annotations

import datetime as dt
import json
import smtplib
import subprocess
import time
import urllib.request
from email.message import EmailMessage
from pathlib import Path

DIR = Path.home() / "caca-gpu"
ESTADO = DIR / "estado.json"
LOG = DIR / "caca.log"
CHAVE_SSH = DIR / "chave"
CFG = json.loads((DIR / "config.json").read_text())
IMAGEM = "ghcr.io/lucasrangelssouza/qwen-vllm:v0.30.0-cu13-slim1"
DISCO = 50
MARGEM = float(CFG.get("margem", 0.01))
ANTIGA = int(CFG.get("antiga", 60855119))
MAX_CAND = int(CFG.get("max_candidatas", 2))
MIN_TOKS = float(CFG.get("min_tok_s", 15))
PRAZO_LIGAR = 35 * 60  # a imagem do Qwen é grande: host com internet comum leva 20-30 min para baixar
PRAZO_PREPARAR = 50 * 60
STACK = "/opt/platform/stacks/llm-queue"
SEGREDO = "/opt/platform/secrets/llm-queue.env"
API = "https://console.vast.ai/api"


def log(msg: str) -> None:
    with LOG.open("a") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")


def sh(cmd: list[str], timeout: int = 60, entrada: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, input=entrada)


def env(container: str, nome: str) -> str:
    return sh(["docker", "exec", container, "printenv", nome], 30).stdout.strip()


CHAVE = env("llm-queue", "VAST_API_KEY")


def vast(metodo: str, caminho: str, corpo: dict | None = None) -> dict:
    req = urllib.request.Request(API + caminho, method=metodo, data=json.dumps(corpo).encode() if corpo is not None else None,
                                 headers={"Authorization": "Bearer " + CHAVE, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read() or b"{}")


def avisar(assunto: str, texto: str) -> None:
    try:
        m = EmailMessage()
        m["Subject"] = "[Caça-GPU] " + assunto
        m["From"] = env("llm-access", "SMTP_FROM")
        m["To"] = CFG["email"]
        m.set_content(texto)
        with smtplib.SMTP(env("llm-access", "SMTP_HOST"), int(env("llm-access", "SMTP_PORT") or 587), timeout=30) as s:
            s.starttls()
            s.login(env("llm-access", "SMTP_USER"), env("llm-access", "SMTP_PASSWORD"))
            s.send_message(m)
        log("aviso: " + assunto)
    except Exception as e:  # o aviso nunca derruba o vigia
        log("aviso falhou (%s): %r" % (assunto, e))


def madrugada() -> bool:
    h = (dt.datetime.utcnow() - dt.timedelta(hours=3)).hour
    return 0 <= h < 6


def preco_inst(i: dict) -> float:
    return float(i.get("dph_base") or 0) + float(i.get("storage_cost") or 0) * DISCO / 720


def preco_oferta(o: dict) -> float:
    return float(o["dph_base"]) + float(o.get("storage_cost") or 0) * DISCO / 720


def ssh_de(i: dict) -> tuple[str, int]:
    return str(i.get("ssh_host")), int(i.get("ssh_port") or 0)


def remoto(alvo: tuple[str, int], comando: str, timeout: int = 60, entrada: str | None = None) -> subprocess.CompletedProcess:
    return sh(["ssh", "-i", str(CHAVE_SSH), "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "BatchMode=yes",
               "-o", "ConnectTimeout=20", "-o", "LogLevel=ERROR", "-p", str(alvo[1]), "root@" + alvo[0], comando], timeout, entrada)


PREPARO = r"""#!/bin/bash
# preparo da candidata: baixa o modelo e sobe o vLLM com o start_vllm.sh da produção
exec >> /workspace/caca-prep.log 2>&1
echo "== preparo $(date -u +%FT%TZ)"
[ -f /venv/main/bin/activate ] && . /venv/main/bin/activate
mkdir -p /workspace/models
if ! test -s /workspace/models/awq/model.safetensors; then
  pip install -q hf_transfer >/dev/null 2>&1 && export HF_HUB_ENABLE_HF_TRANSFER=1
  hf download twolven/Qwen3.8-27B-abliterated-AWQ-MTP --local-dir /workspace/models/awq >/dev/null 2>&1 || { unset HF_HUB_ENABLE_HF_TRANSFER; hf download twolven/Qwen3.8-27B-abliterated-AWQ-MTP --local-dir /workspace/models/awq >/dev/null 2>&1; }
fi
test -s /workspace/models/awq/config.json || { echo FALHA_DOWNLOAD; exit 1; }
echo MODELO_OK
bash /workspace/start_vllm.sh
"""

PROVA = r"""
set -u
h=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18000/health)
[ "$h" = 200 ] || { echo "SAUDE $h"; exit 2; }
r1=$(curl -s -m 60 http://127.0.0.1:18000/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"qwen-abliterated","max_tokens":20,"messages":[{"role":"user","content":"Responda apenas: ok"}],"chat_template_kwargs":{"enable_thinking":false}}')
echo "$r1" | grep -qi '"content"' || { echo "RESPOSTA $r1" | head -c 300; exit 3; }
r2=$(curl -s -m 60 http://127.0.0.1:18000/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"qwen-abliterated","max_tokens":200,"messages":[{"role":"user","content":"Use a ferramenta soma com a=2 e b=3."}],"tools":[{"type":"function","function":{"name":"soma","description":"soma dois numeros","parameters":{"type":"object","properties":{"a":{"type":"number"},"b":{"type":"number"}},"required":["a","b"]}}}],"chat_template_kwargs":{"enable_thinking":false}}')
echo "$r2" | grep -q '"tool_calls"' && echo "$r2" | grep -q 'soma' || { echo "FERRAMENTA $r2" | head -c 300; exit 4; }
t0=$(date +%s.%N)
r3=$(curl -s -m 120 http://127.0.0.1:18000/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"qwen-abliterated","max_tokens":300,"min_tokens":300,"ignore_eos":true,"messages":[{"role":"user","content":"Conte uma historia longa."}],"chat_template_kwargs":{"enable_thinking":false}}')
t1=$(date +%s.%N)
n=$(echo "$r3" | grep -o '"completion_tokens":[0-9]*' | grep -o '[0-9]*$')
awk -v n="${n:-0}" -v a="$t0" -v b="$t1" 'BEGIN{printf "TOKS %.1f\n", n/(b-a)}'
"""


def destruir(inst: int, motivo: str) -> None:
    if inst == ANTIGA:
        log("não destruo a antiga %d (%s)" % (inst, motivo))
        return
    try:
        vast("DELETE", "/v0/instances/%d/" % inst)
        log("destruí %d: %s" % (inst, motivo))
    except Exception as e:
        log("falha ao destruir %d: %r" % (inst, e))


def fixa_atual() -> int:
    return int(env("llm-queue", "GPU_STATIC_INSTANCE_ID") or 0)


def apontar(inst: int) -> None:
    sh(["sudo", "sed", "-i", "s/^GPU_STATIC_INSTANCE_ID=.*/GPU_STATIC_INSTANCE_ID=%d/" % inst, SEGREDO], 30)
    r = subprocess.run("cd %s && sudo docker compose --env-file .release.env up -d --force-recreate" % STACK, shell=True,
                       capture_output=True, text=True, timeout=300)
    log("llm-queue recriado apontando para %d (rc %d)" % (inst, r.returncode))


def conversa_pela_fila() -> bool:
    ip = sh(["docker", "inspect", "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}", "llm-queue"], 30).stdout.split()
    if not ip:
        return False
    corpo = json.dumps({"model": "qwen-abliterated", "max_tokens": 20, "messages": [{"role": "user", "content": "Responda apenas: ok"}],
                        "chat_template_kwargs": {"enable_thinking": False}}).encode()
    req = urllib.request.Request("http://%s:8000/v1/chat/completions" % ip[0], data=corpo, method="POST",
                                 headers={"Authorization": "Bearer " + env("llm-access", "UPSTREAM_KEY"), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            j = json.loads(r.read())
        return bool(j.get("choices"))
    except Exception as e:
        log("conversa pela fila falhou: %r" % e)
        return False


def trocar(c: dict, fixa: int, ref: float, insts: dict) -> bool:
    log("TROCA: %d (%.3f) -> %d (%.3f)" % (fixa, ref, c["instancia"], c["preco"]))
    apontar(c["instancia"])
    ok = False
    for _ in range(40):  # até ~10 min para a fila reconhecer a máquina e responder
        time.sleep(15)
        if conversa_pela_fila():
            ok = True
            break
    if not ok:
        log("troca falhou: voltando para %d" % fixa)
        apontar(fixa)
        avisar("troca de GPU falhou, voltei para a anterior",
               "Tentei trocar o Qwen de %d para %d (US$ %.3f/h), mas a fila não respondeu em 10 min. Voltei para %d."
               % (fixa, c["instancia"], c["preco"], fixa))
        return False
    antiga = insts.get(fixa) or {}
    if antiga.get("actual_status") == "running":
        destruir(fixa, "substituída pela %d mais barata" % c["instancia"])
    else:  # a fixa caiu (host offline): não destrói; fica de candidata e, se voltar e for mais barata, é testada e volta
        log("fixa anterior %d está %s: fica guardada como candidata" % (fixa, antiga.get("actual_status")))
        c["_reserva"] = {"instancia": fixa, "oferta": 0, "maquina": antiga.get("machine_id"), "local": str(antiga.get("geolocation")),
                         "preco": round(preco_inst(antiga), 4) if antiga else ref, "em": time.time(), "fase": "ligando", "volta": True}
    avisar("Qwen trocado para máquina mais barata: US$ %.3f/h" % c["preco"],
           "O Qwen agora roda na instância %d (%s, US$ %.3f/h, ~US$ %.0f/mês).\nA anterior (%d, US$ %.3f/h) foi destruída%s.\n"
           "Provas antes da troca: saúde, resposta, ferramenta e %s tok/s. Depois da troca: conversa real pela fila respondeu."
           % (c["instancia"], c["local"], c["preco"], c["preco"] * 720, fixa, ref, " (menos a antiga do Brasil, que nunca é apagada)" if fixa == ANTIGA else "",
              c.get("toks", "?")))
    return True


def cuidar(c: dict, insts: dict, est: dict) -> None:
    i = insts.get(c["instancia"])
    if not i:
        c["fase"] = "fim"
        log("candidata %d sumiu da conta" % c["instancia"])
        return
    msg = i.get("status_msg") or ""
    if c["fase"] == "ligando":
        if i.get("actual_status") == "running":
            alvo = ssh_de(i)
            r = remoto(alvo, "mkdir -p /workspace && cat > /workspace/start_vllm.sh", 60, (DIR / "start_vllm.sh").read_text())
            r2 = remoto(alvo, "cat > /workspace/caca-prep.sh && chmod +x /workspace/caca-prep.sh && (setsid nohup /workspace/caca-prep.sh >/dev/null 2>&1 < /dev/null &) && echo ok", 60, PREPARO)
            if r.returncode == 0 and "ok" in r2.stdout:
                c["fase"], c["prep_em"] = "preparando", time.time()
                log("candidata %d ligou; preparo iniciado" % c["instancia"])
            else:
                log("candidata %d: SSH ainda não entrou (%s)" % (c["instancia"], (r.stderr or r2.stderr)[:120]))
        if c["fase"] == "ligando" and not c.get("volta") and c["instancia"] != ANTIGA and (time.time() - c["em"] > PRAZO_LIGAR or "no space" in msg):
            falhou(c, est, "não ligou: " + msg[:120])
    elif c["fase"] == "preparando":
        r = remoto(ssh_de(i), PROVA, 300)
        saida = (r.stdout + r.stderr).strip()
        if r.returncode == 0 and "TOKS" in saida:
            toks = float(saida.split("TOKS")[-1].split()[0])
            if toks < MIN_TOKS:
                return falhou(c, est, "lenta: %.1f tok/s" % toks)
            c["fase"], c["toks"] = "pronta", toks
            log("candidata %d PRONTA (%.1f tok/s)" % (c["instancia"], toks))
            avisar("candidata testada e aprovada: US$ %.3f/h" % c["preco"],
                   "A instância %d (%s, US$ %.3f/h) passou nas provas: saúde, resposta, ferramenta, %.1f tok/s.\n"
                   "A troca acontece sozinha na próxima madrugada (00h–06h de Brasília)." % (c["instancia"], c["local"], c["preco"], toks))
        elif r.returncode in (3, 4):
            falhou(c, est, "prova falhou: " + saida[:200])
        elif time.time() - c["prep_em"] > PRAZO_PREPARAR:
            log_prep = remoto(ssh_de(i), "tail -5 /workspace/caca-prep.log; tail -3 /workspace/vllm_llm.log", 60).stdout
            falhou(c, est, "não subiu o vLLM em 50 min: " + log_prep[-300:])


def falhou(c: dict, est: dict, motivo: str) -> None:
    log("candidata %d FALHOU: %s" % (c["instancia"], motivo))
    if c.get("volta") or c["instancia"] == ANTIGA:  # máquina nossa que caiu: não destrói, volta a esperar
        c["fase"], c["em"] = "ligando", time.time()
        return
    destruir(c["instancia"], motivo)
    if c.get("maquina") and c.get("maquina") not in est["negra"]:
        est["negra"].append(c["maquina"])
    c["fase"] = "fim"
    avisar("candidata descartada (US$ %.3f/h)" % c["preco"], "A instância %d (%s) foi destruída: %s" % (c["instancia"], c["local"], motivo))


def main() -> None:
    est = json.loads(ESTADO.read_text()) if ESTADO.exists() else {}
    est.setdefault("negra", [])
    est.setdefault("candidatas", [])
    est.setdefault("antiga_rodando", False)
    if est.get("candidato"):  # formato da v1
        velho = est.pop("candidato")
        velho.setdefault("fase", "ligando")
        est["candidatas"].append(velho)
    insts = {i["id"]: i for i in vast("GET", "/v1/instances/").get("instances", [])}
    fixa = fixa_atual()
    ref = preco_inst(insts[fixa]) if fixa in insts else 9.0
    est["candidatas"] = [c for c in est["candidatas"] if c["instancia"] != fixa and c.get("fase") != "fim"]

    # EMERGÊNCIA: a fixa caiu (host offline/parado) há mais de 5 min. Troca na hora, a qualquer horário, pela candidata pronta mais
    # barata; sem nenhuma pronta, aluga já a oferta mais barata que existir (mesmo mais cara que a fixa) e ela vira candidata.
    fx = insts.get(fixa) or {}
    if fx.get("actual_status") == "running":
        est.pop("fixa_off_desde", None)
    else:
        est.setdefault("fixa_off_desde", time.time())
        if est.get("avisado_off") != fixa:
            est["avisado_off"] = fixa
            avisar("GPU do Qwen caiu (%d)" % fixa, "A fixa %d está %s (%s). Se não voltar em 5 min eu troco por outra sozinho."
                   % (fixa, fx.get("actual_status"), (fx.get("status_msg") or "")[:120]))
    emergencia = time.time() - est.get("fixa_off_desde", time.time()) > 300

    # a antiga do Brasil voltou: avisa e entra como candidata (já tem o modelo no disco)
    a = insts.get(ANTIGA)
    rodando = bool(a and a.get("actual_status") == "running")
    if rodando and not est["antiga_rodando"] and fixa != ANTIGA and not any(c["instancia"] == ANTIGA for c in est["candidatas"]):
        est["candidatas"].append({"instancia": ANTIGA, "oferta": 0, "maquina": a.get("machine_id"), "local": str(a.get("geolocation")),
                                  "preco": round(preco_inst(a), 4), "em": time.time(), "fase": "ligando"})
        avisar("a GPU antiga do Brasil voltou", "A instância %d (US$ %.3f/h) ligou de novo; vou testá-la e, se passar, ela volta a ser a fixa na madrugada."
               % (ANTIGA, preco_inst(a)))
    est["antiga_rodando"] = rodando

    for c in est["candidatas"]:
        try:
            cuidar(c, insts, est)
        except Exception as e:
            log("erro cuidando de %s: %r" % (c.get("instancia"), e))
    est["candidatas"] = [c for c in est["candidatas"] if c.get("fase") != "fim"]
    ESTADO.write_text(json.dumps(est))

    # troca de madrugada: a pronta mais barata, se for mais barata que a fixa
    prontas = sorted([c for c in est["candidatas"] if c["fase"] == "pronta"], key=lambda c: c["preco"])
    if prontas and (emergencia or (prontas[0]["preco"] < ref - 0.001 and madrugada())):
        c = prontas[0]
        if emergencia:
            log("EMERGÊNCIA: fixa %d fora há %.0f min; trocando já pela %d" % (fixa, (time.time() - est["fixa_off_desde"]) / 60, c["instancia"]))
        if trocar(c, fixa, ref, insts):
            est.pop("fixa_off_desde", None)
            # as outras candidatas mais caras que a nova fixa não servem mais
            for o in est["candidatas"]:
                if o is not c and o["preco"] >= c["preco"]:
                    destruir(o["instancia"], "mais cara que a nova fixa")
                    o["fase"] = "fim"
            est["candidatas"] = [o for o in est["candidatas"] if o is not c and o.get("fase") != "fim"]
            if c.get("_reserva"):
                est["candidatas"].append(c.pop("_reserva"))
            fixa, ref = c["instancia"], c["preco"]
        ESTADO.write_text(json.dumps(est))

    # procura sempre: mais barata que a mais barata que já temos
    vivas = [c for c in est["candidatas"] if c["instancia"] != ANTIGA]
    teto = min([ref] + [c["preco"] for c in est["candidatas"]]) - MARGEM
    q = {"num_gpus": {"eq": 2}, "gpu_name": {"in": ["RTX 3090", "RTX 3090 Ti"]}, "rentable": {"eq": True}, "rented": {"eq": False},
         "cuda_max_good": {"gte": 13}, "disk_space": {"gte": 60}, "inet_down": {"gte": 300}, "order": [["dph_total", "asc"]],
         "limit": 100, "type": "on-demand"}
    nossas = {i.get("machine_id") for i in insts.values()}
    ofertas = sorted([o for o in vast("POST", "/v0/bundles/", q).get("offers", [])
                      if o.get("machine_id") not in est["negra"] and o.get("machine_id") not in nossas], key=preco_oferta)
    if not ofertas:
        log("nenhuma oferta; fixa %d %.3f" % (fixa, ref))
        return
    o = ofertas[0]
    p = preco_oferta(o)
    log("melhor %.3f (%d %s) | fixa %d %.3f | candidatas %s" % (p, o["id"], o.get("geolocation"), fixa, ref,
        ",".join("%d:%s:%.3f" % (c["instancia"], c["fase"], c["preco"]) for c in est["candidatas"]) or "-"))
    em_teste = [c for c in est["candidatas"] if not c.get("volta") and c["instancia"] != ANTIGA]
    urgente = emergencia and not em_teste  # fixa caiu e ninguém sendo preparado: aluga a mais barata que existir
    if urgente:
        log("EMERGÊNCIA: alugando a mais barata disponível (%.3f) mesmo acima da fixa" % p)
    if urgente or (p <= teto and len(vivas) < MAX_CAND):
        r = vast("PUT", "/v0/asks/%d/" % o["id"], {"client_id": "me", "image": IMAGEM, "disk": DISCO, "runtype": "ssh_direct",
                                                   "env": {"CONTAINER_RUNTIME": "runc"}, "label": "caca-%d" % o["id"]})
        if r.get("success"):
            c = {"instancia": int(r["new_contract"]), "oferta": o["id"], "maquina": o.get("machine_id"), "local": str(o.get("geolocation")),
                 "preco": round(p, 4), "em": time.time(), "fase": "ligando"}
            est["candidatas"].append(c)
            log("ALUGUEI %d por %.3f" % (c["instancia"], p))
            avisar("aluguei 2x3090 mais barata para testar: US$ %.3f/h" % p,
                   "Instância %d (%s, máquina %s), US$ %.3f/h (~US$ %.0f/mês). Fixa atual: %d a US$ %.3f/h.\n"
                   "Agora eu testo sozinho (modelo, vLLM, provas) e, se passar, troco na madrugada." % (c["instancia"], c["local"], c["maquina"], p, p * 720, fixa, ref))
        else:
            log("aluguel recusado: %s" % json.dumps(r)[:200])
    ESTADO.write_text(json.dumps(est))


if __name__ == "__main__":
    DIR.mkdir(exist_ok=True)
    try:
        main()
    except Exception as e:
        log("erro: %r" % e)
