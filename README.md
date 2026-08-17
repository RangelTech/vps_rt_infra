# vps_rt_infra

Infraestrutura como código da VPS pessoal em Contabo usando [`Terraform`](terraform/main.tf:1), [`Docker Compose`](compose/docker-compose.yml:1), [`cloud-init`](cloud-init/bootstrap.sh:1) e workflows em [`.github/workflows/`](.github/workflows).

Este repositório gerencia somente a camada VPS da stack em `rangeltech.net`: bootstrap do host, DNS, reverse proxy, banco, storage, observabilidade, utilitários operacionais, o serviço principal [`9router`](compose/docker-compose.yml:299) e sites estáticos de clientes com domínio próprio (ver [`sites/README.md`](sites/README.md:1)).

## Fluxo operacional padrão

Quase toda mudança deve seguir este fluxo:

1. editar o arquivo certo neste repositório;
2. commitar e dar push;
3. deixar o workflow [`Terraform Apply`](.github/workflows/terraform-apply.yml:1) ou [`Deploy VPS`](.github/workflows/deploy-vps.yml:1) sincronizar a VPS;
4. validar o endpoint público, logs e estado dos containers.

Regra prática:

- se a mudança afeta versão, credencial, DNS, variáveis, arquivos sincronizados ou bootstrap, use [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:1);
- se a mudança afeta somente Compose/configs/scripts já existentes na VPS, [`deploy-vps.yml`](.github/workflows/deploy-vps.yml:1) costuma bastar;
- evitar editar manualmente a VPS, exceto diagnóstico emergencial.

## Mapa rápido: o que editar para cada tipo de mudança

| Quero mudar... | Arquivo principal | Normalmente disparar |
|---|---|---|
| versão/tag de serviço | [`terraform/variables.tf`](terraform/variables.tf:78) ou [`terraform/terraform.tfvars`](terraform/terraform.tfvars.example:1) | [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:1) |
| senha/usuário/segredo | [`terraform/variables.tf`](terraform/variables.tf:162) + [`terraform/terraform.tfvars`](terraform/terraform.tfvars.example:1) + GitHub Secrets | [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:1) |
| rota/subdomínio/TLS/middleware | [`compose/docker-compose.yml`](compose/docker-compose.yml:17), [`configs/traefik/traefik.yml`](configs/traefik/traefik.yml:1), [`configs/traefik/dynamic.yml`](configs/traefik/dynamic.yml:1), [`terraform/dns.tf`](terraform/dns.tf:1) | [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:1) |
| volume, porta, env, healthcheck de container | [`compose/docker-compose.yml`](compose/docker-compose.yml:1) | [`deploy-vps.yml`](.github/workflows/deploy-vps.yml:1) ou [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:1) |
| scrape de métricas | [`configs/prometheus/prometheus.yml`](configs/prometheus/prometheus.yml:1) | [`deploy-vps.yml`](.github/workflows/deploy-vps.yml:1) |
| coleta de logs | [`configs/promtail/config.yml`](configs/promtail/config.yml:1) ou [`configs/loki/config.yml`](configs/loki/config.yml:1) | [`deploy-vps.yml`](.github/workflows/deploy-vps.yml:1) |
| dashboards/datasources do Grafana | [`configs/grafana/provisioning/`](configs/grafana/provisioning) | [`deploy-vps.yml`](.github/workflows/deploy-vps.yml:1) |
| scripts operacionais/backup/healthcheck | [`scripts/`](scripts) | [`deploy-vps.yml`](.github/workflows/deploy-vps.yml:1) |
| bootstrap do host/usuário/chave | [`cloud-init/bootstrap.sh`](cloud-init/bootstrap.sh:1) ou [`terraform/main.tf`](terraform/main.tf:1) | [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:1) |
| site estático de cliente (novo/existente) | [`sites/README.md`](sites/README.md:1), pasta `sites/<slug>/public/`, [`compose/docker-compose.yml`](compose/docker-compose.yml:1) | [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:1) |
| auto-restart/reconciliação do Compose | [`scripts/compose-healer.sh`](scripts/compose-healer.sh:1), [`scripts/install-compose-healer.sh`](scripts/install-compose-healer.sh:1), [`terraform/main.tf`](terraform/main.tf:139), [`deploy-vps.yml`](.github/workflows/deploy-vps.yml:1) | [`deploy-vps.yml`](.github/workflows/deploy-vps.yml:1) ou [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:1) |

