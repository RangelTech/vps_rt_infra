#!/usr/bin/env bash
# Regra do Lucas (15/11/2026): TODO tráfego de rede social sai pelo proxy SP (KingHost), não só alguns pontos.
# As redes de saída dos serviços que falam com WhatsApp/Meta/Instagram/LinkedIn/TikTok só alcançam o proxy SP;
# qualquer outro destino público é descartado. Redes privadas (Synapse, gateway, outros contêineres) seguem livres.
#   uso: aplicar-firewall.sh            (idempotente; roda no boot pela unidade rt-proxy-sp.service)
set -euo pipefail
REDES="${PROXY_SP_REDES:-canais_egress perfil-navegador_egress}"
ENV=/opt/platform/secrets/proxy-sp.env      # PROXY_SP_HOST=..., PROXY_SP_PORTA=...
[ -f "$ENV" ] || { echo "sem $ENV" >&2; exit 1; }
. "$ENV"
IP="$(getent ahostsv4 "$PROXY_SP_HOST" | awk 'NR==1{print $1}')"
[ -n "$IP" ] || { echo "não resolvi $PROXY_SP_HOST" >&2; exit 1; }
CH=RT-PROXY-SP
iptables -N "$CH" 2>/dev/null || iptables -F "$CH"
for rede in $REDES; do
  SUB="$(docker network inspect "$rede" --format '{{range .IPAM.Config}}{{.Subnet}} {{end}}' 2>/dev/null | awk '{print $1}')"
  [ -n "$SUB" ] || { echo "rede $rede não existe (ainda); pulando"; continue; }
  for priv in 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16; do iptables -A "$CH" -s "$SUB" -d "$priv" -j RETURN; done
  iptables -A "$CH" -s "$SUB" -d "$IP" -p tcp --dport "$PROXY_SP_PORTA" -j RETURN
  iptables -A "$CH" -s "$SUB" -j DROP
  echo "ok  $rede ($SUB) -> só $IP:$PROXY_SP_PORTA"
done
iptables -C DOCKER-USER -j "$CH" 2>/dev/null || iptables -I DOCKER-USER 1 -j "$CH"
