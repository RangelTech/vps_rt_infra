variable "hostinger_api_token" {
  type      = string
  sensitive = true
}

variable "zone" {
  type    = string
  default = "rangeltech.net"
}

variable "vps_ip" {
  type    = string
  default = "66.94.101.153"
}
