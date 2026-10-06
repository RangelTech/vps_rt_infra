"""Teste Senior: abre o Chromium (Playwright) com a sessao salva em estado_senior.json, espera 5s e fecha.

Por enquanto nao executa nenhuma acao na plataforma; a base para as rotinas diarias de QA.
Horarios (America/Sao_Paulo): 09:00, 12:00, 13:00 e 18:00.
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pendulum
from airflow.decorators import dag, task

TZ = pendulum.timezone("America/Sao_Paulo")
ESTADO = Path(__file__).parent / "estado_senior.json"
URL = "https://platform.senior.com.br/senior-x/#/"


@dag(
    dag_id="teste_senior",
    description="Abre a plataforma Senior com os cookies salvos, espera 5s e fecha",
    schedule="0 9,12,13,18 * * *",
    start_date=pendulum.datetime(2026, 10, 1, tz=TZ),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=2)},
    tags=["qa", "senior", "playwright"],
)
def teste_senior():
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
            finally:
                browser.close()

    abrir_e_fechar()


teste_senior()
