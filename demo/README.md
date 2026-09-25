# Public-demo deployment (isolated from production)

Deploys the `public-demo` Compose profile from the public repository
[`distributed-agent-runtime-lab`](https://github.com/LucasRangelSSouza/distributed-agent-runtime-lab)
(`deploy/public-demo/`) onto this VPS, as a completely separate Docker Compose
project from the one in `compose/docker-compose.yml` (the production stack:
Matrix bridges, Infisical, etc.). Nothing here is added to, or removes
anything from, that stack.

## Isolation boundary

| | Production (`compose/`) | Demo (`demo/`) |
|---|---|---|
| Compose project name | `compose` | `public-demo` |
| Host path | `/opt/platform` | `/opt/demo/runtime-lab` (app), `/opt/demo-infra` (these scripts) |
| Deployed by | `deploy-vps.yml` / `terraform-apply.yml` | `deploy-demo.yml` only |
| Docker networks | `internal`, `public` | its own `app`/`data`/`ops`/`egress` networks, plus `public` for nginx only |
| Public routing | Traefik, one router per service | Traefik, exactly one router (`demo-nginx`) |

The only point of contact between the two is the Docker network named
`public`: it already exists (created by `compose/docker-compose.yml`) and
every other client site on this VPS joins it the same way (see
`sites/README.md`). The demo's nginx joins it too, with no published host
port of its own — see `patch_compose_for_traefik.py` below.

## What this directory contains

- `deploy.sh`: runs on the VPS (rsynced here, then invoked over SSH by
  `.github/workflows/deploy-demo.yml`). Clones/updates the public repo at a
  pinned ref, generates or reuses the demo's own secrets, downloads the
  public education Kaggle release once, patches nginx for Traefik, and runs
  `docker compose up -d` as the `public-demo` project. It never touches
  `/opt/platform`.
- `patch_compose_for_traefik.py`: the one deliberate difference between what
  runs here and what the public repo ships. The public repo's compose file
  publishes its own host ports 80/443 for a standalone local run — this VPS's
  ports 80/443 already belong to the shared Traefik, so this script removes
  nginx's `ports:`, joins it to the external `public` network, and adds the
  same kind of Traefik labels every other site here uses. It is the only
  place that knows this VPS's routing; the public repo stays portable and
  unaware of it (spec: a repo's own compose file is never edited for one
  deployment target).

## First deploy

1. Run the "Deploy Public Demo" GitHub Action (`workflow_dispatch`, input
   `ref` = the `distributed-agent-runtime-lab` tag to deploy).
2. It prints the Metabase public dashboard UUID it created; this is also
   saved into the demo's own `.env` on the VPS automatically.
3. Verify `https://demo.rangeltech.net/rag/` and the printed dashboard path
   return `200`.

## Operating it afterward

Everything from `distributed-agent-runtime-lab`'s own
[`docs/public-demo-runbook.md`](https://github.com/LucasRangelSSouza/distributed-agent-runtime-lab/blob/main/docs/public-demo-runbook.md)
applies as-is (image update, rollback, secret rotation, public-link
revocation, backup/restore, teardown), except: run everything through
`ssh deploy@rangeltech.net` into `/opt/demo/runtime-lab`, not a local machine,
and there is no local Docker Desktop TLS cert to worry about — Traefik owns
public TLS via Let's Encrypt, same as every other host on this VPS.

To redeploy a new tag, just re-run the workflow with the new `ref`. To tear
the whole demo down without touching production:

```bash
ssh deploy@rangeltech.net "cd /opt/demo/runtime-lab && bash scripts/public_demo.sh down -v"
```
