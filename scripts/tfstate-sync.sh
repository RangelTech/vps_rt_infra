#!/usr/bin/env bash
# Estado do Terraform: pull/push entre o diretorio local e o Google Drive (criptografado, rclone crypt).
# Uso: tfstate-sync.sh pull|push <dir>   (RCLONE_CONFIG deve apontar para um conf com o remote gdrive-crypt)
# Trava simples: arquivo LOCK no Drive; pull falha se a trava existir (outro apply em curso).
set -euo pipefail
ACT="${1:?pull|push}"; DIR="${2:?dir}"
R="gdrive-crypt:dns"
case "$ACT" in
  pull)
    if rclone lsf "$R/LOCK" >/dev/null 2>&1; then echo "estado travado por outro apply: $(rclone cat "$R/LOCK")" >&2; exit 1; fi
    echo "${GITHUB_RUN_ID:-local}@$(date -Is)" | rclone rcat "$R/LOCK"
    rclone copyto "$R/terraform.tfstate" "$DIR/terraform.tfstate" 2>/dev/null || echo "sem estado remoto (primeira vez)"
    ;;
  push)
    [ -f "$DIR/terraform.tfstate" ] && rclone copyto "$DIR/terraform.tfstate" "$R/terraform.tfstate"
    rclone copyto "$DIR/terraform.tfstate" "$R/backup-$(date +%Y%m%d-%H%M%S).tfstate" 2>/dev/null || true
    rclone deletefile "$R/LOCK" 2>/dev/null || true
    ;;
  unlock) rclone deletefile "$R/LOCK" 2>/dev/null || true ;;
  *) echo "acao invalida" >&2; exit 2 ;;
esac
