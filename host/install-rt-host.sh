#!/usr/bin/env bash
# Prepara o host para cota XFS real e firewall do runtime-manager. Idempotente. Roda como root.
#  1) imagem XFS esparsa montada em /srv/rt/tenants com prjquota (migra os dados existentes);
#  2) instala rt-quota.* e rt-nft.* (systemd) e o aplicador de cota.
set -euo pipefail
IMG="${RT_XFS_IMG:-/srv/rt-xfs/tenants.img}"; SIZE="${RT_XFS_SIZE:-150G}"; MNT=/srv/rt/tenants
HERE="$(cd "$(dirname "$0")" && pwd)"
install -d /srv/rt-xfs /var/lib/docker/volumes/runtime-manager_rmdata/_data/nft /var/lib/docker/volumes/runtime-manager_rmdata/_data/quota
if ! findmnt -n -t xfs "$MNT" >/dev/null; then
  [ -f "$IMG" ] || { truncate -s "$SIZE" "$IMG"; mkfs.xfs -q "$IMG"; }
  # dados existentes: so mexe com os workspaces parados (o chamador garante)
  if [ -d "$MNT" ] && [ "$(ls -A "$MNT" 2>/dev/null | wc -l)" -gt 0 ]; then mv "$MNT" "${MNT}.pre-xfs"; fi
  mkdir -p "$MNT"
  grep -q "$IMG" /etc/fstab || echo "$IMG $MNT xfs loop,prjquota,nofail 0 0" >> /etc/fstab
  mount "$MNT"
  [ -d "${MNT}.pre-xfs" ] && cp -a "${MNT}.pre-xfs/." "$MNT/"
fi
install -m 0755 "$HERE/rt-quota-apply.sh" /opt/platform/scripts/rt-quota-apply.sh
install -m 0644 "$HERE"/rt-quota.service "$HERE"/rt-quota.path "$HERE"/rt-quota.timer "$HERE"/rt-nft.service "$HERE"/rt-nft.path /etc/systemd/system/
# O ruleset do RM inclui `table bridge rt_br` (isolamento entre workspaces na rt-ssh, sem br_netfilter).
# Se o kernel nao suporta nft na familia bridge, o `nft -f` inteiro falharia: aborta antes.
nft add table bridge rt_probe_install && nft delete table bridge rt_probe_install   || { echo "kernel sem nftables na familia bridge: o isolamento da rt-ssh nao pode ser aplicado" >&2; exit 1; }
systemctl daemon-reload
systemctl enable --now rt-quota.path rt-quota.timer rt-nft.path
findmnt -n -t xfs "$MNT" && echo "XFS montado em $MNT"
