#!/bin/bash
# Writes the release's versions to $GITHUB_OUTPUT: `arcomium` (the tag without
# its v, or arcomium/VERSION when the run is not for a tag) and `chromium`.
#
# A release tag is vMAJOR.MINOR.PATCH. MAJOR.MINOR must be arcomium/VERSION's
# and PATCH no lower than its: VERSION names the core release the submodule
# is on, and the platform repositories may tag patch releases on top of it
# (packaging, CI, a newer ungoogled-chromium) without a new core version.
#
#   release-version.sh <chromium_version.txt>
set -euo pipefail

fail() {
  echo "::error::$1"
  exit 1
}

semver='^v([0-9]+)\.([0-9]+)\.([0-9]+)$'
core="$(tr -d '[:space:]' < arcomium/VERSION)"
chromium="$(tr -d '[:space:]' < "$1")"
[[ "v$core" =~ $semver ]] || fail "arcomium/VERSION is '$core', not MAJOR.MINOR.PATCH."
core_major=${BASH_REMATCH[1]} core_minor=${BASH_REMATCH[2]} core_patch=${BASH_REMATCH[3]}

version="$core"
if [ "${GITHUB_REF_TYPE:-}" = tag ]; then
  tag="$GITHUB_REF_NAME"
  [[ "$tag" =~ $semver ]] || fail "Tag $tag is not vMAJOR.MINOR.PATCH."
  if [ "$((10#${BASH_REMATCH[1]}))" -ne "$((10#$core_major))" ] ||
     [ "$((10#${BASH_REMATCH[2]}))" -ne "$((10#$core_minor))" ] ||
     [ "$((10#${BASH_REMATCH[3]}))" -lt "$((10#$core_patch))" ]; then
    fail "Tag $tag does not match arcomium/VERSION $core: it must be v$core_major.$core_minor.N with N >= $core_patch. Bump the arcomium submodule or fix the tag."
  fi
  version="${tag#v}"
fi

echo "Arcomium $version (arcomium/VERSION $core), Chromium $chromium"
{
  echo "arcomium=$version"
  echo "chromium=$chromium"
} >> "$GITHUB_OUTPUT"
