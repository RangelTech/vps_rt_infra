#!/usr/bin/env bash
# Alerta de backup (A-10): sinaliza last_ok.json mais velho que MAX_AGE_HOURS (26 h), ok != true ou falha registrada
# por backup.sh (last_fail.json mais novo que last_ok.json). Sai 0 = saudavel, 1 = ALERTA (compativel com uma tarefa
# de DAG/SSH que so le o codigo de saida). Roda no host por timer (rt-backup-alert.timer); somente leitura nos dados.
#
# Notificacao (todas opcionais, segredo so em /opt/platform/secrets/alert.env, nunca em log):
#   ALERT_WEBHOOK_URL   POST JSON {"text": "..."} (Google Chat/Slack/ntfy-compativel)
#   ALERT_PUSH_URL      Uptime Kuma push monitor: GET com ?status=up|down&msg=... (um monitor "push" alerta tambem
#                       se a propria VPS parar de enviar batimento)
# Sempre: syslog (logger -p user.err -t rt-backup-alert) e $OUT/alert.json.
set -uo pipefail
OUT="${BACKUP_OUT:-/opt/platform/data/backups}"
MAX_AGE_HOURS="${MAX_AGE_HOURS:-26}"
[ -r /opt/platform/secrets/alert.env ] && { set -a; . /opt/platform/secrets/alert.env; set +a; }

problems=()
age_of() { python3 - "$1" <<'PY'
import json, sys, datetime as d
try: t = d.datetime.fromisoformat(json.load(open(sys.argv[1]))["finished_at"])
except Exception: print("-1"); sys.exit()
print(int((d.datetime.now(t.tzinfo) - t).total_seconds()))
PY
}

if [ ! -r "$OUT/last_ok.json" ]; then
  problems+=("last_ok.json ausente: nenhum backup concluido")
else
  age=$(age_of "$OUT/last_ok.json")
  okflag=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("ok"))' "$OUT/last_ok.json" 2>/dev/null)
  if [ "$age" -lt 0 ]; then problems+=("last_ok.json ilegivel")
  elif [ "$age" -gt $((MAX_AGE_HOURS*3600)) ]; then problems+=("ultimo backup OK ha $((age/3600))h (limite ${MAX_AGE_HOURS}h)"); fi
  [ "$okflag" = "True" ] || problems+=("last_ok.json com ok=$okflag")
fi
if [ -r "$OUT/last_fail.json" ]; then
  fa=$(age_of "$OUT/last_fail.json"); oa=$(age_of "$OUT/last_ok.json" 2>/dev/null || echo -1)
  # falha mais recente que o ultimo OK (age menor = mais novo)
  if [ "$fa" -ge 0 ] && { [ "$oa" -lt 0 ] || [ "$fa" -lt "$oa" ]; }; then
    problems+=("backup.sh falhou em $(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("finished_at"))' "$OUT/last_fail.json"): $(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("reason",""))' "$OUT/last_fail.json")")
  fi
fi
# restore-verify mensal/semanal: reprovado tambem alerta
if [ -r "$OUT/restore_verify.json" ]; then
  python3 -c 'import json,sys;sys.exit(0 if json.load(open(sys.argv[1])).get("ok") else 1)' "$OUT/restore_verify.json" || problems+=("restore-verify reprovado (ver $OUT/restore_verify.json)")
fi

if [ ${#problems[@]} -eq 0 ]; then
  printf '{"alert":false,"checked_at":"%s"}\n' "$(date -Is)" > "$OUT/alert.json"
  [ -n "${ALERT_PUSH_URL:-}" ] && curl -fsS -m 10 -o /dev/null "${ALERT_PUSH_URL%%\?*}?status=up&msg=backup-ok" || true
  echo "backup saudavel"; exit 0
fi
msg="ALERTA backup VPS: $(IFS='; '; echo "${problems[*]}")"
printf '{"alert":true,"checked_at":"%s","problems":%s}\n' "$(date -Is)" "$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1:]))' "${problems[@]}")" > "$OUT/alert.json"
logger -p user.err -t rt-backup-alert "$msg" 2>/dev/null || true
echo "$msg" >&2
[ -n "${ALERT_WEBHOOK_URL:-}" ] && curl -fsS -m 10 -o /dev/null -H 'Content-Type: application/json' -d "$(python3 -c 'import json,sys;print(json.dumps({"text":sys.argv[1]}))' "$msg")" "$ALERT_WEBHOOK_URL" || true
[ -n "${ALERT_PUSH_URL:-}" ] && curl -fsS -m 10 -o /dev/null -G --data-urlencode "status=down" --data-urlencode "msg=${msg:0:200}" "${ALERT_PUSH_URL%%\?*}" || true
exit 1
