# memoria.md — vps_rt_infra

> Documento de continuidade entre chats. Se você é uma nova instância do Claude/Roo assumindo este projeto, leia este arquivo inteiro antes de fazer qualquer coisa. Ele reflete o estado real do repositório, as decisões já tomadas e o que falta fazer.

Última atualização: 2026-08-17.

## 1. O que é este projeto

`vps_rt_infra` é o repositório de Infraestrutura como Código (Terraform + Docker Compose + GitHub Actions) que sobe **toda a camada VPS pessoal** do usuário (Lucas Rangel) em uma VPS Contabo, usando o domínio `rangeltech.net` (registrado na Hostinger).

Este repositório **substitui completamente** a parte "VPS" da arquitetura descrita em [`../arquitetura_saas_koyeb_vps_iac.md`](../arquitetura_saas_koyeb_vps_iac.md:1) — ele não depende de Koyeb. A VPS sobe: banco de dados, storage, observabilidade, IDE web, utilitário `9router` e backups.

Repositório GitHub: `LucasRangelSSouza/vps_rt_infra` (branch `main`), push feito via PAT em [`secrets/github-dev.md`](../secrets/github-dev.md:1).

O fluxo operacional pretendido (e já implementado) é:

1. editar uma variável/versão/arquivo de config no repo;
2. commit + push para `main` (ou disparar manualmente);
3. o workflow [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:1) roda `terraform apply` sozinho;
4. o Terraform renderiza `compose/.env`, sincroniza arquivos via SSH para a VPS e roda `docker compose up -d`.

Nenhuma edição manual deve ser feita direto na VPS — tudo deve fluir por este repo.

## 2. Infraestrutura física / credenciais de acesso

- **VPS**: Contabo Cloud VPS 6 (2026), IPv4 `66.94.101.153`, IPv6 subnet `2605:a144:2346:8840:0000:0000:0000:0001/64`, localização Carlstadt (US-east).
  - Credenciais originais (root/senha) em [`../secrets/contabo-vps.json`](../secrets/contabo-vps.json:1) — **fora do repo git**, só local.
  - Após o primeiro bootstrap, o acesso passa a ser via usuário `deploy` + chave SSH dedicada.
- **Chave SSH dedicada** (v2, atual): pública/privada em `C:/Users/lucas.rangel/.ssh/vps_rt_infra_ed25519_v2[.pub]`. Referenciada em [`terraform/variables.tf`](terraform/variables.tf:51) como default de `ssh_private_key_path`.
- **DNS**: Hostinger, domínio `rangeltech.net`. API key em [`../secrets/api_key_hostinger.json`](../secrets/api_key_hostinger.json:1) (fora do repo).
- **GitHub**: PAT dev em [`../secrets/github-dev.md`](../secrets/github-dev.md:1), usado para criar/gerenciar o repo e subir secrets via API.

## 3. Arquitetura Terraform (como o deploy realmente funciona)

Não há criação de VM via Terraform — a Contabo já entrega a VPS pronta. O Terraform trata a VPS como um alvo existente e faz tudo via provisioners SSH:

- [`terraform/main.tf`](terraform/main.tf:1)
  - `local_file.compose_env`: renderiza `compose/.env` a partir de [`compose/.env.tftpl`](compose/.env.tftpl:1) usando `templatefile()`, injetando todas as versões/credenciais de `variables.tf`.
  - `null_resource.bootstrap`: conecta como `root` (usuário inicial) usando a MESMA chave privada (`ssh_private_key_path`) — a Contabo já foi configurada via painel para aceitar essa chave em `/root/.ssh/authorized_keys`. Sobe e executa [`cloud-init/bootstrap.sh`](cloud-init/bootstrap.sh:1).
  - `null_resource.deploy_stack`: conecta como `deploy_user` (criado pelo bootstrap), sincroniza `compose/`, `configs/`, `apps/`, `scripts/` para `/opt/platform` na VPS, e roda `docker compose build/pull/up -d` + instala cron de backup.
  - `deploy_stack` tem `triggers` com hash sha256 de: docker-compose.yml, .env renderizado, traefik static/dynamic, datasources do grafana (postgres/prometheus/loki), prometheus.yml, loki config.yml, promtail config.yml, Dockerfile do 9route, scripts de backup e healthcheck. Ou seja: mudar qualquer um desses arquivos força um redeploy real no próximo `apply`.
