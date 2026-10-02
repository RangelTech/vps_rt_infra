locals {
  dns_records = [
    { name = "@", type = "A", value = var.server_ip, ttl = 300 },
    # Personal portfolio (lucas-rangel-portfolio), moved off the apex on 2026-10-02 so the apex can host the company site later.
    { name = "lucas", type = "A", value = var.server_ip, ttl = 300 },
    # Records below existed in the live zone but not in this file; synced from the Hostinger API on 2026-10-02.
    # Hostinger mail (MX, SPF, DKIM, DMARC, autodiscover) and the www alias of the apex.
    { name = "@", type = "MX", values = ["5 mx1.hostinger.com.", "10 mx2.hostinger.com."], ttl = 14400 },
    { name = "@", type = "TXT", value = "v=spf1 include:_spf.mail.hostinger.com ~all", ttl = 3600 },
    { name = "_dmarc", type = "TXT", value = "v=DMARC1; p=none", ttl = 3600 },
    { name = "autoconfig", type = "CNAME", value = "autoconfig.mail.hostinger.com.", ttl = 300 },
    { name = "autodiscover", type = "CNAME", value = "autodiscover.mail.hostinger.com.", ttl = 300 },
    { name = "hostingermail-a._domainkey", type = "CNAME", value = "hostingermail-a.dkim.mail.hostinger.com.", ttl = 300 },
    { name = "hostingermail-b._domainkey", type = "CNAME", value = "hostingermail-b.dkim.mail.hostinger.com.", ttl = 300 },
    { name = "hostingermail-c._domainkey", type = "CNAME", value = "hostingermail-c.dkim.mail.hostinger.com.", ttl = 300 },
    { name = "www", type = "CNAME", value = "rangeltech.net.", ttl = 300 },
    # Other services on this VPS, created outside this file.
    { name = "erp", type = "A", value = var.server_ip, ttl = 300 },
    { name = "ia-catalogo-demo", type = "A", value = var.server_ip, ttl = 300 },
    { name = "ia-educacional-demo", type = "A", value = var.server_ip, ttl = 300 },
    { name = "ia-hamburgueria-demo", type = "A", value = var.server_ip, ttl = 300 },
    { name = "ia-licita-enterprisse", type = "A", value = var.server_ip, ttl = 300 },
    { name = "ia-loja-demo", type = "A", value = var.server_ip, ttl = 300 },
    { name = "ia-smoke-cloud", type = "A", value = var.server_ip, ttl = 300 },
    { name = "pncp", type = "A", value = var.server_ip, ttl = 300 },
    { name = "qwen", type = "A", value = var.server_ip, ttl = 300 },
    # Hosts on other servers (Hostinger VPS for Coolify/n8n/Easypanel/Evolution and others).
    { name = "billion", type = "A", value = "85.208.51.111", ttl = 14400 },
    { name = "chatwoot", type = "A", value = "82.25.65.105", ttl = 300 },
    { name = "coolify", type = "A", value = "82.25.65.105", ttl = 300 },
    { name = "easypanel", type = "A", value = "82.25.65.105", ttl = 14400 },
    { name = "evolution", type = "A", value = "82.25.65.105", ttl = 14400 },
    { name = "n8n", type = "A", value = "82.25.65.105", ttl = 300 },
    { name = "pickupclub", type = "A", value = "195.88.87.245", ttl = 14400 },
    { name = "vscode", type = "A", value = "84.46.252.249", ttl = 14400 },
    # "www" is a CNAME to the apex (declared above with the mail records):
    # a name cannot carry both a CNAME and another record type.
    # Public-demo Compose profile (distributed-agent-runtime-lab, deploy/public-demo/):
    # its own isolated nginx, on the public network only for Traefik routing.
    { name = "demo", type = "A", value = var.server_ip, ttl = 300 },
    # RAG Chat public demo (portfolio repo rag-chat): its own Compose project, one Traefik router.
    { name = "rag", type = "A", value = var.server_ip, ttl = 300 },
    # BI edge: public dashboards (own nginx in front of the existing Metabase), reusable for later dashboards.
    { name = "bi", type = "A", value = var.server_ip, ttl = 300 },
    { name = "9route", type = "A", value = var.server_ip, ttl = 300 },
    { name = "grafana", type = "A", value = var.server_ip, ttl = 300 },
    { name = "storage", type = "A", value = var.server_ip, ttl = 300 },
    { name = "minio-admin", type = "A", value = var.server_ip, ttl = 300 },
    { name = "pgadmin", type = "A", value = var.server_ip, ttl = 300 },
    { name = "uptime", type = "A", value = var.server_ip, ttl = 300 },
    { name = "traefik", type = "A", value = var.server_ip, ttl = 300 },
    { name = "code", type = "A", value = var.server_ip, ttl = 300 },
    { name = "prometheus", type = "A", value = var.server_ip, ttl = 300 },
    { name = "logs", type = "A", value = var.server_ip, ttl = 300 },
    # agent-llm mega spec (infra-01): agent-platform (backend+frontend),
    # Chatwoot e a ponte migram do Cloud Run pra cá.
    { name = "ia", type = "A", value = var.server_ip, ttl = 300 },
    { name = "chat", type = "A", value = var.server_ip, ttl = 300 },
    { name = "bridge", type = "A", value = var.server_ip, ttl = 300 },
    # infra-09: Infisical self-hosted secret manager (UI + API for Machine
    # Identity / Universal Auth lookups from CI and app containers).
    { name = "infisical", type = "A", value = var.server_ip, ttl = 300 },
    # SPEC_HERMES_INTEGRADO_RIA_ATENDIMENTO.md Fase B: Hermes Relay (WSS
    # persistente por dispositivo). Servico ja deployado (apps/hermes-relay,
    # compose/docker-compose.yml) mas este registro ainda nao foi aplicado
    # de verdade -- 29/09/2026, sem HOSTINGER_API_KEY disponivel na maquina
    # que criou o servico. Aplicar via o pipeline real deste repo assim que
    # possivel; ate la o router Traefik do hermes-relay fica inerte.
    { name = "hermes-relay", type = "A", value = var.server_ip, ttl = 300 },
    # produto-05 seção 4: 1 registro coringa só, cadastrado uma vez — cada
    # container Evolution por tenant sobe com label Traefik
    # Host(`evolution-<tenant_id>.evolution.rangeltech.net`), sem precisar
    # de registro DNS novo a cada tenant provisionado.
    { name = "*.evolution", type = "A", value = var.server_ip, ttl = 300 },
    # Verificação de domínio pro app TikTok Developers (RAtende), 25/08/2026 —
    # exigido pra aceitar as URLs de Termos/Política sob ia.rangeltech.net.
    { name = "ia", type = "TXT", value = "tiktok-developers-site-verification=IctaIyx7EzE65hXP66TM9xFIrXR7oDl9", ttl = 300 },
    # Mesma verificação, agora pro domínio do Chatwoot em si
    # (chat.rangeltech.net) — exigido pro redirect URI do Login Kit.
    { name = "chat", type = "TXT", value = "tiktok-developers-site-verification=9VCnh82QgEEOLPsmWXeQREModQPcfma0", ttl = 300 }
  ]
}

resource "local_file" "hostinger_zone" {
  filename = "${path.module}/hostinger-zone.json"
  # overwrite = true replaces only the records whose name and type match an
  # entry here; anything else in the zone stays. This list mirrors the full
  # live zone anyway, so the file is the source of truth for every record.
  content = jsonencode({
    overwrite = true
    zone = [
      for record in local.dns_records : {
        name    = record.name
        type    = record.type
        ttl     = record.ttl
        records = [for value in try(record.values, [record.value]) : { content = value }]
      }
    ]
  })
  file_permission = "0600"
}

resource "null_resource" "hostinger_dns" {
  triggers = {
    zone_sha  = local_file.hostinger_zone.content_sha256
    domain    = var.root_domain
    server_ip = var.server_ip
  }

  provisioner "local-exec" {
    command = "bash ../scripts/hostinger_dns.sh '${var.root_domain}' '${var.hostinger_api_key}' '${local_file.hostinger_zone.filename}'"
  }
}
