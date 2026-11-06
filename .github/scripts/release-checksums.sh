#!/bin/bash
# Rewrites SHA256SUMS of a GitHub release from all of its assets, so it stays
# complete as each architecture adds its packages. It takes each asset's SHA-256
# from the digest GitHub computed on upload and downloads only an asset that has
# none. A local copy of an asset in DIR must match that digest.
#
#   release-checksums.sh <tag> <dir>     # needs GH_TOKEN and GH_REPO
set -euo pipefail

tag="$1"
dir="$2"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

gh api "repos/$GH_REPO/releases/tags/$tag" \
    --jq '.assets[] | select(.name != "SHA256SUMS") | [.name, (.digest // "")] | @tsv' \
    > "$work/assets"
[ -s "$work/assets" ] || { echo "::error::Release $tag has no assets."; exit 1; }

while IFS=$'\t' read -r name digest; do
  sum="${digest#sha256:}"
  if [ -z "$digest" ] || [ "$sum" = "$digest" ]; then
    echo "No SHA-256 digest for $name; downloading it." >&2
    gh release download "$tag" --pattern "$name" --dir "$work/download" --clobber >&2
    sum="$(sha256sum "$work/download/$name" | cut -d' ' -f1)"
    rm -f "$work/download/$name"
  fi
  if [ -f "$dir/$name" ]; then
    local_sum="$(sha256sum "$dir/$name" | cut -d' ' -f1)"
    if [ "$local_sum" != "$sum" ]; then
      echo "::error::$name on the release does not match the file uploaded ($sum, $local_sum)." >&2
      exit 1
    fi
  fi
  printf '%s  %s\n' "$sum" "$name"
done < "$work/assets" | sort -k2 > "$work/SHA256SUMS"

cat "$work/SHA256SUMS"
gh release upload "$tag" "$work/SHA256SUMS" --clobber
