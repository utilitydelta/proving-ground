#!/usr/bin/env bash
# Create the next session folder with its skeleton.
#
#   scripts/new-session.sh <mode> <slug>
#
# Modes (AGENTS.md): watch task factory tend debrief closeoff invariant. N is the highest existing session-vN plus one.
# Writes goal.md, log.md, human.md, report.md, findings/ and scratch/ (gitignored). Factory mode adds what
# scripts/factory.sh and the factory skill read: session-state.md, progress.md, units/ and jobs/{pending,running,done}/.
# Prints the folder.
set -euo pipefail

# shellcheck source=lib/env.sh
source "$(dirname "$0")/lib/env.sh"
modes=(watch task factory tend debrief closeoff invariant)
(( $# == 2 )) || { sed -n 4p "$0" >&2; exit 2; }
mode=$1 slug=$2
[[ " ${modes[*]} " == *" $mode "* ]] || { echo "new-session: mode must be one of: ${modes[*]}" >&2; exit 2; }
[[ $slug =~ ^[a-z0-9][a-z0-9-]*$ ]] || { echo "new-session: slug must be lower-case words joined by -" >&2; exit 2; }

sessions=$ROOT/sessions
mkdir -p "$sessions"
highest=$(find "$sessions" -maxdepth 1 -type d -name 'session-v*' -printf '%f\n' \
    | sed -nE 's/^session-v([0-9]+)-.*/\1/p' | sort -n | tail -1)
n=$(( ${highest:-0} + 1 ))
dir=$sessions/session-v$n-$mode-$slug
# mkdir without -p fails if a parallel run took the same N.
mkdir "$dir"
mkdir "$dir/findings" "$dir/scratch"
echo "# Goal: $slug" > "$dir/goal.md"
echo "# Log: session-v$n" > "$dir/log.md"
echo "# Human: session-v$n" > "$dir/human.md"
echo "# Report: session-v$n" > "$dir/report.md"

if [[ $mode == factory ]]; then
    head_of() { [[ -n $1 ]] && git -C "$1" rev-parse --short HEAD 2> /dev/null || echo none; }
    cat > "$dir/session-state.md" <<EOF
Status: building
human head: $(head_of "$HUMAN_REPO")
lead head: $(head_of "${LEAD_REPO:-}")

## Queue

## Waiting

## Done
EOF
    echo "# Progress: session-v$n" > "$dir/progress.md"
    mkdir -p "$dir/units" "$dir/jobs/pending" "$dir/jobs/running" "$dir/jobs/done"
fi
echo "$dir"
