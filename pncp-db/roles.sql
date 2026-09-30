-- Run once as the owner. Passwords come from psql variables (-v), never from this file.
REVOKE ALL ON DATABASE pncp FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
CREATE SCHEMA IF NOT EXISTS pncp AUTHORIZATION pncp_owner;

CREATE ROLE rag_reader LOGIN PASSWORD :'rag_pw' CONNECTION LIMIT 10;
CREATE ROLE bi_reader LOGIN PASSWORD :'bi_pw' CONNECTION LIMIT 12;
CREATE ROLE public_reader LOGIN PASSWORD :'public_pw' CONNECTION LIMIT 8;
ALTER ROLE public_reader SET statement_timeout = '20s';
ALTER ROLE public_reader SET work_mem = '8MB';
ALTER ROLE public_reader SET idle_in_transaction_session_timeout = '30s';
ALTER ROLE rag_reader SET statement_timeout = '15s';
ALTER ROLE bi_reader SET statement_timeout = '60s';
GRANT CONNECT ON DATABASE pncp TO rag_reader, bi_reader, public_reader;
GRANT USAGE ON SCHEMA pncp TO rag_reader, bi_reader, public_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE pncp_owner IN SCHEMA pncp GRANT SELECT ON TABLES TO rag_reader, bi_reader, public_reader;
