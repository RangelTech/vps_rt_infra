# PNCP dashboard edge (private infrastructure)

`https://pncp.rangeltech.net`: a portfolio-styled shell page plus the single public Metabase dashboard route, served by its own nginx and routed by Traefik. The Metabase instance and analytics database are the existing `public-demo` ones; this project only attaches to their `app` network to reach Metabase.

Deploy: copy this directory to `/opt/pncp-dashboard`, write `/opt/pncp-dashboard/.env` with `PUBLIC_DASHBOARD_UUID=<uuid printed by seed_pncp_dashboard.py>`, then `docker compose up -d`.
