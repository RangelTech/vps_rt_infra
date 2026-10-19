#!/usr/bin/env bash
# Aplica as cotas de disco dos workspaces (spec 04 / 10 A-9). Roda como root no host.
#  - le  /var/lib/docker/volumes/runtime-manager_rmdata/_data/quota/limits.json (escrito pelo RM)
#  - aplica projeto XFS por tenant (xfs_quota) em /srv/rt/tenants
#  - publica usage.json (uso real por tenant) no mesmo diretorio
# Idempotente. Dispara por rt-quota.path (mudanca de limites) e rt-quota.timer (medicao, 1 min).
set -euo pipefail
DIR="${RT_QUOTA_DIR:-/var/lib/docker/volumes/runtime-manager_rmdata/_data/quota}"
MOUNT="${RT_QUOTA_MOUNT:-/srv/rt/tenants}"
[ -f "$DIR/limits.json" ] || exit 0
findmnt -n -t xfs "$MOUNT" >/dev/null || { echo "rt-quota: $MOUNT nao e XFS" >&2; exit 1; }
touch /etc/projects /etc/projid
python3 - "$DIR/limits.json" "$MOUNT" <<'PY'
import json, subprocess, sys
limits = json.load(open(sys.argv[1])); mount = sys.argv[2]
projects = open("/etc/projects").read().splitlines(); projid = open("/etc/projid").read().splitlines()
def ensure(lines, line, path):
    if line not in lines:
        with open(path, "a") as f: f.write(line + "\n")
        lines.append(line)
for i, (t, v) in enumerate(sorted(limits.items())):
    pid = 100000 + (abs(hash_t := sum(map(ord, t)) * 131) % 800000)
    name = f"rt_{t}"
    ensure(projects, f"{pid}:{v['path']}", "/etc/projects")
    ensure(projid, f"{name}:{pid}", "/etc/projid")
    for cmd in (f"project -s -p {v['path']} {name}", f"limit -p bhard={int(v['gb'])}g {name}"):
        subprocess.run(["xfs_quota", "-x", "-c", cmd, mount], check=True, capture_output=True)
PY
# uso por tenant (blocos de 1K)
xfs_quota -x -c 'report -p -N -b' "$MOUNT" | python3 -c '
import json, sys
out = {}
for ln in sys.stdin:
    p = ln.split()
    if len(p) >= 4 and p[0].startswith("rt_"):
        out[p[0][3:]] = {"used": int(p[1]) * 1024, "hard": int(p[3]) * 1024}
json.dump(out, open("'"$DIR"'/usage.json.tmp", "w"))' && mv -f "$DIR/usage.json.tmp" "$DIR/usage.json"
