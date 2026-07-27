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

1. Gerar um par de chaves SSH dedicado (ex.: `ssh-keygen -t ed25519 -f ~/.ssh/vps_rt_infra_ed25519`)
   — a chave pública vai em `public_ssh_key` e a privada em `ssh_private_key_path`
   (`terraform.tfvars`) e no secret `VPS_SSH_PRIVATE_KEY` do GitHub Actions. A senha root da
   Contabo (`secrets/contabo-vps.json`, fora deste repo) é usada só na primeira conexão de
   bootstrap; depois disso o acesso deve migrar 100% para chave.
2. Copiar `terraform/terraform.tfvars.example` para `terraform/terraform.tfvars` (nunca
   commitar — já está no `.gitignore`) e preencher com os dados reais de
   `secrets/contabo-vps.json` e `secrets/api_key_hostinger.json` (workspace principal, fora
   deste repo), gerando senhas fortes para cada serviço.
3. Registrar os mesmos valores como secrets do repositório GitHub (`Settings > Secrets and
   variables > Actions`) para os workflows `terraform-plan.yml` / `terraform-apply.yml` /
   `deploy-vps.yml` funcionarem: `VPS_HOST`, `VPS_DEPLOY_USER`, `VPS_SSH_PRIVATE_KEY`,
   `VPS_INITIAL_SSH_PASSWORD`, `VPS_PUBLIC_SSH_KEY`, `HOSTINGER_API_KEY`,
   `POSTGRES_ADMIN_PASSWORD`, `PGBOUNCER_ADMIN_PASSWORD`, `REDIS_PASSWORD`,
   `MINIO_ROOT_PASSWORD`, `PGADMIN_PASSWORD`, `GRAFANA_ADMIN_PASSWORD`,
   `UPTIME_KUMA_PASSWORD`, `TRAEFIK_BASIC_AUTH`, `RESTIC_REPOSITORY`, `RESTIC_PASSWORD`.
4. Definir um destino externo de backup (restic) — ver item 3 em "Pendências" abaixo.

## 9route e repositório GitHub — resolvidos

- **Pacote do 9route**: confirmado como `9router@0.5.40` (instalação global via
  `npm i -g 9router`, ver [`9router.bat`](../9router.bat)). Já configurado como default de
  `ninerouter_package` em [`terraform/variables.tf`](terraform/variables.tf) e usado pelo
  [`apps/9route/Dockerfile`](apps/9route/Dockerfile).
- **PAT do GitHub**: usado o PAT classic de [`../secrets/github-dev.md`](../secrets/github-dev.md)
  (conta pessoal `LucasRangelSSouza`, escopos `repo, workflow`) para criar este repositório.
- **Repositório remoto**: criado como privado em
  <https://github.com/LucasRangelSSouza/vps_rt_infra>, com este scaffold já commitado e
  enviado (`git push`) para a branch `main`.

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

1. **Destino externo de backup** (fora da própria VPS) — este scaffold usa `restic`, mas precisa
   de um repositório de destino (ex.: Backblaze B2, outro provedor de object storage) e das
   credenciais correspondentes (`restic_repository`, `restic_password`,
   `restic_environment`) antes do primeiro backup real.
2. **Trocar/desativar a senha root da Contabo** após o primeiro bootstrap bem-sucedido, já que
   o acesso definitivo passa a ser via `deploy_user` + chave SSH.
3. **Primeiro `terraform apply` real** — ainda não executado (sem `terraform` instalado
   localmente neste ambiente); rodar localmente com Terraform instalado ou via o workflow
   `terraform-apply.yml` depois de preencher `terraform.tfvars`/secrets do GitHub.
