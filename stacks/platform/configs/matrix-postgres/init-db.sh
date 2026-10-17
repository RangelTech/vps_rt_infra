#!/bin/bash
# correcao-01-execucao-completa.md secao 4 -- Synapse EXIGE collation 'C'
# no Postgres (achado real, ver memoria.md 28/08/2026: falha com
# IncorrectDatabaseSetup contra o locale padrão en_US.utf8 do container
# oficial). POSTGRES_DB do compose fica só "postgres" (admin connection);
# os 3 bancos de verdade são criados aqui, explicitamente em locale C.
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
  CREATE DATABASE synapse OWNER $POSTGRES_USER
    ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C' TEMPLATE template0;
  CREATE DATABASE mautrix_meta_facebook OWNER $POSTGRES_USER
    ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C' TEMPLATE template0;
  CREATE DATABASE mautrix_meta_instagram OWNER $POSTGRES_USER
    ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C' TEMPLATE template0;
EOSQL
