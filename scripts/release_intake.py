#!/usr/bin/env python3
"""Le o ultimo release de cada fonte permitida (releases/sources.json), valida o manifesto e grava releases/<servico>.lock.

Valida: remetente (repo exato), schema, servico, campos do artefato, existencia do asset na release, sha256 hex, image_id.
Saida: imprime os servicos atualizados (um por linha) e escreve em $GITHUB_OUTPUT `updated=<lista>`.
Nao faz deploy; o workflow deploy.yml faz.
"""
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN = os.environ.get("GITHUB_TOKEN", "")


def gh(url, accept="application/vnd.github+json"):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "rt-release-intake"})
    if TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)
    return urllib.request.urlopen(req, timeout=60)


def read_lock(path):
    d = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            if "=" in line:
                k, v = line.rstrip("\n").split("=", 1)
                d[k] = v
    return d


def main():
    src = json.load(open(os.path.join(ROOT, "releases", "sources.json"), encoding="utf-8"))["sources"]
    updated = []
    for s in src:
        repo, svc = s["repo"], s["service"]
        try:
            rel = json.load(gh(f"https://api.github.com/repos/{repo}/releases/latest"))
        except Exception as e:  # sem release ainda
            print(f"[{svc}] sem release: {e}")
            continue
        assets = {a["name"]: a for a in rel.get("assets", [])}
        if "release-manifest.json" not in assets:
            print(f"[{svc}] release {rel['tag_name']} sem release-manifest.json - ignorado")
            continue
        m = json.load(gh(assets["release-manifest.json"]["browser_download_url"], "application/octet-stream"))
        # --- validacao
        assert m.get("schema") == 1, "schema invalido"
        assert m.get("repo") == repo, f"repo do manifesto ({m.get('repo')}) != fonte permitida ({repo})"
        assert m.get("service") == svc, "servico do manifesto diferente da fonte"
        art = m.get("artifact") or {}
        assert art.get("type") == "docker-archive", "artefato nao suportado"
        assert re.fullmatch(r"[0-9a-f]{64}", art.get("sha256", "")), "sha256 invalido"
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", art.get("image_id", "")), "image_id invalido"
        assert art.get("asset") in assets, "asset do artefato ausente na release"
        assert m.get("version") == rel["tag_name"], "versao do manifesto != tag da release"
        lock_path = os.path.join(ROOT, "releases", f"{svc}.lock")
        cur = read_lock(lock_path)
        if cur.get("image_id") == art["image_id"]:
            print(f"[{svc}] ja esta em {m['version']} ({art['image_id'][7:19]})")
            continue
        lines = {
            "service": svc,
            "stack": s["stack"],
            "compose_service": s.get("compose_service", svc),
            "layer": s.get("layer", "A"),
            "repo": repo,
            "version": m["version"],
            "commit": m["commit"],
            "artifact_url": assets[art["asset"]]["browser_download_url"],
            "artifact_sha256": art["sha256"],
            "image_id": art["image_id"],
            "manifest_version": str(m["schema"]),
            "previous_version": cur.get("version", ""),
            "previous_image_id": cur.get("image_id", ""),
        }
        with open(lock_path, "w", encoding="utf-8", newline="\n") as fh:
            for k, v in lines.items():
                fh.write(f"{k}={v}\n")
        print(f"[{svc}] atualizado: {cur.get('version', '-')} -> {m['version']}")
        updated.append(svc)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write("updated=" + " ".join(updated) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
