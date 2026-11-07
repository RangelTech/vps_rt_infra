#!/usr/bin/env python3
"""Resolve, NA HORA DO DEPLOY, a release de UM servico: le o repo da fonte (releases/sources.json), valida o manifesto e grava releases/<servico>.lock.

Uso: resolve_release.py <servico> [--version vX.Y.Z]   (sem --version: a release mais recente nao-rascunho)
Valida: remetente (repo exato), schema, servico, campos do artefato, existencia do asset na release, sha256 hex, image_id.
Saida: imprime o resultado e escreve em $GITHUB_OUTPUT `version=` e `changed=true|false`.
Nao faz deploy; o deploy.yml faz. Nao ha mais robo periodico: o botao de deploy busca a release quando e acionado.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN = os.environ.get("GITHUB_TOKEN", "")


def gh(url, accept="application/vnd.github+json"):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "rt-resolve-release"})
    if TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)
    for tentativa in range(4):
        try:
            return urllib.request.urlopen(req, timeout=60)
        except urllib.error.HTTPError:
            raise
        except urllib.error.URLError:
            if tentativa == 3:
                raise
            time.sleep(2 * (tentativa + 1))


def read_lock(path):
    d = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            if "=" in line:
                k, v = line.rstrip("\n").split("=", 1)
                d[k] = v
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("service")
    ap.add_argument("--version", default="")
    args = ap.parse_args()
    svc = args.service
    if not re.fullmatch(r"[a-z0-9-]+", svc):
        print("servico invalido")
        return 2
    if args.version and not re.fullmatch(r"[A-Za-z0-9._-]{1,40}", args.version):
        print("versao invalida")
        return 2
    src = {s["service"]: s for s in json.load(open(os.path.join(ROOT, "releases", "sources.json"), encoding="utf-8"))["sources"]}
    if svc not in src:
        print(f"[{svc}] nao esta em releases/sources.json")
        return 2
    s = src[svc]
    repo = s["repo"]
    if args.version:
        rel = json.load(gh(f"https://api.github.com/repos/{repo}/releases/tags/{args.version}"))
    else:
        lista = json.load(gh(f"https://api.github.com/repos/{repo}/releases?per_page=20"))
        lista = [r for r in lista if not r.get("draft")]
        if not lista:
            print(f"[{svc}] sem release em {repo}")
            return 1
        rel = lista[0]
    assets = {a["name"]: a for a in rel.get("assets", [])}
    man_name = s.get("manifest_asset", "release-manifest.json")
    if man_name not in assets:
        print(f"[{svc}] release {rel['tag_name']} sem {man_name}")
        return 1
    m = json.load(gh(assets[man_name]["browser_download_url"], "application/octet-stream"))
    # --- validacao
    assert m.get("schema") == 1, "schema invalido"
    # "aliases": nomes anteriores do repositorio (renomeacao): manifestos de releases antigas ainda trazem o nome antigo.
    permitidos = [repo] + list(s.get("aliases", []))
    assert m.get("repo") in permitidos, f"repo do manifesto ({m.get('repo')}) != fonte permitida ({repo})"
    assert m.get("service") == svc, "servico do manifesto diferente da fonte"
    art = m.get("artifact") or {}
    assert art.get("type") == "docker-archive", "artefato nao suportado"
    assert re.fullmatch(r"[0-9a-f]{64}", art.get("sha256", "")), "sha256 invalido"
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", art.get("image_id", "")), "image_id invalido"
    assert art.get("asset") in assets, "asset do artefato ausente na release"
    assert m.get("version") == rel["tag_name"], "versao do manifesto != tag da release"
    lock_path = os.path.join(ROOT, "releases", f"{svc}.lock")
    cur = read_lock(lock_path)
    changed = cur.get("image_id") != art["image_id"]
    if changed:
        lines = {
            "service": svc,
            "stack": s["stack"],
            "compose_service": s.get("compose_service", svc),
            "image_only": "true" if s.get("image_only") else "",
            "layer": s.get("layer", "B"),
            "repo": repo,
            "version": m["version"],
            "commit": m["commit"],
            "artifact_url": assets[art["asset"]]["browser_download_url"],
            "artifact_sha256": art["sha256"],
            "image_id": art["image_id"],
            "manifest_version": str(m["schema"]),
            "pre_deploy_service": (m.get("pre_deploy") or {}).get("compose_service", ""),
            "healthcheck_timeout": str((m.get("healthcheck") or {}).get("timeout_s", 90)),
            "env_required": ",".join((m.get("env") or {}).get("required", [])),
            "previous_version": cur.get("version", ""),
            "previous_image_id": cur.get("image_id", ""),
        }
        with open(lock_path, "w", encoding="utf-8", newline="\n") as fh:
            for k, v in lines.items():
                fh.write(f"{k}={v}\n")
        print(f"[{svc}] {cur.get('version', '-')} -> {m['version']} (resolvida agora)")
    else:
        print(f"[{svc}] ja esta em {m['version']} ({art['image_id'][7:19]}); nada novo para buscar")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"version={m['version']}\nchanged={'true' if changed else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
