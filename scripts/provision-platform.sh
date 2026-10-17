#!/usr/bin/env bash
# Provisiona dados e segredos de runtime da plataforma (spec 03 §5). Roda NA VPS, como root. Idempotente: nunca troca
# um segredo que ja existe; so gera o que falta. NAO imprime valores de segredo (so nomes/estados).
#   - roles do Postgres (agent_llm_app, chatwoot_app, bridge_app, litellm_app): usa a senha existente nos .env legados; se nao houver, gera;
#   - usuarios ACL do Redis (chatwoot db1, litellm db2): gera e grava em /opt/platform/data/redis/users.acl (recarrega com ACL LOAD);
#   - MinIO: bucket chatwoot + usuario de servico com policy so nesse bucket;
#   - arquivos /opt/platform/secrets/<servico>.env (0600).
set -euo pipefail
[ "$(hostname)" = "vmi3468840" ] || { echo "host inesperado" >&2; exit 2; }
SEC=/opt/platform/secrets
CPE=/opt/platform/compose/.env
LEG_AGENT=/opt/platform/agentllm/infra/.env.prod
LEG_CW=/opt/platform/chatwoot/infra/.env.prod.chatwoot
mkdir -p "$SEC"; chmod 700 "$SEC"

ev() { grep -m1 "^$2=" "$1" 2>/dev/null | cut -d= -f2- | sed -E "s/^[\"']//; s/[\"']$//"; }
gen() { head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c "${1:-32}"; }
have() { [ -s "$1" ] && grep -Eq "^$2=.+" "$1"; }
setv() { # arquivo chave valor  (so grava se ainda nao existir)
  have "$1" "$2" && return 0
  printf '%s=%s\n' "$2" "$3" >> "$1"
}
PGU="$(ev $CPE POSTGRES_ADMIN_USER)"
psqlm() { docker exec -i postgres psql -v ON_ERROR_STOP=1 -U "$PGU" -d postgres "$@"; }
role_pw() { # role senha -> ALTER ROLE (senha via variavel psql, nunca na linha de comando)
  echo "ALTER ROLE $1 LOGIN PASSWORD :'pw';" | psqlm -q -v pw="$2"
}

echo "== Postgres: senhas das roles"
AGENT_DB_URL="$(ev $LEG_AGENT DATABASE_URL)"
AGENT_PW="$(echo "$AGENT_DB_URL" | sed -E 's#^[a-z]+://[^:]+:([^@]+)@.*#\1#')"
CW_PW="$(ev $LEG_CW POSTGRES_PASSWORD)"
[ -n "$AGENT_PW" ] && [ -n "$CW_PW" ] || { echo "senhas legadas nao encontradas" >&2; exit 3; }
BRIDGE_PW_FILE="$SEC/.bridge_app.pw"; [ -s "$BRIDGE_PW_FILE" ] || { gen 32 > "$BRIDGE_PW_FILE"; chmod 600 "$BRIDGE_PW_FILE"; role_pw bridge_app "$(cat "$BRIDGE_PW_FILE")"; }
LITELLM_PW_FILE="$SEC/.litellm_app.pw"; [ -s "$LITELLM_PW_FILE" ] || { gen 32 > "$LITELLM_PW_FILE"; chmod 600 "$LITELLM_PW_FILE"; role_pw litellm_app "$(cat "$LITELLM_PW_FILE")"; }
for pair in "agent_llm:agent_llm_app" "chatwoot_prod:chatwoot_app" "chatwoot_bridge:bridge_app" "litellm:litellm_app"; do
  db="${pair%%:*}"; r="${pair##*:}"
  psqlm -q -c "GRANT ALL PRIVILEGES ON DATABASE $db TO $r;"
  docker exec -i postgres psql -v ON_ERROR_STOP=1 -U "$PGU" -d "$db" -q -c "GRANT ALL ON SCHEMA public TO $r; ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $r; ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $r;"
done

echo "== Redis: usuarios ACL (chatwoot db1, litellm db2)"
ACL=/opt/platform/data/redis/users.acl
sha() { printf '%s' "$1" | sha256sum | cut -d' ' -f1; }
for u in chatwoot litellm; do
  f="$SEC/.redis_$u.pw"
  if [ ! -s "$f" ]; then gen 32 > "$f"; chmod 600 "$f"; fi
  if ! grep -q "^user $u " "$ACL"; then
    printf 'user %s on #%s ~* &* +@all -flushall -flushdb -shutdown -acl\n' "$u" "$(sha "$(cat "$f")")" >> "$ACL"
  fi
