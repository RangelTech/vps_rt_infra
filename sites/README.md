# Client static sites

Hospedagem de sites estáticos de clientes na mesma VPS `rangeltech.net`, **isolados** dos serviços principais. Cada cliente roda em container próprio (`nginx:alpine`). Dois modos, dependendo se o cliente tem domínio próprio:

| Modo | Quando usar | Domínio |
|---|---|---|
| **A — domínio próprio** | cliente já tem domínio registrado | `<dominio-do-cliente>` (ex. `clientex.com.br`) |
| **B — subdomínio RT** | cliente não tem domínio ainda | `<slug-do-cliente>.rangeltech.net` |

A diferença entre os dois modos é só **onde o DNS é gerenciado** e a regra de `Host()` do Traefik. O resto (pasta, container, TLS) é idêntico.

## Modelo

- 1 cliente = 1 pasta `sites/<slug>/public/` com os arquivos estáticos (html/css/js/assets).
- 1 cliente = 1 serviço `nginx:alpine` no [`compose/docker-compose.yml`](../compose/docker-compose.yml) (seção "Client static sites", no final do arquivo), com labels de Traefik próprias.
- TLS: automático via Let's Encrypt (HTTP-01 no entrypoint `web`), igual aos outros serviços — funciona tanto pra domínio externo quanto pra subdomínio `*.rangeltech.net`, não precisa mexer no Traefik.

## Adicionar um cliente novo

1. Criar a pasta e colocar os arquivos estáticos:
   ```
   mkdir -p sites/<slug>/public
   ```
2. Em [`compose/docker-compose.yml`](../compose/docker-compose.yml), na seção `## Client static sites ##`, copiar o bloco comentado `site-example` e ajustar `<slug>` e o `Host(...)`:

   **Modo A — domínio próprio do cliente:**
   ```yaml
     site-<slug>:
       image: nginx:alpine
       container_name: site-<slug>
       restart: unless-stopped
       volumes:
         - ../sites/<slug>/public:/usr/share/nginx/html:ro
       networks:
         - public
       labels:
         - traefik.enable=true
         - traefik.docker.network=public
         - traefik.http.routers.site-<slug>.rule=Host(`<dominio-do-cliente>`) || Host(`www.<dominio-do-cliente>`)
         - traefik.http.routers.site-<slug>.entrypoints=websecure
         - traefik.http.routers.site-<slug>.tls.certresolver=letsencrypt
         - traefik.http.routers.site-<slug>.middlewares=security-headers@file
         - traefik.http.services.site-<slug>.loadbalancer.server.port=80
   ```

   **Modo B — subdomínio `*.rangeltech.net`:**
   ```yaml
     site-<slug>:
       image: nginx:alpine
       container_name: site-<slug>
       restart: unless-stopped
       volumes:
         - ../sites/<slug>/public:/usr/share/nginx/html:ro
       networks:
         - public
       labels:
         - traefik.enable=true
         - traefik.docker.network=public
         - traefik.http.routers.site-<slug>.rule=Host(`<slug>.${ROOT_DOMAIN}`)
         - traefik.http.routers.site-<slug>.entrypoints=websecure
         - traefik.http.routers.site-<slug>.tls.certresolver=letsencrypt
         - traefik.http.routers.site-<slug>.middlewares=security-headers@file
         - traefik.http.services.site-<slug>.loadbalancer.server.port=80
   ```

3. DNS:
   - **Modo A**: garantir que o domínio do cliente tem registro `A` apontando pra `66.94.101.153` — feito pelo cliente no registrador dele (ou por nós se o domínio for gerido na nossa Hostinger, separadamente). **Fora** deste repositório, [`terraform/dns.tf`](../terraform/dns.tf) não entra aqui.
   - **Modo B**: adicionar o subdomínio em [`terraform/dns.tf`](../terraform/dns.tf) (mesmo padrão das outras entradas: `{ name = "<slug>", type = "A", value = var.server_ip, ttl = 300 }`) — esse registro é gerido por este repo, igual `grafana`/`9route`/etc.
4. Commit + push. Isso dispara `terraform-apply.yml` (a pasta `sites/**` está nos paths do workflow) — sincroniza `sites/`, o `docker-compose.yml` atualizado e (no modo B) o DNS novo, e sobe o container.
5. Validar: `https://<dominio-do-cliente>` (modo A) ou `https://<slug>.rangeltech.net` (modo B) deve responder `200` com certificado Let's Encrypt válido próprio (não confundir com wildcard).
6. Atualizar a tabela abaixo.

## Remover um cliente

1. Remover o bloco do serviço em `docker-compose.yml`.
2. Modo B: remover a entrada correspondente em `terraform/dns.tf`.
3. Remover (ou arquivar fora do repo) a pasta `sites/<slug>/`.
4. Commit + push, rodar `terraform-apply.yml` (ou `deploy-vps.yml` com `--remove-orphans`, já usado no fluxo padrão) pra derrubar o container órfão.
5. Atualizar a tabela abaixo.

## Clientes ativos

| slug | modo | domínio(s) | pasta | observações |
|---|---|---|---|---|
| _(nenhum ainda)_ | | | | |
