# Registros que já existiam na Hostinger antes de entrar no estado (drift achado em 25/11/2026: o apply falhava desde 16/11
# tentando criar o "qwen" de novo). O import é idempotente: depois de importado, não faz mais nada.
import {
  to = hostinger_dns_record.r["qwen|A"]
  id = "qwen|A|66.94.101.153"
}
