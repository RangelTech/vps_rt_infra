#!/usr/bin/env bash
# Instala rclone (versao fixada, checksum verificado) e garante restic. Idempotente. Roda como root.
set -euo pipefail
RCLONE_VERSION="${RCLONE_VERSION:-v1.74.4}"
if command -v rclone >/dev/null 2>&1 && rclone version | head -1 | grep -q "${RCLONE_VERSION#v}"; then
  echo "rclone ${RCLONE_VERSION} ja instalado"
else
  tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
  base="https://downloads.rclone.org/${RCLONE_VERSION}"
  curl -fsSL -o "$tmp/rclone.zip" "${base}/rclone-${RCLONE_VERSION}-linux-amd64.zip"
  curl -fsSL -o "$tmp/SHA256SUMS" "${base}/SHA256SUMS"
  ( cd "$tmp" && grep " rclone-${RCLONE_VERSION}-linux-amd64.zip\$" SHA256SUMS | sed "s# rclone-.*# rclone.zip#" | sha256sum -c - )
  apt-get install -y -qq unzip >/dev/null
  unzip -q -o "$tmp/rclone.zip" -d "$tmp"
  install -m 0755 "$tmp/rclone-${RCLONE_VERSION}-linux-amd64/rclone" /usr/local/bin/rclone
fi
command -v restic >/dev/null 2>&1 || apt-get install -y -qq restic
install -d -m 0700 -o deploy -g deploy /opt/platform/secrets
rclone version | head -1; restic version | head -1
