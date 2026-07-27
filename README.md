# vps_rt_infra

Infraestrutura como código da VPS pessoal em Contabo usando [`Terraform`](terraform/main.tf:1), [`cloud-init`](cloud-init/bootstrap.sh:1), [`Docker Compose`](compose/docker-compose.yml:1) e workflows do GitHub Actions em [`.github/workflows/`](.github/workflows).

Este repositório gerencia somente a camada VPS da arquitetura descrita em [`arquitetura_saas_koyeb_vps_iac.md`](../arquitetura_saas_koyeb_vps_iac.md:3). Nada aqui depende de Koyeb: a meta é que a VPS suba os serviços persistentes, observabilidade, logs, utilitários operacionais e o [`9router`](apps/9route/Dockerfile:1).

## Objetivo operacional

O fluxo desejado deste repositório é simples:

1. editar variáveis ou versões em [`terraform/variables.tf`](terraform/variables.tf:1) ou em [`terraform/terraform.tfvars`](terraform/terraform.tfvars.example:1);
2. commitar a mudança;
3. disparar [`terraform apply`](.github/workflows/terraform-apply.yml:1) via GitHub Actions;
4. deixar o Terraform renderizar [`compose/.env`](compose/.env.tftpl:1), sincronizar arquivos para a VPS e executar o redeploy da stack.

No dia a dia, a alteração de versão do PostgreSQL, Grafana, 9router, Prometheus, Loki ou qualquer outro serviço deve acontecer por Terraform, não por edição manual na VPS.

## O que este repositório sobe

### Camada base da VPS

- Bootstrap do sistema em [`cloud-init/bootstrap.sh`](cloud-init/bootstrap.sh:1)
  - instala Docker, Docker Compose plugin, curl, jq, fail2ban, ufw;
  - cria o usuário de deploy;
  - instala a chave pública SSH;
  - endurece SSH para migrar de senha root para chave.
- Orquestração/remoto em [`terraform/main.tf`](terraform/main.tf:1)
- DNS da Hostinger em [`terraform/dns.tf`](terraform/dns.tf:1)

### Serviços da stack Docker

Todos os serviços estão declarados em [`compose/docker-compose.yml`](compose/docker-compose.yml:1).

| Serviço | Função | Exposição | Config principal |
|---|---|---|---|
| Traefik | reverse proxy, TLS e roteamento | pública | [`configs/traefik/traefik.yml`](configs/traefik/traefik.yml:1) e [`configs/traefik/dynamic.yml`](configs/traefik/dynamic.yml:1) |
| PostgreSQL | banco principal | interna | [`compose/docker-compose.yml`](compose/docker-compose.yml:25) |
| PgBouncer | pool de conexões Postgres | interna | [`compose/docker-compose.yml`](compose/docker-compose.yml:44) |
| Redis | cache / filas simples / estado efêmero | interna | [`compose/docker-compose.yml`](compose/docker-compose.yml:67) |
| MinIO API | object storage S3-compatible | pública | [`compose/docker-compose.yml`](compose/docker-compose.yml:77) |
| MinIO Console | console administrativa do MinIO | pública protegida | [`compose/docker-compose.yml`](compose/docker-compose.yml:98) |
| pgAdmin | administração do Postgres | pública protegida | [`compose/docker-compose.yml`](compose/docker-compose.yml:105) |
| Grafana | dashboards | pública com login | [`compose/docker-compose.yml`](compose/docker-compose.yml:128) |
| Uptime Kuma | monitoramento sintético | pública | [`compose/docker-compose.yml`](compose/docker-compose.yml:154) |
| VS Code Server | IDE web com terminal/logs/debug | pública com senha | [`compose/docker-compose.yml`](compose/docker-compose.yml:170) |
| Prometheus | coleta de métricas | pública protegida | [`compose/docker-compose.yml`](compose/docker-compose.yml:195) e [`configs/prometheus/prometheus.yml`](configs/prometheus/prometheus.yml:1) |
| Loki | armazenamento/consulta de logs | pública protegida | [`compose/docker-compose.yml`](compose/docker-compose.yml:218) e [`configs/loki/config.yml`](configs/loki/config.yml:1) |
| Promtail | coleta de logs do host e containers | interna | [`compose/docker-compose.yml`](compose/docker-compose.yml:238) e [`configs/promtail/config.yml`](configs/promtail/config.yml:1) |
| node-exporter | métricas do host | interna | [`compose/docker-compose.yml`](compose/docker-compose.yml:254) |
| cAdvisor | métricas de containers | interna | [`compose/docker-compose.yml`](compose/docker-compose.yml:266) |
| 9router | serviço de roteamento/aplicação | pública | [`compose/docker-compose.yml`](compose/docker-compose.yml:281) |

## Domínios públicos planejados

As URLs públicas são refletidas também em [`terraform/outputs.tf`](terraform/outputs.tf:1).

