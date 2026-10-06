#!/usr/bin/env bash
# Roda na VPS. Uso: AIRFLOW_ADMIN_PASSWORD=... deploy.sh
# Na primeira execucao gera /opt/airflow/.env com os segredos; nas seguintes so reaproveita.
set -euo pipefail
ENV_FILE=/opt/airflow/.env
INFRA=/opt/airflow-infra

if [ ! -f "$ENV_FILE" ]; then
  : "${AIRFLOW_ADMIN_PASSWORD:?primeira execucao precisa de AIRFLOW_ADMIN_PASSWORD}"
  sudo mkdir -p /opt/airflow && sudo chown "$(id -un):$(id -gn)" /opt/airflow
  umask 077
  {
    echo "POSTGRES_PASSWORD=$(openssl rand -hex 24)"
    echo "AIRFLOW_FERNET_KEY=$(openssl rand 32 | base64 | tr '+/' '-_')"
    echo "AIRFLOW_SECRET_KEY=$(openssl rand -hex 32)"
    echo "AIRFLOW_ADMIN_PASSWORD=$AIRFLOW_ADMIN_PASSWORD"
  } > "$ENV_FILE"
  echo "Gerado $ENV_FILE"
fi

docker compose --env-file "$ENV_FILE" -f "$INFRA/docker-compose.yml" up -d --build
docker compose --env-file "$ENV_FILE" -f "$INFRA/docker-compose.yml" ps
