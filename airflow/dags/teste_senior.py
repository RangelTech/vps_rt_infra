"""Teste Senior: abre o Chromium (Playwright) com a sessao salva em estado_senior.json, espera 5s e fecha.

Valida a sessao procurando o botao "Registrar Ponto" (dentro de um iframe da tela inicial). NUNCA clica nele:
so registra no log se achou ou nao, salva um print em /opt/airflow/logs/screenshots/ e falha a task se nao achou
(sessao expirada). E a base para as rotinas diarias de QA.

- Horarios (America/Sao_Paulo, UTC-3): 08:55, 11:55, 12:55 e 17:55, so de segunda a sexta.
- Feriados nacionais do Brasil: a run e criada, mas a primeira task pula o resto (fica "skipped").
- Antes de abrir o navegador, pausa aleatoria de 0 a 10 minutos para nao rodar sempre no mesmo minuto.
"""
from __future__ import annotations

import random
import time
from datetime import timedelta
from pathlib import Path

import holidays
import pendulum
from airflow.decorators import dag, task
from airflow.timetables.trigger import CronTriggerTimetable

TZ = pendulum.timezone("America/Sao_Paulo")
ESTADO = Path(__file__).parent / "estado_senior.json"
URL = "https://platform.senior.com.br/senior-x/#/"
JITTER_MAX_SEGUNDOS = 10 * 60
# Botao "Registrar Ponto": id fixo btn-clocking-event-<numero>, dentro de um iframe (hcm-pontomobile).
SELETOR_BOTAO = 'button[id^="btn-clocking-event"]'
PASTA_PRINTS = Path("/opt/airflow/logs/screenshots")
# Execucao manual de teste: dag_run.conf = {"teste": true} pula a checagem de feriado e a pausa aleatoria.


@dag(
    dag_id="teste_senior",
    description="Abre a plataforma Senior com os cookies salvos, espera 5s e fecha (dias uteis)",
    # Cron em horario de Brasilia; a run dispara no proprio horario (logical date = o instante do disparo).
    schedule=CronTriggerTimetable("55 8,11,12,17 * * 1-5", timezone="America/Sao_Paulo"),
    # Comeca em 07/10/2026 e catchup desligado: nunca gera runs atrasadas.
    start_date=pendulum.datetime(2026, 10, 7, tz=TZ),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=2)},
    tags=["qa", "senior", "playwright"],
)
def teste_senior():
    @task.short_circuit
    def eh_dia_util(dag_run=None) -> bool:
        if (dag_run.conf or {}).get("teste"):
            print("Run de teste: ignorando checagem de feriado.")
            return True
        hoje = pendulum.now(TZ).date()
        feriado = holidays.Brazil(years=hoje.year).get(hoje)
        if feriado:
            print(f"{hoje} e feriado ({feriado}); pulando.")
            return False
        return True

    @task
    def pausa_aleatoria(dag_run=None) -> None:
        if (dag_run.conf or {}).get("teste"):
            print("Run de teste: sem pausa.")
            return
        segundos = random.uniform(0, JITTER_MAX_SEGUNDOS)
        print(f"Pausa de {segundos / 60:.1f} min ({segundos:.0f}s) antes de abrir o navegador.")
        time.sleep(segundos)

    @task(execution_timeout=timedelta(minutes=3))
    def abrir_e_fechar() -> None:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            try:
                ctx = browser.new_context(storage_state=str(ESTADO))
                page = ctx.new_page()
                page.goto(URL)
                page.wait_for_timeout(5000)
                print(f"URL: {page.url}")
                print(f"Titulo: {page.title()}")
                # O botao fica num iframe que carrega depois; espera ate 20s por ele em qualquer frame.
                achou = 0
                for _ in range(20):
                    achou = sum(f.locator(SELETOR_BOTAO).count() for f in page.frames)
                    if achou:
                        break
                    page.wait_for_timeout(1000)
                PASTA_PRINTS.mkdir(parents=True, exist_ok=True)
                agora = pendulum.now(TZ).format("YYYYMMDD_HHmmss")
                for nome in (f"senior_{agora}.png", "senior_latest.png"):
                    page.screenshot(path=str(PASTA_PRINTS / nome))
                print(f"BOTAO 'Registrar Ponto' {'ENCONTRADO' if achou else 'NAO ENCONTRADO'} (ocorrencias: {achou}). Nao foi clicado.")
                if not achou:
                    raise AssertionError("Botao Registrar Ponto nao encontrado: sessao expirada ou tela mudou.")
            finally:
                browser.close()

    eh_dia_util() >> pausa_aleatoria() >> abrir_e_fechar()


teste_senior()