## Serviços públicos e como eles funcionam

| URL | Serviço | Tipo de acesso | Fonte principal |
|---|---|---|---|
| `https://traefik.rangeltech.net` | Traefik dashboard | basic auth | [`compose/docker-compose.yml`](compose/docker-compose.yml:2) |
| `https://grafana.rangeltech.net` | Grafana | login nativo | [`compose/docker-compose.yml`](compose/docker-compose.yml:140) |
| `https://prometheus.rangeltech.net` | Prometheus | basic auth | [`compose/docker-compose.yml`](compose/docker-compose.yml:211) |
| `https://logs.rangeltech.net` | Loki | basic auth | [`compose/docker-compose.yml`](compose/docker-compose.yml:235) |
| `https://storage.rangeltech.net` | MinIO API | endpoint S3 | [`compose/docker-compose.yml`](compose/docker-compose.yml:85) |
| `https://minio-admin.rangeltech.net` | MinIO Console | basic auth + login MinIO | [`compose/docker-compose.yml`](compose/docker-compose.yml:85) |
| `https://pgadmin.rangeltech.net` | pgAdmin | basic auth + login pgAdmin | [`compose/docker-compose.yml`](compose/docker-compose.yml:116) |
| `https://uptime.rangeltech.net` | Uptime Kuma | login nativo | [`compose/docker-compose.yml`](compose/docker-compose.yml:170) |
| `https://code.rangeltech.net` | code-server | senha web | [`compose/docker-compose.yml`](compose/docker-compose.yml:186) |
| `https://9route.rangeltech.net` | 9router | serviço principal | [`compose/docker-compose.yml`](compose/docker-compose.yml:299) |
| `tcp://66.94.101.153:5432` | PgBouncer -> Postgres | conexão TCP autenticada | [`compose/docker-compose.yml`](compose/docker-compose.yml:45) |

## Serviços internos

Os serviços abaixo não devem ter publicação HTTP direta:

- [`postgres`](compose/docker-compose.yml:26)
- [`redis`](compose/docker-compose.yml:75)
- [`promtail`](compose/docker-compose.yml:256)
- [`node-exporter`](compose/docker-compose.yml:272)
- [`cadvisor`](compose/docker-compose.yml:284)

A exceção operacional é [`pgbouncer`](compose/docker-compose.yml:45), que fica atrás do entrypoint TCP do Traefik para expor a porta `5432` externamente.

## Guia por serviço

### Traefik

**Função**
- reverse proxy público;
- TLS/Let's Encrypt;
- roteamento HTTP e TCP;
- dashboard administrativo.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](compose/docker-compose.yml:2)
- [`configs/traefik/traefik.yml`](configs/traefik/traefik.yml:1)
- [`configs/traefik/dynamic.yml`](configs/traefik/dynamic.yml:1)
- [`terraform/dns.tf`](terraform/dns.tf:1)

**Quando editar**
- adicionar/remover entrypoints;
- mexer em ACME/TLS;
- alterar middlewares compartilhados;
- ajustar dashboard;
- publicar novas rotas HTTP/TCP.

**Fluxo de mudança**
1. editar [`configs/traefik/traefik.yml`](configs/traefik/traefik.yml:1) para configuração estática;
2. editar [`configs/traefik/dynamic.yml`](configs/traefik/dynamic.yml:1) para middlewares e regras compartilhadas;
3. editar labels em [`compose/docker-compose.yml`](compose/docker-compose.yml:17) quando a mudança for específica de serviço;
4. editar [`terraform/dns.tf`](terraform/dns.tf:1) se houver novo subdomínio;
5. executar [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:1).

**Validar depois**
- `https://traefik.rangeltech.net` responder `401` quando protegido por basic auth;
- certificados emitidos;
- serviços continuarem roteando.

### PostgreSQL

**Função**
- banco principal da plataforma.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](compose/docker-compose.yml:26)
- [`terraform/variables.tf`](terraform/variables.tf:166)
- [`compose/.env.tftpl`](compose/.env.tftpl:1)
- [`scripts/backup-postgres.sh`](scripts/backup-postgres.sh:1)
- [`scripts/restore-postgres.sh`](scripts/restore-postgres.sh:1)

