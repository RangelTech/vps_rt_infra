#!/usr/bin/env bash
# Updates DNS records for a domain using the Hostinger API.
#
# Usage: hostinger_dns.sh <domain> <api_key> <zone_json_file>
#
# zone_json_file must contain: {"overwrite": true, "zone": [{"name":"@","type":"A","value":"1.2.3.4","ttl":300}, ...]}
#
# API reference: POST https://developers.hostinger.com/v1/dns-zone/{domain}
# Auth: Authorization: Bearer <api_key>

set -euo pipefail

DOMAIN="${1:?Usage: hostinger_dns.sh <domain> <api_key> <zone_json_file>}"
API_KEY="${2:?Usage: hostinger_dns.sh <domain> <api_key> <zone_json_file>}"
ZONE_FILE="${3:?Usage: hostinger_dns.sh <domain> <api_key> <zone_json_file>}"

if [ ! -f "${ZONE_FILE}" ]; then
  echo "Zone file not found: ${ZONE_FILE}" >&2
  exit 1
fi

echo "==> Updating DNS zone for ${DOMAIN} via Hostinger API"

response=$(curl -sS -w '\n%{http_code}' -X POST \
  "https://developers.hostinger.com/v1/dns-zone/${DOMAIN}" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  --data @"${ZONE_FILE}")

http_code=$(echo "${response}" | tail -n1)
body=$(echo "${response}" | sed '$d')

echo "${body}"

if [ "${http_code}" -ge 200 ] && [ "${http_code}" -lt 300 ]; then
  echo "==> DNS zone updated successfully (HTTP ${http_code})"
else
  echo "==> Failed to update DNS zone (HTTP ${http_code})" >&2
  exit 1
fi
