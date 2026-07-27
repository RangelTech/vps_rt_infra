# vps_rt_infra

Infraestrutura como código (Terraform + cloud-init + Docker Compose + GitHub Actions)
para a VPS Contabo pessoal que hospeda os serviços de dados/persistência e o 9route.

Esta é a fatia **somente VPS** da arquitetura descrita em
[`arquitetura_saas_koyeb_vps_iac.md`](../arquitetura_saas_koyeb_vps_iac.md). A parte Koyeb
**não** faz parte deste repositório — ela entra em uma leva futura.

## O que este repositório gerencia

- Bootstrap do sistema operacional da VPS (Docker, firewall, fail2ban, hardening SSH).
- Stack Docker Compose com volumes persistentes:
  - Traefik (reverse proxy + TLS automático via Let's Encrypt)
  - PostgreSQL
  - PgBouncer
  - Redis
  - MinIO (API + console)
  - pgAdmin
  - Grafana
  - Uptime Kuma
  - 9route (dockerizado, antes rodava local via [`9router.bat`](../9router.bat))
  - agente de backup (restic) para Postgres e MinIO
- DNS do domínio `rangeltech.net` via API da Hostinger (registros A/AAAA/CNAME).
- CI/CD via GitHub Actions: `terraform plan`/`apply` e deploy da stack na VPS.

## Servidor alvo

```text
Provedor: Contabo
IP:       66.94.101.153
Local:    Carlstadt (US-east)
OS alvo:  Ubuntu 24.04 LTS
```

A VPS já foi comprada manualmente (não é criada pelo Terraform). O Terraform aqui atua como
**configuration harness**: conecta via SSH, faz o bootstrap do SO, sobe a stack Docker e
gerencia o DNS. Ver [`terraform/main.tf`](terraform/main.tf).

## Pré-requisitos antes do primeiro `terraform apply`

1. Trocar a senha root da Contabo (veio por e-mail) e/ou gerar um par de chaves SSH dedicado
   para o Terraform/GitHub Actions.
2. Preencher `terraform/terraform.tfvars` (nunca commitar) ou exportar variáveis `TF_VAR_*`
   com os dados de `secrets/contabo-vps.json` e `secrets/api_key_hostinger.json` (fora deste
   repo, na pasta `secrets/` do workspace principal).
3. Confirmar o pacote/imagem exato do 9route (pendente — ver seção "Pendências").
4. Confirmar qual PAT do GitHub será usado para criar o repositório remoto pessoal
   `vps_rt_infra` (pendente — ver seção "Pendências").

## Estrutura

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
│   └── .env.example
├── configs/
│   ├── traefik/
│   │   ├── traefik.yml
│   │   └── dynamic.yml
│   ├── pgbouncer/
│   │   └── userlist.txt.example
│   └── grafana/
│       └── provisioning/datasources/postgres.yml
├── apps/
│   └── 9route/
│       └── Dockerfile
├── scripts/
│   ├── deploy.sh
│   ├── backup-postgres.sh
│   ├── backup-minio.sh
│   ├── restore-postgres.sh
│   ├── hostinger_dns.sh
│   └── healthcheck.sh
└── .github/
    └── workflows/
        ├── terraform-plan.yml
        ├── terraform-apply.yml
        └── deploy-vps.yml
```

## Domínios planejados (rangeltech.net)

| Subdomínio                    | Serviço                         | Exposição                  |
|--------------------------------|----------------------------------|-----------------------------|
| `9route.rangeltech.net`        | 9route                           | Pública                     |
| `grafana.rangeltech.net`       | Grafana                          | Pública + login             |
| `storage.rangeltech.net`       | MinIO API (S3)                  | Pública (URLs assinadas)    |
| `minio-admin.rangeltech.net`   | MinIO Console                    | Basic auth + allowlist      |
| `pgadmin.rangeltech.net`       | pgAdmin                         | Basic auth + allowlist      |
| `uptime.rangeltech.net`        | Uptime Kuma                      | Pública                     |
| `traefik.rangeltech.net`       | Dashboard Traefik                | Basic auth + allowlist      |

PostgreSQL (via PgBouncer), Redis e a porta 5432 direta **não** são expostos publicamente —
apenas dentro da rede interna do Docker Compose ou por túnel SSH/Tailscale quando necessário.

## Pendências para fechar o plano

1. **Nome exato do pacote/imagem do 9route** — hoje ele roda local via `9router` (CLI global,
   ver [`9router.bat`](../9router.bat)). O Dockerfile em
   [`apps/9route/Dockerfile`](apps/9route/Dockerfile) está parametrizado com um build-arg
   `NINEROUTER_PACKAGE`, mas precisa do nome real do pacote npm (ou do repositório fonte) para
   ser finalizado.
2. **PAT do GitHub para o repositório pessoal** — por padrão usaríamos o PAT em
   [`../secrets/github-dev.md`](../secrets/github-dev.md), mas ele é um PAT classic da conta
   `LucasRangelSSouza` com escopo `repo, workflow` já usado para os repositórios da org Eduk.
   Confirmar se deve ser reaproveitado ou se um PAT pessoal dedicado deve ser gerado antes de
   criar o repositório remoto `vps_rt_infra` (conta pessoal, fora da org Eduk).
3. **Destino externo de backup** (fora da própria VPS) — este scaffold usa `restic`, mas precisa
   de um repositório de destino (ex.: Backblaze B2, outro provedor de object storage) e das
   credenciais correspondentes antes do primeiro backup real.
