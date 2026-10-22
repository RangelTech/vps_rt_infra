# vps_rt_infra

A infraestrutura da VPS da empresa: Terraform, Compose, releases por digest, deploy, backup e scripts do host. Atende o Luar e outros projetos, por isso o nome não leva o prefixo `luar_`. É o único repositório com credencial da VPS e o único que implanta.

## Onde ele se encaixa

```
                    Cliente (navegador e canais)
                                |
                        Traefik (VPS)
                                |
 luar_chatwoot --contexto assinado--> luar_engine --runs--> luar_harness
 (telas, inbox, Kanban,               (motor de IA:         (fila, broker,
  bridge, gateway de canais)           templates, skills,    workers Hermes)
                                       credenciais, uso)            |
                                            |                luar_workspaces
                                       luar_ai_gateway       (ambiente de cada
                                       (LLM multi-tenant)     empresa)

 vps_rt_infra: compose, releases por digest, deploy e backup (só ela implanta)
 airflow:      orquestração da empresa, inclui o backup noturno da VPS
 luar_docs:    specs, evidências e ADRs
```

## Árvore de pastas

```
terraform/   DNS e recursos declarados
stacks/      um compose por serviço (platform, chatwoot, agent-platform, kernel-harness, ...)
releases/    sources.json e <servico>.lock: repositório, versão, digest e sha256 do artefato
scripts/     deploy.sh, release_intake.py, backup.sh, restore-verify.sh, healthcheck.sh, qa/
configs/     Traefik, Prometheus, Loki e Grafana
cloud-init/  bootstrap do host
sites/       sites estáticos de clientes
docs/        runbooks (SSH, incidentes) e o manual operacional de cada serviço da VPS
.github/     workflows de deploy e de intake de release
```

## Como um serviço chega à produção

1. O repositório do serviço publica a release (imagem e manifesto).
2. `release_intake.py` fixa o digest em `releases/<servico>.lock`.
3. `deploy.sh` troca o container, espera o healthcheck e reverte se falhar.

Nunca troque um container na mão: só por release e lock.

## Segurança

O repositório é público: sem segredos, `.env` ou chaves, e IPs só quando indispensáveis. Os segredos de runtime ficam em `/opt/platform/secrets`, na VPS.

## Contratos

- `releases/sources.json`: lista fechada de repositórios e serviços que o intake aceita (`repo`, serviço, nome do artefato). Fonte fora da lista é rejeitada.
- `releases/<servico>.lock`: `repo=`, versão, `artifact_url`, `sha256` do artefato e o digest da imagem. O deploy só usa o que está no lock.
- Manifesto de release (publicado pelo repositório do serviço): imagem, memória, CPU, passo `pre-deploy` opcional (por exemplo migration).

## Variáveis e segredos

Só os nomes ficam em `.env.example`. Os valores vivem em `/opt/platform/secrets` na VPS e no Infisical. Os workflows usam os secrets do GitHub do repositório; revise-os a cada rodízio de credencial.

## Como rodar e testar

- Local: `shellcheck scripts/*.sh` e `terraform -chdir=terraform validate`. O CI (`ci.yml`) repete as duas checagens.
- Teste de restauração: `scripts/restore-verify.sh` (o workflow `backup-verify.yml` roda toda semana).
- Mudança de stack: PR, CI verde, o captain faz merge e o `deploy.yml` aplica com o host fixado.

## Runbooks e decisões

- [`docs/runbooks/ssh-recovery.md`](docs/runbooks/ssh-recovery.md): recuperar o acesso SSH ao host.
- [`docs/runbooks/incidente-2026-09-29-postgres-tls-key.md`](docs/runbooks/incidente-2026-09-29-postgres-tls-key.md): incidente da chave TLS do Postgres e o que mudou depois.
- [`docs/manual-operacional.md`](docs/manual-operacional.md): serviço por serviço (Traefik, Postgres, Redis, MinIO, Grafana, backups, workflows). Escrito antes do modelo de releases por digest: confirme o estado atual no compose antes de seguir.
- Decisões de arquitetura: `luar_docs` (spec 10, §0.8 e Fase R).

## Como contribuir

Uma branch por tarefa, Conventional Commits em português, CI verde. Nunca implante na mão: só por release e lock. Não commite segredo, `.env` nem chave.
