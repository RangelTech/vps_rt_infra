# stacks/platform

Espelho versionado do que roda em `/opt/platform` na VPS (compose + configs sem segredos). Segredos ficam em
`/opt/platform/compose/.env` (nomes em `.env.example`) e em `/opt/platform/secrets`. Postgres e Redis unicos da
plataforma; rede `dbnet` liga o Postgres aos servicos que precisam dele (Metabase, RAG, Airflow).
Nao versionados de proposito: `configs/postgres-tls/` (chave privada), `configs/synapse/homeserver.yaml` (senha do banco).
Aplicar: copiar para `/opt/platform/compose/` e `docker compose -p compose up -d --no-build --pull never <servico>` (nunca --remove-orphans).
