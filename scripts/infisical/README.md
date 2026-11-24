# scripts/infisical

Ferramentas da fundação de segredos (spec 57, seção 0A). **Nenhum valor de segredo fica neste repositório.**

- `infapi.py`: cliente mínimo da API do Infisical (login Universal Auth). A credencial vem de um arquivo **fora do repositório** (`INFISICAL_ENV_FILE`; padrão: o cofre pessoal em `~/.claude/secrets/infisical-rt-automacao.env`).
- `importar_env.py <produto>`: copia o `.env` de um produto da VPS (`/opt/platform/secrets/<produto>.env`) para o Infisical (projeto `rt-produtos`, ambiente `prod`, pasta `/<produto>`) **sem trocar nenhum valor** (regra R5), confere **1 a 1** e grava um relatório de evidência (só nomes, nunca valores). Não sobrescreve segredo que já existe. Sai com erro se alguma variável não bater.

Uso: `py -3 scripts/infisical/importar_env.py arenabruta`
