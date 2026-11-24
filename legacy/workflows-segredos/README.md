# Workflows antigos que gravavam segredos direto na VPS (desligados em 24/11/2026)

Estes workflows escreviam `/opt/platform/secrets/*.env` direto na VPS (alguns geravam o valor lá mesmo). Desde a spec 57
(seção 0A) a **fonte oficial dos segredos é o Infisical** e o `deploy.yml` gera os `.env` a partir dele no momento do deploy.
Se estes workflows continuassem ativos, um valor gravado só na VPS seria desfeito no próximo deploy.

**Para mudar um segredo agora:** altere no Infisical (projeto/pasta do serviço, ver `scripts/infisical/mapa_envs.json`) e rode
`gh workflow run deploy.yml -f service=<servico> -f version=<versao atual>`. Nunca troque credencial sem ordem (regra R5).

Ficam aqui só como histórico (fora de `.github/workflows`, não rodam).