**Quando editar**
- trocar versão do Postgres;
- alterar database/admin user/password;
- ajustar volume/healthcheck;
- revisar estratégia de backup/restore.

**Fluxo de mudança**
1. editar `postgres_version`, `postgres_db`, `postgres_admin_user` ou `postgres_admin_password` em [`terraform/variables.tf`](terraform/variables.tf:84) e/ou [`terraform/terraform.tfvars`](terraform/terraform.tfvars.example:1);
2. se a mudança for estrutural do container, editar [`compose/docker-compose.yml`](compose/docker-compose.yml:26);
3. executar [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:1).

**Validar depois**
- container `postgres` saudável;
- conexão interna funcionando via `pg_isready`;
- Grafana/pgAdmin continuarem conectando.

### PgBouncer

**Função**
- pool de conexões do Postgres;
- endpoint TCP externo na porta `5432` via Traefik.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](compose/docker-compose.yml:45)
- [`terraform/variables.tf`](terraform/variables.tf:181)

**Quando editar**
- pool size;
- auth/admin user;
- política de conexão;
- exposição TCP.

**Fluxo de mudança**
1. editar envs/labels do serviço em [`compose/docker-compose.yml`](compose/docker-compose.yml:52);
2. editar `pgbouncer_version`, `pgbouncer_admin_user` ou `pgbouncer_admin_password` em [`terraform/variables.tf`](terraform/variables.tf:90);
3. executar [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:1) se mudou variáveis, ou [`deploy-vps.yml`](.github/workflows/deploy-vps.yml:1) se foi só Compose.

**Validar depois**
- porta `5432` acessível;
- autenticação funcionando;
- aplicações continuam conectando ao banco.

### Redis

**Função**
- cache/estado efêmero/filas simples.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](compose/docker-compose.yml:75)
- [`terraform/variables.tf`](terraform/variables.tf:191)

**Fluxo de mudança**
1. editar versão/senha em [`terraform/variables.tf`](terraform/variables.tf:96) ou [`terraform/terraform.tfvars`](terraform/terraform.tfvars.example:1);
2. editar comando/volume em [`compose/docker-compose.yml`](compose/docker-compose.yml:79);
3. executar [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:1).

### MinIO API e Console

**Função**
- storage S3-compatible;
- console administrativa separada.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](compose/docker-compose.yml:85)
- [`terraform/variables.tf`](terraform/variables.tf:196)
- [`scripts/backup-minio.sh`](scripts/backup-minio.sh:1)

**Quando editar**
- versão do MinIO;
- credenciais root;
- console port/routing;
- volume persistente.

**Fluxo de mudança**
1. editar `minio_version`, `minio_root_user` ou `minio_root_password` em [`terraform/variables.tf`](terraform/variables.tf:102);
2. editar rotas `storage.*` e `minio-admin.*` em [`compose/docker-compose.yml`](compose/docker-compose.yml:99) se necessário;
3. executar [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:1).

**Validar depois**
- `https://storage.rangeltech.net/minio/health/live` retornar `200`;
- `https://minio-admin.rangeltech.net` retornar `401` antes do login;
- console abrir após basic auth + login MinIO.

### pgAdmin

**Função**
- administração web do Postgres.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](compose/docker-compose.yml:116)
- [`terraform/variables.tf`](terraform/variables.tf:206)

**Fluxo de mudança**
1. editar `pgadmin_version`, `pgadmin_email` ou `pgadmin_password` em [`terraform/variables.tf`](terraform/variables.tf:108);
2. editar labels/volume/env em [`compose/docker-compose.yml`](compose/docker-compose.yml:120);
3. executar [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:1).

**Validar depois**
- `https://pgadmin.rangeltech.net` retornar `401` antes do basic auth;
- login do app funcionar depois.

### Grafana

**Função**
- dashboards e exploração de métricas/logs.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](compose/docker-compose.yml:140)
- [`configs/grafana/provisioning/datasources/postgres.yml`](configs/grafana/provisioning/datasources/postgres.yml:1)
- [`configs/grafana/provisioning/datasources/prometheus.yml`](configs/grafana/provisioning/datasources/prometheus.yml:1)
- [`configs/grafana/provisioning/datasources/loki.yml`](configs/grafana/provisioning/datasources/loki.yml:1)
- [`configs/grafana/provisioning/dashboards/dashboards.yml`](configs/grafana/provisioning/dashboards/dashboards.yml:1)
- [`configs/grafana/provisioning/dashboards/json/platform-observability.json`](configs/grafana/provisioning/dashboards/json/platform-observability.json:1)

