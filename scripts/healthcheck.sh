#!/usr/bin/env bash
# Healthcheck estrito da plataforma (roda NA VPS). Sai com codigo != 0 se QUALQUER item critico falhar. Sem `|| true`.
set -uo pipefail
fail=0
chk() { # nome, comando
  if eval "$2" >/dev/null 2>&1; then echo "OK   $1"; else echo "FAIL $1"; fail=1; fi
}
chk "traefik rodando"            "[ \"\$(docker inspect -f '{{.State.Running}}' traefik)\" = true ]"
chk "postgres saudavel"          "[ \"\$(docker inspect -f '{{.State.Health.Status}}' postgres)\" = healthy ]"
chk "infisical saudavel (API)"   "curl -fsS -m 8 http://127.0.0.1:8080/api/status || docker exec infisical wget -qO- http://127.0.0.1:8080/api/status"
chk "airflow webserver saudavel" "[ \"\$(docker inspect -f '{{.State.Health.Status}}' airflow-airflow-webserver-1)\" = healthy ]"
chk "airflow scheduler rodando"  "[ \"\$(docker inspect -f '{{.State.Running}}' airflow-airflow-scheduler-1)\" = true ]"
chk "ultimo backup < 26h"        "python3 -c \"import json,datetime as d;j=json.load(open('/opt/platform/data/backups/last_ok.json'));t=d.datetime.fromisoformat(j['finished_at']);assert (d.datetime.now(t.tzinfo)-t).total_seconds()<26*3600\""
# nenhum container em Restarting
rest="$(docker ps --filter status=restarting --format '{{.Names}}')"
if [ -n "$rest" ]; then echo "FAIL containers reiniciando em loop: $rest"; fail=1; else echo "OK   nenhum container em loop"; fi
exit "$fail"
