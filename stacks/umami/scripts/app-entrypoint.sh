#!/bin/sh
# Umami. Le a senha do banco e o APP_SECRET do volume de segredos e entrega o resto ao comando original da imagem.
set -e
i=0; while [ ! -s /secrets/env ] && [ "$i" -lt 60 ]; do i=$((i+1)); sleep 2; done
[ -s /secrets/env ] || { echo "segredos ausentes em /secrets/env (suba o umami-db primeiro)" >&2; exit 1; }
# shellcheck disable=SC1091
. /secrets/env
export DATABASE_URL="postgresql://umami:${DB_PASS}@umami-db:5432/umami"
export APP_SECRET
exec "$@"
