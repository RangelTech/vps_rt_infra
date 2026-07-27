#!/usr/bin/env bash
# Local helper to run terraform plan/apply against the VPS.
# Loads variables from .env (see .env.example) and terraform/terraform.tfvars.
#
# Usage:
#   ./scripts/deploy.sh plan
#   ./scripts/deploy.sh apply

set -euo pipefail

ACTION="${1:-plan}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "${ROOT_DIR}/terraform"

terraform init -upgrade

case "${ACTION}" in
  plan)
    terraform plan -var-file=terraform.tfvars
    ;;
  apply)
    terraform apply -var-file=terraform.tfvars -auto-approve
    ;;
  *)
    echo "Unknown action: ${ACTION} (expected plan|apply)" >&2
    exit 1
    ;;
esac
