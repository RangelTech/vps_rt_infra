#!/bin/sh
# Provisiona o Umami uma unica vez, direto no banco: senha do administrador (so o hash bcrypt esta versionado) e os sites.
set -e
i=0; while [ ! -s /secrets/env ] && [ "$i" -lt 90 ]; do i=$((i+1)); sleep 2; done
# shellcheck disable=SC1091
. /secrets/env
export PGPASSWORD="$DB_PASS"
PSQL="psql -h umami-db -U umami -d umami -v ON_ERROR_STOP=1 -X -q"

if [ ! -f /secrets/provisionado ]; then
  echo "aguardando o Umami criar as tabelas..."
  n=0
  until [ "$($PSQL -tA -c "select count(*) from \"user\" where username='admin'" 2>/dev/null || echo 0)" = "1" ]; do
    n=$((n+1)); [ "$n" -gt 180 ] && { echo "tabelas nao apareceram em 15 min" >&2; exit 1; }
    sleep 5
  done
  HASH="$(cat /stack/admin.hash)"
  # o psql so interpola :'variavel' quando o SQL vem pela entrada padrao (nao com -c)
  printf '%s
' "UPDATE \"user\" SET password = :'h' WHERE username = 'admin';" | $PSQL -v h="$HASH"
  while IFS="$(printf '	')" read -r wid nome dominio; do
    [ -n "$wid" ] || continue
    printf '%s
' "INSERT INTO website (website_id, name, domain, user_id) SELECT :'wid'::uuid, :'nome', :'dom', user_id FROM \"user\" WHERE username = 'admin' ON CONFLICT (website_id) DO NOTHING;" | $PSQL -v wid="$wid" -v nome="$nome" -v dom="$dominio"
  done < /stack/sites.tsv
  touch /secrets/provisionado
  echo "provisionado"
fi
touch /tmp/provisionado
exec tail -f /dev/null
