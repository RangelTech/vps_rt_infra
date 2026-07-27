output "server_ip" {
  value = var.server_ip
}

output "root_domain" {
  value = var.root_domain
}

output "public_urls" {
  value = {
    ninerouter   = "https://9route.${var.root_domain}"
    grafana      = "https://grafana.${var.root_domain}"
    storage      = "https://storage.${var.root_domain}"
    minio_admin  = "https://minio-admin.${var.root_domain}"
    pgadmin      = "https://pgadmin.${var.root_domain}"
    uptime       = "https://uptime.${var.root_domain}"
    traefik      = "https://traefik.${var.root_domain}"
  }
}
