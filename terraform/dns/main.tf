# DNS da Rangel Tech (Hostinger). Terraform gerencia SO o que esta em records.tf.
# Estado: local + sincronizado com o Google Drive (criptografado) por scripts/tfstate-sync.sh. Nunca no Git.
provider "hostinger" {
  api_token = var.hostinger_api_token
}

resource "hostinger_dns_record" "r" {
  for_each = local.records

  zone  = var.zone
  name  = each.value.name
  type  = each.value.type
  ttl   = each.value.ttl
  value = each.value.value
}
