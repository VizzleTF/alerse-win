#!/bin/bash
# Opens an issue when the upstream platform repository has released a newer
# Chromium than its submodule here is on, so security fixes do not wait for
# someone to look. One issue per upstream release: it is not opened again,
# even after it is closed.
#
#   check-upstream.sh <submodule> <owner/upstream-repo>   # needs GH_TOKEN and GH_REPO
set -euo pipefail

submodule="$1"
upstream="$2"

ours="$(tr -d '[:space:]' < "$submodule/ungoogled-chromium/chromium_version.txt")"
tag="$(gh api "repos/$upstream/releases/latest" --jq .tag_name)"
theirs="${tag%%-*}"
echo "$submodule: Chromium $ours; $upstream latest release: $tag"

if [ "$theirs" = "$ours" ] ||
   [ "$(printf '%s\n%s\n' "$ours" "$theirs" | sort -V | tail -1)" = "$ours" ]; then
  echo "Up to date."
  exit 0
fi

title="Update $submodule to $tag (Chromium $theirs)"
if gh issue list --state all --limit 500 --json title --jq '.[].title' | grep -Fxq "$title"; then
  echo "Issue already exists: $title"
  exit 0
fi

# Chrome's own stable version, for how far behind upstream is; optional.
stable="$(curl -fsS --max-time 20 \
    'https://versionhistory.googleapis.com/v1/chrome/platforms/win64/channels/stable/versions?pageSize=1' |
  jq -r '.versions[0].version // empty' 2>/dev/null || true)"

body="$(cat <<EOF
[$upstream $tag](https://github.com/$upstream/releases/tag/$tag) is out with Chromium $theirs; \`$submodule\` here is on Chromium $ours.${stable:+ Chrome stable is $stable.}

Chromium releases carry security fixes. To update:

1. Move the \`$submodule\` submodule to \`$tag\` and check that every patch still applies.
2. Tag a patch release (\`vX.Y.Z\`) once \`main\` builds.

Opened by the [upstream](https://github.com/$GH_REPO/actions/workflows/upstream.yml) workflow.
EOF
)"
gh issue create --title "$title" --body "$body"
