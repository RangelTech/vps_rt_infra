# Incidente 29/09/2026 — Postgres de produção fora do ar desde 25/09

## O que aconteceu

O container `postgres` (serviço real por trás de `postgres-direct`/porta 5433 e
do `pgbouncer`) estava em **crash-loop desde 2026-09-25 14:23** e acabou
`Exited (1)`, sem reiniciar sozinho. Isso derrubava **qualquer rota do
`agent-llm-backend` que tocasse banco** (login, chat, tudo) — não só Hermes.
`GET /api/health` continuava 200 (não toca banco), o que escondeu o problema.

## Causa raiz

```
FATAL: private key file "/etc/postgres-tls/server.key" must be owned by the
database user or root
```

`/opt/platform/configs/postgres-tls/server.key` estava com dono `deploy`
(usuário do host), não `999`/`postgres` (uid dentro do container) nem root.
O Postgres 16 recusa subir com TLS se a chave não pertencer ao usuário do
banco ou a root — não achei o que mudou exatamente em 25/09 pra essa checagem
passar a falhar (o arquivo é de 31/07), mas essa é a causa direta.

## Como achei

Testando o deploy do Hermes Fase A em produção: `POST /api/auth/login`
(rota pré-existente, nada a ver com Hermes) voltava 500. Log do Cloud Run
mostrou `psycopg.OperationalError: ... SSL error: unexpected eof while
reading` pra `66.94.101.153:5433`. SSH na VPS → `docker ps -a` → container
`postgres` real (não confundir com `matrix-postgres`/`infisical-postgres`)
`Exited (1) 3 days ago`.

## Fix aplicado (ao vivo, já em produção)

```bash
chown 999:999 /opt/platform/configs/postgres-tls/server.key
chmod 600 /opt/platform/configs/postgres-tls/server.key
docker start postgres
```

Confirmado saudável (`docker ps` → `healthy`). Forcei um novo deploy do
`agent-llm-backend` (mesma imagem, `gcloud run deploy --image=...`) pra
rodar as migrations que tinham falhado nesse intervalo — confirmei
`schema_migrations` e as 9 tabelas `hermes_*` presentes depois.

## Pendências desta descoberta (não resolvidas nesta sessão)

- **Por que ninguém percebeu em 4 dias**: não há alerta de "Postgres
  indisponível" nem healthcheck de produção que realmente toque o banco
  (o próprio `/api/health` não pega isso). A spec do Hermes já pede
  isso pra si mesma (seção 12: "alertas para Relay indisponível...");
  vale um alerta equivalente pro Postgres real da VPS também — ideal:
  Uptime Kuma (já rodando na VPS) monitorando uma rota que force um
  round-trip de banco, não só `/api/health`.
- **Por que a chave ficou com dono errado**: não investiguei se algo
  reescreveu o arquivo (ex.: um `docker compose up` recriando o volume,
  um provisionamento futuro) ou se sempre esteve assim e uma versão nova
  da imagem `pgvector/pgvector:pg16` passou a checar isso. Vale
  documentar/automatizar o `chown` certo em qualquer processo que
  (re)gere esse arquivo.

## Contexto relacionado

Esta VM/VPS também ganhou nesta mesma sessão o serviço `hermes-relay`
(SPEC_HERMES_INTEGRADO_RIA_ATENDIMENTO.md, Fase B, slice 1) — ver
`apps/hermes-relay/` e o bloco novo em `compose/docker-compose.yml`.
