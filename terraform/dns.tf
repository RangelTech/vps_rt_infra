locals {
  dns_records = [
    { name = "@",          type = "A", value = var.server_ip, ttl = 300 },
    { name = "9route",     type = "A", value = var.server_ip, ttl = 300 },
    { name = "grafana",    type = "A", value = var.server_ip, ttl = 300 },
    { name = "storage",    type = "A", value = var.server_ip, ttl = 300 },
    { name = "minio-admin", type = "A", value = var.server_ip, ttl = 300 },
    { name = "pgadmin",    type = "A", value = var.server_ip, ttl = 300 },
    { name = "uptime",     type = "A", value = var.server_ip, ttl = 300 },
    { name = "traefik",    type = "A", value = var.server_ip, ttl = 300 },
    { name = "code",       type = "A", value = var.server_ip, ttl = 300 },
    { name = "prometheus", type = "A", value = var.server_ip, ttl = 300 },
    { name = "logs",       type = "A", value = var.server_ip, ttl = 300 },
    # agent-llm mega spec (infra-01): agent-platform (backend+frontend),
    # Chatwoot e a ponte migram do Cloud Run pra cá.
    { name = "ia",         type = "A", value = var.server_ip, ttl = 300 },
    { name = "chat",       type = "A", value = var.server_ip, ttl = 300 },
    { name = "bridge",     type = "A", value = var.server_ip, ttl = 300 },
    # infra-09: Infisical self-hosted secret manager (UI + API for Machine
    # Identity / Universal Auth lookups from CI and app containers).
    { name = "infisical",  type = "A", value = var.server_ip, ttl = 300 },
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
  filename        = "${path.module}/hostinger-zone.json"
  content = jsonencode({
    overwrite = true
    zone = [
      for record in local.dns_records : {
        name    = record.name
        type    = record.type
        ttl     = record.ttl
        records = [{ content = record.value }]
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
