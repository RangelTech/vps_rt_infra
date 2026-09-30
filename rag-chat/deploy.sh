#!/usr/bin/env bash
# Usage: deploy.sh <commit-or-ref>   (run on the VPS)
set -euo pipefail
REF="${1:-main}"
mkdir -p /opt/rag-chat/data
if [ ! -d /opt/rag-chat/src/.git ]; then git clone https://github.com/LucasRangelSSouza/rag-chat.git /opt/rag-chat/src; fi
git -C /opt/rag-chat/src fetch --quiet origin
git -C /opt/rag-chat/src checkout --quiet "$REF"
docker compose -f /opt/rag-chat-infra/docker-compose.yml up -d --build
git -C /opt/rag-chat/src rev-parse HEAD