| URL | Serviço | Observação |
|---|---|---|
| `https://9route.rangeltech.net` | 9router | serviço principal |
| `https://grafana.rangeltech.net` | Grafana | login próprio do Grafana |
| `https://storage.rangeltech.net` | MinIO API | endpoint S3 |
| `https://minio-admin.rangeltech.net` | MinIO Console | protegido por basic auth do Traefik |
| `https://pgadmin.rangeltech.net` | pgAdmin | protegido por basic auth do Traefik |
| `https://uptime.rangeltech.net` | Uptime Kuma | monitoramento externo |
| `https://traefik.rangeltech.net` | Dashboard Traefik | protegido por basic auth do Traefik |
| `https://code.rangeltech.net` | VS Code Server | acesso web à árvore inteira |
| `https://prometheus.rangeltech.net` | Prometheus | protegido por basic auth do Traefik |
| `https://logs.rangeltech.net` | Loki | protegido por basic auth do Traefik |

### Serviços não expostos diretamente

Os itens abaixo não devem ser publicados diretamente na internet:

- PostgreSQL
- PgBouncer
- Redis
- Promtail
- node-exporter
- cAdvisor

Eles ficam somente nas redes internas definidas em [`compose/docker-compose.yml`](compose/docker-compose.yml:306).

## VS Code Server

O pedido de acesso completo à árvore foi atendido em [`compose/docker-compose.yml`](compose/docker-compose.yml:170).

Principais pontos:

- a pasta `../` é montada como `/workspace`, então o code-server enxerga toda a árvore de [`vps_rt_infra/`](.) no host da VPS;
- o socket Docker é montado em `/var/run/docker.sock`, permitindo inspecionar containers e logs;
- a senha web usa `CODE_SERVER_PASSWORD`;
- o sudo interno usa `CODE_SERVER_SUDO_PASSWORD`.

Volume relevante:

- [`../:/workspace`](compose/docker-compose.yml:182)
- [`../data/code-server:/config`](compose/docker-compose.yml:183)

## Observabilidade e logs

### Métricas

- Prometheus coleta alvos definidos em [`configs/prometheus/prometheus.yml`](configs/prometheus/prometheus.yml:1)
- Traefik agora expõe métricas via entrypoint `metrics` em [`configs/traefik/traefik.yml`](configs/traefik/traefik.yml:9)
- node-exporter publica métricas do host
- cAdvisor publica métricas dos containers

### Logs

- Loki armazena logs
- Promtail envia logs de:
  - `/var/log`
  - `/var/lib/docker/containers/*/*-json.log`

### Grafana

Datasources provisionados automaticamente em:

- [`configs/grafana/provisioning/datasources/postgres.yml`](configs/grafana/provisioning/datasources/postgres.yml:1)
- [`configs/grafana/provisioning/datasources/prometheus.yml`](configs/grafana/provisioning/datasources/prometheus.yml:1)
- [`configs/grafana/provisioning/datasources/loki.yml`](configs/grafana/provisioning/datasources/loki.yml:1)

## Onde editar cada coisa

### Alterar versão de um serviço

Edite os defaults em [`terraform/variables.tf`](terraform/variables.tf:72) ou sobrescreva no arquivo local [`terraform/terraform.tfvars`](terraform/terraform.tfvars.example:1).

Variáveis já expostas:

- `traefik_version`
- `postgres_version`
- `pgbouncer_version`
- `redis_version`
- `minio_version`
- `pgadmin_version`
- `grafana_version`
- `uptime_kuma_version`
- `code_server_version`
- `prometheus_version`
- `loki_version`
- `promtail_version`
- `node_exporter_version`
- `cadvisor_version`
- `ninerouter_package`

Exemplo: trocar versão do Grafana

```hcl
grafana_version = "11.2.1"
```

Exemplo: trocar pacote do 9router

```hcl
ninerouter_package = "9router@0.5.41"
```

Depois rode o workflow [`Terraform Apply`](.github/workflows/terraform-apply.yml:1) ou faça `terraform apply` localmente em uma máquina que tenha Terraform.

### Alterar credenciais

As senhas e segredos estão modelados em [`terraform/variables.tf`](terraform/variables.tf:162) e entram no Compose através de [`compose/.env.tftpl`](compose/.env.tftpl:1).

Os placeholders ficam em [`terraform/terraform.tfvars.example`](terraform/terraform.tfvars.example:1), mas o arquivo real deve ser um [`terraform/terraform.tfvars`](terraform/terraform.tfvars.example:1) local e ignorado pelo git.

### Alterar roteamento e TLS

- configuração estática do Traefik: [`configs/traefik/traefik.yml`](configs/traefik/traefik.yml:1)
- middlewares e regras dinâmicas compartilhadas: [`configs/traefik/dynamic.yml`](configs/traefik/dynamic.yml:1)
- labels por serviço: [`compose/docker-compose.yml`](compose/docker-compose.yml:16)

### Alterar DNS

Os registros são geridos em [`terraform/dns.tf`](terraform/dns.tf:1).

### Alterar healthcheck operacional

O script de verificação está em [`scripts/healthcheck.sh`](scripts/healthcheck.sh:1).

### Alterar backups

Scripts relevantes:

