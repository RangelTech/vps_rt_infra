#!/usr/bin/env bash
# Prova (spec 57 §8.6/§8.7) de que os buckets do MinIO voltam do backup: restaura data/minio do último snapshot restic numa
# pasta temporária, sobe um MinIO descartável em cima dela e compara, bucket a bucket, objetos e bytes com o MinIO oficial.
# Somente leitura no repositório de backup e no MinIO oficial. Roda na VPS como root.
set -euo pipefail
[ "$(hostname)" = "vmi3468840" ] || { echo "host inesperado" >&2; exit 2; }
SEC=/opt/platform/secrets
set -a; . "$SEC/restic.env"; set +a
export RCLONE_CONFIG="$SEC/rclone.conf"
W="$(mktemp -d /opt/platform/data/restore-minio.XXXX)"
trap 'docker rm -f minio-restaurado >/dev/null 2>&1 || true; rm -rf "$W"' EXIT
SNAP="$(restic snapshots --json --latest 1 | python3 -c 'import sys,json; s=json.load(sys.stdin); print(s[-1]["short_id"], s[-1]["time"][:19])')"
echo "snapshot: $SNAP"
restic restore "${SNAP%% *}" --target "$W" --include /opt/platform/data/minio >/dev/null
RU="$(docker exec minio printenv MINIO_ROOT_USER)"; RP="$(docker exec minio printenv MINIO_ROOT_PASSWORD)"
docker run -d --name minio-restaurado --network internal -e MINIO_ROOT_USER="$RU" -e MINIO_ROOT_PASSWORD="$RP" \
  -v "$W/opt/platform/data/minio":/data quay.io/minio/minio:RELEASE.2024-10-13T13-34-11Z server /data >/dev/null
sleep 8
contar_mc() {
  docker exec minio sh -c "mc alias set c http://$1:9000 '$RU' '$RP' >/dev/null && mc du --depth 2 c; mc alias rm c >/dev/null" | tr '\t' ' '
}
contar_mc 127.0.0.1 | sort > "$W/oficial.txt"
contar_mc minio-restaurado | sort > "$W/restaurado.txt"
echo "== oficial";    cat "$W/oficial.txt"
echo "== restaurado"; cat "$W/restaurado.txt"
if diff -q "$W/oficial.txt" "$W/restaurado.txt" >/dev/null; then echo "RESULTADO: IGUAL"; else echo "RESULTADO: DIFERENTE"; diff "$W/oficial.txt" "$W/restaurado.txt" || true; fi
