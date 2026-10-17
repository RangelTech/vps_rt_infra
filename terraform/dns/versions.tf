terraform {
  required_version = ">= 1.9.0"
  required_providers {
    hostinger = {
      source  = "hostinger/hostinger"
      version = "~> 0.1.23"
    }
  }
}