**Quando editar**
- versão do Grafana;
- credenciais admin;
- datasources;
- dashboards provisionados;
- root URL/security flags.

**Fluxo de mudança**
1. editar versão/credenciais em [`terraform/variables.tf`](terraform/variables.tf:114);
2. editar provisionamento em [`configs/grafana/provisioning/`](configs/grafana/provisioning);
3. colocar novos dashboards JSON em [`configs/grafana/provisioning/dashboards/json/`](configs/grafana/provisioning/dashboards/json);
4. executar [`deploy-vps.yml`](.github/workflows/deploy-vps.yml:1) para provisionamento/config ou [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:1) se mudou versão/credenciais.

**Validar depois**
- `https://grafana.rangeltech.net` responder `302`/tela de login;
- datasources `postgres`, `prometheus` e `loki` saudáveis;
- dashboard provisionado carregado.

### Uptime Kuma

**Função**
- monitoramento sintético externo.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](compose/docker-compose.yml:170)
- [`terraform/variables.tf`](terraform/variables.tf:120)

**Fluxo de mudança**
1. editar `uptime_kuma_version`, `uptime_kuma_user` e `uptime_kuma_password` em [`terraform/variables.tf`](terraform/variables.tf:120);
2. editar volume/labels em [`compose/docker-compose.yml`](compose/docker-compose.yml:174);
3. executar [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:1).

**Validar depois**
- `https://uptime.rangeltech.net` responder `302`/login.

### code-server

**Função**
- IDE web com acesso à árvore inteira sincronizada na VPS.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](compose/docker-compose.yml:186)
- [`terraform/variables.tf`](terraform/variables.tf:242)

**Detalhes importantes**
- monta [`../:/workspace`](compose/docker-compose.yml:198);
- monta Docker socket em [`/var/run/docker.sock`](compose/docker-compose.yml:200);
- usa `PASSWORD` e `SUDO_PASSWORD` renderizados do Terraform.

**Fluxo de mudança**
1. editar versão/senhas em [`terraform/variables.tf`](terraform/variables.tf:126);
2. editar mounts/env/labels em [`compose/docker-compose.yml`](compose/docker-compose.yml:197);
3. executar [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:1).

**Validar depois**
- `https://code.rangeltech.net` responder `302`/login;
- workspace abrir;
- terminal interno enxergar Docker/arquivos.

### Prometheus

**Função**
- coleta e consulta de métricas.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](compose/docker-compose.yml:211)
- [`configs/prometheus/prometheus.yml`](configs/prometheus/prometheus.yml:1)
- [`terraform/variables.tf`](terraform/variables.tf:132)

**Fluxo de mudança**
1. editar versão em [`terraform/variables.tf`](terraform/variables.tf:132);
2. editar alvos e jobs em [`configs/prometheus/prometheus.yml`](configs/prometheus/prometheus.yml:1);
3. executar [`deploy-vps.yml`](.github/workflows/deploy-vps.yml:1) para scrape config ou [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:1) para versão/segredos.

**Validar depois**
- `https://prometheus.rangeltech.net` retornar `401` antes da auth;
- targets `up` na UI.

### Loki

**Função**
- armazenamento e consulta de logs.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](compose/docker-compose.yml:235)
- [`configs/loki/config.yml`](configs/loki/config.yml:1)
- [`terraform/variables.tf`](terraform/variables.tf:138)

**Fluxo de mudança**
1. editar versão em [`terraform/variables.tf`](terraform/variables.tf:138);
2. editar config em [`configs/loki/config.yml`](configs/loki/config.yml:1);
3. executar [`deploy-vps.yml`](.github/workflows/deploy-vps.yml:1) ou [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:1).

**Validar depois**
- `https://logs.rangeltech.net` retornar `401` antes da auth;
- datasource Loki continuar saudável no Grafana.

### Promtail

**Função**
- coleta logs do host e containers e envia para Loki.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](compose/docker-compose.yml:256)
- [`configs/promtail/config.yml`](configs/promtail/config.yml:1)
- [`terraform/variables.tf`](terraform/variables.tf:144)

