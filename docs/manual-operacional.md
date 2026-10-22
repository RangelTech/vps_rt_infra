# vps_rt_infra

Infraestrutura como código da VPS pessoal em Contabo usando [`Terraform`](../terraform/main.tf), [`Docker Compose`](../compose/docker-compose.yml), [`cloud-init`](../cloud-init/bootstrap.sh) e workflows em [`.github/workflows/`](../.github/workflows).

Este repositório gerencia somente a camada VPS da stack em `rangeltech.net`: bootstrap do host, DNS, reverse proxy, banco, storage, observabilidade, utilitários operacionais, o serviço principal [`9router`](../compose/docker-compose.yml) e sites estáticos de clientes com domínio próprio (ver [`sites/README.md`](../sites/README.md)).

## Fluxo operacional padrão

Quase toda mudança deve seguir este fluxo:

1. editar o arquivo certo neste repositório;
2. commitar e dar push;
3. deixar o workflow `Terraform Apply` ou `Deploy VPS` sincronizar a VPS;
4. validar o endpoint público, logs e estado dos containers.

Regra prática:

- se a mudança afeta versão, credencial, DNS, variáveis, arquivos sincronizados ou bootstrap, use `terraform-apply.yml`;
- se a mudança afeta somente Compose/configs/scripts já existentes na VPS, `deploy-vps.yml` costuma bastar;
- evitar editar manualmente a VPS, exceto diagnóstico emergencial.

## Mapa rápido: o que editar para cada tipo de mudança

| Quero mudar... | Arquivo principal | Normalmente disparar |
|---|---|---|
| versão/tag de serviço | [`terraform/variables.tf`](../terraform/variables.tf) ou [`terraform/terraform.tfvars`](../terraform/terraform.tfvars.example) | `terraform-apply.yml` |
| senha/usuário/segredo | [`terraform/variables.tf`](../terraform/variables.tf) + [`terraform/terraform.tfvars`](../terraform/terraform.tfvars.example) + GitHub Secrets | `terraform-apply.yml` |
| rota/subdomínio/TLS/middleware | [`compose/docker-compose.yml`](../compose/docker-compose.yml), [`configs/traefik/traefik.yml`](../configs/traefik/traefik.yml), [`configs/traefik/dynamic.yml`](../configs/traefik/dynamic.yml), [`terraform/dns.tf`](../terraform/dns.tf) | `terraform-apply.yml` |
| volume, porta, env, healthcheck de container | [`compose/docker-compose.yml`](../compose/docker-compose.yml) | `deploy-vps.yml` ou `terraform-apply.yml` |
| scrape de métricas | [`configs/prometheus/prometheus.yml`](../configs/prometheus/prometheus.yml) | `deploy-vps.yml` |
| coleta de logs | [`configs/promtail/config.yml`](../configs/promtail/config.yml) ou [`configs/loki/config.yml`](../configs/loki/config.yml) | `deploy-vps.yml` |
| dashboards/datasources do Grafana | [`configs/grafana/provisioning/`](../configs/grafana/provisioning) | `deploy-vps.yml` |
| scripts operacionais/backup/healthcheck | [`scripts/`](../scripts) | `deploy-vps.yml` |
| bootstrap do host/usuário/chave | [`cloud-init/bootstrap.sh`](../cloud-init/bootstrap.sh) ou [`terraform/main.tf`](../terraform/main.tf) | `terraform-apply.yml` |
| site estático de cliente (novo/existente) | [`sites/README.md`](../sites/README.md), pasta `sites/<slug>/public/`, [`compose/docker-compose.yml`](../compose/docker-compose.yml) | `terraform-apply.yml` |
| auto-restart/reconciliação do Compose | `scripts/compose-healer.sh`, `scripts/install-compose-healer.sh`, [`terraform/main.tf`](../terraform/main.tf), `deploy-vps.yml` | `deploy-vps.yml` ou `terraform-apply.yml` |

## Serviços públicos e como eles funcionam

