# Hermes Relay (SPEC_HERMES_INTEGRADO_RIA_ATENDIMENTO.md, Fase B) -- slice 1.
# Runs on this VPS, not Cloud Run: the spec requires infra that supports a
# persistent WebSocket per connected device (sec. 12).
FROM python:3.12-slim AS runtime

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

RUN useradd -m -u 10001 hermes-relay
USER hermes-relay

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).read()"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
