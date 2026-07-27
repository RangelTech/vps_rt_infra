variable "server_ip" {
  description = "Public IPv4 of the Contabo VPS"
  type        = string
  default     = "66.94.101.153"
}

variable "server_ipv6" {
  description = "Primary IPv6 or subnet label for documentation"
  type        = string
  default     = "2605:a144:2346:8840:0000:0000:0000:0001/64"
}

variable "root_domain" {
  description = "Base domain used by the reverse proxy"
  type        = string
  default     = "rangeltech.net"
}

variable "ssh_port" {
  description = "SSH port exposed by the VPS"
  type        = number
  default     = 22
}

variable "initial_ssh_user" {
  description = "Bootstrap SSH user available before provisioning"
  type        = string
  default     = "root"
}

variable "initial_ssh_password" {
  description = "Bootstrap SSH password used only for the first provisioning"
  type        = string
  sensitive   = true
}

variable "deploy_user" {
  description = "Non-root deploy user created during bootstrap"
  type        = string
  default     = "deploy"
}

variable "public_ssh_key" {
  description = "Public key allowed to access the deploy user"
  type        = string
}

variable "ssh_private_key_path" {
  description = "Local path to the private key matching public_ssh_key, used by Terraform to connect as deploy_user after bootstrap"
  type        = string
  default     = "~/.ssh/vps_rt_infra_ed25519"
}

variable "hostinger_api_key" {
  description = "Hostinger API key for DNS record management"
  type        = string
  sensitive   = true
}

variable "letsencrypt_email" {
  description = "Email used for Let's Encrypt ACME registration"
  type        = string
  default     = "lucas.rangel@outlook.com"
}

variable "timezone" {
  description = "System timezone"
  type        = string
  default     = "America/Sao_Paulo"
}

variable "postgres_db" {
  type    = string
  default = "platform"
}

variable "postgres_admin_user" {
  type    = string
  default = "platform_admin"
}

variable "postgres_admin_password" {
  type      = string
  sensitive = true
}

variable "pgbouncer_admin_user" {
  type    = string
  default = "pgbouncer_admin"
}

variable "pgbouncer_admin_password" {
  type      = string
  sensitive = true
}

variable "redis_password" {
  type      = string
  sensitive = true
}

variable "minio_root_user" {
  type    = string
  default = "minioadmin"
}

variable "minio_root_password" {
  type      = string
  sensitive = true
}

variable "pgadmin_email" {
  type    = string
  default = "lucas.rangel@outlook.com"
}

variable "pgadmin_password" {
  type      = string
  sensitive = true
}

variable "grafana_admin_user" {
  type    = string
  default = "admin"
}

variable "grafana_admin_password" {
  type      = string
  sensitive = true
}

variable "uptime_kuma_user" {
  type    = string
  default = "admin"
}

variable "uptime_kuma_password" {
  type      = string
  sensitive = true
}

variable "traefik_basic_auth" {
  description = "Basic auth line in htpasswd format for Traefik-protected admin routes"
  type        = string
  sensitive   = true
}

variable "ninerouter_package" {
  description = "NPM package to install for 9router"
  type        = string
  default     = "9router@0.5.40"
}

variable "ninerouter_port" {
  description = "Internal port exposed by the 9router container"
  type        = number
  default     = 20128
}

variable "restic_repository" {
  description = "External backup repository URL"
  type        = string
  default     = ""
}

variable "restic_password" {
  description = "Password for the Restic repository"
  type        = string
  sensitive   = true
  default     = ""
}

variable "restic_environment" {
  description = "Additional env vars for restic backend auth"
  type        = map(string)
  default     = {}
}
