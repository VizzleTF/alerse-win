#!/bin/bash
# Writes the release's versions to $GITHUB_OUTPUT: `arcomium` (arcomium/VERSION)
# and `chromium`.
#
# A release tag is v + arcomium/VERSION: tools/rename_product.py builds that
# version into the browser (its update check compares it with the latest
# release's tag) and into Chromium's version number (PATCH x 100 + Arcomium's
# PATCH, see arcomium/docs/versioning.md), so a release of the platform alone
# raises VERSION too. That number must also be above the latest release's, or
# the Windows installer would not install over it: a release on the same
# Chromium cannot lower Arcomium's PATCH (0.1.7 is followed by 0.2.8, not
# 0.2.0). The latest release is read with gh (GH_TOKEN, GH_REPO).
#
#   release-version.sh <chromium_version.txt>
set -euo pipefail

fail() {
  echo "::error::$1"
  exit 1
}

semver='^v([0-9]+)\.([0-9]+)\.([0-9]+)$'
chromium_re='^([0-9]+)\.([0-9]+)\.([0-9]+)\.([0-9]+)$'
core="$(tr -d '[:space:]' < arcomium/VERSION)"
chromium="$(tr -d '[:space:]' < "$1")"
[[ "v$core" =~ $semver ]] || fail "arcomium/VERSION is '$core', not MAJOR.MINOR.PATCH."
core_patch=${BASH_REMATCH[3]}

# Sets $stamp to the browser's Chromium version: Chromium's $1 with
# Arcomium's PATCH $2 stamped in.
stamp() {
  [[ "$1" =~ $chromium_re ]] || fail "'$1' is not a Chromium version."
  stamp="$((10#${BASH_REMATCH[1]})).$((10#${BASH_REMATCH[2]})).$((10#${BASH_REMATCH[3]}))"
  stamp+=".$((10#${BASH_REMATCH[4]} * 100 + 10#$2))"
}

# Whether Chromium version $1 is above $2.
newer() {
  local IFS=.
  local -a a=($1) b=($2)
  for i in 0 1 2 3; do
    [ "${a[i]}" -ne "${b[i]}" ] && { [ "${a[i]}" -gt "${b[i]}" ]; return; }
  done
  return 1
}

if [ "${GITHUB_REF_TYPE:-}" = tag ]; then
  tag="$GITHUB_REF_NAME"
  [ "$tag" = "v$core" ] ||
    fail "Tag $tag is not v$core, v + arcomium/VERSION. Bump the arcomium submodule or fix the tag."
  stamp "$chromium" "$core_patch"
  ours="$stamp"
  err="$(mktemp)"
  if latest="$(gh api "repos/$GH_REPO/releases/latest" \
      --jq '.tag_name + " " + .body' 2> "$err")"; then
    latest_tag="${latest%% *}"
    if [ "$latest_tag" != "$tag" ]; then
      [[ "$latest_tag" =~ $semver ]] ||
        fail "The latest release's tag $latest_tag is not vMAJOR.MINOR.PATCH."
      latest_patch=${BASH_REMATCH[3]}
      latest_chromium="$(grep -oE 'Chromium [0-9]+(\.[0-9]+){3}' <<< "$latest" |
        head -n 1 | cut -d' ' -f2)"
      [ -n "$latest_chromium" ] ||
        fail "The notes of the latest release, $latest_tag, name no Chromium version."
      stamp "$latest_chromium" "$latest_patch"
      theirs="$stamp"
      newer "$ours" "$theirs" ||
        fail "$tag on Chromium $chromium is $ours, not above $theirs of $latest_tag on Chromium $latest_chromium: the installer would not update it. Raise Arcomium's PATCH above $latest_patch."
      echo "Chromium version $ours, above $theirs of $latest_tag."
    fi
  elif grep -q 'HTTP 404' "$err"; then
    echo "No release yet."
  else
    cat "$err"
    fail "Could not read the latest release."
  fi
  rm -f "$err"
fi

echo "Arcomium $core, Chromium $chromium"
{
  echo "arcomium=$core"
  echo "chromium=$chromium"
} >> "$GITHUB_OUTPUT"