done
RPW="$(ev $CPE REDIS_PASSWORD)"
docker exec redis redis-cli --user default --pass "$RPW" --no-auth-warning ACL LOAD

echo "== MinIO: bucket chatwoot + usuario de servico"
# credenciais reais do container (o .env pode ter caracteres que o compose interpreta)
MROOT="$(docker exec minio printenv MINIO_ROOT_USER)"; MPW="$(docker exec minio printenv MINIO_ROOT_PASSWORD)"
MCF="$SEC/.minio_chatwoot.keys"
if [ ! -s "$MCF" ]; then printf 'chatwoot-svc\n%s\n' "$(gen 40)" > "$MCF"; chmod 600 "$MCF"; fi
MUSER="$(sed -n 1p "$MCF")"; MKEY="$(sed -n 2p "$MCF")"
docker run --rm --network internal --entrypoint sh -e MR="$MROOT" -e MP="$MPW" -e MU="$MUSER" -e MK="$MKEY" minio/mc:latest -c '
  mc alias set l http://minio:9000 "$MR" "$MP" >/dev/null &&
  mc mb --ignore-existing l/chatwoot >/dev/null &&
  printf "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"s3:*\"],\"Resource\":[\"arn:aws:s3:::chatwoot\",\"arn:aws:s3:::chatwoot/*\"]}]}" > /tmp/p.json &&
  (mc admin policy create l chatwoot-rw /tmp/p.json >/dev/null 2>&1 || mc admin policy create l chatwoot-rw /tmp/p.json) ;
  (mc admin user info l "$MU" >/dev/null 2>&1 || mc admin user add l "$MU" "$MK" >/dev/null) &&
  mc admin policy attach l chatwoot-rw --user "$MU" >/dev/null 2>&1; echo minio_ok'

echo "== env: agent-platform-backend"
F="$SEC/agent-platform-backend.env"; touch "$F"; chmod 600 "$F"
setv "$F" DATABASE_URL "$AGENT_DB_URL"
setv "$F" PORT 8090
setv "$F" KERNEL_URL "http://kernel-llm:8080"
setv "$F" KERNEL_AUDIENCE ""
setv "$F" KERNEL_INTERNAL_TOKEN "$(ev $LEG_AGENT KERNEL_INTERNAL_TOKEN)"
setv "$F" PUBLIC_BASE_URL "https://ia.rangeltech.net"
setv "$F" BRIDGE_URL "http://chatwoot-bridge:8100"
setv "$F" BRIDGE_ADMIN_TOKEN "$(ev $LEG_AGENT BRIDGE_ADMIN_TOKEN)"
for k in STORAGE_BACKEND S3_ENDPOINT_URL S3_REGION S3_BUCKET S3_ACCESS_KEY_ID S3_SECRET_ACCESS_KEY S3_PREFIX S3_PUBLIC_BASE_URL ENCRYPTION_KEY; do setv "$F" "$k" "$(ev $LEG_AGENT $k)"; done
setv "$F" MASTER_EMAIL "master@rangeltech.net"
setv "$F" MASTER_PASSWORD "$(gen 24)"
setv "$F" AWS_REQUEST_CHECKSUM_CALCULATION "when_required"
setv "$F" AWS_RESPONSE_CHECKSUM_VALIDATION "when_required"

echo "== env: kernel-llm"
F="$SEC/kernel-llm.env"; touch "$F"; chmod 600 "$F"
setv "$F" DATABASE_URL "$AGENT_DB_URL"
setv "$F" INTERNAL_TOKEN "$(ev $LEG_AGENT KERNEL_INTERNAL_TOKEN)"
setv "$F" PLATFORM_BACKEND_URL "http://agent-platform-backend:8090"
setv "$F" ENABLE_STUB_CONTROL "false"
for k in STORAGE_BACKEND S3_ENDPOINT_URL S3_REGION S3_BUCKET S3_ACCESS_KEY_ID S3_SECRET_ACCESS_KEY S3_PREFIX S3_PUBLIC_BASE_URL; do setv "$F" "$k" "$(ev $LEG_AGENT $k)"; done

