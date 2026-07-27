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
    { name = "logs",       type = "A", value = var.server_ip, ttl = 300 }
  ]
}

resource "local_file" "hostinger_zone" {
  filename        = "${path.module}/hostinger-zone.json"
  content         = jsonencode({ overwrite = true, zone = local.dns_records })
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
