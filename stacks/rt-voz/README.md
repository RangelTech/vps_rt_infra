# rt-voz (túnel)

Liga a VPS ao servidor de voz `RangelTech/rt-voz`, que roda numa GPU 1x3090 da Vast (spec 44, parte 8.5).

- Produtos chamam `http://rt-voz:18010` na rede `internal` com `Authorization: Bearer $VOZ_TOKEN`.
- Segredo `/opt/platform/secrets/rt-voz.env`: `VOZ_SSH_HOST`, `VOZ_SSH_PORT`, `VOZ_SSH_KEY_B64` (a mesma chave que a fila usa na Vast), `VOZ_TOKEN`.
- Trocou a máquina da Vast: atualizar host e porta no segredo e rodar `docker compose up -d --force-recreate`.
- A GPU escuta só em 127.0.0.1; o túnel é o único caminho até ela.
