#!/bin/sh
# Postgres do Umami. Na 1a subida gera a senha do banco e o APP_SECRET no volume de segredos (nunca no Git).
set -e
mkdir -p /secrets
if [ ! -s /secrets/env ]; then
  umask 077
  DB_PASS="$(head -c 96 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 32)"
  APP_SECRET="$(head -c 96 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 48)"
  printf 'DB_PASS=%s\nAPP_SECRET=%s\n' "$DB_PASS" "$APP_SECRET" > /secrets/env
  chmod 644 /secrets/env   # volume interno; o app (usuario nao root) precisa ler
fi
# shellcheck disable=SC1091
. /secrets/env
export POSTGRES_USER=umami POSTGRES_DB=umami POSTGRES_PASSWORD="$DB_PASS"
exec docker-entrypoint.sh postgres