echo "== env: litellm"
F="$SEC/litellm.env"; touch "$F"; chmod 600 "$F"
setv "$F" DATABASE_URL "postgresql://litellm_app:$(cat "$LITELLM_PW_FILE")@postgres:5432/litellm"
setv "$F" REDIS_URL "redis://litellm:$(cat "$SEC/.redis_litellm.pw")@redis:6379/2"
setv "$F" LITELLM_MASTER_KEY "sk-$(gen 40)"
setv "$F" LITELLM_SALT_KEY "sk-$(gen 40)"
setv "$F" STORE_MODEL_IN_DB "True"

echo "== env: chatwoot-rails"
F="$SEC/chatwoot-rails.env"; touch "$F"; chmod 600 "$F"
for k in RAILS_ENV NODE_ENV INSTALLATION_ENV RAILS_LOG_TO_STDOUT POSTGRES_HOST POSTGRES_PORT POSTGRES_DATABASE POSTGRES_USERNAME POSTGRES_PASSWORD SECRET_KEY_BASE FRONTEND_URL ENABLE_ACCOUNT_SIGNUP DEFAULT_LOCALE FB_APP_ID FB_APP_SECRET FB_VERIFY_TOKEN INSTAGRAM_APP_ID INSTAGRAM_APP_SECRET INSTAGRAM_VERIFY_TOKEN IG_VERIFY_TOKEN WHATSAPP_APP_ID WHATSAPP_APP_SECRET WHATSAPP_CONFIGURATION_ID TIKTOK_APP_ID TIKTOK_APP_SECRET BRIDGE_ADMIN_TOKEN; do
  v="$(ev $LEG_CW $k)"; [ -n "$v" ] && setv "$F" "$k" "$v" || true
done
setv "$F" REDIS_URL "redis://chatwoot:$(cat "$SEC/.redis_chatwoot.pw")@redis:6379/1"
setv "$F" FORCE_SSL "true"
setv "$F" ACTIVE_STORAGE_SERVICE "s3_compatible"
setv "$F" STORAGE_BUCKET_NAME "chatwoot"
setv "$F" STORAGE_REGION "us-east-1"
setv "$F" STORAGE_ENDPOINT "http://minio:9000"
setv "$F" STORAGE_FORCE_PATH_STYLE "true"
setv "$F" STORAGE_ACCESS_KEY_ID "$MUSER"
setv "$F" STORAGE_SECRET_ACCESS_KEY "$MKEY"
setv "$F" AWS_REQUEST_CHECKSUM_CALCULATION "when_required"
setv "$F" AWS_RESPONSE_CHECKSUM_VALIDATION "when_required"
setv "$F" BRIDGE_URL "http://chatwoot-bridge:8100"

echo "== env: chatwoot-bridge"
F="$SEC/chatwoot-bridge.env"; touch "$F"; chmod 600 "$F"
setv "$F" DATABASE_URL "postgresql://bridge_app:$(cat "$BRIDGE_PW_FILE")@postgres:5432/chatwoot_bridge"
setv "$F" PORT 8100
setv "$F" ENVIRONMENT production
setv "$F" ENCRYPTION_KEY "$(python3 -c 'import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
setv "$F" BRIDGE_ADMIN_TOKEN "$(ev $LEG_CW BRIDGE_ADMIN_TOKEN)"
setv "$F" BRIDGE_PUBLIC_URL "https://bridge.rangeltech.net"
setv "$F" CHATWOOT_BASE_URL "https://chat.rangeltech.net"
PT="$(docker exec postgres psql -U "$PGU" -d chatwoot_prod -Atc "select token from access_tokens where owner_type='PlatformApp' limit 1")"
setv "$F" CHATWOOT_PLATFORM_TOKEN "$PT"
setv "$F" AGENT_PLATFORM_URL "http://agent-platform-backend:8090"

chmod 600 "$SEC"/*.env
echo "== resumo (so nomes de variaveis presentes por arquivo)"
for f in "$SEC"/agent-platform-backend.env "$SEC"/kernel-llm.env "$SEC"/litellm.env "$SEC"/chatwoot-rails.env "$SEC"/chatwoot-bridge.env; do
  echo "$(basename "$f"): $(grep -Ec '^[A-Z0-9_]+=.+' "$f") preenchidas, vazias: $(grep -E '^[A-Z0-9_]+=$' "$f" | cut -d= -f1 | tr '\n' ' ')"
done
