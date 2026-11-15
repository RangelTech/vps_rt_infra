# Registros GERENCIADOS pelo Terraform (todos de valor unico). Gerado a partir da zona real em 17/10/2026.
# NAO gerenciados (e-mail, nunca tocar): MX, SPF (@ TXT), _dmarc, autoconfig, autodiscover, hostingermail-*._domainkey.
locals {
  records = {
    "*.evolution|A"  = { name = "*.evolution", type = "A", ttl = 300, value = var.vps_ip }
    "*.apps|A"       = { name = "*.apps", type = "A", ttl = 300, value = var.vps_ip }
    "@|A"            = { name = "@", type = "A", ttl = 300, value = var.vps_ip }
    "ai|A"           = { name = "ai", type = "A", ttl = 300, value = var.vps_ip }
    "airflow|A"      = { name = "airflow", type = "A", ttl = 300, value = var.vps_ip }
    "bi|A"           = { name = "bi", type = "A", ttl = 300, value = var.vps_ip }
    "bridge|A"       = { name = "bridge", type = "A", ttl = 300, value = var.vps_ip }
    "chat|A"         = { name = "chat", type = "A", ttl = 300, value = var.vps_ip }
    "demo|A"         = { name = "demo", type = "A", ttl = 300, value = var.vps_ip }
    "ia|A"           = { name = "ia", type = "A", ttl = 300, value = var.vps_ip }
    "infisical|A"    = { name = "infisical", type = "A", ttl = 300, value = var.vps_ip }
    "metricas|A"     = { name = "metricas", type = "A", ttl = 300, value = var.vps_ip }
    "user|A"         = { name = "user", type = "A", ttl = 300, value = var.vps_ip }
    "turn|A"         = { name = "turn", type = "A", ttl = 300, value = var.vps_ip }
    "luar|A"         = { name = "luar", type = "A", ttl = 300, value = var.vps_ip }
    "brain|A"        = { name = "brain", type = "A", ttl = 300, value = var.vps_ip }
    "remoto|A"       = { name = "remoto", type = "A", ttl = 300, value = var.vps_ip }
    "cortai|A"       = { name = "cortai", type = "A", ttl = 300, value = var.vps_ip }
    "anima-ai|A"     = { name = "anima-ai", type = "A", ttl = 300, value = var.vps_ip }
    "atende-ai|A" = { name = "atende-ai", type = "A", ttl = 300, value = var.vps_ip }
    "atende-whats|A" = { name = "atende-whats", type = "A", ttl = 300, value = var.vps_ip }
    "atende-insta|A" = { name = "atende-insta", type = "A", ttl = 300, value = var.vps_ip }
    "atende-tiktok|A" = { name = "atende-tiktok", type = "A", ttl = 300, value = var.vps_ip }
    "atende-face|A" = { name = "atende-face", type = "A", ttl = 300, value = var.vps_ip }
    "rendai|A"       = { name = "rendai", type = "A", ttl = 300, value = var.vps_ip }
    "perfilai|A"     = { name = "perfilai", type = "A", ttl = 300, value = var.vps_ip }
    "insta-ai|A"      = { name = "insta-ai", type = "A", ttl = 300, value = var.vps_ip }
    "face-ai|A"       = { name = "face-ai", type = "A", ttl = 300, value = var.vps_ip }
    "tittok-ai|A"     = { name = "tittok-ai", type = "A", ttl = 300, value = var.vps_ip }
    "linkdn-ai|A"     = { name = "linkdn-ai", type = "A", ttl = 300, value = var.vps_ip }
    "gw|A"           = { name = "gw", type = "A", ttl = 300, value = var.vps_ip }
    "qwen|A"         = { name = "qwen", type = "A", ttl = 300, value = var.vps_ip }
    "conector|A"     = { name = "conector", type = "A", ttl = 300, value = var.vps_ip }
    "lucas|A"        = { name = "lucas", type = "A", ttl = 300, value = var.vps_ip }
    "minio-admin|A"  = { name = "minio-admin", type = "A", ttl = 300, value = var.vps_ip }
    "rag|A"          = { name = "rag", type = "A", ttl = 300, value = var.vps_ip }
    "storage|A"      = { name = "storage", type = "A", ttl = 300, value = var.vps_ip }
    "traefik|A"      = { name = "traefik", type = "A", ttl = 300, value = var.vps_ip }
    "uptime|A"       = { name = "uptime", type = "A", ttl = 300, value = var.vps_ip }
    "www|CNAME"      = { name = "www", type = "CNAME", ttl = 300, value = "rangeltech.net." }
    "chat|TXT"       = { name = "chat", type = "TXT", ttl = 300, value = "\"tiktok-developers-site-verification=9VCnh82QgEEOLPsmWXeQREModQPcfma0\"" }
    "ia|TXT"         = { name = "ia", type = "TXT", ttl = 300, value = "\"tiktok-developers-site-verification=IctaIyx7EzE65hXP66TM9xFIrXR7oDl9\"" }
  }
}
