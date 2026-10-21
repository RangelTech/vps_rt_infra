#!/usr/bin/env bash
# Validacao ESTATICA da pilha (qualquer maquina; nao sobe nada, nao fala com registro):
#   1. render de teste com o .env.example preenchido com valores falsos
#   2. `docker compose config` (so valida)
#   3. nenhuma porta publicada, nenhum Traefik, nenhuma rede `public`, nenhuma imagem `latest`
#   4. nenhum cookie/sessionid/datr/xs nas configs
# --strict: falha tambem se restar DIGEST_A_PREENCHER (obrigatorio antes de qualquer deploy)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; STRICT=0; [ "${1:-}" = "--strict" ] && STRICT=1
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
# valores falsos so para validar
sed -E 's/^([A-Z_]+_(PASSWORD|SECRET|SECRET_KEY|TOKEN)|SYNAPSE_FORM_SECRET)=$/\1=falso/' "$HERE/.env.example" > "$T/env"
"$HERE/scripts/render-configs.sh" --env "$T/env" --out "$T/rendered" >/dev/null && echo "ok  render"
docker compose --env-file "$HERE/versions.env" --env-file "$T/env" -f "$HERE/compose.yml" config -q && echo "ok  docker compose config"
J="$(docker compose --env-file "$HERE/versions.env" --env-file "$T/env" -f "$HERE/compose.yml" config --format json)"
printf '%s' "$J" > "$T/c.json"
PY3=python3; "$PY3" -c "" >/dev/null 2>&1 || PY3=python; "$PY3" - "$T/c.json" <<'PY'
import json,sys
c=json.load(open(sys.argv[1])); bad=[]
for n,s in c["services"].items():
    if s.get("ports"): bad.append(f"{n}: portas publicadas")
    if any(str(k).startswith("traefik.http") for k in (s.get("labels") or {})): bad.append(f"{n}: label traefik")
    if "public" in (s.get("networks") or {}): bad.append(f"{n}: rede public")
    if ":latest" in s["image"] or ":" not in s["image"].split("/")[-1]: bad.append(f"{n}: imagem sem tag fixa")
if bad: print("\n".join(bad)); sys.exit(1)
print("ok  sem portas publicas / traefik / public / latest")
PY
if grep -rniE 'cookie|sessionid|csrftoken|\bdatr\b|c_user|ds_user_id' "$HERE/templates" | grep -viE '^\S+:[0-9]+:\s*#' ; then echo "ERRO: referencia a cookie em config" >&2; exit 4; fi
echo "ok  sem cookies nas configs"
if grep -q DIGEST_A_PREENCHER "$HERE/versions.env"; then
  [ "$STRICT" = 1 ] && { echo "ERRO: versions.env com DIGEST_A_PREENCHER (rode scripts/resolve_digests.sh)" >&2; exit 5; }
  echo "aviso: digests ainda por preencher"
fi
echo "VALIDACAO OK"
