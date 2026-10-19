#!/usr/bin/env bash
# Prova de restauracao do backup (A-10). Pega um snapshot restic (Google Drive via rclone), restaura os dumps
# Postgres num Postgres DESCARTAVEL e valida tambem os volumes (kernel, runtime-manager, workspaces).
# Nunca escreve em producao: so cria 1 container temporario (sem rede, sem porta) e 1 diretorio temporario,
# e remove SOMENTE esses dois ao terminar (trap). Sai com 1 se qualquer verificacao falhar.
#
# Uso:  restore-verify.sh                 # ultimo snapshot daily (VPS: usa docker; CI: defina PGHOST/PGUSER/PGPASSWORD)
# Env:  RESTORE_SNAPSHOT (padrao latest) RESTORE_TAG (daily) RESTORE_HOST (rt-vps) MAX_AGE_HOURS (26)
#       WORKDIR_BASE (/var/tmp) VOLUME_CHECK (1) REQUIRE_ROWS ("db.tabela ...") PG_IMAGE (pgvector/pgvector:pg16)
#       RESTIC_ENV_FILE / RCLONE_CONFIG (padrao: /opt/platform/secrets/*) REPORT_JSON (arquivo de saida opcional)
set -uo pipefail

SNAP="${RESTORE_SNAPSHOT:-latest}"; TAG="${RESTORE_TAG:-daily}"; HOSTF="${RESTORE_HOST:-rt-vps}"
MAX_AGE_HOURS="${MAX_AGE_HOURS:-26}"; WORKDIR_BASE="${WORKDIR_BASE:-/var/tmp}"; VOLUME_CHECK="${VOLUME_CHECK:-1}"
REQUIRE_ROWS="${REQUIRE_ROWS:-chatwoot_prod.accounts chatwoot_prod.users chatwoot_prod.conversations infisical.users}"
PG_IMAGE="${PG_IMAGE:-pgvector/pgvector:pg16}"
VOLUME_PATHS=(/var/lib/docker/volumes/kernel-harness_profiles /var/lib/docker/volumes/kernel-harness_users
  /var/lib/docker/volumes/kernel-harness_tenant_skills /var/lib/docker/volumes/runtime-manager_rmdata
  /var/lib/docker/volumes/runtime-manager_edge-dynamic /srv/rt/tenants /srv/rt/hermes)

RESTIC_ENV_FILE="${RESTIC_ENV_FILE:-/opt/platform/secrets/restic.env}"
# shellcheck source=/dev/null
[ -r "$RESTIC_ENV_FILE" ] && { set -a; . "$RESTIC_ENV_FILE"; set +a; }
[ -z "${RCLONE_CONFIG:-}" ] && [ -r /opt/platform/secrets/rclone.conf ] && export RCLONE_CONFIG=/opt/platform/secrets/rclone.conf

WORK="$(mktemp -d "$WORKDIR_BASE/rt-restore-verify.XXXXXX")"
CNAME="rt-restore-verify-pg-$$"
USE_DOCKER=0; [ -z "${PGHOST:-}" ] && USE_DOCKER=1
rc=0; REPORT=""
log() { echo "$*"; }
bad() { echo "FALHA: $*"; rc=1; }
cleanup() {
  [ "$USE_DOCKER" = 1 ] && docker rm -f -v "$CNAME" >/dev/null 2>&1
  case "$WORK" in "$WORKDIR_BASE"/rt-restore-verify.*) rm -rf "$WORK";; esac
}
trap cleanup EXIT
trap "exit 143" INT TERM

# ---- postgres descartavel ---------------------------------------------------
if [ "$USE_DOCKER" = 1 ]; then
  PW="$(head -c 18 /dev/urandom | base64 | tr -dc A-Za-z0-9)"
  docker run -d --rm --name "$CNAME" --network none --memory 2g -e POSTGRES_PASSWORD="$PW" \
    --label rt.restore-verify=1 "$PG_IMAGE" >/dev/null || { echo "nao subiu o postgres descartavel"; exit 1; }
  PSQL() { docker exec -i "$CNAME" psql -U postgres -v ON_ERROR_STOP=1 "$@"; }
  PGRESTORE() { docker exec -i "$CNAME" pg_restore -U postgres "$@"; }
  AMCHECK() { docker exec -i "$CNAME" pg_amcheck -U postgres "$@"; }
else
  PSQL() { psql -v ON_ERROR_STOP=1 "$@"; }
  PGRESTORE() { pg_restore "$@"; }
  AMCHECK() { pg_amcheck "$@"; }
