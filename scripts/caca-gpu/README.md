# Caça-GPU (GPU do Qwen sempre no ar e cada vez mais barata)

Roda na VPS, no cron do usuário `deploy`, de minuto em minuto:

```
* * * * * /usr/bin/flock -n /home/deploy/caca-gpu/.trava /usr/bin/python3 /home/deploy/caca-gpu/caca.py >/dev/null 2>&1
```

Arquivos em `/home/deploy/caca-gpu/`: `caca.py` (este), `start_vllm.sh` (cópia de `queue/remote/start_vllm.sh` do
qwen-abliterated-api), `chave` (SSH das instâncias da Vast, 600), `config.json`, `estado.json` e `caca.log`.

`config.json`: `{"email": "<e-mail do Lucas>", "margem": 0.01, "antiga": 60855119, "max_candidatas": 2, "min_tok_s": 15}`.

## O que ele faz

1. **Procura sempre** uma 2x RTX 3090 (ou Ti), CUDA 13 ou mais, aluguel fixo, disco de 60 GB ou mais, internet de 300 Mbps ou mais.
   O preço comparado é aluguel + 50 GB de disco. Se achar uma mais barata (por `margem`) que a mais barata que já temos, aluga
   na hora. No máximo `max_candidatas` em teste ao mesmo tempo.
2. **Testa sozinho** cada candidata: quando liga, entra por SSH, baixa o modelo, sobe o vLLM com o `start_vllm.sh` da produção e
   faz as provas (saúde, resposta curta, chamada de ferramenta e velocidade de pelo menos `min_tok_s`). Se não ligar em 35 min,
   der "no space", ficar ligada 8 min sem aceitar a nossa chave SSH ou falhar numa prova, a candidata é destruída e a máquina
   vai para a lista negra. Fora da emergência, candidata mais cara que a fixa é destruída.
3. **Troca só de madrugada** (00h às 06h de Brasília): a candidata pronta mais barata vira a fixa (`GPU_STATIC_INSTANCE_ID` +
   recriar o `llm-queue`). Uma conversa real pela fila é conferida e **só então** a fixa anterior é destruída. Se a conversa
   não passar em 10 min, ele volta para a anterior.
4. **Emergência** (a qualquer hora): se a fixa ficar offline ou parada por mais de 5 min, ele troca na hora pela candidata
   pronta mais barata. Se não houver, aluga as 2 mais baratas que existirem (mesmo mais caras), testa as duas ao mesmo tempo e
   troca pela primeira que passar; a outra, mais cara, é destruída. Medido em 22/11/2026: Quebec caiu às 01:30, a troca de
   emergência terminou às 02:52, e os clientes foram atendidos pelo Claude/GPT nesse meio tempo. A fixa que caiu **não é destruída**: fica guardada como candidata e, se voltar e for mais barata, é testada e
   volta na madrugada.
5. A máquina antiga do Brasil (`antiga`) nunca é destruída. Se voltar a rodar, vira candidata.

Cada aluguel, aprovação, troca, falha ou queda gera um e-mail (SMTP do llm-access).

## Junto com isto

- No llm-access (desde a v0.5.65), se o `llm-queue` disser que a GPU está degradada, o pedido do cliente vai para o
  Claude/GPT barato do rodízio em vez de esperar a GPU. Voz e chat não ficam mudos durante a troca.
- Para trocar à mão: `sudo sed -i "s/^GPU_STATIC_INSTANCE_ID=.*/GPU_STATIC_INSTANCE_ID=<id>/" /opt/platform/secrets/llm-queue.env`
  e `cd /opt/platform/stacks/llm-queue && sudo docker compose --env-file .release.env up -d --force-recreate`.