| URL | Serviço | Tipo de acesso | Fonte principal |
|---|---|---|---|
| `https://traefik.rangeltech.net` | Traefik dashboard | basic auth | [`compose/docker-compose.yml`](../compose/docker-compose.yml) |
| `https://grafana.rangeltech.net` | Grafana | login nativo | [`compose/docker-compose.yml`](../compose/docker-compose.yml) |
| `https://prometheus.rangeltech.net` | Prometheus | basic auth | [`compose/docker-compose.yml`](../compose/docker-compose.yml) |
| `https://logs.rangeltech.net` | Loki | basic auth | [`compose/docker-compose.yml`](../compose/docker-compose.yml) |
| `https://storage.rangeltech.net` | MinIO API | endpoint S3 | [`compose/docker-compose.yml`](../compose/docker-compose.yml) |
| `https://minio-admin.rangeltech.net` | MinIO Console | basic auth + login MinIO | [`compose/docker-compose.yml`](../compose/docker-compose.yml) |
| `https://pgadmin.rangeltech.net` | pgAdmin | basic auth + login pgAdmin | [`compose/docker-compose.yml`](../compose/docker-compose.yml) |
| `https://uptime.rangeltech.net` | Uptime Kuma | login nativo | [`compose/docker-compose.yml`](../compose/docker-compose.yml) |
| `https://code.rangeltech.net` | code-server | senha web | [`compose/docker-compose.yml`](../compose/docker-compose.yml) |
| `https://9route.rangeltech.net` | 9router | serviço principal | [`compose/docker-compose.yml`](../compose/docker-compose.yml) |
| `tcp://66.94.101.153:5432` | PgBouncer -> Postgres | conexão TCP autenticada | [`compose/docker-compose.yml`](../compose/docker-compose.yml) |

## Serviços internos

Os serviços abaixo não devem ter publicação HTTP direta:

- [`postgres`](../compose/docker-compose.yml)
- [`redis`](../compose/docker-compose.yml)
- [`promtail`](../compose/docker-compose.yml)
- [`node-exporter`](../compose/docker-compose.yml)
- [`cadvisor`](../compose/docker-compose.yml)

A exceção operacional é [`pgbouncer`](../compose/docker-compose.yml), que fica atrás do entrypoint TCP do Traefik para expor a porta `5432` externamente.

## Guia por serviço

### Traefik

**Função**
- reverse proxy público;
- TLS/Let's Encrypt;
- roteamento HTTP e TCP;
- dashboard administrativo.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](../compose/docker-compose.yml)
- [`configs/traefik/traefik.yml`](../configs/traefik/traefik.yml)
- [`configs/traefik/dynamic.yml`](../configs/traefik/dynamic.yml)
- [`terraform/dns.tf`](../terraform/dns.tf)

**Quando editar**
- adicionar/remover entrypoints;
- mexer em ACME/TLS;
- alterar middlewares compartilhados;
- ajustar dashboard;
- publicar novas rotas HTTP/TCP.

**Fluxo de mudança**
1. editar [`configs/traefik/traefik.yml`](../configs/traefik/traefik.yml) para configuração estática;
2. editar [`configs/traefik/dynamic.yml`](../configs/traefik/dynamic.yml) para middlewares e regras compartilhadas;
3. editar labels em [`compose/docker-compose.yml`](../compose/docker-compose.yml) quando a mudança for específica de serviço;
4. editar [`terraform/dns.tf`](../terraform/dns.tf) se houver novo subdomínio;
5. executar `terraform-apply.yml`.

**Validar depois**
- `https://traefik.rangeltech.net` responder `401` quando protegido por basic auth;
- certificados emitidos;
- serviços continuarem roteando.

### PostgreSQL

**Função**
- banco principal da plataforma.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](../compose/docker-compose.yml)
- [`terraform/variables.tf`](../terraform/variables.tf)
- [`compose/.env.tftpl`](../compose/.env.tftpl)
- `scripts/backup-postgres.sh`
- `scripts/restore-postgres.sh`

**Quando editar**
- trocar versão do Postgres;
- alterar database/admin user/password;
- ajustar volume/healthcheck;
- revisar estratégia de backup/restore.

**Fluxo de mudança**
1. editar `postgres_version`, `postgres_db`, `postgres_admin_user` ou `postgres_admin_password` em [`terraform/variables.tf`](../terraform/variables.tf) e/ou [`terraform/terraform.tfvars`](../terraform/terraform.tfvars.example);
2. se a mudança for estrutural do container, editar [`compose/docker-compose.yml`](../compose/docker-compose.yml);
3. executar `terraform-apply.yml`.

**Validar depois**
- container `postgres` saudável;
- conexão interna funcionando via `pg_isready`;
- Grafana/pgAdmin continuarem conectando.

### PgBouncer