fi
for _ in $(seq 1 60); do PSQL -d postgres -Atc 'select 1' >/dev/null 2>&1 && break; sleep 1; done
PSQL -d postgres -Atc 'select 1' >/dev/null 2>&1 || { echo "postgres descartavel nao ficou pronto"; exit 1; }

# ---- 1. idade do snapshot ---------------------------------------------------
restic snapshots "$([ "$SNAP" = latest ] && echo --latest 1 || echo "$SNAP")" --tag "$TAG" --host "$HOSTF" --json > "$WORK/snap.json" 2>"$WORK/snap.err" \
  || { cat "$WORK/snap.err"; exit 1; }
read -r SNAPID AGE < <(python3 - "$WORK/snap.json" <<'PY'
import json, sys, datetime as d
s = json.load(open(sys.argv[1]))
if not s: print("none 9999"); sys.exit()
s = s[-1]; t = d.datetime.fromisoformat(s["time"][:19]).replace(tzinfo=d.timezone.utc)
print(s["short_id"], round((d.datetime.now(d.timezone.utc) - t).total_seconds() / 3600, 1))
PY
)
[ "$SNAPID" = none ] && { echo "nenhum snapshot ($TAG/$HOSTF)"; exit 1; }
log "==> snapshot $SNAPID (${AGE}h)"
if [ "$SNAP" = latest ] && awk "BEGIN{exit !($AGE >= $MAX_AGE_HOURS)}"; then bad "snapshot velho: ${AGE}h >= ${MAX_AGE_HOURS}h"; fi

# ---- 2. restore para diretorio temporario -----------------------------------
INC=(--include '**/staging/*/pg/*.dump')
[ "$VOLUME_CHECK" = 1 ] && for p in "${VOLUME_PATHS[@]}"; do INC+=(--include "$p"); done
log "==> restic restore -> $WORK/r"
restic restore "$SNAPID" --target "$WORK/r" "${INC[@]}" 2>&1 | tail -2

# ---- 3. dumps Postgres ------------------------------------------------------
log "==> pg_restore em banco descartavel"
n=0; ndumps=0
DUMPS="$(find "$WORK/r" -path '*/staging/*/pg/*.dump' | sort)"
[ -z "$DUMPS" ] && bad "nenhum dump no snapshot"
declare -A ROWS
while IFS= read -r -u 3 f; do
  [ -n "$f" ] || continue
  ndumps=$((ndumps+1)); b="$(basename "$f" .dump)"; db="${b#*.}"; n=$((n+1)); t="v$n"
  PSQL -d postgres -Atc "create database $t" >/dev/null
  toc="$(PGRESTORE -l < "$f" 2>/dev/null | grep -E '^[0-9]+; [0-9]+ [0-9]+ TABLE ' | grep -v -c -E ' TABLE (DATA|ATTACH) ')" || true
  err="$(PGRESTORE --no-owner --no-privileges -d "$t" < "$f" 2>&1 >/dev/null | grep -v -i -E 'already exists|extension' | head -3)"
  nt="$(PSQL -d "$t" -Atc "select count(*) from pg_tables where schemaname not in ('pg_catalog','information_schema')")"
  badidx="$(PSQL -d "$t" -Atc "select count(*) from pg_index where not indisvalid")"
  PSQL -d "$t" -Atc "create extension if not exists amcheck" >/dev/null 2>&1
  AMCHECK -d "$t" >"$WORK/amcheck.out" 2>&1; amc=$?
  # contagem exata por tabela (uma consulta so): "tabela=linhas"
  CNT="$(PSQL -d "$t" -At -F= -c "select tablename, c from (select tablename, (xpath('/row/c/text()', query_to_xml(format('select count(*) as c from %I.%I', schemaname, tablename), false, true, '')))[1]::text::bigint as c from pg_tables where schemaname not in ('pg_catalog','information_schema')) x order by c desc")"
  rows="$(printf '%s\n' "$CNT" | awk -F= 'NF==2{s+=$2} END{print s+0}')"
  top="$(printf '%s\n' "$CNT" | head -3 | paste -sd' ')"
  while IFS='=' read -r tn tc; do [ -n "$tn" ] && ROWS["$db.$tn"]="$tc"; done <<< "$CNT"
  st=ok; [ -n "$err" ] && st="ERRO_RESTORE"; [ "$nt" != "$toc" ] && st="TABELAS($nt/$toc)"; [ "$badidx" != 0 ] && st="INDICE_INVALIDO"; [ "$amc" != 0 ] && st="AMCHECK"
  [ "$st" = ok ] || { bad "$b: $st ${err:+($err)}"; [ "$amc" != 0 ] && head -3 "$WORK/amcheck.out"; }
  printf '%-4s %-52s tabelas=%s/%s linhas=%s top: %s\n' "$st" "$b" "$nt" "$toc" "$rows" "$top"
  REPORT="$REPORT{\"dump\":\"$b\",\"status\":\"$st\",\"tables\":$nt,\"rows\":$rows},"
  PSQL -d postgres -Atc "drop database $t" >/dev/null
