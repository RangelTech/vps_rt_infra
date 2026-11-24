# scripts/infisical

Ferramentas da fundação de segredos (spec 57, seção 0A). **Nenhum valor de segredo fica neste repositório.**

| Arquivo | Para quê |
|---|---|
| `infapi.py` | Cliente mínimo da API do Infisical (login Universal Auth). A credencial vem de um arquivo **fora do repositório** (`INFISICAL_ENV_FILE`; padrão: o cofre pessoal, `~/.claude/secrets/infisical-rt-automacao.env`). |
| `importar.py <projeto> <caminho-na-vps> <pasta> [env|bloco]` | Copia um arquivo de segredo da VPS para o Infisical **sem trocar nenhum valor** (regra R5), confere **1 a 1** e grava um relatório de evidência (só nomes). Não sobrescreve segredo que já existe; sai com erro se algo não bater. `bloco` guarda o arquivo inteiro (chave privada, `rclone.conf`). |
| `render_env.py <projeto> <pasta> <destino> [env|bloco]` | **Gera o `.env` a partir do Infisical, no momento do deploy.** Usa a identidade **somente leitura** (`INFISICAL_ENV_FILE=...infisical-rt-deploy-leitura.env`). Escreve de forma atômica (modo 600); se o Infisical estiver fora do ar ou a pasta vier vazia, **sai com erro sem tocar no arquivo atual**. |
| `testar_render.py` | Prova que **cada `.env` gerado do Infisical é igual ao arquivo atual da VPS** (mesmas variáveis e valores). |
| `infisical_projetos.json` | Ids dos projetos do Infisical (`rt-produtos`, `qwen`, `luar`, `segundo-cerebro`, `plataforma`). Não é segredo. |

## Mapa de projetos e pastas
- `rt-produtos`: uma pasta por produto (`arenabruta`, `cortai`, ...), mais `perfil-navegador` e `_admin` (credencial do `/admin`).
- `qwen`: `llm-access`, `llm-queue`, `llm-gateway`, `gateway-keys`.
- `segundo-cerebro`: `segundo-cerebro-remoto`.
- `luar`: `agent-platform-backend`, `canais`, `chatwoot-*`, `kernel-harness`, `luar-conector-hub`, `rt-canais`, `rt-gateway`, `rt-hermes`, `rt-hermes-produtos`, `runtime-manager`.
- `plataforma`: `ai-aluno-turn`, `portfolio-api`, `proxy-sp`, `restic`, `rclone`, `airflow-pessoal-deploy-key`, `compose` (o `compose/.env` com as chaves-mestras).

Uso: `py -3 scripts/infisical/importar.py qwen /opt/platform/secrets/llm-access.env llm-access`