- [`scripts/backup-postgres.sh`](scripts/backup-postgres.sh:1)
- [`scripts/backup-minio.sh`](scripts/backup-minio.sh:1)
- [`scripts/restore-postgres.sh`](scripts/restore-postgres.sh:1)
- [`scripts/install-backup-cron.sh`](scripts/install-backup-cron.sh:1)

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
│       └── provisioning/datasources/
│           ├── postgres.yml
│           ├── prometheus.yml
│           └── loki.yml
├── apps/
│   └── 9route/
│       └── Dockerfile
├── scripts/
│   ├── deploy.sh
│   ├── backup-postgres.sh
│   ├── backup-minio.sh
│   ├── restore-postgres.sh
│   ├── install-backup-cron.sh
│   ├── hostinger_dns.sh
│   └── healthcheck.sh
└── .github/
    └── workflows/
        ├── terraform-plan.yml
        ├── terraform-apply.yml
        └── deploy-vps.yml
```

## Arquivos mais importantes

- [`terraform/main.tf`](terraform/main.tf:1): renderiza [`compose/.env`](compose/.env.tftpl:1), sincroniza arquivos, sobe a stack e dispara bootstrap/deploy remoto.
- [`terraform/variables.tf`](terraform/variables.tf:1): catálogo central de versões, credenciais e knobs operacionais.
- [`compose/docker-compose.yml`](compose/docker-compose.yml:1): definição integral da stack.
- [`cloud-init/bootstrap.sh`](cloud-init/bootstrap.sh:1): primeira preparação do host.
- [`terraform/dns.tf`](terraform/dns.tf:1): registros DNS da Hostinger.
- [`terraform/outputs.tf`](terraform/outputs.tf:1): URLs públicas previstas.
- [`scripts/healthcheck.sh`](scripts/healthcheck.sh:1): smoke test dos endpoints críticos.

## Secrets necessários

Os workflows em [`.github/workflows/`](.github/workflows) precisam, no mínimo, destes secrets do GitHub:

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

Eles já estão referenciados em [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:41), [`terraform-plan.yml`](.github/workflows/terraform-plan.yml:41) e [`deploy-vps.yml`](.github/workflows/deploy-vps.yml:1).

## Workflows do GitHub Actions

### [`terraform-plan.yml`](.github/workflows/terraform-plan.yml:1)

- roda em pull requests;
- inicializa Terraform;
- injeta a chave SSH privada do runner;
- executa `terraform plan`.

### [`terraform-apply.yml`](.github/workflows/terraform-apply.yml:1)

- roda em `push` para `main` e em `workflow_dispatch`;
- injeta todos os `TF_VAR_*` sensíveis;
- executa `terraform apply -auto-approve`;
- imprime [`terraform output`](terraform/outputs.tf:1).

### [`deploy-vps.yml`](.github/workflows/deploy-vps.yml:1)

- serve para redeploy rápido da stack sem reaplicar toda a infraestrutura;
- sincroniza arquivos e executa `docker compose up -d --remove-orphans`;
- roda [`scripts/healthcheck.sh`](scripts/healthcheck.sh:1) ao final.

## Pré-requisitos do primeiro apply

1. gerar um par SSH dedicado para a VPS;
2. copiar [`terraform/terraform.tfvars.example`](terraform/terraform.tfvars.example:1) para `terraform/terraform.tfvars` e preencher valores reais;
3. registrar os mesmos valores como GitHub Secrets;
4. confirmar que o domínio `rangeltech.net` está apontando para a zona correta na Hostinger;
5. escolher e configurar um destino real do restic.

## Backups

O modelo atual usa restic para backup externo.

- Postgres: [`scripts/backup-postgres.sh`](scripts/backup-postgres.sh:1)
- MinIO: [`scripts/backup-minio.sh`](scripts/backup-minio.sh:1)

Ainda depende de:

- `RESTIC_REPOSITORY`
- `RESTIC_PASSWORD`
- variáveis auxiliares em `restic_environment`

## Estado atual do projeto

O repositório já está preparado para:

- subir PostgreSQL, PgBouncer, Redis, MinIO, pgAdmin, Grafana, Uptime Kuma, Traefik e 9router;
- incluir VS Code Server com acesso à árvore inteira;
- incluir stack de métricas e logs com Prometheus, Loki, Promtail, node-exporter e cAdvisor;
- expor subdomínios em `rangeltech.net`;
- operar por GitHub Actions.

O que ainda falta para a execução real é:

1. preencher segredos reais;
2. automatizar a gravação desses segredos no repositório GitHub;
3. disparar o primeiro apply real;
4. validar múltiplos redeploys.

## Referências rápidas

- arquitetura base: [`../arquitetura_saas_koyeb_vps_iac.md`](../arquitetura_saas_koyeb_vps_iac.md:3)
- serviço local legado do 9router: [`../9router.bat`](../9router.bat)
- deploy principal: [`terraform/main.tf`](terraform/main.tf:1)
- stack: [`compose/docker-compose.yml`](compose/docker-compose.yml:1)