**Função**
- pool de conexões do Postgres;
- endpoint TCP externo na porta `5432` via Traefik.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](../compose/docker-compose.yml)
- [`terraform/variables.tf`](../terraform/variables.tf)

**Quando editar**
- pool size;
- auth/admin user;
- política de conexão;
- exposição TCP.

**Fluxo de mudança**
1. editar envs/labels do serviço em [`compose/docker-compose.yml`](../compose/docker-compose.yml);
2. editar `pgbouncer_version`, `pgbouncer_admin_user` ou `pgbouncer_admin_password` em [`terraform/variables.tf`](../terraform/variables.tf);
3. executar `terraform-apply.yml` se mudou variáveis, ou `deploy-vps.yml` se foi só Compose.

**Validar depois**
- porta `5432` acessível;
- autenticação funcionando;
- aplicações continuam conectando ao banco.

### Redis

**Função**
- cache/estado efêmero/filas simples.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](../compose/docker-compose.yml)
- [`terraform/variables.tf`](../terraform/variables.tf)

**Fluxo de mudança**
1. editar versão/senha em [`terraform/variables.tf`](../terraform/variables.tf) ou [`terraform/terraform.tfvars`](../terraform/terraform.tfvars.example);
2. editar comando/volume em [`compose/docker-compose.yml`](../compose/docker-compose.yml);
3. executar `terraform-apply.yml`.

### MinIO API e Console

**Função**
- storage S3-compatible;
- console administrativa separada.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](../compose/docker-compose.yml)
- [`terraform/variables.tf`](../terraform/variables.tf)
- `scripts/backup-minio.sh`

**Quando editar**
- versão do MinIO;
- credenciais root;
- console port/routing;
- volume persistente.

**Fluxo de mudança**
1. editar `minio_version`, `minio_root_user` ou `minio_root_password` em [`terraform/variables.tf`](../terraform/variables.tf);
2. editar rotas `storage.*` e `minio-admin.*` em [`compose/docker-compose.yml`](../compose/docker-compose.yml) se necessário;
3. executar `terraform-apply.yml`.

**Validar depois**
- `https://storage.rangeltech.net/minio/health/live` retornar `200`;
- `https://minio-admin.rangeltech.net` retornar `401` antes do login;
- console abrir após basic auth + login MinIO.

### pgAdmin

**Função**
- administração web do Postgres.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](../compose/docker-compose.yml)
- [`terraform/variables.tf`](../terraform/variables.tf)

**Fluxo de mudança**
1. editar `pgadmin_version`, `pgadmin_email` ou `pgadmin_password` em [`terraform/variables.tf`](../terraform/variables.tf);
2. editar labels/volume/env em [`compose/docker-compose.yml`](../compose/docker-compose.yml);
3. executar `terraform-apply.yml`.

**Validar depois**
- `https://pgadmin.rangeltech.net` retornar `401` antes do basic auth;
- login do app funcionar depois.

### Grafana

**Função**
- dashboards e exploração de métricas/logs.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](../compose/docker-compose.yml)
- [`configs/grafana/provisioning/datasources/postgres.yml`](../configs/grafana/provisioning/datasources/postgres.yml)
- [`configs/grafana/provisioning/datasources/prometheus.yml`](../configs/grafana/provisioning/datasources/prometheus.yml)
- [`configs/grafana/provisioning/datasources/loki.yml`](../configs/grafana/provisioning/datasources/loki.yml)
- [`configs/grafana/provisioning/dashboards/dashboards.yml`](../configs/grafana/provisioning/dashboards/dashboards.yml)
- [`configs/grafana/provisioning/dashboards/json/platform-observability.json`](../configs/grafana/provisioning/dashboards/json/platform-observability.json)

**Quando editar**
- versão do Grafana;
- credenciais admin;
- datasources;
- dashboards provisionados;
- root URL/security flags.

**Fluxo de mudança**
1. editar versão/credenciais em [`terraform/variables.tf`](../terraform/variables.tf);
2. editar provisionamento em [`configs/grafana/provisioning/`](../configs/grafana/provisioning);
3. colocar novos dashboards JSON em [`configs/grafana/provisioning/dashboards/json/`](../configs/grafana/provisioning/dashboards/json);
4. executar `deploy-vps.yml` para provisionamento/config ou `terraform-apply.yml` se mudou versão/credenciais.

**Validar depois**
- `https://grafana.rangeltech.net` responder `302`/tela de login;
- datasources `postgres`, `prometheus` e `loki` saudáveis;
- dashboard provisionado carregado.

