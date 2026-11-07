#!/usr/bin/env bash
# Backup diario da VPS para o Google Drive (restic sobre rclone). Roda como root (timer systemd rt-backup).
#
#  - dumps logicos POR BANCO dos Postgres da plataforma (nunca copia de diretorio de dados com banco aberto);
#  - arquivos de configuracao/estado pequenos (compose, configs, secrets, Traefik/ACME, MinIO, Synapse, Redis...);
#  - Airflow pessoal: leitura somente (pg_dump + copia dos volumes state/dags); NUNCA altera o Airflow;
#  - falha (exit != 0) se algum dump estiver vazio/minusculo; grava last_ok.json so quando tudo deu certo.
#
# Variaveis opcionais: BACKUP_TAG (padrao: daily), COLD_PGDATA (diretorio de dados de um Postgres PARADO a copiar a frio),
#                      MIN_DUMP_BYTES (padrao 2000), EXTRA_PATHS (lista separada por espaco).
set -euo pipefail

BASE=/opt/platform
SEC="$BASE/secrets"
OUT="$BASE/data/backups"
TAG="${BACKUP_TAG:-daily}"
MIN_DUMP_BYTES="${MIN_DUMP_BYTES:-2000}"
PG_INCLUDE='^(postgres|matrix-postgres|canais-matrix-postgres|evolution-pg-.*)$'
# bancos grandes e reconstruiveis a partir da fonte: nao entram no dump logico diario (pncp = 15 GB, embeddings/OBTs do PNCP e SIOPE)
SKIP_DBS="${BACKUP_SKIP_DBS:-pncp}"

# guarda de host: so roda na VPS Contabo da Rangel Tech (nunca em outra maquina)
[ "$(hostname)" = "vmi3468840" ] || { echo "host inesperado: $(hostname) - abortando" >&2; exit 2; }

set -a; . "$SEC/restic.env"; set +a
export RCLONE_CONFIG="$SEC/rclone.conf"
# lock orfao (processo que morreu no meio) bloqueia forget/check e derrubava o backup todo dia; `unlock` so remove lock vencido
restic unlock >/dev/null 2>&1 || true

TS="$(date +%Y%m%d-%H%M%S)"
STAGE="$OUT/staging/$TS"
mkdir -p "$STAGE/pg"
fail=0
# registra a falha (sem segredo) para o alerta; last_ok.json so e escrito no fim com sucesso
on_exit() {
  rc=$?
  [ "$rc" -ne 0 ] && printf '{"ok":false,"tag":"%s","finished_at":"%s","reason":"exit %s"}\n' "$TAG" "$(date -Is)" "$rc" > "$OUT/last_fail.json"
  rm -rf "$STAGE"
}
trap on_exit EXIT

echo "==> [$TS] dumps dos Postgres ($TAG)"
for c in $(docker ps --format '{{.Names}}' | grep -E "$PG_INCLUDE" || true); do
  user="$(docker exec "$c" printenv POSTGRES_USER 2>/dev/null || true)"; user="${user:-postgres}"
  dbs="$(docker exec "$c" psql -U "$user" -d postgres -Atc "select datname from pg_database where not datistemplate and datname<>'postgres'" 2>/dev/null || true)"
  if [ -z "$dbs" ]; then echo "AVISO: $c sem bancos listados"; fail=1; continue; fi
  for db in $dbs; do
    case " $SKIP_DBS " in *" $db "*) echo "skip $c/$db (BACKUP_SKIP_DBS)"; continue;; esac
    f="$STAGE/pg/$c.$db.dump"
    if docker exec "$c" pg_dump -U "$user" -Fc "$db" > "$f" 2>"$f.err"; then
      sz="$(stat -c %s "$f")"
      nt="$(docker exec "$c" psql -U "$user" -d "$db" -Atc "select count(*) from pg_tables where schemaname not in ('pg_catalog','information_schema')" 2>/dev/null || echo 1)"
      if [ "$nt" = "0" ]; then echo "ok  $c/$db ${sz}B (banco vazio)"
      elif [ "$sz" -lt "$MIN_DUMP_BYTES" ]; then echo "FALHA: dump pequeno demais ($sz B): $c/$db"; fail=1; else echo "ok  $c/$db ${sz}B"; fi
      rm -f "$f.err"
    else
      echo "FALHA: pg_dump $c/$db: $(head -c 200 "$f.err")"; fail=1
    fi
  done
done

echo "==> copias consistentes dos SQLite (API de backup do SQLite; nunca copia de arquivo com banco aberto)"
mkdir -p "$STAGE/sqlite"
if ! python3 - "$STAGE/sqlite" <<'PY'
import glob, os, sqlite3, sys
saida = sys.argv[1]
alvos = ["/var/lib/docker/volumes/aluno_aluno-data/_data/aluno.db", "/opt/rag-chat/data/index.db", "/opt/portfolio-feedback/data/feedback.db",
         "/opt/platform/data/llm-access/access.db"]  # painel da LLM: chaves, limites, sessoes e uso