- [`terraform/dns.tf`](terraform/dns.tf:1): gera um JSON de zona (`hostinger-zone.json`) com os registros A abaixo e chama [`scripts/hostinger_dns.sh`](scripts/hostinger_dns.sh:1) via `local-exec` para fazer PUT na API da Hostinger.
- [`terraform/outputs.tf`](terraform/outputs.tf:1): expõe `server_ip`, `root_domain` e o mapa `public_urls` com todos os subdomínios.
- [`terraform/variables.tf`](terraform/variables.tf:1): catálogo central — IP do servidor, domínio, usuário SSH, todas as versões de imagem Docker (edite aqui para fazer upgrade/downgrade de qualquer serviço) e todas as credenciais (marcadas `sensitive`).

### Registros DNS atuais ([`terraform/dns.tf`](terraform/dns.tf:2))

`@`, `9route`, `grafana`, `storage`, `minio-admin`, `pgadmin`, `uptime`, `traefik`, `code`, `prometheus`, `logs` — todos tipo A apontando para `server_ip`, TTL 300.

### URLs públicas ([`terraform/outputs.tf`](terraform/outputs.tf:9))

| Serviço | URL |
|---|---|
| 9router | `https://9route.rangeltech.net` |
| Grafana | `https://grafana.rangeltech.net` |
| MinIO API (storage) | `https://storage.rangeltech.net` |
| MinIO Console | `https://minio-admin.rangeltech.net` |
| pgAdmin | `https://pgadmin.rangeltech.net` |
| Uptime Kuma | `https://uptime.rangeltech.net` |
| Traefik dashboard | `https://traefik.rangeltech.net` |
| VS Code Server | `https://code.rangeltech.net` |
| Prometheus | `https://prometheus.rangeltech.net` |
| Loki | `https://logs.rangeltech.net` |
| PostgreSQL (via PgBouncer) | `pgbouncer:5432` exposto via Traefik TCP router, `HostSNI(*)` na entrypoint `postgres` (porta 5432) |

## 4. Stack Docker Compose ([`compose/docker-compose.yml`](compose/docker-compose.yml:1))

Serviços e papéis:

