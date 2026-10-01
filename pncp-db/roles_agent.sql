-- Run after the analytical schemas exist. Read-only role for the SQL agent, limited to the allow-listed schemas.
CREATE ROLE sql_agent LOGIN PASSWORD :'agent_pw' CONNECTION LIMIT 6;
ALTER ROLE sql_agent SET statement_timeout = '10s';
ALTER ROLE sql_agent SET default_transaction_read_only = on;
ALTER ROLE sql_agent SET work_mem = '16MB';
GRANT CONNECT ON DATABASE pncp TO sql_agent;
DO $$
DECLARE s text;
BEGIN
  FOREACH s IN ARRAY ARRAY['pncp', 'siope', 'ibge'] LOOP
    IF EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = s) THEN
      EXECUTE format('GRANT USAGE ON SCHEMA %I TO sql_agent, rag_reader, bi_reader, public_reader', s);
      EXECUTE format('GRANT SELECT ON ALL TABLES IN SCHEMA %I TO sql_agent, bi_reader, public_reader', s);
      EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE pncp_owner IN SCHEMA %I GRANT SELECT ON TABLES TO sql_agent, rag_reader, bi_reader, public_reader', s);
    END IF;
  END LOOP;
END $$;

-- The pgvector types and operators live in schema public; read roles need to see them for halfvec queries.
GRANT USAGE ON SCHEMA public TO sql_agent, rag_reader, bi_reader, public_reader;
