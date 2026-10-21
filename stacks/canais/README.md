# Pilha `canais` (Fase CH-1)

Synapse privado + `matrix-postgres` + `mautrix-meta` (Messenger) + `mautrix-instagram` + `mautrix-whatsapp` + molde dos workers TikTok.
Separada da pilha `platform`. **Estes arquivos so foram revisados e validados estaticamente; nada foi subido na VPS.**

## O que tem aqui
| Arquivo | Papel |
|---|---|
| `compose.yml` | servicos, redes `canais_net` (interna, sem saida) e `canais_egress` (so saida), healthchecks, limites |
| `versions.env` | imagens por tag + digest (marcador `DIGEST_A_PREENCHER` ate rodar `scripts/resolve_digests.sh` na raiz do repo) |
| `.env.example` | nomes das variaveis; valores reais so em `/opt/platform/secrets/canais.env` (0600) |
| `templates/` | Synapse, registros de appservice (gateway + 3 bridges) e configs dos bridges (sem cookies) |
| `scripts/render-configs.sh` | templates + segredos -> `$CANAIS_DATA/rendered` (0600, fora do git) |
| `scripts/prepare-host.sh` | diretorios e donos (999:999 postgres, 991 Synapse, 1337 bridges) |
| `scripts/backup-before-upgrade.sh` / `restore.sh` / `rollback.sh` | backup antes de atualizar, restore (teste descartavel ou aplicar) e rollback de imagem |
| `scripts/validate.sh [--strict]` | `docker compose config` + checagens (sem portas publicas, sem Traefik, sem `public`, sem `latest`, sem cookies) |

## Os 3 problemas conhecidos de 28/08/2026 e onde estao resolvidos
1. **Config do Synapse fora de `/data`**: homeserver em `/etc/synapse` (`SYNAPSE_CONFIG_PATH`), so estado real em `/data`. Nunca montar arquivo dentro do volume de outro mount.
2. **Redes**: bridges e workers precisam de saida real para a internet, que a rede `internal: true` nao roteia. Em vez de entrar na rede `public` (do Traefik), usam `canais_egress`, dedicada, sem portas publicadas.
3. **`matrix-postgres`**: diretorio de dados `999:999` (`prepare-host.sh`).

## Ligacao com o gateway (rede interna)
O gateway (`chatwoot-bridge`) precisa enxergar `synapse:8008`, `mautrix-instagram:29319`, `mautrix-meta:29319`, `mautrix-whatsapp:29318` e ser alcancavel pelo Synapse (`GATEWAY_AS_URL`).
Mudanca necessaria em `stacks/chatwoot/compose.yml` (**fora do escopo desta entrega, por release**): adicionar a rede externa `canais_net` ao servico `chatwoot-bridge`.
Variaveis do gateway: `MATRIX_SERVER_NAME`, `MATRIX_AS_TOKEN`=`GATEWAY_AS_TOKEN`, `MATRIX_HS_TOKEN`=`GATEWAY_HS_TOKEN`, `BRIDGE_PROVISIONING_SECRET`.

## Decisoes a confirmar no CH-0 (nao assumidas como provadas)
- `bridge.permissions` do mautrix aceita chaves exatas (usuario, dominio ou `*`), **nao regex**. O padrao `@luar_t<conta>_c<id>:<servidor>` e imposto em duas camadas: namespace exclusivo do appservice do gateway (`registrations/gateway.yaml.tmpl`) e Synapse com registro fechado; no bridge a permissao `user` vale para o dominio e `admin` so para `BRIDGE_ADMIN_MXID`. Provar na CH-11 (autorizacao negativa). Plano B: um processo por tenant.
- Endpoint de saude `/_matrix/mau/live` e chaves minimas das configs (`network.mode`, `history_sync`) variam por versao: conferir contra o config de exemplo da imagem `v26.10` (`<imagem> -e`) antes do 1o deploy.
- Tags `v26.10`/`ig-v26.10` no `dock.mau.dev`: `resolve_digests.sh` falha se a tag nao existir.
- UID dos bridges (1337) e do Synapse (991): conferir com `docker inspect` na imagem fixada.

## Migracao dos bridges antigos (28/08) sem apagar nada
A pilha antiga (`platform`: `synapse`, `matrix-postgres`, `mautrix-meta-facebook/instagram`, cookies da extensao) **continua parada ou intacta** ate o aceite; a nova usa nomes `canais-*` e dados em `data/canais/`. Sessoes por cookie **nao convertem** (CH-9: reconexao pelo assistente). Dados antigos ficam como estao ate o U-7, com backup.

## Fluxo de atualizacao (resumo; detalhe em `docs/canais/runbooks/atualizar-bridge.md`)
`resolve_digests.sh` -> `validate.sh --strict` -> `backup-before-upgrade.sh` -> `restore.sh <backup> --teste` -> drenar -> release/lock (`apply-stack.sh canais`) -> conta de teste -> vigilancia. Falhou: `rollback.sh`; dados: `restore.sh --aplicar`.