**Fluxo de mudança**
1. editar versão em [`terraform/variables.tf`](terraform/variables.tf:144);
2. editar scrape config/path labels em [`configs/promtail/config.yml`](configs/promtail/config.yml:1);
3. executar [`deploy-vps.yml`](.github/workflows/deploy-vps.yml:1).

### node-exporter

**Função**
- métricas do host.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](compose/docker-compose.yml:272)
- [`terraform/variables.tf`](terraform/variables.tf:150)

**Fluxo de mudança**
1. editar versão em [`terraform/variables.tf`](terraform/variables.tf:150);
2. editar command/mounts em [`compose/docker-compose.yml`](compose/docker-compose.yml:276);
3. executar [`deploy-vps.yml`](.github/workflows/deploy-vps.yml:1) ou [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:1).

### cAdvisor

**Função**
- métricas dos containers.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](compose/docker-compose.yml:284)
- [`terraform/variables.tf`](terraform/variables.tf:156)

**Fluxo de mudança**
1. editar versão em [`terraform/variables.tf`](terraform/variables.tf:156);
2. editar mounts/permissões em [`compose/docker-compose.yml`](compose/docker-compose.yml:288);
3. executar [`deploy-vps.yml`](.github/workflows/deploy-vps.yml:1) ou [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:1).

### 9router

**Função**
- serviço principal exposto em `https://9route.rangeltech.net`.

**Arquivos que controlam o serviço**
- [`compose/docker-compose.yml`](compose/docker-compose.yml:299)
- [`terraform/variables.tf`](terraform/variables.tf:254)
- [`apps/9route/Dockerfile`](apps/9route/Dockerfile:1)

**Quando editar**
- atualizar pacote `9router@...`;
- ajustar porta/env/data dir;
- revisar imagem base/processo de build futuro.

**Fluxo de mudança**
1. editar `ninerouter_package` em [`terraform/variables.tf`](terraform/variables.tf:254) ou no tfvars;
2. editar env/labels/volume em [`compose/docker-compose.yml`](compose/docker-compose.yml:303);
3. se o build local mudar, editar [`apps/9route/Dockerfile`](apps/9route/Dockerfile:1);
4. executar [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:1).

**Validar depois**
- `https://9route.rangeltech.net` responder `307`/resposta esperada do app;
- logs sem erro fatal;
- volume [`../data/9router`](compose/docker-compose.yml:309) persistindo dados.

### Client static sites

**Função**
- hospedar sites estáticos de clientes, cada um com domínio próprio (não subdomínio de `rangeltech.net`);
- isolado dos serviços principais: 1 container `nginx:alpine` por cliente.

**Arquivos que controlam o serviço**
- [`sites/README.md`](sites/README.md:1) — runbook completo de onboarding/remoção de cliente
- `sites/<slug>/public/` — arquivos estáticos do cliente
- [`compose/docker-compose.yml`](compose/docker-compose.yml:1) — seção `## Client static sites ##`, 1 bloco de serviço por cliente

**Quando editar**
- adicionar/remover cliente;
- trocar domínio de um cliente;
- publicar novos arquivos estáticos.

**Fluxo de mudança**
1. seguir [`sites/README.md`](sites/README.md:1) (criar pasta, copiar bloco de serviço, ajustar domínio);
2. garantir DNS do domínio do cliente apontando (A record) pro IP da VPS — fora deste repo, feito no registrador do cliente (ou na nossa Hostinger separadamente se o domínio for nosso);
3. executar [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:1) (a pasta `sites/**` já está nos paths que disparam o workflow).

**Validar depois**
- `https://<domínio-do-cliente>` responder `200` com certificado Let's Encrypt próprio (não o de `rangeltech.net`).

## DNS

Todos os registros públicos da zona `rangeltech.net` são geridos em [`terraform/dns.tf`](terraform/dns.tf:1). Domínios de clientes de sites estáticos (seção "Client static sites" acima) **não** entram aqui — são domínios externos, geridos fora deste repositório. Sempre que surgir um novo subdomínio público de `rangeltech.net`, a mudança correta é:

1. adicionar o registro em [`terraform/dns.tf`](terraform/dns.tf:1);
2. adicionar a rota correspondente em [`compose/docker-compose.yml`](compose/docker-compose.yml:17) e/ou [`configs/traefik/dynamic.yml`](configs/traefik/dynamic.yml:1);
3. executar [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:1).

