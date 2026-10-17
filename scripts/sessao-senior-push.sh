#!/usr/bin/env bash
# Publica a sessao renovada do Senior (volume do Airflow) no repo privado airflow-pessoal. Acionado via SSH restrito (usuario rtsession).
set -euo pipefail
[ "$(hostname)" = "vmi3468840" ] || exit 2
SRC=/var/lib/docker/volumes/airflow_airflow-state/_data/estado_senior.json
W=/opt/platform/data/sessao-senior-repo
export GIT_SSH_COMMAND="ssh -i /opt/platform/secrets/airflow_pessoal_deploy_key -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/opt/platform/secrets/gh_known_hosts"
[ -d "$W/.git" ] || git clone -q git@github.com:LucasRangelSSouza/airflow-pessoal.git "$W"
cd "$W"; git pull -q --rebase origin main
python3 -c "import json;json.load(open('$SRC'))"
cp "$SRC" dags/estado_senior.json
if git diff --quiet; then echo "sessao inalterada"; exit 0; fi
git -c user.name=rt-vps -c user.email=rt-vps@users.noreply.github.com commit -qam "sessao senior renovada $(date +%F)"
git push -q origin HEAD:main && echo "sessao publicada"
