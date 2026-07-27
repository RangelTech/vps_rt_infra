#!/usr/bin/env bash
# Bootstrap script for the Contabo VPS (Ubuntu 24.04 LTS).
# Executed once as root by Terraform (null_resource.bootstrap) via SSH.
# Idempotent: safe to re-run.
#
# Expected environment variables (passed inline by Terraform):
#   DEPLOY_USER      - non-root user that will own /opt/platform and run docker compose
#   PUBLIC_SSH_KEY   - public key authorized for DEPLOY_USER
#   TIMEZONE         - system timezone, e.g. America/Sao_Paulo
#   REMOTE_BASE_DIR  - base directory for the stack, e.g. /opt/platform

set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-deploy}"
PUBLIC_SSH_KEY="${PUBLIC_SSH_KEY:?PUBLIC_SSH_KEY is required}"
TIMEZONE="${TIMEZONE:-America/Sao_Paulo}"
REMOTE_BASE_DIR="${REMOTE_BASE_DIR:-/opt/platform}"

echo "==> [1/9] Updating system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get upgrade -y

echo "==> [2/9] Setting timezone to ${TIMEZONE}"
timedatectl set-timezone "${TIMEZONE}" || true

echo "==> [3/9] Installing base packages"
apt-get install -y \
  ca-certificates \
  curl \
  gnupg \
  lsb-release \
  ufw \
  fail2ban \
  unattended-upgrades \
  git \
  htop \
  jq \
  restic

echo "==> [4/9] Installing Docker Engine + Compose plugin"
if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "${VERSION_CODENAME}") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable docker
systemctl start docker

echo "==> [5/9] Creating deploy user"
if ! id -u "${DEPLOY_USER}" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "${DEPLOY_USER}"
  usermod -aG sudo "${DEPLOY_USER}"
  usermod -aG docker "${DEPLOY_USER}"
fi
mkdir -p "/home/${DEPLOY_USER}/.ssh"
echo "${PUBLIC_SSH_KEY}" > "/home/${DEPLOY_USER}/.ssh/authorized_keys"
chmod 700 "/home/${DEPLOY_USER}/.ssh"
chmod 600 "/home/${DEPLOY_USER}/.ssh/authorized_keys"
chown -R "${DEPLOY_USER}:${DEPLOY_USER}" "/home/${DEPLOY_USER}/.ssh"
echo "${DEPLOY_USER} ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/90-${DEPLOY_USER}"
chmod 440 "/etc/sudoers.d/90-${DEPLOY_USER}"

echo "==> [6/9] Hardening SSH (key-only, no root login)"
SSHD_CONFIG=/etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' "${SSHD_CONFIG}"
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin prohibit-password/' "${SSHD_CONFIG}"
sed -i 's/^#\?ChallengeResponseAuthentication.*/ChallengeResponseAuthentication no/' "${SSHD_CONFIG}"
systemctl restart ssh

echo "==> [7/9] Configuring firewall (ufw)"
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "==> [8/9] Enabling fail2ban for sshd"
cat > /etc/fail2ban/jail.d/sshd.local <<'EOF'
[sshd]
enabled = true
port    = ssh
maxretry = 5
bantime  = 1h
findtime = 10m
EOF
systemctl enable fail2ban
systemctl restart fail2ban

echo "==> [9/9] Creating base directory structure"
mkdir -p "${REMOTE_BASE_DIR}"/{compose,configs,apps,scripts,data}
chown -R "${DEPLOY_USER}:${DEPLOY_USER}" "${REMOTE_BASE_DIR}"

echo "==> Bootstrap finished successfully."