### Uptime Kuma

**Função**
- monitoramento sintético externo.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](../compose/docker-compose.yml)
- [`terraform/variables.tf`](../terraform/variables.tf)

**Fluxo de mudança**
1. editar `uptime_kuma_version`, `uptime_kuma_user` e `uptime_kuma_password` em [`terraform/variables.tf`](../terraform/variables.tf);
2. editar volume/labels em [`compose/docker-compose.yml`](../compose/docker-compose.yml);
3. executar `terraform-apply.yml`.

**Validar depois**
- `https://uptime.rangeltech.net` responder `302`/login.

### code-server

**Função**
- IDE web com acesso à árvore inteira sincronizada na VPS.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](../compose/docker-compose.yml)
- [`terraform/variables.tf`](../terraform/variables.tf)

**Detalhes importantes**
- monta [`../:/workspace`](../compose/docker-compose.yml);
- monta Docker socket em [`/var/run/docker.sock`](../compose/docker-compose.yml);
- usa `PASSWORD` e `SUDO_PASSWORD` renderizados do Terraform.

**Fluxo de mudança**
1. editar versão/senhas em [`terraform/variables.tf`](../terraform/variables.tf);
2. editar mounts/env/labels em [`compose/docker-compose.yml`](../compose/docker-compose.yml);
3. executar `terraform-apply.yml`.

**Validar depois**
- `https://code.rangeltech.net` responder `302`/login;
- workspace abrir;
- terminal interno enxergar Docker/arquivos.

### Prometheus

**Função**
- coleta e consulta de métricas.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](../compose/docker-compose.yml)
- [`configs/prometheus/prometheus.yml`](../configs/prometheus/prometheus.yml)
- [`terraform/variables.tf`](../terraform/variables.tf)

**Fluxo de mudança**
1. editar versão em [`terraform/variables.tf`](../terraform/variables.tf);
2. editar alvos e jobs em [`configs/prometheus/prometheus.yml`](../configs/prometheus/prometheus.yml);
3. executar `deploy-vps.yml` para scrape config ou `terraform-apply.yml` para versão/segredos.

**Validar depois**
- `https://prometheus.rangeltech.net` retornar `401` antes da auth;
- targets `up` na UI.

### Loki

**Função**
- armazenamento e consulta de logs.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](../compose/docker-compose.yml)
- [`configs/loki/config.yml`](../configs/loki/config.yml)
- [`terraform/variables.tf`](../terraform/variables.tf)

**Fluxo de mudança**
1. editar versão em [`terraform/variables.tf`](../terraform/variables.tf);
2. editar config em [`configs/loki/config.yml`](../configs/loki/config.yml);
3. executar `deploy-vps.yml` ou `terraform-apply.yml`.

**Validar depois**
- `https://logs.rangeltech.net` retornar `401` antes da auth;
- datasource Loki continuar saudável no Grafana.

### Promtail

**Função**
- coleta logs do host e containers e envia para Loki.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](../compose/docker-compose.yml)
- [`configs/promtail/config.yml`](../configs/promtail/config.yml)
- [`terraform/variables.tf`](../terraform/variables.tf)

**Fluxo de mudança**
1. editar versão em [`terraform/variables.tf`](../terraform/variables.tf);
2. editar scrape config/path labels em [`configs/promtail/config.yml`](../configs/promtail/config.yml);
3. executar `deploy-vps.yml`.

### node-exporter

**Função**
- métricas do host.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](../compose/docker-compose.yml)
- [`terraform/variables.tf`](../terraform/variables.tf)

**Fluxo de mudança**
1. editar versão em [`terraform/variables.tf`](../terraform/variables.tf);
2. editar command/mounts em [`compose/docker-compose.yml`](../compose/docker-compose.yml);
3. executar `deploy-vps.yml` ou `terraform-apply.yml`.

### cAdvisor

**Função**
- métricas dos containers.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](../compose/docker-compose.yml)
- [`terraform/variables.tf`](../terraform/variables.tf)

**Fluxo de mudança**
1. editar versão em [`terraform/variables.tf`](../terraform/variables.tf);
2. editar mounts/permissões em [`compose/docker-compose.yml`](../compose/docker-compose.yml);
3. executar `deploy-vps.yml` ou `terraform-apply.yml`.

### 9router