alvos += glob.glob("/var/lib/docker/volumes/kernel-harness_home2/_data/**/*.db", recursive=True)
alvos += glob.glob("/var/lib/docker/volumes/kernel-harness_profiles/_data/*/state.db")
falhas = n = 0
for src in alvos:
    if not os.path.isfile(src) or os.path.getsize(src) < 4096:
        continue
    dst = os.path.join(saida, src.strip("/").replace("/", "__"))
    try:
        a = sqlite3.connect(f"file:{src}?mode=ro", uri=True, timeout=30)
        b = sqlite3.connect(dst)
        a.backup(b)
        b.close(); a.close()
        n += 1
    except Exception as e:  # noqa: BLE001
        falhas += 1
        print(f"FALHA sqlite {src}: {e}")
print(f"ok  {n} bancos SQLite copiados, {falhas} falha(s)")
sys.exit(1 if falhas else 0)
PY
then fail=1; fi

PATHS=(
  "$STAGE"
  "$BASE/compose" "$BASE/configs" "$BASE/scripts" "$BASE/apps" "$BASE/sites" "$BASE/services.json" "$SEC"
  "$BASE/chatwoot" "$BASE/data/traefik" "$BASE/data/minio" "$BASE/data/synapse"
  "$BASE/data/mautrix-meta-facebook" "$BASE/data/mautrix-meta-instagram"
  "$BASE/data/canais/synapse" "$BASE/data/canais/mautrix-meta" "$BASE/data/canais/mautrix-instagram" "$BASE/data/canais/mautrix-whatsapp" "$BASE/data/canais/tiktok-sessions" "$BASE/data/canais/tiktok-sessions-gw" "$BASE/stacks/canais"
  "$BASE/data/infisical-redis" "$BASE/data/redis" "$BASE/data/redis-chatwoot" "$BASE/data/uptime-kuma"
  /opt/airflow-infra /opt/airflow /var/lib/docker/volumes/airflow_airflow-state/_data
  /opt/platform/stacks /opt/platform/releases /opt/platform/data/ninerouter /opt/platform/data/llm-gateway /opt/platform/data/redis/users.acl /opt/portfolio-feedback/data
  /etc/cron.d/platform-backups /etc/systemd/system/rt-backup.service /etc/systemd/system/rt-backup.timer
  # agentes por skills (spec 04/10): perfis Hermes (state.db), skills da empresa/usuario, estado do runtime-manager e workspaces das empresas
  /var/lib/docker/volumes/kernel-harness_profiles /var/lib/docker/volumes/kernel-harness_users /var/lib/docker/volumes/kernel-harness_tenant_skills
  /var/lib/docker/volumes/runtime-manager_rmdata /var/lib/docker/volumes/runtime-manager_edge-dynamic /opt/platform/data/traefik-dynamic /srv/rt/tenants /srv/rt/hermes
  /etc/systemd/system/rt-compose-healer.service /etc/systemd/system/rt-compose-healer.timer
)
[ -n "${COLD_PGDATA:-}" ] && PATHS+=("$COLD_PGDATA")
# shellcheck disable=SC2206
[ -n "${EXTRA_PATHS:-}" ] && PATHS+=($EXTRA_PATHS)
EXISTING=(); for p in "${PATHS[@]}"; do [ -e "$p" ] && EXISTING+=("$p"); done

echo "==> restic backup (${#EXISTING[@]} caminhos, tag $TAG)"
restic backup --tag "$TAG" --host rt-vps --exclude '**/node_modules' --exclude '**/.cache' \
  --exclude "$BASE/data/prometheus" --exclude "$BASE/data/loki" --exclude "$BASE/data/code-server" "${EXISTING[@]}" | tail -6

if [ "$fail" -ne 0 ]; then echo "BACKUP COM FALHA: veja as linhas FALHA/AVISO acima" >&2; exit 1; fi

restic forget --tag "$TAG" --host rt-vps --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune | tail -2
restic check --read-data-subset=2% | tail -2

snap="$(restic snapshots --tag "$TAG" --host rt-vps --latest 1 --json | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d[-1]["short_id"] if d else "")')"
printf '{"ok":true,"tag":"%s","snapshot":"%s","finished_at":"%s","dumps":%s}\n' "$TAG" "$snap" "$(date -Is)" "$(ls "$STAGE/pg" | wc -l)" > "$OUT/last_ok.json"
rm -f "$OUT/last_fail.json"
echo "==> OK snapshot $snap"
