#!/usr/bin/env bash
# Funcoes comuns dos scripts de host (rodam NA VPS). Guarda de host: so a VPS Contabo da Rangel Tech.
RT_EXPECTED_HOST="${RT_EXPECTED_HOST:-vmi3468840}"
rt_guard_host() {
  [ "$(hostname)" = "$RT_EXPECTED_HOST" ] || { echo "host inesperado: $(hostname) (esperado $RT_EXPECTED_HOST) - abortando" >&2; exit 2; }
}
rt_log() { echo "[$(date -Is)] $*"; }
# le chave=valor de um .lock (formato KEY=VALUE, sem aspas)
rt_lock_get() { grep -E "^$2=" "$1" | head -n1 | cut -d= -f2-; }
