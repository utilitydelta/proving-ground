#!/usr/bin/env bash
# The push `finish` uses: refuses while the remote is the template this repo came from, then runs git push.
#
#   scripts/push.sh [--template] [git push args...]
#
# A clone pushed to TEMPLATE_ORIGIN (project.env) would publish the adopting project's sessions, registers and paths
# into the public template. Refused, exit 2, until origin points at the project's own repo. --template is for
# maintaining the template itself and pushes anyway. The remote judged is the first non-option argument, else origin.
set -euo pipefail

# shellcheck source=lib/env.sh
source "$(dirname "$0")/lib/env.sh"
template=0
[[ ${1:-} == --template ]] && { template=1; shift; }
remote=origin
for arg in "$@"; do [[ $arg == -* ]] || { remote=$arg; break; }; done
url=$(git -C "$ROOT" remote get-url "$remote" 2> /dev/null || true)
slug=${TEMPLATE_ORIGIN:-}
slug=${slug%/}
if (( ! template )) && [[ -n $slug && -n $url ]] && [[ $url =~ [:/]${slug//./\\.}(\.git)?/?$ ]]; then
    echo "push: refused, $remote is $url, the template (TEMPLATE_ORIGIN=$slug in project.env)." >&2
    echo "push: point it at the project's own repo: git remote set-url $remote <url>. Template maintainers: --template." >&2
    exit 2
fi
exec git -C "$ROOT" push "$@"
