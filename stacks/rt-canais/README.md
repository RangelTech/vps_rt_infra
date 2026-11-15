# Pilha `rt-canais` (spec 44 Parte 6)

Matrix + pontes + gateway dos **produtos** (Atende AI, Grupo AI). **Separada do LUAR** (stack `canais`, que não é tocada).

| Contêiner | Uso |
|---|---|
| `rt-matrix-postgres` | Postgres (Synapse, 3 pontes e o banco `rt_gateway`) |
| `rt-synapse` | servidor Matrix `produtos.internal`, registro fechado |
| `rt-mautrix-whatsapp` / `rt-mautrix-meta` / `rt-mautrix-instagram` | pontes (WhatsApp, Messenger, DMs do Instagram) |
| `rt-gateway` | imagem do repo `RangelTech/rt-canais`: API `/internal/channels` (rede `internal`), appservice, workers TikTok ReLttk |

- Redes: `rt_canais_net` (interna), `rt_canais_egress` (saída **só** pelo proxy SP: firewall RT-PROXY-SP), `internal` (só o gateway, para os produtos).
- Segredos: `/opt/platform/secrets/rt-canais.env` (nomes em `.env.example`) e `/opt/platform/secrets/rt-gateway.env`
  (`CHANNELS_GATEWAY_TOKEN`, `ENCRYPTION_KEY`, `MATRIX_SERVER_NAME`, `MATRIX_AS_TOKEN`=`GATEWAY_AS_TOKEN`, `MATRIX_HS_TOKEN`=`GATEWAY_HS_TOKEN`, `BRIDGE_PROVISIONING_SECRET`).
- Subir: `scripts/prepare-host.sh` → `scripts/render-configs.sh` → `docker compose --env-file versions.env --env-file /opt/platform/secrets/rt-canais.env up -d` (gateway pelo deploy.yml, service=rt-gateway).
