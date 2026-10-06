# Airflow pessoal da RT (airflow.rangeltech.net) com Playwright + Chromium para os testes automatizados de QA.
FROM apache/airflow:2.10.5-python3.12

USER airflow
RUN pip install --no-cache-dir playwright==1.58.0 holidays==0.90

# Navegador e dependencias de sistema ficam fora do HOME para qualquer usuario conseguir ler.
USER root
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN /home/airflow/.local/bin/playwright install --with-deps chromium \
    && chmod -R a+rX /ms-playwright \
    && rm -rf /var/lib/apt/lists/*

USER airflow