## Credenciais e secrets

As variáveis sensíveis estão centralizadas em [`terraform/variables.tf`](terraform/variables.tf:162) e renderizadas em [`compose/.env.tftpl`](compose/.env.tftpl:1).

Fontes de verdade operacionais:

- valores locais reais em `terraform/terraform.tfvars` ignorado pelo git;
- espelhamento no GitHub Secrets para os workflows;
- referência local consolidada em [`../secrets/vps-rt-services.json`](../secrets/vps-rt-services.json).

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

Ver referências em [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:41), [`terraform-plan.yml`](.github/workflows/terraform-plan.yml:41) e [`deploy-vps.yml`](.github/workflows/deploy-vps.yml:1).

## Backups

Scripts atuais:

- [`scripts/backup-postgres.sh`](scripts/backup-postgres.sh:1)
- [`scripts/backup-minio.sh`](scripts/backup-minio.sh:1)
- [`scripts/restore-postgres.sh`](scripts/restore-postgres.sh:1)
- [`scripts/install-backup-cron.sh`](scripts/install-backup-cron.sh:1)
- [`scripts/compose-healer.sh`](scripts/compose-healer.sh:1)
- [`scripts/install-compose-healer.sh`](scripts/install-compose-healer.sh:1)

O backend externo é configurado com `RESTIC_REPOSITORY`, `RESTIC_PASSWORD` e `restic_environment`, todos conectados via Terraform + GitHub Actions.

`scripts/bootstrap_github_secrets.py` foi removido em 17/08/2026 — gerava senhas novas para TODOS os serviços a cada execução, incluindo os já em produção, risco real de girar credencial em uso sem querer. Se precisar recriar `terraform.tfvars`/GitHub Secrets do zero (nova máquina, rotação deliberada), fazer manualmente: gerar cada valor (`openssl rand -hex 32` ou equivalente), gravar em `terraform/terraform.tfvars` e como GitHub Secret do ambiente `production`, um de cada vez.

## Auto-restart da stack

O host usa um timer systemd `rt-compose-healer.timer`, instalado por [`scripts/install-compose-healer.sh`](scripts/install-compose-healer.sh:1), para reconciliar a stack a cada minuto. O script [`scripts/compose-healer.sh`](scripts/compose-healer.sh:1) lista os serviços de `docker compose config --services`; se qualquer serviço esperado estiver sem container ou com estado diferente de `running`, ele executa `docker compose up -d --remove-orphans` em `/opt/platform/compose`.

Isso complementa `restart: unless-stopped`: a política do Docker cobre crash do processo, mas não corrige uma parada limpa/manual em lote. Para manutenção intencional, criar temporariamente `/opt/platform/.maintenance` faz o healer não agir.

## Workflows

### [`terraform-plan.yml`](.github/workflows/terraform-plan.yml:1)
- usado em PR;
- valida alterações e roda `terraform plan`.

### [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:1)
- usado para aplicar mudança estrutural/variáveis/segredos/DNS;
- renderiza `compose/.env`, sincroniza arquivos e converge a stack.

### [`deploy-vps.yml`](.github/workflows/deploy-vps.yml:1)
- usado para redeploy rápido de arquivos já existentes;
- roda `docker compose up -d --remove-orphans`, instala `rt-compose-healer.timer` e executa [`scripts/healthcheck.sh`](scripts/healthcheck.sh:1).

## Validação rápida pós-mudança

Checklist objetivo depois de cada alteração importante:

1. verificar containers com `docker ps`;
2. testar endpoints críticos;
3. checar logs do serviço alterado e do [`traefik`](compose/docker-compose.yml:2);
4. confirmar healthchecks;
5. se houver credencial/rota nova, atualizar [`../secrets/vps-rt-services.json`](../secrets/vps-rt-services.json).

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

- arquitetura base: [`../arquitetura_saas_koyeb_vps_iac.md`](../arquitetura_saas_koyeb_vps_iac.md:3)
- deploy principal: [`terraform/main.tf`](terraform/main.tf:1)
- stack: [`compose/docker-compose.yml`](compose/docker-compose.yml:1)
- DNS: [`terraform/dns.tf`](terraform/dns.tf:1)
- healthcheck: [`scripts/healthcheck.sh`](scripts/healthcheck.sh:1)
- memória operacional: [`memoria.md`](memoria.md:1)