done 3<<< "$DUMPS"
for k in $REQUIRE_ROWS; do
  v="${ROWS[$k]:-}"; if [ -z "$v" ] || [ "$v" -le 0 ] 2>/dev/null; then bad "tabela-chave vazia ou ausente: $k (=${v:-ausente})"; else log "chave ok $k = $v"; fi
done

# ---- 4. volumes -------------------------------------------------------------
VREP=""
if [ "$VOLUME_CHECK" = 1 ]; then
  log "==> volumes restaurados"
  for p in "${VOLUME_PATHS[@]}"; do
    d="$WORK/r$p"
    if [ ! -d "$d" ]; then bad "volume ausente no snapshot: $p"; VREP="$VREP{\"path\":\"$p\",\"status\":\"ausente\"},"; continue; fi
    # o backup exclui node_modules e .cache: a comparacao com o volume vivo ignora os mesmos
    rf="$(find "$d" \( -name node_modules -o -name .cache \) -prune -o -type f -print | wc -l)"; rb="$(du -sb "$d" | cut -f1)"
    lf=-; lb=-
    if [ -d "$p" ]; then lf="$(find "$p" \( -name node_modules -o -name .cache \) -prune -o -type f -print 2>/dev/null | wc -l)"; lb="$(du -sb "$p" 2>/dev/null | cut -f1)"; fi
    st=ok; [ "$rf" -gt 0 ] || st="vazio"
    # volumes vivos mudam entre o backup e agora: tolera 25% de diferenca em arquivos
    if [ "$lf" != "-" ] && [ "$lf" -gt 20 ] && awk "BEGIN{exit !($rf < 0.75*$lf)}"; then st="faltam_arquivos"; fi
    [ "$st" = ok ] || bad "$p: $st (restaurado=$rf vivo=$lf)"
    printf '%-5s %-58s arquivos=%s/%s bytes=%s/%s\n' "$st" "$p" "$rf" "$lf" "$rb" "$lb"
    VREP="$VREP{\"path\":\"$p\",\"status\":\"$st\",\"files\":$rf,\"bytes\":$rb},"
  done
  # integridade dos bancos SQLite (state.db dos perfis Hermes, rmdata)
  sq="$(python3 - "$WORK/r" <<'PY'
import os, sys, sqlite3
tot = ko = skipped = 0
for root, _, fs in os.walk(sys.argv[1]):
    for f in fs:
        if f.endswith((".db", ".sqlite", ".sqlite3")):
            p = os.path.join(root, f)
            try:
                with open(p, "rb") as h:
                    if h.read(15) != b"SQLite format 3": continue
                c = sqlite3.connect(f"file:{p}?mode=ro", uri=True); r = c.execute("pragma integrity_check").fetchone()[0]; c.close()
            except Exception as e:
                r = str(e)
            tot += 1
            if r != "ok":
                # modulo FTS5/tokenizer ausente no python do host nao e corrupcao: nao verificavel
                if "vtable constructor" in r or "no such module" in r or "no such tokenizer" in r:
                    skipped += 1
                    continue
                ko += 1
                print("sqlite ruim:", os.path.relpath(p, sys.argv[1]), r, file=sys.stderr)
print(tot, ko, skipped)
PY
)"
  read -r s_tot s_ko s_skip <<< "$sq"; log "sqlite integrity_check: $s_tot bancos, $s_ko com problema, $s_skip nao verificaveis (FTS5)"
  [ "$s_ko" = 0 ] || bad "sqlite corrompido"
fi

log "==> resultado: $([ $rc = 0 ] && echo APROVADO || echo REPROVADO) (snapshot $SNAPID, $ndumps dumps)"
[ -n "${REPORT_JSON:-}" ] && printf '{"ok":%s,"snapshot":"%s","age_h":%s,"finished_at":"%s","dumps":[%s],"volumes":[%s]}\n' \
  "$([ $rc = 0 ] && echo true || echo false)" "$SNAPID" "$AGE" "$(date -Is)" "${REPORT%,}" "${VREP%,}" > "$REPORT_JSON"
exit $rc