- **traefik**: reverse proxy/TLS (Let's Encrypt), entrypoints `web`(80), `websecure`(443), `postgres`(5432); dashboard protegido por basic auth.
- **postgres**: banco principal, rede `internal` apenas, healthcheck `pg_isready`.
- **pgbouncer**: pool de conexões, exposto publicamente via TCP router do Traefik (porta 5432) para acesso externo autenticado.
- **redis**: cache/estado, `internal` apenas, senha via `--requirepass`.
- **minio**: object storage S3-compatible, API pública em `storage.*` e console protegido em `minio-admin.*`.
- **pgadmin**: admin do Postgres, protegido por basic auth do Traefik.
- **grafana**: dashboards, login próprio (usuário/senha Grafana), datasources/dashboards provisionados automaticamente (ver seção 5).
- **uptime-kuma**: monitoramento sintético externo.
- **code-server**: VS Code na web, monta `../` (toda a árvore `vps_rt_infra/`) como `/workspace` e o socket Docker, senha própria + senha de sudo.
- **prometheus**: métricas, protegido por basic auth.
- **loki**: logs, protegido por basic auth.
- **promtail**: agente de coleta de logs, `internal` apenas, lê `/var/log` e `/var/lib/docker/containers/*/*-json.log` do host.
- **node-exporter**: métricas do host (`pid: host`, monta `/` como `/host`).
- **cadvisor**: métricas de containers (`privileged: true`).
- **ninerouter (9router)**: build local a partir de [`apps/9route/Dockerfile`](apps/9route/Dockerfile:1), instala o pacote npm `9router@<versão>`, exposto publicamente.

Redes: `internal` (bridge, `internal: true` — sem saída à internet) e `public` (bridge normal, exposta ao Traefik).

Serviços que **não** devem ser expostos diretamente na internet: Postgres (só via PgBouncer+Traefik TCP), Redis, Promtail, node-exporter, cAdvisor.

## 5. Observabilidade (Grafana + Prometheus + Loki) — todo 28, CONCLUÍDO

Estado antes da correção: o datasource Postgres do Grafana usava `${POSTGRES_DB}`/`${POSTGRES_ADMIN_USER}`/`${POSTGRES_ADMIN_PASSWORD}` mas o container `grafana` não recebia essas env vars — a interpolação falhava silenciosamente.

Correções aplicadas:

- [`compose/docker-compose.yml`](compose/docker-compose.yml:148): adicionado `POSTGRES_DB`, `POSTGRES_ADMIN_USER`, `POSTGRES_ADMIN_PASSWORD` ao `environment` do serviço `grafana`.
- Datasources com UID estável para permitir dashboards provisionados referenciarem por UID:
  - [`configs/grafana/provisioning/datasources/postgres.yml`](configs/grafana/provisioning/datasources/postgres.yml:1) → `uid: postgres-platform`
  - [`configs/grafana/provisioning/datasources/prometheus.yml`](configs/grafana/provisioning/datasources/prometheus.yml:1) → `uid: prometheus`
  - [`configs/grafana/provisioning/datasources/loki.yml`](configs/grafana/provisioning/datasources/loki.yml:1) → `uid: loki`
- Criado provider de dashboards: [`configs/grafana/provisioning/dashboards/dashboards.yml`](configs/grafana/provisioning/dashboards/dashboards.yml:1) (varre `configs/grafana/provisioning/dashboards/json/` a cada 30s).
- Criado o primeiro dashboard real: [`configs/grafana/provisioning/dashboards/json/platform-observability.json`](configs/grafana/provisioning/dashboards/json/platform-observability.json:1) — "Platform Observability", com painéis de CPU/memória/disco do host, CPU/memória por container, status dos scrape targets, conexões/atividade do Postgres e logs de erro recentes.
- Scrape targets confirmados em [`configs/prometheus/prometheus.yml`](configs/prometheus/prometheus.yml:1): `prometheus`, `node-exporter`, `cadvisor`, `traefik` (via `/metrics`).
- Labels de log confirmados em [`configs/promtail/config.yml`](configs/promtail/config.yml:1): job `varlogs` (`/var/log/*.log`) e job `docker` (`/var/lib/docker/containers/*/*-json.log`).
- README atualizado com toda essa seção (ver [`README.md`](README.md:115)).

**Para adicionar um novo dashboard**: exportar o JSON do Grafana e colocar em `configs/grafana/provisioning/dashboards/json/` — não precisa reiniciar nada além do próximo `terraform apply` (que já tem o hash desse diretório nos triggers... na verdade os triggers atuais só cobrem os arquivos individuais dos datasources, não recursivamente a pasta `json/` — **atenção**: se só o JSON do dashboard mudar sem tocar em outro arquivo com hash monitorado, o redeploy automático via CI pode não disparar porque `deploy_stack` não tem trigger para arquivos dentro de `dashboards/json/`. Isso é uma lacuna conhecida, ver seção 8).

## 6. Segurança / secrets

- Todo segredo sensível é declarado como `variable ... { sensitive = true }` em [`terraform/variables.tf`](terraform/variables.tf:1) e passado via `TF_VAR_*` no workflow.
- Local: `terraform/terraform.tfvars` (gitignored, só existe localmente/no runner) — template em [`terraform/terraform.tfvars.example`](terraform/terraform.tfvars.example:1).
- GitHub Actions: os mesmos valores replicados como GitHub Secrets do repo (ambiente `production`).
- ~~Script de automação: `scripts/bootstrap_github_secrets.py`~~ — **removido em 17/08/2026** (mega spec agent-llm, `analise-06-estudo-profundo-repos.md`). Gerava senhas NOVAS pra todos os serviços a cada execução e sobrescrevia `terraform.tfvars` + todos os GitHub Secrets sem distinguir "primeira vez" de "já em produção" — risco real de girar credencial em uso. Ficam documentados aqui pra quando precisar recriar algo do zero: lista de secrets usados pelo Terraform: `VPS_HOST`, `VPS_DEPLOY_USER`, `VPS_SSH_PRIVATE_KEY`, `VPS_INITIAL_SSH_PASSWORD`, `VPS_PUBLIC_SSH_KEY`, `HOSTINGER_API_KEY`, `POSTGRES_ADMIN_PASSWORD`, `PGBOUNCER_ADMIN_PASSWORD`, `REDIS_PASSWORD`, `MINIO_ROOT_PASSWORD`, `PGADMIN_PASSWORD`, `GRAFANA_ADMIN_PASSWORD`, `UPTIME_KUMA_PASSWORD`, `TRAEFIK_BASIC_AUTH` (bcrypt de `admin:<senha>`), `CODE_SERVER_PASSWORD`, `CODE_SERVER_SUDO_PASSWORD`, `RESTIC_REPOSITORY`, `RESTIC_PASSWORD`, `RESTIC_ENVIRONMENT_JSON`. Recriar/rotacionar agora é manual: gerar cada valor, gravar em `terraform/terraform.tfvars` E como GitHub Secret do ambiente `production`, um de cada vez — mais lento, mas sem risco de girar tudo por engano.

## 7. Backups (restic)

- Scripts: [`scripts/backup-postgres.sh`](scripts/backup-postgres.sh:1), [`scripts/backup-minio.sh`](scripts/backup-minio.sh:1), [`scripts/restore-postgres.sh`](scripts/restore-postgres.sh:1), [`scripts/install-backup-cron.sh`](scripts/install-backup-cron.sh:1).
- Depende de `restic_repository` + `restic_password` + `restic_environment` (map opcional, ex. credenciais S3), todos wired ponta a ponta: GitHub secret → `TF_VAR_*` → `terraform.tfvars`/`main.tf` → `compose/.env`.
- Enquanto o repositório restic não apontar para um backend real, os scripts detectam e **pulam** o upload (não falham o deploy).
- Para configurar credenciais reais do backend: gerar `RESTIC_REPOSITORY`/`RESTIC_PASSWORD`/`RESTIC_ENVIRONMENT_JSON` manualmente e gravar como GitHub Secret + `terraform.tfvars` (script de bootstrap automático removido, ver seção 6).

## 8. Estado atual (o que já foi feito vs. o que falta)

### Já feito (todos 1-28)

- Arquitetura, estrutura de repositório, stack Compose completa, DNS, secrets, workflows, bootstrap SSH, cleanup do repo, subdomínios por serviço, Postgres exposto via Traefik TCP, credenciais reais wired, observabilidade Grafana/Prometheus/Loki funcional.

### Pendente (todos 29-37) — ordem recomendada de execução

1. **(29, em andamento)** Este arquivo `memoria.md`.
2. **(30)** Rodar o primeiro `terraform apply` real (workflow `Terraform Apply` ou `scripts/deploy.sh apply` localmente) — **isto ainda não foi feito nesta sessão**. Pré-requisito: garantir que `terraform/terraform.tfvars` existe com valores reais (rodar `scripts/bootstrap_github_secrets.py` se ainda não rodado, ou confirmar que já rodou antes).
3. **(31)** SSH na VPS (`deploy@66.94.101.153`) e `docker ps` / `docker compose ps` para confirmar todos os containers up e healthy.
4. **(32)** Testar cada endpoint HTTPS (status code, login funcionando) — lista completa na seção 3.
5. **(33)** Medir latência de cada endpoint (ex. `curl -o /dev/null -s -w "%{time_total}\n"`).
6. **(34)** Rodar o pipeline CI/CD (push de mudança pequena em `terraform/variables.tf` ou config) múltiplas vezes para provar redeploy automático confiável.
7. **(35)** Gerar um JSON local (fora do git) com url/login/senha de cada serviço — usar os valores de `terraform.tfvars` + `terraform output public_urls`.
8. **(36)** Reescrever [`README.md`](README.md:1) como guia por serviço ("editar X → push → CI/CD roda").
9. **(37)** Passe final de verificação e resumo de conclusão.

### Mudanças locais não commitadas (no momento da escrita deste arquivo)

`git status` no diretório `vps_rt_infra/` mostra os seguintes arquivos **modificados mas não commitados** em `main`:

- `.github/workflows/terraform-apply.yml`
- `README.md`
- `compose/.env.tftpl`
- `compose/docker-compose.yml`
- `configs/grafana/provisioning/datasources/loki.yml`
- `configs/grafana/provisioning/datasources/postgres.yml`
- `configs/grafana/provisioning/datasources/prometheus.yml`
- `scripts/bootstrap_github_secrets.py`
- `terraform/main.tf`

**Ação necessária antes ou durante o todo 30**: revisar o diff completo desses arquivos, garantir que estão consistentes (provavelmente correspondem ao trabalho do todo 26-28: subdomínios, credenciais, Grafana), e então `git add -A && git commit && git push` para `main` — isso é o que vai efetivamente disparar o workflow `Terraform Apply` (que roda em `push` para `main` com paths em `terraform/**`, `compose/**`, `configs/**`, `apps/**`, `cloud-init/**`, `scripts/**`).

### Lacuna conhecida (achado durante o todo 28, ainda não corrigido)

Os `triggers` de `null_resource.deploy_stack` em [`terraform/main.tf`](terraform/main.tf:122) usam `filesha256()` em arquivos **individuais**, não em diretórios inteiros. Isso significa:

- Novos arquivos JSON adicionados em `configs/grafana/provisioning/dashboards/json/` **não** disparam automaticamente um redeploy via trigger de hash (a pasta inteira via `provisioner "file"` ainda é sincronizada em todo apply, mas se nada mais mudou, o `null_resource.deploy_stack` pode não ser considerado "tainted" pelo Terraform e não rodar de novo).
- Também vale para qualquer novo arquivo dentro de `configs/` que não tenha uma linha de trigger dedicada.
- **Correção sugerida** (não aplicada ainda): trocar os triggers baseados em arquivo único por um hash agregado de todo o diretório `configs/` (ex.: `md5(join("", [for f in fileset(path.module, "../configs/**") : filemd5(f)]))`), ou simplesmente aceitar que o workflow também pode ser disparado manualmente via `workflow_dispatch` quando necessário.

## 8b. Client static sites (2026-08-17)

Novo escopo do repo: hospedar sites estáticos de clientes, isolados dos serviços principais. Dois modos: **A** domínio próprio do cliente, **B** cliente sem domínio ainda -> subdomínio `<slug>.rangeltech.net` (esse sim entra em `terraform/dns.tf`, igual `grafana`/`9route`/etc). Modo é só uma questão de qual `Host()` usar + onde o DNS é gerenciado; container/pasta/TLS são idênticos.

- **Decisão**: repositório único (`vps_rt_infra`), não 1 repo por site. Justificativa do usuário: sites são simples/estáticos, não justificam overhead de N repositórios; infra e CI/CD já estão centralizados aqui. Repo por cliente só faria sentido se o cliente precisasse de acesso git próprio.
- **Decisão**: 1 container `nginx:alpine` por cliente (não 1 nginx compartilhado com vhosts), consistente com o padrão já usado por todo o resto do compose (1 serviço = 1 bloco com labels Traefik próprias). Trade-off aceito: mais containers idle (nginx:alpine é leve, ~5-10MB, ok pra VPS 6).
- **Estrutura**: `sites/<slug>/public/` (arquivos estáticos) + bloco de serviço em [`compose/docker-compose.yml`](compose/docker-compose.yml:1) seção `## Client static sites ##` (final do arquivo, antes de `networks:`). Runbook completo de onboarding/remoção em [`sites/README.md`](sites/README.md:1).
- **TLS**: mesmo `certresolver=letsencrypt` (HTTP-01) já usado por todo mundo — funciona pra qualquer domínio apontado pro IP da VPS, não precisa mudar nada no Traefik.
- **DNS**: modo A fica fora do escopo do [`terraform/dns.tf`](terraform/dns.tf:1) — domínio do cliente aponta A record pro IP `66.94.101.153` fora deste repo (registrador do cliente, ou Hostinger nossa se o domínio for nosso). Modo B entra normalmente em `terraform/dns.tf` como mais uma linha de `dns_records` (`{ name = "<slug>", type = "A", value = var.server_ip, ttl = 300 }`), igual qualquer outro subdomínio da stack.
- **Sync/deploy**: `sites/` foi adicionado em 3 lugares que precisavam saber da pasta nova:
  - [`terraform/main.tf`](terraform/main.tf:121): `provisioner "file"` sincroniza `sites/` pra `/opt/platform/sites`, mkdir do dir remoto, e trigger `sites_sha` (hash agregado via `fileset`+`filemd5`, não por arquivo individual — necessário porque cada cliente novo adiciona arquivos, e o padrão de trigger por arquivo único não escala pra isso, mesma lacuna já documentada na seção 8 pra `dashboards/json/`).
  - [`.github/workflows/deploy-vps.yml`](.github/workflows/deploy-vps.yml:1): `sites/` adicionado no rsync.
  - [`.github/workflows/terraform-apply.yml`](.github/workflows/terraform-apply.yml:1) e [`terraform-plan.yml`](.github/workflows/terraform-plan.yml:1): `sites/**` adicionado nos `paths` que disparam o workflow.
- **Ainda não commitado/aplicado**: nenhum cliente real foi cadastrado ainda (só o scaffold/bloco de exemplo comentado). Primeiro cliente real vai ser o primeiro teste ponta a ponta desse fluxo — validar principalmente o trigger `sites_sha` do Terraform e o certificado Let's Encrypt saindo certo pro domínio externo.

## 9. Decisões de design importantes (para não repetir debate)

- **Sem VM management via Terraform**: a Contabo já entrega o servidor; Terraform só bootstrap + deploy via SSH. Isso é intencional, não uma limitação a "corrigir".
- **Rede `internal` sem saída**: serviços de dado (Postgres, Redis) ficam isolados; só saem via Traefik quando explicitamente necessário (PgBouncer para Postgres).
- **PgBouncer, não Postgres direto, exposto externamente**: acesso externo ao banco passa sempre pelo pool de conexões.
- **Basic auth do Traefik (`admin-auth@docker`)** protege: dashboard do Traefik, console do MinIO, pgAdmin, Prometheus, Loki. Grafana e Uptime Kuma usam login próprio da aplicação. 9router e MinIO API ficam sem basic auth (são a "aplicação" pública).
- **Chave SSH v2**: houve uma migração de uma chave anterior para `vps_rt_infra_ed25519_v2` (todo 22) — se algo referenciar a chave antiga, está desatualizado.
- **`bootstrap_github_secrets.py` é destrutivo para credenciais**: gera senhas novas a cada execução. Não rodar de novo sem necessidade real (ex. rotação de credenciais) uma vez que a VPS já estiver em produção com essas senhas.

## 10. Onde continuar (para a próxima sessão/chat)

Se você está retomando este projeto:

1. Leia este arquivo inteiro (já feito, se está lendo agora).
2. Rode `git status` em `vps_rt_infra/` para confirmar se as mudanças da seção 8 já foram commitadas ou não.
3. Se ainda não commitadas: revise o diff, commit, push.
4. Confirme que `terraform/terraform.tfvars` existe e está atualizado (ou rode `scripts/bootstrap_github_secrets.py` se for a primeira vez).
5. Prossiga para o todo 30 (primeiro `terraform apply` real) e siga a ordem da seção 8.

## 11. Site portfolio pessoal + demo publica do portfolio Data/AI (2026-09-25)

Dois novos consumidores desta VPS, ambos aditivos, nenhum tocando os servicos de producao (Matrix bridges, Infisical, etc.) ja rodando aqui:

- **`site-portfolio`** (`compose/docker-compose.yml`, secao "Client static sites"): static export do repo publico `lucas-rangel-portfolio`, publicado por `.github/workflows/deploy-portfolio.yml` (dispatch manual, `ref` = tag do site) via rsync direto pra `sites/portfolio/public/` (conteudo nao versionado aqui, so o `.gitkeep`). Roteado por `Host(rangeltech.net) || Host(www.rangeltech.net)` — os dois registros DNS (`@` ja existia, `www` novo) em `terraform/dns.tf`.
- **`demo.rangeltech.net`**: perfil `public-demo` do repo publico `distributed-agent-runtime-lab` (RAG + Metabase + Airflow pausado, todos isolados), rodando como projeto Compose **separado** (`public-demo`, distinto do projeto `compose` de producao), em `/opt/demo/runtime-lab`. Deploy proprio em `demo/` (`deploy.sh` + `patch_compose_for_traefik.py` + `README.md`), disparado por `.github/workflows/deploy-demo.yml` (dispatch manual). O unico ponto de contato com a stack de producao e a rede Docker `public` ja existente — o nginx do demo entra nela so pra rotear via Traefik (labels, sem porta publicada propria), exatamente como qualquer client site. Ver `demo/README.md` pro limite de isolamento completo.

Ambos usam as MESMAS secrets do GitHub Actions ja configuradas (`VPS_SSH_PRIVATE_KEY`, `VPS_HOST`, `VPS_DEPLOY_USER`), sem secret nova.

**Pendente**: apos o primeiro `deploy-demo.yml`, so a mudanca de UUID do dashboard publico do Metabase requer recriar o nginx do demo — o script ja faz isso sozinho quando detecta que o UUID mudou.

**Estado 2026-09-25 (fim do dia)**: `https://rangeltech.net` (portfolio) e `https://demo.rangeltech.net` (public-demo, ref v0.2.2) no ar, validados por curl (chat 200, dashboard publico 200, /admin /question /api/database 403, /airflow 404, /v1/answer respondendo com citacao). Licoes: (1) `www` ja era CNAME na zona Hostinger -- o payload `overwrite` do dns.tf e upsert por registro, nao substitui a zona; (2) o commit d8ca75b levou junto o WIP matrix/synapse/mautrix que ja estava no mesmo `docker-compose.yml` (containers ja rodavam; so a config ficou commitada); (3) `ninerouter` nao existe mais no compose mas `terraform/main.tf` ainda roda `docker compose build ninerouter` (falha inofensiva, pre-existente); (4) **nunca** duplicar a chave `http:` em `configs/traefik/dynamic.yml` -- sobrescreve os routers de producao.
