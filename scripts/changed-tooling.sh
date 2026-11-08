#!/usr/bin/env bash
# Did this session change bot tooling? `finish` runs scripts/check-tooling.sh only when it did.
#
#   scripts/changed-tooling.sh <base-ref>
#
# Exit 0 when scripts/, .claude/ or project.env differ from <base-ref> (committed since, staged, unstaged or untracked),
# printing the changed paths; exit 1 when none do; 2 on a bad ref or usage.
set -euo pipefail

(( $# == 1 )) || { sed -n 4p "$0" >&2; exit 2; }
cd "$(dirname "$0")/.."
git rev-parse --verify -q "$1^{commit}" > /dev/null || { echo "changed-tooling: $1 is not a commit here" >&2; exit 2; }
paths=(scripts .claude project.env)
changed=$( { git diff --name-only "$1" -- "${paths[@]}"
             git ls-files --others --exclude-standard -- "${paths[@]}"; } | sort -u)
[[ -n $changed ]] || exit 1
echo "$changed"
