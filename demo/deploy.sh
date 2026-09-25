#!/usr/bin/env bash
# Runs on the VPS (invoked over SSH by .github/workflows/deploy-demo.yml).
#
# Clones/updates the public repo distributed-agent-runtime-lab at a pinned
# ref into /opt/demo/runtime-lab, patches its public-demo nginx to join this
# VPS's existing Traefik instead of publishing its own 80/443 (which Traefik
# already owns), downloads the pinned public education Kaggle release once,
# and brings the profile up as its own Compose project. It never touches
# /opt/platform (the production stack) or any of its containers.
set -euo pipefail

DEMO_ROOT=/opt/demo
INFRA_DIR=/opt/demo-infra
REPO_URL=https://github.com/LucasRangelSSouza/distributed-agent-runtime-lab.git
REF="${RUNTIME_LAB_REF:?RUNTIME_LAB_REF is required}"
ROOT_DOMAIN="${ROOT_DOMAIN:-rangeltech.net}"

mkdir -p "$DEMO_ROOT"
if [ -d "$DEMO_ROOT/runtime-lab/.git" ]; then
  git -C "$DEMO_ROOT/runtime-lab" fetch --tags --force origin
else
  git clone "$REPO_URL" "$DEMO_ROOT/runtime-lab"
fi
git -C "$DEMO_ROOT/runtime-lab" checkout --force "$REF"
cd "$DEMO_ROOT/runtime-lab"

# Ubuntu 24.04 marks the system Python as externally managed (PEP 668); a
# dedicated venv avoids fighting that instead of overriding it.
VENV=/opt/demo/.venv
if [ ! -x "$VENV/bin/python3" ]; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3-venv
  python3 -m venv "$VENV"
fi
"$VENV/bin/pip" install --quiet pyyaml kagglehub
PY="$VENV/bin/python3"

# Secrets persist across deploys; only the first deploy generates them.
[ -f deploy/public-demo/.env ] || $PY scripts/public_demo_env.py
$PY scripts/public_demo_env.py --set EDUCATION_RELEASE_DIR=./data/education-release

# The compose file still bind-mounts a cert pair (nginx's own 8443 listener,
# unreachable from outside since Traefik owns public TLS); it must exist.
[ -f deploy/public-demo/certs/tls.crt ] || bash scripts/public_demo_cert.sh

# Public dataset, no credential needed; cached across deploys.
mkdir -p deploy/public-demo/data/education-release
if [ ! -f deploy/public-demo/data/education-release/release_manifest.json ]; then
  # kagglehub prints its own progress lines to stdout before the path; only
  # the last line is the actual return value (same reasoning as the seed
  # UUID capture below).
  release_dir=$($PY -c "import kagglehub; print(kagglehub.dataset_download('lucasrangelss/brazil-education-data-lake/versions/1'))" | tail -1)
  cp "$release_dir"/* deploy/public-demo/data/education-release/
fi

# The repo's own CI already runs check_public_demo_policy.py --strict-release
# against the unpatched profile before this ref is tagged. Running it again
# here, after patch_compose_for_traefik.py's deliberate change (nginx joins
# the external "public" network for Traefik), would only ever fail on that
# same intentional exception -- it is not re-run in this deploy script.

# Idempotent: no-ops if nginx is already patched.
$PY "$INFRA_DIR/patch_compose_for_traefik.py" deploy/public-demo/compose.yaml "$ROOT_DOMAIN"

# airflow's compose service has only an `image:`, no `build:` section: its
# Dockerfile (which fetches the two owner-repo DAG packages by pinned commit)
# is built out of band by scripts/build_public_demo_images.sh, matching
# exactly how the repo's own CI/local docs build it. Skip that script's other
# two images (runtime/RAG): those are now real, already-pulled GHCR images.
set -a; . deploy/public-demo/versions.env; set +a
docker image inspect "$AIRFLOW_IMAGE" >/dev/null 2>&1 || docker build --tag "$AIRFLOW_IMAGE" \
  --build-arg "AIRFLOW_IMAGE=$AIRFLOW_BASE_IMAGE" \
  --build-arg "DATA_MAP_REPO=$DATA_MAP_REPO" \
  --build-arg "DATA_MAP_COMMIT=$DATA_MAP_COMMIT" \
  --build-arg "DATA_MAP_ARCHIVE_SHA256=$DATA_MAP_ARCHIVE_SHA256" \
  --build-arg "MLOPS_REPO=$MLOPS_REPO" \
  --build-arg "MLOPS_COMMIT=$MLOPS_COMMIT" \
  --build-arg "MLOPS_ARCHIVE_SHA256=$MLOPS_ARCHIVE_SHA256" \
  deploy/public-demo/airflow

# --ignore-buildable only skips services with a `build:` section; airflow
# has none (its image is built above, out of band), so it must be excluded
# by name instead or `pull` tries to fetch it from a registry that doesn't
# have it.
pullable=$(bash scripts/public_demo.sh config --services | grep -v '^airflow$')
# This host's IPv6 route to GitHub's blob storage (ghcr.io image layers)
# resets mid-transfer often enough to need retries; each attempt resumes
# from already-downloaded layers rather than starting over.
for attempt in 1 2 3 4 5; do
  bash scripts/public_demo.sh pull $pullable && break
  [ "$attempt" = 5 ] && exit 1
  sleep 10
done
bash scripts/public_demo.sh up -d

# Metabase seed is idempotent by object name (see seed_metabase.py); safe to
# always run. Only touch nginx if the dashboard UUID actually changed.
seed_output=$(bash scripts/public_demo.sh --profile seed run --rm metabase-seed)
uuid=$(printf '%s' "$seed_output" | tail -1 | $PY -c "import json,sys; print(json.load(sys.stdin)['public_uuid'])")
current_uuid=$(grep '^PUBLIC_DASHBOARD_UUID=' deploy/public-demo/.env | cut -d= -f2)
if [ "$uuid" != "$current_uuid" ]; then
  $PY scripts/public_demo_env.py --set "PUBLIC_DASHBOARD_UUID=$uuid"
  bash scripts/public_demo.sh up -d nginx
fi

echo "deployed: https://demo.${ROOT_DOMAIN}/ , dashboard UUID $uuid"
