#!/usr/bin/env bash
# Resolve o digest de cada imagem de stacks/canais/versions.env e substitui o marcador DIGEST_A_PREENCHER.
# Le SOMENTE o manifesto no registro (docker buildx imagetools inspect / skopeo); nao baixa camadas, nao inicia nada.
# Uso: scripts/resolve_digests.sh [--check]   (--check: so lista o que falta, nao grava)
# Revisar o diff do versions.env antes de commitar. O digest e o da LISTA de manifestos (multi-arch), como o registro publica.
set -euo pipefail
F="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/stacks/canais/versions.env"; CHECK=0; [ "${1:-}" = "--check" ] && CHECK=1
digest_of() {
  local ref="$1"
  if command -v skopeo >/dev/null; then skopeo inspect --raw "docker://$ref" >/dev/null && skopeo inspect --format '{{.Digest}}' "docker://$ref"
  else docker buildx imagetools inspect "$ref" --format '{{json .Manifest.Digest}}' | tr -d '"'; fi
}
rc=0; TMP="$(mktemp)"
while IFS= read -r line; do
  case "$line" in
    '#'*) echo "$line" >> "$TMP";;
    *DIGEST_A_PREENCHER*)
      key="${line%%=*}"; val="${line#*=}"; base="${val%%@*}"
      if [ "$CHECK" = 1 ]; then echo "pendente: $key ($base)"; echo "$line" >> "$TMP"; continue; fi
      if d="$(digest_of "$base")" && [[ "$d" =~ ^sha256:[0-9a-f]{64}$ ]]; then echo "$key=$base@$d" >> "$TMP"; echo "ok  $key -> $d" >&2
      else echo "FALHA: $key ($base) - tag inexistente ou registro inacessivel" >&2; echo "$line" >> "$TMP"; rc=1; fi;;
    *) echo "$line" >> "$TMP";;
  esac
done < "$F"
[ "$CHECK" = 1 ] || cp "$TMP" "$F"; rm -f "$TMP"
grep -q DIGEST_A_PREENCHER "$F" && echo "ainda ha marcadores em $F" >&2
exit $rc
