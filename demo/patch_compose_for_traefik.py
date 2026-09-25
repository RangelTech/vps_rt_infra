"""Patch the public-demo compose file so the VPS's shared Traefik can route to it.

Run against a checked-out copy of distributed-agent-runtime-lab's
deploy/public-demo/compose.yaml. The upstream repo never sees this: it stays a
plain, portable Compose profile that publishes its own ports 80/443 for a
standalone local run. On this VPS, port 80/443 already belong to the shared
Traefik (compose/docker-compose.yml, this repository), so nginx here must give
up its own host ports and join the existing external "public" Docker network
instead, picked up by Traefik's Docker provider via labels -- the same
mechanism every other service and client site on this VPS already uses.

Usage:
    python patch_compose_for_traefik.py <path-to-compose.yaml> <root-domain>

Writes the result back to the same path. Idempotent: running it twice on an
already-patched file is a no-op (detected by the traefik.enable label).
"""

from __future__ import annotations

import sys

import yaml

TRAEFIK_LABELS = [
    "traefik.enable=true",
    "traefik.docker.network=public",
    "traefik.http.routers.demo-nginx.rule=Host(`{host}`)",
    "traefik.http.routers.demo-nginx.entrypoints=websecure",
    "traefik.http.routers.demo-nginx.tls.certresolver=letsencrypt",
    "traefik.http.routers.demo-nginx.middlewares=security-headers@file",
    "traefik.http.services.demo-nginx.loadbalancer.server.port=8080",
]


def patch(path: str, root_domain: str) -> None:
    with open(path, encoding="utf-8") as handle:
        doc = yaml.safe_load(handle)

    nginx = doc["services"]["nginx"]
    if any(str(label).startswith("traefik.enable") for label in nginx.get("labels", [])):
        print("already patched; no-op")
        return

    nginx.pop("ports", None)
    nginx["networks"] = sorted(set(nginx.get("networks", [])) | {"public"})
    nginx["labels"] = list(nginx.get("labels", [])) + [
        label.format(host=f"demo.{root_domain}") for label in TRAEFIK_LABELS
    ]

    doc.setdefault("networks", {})["public"] = {"external": True, "name": "public"}

    with open(path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(doc, handle, sort_keys=False, default_flow_style=False)
    print(f"patched {path}: nginx now joins the external 'public' network, routed as demo.{root_domain}, no published ports")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: patch_compose_for_traefik.py <compose.yaml> <root-domain>")
    patch(sys.argv[1], sys.argv[2])
