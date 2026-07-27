#!/usr/bin/env python3
"""Bootstrap GitHub Actions secrets for the vps_rt_infra repository.

This script:
1. loads local source credentials from ../secrets in the parent workspace;
2. generates strong service passwords when needed;
3. builds a repository-local terraform.tfvars file;
4. encrypts and uploads GitHub Actions secrets through the GitHub REST API.

Required environment variables:
- GITHUB_TOKEN: classic PAT with repo scope

Optional environment variables:
- GITHUB_OWNER (default: LucasRangelSSouza)
- GITHUB_REPO (default: vps_rt_infra)
- VPS_INFRA_DIR (default: repo root inferred from this file)
- SECRETS_DIR (default: ../secrets relative to workspace root)
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import string
from pathlib import Path
from typing import Dict, Any

import bcrypt
import requests
from nacl import encoding, public

OWNER = os.environ.get("GITHUB_OWNER", "LucasRangelSSouza")
REPO = os.environ.get("GITHUB_REPO", "vps_rt_infra")
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(os.environ.get("VPS_INFRA_DIR", SCRIPT_DIR.parent))
WORKSPACE_ROOT = REPO_ROOT.parent
SECRETS_DIR = Path(os.environ.get("SECRETS_DIR", WORKSPACE_ROOT / "secrets"))
TFVARS_PATH = REPO_ROOT / "terraform" / "terraform.tfvars"
SSH_PUBLIC_KEY_PATH = Path(os.environ.get("VPS_SSH_PUBLIC_KEY_PATH", Path.home() / ".ssh" / "vps_rt_infra_ed25519.pub"))
SSH_PRIVATE_KEY_PATH = Path(os.environ.get("VPS_SSH_PRIVATE_KEY_PATH", Path.home() / ".ssh" / "vps_rt_infra_ed25519"))

API_ROOT = f"https://api.github.com/repos/{OWNER}/{REPO}"
ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
TIMEZONE = "America/Sao_Paulo"
ROOT_DOMAIN = "rangeltech.net"


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def random_password(length: int = 28) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def bcrypt_htpasswd(username: str, password: str) -> str:
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    return f"{username}:{hashed}"


def read_required_file(path: Path, label: str) -> str:
    if not path.exists():
        raise SystemExit(f"Required file not found for {label}: {path}")
    return path.read_text(encoding="utf-8").strip()


def build_secret_values() -> Dict[str, str]:
    contabo = load_json(SECRETS_DIR / "contabo-vps.json")
    hostinger = load_json(SECRETS_DIR / "api_key_hostinger.json")

    github_token = require_env("GITHUB_TOKEN")
    _ = github_token  # explicit required check for clearer failure mode

    ssh_public_key = read_required_file(SSH_PUBLIC_KEY_PATH, "public ssh key")
    ssh_private_key = read_required_file(SSH_PRIVATE_KEY_PATH, "private ssh key")

    traefik_admin_password = random_password()

    values = {
        "VPS_HOST": contabo["ssh"]["host"],
        "VPS_DEPLOY_USER": "deploy",
        "VPS_SSH_PRIVATE_KEY": ssh_private_key,
        "VPS_INITIAL_SSH_PASSWORD": contabo["ssh"]["password"],
        "VPS_PUBLIC_SSH_KEY": ssh_public_key,
        "HOSTINGER_API_KEY": hostinger["api_key"],
        "POSTGRES_ADMIN_PASSWORD": random_password(),
        "PGBOUNCER_ADMIN_PASSWORD": random_password(),
        "REDIS_PASSWORD": random_password(),
        "MINIO_ROOT_PASSWORD": random_password(),
        "PGADMIN_PASSWORD": random_password(),
        "GRAFANA_ADMIN_PASSWORD": random_password(),
        "UPTIME_KUMA_PASSWORD": random_password(),
        "TRAEFIK_BASIC_AUTH": bcrypt_htpasswd("admin", traefik_admin_password),
        "CODE_SERVER_PASSWORD": random_password(),
        "CODE_SERVER_SUDO_PASSWORD": random_password(),
        "RESTIC_REPOSITORY": "s3:https://s3.us-east-1.amazonaws.com/your-backup-bucket/vps-rt",
        "RESTIC_PASSWORD": random_password(),
        "TRAEFIK_BASIC_AUTH_PASSWORD": traefik_admin_password,
    }
    return values


def build_tfvars(values: Dict[str, str]) -> str:
    public_key = values["VPS_PUBLIC_SSH_KEY"].replace("\n", " ").strip()
    lines = [
        f'server_ip                = "{values["VPS_HOST"]}"',
        'server_ipv6              = "2605:a144:2346:8840:0000:0000:0000:0001/64"',
        f'root_domain              = "{ROOT_DOMAIN}"',
        'ssh_port                 = 22',
        'initial_ssh_user         = "root"',
        f'initial_ssh_password     = "{escape_hcl(values["VPS_INITIAL_SSH_PASSWORD"])}"',
        'deploy_user              = "deploy"',
        f'public_ssh_key           = "{escape_hcl(public_key)}"',
        f'hostinger_api_key        = "{escape_hcl(values["HOSTINGER_API_KEY"])}"',
        'letsencrypt_email        = "lucas.rangel@outlook.com"',
        f'timezone                 = "{TIMEZONE}"',
        '',
        'traefik_version          = "3.1"',
        'postgres_version         = "16.4"',
        'pgbouncer_version        = "1.21.0"',
        'redis_version            = "7.4"',
        'minio_version            = "RELEASE.2024-10-13T13-34-11Z"',
        'pgadmin_version          = "8.12"',
        'grafana_version          = "11.2.0"',
        'uptime_kuma_version      = "1.23.13"',
        'code_server_version      = "4.103.2"',
        'prometheus_version       = "v2.54.1"',
        'loki_version             = "3.1.1"',
        'promtail_version         = "3.1.1"',
        'node_exporter_version    = "v1.8.2"',
        'cadvisor_version         = "v0.49.1"',
        '',
        'postgres_db              = "platform"',
        'postgres_admin_user      = "platform_admin"',
        f'postgres_admin_password  = "{escape_hcl(values["POSTGRES_ADMIN_PASSWORD"])}"',
        'pgbouncer_admin_user     = "pgbouncer_admin"',
        f'pgbouncer_admin_password = "{escape_hcl(values["PGBOUNCER_ADMIN_PASSWORD"])}"',
        f'redis_password           = "{escape_hcl(values["REDIS_PASSWORD"])}"',
        'minio_root_user          = "minioadmin"',
        f'minio_root_password      = "{escape_hcl(values["MINIO_ROOT_PASSWORD"])}"',
        'pgadmin_email            = "lucas.rangel@outlook.com"',
        f'pgadmin_password         = "{escape_hcl(values["PGADMIN_PASSWORD"])}"',
        'grafana_admin_user       = "admin"',
        f'grafana_admin_password   = "{escape_hcl(values["GRAFANA_ADMIN_PASSWORD"])}"',
        'uptime_kuma_user         = "admin"',
        f'uptime_kuma_password     = "{escape_hcl(values["UPTIME_KUMA_PASSWORD"])}"',
        f'traefik_basic_auth       = "{escape_hcl(values["TRAEFIK_BASIC_AUTH"])}"',
        f'code_server_password     = "{escape_hcl(values["CODE_SERVER_PASSWORD"])}"',
        f'code_server_sudo_password = "{escape_hcl(values["CODE_SERVER_SUDO_PASSWORD"])}"',
        '',
        'ninerouter_package       = "9router@0.5.40"',
        'ninerouter_port          = 20128',
        '',
        f'restic_repository        = "{escape_hcl(values["RESTIC_REPOSITORY"])}"',
        f'restic_password          = "{escape_hcl(values["RESTIC_PASSWORD"])}"',
        'restic_environment = {',
        '  AWS_ACCESS_KEY_ID     = "CHANGE_ME"',
        '  AWS_SECRET_ACCESS_KEY = "CHANGE_ME"',
        '}',
        '',
        '# Convenience only: the plain admin password behind TRAEFIK_BASIC_AUTH is',
        f'# {values["TRAEFIK_BASIC_AUTH_PASSWORD"]}',
    ]
    return "\n".join(lines) + "\n"


def escape_hcl(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def github_headers(token: str) -> Dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_repo_public_key(token: str) -> Dict[str, str]:
    response = requests.get(f"{API_ROOT}/actions/secrets/public-key", headers=github_headers(token), timeout=30)
    response.raise_for_status()
    return response.json()


def encrypt_secret(public_key_b64: str, secret_value: str) -> str:
    public_key_bytes = base64.b64decode(public_key_b64)
    public_key = public.PublicKey(public_key_bytes)
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def put_secret(token: str, key_id: str, public_key_b64: str, name: str, value: str) -> None:
    encrypted_value = encrypt_secret(public_key_b64, value)
    payload = {"encrypted_value": encrypted_value, "key_id": key_id}
    response = requests.put(
        f"{API_ROOT}/actions/secrets/{name}",
        headers=github_headers(token),
        json=payload,
        timeout=30,
    )
    response.raise_for_status()


def main() -> None:
    token = require_env("GITHUB_TOKEN")
    values = build_secret_values()

    TFVARS_PATH.write_text(build_tfvars(values), encoding="utf-8")
    print(f"Wrote {TFVARS_PATH}")

    public_key_meta = get_repo_public_key(token)
    key_id = public_key_meta["key_id"]
    public_key_b64 = public_key_meta["key"]

    upload_names = [
        "VPS_HOST",
        "VPS_DEPLOY_USER",
        "VPS_SSH_PRIVATE_KEY",
        "VPS_INITIAL_SSH_PASSWORD",
        "VPS_PUBLIC_SSH_KEY",
        "HOSTINGER_API_KEY",
        "POSTGRES_ADMIN_PASSWORD",
        "PGBOUNCER_ADMIN_PASSWORD",
        "REDIS_PASSWORD",
        "MINIO_ROOT_PASSWORD",
        "PGADMIN_PASSWORD",
        "GRAFANA_ADMIN_PASSWORD",
        "UPTIME_KUMA_PASSWORD",
        "TRAEFIK_BASIC_AUTH",
        "CODE_SERVER_PASSWORD",
        "CODE_SERVER_SUDO_PASSWORD",
        "RESTIC_REPOSITORY",
        "RESTIC_PASSWORD",
    ]

    for secret_name in upload_names:
        put_secret(token, key_id, public_key_b64, secret_name, values[secret_name])
        print(f"Uploaded GitHub secret: {secret_name}")

    summary_path = REPO_ROOT / "secrets-bootstrap-summary.txt"
    summary_path.write_text(
        "\n".join(
            [
                f"Repository: {OWNER}/{REPO}",
                f"TF vars file: {TFVARS_PATH}",
                f"SSH public key: {SSH_PUBLIC_KEY_PATH}",
                f"SSH private key: {SSH_PRIVATE_KEY_PATH}",
                "",
                "Service endpoints root:",
                f"- 9route: https://9route.{ROOT_DOMAIN}",
                f"- Grafana: https://grafana.{ROOT_DOMAIN}",
                f"- VS Code Server: https://code.{ROOT_DOMAIN}",
                f"- Prometheus: https://prometheus.{ROOT_DOMAIN}",
                f"- Loki: https://logs.{ROOT_DOMAIN}",
                "",
                "The plain Traefik admin password used to generate TRAEFIK_BASIC_AUTH is:",
                values["TRAEFIK_BASIC_AUTH_PASSWORD"],
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()