**Função**
- serviço principal exposto em `https://9route.rangeltech.net`.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](../compose/docker-compose.yml)
- [`terraform/variables.tf`](../terraform/variables.tf)
- [`apps/9route/Dockerfile`](../apps/9route/Dockerfile)

**Quando editar**
- atualizar pacote `9router@...`;
- ajustar porta/env/data dir;
- revisar imagem base/processo de build futuro.

**Fluxo de mudança**
1. editar `ninerouter_package` em [`terraform/variables.tf`](../terraform/variables.tf) ou no tfvars;
2. editar env/labels/volume em [`compose/docker-compose.yml`](../compose/docker-compose.yml);
3. se o build local mudar, editar [`apps/9route/Dockerfile`](../apps/9route/Dockerfile);
4. executar `terraform-apply.yml`.

**Validar depois**
- `https://9route.rangeltech.net` responder `307`/resposta esperada do app;
- logs sem erro fatal;
- volume [`../data/9router`](../compose/docker-compose.yml) persistindo dados.

### Client static sites

**Função**
- hospedar sites estáticos de clientes, cada um com domínio próprio (não subdomínio de `rangeltech.net`);
- isolado dos serviços principais: 1 container `nginx:alpine` por cliente.

**Arquivos que controlam o serviço**
- [`sites/README.md`](../sites/README.md) — runbook completo de onboarding/remoção de cliente
- `sites/<slug>/public/` — arquivos estáticos do cliente
- [`compose/docker-compose.yml`](../compose/docker-compose.yml) — seção `## Client static sites ##`, 1 bloco de serviço por cliente

**Quando editar**
- adicionar/remover cliente;
- trocar domínio de um cliente;
- publicar novos arquivos estáticos.

**Fluxo de mudança**
1. seguir [`sites/README.md`](../sites/README.md) (criar pasta, copiar bloco de serviço, ajustar domínio);
2. garantir DNS do domínio do cliente apontando (A record) pro IP da VPS — fora deste repo, feito no registrador do cliente (ou na nossa Hostinger separadamente se o domínio for nosso);
3. executar `terraform-apply.yml` (a pasta `sites/**` já está nos paths que disparam o workflow).

**Validar depois**
- `https://<domínio-do-cliente>` responder `200` com certificado Let's Encrypt próprio (não o de `rangeltech.net`).

## DNS

Todos os registros públicos da zona `rangeltech.net` são geridos em [`terraform/dns.tf`](../terraform/dns.tf). Domínios de clientes de sites estáticos (seção "Client static sites" acima) **não** entram aqui — são domínios externos, geridos fora deste repositório. Sempre que surgir um novo subdomínio público de `rangeltech.net`, a mudança correta é:

1. adicionar o registro em [`terraform/dns.tf`](../terraform/dns.tf);
2. adicionar a rota correspondente em [`compose/docker-compose.yml`](../compose/docker-compose.yml) e/ou [`configs/traefik/dynamic.yml`](../configs/traefik/dynamic.yml);
3. executar `terraform-apply.yml`.

## Credenciais e secrets

As variáveis sensíveis estão centralizadas em [`terraform/variables.tf`](../terraform/variables.tf) e renderizadas em [`compose/.env.tftpl`](../compose/.env.tftpl).

Fontes de verdade operacionais:

- valores locais reais em `terraform/terraform.tfvars` ignorado pelo git;
- espelhamento no GitHub Secrets para os workflows;
- referência local consolidada em `../secrets/vps-rt-services.json`.

Secrets mínimos esperados pelos workflows:

- `VPS_HOST`
- `VPS_DEPLOY_USER`
- `VPS_SSH_PRIVATE_KEY`
- `VPS_INITIAL_SSH_PASSWORD`
- `VPS_PUBLIC_SSH_KEY`
- `HOSTINGER_API_KEY`
- `POSTGRES_ADMIN_PASSWORD`
- `PGBOUNCER_ADMIN_PASSWORD`
- `REDIS_PASSWORD`
- `MINIO_ROOT_PASSWORD`
- `PGADMIN_PASSWORD`
- `GRAFANA_ADMIN_PASSWORD`
- `UPTIME_KUMA_PASSWORD`
- `TRAEFIK_BASIC_AUTH`
- `CODE_SERVER_PASSWORD`
- `CODE_SERVER_SUDO_PASSWORD`
- `RESTIC_REPOSITORY`
- `RESTIC_PASSWORD`

Ver referências em `terraform-apply.yml`, `terraform-plan.yml` e `deploy-vps.yml`.

