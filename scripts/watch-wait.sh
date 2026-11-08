#!/usr/bin/env bash
# Block until the human repo has changed since the last checkpoint and then stayed quiet. Prints the changed paths
# and exits 0. Watch mode runs this under Monitor.
#
#   scripts/watch-wait.sh <state-file> <quiet-seconds>
#
# HUMAN_REPO comes from project.env. In a git repo the snapshot hashes the content of every tracked and untracked
# (not ignored) file; outside git it lists every file with its mtime. The state file holds the last snapshot.
set -euo pipefail

# shellcheck source=lib/env.sh
source "$(dirname "$0")/lib/env.sh"
(( $# == 2 )) || { sed -n 5p "$0" >&2; exit 2; }
state=$1 quiet=$2
[[ $quiet =~ ^[0-9]+$ ]] || { echo "watch-wait: quiet-seconds must be a whole number" >&2; exit 2; }
[[ -d $HUMAN_REPO ]] || { echo "watch-wait: HUMAN_REPO $HUMAN_REPO is not a directory" >&2; exit 2; }

snapshot() {
    if git -C "$HUMAN_REPO" rev-parse --git-dir > /dev/null 2>&1; then
        git -C "$HUMAN_REPO" ls-files -co --exclude-standard -z \
            | (cd "$HUMAN_REPO" && xargs -0 -r sha1sum 2> /dev/null || true) \
            | sed -E 's/^([0-9a-f]+)  (.*)$/\2\t\1/'
    else
        (cd "$HUMAN_REPO" && find . -type f -printf '%P\t%T@\n' | sort)
    fi
}

last=$(cat "$state" 2> /dev/null || true)
prev=
stable_since=0
while true; do
    now=$(snapshot)
    if [[ $now != "$prev" ]]; then
        prev=$now
        stable_since=$(date +%s)
    elif [[ $now != "$last" ]] && (( $(date +%s) - stable_since >= quiet )); then
        { diff <(echo "$last") <(echo "$now") || true; } | sed -nE 's/^[<>] ([^\t]*)\t.*/\1/p' | sort -u
        printf '%s' "$now" > "$state"
        exit 0
    fi
    sleep 5
done
