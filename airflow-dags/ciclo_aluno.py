"""Ciclo de vida da area do aluno (user.rangeltech.net): recuperacao de venda e boas-vindas.

Duas vezes por dia (10h e 17h, Brasilia) chama POST /api/ciclo/executar. Quem decide tudo e o motor da area do aluno
(regras em app/ciclo_regras.json do repo ai_aluno): quem comecou a comprar e nao pagou (carrinho, Pix, boleto, cartao recusado)
e quem comprou e ainda nao entrou. Regras que ele aplica: so entre 8h e 20h, no maximo 1 mensagem por pessoa por dia,
para ao comprar / pedir para sair / depois de 21 dias. A DAG so orquestra: horario, tentativas e alerta se falhar.

Token: Variable do Airflow `ALUNO_API_TOKEN` (gravada pelo workflow aluno-airflow-ciclo; nunca no Git).
Teste sem enviar nada: trigger com conf {"dry": true}.
"""
import json
import urllib.error
import urllib.request
from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator

URL = "https://user.rangeltech.net/api/ciclo/executar"


def executar(**ctx):
    dry = bool((ctx["dag_run"].conf or {}).get("dry", False))
    req = urllib.request.Request(
        URL + ("?dry=1" if dry else ""),
        data=b"",
        method="POST",
        headers={"Authorization": "Bearer " + Variable.get("ALUNO_API_TOKEN"), "User-Agent": "rt-airflow/1.0", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            out = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"ciclo/executar respondeu {e.code}") from e
    # so contagens no log: nada de e-mail, telefone ou nome de cliente
    print({k: out.get(k) for k in ("dry", "agora", "dentro_da_janela", "enviados", "parados", "aguardando", "sem_canal")})
    if out.get("sem_canal"):
        print("ATENCAO: ha leads sem canal de envio (SMTP ou webhook de WhatsApp nao configurado).")
    return {k: out.get(k) for k in ("enviados", "parados", "aguardando", "sem_canal")}


with DAG(
    dag_id="ciclo_aluno",
    description="Recuperacao de venda e boas-vindas da area do aluno",
    schedule="0 10,17 * * *",
    start_date=pendulum.datetime(2026, 10, 29, tz="America/Sao_Paulo"),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 3, "retry_delay": timedelta(minutes=10)},
    tags=["aluno", "vendas"],
) as dag:
    PythonOperator(task_id="executar_ciclo", python_callable=executar, execution_timeout=timedelta(minutes=10))