## Backups

Scripts atuais:

- `scripts/backup-postgres.sh`
- `scripts/backup-minio.sh`
- `scripts/restore-postgres.sh`
- `scripts/install-backup-cron.sh`
- `scripts/compose-healer.sh`
- `scripts/install-compose-healer.sh`

O backend externo é configurado com `RESTIC_REPOSITORY`, `RESTIC_PASSWORD` e `restic_environment`, todos conectados via Terraform + GitHub Actions.

`scripts/bootstrap_github_secrets.py` foi removido em 17/08/2026 — gerava senhas novas para TODOS os serviços a cada execução, incluindo os já em produção, risco real de girar credencial em uso sem querer. Se precisar recriar `terraform.tfvars`/GitHub Secrets do zero (nova máquina, rotação deliberada), fazer manualmente: gerar cada valor (`openssl rand -hex 32` ou equivalente), gravar em `terraform/terraform.tfvars` e como GitHub Secret do ambiente `production`, um de cada vez.

## Auto-restart da stack

O host usa um timer systemd `rt-compose-healer.timer`, instalado por `scripts/install-compose-healer.sh`, para reconciliar a stack a cada minuto. O script `scripts/compose-healer.sh` lista os serviços de `docker compose config --services`; se qualquer serviço esperado estiver sem container ou com estado diferente de `running`, ele executa `docker compose up -d --remove-orphans` em `/opt/platform/compose`.

Isso complementa `restart: unless-stopped`: a política do Docker cobre crash do processo, mas não corrige uma parada limpa/manual em lote. Para manutenção intencional, criar temporariamente `/opt/platform/.maintenance` faz o healer não agir.

## Workflows

### `terraform-plan.yml`
- usado em PR;
- valida alterações e roda `terraform plan`.

### `terraform-apply.yml`
- usado para aplicar mudança estrutural/variáveis/segredos/DNS;
- renderiza `compose/.env`, sincroniza arquivos e converge a stack.

### `deploy-vps.yml`
- usado para redeploy rápido de arquivos já existentes;
- roda `docker compose up -d --remove-orphans`, instala `rt-compose-healer.timer` e executa [`scripts/healthcheck.sh`](../scripts/healthcheck.sh).

## Validação rápida pós-mudança

Checklist objetivo depois de cada alteração importante:

1. verificar containers com `docker ps`;
2. testar endpoints críticos;
3. checar logs do serviço alterado e do [`traefik`](../compose/docker-compose.yml);
4. confirmar healthchecks;
5. se houver credencial/rota nova, atualizar `../secrets/vps-rt-services.json`.

Exemplos de resultado esperado:

- Traefik dashboard: `401`
- Prometheus: `401`
- Loki: `401`
- MinIO health: `200`
- Grafana: `302`
- Uptime Kuma: `302`
- code-server: `302`
- 9router: `307`

## Estrutura do repositório

```text
vps_rt_infra/
├── README.md
├── .gitignore
├── .env.example
├── terraform/
│   ├── versions.tf
│   ├── variables.tf
│   ├── main.tf
│   ├── dns.tf
│   ├── outputs.tf
│   └── terraform.tfvars.example
├── cloud-init/
│   └── bootstrap.sh
├── compose/
│   ├── docker-compose.yml
│   ├── .env.example
│   └── .env.tftpl
├── configs/
│   ├── traefik/
│   │   ├── traefik.yml
│   │   └── dynamic.yml
│   ├── pgbouncer/
│   │   └── userlist.txt.example
│   ├── prometheus/
│   │   └── prometheus.yml
│   ├── loki/
│   │   └── config.yml
│   ├── promtail/
│   │   └── config.yml
│   └── grafana/
│       └── provisioning/
├── apps/
│   └── 9route/
├── sites/
│   ├── README.md
│   └── <slug>/
│       └── public/
├── scripts/
└── .github/
    └── workflows/
```

## Referências rápidas

- arquitetura base: `../arquitetura_saas_koyeb_vps_iac.md`
- deploy principal: [`terraform/main.tf`](../terraform/main.tf)
- stack: [`compose/docker-compose.yml`](../compose/docker-compose.yml)
- DNS: [`terraform/dns.tf`](../terraform/dns.tf)
- healthcheck: [`scripts/healthcheck.sh`](../scripts/healthcheck.sh)
- memória operacional: no repositório `luar_docs`
